"""
api/routes/analysis.py

Endpoint per avviare e recuperare l'analisi di un'email caricata.
"""

import json
from pathlib import Path
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


class NotesUpdate(BaseModel):
    notes: str = ""

from sqlalchemy import text
from core.rate_limiting import limiter
from models.database import get_session, EmailAnalysis, engine
from utils.config import settings
from utils.i18n import t
from core.analysis.email_parser import parse_email_file
from core.analysis.header_analyzer import analyze_headers
from core.analysis.body_analyzer import analyze_body
from core.analysis.url_analyzer import analyze_urls
from core.analysis.attachment_analyzer import analyze_attachments
from core.analysis.scorer import compute_risk_score

router = APIRouter()

import logging
_logger = logging.getLogger(__name__)


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
    raise HTTPException(status_code=404, detail=t("analysis.file_not_found", job_id=job_id))


def _dataclass_to_dict(obj) -> dict:
    """Serializza dataclass ricorsivamente, gestendo tipi non-JSON-serializable."""
    try:
        return json.loads(json.dumps(asdict(obj), default=str, ensure_ascii=False))
    except Exception:
        return {}


def _cleanup_files(job_id: str) -> int:
    """Elimina file email caricato e report .docx per un job_id. Ritorna numero file rimossi."""
    import logging
    logger = logging.getLogger(__name__)
    removed = 0

    # Elimina file email (tutti gli estensioni supportate)
    for ext in settings.ALLOWED_EXTENSIONS:
        candidate = settings.UPLOAD_DIR / f"{job_id}{ext}"
        if candidate.exists():
            try:
                candidate.unlink()
                logger.debug(f"[CLEANUP] Deleted: {candidate}")
                removed += 1
            except Exception as e:
                logger.error(f"[CLEANUP] Failed to delete {candidate}: {e}")

    # Elimina report .docx
    report = settings.REPORTS_DIR / f"{job_id}.docx"
    if report.exists():
        try:
            report.unlink()
            logger.debug(f"[CLEANUP] Deleted: {report}")
            removed += 1
        except Exception as e:
            logger.error(f"[CLEANUP] Failed to delete {report}: {e}")

    logger.info(f"[CLEANUP] Job {job_id}: {removed} files removed")
    return removed


class BulkDeleteRequest(BaseModel):
    job_ids: list[str]


