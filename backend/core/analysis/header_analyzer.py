"""
core/analysis/header_analyzer.py

Analisi degli header email:
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

# DNS queries (dnspython già in requirements.txt)
try:
    import dns.resolver
    import dns.exception
    _DNS_AVAILABLE = True
except ImportError:
    _DNS_AVAILABLE = False


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


# ── AuthDetail ───────────────────────────────────────────────────────────────

@dataclass
class AuthDetail:
    """Sub-campi verbosi di SPF, DKIM e DMARC — stile MXToolbox."""

    # ── SPF ──────────────────────────────────────────────────────────────────
    spf_result: str = ""
    spf_client_ip: str = ""          # IP del server mittente (da Authentication-Results o Received-SPF)
    spf_envelope_from: str = ""      # smtp.mailfrom / envelope-from
    spf_dns_record: str = ""         # record TXT da DNS (v=spf1 ...)
    spf_dns_error: str = ""          # errore DNS se la query fallisce

    # ── DKIM ─────────────────────────────────────────────────────────────────
    # Lista di dict — una per ciascuna firma DKIM-Signature nell'email
    # Ogni dict: { d, s, a, c, h (lista), bh (16 chars), result,
    #              dns_key_found (bool), dns_key_truncated, dns_error }
    dkim_signatures: list[dict] = field(default_factory=list)

    # ── SPF failure reason ───────────────────────────────────────────────────
    spf_failure_reason: str = ""     # testo esplicativo (da parentesi Authentication-Results o Received-SPF)

    # ── DKIM failure reason ──────────────────────────────────────────────────
    dkim_failure_reason: str = ""    # testo esplicativo (da parentesi Authentication-Results)

    # ── DMARC ────────────────────────────────────────────────────────────────
    dmarc_result: str = ""
    dmarc_from_domain: str = ""      # dominio nel campo From:
    dmarc_dns_record: str = ""       # record TXT da DNS (v=DMARC1; ...)
    dmarc_policy: str = ""           # p=  (none / quarantine / reject)
    dmarc_subdomain_policy: str = "" # sp=
    dmarc_adkim: str = ""            # adkim= (r=relaxed, s=strict)
    dmarc_aspf: str = ""             # aspf=
    dmarc_pct: str = "100"           # pct= (percentuale messaggi coperti)
    dmarc_rua: str = ""              # rua= (URI aggregate report)
    dmarc_dns_error: str = ""
    dmarc_failure_reason: str = ""   # sintesi: quali allineamenti sono falliti


# ── HeaderFinding ─────────────────────────────────────────────────────────────

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
    spf_result: str = ""    # valore raw: pass / fail / softfail / neutral / none / …
    dkim_result: str = ""   # valore raw: pass / fail / none / …
    dmarc_result: str = ""  # valore raw: pass / fail / none / …
    auth_summary: str = ""
    auth_detail: AuthDetail = field(default_factory=AuthDetail)   # ← sub-campi verbosi
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


# ── Helpers per l'auth detail ─────────────────────────────────────────────────

def _tag(raw: str, key: str) -> str:
    """Estrae il valore di un tag `key=value` da un header DKIM/SPF/DMARC."""
    m = re.search(rf"\b{re.escape(key)}=([^;\s]+)", raw, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _parse_dkim_signature(raw: str) -> dict:
    """
    Parsifica un singolo header DKIM-Signature.
    Restituisce dict con: d, s, a, c, h (lista), bh (primi 16 chars).
    """
    # Normalizza: rimuovi continuazioni riga, schiaccia spazi
    clean = " ".join(raw.split())
    d  = _tag(clean, "d")
    s  = _tag(clean, "s")
    a  = _tag(clean, "a")
    c  = _tag(clean, "c")
    bh = _tag(clean, "bh")
    h_raw = _tag(clean, "h")
    h_list = [x.strip() for x in h_raw.split(":")] if h_raw else []
    return {
        "d":  d,
        "s":  s,
        "a":  a,
        "c":  c,
        "h":  h_list,
        "bh": bh[:16] + ("…" if len(bh) > 16 else ""),
    }


def _parse_auth_results_subfields(auth_headers: list[str]) -> dict:
    """
    Estrae sub-campi dall'ultimo Authentication-Results header (quello
    aggiunto dal server ricevente finale, tipicamente il più in basso).

    Restituisce dict con:
      spf_client_ip, spf_envelope_from,
      dkim_header_d, dkim_header_s, dkim_header_b,
      dmarc_header_from
    """
    if not auth_headers:
        return {}
    raw = " ".join(auth_headers[-1].split())  # LAST header, spazi normalizzati

    out: dict = {}

    # ── SPF sub-campi ──
    # Formato Gmail:  spf=pass (google.com: domain of x@y.com designates 1.2.3.4 as permitted sender) smtp.mailfrom=x@y.com
    # Formato Outlook: spf=pass (sender IP is 1.2.3.4) smtp.mailfrom=outlook.com
    # client-ip=1.2.3.4 può apparire come tag separato (alcuni server)

    # Motivo SPF: testo tra parentesi subito dopo "spf=<risultato>"
    m_spf_par = re.search(r"spf=\w+\s*\(([^)]+)\)", raw, re.IGNORECASE)
    out["spf_reason"] = m_spf_par.group(1).strip() if m_spf_par else ""

    spf_client_ip = _tag(raw, "client-ip")
    if not spf_client_ip:
        # Prova a estrarre dall'interno delle parentesi: "designates 1.2.3.4 as"
        m = re.search(r"designates\s+([\d.:a-fA-F]+)\s+as", raw, re.IGNORECASE)
        if m:
            spf_client_ip = m.group(1)
    if not spf_client_ip:
        # Formato Outlook: "sender IP is 1.2.3.4"
        m = re.search(r"sender\s+IP\s+is\s+([\d.:a-fA-F]+)", raw, re.IGNORECASE)
        if m:
            spf_client_ip = m.group(1)
    out["spf_client_ip"] = spf_client_ip

    envelope = _tag(raw, "smtp.mailfrom") or _tag(raw, "envelope-from")
    out["spf_envelope_from"] = envelope

    # ── DKIM sub-campi ──
    # Motivo DKIM: testo tra parentesi subito dopo "dkim=<risultato>"
    m_dkim_par = re.search(r"dkim=\w+\s*\(([^)]+)\)", raw, re.IGNORECASE)
    out["dkim_reason"] = m_dkim_par.group(1).strip() if m_dkim_par else ""

    out["dkim_header_d"] = _tag(raw, "header.d")
    out["dkim_header_s"] = _tag(raw, "header.s")
    b_val = _tag(raw, "header.b")
    out["dkim_header_b"] = b_val[:8] + ("…" if len(b_val) > 8 else "") if b_val else ""

    # ── DMARC sub-campi ──
    out["dmarc_header_from"] = _tag(raw, "header.from")

    # DMARC parentesi: (p=REJECT sp=REJECT dis=NONE) oppure (p=NONE)
    m_par = re.search(r"dmarc=\w+\s*\(([^)]+)\)", raw, re.IGNORECASE)
    if m_par:
        par = m_par.group(1)
        out["dmarc_par_p"]   = _tag(par, "p")
        out["dmarc_par_sp"]  = _tag(par, "sp")
    else:
        out["dmarc_par_p"]  = ""
        out["dmarc_par_sp"] = ""

    return out


def _parse_dmarc_dns_record(record: str) -> dict:
    """Estrae i tag principali da un record TXT DMARC (v=DMARC1; ...)."""
    return {
        "policy":            _tag(record, "p").lower(),
        "subdomain_policy":  _tag(record, "sp").lower(),
        "adkim":             _tag(record, "adkim").lower() or "r",   # default relaxed
        "aspf":              _tag(record, "aspf").lower() or "r",
        "pct":               _tag(record, "pct") or "100",
        "rua":               _tag(record, "rua"),
    }


# ── DNS queries (dnspython) ────────────────────────────────────────────────────

def _dns_query_txt(qname: str) -> tuple[list[str], str]:
    """
    Esegue una query DNS TXT con timeout breve (2s).
    Restituisce (lista_record_stringa, errore).
    """
    if not _DNS_AVAILABLE:
        return [], "dnspython non disponibile"
    try:
        resolver = dns.resolver.Resolver()
        resolver.lifetime = 2.0
        answers = resolver.resolve(qname, "TXT")
        records = []
        for rdata in answers:
            # rdata.strings è una lista di bytes
            joined = b"".join(rdata.strings).decode("utf-8", errors="replace")
            records.append(joined)
        return records, ""
    except dns.resolver.NXDOMAIN:
        return [], "NXDOMAIN"
    except dns.resolver.NoAnswer:
        return [], "NoAnswer"
    except dns.exception.Timeout:
        return [], "timeout"
    except Exception as e:
        return [], str(e)[:80]


def _query_spf_record(domain: str) -> tuple[str, str]:
    """Recupera il record SPF TXT per `domain`. Restituisce (record, errore)."""
    if not domain:
        return "", ""
    records, err = _dns_query_txt(domain)
    for r in records:
        if r.lower().startswith("v=spf1"):
            return r, ""
    return "", err or "record SPF non trovato"


def _query_dmarc_record(from_domain: str) -> tuple[str, str]:
    """Recupera il record DMARC TXT per `_dmarc.<from_domain>`."""
    if not from_domain:
        return "", ""
    records, err = _dns_query_txt(f"_dmarc.{from_domain}")
    for r in records:
        if r.lower().startswith("v=dmarc1"):
            return r, ""
    return "", err or "record DMARC non trovato"


def _query_dkim_key(selector: str, domain: str) -> tuple[str, bool, str]:
    """
    Recupera la chiave pubblica DKIM da `<selector>._domainkey.<domain>`.
    Restituisce (chiave_troncata, trovata, errore).
    """
    if not selector or not domain:
        return "", False, "selector o domain mancante"
    records, err = _dns_query_txt(f"{selector}._domainkey.{domain}")
    for r in records:
        # Il record contiene p=<base64_chiave>
        p_val = _tag(r, "p")
        if p_val:
            truncated = p_val[:32] + ("…" if len(p_val) > 32 else "")
            return truncated, True, ""
    return "", False, err or "chiave non trovata"


# ── _check_auth ───────────────────────────────────────────────────────────────

def _check_auth(parsed: ParsedEmail, result: HeaderAnalysisResult):
    """Valuta i risultati SPF / DKIM / DMARC."""
    spf = parsed.spf_result.lower()
    dkim = parsed.dkim_result.lower()
    dmarc = parsed.dmarc_result.lower()

    result.spf_ok = spf in ("pass",)
    result.dkim_ok = dkim in ("pass",)
    result.dmarc_ok = dmarc in ("pass",)

    # Espone i valori raw al frontend per la visualizzazione dettagliata
    result.spf_result = spf
    result.dkim_result = dkim
    result.dmarc_result = dmarc

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

    # ── Analisi dettagliata ───────────────────────────────────────────────────
    _build_auth_detail(parsed, result)


def _build_auth_detail(parsed: ParsedEmail, result: HeaderAnalysisResult) -> None:
    """
    Costruisce `result.auth_detail` con tutti i sub-campi verbosi di
    SPF, DKIM e DMARC (parsing header + query DNS indipendente).
    Gli errori DNS non bloccano mai l'analisi.
    """
    ad = result.auth_detail

    # ── Sub-campi da Authentication-Results ──────────────────────────────────
    sub = _parse_auth_results_subfields(parsed.auth_results_raw)

    # ── SPF ──────────────────────────────────────────────────────────────────
    ad.spf_result       = result.spf_result
    ad.spf_client_ip    = sub.get("spf_client_ip", "")
    ad.spf_envelope_from = sub.get("spf_envelope_from", "")

    # IP da Received-SPF se non trovato in Authentication-Results
    if not ad.spf_client_ip and parsed.received_spf_raw:
        m = re.search(r"client-ip=([\d.:a-fA-F]+)", parsed.received_spf_raw, re.IGNORECASE)
        if m:
            ad.spf_client_ip = m.group(1)
    if not ad.spf_envelope_from and parsed.received_spf_raw:
        m = re.search(r"envelope-from=<([^>]+)>", parsed.received_spf_raw, re.IGNORECASE)
        if m:
            ad.spf_envelope_from = m.group(1)

    # Motivo fallimento SPF (solo se SPF non è pass/none/assente)
    if result.spf_result and result.spf_result not in ("pass", "none"):
        reason = sub.get("spf_reason", "")
        if not reason and parsed.received_spf_raw:
            m = re.search(r"\(([^)]{5,})\)", parsed.received_spf_raw)
            if m:
                reason = m.group(1).strip()
        ad.spf_failure_reason = reason

    # DNS: recupera record SPF per il dominio envelope-from (o From)
    spf_domain = ""
    if ad.spf_envelope_from:
        m = re.search(r"@([\w.\-]+)", ad.spf_envelope_from)
        spf_domain = m.group(1) if m else ad.spf_envelope_from
    if not spf_domain:
        m = re.search(r"@([\w.\-]+)", parsed.mail_from or "")
        spf_domain = m.group(1) if m else ""
    if spf_domain:
        ad.spf_dns_record, ad.spf_dns_error = _query_spf_record(spf_domain)

    # ── DKIM ─────────────────────────────────────────────────────────────────
    ad.dkim_signatures = []

    # Usa le firme dall'header DKIM-Signature (una o più)
    raw_sigs = parsed.dkim_signatures_raw or []

    # Determina il risultato per ogni firma: se c'è solo una firma,
    # il risultato globale si applica; con più firme il campo può avere
    # più valori separati da virgola (raro) — usiamo il globale per ora.
    global_dkim_result = result.dkim_result

    for sig_raw in raw_sigs:
        sig = _parse_dkim_signature(sig_raw)
        sig["result"] = global_dkim_result  # associa risultato

        # DNS: verifica esistenza chiave pubblica
        if sig.get("s") and sig.get("d"):
            key_trunc, found, dns_err = _query_dkim_key(sig["s"], sig["d"])
            sig["dns_key_found"]     = found
            sig["dns_key_truncated"] = key_trunc
            sig["dns_error"]         = dns_err
        else:
            sig["dns_key_found"]     = False
            sig["dns_key_truncated"] = ""
            sig["dns_error"]         = "selector o domain mancante nell'header"

        ad.dkim_signatures.append(sig)

    # Motivo fallimento DKIM (solo se DKIM non è pass/none/assente)
    if result.dkim_result and result.dkim_result not in ("pass", "none"):
        ad.dkim_failure_reason = sub.get("dkim_reason", "")

    # Se non ci sono header DKIM-Signature ma abbiamo un risultato
    # da Authentication-Results, creiamo una firma sintetica da quei dati
    if not ad.dkim_signatures and global_dkim_result:
        d = sub.get("dkim_header_d", "")
        s = sub.get("dkim_header_s", "")
        syn: dict = {
            "d":      d,
            "s":      s,
            "a":      "",
            "c":      "",
            "h":      [],
            "bh":     "",
            "result": global_dkim_result,
        }
        if d and s:
            key_trunc, found, dns_err = _query_dkim_key(s, d)
            syn["dns_key_found"]     = found
            syn["dns_key_truncated"] = key_trunc
            syn["dns_error"]         = dns_err
        else:
            syn["dns_key_found"]     = False
            syn["dns_key_truncated"] = ""
            syn["dns_error"]         = "dati DKIM-Signature non disponibili"
        if d or global_dkim_result:
            ad.dkim_signatures.append(syn)

    # ── DMARC ────────────────────────────────────────────────────────────────
    ad.dmarc_result = result.dmarc_result

    # Dominio From (usato per lookup _dmarc.domain)
    m = re.search(r"@([\w.\-]+)", parsed.mail_from or "")
    from_domain = m.group(1) if m else ""
    ad.dmarc_from_domain = from_domain or sub.get("dmarc_header_from", "")

    # Sub-campi dalla parentesi di Authentication-Results
    ad.dmarc_policy           = sub.get("dmarc_par_p", "").lower()
    ad.dmarc_subdomain_policy = sub.get("dmarc_par_sp", "").lower()

    # DNS: recupera record DMARC completo
    dmarc_domain = ad.dmarc_from_domain
    if dmarc_domain:
        dns_rec, dns_err = _query_dmarc_record(dmarc_domain)
        ad.dmarc_dns_record = dns_rec
        ad.dmarc_dns_error  = dns_err
        if dns_rec:
            parsed_dmarc = _parse_dmarc_dns_record(dns_rec)
            ad.dmarc_policy           = parsed_dmarc["policy"] or ad.dmarc_policy
            ad.dmarc_subdomain_policy = parsed_dmarc["subdomain_policy"] or ad.dmarc_subdomain_policy
            ad.dmarc_adkim            = parsed_dmarc["adkim"]
            ad.dmarc_aspf             = parsed_dmarc["aspf"]
            ad.dmarc_pct              = parsed_dmarc["pct"]
            ad.dmarc_rua              = parsed_dmarc["rua"]

    # Motivo fallimento DMARC: sintetizza dagli esiti SPF/DKIM
    if result.dmarc_result and result.dmarc_result not in ("pass", "none"):
        parts = []
        if result.spf_result and result.spf_result not in ("pass",):
            parts.append(f"SPF={result.spf_result}")
        if result.dkim_result and result.dkim_result not in ("pass",):
            parts.append(f"DKIM={result.dkim_result}")
        if parts:
            ad.dmarc_failure_reason = "Allineamento fallito: " + ", ".join(parts)
        elif result.spf_ok or result.dkim_ok:
            # SPF o DKIM passano ma non sono allineati con il dominio From
            ad.dmarc_failure_reason = "SPF/DKIM non allineati con il dominio From"


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


def _check_list_unsubscribe(parsed: ParsedEmail, result: HeaderAnalysisResult):
    """
    Analizza l'header List-Unsubscribe.
    Rileva: dominio esterno, HTTP non sicuro, IP diretto, formato malformato.
    Finding INFO se presente e corretto (bulk legittimo).
    """
    value = parsed.list_unsubscribe.strip()
    if not value:
        return

    from_domain = _extract_domain(parsed.mail_from)

    # Estrai tutti gli URI/indirizzi tra < >
    angle_items = re.findall(r"<([^>]+)>", value)
    if not angle_items:
        result.findings.append(HeaderFinding(
            field="List-Unsubscribe",
            severity="low",
            description=t("header.list_unsub_malformed"),
            evidence=value[:200],
        ))
        return

    has_http = False
    has_ip = False
    external_domain = ""

    for item in angle_items:
        item = item.strip()
        if item.lower().startswith("http://"):
            has_http = True
            # Controlla IP diretto
            m_ip = re.match(r"https?://([\d.]+|[0-9a-fA-F:]+)[/:]", item)
            if m_ip:
                has_ip = True
            # Controlla dominio esterno
            m_dom = re.match(r"https?://([^/:?#]+)", item)
            if m_dom and from_domain:
                link_domain = m_dom.group(1).lower()
                if not link_domain.endswith(from_domain):
                    external_domain = link_domain
        elif item.lower().startswith("https://"):
            # Controlla IP diretto
            m_ip = re.match(r"https?://([\d.]+)[/:]", item)
            if m_ip:
                has_ip = True
            # Controlla dominio esterno
            m_dom = re.match(r"https://([^/:?#]+)", item)
            if m_dom and from_domain:
                link_domain = m_dom.group(1).lower()
                if not link_domain.endswith(from_domain):
                    external_domain = link_domain
        elif item.lower().startswith("mailto:"):
            # Controlla dominio mailto vs mittente
            m = re.search(r"@([\w.\-]+)", item)
            if m and from_domain:
                mailto_domain = m.group(1).lower()
                if not mailto_domain.endswith(from_domain):
                    external_domain = mailto_domain

    if has_ip:
        result.findings.append(HeaderFinding(
            field="List-Unsubscribe",
            severity="high",
            description=t("header.list_unsub_ip"),
            evidence=value[:200],
        ))
    elif has_http:
        result.findings.append(HeaderFinding(
            field="List-Unsubscribe",
            severity="low",
            description=t("header.list_unsub_http"),
            evidence=value[:200],
        ))

    if external_domain:
        result.findings.append(HeaderFinding(
            field="List-Unsubscribe",
            severity="medium",
            description=t("header.list_unsub_external_domain", domain=external_domain),
            evidence=value[:200],
        ))

    # Se nessun problema rilevato, finding informativo (bulk legittimo)
    if not has_ip and not has_http and not external_domain:
        result.findings.append(HeaderFinding(
            field="List-Unsubscribe",
            severity="info",
            description=t("header.list_unsub_present"),
            evidence=value[:200],
        ))


def _check_campaign_id(parsed: ParsedEmail, result: HeaderAnalysisResult):
    """
    Analizza l'header X-Campaign-ID.
    Finding INFO se presente; LOW se manca il List-Unsubscribe.
    """
    value = parsed.x_campaign_id.strip()
    if not value:
        return

    result.findings.append(HeaderFinding(
        field="X-Campaign-ID",
        severity="info",
        description=t("header.campaign_id_detected", value=value[:100]),
        evidence=f"X-Campaign-ID: {value[:100]}",
    ))

    # Bulk email senza List-Unsubscribe → segnale sospetto
    if not parsed.list_unsubscribe.strip():
        result.findings.append(HeaderFinding(
            field="X-Campaign-ID",
            severity="low",
            description=t("header.campaign_no_unsub"),
            evidence=f"X-Campaign-ID presente ({value[:60]}) ma List-Unsubscribe assente",
        ))


def _check_arc_chain(parsed: ParsedEmail, result: HeaderAnalysisResult):
    """
    Valida la catena ARC (Authenticated Received Chain).
    Verifica sequenza i= negli ARC-Seal e cv= per manomissione.
    Se ARC assente, nessun finding (è opzionale).
    """
    seals = parsed.arc_seal_raw
    if not seals:
        return  # ARC opzionale — assenza normale

    # Estrai numeri i= da ciascun ARC-Seal
    instances = []
    has_fail = False
    for seal in seals:
        m_i = re.search(r"\bi=(\d+)", seal)
        if m_i:
            instances.append(int(m_i.group(1)))
        m_cv = re.search(r"\bcv=(\w+)", seal, re.IGNORECASE)
        if m_cv and m_cv.group(1).lower() == "fail":
            has_fail = True

    n = len(instances)

    if has_fail:
        result.findings.append(HeaderFinding(
            field="ARC-Seal",
            severity="high",
            description=t("header.arc_fail"),
            evidence=f"ARC-Seal cv=fail rilevato (catena: {sorted(instances)})",
        ))
        return

    # Controlla che la sequenza sia continua: {1, 2, ..., n}
    if instances:
        expected = set(range(1, n + 1))
        found_set = set(instances)
        if found_set != expected:
            found_str = ",".join(str(i) for i in sorted(found_set))
            result.findings.append(HeaderFinding(
                field="ARC-Seal",
                severity="medium",
                description=t("header.arc_incomplete", found=found_str),
                evidence=f"Attesi: {sorted(expected)}, trovati: {sorted(found_set)}",
            ))
            return

        result.findings.append(HeaderFinding(
            field="ARC-Seal",
            severity="info",
            description=t("header.arc_valid", n=n),
            evidence=f"Hop ARC: {sorted(instances)}",
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
    _check_list_unsubscribe(parsed, result)
    _check_campaign_id(parsed, result)
    _check_arc_chain(parsed, result)

    result.score_contribution = _compute_score(result)
    return result