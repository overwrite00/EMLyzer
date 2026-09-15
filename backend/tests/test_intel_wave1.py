"""
Test di regressione Wave 1 — Threat Intelligence.

Copre:
- bugfix matcher campagne (word-boundary, best-match, score_override, floor)
- fix del proxy body_hash (mega-cluster spurio)
- infrastruttura condivisa: cache, fetch, snapshot
- rate limit handler JSON
"""

import time
import threading

import pytest

from core.analysis import body_analyzer, campaign_registry
from core.analysis.body_analyzer import (
    match_campaigns, best_campaign_match, _compute_score, _severity_from_override,
    BodyFinding,
)
from core.analysis.scorer import _compute_floors


# ---------------------------------------------------------------------------
# Matcher campagne — falsi positivi noti oggi (prima del fix)
# ---------------------------------------------------------------------------

def test_word_boundary_no_false_positive_on_substring():
    """'poste' non deve scattare dentro 'imposte comunali' (substring match rimosso)."""
    matches = match_campaigns(
        text_lower="ho pagato le imposte comunali questo mese, tutto regolare",
        subject_lower="imposte comunali 2026",
    )
    ids = [m.campaign_id for m in matches]
    assert "poste-italiane-2025" not in ids


def test_legitimate_invoice_does_not_match_emotet():
    """'fattura' + 'urgente' da sole non bastano più a far scattare emotet-2025."""
    matches = match_campaigns(
        text_lower="in allegato la fattura urgente da saldare entro fine mese, grazie",
        subject_lower="fattura urgente",
    )
    ids = [m.campaign_id for m in matches]
    assert "emotet-2025" not in ids


def test_best_match_not_first_match():
    """match_campaigns ritorna tutti i match ordinati per score, non il primo per ordine dict."""
    text = "pagopa notifica pagamento avviso scadenza pagamento dovuto pagopa.it"
    matches = match_campaigns(text_lower=text, subject_lower="avviso scadenza pagamento")
    assert matches, "atteso almeno un match su pagopa-2025"
    assert matches[0].campaign_id == "pagopa-2025"
    # ordinati per score decrescente
    scores = [m.score for m in matches]
    assert scores == sorted(scores, reverse=True)


def test_sender_pattern_boosts_confidence():
    """Un sender_pattern presente nel mittente alza la confidenza a 'high'."""
    text = "inps verificare profilo spid sussidio bonus conseguenze penali"
    without_sender = best_campaign_match(text_lower=text, subject_lower="verifica profilo spid", mail_from_lower="mittente@example.com")
    with_sender = best_campaign_match(text_lower=text, subject_lower="verifica profilo spid", mail_from_lower="noreply@inps.it")
    assert without_sender is not None and with_sender is not None
    assert with_sender.confidence == "high"
    assert with_sender.score >= without_sender.score


def test_disabled_campaign_is_never_matched():
    text = "inps verificare profilo spid sussidio bonus conseguenze penali"
    registry = {
        "campaigns": [{
            "id": "inps-2024", "name": "INPS", "enabled": False,
            "keywords": ["inps", "verificare", "profilo", "spid", "sussidio", "bonus"],
            "risk_contribution": 25,
        }]
    }
    matches = match_campaigns(text_lower=text, subject_lower="", registry=registry)
    assert matches == []


# ---------------------------------------------------------------------------
# score_override / counts_toward_floor
# ---------------------------------------------------------------------------

def test_compute_score_uses_override_when_present():
    result = type("R", (), {})()
    finding_default = BodyFinding(category="text", severity="high", description="x")
    finding_override = BodyFinding(category="campaign", severity="high", description="y", score_override=25.0)
    result.findings = [finding_default, finding_override]
    score = _compute_score(result)
    assert score == 25 + 25  # weights["high"]=25 per il primo, override=25 per il secondo


def test_two_campaigns_different_risk_contribution_score_differently():
    result_a = type("R", (), {"findings": [BodyFinding(category="campaign", severity="high", description="a", score_override=25.0)]})()
    result_b = type("R", (), {"findings": [BodyFinding(category="campaign", severity="high", description="b", score_override=45.0)]})()
    assert _compute_score(result_a) != _compute_score(result_b)
    assert _compute_score(result_a) == 25
    assert _compute_score(result_b) == 45


def test_severity_from_override_thresholds():
    assert _severity_from_override(5) == "low"
    assert _severity_from_override(15) == "medium"
    assert _severity_from_override(25) == "high"


def test_low_confidence_campaign_does_not_count_toward_floor():
    """Un finding campagna a bassa confidenza non deve far scattare il floor 'high_body>=2'."""
    findings = [
        BodyFinding(category="campaign", severity="high", description="a", score_override=25.0, counts_toward_floor=False),
        BodyFinding(category="text", severity="high", description="b"),
    ]
    body_result = type("R", (), {"findings": findings})()
    floor = _compute_floors(header_result=None, body_result=body_result, url_result=None, attachment_result=None)
    # Solo 1 "high" conta verso il floor (l'altro ha counts_toward_floor=False) -> niente floor 30
    assert floor < 30.0


