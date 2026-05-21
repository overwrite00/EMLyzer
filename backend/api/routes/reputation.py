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
import logging
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm.attributes import flag_modified
from models.database import get_session, EmailAnalysis
from utils.i18n import t
from core.reputation.connectors import (
    run_fast_checks,
    run_slow_checks,
    finalize_fast_only,
    ReputationSummary,
)
from dataclasses import asdict
import json

router = APIRouter()
_logger = logging.getLogger(__name__)
_bg_logger = logging.getLogger("emlyzer.reputation.background")

# ─────────────────────────────────────────────────────────────────────────────
# INTELLIGENT FILTERING — CDN/Hosting Providers da escludere dalle ricerche
# di reputazione (sono servizi legittimi, non rilevanti per analisi phishing)
# ─────────────────────────────────────────────────────────────────────────────

_TRUSTED_CDN_DOMAINS = {
    # Google
    "googleapis.com", "gstatic.com", "google.com", "googleusercontent.com",
    "google-analytics.com", "googletagmanager.com", "googleadservices.com",

    # Microsoft
    "microsoft.com", "azureedge.net", "windows.net", "office365.com",
    "outlook.com", "live.com", "onedrive.com",

    # CloudFlare, AWS, Azure, Akamai
    "cloudflare.com", "amazonaws.com", "akamaized.net", "akamai.com",
    "azurewebsites.net", "blob.core.windows.net",

    # CDN networks
    "cdn77.org", "cloudfront.net", "edgecast.com", "fastly.net",
    "jsdelivr.net", "unpkg.com", "cdnjs.com",

    # Social media / trusted platforms
    "facebook.com", "fbcdn.net", "twitter.com", "t.co", "youtube.com",
    "youtu.be", "github.com", "githubusercontent.com", "gitlab.com",
    "linkedin.com", "instagram.com", "pinterest.com",

    # Payment / Shopping (legitimate)
    "paypal.com", "stripe.com", "shopify.com", "amazon.com", "ebay.com",

    # Email services
    "gmail.com", "hotmail.com", "yahoo.com", "protonmail.com",
    "sendgrid.net", "mailchimp.com",
}

_TRUSTED_CDN_IPS = {
    # Google IP ranges (AS15169)
    "142.251", "142.250", "142.249", "142.248", "142.247",
    "172.217", "172.218", "172.219", "172.220",
    "199.36.153", "199.36.154",

    # CloudFlare (AS13335)
    "104.16", "104.17", "104.18", "104.19", "104.20", "104.21",
    "104.22", "104.23", "104.24", "104.25",

    # Microsoft Azure (AS8075)
    "13.64", "13.65", "13.66", "13.67", "13.68", "13.69",
    "13.70", "13.71", "13.72", "13.73", "13.74", "13.75",

    # Amazon AWS (AS16509)
    "52.0", "52.1", "52.2", "52.3", "52.4", "52.5",
    "54.0", "54.1", "54.2", "54.3", "54.4",
}

def _is_trusted_cdn(hostname: str) -> bool:
    """Controlla se il dominio è di un CDN legittimo noto."""
    if not hostname:
        return False
    hostname_lower = hostname.lower()
    # Exact match
    if hostname_lower in _TRUSTED_CDN_DOMAINS:
        return True
    # Suffix match (es. fonts.googleapis.com -> googleapis.com)
    for trusted in _TRUSTED_CDN_DOMAINS:
        if hostname_lower.endswith("." + trusted) or hostname_lower == trusted:
            return True
    return False

