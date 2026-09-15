"""Test Wave 6 — CRUD campagne utente e backtest."""

import pytest

from core.analysis import campaign_registry


@pytest.fixture(autouse=True)
def _isolate_user_campaigns(tmp_path, monkeypatch):
    from utils.config import settings
    monkeypatch.setattr(settings, "USER_DATA_DIR", tmp_path)
    campaign_registry._registry = campaign_registry.Snapshot()
    yield
    campaign_registry._registry = campaign_registry.Snapshot()


def test_validate_rejects_bad_id():
    with pytest.raises(campaign_registry.CampaignValidationError):
        campaign_registry.validate_campaign_payload({"id": "Not Valid!", "name": "x", "keywords": ["abc"]})


def test_validate_rejects_numeric_keyword():
    with pytest.raises(campaign_registry.CampaignValidationError):
        campaign_registry.validate_campaign_payload({"id": "test-2026", "name": "x", "keywords": ["12345"]})


def test_validate_rejects_score_above_cap():
    with pytest.raises(campaign_registry.CampaignValidationError):
        campaign_registry.validate_campaign_payload({
            "id": "test-2026", "name": "x", "keywords": ["abcdef"], "risk_contribution": 100,
        })


def test_create_update_delete_roundtrip():
    created = campaign_registry.create_user_campaign({
        "id": "test-2026", "name": "Test Campaign", "keywords": ["testword", "anotherword"],
    })
    assert created["id"] == "test-2026"
    assert created["source"] == "user"

    reg = campaign_registry.get()
    ids = [c["id"] for c in reg["db"]["campaigns"]]
    assert "test-2026" in ids

    updated = campaign_registry.update_user_campaign("test-2026", {
        "name": "Updated", "keywords": ["testword"],
    })
    assert updated["name"] == "Updated"

    campaign_registry.delete_user_campaign("test-2026")
    reg2 = campaign_registry.get()
    ids2 = [c["id"] for c in reg2["db"]["campaigns"]]
    assert "test-2026" not in ids2


def test_duplicate_id_rejected():
    campaign_registry.create_user_campaign({"id": "dup-2026", "name": "A", "keywords": ["wordone"]})
    with pytest.raises(campaign_registry.CampaignValidationError):
        campaign_registry.create_user_campaign({"id": "dup-2026", "name": "B", "keywords": ["wordtwo"]})


def test_user_campaign_overrides_system_and_is_reported():
    campaign_registry.create_user_campaign({
        "id": "inps-2024", "name": "INPS override utente", "keywords": ["custom-inps-keyword"],
    })
    reg = campaign_registry.get()
    assert "inps-2024" in reg["overridden_ids"]
    matching = [c for c in reg["db"]["campaigns"] if c["id"] == "inps-2024"]
    assert matching[0]["name"] == "INPS override utente"


def test_max_user_campaigns_enforced(monkeypatch):
    monkeypatch.setattr(campaign_registry, "MAX_USER_CAMPAIGNS", 2)
    campaign_registry.create_user_campaign({"id": "a-2026", "name": "A", "keywords": ["wordone"]})
    campaign_registry.create_user_campaign({"id": "b-2026", "name": "B", "keywords": ["wordtwo"]})
    with pytest.raises(campaign_registry.CampaignValidationError):
        campaign_registry.create_user_campaign({"id": "c-2026", "name": "C", "keywords": ["wordthree"]})


def test_restore_system_version_removes_override():
    campaign_registry.create_user_campaign({"id": "pagopa-2025", "name": "override", "keywords": ["xword"]})
    assert "pagopa-2025" in campaign_registry.get()["overridden_ids"]
    campaign_registry.restore_system_version("pagopa-2025")
    reg = campaign_registry.get()
    assert "pagopa-2025" not in reg["overridden_ids"]
    matching = [c for c in reg["db"]["campaigns"] if c["id"] == "pagopa-2025"]
    assert matching[0]["source"] == "builtin"
