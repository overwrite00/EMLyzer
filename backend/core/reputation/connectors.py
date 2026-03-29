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
    entity_type: str  # "ip" / "url" / "hash"
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
    malicious = stats.get("malicious", 0)
    suspicious = stats.get("suspicious", 0)
    harmless = stats.get("harmless", 0)
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
    if code == 429:
        return "Quota VirusTotal esaurita (4 req/min piano gratuito — riprova tra poco)"
    if code == 401:
        return "Chiave API VirusTotal non valida"
    if code == 404:
        return "Entità non trovata in VirusTotal"
    return f"HTTP {code}: {e.response.text[:150]}"


def check_ip_virustotal(ip: str) -> ReputationResult:
    r = ReputationResult(source="VirusTotal", entity=ip, entity_type="ip")
    if not settings.VIRUSTOTAL_API_KEY:
        r.skipped = True
        r.skip_reason = "VIRUSTOTAL_API_KEY non configurata nel file .env"
        return r
    r.queried = True
    try:
        _rate_limit("virustotal", 15.0)
        resp = requests.get(
            f"https://www.virustotal.com/api/v3/ip_addresses/{ip}",
            headers=_vt_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        stats = (
            resp.json()
            .get("data", {})
            .get("attributes", {})
            .get("last_analysis_stats", {})
        )
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
        r.skipped = True
        r.skip_reason = "VIRUSTOTAL_API_KEY non configurata nel file .env"
        return r
    r.queried = True
    try:
        _rate_limit("virustotal", 15.0)
        url_id = base64.urlsafe_b64encode(url.encode()).rstrip(b"=").decode()
        resp = requests.get(
            f"https://www.virustotal.com/api/v3/urls/{url_id}",
            headers=_vt_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 404:
            # URL non in cache: invia per analisi futura
            requests.post(
                "https://www.virustotal.com/api/v3/urls",
                headers=_vt_headers(),
                data={"url": url},
                timeout=REQUEST_TIMEOUT,
            )
            r.detail = "URL inviato a VirusTotal per analisi (non era ancora in cache)"
            return r
        resp.raise_for_status()
        stats = (
            resp.json()
            .get("data", {})
            .get("attributes", {})
            .get("last_analysis_stats", {})
        )
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
        r.skipped = True
        r.skip_reason = "VIRUSTOTAL_API_KEY non configurata nel file .env"
        return r
    r.queried = True
    try:
        _rate_limit("virustotal", 15.0)
        resp = requests.get(
            f"https://www.virustotal.com/api/v3/files/{sha256}",
            headers=_vt_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 404:
            r.detail = "Hash non trovato in VirusTotal"
            return r
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
        resp = requests.get(
            "https://openphish.com/feed.txt",
            headers={"User-Agent": "EMLyzer/0.3.2 (email forensics tool)"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        _openphish_cache = {
            l.strip().lower() for l in resp.text.splitlines() if l.strip()
        }
        _openphish_loaded = True
    except Exception as e:
        _openphish_error = str(e)
        _openphish_loaded = True


def check_url_openphish(url: str) -> ReputationResult:
    r = ReputationResult(
        source="OpenPhish", entity=url, entity_type="url", queried=True
    )
    try:
        _load_openphish()
        if _openphish_error:
            r.error = f"Feed non raggiungibile: {_openphish_error}"
            return r
        r.is_malicious = url.lower() in _openphish_cache
        r.confidence = 90.0 if r.is_malicious else 0.0
        r.detail = (
            "URL nel feed OpenPhish — phishing confermato"
            if r.is_malicious
            else f"URL non nel feed ({len(_openphish_cache):,} voci caricate)"
        )
    except Exception as e:
        r.error = f"Errore: {e}"
    return r


# ---------------------------------------------------------------------------
# PhishTank
# ---------------------------------------------------------------------------


def check_url_phishtank(url: str) -> ReputationResult:
    r = ReputationResult(source="PhishTank", entity=url, entity_type="url")
    if not settings.PHISHTANK_API_KEY:
        r.skipped = True
        r.skip_reason = "PHISHTANK_API_KEY non configurata nel file .env"
        return r
    r.queried = True
    try:
        _rate_limit("phishtank")
        resp = requests.post(
            "https://checkurl.phishtank.com/checkurl/",
            data={
                "url": urllib.parse.quote(url, safe=""),
                "format": "json",
                "app_key": settings.PHISHTANK_API_KEY,
            },
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
    r = ReputationResult(source="MalwareBazaar", entity=sha256, entity_type="hash")

    if not settings.MALWAREBAZAAR_API_KEY:
        r.skipped = True
        r.skip_reason = "MALWAREBAZAAR_API_KEY non configurata — registrati su bazaar.abuse.ch/account/"
        return r

    r.queried = True
    try:
        _rate_limit("malwarebazaar")
        resp = requests.post(
            "https://mb-api.abuse.ch/api/v1/",
            data={"query": "get_info", "hash": sha256},
            headers={
                "User-Agent": "EMLyzer/0.3.2 (email forensics tool)",
                "Auth-Key": settings.MALWAREBAZAAR_API_KEY,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        st = data.get("query_status", "")
        if st == "ok":
            r.is_malicious = True
            r.confidence = 100.0
            info = data.get("data", [{}])[0]
            r.detail = (
                f"Malware: {info.get('signature','N/A')} | "
                f"Tipo: {info.get('file_type','N/A')} | "
                f"Tag: {', '.join(info.get('tags',[]) or [])}"
            )
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
        resp = requests.get(
            "https://www.spamhaus.org/drop/drop.txt",
            headers={"User-Agent": "EMLyzer/0.3.3 (email forensics tool)"},
            timeout=REQUEST_TIMEOUT,
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
    r = ReputationResult(
        source="Spamhaus DROP", entity=ip, entity_type="ip", queried=True
    )
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
        _rate_limit("asn_lookup", min_interval=0.5)
        resp = requests.get(
            f"https://ipinfo.io/{ip}/json",
            headers={"User-Agent": "EMLyzer/0.3.3 (email forensics tool)"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        org = data.get("org", "")  # es. "AS16509 Amazon.com, Inc."
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
    """
    r = ReputationResult(
        source="crt.sh", entity=domain, entity_type="url", queried=True
    )
    try:
        _rate_limit("crtsh", min_interval=1.0)
        resp = requests.get(
            "https://crt.sh/",
            params={"q": domain, "output": "json"},
            headers={"User-Agent": "EMLyzer/0.3.3 (email forensics tool)"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        certs = resp.json()
        if not certs:
            r.detail = "Nessun certificato TLS trovato per questo dominio"
            return r

        # Ordina per data di emissione
        dates = []
        for c in certs:
            d = c.get("not_before", "")
            if d:
                dates.append(d)
        dates.sort()

        total = len(certs)
        first = dates[0][:10] if dates else "?"
        last = dates[-1][:10] if dates else "?"
        r.detail = f"{total} certificati trovati — primo: {first}, ultimo: {last}"

        # Flag: dominio con pochissimi certificati e recente → sospetto
        if total <= 2 and dates and dates[-1] > "2024-01-01":
            r.is_malicious = False  # non malevolo di per sé, ma è un segnale
            r.confidence = 30.0
            r.detail += " ⚠ dominio molto recente con pochi certificati"

    except Exception as e:
        r.error = f"Errore crt.sh: {e}"
    return r


# ---------------------------------------------------------------------------
# Redirect chain — segue i redirect degli URL shortener
# ---------------------------------------------------------------------------


def check_url_redirect_chain(url: str) -> ReputationResult:
    """
    Segue la catena di redirect di un URL e riporta la destinazione finale.
    Utile per URL shortener (bit.ly, t.co, ecc.) che nascondono la destinazione.
    """
    r = ReputationResult(
        source="Redirect Chain", entity=url, entity_type="url", queried=True
    )
    try:
        _rate_limit("redirect_chain", min_interval=0.5)
        resp = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; EMLyzer/0.3.3)",
                "Accept": "text/html,application/xhtml+xml,*/*",
            },
            allow_redirects=True,
            timeout=REQUEST_TIMEOUT,
            # Non scaricare il body
            stream=True,
        )
        resp.close()  # chiudi subito senza leggere il body

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
    "bit.ly",
    "t.co",
    "tinyurl.com",
    "goo.gl",
    "ow.ly",
    "short.link",
    "buff.ly",
    "dlvr.it",
    "ift.tt",
    "su.pr",
    "tiny.cc",
    "is.gd",
    "cli.gs",
    "pic.gd",
    "bc.vc",
}


# ---------------------------------------------------------------------------
# Registro servizi — stato per la UI
# ---------------------------------------------------------------------------

_SERVICE_DEFS = [
    # IP
    (
        "AbuseIPDB",
        "ip",
        True,
        "Reputazione IP (Received header, X-Originating-IP, IP negli URL)",
    ),
    (
        "VirusTotal",
        "ip+url+hash",
        True,
        "Analisi multi-engine IP, URL e hash (piano free: 4 req/min)",
    ),
    (
        "Spamhaus DROP",
        "ip",
        False,
        "Blocklist IP malevoli di alto profilo — no API key richiesta",
    ),
    (
        "ASN Lookup",
        "ip",
        False,
        "Autonomous System Number per ogni IP — no API key (ipinfo.io)",
    ),
    # URL
    ("OpenPhish", "url", False, "Feed URL phishing — no API key richiesta"),
    ("PhishTank", "url", True, "Database URL phishing verificati dalla community"),
    (
        "Redirect Chain",
        "url",
        False,
        "Segue i redirect degli URL shortener — no API key",
    ),
    ("crt.sh", "url", False, "Certificati TLS emessi per il dominio — no API key"),
    # Hash
    (
        "MalwareBazaar",
        "hash",
        True,
        "Hash allegati nel database malware (API key richiesta — bazaar.abuse.ch)",
    ),
]


def _build_service_registry(all_results: list[ReputationResult]) -> list[dict]:
    by_source: dict[str, list[ReputationResult]] = {}
    for r in all_results:
        by_source.setdefault(r.source, []).append(r)

    key_map = {
        "AbuseIPDB": bool(settings.ABUSEIPDB_API_KEY),
        "VirusTotal": bool(settings.VIRUSTOTAL_API_KEY),
        "Spamhaus DROP": True,
        "ASN Lookup": True,
        "OpenPhish": True,
        "PhishTank": bool(settings.PHISHTANK_API_KEY),
        "Redirect Chain": True,
        "crt.sh": True,
        "MalwareBazaar": bool(settings.MALWAREBAZAAR_API_KEY),
    }

    registry = []
    for name, entity_type, requires_key, description in _SERVICE_DEFS:
        enabled = key_map.get(name, False)
        results = by_source.get(name, [])
        queried = sum(1 for r in results if r.queried)
        malicious = sum(1 for r in results if r.is_malicious)
        errors = [r.error for r in results if r.error]

        if not enabled:
            # Servizio non configurato (manca API key)
            state = "skipped"
            skip_msgs = [r.skip_reason for r in results if r.skip_reason]
            state_detail = (
                skip_msgs[0]
                if skip_msgs
                else (
                    f"Aggiungi la chiave API nel file .env"
                    if requires_key
                    else "Servizio disabilitato"
                )
            )
        elif errors:
            state = "error"
            state_detail = errors[0]
        elif malicious > 0:
            state = "malicious"
            state_detail = (
                f"{malicious} indicatori malevoli su {queried} entità analizzate"
            )
        elif queried > 0:
            state = "clean"
            state_detail = f"{queried} {'entità analizzata' if queried == 1 else 'entità analizzate'} — nessun indicatore malevolo"
        else:
            # Servizio attivo ma non pertinente per questa email
            # (es. nessun URL → OpenPhish non chiamato; nessun allegato → MalwareBazaar non chiamato)
            state = "not_applicable"
            entity_desc = {
                "ip": "nessun IP nei Received header",
                "url": "nessun URL nel corpo",
                "hash": "nessun allegato",
                "ip+url+hash": "nessuna entità da analizzare",
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
            for r in results
            if r.queried
        ]

        registry.append(
            {
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
            }
        )

    return registry


# ---------------------------------------------------------------------------
# Aggregator principale
# ---------------------------------------------------------------------------


@dataclass
class ReputationSummary:
    ip_results: list[ReputationResult] = field(default_factory=list)
    url_results: list[ReputationResult] = field(default_factory=list)
    hash_results: list[ReputationResult] = field(default_factory=list)
    service_registry: list[dict] = field(default_factory=list)
    malicious_count: int = 0
    reputation_score: float = 0.0


def run_reputation_checks(
    ips: list[str], urls: list[str], hashes: list[str]
) -> ReputationSummary:
    summary = ReputationSummary()

    # ── IP ────────────────────────────────────────────────────────────────────
    for ip in ips[:15]:
        # AbuseIPDB — richiede API key
        if settings.ABUSEIPDB_API_KEY:
            summary.ip_results.append(check_ip_abuseipdb(ip))
        else:
            r = ReputationResult(
                source="AbuseIPDB",
                entity=ip,
                entity_type="ip",
                skipped=True,
                skip_reason="ABUSEIPDB_API_KEY non configurata",
            )
            summary.ip_results.append(r)

        # VirusTotal IP — richiede API key
        if settings.VIRUSTOTAL_API_KEY:
            summary.ip_results.append(check_ip_virustotal(ip))
        else:
            r = ReputationResult(
                source="VirusTotal",
                entity=ip,
                entity_type="ip",
                skipped=True,
                skip_reason="VIRUSTOTAL_API_KEY non configurata",
            )
            summary.ip_results.append(r)

        # Spamhaus DROP — gratuito, no API key
        summary.ip_results.append(check_ip_spamhaus(ip))

        # ASN Lookup — gratuito, no API key
        summary.ip_results.append(check_ip_asn(ip))

    # ── URL ───────────────────────────────────────────────────────────────────
    for url in urls[:20]:
        # OpenPhish — gratuito
        summary.url_results.append(check_url_openphish(url))

        # PhishTank — richiede API key
        if settings.PHISHTANK_API_KEY:
            summary.url_results.append(check_url_phishtank(url))
        else:
            r = ReputationResult(
                source="PhishTank",
                entity=url,
                entity_type="url",
                skipped=True,
                skip_reason="PHISHTANK_API_KEY non configurata",
            )
            summary.url_results.append(r)

        # VirusTotal URL — richiede API key
        if settings.VIRUSTOTAL_API_KEY:
            summary.url_results.append(check_url_virustotal(url))
        else:
            r = ReputationResult(
                source="VirusTotal",
                entity=url,
                entity_type="url",
                skipped=True,
                skip_reason="VIRUSTOTAL_API_KEY non configurata",
            )
            summary.url_results.append(r)

        # Redirect chain — solo per URL shortener o HTTP (non HTTPS trusted)
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            host = parsed.netloc.lower().lstrip("www.")
            is_shortener = host in URL_SHORTENERS
            is_http = parsed.scheme == "http"
            if is_shortener or is_http:
                summary.url_results.append(check_url_redirect_chain(url))
        except Exception:
            pass

        # crt.sh — solo per URL con dominio (non IP diretti)
        try:
            from urllib.parse import urlparse
            import ipaddress

            host = urlparse(url).netloc.split(":")[0]
            try:
                ipaddress.ip_address(host)  # è un IP → salta crt.sh
            except ValueError:
                # È un dominio → controlla certificati
                domain = host.lstrip("www.")
                summary.url_results.append(check_domain_crtsh(domain))
        except Exception:
            pass

    # ── Hash ──────────────────────────────────────────────────────────────────
    for sha256 in hashes[:10]:
        if settings.MALWAREBAZAAR_API_KEY:
            summary.hash_results.append(check_hash_malwarebazaar(sha256))
        else:
            r = ReputationResult(
                source="MalwareBazaar",
                entity=sha256,
                entity_type="hash",
                skipped=True,
                skip_reason="MALWAREBAZAAR_API_KEY non configurata",
            )
            summary.hash_results.append(r)
        if settings.VIRUSTOTAL_API_KEY:
            summary.hash_results.append(check_hash_virustotal(sha256))
        else:
            r = ReputationResult(
                source="VirusTotal",
                entity=sha256,
                entity_type="hash",
                skipped=True,
                skip_reason="VIRUSTOTAL_API_KEY non configurata",
            )
            summary.hash_results.append(r)

    all_results = summary.ip_results + summary.url_results + summary.hash_results
    summary.service_registry = _build_service_registry(all_results)

    malicious = [
        r for r in all_results if r.is_malicious and not r.skipped and not r.error
    ]
    summary.malicious_count = len(malicious)
    if malicious:
        avg_conf = sum(r.confidence for r in malicious) / len(malicious)
        summary.reputation_score = min(avg_conf * 1.2, 100.0)

    return summary
