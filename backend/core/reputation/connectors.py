"""
core/reputation/connectors.py

Connettori reputazione:
  IP:   AbuseIPDB, VirusTotal, Spamhaus DROP, ASN lookup (ipinfo.io)
  URL:  VirusTotal, OpenPhish, PhishTank, redirect chain
  Hash: VirusTotal, MalwareBazaar
  Domini: crt.sh (certificati TLS)

Ogni connettore traccia il proprio stato (queried/skipped/error) per la UI.
"""

import json
import time
import base64
import ipaddress
import urllib.parse
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait
from datetime import datetime, timezone
from pathlib import Path
import requests
from dataclasses import dataclass, field
from utils.config import settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT      = 8    # servizi di sicurezza (AbuseIPDB, VirusTotal, ecc.)
REQUEST_TIMEOUT_ASN  = 4    # ASN lookup
REQUEST_TIMEOUT_INFO = 5    # servizi informativi (crt.sh, redirect chain)

# ---------------------------------------------------------------------------
# Disk cache per feed locali (Spamhaus DROP, OpenPhish)
# ---------------------------------------------------------------------------
# I feed vengono scaricati al primo avvio e salvati in backend/data/cache/.
# Alla sessione successiva vengono letti dal disco se non scaduti (TTL).
# Se il download fallisce ma il cache scaduto esiste, viene usato come fallback.

_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"


def _cache_load(name: str, ttl_hours: int | None = None) -> list | None:
    """Carica dati dal cache su disco.
    Se ttl_hours è None ignora l'età (fallback stale).
    Restituisce la lista di dati o None se cache assente/corrotta/scaduta."""
    try:
        path = _CACHE_DIR / f"{name}.json"
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as f:
            cached = json.load(f)
        if ttl_hours is not None:
            saved_at = datetime.fromisoformat(cached["saved_at"])
            age_h = (datetime.now(timezone.utc) - saved_at).total_seconds() / 3600
            if age_h > ttl_hours:
                return None
        return cached["data"]
    except Exception:
        return None


def _cache_save(name: str, data: list) -> None:
    """Salva dati su disco come JSON con timestamp UTC. Scrittura atomica."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _CACHE_DIR / f"{name}.json"
        payload = {"saved_at": datetime.now(timezone.utc).isoformat(), "data": data}
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f)
        tmp.replace(path)
    except Exception:
        pass  # cache su disco è best-effort


# ---------------------------------------------------------------------------
# Rate limiter thread-safe con semaforo per servizio
# ---------------------------------------------------------------------------
# Ogni servizio ha un lock + timestamp dell'ultima richiesta.
# Garantisce che tra due chiamate allo stesso servizio passi almeno min_interval.
# Thread-safe: Lock serializza l'accesso al timestamp per ogni connettore.

_rate_lock:  dict[str, threading.Lock]  = {}
_rate_last:  dict[str, float]           = {}
_rate_meta_lock = threading.Lock()  # protegge la creazione di nuovi lock

# Intervalli minimi (secondi) per connettore
_RATE_INTERVALS: dict[str, float] = {
    "virustotal":   15.5,   # 4 req/min → 1 ogni 15s (con margine)
    "abuseipdb":    1.1,    # 1000/day → ~1 req/s
    "crtsh":        2.5,    # ~60/min → 1 ogni 2s (con margine)
    "malwarebazaar":0.7,    # ~100/min
    "phishtank":    0.5,
    "asnlookup":    0.3,
    "redirectchain":0.2,
    "shodaninternetdb": 0.3,  # InternetDB gratuito, nessun limit ufficiale
    "urlhaus":      0.3,    # URLhaus abuse.ch
    "threatfox":    0.3,    # ThreatFox abuse.ch
    "openphish":    0.0,    # feed locale, nessun limit
    "spamhaus":     0.0,    # feed locale, nessun limit
    "circl":            0.5,    # CIRCL Passive DNS — nessun limite ufficiale, conservativo
    "greynoise":        1.1,    # GreyNoise Community — 100 req/g free
    "urlscan":          1.0,    # URLScan.io — 100 req/h free
    "pulsedive":        2.5,    # Pulsedive — 30 req/min free
    "criminalip":       1.1,    # Criminal IP — free tier, conservativo
    "securitytrails":   3.0,    # SecurityTrails — 50 req/mese, molto conservativo
    "hybridanalysis":   1.0,    # Hybrid Analysis — free con registrazione
}

def _rate_limit(connector: str):
    """Attende il tempo necessario per rispettare il rate limit del connettore."""
    key = connector.lower().replace("_", "").replace("-", "").replace(" ", "")
    interval = _RATE_INTERVALS.get(key, 0.5)
    if interval <= 0:
        return

    with _rate_meta_lock:
        if key not in _rate_lock:
            _rate_lock[key] = threading.Lock()

    with _rate_lock[key]:
        now = time.monotonic()
        last = _rate_last.get(key, 0.0)
        wait_s = interval - (now - last)
        if wait_s > 0:
            time.sleep(wait_s)
        _rate_last[key] = time.monotonic()


def _http_get_with_retry(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    auth: tuple | None = None,
    timeout: float = REQUEST_TIMEOUT,
    max_retries: int = 2,
    rate_key: str = "",
) -> requests.Response:
    """
    Esegue una GET con retry su errori temporanei (429, 502, 503, 504).
    Backoff esponenziale: 2s, 4s. Su 429 usa Retry-After se presente.
    auth: tupla (user, password) per HTTP Basic Auth (opzionale).
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            backoff = 2.0 * (2 ** (attempt - 1))   # 2s, 4s
            logger.debug("Retry %d/%d per %s (attesa %.1fs)", attempt, max_retries, url, backoff)
            time.sleep(backoff)
        try:
            if rate_key:
                _rate_limit(rate_key)
            resp = requests.get(url, params=params, headers=headers, auth=auth, timeout=timeout)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 5))
                logger.debug("429 da %s — attesa %.1fs", url, retry_after)
                time.sleep(min(retry_after, 30))
                last_exc = requests.HTTPError(response=resp)
                continue
            if resp.status_code in (502, 503, 504) and attempt < max_retries:
                last_exc = requests.HTTPError(response=resp)
                continue
            return resp
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_exc = e
            continue
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("_http_get_with_retry: nessuna risposta")


def _http_post_with_retry(
    url: str,
    *,
    data: dict | None = None,
    json_data: dict | None = None,
    headers: dict | None = None,
    timeout: float = REQUEST_TIMEOUT,
    max_retries: int = 2,
    rate_key: str = "",
) -> requests.Response:
    """POST con retry e backoff — stessa logica di _http_get_with_retry."""
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            backoff = 2.0 * (2 ** (attempt - 1))
            time.sleep(backoff)
        try:
            if rate_key:
                _rate_limit(rate_key)
            resp = requests.post(url, data=data, json=json_data,
                                 headers=headers, timeout=timeout)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 5))
                time.sleep(min(retry_after, 30))
                last_exc = requests.HTTPError(response=resp)
                continue
            if resp.status_code in (502, 503, 504) and attempt < max_retries:
                last_exc = requests.HTTPError(response=resp)
                continue
            return resp
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_exc = e
            continue
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("_http_post_with_retry: nessuna risposta")


# ---------------------------------------------------------------------------
# Dataclass risultato
# ---------------------------------------------------------------------------

@dataclass
class ReputationResult:
    source: str
    entity: str
    entity_type: str       # "ip" / "url" / "hash"
    queried: bool = False  # True = chiamata API effettivamente eseguita
    is_malicious: bool = False
    confidence: float = 0.0
    detail: str = ""
    error: str = ""
    skipped: bool = False
    skip_reason: str = ""


# ---------------------------------------------------------------------------
# AbuseIPDB
# ---------------------------------------------------------------------------

