"""
api/routes/report.py

Genera il report Word (.docx) per un'analisi completata.
"""

import re
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session, EmailAnalysis
from core.reporting.docx_reporter import generate_report
from utils.config import settings
from utils.i18n import t

router = APIRouter()


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

    report_path: Path = settings.REPORTS_DIR / f"{job_id}.docx"

    try:
        generate_report(record, report_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=t("report.generation_error", error=e))

    return FileResponse(
        path=str(report_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"emlyzer_report_{job_id[:8]}.docx",
    )
