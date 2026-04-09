"""
core/analysis/attachment_analyzer.py

Analisi statica degli allegati:
- Hash MD5 / SHA1 / SHA256 (già calcolati dal parser)
- Mismatch MIME dichiarato vs reale
- Rilevamento macro Office
- JavaScript in PDF
- Stream sospetti PDF
- Doppia estensione

IMPORTANTE: nessun file viene eseguito. Solo analisi statica dei byte.
"""

import re
from utils.i18n import t
from dataclasses import dataclass, field
from typing import Optional


# Estensioni eseguibili / pericolose
DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".com", ".ps1", ".vbs", ".js", ".jse",
    ".wsf", ".wsh", ".msi", ".scr", ".pif", ".hta", ".cpl",
    ".dll", ".sys", ".lnk", ".reg",
}

# Magic bytes per rilevamento grezzo
OFFICE_MAGIC = b"\xD0\xCF\x11\xE0"           # OLE2 (.doc, .xls, .ppt vecchi)
OOXML_MAGIC = b"\x50\x4B\x03\x04"            # ZIP / OOXML (.docx, .xlsx, .pptx)
PDF_MAGIC = b"%PDF"
ZIP_MAGIC = b"\x50\x4B"

# Pattern macro OLE (VBA)
VBA_SIGNATURES = [
    b"VBA",
    b"_VBA_PROJECT",
    b"ThisDocument",
    b"AutoOpen",
    b"AutoExec",
    b"Document_Open",
    b"Workbook_Open",
]

# Pattern JS in PDF
PDF_JS_PATTERNS = [
    rb"/JS\s",
    rb"/JavaScript",
    rb"eval\s*\(",
    rb"app\.alert",
    rb"this\.print",
]

# Pattern stream sospetti PDF
PDF_SUSPICIOUS_STREAMS = [
    rb"/AA\s",          # Additional Actions
    rb"/OpenAction",    # Azione all'apertura
    rb"/Launch",        # Lancia programma esterno
    rb"/EmbeddedFile",  # File embedded
    rb"/RichMedia",     # Flash / multimedia
    rb"/XFA",           # XML Forms Architecture (spesso usato in exploit)
]


@dataclass
class AttachmentFinding:
    severity: str  # info / low / medium / high / critical
    description: str
    evidence: str = ""


@dataclass
class AttachmentAnalysis:
    filename: str
    size_bytes: int
    declared_mime: str
    real_mime: str
    hash_md5: str
    hash_sha1: str
    hash_sha256: str
    mime_mismatch: bool
    findings: list[AttachmentFinding] = field(default_factory=list)
    has_macro: bool = False
    has_js: bool = False
    has_suspicious_pdf_stream: bool = False
    double_extension: bool = False
    dangerous_extension: bool = False
    risk_score: float = 0.0


@dataclass
class AttachmentAnalysisResult:
    attachments: list[AttachmentAnalysis] = field(default_factory=list)
    total_attachments: int = 0
    critical_count: int = 0
    score_contribution: float = 0.0


def _check_double_extension(filename: str) -> bool:
    """Rileva doppia estensione tipo 'invoice.pdf.exe'."""
    parts = filename.lower().split(".")
    if len(parts) >= 3:
        # Controlla se la penultima estensione è comune (pdf, doc, jpg, ecc.)
        common_exts = {"pdf", "doc", "docx", "xls", "xlsx", "jpg", "png", "zip", "txt"}
        return parts[-2] in common_exts and f".{parts[-1]}" in DANGEROUS_EXTENSIONS
    return False


def _analyze_office_ole(data: bytes) -> tuple[bool, list[str]]:
    """Cerca firme VBA in file OLE2 (Office legacy)."""
    evidences = []
    has_macro = False
    for sig in VBA_SIGNATURES:
        if sig in data:
            has_macro = True
            evidences.append(sig.decode("utf-8", errors="replace"))
    return has_macro, evidences


def _analyze_ooxml(data: bytes) -> tuple[bool, list[str]]:
    """
    File OOXML sono ZIP: cerca 'vbaProject.bin' nel TOC dello ZIP
    senza estrarlo (evita zip bomb: leggiamo solo i primi 32KB).
    """
    chunk = data[:32768]
    has_macro = b"vbaProject.bin" in chunk
    evidences = ["vbaProject.bin trovato nel file OOXML"] if has_macro else []
    return has_macro, evidences


