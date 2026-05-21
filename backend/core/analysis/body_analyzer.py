"""
core/analysis/body_analyzer.py

Analisi del corpo email:
- Pattern linguistici di urgenza / phishing (text)
- Link offuscati, form, CSS invisibile, JS sospetto (HTML)
- Base64 inline sospetto
"""

import re
import base64
import logging as _logging
import unicodedata
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
import bleach

from core.analysis.email_parser import ParsedEmail
from core.analysis.nlp_classifier import classify_text, NLPResult
from utils.i18n import t

_logger = _logging.getLogger(__name__)


# --- Pattern linguistici sospetti (case-insensitive) ---
URGENCY_PATTERNS = [
    r"\burgent\b", r"\bimmediately\b", r"\baction required\b",
    r"\baccount.*suspend", r"\bverify.*account", r"\bconfirm.*identity",
    r"\bclick.*now\b", r"\blimited.*time\b", r"\bexpire[sd]?\b",
    r"\bunusual.*activit", r"\bsuspicious.*activit",
    # Italiano — espanso
    r"\burgente\b", r"\bscadenza\b", r"\bverifica.*(?:account|conto|email|identit)",
    r"\bconferma.*(?:identit|account|conto|dati)\b", r"\baccesso.*bloccato", r"\bsospeso\b",
    r"\bclicca.*ora\b", r"\bimmediatamente\b", r"\bazione.*richiesta\b",
    r"\blimitato.*tempo\b", r"\btempo.*limitato\b", r"\bscade\b", r"\bscadenza\b",
    r"\bbloccato\b", r"\blimitato\b", r"\brestritto\b",
    r"\battivit[aà]\s+(?:inusuale|sospetta|anomala|strana)\b",
    # Portoghese — espanso
    r"\bexpirando\b", r"\bexpira[m]?\b", r"\bimediato\b", r"\bimediatamente\b",
    r"\bverificar.*conta", r"\bconfirme.*identidade", r"\bacesso.*bloqueado\b",
    r"\bclique.*agora\b",
    # Portoghese — aggiunti
    r"\bur(?:gência|gencia|gência|gencia|ência|encia)\b",  # varianti di urgência/urgência
    r"\bação\s+obrigatória\b", r"\bação\s+necessária\b",
    r"\bserá\s+suspenso\b", r"\bser[aá]\s+bloquead[oa]\b",
    r"\bdesbloqueie\b", r"\bdesbloqu[a-z]*", r"\breativar\b", r"\breativaç",
    r"\batividade\s+(?:suspeita|inusitada|suspeito|anormal)\b",
    r"\bconfirme\s+(?:sua|seu|seus|sua)\s+(?:conta|email|e-mail|identidade)\b",
    r"\bprazo\s+final\b", r"\blimite.*tempo\b",
    r"\bsuspen[dç][ãa]o?\b",
    r"\bhoje\b",  # "hoje" (today) — urgency indicator in Portuguese
]

