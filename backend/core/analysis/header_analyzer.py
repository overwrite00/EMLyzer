"""
core/analysis/header_analyzer.py

Analisi forense degli header email:
- Mismatch di identità (From vs Return-Path vs Reply-To)
- Ricostruzione percorso SMTP (Received chain)
- Rilevamento header forging / injection
- Tool di invio massivo
- Risultati SPF/DKIM/DMARC
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from core.analysis.email_parser import ParsedEmail
from utils.i18n import t


# Noti tool di invio massivo (X-Mailer / User-Agent)
BULK_SENDER_PATTERNS = [
    r"mailchimp", r"sendgrid", r"mailgun", r"constant.?contact",
    r"aweber", r"getresponse", r"klaviyo", r"brevo", r"sendinblue",
    r"phpmailer", r"swiftmailer", r"massmailer", r"bulkmailer",
    r"gmass", r"lemlist", r"woodpecker", r"outreach", r"salesloft",
]

# Pattern sospetti nei campi header (injection)
HEADER_INJECTION_PATTERNS = [
    r"\r\n", r"\n\n", r"%0a", r"%0d", r"\x00",
]

import ipaddress as _ipaddress

# Regex per estrarre IP (v4 e v6) dai Received header
# Formati RFC supportati:
#   [IPv6:2001:db8::1]   — prefisso esplicito (Gmail, Postfix)
#   [2001:db8::1]        — IPv6 senza prefisso
#   [203.0.113.42]       — IPv4 classico
_IP_IN_RECEIVED_RE = re.compile(
    r"\[IPv6:([0-9a-fA-F:]+)\]"           # IPv6 con prefisso esplicito
    r"|\[(\d{1,3}(?:\.\d{1,3}){3})\]"  # IPv4 classico
    r"|\[([0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{0,4}){2,7})\]",  # IPv6 senza prefisso
    re.IGNORECASE,
)

def _extract_ip_from_received(received: str) -> tuple[str | None, bool]:
    """
    Estrae il primo IP (v4 o v6) da un Received header.
    Ritorna (ip_str_normalizzato, is_private).
    """
    m = _IP_IN_RECEIVED_RE.search(received)
    if not m:
        return None, False
    raw = m.group(1) or m.group(2) or m.group(3)
    if not raw:
        return None, False
    try:
        addr = _ipaddress.ip_address(raw)
        return str(addr), addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return None, False

def _is_private_ip(ip_str: str) -> bool:
    """True se l'IP è privato/riservato."""
    try:
        addr = _ipaddress.ip_address(ip_str.strip().strip("[]"))
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return True


@dataclass
class HeaderFinding:
    field: str
    severity: str  # info / low / medium / high
    description: str
    evidence: str = ""


@dataclass
class HeaderAnalysisResult:
    findings: list[HeaderFinding] = field(default_factory=list)
    identity_mismatches: list[str] = field(default_factory=list)
    bulk_sender_detected: bool = False
    bulk_sender_tool: str = ""
    spf_ok: bool = False
    dkim_ok: bool = False
    dmarc_ok: bool = False
    auth_summary: str = ""
    received_hops: list[dict] = field(default_factory=list)
    injection_attempts: list[str] = field(default_factory=list)
    score_contribution: float = 0.0


def _extract_domain(address: str) -> str:
    """Estrae il dominio da un indirizzo email, ignorando il display name."""
    m = re.search(r"@([\w.\-]+)", address)
    return m.group(1).lower() if m else ""


def _check_identity_mismatch(parsed: ParsedEmail, result: HeaderAnalysisResult):
    """Confronta From, Return-Path, Reply-To per individuare mismatch."""
    from_domain = _extract_domain(parsed.mail_from)
    rp_domain = _extract_domain(parsed.return_path)
    rt_domain = _extract_domain(parsed.reply_to)

    if from_domain and rp_domain and from_domain != rp_domain:
        desc = f"From domain '{from_domain}' ≠ Return-Path domain '{rp_domain}'"
        result.identity_mismatches.append(desc)
        result.findings.append(HeaderFinding(
            field="From/Return-Path",
            severity="high",
            description=t("header.from_rp_mismatch"),
            evidence=desc,
        ))

    if from_domain and rt_domain and from_domain != rt_domain:
        desc = f"From domain '{from_domain}' ≠ Reply-To domain '{rt_domain}'"
        result.identity_mismatches.append(desc)
        result.findings.append(HeaderFinding(
            field="From/Reply-To",
            severity="medium",
            description=t("header.from_rt_mismatch"),
            evidence=desc,
        ))


