"""
api/routes/intel.py

Osservabilità (Wave 3) e refresh on-demand (Wave 4) della Threat
Intelligence: feed IOC di reputazione, campagne note, bollettini CERT-AGID.

Contratto di GET /status definito nella sua forma finale fin dalla Wave 3,
con valori neutri per ciò che le Wave successive popoleranno (campagne
utente, bollettini) — per non dover riscrivere il client due volte.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.intel import feeds as intel_feeds
from core.intel import runner as intel_runner
from core.intel import runs as intel_runs
from core.intel import scheduler as intel_scheduler
from core.intel.auth import require_trusted_client
from core.analysis import campaign_registry
from core.rate_limiting import limiter

router = APIRouter()

SCHEMA_VERSION = 1


def _feed_status(name: str) -> dict:
    spec = intel_feeds.FEEDS[name]
    snap = intel_feeds.snapshot(name)
    meta = snap.meta
    data = snap.get()
    runs = [
        {
            "run_id": r.run_id, "result": r.result,
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in intel_runs.recent_runs(name)
    ]
    return {
        "name": name,
        "enabled": True,
        "requires_key": bool(spec.requires_key),
        "key_configured": _key_configured(spec.requires_key),
        "state": meta.state,
        "entry_count": len(data) if data is not None else meta.entry_count,
        "ttl_hours": spec.ttl_hours,
        "age_hours": _age_hours(meta),
        "last_success": meta.loaded_at.isoformat() if meta.loaded_at else None,
        "last_error": {"category": meta.last_error_category, "message": meta.last_error_message}
                      if meta.last_error_category else None,
        "runs": runs,
    }


def _age_hours(meta) -> float | None:
    if not meta.loaded_at:
        return None
    from datetime import datetime, timezone
    return round((datetime.now(timezone.utc) - meta.loaded_at).total_seconds() / 3600, 1)


def _key_configured(setting_name: str | None) -> bool:
    if not setting_name:
        return True
    from utils.config import settings
    return bool(getattr(settings, setting_name, ""))


@router.get("/status")
async def get_status():
    """Stato unificato di feed IOC, campagne note e bollettini — un solo endpoint per l'intera UI Threat Intelligence."""
    reg_meta = campaign_registry.get_meta()
    reg = campaign_registry.get()

    try:
        from core.intel import bulletins as intel_bulletins
        bulletins_status = intel_bulletins.status()
    except ImportError:
        bulletins_status = {"state": "disabled"}

    return {
        "schema_version": SCHEMA_VERSION,
        "scheduler_running": intel_scheduler.is_running(),
        "feeds": [_feed_status(name) for name in intel_feeds.FEEDS],
        "campaigns": {
            "system_count": len(reg["db"].get("campaigns", [])),
            "user_count": reg.get("user_count", 0),
            "effective_count": len(reg["db"].get("campaigns", [])),
            "overridden_ids": reg.get("overridden_ids", []),
            "last_reload": reg_meta.loaded_at.isoformat() if reg_meta.loaded_at else None,
            "source": "system+user" if reg.get("user_count") else "system",
        },
        "bulletins": bulletins_status,
    }


_RefreshTarget = Literal["openphish", "spamhaus", "campaigns", "bulletins"]


class RefreshResponse(BaseModel):
    target: str
    accepted: bool
    run_id: int | None = None
    already_running: bool = False


@router.post("/refresh", dependencies=[Depends(require_trusted_client)])
@limiter.limit("2/minute")
async def refresh_target(request: Request, target: _RefreshTarget):
    """
    Forza il refresh di un feed/dominio specifico. `target` è vincolato a una
    whitelist (Literal -> 422 automatico su Pydantic per valori fuori lista):
    mai un URL libero, che su un endpoint senza vera autenticazione sarebbe
    una SSRF diretta.
    """
    if target in intel_feeds.FEEDS:
        job_name = target
    elif target == "campaigns":
        campaign_registry.reload()
        return RefreshResponse(target=target, accepted=True)
    elif target == "bulletins":
        job_name = "bulletins"
    else:
        raise HTTPException(status_code=422, detail=f"Target sconosciuto: {target}")

    job = intel_runner.get_job(job_name)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Nessun job registrato per '{target}'")

    snap = intel_feeds.snapshot(job_name) if job_name in intel_feeds.FEEDS else None
    if snap is not None and snap.refreshing:
        return RefreshResponse(target=target, accepted=False, already_running=True)

    run_id = intel_runner.run_job_now(job_name)
    return RefreshResponse(target=target, accepted=True, run_id=run_id)


@router.get("/bulletins")
async def list_bulletins():
    """
    Bacheca di spunti CERT-AGID (Wave 7) — solo titolo/data/link/estratto,
    mai il testo integrale. Nessuna keyword viene generata qui: il pulsante
    "Crea campagna da questo bollettino" nel frontend apre il form di
    creazione manuale (Wave 6) precompilato solo con questi metadati.
    """
    from core.intel import bulletins as intel_bulletins
    return {"items": intel_bulletins.list_bulletins(), "status": intel_bulletins.status()}
