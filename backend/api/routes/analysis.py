"""
api/routes/analysis.py

Endpoint per avviare e recuperare l'analisi di un'email caricata.
"""

import json
from pathlib import Path
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


class NotesUpdate(BaseModel):
    notes: str = ""

from sqlalchemy import text
from models.database import get_session, EmailAnalysis, engine
from utils.config import settings
from core.analysis.email_parser import parse_email_file
from core.analysis.header_analyzer import analyze_headers
from core.analysis.body_analyzer import analyze_body
from core.analysis.url_analyzer import analyze_urls
from core.analysis.attachment_analyzer import analyze_attachments
from core.analysis.scorer import compute_risk_score

router = APIRouter()

import logging as _logging
_logger = _logging.getLogger(__name__)


async def _vacuum_db() -> None:
    """Esegue VACUUM sul DB SQLite per recuperare spazio su disco.

    Usato dopo operazioni di eliminazione massiva. Richiede una connessione
    fuori da qualsiasi transazione (isolation_level=AUTOCOMMIT).
    Non bloccante: le eccezioni vengono loggate ma ignorate.
    """
    try:
        async with engine.execution_options(
            isolation_level="AUTOCOMMIT"
        ).connect() as conn:
            await conn.execute(text("VACUUM"))
            _logger.info("VACUUM completato — spazio DB recuperato")
    except Exception as e:
        _logger.warning("VACUUM fallito (non critico): %s", e)


def _find_upload_file(job_id: str) -> Path:
    """Cerca il file caricato per job_id (sicuro: non accetta path traversal)."""
    for ext in settings.ALLOWED_EXTENSIONS:
        candidate = settings.UPLOAD_DIR / f"{job_id}{ext}"
        if candidate.exists():
            return candidate
    raise HTTPException(status_code=404, detail=f"File non trovato per job_id: {job_id}")


def _dataclass_to_dict(obj) -> dict:
    """Serializza dataclass ricorsivamente, gestendo tipi non-JSON-serializable."""
    try:
        return json.loads(json.dumps(asdict(obj), default=str, ensure_ascii=False))
    except Exception:
        return {}


def _cleanup_files(job_id: str) -> int:
    """Elimina file email caricato e report .docx per un job_id. Ritorna numero file rimossi."""
    removed = 0
    for ext in settings.ALLOWED_EXTENSIONS:
        candidate = settings.UPLOAD_DIR / f"{job_id}{ext}"
        if candidate.exists():
            candidate.unlink()
            removed += 1
    report = settings.REPORTS_DIR / f"{job_id}.docx"
    if report.exists():
        report.unlink()
        removed += 1
    return removed


class BulkDeleteRequest(BaseModel):
    job_ids: list[str]


@router.post("/bulk-delete")
async def bulk_delete_analyses(
    body: BulkDeleteRequest,
    db: AsyncSession = Depends(get_session),
):
    """Elimina più analisi in una singola richiesta (DB + file fisici)."""
    import re
    if len(body.job_ids) > 100:
        raise HTTPException(status_code=400, detail="Massimo 100 analisi per richiesta")

    valid_ids = [jid for jid in body.job_ids if re.match(r'^[0-9a-f-]{36}$', jid)]
    if not valid_ids:
        raise HTTPException(status_code=400, detail="Nessun job_id valido fornito")

    deleted_count = 0
    files_removed = 0
    for jid in valid_ids:
        record = await db.get(EmailAnalysis, jid)
        if record:
            await db.delete(record)
            deleted_count += 1
            files_removed += _cleanup_files(jid)

    await db.commit()
    # VACUUM dopo eliminazioni massive per recuperare spazio su disco
    if deleted_count > 0:
        await _vacuum_db()
    return {
        "status": "deleted",
        "requested": len(body.job_ids),
        "deleted": deleted_count,
        "files_removed": files_removed,
    }


