"""
api/routes/report.py

Genera il report Word (.docx) per un'analisi completata.
"""

import re
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import get_session, EmailAnalysis
from core.reporting.docx_reporter import generate_report
from core.analysis.campaign_detector import detect_campaigns, EmailSummary, _hash_body
from utils.config import settings
from utils.i18n import t

router = APIRouter()


async def _fetch_campaign_clusters(job_id: str, db: AsyncSession):
    """
    Esegue il rilevamento campagne su tutte le email nel DB e restituisce
    i cluster che contengono questo job_id.
    """
    try:
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

        summaries = []
        for r in rows:
            body_hash = ""
            if r.body_indicators:
                bi = r.body_indicators if isinstance(r.body_indicators, dict) else {}
                proxy = (
                    f"{bi.get('urgency_count', 0)}_{bi.get('phishing_cta_count', 0)}"
                    f"_{bi.get('forms_found', 0)}_{bi.get('js_found', False)}"
                )
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

        campaign_report = detect_campaigns(summaries)
        # Filtra solo i cluster che contengono questo job_id
        return [c for c in campaign_report.clusters if job_id in c.job_ids]
    except Exception:
        return []


@router.get("/{job_id}")
async def download_report(
    job_id: str,
    db: AsyncSession = Depends(get_session),
):
    if not re.match(r'^[0-9a-f-]{36}$', job_id):
        raise HTTPException(status_code=400, detail=t("analysis.invalid_job_id"))

    record = await db.get(EmailAnalysis, job_id)
    if not record:
        raise HTTPException(status_code=404, detail=t("analysis.not_found"))

    # Recupera i cluster di campagna che includono questa email (best-effort)
    campaign_clusters = await _fetch_campaign_clusters(job_id, db)

    report_path: Path = settings.REPORTS_DIR / f"{job_id}.docx"

    try:
        generate_report(record, report_path, campaign_clusters=campaign_clusters)
    except Exception as e:
        raise HTTPException(status_code=500, detail=t("report.generation_error", error=e))

    return FileResponse(
        path=str(report_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"emlyzer_report_{job_id[:8]}.docx",
    )
