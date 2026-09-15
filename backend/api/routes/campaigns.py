"""
api/routes/campaigns.py

Due concetti distinti, deliberatamente non unificati (v0.17):
- "Cluster simili" (GET /) — clustering interno delle email già analizzate,
  raggruppate per similarità (subject/body/sender). Nessuna nozione di
  "campagna nota": è un'euristica sul corpus dell'utente.
- "Campagne note" (/known/*, Wave 6) — DB curato di pattern di campagne di
  phishing note (brand, keyword, sender/subject pattern), fuso da
  backend/config/campaigns.json (sistema) e backend/data/campaigns_user.json
  (utente, precedenza sui conflitti di id). Usato dal matcher in
  body_analyzer.py durante l'analisi di ogni nuova email.
"""

import re
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import get_session, EmailAnalysis
from core.analysis.campaign_detector import (
    detect_campaigns, EmailSummary, CampaignReport,
)
from core.analysis import campaign_registry
from core.analysis.body_analyzer import match_campaigns
from core.intel.auth import require_trusted_client
from core.rate_limiting import limiter
from dataclasses import asdict
from pydantic import BaseModel, Field
import json

router = APIRouter()


@router.get("/")
async def get_campaigns(
    db: AsyncSession = Depends(get_session),
    threshold: float = Query(default=0.6, ge=0.1, le=1.0,
                             description="Soglia similarità Jaccard subject (0.1–1.0)"),
    min_size: int = Query(default=2, ge=2, le=20,
                          description="Dimensione minima cluster"),
):
    """
    Analizza tutte le email nel database e restituisce i cluster di campagne.
    """
    # Carica tutte le analisi
    result = await db.execute(
        select(
            EmailAnalysis.id,
            EmailAnalysis.mail_subject,
            EmailAnalysis.mail_from,
            EmailAnalysis.mail_date,
            EmailAnalysis.message_id,
            EmailAnalysis.x_mailer,
            EmailAnalysis.x_campaign_id,
            EmailAnalysis.risk_label,
            EmailAnalysis.risk_score,
            EmailAnalysis.body_indicators,
        ).order_by(EmailAnalysis.created_at.desc()).limit(500)
    )
    rows = result.all()

    # Costruisci EmailSummary per ogni riga
    summaries = []
    for r in rows:
        # v0.17 FIX: body_hash reale (body_indicators.body_sha256, calcolato in
        # body_analyzer.py sul body normalizzato), non più un proxy sui contatori.
        # Il proxy precedente (urgency_count/cta_count/forms/js) collideva su
        # qualunque email con gli stessi 4 valori a zero — la stragrande
        # maggioranza — producendo un mega-cluster spurio nella strategia
        # "body_hash identico" (priorità più alta in detect_campaigns).
        # Le email analizzate prima di questo fix non hanno body_sha256:
        # restano fuori dalla strategia body_hash invece di collidere a caso.
        body_hash = ""
        if r.body_indicators:
            bi = r.body_indicators if isinstance(r.body_indicators, dict) else {}
            real_hash = bi.get("body_sha256", "")
            if isinstance(real_hash, str) and len(real_hash) == 64:
                body_hash = real_hash

        summaries.append(EmailSummary(
            job_id=r.id,
            subject=r.mail_subject or "",
            mail_from=r.mail_from or "",
            mail_date=r.mail_date or "",
            message_id=r.message_id or "",
            body_hash=body_hash,
            x_mailer=r.x_mailer or "",
            x_campaign_id=r.x_campaign_id or "",
            risk_label=r.risk_label or "",
            risk_score=r.risk_score or 0.0,
        ))

    report = detect_campaigns(
        summaries,
        subject_threshold=threshold,
        min_cluster_size=min_size,
    )

    # Serializza
    clusters_out = []
    for c in report.clusters:
        d = asdict(c)
        clusters_out.append(d)

    return {
        "total_emails_analyzed": report.total_emails_analyzed,
        "clusters_found": report.clusters_found,
        "isolated_emails": report.isolated_emails,
        "threshold_used": threshold,
        "min_cluster_size": min_size,
        "clusters": clusters_out,
    }


# ---------------------------------------------------------------------------
# "Campagne note" (Wave 6) — CRUD + backtest
# ---------------------------------------------------------------------------

class CampaignPayload(BaseModel):
    id: str
    name: str
    keywords: list[str]
    required_keywords: list[str] = Field(default_factory=list)
    sender_patterns: list[str] = Field(default_factory=list)
    subject_patterns: list[str] = Field(default_factory=list)
    risk_contribution: float = 25.0
    enabled: bool = True
    description: str = ""
    reference_url: str = ""
    active_period: str = ""


@router.get("/known")
async def list_known_campaigns():
    """Elenco fuso sistema+utente, con indicazione di quali id sono override utente."""
    reg = campaign_registry.get()
    return {
        "campaigns": reg["db"].get("campaigns", []),
        "user_campaign_ids": [c["id"] for c in campaign_registry.list_user_campaigns()],
        "overridden_ids": reg.get("overridden_ids", []),
    }


@router.post("/known", dependencies=[Depends(require_trusted_client)])
@limiter.limit("10/minute")
async def create_known_campaign(request: Request, payload: CampaignPayload):
    try:
        created = campaign_registry.create_user_campaign(payload.model_dump())
    except campaign_registry.CampaignValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return created


@router.put("/known/{campaign_id}", dependencies=[Depends(require_trusted_client)])
@limiter.limit("10/minute")
async def update_known_campaign(request: Request, campaign_id: str, payload: CampaignPayload):
    try:
        updated = campaign_registry.update_user_campaign(campaign_id, payload.model_dump())
    except campaign_registry.CampaignValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return updated