def _check_auth(parsed: ParsedEmail, result: HeaderAnalysisResult):
    """Valuta i risultati SPF / DKIM / DMARC."""
    spf = parsed.spf_result.lower()
    dkim = parsed.dkim_result.lower()
    dmarc = parsed.dmarc_result.lower()

    result.spf_ok = spf in ("pass",)
    result.dkim_ok = dkim in ("pass",)
    result.dmarc_ok = dmarc in ("pass",)

    if spf and spf not in ("pass", ""):
        result.findings.append(HeaderFinding(
            field="SPF",
            severity="high" if spf in ("fail", "hardfail") else "medium",
            description=t("header.spf_result", result=spf),
            evidence=f"Received-SPF / Authentication-Results: spf={spf}",
        ))

    if dkim and not result.dkim_ok:
        result.findings.append(HeaderFinding(
            field="DKIM",
            severity="high",
            description=t("header.dkim_result", result=dkim),
            evidence=f"Authentication-Results: dkim={dkim}",
        ))

    if dmarc and not result.dmarc_ok:
        result.findings.append(HeaderFinding(
            field="DMARC",
            severity="high",
            description=t("header.dmarc_result", result=dmarc),
            evidence=f"Authentication-Results: dmarc={dmarc}",
        ))

    failed = sum([not result.spf_ok and bool(spf),
                  not result.dkim_ok and bool(dkim),
                  not result.dmarc_ok and bool(dmarc)])
    if failed == 3:
        result.auth_summary = t("header.auth_all_fail")
    elif failed > 0:
        result.auth_summary = t("header.auth_partial", n=failed)
    else:
        result.auth_summary = t("header.auth_ok") if (spf or dkim or dmarc) else t("header.auth_absent")


def _check_bulk_sender(parsed: ParsedEmail, result: HeaderAnalysisResult):
    """Rileva tool di invio massivo tramite X-Mailer / User-Agent."""
    mailer = parsed.x_mailer.lower()
    if not mailer:
        return
    for pattern in BULK_SENDER_PATTERNS:
        if re.search(pattern, mailer, re.IGNORECASE):
            result.bulk_sender_detected = True
            result.bulk_sender_tool = parsed.x_mailer
            result.findings.append(HeaderFinding(
                field="X-Mailer",
                severity="info",
                description=t("header.bulk_sender", tool=parsed.x_mailer),
                evidence=f"X-Mailer: {parsed.x_mailer}",
            ))
            break


def _check_header_injection(parsed: ParsedEmail, result: HeaderAnalysisResult):
    """Cerca sequenze di header injection nei campi critici."""
    fields_to_check = {
        "Subject": parsed.mail_subject,
        "From": parsed.mail_from,
        "Reply-To": parsed.reply_to,
        "Message-ID": parsed.message_id,
    }
    for field_name, value in fields_to_check.items():
        if not value:
            continue
        for pattern in HEADER_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                result.injection_attempts.append(field_name)
                result.findings.append(HeaderFinding(
                    field=field_name,
                    severity="high",
                    description=t("header.injection", field=field_name),
                    evidence=repr(value[:200]),
                ))


def _parse_received_chain(parsed: ParsedEmail, result: HeaderAnalysisResult):
    """
    Analizza la catena Received per ricostruire il percorso SMTP.
    I Received header sono in ordine inverso nel messaggio (ogni server aggiunge in cima):
    get_all() restituisce [ultimo_hop, ..., primo_hop].
    Invertendo, hop 1 = mittente originale, hop N = server di destinazione finale.
    """
    for i, received in enumerate(reversed(parsed.received_chain)):
        hop: dict = {"hop": i + 1, "raw": received[:300]}

        # Estrai IP (IPv4 e IPv6)
        ip_str, is_private = _extract_ip_from_received(received)
        if ip_str:
            hop["ip"] = ip_str
            if is_private:
                hop["private_ip"] = True

        # Estrai "by" hostname
        by_m = re.search(r"\bby\s+([\w.\-]+)", received, re.IGNORECASE)
        if by_m:
            hop["by"] = by_m.group(1)

        # Estrai timestamp
        ts_m = re.search(r";\s*(.+)$", received.strip())
        if ts_m:
            hop["timestamp"] = ts_m.group(1).strip()

        result.received_hops.append(hop)


def _check_originating_ip(parsed: ParsedEmail, result: HeaderAnalysisResult):
    """Controlla X-Originating-IP per IP privati o anomali."""
    ip = parsed.x_originating_ip.strip()
    if not ip:
        return
    # Rimuovi parentesi quadre se presenti
    ip = ip.strip("[]")
    if _is_private_ip(ip):
        result.findings.append(HeaderFinding(
            field="X-Originating-IP",
            severity="medium",
            description=t("header.private_ip", ip=ip),
            evidence=ip,
        ))


def _check_missing_fields(parsed: ParsedEmail, result: HeaderAnalysisResult):
    """Segnala assenza di campi importanti."""
    if not parsed.message_id:
        result.findings.append(HeaderFinding(
            field="Message-ID",
            severity="medium",
            description=t("header.no_message_id"),
        ))
    if not parsed.mail_date:
        result.findings.append(HeaderFinding(
            field="Date",
            severity="low",
            description=t("header.no_date"),
        ))


def _compute_score(result: HeaderAnalysisResult) -> float:
    """Calcola un punteggio di rischio parziale basato sui findings."""
    weights = {"info": 0, "low": 5, "medium": 15, "high": 25}
    score = sum(weights.get(f.severity, 0) for f in result.findings)
    return min(score, 100.0)


def analyze_headers(parsed: ParsedEmail) -> HeaderAnalysisResult:
    """Entry point: esegue tutte le analisi header e restituisce HeaderAnalysisResult."""
    result = HeaderAnalysisResult()

    _check_identity_mismatch(parsed, result)
    _check_auth(parsed, result)
    _check_bulk_sender(parsed, result)
    _check_header_injection(parsed, result)
    _parse_received_chain(parsed, result)
    _check_originating_ip(parsed, result)
    _check_missing_fields(parsed, result)

    result.score_contribution = _compute_score(result)
    return result