"""
core/analysis/campaign_proposals.py

Wave 9 — auto-apprendimento interno: propone nuove "campagne note" a partire
dal clustering delle email già analizzate dall'utente. Dichiaratamente
l'ultima priorità del piano, a rendimento incerto: su un'istanza self-hosted
con poche centinaia di email il numero di proposte valide sarà vicino a
zero. La curatela manuale assistita dal backtest (Wave 6) copre l'80% del
bisogno con una frazione del lavoro — questa Wave esiste per l'altro 20%.

Regole (tutte deliberate, vedi CHANGELOG per il perché):
- Solo due strategie di campaign_detector: subject-Jaccard e body_hash
  (quest'ultimo ora sul body_sha256 reale, non più sul proxy a contatori).
  ESCLUSE sender_domain (dipende da risk_label, cioè dall'output dello
  stesso scorer che la campagna poi influenzerebbe — retroazione positiva)
  e message_id (raggruppa per dominio infrastrutturale tipo @gmail.com,
  quasi rumore puro).
- min_cluster_size >= 4 (non 2): due email non sono una campagna.
- Finestra temporale: ultimi 90 giorni (created_at).
- Almeno 2 email risk_label in (high, critical): un cluster di sole email
  "low" non è abbastanza segnale per proporre una campagna.
- Almeno 2 domini mittente distinti: distingue una campagna vera (mittenti
  ruotati) da una newsletter o da un thread ripetuto con lo stesso mittente.
- Dedup: se >=60% delle email del cluster già matchano una campagna nota
  esistente (via match_campaigns sulla campaign_surface persistita), il
  cluster è considerato già coperto e non genera una proposta.
- Cooldown: un cluster deve essere osservato in due esecuzioni distinte di
  generate_proposals() prima di diventare una proposta persistita. Il
  contatore di "sightings" vive in memoria di processo (si azzera a un
  riavvio) — accettabile per una funzione on-demand a basso rendimento
  dichiarato; non vale la pena di un secondo meccanismo di persistenza
  solo per questo.

Le proposte finiscono SEMPRE nella tabella campaign_proposals con
status="pending": mai scritte direttamente in campaigns_user.json.
approve_proposal() ritorna il payload pronto per il form di Wave 6 (che
l'utente conferma esplicitamente), non scrive nulla da sola.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.analysis import campaign_registry
from core.analysis.body_analyzer import match_campaigns
from core.analysis.campaign_detector import _jaccard, _subject_tokens, _extract_sender_domain
from models.database import EmailAnalysis, CampaignProposal

logger = logging.getLogger(__name__)

MIN_CLUSTER_SIZE = 4
WINDOW_DAYS = 90
MIN_HIGH_RISK_EMAILS = 2
MIN_DISTINCT_SENDER_DOMAINS = 2
DEDUP_COVERAGE_THRESHOLD = 0.6
SUBJECT_JACCARD_THRESHOLD = 0.6
PROPOSAL_TTL_DAYS = 30

# Cooldown in memoria di processo — vedi motivazione nel docstring del modulo.
_sighting_counts: dict[str, int] = {}


def _fingerprint(job_ids: list[str]) -> str:
    return hashlib.sha256(",".join(sorted(job_ids)).encode()).hexdigest()


async def _load_candidate_rows(db: AsyncSession) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    result = await db.execute(
        select(
            EmailAnalysis.id, EmailAnalysis.mail_subject, EmailAnalysis.mail_from,
            EmailAnalysis.risk_label, EmailAnalysis.body_indicators, EmailAnalysis.created_at,
        ).where(EmailAnalysis.created_at >= cutoff).limit(3000)
    )
    rows = []
    for r in result.all():
        bi = r.body_indicators if isinstance(r.body_indicators, dict) else {}
        rows.append({
            "job_id": r.id,
            "subject": r.mail_subject or "",
            "mail_from": r.mail_from or "",
            "risk_label": r.risk_label or "",
            "body_sha256": bi.get("body_sha256", ""),
            "campaign_surface": bi.get("campaign_surface", []),
        })
    return rows


def _cluster_by_body_hash(rows: list[dict]) -> list[list[dict]]:
    groups: dict[str, list[dict]] = {}
    for r in rows:
        h = r["body_sha256"]
        if h and len(h) == 64:
            groups.setdefault(h, []).append(r)
    return [g for g in groups.values() if len(g) >= MIN_CLUSTER_SIZE]


def _cluster_by_subject(rows: list[dict]) -> list[list[dict]]:
    tokenized = [(r, _subject_tokens(r["subject"])) for r in rows if r["subject"]]
    visited: set[str] = set()
    clusters: list[list[dict]] = []
    for i, (r_i, tokens_i) in enumerate(tokenized):
        if not tokens_i or r_i["job_id"] in visited:
            continue
        group = [r_i]
        for j, (r_j, tokens_j) in enumerate(tokenized):
            if i == j or r_j["job_id"] in visited or not tokens_j:
                continue
            if _jaccard(tokens_i, tokens_j) >= SUBJECT_JACCARD_THRESHOLD:
                group.append(r_j)
        if len(group) >= MIN_CLUSTER_SIZE:
            for g in group:
                visited.add(g["job_id"])
            clusters.append(group)
    return clusters


def _passes_quality_gate(cluster: list[dict]) -> bool:
    high_risk = sum(1 for r in cluster if r["risk_label"] in ("high", "critical"))
    if high_risk < MIN_HIGH_RISK_EMAILS:
        return False
    domains = {_extract_sender_domain(r["mail_from"]) for r in cluster}
    domains.discard("")
    if len(domains) < MIN_DISTINCT_SENDER_DOMAINS:
        return False
    return True


def _already_covered_by_existing_campaign(cluster: list[dict]) -> bool:
    evaluable = [r for r in cluster if r["campaign_surface"]]
    if not evaluable:
        return False  # nessuna superficie disponibile: non possiamo escluderlo, procedi
    reg = campaign_registry.get()["db"]
    matched = 0
    for r in evaluable:
        text = " ".join(r["campaign_surface"])
        if match_campaigns(text_lower=text, subject_lower="", registry=reg):
            matched += 1
    return (matched / len(evaluable)) >= DEDUP_COVERAGE_THRESHOLD


def _extract_keywords(cluster: list[dict], max_keywords: int = 8) -> list[str]:
    """Keyword candidate: token di subject comuni a più email del cluster (mai dal body)."""
    from collections import Counter
    counter = Counter()
    for r in cluster:
        counter.update(_subject_tokens(r["subject"]))
    return [tok for tok, count in counter.most_common(max_keywords) if count >= 2]


async def generate_proposals(db: AsyncSession) -> list[CampaignProposal]:
    """
    Esegue il clustering ristretto, applica i filtri di qualità e il dedup,
    e persiste come nuove righe 'pending' solo i cluster osservati per la
    seconda volta (cooldown). Ritorna le proposte create in QUESTA esecuzione.
    """
    rows = await _load_candidate_rows(db)
    clusters = _cluster_by_body_hash(rows) + _cluster_by_subject(rows)

    created: list[CampaignProposal] = []
    seen_fingerprints_this_run: set[str] = set()

    for cluster in clusters:
        job_ids = [r["job_id"] for r in cluster]
        fingerprint = _fingerprint(job_ids)
        if fingerprint in seen_fingerprints_this_run:
            continue
        seen_fingerprints_this_run.add(fingerprint)

        if not _passes_quality_gate(cluster):
            continue
        if _already_covered_by_existing_campaign(cluster):
            continue

        _sighting_counts[fingerprint] = _sighting_counts.get(fingerprint, 0) + 1
        if _sighting_counts[fingerprint] < 2:
            continue  # cooldown: serve una seconda osservazione

        existing = await db.execute(
            select(CampaignProposal).where(CampaignProposal.cluster_fingerprint == fingerprint)
        )
        if existing.scalar_one_or_none() is not None:
            continue  # già proposta (pending/approved/rejected) in passato

        keywords = _extract_keywords(cluster)
        if not keywords:
            continue

        slug = f"local-{fingerprint[:8]}-{datetime.now(timezone.utc).year}"
        proposal = CampaignProposal(
            source="local-learning",
            status="pending",
            cluster_fingerprint=fingerprint,
            seen_count=_sighting_counts[fingerprint],
            job_ids=job_ids,
            proposed_payload={
                "id": slug,
                "name": f"Cluster locale {fingerprint[:8]}",
                "keywords": keywords,
                "risk_contribution": 15.0,  # severity "medium": una proposta automatica parte prudente
                "enabled": True,
                "source": "local-learning",
                "description": f"Proposta generata da un cluster di {len(cluster)} email simili.",
            },
        )
        db.add(proposal)
        created.append(proposal)

    if created:
        await db.commit()
    return created


async def list_proposals(db: AsyncSession, *, status: str = "pending") -> list[dict]:
    result = await db.execute(select(CampaignProposal).where(CampaignProposal.status == status))
    proposals = result.scalars().all()

    all_job_ids = {jid for p in proposals for jid in p.job_ids}
    existing_ids: set[str] = set()
    if all_job_ids:
        rows = await db.execute(select(EmailAnalysis.id).where(EmailAnalysis.id.in_(all_job_ids)))
        existing_ids = {r[0] for r in rows.all()}

    out = []
    for p in proposals:
        resolved_count = sum(1 for jid in p.job_ids if jid in existing_ids)
        is_stale = resolved_count < MIN_CLUSTER_SIZE
        out.append({
            "id": p.id, "created_at": p.created_at.isoformat(), "source": p.source,
            "status": p.status, "seen_count": p.seen_count, "job_count": len(p.job_ids),
            "resolved_count": resolved_count, "stale": is_stale,
            "proposed_payload": p.proposed_payload,
        })
    return out


async def approve_proposal(db: AsyncSession, proposal_id: str) -> dict:
    """
    NON scrive in campaigns_user.json: ritorna il payload pronto perché il
    frontend lo apra nel form di Wave 6, dove l'utente conferma esplicitamente
    (eventualmente modificando keyword/nome prima di salvare per davvero).
    """
    proposal = await db.get(CampaignProposal, proposal_id)
    if proposal is None:
        raise ValueError("Proposta non trovata")
    if proposal.status != "pending":
        raise ValueError(f"Proposta già {proposal.status}")
    proposal.status = "approved"
    proposal.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return proposal.proposed_payload


async def reject_proposal(db: AsyncSession, proposal_id: str, reason: str = "") -> None:
    proposal = await db.get(CampaignProposal, proposal_id)
    if proposal is None:
        raise ValueError("Proposta non trovata")
    proposal.status = "rejected"
    proposal.reviewed_at = datetime.now(timezone.utc)
    proposal.reject_reason = reason[:500]
    await db.commit()
