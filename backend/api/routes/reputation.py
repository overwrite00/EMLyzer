"""
api/routes/reputation.py

Esegue i check di reputazione su un'analisi già completata.

Fonti IP inviate:
  - IP nei received_hops (catena SMTP, solo pubblici)
  - record.x_originating_ip (colonna diretta nel DB — non in header_indicators)
  - IP diretti negli URL: url_indicators.urls[].is_ip_address=True → host è un IP
  - IP risolti via DNS: url_indicators.urls[].resolved_ip

Fonti URL inviate:
  - url_indicators.urls[].original_url (nome campo dataclass serializzato)
  - body_indicators.obfuscated_links[].actual_href (link nascosti)

Fonti hash inviate:
  - attachment_indicators.attachments[].hash_sha256

Note sui nomi dei campi nel DB:
  - url_indicators usa il nome del dataclass Python: "original_url" (non "url")
  - url_indicators usa "is_ip_address" (non "is_ip")
  - x_originating_ip è una colonna diretta di EmailAnalysis, non dentro header_indicators
"""

import re
import ipaddress
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session, EmailAnalysis
from core.reputation.connectors import run_reputation_checks
from dataclasses import asdict
import json

router = APIRouter()


def _is_public_ip(ip_str: str) -> bool:
    """True se l'IP è pubblico e vale la pena controllarlo."""
    try:
        addr = ipaddress.ip_address(ip_str.strip().strip("[]"))
        return not addr.is_private and not addr.is_loopback \
               and not addr.is_link_local and not addr.is_multicast \
               and not addr.is_reserved
    except ValueError:
        return False


def _extract_indicators(record: EmailAnalysis) -> tuple[list[str], list[str], list[str]]:
    """
    Estrae IP, URL e hash da tutti gli indicatori salvati nel DB.
    Deduplicazione: ogni entità appare una sola volta.
    """
    seen_ips:    set[str] = set()
    seen_urls:   set[str] = set()
    seen_hashes: set[str] = set()
    ips:    list[str] = []
    urls:   list[str] = []
    hashes: list[str] = []

    def add_ip(raw: str) -> None:
        ip = raw.strip().strip("[]") if raw else ""
        if ip and ip not in seen_ips and _is_public_ip(ip):
            seen_ips.add(ip)
            ips.append(ip)

    def add_url(raw: str) -> None:
        url = raw.strip() if raw else ""
        if url and url not in seen_urls:
            seen_urls.add(url)
            urls.append(url)

    def add_hash(raw: str) -> None:
        h = raw.strip() if raw else ""
        if h and h not in seen_hashes:
            seen_hashes.add(h)
            hashes.append(h)

    # ── 1. IP dalla catena SMTP (received_hops) ───────────────────────────────
    hi = record.header_indicators or {}
    for hop in hi.get("received_hops", []):
        # private_ip è già calcolato dall'header analyzer
        if hop.get("ip") and not hop.get("private_ip"):
            add_ip(hop["ip"])

    # ── 2. X-Originating-IP ───────────────────────────────────────────────────
    # Attenzione: è una colonna diretta di EmailAnalysis, NON dentro header_indicators
    if record.x_originating_ip:
        add_ip(record.x_originating_ip)

    # ── 3. URL dal body, IP diretti e IP risolti via DNS ─────────────────────
    ui = record.url_indicators or {}
    for u in ui.get("urls", []):
        # URL — il campo dataclass serializzato si chiama "original_url" (non "url")
        url_str = u.get("original_url") or u.get("url", "")
        if url_str:
            add_url(url_str)

        host = u.get("host", "")

        # IP diretto nell'URL (es. http://185.1.2.3/phish)
        # Il campo si chiama "is_ip_address" nel dataclass serializzato
        if u.get("is_ip_address") or u.get("is_ip"):
            add_ip(host)

        # IP risolto via DNS per il dominio dell'URL
        resolved = u.get("resolved_ip", "")
        if resolved:
            add_ip(resolved)

    # ── 4. Link offuscati (actual_href) ───────────────────────────────────────
    # href reale diverso dal testo visibile — particolarmente sospetti
    bi = record.body_indicators or {}
    for link in bi.get("obfuscated_links", []):
        href = link.get("actual_href", "")
        if href:
            add_url(href)

    # ── 5. Hash SHA256 degli allegati ─────────────────────────────────────────
    ai = record.attachment_indicators or {}
    for att in ai.get("attachments", []):
        h = att.get("hash_sha256", "")
        if h:
            add_hash(h)

    return ips, urls, hashes


@router.post("/{job_id}")
async def run_reputation(
    job_id: str,
    db: AsyncSession = Depends(get_session),
):
    if not re.match(r'^[0-9a-f-]{36}$', job_id):
        raise HTTPException(status_code=400, detail="job_id non valido")

    record = await db.get(EmailAnalysis, job_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail="Analisi non trovata. Esegui prima POST /api/analysis/{job_id}",
        )

    ips, urls, hashes = _extract_indicators(record)

    summary = run_reputation_checks(ips=ips, urls=urls, hashes=hashes)

    rep_dict = json.loads(json.dumps(asdict(summary), default=str))
    record.reputation_results = rep_dict
    await db.commit()

    return {
        "job_id":           job_id,
        "reputation_score": summary.reputation_score,
        "malicious_count":  summary.malicious_count,
        "service_registry": rep_dict.get("service_registry", []),
        "results":          rep_dict,
        "entities_analyzed": {
            "ips":    len(ips),
            "urls":   len(urls),
            "hashes": len(hashes),
        },
    }