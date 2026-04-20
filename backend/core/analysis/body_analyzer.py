"""
core/analysis/body_analyzer.py

Analisi del corpo email:
- Pattern linguistici di urgenza / phishing (text)
- Link offuscati, form, CSS invisibile, JS sospetto (HTML)
- Base64 inline sospetto
"""

import re
import base64
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
import bleach

from core.analysis.email_parser import ParsedEmail
from core.analysis.nlp_classifier import classify_text, NLPResult
from utils.i18n import t


# --- Pattern linguistici sospetti (case-insensitive) ---
URGENCY_PATTERNS = [
    r"\burgent\b", r"\bimmediately\b", r"\baction required\b",
    r"\baccount.*suspend", r"\bverify.*account", r"\bconfirm.*identity",
    r"\bclick.*now\b", r"\blimited.*time\b", r"\bexpire[sd]?\b",
    r"\bunusual.*activit", r"\bsuspicious.*activit",
    # Italiano
    r"\burgente\b", r"\bscadenza\b", r"\bverifica.*account",
    r"\bconferma.*identit", r"\baccesso.*bloccato", r"\bsospeso\b",
    r"\bclicca.*ora\b", r"\bimmediatamente\b",
]

PHISHING_CTAS = [
    r"\bclick here\b", r"\blog in\b", r"\bsign in\b",
    r"\bverify now\b", r"\bupdate.*payment", r"\benter.*password",
    r"\bprovide.*credential", r"\bdownload.*attachment",
    # Italiano
    r"\baccedi ora\b", r"\bclicca qui\b", r"\bconferma.*dati",
    r"\baggiornam.*pagam", r"\binserisci.*password",
]

CREDENTIAL_KEYWORDS = [
    r"\bpassword\b", r"\bpin\b", r"\bcredential", r"\bsocial security\b",
    r"\bcredit card\b", r"\biban\b", r"\bconto bancario\b",
    r"\bcodice fiscale\b",
]

# Mappa omoglifi Unicode → carattere latino equivalente
# Cirillico e greco visivamente identici a caratteri latini
_HOMOGLYPH_MAP: dict[str, str] = {
    # Cirillico
    '\u0430': 'a',  # а
    '\u0435': 'e',  # е
    '\u043e': 'o',  # о
    '\u0440': 'p',  # р
    '\u0441': 'c',  # с
    '\u0445': 'x',  # х
    '\u0443': 'y',  # у
    '\u0456': 'i',  # і
    '\u0455': 's',  # ѕ
    '\u0501': 'd',  # ԁ
    '\u0412': 'B',  # В
    '\u041c': 'M',  # М
    '\u041d': 'H',  # Н
    '\u041e': 'O',  # О
    '\u0420': 'P',  # Р
    '\u0421': 'C',  # С
    '\u0422': 'T',  # Т
    '\u0425': 'X',  # Х
    '\u0410': 'A',  # А
    '\u0415': 'E',  # Е
    '\u0406': 'I',  # І
    # Greco
    '\u0391': 'A',  # Α
    '\u0392': 'B',  # Β
    '\u0395': 'E',  # Ε
    '\u0396': 'Z',  # Ζ
    '\u0397': 'H',  # Η
    '\u0399': 'I',  # Ι
    '\u039a': 'K',  # Κ
    '\u039c': 'M',  # Μ
    '\u039d': 'N',  # Ν
    '\u039f': 'O',  # Ο
    '\u03a1': 'P',  # Ρ
    '\u03a4': 'T',  # Τ
    '\u03a5': 'Y',  # Υ
    '\u03a7': 'X',  # Χ
    '\u03b1': 'a',  # α
    '\u03bf': 'o',  # ο
    '\u03c1': 'p',  # ρ
    '\u03bd': 'v',  # ν
    '\u03c9': 'w',  # ω
}

# URL shortener noti
URL_SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "ow.ly", "is.gd", "buff.ly",
    "rebrand.ly", "short.io", "cutt.ly", "tiny.cc", "rb.gy",
}


