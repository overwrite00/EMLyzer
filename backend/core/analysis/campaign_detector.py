"""
core/analysis/campaign_detector.py

Rilevamento campagne malevole coordinate attraverso il clustering di email simili.

Tecniche usate:
- Similarità subject (Jaccard su token normalizzati)
- Hash del body (confronto SHA256 del testo pulito)
- Pattern Message-ID (regex su dominio/formato)
- Analisi temporale (raggruppamento per finestra temporale)
- Clustering: trova gruppi di email con ≥ 2 elementi simili
"""

import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Strutture dati
# ---------------------------------------------------------------------------

@dataclass
class EmailSummary:
    """Rappresentazione leggera di un'analisi salvata, per il clustering."""
    job_id: str
    subject: str = ""
    mail_from: str = ""
    mail_date: str = ""
    message_id: str = ""
    body_hash: str = ""          # SHA256 del body normalizzato
    x_mailer: str = ""
    x_campaign_id: str = ""
    risk_label: str = ""
    risk_score: float = 0.0


@dataclass
class CampaignCluster:
    cluster_id: str
    similarity_type: str         # "subject" / "body_hash" / "message_id" / "campaign_id" / "sender_domain"
    description: str
    email_count: int
    job_ids: list[str] = field(default_factory=list)
    common_value: str = ""       # valore condiviso che ha originato il cluster
    risk_labels: list[str] = field(default_factory=list)
    max_risk_score: float = 0.0
    first_seen: str = ""
    last_seen: str = ""


@dataclass
class CampaignReport:
    total_emails_analyzed: int = 0
    clusters_found: int = 0
    clusters: list[CampaignCluster] = field(default_factory=list)
    isolated_emails: int = 0     # email non raggruppate in nessun cluster


# ---------------------------------------------------------------------------
# Funzioni di normalizzazione e hashing
# ---------------------------------------------------------------------------

