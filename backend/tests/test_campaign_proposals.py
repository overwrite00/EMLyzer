"""Test Wave 9 — auto-apprendimento interno (proposte di campagna)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from core.analysis import campaign_proposals as proposals_mod
from core.analysis import campaign_registry
from models.database import AsyncSessionLocal, EmailAnalysis, CampaignProposal, init_db


def _make_email(subject: str, mail_from: str, risk_label: str, body_sha256: str = "") -> EmailAnalysis:
    return EmailAnalysis(
        id=str(uuid.uuid4()), filename="x.eml", file_hash_sha256=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
        mail_subject=subject, mail_from=mail_from, risk_label=risk_label,
        body_indicators={"body_sha256": body_sha256, "campaign_surface": []},
    )


async def _clear_tables():
    await init_db()
    async with AsyncSessionLocal() as db:
        await db.execute(EmailAnalysis.__table__.delete())
        await db.execute(CampaignProposal.__table__.delete())
        await db.commit()


@pytest.fixture(autouse=True)
def _reset_state():
    import asyncio
    proposals_mod._sighting_counts.clear()
    campaign_registry._registry = campaign_registry.Snapshot()
    # Il DB di test e' condiviso (session-scoped, vedi conftest.py) tra tutti
    # i test del progetto: senza pulire le tabelle qui, il clustering di un
    # test vedrebbe anche le email/proposte lasciate da un test precedente.
    # asyncio.run() qui (fixture sincrona) invece di una fixture async: la
    # configurazione pytest-asyncio del progetto è in modalità strict e non
    # riconosce fixture async decorate con @pytest.fixture.
    asyncio.run(_clear_tables())
    yield
    proposals_mod._sighting_counts.clear()


@pytest.mark.asyncio
async def test_cluster_below_min_size_is_ignored():
    await init_db()
    async with AsyncSessionLocal() as db:
        for i in range(3):  # sotto MIN_CLUSTER_SIZE=4
            db.add(_make_email(f"urgent action {i}", f"a@sender{i}.com", "high"))
        await db.commit()
        created = await proposals_mod.generate_proposals(db)
    assert created == []


@pytest.mark.asyncio
async def test_cluster_without_enough_high_risk_is_rejected():
    await init_db()
    async with AsyncSessionLocal() as db:
        for i in range(5):
            db.add(_make_email("verify your account now please urgent", f"a@sender{i}.com", "low"))
        await db.commit()
        created = await proposals_mod.generate_proposals(db)
    assert created == []


@pytest.mark.asyncio
async def test_cluster_with_single_sender_domain_is_rejected():
    await init_db()
    async with AsyncSessionLocal() as db:
        for i in range(5):
            db.add(_make_email("verify your account now please urgent", "a@same-sender.com", "high"))
        await db.commit()
        created = await proposals_mod.generate_proposals(db)
    assert created == []  # tutte dallo stesso dominio: non abbastanza "rotazione mittenti"


@pytest.mark.asyncio
async def test_valid_cluster_requires_two_sightings_cooldown():
    await init_db()
    async with AsyncSessionLocal() as db:
        for i in range(5):
            db.add(_make_email("verify your account now please urgent", f"a@sender{i}.com", "high"))
        await db.commit()

        first_run = await proposals_mod.generate_proposals(db)
        assert first_run == []  # prima osservazione: cooldown, nessuna proposta ancora

        second_run = await proposals_mod.generate_proposals(db)
        assert len(second_run) == 1  # seconda osservazione: proposta creata

        rows = (await db.execute(select(CampaignProposal))).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "pending"
        assert rows[0].source == "local-learning"
        assert rows[0].proposed_payload["source"] == "local-learning"


@pytest.mark.asyncio
async def test_dedup_skips_cluster_already_covered_by_existing_campaign():
    await init_db()
    async with AsyncSessionLocal() as db:
        # campaign_surface che matcha una campagna di sistema esistente (inps-2024)
        surface = ["inps", "verificare", "profilo", "spid", "sussidio", "bonus"]
        for i in range(5):
            email = _make_email("verify your account now please urgent", f"a@sender{i}.com", "high")
            email.body_indicators = {"body_sha256": "", "campaign_surface": surface}
            db.add(email)
        await db.commit()

        await proposals_mod.generate_proposals(db)
        created = await proposals_mod.generate_proposals(db)
    assert created == []  # coperto da inps-2024 esistente, nessuna proposta


@pytest.mark.asyncio
async def test_approve_returns_payload_without_writing_campaigns_user_json(tmp_path, monkeypatch):
    from utils.config import settings
    monkeypatch.setattr(settings, "USER_DATA_DIR", tmp_path)

    await init_db()
    async with AsyncSessionLocal() as db:
        for i in range(5):
            db.add(_make_email("verify your account now please urgent", f"a@sender{i}.com", "high"))
        await db.commit()
        await proposals_mod.generate_proposals(db)
        created = await proposals_mod.generate_proposals(db)
        assert len(created) == 1
        proposal_id = created[0].id

        payload = await proposals_mod.approve_proposal(db, proposal_id)
        assert "keywords" in payload
        assert not (tmp_path / "campaigns_user.json").exists()  # approve non scrive

        updated = await db.get(CampaignProposal, proposal_id)
        assert updated.status == "approved"


@pytest.mark.asyncio
async def test_reject_sets_status_and_reason():
    await init_db()
    async with AsyncSessionLocal() as db:
        for i in range(5):
            db.add(_make_email("verify your account now please urgent", f"a@sender{i}.com", "high"))
        await db.commit()
        await proposals_mod.generate_proposals(db)
        created = await proposals_mod.generate_proposals(db)
        proposal_id = created[0].id

        await proposals_mod.reject_proposal(db, proposal_id, reason="troppo generica")
        updated = await db.get(CampaignProposal, proposal_id)
        assert updated.status == "rejected"
        assert updated.reject_reason == "troppo generica"


@pytest.mark.asyncio
async def test_stale_proposal_when_emails_deleted():
    await init_db()
    async with AsyncSessionLocal() as db:
        emails = [_make_email("verify your account now please urgent", f"a@sender{i}.com", "high") for i in range(5)]
        for e in emails:
            db.add(e)
        await db.commit()
        await proposals_mod.generate_proposals(db)
        await proposals_mod.generate_proposals(db)

        # cancella la maggior parte delle email referenziate
        for e in emails[:4]:
            await db.delete(e)
        await db.commit()

        listed = await proposals_mod.list_proposals(db, status="pending")
    assert len(listed) == 1
    assert listed[0]["stale"] is True
    assert listed[0]["resolved_count"] < proposals_mod.MIN_CLUSTER_SIZE