@dataclass
class BodyFinding:
    category: str  # text / html / url / base64
    severity: str  # info / low / medium / high
    description: str
    evidence: str = ""
    count: int = 1


@dataclass
class BodyAnalysisResult:
    findings: list[BodyFinding] = field(default_factory=list)
    urgency_count: int = 0
    phishing_cta_count: int = 0
    credential_keyword_count: int = 0
    obfuscated_links: list[dict] = field(default_factory=list)
    forms_found: int = 0
    js_found: bool = False
    invisible_elements: int = 0
    base64_inline_count: int = 0
    extracted_urls: list[str] = field(default_factory=list)
    raw_hidden_content: str = ""   # testo estratto dagli elementi nascosti
    nlp_result: object = None           # NLPResult dal classificatore ML
    score_contribution: float = 0.0


def _analyze_text(body_text: str, result: BodyAnalysisResult):
    """Analisi pattern su testo plain."""
    if not body_text:
        return
    text_lower = body_text.lower()

    for pattern in URGENCY_PATTERNS:
        matches = re.findall(pattern, text_lower)
        result.urgency_count += len(matches)

    for pattern in PHISHING_CTAS:
        matches = re.findall(pattern, text_lower)
        result.phishing_cta_count += len(matches)

    for pattern in CREDENTIAL_KEYWORDS:
        matches = re.findall(pattern, text_lower)
        result.credential_keyword_count += len(matches)

    if result.urgency_count >= 3:
        result.findings.append(BodyFinding(
            category="text",
            severity="high",
            description=t("body.urgency_high", count=result.urgency_count),
            evidence=t("body.urgency_high", count=result.urgency_count),
            count=result.urgency_count,
        ))
    elif result.urgency_count >= 1:
        result.findings.append(BodyFinding(
            category="text",
            severity="medium",
            description=t("body.urgency_medium", count=result.urgency_count),
            count=result.urgency_count,
        ))

    if result.phishing_cta_count >= 2:
        result.findings.append(BodyFinding(
            category="text",
            severity="high",
            description=t("body.cta_high", count=result.phishing_cta_count),
            count=result.phishing_cta_count,
        ))
    elif result.phishing_cta_count == 1:
        result.findings.append(BodyFinding(
            category="text",
            severity="medium",
            description=t("body.cta_medium"),
        ))

    if result.credential_keyword_count >= 1:
        result.findings.append(BodyFinding(
            category="text",
            severity="high",
            description=t("body.credentials", count=result.credential_keyword_count),
            count=result.credential_keyword_count,
        ))


