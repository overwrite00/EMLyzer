"""
Test di regressione Wave 2 — core/intel/feeds.py.

Copre il bug storico del fallback su cache stale (il verdetto deve essere
valido quando la cache stale ha dati, non un errore) e il sanity check
pre-swap (un fetch degradato non deve mai sovrascrivere una cache buona).
"""

import pytest

from core.intel import feeds as intel_feeds
from core.intel import cache as intel_cache
from core.intel import fetch as intel_fetch
from core.intel.snapshot import Snapshot, STATE_OK, STATE_STALE, STATE_UNAVAILABLE


@pytest.fixture(autouse=True)
def _isolate_feed_state(tmp_path, monkeypatch):
    """Ogni test riparte con snapshot vuoti e una CACHE_DIR isolata."""
    from utils.config import settings
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path)
    for name in intel_feeds.FEEDS:
        intel_feeds._snapshots[name] = Snapshot()
        intel_feeds._failure_streak[name] = 0
        intel_feeds._next_allowed_attempt[name] = 0.0
    yield


def test_parse_openphish_filters_malformed_lines():
    raw = b"https://evil.example/a\nnot-a-url\nhttp://evil.example/b\n\n"
    parsed = intel_feeds._parse_openphish(raw)
    assert parsed == ["https://evil.example/a", "http://evil.example/b"]


def test_parse_spamhaus_skips_invalid_cidr():
    raw = b"1.2.3.0/24 ; SBL12345\nnot-a-cidr ; comment\n; full comment line\n"
    parsed = intel_feeds._parse_spamhaus(raw)
    assert parsed == ["1.2.3.0/24"]


def test_looks_like_error_page_detects_html():
    assert intel_feeds._looks_like_error_page(b"<!DOCTYPE html><html>...")
    assert intel_feeds._looks_like_error_page(b"<html><body>captive portal</body></html>")
    assert not intel_feeds._looks_like_error_page(b"https://evil.example/a\nhttp://x")


def test_refresh_fetch_failure_falls_back_to_stale_with_valid_verdict(monkeypatch):
    """
    Bug storico: un fetch fallito con cache stale disponibile deve produrre
    uno snapshot ANCORA UTILIZZABILE (state=stale), non 'unavailable'.
    """
    spec = intel_feeds.FEEDS["openphish"]
    intel_cache.save(spec.cache_key, ["https://old-phish.example/x"], source_url=spec.url, schema=spec.cache_schema)

    def _boom(*a, **kw):
        raise intel_fetch.FetchError("connection_error", "rete non raggiungibile")
    monkeypatch.setattr(intel_fetch, "fetch_bytes", _boom)

    ok = intel_feeds.refresh("openphish", force=True)
    assert ok is True
    snap = intel_feeds.snapshot("openphish")
    assert snap.meta.state == STATE_STALE
    assert "https://old-phish.example/x" in snap.get()


def test_refresh_no_cache_no_network_is_unavailable(monkeypatch):
    def _boom(*a, **kw):
        raise intel_fetch.FetchError("connection_error", "rete non raggiungibile")
    monkeypatch.setattr(intel_fetch, "fetch_bytes", _boom)

    ok = intel_feeds.refresh("openphish", force=True)
    assert ok is False
    assert intel_feeds.snapshot("openphish").meta.state == STATE_UNAVAILABLE


def test_sanity_check_rejects_degraded_fetch_and_preserves_previous_cache(monkeypatch):
    """
    Un fetch che sembra una pagina di errore HTML non deve MAI sovrascrivere
    una cache buona esistente — altrimenti lo scheduler automatico è più
    pericoloso del lazy-load: persisterebbe il degrado a ogni tick.
    """
    spec = intel_feeds.FEEDS["openphish"]
    good_data = [f"https://evil.example/{i}" for i in range(100)]
    intel_cache.save(spec.cache_key, good_data, source_url=spec.url, schema=spec.cache_schema)

    def _fake_fetch(*a, **kw):
        return intel_fetch.FetchResult(content=b"<!DOCTYPE html><html>captive portal</html>", final_url=spec.url, status_code=200)
    monkeypatch.setattr(intel_fetch, "fetch_bytes", _fake_fetch)

    ok = intel_feeds.refresh("openphish", force=True)
    assert ok is True  # ricade sulla cache stale, che è ancora buona
    snap = intel_feeds.snapshot("openphish")
    assert len(snap.get()) == 100  # non sovrascritta con un set vuoto/degradato

    # la cache su disco non deve essere stata toccata dal fetch degradato
    reloaded = intel_cache.load(spec.cache_key, ttl_hours=None)
    assert reloaded.data == good_data


def test_sanity_check_rejects_below_min_entries(monkeypatch):
    spec = intel_feeds.FEEDS["openphish"]

    def _fake_fetch(*a, **kw):
        return intel_fetch.FetchResult(content=b"https://only-one.example/x", final_url=spec.url, status_code=200)
    monkeypatch.setattr(intel_fetch, "fetch_bytes", _fake_fetch)

    ok = intel_feeds.refresh("openphish", force=True)
    assert ok is False  # nessuna cache precedente disponibile, sotto min_entries
    assert intel_feeds.snapshot("openphish").meta.state == STATE_UNAVAILABLE


def test_successful_refresh_installs_ok_state(monkeypatch):
    spec = intel_feeds.FEEDS["openphish"]
    body = "\n".join(f"https://evil.example/{i}" for i in range(60)).encode()

    def _fake_fetch(*a, **kw):
        return intel_fetch.FetchResult(content=body, final_url=spec.url, status_code=200)
    monkeypatch.setattr(intel_fetch, "fetch_bytes", _fake_fetch)

    ok = intel_feeds.refresh("openphish", force=True)
    assert ok is True
    snap = intel_feeds.snapshot("openphish")
    assert snap.meta.state == STATE_OK
    assert "https://evil.example/0" in snap.get()


def test_cache_key_stable_for_existing_feeds():
    """I nomi file cache non devono cambiare: gli utenti hanno già questi file su disco."""
    assert intel_feeds.FEEDS["openphish"].cache_key == "openphish_feed"
    assert intel_feeds.FEEDS["spamhaus"].cache_key == "spamhaus_drop"
