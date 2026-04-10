"""
core/analysis/url_analyzer.py

Analisi URL estratti dal corpo email:
- Parsing dominio / IP / percorso
- Rilevamento URL shortener, IP diretto, Punycode/IDN
- DNS lookup (A record) con timeout via dnspython
- WHOIS età dominio (best-effort, con timeout garantito)
- Elaborazione URL in parallelo con ThreadPoolExecutor
"""

import re
import urllib.parse
import concurrent.futures
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import tldextract
import dns.resolver
import dns.exception
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

# Timeout operazioni di rete (secondi)
DNS_TIMEOUT   = 5.0   # per singola query DNS (dnspython, per-resolver)
WHOIS_TIMEOUT = 8.0   # wall-clock per singola query WHOIS (via executor)

# Worker paralleli per l'analisi URL
URL_WORKERS = 8

# Timeout totale (secondi) per l'intera analisi URL batch
URL_BATCH_TIMEOUT = 55


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
    """
    DNS A lookup con timeout tramite dnspython.
    Evita l'uso di socket.gethostbyname() che blocca il thread senza
    timeout configurabile, comportandosi in modo imprevedibile su Linux.
    Ritorna (ip, error).
    """
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout  = DNS_TIMEOUT
        resolver.lifetime = DNS_TIMEOUT
        answers = resolver.resolve(host, "A")
        return str(answers[0]), ""
    except dns.exception.Timeout:
        return "", f"DNS timeout ({DNS_TIMEOUT}s)"
    except dns.resolver.NXDOMAIN:
        return "", "DNS: dominio non trovato"
    except dns.resolver.NoAnswer:
        return "", "DNS: nessun record A"
    except dns.resolver.NoNameservers:
        return "", "DNS: nessun nameserver disponibile"
    except Exception as e:
        return "", str(e)


def _whois_age_blocking(domain: str) -> tuple[Optional[datetime], Optional[int], str]:
    """
    Esegue la query WHOIS vera e propria.
    Funzione bloccante — deve essere sempre chiamata tramite _whois_age()
    che la avvolge in un executor con timeout wall-clock garantito.
    """
    import logging as _logging
    import whois  # import lazy per performance
    _whois_logger       = _logging.getLogger("whois")
    _whois_whois_logger = _logging.getLogger("whois.whois")
    _prev_level  = _whois_logger.level
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


def _whois_age(domain: str) -> tuple[Optional[datetime], Optional[int], str]:
    """
    WHOIS con wall-clock timeout garantito tramite ThreadPoolExecutor.

    Problema su Linux: python-whois apre connessioni TCP verso server WHOIS
    che possono non rispondere per decine di secondi (comportamento diverso
    da Windows dove il resolver di sistema tende ad essere più rapido).
    Il wrapping in un executor con future.result(timeout=N) garantisce un
    limite assoluto indipendente dal comportamento del server remoto.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_whois_age_blocking, domain)
        try:
            return future.result(timeout=WHOIS_TIMEOUT)
        except concurrent.futures.TimeoutError:
            return None, None, f"WHOIS timeout ({WHOIS_TIMEOUT}s)"


def _analyze_single_url(url: str, do_whois: bool = True) -> URLAnalysis:
    analysis = URLAnalysis(original_url=url)

    scheme, host, path, _ = _parse_url(url)
    analysis.scheme    = scheme
    analysis.host      = host
    analysis.path      = path
    analysis.https_used = scheme.lower() == "https"

    # Rimuovi porta dall'host
    clean_host = host.split(":")[0] if host else ""

    # IP diretto?
    if IP_HOST_RE.match(clean_host):
        analysis.is_ip_address = True
        analysis.resolved_ip   = clean_host
        analysis.findings.append({
            "severity": "high",
            "description": t("url.ip_direct", ip=clean_host),
        })
    else:
        # Estrai dominio con tldextract
        ext = tldextract.extract(url)
        analysis.domain    = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
        analysis.subdomain = ext.subdomain
        analysis.tld       = ext.suffix

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

        # DNS lookup con timeout
        ip, dns_err = _resolve_ip(clean_host)
        analysis.resolved_ip = ip
        analysis.dns_error   = dns_err
        if dns_err:
            analysis.findings.append({
                "severity": "medium",
                "description": t("url.dns_fail", host=clean_host),
                "evidence": dns_err,
            })

        # WHOIS età dominio (opzionale, con timeout garantito)
        if do_whois and analysis.domain:
            creation, age_days, _ = _whois_age(analysis.domain)
            analysis.whois_creation_date = creation
            analysis.domain_age_days     = age_days
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


def analyze_urls(urls: list[str], do_whois: bool = True) -> URLAnalysisResult:
    """
    Analizza una lista di URL estratti dal corpo email.

    do_whois=True di default; passare False per analisi più rapide (es. input manuale).

    Gli URL vengono elaborati in parallelo con ThreadPoolExecutor (URL_WORKERS thread)
    per eliminare l'attesa sequenziale su DNS e WHOIS che causava timeout su Linux.
    Un cap complessivo di URL_BATCH_TIMEOUT secondi garantisce che l'intera fase
    URL non superi mai il budget di tempo dell'endpoint, anche con 50 URL lenti.
    """
    result = URLAnalysisResult()

    # Deduplica e filtra URL validi
    seen: set[str] = set()
    valid_urls: list[str] = []
    for url in urls:
        url = url.strip().rstrip(".,;)'\"")
        if url and url not in seen and re.match(r"https?://", url):
            seen.add(url)
            valid_urls.append(url)

    capped_urls = valid_urls[:50]  # limite di sicurezza: max 50 URL per email
    result.total_urls = len(capped_urls)

    if not capped_urls:
        return result

    # Elaborazione parallela degli URL
    analyses: list[URLAnalysis] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=URL_WORKERS) as executor:
        future_map = {
            executor.submit(_analyze_single_url, url, do_whois): url
            for url in capped_urls
        }
        try:
            for future in concurrent.futures.as_completed(future_map, timeout=URL_BATCH_TIMEOUT):
                try:
                    analyses.append(future.result())
                except Exception:
                    pass  # URL non analizzabile: skippa senza bloccare
        except concurrent.futures.TimeoutError:
            # Raccoglie i risultati già disponibili entro il timeout di batch
            for future in future_map:
                if future.done():
                    try:
                        analyses.append(future.result())
                    except Exception:
                        pass

    result.urls            = analyses
    result.high_risk_count = sum(1 for a in analyses if a.risk_score >= 25)

    # Score complessivo: media pesata degli URL ad alto rischio
    if analyses:
        scores = [u.risk_score for u in analyses]
        result.score_contribution = min(
            sum(scores) / len(scores) + result.high_risk_count * 5, 100.0
        )

    return result
