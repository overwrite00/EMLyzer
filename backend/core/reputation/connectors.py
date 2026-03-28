"""
core/reputation/connectors.py

Connettori reputazione: AbuseIPDB, VirusTotal, OpenPhish, PhishTank, MalwareBazaar.
Ogni connettore traccia il proprio stato (queried/skipped/error) per la UI.
"""

import time
import base64
import urllib.parse
import requests
from dataclasses import dataclass, field
from utils.config import settings


REQUEST_TIMEOUT = 8
_last_request: dict[str, float] = {}


def _rate_limit(connector: str, min_interval: float = 1.2):
    now = time.monotonic()
    last = _last_request.get(connector, 0.0)
    if now - last < min_interval:
        time.sleep(min_interval - (now - last))
    _last_request[connector] = time.monotonic()


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
        _rate_limit("abuseipdb")
        resp = requests.get(
            "https://api.abuseipdb.com/api/v2/check",
            headers={"Key": settings.ABUSEIPDB_API_KEY, "Accept": "application/json"},
            params={"ipAddress": ip, "maxAgeInDays": 90},
            timeout=REQUEST_TIMEOUT,
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
        _rate_limit("virustotal", 15.0)
        resp = requests.get(
            f"https://www.virustotal.com/api/v3/ip_addresses/{ip}",
            headers=_vt_headers(), timeout=REQUEST_TIMEOUT,
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
        _rate_limit("virustotal", 15.0)
        url_id = base64.urlsafe_b64encode(url.encode()).rstrip(b"=").decode()
        resp = requests.get(
            f"https://www.virustotal.com/api/v3/urls/{url_id}",
            headers=_vt_headers(), timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 404:
            # URL non in cache: invia per analisi futura
            requests.post("https://www.virustotal.com/api/v3/urls",
                headers=_vt_headers(), data={"url": url}, timeout=REQUEST_TIMEOUT)
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
        _rate_limit("virustotal", 15.0)
        resp = requests.get(
            f"https://www.virustotal.com/api/v3/files/{sha256}",
            headers=_vt_headers(), timeout=REQUEST_TIMEOUT,
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
        resp = requests.get("https://openphish.com/feed.txt",
            headers={"User-Agent": "EMLyzer/0.3.2 (email forensics tool)"},
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
        _rate_limit("phishtank")
        resp = requests.post(
            "https://checkurl.phishtank.com/checkurl/",
            data={"url": urllib.parse.quote(url, safe=""), "format": "json",
                  "app_key": settings.PHISHTANK_API_KEY},
            timeout=REQUEST_TIMEOUT,
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
    r = ReputationResult(source="MalwareBazaar", entity=sha256, entity_type="hash", queried=True)
    try:
        _rate_limit("malwarebazaar")
        resp = requests.post("https://mb-api.abuse.ch/api/v1/",
            data={"query": "get_info", "hash": sha256},
            headers={"User-Agent": "EMLyzer/0.3.2 (email forensics tool)"},
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
# Registro servizi — stato per la UI
# ---------------------------------------------------------------------------

_SERVICE_DEFS = [
    ("AbuseIPDB",     "ip",           True,  "Reputazione IP dai Received header"),
    ("VirusTotal",    "ip+url+hash",  True,  "Analisi multi-engine IP, URL e hash (piano free: 4 req/min)"),
    ("OpenPhish",     "url",          False, "Feed URL phishing — no API key richiesta"),
    ("PhishTank",     "url",          True,  "Database URL phishing verificati dalla community"),
    ("MalwareBazaar", "hash",         False, "Hash allegati nel database malware — no API key richiesta"),
]

def _build_service_registry(all_results: list[ReputationResult]) -> list[dict]:
    by_source: dict[str, list[ReputationResult]] = {}
    for r in all_results:
        by_source.setdefault(r.source, []).append(r)

    key_map = {
        "AbuseIPDB":    bool(settings.ABUSEIPDB_API_KEY),
        "VirusTotal":   bool(settings.VIRUSTOTAL_API_KEY),
        "OpenPhish":    True,
        "PhishTank":    bool(settings.PHISHTANK_API_KEY),
        "MalwareBazaar": True,
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
        elif errors and queried == 0:
            state = "error"
            state_detail = errors[0]
        elif malicious > 0:
            state = "malicious"
            state_detail = f"{malicious} indicatori malevoli su {queried} entità analizzate"
        elif queried > 0:
            state = "clean"
            state_detail = f"{queried} {'entità analizzata' if queried == 1 else 'entità analizzate'} — nessun indicatore malevolo"
        else:
            # Servizio attivo ma non pertinente per questa email
            # (es. nessun URL → OpenPhish non chiamato; nessun allegato → MalwareBazaar non chiamato)
            state = "not_applicable"
            entity_desc = {
                "ip":           "nessun IP nei Received header",
                "url":          "nessun URL nel corpo",
                "hash":         "nessun allegato",
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


def run_reputation_checks(ips: list[str], urls: list[str], hashes: list[str]) -> ReputationSummary:
    summary = ReputationSummary()

    for ip in ips[:10]:
        summary.ip_results.append(check_ip_abuseipdb(ip))
        if settings.VIRUSTOTAL_API_KEY:
            summary.ip_results.append(check_ip_virustotal(ip))

    for url in urls[:20]:
        summary.url_results.append(check_url_openphish(url))
        if settings.PHISHTANK_API_KEY:
            summary.url_results.append(check_url_phishtank(url))
        if settings.VIRUSTOTAL_API_KEY:
            summary.url_results.append(check_url_virustotal(url))

    for sha256 in hashes[:10]:
        summary.hash_results.append(check_hash_malwarebazaar(sha256))
        if settings.VIRUSTOTAL_API_KEY:
            summary.hash_results.append(check_hash_virustotal(sha256))

    all_results = summary.ip_results + summary.url_results + summary.hash_results
    summary.service_registry = _build_service_registry(all_results)

    malicious = [r for r in all_results if r.is_malicious and not r.skipped and not r.error]
    summary.malicious_count = len(malicious)
    if malicious:
        avg_conf = sum(r.confidence for r in malicious) / len(malicious)
        summary.reputation_score = min(avg_conf * 1.2, 100.0)

    return summary