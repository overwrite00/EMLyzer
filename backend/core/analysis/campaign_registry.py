"""
core/analysis/campaign_registry.py

Incapsula CAMPAIGNS_DB + CAMPAIGNS_BY_KEYWORDS (prima globali di modulo
costruite una sola volta all'import di body_analyzer.py, senza alcun modo di
ricaricarle senza riavviare l'app) dietro un core.intel.snapshot.Snapshot.

reload() costruisce ENTRAMBE le strutture in locale e le installa con un
solo swap finale — mai clear()+repopulate, che esporrebbe ai lettori
concorrenti un indice a metà popolato durante un'analisi in corso.

analyze_body deve leggere lo snapshot UNA VOLTA all'inizio e passarlo
esplicitamente a match_campaigns/best_campaign_match, non rileggere la
globale in più punti (prima il bug: `analyze_body` leggeva `CAMPAIGNS_DB`
a un punto e `_detect_campaign_match` rileggeva `CAMPAIGNS_BY_KEYWORDS` in
un altro — un reload nel mezzo produceva un'analisi con visione mista).

Wave 6 aggiungerà la fusione con backend/data/campaigns_user.json; per ora
(Wave 1/2) il registry carica solo backend/config/campaigns.json.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
import logging

from core.intel.snapshot import Snapshot, SnapshotMeta, STATE_OK, STATE_UNAVAILABLE
from utils.config import settings

logger = logging.getLogger(__name__)

_registry: Snapshot[dict] = Snapshot()

# threading.Lock, non asyncio.Lock: la scrittura di campaigns_user.json è
# I/O sincrono e veloce, eseguito direttamente nell'handler async (non in un
# executor) — un lock asyncio non offrirebbe garanzie aggiuntive qui e la
# regola di progetto è "mai un lock tenuto attraverso un await": questo lock
# non lo è mai, perché tutto il blocco protetto è sincrono.
_write_lock = threading.Lock()

_ID_RE = re.compile(r'^[a-z0-9][a-z0-9-]{2,63}$')
MAX_USER_CAMPAIGNS = 500
MAX_KEYWORDS = 40
MAX_KEYWORD_LEN = 60
MAX_SCORE_OVERRIDE = 50.0


class CampaignValidationError(ValueError):
    pass


def validate_campaign_payload(payload: dict, *, existing_ids: set[str] | None = None) -> dict:
    """
    Valida e normalizza una campagna utente prima della scrittura su disco.
    Solleva CampaignValidationError con un messaggio utilizzabile in un 422.
    """
    cid = str(payload.get("id", "")).strip().lower()
    if not _ID_RE.match(cid):
        raise CampaignValidationError("id non valido: solo minuscole/cifre/trattino, 3-64 caratteri")

    name = str(payload.get("name", "")).strip()
    if not name or len(name) > 200:
        raise CampaignValidationError("name obbligatorio, max 200 caratteri")

    keywords = payload.get("keywords") or []
    if not isinstance(keywords, list) or not keywords:
        raise CampaignValidationError("keywords: obbligatoria almeno una keyword")
    if len(keywords) > MAX_KEYWORDS:
        raise CampaignValidationError(f"keywords: massimo {MAX_KEYWORDS}")
    for kw in keywords:
        if not isinstance(kw, str) or len(kw) < 3 or len(kw) > MAX_KEYWORD_LEN or kw.strip().isdigit():
            raise CampaignValidationError(f"keyword non valida: {kw!r} (min 3 caratteri, non puramente numerica)")

    score_override = payload.get("risk_contribution", 25)
    try:
        score_override = float(score_override)
    except (TypeError, ValueError):
        raise CampaignValidationError("risk_contribution deve essere numerico")
    if score_override < 0 or score_override > MAX_SCORE_OVERRIDE:
        raise CampaignValidationError(f"risk_contribution deve essere tra 0 e {MAX_SCORE_OVERRIDE}")

    normalized = {
        "id": cid,
        "name": name,
        "keywords": [str(k).strip() for k in keywords],
        "required_keywords": [str(k).strip() for k in (payload.get("required_keywords") or [])],
        "sender_patterns": [str(s).strip() for s in (payload.get("sender_patterns") or [])],
        "subject_patterns": [str(s).strip() for s in (payload.get("subject_patterns") or [])],
        "risk_contribution": score_override,
        "enabled": bool(payload.get("enabled", True)),
        "source": "user",
        "description": str(payload.get("description", ""))[:1000],
        "reference_url": str(payload.get("reference_url", ""))[:500],
        "active_period": str(payload.get("active_period", ""))[:50],
    }
    return normalized


def _build_by_keywords(db: dict) -> dict[str, list[dict]]:
    by_keywords: dict[str, list[dict]] = {}
    for campaign in db.get("campaigns", []):
        for keyword in campaign.get("keywords", []):
            by_keywords.setdefault(keyword, []).append(campaign)
    return by_keywords


def _read_system_campaigns() -> dict:
    path = settings.CONFIG_DIR / "campaigns.json"
    if not path.exists():
        return {"campaigns": []}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _read_user_campaigns() -> dict:
    """
    backend/data/campaigns_user.json (Wave 6) — non backend/config/, per
    evitare conflitti git a ogni aggiornamento del tool ed essere compatibile
    con deploy dove config/ è read-only. Copertura già garantita da
    .gitignore su backend/data/, nessuna voce aggiuntiva necessaria.
    """
    path = settings.USER_DATA_DIR / "campaigns_user.json"
    if not path.exists():
        return {"campaigns": []}
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("[campaign_registry] campaigns_user.json illeggibile: %s", e)
        return {"campaigns": []}


def _merge(system_db: dict, user_db: dict) -> tuple[dict, list[str]]:
    """
    Fonde sistema+utente con precedenza utente sui conflitti di id.
    Ritorna (db_fuso, overridden_ids) — overridden_ids sono gli id di sistema
    sovrascritti da una voce utente, esposti in /api/intel/status perché
    l'utente possa individuarli e, se vuole, "ripristinare la versione di
    sistema" (Wave 6 UI).
    """
    by_id: dict[str, dict] = {c["id"]: c for c in system_db.get("campaigns", []) if c.get("id")}
    overridden: list[str] = []
    for c in user_db.get("campaigns", []):
        cid = c.get("id")
        if not cid:
            continue
        if cid in by_id and by_id[cid].get("source", "builtin") != "user":
            overridden.append(cid)
        by_id[cid] = c
    return {"campaigns": list(by_id.values())}, overridden


def reload() -> None:
    """Ricostruisce il registry da disco (sistema+utente) e lo installa con un solo swap atomico."""
    try:
        system_db = _read_system_campaigns()
        user_db = _read_user_campaigns()
    except Exception as e:
        logger.error("[campaign_registry] Impossibile leggere campaigns.json: %s", e)
        _registry.mark_error("config_read_error", str(type(e).__name__))
        return

    db, overridden_ids = _merge(system_db, user_db)
    by_keywords = _build_by_keywords(db)
    value = {
        "db": db,
        "by_keywords": by_keywords,
        "user_count": len(user_db.get("campaigns", [])),
        "overridden_ids": overridden_ids,
    }
    meta = SnapshotMeta(
        state=STATE_OK,
        loaded_at=datetime.now(timezone.utc),
        entry_count=len(db.get("campaigns", [])),
        source="system+user" if user_db.get("campaigns") else "builtin",
    )
    _registry.swap(value, meta=meta)


def get() -> dict:
    """Ritorna lo snapshot corrente ({"db":..., "by_keywords":...}), caricandolo se necessario."""
    value = _registry.get()
    if value is None:
        reload()
        value = _registry.get()
    return value or {"db": {"campaigns": []}, "by_keywords": {}}


def get_meta() -> SnapshotMeta:
    return _registry.meta


# ---------------------------------------------------------------------------
# CRUD campagne utente (Wave 6)
# ---------------------------------------------------------------------------

def _user_campaigns_path():
    return settings.USER_DATA_DIR / "campaigns_user.json"


def list_user_campaigns() -> list[dict]:
    return _read_user_campaigns().get("campaigns", [])


def get_user_campaign(campaign_id: str) -> dict | None:
    for c in list_user_campaigns():
        if c.get("id") == campaign_id:
            return c
    return None


def _write_user_campaigns(campaigns: list[dict]) -> None:
    """
    Scrittura atomica con backup e rollback: se il reload successivo alla
    scrittura fallisce, il file .bak viene ripristinato e il registry
    ricaricato di nuovo — un JSON scritto ma non validabile non deve mai
    restare a metà installato nel registry in memoria.
    """
    path = _user_campaigns_path()
    settings.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = path.with_suffix(".json.bak")

    previous_bytes = path.read_bytes() if path.exists() else None

    payload = json.dumps({"campaigns": campaigns}, indent=2, ensure_ascii=False)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(payload, encoding="utf-8")
    if previous_bytes is not None:
        backup_path.write_bytes(previous_bytes)
    tmp.replace(path)

    try:
        reload()
        if get_meta().state != STATE_OK:
            raise RuntimeError("reload non riuscito dopo la scrittura")
    except Exception as e:
        logger.error("[campaign_registry] Rollback campaigns_user.json dopo scrittura fallita: %s", e)
        if previous_bytes is not None:
            path.write_bytes(previous_bytes)
        else:
            path.unlink(missing_ok=True)
        reload()
        raise


def create_user_campaign(payload: dict) -> dict:
    campaigns = list_user_campaigns()
    if len(campaigns) >= MAX_USER_CAMPAIGNS:
        raise CampaignValidationError(f"Limite massimo di {MAX_USER_CAMPAIGNS} campagne utente raggiunto")
    existing_ids = {c["id"] for c in campaigns}
    normalized = validate_campaign_payload(payload)
    if normalized["id"] in existing_ids:
        raise CampaignValidationError(f"Esiste già una campagna utente con id '{normalized['id']}'")
    with _write_lock:
        campaigns.append(normalized)
        _write_user_campaigns(campaigns)
    return normalized


def update_user_campaign(campaign_id: str, payload: dict) -> dict:
    payload = dict(payload)
    payload["id"] = campaign_id
    normalized = validate_campaign_payload(payload)
    with _write_lock:
        campaigns = list_user_campaigns()
        idx = next((i for i, c in enumerate(campaigns) if c.get("id") == campaign_id), None)
        if idx is None:
            raise CampaignValidationError(f"Nessuna campagna utente con id '{campaign_id}'")
        campaigns[idx] = normalized
        _write_user_campaigns(campaigns)
    return normalized


def delete_user_campaign(campaign_id: str) -> None:
    with _write_lock:
        campaigns = list_user_campaigns()
        remaining = [c for c in campaigns if c.get("id") != campaign_id]
        if len(remaining) == len(campaigns):
            raise CampaignValidationError(f"Nessuna campagna utente con id '{campaign_id}'")
        _write_user_campaigns(remaining)


def restore_system_version(campaign_id: str) -> None:
    """'Ripristina versione di sistema' — rimuove l'override utente per questo id, se presente."""
    delete_user_campaign(campaign_id)
