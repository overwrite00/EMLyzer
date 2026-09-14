"""Test HTTP end-to-end degli endpoint /api/campaigns/known (Wave 6) e auth (Wave 3.5)."""

import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from core.analysis import campaign_registry


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    from utils.config import settings
    monkeypatch.setattr(settings, "USER_DATA_DIR", tmp_path)
    campaign_registry._registry = campaign_registry.Snapshot()
    yield
    campaign_registry._registry = campaign_registry.Snapshot()


@pytest.mark.asyncio
async def test_list_known_campaigns_returns_system_campaigns():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/campaigns/known")
    assert r.status_code == 200
    data = r.json()
    assert len(data["campaigns"]) >= 14


@pytest.mark.asyncio
async def test_create_campaign_from_loopback_succeeds():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/campaigns/known", json={
            "id": "e2e-test-2026", "name": "E2E Test", "keywords": ["e2ekeyword", "anothere2e"],
        })
    assert r.status_code == 200, r.text
    assert r.json()["id"] == "e2e-test-2026"


@pytest.mark.asyncio
async def test_create_campaign_invalid_payload_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/campaigns/known", json={
            "id": "BAD ID", "name": "x", "keywords": ["abc"],
        })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_backtest_returns_coverage_note():
    from models.database import init_db
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/campaigns/known/backtest", json={
            "keywords": ["somekeyword", "anotherkeyword"],
        })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "coverage_note" in body
    assert "matched_count" in body


@pytest.mark.asyncio
async def test_mutating_endpoint_rejected_from_non_loopback(monkeypatch):
    """Simula un client non-loopback (Wave 3.5): senza token, 403."""
    from httpx import ASGITransport

    async def _get_client_host(self, *a, **kw):
        return None

    transport = ASGITransport(app=app, client=("203.0.113.5", 12345))
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/campaigns/known", json={
            "id": "should-fail-2026", "name": "x", "keywords": ["somekeyword"],
        })
    assert r.status_code == 403
