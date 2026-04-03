"""
core/analysis/url_analyzer.py

Analisi URL estratti dal corpo email:
- Parsing dominio / IP / percorso
- Rilevamento URL shortener, IP diretto, Punycode/IDN
- DNS lookup (A record) locale
- WHOIS età dominio (best-effort, offline-friendly)
- Redirect chain (opzionale, richiede rete)
"""

import re
import socket
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import tldextract
from utils.i18n import t


# URL shortener noti (stesso set usato in body_analyzer)
URL_SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "ow.ly", "is.gd", "buff.ly",
    "rebrand.ly", "short.io", "cutt.ly", "tiny.cc", "rb.gy", "goo.gl",
}

# Regex per rilevare indirizzi IP diretti come host
IP_HOST_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")

# Punycode / IDN
PUNYCODE_RE = re.compile(r"xn--", re.IGNORECASE)


@dataclass
class URLAnalysis:
    original_url: str
    scheme: str = ""
    host: str = ""
    path: str = ""
    domain: str = ""
    subdomain: str = ""
    tld: str = ""
    is_ip_address: bool = False
    is_shortener: bool = False
    is_punycode: bool = False
    resolved_ip: str = ""
    dns_error: str = ""
    whois_creation_date: Optional[datetime] = None
    domain_age_days: Optional[int] = None
    is_new_domain: bool = False   # < 30 giorni
    https_used: bool = False
    findings: list[dict] = field(default_factory=list)
    risk_score: float = 0.0


@dataclass
class URLAnalysisResult:
    urls: list[URLAnalysis] = field(default_factory=list)
    total_urls: int = 0
    high_risk_count: int = 0
    score_contribution: float = 0.0


def _parse_url(url: str) -> tuple[str, str, str, str]:
    """Ritorna (scheme, host, path, query)."""
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme, parsed.netloc or parsed.path, parsed.path, parsed.query
    except Exception:
        return "", url, "", ""


def _resolve_ip(host: str) -> tuple[str, str]:
    """DNS A lookup. Ritorna (ip, error)."""
    try:
        ip = socket.gethostbyname(host)
        return ip, ""
    except socket.gaierror as e:
        return "", str(e)
    except Exception as e:
        return "", str(e)


def _whois_age(domain: str) -> tuple[Optional[datetime], Optional[int], str]:
    """
    Tenta WHOIS per ricavare la data di creazione.
    Ritorna (creation_date, age_days, error).
    Non blocca l'analisi se fallisce.

    python-whois emette logger.error() quando un server WHOIS chiude il socket
    bruscamente (comportamento normale per molti server TLD). Lo soppressa
    temporaneamente durante la chiamata per non inquinare i log di uvicorn.
    """
    import logging as _logging
    import whois  # python-whois — import lazy per performance
    # Sopprime il logger di python-whois: i server WHOIS chiudono il socket
    # TCP dopo la risposta (TCP half-close normale) e python-whois lo logga
    # come error. Il filtro globale in main.py lo blocca già, ma setLevel
    # qui aggiunge un secondo livello di difesa indipendente dall'app FastAPI.
    _whois_logger = _logging.getLogger("whois")
    _whois_whois_logger = _logging.getLogger("whois.whois")
    _prev_level = _whois_logger.level
    _prev_level2 = _whois_whois_logger.level
    _whois_logger.setLevel(_logging.CRITICAL)
    _whois_whois_logger.setLevel(_logging.CRITICAL)
    try:
        w = whois.whois(domain)
        creation = w.creation_date
        if isinstance(creation, list):
            creation = creation[0]
        if creation:
            if creation.tzinfo is None:
                creation = creation.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - creation).days
            return creation, age, ""
        return None, None, "No creation date in WHOIS"
    except Exception as e:
        return None, None, str(e)
    finally:
        _whois_logger.setLevel(_prev_level)
        _whois_whois_logger.setLevel(_prev_level2)