def _analyze_html(body_html: str, result: BodyAnalysisResult):
    """Analisi HTML: link offuscati, form, CSS invisibile, JS."""
    if not body_html:
        return

    # html.parser e' incluso in Python stdlib: zero dipendenze esterne,
    # funziona su Windows/Linux/macOS con qualsiasi versione di Python.
    try:
        soup = BeautifulSoup(body_html, "html.parser")
    except Exception:
        return

    # 1. Link offuscati: href != testo visibile
    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "").strip()
        visible_text = a_tag.get_text(strip=True)

        if href:
            result.extracted_urls.append(href)

        # Controlla mismatch href vs testo visibile
        href_domain = _extract_domain_from_url(href)
        if visible_text and href and href_domain:
            # Caso 1: il testo visibile è un URL completo che punta a dominio diverso
            if _looks_like_url(visible_text):
                visible_domain = _extract_domain_from_url(visible_text)
                if visible_domain and visible_domain != href_domain:
                    result.obfuscated_links.append({
                        "visible_text": visible_text[:200],
                        "actual_href": href[:500],
                        "visible_domain": visible_domain,
                        "href_domain": href_domain,
                    })
            else:
                # Caso 2: il testo visibile contiene un dominio riconoscibile (es. "www.paypal.com")
                domain_in_text = re.search(
                    r'\b([\w-]+\.(com|org|net|it|eu|io|gov|edu|co\.\w+))\b',
                    visible_text, re.IGNORECASE
                )
                if domain_in_text:
                    text_domain = domain_in_text.group(1).lower().lstrip("www.")
                    href_domain_clean = href_domain.lstrip("www.")
                    if text_domain and text_domain not in href_domain_clean:
                        result.obfuscated_links.append({
                            "visible_text": visible_text[:200],
                            "actual_href": href[:500],
                            "visible_domain": text_domain,
                            "href_domain": href_domain_clean,
                        })

        # Controlla URL shortener
        href_domain = _extract_domain_from_url(href)
        if href_domain in URL_SHORTENER_DOMAINS:
            result.findings.append(BodyFinding(
                category="html",
                severity="medium",
                description=t("body.shortener", domain=href_domain),
                evidence=href[:200],
            ))

    if result.obfuscated_links:
        result.findings.append(BodyFinding(
            category="html",
            severity="high",
            description=t("body.obfuscated_links", count=len(result.obfuscated_links)),
            count=len(result.obfuscated_links),
        ))

    # 2. Form embedded
    forms = soup.find_all("form")
    result.forms_found = len(forms)
    if forms:
        result.findings.append(BodyFinding(
            category="html",
            severity="high",
            description=t("body.form_embedded", count=len(forms)),
            evidence=t("body.form_evidence"),
            count=len(forms),
        ))

    # 3. JavaScript
    scripts = soup.find_all("script")
    if scripts:
        result.js_found = True
        result.findings.append(BodyFinding(
            category="html",
            severity="high",
            description=t("body.javascript", count=len(scripts)),
            count=len(scripts),
        ))

    # 4. Elementi invisibili (CSS: display:none, visibility:hidden, font-size:0, color bianco)
    invisible_count = 0
    for tag in soup.find_all(style=True):
        style = tag.get("style", "").lower()
        if any(p in style for p in [
            "display:none", "display: none",
            "visibility:hidden", "visibility: hidden",
            "font-size:0", "font-size: 0",
            "color:#fff", "color: #fff", "color:white", "color: white",
            "opacity:0", "opacity: 0",
        ]):
            invisible_count += 1
    result.invisible_elements = invisible_count
    if invisible_count > 0:
        # Estrai il testo degli elementi nascosti per mostrarlo nell'interfaccia
        hidden_texts = []
        for tag in soup.find_all(style=True):
            style = tag.get("style", "").lower()
            if any(p in style for p in [
                "display:none", "display: none",
                "visibility:hidden", "visibility: hidden",
                "font-size:0", "font-size: 0",
                "color:#fff", "color: #fff", "color:white", "color: white",
                "opacity:0", "opacity: 0",
            ]):
                txt = tag.get_text(separator=" ", strip=True)
                if txt:
                    hidden_texts.append(txt)
        if hidden_texts:
            result.raw_hidden_content = "\n".join(hidden_texts[:20])
        result.findings.append(BodyFinding(
            category="html",
            severity="medium",
            description=t("body.hidden_elements", count=invisible_count),
            evidence=t("body.hidden_evidence"),
            count=invisible_count,
        ))

    # 5. Base64 inline sospetto (immagini o dati non-image)
    base64_data = re.findall(r'data:([^;]+);base64,([A-Za-z0-9+/=]{50,})', body_html)
    for mime_type, b64_data in base64_data:
        result.base64_inline_count += 1
        if not mime_type.startswith("image/"):
            result.findings.append(BodyFinding(
                category="base64",
                severity="high",
                description=t("body.base64_non_image", mime=mime_type),
                evidence=f"data:{mime_type};base64,...",
            ))
        else:
            # Immagine inline: normale ma da segnalare
            result.findings.append(BodyFinding(
                category="base64",
                severity="info",
                description=t("body.base64_image", mime=mime_type),
            ))

    # 6. Estrai URL dal testo grezzo dell'HTML
    raw_urls = re.findall(r'https?://[^\s"\'<>]+', body_html)
    for url in raw_urls:
        if url not in result.extracted_urls:
            result.extracted_urls.append(url)