def _normalize_subject(subject: str) -> str:
    """Normalizza il subject rimuovendo prefissi comuni e punteggiatura."""
    if not subject:
        return ""
    s = re.sub(r'^(re|fwd?|fw|inoltro|risposta|r):\s*', '', subject.lower().strip(),
               flags=re.IGNORECASE)
    s = re.sub(r'[^\w\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _subject_tokens(subject: str) -> set[str]:
    """Tokenizza il subject in parole significative (min 3 caratteri)."""
    stopwords = {'the', 'and', 'for', 'you', 'your', 'our', 'this',
                 'that', 'with', 'from', 'have', 'has', 'per', 'con',
                 'del', 'della', 'che', 'una', 'suo', 'nel', 'dei'}
    tokens = set(_normalize_subject(subject).split())
    return {t for t in tokens if len(t) >= 3 and t not in stopwords}


def _jaccard(set_a: set, set_b: set) -> float:
    """Coefficiente di Jaccard tra due insiemi."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def _hash_body(body_text: str) -> str:
    """SHA256 del body normalizzato (spazi multipli → singolo, lowercase)."""
    if not body_text:
        return ""
    normalized = re.sub(r'\s+', ' ', body_text.lower().strip())
    return hashlib.sha256(normalized.encode('utf-8', errors='replace')).hexdigest()


def _extract_message_id_pattern(message_id: str) -> str:
    """Estrae il dominio/pattern dal Message-ID per confronto."""
    if not message_id:
        return ""
    # Rimuovi < >
    mid = message_id.strip('<> ')
    # Estrai parte dopo @
    parts = mid.split('@')
    if len(parts) >= 2:
        return parts[-1].lower().strip('>')
    return mid.lower()[:50]


def _extract_sender_domain(mail_from: str) -> str:
    """Estrae il dominio del mittente."""
    m = re.search(r'@([\w.\-]+)', mail_from or '')
    return m.group(1).lower() if m else ''


# ---------------------------------------------------------------------------
# Algoritmo di clustering
# ---------------------------------------------------------------------------

def detect_campaigns(emails: list[EmailSummary],
                     subject_threshold: float = 0.6,
                     min_cluster_size: int = 2) -> CampaignReport:
    """
    Analizza una lista di email e raggruppa quelle simili in cluster/campagne.

    subject_threshold: similarità Jaccard minima per raggruppare (0.0–1.0)
    min_cluster_size: numero minimo di email per formare un cluster
    """
    report = CampaignReport(total_emails_analyzed=len(emails))
    if len(emails) < min_cluster_size:
        report.isolated_emails = len(emails)
        return report

    clustered_ids: set[str] = set()
    cluster_seq = 0

    # ── 1. Clustering per body hash identico ─────────────────────────────────
    body_hash_groups: dict[str, list[EmailSummary]] = {}
    for email in emails:
        if email.body_hash and len(email.body_hash) == 64:
            body_hash_groups.setdefault(email.body_hash, []).append(email)

    for body_hash, group in body_hash_groups.items():
        if len(group) >= min_cluster_size:
            cluster_seq += 1
            ids = [e.job_id for e in group]
            clustered_ids.update(ids)
            report.clusters.append(_make_cluster(
                cluster_id=f"C{cluster_seq:03d}",
                similarity_type="body_hash",
                description="Body identico (stesso template email)",
                emails=group,
                common_value=f"SHA256: {body_hash[:16]}...",
            ))

    # ── 2. Clustering per X-Campaign-ID ──────────────────────────────────────
    campaign_groups: dict[str, list[EmailSummary]] = {}
    for email in emails:
        if email.x_campaign_id and email.x_campaign_id.strip():
            campaign_groups.setdefault(email.x_campaign_id.strip(), []).append(email)

    for campaign_id, group in campaign_groups.items():
        if len(group) >= min_cluster_size:
            # Evita duplicati con cluster già trovati
            new_ids = [e.job_id for e in group if e.job_id not in clustered_ids]
            if len(new_ids) >= min_cluster_size:
                cluster_seq += 1
                all_ids = [e.job_id for e in group]
                clustered_ids.update(all_ids)
                report.clusters.append(_make_cluster(
                    cluster_id=f"C{cluster_seq:03d}",
                    similarity_type="campaign_id",
                    description=f"Stesso X-Campaign-ID: {campaign_id}",
                    emails=group,
                    common_value=campaign_id,
                ))

    # ── 3. Clustering per dominio Message-ID ─────────────────────────────────
    msgid_groups: dict[str, list[EmailSummary]] = {}
    for email in emails:
        if email.message_id:
            pattern = _extract_message_id_pattern(email.message_id)
            if pattern and len(pattern) > 3:
                msgid_groups.setdefault(pattern, []).append(email)

    for pattern, group in msgid_groups.items():
        if len(group) >= min_cluster_size:
            new_ids = [e.job_id for e in group if e.job_id not in clustered_ids]
            if len(new_ids) >= min_cluster_size:
                cluster_seq += 1
                all_ids = [e.job_id for e in group]
                clustered_ids.update(all_ids)
                report.clusters.append(_make_cluster(
                    cluster_id=f"C{cluster_seq:03d}",
                    similarity_type="message_id",
                    description=f"Stesso dominio Message-ID: @{pattern}",
                    emails=group,
                    common_value=f"@{pattern}",
                ))

    # ── 4. Clustering per subject simile (Jaccard) ────────────────────────────
    email_tokens = [(e, _subject_tokens(e.subject)) for e in emails if e.subject]
    visited = set()

    for i, (email_i, tokens_i) in enumerate(email_tokens):
        if not tokens_i or email_i.job_id in visited:
            continue

        group = [email_i]
        for j, (email_j, tokens_j) in enumerate(email_tokens):
            if i == j or email_j.job_id in visited:
                continue
            if not tokens_j:
                continue
            sim = _jaccard(tokens_i, tokens_j)
            if sim >= subject_threshold:
                group.append(email_j)

        if len(group) >= min_cluster_size:
            new_ids = [e.job_id for e in group if e.job_id not in clustered_ids]
            if len(new_ids) >= min_cluster_size:
                cluster_seq += 1
                all_ids = [e.job_id for e in group]
                for gid in all_ids:
                    visited.add(gid)
                    clustered_ids.add(gid)

                # Subject comune: usa quello con più token in comune
                common_subject = max(
                    (e.subject for e in group if e.subject),
                    key=lambda s: len(_subject_tokens(s)),
                    default=""
                )
                report.clusters.append(_make_cluster(
                    cluster_id=f"C{cluster_seq:03d}",
                    similarity_type="subject",
                    description=f"Subject simile (Jaccard ≥ {subject_threshold:.0%})",
                    emails=group,
                    common_value=common_subject[:100],
                ))

    # ── 5. Clustering per dominio mittente (solo per email ad alto rischio) ───
    sender_groups: dict[str, list[EmailSummary]] = {}
    for email in emails:
        if email.risk_label in ('high', 'critical'):
            domain = _extract_sender_domain(email.mail_from)
            if domain and len(domain) > 4:
                sender_groups.setdefault(domain, []).append(email)

    for domain, group in sender_groups.items():
        if len(group) >= min_cluster_size:
            new_ids = [e.job_id for e in group if e.job_id not in clustered_ids]
            if len(new_ids) >= min_cluster_size:
                cluster_seq += 1
                all_ids = [e.job_id for e in group]
                clustered_ids.update(all_ids)
                report.clusters.append(_make_cluster(
                    cluster_id=f"C{cluster_seq:03d}",
                    similarity_type="sender_domain",
                    description=f"Stesso dominio mittente (ad alto rischio): {domain}",
                    emails=group,
                    common_value=domain,
                ))

    report.clusters_found = len(report.clusters)
    report.isolated_emails = len(emails) - len(clustered_ids)
    return report


def _make_cluster(cluster_id: str, similarity_type: str, description: str,
                  emails: list[EmailSummary], common_value: str) -> CampaignCluster:
    """Costruisce un CampaignCluster dalla lista di email."""
    dates = []
    for e in emails:
        if e.mail_date:
            try:
                # Prova parsing ISO / RFC 2822
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(e.mail_date)
                dates.append(dt.isoformat())
            except Exception:
                pass

    dates.sort()
    return CampaignCluster(
        cluster_id=cluster_id,
        similarity_type=similarity_type,
        description=description,
        email_count=len(emails),
        job_ids=[e.job_id for e in emails],
        common_value=common_value,
        risk_labels=[e.risk_label for e in emails if e.risk_label],
        max_risk_score=max((e.risk_score for e in emails), default=0.0),
        first_seen=dates[0] if dates else "",
        last_seen=dates[-1] if dates else "",
    )
