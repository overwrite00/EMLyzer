"""
Backend-agnostic .msg (Microsoft Outlook) parsing interface.

Supports multiple backend implementations:
- OxMsgBackend: python-oxmsg (recommended, MIT license)
- CustomOleBackend: custom implementation (fallback, future)

This abstraction decouples EMLyzer from any specific .msg library.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MsgFields:
    """Neutral output format, independent of backend implementation."""
    mail_from: str = ""
    mail_to: list[str] = field(default_factory=list)
    mail_cc: list[str] = field(default_factory=list)
    subject: str = ""
    date: str = ""
    body_text: str = ""
    body_html: str = ""
    transport_headers: str = ""
    attachments: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class MsgBackend(ABC):
    """Abstract interface for .msg parsing backends."""

    name: str

    @abstractmethod
    def available(self) -> bool:
        """Check if backend is installed and ready."""
        ...

    @abstractmethod
    def parse(self, raw: bytes) -> MsgFields:
        """Parse raw .msg bytes, return MsgFields."""
        ...


class OxMsgBackend(MsgBackend):
    """Implementation using python-oxmsg (MIT license, Unstructured-IO maintained)."""

    name = "python-oxmsg"

    def available(self) -> bool:
        try:
            import oxmsg  # noqa
            return True
        except ImportError:
            return False

    def parse(self, raw: bytes) -> MsgFields:
        import io
        import re
        from oxmsg import Message

        out = MsgFields()
        try:
            msg = Message.load(io.BytesIO(raw))

            # Core fields (1:1 mapping with extract-msg)
            out.mail_from = msg.sender or ""
            out.subject = msg.subject or ""
            out.date = str(msg.sent_date or "")
            out.body_text = msg.body or ""
            out.body_html = msg.html_body or ""

            # Transport headers (raw RFC822, if available)
            try:
                out.transport_headers = msg.properties.get("transport_message_headers", "") or ""
            except:
                pass

            # Split To/Cc via MAPI property 0x0C15 (recipient type: 1=To, 2=Cc, 3=Bcc)
            out.mail_to, out.mail_cc = _extract_recipients(msg)

            # Attachments (with mime_type bonus vs extract-msg)
            try:
                for att in msg.attachments or []:
                    out.attachments.append({
                        "filename": att.file_name or "attachment",
                        "data": att.file_bytes or b"",
                        "declared_mime": att.mime_type or "application/octet-stream",
                        "size_bytes": len(att.file_bytes or b""),
                    })
            except:
                pass

            # RTF-only fallback (legacy Outlook <2010)
            if not out.body_text.strip():
                _handle_rtf_only(msg, out, re)

        except Exception as e:
            out.errors.append(f"oxmsg parse error: {e}")

        return out


def _extract_recipients(msg):
    """Extract To and Cc recipients from .msg via MAPI property 0x0C15."""
    to_list, cc_list = [], []
    try:
        for recip in msg.recipients or []:
            try:
                # 0x0C15 = recipient type (1=To, 2=Cc, 3=Bcc)
                recip_type = recip.properties.int_prop_value(0x0C15)
                email = recip.email or ""
                if email:
                    if recip_type == 1:  # To
                        to_list.append(email)
                    elif recip_type == 2:  # Cc
                        cc_list.append(email)
            except:
                # If property reading fails, try generic email extraction
                email = recip.email or ""
                if email:
                    to_list.append(email)
    except:
        pass

    return to_list, cc_list


def _handle_rtf_only(msg, out: MsgFields, re_module):
    """Handle rare RTF-only .msg files (Outlook 97-2003)."""
    try:
        # 0x1009 = PR_RTF_COMPRESSED
        rtf_prop = msg.properties.int_prop_value(0x1009)
        if rtf_prop:
            try:
                # Try to decompress and parse RTF (requires optional RTFDE)
                from RTFDE import RTFDE
                rtf_decompressed = RTFDE(rtf_prop).decompress()
                # Remove RTF markup (simple regex)
                body_text = re_module.sub(r'\\[a-z]+\d*\s?', '', rtf_decompressed)
                body_text = body_text.replace('{', '').replace('}', '').strip()
                if body_text:
                    out.body_text = body_text
            except ImportError:
                out.errors.append(
                    "RTF-only body detected (legacy .msg format, Outlook <2010). "
                    "Plain text unavailable. Install RTFDE for support: pip install RTFDE"
                )
            except Exception as e:
                out.errors.append(f"RTF decompression failed: {e}")
    except:
        pass


def get_msg_backend() -> Optional[MsgBackend]:
    """
    Select available .msg backend.

    Backends are tried in order; first available is used.
    Extensible: add new backends to the list to support fallbacks.
    """
    backends: list[MsgBackend] = [
        OxMsgBackend(),
        # Future: CustomOleBackend(),
    ]
    return next((b for b in backends if b.available()), None)
