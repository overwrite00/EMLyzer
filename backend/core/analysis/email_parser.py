"""
core/analysis/email_parser.py

Parses .eml and .msg files into a unified internal structure.
Cross-platform: uses pathlib, no Unix-specific calls.
No eval/exec. Input sanitized before processing.
"""

import hashlib
import re
import email
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

    # Auth
    spf_result: str = ""
    dkim_result: str = ""
    dmarc_result: str = ""

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


def _extract_auth_result(value: str, keyword: str) -> str:
    """Extract pass/fail/none/neutral from Authentication-Results header."""
    if not value:
        return ""
    pattern = rf"{keyword}=(\S+)"
    m = re.search(pattern, value, re.IGNORECASE)
    return m.group(1).rstrip(";").lower() if m else ""


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
        val = msg.get(name, "")
        return str(val).strip() if val else ""

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

    # To / CC (can be multi-value)
    to_raw = msg.get_all("To") or []
    parsed.mail_to = [str(t).strip() for t in to_raw]
    cc_raw = msg.get_all("CC") or []
    parsed.mail_cc = [str(c).strip() for c in cc_raw]

    # Received chain
    parsed.received_chain = [str(r).strip() for r in (msg.get_all("Received") or [])]

    # Auth-Results
    auth_results = get_header("Authentication-Results")
    parsed.spf_result = _extract_auth_result(auth_results, "spf")
    parsed.dkim_result = _extract_auth_result(auth_results, "dkim")
    parsed.dmarc_result = _extract_auth_result(auth_results, "dmarc")

    # Also check dedicated headers
    if not parsed.spf_result:
        parsed.spf_result = _extract_auth_result(get_header("Received-SPF"), "")

    # All headers (lowercased keys)
    for key in msg.keys():
        parsed.raw_headers[key.lower()] = str(msg[key])

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
