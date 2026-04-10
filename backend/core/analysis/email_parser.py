"""
core/analysis/email_parser.py

Parses .eml and .msg files into a unified internal structure.
Cross-platform: uses pathlib, no Unix-specific calls.
No eval/exec. Input sanitized before processing.
"""

import hashlib
import re
import email
import email.header
import email.policy
from email import message_from_bytes
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import filetype


@dataclass
class ParsedEmail:
    """Unified representation of a parsed email, regardless of source format."""

    # Source info
    filename: str = ""
    file_size_bytes: int = 0
    file_hash_md5: str = ""
    file_hash_sha1: str = ""
    file_hash_sha256: str = ""

    # Headers
    mail_from: str = ""
    mail_to: list[str] = field(default_factory=list)
    mail_cc: list[str] = field(default_factory=list)
    mail_subject: str = ""
    mail_date: str = ""
    message_id: str = ""
    return_path: str = ""
    reply_to: str = ""
    x_mailer: str = ""
    x_originating_ip: str = ""
    x_campaign_id: str = ""
    list_unsubscribe: str = ""
    received_chain: list[str] = field(default_factory=list)

    # Auth — risultati sintetici (pass/fail/none/…)
    spf_result: str = ""
    dkim_result: str = ""
    dmarc_result: str = ""

    # Auth — header grezzi per l'analisi dettagliata
    dkim_signatures_raw: list[str] = field(default_factory=list)   # tutti gli header DKIM-Signature
    received_spf_raw: str = ""                                       # primo Received-SPF grezzo
    auth_results_raw: list[str] = field(default_factory=list)       # tutti gli Authentication-Results

    # Raw headers dict (all headers, lowercased keys)
    raw_headers: dict = field(default_factory=dict)

    # Body
    body_text: str = ""
    body_html: str = ""

    # Attachments
    attachments: list[dict] = field(default_factory=list)

    # Parse errors
    parse_errors: list[str] = field(default_factory=list)


def _compute_hashes(data: bytes) -> tuple[str, str, str]:
    return (
        hashlib.md5(data).hexdigest(),
        hashlib.sha1(data).hexdigest(),
        hashlib.sha256(data).hexdigest(),
    )


def _decode_rfc2047(raw: str) -> str:
    """Decodifica un valore header RFC 2047 (=?charset?Q/B?...?=).

    Supporta UTF-8, Latin-1, Windows-1252, emoji (es. =?UTF-8?B?8J+YgA==?=)
    e qualsiasi charset registrato IANA. Fallback graceful con errors='replace'.
    """
    if not raw:
        return ""
    try:
        parts = email.header.decode_header(raw)
        result = []
        for fragment, charset in parts:
            if isinstance(fragment, bytes):
                # Costruisce lista charset da provare in ordine di affidabilità
                charsets: list[str] = []
                if charset:
                    charsets.append(charset.lower().replace("_", "-"))
                charsets += ["utf-8", "latin-1", "windows-1252"]
                decoded: str | None = None
                for cs in charsets:
                    try:
                        decoded = fragment.decode(cs)
                        break
                    except (UnicodeDecodeError, LookupError):
                        continue
                result.append(
                    decoded if decoded is not None
                    else fragment.decode("utf-8", errors="replace")
                )
            else:
                result.append(str(fragment))
        result_str = "".join(result).strip()
        # Fix per raw UTF-8 headers: compat32 policy salva byte non-ASCII come
        # surrogate escapes (\udcc3\udca3 per \xc3\xa3 = ã). Li recuperiamo qui.
        try:
            result_str = result_str.encode("utf-8", errors="surrogateescape").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
        return result_str
    except Exception:
        return raw.strip()