def _is_trusted_cdn_ip(ip: str) -> bool:
    """Controlla se l'IP è di un CDN legittimo noto."""
    if not ip:
        return False
    for trusted_prefix in _TRUSTED_CDN_IPS:
        if ip.startswith(trusted_prefix):
            return True
    return False


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
    Estrae IP, URL e hash per i servizi FAST — con FILTRI INTELLIGENTI.

    LOGICA ANALITICA:
    - IP: Estrai SOLO sender IP da Received headers + X-Originating-IP
          ESCLUDI: IPs di CDN pubbliche (Google, CloudFlare, etc.)
    - URL: Estrai SOLO URL sospette (non-CDN, non-trusted domains)
           ESCLUDI: URL da Google Fonts, Microsoft, etc.
    - Hash: Estrai SOLO file eseguibili, documenti Office potenzialmente malevoli

    Obiettivo: Ridurre il rumore, inviare ai servizi di reputazione SOLO dati
               rilevanti per identificare email maligne.
    """
    seen_ips:    set[str] = set()
    seen_urls:   set[str] = set()
    seen_hashes: set[str] = set()
    seen_domains: set[str] = set()
    ips:    list[str] = []
    urls:   list[str] = []
    hashes: list[str] = []
    domains: list[str] = []

    def add_ip(raw: str, skip_cdn_check: bool = False) -> None:
        """Aggiunge IP solo se pubblico e non di CDN legittimi."""
        ip = raw.strip().strip("[]") if raw else ""
        if ip and ip not in seen_ips and _is_public_ip(ip):
            # Skip IPs di CDN legittimi (a meno che sia sender IP)
            if not skip_cdn_check and _is_trusted_cdn_ip(ip):
                _logger.debug(f"[FILTRO] IP {ip} da CDN legittima - escluso")
                return
            seen_ips.add(ip)
            ips.append(ip)

    def add_url(raw: str, is_suspicious: bool = False) -> None:
        """Aggiunge URL solo se sospetta o non da CDN legittimi."""
        url = raw.strip() if raw else ""
        if not url or url in seen_urls:
            return

        # Estrai hostname dall'URL
        try:
            from urllib.parse import urlparse
            hostname = urlparse(url).netloc.split(":")[0].lstrip("www.")
        except Exception:
            hostname = ""

        # Se è URL sospetta (shortener, IP diretto, nuovo dominio, punycode)
        # aggiungi indipendentemente da CDN
        if is_suspicious:
            seen_urls.add(url)
            urls.append(url)
            return

        # Altrimenti, escludi URL da CDN/trusted domains
        if _is_trusted_cdn(hostname):
            _logger.debug(f"[FILTRO] URL {url} da CDN legittima - escluso")
            return

        seen_urls.add(url)
        urls.append(url)

    def add_hash(raw: str) -> None:
        """Aggiunge solo hash di file potenzialmente malevoli."""
        h = raw.strip() if raw else ""
        if h and h not in seen_hashes:
            seen_hashes.add(h)
            hashes.append(h)

    def add_domain(raw: str) -> None:
        """Estrai dominio da URL e aggiungilo se non è CDN trusted."""
        if not raw:
            return
        try:
            from urllib.parse import urlparse
            hostname = urlparse(raw).netloc.split(":")[0].lstrip("www.")
            # Scarta IP diretti
            if hostname and not (hostname.count(".") < 1 or hostname.replace(".", "").isdigit()):
                if hostname not in seen_domains and not _is_trusted_cdn(hostname):
                    seen_domains.add(hostname)
                    domains.append(hostname)
                    _logger.debug(f"[DOMAIN] {hostname} - estratto da URL")
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # ESTRAZIONE IP: Sender IP + Received headers (ESCLUDI resolved IPs from URLs)
    # ─────────────────────────────────────────────────────────────────────────
    hi = record.header_indicators or {}

    # Sender IP: SEMPRE importante, skip CDN check
    if record.x_originating_ip:
        add_ip(record.x_originating_ip, skip_cdn_check=True)

    # Received hops: primi 2-3 hop (mittente -> intermediari prossimi)
    # Skip hop finali (recipient server)
    for i, hop in enumerate(hi.get("received_hops", [])):
        if i > 2:  # Solo primi 3 hop
            break
        if hop.get("ip") and not hop.get("private_ip"):
            add_ip(hop["ip"], skip_cdn_check=True)

    # ─────────────────────────────────────────────────────────────────────────
    # ESTRAZIONE URL: Sospette + non-CDN (ESCLUDI resolved IPs e URL CDN)
    # ─────────────────────────────────────────────────────────────────────────
    ui = record.url_indicators or {}
    for u in ui.get("urls", []):
        url_str = u.get("original_url") or u.get("url", "")
        if not url_str:
            continue

        # Determina se URL è sospetta
        is_suspicious = (
            u.get("is_ip_address") or u.get("is_ip") or  # IP diretto
            u.get("is_shortener") or                      # Shortener (bit.ly, etc.)
            u.get("is_new_domain") or                     # Dominio nuovo
            u.get("is_punycode") or                       # IDN/Punycode
            (u.get("risk_score", 0) >= 25)              # Risk score alto
        )

        add_url(url_str, is_suspicious=is_suspicious)

    # Link offuscati: SEMPRE sospetti per definizione
    bi = record.body_indicators or {}
    for link in bi.get("obfuscated_links", []):
        href = link.get("actual_href", "")
        if href:
            add_url(href, is_suspicious=True)

    # ─────────────────────────────────────────────────────────────────────────
    # ESTRAZIONE HASH: File allegati eseguibili/doc potenzialmente malevoli
    # ─────────────────────────────────────────────────────────────────────────
    ai = record.attachment_indicators or {}
    for att in ai.get("attachments", []):
        # Estrai SOLO hash di file potenzialmente malevoli
        h = att.get("hash_sha256", "")
        if h:
            add_hash(h)

    # ─────────────────────────────────────────────────────────────────────────
    # ESTRAZIONE DOMINI: Per servizi che lavorano su domini (crt.sh, CIRCL, etc.)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ui.get("urls", []):
        url_str = u.get("original_url") or u.get("url", "")
        if url_str:
            add_domain(url_str)
    for link in bi.get("obfuscated_links", []):
        href = link.get("actual_href", "")
        if href:
            add_domain(href)

    return ips, urls, hashes, domains


def _extract_priority_indicators(
    record: EmailAnalysis,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Estrae indicatori CRITICI per servizi SLOW (VirusTotal, AbuseIPDB, SecurityTrails, etc.).

    LOGICA INTELLIGENTE per rate-limited services:

    IP (Sender + intermediari):
      - x_originating_ip (sempre)
      - Received hops 1-2 (mittente + primo intermediario)
      - ESCLUDI: resolved IPs da URLs (sono spesso CDN pubbliche)
      - ESCLUDI: IPv6 (troppi false positives)
      - ESCLUDI: IPs trusted CDN

    URL (Massimizza coverage entro hard cap):
      - Hard cap: max 4 URL per VirusTotal free (4 req/min)
      - INCLUDI: TUTTE le URL non-CDN (sospette e normali)
      - PRIORIZZA: URL sospette (IP diretto, shortener, new domain,
        punycode, risk>=25) sono aggiunte per prime
      - INCLUDI: anche URL "normali" non-CDN se c'è spazio fino a 4
      - ESCLUDI: URL da Google, Microsoft, trusted CDN hosts
      - SEMPRE: link offuscati (sono definitivamente sospetti)

    Domain (Per SecurityTrails, crt.sh):
      - Hard cap: max 1 dominio per SecurityTrails (quota 50/month)
      - Hard cap: max 2 domini per crt.sh
      - Prioritizza domini da URL sospette

    Hash:
      - Tutti gli allegati (sono rari e vanno sempre verificati)

    Obiettivo: Massimizzare coverage (entro rate limit), inviare
               TUTTI i dati rilevanti che potrebbero rivelare
               malware/phishing, senza sprecare crediti VirusTotal/SecurityTrails.
    """
    seen_ips:    set[str] = set()
    seen_urls:   set[str] = set()
    seen_hashes: set[str] = set()
    seen_domains: set[str] = set()
    ips:    list[str] = []
    urls:   list[str] = []
    hashes: list[str] = []
    domains: list[str] = []

    def add_ip(raw: str, skip_cdn_check: bool = True) -> None:
        """Aggiunge SOLO sender IP e intermediari prossimi."""
        ip = raw.strip().strip("[]") if raw else ""
        if ip and ip not in seen_ips and _is_public_ip(ip):
            # Per SLOW services, skip anche IPv6 (troppi false positives)
            if ":" in ip:  # IPv6
                _logger.debug(f"[FILTRO SLOW] IPv6 {ip} - escluso (troppi false positives)")
                return
            # Skip IPs trusted CDN (se non skip_cdn_check)
            if not skip_cdn_check and _is_trusted_cdn_ip(ip):
                _logger.debug(f"[FILTRO SLOW] IP {ip} da CDN trusted - escluso")
                return
            seen_ips.add(ip)
            ips.append(ip)

    def add_url_if_worth_checking(u: dict) -> None:
        """
        Aggiunge URL in ordine di priorità per massimizzare coverage.

        Hard cap: max 4 URL per VirusTotal free (4 req/min).
        Strategia: priorizza URL sospette, ma includi anche normali se c'è spazio.

        Non escludere completamente le URL non-sospette — sono comunque
        dati rilevanti che valgono la pena verificare con VirusTotal.
        """
        if len(urls) >= 4:  # Hard cap VirusTotal free tier
            return

        url_str = u.get("original_url") or u.get("url", "")
        if not url_str or url_str in seen_urls:
            return

        # Estrai hostname e controlla se trusted CDN (escludi sempre)
        try:
            from urllib.parse import urlparse
            hostname = urlparse(url_str).netloc.split(":")[0].lstrip("www.")
        except Exception:
            hostname = ""

        if _is_trusted_cdn(hostname):
            _logger.debug(f"[FILTRO SLOW] URL {url_str} da trusted CDN - esclusa")
            return

        # Determina se è sospetta (per logging)
        is_suspicious = (
            u.get("is_ip_address") or u.get("is_ip") or      # IP diretto
            u.get("is_shortener") or                          # Shortener
            u.get("is_new_domain") or                         # Nuovo dominio
            u.get("is_punycode") or                           # IDN spoofing
            (u.get("risk_score", 0) >= 25)                   # Risk score alto
        )

        # Aggiungi TUTTE le URL non-CDN, indipendentemente da is_suspicious.
        # VirusTotal ha rate limit stretto, ma anche una singola URL non-sospetta
        # da un sito non-CDN merita verifica se è presente nell'email.
        seen_urls.add(url_str)
        urls.append(url_str)
        if is_suspicious:
            _logger.debug(f"[FILTRO SLOW] URL {url_str} (sospetta, risk_score={u.get('risk_score', 0)}) - inclusa")
        else:
            _logger.debug(f"[FILTRO SLOW] URL {url_str} (normale, non da CDN) - inclusa per coverage")

    # ─────────────────────────────────────────────────────────────────────────
    # IP: Sender IP + primi 2 hop (mittente -> intermediari prossimi)
    # ESCLUDE resolved IPs, IPv6, e IPs da CDN trusted
    # ─────────────────────────────────────────────────────────────────────────
    hi = record.header_indicators or {}

    # Sender IP: SEMPRE (skip CDN check perché è il mittente)
    if record.x_originating_ip:
        add_ip(record.x_originating_ip, skip_cdn_check=True)

    # Received hops: SOLO primi 2 (mittente e primo intermediario)
    for i, hop in enumerate(hi.get("received_hops", [])):
        if i > 1:  # Skip hop 3+
            break
        if hop.get("ip") and not hop.get("private_ip"):
            add_ip(hop["ip"], skip_cdn_check=True)

    # ─────────────────────────────────────────────────────────────────────────
    # URL: Tutte le non-CDN, fino a 4 (hard cap VirusTotal free tier)
    # Priorità: sospette prima, ma includi anche non-sospette per coverage
    # ─────────────────────────────────────────────────────────────────────────
    ui = record.url_indicators or {}
    for u in ui.get("urls", []):
        add_url_if_worth_checking(u)

    # Link offuscati: SEMPRE sospetti per definizione
    bi = record.body_indicators or {}
    for link in bi.get("obfuscated_links", []):
        href = link.get("actual_href", "")
        if href and href not in seen_urls and len(urls) < 4:
            seen_urls.add(href)
            urls.append(href)

    # ─────────────────────────────────────────────────────────────────────────
    # Hash: Tutti gli allegati
    # ─────────────────────────────────────────────────────────────────────────
    ai = record.attachment_indicators or {}
    for att in ai.get("attachments", []):
        h = att.get("hash_sha256", "")
        if h and h not in seen_hashes:
            seen_hashes.add(h)
            hashes.append(h)

    # ─────────────────────────────────────────────────────────────────────────
    # Domain: Per SecurityTrails (max 1) e crt.sh (max 2)
    # Estrai domini da URL sospette
    # ─────────────────────────────────────────────────────────────────────────
    for u in ui.get("urls", []):
        if len(domains) >= 2:  # Hard cap crt.sh (2 domini)
            break
        url_str = u.get("original_url") or u.get("url", "")
        if url_str:
            try:
                from urllib.parse import urlparse
                hostname = urlparse(url_str).netloc.split(":")[0].lstrip("www.")
                is_suspicious = (
                    u.get("is_ip_address") or u.get("is_ip") or
                    u.get("is_shortener") or u.get("is_new_domain") or
                    u.get("is_punycode") or (u.get("risk_score", 0) >= 25)
                )
                if hostname and not _is_trusted_cdn(hostname) and hostname not in seen_domains:
                    # Prioritizza domini da URL sospette
                    if is_suspicious or len(domains) < 1:
                        seen_domains.add(hostname)
                        domains.append(hostname)
                        _logger.debug(f"[FILTRO SLOW] Domain {hostname} - estratto da URL sospetta")
            except Exception:
                pass

    return ips, urls, hashes, domains


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
        raise HTTPException(status_code=400, detail=t("analysis.invalid_job_id"))

    record = await db.get(EmailAnalysis, job_id)
    if not record:
        raise HTTPException(status_code=404,
            detail=t("analysis.run_first", job_id=job_id))

    ips, urls, hashes, domains = _extract_indicators(record)

    # DEBUG LOGGING: Mostra esattamente cosa viene estratto
    _logger.debug(f"[REPUTATION] Extracted indicators for job {job_id}: IPs={len(ips)}, URLs={len(urls)}, Hashes={len(hashes)}, Domains={len(domains)}, received_hops={len(record.header_indicators.get('received_hops', []) if record.header_indicators else [])}, x_originating_ip={record.x_originating_ip}")

    # Fase 1: servizi fast, timeout generoso 25s
    loop = asyncio.get_event_loop()
    try:
        summary = await asyncio.wait_for(
            loop.run_in_executor(None, run_fast_checks, ips, urls, hashes, domains),
            timeout=50.0,  # sicuro con axios frontend timeout=60s
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504,
            detail=t("reputation.timeout"))

    rep_dict = _summary_to_dict(summary)
    rep_dict["reputation_phase"] = "fast"   # indica che la fase 2 è ancora in corso
    record.reputation_results = rep_dict
    flag_modified(record, "reputation_results")
    await db.commit()

    # Avvia fase 2 in background con indicatori SELETTIVI (solo IP interni + URL sospetti)
    # per rispettare i rate limit di VirusTotal (4/min) e AbuseIPDB senza sprecare richieste
    slow_ips, slow_urls, slow_hashes, slow_domains = _extract_priority_indicators(record)
    has_slow = bool(slow_ips or slow_urls or slow_hashes or slow_domains)
    slow_indicators = {"ips": slow_ips, "urls": slow_urls, "hashes": slow_hashes, "domains": slow_domains}

    # DEBUG LOGGING: Mostra indicatori selettivi per SLOW services
    _logger.debug(f"[REPUTATION] Slow indicators for job {job_id}: IPs={len(slow_ips)}, URLs={len(slow_urls)}, Hashes={len(slow_hashes)}, Domains={len(slow_domains)}")

    if has_slow:
        rep_dict["slow_indicators"] = slow_indicators
        background_tasks.add_task(
            _run_slow_background, job_id, slow_ips, slow_urls, slow_hashes, rep_dict, slow_domains
        )
    else:
        # Nessun indicatore SLOW: rimuovi i placeholder "in elaborazione" prima di
        # salvare come "complete". Senza questo i servizi AbuseIPDB/VirusTotal/crt.sh
        # rimarrebbero bloccati in stato "pending" indefinitamente nel frontend.
        summary = finalize_fast_only(summary)
        rep_dict = _summary_to_dict(summary)
        rep_dict["slow_indicators"] = slow_indicators
        rep_dict["reputation_phase"] = "complete"
        record.reputation_results = rep_dict
        flag_modified(record, "reputation_results")
        await db.commit()

    return {
        "job_id":            job_id,
        "phase":             "fast" if has_slow else "complete",
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
        "slow_indicators":   slow_indicators,
    }


