"""
core/reputation/connectors.py

Connettori reputazione:
  IP:   AbuseIPDB, VirusTotal, Spamhaus DROP, ASN lookup (ipinfo.io)
  URL:  VirusTotal, OpenPhish, PhishTank, redirect chain
  Hash: VirusTotal, MalwareBazaar
  Domini: crt.sh (certificati TLS)

Ogni connettore traccia il proprio stato (queried/skipped/error) per la UI.
"""

import time
import base64
import ipaddress
import urllib.parse
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait
import requests
from dataclasses import dataclass, field
from utils.config import settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT      = 8    # servizi di sicurezza (AbuseIPDB, VirusTotal, ecc.)
REQUEST_TIMEOUT_ASN  = 4    # ASN lookup
REQUEST_TIMEOUT_INFO = 5    # servizi informativi (crt.sh, redirect chain)

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
    "openphish":    0.0,    # feed locale, nessun limit
    "spamhaus":     0.0,    # feed locale, nessun limit
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
    timeout: float = REQUEST_TIMEOUT,
    max_retries: int = 2,
    rate_key: str = "",
) -> requests.Response:
    """
    Esegue una GET con retry su errori temporanei (429, 502, 503, 504).
    Backoff esponenziale: 2s, 4s. Su 429 usa Retry-After se presente.
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
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
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
    try:
        resp = _http_get_with_retry("https://openphish.com/feed.txt",
            headers={"User-Agent": f"EMLyzer/{settings.VERSION} (email forensics tool)"},
            timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        _openphish_cache = {l.strip().lower() for l in resp.text.splitlines() if l.strip()}
        _openphish_loaded = True
    except Exception as e:
        _openphish_error = str(e)
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
            headers={"User-Agent": f"EMLyzer/{settings.VERSION} (email forensics tool)"},
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
# MalwareBazaar  (no API key)
# ---------------------------------------------------------------------------

def check_hash_malwarebazaar(sha256: str) -> ReputationResult:
    r = ReputationResult(source="MalwareBazaar", entity=sha256, entity_type="hash")

    if not settings.MALWAREBAZAAR_API_KEY:
        r.skipped = True
        r.skip_reason = "MALWAREBAZAAR_API_KEY non configurata — registrati su bazaar.abuse.ch/account/"
        return r

    r.queried = True
    try:
        resp = _http_post_with_retry("https://mb-api.abuse.ch/api/v1/",
            data={"query": "get_info", "hash": sha256},
            headers={
                "User-Agent": f"EMLyzer/{settings.VERSION} (email forensics tool)",
                "Auth-Key": settings.MALWAREBAZAAR_API_KEY,
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
    try:
        # DROP list: singoli IP/CIDR malevoli di alto profilo
        resp = _http_get_with_retry(
            "https://www.spamhaus.org/drop/drop.txt",
            headers={"User-Agent": f"EMLyzer/{settings.VERSION} (email forensics tool)"},
            timeout=REQUEST_TIMEOUT,
            rate_key="spamhaus",
            max_retries=2,
        )
        resp.raise_for_status()
        networks = []
        for line in resp.text.splitlines():
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            cidr = line.split(";")[0].strip()
            try:
                networks.append(ipaddress.ip_network(cidr, strict=False))
            except ValueError:
                pass
        _spamhaus_cache = networks
        _spamhaus_loaded = True
    except Exception as e:
        _spamhaus_error = str(e)
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
            headers={"User-Agent": f"EMLyzer/{settings.VERSION} (email forensics tool)"},
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
            headers={"User-Agent": f"EMLyzer/{settings.VERSION} (email forensics tool)"},
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
    ("AbuseIPDB",      "ip",          True,  "Reputazione IP (Received header, X-Originating-IP, IP negli URL)"),
    ("VirusTotal",     "ip+url+hash", True,  "Analisi multi-engine IP, URL e hash (piano free: 4 req/min)"),
    ("Spamhaus DROP",  "ip",          False, "Blocklist IP malevoli di alto profilo — no API key richiesta"),
    ("ASN Lookup",     "ip",          False, "Autonomous System Number per ogni IP — no API key (ipinfo.io)"),
    # URL
    ("OpenPhish",      "url",         False, "Feed URL phishing — no API key richiesta"),
    ("PhishTank",      "url",         True,  "Database URL phishing verificati dalla community"),
    ("Redirect Chain", "url",         False, "Segue i redirect degli URL shortener — no API key"),
    ("crt.sh",         "url",         False, "Certificati TLS emessi per il dominio — no API key"),
    # Hash
    ("MalwareBazaar",  "hash",        True,  "Hash allegati nel database malware (API key richiesta — bazaar.abuse.ch)"),
]

def _build_service_registry(all_results: list[ReputationResult]) -> list[dict]:
    by_source: dict[str, list[ReputationResult]] = {}
    for r in all_results:
        by_source.setdefault(r.source, []).append(r)

    key_map = {
        "AbuseIPDB":      bool(settings.ABUSEIPDB_API_KEY),
        "VirusTotal":     bool(settings.VIRUSTOTAL_API_KEY),
        "Spamhaus DROP":  True,
        "ASN Lookup":     True,
        "OpenPhish":      True,
        "PhishTank":      bool(settings.PHISHTANK_API_KEY),
        "Redirect Chain": True,
        "crt.sh":         True,
        "MalwareBazaar":  bool(settings.MALWAREBAZAAR_API_KEY),
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
    "check_ip_spamhaus",        # feed locale, 0s
    "check_ip_asn",             # 1 HTTP, 0.3s rate
    "check_url_openphish",      # feed locale, 0s
    "check_url_redirect_chain", # 1 HTTP per URL, 0.2s rate
    "check_url_phishtank",      # 1 HTTP, 0.5s rate
    "check_hash_malwarebazaar", # 1 HTTP, 0.7s rate
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
        _c(check_ip_spamhaus, ip, "ip")
        _c(check_ip_asn,      ip, "ip")

    # ── URL ─────────────────────────────────────────────────────────────────
    for url in urls[:20]:
        _c(check_url_openphish, url, "url")
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
        # crt.sh — solo domini (non IP diretti)
        try:
            host = urllib.parse.urlparse(url).netloc.split(":")[0]
            ipaddress.ip_address(host)   # se è un IP → ValueError → salta
        except ValueError:
            domain = host.lstrip("www.")
            if domain:
                _c(check_domain_crtsh, domain, "url")
        except Exception:
            pass

    # ── Hash ────────────────────────────────────────────────────────────────
    for h in hashes[:10]:
        if settings.MALWAREBAZAAR_API_KEY:
            _c(check_hash_malwarebazaar, h, "hash")
        else:
            _s("MalwareBazaar", h, "hash", "MALWAREBAZAAR_API_KEY non configurata")
        if settings.VIRUSTOTAL_API_KEY:
            _c(check_hash_virustotal, h, "hash")
        else:
            _s("VirusTotal", h, "hash", "VIRUSTOTAL_API_KEY non configurata")

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