@router.post("/bulk-delete")
@limiter.limit("5/minute")
async def bulk_delete_analyses(
    request: Request,
    body: BulkDeleteRequest,
    db: AsyncSession = Depends(get_session),
):
    """Elimina più analisi in una singola richiesta (DB + file fisici)."""
    import re
    if len(body.job_ids) > 100:
        raise HTTPException(status_code=400, detail=t("analysis.bulk_max"))

    valid_ids = [jid for jid in body.job_ids if re.match(r'^[0-9a-f-]{36}$', jid)]
    if not valid_ids:
        raise HTTPException(status_code=400, detail=t("analysis.no_valid_ids"))

    # CRITICAL: Batch delete instead of N+1 queries
    # Old approach (N+1): for each job_id, await db.get() → 100 jobs = 100 queries
    # New approach (batch): single query with .where(id.in_(valid_ids)) → 1 query
    stmt = select(EmailAnalysis).where(EmailAnalysis.id.in_(valid_ids))
    result = await db.execute(stmt)
    records_to_delete = result.scalars().all()

    deleted_count = 0
    files_removed = 0
    for record in records_to_delete:
        await db.delete(record)
        deleted_count += 1
        files_removed += _cleanup_files(record.id)

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
@limiter.limit("10/minute")
async def run_analysis(
    request: Request,
    job_id: str,
    do_whois: bool = True,
    db: AsyncSession = Depends(get_session),
):
    """Esegue l'analisi completa dell'email e salva i risultati nel DB."""

    # Validazione job_id (solo caratteri UUID sicuri)
    import re
    if not re.match(r'^[0-9a-f-]{36}$', job_id):
        raise HTTPException(status_code=400, detail=t("analysis.invalid_job_id"))

    # Recupera il file
    file_path = _find_upload_file(job_id)

    # Verifica dimensione file prima di leggere in RAM (non affidarsi solo al chunking upload)
    MAX_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    file_size = file_path.stat().st_size
    if file_size > MAX_SIZE:
        _logger.warning("[%s] [FILE SIZE EXCEEDED] File size %d bytes > limit %d bytes",
                       job_id, file_size, MAX_SIZE)
        raise HTTPException(
            status_code=413,
            detail=t("upload.too_large", max_mb=settings.MAX_UPLOAD_SIZE_MB)
        )

    raw = file_path.read_bytes()
    original_filename = file_path.name  # es. <uuid>.eml

    # --- Pipeline di analisi ---
    # Eseguita in un thread separato per non bloccare l'event loop asyncio.
    # parse_email_file, analyze_*, whois e DNS sono operazioni sincrone
    # (CPU-bound + I/O bloccante) che su Linux possono saturare il loop
    # e causare timeout del client se eseguite direttamente nell'async handler.
    def _pipeline():
        """
        Esegue la full analysis pipeline per un'email.

        Ordine di esecuzione (sequenziale):
        1. parse_email_file() — parsing RFC 2822/MSG, estrazioni header, body, allegati
        2. analyze_headers() — SPF/DKIM/DMARC, auth injection, bulk sender, originatingIP
        3. analyze_body() — urgency patterns, phishing CTA, credentials, homoglyphs, LanguageTool
        4. analyze_urls() — resolving, whois, domain age, shortener detection, TLS
        5. analyze_attachments() — MIME type, macro/VBA, double extension, PDF/JS scanning
        6. compute_risk_score() — normalizzazione adattiva, floor rules, risk label assegnamento

        Returns: 6-tuple (parsed, header_result, body_result, url_result, attachment_result, risk_score)
        """
        _parsed            = parse_email_file(raw, original_filename)
        _header_result     = analyze_headers(_parsed)
        _body_result       = analyze_body(_parsed, _header_result)
        _url_result        = analyze_urls(_body_result.extracted_urls, do_whois=do_whois)
        _attachment_result = analyze_attachments(_parsed.attachments)
        _risk              = compute_risk_score(_header_result, _body_result, _url_result, _attachment_result)
        return _parsed, _header_result, _body_result, _url_result, _attachment_result, _risk

    parsed, header_result, body_result, url_result, attachment_result, risk = \
        await run_in_threadpool(_pipeline)

    # --- P0-4: Verify Analyzer Execution ---
    _logger.info("[%s] Pipeline completato: header=%d findings, body=%d findings, urls=%d urls", job_id, len(header_result.findings), len(body_result.findings), len(url_result.urls))

    # Check if any findings were detected
    total_findings = (
        len(header_result.findings or []) +
        len(body_result.findings or []) +
        len(url_result.urls or []) +
        len(attachment_result.attachments or [])
    )
    _logger.info("[%s] [RESULT CHECK] Total entities analyzed: headers=%d, body_checks=%d, urls=%d, attachments=%d",
                 job_id, len(header_result.findings or []), len(body_result.findings or []),
                 len(url_result.urls or []), len(attachment_result.attachments or []))

    if total_findings == 0 and risk.score == 0:
        _logger.warning("[%s] [RESULT WARNING] All analyzers returned 0 findings - email appears clean or analyzers not executing", job_id)
    else:
        _logger.info("[%s] [RESULT OK] Found %d total indicators, risk_score=%.1f", job_id, total_findings, risk.score)

    # --- Persisti nel DB ---
    record = EmailAnalysis(
        id=job_id,
        filename=original_filename,
        file_hash_sha256=parsed.file_hash_sha256,
        mail_from=parsed.mail_from,
        mail_to=json.dumps(parsed.mail_to),
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
            } if body_result.nlp_result else {},
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

    # Upsert: idempotent merge per evitare race conditions tra get() e add()
    # SQLAlchemy merge() è atomico: se il record esiste, lo aggiorna; se no, lo crea.
    # Questo previene la finestra di tempo dove un'altra richiesta potrebbe modificare il record.
    _logger.info("[%s] [DB UPSERT] Merging EmailAnalysis record (atomic upsert)", job_id)
    try:
        # merge() è atomico in SQLAlchemy 2.0+: no race condition tra get() e add()
        merged_record = await db.merge(record)
        _logger.info("[%s] [DB COMMIT] Committing transaction to database", job_id)
        await db.commit()
        _logger.info("[%s] [DB SUCCESS] Analysis persisted successfully, record_id=%s", job_id, merged_record.id)
    except Exception as e:
        _logger.error("[%s] [DB ERROR] Failed to commit to database: %s", job_id, str(e))
        await db.rollback()
        raise HTTPException(status_code=500, detail=t("analysis.db_error"))

    return _build_response(job_id, parsed, header_result, body_result, url_result, attachment_result, risk, do_whois)


