"""Regressioni per correzioni di sicurezza e normalizzazione reputazione."""

import hashlib
import pickle

import pytest

from core.analysis.nlp_classifier import _verify_and_load_pickle
from core.analysis.url_analyzer import _safe_log_host
from core.reputation import connectors
from core.reputation.connectors import normalize_url_host


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.example.com/path", "example.com"),
        ("https://web.example.com/path", "web.example.com"),
        ("https://user:password@Example.COM:8443/path", "example.com"),
        ("https://[2001:db8::1]:443/path", "2001:db8::1"),
        ("https://[invalid", ""),
        ("not-an-absolute-url", ""),
    ],
)
def test_normalized_url_host(url, expected):
    assert normalize_url_host(url) == expected


def test_pickle_loader_accepts_reviewed_digest(tmp_path):
    payload = {"model": "test"}
    model_path = tmp_path / "model.pkl"
    model_bytes = pickle.dumps(payload)
    model_path.write_bytes(model_bytes)

    loaded = _verify_and_load_pickle(
        model_path, hashlib.sha256(model_bytes).hexdigest()
    )

    assert loaded == payload


def test_pickle_loader_rejects_unreviewed_bytes(tmp_path):
    model_path = tmp_path / "model.pkl"
    model_path.write_bytes(pickle.dumps({"model": "modified"}))

    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        _verify_and_load_pickle(model_path, "0" * 64)


def test_safe_log_host_strips_sensitive_url_parts():
    assert _safe_log_host("https://user:secret@example.com/path?token=secret#x") == "example.com"
    assert _safe_log_host("https://[invalid") == "<invalid>"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://10.0.0.1/internal",
        "http://169.254.169.254/latest/meta-data/",
    ],
)
def test_redirect_chain_blocks_unsafe_initial_targets(url, monkeypatch):
    called = False

    def unexpected_request(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("unsafe target must be rejected before the request")

    monkeypatch.setattr(connectors.requests, "get", unexpected_request)
    result = connectors.check_url_redirect_chain(url)

    assert called is False
    assert result.error_type == "ssrf_blocked"


def test_redirect_chain_blocks_public_to_private_redirect(monkeypatch):
    class RedirectResponse:
        url = "http://93.184.216.34/start"
        is_redirect = True
        headers = {"Location": "http://127.0.0.1/private"}
        closed = False

        def close(self):
            self.closed = True

    response = RedirectResponse()
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    monkeypatch.setattr(connectors.requests, "get", fake_get)
    result = connectors.check_url_redirect_chain("http://93.184.216.34/start")

    assert len(calls) == 1
    assert calls[0][1]["allow_redirects"] is False
    assert response.closed is True
    assert result.error_type == "ssrf_blocked"


def test_redacted_url_hides_credentials_and_tokens():
    assert connectors._redacted_url(
        "https://user:secret@example.com:8443/path?token=secret#fragment"
    ) == "https://example.com:8443/path"


@pytest.mark.asyncio
async def test_urlscan_diagnostic_requires_trusted_client(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from api.routes import reputation as reputation_route
    from core.intel import auth as intel_auth
    from main import app
    from utils.config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        reputation_route,
        "_test_urlscan_health_sync",
        lambda: {"connectivity": True, "api_key_configured": False},
    )
    intel_auth._token_cache = None
    token = intel_auth.get_or_create_token()
    transport = ASGITransport(app=app, client=("203.0.113.5", 12345))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        denied = await client.get("/api/reputation/test-urlscan")
        allowed = await client.get(
            "/api/reputation/test-urlscan",
            headers={"X-EMLyzer-Token": token},
        )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["connectivity"] is True