@router.delete("/known/{campaign_id}", dependencies=[Depends(require_trusted_client)])
@limiter.limit("10/minute")
async def delete_known_campaign(request: Request, campaign_id: str):
    try:
        campaign_registry.delete_user_campaign(campaign_id)
    except campaign_registry.CampaignValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"deleted": campaign_id}


@router.post("/known/{campaign_id}/restore", dependencies=[Depends(require_trusted_client)])
@limiter.limit("10/minute")
async def restore_known_campaign(request: Request, campaign_id: str):
    """Rimuove l'override utente per campaign_id, ripristinando la versione di sistema (se esiste)."""
    try:
        campaign_registry.restore_system_version(campaign_id)
    except campaign_registry.CampaignValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"restored": campaign_id}


class BacktestPayload(BaseModel):
    keywords: list[str]
    required_keywords: list[str] = Field(default_factory=list)
    risk_contribution: float = 25.0
    detail: bool = False


_BACKTEST_CORPUS_CAP = 500


@router.post("/known/backtest", dependencies=[Depends(require_trusted_client)])
@limiter.limit("20/minute")
async def backtest_campaign(
    request: Request,
    payload: BacktestPayload,
    db: AsyncSession = Depends(get_session),
):
    """
    Esegue il matcher CANDIDATO (non ancora salvato) contro la
    campaign_surface persistita nelle email già analizzate — token
    normalizzati e filtrati anti-PII (body_analyzer._store_campaign_surface),
    non il body integrale.

    Dichiara sempre la copertura: le email analizzate prima dell'introduzione
    di campaign_surface (v0.17) non sono valutabili e vengono conteggiate a
    parte, non ignorate silenziosamente.

    Di default ritorna solo aggregati (protegge dal backtest come canale di
    lettura del corpus su un endpoint senza vera autenticazione); i subject
    delle email matchate sono inclusi solo con detail=true.
    """
    result = await db.execute(
        select(EmailAnalysis.id, EmailAnalysis.mail_subject, EmailAnalysis.risk_label, EmailAnalysis.body_indicators)
        .order_by(EmailAnalysis.created_at.desc())
        .limit(_BACKTEST_CORPUS_CAP)
    )
    rows = result.all()

    candidate_registry = {"campaigns": [{
        "id": "__candidate__", "name": "candidate", "enabled": True,
        "keywords": payload.keywords, "required_keywords": payload.required_keywords,
        "risk_contribution": payload.risk_contribution,
    }]}

    total = len(rows)
    evaluable = 0
    matched_rows = []
    by_risk = {"low": 0, "medium": 0, "high": 0, "critical": 0, "": 0}

    for r in rows:
        bi = r.body_indicators if isinstance(r.body_indicators, dict) else {}
        surface = bi.get("campaign_surface")
        if not surface:
            continue  # analizzata prima di v0.17 (o feature disattivata): non valutabile
        evaluable += 1
        text = " ".join(surface)
        matches = match_campaigns(text_lower=text, subject_lower="", registry=candidate_registry)
        if matches:
            matched_rows.append(r)
            by_risk[r.risk_label or ""] = by_risk.get(r.risk_label or "", 0) + 1

    response = {
        "total_emails": total,
        "evaluable_emails": evaluable,
        "not_evaluable_emails": total - evaluable,
        "matched_count": len(matched_rows),
        "matched_by_risk_label": by_risk,
        "likely_false_positive_count": by_risk.get("low", 0) + by_risk.get("", 0),
        "coverage_note": (
            f"valutate {evaluable}/{total} email con campaign_surface disponibile"
            + (f"; {total - evaluable} analizzate prima di questa funzione non sono valutabili" if total - evaluable else "")
        ),
    }
    if payload.detail:
        response["matched_subjects"] = [r.mail_subject for r in matched_rows[:50]]
    return response


# ---------------------------------------------------------------------------
# Auto-apprendimento interno (Wave 9) — proposte, mai merge automatico
# ---------------------------------------------------------------------------

from core.analysis import campaign_proposals as _proposals


@router.post("/proposals/generate", dependencies=[Depends(require_trusted_client)])
@limiter.limit("5/minute")
async def generate_proposals(request: Request, db: AsyncSession = Depends(get_session)):
    """
    Esegue il clustering ristretto (solo subject-Jaccard e body_hash reale)
    e persiste come 'pending' solo i cluster osservati per la seconda volta
    (cooldown) che superano i filtri di qualità e non sono già coperti da
    una campagna nota esistente. Va chiamato on-demand (bottone in UI), non
    schedulato: rendimento dichiaratamente incerto su un corpus piccolo.
    """
    created = await _proposals.generate_proposals(db)
    return {"created_count": len(created), "created_ids": [p.id for p in created]}


@router.get("/proposals")
async def list_proposals(status: str = Query(default="pending"), db: AsyncSession = Depends(get_session)):
    return {"proposals": await _proposals.list_proposals(db, status=status)}


@router.post("/proposals/{proposal_id}/approve", dependencies=[Depends(require_trusted_client)])
@limiter.limit("10/minute")
async def approve_proposal(request: Request, proposal_id: str, db: AsyncSession = Depends(get_session)):
    """Non scrive nulla: ritorna il payload da aprire nel form di creazione manuale (Wave 6)."""
    try:
        payload = await _proposals.approve_proposal(db, proposal_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"payload_for_form": payload}


class RejectPayload(BaseModel):
    reason: str = ""


@router.post("/proposals/{proposal_id}/reject", dependencies=[Depends(require_trusted_client)])
@limiter.limit("10/minute")
async def reject_proposal(request: Request, proposal_id: str, payload: RejectPayload, db: AsyncSession = Depends(get_session)):
    try:
        await _proposals.reject_proposal(db, proposal_id, payload.reason)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"rejected": proposal_id}