@router.get("/{job_id}")
async def get_analysis(
    job_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Recupera i risultati di un'analisi già eseguita."""
    import re
    if not re.match(r'^[0-9a-f-]{36}$', job_id):
        raise HTTPException(status_code=400, detail=t("analysis.invalid_job_id"))

    record = await db.get(EmailAnalysis, job_id)
    if not record:
        raise HTTPException(status_code=404, detail=t("analysis.not_found"))

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

    # mail_to è salvato come JSON (lista serializzata): decodifica per
    # restituire la stessa struttura del POST. Fallback al valore grezzo
    # per record storici salvati in altri formati.
    mail_to = record.mail_to
    if isinstance(mail_to, str):
        try:
            decoded = json.loads(mail_to)
            if isinstance(decoded, list):
                mail_to = decoded
        except (ValueError, TypeError):
            pass

    return {
        "job_id": record.id,
        "status": "completed",
        "analyst_notes": record.analyst_notes,
        "email": {
            "filename":        record.filename,
            "subject":         record.mail_subject,
            "from":            record.mail_from,
            "to":              mail_to,
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
            "matched_campaign_id":     bi.get("matched_campaign_id", ""),
            "matched_campaign_name":   bi.get("matched_campaign_name", ""),
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
    """
    Prepara la risposta JSON per il client con tutti i risultati dell'analisi.

    Struttura risposta:
    - job_id, status="completed"
    - email: metadata (filename, subject, from, to, date, message_id, file_hash, parse_errors)
    - risk: score, label, explanation, detailed contributions per modulo
    - header_analysis: SPF/DKIM/DMARC, injection, bulk sender, etc.
    - body_analysis: phishing patterns, urgency, credentials, homoglyphs, forms, JS
    - url_analysis: lista URL con risk score, IP, whois age, shortener, TLS, DNS
    - attachment_analysis: file count, mime types, macro detection, VBA signatures
    - reputation_results: results da servizi di reputazione (dopo fase 2 background)

    Args:
        job_id: UUID unico dell'analisi
        parsed: ParsedEmail con metadata e content
        header_result: HeaderAnalysisResult da analyze_headers()
        body_result: BodyAnalysisResult da analyze_body()
        url_result: URLAnalysisResult da analyze_urls()
        attachment_result: AttachmentAnalysisResult da analyze_attachments()
        risk: RiskScore con score finale e spiegazione
        do_whois: boolean che determina se WHOIS è stato eseguito (info nella response)

    Returns:
        dict pronto per JSON serializzazione e invio al client
    """
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
            "matched_campaign_id": body_result.matched_campaign_id,
            "matched_campaign_name": body_result.matched_campaign_name,
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


import bleach as _bleach
from bleach.css_sanitizer import CSSSanitizer as _CSSSanitizer

# Proprietà CSS sicure per le anteprime email — ricreato una sola volta a livello modulo
_HTML_CSS_SANITIZER = _CSSSanitizer(
    allowed_css_properties=[
        'background-color', 'border', 'border-collapse', 'border-color',
        'border-radius', 'border-spacing', 'border-style', 'border-width',
        'color', 'display', 'font-family', 'font-size', 'font-style',
        'font-weight', 'height', 'line-height', 'margin', 'margin-bottom',
        'margin-left', 'margin-right', 'margin-top', 'max-width', 'min-width',
        'padding', 'padding-bottom', 'padding-left', 'padding-right',
        'padding-top', 'text-align', 'text-decoration', 'vertical-align',
        'width', 'white-space', 'word-break', 'word-wrap',
    ]
)

# Allowlist di tag HTML sicuri per email preview.
# Tag esclusi per protezione: script, style, iframe, form, input, meta, link (no remote resources/code execution)
_BLEACH_ALLOWED_TAGS = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'caption',
    'cite', 'code', 'dd', 'del', 'dfn', 'div', 'dl', 'dt', 'em',
    'figcaption', 'figure', 'footer', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'header', 'hr', 'i', 'img', 'ins', 'kbd', 'li', 'main', 'mark',
    'ol', 'p', 'pre', 'q', 's', 'samp', 'section', 'small', 'span',
    'strong', 'sub', 'summary', 'sup', 'table', 'tbody', 'td', 'th',
    'thead', 'time', 'tr', 'u', 'ul',
]

_BLEACH_ALLOWED_ATTRS = {
    '*':    ['class', 'id', 'style', 'title'],
    'a':    ['href', 'title'],
    'img':  ['alt', 'width', 'height'],
    'td':   ['colspan', 'rowspan', 'align', 'valign'],
    'th':   ['colspan', 'rowspan', 'align', 'valign', 'scope'],
    'col':  ['span', 'width'],
}


def _sanitize_email_html(html_body: str) -> str:
    """Sanitizza HTML email per anteprima sicura nell'analista.

    - Allowlist di tag sicuri (no script, no form, no iframe, no object)
    - CSS inline filtrato con CSSSanitizer (allowlist proprietà sicure)
    - Sostituisce img src con placeholder GIF 1px (blocca risorse esterne)
    - Disabilita tutti i link (href → #, pointer-events:none via CSS)
    - Avvolge in documento HTML con CSP strict inline
    """
    import re as _re

    cleaned = _bleach.clean(
        html_body,
        tags=_BLEACH_ALLOWED_TAGS,
        attributes=_BLEACH_ALLOWED_ATTRS,
        strip=True,
        strip_comments=True,
        css_sanitizer=_HTML_CSS_SANITIZER,
    )

    _BLANK_GIF = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
    # Replace existing img src with blank GIF placeholder
    cleaned = _re.sub(
        r'(<img\b[^>]*?)\s+src=["\'][^"\']*["\']',
        rf'\1 src="{_BLANK_GIF}"',
        cleaned, flags=_re.IGNORECASE,
    )
    # Add placeholder to img tags without src
    cleaned = _re.sub(
        r'(<img\b(?![^>]*\bsrc=)[^>]*)(/?>)',
        rf'\1 src="{_BLANK_GIF}"\2',
        cleaned, flags=_re.IGNORECASE,
    )
    # Disable all links: replace href value with #
    cleaned = _re.sub(
        r'(<a\b[^>]*?)\s+href=["\'][^"\']*["\']',
        r'\1 href="#"',
        cleaned, flags=_re.IGNORECASE,
    )
    # Add href="#" to <a> tags that have no href
    cleaned = _re.sub(
        r'(<a\b(?![^>]*\bhref=)[^>]*)(/?>)',
        r'\1 href="#"\2',
        cleaned, flags=_re.IGNORECASE,
    )

    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        'style-src \'unsafe-inline\'; img-src data:; script-src \'none\'; '
        'connect-src \'none\'; frame-src \'none\';">'
        '<style>body{font-family:sans-serif;font-size:13px;padding:12px;margin:0;'
        'color:#222;background:#fff;word-break:break-word}'
        'a{color:#888;text-decoration:underline;pointer-events:none;cursor:default}'
        'img{max-width:100%;height:auto}*{box-sizing:border-box}</style>'
        f'</head><body>{cleaned}</body></html>'
    )


@router.get("/{job_id}/body")
async def get_email_body(
    job_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Restituisce il contenuto testuale e HTML dell'email.

    L'HTML è sanitizzato con bleach (allowlist tag), img src sostituiti con
    placeholder, link disabilitati e avvolto in documento con CSP strict.
    Sicuro per l'anteprima in iframe sandbox.
    """
    import re, asyncio
    if not re.match(r'^[0-9a-f-]{36}$', job_id):
        raise HTTPException(status_code=400, detail=t("analysis.invalid_job_id"))

    record = await db.get(EmailAnalysis, job_id)
    if not record:
        raise HTTPException(status_code=404, detail=t("analysis.not_found"))

    file_path = _find_upload_file(job_id)
    raw = file_path.read_bytes()

    loop = asyncio.get_running_loop()
    parsed = await loop.run_in_executor(None, parse_email_file, raw, file_path.name)

    body_text = (parsed.body_text or "").strip()[:50_000]
    sanitized_html = _sanitize_email_html(parsed.body_html) if parsed.body_html else None

    return {
        "job_id":             job_id,
        "has_text":           bool(body_text),
        "has_html":           bool(parsed.body_html),
        "body_text":          body_text,
        "body_html_sanitized": sanitized_html,
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
        raise HTTPException(status_code=400, detail=t("analysis.invalid_job_id"))

    record = await db.get(EmailAnalysis, job_id)
    if not record:
        raise HTTPException(status_code=404, detail=t("analysis.not_found"))

    if len(body.notes) > 10000:
        raise HTTPException(status_code=400, detail=t("analysis.notes_too_long"))

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
        raise HTTPException(status_code=400, detail=t("analysis.invalid_job_id"))

    record = await db.get(EmailAnalysis, job_id)
    if not record:
        raise HTTPException(status_code=404, detail=t("analysis.not_found"))

    # Cleanup file first, then delete from DB (atomic semantic)
    # If file cleanup fails, DB delete won't execute
    try:
        files_removed = _cleanup_files(job_id)
    except Exception as e:
        _logger.error("[%s] [FILE CLEANUP ERROR] Failed to delete files: %s", job_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=t("analysis.delete_error"))

    # File cleanup succeeded, safe to delete from DB
    try:
        await db.delete(record)
        await db.commit()
    except Exception as e:
        _logger.error("[%s] [DB DELETE ERROR] Failed to delete from database: %s", job_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=t("analysis.delete_error"))

    # VACUUM is non-critical, don't fail if it errors
    try:
        await _vacuum_db()
    except Exception as e:
        _logger.warning("[%s] [VACUUM WARNING] Database compaction failed (non-critical): %s", job_id, e)

    return {"status": "deleted", "job_id": job_id, "files_removed": files_removed}