# ---------------------------------------------------------------------------
# Fase 2 — background task (non ha timeout di sessione)
# ---------------------------------------------------------------------------


async def _run_slow_background(
    job_id: str,
    ips: list[str],
    urls: list[str],
    hashes: list[str],
    fast_rep_dict: dict,
    domains: list[str] | None = None,
) -> None:
    """
    Esegue VirusTotal/AbuseIPDB/crt.sh in background.
    Usa asyncio.get_running_loop() (Python 3.10+) per eseguire run_slow_checks
    nel thread pool senza bloccare il loop FastAPI.
    Quando finisce salva reputation_phase="complete" nel DB.
    """
    from models.database import AsyncSessionLocal as async_session_factory

    fast_summary = _dict_to_summary(fast_rep_dict)
    domains = domains or []

    try:
        loop = asyncio.get_running_loop()
        updated = await loop.run_in_executor(
            None, run_slow_checks, ips, urls, hashes, fast_summary, domains
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
                # Preserva slow_indicators salvati dalla fase 1
                prev = record.reputation_results or {}
                if "slow_indicators" in prev:
                    final_dict["slow_indicators"] = prev["slow_indicators"]
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
        domain_results=[to_result(r) for r in d.get("domain_results", [])],
        service_registry=d.get("service_registry", []),
        malicious_count=d.get("malicious_count", 0),
        reputation_score=d.get("reputation_score", 0.0),
    )