def test_two_full_confidence_high_findings_trigger_floor():
    findings = [
        BodyFinding(category="campaign", severity="high", description="a", score_override=25.0, counts_toward_floor=True),
        BodyFinding(category="text", severity="high", description="b"),
    ]
    body_result = type("R", (), {"findings": findings})()
    floor = _compute_floors(header_result=None, body_result=body_result, url_result=None, attachment_result=None)
    assert floor >= 30.0


# ---------------------------------------------------------------------------
# campaign_registry — reload atomico
# ---------------------------------------------------------------------------

def test_registry_reload_replaces_atomically():
    campaign_registry.reload()
    reg1 = campaign_registry.get()
    assert reg1["db"].get("campaigns")
    assert reg1["by_keywords"]
    # un secondo reload produce un nuovo oggetto, non una mutazione in-place
    campaign_registry.reload()
    reg2 = campaign_registry.get()
    assert reg1 is not reg2


# ---------------------------------------------------------------------------
# core.intel.cache
# ---------------------------------------------------------------------------

def test_cache_roundtrip_and_ttl(tmp_path, monkeypatch):
    from core.intel import cache as intel_cache
    from utils.config import settings
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path)

    assert intel_cache.load("nope") is None
    assert intel_cache.save("feedx", ["a", "b", "c"], source_url="https://example.com/feed")
    entry = intel_cache.load("feedx", ttl_hours=24)
    assert entry is not None
    assert entry.data == ["a", "b", "c"]
    assert entry.schema == intel_cache.CURRENT_SCHEMA

    # TTL scaduto (0 ore) -> None anche se il file esiste
    assert intel_cache.load("feedx", ttl_hours=0) is None
    # TTL None -> ignora l'età, sempre leggibile (fallback stale)
    assert intel_cache.load("feedx", ttl_hours=None) is not None


def test_cache_legacy_payload_without_schema_is_readable(tmp_path, monkeypatch):
    import json
    from datetime import datetime, timezone
    from core.intel import cache as intel_cache
    from utils.config import settings
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path)

    legacy_path = tmp_path / "legacy.json"
    legacy_payload = {"saved_at": datetime.now(timezone.utc).isoformat(), "data": ["x", "y"]}
    legacy_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    entry = intel_cache.load("legacy")
    assert entry is not None
    assert entry.schema == 0
    assert entry.data == ["x", "y"]


def test_cache_schema_mismatch_is_clean_miss(tmp_path, monkeypatch):
    from core.intel import cache as intel_cache
    from utils.config import settings
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path)

    intel_cache.save("versioned", ["a"], schema=1)
    assert intel_cache.load("versioned", expected_schema=2) is None
    assert intel_cache.load("versioned", expected_schema=1) is not None


def test_cache_save_failure_does_not_raise(tmp_path, monkeypatch):
    """Una directory non scrivibile non deve propagare un'eccezione: save() ritorna False."""
    from core.intel import cache as intel_cache
    from utils.config import settings
    unwritable = tmp_path / "does" / "not" / "exist_and_cannot_be_created"
    monkeypatch.setattr(settings, "CACHE_DIR", unwritable)
    monkeypatch.setattr(type(settings.CACHE_DIR), "mkdir", lambda self, **kw: (_ for _ in ()).throw(PermissionError()))
    assert intel_cache.save("x", [1, 2, 3]) is False


# ---------------------------------------------------------------------------
# core.intel.snapshot
# ---------------------------------------------------------------------------

def test_snapshot_swap_is_visible_to_readers():
    from core.intel.snapshot import Snapshot, SnapshotMeta, STATE_OK
    snap = Snapshot()
    assert snap.get() is None
    snap.swap({"n": 1}, meta=SnapshotMeta(state=STATE_OK))
    assert snap.get() == {"n": 1}
    snap.swap({"n": 2}, meta=SnapshotMeta(state=STATE_OK))
    assert snap.get() == {"n": 2}


def test_snapshot_try_begin_refresh_blocks_concurrent():
    from core.intel.snapshot import Snapshot
    snap = Snapshot()
    assert snap.try_begin_refresh() is True
    assert snap.try_begin_refresh() is False  # già in corso
    snap.end_refresh()
    assert snap.try_begin_refresh() is True


def test_snapshot_refresh_flag_auto_reclaimed_after_abandon_threshold():
    from core.intel.snapshot import Snapshot
    snap = Snapshot(refresh_abandon_after=0.05)
    assert snap.try_begin_refresh() is True
    time.sleep(0.1)
    # il flag precedente è "abbandonato": un nuovo chiamante può procedere
    assert snap.try_begin_refresh() is True


# ---------------------------------------------------------------------------
# Rate limiter — handler JSON registrato
# ---------------------------------------------------------------------------

def test_rate_limit_handler_is_registered():
    from main import app
    from slowapi.errors import RateLimitExceeded
    assert RateLimitExceeded in app.exception_handlers