@router.post("/{job_id}")
async def run_analysis(
    job_id: str,
    do_whois: bool = True,
    db: AsyncSession = Depends(get_session),
):
    """Esegue l'analisi completa dell'email e salva i risultati nel DB."""

    # Validazione job_id (solo caratteri UUID sicuri)
    import re
    if not re.match(r'^[0-9a-f-]{36}$', job_id):
        raise HTTPException(status_code=400, detail="job_id non valido")

    # Recupera il file
    file_path = _find_upload_file(job_id)
    raw = file_path.read_bytes()
    original_filename = file_path.name  # es. <uuid>.eml

    # --- Pipeline di analisi ---
    # Eseguita in un thread separato per non bloccare l'event loop asyncio.
    # parse_email_file, analyze_*, whois e DNS sono operazioni sincrone
    # (CPU-bound + I/O bloccante) che su Linux possono saturare il loop
    # e causare timeout del client se eseguite direttamente nell'async handler.
    def _pipeline():
        _parsed            = parse_email_file(raw, original_filename)
        _header_result     = analyze_headers(_parsed)
        _body_result       = analyze_body(_parsed)
        _url_result        = analyze_urls(_body_result.extracted_urls, do_whois=do_whois)
        _attachment_result = analyze_attachments(_parsed.attachments)
        _risk              = compute_risk_score(_header_result, _body_result, _url_result, _attachment_result)
        return _parsed, _header_result, _body_result, _url_result, _attachment_result, _risk

    parsed, header_result, body_result, url_result, attachment_result, risk = \
        await run_in_threadpool(_pipeline)

    # --- Persisti nel DB ---
    record = EmailAnalysis(
        id=job_id,
        filename=original_filename,
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
        body_indicators={
            **_dataclass_to_dict(body_result),
            "nlp": {
                "available":            getattr(body_result.nlp_result, "available", False),
                "phishing_probability": getattr(body_result.nlp_result, "phishing_probability", 0.0),
                "label":                getattr(body_result.nlp_result, "label", "unknown"),
                "confidence":           getattr(body_result.nlp_result, "confidence", "n/a"),
                "top_features":         getattr(body_result.nlp_result, "top_features", []),
            } if body_result.nlp_result else None,
        },
        url_indicators={
            **_dataclass_to_dict(url_result),
            "urls": [
                {**_dataclass_to_dict(u), "whois_attempted": do_whois}
                for u in url_result.urls
            ],
        },
        attachment_indicators=_dataclass_to_dict(attachment_result),
        risk_score=risk.score,
        risk_label=risk.label,
        risk_explanation={"explanation": risk.explanation, "contributions": _dataclass_to_dict(risk)},
    )

    # Upsert: se già esiste (riesecuzione analisi), aggiorna
    existing = await db.get(EmailAnalysis, job_id)
    if existing:
        await db.delete(existing)
        await db.flush()

    db.add(record)
    await db.commit()

    return _build_response(job_id, parsed, header_result, body_result, url_result, attachment_result, risk, do_whois)


@router.get("/{job_id}")
async def get_analysis(
    job_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Recupera i risultati di un'analisi già eseguita."""
    import re
    if not re.match(r'^[0-9a-f-]{36}$', job_id):
        raise HTTPException(status_code=400, detail="job_id non valido")

    record = await db.get(EmailAnalysis, job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Analisi non trovata")

    return _build_response_from_record(record)


@router.get("/")
async def list_analyses(
    db: AsyncSession = Depends(get_session),
    q: str = "",           # ricerca testo libero su subject/from
    risk: str = "",        # filtro label: low,medium,high,critical (comma-separated)
    page: int = 1,
    page_size: int = 25,
):
    """Lista analisi con supporto filtro, ricerca e paginazione."""
    from sqlalchemy import or_, func

    query = select(
        EmailAnalysis.id,
        EmailAnalysis.filename,
        EmailAnalysis.mail_subject,
        EmailAnalysis.mail_from,
        EmailAnalysis.mail_date,
        EmailAnalysis.risk_score,
        EmailAnalysis.risk_label,
        EmailAnalysis.created_at,
    )

    # Filtro testo libero
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                EmailAnalysis.mail_subject.ilike(pattern),
                EmailAnalysis.mail_from.ilike(pattern),
            )
        )

    # Filtro risk label
    if risk.strip():
        labels = [r.strip().lower() for r in risk.split(",") if r.strip()]
        if labels:
            query = query.where(EmailAnalysis.risk_label.in_(labels))

    # Conta totale (per paginazione)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginazione
    page_size = max(1, min(page_size, 100))
    page      = max(1, page)
    offset    = (page - 1) * page_size

    query = query.order_by(EmailAnalysis.created_at.desc()).limit(page_size).offset(offset)
    rows  = (await db.execute(query)).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "items": [
            {
                "job_id":      r.id,
                "filename":    r.filename,
                "subject":     r.mail_subject,
                "from":        r.mail_from,
                "date":        r.mail_date,
                "risk_score":  r.risk_score,
                "risk_label":  r.risk_label,
                "analyzed_at": str(r.created_at),
            }
            for r in rows
        ],
    }