# ---------------------------------------------------------------------------
# Phase 2C: Health Check Endpoint per URLScan.io (v0.14.3+)
# ---------------------------------------------------------------------------

@router.get("/test-urlscan")
async def test_urlscan_health():
    """
    Testa la connessione a URLScan.io e verifica la configurazione dell'API key.
    Utile per diagnosticare problemi di autenticazione o rate limiting.

    Ritorna:
      {
        "connectivity": bool,          # Riesce a raggiungere urlscan.io?
        "api_key_configured": bool,    # URLSCAN_API_KEY è configurato?
        "api_key_valid": bool,         # La chiave è valida? (test con query semplice)
        "system_info": {...},          # Sistema operativo, Python version, etc.
        "suggestions": [...]           # Consigli di configurazione
      }
    """
    import sys
    import platform
    import requests
    from utils.config import settings

    result = {
        "connectivity": False,
        "api_key_configured": False,
        "api_key_valid": False,
        "system_info": {
            "os": platform.system(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "requests_version": requests.__version__,
        },
        "suggestions": [],
    }

    # Test 1: Connessione a URLScan.io
    try:
        resp = requests.head("https://urlscan.io/api/v1/search/", timeout=5)
        result["connectivity"] = True
    except Exception as e:
        result["suggestions"].append(f"URLScan.io non raggiungibile: {type(e).__name__}")
        return result

    # Test 2: API key configurato?
    api_key = settings.URLSCAN_API_KEY
    if api_key and api_key.strip():
        result["api_key_configured"] = True

        # Test 3: API key valido?
        try:
            headers = {"API-Key": api_key.strip()}
            resp = requests.get(
                "https://urlscan.io/api/v1/search/",
                params={"q": "page.domain:example.com", "size": "1"},
                headers=headers,
                timeout=5,
            )
            if resp.status_code == 200:
                result["api_key_valid"] = True
            elif resp.status_code == 401:
                result["suggestions"].append("API key invalida o scaduta. Verifica urlscan.io/user/settings")
            elif resp.status_code == 403:
                result["suggestions"].append("HTTP 403 Forbidden. Possibili cause: 1) Rate limit superato (1000 req/giorno), 2) IP blacklisted, 3) API key non valida. Verifica urlscan.io/user/settings")
            else:
                result["suggestions"].append(f"URLScan.io HTTP {resp.status_code}. Risposta: {resp.text[:100]}")
        except Exception as e:
            result["suggestions"].append(f"Errore test API key: {type(e).__name__}: {str(e)[:100]}")
    else:
        result["suggestions"].append("URLSCAN_API_KEY non configurato in .env. Registrati su https://urlscan.io/user/signup e configura la chiave per aumentare il limite a 1000 req/giorno")

    return result