PHISHING_CTAS = [
    r"\bclick here\b", r"\blog in\b", r"\bsign in\b",
    r"\bverify now\b", r"\bupdate.*payment", r"\benter.*password",
    r"\bprovide.*credential", r"\bdownload.*attachment",
    # Italiano — espanso
    r"\baccedi ora\b", r"\baccedi\s+(?:subito|adesso|qui|now)\b",
    r"\bclicca qui\b", r"\bclicca.*(?:qui|qua|subito|adesso)\b",
    r"\bconferma.*(?:dati|account|identit|email)\b", r"\bconferma\s+(?:subito|adesso|ora|now)\b",
    r"\baggiornam.*(?:pagam|dati|password|credenziali)\b",
    r"\binserisci.*(?:password|credenziali|dati|email)\b",
    r"\bverifica\s+(?:subito|adesso|ora|now)\b", r"\bverifica.*(?:conto|account|identit|email)\b",
    r"\bvalida.*(?:conto|account|identit|email)\b",
    r"\baggiornam.*(?:account|conto)\b", r"\baggiorna.*(?:account|conto|dati)\b",
    # Portoghese — espanso
    r"\bresgatar agora\b", r"\bclique aqui\b", r"\bclique.*aqui\b", r"\bclique.*agora\b",
    r"\bconfirme.*dados", r"\batualize.*pagam", r"\binserir.*senha",
    r"\bfaça login\b", r"\bfaça.*acesso\b", r"\bverificar agora\b", r"\blogar\b",
    # Portoghese — aggiunti
    r"\bacesse\s+(?:sua|seu|seus|sua)\s+conta\b",
    r"\batualize\s+(?:seus|sua|seu)\s+(?:dados|password|passwd|senha)\b",
    r"\bconfirme\s+seu\s+(?:e-?mail|email|e-mail)\b",
    r"\bvalide\s+sua\s+identidade\b",
    r"\bautentique-?se\b", r"\bautenticate\b",
    r"\bfaça\s+(?:seu\s+)?(?:login|acesso)\b",
]

