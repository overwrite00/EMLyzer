"""
api/routes/campaigns.py

Endpoint per il rilevamento campagne malevole coordinate.
Analizza tutte le email nel DB e raggruppa quelle simili.
"""

import re
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import get_session, EmailAnalysis
from core.analysis.campaign_detector import (
    detect_campaigns, EmailSummary, CampaignReport,
    _hash_body,
)
from dataclasses import asdict
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
        # Estrai body_text dal body_indicators se disponibile
        body_hash = ""
        if r.body_indicators:
            bi = r.body_indicators if isinstance(r.body_indicators, dict) else {}
            # Usiamo il conteggio urgency+cta come proxy per l'hash del contenuto
            # (il body_text non è salvato direttamente nel DB per privacy)
            proxy = f"{bi.get('urgency_count',0)}_{bi.get('phishing_cta_count',0)}_{bi.get('forms_found',0)}_{bi.get('js_found',False)}"
            body_hash = _hash_body(proxy)

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