def _build_response_from_record(record) -> dict:
    """
    Ricostruisce la risposta completa dal record DB.
    Struttura identica a _build_response, così AnalysisDetail funziona sia
    per analisi appena eseguite sia per analisi recuperate dallo storico.
    """
    hi = record.header_indicators or {}
    bi = record.body_indicators or {}
    ui = record.url_indicators or {}
    ai = record.attachment_indicators or {}
    ri = record.risk_explanation or {}

    return {
        "job_id": record.id,
        "status": "completed",
        "analyst_notes": record.analyst_notes,
        "email": {
            "filename":        record.filename,
            "subject":         record.mail_subject,
            "from":            record.mail_from,
            "to":              record.mail_to,
            "date":            record.mail_date,
            "message_id":      record.message_id,
            "file_hash_sha256": record.file_hash_sha256,
            "parse_errors":    [],
        },
        "risk": {
            "score":        record.risk_score,
            "label":        record.risk_label,
            "label_text":   ri.get("label_text", record.risk_label),
            "explanation":  ri.get("explanation", []),
            "contributions": ri.get("contributions", []),
        },
        "header_analysis": hi,
        "body_analysis": {
            "urgency_count":           bi.get("urgency_count", 0),
            "phishing_cta_count":      bi.get("phishing_cta_count", 0),
            "credential_keyword_count": bi.get("credential_keyword_count", 0),
            "forms_found":             bi.get("forms_found", 0),
            "js_found":                bi.get("js_found", False),
            "invisible_elements":      bi.get("invisible_elements", 0),
            "raw_hidden_content":      bi.get("raw_hidden_content", ""),
            "obfuscated_links":        bi.get("obfuscated_links", []),
            "findings":                bi.get("findings", []),
            "extracted_urls_count":    bi.get("extracted_urls_count", 0),
            "nlp":                     bi.get("nlp", None),
        },
        "url_analysis": {
            "total_urls":      ui.get("total_urls", 0),
            "high_risk_count": ui.get("high_risk_count", 0),
            "urls": [
                {
                    # Normalizza i nomi dal dataclass ai nomi usati dal frontend
                    "url":              u.get("original_url", u.get("url", "")),
                    "host":             u.get("host", ""),
                    "is_ip":            u.get("is_ip_address", u.get("is_ip", False)),
                    "is_shortener":     u.get("is_shortener", False),
                    "is_punycode":      u.get("is_punycode", False),
                    "https":            u.get("https_used", u.get("https", False)),
                    "resolved_ip":      u.get("resolved_ip", ""),
                    "domain_age_days":  u.get("domain_age_days"),
                    "whois_creation_date": u.get("whois_creation_date"),
                    "whois_attempted":  u.get("whois_attempted", False),
                    "risk_score":       u.get("risk_score", 0),
                    "findings":         u.get("findings", []),
                }
                for u in ui.get("urls", [])
            ],
        },
        "attachment_analysis": {
            "total":          ai.get("total_attachments", 0),
            "critical_count": ai.get("critical_count", 0),
            "attachments":    ai.get("attachments", []),
        },
        "reputation_results": record.reputation_results,
    }