def check_ip_abuseipdb(ip: str) -> ReputationResult:
    r = ReputationResult(source="AbuseIPDB", entity=ip, entity_type="ip")
    if not settings.ABUSEIPDB_API_KEY:
        r.skipped = True
        r.skip_reason = "ABUSEIPDB_API_KEY non configurata nel file .env"
        return r
    r.queried = True
    try:
        resp = _http_get_with_retry(
            "https://api.abuseipdb.com/api/v2/check",
            params={"ipAddress": ip, "maxAgeInDays": 90},
            headers={"Key": settings.ABUSEIPDB_API_KEY, "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
            rate_key="abuseipdb",
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        score = data.get("abuseConfidenceScore", 0)
        r.confidence = float(score)
        r.is_malicious = score >= 50
        r.detail = (
            f"Confidence: {score}% | "
            f"Segnalazioni: {data.get('totalReports', 0)} | "
            f"ISP: {data.get('isp', 'N/A')} | "
            f"Country: {data.get('countryCode', 'N/A')} | "
            f"Tipo: {data.get('usageType', 'N/A')}"
        )
    except requests.HTTPError as e:
        r.error = f"HTTP {e.response.status_code}: {e.response.text[:150]}"
    except requests.RequestException as e:
        r.error = f"Errore di rete: {e}"
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


# ---------------------------------------------------------------------------
# VirusTotal v3  (piano gratuito: 4 req/min, 500 req/giorno)
# ---------------------------------------------------------------------------

def _vt_headers():
    return {"x-apikey": settings.VIRUSTOTAL_API_KEY}

def _vt_stats_detail(stats: dict, name: str = "") -> tuple[bool, float, str]:
    malicious  = stats.get("malicious", 0)
    suspicious = stats.get("suspicious", 0)
    harmless   = stats.get("harmless", 0)
    undetected = stats.get("undetected", 0)
    total = malicious + suspicious + harmless + undetected or 1
    confidence = round((malicious / total) * 100, 1)
    is_mal = malicious > 0
    detail = (
        f"{malicious} malevoli, {suspicious} sospetti su {total} engine"
        + (f" | File: {name}" if name else "")
        + f" | Harmless: {harmless} | Undetected: {undetected}"
    )
    return is_mal, confidence, detail

def _vt_http_error(e: requests.HTTPError) -> str:
    code = e.response.status_code
    if code == 429: return "Quota VirusTotal esaurita (4 req/min piano gratuito — riprova tra poco)"
    if code == 401: return "Chiave API VirusTotal non valida"
    if code == 404: return "Entità non trovata in VirusTotal"
    return f"HTTP {code}: {e.response.text[:150]}"


def check_ip_virustotal(ip: str) -> ReputationResult:
    r = ReputationResult(source="VirusTotal", entity=ip, entity_type="ip")
    if not settings.VIRUSTOTAL_API_KEY:
        r.skipped = True; r.skip_reason = "VIRUSTOTAL_API_KEY non configurata nel file .env"; return r
    r.queried = True
    try:
        resp = _http_get_with_retry(
            f"https://www.virustotal.com/api/v3/ip_addresses/{ip}",
            headers=_vt_headers(),
            timeout=REQUEST_TIMEOUT,
            rate_key="virustotal",
        )
        resp.raise_for_status()
        stats = resp.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        r.is_malicious, r.confidence, r.detail = _vt_stats_detail(stats)
    except requests.HTTPError as e:
        r.error = _vt_http_error(e)
    except requests.RequestException as e:
        r.error = f"Errore di rete: {e}"
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


def check_url_virustotal(url: str) -> ReputationResult:
    r = ReputationResult(source="VirusTotal", entity=url, entity_type="url")
    if not settings.VIRUSTOTAL_API_KEY:
        r.skipped = True; r.skip_reason = "VIRUSTOTAL_API_KEY non configurata nel file .env"; return r
    r.queried = True
    try:
        url_id = base64.urlsafe_b64encode(url.encode()).rstrip(b"=").decode()
        resp = _http_get_with_retry(
            f"https://www.virustotal.com/api/v3/urls/{url_id}",
            headers=_vt_headers(),
            timeout=REQUEST_TIMEOUT,
            rate_key="virustotal",
        )
        if resp.status_code == 404:
            # URL non in cache: invia per analisi futura
            _http_post_with_retry(
                "https://www.virustotal.com/api/v3/urls",
                headers=_vt_headers(),
                data={"url": url},
                timeout=REQUEST_TIMEOUT,
                rate_key="virustotal",
            )
            r.detail = "URL inviato a VirusTotal per analisi (non era ancora in cache)"
            return r
        resp.raise_for_status()
        stats = resp.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        r.is_malicious, r.confidence, r.detail = _vt_stats_detail(stats)
    except requests.HTTPError as e:
        r.error = _vt_http_error(e)
    except requests.RequestException as e:
        r.error = f"Errore di rete: {e}"
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


def check_hash_virustotal(sha256: str) -> ReputationResult:
    r = ReputationResult(source="VirusTotal", entity=sha256, entity_type="hash")
    if not settings.VIRUSTOTAL_API_KEY:
        r.skipped = True; r.skip_reason = "VIRUSTOTAL_API_KEY non configurata nel file .env"; return r
    r.queried = True
    try:
        resp = _http_get_with_retry(
            f"https://www.virustotal.com/api/v3/files/{sha256}",
            headers=_vt_headers(),
            timeout=REQUEST_TIMEOUT,
            rate_key="virustotal",
        )
        if resp.status_code == 404:
            r.detail = "Hash non trovato in VirusTotal"; return r
        resp.raise_for_status()
        attrs = resp.json().get("data", {}).get("attributes", {})
        name = attrs.get("meaningful_name") or attrs.get("name", "")
        stats = attrs.get("last_analysis_stats", {})
        r.is_malicious, r.confidence, r.detail = _vt_stats_detail(stats, name)
    except requests.HTTPError as e:
        r.error = _vt_http_error(e)
    except requests.RequestException as e:
        r.error = f"Errore di rete: {e}"
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


# ---------------------------------------------------------------------------
# OpenPhish  (no API key)
# ---------------------------------------------------------------------------

_openphish_cache: set[str] = set()
_openphish_loaded = False
_openphish_error: str = ""

def _load_openphish():
    global _openphish_cache, _openphish_loaded, _openphish_error
    if _openphish_loaded:
        return
    # Prova cache su disco (TTL 12h) prima di scaricare dalla rete
    cached = _cache_load("openphish_feed", ttl_hours=12)
    if cached is not None:
        _openphish_cache = set(cached)
        _openphish_loaded = True
        return
    try:
        resp = _http_get_with_retry("https://openphish.com/feed.txt",
            headers={"User-Agent": f"EMLyzer/{settings.VERSION} (email analysis tool)"},
            timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        urls = [l.strip().lower() for l in resp.text.splitlines() if l.strip()]
        _openphish_cache = set(urls)
        _openphish_loaded = True
        _cache_save("openphish_feed", urls)
    except Exception as e:
        _openphish_error = str(e)
        # Fallback: cache scaduta piuttosto che feed vuoto
        stale = _cache_load("openphish_feed")  # nessun controllo TTL
        if stale is not None:
            _openphish_cache = set(stale)
            _openphish_error += " (usando cache scaduta)"
        _openphish_loaded = True

def check_url_openphish(url: str) -> ReputationResult:
    r = ReputationResult(source="OpenPhish", entity=url, entity_type="url", queried=True)
    try:
        _load_openphish()
        if _openphish_error:
            r.error = f"Feed non raggiungibile: {_openphish_error}"; return r
        r.is_malicious = url.lower() in _openphish_cache
        r.confidence = 90.0 if r.is_malicious else 0.0
        r.detail = ("URL nel feed OpenPhish — phishing confermato"
                    if r.is_malicious
                    else f"URL non nel feed ({len(_openphish_cache):,} voci caricate)")
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


# ---------------------------------------------------------------------------
# PhishTank
# ---------------------------------------------------------------------------

def check_url_phishtank(url: str) -> ReputationResult:
    r = ReputationResult(source="PhishTank", entity=url, entity_type="url")
    if not settings.PHISHTANK_API_KEY:
        r.skipped = True; r.skip_reason = "PHISHTANK_API_KEY non configurata nel file .env"; return r
    r.queried = True
    try:
        resp = _http_post_with_retry(
            "https://checkurl.phishtank.com/checkurl/",
            data={
                "url": url,
                "format": "json",
                "app_key": settings.PHISHTANK_API_KEY or "",
            },
            headers={"User-Agent": f"EMLyzer/{settings.VERSION} (email analysis tool)"},
            timeout=REQUEST_TIMEOUT,
            rate_key="phishtank",
        )
        resp.raise_for_status()
        data = resp.json().get("results", {})
        in_db = data.get("in_database", False)
        verified = data.get("verified", False)
        is_phish = data.get("valid", False)
        r.is_malicious = is_phish
        r.confidence = 100.0 if (in_db and verified) else (50.0 if in_db else 0.0)
        r.detail = f"In database: {in_db} | Verificato: {verified} | Phish: {is_phish}"
    except requests.HTTPError as e:
        r.error = f"HTTP {e.response.status_code}: {e.response.text[:150]}"
    except requests.RequestException as e:
        r.error = f"Errore di rete: {e}"
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


# ---------------------------------------------------------------------------
# MalwareBazaar  (richiede Auth-Key da auth.abuse.ch)
# Accetta ABUSECH_API_KEY (preferita) o MALWAREBAZAAR_API_KEY (legacy)
# ---------------------------------------------------------------------------

def check_hash_malwarebazaar(sha256: str) -> ReputationResult:
    r = ReputationResult(source="MalwareBazaar", entity=sha256, entity_type="hash")
    _key = settings.ABUSECH_API_KEY or settings.MALWAREBAZAAR_API_KEY

    if not _key:
        r.skipped = True
        r.skip_reason = "ABUSECH_API_KEY non configurata — registrati su auth.abuse.ch (o usa MALWAREBAZAAR_API_KEY legacy)"
        return r

    r.queried = True
    try:
        resp = _http_post_with_retry("https://mb-api.abuse.ch/api/v1/",
            data={"query": "get_info", "hash": sha256},
            headers={
                "User-Agent": f"EMLyzer/{settings.VERSION} (email analysis tool)",
                "Auth-Key": _key,
            },
            timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        st = data.get("query_status", "")
        if st == "ok":
            r.is_malicious = True; r.confidence = 100.0
            info = data.get("data", [{}])[0]
            r.detail = (f"Malware: {info.get('signature','N/A')} | "
                        f"Tipo: {info.get('file_type','N/A')} | "
                        f"Tag: {', '.join(info.get('tags',[]) or [])}")
        elif st == "hash_not_found":
            r.detail = "Hash non trovato in MalwareBazaar"
        else:
            r.detail = f"Status: {st}"
    except requests.RequestException as e:
        r.error = f"Errore di rete: {e}"
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


# ---------------------------------------------------------------------------
# Spamhaus DROP — blocklist IP pubblica, no API key
# ---------------------------------------------------------------------------

_spamhaus_cache: set[str] = set()
_spamhaus_loaded = False
_spamhaus_error: str = ""

def _load_spamhaus():
    global _spamhaus_cache, _spamhaus_loaded, _spamhaus_error
    if _spamhaus_loaded:
        return
    # Prova cache su disco (TTL 24h) prima di scaricare dalla rete
    cached = _cache_load("spamhaus_drop", ttl_hours=24)
    if cached is not None:
        try:
            _spamhaus_cache = [ipaddress.ip_network(c, strict=False) for c in cached]
            _spamhaus_loaded = True
            return
        except Exception:
            pass  # cache corrotta, riscarica
    try:
        # DROP list: singoli IP/CIDR malevoli di alto profilo
        resp = _http_get_with_retry(
            "https://www.spamhaus.org/drop/drop.txt",
            headers={"User-Agent": f"EMLyzer/{settings.VERSION} (email analysis tool)"},
            timeout=REQUEST_TIMEOUT,
            rate_key="spamhaus",
            max_retries=2,
        )
        resp.raise_for_status()
        networks = []
        cidr_strings = []
        for line in resp.text.splitlines():
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            cidr = line.split(";")[0].strip()
            try:
                networks.append(ipaddress.ip_network(cidr, strict=False))
                cidr_strings.append(cidr)
            except ValueError:
                pass
        _spamhaus_cache = networks
        _spamhaus_loaded = True
        _cache_save("spamhaus_drop", cidr_strings)
    except Exception as e:
        _spamhaus_error = str(e)
        # Fallback: cache scaduta piuttosto che lista vuota
        stale = _cache_load("spamhaus_drop")  # nessun controllo TTL
        if stale is not None:
            try:
                _spamhaus_cache = [ipaddress.ip_network(c, strict=False) for c in stale]
                _spamhaus_error += " (usando cache scaduta)"
            except Exception:
                pass
        _spamhaus_loaded = True

def check_ip_spamhaus(ip: str) -> ReputationResult:
    r = ReputationResult(source="Spamhaus DROP", entity=ip, entity_type="ip", queried=True)
    try:
        _load_spamhaus()
        if _spamhaus_error:
            r.error = f"Feed non raggiungibile: {_spamhaus_error}"
            return r
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            r.detail = "Formato IP non valido"
            return r
        for net in _spamhaus_cache:
            if addr in net:
                r.is_malicious = True
                r.confidence = 95.0
                r.detail = f"IP in Spamhaus DROP ({net})"
                return r
        r.detail = f"IP non in Spamhaus DROP ({len(_spamhaus_cache)} reti caricate)"
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


# ---------------------------------------------------------------------------
# ASN Lookup — ipinfo.io, gratuito senza chiave (50k req/mese)
# ---------------------------------------------------------------------------

def check_ip_asn(ip: str) -> ReputationResult:
    """Lookup ASN per IP tramite ipinfo.io (free, no API key)."""
    r = ReputationResult(source="ASN Lookup", entity=ip, entity_type="ip", queried=True)
    try:
        resp = _http_get_with_retry(
            f"https://ipinfo.io/{ip}/json",
            headers={"User-Agent": f"EMLyzer/{settings.VERSION} (email analysis tool)"},
            timeout=REQUEST_TIMEOUT_ASN,
            rate_key="asnlookup",
            max_retries=1,
        )
        resp.raise_for_status()
        data = resp.json()
        org  = data.get("org", "")       # es. "AS16509 Amazon.com, Inc."
        city = data.get("city", "")
        country = data.get("country", "")
        hostname = data.get("hostname", "")
        parts = []
        if org:
            parts.append(org)
        if city and country:
            parts.append(f"{city}, {country}")
        elif country:
            parts.append(country)
        if hostname:
            parts.append(f"hostname: {hostname}")
        r.detail = " | ".join(parts) if parts else "Nessun dato ASN"
    except Exception as e:
        r.error = f"Errore lookup ASN: {e}"
    return r


# ---------------------------------------------------------------------------
# crt.sh — certificati TLS per dominio (gratuito, no API key)
# ---------------------------------------------------------------------------

def check_domain_crtsh(domain: str) -> ReputationResult:
    """
    Cerca certificati TLS emessi per il dominio su crt.sh.
    Utile per capire l'età reale del sito e i suoi sottodomini.
    502/503/504 sono errori temporanei di crt.sh — non vengono mostrati come errori bloccanti.
    """
    r = ReputationResult(source="crt.sh", entity=domain, entity_type="url", queried=True)

    try:
        # _http_get_with_retry gestisce 429 (con Retry-After), 502/503/504 (retry 2x)
        # rate_key="crtsh" garantisce max 1 req/2.5s tra chiamate concorrenti
        resp = _http_get_with_retry(
            "https://crt.sh/",
            params={"q": domain, "output": "json"},
            headers={"User-Agent": f"EMLyzer/{settings.VERSION} (email analysis tool)"},
            timeout=REQUEST_TIMEOUT_INFO,
            rate_key="crtsh",
            max_retries=2,
        )
        resp.raise_for_status()
        certs = resp.json()
        if not certs:
            r.detail = "Nessun certificato TLS trovato per questo dominio"
            return r

        # Ordina per data di emissione
        dates = [c.get("not_before", "") for c in certs if c.get("not_before")]
        dates.sort()

        total = len(certs)
        first = dates[0][:10] if dates else "?"
        last  = dates[-1][:10] if dates else "?"
        r.detail = f"{total} certificati — primo: {first}, ultimo: {last}"

        # Flag: dominio con pochissimi certificati e recente → sospetto
        if total <= 2 and dates and dates[-1] > "2024-01-01":
            r.confidence = 30.0
            r.detail += " ⚠ dominio molto recente"

    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        if code in (502, 503, 504):
            r.detail = "crt.sh temporaneamente non disponibile"
        elif code == 429:
            r.detail = "crt.sh: troppe richieste, riprova tra qualche minuto"
        else:
            r.error = f"crt.sh HTTP {code}"
    except requests.exceptions.Timeout:
        r.detail = "crt.sh: nessuna risposta nel tempo limite"
    except requests.exceptions.ConnectionError:
        r.detail = "crt.sh non raggiungibile"
    except Exception as e:
        r.error = f"crt.sh: {type(e).__name__}"
    return r


# ---------------------------------------------------------------------------
# CIRCL Passive DNS — storico risoluzione DNS per IP e domini (gratuito)
# ---------------------------------------------------------------------------

def check_ip_circl_pdns(ip: str) -> ReputationResult:
    """
    CIRCL Passive DNS — storico DNS per IP.
    Ritorna i domini che hanno storicamente risolto a questo IP.
    Informativo: non imposta is_malicious.
    Richiede CIRCL_API_KEY in formato "username:password" (registrazione gratuita su circl.lu/pdns).
    """
    api_key = settings.CIRCL_API_KEY.strip()
    if not api_key:
        return ReputationResult(
            source="CIRCL Passive DNS", entity=ip, entity_type="ip",
            skipped=True, skip_reason="CIRCL_API_KEY non configurata",
        )
    user, _, pwd = api_key.partition(":")
    try:
        resp = _http_get_with_retry(
            f"https://www.circl.lu/pdns/query/{ip}",
            headers={"Accept": "application/json",
                     "User-Agent": f"EMLyzer/{settings.VERSION} (email analysis tool)"},
            auth=(user, pwd),
            timeout=REQUEST_TIMEOUT_INFO,
            rate_key="circl",
            max_retries=1,
        )
        if resp.status_code == 404:
            return ReputationResult(
                source="CIRCL Passive DNS", entity=ip, entity_type="ip",
                queried=True, detail="Nessun record trovato.",
            )
        resp.raise_for_status()
        records = [json.loads(ln) for ln in resp.text.splitlines() if ln.strip()]
        if not records:
            return ReputationResult(
                source="CIRCL Passive DNS", entity=ip, entity_type="ip",
                queried=True, detail="Nessun record trovato.",
            )
        # Estrai domini unici (rrname) → questi hostname hanno puntato a questo IP
        domains = list(dict.fromkeys(
            r.get("rrname", "").rstrip(".") for r in records if r.get("rrname")
        ))
        time_last = max((r.get("time_last", "") for r in records), default="")
        time_last_str = time_last[:10] if time_last else "?"
        sample = ", ".join(domains[:5])
        extra = f" (+{len(domains) - 5} altri)" if len(domains) > 5 else ""
        detail = (
            f"{len(records)} record — domini: {sample}{extra}"
            f" | ultimo visto: {time_last_str}"
        )
        return ReputationResult(
            source="CIRCL Passive DNS", entity=ip, entity_type="ip",
            queried=True, detail=detail,
        )
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        if code == 401:
            return ReputationResult(
                source="CIRCL Passive DNS", entity=ip, entity_type="ip",
                error="Credenziali CIRCL non valide (CIRCL_API_KEY=user:password)",
            )
        return ReputationResult(
            source="CIRCL Passive DNS", entity=ip, entity_type="ip",
            error=f"CIRCL HTTP {code}",
        )
    except Exception as exc:
        return ReputationResult(
            source="CIRCL Passive DNS", entity=ip, entity_type="ip",
            error=f"CIRCL: {type(exc).__name__}",
        )


def check_domain_circl_pdns(domain: str) -> ReputationResult:
    """
    CIRCL Passive DNS — storico DNS per dominio.
    Ritorna gli IP a cui il dominio ha storicamente risolto e altri record DNS.
    Informativo: non imposta is_malicious.
    Richiede CIRCL_API_KEY in formato "username:password" (registrazione gratuita su circl.lu/pdns).
    """
    api_key = settings.CIRCL_API_KEY.strip()
    if not api_key:
        return ReputationResult(
            source="CIRCL Passive DNS", entity=domain, entity_type="url",
            skipped=True, skip_reason="CIRCL_API_KEY non configurata",
        )
    user, _, pwd = api_key.partition(":")
    try:
        resp = _http_get_with_retry(
            f"https://www.circl.lu/pdns/query/{domain}",
            headers={"Accept": "application/json",
                     "User-Agent": f"EMLyzer/{settings.VERSION} (email analysis tool)"},
            auth=(user, pwd),
            timeout=REQUEST_TIMEOUT_INFO,
            rate_key="circl",
            max_retries=1,
        )
        if resp.status_code == 404:
            return ReputationResult(
                source="CIRCL Passive DNS", entity=domain, entity_type="url",
                queried=True, detail="Nessun record trovato.",
            )
        resp.raise_for_status()
        records = [json.loads(ln) for ln in resp.text.splitlines() if ln.strip()]
        if not records:
            return ReputationResult(
                source="CIRCL Passive DNS", entity=domain, entity_type="url",
                queried=True, detail="Nessun record trovato.",
            )
        # Raggruppa per rrtype — mostra A/AAAA/MX/NS/CNAME
        by_type: dict[str, list[str]] = {}
        for r in records:
            rt  = r.get("rrtype", "?")
            rd  = r.get("rdata", "").rstrip(".")
            if rd:
                by_type.setdefault(rt, []).append(rd)
        parts = []
        for rt in ("A", "AAAA", "MX", "NS", "CNAME"):
            vals = list(dict.fromkeys(by_type.get(rt, [])))   # dedup con ordine
            if vals:
                sample = ", ".join(vals[:3])
                extra  = f" (+{len(vals) - 3})" if len(vals) > 3 else ""
                parts.append(f"{rt}: {sample}{extra}")
        time_last = max((r.get("time_last", "") for r in records), default="")
        time_last_str = time_last[:10] if time_last else "?"
        body = " | ".join(parts) if parts else f"{len(records)} record"
        detail = f"{body} | ultimo visto: {time_last_str}"
        return ReputationResult(
            source="CIRCL Passive DNS", entity=domain, entity_type="url",
            queried=True, detail=detail,
        )
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        if code == 401:
            return ReputationResult(
                source="CIRCL Passive DNS", entity=domain, entity_type="url",
                error="Credenziali CIRCL non valide (CIRCL_API_KEY=user:password)",
            )
        return ReputationResult(
            source="CIRCL Passive DNS", entity=domain, entity_type="url",
            error=f"CIRCL HTTP {code}",
        )
    except Exception as exc:
        return ReputationResult(
            source="CIRCL Passive DNS", entity=domain, entity_type="url",
            error=f"CIRCL: {type(exc).__name__}",
        )


# ---------------------------------------------------------------------------
# GreyNoise Community — classifica IP come scanner/malicious/benign
# ---------------------------------------------------------------------------

def check_ip_greynoise(ip: str) -> ReputationResult:
    """
    GreyNoise Community API — classifica un IP come malicious, benign o unknown.
    Distingue scanner innocui (noise=True) da attori malevoli, riducendo i falsi positivi.
    Richiede GREYNOISE_API_KEY (100 req/g free).
    """
    api_key = settings.GREYNOISE_API_KEY.strip()
    if not api_key:
        return ReputationResult(
            source="GreyNoise Community", entity=ip, entity_type="ip",
            skipped=True, skip_reason="GREYNOISE_API_KEY non configurata — registrati su greynoise.io",
        )
    try:
        resp = _http_get_with_retry(
            f"https://api.greynoise.io/v3/community/{ip}",
            headers={"key": api_key, "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
            rate_key="greynoise",
        )
        if resp.status_code == 404:
            return ReputationResult(
                source="GreyNoise Community", entity=ip, entity_type="ip",
                queried=True, detail="IP non presente nel database GreyNoise.",
            )
        if resp.status_code == 401:
            return ReputationResult(
                source="GreyNoise Community", entity=ip, entity_type="ip",
                error="API key non valida (GREYNOISE_API_KEY)",
            )
        resp.raise_for_status()
        data = resp.json()
        classification = data.get("classification", "unknown")
        noise = data.get("noise", False)
        riot = data.get("riot", False)
        name = data.get("name", "")
        last_seen = (data.get("last_seen") or "")[:10]

        malicious = classification == "malicious"
        if riot:
            detail = f"Servizio noto benigno: {name}" if name else "Servizio noto benigno"
        elif noise and classification == "benign":
            detail = f"Scanner benigno: {name}" if name else f"Scanner benigno ({classification})"
        elif malicious:
            detail = f"Malevolo — {name}" if name else "Classificato come malevolo"
            if last_seen:
                detail += f" | ultimo visto: {last_seen}"
        else:
            detail = f"Classificazione: {classification}"
            if noise:
                detail += " (attivo su internet)"
            if last_seen:
                detail += f" | ultimo visto: {last_seen}"

        return ReputationResult(
            source="GreyNoise Community", entity=ip, entity_type="ip",
            queried=True, is_malicious=malicious,
            confidence=90.0 if malicious else 0.0,
            detail=detail,
        )
    except requests.HTTPError as e:
        return ReputationResult(
            source="GreyNoise Community", entity=ip, entity_type="ip",
            error=f"GreyNoise HTTP {e.response.status_code if e.response is not None else '?'}",
        )
    except Exception as exc:
        return ReputationResult(
            source="GreyNoise Community", entity=ip, entity_type="ip",
            error=f"GreyNoise: {type(exc).__name__}",
        )


# ---------------------------------------------------------------------------
# URLScan.io — ricerca scansioni esistenti per dominio
# ---------------------------------------------------------------------------

def check_url_urlscan(url: str) -> ReputationResult:
    """
    URLScan.io — cerca scansioni esistenti per il dominio dell'URL.
    Restituisce il verdetto dell'ultima scansione disponibile.
    URLSCAN_API_KEY opzionale per search (ma aumenta il rate limit).
    """
    try:
        host = urllib.parse.urlparse(url).netloc.split(":")[0].lstrip("www.")
        if not host:
            return ReputationResult(
                source="URLScan.io", entity=url, entity_type="url",
                skipped=True, skip_reason="Impossibile estrarre il dominio dall'URL",
            )
        # Verifica che non sia un IP diretto (URLScan preferisce domini)
        try:
            ipaddress.ip_address(host)
            is_ip = True
        except ValueError:
            is_ip = False
    except Exception as exc:
        return ReputationResult(
            source="URLScan.io", entity=url, entity_type="url",
            error=f"URLScan parse: {type(exc).__name__}",
        )

    query = host if not is_ip else url
    headers: dict = {"Content-Type": "application/json"}
    if settings.URLSCAN_API_KEY:
        headers["API-Key"] = settings.URLSCAN_API_KEY.strip()

    try:
        resp = _http_get_with_retry(
            "https://urlscan.io/api/v1/search/",
            params={"q": f"page.domain:{query}", "size": "3", "sort": "date"},
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            rate_key="urlscan",
        )
        if resp.status_code == 401:
            return ReputationResult(
                source="URLScan.io", entity=url, entity_type="url",
                error="API key non valida (URLSCAN_API_KEY)",
            )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])

        if not results:
            return ReputationResult(
                source="URLScan.io", entity=url, entity_type="url",
                queried=True, detail=f"Nessuna scansione trovata per {query}.",
            )

        latest = results[0]
        verdict = latest.get("verdicts", {}).get("overall", {})
        malicious = bool(verdict.get("malicious", False))
        score = verdict.get("score", 0)
        tags = verdict.get("tags", [])
        scan_date = (latest.get("task", {}).get("time") or "")[:10]

        tag_str = ", ".join(tags[:3]) if tags else ""
        detail = f"{len(results)} scansion{'e' if len(results)==1 else 'i'} trovate"
        if scan_date:
            detail += f" | ultima: {scan_date}"
        if score:
            detail += f" | score: {score}"
        if tag_str:
            detail += f" | tag: {tag_str}"

        return ReputationResult(
            source="URLScan.io", entity=url, entity_type="url",
            queried=True, is_malicious=malicious,
            confidence=float(score) if malicious else 0.0,
            detail=detail,
        )
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        return ReputationResult(
            source="URLScan.io", entity=url, entity_type="url",
            error=f"URLScan HTTP {code}",
        )
    except Exception as exc:
        return ReputationResult(
            source="URLScan.io", entity=url, entity_type="url",
            error=f"URLScan: {type(exc).__name__}",
        )


# ---------------------------------------------------------------------------
# Pulsedive — threat intel aggregata per IP e URL
# ---------------------------------------------------------------------------

def _check_pulsedive(entity: str, entity_type: str) -> ReputationResult:
    """Helper comune per IP e URL su Pulsedive."""
    api_key = settings.PULSEDIVE_API_KEY.strip()
    if not api_key:
        return ReputationResult(
            source="Pulsedive", entity=entity, entity_type=entity_type,
            skipped=True, skip_reason="PULSEDIVE_API_KEY non configurata — registrati su pulsedive.com",
        )
    try:
        resp = _http_get_with_retry(
            "https://pulsedive.com/api/info.php",
            params={"indicator": entity, "pretty": "1", "key": api_key},
            timeout=REQUEST_TIMEOUT,
            rate_key="pulsedive",
        )
        if resp.status_code == 404:
            return ReputationResult(
                source="Pulsedive", entity=entity, entity_type=entity_type,
                queried=True, detail="Indicatore non presente nel database Pulsedive.",
            )
        if resp.status_code == 400:
            data = resp.json() if resp.content else {}
            msg = data.get("error", "Indicatore non riconosciuto")
            return ReputationResult(
                source="Pulsedive", entity=entity, entity_type=entity_type,
                queried=True, detail=f"Pulsedive: {msg}",
            )
        resp.raise_for_status()
        data = resp.json()
        risk = data.get("risk", "unknown").lower()
        risk_factors = data.get("risk_factors", [])

        malicious = risk in ("high", "critical")
        confidence_map = {"critical": 95.0, "high": 80.0, "medium": 50.0, "low": 20.0}
        confidence = confidence_map.get(risk, 0.0)

        factors_str = ", ".join(f["name"] for f in risk_factors[:3]) if risk_factors else ""
        detail = f"Risk: {risk}"
        if factors_str:
            detail += f" | {factors_str}"

        return ReputationResult(
            source="Pulsedive", entity=entity, entity_type=entity_type,
            queried=True, is_malicious=malicious, confidence=confidence,
            detail=detail,
        )
    except requests.HTTPError as e:
        return ReputationResult(
            source="Pulsedive", entity=entity, entity_type=entity_type,
            error=f"Pulsedive HTTP {e.response.status_code if e.response is not None else '?'}",
        )
    except Exception as exc:
        return ReputationResult(
            source="Pulsedive", entity=entity, entity_type=entity_type,
            error=f"Pulsedive: {type(exc).__name__}",
        )


def check_ip_pulsedive(ip: str) -> ReputationResult:
    """Pulsedive threat intel per IP."""
    return _check_pulsedive(ip, "ip")


def check_url_pulsedive(url: str) -> ReputationResult:
    """Pulsedive threat intel per URL."""
    return _check_pulsedive(url, "url")


# ---------------------------------------------------------------------------
# Criminal IP — score rischio IP con geolocalizzazione
# ---------------------------------------------------------------------------

def check_ip_criminalip(ip: str) -> ReputationResult:
    """
    Criminal IP — score di rischio IP 0-5.
    0=Safe, 1=Low, 2=Medium, 3=High, 4=Critical.
    Richiede CRIMINALIP_API_KEY (free tier disponibile).
    """
    api_key = settings.CRIMINALIP_API_KEY.strip()
    if not api_key:
        return ReputationResult(
            source="Criminal IP", entity=ip, entity_type="ip",
            skipped=True, skip_reason="CRIMINALIP_API_KEY non configurata — registrati su criminalip.io",
        )
    try:
        resp = _http_get_with_retry(
            "https://api.criminalip.io/v1/ip/summary",
            params={"ip": ip},
            headers={"x-api-key": api_key},
            timeout=REQUEST_TIMEOUT,
            rate_key="criminalip",
        )
        if resp.status_code == 401:
            return ReputationResult(
                source="Criminal IP", entity=ip, entity_type="ip",
                error="API key non valida (CRIMINALIP_API_KEY)",
            )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", 0)
        if status != 200:
            msg = data.get("message", f"status {status}")
            return ReputationResult(
                source="Criminal IP", entity=ip, entity_type="ip",
                queried=True, detail=f"Criminal IP: {msg}",
            )

        score_data = data.get("data", {}).get("score", {})
        inbound = score_data.get("inbound", 0)
        outbound = score_data.get("outbound", 0)
        max_score = max(inbound, outbound)

        score_labels = {0: "Safe", 1: "Low", 2: "Medium", 3: "High", 4: "Critical"}
        label = score_labels.get(max_score, f"Score {max_score}")
        malicious = max_score >= 3
        confidence = {3: 70.0, 4: 90.0}.get(max_score, 0.0)

        country = data.get("data", {}).get("country", "")
        detail = f"Score: {label} ({max_score}/4)"
        if country:
            detail += f" | paese: {country}"

        return ReputationResult(
            source="Criminal IP", entity=ip, entity_type="ip",
            queried=True, is_malicious=malicious, confidence=confidence,
            detail=detail,
        )
    except requests.HTTPError as e:
        return ReputationResult(
            source="Criminal IP", entity=ip, entity_type="ip",
            error=f"Criminal IP HTTP {e.response.status_code if e.response is not None else '?'}",
        )
    except Exception as exc:
        return ReputationResult(
            source="Criminal IP", entity=ip, entity_type="ip",
            error=f"Criminal IP: {type(exc).__name__}",
        )


# ---------------------------------------------------------------------------
# SecurityTrails — DNS attuale e storico per domini (informativo)
# ---------------------------------------------------------------------------

def check_domain_securitytrails(domain: str) -> ReputationResult:
    """
    SecurityTrails — DNS attuale e storico per dominio.
    Servizio informativo: non emette giudizi malevolo/pulito.
    Richiede SECURITYTRAILS_API_KEY (50 req/mese free).
    """
    api_key = settings.SECURITYTRAILS_API_KEY.strip()
    if not api_key:
        return ReputationResult(
            source="SecurityTrails", entity=domain, entity_type="url",
            skipped=True, skip_reason="SECURITYTRAILS_API_KEY non configurata — registrati su securitytrails.com",
        )
    try:
        resp = _http_get_with_retry(
            f"https://api.securitytrails.com/v1/domain/{domain}/dns",
            headers={"APIKEY": api_key, "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_INFO,
            rate_key="securitytrails",
        )
        if resp.status_code == 401:
            return ReputationResult(
                source="SecurityTrails", entity=domain, entity_type="url",
                error="API key non valida (SECURITYTRAILS_API_KEY)",
            )
        if resp.status_code == 404:
            return ReputationResult(
                source="SecurityTrails", entity=domain, entity_type="url",
                queried=True, detail="Dominio non trovato in SecurityTrails.",
            )
        resp.raise_for_status()
        data = resp.json()
        current = data.get("current_dns", {})

        parts = []
        a_vals = [r.get("ip", "") for r in current.get("a", {}).get("values", []) if r.get("ip")]
        if a_vals:
            parts.append(f"A: {', '.join(a_vals[:3])}" + (f" (+{len(a_vals)-3})" if len(a_vals) > 3 else ""))
        mx_vals = [r.get("hostname", "") for r in current.get("mx", {}).get("values", []) if r.get("hostname")]
        if mx_vals:
            parts.append(f"MX: {', '.join(mx_vals[:2])}" + (f" (+{len(mx_vals)-2})" if len(mx_vals) > 2 else ""))
        ns_vals = [r.get("nameserver", "") for r in current.get("ns", {}).get("values", []) if r.get("nameserver")]
        if ns_vals:
            parts.append(f"NS: {', '.join(ns_vals[:2])}" + (f" (+{len(ns_vals)-2})" if len(ns_vals) > 2 else ""))

        detail = " | ".join(parts) if parts else "Nessun record DNS trovato"

        return ReputationResult(
            source="SecurityTrails", entity=domain, entity_type="url",
            queried=True, detail=detail,
        )
    except requests.HTTPError as e:
        return ReputationResult(
            source="SecurityTrails", entity=domain, entity_type="url",
            error=f"SecurityTrails HTTP {e.response.status_code if e.response is not None else '?'}",
        )
    except Exception as exc:
        return ReputationResult(
            source="SecurityTrails", entity=domain, entity_type="url",
            error=f"SecurityTrails: {type(exc).__name__}",
        )


# ---------------------------------------------------------------------------
# Hybrid Analysis — analisi statica hash allegati
# ---------------------------------------------------------------------------

def check_hash_hybrid_analysis(sha256: str) -> ReputationResult:
    """
    Hybrid Analysis (CrowdStrike Falcon) — ricerca hash nel database sandbox.
    threat_level: 0=no threat, 1=suspicious, 2=malicious.
    Richiede HYBRID_ANALYSIS_API_KEY (gratuito con registrazione).
    """
    api_key = settings.HYBRID_ANALYSIS_API_KEY.strip()
    if not api_key:
        return ReputationResult(
            source="Hybrid Analysis", entity=sha256, entity_type="hash",
            skipped=True, skip_reason="HYBRID_ANALYSIS_API_KEY non configurata — registrati su hybrid-analysis.com",
        )
    try:
        resp = _http_post_with_retry(
            "https://www.hybrid-analysis.com/api/v2/search/hash",
            data={"hash": sha256},
            headers={
                "api-key": api_key,
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": f"EMLyzer/{settings.VERSION}",
            },
            timeout=REQUEST_TIMEOUT,
            rate_key="hybridanalysis",
        )
        if resp.status_code == 401:
            return ReputationResult(
                source="Hybrid Analysis", entity=sha256, entity_type="hash",
                error="API key non valida (HYBRID_ANALYSIS_API_KEY)",
            )
        resp.raise_for_status()
        results = resp.json()

        if not results:
            return ReputationResult(
                source="Hybrid Analysis", entity=sha256, entity_type="hash",
                queried=True, detail="Hash non trovato nel database Hybrid Analysis.",
            )

        # Prendi il risultato con il threat_level più alto
        best = max(results, key=lambda r: r.get("threat_level", 0))
        threat_level = best.get("threat_level", 0)
        verdict = best.get("verdict", "no specific threat")
        tags = best.get("tags") or []
        threat_score = best.get("threat_score")
        file_type = best.get("type", "")

        malicious = threat_level >= 2

        detail = f"Verdict: {verdict}"
        if file_type:
            detail += f" | tipo: {file_type}"
        if threat_score is not None:
            detail += f" | score: {threat_score}/100"
        if tags:
            detail += f" | tag: {', '.join(str(t) for t in tags[:3])}"
        if len(results) > 1:
            detail += f" | {len(results)} campioni trovati"

        return ReputationResult(
            source="Hybrid Analysis", entity=sha256, entity_type="hash",
            queried=True, is_malicious=malicious,
            confidence=float(threat_score) if (malicious and threat_score is not None) else (80.0 if malicious else 0.0),
            detail=detail,
        )
    except requests.HTTPError as e:
        return ReputationResult(
            source="Hybrid Analysis", entity=sha256, entity_type="hash",
            error=f"Hybrid Analysis HTTP {e.response.status_code if e.response is not None else '?'}",
        )
    except Exception as exc:
        return ReputationResult(
            source="Hybrid Analysis", entity=sha256, entity_type="hash",
            error=f"Hybrid Analysis: {type(exc).__name__}",
        )


# ---------------------------------------------------------------------------
# Redirect chain — segue i redirect degli URL shortener
# ---------------------------------------------------------------------------

def check_url_redirect_chain(url: str) -> ReputationResult:
    """
    Segue la catena di redirect di un URL e riporta la destinazione finale.
    Utile per URL shortener (bit.ly, t.co, ecc.) che nascondono la destinazione.
    """
    r = ReputationResult(source="Redirect Chain", entity=url, entity_type="url", queried=True)
    try:
        _rate_limit("redirectchain")
        resp = requests.get(
            url,
            headers={
                "User-Agent": f"Mozilla/5.0 (compatible; EMLyzer/{settings.VERSION})",
                "Accept": "text/html,application/xhtml+xml,*/*",
            },
            allow_redirects=True,
            timeout=REQUEST_TIMEOUT_INFO,
            stream=True,   # non scarica il body
        )
        resp.close()

        chain = [str(r.url) for r in resp.history] + [str(resp.url)]
        final = str(resp.url)

        if len(chain) <= 1:
            r.detail = f"Nessun redirect — URL finale: {final}"
        else:
            hops = " → ".join(chain)
            r.detail = f"{len(chain)-1} redirect: {hops[:300]}"
            # Se la destinazione finale è diversa dall'originale, segnala
            if final != url:
                r.confidence = 50.0  # neutro ma merita attenzione
    except requests.exceptions.SSLError as e:
        r.error = f"Errore SSL: {e}"
    except requests.exceptions.ConnectionError as e:
        r.error = f"Connessione fallita: {e}"
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


# ---------------------------------------------------------------------------
# Shodan InternetDB — porte aperte, CVE e tag per IP (gratuito, no API key)
# ---------------------------------------------------------------------------

_SHODAN_MALICIOUS_TAGS = frozenset({"malware", "c2", "compromised", "botnet"})

def check_ip_shodan_internetdb(ip: str) -> ReputationResult:
    """
    Interroga Shodan InternetDB per l'IP: porte aperte, CVE, tag e hostname.
    Servizio informativo — segnala come malevolo solo se i tag indicano attività ostile.
    """
    r = ReputationResult(source="Shodan InternetDB", entity=ip, entity_type="ip", queried=True)
    try:
        resp = _http_get_with_retry(
            f"https://internetdb.shodan.io/{ip}",
            headers={"User-Agent": f"EMLyzer/{settings.VERSION} (email analysis tool)"},
            timeout=REQUEST_TIMEOUT_INFO,
            rate_key="shodaninternetdb",
            max_retries=1,
        )
        if resp.status_code == 404:
            r.detail = "IP non trovato in Shodan InternetDB"
            return r
        resp.raise_for_status()
        data = resp.json()

        ports     = data.get("ports", []) or []
        vulns     = data.get("vulns", []) or []
        tags      = data.get("tags",  []) or []
        hostnames = data.get("hostnames", []) or []

        mal_tags = [t for t in tags if t.lower() in _SHODAN_MALICIOUS_TAGS]
        if mal_tags:
            r.is_malicious = True
            r.confidence = 80.0
        elif vulns:
            r.confidence = 30.0  # segnale di attenzione, non conferma di malizia

        parts = []
        if ports:
            parts.append(f"Porte: {', '.join(str(p) for p in ports[:10])}")
        if vulns:
            parts.append(f"CVE: {', '.join(list(vulns)[:5])}")
        if tags:
            parts.append(f"Tags: {', '.join(tags[:5])}")
        if hostnames:
            parts.append(f"Hostnames: {', '.join(hostnames[:3])}")
        r.detail = " | ".join(parts) if parts else "Nessun dato trovato"

    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        if code == 404:
            r.detail = "IP non trovato in Shodan InternetDB"
        else:
            r.error = f"HTTP {code}"
    except requests.exceptions.Timeout:
        r.error = "Timeout Shodan InternetDB"
    except requests.exceptions.ConnectionError:
        r.error = "Shodan InternetDB non raggiungibile"
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


# ---------------------------------------------------------------------------
# Abuse.ch URLhaus — database URL malware (richiede Auth-Key da auth.abuse.ch)
# ---------------------------------------------------------------------------

def check_url_urlhaus(url: str) -> ReputationResult:
    """Controlla se l'URL è nel database URLhaus di abuse.ch."""
    r = ReputationResult(source="URLhaus", entity=url, entity_type="url")
    _abusech_key = settings.ABUSECH_API_KEY
    if not _abusech_key:
        r.skipped = True
        r.skip_reason = "ABUSECH_API_KEY non configurata — registrati gratuitamente su auth.abuse.ch"
        return r
    r.queried = True
    try:
        resp = _http_post_with_retry(
            "https://urlhaus-api.abuse.ch/v1/url/",
            data={"url": url},
            headers={
                "User-Agent": f"EMLyzer/{settings.VERSION} (email analysis tool)",
                "Auth-Key": _abusech_key,
            },
            timeout=REQUEST_TIMEOUT,
            rate_key="urlhaus",
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("query_status", "")

        if status == "no_results":
            r.detail = "URL non trovato in URLhaus"
            return r

        if status == "ok":
            url_status = data.get("url_status", "")
            threat     = data.get("threat", "")
            tags       = data.get("tags", []) or []

            r.is_malicious = url_status in ("online", "unknown") or bool(threat)
            if url_status == "online":
                r.confidence = 95.0
            elif threat:
                r.confidence = 70.0
            elif r.is_malicious:
                r.confidence = 50.0

            parts = []
            if url_status:
                parts.append(f"Stato: {url_status}")
            if threat:
                parts.append(f"Minaccia: {threat}")
            if tags:
                parts.append(f"Tags: {', '.join(tags[:5])}")
            r.detail = " | ".join(parts) if parts else "Trovato in URLhaus"
        else:
            r.detail = f"Status: {status}"

    except requests.RequestException as e:
        r.error = f"Errore di rete: {e}"
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


# ---------------------------------------------------------------------------
# ThreatFox (abuse.ch) — database IOC: IP, URL e hash (richiede Auth-Key da auth.abuse.ch)
# ---------------------------------------------------------------------------

def _query_threatfox(ioc: str) -> dict:
    """Chiamata generica a ThreatFox per un singolo IOC."""
    resp = _http_post_with_retry(
        "https://threatfox-api.abuse.ch/api/v1/",
        json_data={"query": "search_ioc", "search_term": ioc},
        headers={
            "User-Agent":   f"EMLyzer/{settings.VERSION} (email analysis tool)",
            "Content-Type": "application/json",
            "Auth-Key":     settings.ABUSECH_API_KEY,
        },
        timeout=REQUEST_TIMEOUT,
        rate_key="threatfox",
    )
    resp.raise_for_status()
    return resp.json()


def _parse_threatfox_result(r: ReputationResult, data: dict) -> ReputationResult:
    """Interpreta la risposta ThreatFox e popola il ReputationResult."""
    status = data.get("query_status", "")
    # "no_results" / "no_result" → IOC non presente nel DB
    # "illegal_search_term" → formato IOC non riconosciuto (es. URL non standard):
    #   non è un errore applicativo, equivale a "non trovato"
    if status in ("no_results", "no_result", "illegal_search_term", ""):
        r.detail = "IOC non trovato in ThreatFox"
        return r
    if status == "ok":
        iocs = data.get("data") or []
        if not iocs:
            r.detail = "IOC non trovato in ThreatFox"
            return r
        r.is_malicious = True
        best = iocs[0]
        r.confidence = float(best.get("confidence_level", 50))
        malware      = best.get("malware", "")
        threat_type  = best.get("threat_type", "")
        ioc_type     = best.get("ioc_type", "")
        parts = []
        if malware:
            parts.append(f"Malware: {malware}")
        if threat_type:
            parts.append(f"Tipo: {threat_type}")
        if len(iocs) > 1:
            parts.append(f"{len(iocs)} occorrenze")
        r.detail = " | ".join(parts) if parts else f"Trovato in ThreatFox ({ioc_type})"
    else:
        r.detail = f"Status: {status}"
    return r


def _threatfox_skip(entity: str, entity_type: str) -> ReputationResult:
    """Helper: risultato skip uniforme per tutti i wrapper ThreatFox."""
    r = ReputationResult(source="ThreatFox", entity=entity, entity_type=entity_type)
    r.skipped = True
    r.skip_reason = "ABUSECH_API_KEY non configurata — registrati gratuitamente su auth.abuse.ch"
    return r


def check_ip_threatfox(ip: str) -> ReputationResult:
    """Controlla se l'IP è presente nel database ThreatFox."""
    if not settings.ABUSECH_API_KEY:
        return _threatfox_skip(ip, "ip")
    r = ReputationResult(source="ThreatFox", entity=ip, entity_type="ip", queried=True)
    try:
        _parse_threatfox_result(r, _query_threatfox(ip))
    except requests.RequestException as e:
        r.error = f"Errore di rete: {e}"
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


def check_url_threatfox(url: str) -> ReputationResult:
    """Controlla se l'URL è presente nel database ThreatFox."""
    if not settings.ABUSECH_API_KEY:
        return _threatfox_skip(url, "url")
    r = ReputationResult(source="ThreatFox", entity=url, entity_type="url", queried=True)
    try:
        _parse_threatfox_result(r, _query_threatfox(url))
    except requests.RequestException as e:
        r.error = f"Errore di rete: {e}"
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


def check_hash_threatfox(sha256: str) -> ReputationResult:
    """Controlla se l'hash SHA256 è presente nel database ThreatFox."""
    if not settings.ABUSECH_API_KEY:
        return _threatfox_skip(sha256, "hash")
    r = ReputationResult(source="ThreatFox", entity=sha256, entity_type="hash", queried=True)
    try:
        _parse_threatfox_result(r, _query_threatfox(sha256))
    except requests.RequestException as e:
        r.error = f"Errore di rete: {e}"
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


URL_SHORTENERS = {
    "bit.ly", "t.co", "tinyurl.com", "goo.gl", "ow.ly",
    "short.link", "buff.ly", "dlvr.it", "ift.tt", "su.pr",
    "tiny.cc", "is.gd", "cli.gs", "pic.gd", "bc.vc",
}


# ---------------------------------------------------------------------------
# Registro servizi — stato per la UI
# ---------------------------------------------------------------------------

_SERVICE_DEFS = [
    # IP
    ("AbuseIPDB",         "ip",          True,  "Reputazione IP (Received header, X-Originating-IP, IP negli URL)"),
    ("VirusTotal",        "ip+url+hash", True,  "Analisi multi-engine IP, URL e hash (piano free: 4 req/min)"),
    ("Spamhaus DROP",     "ip",          False, "Blocklist IP malevoli di alto profilo — no API key richiesta"),
    ("ASN Lookup",        "ip",          False, "Autonomous System Number per ogni IP — no API key (ipinfo.io)"),
    ("Shodan InternetDB", "ip",          False, "Porte aperte, CVE e tag per ogni IP — no API key (Shodan)"),
    ("CIRCL Passive DNS", "ip+url",      True,  "Storico risoluzione DNS per IP e domini — gratuito con registrazione (circl.lu/pdns)"),
    ("GreyNoise Community","ip",         True,  "Classifica IP come scanner/malicious/benign — 100 req/g free (greynoise.io)"),
    ("Criminal IP",       "ip",          True,  "Score rischio IP 0-4 con geolocalizzazione — free tier (criminalip.io)"),
    # URL
    ("OpenPhish",         "url",         False, "Feed URL phishing — no API key richiesta"),
    ("PhishTank",         "url",         True,  "Database URL phishing verificati dalla community"),
    ("Redirect Chain",    "url",         False, "Segue i redirect degli URL shortener — no API key"),
    ("crt.sh",            "url",         False, "Certificati TLS emessi per il dominio — no API key"),
    ("URLhaus",           "url",         True,  "Database URL malware di abuse.ch (ABUSECH_API_KEY — auth.abuse.ch)"),
    ("URLScan.io",        "url",         False, "Ricerca scansioni esistenti per URL/domini — URLSCAN_API_KEY opzionale (urlscan.io)"),
    ("SecurityTrails",    "url",         True,  "DNS attuale e storico per domini — 50 req/mese free (securitytrails.com)"),
    # Hash
    ("MalwareBazaar",     "hash",        True,  "Hash allegati nel database malware (ABUSECH_API_KEY o MALWAREBAZAAR_API_KEY)"),
    ("Hybrid Analysis",   "hash",        True,  "Analisi statica allegati nel database sandbox Falcon — gratuito con registrazione (hybrid-analysis.com)"),
    # Multi-tipo
    ("ThreatFox",         "ip+url+hash", True,  "Database IOC abuse.ch (IP, URL, hash) — ABUSECH_API_KEY — auth.abuse.ch"),
    ("Pulsedive",         "ip+url",      True,  "Threat intel aggregata per IP e URL — 30 req/min free (pulsedive.com)"),
]

def _build_service_registry(all_results: list[ReputationResult]) -> list[dict]:
    by_source: dict[str, list[ReputationResult]] = {}
    for r in all_results:
        by_source.setdefault(r.source, []).append(r)

    key_map = {
        "AbuseIPDB":         bool(settings.ABUSEIPDB_API_KEY),
        "VirusTotal":        bool(settings.VIRUSTOTAL_API_KEY),
        "Spamhaus DROP":     True,
        "ASN Lookup":        True,
        "Shodan InternetDB": True,
        "OpenPhish":         True,
        "PhishTank":         bool(settings.PHISHTANK_API_KEY),
        "Redirect Chain":    True,
        "crt.sh":            True,
        "URLhaus":           bool(settings.ABUSECH_API_KEY),
        "MalwareBazaar":     bool(settings.ABUSECH_API_KEY or settings.MALWAREBAZAAR_API_KEY),
        "ThreatFox":         bool(settings.ABUSECH_API_KEY),
        "CIRCL Passive DNS":   bool(settings.CIRCL_API_KEY),
        "GreyNoise Community": bool(settings.GREYNOISE_API_KEY),
        "URLScan.io":          True,   # search è pubblico anche senza chiave
        "Pulsedive":           bool(settings.PULSEDIVE_API_KEY),
        "Criminal IP":         bool(settings.CRIMINALIP_API_KEY),
        "SecurityTrails":      bool(settings.SECURITYTRAILS_API_KEY),
        "Hybrid Analysis":     bool(settings.HYBRID_ANALYSIS_API_KEY),
    }

    registry = []
    for name, entity_type, requires_key, description in _SERVICE_DEFS:
        enabled = key_map.get(name, False)
        results = by_source.get(name, [])
        queried  = sum(1 for r in results if r.queried)
        malicious = sum(1 for r in results if r.is_malicious)
        errors   = [r.error for r in results if r.error]

        if not enabled:
            # Servizio non configurato (manca API key)
            state = "skipped"
            skip_msgs = [r.skip_reason for r in results if r.skip_reason]
            state_detail = skip_msgs[0] if skip_msgs else (
                f"Aggiungi la chiave API nel file .env" if requires_key else "Servizio disabilitato"
            )
        elif errors:
            state = "error"
            state_detail = errors[0]
        elif malicious > 0:
            state = "malicious"
            state_detail = f"{malicious} indicatori malevoli su {queried} entità analizzate"
        elif queried > 0:
            state = "clean"
            state_detail = f"{queried} {'entità analizzata' if queried == 1 else 'entità analizzate'} — nessun indicatore malevolo"
        elif any("in elaborazione" in (r.skip_reason or "") for r in results):
            # Servizio SLOW in elaborazione background — placeholder temporaneo
            state = "pending"
            state_detail = "In elaborazione — i risultati saranno disponibili a breve"
        else:
            # Servizio attivo ma non pertinente per questa email
            # (es. nessun URL → OpenPhish non chiamato; nessun allegato → MalwareBazaar non chiamato)
            state = "not_applicable"
            # Messaggio specifico per servizio
            if name == "Redirect Chain":
                state_detail = "Attivo — nessun URL shortener o HTTP nel corpo"
            elif name == "crt.sh":
                state_detail = "Attivo — in elaborazione (background)"
            else:
                # Servizio attivo e configurato ma nessuna entità da questa email
                entity_desc = {
                    "ip":           "nessun IP pubblico in questa email",
                    "url":          "nessun URL sospetto in questa email",
                    "hash":         "nessun allegato in questa email",
                    "ip+url+hash":  "nessuna entità da analizzare",
                }.get(entity_type, "nessuna entità pertinente")
                state_detail = f"Attivo — {entity_desc}"

        # Raccoglie i risultati non-skipped per mostrare dettaglio in UI
        detail_results = [
            {
                "entity": r.entity,
                "entity_type": r.entity_type,
                "is_malicious": r.is_malicious,
                "confidence": r.confidence,
                "detail": r.detail,
                "error": r.error,
            }
            for r in results if r.queried
        ]

        registry.append({
            "name": name,
            "entity_type": entity_type,
            "enabled": enabled,
            "requires_key": requires_key,
            "description": description,
            "state": state,
            "state_detail": state_detail,
            "queried_count": queried,
            "malicious_count": malicious,
            "detail_results": detail_results,
        })

    return registry


# ---------------------------------------------------------------------------
# Aggregator principale
# ---------------------------------------------------------------------------

@dataclass
class ReputationSummary:
    ip_results:       list[ReputationResult] = field(default_factory=list)
    url_results:      list[ReputationResult] = field(default_factory=list)
    hash_results:     list[ReputationResult] = field(default_factory=list)
    service_registry: list[dict]             = field(default_factory=list)
    malicious_count:  int   = 0
    reputation_score: float = 0.0


# ---------------------------------------------------------------------------
# Classificazione servizi per velocità
# ---------------------------------------------------------------------------
# FAST: nessun rate limit stringente, risposta garantita in < 15s
# SLOW: rate limit che renderebbe il frontend in timeout (VT=15.5s/req, IPDB=1.1s/req)
#       → eseguiti in background, il frontend fa polling

_FAST_SERVICES = frozenset({
    # Feed locali e chiamate HTTP singole leggere — completano in < 5s
    # indipendentemente dal numero di entità
    "check_ip_spamhaus",           # feed locale, 0s
    "check_ip_asn",                # 1 HTTP, 0.3s rate
    "check_ip_shodan_internetdb",  # 1 HTTP, 0.3s rate — InternetDB gratuito
    "check_ip_circl_pdns",         # 1 HTTP, 0.5s rate — CIRCL Passive DNS
    "check_ip_greynoise",          # 1 HTTP, 1.1s rate — GreyNoise Community
    "check_ip_pulsedive",          # 1 HTTP, 2.5s rate — Pulsedive
    "check_ip_criminalip",         # 1 HTTP, 1.1s rate — Criminal IP
    "check_ip_threatfox",          # 1 HTTP, 0.3s rate
    "check_url_openphish",         # feed locale, 0s
    "check_url_redirect_chain",    # 1 HTTP per URL, 0.2s rate
    "check_url_phishtank",         # 1 HTTP, 0.5s rate
    "check_url_urlhaus",           # 1 HTTP, 0.3s rate
    "check_url_threatfox",         # 1 HTTP, 0.3s rate
    "check_domain_circl_pdns",     # 1 HTTP, 0.5s rate — CIRCL Passive DNS
    "check_url_urlscan",           # 1 HTTP, 1.0s rate — URLScan.io
    "check_url_pulsedive",         # 1 HTTP, 2.5s rate — Pulsedive
    "check_domain_securitytrails", # 1 HTTP, 3.0s rate — SecurityTrails
    "check_hash_malwarebazaar",    # 1 HTTP, 0.7s rate
    "check_hash_threatfox",        # 1 HTTP, 0.3s rate
    "check_hash_hybrid_analysis",  # 1 HTTP, 1.0s rate — Hybrid Analysis
})

_SLOW_SERVICES = frozenset({
    # Servizi con rate limit stringente o timeout alto per molte entità
    # → eseguiti in background dopo la risposta al browser
    "check_ip_abuseipdb",   # 1.1s rate
    "check_ip_virustotal",  # 15.5s rate
    "check_url_virustotal", # 15.5s rate
    "check_hash_virustotal",# 15.5s rate
    "check_domain_crtsh",   # 2.5s rate × N domini = troppo per risposta sincrona
})

# Mappa fn.__name__ → nome servizio corretto per _build_service_registry
# IMPORTANTE: senza questa mappa i placeholder "in elaborazione" usano nomi sbagliati
# (es. "check_ip_abuseipdb" → "Ip Abuseipdb" invece di "AbuseIPDB")
_FN_TO_SOURCE: dict[str, str] = {
    "check_ip_abuseipdb":    "AbuseIPDB",
    "check_ip_virustotal":   "VirusTotal",
    "check_url_virustotal":  "VirusTotal",
    "check_hash_virustotal": "VirusTotal",
    "check_hash_virustotal": "VirusTotal",
    "check_domain_crtsh":    "crt.sh",
}


def _build_flat_tasks(

    ips: list[str], urls: list[str], hashes: list[str]
) -> tuple[list[tuple], list[ReputationResult]]:
    """
    Costruisce la lista piatta di tutti i task da eseguire e le risposte immediate (skip).
    Ritorna (call_tasks, skip_results) dove:
      call_tasks = [(fn, entity, kind), ...]  — da eseguire in parallelo
      skip_results = [ReputationResult, ...]  — skipped perché manca API key
    """
    call_tasks: list[tuple] = []
    skip_results: list[ReputationResult] = []

    def _c(fn, entity, kind):
        call_tasks.append((fn, entity, kind))

    def _s(source, entity, kind, reason):
        skip_results.append(ReputationResult(
            source=source, entity=entity, entity_type=kind,
            skipped=True, skip_reason=reason,
        ))

    # ── IP ──────────────────────────────────────────────────────────────────
    for ip in ips[:15]:
        if settings.ABUSEIPDB_API_KEY:
            _c(check_ip_abuseipdb,  ip, "ip")
        else:
            _s("AbuseIPDB",  ip, "ip", "ABUSEIPDB_API_KEY non configurata")
        if settings.VIRUSTOTAL_API_KEY:
            _c(check_ip_virustotal, ip, "ip")
        else:
            _s("VirusTotal", ip, "ip", "VIRUSTOTAL_API_KEY non configurata")
        _c(check_ip_spamhaus,          ip, "ip")
        _c(check_ip_asn,               ip, "ip")
        _c(check_ip_shodan_internetdb, ip, "ip")
        if settings.CIRCL_API_KEY:
            _c(check_ip_circl_pdns,    ip, "ip")
        else:
            _s("CIRCL Passive DNS", ip, "ip", "CIRCL_API_KEY non configurata — registrati su circl.lu/pdns")
        if settings.GREYNOISE_API_KEY:
            _c(check_ip_greynoise, ip, "ip")
        else:
            _s("GreyNoise Community", ip, "ip", "GREYNOISE_API_KEY non configurata — registrati su greynoise.io")
        if settings.PULSEDIVE_API_KEY:
            _c(check_ip_pulsedive, ip, "ip")
        else:
            _s("Pulsedive", ip, "ip", "PULSEDIVE_API_KEY non configurata — registrati su pulsedive.com")
        if settings.CRIMINALIP_API_KEY:
            _c(check_ip_criminalip, ip, "ip")
        else:
            _s("Criminal IP", ip, "ip", "CRIMINALIP_API_KEY non configurata — registrati su criminalip.io")
        if settings.ABUSECH_API_KEY:
            _c(check_ip_threatfox, ip, "ip")
        else:
            _s("ThreatFox", ip, "ip", "ABUSECH_API_KEY non configurata — registrati su auth.abuse.ch")

    # ── URL ─────────────────────────────────────────────────────────────────
    for url in urls[:20]:
        _c(check_url_openphish, url, "url")
        if settings.ABUSECH_API_KEY:
            _c(check_url_urlhaus,   url, "url")
            _c(check_url_threatfox, url, "url")
        else:
            _s("URLhaus",   url, "url", "ABUSECH_API_KEY non configurata — registrati su auth.abuse.ch")
            _s("ThreatFox", url, "url", "ABUSECH_API_KEY non configurata — registrati su auth.abuse.ch")
        if settings.PHISHTANK_API_KEY:
            _c(check_url_phishtank, url, "url")
        else:
            _s("PhishTank", url, "url", "PHISHTANK_API_KEY non configurata")
        if settings.VIRUSTOTAL_API_KEY:
            _c(check_url_virustotal, url, "url")
        else:
            _s("VirusTotal", url, "url", "VIRUSTOTAL_API_KEY non configurata")
        # Redirect chain — solo shortener o HTTP
        try:
            parsed = urllib.parse.urlparse(url)
            host = parsed.netloc.lower().lstrip("www.")
            if host in URL_SHORTENERS or parsed.scheme == "http":
                _c(check_url_redirect_chain, url, "url")
        except Exception:
            pass
        # crt.sh e CIRCL Passive DNS — solo domini (non IP diretti)
        try:
            host = urllib.parse.urlparse(url).netloc.split(":")[0]
            ipaddress.ip_address(host)   # se è un IP → ValueError → salta
        except ValueError:
            domain = host.lstrip("www.")
            if domain:
                _c(check_domain_crtsh, domain, "url")
                if settings.CIRCL_API_KEY:
                    _c(check_domain_circl_pdns, domain, "url")
                _c(check_url_urlscan, url, "url")
                if settings.PULSEDIVE_API_KEY:
                    _c(check_url_pulsedive, url, "url")
                else:
                    _s("Pulsedive", url, "url", "PULSEDIVE_API_KEY non configurata — registrati su pulsedive.com")
                if settings.SECURITYTRAILS_API_KEY:
                    _c(check_domain_securitytrails, domain, "url")
                else:
                    _s("SecurityTrails", url, "url", "SECURITYTRAILS_API_KEY non configurata — registrati su securitytrails.com")
        except Exception:
            pass

    # ── Hash ────────────────────────────────────────────────────────────────
    for h in hashes[:10]:
        if settings.ABUSECH_API_KEY:
            _c(check_hash_threatfox, h, "hash")
        else:
            _s("ThreatFox", h, "hash", "ABUSECH_API_KEY non configurata — registrati su auth.abuse.ch")
        if settings.ABUSECH_API_KEY or settings.MALWAREBAZAAR_API_KEY:
            _c(check_hash_malwarebazaar, h, "hash")
        else:
            _s("MalwareBazaar", h, "hash", "ABUSECH_API_KEY non configurata — registrati su auth.abuse.ch (o MALWAREBAZAAR_API_KEY legacy)")
        if settings.VIRUSTOTAL_API_KEY:
            _c(check_hash_virustotal, h, "hash")
        else:
            _s("VirusTotal", h, "hash", "VIRUSTOTAL_API_KEY non configurata")
        if settings.HYBRID_ANALYSIS_API_KEY:
            _c(check_hash_hybrid_analysis, h, "hash")
        else:
            _s("Hybrid Analysis", h, "hash", "HYBRID_ANALYSIS_API_KEY non configurata — registrati su hybrid-analysis.com")

    return call_tasks, skip_results


def run_reputation_checks(ips: list[str], urls: list[str], hashes: list[str]) -> ReputationSummary:
    """
    Esegue TUTTI i check reputazionali in un unico ThreadPoolExecutor flat.
    Design:
    - Nessun executor annidato: tutti i task (entità × servizi) su un unico pool
    - Rate limiting thread-safe per connettore: Lock + timestamp per serializzare
      le chiamate allo stesso servizio (VirusTotal: max 1 ogni 15s)
    - Retry con backoff esponenziale su 429 e 5xx per ogni connettore
    - Feed statici (OpenPhish, Spamhaus) pre-caricati nel thread principale
    - max_workers proporzionale ai task ma cappato a 16 (non saturare la rete)
    - Timeout globale: REQUEST_TIMEOUT * 4 per dare margine ai retry
    """
    summary = ReputationSummary()

    # Pre-carica i feed nel thread principale
    _load_spamhaus()
    _load_openphish()

    call_tasks, skip_results = _build_flat_tasks(ips, urls, hashes)

    # Distribuisce i risultati skip nelle liste corrette
    for r in skip_results:
        if r.entity_type == "ip":
            summary.ip_results.append(r)
        elif r.entity_type == "url":
            summary.url_results.append(r)
        else:
            summary.hash_results.append(r)

    if call_tasks:
        # Tutti i task in un unico pool — nessun nesting, nessun overhead extra su Windows
        # max_workers = numero di task (ogni servizio su ogni entità gira subito in parallelo)
        # Cap a 32 per non saturare il sistema
        # max 16 worker: evita spike di rete e rispetta i rate limit dei servizi
        # VirusTotal viene serializzato dal _rate_limit interno (15s tra chiamate)
        # crt.sh viene serializzato dal _rate_limit interno (2.5s tra chiamate)
        n_workers = min(len(call_tasks), 16)
        # Timeout generoso: REQUEST_TIMEOUT(8) * 4 + margine retry = ~40s
        # Ogni singolo connettore ha già il proprio timeout interno più basso
        single_timeout = REQUEST_TIMEOUT * 5  # 40s: copre worst-case con retry

        pool = ThreadPoolExecutor(max_workers=n_workers,
                                  thread_name_prefix="emlyzer-rep")
        try:
            future_map = {
                pool.submit(fn, entity): (kind, entity, fn.__name__)
                for fn, entity, kind in call_tasks
            }
            done, not_done = wait(future_map.keys(), timeout=single_timeout)

            for future in done:
                kind, entity, fn_name = future_map[future]
                try:
                    r = future.result()
                except Exception as e:
                    r = ReputationResult(
                        source=fn_name, entity=entity, entity_type=kind,
                        error=f"Errore: {e}",
                    )
                if kind == "ip":
                    summary.ip_results.append(r)
                elif kind == "url":
                    summary.url_results.append(r)
                else:
                    summary.hash_results.append(r)

            for future in not_done:
                future.cancel()
                kind, entity, fn_name = future_map[future]
                r = ReputationResult(
                    source=fn_name, entity=entity, entity_type=kind,
                    error="Timeout servizio",
                )
                if kind == "ip":
                    summary.ip_results.append(r)
                elif kind == "url":
                    summary.url_results.append(r)
                else:
                    summary.hash_results.append(r)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    all_results = summary.ip_results + summary.url_results + summary.hash_results
    summary.service_registry = _build_service_registry(all_results)

    malicious = [r for r in all_results if r.is_malicious and not r.skipped and not r.error]
    summary.malicious_count = len(malicious)
    if malicious:
        avg_conf = sum(r.confidence for r in malicious) / len(malicious)
        summary.reputation_score = min(avg_conf * 1.2, 100.0)

    return summary


# ---------------------------------------------------------------------------
# Interfaccia a due fasi — FAST e SLOW
# ---------------------------------------------------------------------------

def run_fast_checks(ips: list[str], urls: list[str], hashes: list[str]) -> "ReputationSummary":
    """
    Fase 1 — servizi senza rate limit stringente.
    Risposta garantita in < 15s indipendentemente dal numero di entità.
    Include: Spamhaus, ASN, OpenPhish, PhishTank, crt.sh, Redirect Chain, MalwareBazaar.
    Esclude: VirusTotal (15.5s/req) e AbuseIPDB (1.1s/req serializzati).
    """
    _load_spamhaus()
    _load_openphish()

    call_tasks, skip_results = _build_flat_tasks(ips, urls, hashes)

    # Filtra solo i servizi fast
    fast_calls = [(fn, entity, kind) for fn, entity, kind in call_tasks
                  if fn.__name__ in _FAST_SERVICES]
    slow_skips = [ReputationResult(
        source=_FN_TO_SOURCE.get(fn.__name__, fn.__name__),
        entity=entity, entity_type=kind,
        skipped=True, skip_reason="Rimandato alla fase lenta (in elaborazione)"
    ) for fn, entity, kind in call_tasks if fn.__name__ in _SLOW_SERVICES]

    summary = ReputationSummary()
    for r in skip_results + slow_skips:
        if r.entity_type == "ip":    summary.ip_results.append(r)
        elif r.entity_type == "url": summary.url_results.append(r)
        else:                        summary.hash_results.append(r)

    if fast_calls:
        n_workers = min(len(fast_calls), 16)
        single_timeout = REQUEST_TIMEOUT * 3   # 24s: generoso per crt.sh lento

        pool = ThreadPoolExecutor(max_workers=n_workers,
                                  thread_name_prefix="emlyzer-fast")
        try:
            future_map = {
                pool.submit(fn, entity): (kind, entity, fn.__name__)
                for fn, entity, kind in fast_calls
            }
            done, not_done = futures_wait(future_map.keys(), timeout=single_timeout)
            for future in done:
                kind, entity, fn_name = future_map[future]
                try:
                    r = future.result()
                except Exception as e:
                    r = ReputationResult(source=fn_name, entity=entity,
                                         entity_type=kind, error=f"Errore: {e}")
                if kind == "ip":    summary.ip_results.append(r)
                elif kind == "url": summary.url_results.append(r)
                else:               summary.hash_results.append(r)
            for future in not_done:
                future.cancel()
                kind, entity, fn_name = future_map[future]
                r = ReputationResult(source=fn_name, entity=entity,
                                     entity_type=kind, error="Timeout")
                if kind == "ip":    summary.ip_results.append(r)
                elif kind == "url": summary.url_results.append(r)
                else:               summary.hash_results.append(r)
        finally:
            # shutdown(wait=False, cancel_futures=True): non blocca
            # threading._shutdown() alla chiusura → nessun KeyboardInterrupt su CTRL+C
            pool.shutdown(wait=False, cancel_futures=True)

    all_results = summary.ip_results + summary.url_results + summary.hash_results
    summary.service_registry = _build_service_registry(all_results)
    malicious = [r for r in all_results if r.is_malicious and not r.skipped and not r.error]
    summary.malicious_count = len(malicious)
    if malicious:
        avg_conf = sum(r.confidence for r in malicious) / len(malicious)
        summary.reputation_score = min(avg_conf * 1.2, 100.0)
    return summary


def finalize_fast_only(summary: "ReputationSummary") -> "ReputationSummary":
    """Rimuove i placeholder 'in elaborazione' quando non ci sono indicatori SLOW.

    Chiamata dalla route quando has_slow=False, evita che AbuseIPDB/VirusTotal/crt.sh
    rimangano bloccati in stato 'pending' indefinitamente.
    Ricalcola service_registry dopo la pulizia: i servizi SLOW appaiono
    come 'not_applicable' anziché 'pending'.
    """
    for lst in (summary.ip_results, summary.url_results, summary.hash_results):
        to_remove = [r for r in lst if r.skipped
                     and "in elaborazione" in (r.skip_reason or "")]
        for r in to_remove:
            lst.remove(r)
    all_results = summary.ip_results + summary.url_results + summary.hash_results
    summary.service_registry = _build_service_registry(all_results)
    return summary


def run_slow_checks(ips: list[str], urls: list[str], hashes: list[str],
                    existing: "ReputationSummary") -> "ReputationSummary":
    """
    Fase 2 — servizi con rate limit stringente (VirusTotal, AbuseIPDB).
    Eseguita in background; i risultati vengono mergiati con quelli della fase 1.
    Il rate limiter thread-safe garantisce max 4 req/min per VirusTotal.
    """
    call_tasks, skip_results = _build_flat_tasks(ips, urls, hashes)

    slow_calls = [(fn, entity, kind) for fn, entity, kind in call_tasks
                  if fn.__name__ in _SLOW_SERVICES]

    if not slow_calls:
        return existing

    # Esegui con thread daemon: se Python si chiude (CTRL+C), questi thread
    # vengono abbandonati senza bloccare threading._shutdown().
    # max_workers=4 evita spike su Windows. Nessun timeout: il rate limiter
    # interno (VT: 15.5s/req) garantisce la serializzazione naturale.
    n_workers = min(len(slow_calls), 4)
    pool = ThreadPoolExecutor(
        max_workers=n_workers,
        thread_name_prefix="emlyzer-slow",
        # initializer non supporta daemon=True direttamente, ma
        # shutdown(wait=False) ha lo stesso effetto alla chiusura
    )
    try:
        future_map = {
            pool.submit(fn, entity): (kind, entity, fn.__name__)
            for fn, entity, kind in slow_calls
        }
        done, _ = futures_wait(future_map.keys(), timeout=None)
        for future in done:
            kind, entity, fn_name = future_map[future]
            try:
                r = future.result()
            except Exception as e:
                r = ReputationResult(source=fn_name, entity=entity,
                                     entity_type=kind, error=f"Errore: {e}")
            if kind == "ip":    existing.ip_results.append(r)
            elif kind == "url": existing.url_results.append(r)
            else:               existing.hash_results.append(r)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    # Ricalcola registry e score dopo merge
    all_results = existing.ip_results + existing.url_results + existing.hash_results
    # Rimuovi i placeholder "in elaborazione" per i servizi ora completati
    # Usa _FN_TO_SOURCE per i nomi corretti (stessa mappa usata per crearli)
    slow_names = {_FN_TO_SOURCE.get(fn.__name__, fn.__name__)
                  for fn, _, _ in slow_calls}
    for lst in (existing.ip_results, existing.url_results, existing.hash_results):
        to_remove = [r for r in lst if r.skipped
                     and r.source in slow_names
                     and "in elaborazione" in (r.skip_reason or "")]
        for r in to_remove:
            lst.remove(r)

    all_results = existing.ip_results + existing.url_results + existing.hash_results
    existing.service_registry = _build_service_registry(all_results)
    malicious = [r for r in all_results if r.is_malicious and not r.skipped and not r.error]
    existing.malicious_count = len(malicious)
    if malicious:
        avg_conf = sum(r.confidence for r in malicious) / len(malicious)
        existing.reputation_score = min(avg_conf * 1.2, 100.0)
    return existing