def _analyze_pdf(data: bytes) -> tuple[bool, bool, list[str], list[str]]:
    """
    Cerca pattern JS e stream sospetti in PDF.
    Ritorna (has_js, has_suspicious_stream, js_evidences, stream_evidences).
    """
    js_found = False
    js_evidences = []
    stream_found = False
    stream_evidences = []

    # Leggiamo al massimo i primi 2MB per sicurezza
    chunk = data[:2097152]

    for pattern in PDF_JS_PATTERNS:
        if re.search(pattern, chunk):
            js_found = True
            js_evidences.append(pattern.decode("utf-8", errors="replace").strip())

    for pattern in PDF_SUSPICIOUS_STREAMS:
        if re.search(pattern, chunk):
            stream_found = True
            stream_evidences.append(pattern.decode("utf-8", errors="replace").strip())

    return js_found, stream_found, js_evidences, stream_evidences


def analyze_attachment(att: dict, raw_data: Optional[bytes] = None) -> AttachmentAnalysis:
    """
    Analizza un allegato.
    att: dict prodotto dal parser (filename, size_bytes, declared_mime, real_mime, hashes, mime_mismatch)
    raw_data: bytes dell'allegato (opzionale; se None alcune analisi approfondite non vengono eseguite)
    """
    analysis = AttachmentAnalysis(
        filename=att.get("filename", "unknown"),
        size_bytes=att.get("size_bytes", 0),
        declared_mime=att.get("declared_mime", ""),
        real_mime=att.get("real_mime", ""),
        hash_md5=att.get("hash_md5", ""),
        hash_sha1=att.get("hash_sha1", ""),
        hash_sha256=att.get("hash_sha256", ""),
        mime_mismatch=att.get("mime_mismatch", False),
    )

    filename_lower = analysis.filename.lower()
    import pathlib
    ext = pathlib.Path(filename_lower).suffix

    # 1. Estensione pericolosa
    if ext in DANGEROUS_EXTENSIONS:
        analysis.dangerous_extension = True
        analysis.findings.append(AttachmentFinding(
            severity="critical",
            description=t("att.dangerous_ext", ext=ext),
            evidence=analysis.filename,
        ))

    # 2. Doppia estensione
    if _check_double_extension(analysis.filename):
        analysis.double_extension = True
        analysis.findings.append(AttachmentFinding(
            severity="high",
            description=t("att.double_ext"),
            evidence=analysis.filename,
        ))

    # 3. Mismatch MIME
    if analysis.mime_mismatch:
        analysis.findings.append(AttachmentFinding(
            severity="high",
            description=t("att.mime_mismatch"),
            evidence=f"Dichiarato: {analysis.declared_mime} | Reale: {analysis.real_mime}",
        ))

    # 4. Analisi binaria (richiede raw_data)
    if raw_data:
        # Office OLE2
        if raw_data[:4] == OFFICE_MAGIC:
            has_macro, evidences = _analyze_office_ole(raw_data)
            if has_macro:
                analysis.has_macro = True
                analysis.findings.append(AttachmentFinding(
                    severity="critical",
                    description=t("att.macro_ole"),
                    evidence=", ".join(evidences),
                ))

        # OOXML (ZIP-based)
        elif raw_data[:4] == OOXML_MAGIC:
            has_macro, evidences = _analyze_ooxml(raw_data)
            if has_macro:
                analysis.has_macro = True
                analysis.findings.append(AttachmentFinding(
                    severity="critical",
                    description=t("att.macro_ooxml"),
                    evidence=", ".join(evidences),
                ))

        # PDF
        elif raw_data[:4] == PDF_MAGIC:
            has_js, has_stream, js_ev, stream_ev = _analyze_pdf(raw_data)
            if has_js:
                analysis.has_js = True
                analysis.findings.append(AttachmentFinding(
                    severity="critical",
                    description=t("att.pdf_js"),
                    evidence=", ".join(js_ev),
                ))
            if has_stream:
                analysis.has_suspicious_pdf_stream = True
                analysis.findings.append(AttachmentFinding(
                    severity="high",
                    description=t("att.pdf_stream"),
                    evidence=", ".join(stream_ev),
                ))

    # Risk score
    weights = {"info": 0, "low": 5, "medium": 15, "high": 25, "critical": 40}
    analysis.risk_score = min(sum(weights.get(f.severity, 0) for f in analysis.findings), 100.0)

    return analysis


def analyze_attachments(attachments: list[dict]) -> AttachmentAnalysisResult:
    """Analizza tutti gli allegati (solo metadati, no raw_data in questa fase)."""
    result = AttachmentAnalysisResult()
    result.total_attachments = len(attachments)

    for att in attachments:
        analysis = analyze_attachment(att, raw_data=None)
        result.attachments.append(analysis)
        if any(f.severity == "critical" for f in analysis.findings):
            result.critical_count += 1

    if result.attachments:
        scores = [a.risk_score for a in result.attachments]
        result.score_contribution = min(max(scores) + result.critical_count * 10, 100.0)

    return result
