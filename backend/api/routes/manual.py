"""
api/routes/manual.py

Endpoint per l'input manuale del sorgente email.
L'utente incolla header + body come testo grezzo (RFC 822).
Viene analizzato come se fosse un .eml.
"""

import re
import uuid
import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from utils.config import settings
from utils.i18n import t
from core.analysis.email_parser import parse_email_file, raw_looks_like_eml
from core.analysis.header_analyzer import analyze_headers
from core.analysis.body_analyzer import analyze_body
from core.analysis.url_analyzer import analyze_urls
from core.analysis.attachment_analyzer import analyze_attachments
from core.analysis.scorer import compute_risk_score

router = APIRouter()


class ManualInput(BaseModel):
    source: str
    filename: str = "manual_input.eml"
    do_whois: bool = False


@router.post("/")
async def analyze_manual(payload: ManualInput):
    """
    Analizza un sorgente email incollato manualmente.
    Non richiede upload file: accetta il testo come JSON body.
    """
    source = payload.source.strip()

    if not source:
        raise HTTPException(status_code=400, detail=t("manual.empty"))

    # Normalizza i line ending (Windows \r\n → \n, poi riconverti per RFC 822)
    source = source.replace("\r\n", "\n").replace("\r", "\n")

    # Converti in bytes come farebbe un vero .eml
    raw = source.encode("utf-8", errors="replace")

    if len(raw) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=t("upload.too_large", max_mb=settings.MAX_UPLOAD_SIZE_MB))

    # Verifica che sembri un'email RFC 822
    if not raw_looks_like_eml(raw):
        raise HTTPException(
            status_code=422,
            detail=t("manual.parse_error"),
        )

    # Genera un job_id deterministico dall'hash del contenuto
    sha256 = hashlib.sha256(raw).hexdigest()
    job_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, sha256))

    # Salva come file .eml nella upload dir (per poter generare il report .docx)
    dest: Path = settings.UPLOAD_DIR / f"{job_id}.eml"
    dest.write_bytes(raw)

    # Pipeline di analisi (identica all'upload file)
    from api.routes.analysis import _build_response, _dataclass_to_dict
    from models.database import EmailAnalysis, AsyncSessionLocal

    # Stessa ottimizzazione di analysis.py: pipeline bloccante in thread separato
    # per non congelare l'event loop asyncio su Linux.
    _do_whois = payload.do_whois

    def _pipeline():
        _parsed            = parse_email_file(raw, payload.filename)
        _header_result     = analyze_headers(_parsed)
        _body_result       = analyze_body(_parsed)
        _url_result        = analyze_urls(_body_result.extracted_urls, do_whois=_do_whois)
        _attachment_result = analyze_attachments(_parsed.attachments)
        _risk              = compute_risk_score(_header_result, _body_result, _url_result, _attachment_result)
        return _parsed, _header_result, _body_result, _url_result, _attachment_result, _risk

    parsed, header_result, body_result, url_result, attachment_result, risk = \
        await run_in_threadpool(_pipeline)

    # Persisti nel DB
    import json
    record = EmailAnalysis(
        id=job_id,
        filename=payload.filename,
        file_hash_sha256=parsed.file_hash_sha256,
        mail_from=parsed.mail_from,
        mail_to=str(parsed.mail_to),
        mail_subject=parsed.mail_subject,
        mail_date=parsed.mail_date,
        message_id=parsed.message_id,
        return_path=parsed.return_path,
        reply_to=parsed.reply_to,
        x_mailer=parsed.x_mailer,
        x_originating_ip=parsed.x_originating_ip,
        x_campaign_id=parsed.x_campaign_id,
        spf_result=parsed.spf_result,
        dkim_result=parsed.dkim_result,
        dmarc_result=parsed.dmarc_result,
        header_indicators=_dataclass_to_dict(header_result),
        body_indicators=_dataclass_to_dict(body_result),
        url_indicators=_dataclass_to_dict(url_result),
        attachment_indicators=_dataclass_to_dict(attachment_result),
        risk_score=risk.score,
        risk_label=risk.label,
        risk_explanation={"explanation": risk.explanation, "contributions": _dataclass_to_dict(risk)},
    )

    async with AsyncSessionLocal() as db:
        existing = await db.get(EmailAnalysis, job_id)
        if existing:
            await db.delete(existing)
            await db.flush()
        db.add(record)
        await db.commit()

    return _build_response(job_id, parsed, header_result, body_result, url_result, attachment_result, risk)
