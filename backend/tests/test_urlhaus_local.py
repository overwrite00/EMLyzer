"""Test Wave 8 — connettore URLhaus bulk locale (nessuna API key richiesta)."""

import pytest

from core.intel import feeds as intel_feeds
from core.intel.snapshot import Snapshot, SnapshotMeta, STATE_OK, STATE_UNAVAILABLE
from core.reputation import connectors


@pytest.fixture(autouse=True)
def _isolate():
    intel_feeds._snapshots["urlhaus"] = Snapshot()
    yield
    intel_feeds._snapshots["urlhaus"] = Snapshot()


def test_parse_urlhaus_csv_extracts_urls():
    raw = (
        b'# comment line\n'
        b'"1","2026-01-01","https://evil.example/a","online","2026-01-01","malware_download","tag","link","reporter"\n'
        b'"2","2026-01-01","http://evil.example/b","online","2026-01-01","malware_download","tag","link","reporter"\n'
    )
    parsed = intel_feeds._parse_urlhaus(raw)
    assert parsed == ["https://evil.example/a", "http://evil.example/b"]


def test_check_url_urlhaus_local_detects_malicious():
    snap = intel_feeds.snapshot("urlhaus")
    snap.swap({"https://evil.example/x"}, meta=SnapshotMeta(state=STATE_OK, entry_count=1))
    r = connectors.check_url_urlhaus_local("https://evil.example/x")
    assert r.is_malicious is True
    assert r.source == "URLhaus (feed locale)"


def test_check_url_urlhaus_local_clean_url():
    snap = intel_feeds.snapshot("urlhaus")
    snap.swap({"https://evil.example/x"}, meta=SnapshotMeta(state=STATE_OK, entry_count=1))
    r = connectors.check_url_urlhaus_local("https://example.com/safe")
    assert r.is_malicious is False


def test_check_url_urlhaus_local_unavailable_reports_error():
    snap = intel_feeds.snapshot("urlhaus")
    # swap (non mark_error) per evitare che ensure_loaded() rilevi get()=None
    # e tenti un vero fetch di rete: qui vogliamo isolare solo il ramo
    # "unavailable" del connettore, non il comportamento di refresh.
    snap.swap(set(), meta=SnapshotMeta(state=STATE_UNAVAILABLE, last_error_category="connection_error", last_error_message="no network"))
    r = connectors.check_url_urlhaus_local("https://example.com/x")
    assert r.error
    assert r.is_malicious is False
