"""Generate the synthetic Outlook .msg fixture used by the .msg parsing tests.

    python backend/tests/fixtures/make_sample_msg.py

The output (sample.msg, next to this script) is deterministic: no timestamps,
only reserved example domains (RFC 2606) and a TEST-NET-1 address (RFC 5737).
It carries just the MAPI properties EMLyzer reads and is not meant to be
opened in Outlook.
"""

from __future__ import annotations

import datetime as dt
import struct
from pathlib import Path

SECTOR = 512
MINI_SECTOR = 64
MINI_CUTOFF = 4096
FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
FATSECT = 0xFFFFFFFD
NOSTREAM = 0xFFFFFFFF

PTYP_INT32, PTYP_STRING, PTYP_TIME, PTYP_BINARY = 0x0003, 0x001F, 0x0040, 0x0102


class Node:
    def __init__(self, name: str, data: bytes | None = None, children: list["Node"] | None = None):
        self.name = name
        self.data = data
        self.children = children or []
        self.sid = 0
        self.left = self.right = self.child = NOSTREAM
        self.color = 1
        self.start = ENDOFCHAIN
        self.size = 0

    @property
    def is_stream(self) -> bool:
        return self.data is not None


def _sort_key(node: Node) -> tuple[int, str]:
    return (len(node.name), node.name.upper())


def _link_siblings(storage: Node) -> None:
    kids = sorted(storage.children, key=_sort_key)
    if not kids:
        return
    depth_of: dict[int, int] = {}

    def build(lo: int, hi: int, depth: int) -> int:
        if lo >= hi:
            return NOSTREAM
        mid = (lo + hi) // 2
        node = kids[mid]
        depth_of[node.sid] = depth
        node.left = build(lo, mid, depth + 1)
        node.right = build(mid + 1, hi, depth + 1)
        return node.sid

    storage.child = build(0, len(kids), 1)
    max_depth = max(depth_of.values())
    if len(kids) != 2**max_depth - 1:
        for n in kids:
            if depth_of[n.sid] == max_depth:
                n.color = 0  # red leaves keep the red-black invariant on an incomplete last level


def _walk(node: Node, out: list[Node]) -> None:
    node.sid = len(out)
    out.append(node)
    for k in node.children:
        _walk(k, out)


