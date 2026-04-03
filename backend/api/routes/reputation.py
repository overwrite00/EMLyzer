"""
api/routes/reputation.py

Check di reputazione a DUE FASI per evitare timeout del browser:

  FASE 1  POST /api/reputation/{job_id}
          Servizi fast (Spamhaus, ASN, OpenPhish, crt.sh, PhishTank,
          Redirect Chain, MalwareBazaar) — risposta garantita < 15s.
          Salva i risultati parziali nel DB e li restituisce subito.

  FASE 2  POST /api/reputation/{job_id}/slow
          Servizi con rate limit stringente (VirusTotal 15s/req,
          AbuseIPDB 1.1s/req) — eseguiti in background, il frontend
          fa polling su GET /api/analysis/{job_id} per vedere quando
          i risultati vengono aggiornati.

Campi DB usati:
  - x_originating_ip: colonna diretta (non dentro header_indicators)
  - url_indicators.urls[].original_url (non "url")
  - url_indicators.urls[].is_ip_address (non "is_ip")
"""

import re
import asyncio
import ipaddress
import threading
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm.attributes import flag_modified
from models.database import get_session, EmailAnalysis
from core.reputation.connectors import (
    run_fast_checks,
    run_slow_checks,
    ReputationSummary,
)
from dataclasses import asdict
import json

router = APIRouter()


def _is_public_ip(ip_str: str) -> bool:
    """True se l'IP (v4 o v6) è pubblico."""
    try:
        raw = ip_str.strip().strip("[]")
        if raw.lower().startswith("ipv6:"):
            raw = raw[5:]
        addr = ipaddress.ip_address(raw)
        return (not addr.is_private and not addr.is_loopback
                and not addr.is_link_local and not addr.is_multicast
                and not addr.is_reserved and not addr.is_unspecified)
    except ValueError:
        return False