def _build_response(job_id, parsed, header_result, body_result, url_result, attachment_result, risk, do_whois: bool = False) -> dict:
    return {
        "job_id": job_id,
        "status": "completed",
        "email": {
            "filename": parsed.filename,
            "subject": parsed.mail_subject,
            "from": parsed.mail_from,
            "to": parsed.mail_to,
            "date": parsed.mail_date,
            "message_id": parsed.message_id,
            "file_hash_sha256": parsed.file_hash_sha256,
            "parse_errors": parsed.parse_errors,
        },
        "risk": {
            "score": risk.score,
            "label": risk.label,
            "label_text": risk.label_text,
            "explanation": risk.explanation,
            "contributions": [
                {
                    "module": c.module,
                    "raw_score": c.raw_score,
                    "weighted_score": c.weighted_score,
                    "top_reasons": c.top_reasons,
                }
                for c in risk.contributions
            ],
        },
        "header_analysis": _dataclass_to_dict(header_result),
        "body_analysis": {
            "urgency_count": body_result.urgency_count,
            "phishing_cta_count": body_result.phishing_cta_count,
            "credential_keyword_count": body_result.credential_keyword_count,
            "forms_found": body_result.forms_found,
            "js_found": body_result.js_found,
            "invisible_elements": body_result.invisible_elements,
            "raw_hidden_content": body_result.raw_hidden_content,
            "obfuscated_links": body_result.obfuscated_links,
            "findings": [_dataclass_to_dict(f) for f in body_result.findings],
            "extracted_urls_count": len(body_result.extracted_urls),
            "nlp": {
                "available": getattr(body_result.nlp_result, "available", False),
                "phishing_probability": getattr(body_result.nlp_result, "phishing_probability", 0.0),
                "label": getattr(body_result.nlp_result, "label", "unknown"),
                "confidence": getattr(body_result.nlp_result, "confidence", "n/a"),
                "top_features": getattr(body_result.nlp_result, "top_features", []),
            } if body_result.nlp_result else None,
        },
        "url_analysis": {
            "total_urls": url_result.total_urls,
            "high_risk_count": url_result.high_risk_count,
            "urls": [
                {
                    "url": u.original_url,
                    "host": u.host,
                    "is_ip": u.is_ip_address,
                    "is_shortener": u.is_shortener,
                    "is_punycode": u.is_punycode,
                    "https": u.https_used,
                    "resolved_ip": u.resolved_ip,
                    "domain_age_days": u.domain_age_days,
                    "whois_creation_date": str(u.whois_creation_date) if u.whois_creation_date else None,
                    "whois_attempted": do_whois,
                    "risk_score": u.risk_score,
                    "findings": u.findings,
                }
                for u in url_result.urls
            ],
        },
        "attachment_analysis": {
            "total": attachment_result.total_attachments,
            "critical_count": attachment_result.critical_count,
            "attachments": [
                {
                    "filename": a.filename,
                    "size_bytes": a.size_bytes,
                    "declared_mime": a.declared_mime,
                    "real_mime": a.real_mime,
                    "mime_mismatch": a.mime_mismatch,
                    "hash_sha256": a.hash_sha256,
                    "has_macro": a.has_macro,
                    "has_js": a.has_js,
                    "risk_score": a.risk_score,
                    "findings": [_dataclass_to_dict(f) for f in a.findings],
                }
                for a in attachment_result.attachments
            ],
        },
    }


@router.patch("/{job_id}/notes")
async def update_notes(
    job_id: str,
    body: "NotesUpdate",
    db: AsyncSession = Depends(get_session),
):
    """Aggiorna le note manuali dell analista."""
    import re
    if not re.match(r'^[0-9a-f-]{36}$', job_id):
        raise HTTPException(status_code=400, detail="job_id non valido")

    record = await db.get(EmailAnalysis, job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Analisi non trovata")

    if len(body.notes) > 10000:
        raise HTTPException(status_code=400, detail="Note troppo lunghe (max 10.000 caratteri)")

    record.analyst_notes = body.notes
    await db.commit()
    return {"job_id": job_id, "analyst_notes": record.analyst_notes, "ok": True}


@router.delete("/{job_id}")
async def delete_analysis(
    job_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Elimina l'analisi dal DB e i file fisici associati (email + report)."""
    import re
    if not re.match(r'^[0-9a-f-]{36}$', job_id):
        raise HTTPException(status_code=400, detail="job_id non valido")

    record = await db.get(EmailAnalysis, job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Analisi non trovata")

    await db.delete(record)
    await db.commit()
    files_removed = _cleanup_files(job_id)
    await _vacuum_db()
    return {"status": "deleted", "job_id": job_id, "files_removed": files_removed}