CREDENTIAL_KEYWORDS = [
    r"\bpassword\b", r"\bpin\b", r"\bcredential", r"\bsocial security\b",
    r"\bcredit card\b", r"\biban\b",
    # Italiano — specifici e finanziari
    r"\bconto\s+(?:bancario|corrente|email|online)\b",
    r"\baccount\b", r"\bemail\b", r"\be-mail\b",
    r"\bpassword\b", r"\bcodice.*(?:fiscale|sicurezza|PIN|segreto)\b",
    r"\bcarta\s+(?:di\s+)?credito\b", r"\bcarta.*credito\b",
    r"\biban\b", r"\bbic\b", r"\biban.*bic\b",
    r"\biban.*numero\b", r"\bnumero.*conto\b",
    r"\bdati\s+(?:bancari|personali|sensibili)\b",
    r"\bcredenziali\b", r"\bidentificativo\b", r"\bcodice\s+(?:personale|segreto)\b",
    # Portoghese — specifici e finanziari
    r"\bsenha\b", r"\bcartão.*crédito\b", r"\bcpf\b",
    # Portoghese — aggiunti per contesto bancario brasiliano
    r"\bagência\b", r"\bconta\s+(?:bancária|corrente|poupança)\b",
    r"\bnúmero\s+da\s+conta\b", r"\bcódigo\s+de\s+segurança\b",
    r"\botp\b", r"\bone-?time\s+password\b",
    r"\bpix\b",  # Sistema di pagamento istantaneo brasiliano — altamente rilevante
    r"\b(?:rg|identidade|cédula)\b",
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
    matched_patterns: list[str] = field(default_factory=list)  # P1: pattern specifici trovati (urgency, CTA, credenziali)


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


def _count_pattern_matches(pattern_list: list[str], text: str, result: BodyAnalysisResult, attr_name: str, max_match_len: int = 150) -> list[tuple[str, int]]:
    """
    Consolida logica pattern matching — evita duplicazione.

    Args:
        pattern_list: lista di regex pattern da matchare
        text: testo normalizzato lowercase
        result: BodyAnalysisResult object (attributo incrementato in-place)
        attr_name: nome dell'attributo su result da incrementare (es. 'urgency_count')
        max_match_len: ignora match > questo valore (probabili falsi positivi)

    Returns:
        list[tuple(pattern_text, count)] ordinato per frequenza descrescente
    """
    pattern_hits = {}  # {pattern_matched: count}

    for pattern in pattern_list:
        matches = re.findall(pattern, text)
        for match_text in matches:
            # Ignora match troppo lunghi — probabili errori di capturing
            if len(match_text) > max_match_len:
                continue
            # Incrementa il contatore nel result object
            setattr(result, attr_name, getattr(result, attr_name) + 1)
            # Track pattern hit
            if match_text not in pattern_hits:
                pattern_hits[match_text] = 0
            pattern_hits[match_text] += 1

    # Ritorna lista di tuple ordinata per frequenza (pattern più comuni prima)
    return sorted(pattern_hits.items(), key=lambda x: x[1], reverse=True)


def _analyze_text(body_text: str, result: BodyAnalysisResult):
    """Analisi pattern su testo plain."""
    if not body_text:
        return
    # Normalizza Unicode accenti (NFC) per matching multilingua
    # Risolve problemi con portoghese/italiano: "será" vs "sera"
    text_normalized = unicodedata.normalize('NFC', body_text)
    text_lower = text_normalized.lower()

    # P1: Deduplica pattern per categoria — mantiene SOLO i pattern unici trovati
    # Usa helper function per evitare duplicazione di logica
    urgency_matches = _count_pattern_matches(URGENCY_PATTERNS, text_lower, result, 'urgency_count')
    cta_matches = _count_pattern_matches(PHISHING_CTAS, text_lower, result, 'phishing_cta_count')
    credential_matches = _count_pattern_matches(CREDENTIAL_KEYWORDS, text_lower, result, 'credential_keyword_count')

    # P1: Estrai solo i testi dei pattern (senza conteggi)
    urgency_unique = [m[0] for m in urgency_matches[:5]]
    cta_unique = [m[0] for m in cta_matches[:5]]
    credential_unique = [m[0] for m in credential_matches[:5]]

    # URGENCY
    if result.urgency_count >= 3:
        evidence = "Pattern: " + ", ".join([f'"{p}"' for p in urgency_unique])
        result.findings.append(BodyFinding(
            category="text",
            severity="high",
            description=t("body.urgency_high", occurrences=result.urgency_count, unique_patterns=len(urgency_unique)),
            evidence=evidence,
            matched_patterns=urgency_unique,
            count=result.urgency_count,
        ))
    elif result.urgency_count >= 1:
        evidence = "Pattern: " + ", ".join([f'"{p}"' for p in urgency_unique])
        result.findings.append(BodyFinding(
            category="text",
            severity="medium",
            description=t("body.urgency_medium", occurrences=result.urgency_count, unique_patterns=len(urgency_unique)),
            evidence=evidence,
            matched_patterns=urgency_unique,
            count=result.urgency_count,
        ))

    # CTA
    if result.phishing_cta_count >= 2:
        evidence = "Pattern: " + ", ".join([f'"{p}"' for p in cta_unique])
        result.findings.append(BodyFinding(
            category="text",
            severity="high",
            description=t("body.cta_high", occurrences=result.phishing_cta_count, unique_patterns=len(cta_unique)),
            evidence=evidence,
            matched_patterns=cta_unique,
            count=result.phishing_cta_count,
        ))
    elif result.phishing_cta_count == 1:
        evidence = "Pattern: " + ", ".join([f'"{p}"' for p in cta_unique])
        result.findings.append(BodyFinding(
            category="text",
            severity="medium",
            description=t("body.cta_medium"),
            evidence=evidence,
            matched_patterns=cta_unique,
        ))

    # CREDENTIALS
    if result.credential_keyword_count >= 3:
        # 3+ credential keywords = HIGH severity (phishing indicator)
        evidence = "Pattern: " + ", ".join([f'"{p}"' for p in credential_unique])
        result.findings.append(BodyFinding(
            category="text",
            severity="high",
            description=t("body.credentials", occurrences=result.credential_keyword_count, unique_patterns=len(credential_unique)),
            evidence=evidence,
            matched_patterns=credential_unique,
            count=result.credential_keyword_count,
        ))
    elif result.credential_keyword_count >= 1:
        # 1-2 credential keywords = MEDIUM severity (cautious indicator)
        evidence = "Pattern: " + ", ".join([f'"{p}"' for p in credential_unique])
        result.findings.append(BodyFinding(
            category="text",
            severity="medium",
            description=t("body.credentials", occurrences=result.credential_keyword_count, unique_patterns=len(credential_unique)),
            evidence=evidence,
            matched_patterns=credential_unique,
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
    except Exception as e:
        _logger.error("[BODY] BeautifulSoup HTML parsing failed (html_len=%d): %s", len(body_html), e)
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
                    text_domain = domain_in_text.group(1).lower()
                    if text_domain.startswith("www."):
                        text_domain = text_domain[4:]
                    href_domain_clean = href_domain[4:] if href_domain.startswith("www.") else href_domain
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
        try:
            resp = _req.post(
                url,
                data={"text": body_text[:5000], "language": "auto"},
                timeout=5,
            )
        except _req.exceptions.Timeout:
            _logger.warning("[BODY] LanguageTool timeout (5s) on %s — skipping check", url)
            return
        except _req.exceptions.ConnectionError as ce:
            _logger.warning("[BODY] LanguageTool connection error on %s: %s — skipping check", url, ce)
            return

        if resp.status_code != 200:
            _logger.warning("[BODY] LanguageTool returned status %d — skipping check", resp.status_code)
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
    except Exception as e:
        _logger.error("[BODY] LanguageTool check failed (non-critical, type=%s): %s", type(e).__name__, str(e))


def _compute_score(result: BodyAnalysisResult) -> float:
    weights = {"info": 0, "low": 5, "medium": 15, "high": 25}
    score = sum(weights.get(f.severity, 0) for f in result.findings)
    return min(score, 100.0)


def analyze_body(parsed: ParsedEmail) -> BodyAnalysisResult:
    """Entry point analisi body. Analizza sia testo plain che HTML."""
    result = BodyAnalysisResult()

    _logger.info("[BODY START] text_len=%d, html_len=%d", len(parsed.body_text or ''), len(parsed.body_html or ''))

    _analyze_text(parsed.body_text, result)
    _logger.debug("[BODY] text analysis: %d findings", len(result.findings))

    # Se il testo plain è vuoto o molto piccolo, estrarre il testo dall'HTML
    # (alcuni email sono HTML-only e non hanno body_text)
    if not parsed.body_text or len(parsed.body_text.strip()) < 50:
        try:
            if parsed.body_html:
                soup = BeautifulSoup(parsed.body_html, "html.parser")
                html_text = soup.get_text(separator=" ", strip=True)
                if html_text and len(html_text) > 50:
                    _logger.debug("[BODY] Extracting text from HTML for pattern analysis (html_text_len=%d)", len(html_text))
                    _analyze_text(html_text, result)
        except Exception as e:
            _logger.error("[BODY] Failed to extract text from HTML (html_len=%d): %s", len(parsed.body_html or ''), e)

    _analyze_html(parsed.body_html, result)
    _logger.debug("[BODY] html analysis: %d findings, %d urls extracted", len(result.findings), len(result.extracted_urls))

    _check_homoglyphs(parsed.body_text, result)
    _logger.debug("[BODY] homoglyphs checked: %d findings", len(result.findings))

    _check_languagetool(parsed.body_text, result)
    _logger.debug("[BODY] languagetool checked: %d findings", len(result.findings))

    # Deduplica URL
    result.extracted_urls = list(dict.fromkeys(result.extracted_urls))
    _logger.info("[BODY] Extracted %d unique URLs from body", len(result.extracted_urls))

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
            _logger.info("[BODY] NLP: label=%s, prob=%.2f, confidence=%s", result.nlp_result.label, result.nlp_result.phishing_probability, result.nlp_result.confidence)
    except Exception as e:
        _logger.warning("[BODY] NLP classification failed: %s", e)

    result.score_contribution = _compute_score(result)
    _logger.info("[BODY END] Total findings: %d (urgency=%d, cta=%d, creds=%d, score=%.1f)",
                 len(result.findings), result.urgency_count, result.phishing_cta_count, result.credential_keyword_count, result.score_contribution)
    return result
