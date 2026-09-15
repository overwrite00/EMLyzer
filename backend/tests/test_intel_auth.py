"""Test Wave 3.5 — hardening minimo degli endpoint mutanti di Threat Intelligence."""

import pytest
from fastapi import HTTPException, Request

from core.intel import auth as intel_auth


def _make_request(client_host: str, token: str = "") -> Request:
    scope = {
        "type": "http",
        "headers": [(b"x-emlyzer-token", token.encode())] if token else [],
        "client": (client_host, 12345),
    }
    return Request(scope)


def test_token_generated_and_persisted(tmp_path, monkeypatch):
    from utils.config import settings
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    intel_auth._token_cache = None

    token1 = intel_auth.get_or_create_token()
    assert token1
    assert (tmp_path / "admin_token").exists()

    intel_auth._token_cache = None  # forza rilettura da disco
    token2 = intel_auth.get_or_create_token()
    assert token1 == token2  # stesso token, non rigenerato a ogni chiamata


@pytest.mark.asyncio
async def test_loopback_client_always_passes(tmp_path, monkeypatch):
    from utils.config import settings
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    intel_auth._token_cache = None

    req = _make_request("127.0.0.1")
    await intel_auth.require_trusted_client(req)  # non deve sollevare


@pytest.mark.asyncio
async def test_non_loopback_without_token_is_rejected(tmp_path, monkeypatch):
    from utils.config import settings
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    intel_auth._token_cache = None

    req = _make_request("192.168.1.50")
    with pytest.raises(HTTPException) as exc_info:
        await intel_auth.require_trusted_client(req)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_non_loopback_with_correct_token_passes(tmp_path, monkeypatch):
    from utils.config import settings
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    intel_auth._token_cache = None
    token = intel_auth.get_or_create_token()

    req = _make_request("192.168.1.50", token=token)
    await intel_auth.require_trusted_client(req)  # non deve sollevare


@pytest.mark.asyncio
async def test_non_loopback_with_wrong_token_is_rejected(tmp_path, monkeypatch):
    from utils.config import settings
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    intel_auth._token_cache = None
    intel_auth.get_or_create_token()

    req = _make_request("192.168.1.50", token="wrong-token")
    with pytest.raises(HTTPException) as exc_info:
        await intel_auth.require_trusted_client(req)
    assert exc_info.value.status_code == 403