def _decode_header_raw_fallback(raw_email: bytes, header_name: str) -> str | None:
    """Fallback per header con byte non-ASCII non codificati RFC 2047.

    Cerca il valore dell'header nei byte grezzi e prova a decodificarlo
    direttamente come UTF-8 o Windows-1252.
    Restituisce None se l'header non è trovato.
    """
    pattern = re.compile(
        rb"(?i)^" + re.escape(header_name.encode()) + rb":\s*(.*?)(?=\r?\n[^ \t]|\r?\n\r?\n|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    m = pattern.search(raw_email)
    if not m:
        return None
    # Unfold: rimuove line folding (CRLF + spazio/tab)
    value_bytes = re.sub(rb"\r?\n[ \t]+", b" ", m.group(1)).strip()
    # Se contiene RFC 2047 encoded words, usa il decoder standard
    if b"=?" in value_bytes:
        return _decode_rfc2047(value_bytes.decode("ascii", errors="replace"))
    # Prova decodifica diretta UTF-8, poi Windows-1252 (copre Latin-1 esteso)
    for cs in ("utf-8", "windows-1252", "latin-1"):
        try:
            return value_bytes.decode(cs)
        except (UnicodeDecodeError, LookupError):
            continue
    return value_bytes.decode("utf-8", errors="replace")


def _extract_auth_results(values: list[str], keyword: str) -> str:
    """Extract pass/fail/none/neutral from the LAST Authentication-Results header."""
    if not values or not isinstance(values, list):
        return ""
    last_header = values[-1]
    last_header_clean = " ".join(last_header.split())
    pattern = rf"{keyword}=(\S+)"
    m = re.search(pattern, last_header_clean, re.IGNORECASE)
    if m:
        return m.group(1).rstrip(";").lower()
    return ""


def _parse_eml(raw: bytes, filename: str) -> ParsedEmail:
    """Parse a raw .eml file."""
    parsed = ParsedEmail()
    parsed.filename = filename
    parsed.file_size_bytes = len(raw)
    parsed.file_hash_md5, parsed.file_hash_sha1, parsed.file_hash_sha256 = _compute_hashes(raw)

    try:
        msg = message_from_bytes(raw, policy=email.policy.compat32)
    except Exception as e:
        parsed.parse_errors.append(f"EML parse error: {e}")
        return parsed

    # --- Headers ---
    def get_header(name: str) -> str:
        """Legge un header e decodifica gli encoded words RFC 2047.

        Fallback ai byte grezzi se compat32 ha introdotto \\ufffd.
        """
        val = msg.get(name, "")
        if not val:
            return ""
        decoded = _decode_rfc2047(str(val))
        if "\ufffd" in decoded:
            fallback = _decode_header_raw_fallback(raw, name)
            if fallback is not None and "\ufffd" not in fallback:
                return fallback.strip()
        return decoded

    def get_headers(name: str) -> list[str]:
        """Legge tutti i valori di un header (può essere presente più volte)."""
        vals = msg.get_all(name) or []
        return [_decode_rfc2047(str(val)) for val in vals if val]

    parsed.mail_from = get_header("From")
    parsed.mail_subject = get_header("Subject")
    parsed.mail_date = get_header("Date")
    parsed.message_id = get_header("Message-ID")
    parsed.return_path = get_header("Return-Path")
    parsed.reply_to = get_header("Reply-To")
    parsed.x_mailer = get_header("X-Mailer") or get_header("User-Agent")
    parsed.x_originating_ip = get_header("X-Originating-IP")
    parsed.x_campaign_id = get_header("X-Campaign-ID")
    parsed.list_unsubscribe = get_header("List-Unsubscribe")

    # To / CC (can be multi-value, decode RFC 2047)
    to_raw = msg.get_all("To") or []
    parsed.mail_to = [_decode_rfc2047(str(t)) for t in to_raw if t]
    cc_raw = msg.get_all("CC") or []
    parsed.mail_cc = [_decode_rfc2047(str(c)) for c in cc_raw if c]

    # Received chain
    parsed.received_chain = [str(r).strip() for r in (msg.get_all("Received") or [])]

    # Auth-Results — usa get_all per gestire email con header multipli
    auth_results = get_headers("Authentication-Results")
    parsed.spf_result = _extract_auth_results(auth_results, "spf")
    parsed.dkim_result = _extract_auth_results(auth_results, "dkim")
    parsed.dmarc_result = _extract_auth_results(auth_results, "dmarc")

    # Salva header grezzi per l'analisi dettagliata
    parsed.auth_results_raw    = auth_results
    parsed.dkim_signatures_raw = get_headers("DKIM-Signature")
    received_spf_list          = get_headers("Received-SPF")
    parsed.received_spf_raw    = received_spf_list[0] if received_spf_list else ""

    # Fallback SPF da Received-SPF (fix: keyword vuota causava match su qualsiasi '=')
    if not parsed.spf_result and parsed.received_spf_raw:
        m = re.search(r"^(\w+)", parsed.received_spf_raw.strip(), re.IGNORECASE)
        if m:
            parsed.spf_result = m.group(1).lower()

    # All headers (lowercased keys) — recupera surrogate escapes da compat32,
    # con fallback raw-bytes se compat32 ha prodotto \ufffd
    for key in msg.keys():
        raw_val = str(msg[key])
        try:
            raw_val = raw_val.encode("utf-8", errors="surrogateescape").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
        if "\ufffd" in raw_val:
            fallback = _decode_header_raw_fallback(raw, key)
            if fallback is not None and "\ufffd" not in fallback:
                raw_val = fallback
        parsed.raw_headers[key.lower()] = raw_val

    # --- Body ---
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition.lower():
                _extract_attachment(part, parsed)
            elif ctype == "text/plain" and not parsed.body_text:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    parsed.body_text = part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception as e:
                    parsed.parse_errors.append(f"Body text decode error: {e}")
            elif ctype == "text/html" and not parsed.body_html:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    parsed.body_html = part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception as e:
                    parsed.parse_errors.append(f"Body HTML decode error: {e}")
    else:
        ctype = msg.get_content_type()
        try:
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True)
            if payload:
                decoded = payload.decode(charset, errors="replace")
                if ctype == "text/html":
                    parsed.body_html = decoded
                else:
                    parsed.body_text = decoded
        except Exception as e:
            parsed.parse_errors.append(f"Single-part body decode error: {e}")

    return parsed