def _extract_indicators(record: EmailAnalysis) -> tuple[list[str], list[str], list[str]]:
    """
    Estrae IP, URL e hash per i servizi FAST (Spamhaus, ASN, OpenPhish, ecc.).
    Include tutti gli IP e URL dell'email — i servizi fast sono senza rate limit stretto.
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
            seen_ips.add(ip); ips.append(ip)

    def add_url(raw: str) -> None:
        url = raw.strip() if raw else ""
        if url and url not in seen_urls:
            seen_urls.add(url); urls.append(url)

    def add_hash(raw: str) -> None:
        h = raw.strip() if raw else ""
        if h and h not in seen_hashes:
            seen_hashes.add(h); hashes.append(h)

    hi = record.header_indicators or {}
    for hop in hi.get("received_hops", []):
        if hop.get("ip") and not hop.get("private_ip"):
            add_ip(hop["ip"])

    if record.x_originating_ip:
        add_ip(record.x_originating_ip)

    ui = record.url_indicators or {}
    for u in ui.get("urls", []):
        url_str = u.get("original_url") or u.get("url", "")
        if url_str:
            add_url(url_str)
        host = u.get("host", "")
        if u.get("is_ip_address") or u.get("is_ip"):
            add_ip(host)
        resolved = u.get("resolved_ip", "")
        if resolved:
            add_ip(resolved)

    bi = record.body_indicators or {}
    for link in bi.get("obfuscated_links", []):
        href = link.get("actual_href", "")
        if href:
            add_url(href)

    ai = record.attachment_indicators or {}
    for att in ai.get("attachments", []):
        h = att.get("hash_sha256", "")
        if h:
            add_hash(h)

    return ips, urls, hashes


def _extract_priority_indicators(
    record: EmailAnalysis,
) -> tuple[list[str], list[str], list[str]]:
    """
    Estrae SOLO gli indicatori ad alta priorità per i servizi SLOW
    (VirusTotal, AbuseIPDB) che hanno rate limit stringenti.

    IP: solo received_hops + x_originating_ip (non i resolved_ip degli URL —
        quelli sono IP di CDN normali come CloudFlare, Amazon, Google).

    URL: solo quelli con indicatori di rischio espliciti:
        - IP diretto (http://185.1.2.3/...)
        - URL shortener (bit.ly, t.co...)
        - Dominio nuovo (< 90 giorni)
        - Dominio punycode/IDN
        - URL score >= 25 dall'analisi
        - Link offuscati (href reale ≠ testo visibile)
        Hard cap: max 4 URL (rispetta il limite 4 req/min di VirusTotal free).

    Hash: tutti gli allegati (normalmente pochi).
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
            seen_ips.add(ip); ips.append(ip)

    def add_url_if_suspicious(u: dict) -> None:
        if len(urls) >= 4:   # hard cap VirusTotal free
            return
        url_str = u.get("original_url") or u.get("url", "")
        if not url_str or url_str in seen_urls:
            return
        suspicious = (
            u.get("is_ip_address") or u.get("is_ip") or
            u.get("is_shortener") or
            u.get("is_new_domain") or
            u.get("is_punycode") or
            (u.get("risk_score", 0) >= 25)
        )
        if suspicious:
            seen_urls.add(url_str); urls.append(url_str)

    # IP: SOLO sorgenti interne all'email (non resolved_ip degli URL)
    hi = record.header_indicators or {}
    for hop in hi.get("received_hops", []):
        if hop.get("ip") and not hop.get("private_ip"):
            add_ip(hop["ip"])
    if record.x_originating_ip:
        add_ip(record.x_originating_ip)

    # URL: solo quelli sospetti
    ui = record.url_indicators or {}
    for u in ui.get("urls", []):
        add_url_if_suspicious(u)

    # Link offuscati: sempre sospetti per definizione
    bi = record.body_indicators or {}
    for link in bi.get("obfuscated_links", []):
        href = link.get("actual_href", "")
        if href and href not in seen_urls and len(urls) < 4:
            seen_urls.add(href); urls.append(href)

    # Hash: tutti
    ai = record.attachment_indicators or {}
    for att in ai.get("attachments", []):
        h = att.get("hash_sha256", "")
        if h and h not in seen_hashes:
            seen_hashes.add(h); hashes.append(h)

    return ips, urls, hashes


def _summary_to_dict(summary: ReputationSummary) -> dict:
    return json.loads(json.dumps(asdict(summary), default=str))


# ---------------------------------------------------------------------------
# FASE 1 — servizi fast, risposta garantita < 15s
# ---------------------------------------------------------------------------

@router.post("/{job_id}")
async def run_reputation_fast(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    """
    Esegue i check di reputazione FAST (Spamhaus, ASN, OpenPhish, crt.sh,
    PhishTank, Redirect Chain, MalwareBazaar).
    Risposta in < 15s. I servizi lenti (VirusTotal, AbuseIPDB) vengono
    avviati automaticamente in background: usa GET /api/analysis/{job_id}
    per vedere quando i risultati vengono aggiornati.
    """
    if not re.match(r'^[0-9a-f-]{36}$', job_id):
        raise HTTPException(status_code=400, detail="job_id non valido")

    record = await db.get(EmailAnalysis, job_id)
    if not record:
        raise HTTPException(status_code=404,
            detail="Analisi non trovata. Esegui prima POST /api/analysis/{job_id}")

    ips, urls, hashes = _extract_indicators(record)

    # Fase 1: servizi fast, timeout generoso 25s
    loop = asyncio.get_event_loop()
    try:
        summary = await asyncio.wait_for(
            loop.run_in_executor(None, run_fast_checks, ips, urls, hashes),
            timeout=50.0,  # sicuro con axios frontend timeout=60s
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504,
            detail="I servizi di reputazione non hanno risposto nel tempo previsto. Riprova.")

    rep_dict = _summary_to_dict(summary)
    rep_dict["reputation_phase"] = "fast"   # indica che la fase 2 è ancora in corso
    record.reputation_results = rep_dict
    flag_modified(record, "reputation_results")
    await db.commit()

    # Avvia fase 2 in background con indicatori SELETTIVI (solo IP interni + URL sospetti)
    # per rispettare i rate limit di VirusTotal (4/min) e AbuseIPDB senza sprecare richieste
    slow_ips, slow_urls, slow_hashes = _extract_priority_indicators(record)
    if slow_ips or slow_urls or slow_hashes:
        background_tasks.add_task(
            _run_slow_background, job_id, slow_ips, slow_urls, slow_hashes, rep_dict
        )

    has_slow = bool(slow_ips or slow_urls or slow_hashes)

    # Se non ci sono entità per la fase 2, segna subito come completo
    if not has_slow:
        rep_dict["reputation_phase"] = "complete"
        record.reputation_results = rep_dict
        flag_modified(record, "reputation_results")
        await db.commit()

    return {
        "job_id":            job_id,
        "phase":             "fast",
        "slow_running":      has_slow,
        "reputation_score":  summary.reputation_score,
        "malicious_count":   summary.malicious_count,
        "service_registry":  rep_dict.get("service_registry", []),
        "results":           rep_dict,
        "entities_analyzed": {
            "ips":    len(ips),
            "urls":   len(urls),
            "hashes": len(hashes),
        },
        "slow_entities": {
            "ips":    len(slow_ips),
            "urls":   len(slow_urls),
            "hashes": len(slow_hashes),
        } if has_slow else None,
    }


# ---------------------------------------------------------------------------
# Fase 2 — background task (non ha timeout di sessione)
# ---------------------------------------------------------------------------

import logging as _logging
_bg_logger = _logging.getLogger("emlyzer.reputation.background")


async def _run_slow_background(
    job_id: str,
    ips: list[str],
    urls: list[str],
    hashes: list[str],
    fast_rep_dict: dict,
) -> None:
    """
    Esegue VirusTotal/AbuseIPDB/crt.sh in background.
    Usa asyncio.get_running_loop() (Python 3.10+) per eseguire run_slow_checks
    nel thread pool senza bloccare il loop FastAPI.
    Quando finisce salva reputation_phase="complete" nel DB.
    """
    from models.database import AsyncSessionLocal as async_session_factory

    fast_summary = _dict_to_summary(fast_rep_dict)

    try:
        loop = asyncio.get_running_loop()
        updated = await loop.run_in_executor(
            None, run_slow_checks, ips, urls, hashes, fast_summary
        )
    except Exception as e:
        _bg_logger.error("run_slow_checks fallito per job %s: %s", job_id, e)
        # Anche se fallisce, segna come complete per fermare il polling
        try:
            async with async_session_factory() as session:
                record = await session.get(EmailAnalysis, job_id)
                if record and record.reputation_results:
                    d = dict(record.reputation_results)
                    d["reputation_phase"] = "complete"
                    record.reputation_results = d
                    flag_modified(record, "reputation_results")
                    await session.commit()
        except Exception:
            pass
        return

    try:
        async with async_session_factory() as session:
            record = await session.get(EmailAnalysis, job_id)
            if record:
                final_dict = _summary_to_dict(updated)
                final_dict["reputation_phase"] = "complete"
                record.reputation_results = final_dict
                flag_modified(record, "reputation_results")
                await session.commit()
                _bg_logger.info("Fase 2 completata per job %s", job_id)
    except Exception as e:
        _bg_logger.error("Salvataggio fase 2 fallito per job %s: %s", job_id, e)


def _dict_to_summary(d: dict) -> ReputationSummary:
    """Ricostruisce un ReputationSummary da un dict serializzato."""
    from core.reputation.connectors import ReputationResult
    def to_result(r: dict) -> ReputationResult:
        return ReputationResult(
            source=r.get("source", ""),
            entity=r.get("entity", ""),
            entity_type=r.get("entity_type", ""),
            queried=r.get("queried", False),
            is_malicious=r.get("is_malicious", False),
            confidence=r.get("confidence", 0.0),
            detail=r.get("detail", ""),
            error=r.get("error", ""),
            skipped=r.get("skipped", False),
            skip_reason=r.get("skip_reason", ""),
        )
    return ReputationSummary(
        ip_results=  [to_result(r) for r in d.get("ip_results", [])],
        url_results= [to_result(r) for r in d.get("url_results", [])],
        hash_results=[to_result(r) for r in d.get("hash_results", [])],
        service_registry=d.get("service_registry", []),
        malicious_count=d.get("malicious_count", 0),
        reputation_score=d.get("reputation_score", 0.0),
    )