def _looks_like_url(text: str) -> bool:
    return bool(re.match(r'https?://', text.strip()))


def _extract_domain_from_url(url: str) -> str:
    m = re.match(r'https?://([^/?\s]+)', url.strip())
    if m:
        host = m.group(1).lower()
        # Rimuovi porta
        return host.split(":")[0]
    return ""


def _check_homoglyphs(body_text: str, result: BodyAnalysisResult):
    """
    Rileva caratteri Unicode omoglifi (cirillico/greco) visivamente identici
    a caratteri latini — tecnica usata per spoofing visivo nei link e nel testo.
    """
    if not body_text:
        return
    found = [ch for ch in body_text if ch in _HOMOGLYPH_MAP]
    if not found:
        return
    n = len(found)
    # Caratteri unici trovati (max 10 nel sample)
    sample = "".join(dict.fromkeys(found))[:10]
    severity = "high" if n >= 3 else "low"
    result.findings.append(BodyFinding(
        category="text",
        severity=severity,
        description=t("body.homoglyphs", count=n),
        evidence=f"Caratteri sospetti: {sample}",
        count=n,
    ))


def _check_languagetool(body_text: str, result: BodyAnalysisResult):
    """
    Verifica errori grammaticali via LanguageTool (opzionale).
    Abilitato solo se LANGUAGETOOL_API_URL è configurato in .env.
    ≥5 errori → finding MEDIUM (possibile testo tradotto automaticamente).
    """
    from utils.config import settings
    url = settings.LANGUAGETOOL_API_URL.strip()
    if not url or not body_text.strip():
        return
    # Normalizza URL: assicura che termini con /check
    if not url.endswith("/check"):
        url = url.rstrip("/") + "/check"
    try:
        import requests as _req
        resp = _req.post(
            url,
            data={"text": body_text[:5000], "language": "auto"},
            timeout=5,
        )
        if resp.status_code != 200:
            return
        matches = resp.json().get("matches", [])
        n = len(matches)
        if n >= 5:
            result.findings.append(BodyFinding(
                category="text",
                severity="medium",
                description=t("body.grammar_errors", count=n),
                evidence=f"{n} potenziali errori rilevati da LanguageTool",
                count=n,
            ))
    except Exception:
        pass  # Servizio non disponibile — analisi continua senza errori


def _compute_score(result: BodyAnalysisResult) -> float:
    weights = {"info": 0, "low": 5, "medium": 15, "high": 25}
    score = sum(weights.get(f.severity, 0) for f in result.findings)
    return min(score, 100.0)


def analyze_body(parsed: ParsedEmail) -> BodyAnalysisResult:
    """Entry point analisi body. Analizza sia testo plain che HTML."""
    result = BodyAnalysisResult()

    _analyze_text(parsed.body_text, result)
    _analyze_html(parsed.body_html, result)
    _check_homoglyphs(parsed.body_text, result)
    _check_languagetool(parsed.body_text, result)

    # Deduplica URL
    result.extracted_urls = list(dict.fromkeys(result.extracted_urls))

    # Classificatore NLP (se scikit-learn disponibile)
    try:
        result.nlp_result = classify_text(parsed.body_text, parsed.body_html)
        if result.nlp_result.available and result.nlp_result.label in ("phishing", "suspicious"):
            sev = "high" if result.nlp_result.confidence == "high" else "medium"
            result.findings.append(BodyFinding(
                category="nlp",
                severity=sev,
                description=t("body.nlp_phishing", **{"prob": int(result.nlp_result.phishing_probability * 100), "confidence": result.nlp_result.confidence}),
                evidence="Feature: " + ", ".join(result.nlp_result.top_features[:5]) if result.nlp_result.top_features else "",
            ))
    except Exception:
        pass

    result.score_contribution = _compute_score(result)
    return result