def build_cfb(root: Node) -> bytes:
    entries: list[Node] = []
    _walk(root, entries)
    for n in entries:
        if not n.is_stream:
            _link_siblings(n)

    mini_stream = bytearray()
    mini_fat: list[int] = []
    large: list[Node] = []
    for n in entries:
        if not n.is_stream:
            continue
        n.size = len(n.data)
        if n.size == 0:
            continue
        if n.size < MINI_CUTOFF:
            count = -(-n.size // MINI_SECTOR)
            first = len(mini_fat)
            n.start = first
            mini_fat.extend(range(first + 1, first + count))
            mini_fat.append(ENDOFCHAIN)
            mini_stream += n.data + b"\x00" * (count * MINI_SECTOR - n.size)
        else:
            large.append(n)

    dir_secs = -(-len(entries) // 4)
    minifat_secs = -(-len(mini_fat) // 128)
    container_secs = -(-len(mini_stream) // SECTOR)
    large_secs = sum(-(-n.size // SECTOR) for n in large)
    data_secs = dir_secs + minifat_secs + container_secs + large_secs
    fat_secs = 1
    while fat_secs * 128 < data_secs + fat_secs:
        fat_secs += 1
    if fat_secs > 109:
        raise ValueError("fixture too large for header-only DIFAT")

    fat: list[int] = [FATSECT] * fat_secs
    cursor = fat_secs

    def chain(count: int) -> int:
        nonlocal cursor
        if count == 0:
            return ENDOFCHAIN
        first = cursor
        fat.extend(range(first + 1, first + count))
        fat.append(ENDOFCHAIN)
        cursor += count
        return first

    dir_start = chain(dir_secs)
    minifat_start = chain(minifat_secs)
    container_start = chain(container_secs)
    for n in large:
        n.start = chain(-(-n.size // SECTOR))
    fat.extend([FREESECT] * (fat_secs * 128 - len(fat)))

    root.start = container_start
    root.size = len(mini_stream)

    header = struct.pack(
        "<8s16sHHHHH6sIIIIIIIII",
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", b"\x00" * 16,
        0x003E, 0x0003, 0xFFFE, 9, 6, b"\x00" * 6,
        0, fat_secs, dir_start, 0, MINI_CUTOFF,
        minifat_start, minifat_secs, ENDOFCHAIN, 0,
    )
    difat = list(range(fat_secs)) + [FREESECT] * (109 - fat_secs)
    header += struct.pack("<109I", *difat)

    def dir_entry(n: Node | None) -> bytes:
        if n is None:
            return struct.pack("<64sHBBIII16sIQQIQ", b"", 0, 0, 0, NOSTREAM, NOSTREAM, NOSTREAM,
                               b"\x00" * 16, 0, 0, 0, 0, 0)
        name = n.name.encode("utf-16-le") + b"\x00\x00"
        obj_type = 5 if n is root else (2 if n.is_stream else 1)
        start = n.start if (n is root or n.is_stream) else 0  # CFB: storages carry start sector 0
        return struct.pack("<64sHBBIII16sIQQIQ", name, len(name), obj_type, n.color,
                           n.left, n.right, n.child, b"\x00" * 16, 0, 0, 0, start, n.size)

    dir_bytes = b"".join(dir_entry(n) for n in entries)
    dir_bytes += dir_entry(None) * (dir_secs * 4 - len(entries))

    out = bytearray(header)
    out += struct.pack(f"<{len(fat)}I", *fat)
    out += dir_bytes
    minifat_bytes = struct.pack(f"<{len(mini_fat)}I", *mini_fat)
    out += minifat_bytes + b"\xff" * (minifat_secs * SECTOR - len(minifat_bytes))
    out += bytes(mini_stream) + b"\x00" * (container_secs * SECTOR - len(mini_stream))
    for n in large:
        out += n.data + b"\x00" * (-(-n.size // SECTOR) * SECTOR - n.size)
    return bytes(out)


# ── MAPI layer ────────────────────────────────────────────────────────────

class Props:
    def __init__(self) -> None:
        self.entries: list[bytes] = []
        self.streams: list[Node] = []

    def _add(self, ptyp: int, pid: int, payload: bytes) -> None:
        self.entries.append(struct.pack("<HHI8s", ptyp, pid, 6, payload))

    def string(self, pid: int, text: str) -> "Props":
        data = text.encode("utf-16-le")
        self._add(PTYP_STRING, pid, struct.pack("<II", len(data) + 2, 0))
        self.streams.append(Node(f"__substg1.0_{pid:04X}{PTYP_STRING:04X}", data))
        return self

    def binary(self, pid: int, data: bytes) -> "Props":
        self._add(PTYP_BINARY, pid, struct.pack("<II", len(data), 0))
        self.streams.append(Node(f"__substg1.0_{pid:04X}{PTYP_BINARY:04X}", data))
        return self

    def int32(self, pid: int, value: int) -> "Props":
        self._add(PTYP_INT32, pid, struct.pack("<I4x", value))
        return self

    def time(self, pid: int, when: dt.datetime) -> "Props":
        epoch = dt.datetime(1601, 1, 1, tzinfo=dt.timezone.utc)
        self._add(PTYP_TIME, pid, struct.pack("<Q", int((when - epoch).total_seconds()) * 10_000_000))
        return self

    def nodes(self, header: bytes) -> list[Node]:
        return [Node("__properties_version1.0", header + b"".join(self.entries))] + self.streams


TRANSPORT_HEADERS = "\r\n".join([
    "Received: from mail.example.com (mail.example.com [192.0.2.10])",
    " by mx.example.org with ESMTPS id synthetic0001",
    " for <user@example.org>; Mon, 02 Mar 2026 10:14:58 +0000",
    "Authentication-Results: mx.example.org;",
    " spf=fail smtp.mailfrom=billing@example.com;",
    " dkim=none;",
    " dmarc=fail header.from=example.com",
    'From: "Example Billing" <billing@example.com>',
    "To: user@example.org",
    "Cc: cc@example.org",
    "Subject: Urgent: verify your account",
    "Date: Mon, 02 Mar 2026 10:14:55 +0000",
    "Message-ID: <synthetic-sample-0001@example.com>",
    "Return-Path: <billing@example.com>",
    "Reply-To: <replies@example.net>",
    "X-Mailer: Synthetic Sample Generator",
    "MIME-Version: 1.0",
    "",
    "",
])

BODY_TEXT = (
    "Dear customer,\r\n\r\n"
    "Your account will be suspended within 24 hours. "
    "Verify your account now: http://example.com/verify\r\n\r\n"
    "Example Billing\r\n"
)

BODY_HTML = (
    "<html><body><p>Dear customer,</p>"
    "<p>Your account will be suspended within 24 hours. "
    '<a href="http://example.com/verify">Verify now</a></p>'
    "<p>Example Billing</p></body></html>"
)

ATTACHMENT_NAME = "invoice.txt"
ATTACHMENT_DATA = b"Synthetic attachment content for EMLyzer parser tests.\n"


def build_sample() -> bytes:
    sent = dt.datetime(2026, 3, 2, 10, 14, 55, tzinfo=dt.timezone.utc)
    recipients = [("Example User", "user@example.org", 1), ("Example Cc", "cc@example.org", 2)]

    root_props = (
        Props()
        .string(0x001A, "IPM.Note")
        .string(0x0037, "Urgent: verify your account")
        .time(0x0039, sent)
        .string(0x0C1A, "Example Billing")
        .string(0x0C1F, "billing@example.com")
        .string(0x5D01, "billing@example.com")
        .string(0x007D, TRANSPORT_HEADERS)
        .string(0x1000, BODY_TEXT)
        .binary(0x1013, BODY_HTML.encode("ascii"))
    )
    header = struct.pack("<8x4I8x", len(recipients), 1, len(recipients), 1)
    children = root_props.nodes(header)

    for i, (name, addr, kind) in enumerate(recipients):
        p = (
            Props()
            .int32(0x0C15, kind)
            .string(0x3001, name)
            .string(0x3002, "SMTP")
            .string(0x3003, addr)
            .string(0x39FE, addr)
        )
        children.append(Node(f"__recip_version1.0_#{i:08X}", children=p.nodes(b"\x00" * 8)))

    attach = (
        Props()
        .int32(0x3705, 1)
        .string(0x3703, ".txt")
        .string(0x3704, ATTACHMENT_NAME)
        .string(0x3707, ATTACHMENT_NAME)
        .string(0x370E, "text/plain")
        .binary(0x3701, ATTACHMENT_DATA)
    )
    children.append(Node("__attach_version1.0_#00000000", children=attach.nodes(b"\x00" * 8)))

    return build_cfb(Node("Root Entry", children=children))


_RTF_INIT_DICT_LEN = 207  # size of the LZFu initial dictionary (MS-OXRTFCP)


def lzfu_literals_only(rtf: bytes) -> bytes:
    """Wrap `rtf` in a valid LZFu stream that uses literals only, plus the end marker."""
    marker = struct.pack(">H", ((_RTF_INIT_DICT_LEN + len(rtf)) % 4096) << 4)
    payload = bytearray()
    for start in range(0, len(rtf), 8):
        chunk = rtf[start:start + 8]
        if len(chunk) < 8:  # end marker follows the last literal inside the same control group
            payload += bytes([1 << len(chunk)]) + chunk + marker
            break
        payload += b"\x00" + chunk
    else:  # no partial group: the end marker opens a new control group
        payload += b"\x01" + marker
    return struct.pack("<II4sI", len(payload) + 12, len(rtf), b"LZFu", 0) + bytes(payload)


def build_rtf_only_sample(rtf: bytes) -> bytes:
    """Outlook 97-2003 style .msg: only PidTagRtfCompressed, no plain-text or HTML body."""
    props = (
        Props()
        .string(0x001A, "IPM.Note")
        .string(0x0037, "RTF only message")
        .binary(0x1009, lzfu_literals_only(rtf))
    )
    header = struct.pack("<8x4I8x", 0, 0, 0, 0)
    return build_cfb(Node("Root Entry", children=props.nodes(header)))


if __name__ == "__main__":
    target = Path(__file__).with_name("sample.msg")
    target.write_bytes(build_sample())
    print(f"wrote {target} ({target.stat().st_size} bytes)")