def _analyze_single_url(url: str, do_whois: bool = False) -> URLAnalysis:
    analysis = URLAnalysis(original_url=url)

    scheme, host, path, _ = _parse_url(url)
    analysis.scheme = scheme
    analysis.host = host
    analysis.path = path
    analysis.https_used = scheme.lower() == "https"

    # Rimuovi porta dall'host
    clean_host = host.split(":")[0] if host else ""

    # IP diretto?
    if IP_HOST_RE.match(clean_host):
        analysis.is_ip_address = True
        analysis.resolved_ip = clean_host
        analysis.findings.append({
            "severity": "high",
            "description": t("url.ip_direct", ip=clean_host),
        })
    else:
        # Estrai dominio con tldextract
        ext = tldextract.extract(url)
        analysis.domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
        analysis.subdomain = ext.subdomain
        analysis.tld = ext.suffix

        # Punycode / IDN
        if PUNYCODE_RE.search(clean_host):
            analysis.is_punycode = True
            analysis.findings.append({
                "severity": "high",
                "description": t("url.punycode", host=clean_host),
                "evidence": t("url.punycode_evidence"),
            })

        # URL shortener
        if analysis.domain in URL_SHORTENER_DOMAINS or clean_host in URL_SHORTENER_DOMAINS:
            analysis.is_shortener = True
            analysis.findings.append({
                "severity": "medium",
                "description": t("url.shortener", domain=analysis.domain),
                "evidence": t("url.shortener_evidence"),
            })

        # DNS lookup
        ip, dns_err = _resolve_ip(clean_host)
        analysis.resolved_ip = ip
        analysis.dns_error = dns_err
        if dns_err:
            analysis.findings.append({
                "severity": "medium",
                "description": t("url.dns_fail", host=clean_host),
                "evidence": dns_err,
            })

        # WHOIS età dominio (opzionale, può essere lento)
        if do_whois and analysis.domain:
            creation, age_days, whois_err = _whois_age(analysis.domain)
            analysis.whois_creation_date = creation
            analysis.domain_age_days = age_days
            if age_days is not None and age_days < 30:
                analysis.is_new_domain = True
                analysis.findings.append({
                    "severity": "high",
                    "description": t("url.new_domain", days=age_days),
                    "evidence": f"Creato il: {creation}",
                })
            elif age_days is not None and age_days < 90:
                analysis.findings.append({
                    "severity": "medium",
                    "description": t("url.recent_domain", days=age_days),
                })

    # HTTP (non HTTPS)
    if scheme.lower() == "http":
        analysis.findings.append({
            "severity": "low",
            "description": t("url.http"),
        })

    # Risk score per questo URL
    weights = {"info": 0, "low": 5, "medium": 15, "high": 25}
    analysis.risk_score = min(sum(weights.get(f["severity"], 0) for f in analysis.findings), 100.0)

    return analysis


def analyze_urls(urls: list[str], do_whois: bool = False) -> URLAnalysisResult:
    """
    Analizza una lista di URL estratti dal corpo email.
    do_whois=False di default (può essere lento; attivare opzionalmente).
    """
    result = URLAnalysisResult()

    # Deduplica e filtra URL validi
    seen = set()
    valid_urls = []
    for url in urls:
        url = url.strip().rstrip(".,;)'\"")
        if url and url not in seen and re.match(r"https?://", url):
            seen.add(url)
            valid_urls.append(url)

    capped_urls = valid_urls[:50]  # limite di sicurezza: max 50 URL per email
    result.total_urls = len(capped_urls)

    for url in capped_urls:
        analysis = _analyze_single_url(url, do_whois=do_whois)
        result.urls.append(analysis)
        if analysis.risk_score >= 25:
            result.high_risk_count += 1

    # Score complessivo: media pesata degli URL ad alto rischio
    if result.urls:
        scores = [u.risk_score for u in result.urls]
        result.score_contribution = min(sum(scores) / len(scores) + result.high_risk_count * 5, 100.0)

    return result