"""
Backend-agnostic .msg (Microsoft Outlook) parsing interface.

Supports multiple backend implementations:
- OxMsgBackend: python-oxmsg (recommended, MIT license)
- CustomOleBackend: custom implementation (fallback, future)

This abstraction decouples EMLyzer from any specific .msg library.
"""

import io
import logging
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# MAPI property ids (MS-OXPROPS)
PID_TRANSPORT_MESSAGE_HEADERS = 0x007D
PID_RECIPIENT_TYPE = 0x0C15
PID_RTF_COMPRESSED = 0x1009

# PidTagRecipientType values
RECIPIENT_TO, RECIPIENT_CC, RECIPIENT_BCC = 1, 2, 3

# MS-OXRTFCP: compressed-RTF header magic values and the LZFu initial dictionary
_RTF_MAGIC_COMPRESSED = b"LZFu"
_RTF_MAGIC_UNCOMPRESSED = b"MELA"
_RTF_INIT_DICT = (
    b"{\\rtf1\\ansi\\mac\\deff0\\deftab720{\\fonttbl;}{\\f0\\fnil \\froman \\fswiss "
    b"\\fmodern \\fscript \\fdecor MS Sans SerifSymbolArialTimes New RomanCourier"
    b"{\\colortbl\\red0\\green0\\blue0\r\n\\par \\pard\\plain\\f0\\fs20\\b\\i\\u\\tab\\tx"
)


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
        from oxmsg import Message

        out = MsgFields()
        try:
            msg = Message.load(io.BytesIO(raw))

            out.mail_from = msg.sender or ""
            out.subject = msg.subject or ""
            out.date = str(msg.sent_date or "")
            out.body_text = msg.body or ""
            out.body_html = msg.html_body or ""

            # Raw RFC 822 transport headers (source of SPF/DKIM/DMARC, Message-ID, Received...)
            try:
                out.transport_headers = msg.properties.str_prop_value(PID_TRANSPORT_MESSAGE_HEADERS) or ""
            except Exception as e:
                logger.warning("Cannot read .msg transport headers: %s", e)
                out.errors.append(f"transport headers unreadable: {e}")

            out.mail_to, out.mail_cc = _extract_recipients(msg, out.errors)

            try:
                for att in msg.attachments or []:
                    out.attachments.append({
                        "filename": att.file_name or "attachment",
                        "data": att.file_bytes or b"",
                        "declared_mime": att.mime_type or "application/octet-stream",
                        "size_bytes": len(att.file_bytes or b""),
                    })
            except Exception as e:
                logger.warning("Cannot read .msg attachments: %s", e)
                out.errors.append(f"attachments unreadable: {e}")

            # RTF-only fallback (legacy Outlook <2010): no plain-text or HTML body at all
            if not out.body_text.strip() and not out.body_html.strip():
                _handle_rtf_only(msg, out)

        except Exception as e:
            out.errors.append(f"oxmsg parse error: {e}")

        return out


def _extract_recipients(msg, errors: list[str]) -> tuple[list[str], list[str]]:
    """Split recipients into To / Cc using PidTagRecipientType (1=To, 2=Cc, 3=Bcc).

    A recipient without a type is treated as To. Bcc recipients are skipped: they
    are never visible to the other recipients and ParsedEmail has no field for them.
    """
    to_list: list[str] = []
    cc_list: list[str] = []
    try:
        recipients = msg.recipients or ()
    except Exception as e:
        logger.warning("Cannot read .msg recipient table: %s", e)
        errors.append(f"recipients unreadable: {e}")
        return to_list, cc_list

    for recip in recipients:
        try:
            address = recip.email_address
            if not address:
                continue
            kind = recip.properties.int_prop_value(PID_RECIPIENT_TYPE)
            if kind == RECIPIENT_BCC:
                continue
            (cc_list if kind == RECIPIENT_CC else to_list).append(address)
        except Exception as e:
            logger.warning("Cannot read a .msg recipient: %s", e)
            errors.append(f"recipient unreadable: {e}")

    return to_list, cc_list


def decompress_rtf(data: bytes) -> bytes:
    """Decompress a PidTagRtfCompressed value (MS-OXRTFCP, "LZFu" or uncompressed "MELA").

    Raises ValueError when the data is not a valid compressed-RTF stream.
    """
    if len(data) < 16:
        raise ValueError("compressed RTF header is truncated")
    comp_size, raw_size = struct.unpack_from("<II", data, 0)
    magic = data[8:12]
    payload = data[16:comp_size + 4]

    if magic == _RTF_MAGIC_UNCOMPRESSED:
        return payload[:raw_size]
    if magic != _RTF_MAGIC_COMPRESSED:
        raise ValueError(f"unknown compressed RTF signature {magic!r}")

    window = bytearray(_RTF_INIT_DICT) + bytearray(4096 - len(_RTF_INIT_DICT))
    write = len(_RTF_INIT_DICT)
    out = bytearray()
    pos = 0
    try:
        while True:
            control = payload[pos]
            pos += 1
            for bit in range(8):
                if control & (1 << bit):
                    ref = (payload[pos] << 8) | payload[pos + 1]
                    pos += 2
                    offset, length = ref >> 4, (ref & 0xF) + 2
                    if offset == write:  # end-of-stream marker
                        return bytes(out[:raw_size])
                    for _ in range(length):
                        byte = window[offset]
                        out.append(byte)
                        window[write] = byte
                        offset = (offset + 1) % 4096
                        write = (write + 1) % 4096
                else:
                    byte = payload[pos]
                    pos += 1
                    out.append(byte)
                    window[write] = byte
                    write = (write + 1) % 4096
    except IndexError:
        raise ValueError("compressed RTF stream is truncated") from None


def _handle_rtf_only(msg, out: MsgFields) -> None:
    """Recover the body of an RTF-only .msg (Outlook 97-2003) via the optional RTFDE package."""
    try:
        compressed = msg.properties.binary_prop_value(PID_RTF_COMPRESSED)
    except Exception as e:
        out.errors.append(f"RTF body unreadable: {e}")
        return
    if not compressed:
        return

    try:
        rtf = decompress_rtf(compressed)
    except ValueError as e:
        out.errors.append(f"RTF-only body detected but its RTF could not be decompressed: {e}")
        return

    try:
        from RTFDE.deencapsulate import DeEncapsulator
    except ImportError:
        out.errors.append(
            "RTF-only body detected (legacy .msg format, Outlook <2010). "
            "Plain text unavailable. Install RTFDE for support: pip install RTFDE"
        )
        return

    try:
        de = DeEncapsulator(rtf)
        de.deencapsulate()
        if de.content_type == "html" and de.html:
            out.body_html = _decode_rtfde(de.html)
        elif de.text:
            out.body_text = _decode_rtfde(de.text)
        else:
            out.errors.append("RTF-only body detected but it holds no encapsulated text or HTML")
    except Exception as e:
        out.errors.append(f"RTF de-encapsulation failed: {e}")


def _decode_rtfde(value: bytes) -> str:
    """RTFDE returns bytes in the document's ANSI code page; mirror the EML header decoding order."""
    for charset in ("utf-8", "windows-1252"):
        try:
            return value.decode(charset)
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", errors="replace")


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