def _extract_attachment(part, parsed: ParsedEmail):
    """Extract attachment metadata (static only, never executed)."""
    try:
        payload = part.get_payload(decode=True)
        if payload is None:
            return

        declared_mime = part.get_content_type()
        filename = part.get_filename() or "unknown"

        # Detect real MIME type using filetype (pure Python, cross-platform)
        detected = filetype.guess(payload)
        real_mime = detected.mime if detected else "application/octet-stream"

        md5, sha1, sha256 = _compute_hashes(payload)

        parsed.attachments.append({
            "filename": filename,
            "size_bytes": len(payload),
            "declared_mime": declared_mime,
            "real_mime": real_mime,
            "mime_mismatch": declared_mime != real_mime,
            "hash_md5": md5,
            "hash_sha1": sha1,
            "hash_sha256": sha256,
        })
    except Exception as e:
        parsed.parse_errors.append(f"Attachment extraction error: {e}")


def _parse_msg(raw: bytes, filename: str) -> ParsedEmail:
    """Parse a raw .msg (Outlook) file using extract-msg."""
    parsed = ParsedEmail()
    parsed.filename = filename
    parsed.file_size_bytes = len(raw)
    parsed.file_hash_md5, parsed.file_hash_sha1, parsed.file_hash_sha256 = _compute_hashes(raw)

    try:
        import extract_msg
        import io
        msg = extract_msg.openMsg(io.BytesIO(raw))
    except Exception as e:
        parsed.parse_errors.append(f"MSG parse error: {e}")
        return parsed

    try:
        parsed.mail_from = str(msg.sender or "")
        parsed.mail_subject = str(msg.subject or "")
        parsed.mail_date = str(msg.date or "")
        parsed.mail_to = [str(msg.to or "")]
        parsed.mail_cc = [str(msg.cc or "")] if msg.cc else []
        parsed.body_text = str(msg.body or "")
        parsed.body_html = str(msg.htmlBody or "") if hasattr(msg, "htmlBody") else ""

        # Attachments
        for att in (msg.attachments or []):
            try:
                data = att.data
                if data:
                    detected = filetype.guess(data)
                    real_mime = detected.mime if detected else "application/octet-stream"
                    md5, sha1, sha256 = _compute_hashes(data)
                    parsed.attachments.append({
                        "filename": str(att.longFilename or att.shortFilename or "unknown"),
                        "size_bytes": len(data),
                        "declared_mime": "application/octet-stream",
                        "real_mime": real_mime,
                        "mime_mismatch": False,
                        "hash_md5": md5,
                        "hash_sha1": sha1,
                        "hash_sha256": sha256,
                    })
            except Exception as e:
                parsed.parse_errors.append(f"MSG attachment error: {e}")

        msg.close()
    except Exception as e:
        parsed.parse_errors.append(f"MSG field extraction error: {e}")

    return parsed


def parse_email_file(file_bytes: bytes, filename: str) -> ParsedEmail:
    """
    Main entry point. Detects format from extension and dispatches parser.
    filename is used only for logging/metadata, never for path operations.
    """
    ext = Path(filename).suffix.lower()

    if ext == ".eml":
        return _parse_eml(file_bytes, filename)
    elif ext == ".msg":
        return _parse_msg(file_bytes, filename)
    else:
        # Try to auto-detect
        if raw_looks_like_eml(file_bytes):
            return _parse_eml(file_bytes, filename)
        parsed = ParsedEmail()
        parsed.filename = filename
        parsed.parse_errors.append(f"Unsupported file extension: {ext}")
        return parsed


def raw_looks_like_eml(data: bytes) -> bool:
    """Heuristic: check if raw bytes look like an RFC 822 email."""
    try:
        header_section = data[:2048].decode("utf-8", errors="ignore")
        return bool(re.search(r"^(From|To|Subject|Received|MIME-Version):", header_section, re.MULTILINE))
    except Exception:
        return False