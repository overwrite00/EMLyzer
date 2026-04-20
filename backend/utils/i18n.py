"""
utils/i18n.py

Localizzazione backend: italiano (it) e inglese (en).
La lingua viene letta da config (default: it).
Usare t("chiave") per ottenere la stringa tradotta.
"""

from utils.config import settings

TRANSLATIONS = {
    # ── Upload ────────────────────────────────────────────────────────────────
    "upload.no_filename": {
        "it": "Nome file mancante",
        "en": "Missing filename",
    },
    "upload.unsupported_format": {
        "it": "Formato non supportato: '{ext}'. Formati accettati: {allowed}",
        "en": "Unsupported format: '{ext}'. Accepted formats: {allowed}",
    },
    "upload.empty_file": {
        "it": "File vuoto",
        "en": "Empty file",
    },
    "upload.too_large": {
        "it": "File troppo grande: max {max_mb} MB",
        "en": "File too large: max {max_mb} MB",
    },
    "upload.save_error": {
        "it": "Errore salvataggio file: {error}",
        "en": "File save error: {error}",
    },
    "upload.success": {
        "it": "File caricato con successo. Avvia l'analisi con POST /api/analysis/{job_id}",
        "en": "File uploaded successfully. Start analysis with POST /api/analysis/{job_id}",
    },

    # ── Analysis ──────────────────────────────────────────────────────────────
    "analysis.invalid_job_id": {
        "it": "job_id non valido",
        "en": "Invalid job_id",
    },
    "analysis.file_not_found": {
        "it": "File non trovato per job_id: {job_id}",
        "en": "File not found for job_id: {job_id}",
    },
    "analysis.not_found": {
        "it": "Analisi non trovata",
        "en": "Analysis not found",
    },
    "analysis.run_first": {
        "it": "Analisi non trovata. Esegui prima POST /api/analysis/{job_id}",
        "en": "Analysis not found. Run POST /api/analysis/{job_id} first",
    },

    # ── Report ────────────────────────────────────────────────────────────────
    "report.generation_error": {
        "it": "Errore generazione report: {error}",
        "en": "Report generation error: {error}",
    },

    # ── Risk labels ───────────────────────────────────────────────────────────
    "risk.low": {
        "it": "Basso rischio",
        "en": "Low risk",
    },
    "risk.medium": {
        "it": "Rischio moderato",
        "en": "Moderate risk",
    },
    "risk.high": {
        "it": "Alto rischio",
        "en": "High risk",
    },
    "risk.critical": {
        "it": "Rischio critico",
        "en": "Critical risk",
    },

    # ── Header analysis findings ──────────────────────────────────────────────
    "header.from_rp_mismatch": {
        "it": "Mismatch tra dominio From e Return-Path",
        "en": "Mismatch between From domain and Return-Path domain",
    },
    "header.from_rt_mismatch": {
        "it": "Mismatch tra dominio From e Reply-To (possibile redirect delle risposte)",
        "en": "Mismatch between From domain and Reply-To (possible reply redirect)",
    },
    "header.spf_result": {
        "it": "SPF result: {result}",
        "en": "SPF result: {result}",
    },
    "header.dkim_result": {
        "it": "DKIM result: {result}",
        "en": "DKIM result: {result}",
    },
    "header.dmarc_result": {
        "it": "DMARC result: {result}",
        "en": "DMARC result: {result}",
    },
    "header.bulk_sender": {
        "it": "Tool di invio massivo rilevato: {tool}",
        "en": "Bulk sending tool detected: {tool}",
    },
    "header.injection": {
        "it": "Possibile header injection in {field}",
        "en": "Possible header injection in {field}",
    },
    "header.no_message_id": {
        "it": "Message-ID assente (anomalo per email legittima)",
        "en": "Missing Message-ID (unusual for legitimate email)",
    },
    "header.no_date": {
        "it": "Header Date assente",
        "en": "Missing Date header",
    },
    "header.private_ip": {
        "it": "X-Originating-IP è un indirizzo privato/loopback: {ip}",
        "en": "X-Originating-IP is a private/loopback address: {ip}",
    },
    "header.auth_all_fail": {
        "it": "FAIL (SPF + DKIM + DMARC tutti falliti)",
        "en": "FAIL (SPF + DKIM + DMARC all failed)",
    },
    "header.auth_partial": {
        "it": "PARZIALE ({n}/3 controlli falliti)",
        "en": "PARTIAL ({n}/3 checks failed)",
    },
    "header.auth_ok": {
        "it": "OK",
        "en": "OK",
    },
    "header.auth_absent": {
        "it": "ASSENTE (nessun risultato auth trovato)",
        "en": "ABSENT (no auth results found)",
    },

    # ── List-Unsubscribe findings ─────────────────────────────────────────────
    "header.list_unsub_present": {
        "it": "List-Unsubscribe presente — email bulk legittima",
        "en": "List-Unsubscribe present — legitimate bulk email",
    },
    "header.list_unsub_external_domain": {
        "it": "List-Unsubscribe punta a un dominio esterno al mittente: {domain}",
        "en": "List-Unsubscribe points to external sender domain: {domain}",
    },
    "header.list_unsub_http": {
        "it": "List-Unsubscribe usa HTTP non sicuro (non HTTPS)",
        "en": "List-Unsubscribe uses insecure HTTP (not HTTPS)",
    },
    "header.list_unsub_ip": {
        "it": "List-Unsubscribe usa IP diretto invece di dominio",
        "en": "List-Unsubscribe uses direct IP instead of domain",
    },
    "header.list_unsub_malformed": {
        "it": "Header List-Unsubscribe malformato (formato non valido)",
        "en": "Malformed List-Unsubscribe header (invalid format)",
    },

    # ── X-Campaign-ID findings ────────────────────────────────────────────────
    "header.campaign_id_detected": {
        "it": "X-Campaign-ID rilevato: {value}",
        "en": "X-Campaign-ID detected: {value}",
    },
    "header.campaign_no_unsub": {
        "it": "Email bulk con X-Campaign-ID ma senza List-Unsubscribe",
        "en": "Bulk email with X-Campaign-ID but missing List-Unsubscribe",
    },

    # ── ARC chain findings ────────────────────────────────────────────────────
    "header.arc_valid": {
        "it": "ARC chain valida ({n} hop)",
        "en": "ARC chain valid ({n} hops)",
    },
    "header.arc_incomplete": {
        "it": "ARC chain incompleta — gap nella sequenza i= (trovati: {found})",
        "en": "ARC chain incomplete — gap in i= sequence (found: {found})",
    },
    "header.arc_fail": {
        "it": "ARC chain validation fallita (cv=fail) — possibile manomissione in transito",
        "en": "ARC chain validation failed (cv=fail) — possible in-transit tampering",
    },

    # ── Body analysis findings ────────────────────────────────────────────────
    "body.urgency_high": {
        "it": "Linguaggio di urgenza artificiale rilevato ({count} pattern)",
        "en": "Artificial urgency language detected ({count} patterns)",
    },
    "body.urgency_medium": {
        "it": "Possibile linguaggio urgente ({count} pattern)",
        "en": "Possible urgent language ({count} patterns)",
    },
    "body.cta_high": {
        "it": "Molteplici call-to-action sospette ({count})",
        "en": "Multiple suspicious call-to-action ({count})",
    },
    "body.cta_medium": {
        "it": "Call-to-action sospetta rilevata",
        "en": "Suspicious call-to-action detected",
    },
    "body.credentials": {
        "it": "Richiesta di credenziali/dati sensibili ({count} keyword)",
        "en": "Request for credentials/sensitive data ({count} keywords)",
    },
    "body.obfuscated_links": {
        "it": "Link offuscati: testo visibile ≠ destinazione reale ({count} link)",
        "en": "Obfuscated links: visible text ≠ actual destination ({count} links)",
    },
    "body.shortener": {
        "it": "URL shortener rilevato: {domain}",
        "en": "URL shortener detected: {domain}",
    },
    "body.form_embedded": {
        "it": "Form HTML embedded nel corpo email ({count} form)",
        "en": "Embedded HTML form in email body ({count} forms)",
    },
    "body.form_evidence": {
        "it": "Le email legittime non contengono form per raccolta dati",
        "en": "Legitimate emails do not contain data collection forms",
    },
    "body.javascript": {
        "it": "JavaScript trovato nel corpo HTML ({count} tag <script>)",
        "en": "JavaScript found in HTML body ({count} <script> tags)",
    },
    "body.hidden_elements": {
        "it": "Elementi HTML nascosti tramite CSS ({count})",
        "en": "HTML elements hidden via CSS ({count})",
    },
    "body.hidden_evidence": {
        "it": "Tecnica usata per bypassare filtri antispam",
        "en": "Technique used to bypass spam filters",
    },
    "body.base64_non_image": {
        "it": "Contenuto Base64 inline non-immagine: {mime}",
        "en": "Non-image inline Base64 content: {mime}",
    },
    "body.base64_image": {
        "it": "Immagine inline Base64 ({mime})",
        "en": "Inline Base64 image ({mime})",
    },

    # ── URL analysis ──────────────────────────────────────────────────────────
    "url.ip_direct": {
        "it": "URL punta direttamente a IP: {ip}",
        "en": "URL points directly to IP address: {ip}",
    },
    "url.punycode": {
        "it": "Dominio Punycode/IDN rilevato: {host}",
        "en": "Punycode/IDN domain detected: {host}",
    },
    "url.punycode_evidence": {
        "it": "Possibile attacco homograph",
        "en": "Possible homograph attack",
    },
    "url.shortener": {
        "it": "URL shortener: {domain}",
        "en": "URL shortener: {domain}",
    },
    "url.shortener_evidence": {
        "it": "La destinazione reale è nascosta",
        "en": "The actual destination is hidden",
    },
    "url.dns_fail": {
        "it": "DNS non risolvibile: {host}",
        "en": "DNS resolution failed: {host}",
    },
    "url.age_new":     { "it": "Dominio {days} giorni (nuovo!)",  "en": "Domain {days} days (new!)" },
    "url.age_recent":  { "it": "Dominio {days} giorni (recente)", "en": "Domain {days} days (recent)" },
    "url.age_ok":      { "it": "Dominio {days} giorni",            "en": "Domain {days} days" },
    "url.new_domain": {
        "it": "Dominio registrato da meno di 30 giorni ({days} giorni)",
        "en": "Domain registered less than 30 days ago ({days} days)",
    },
    "url.recent_domain": {
        "it": "Dominio molto recente ({days} giorni)",
        "en": "Very recent domain ({days} days)",
    },
    "url.http": {
        "it": "URL usa HTTP (non HTTPS)",
        "en": "URL uses HTTP (not HTTPS)",
    },

    # ── Attachment analysis ───────────────────────────────────────────────────
    "att.dangerous_ext": {
        "it": "Estensione pericolosa: {ext}",
        "en": "Dangerous extension: {ext}",
    },
    "att.double_ext": {
        "it": "Doppia estensione rilevata (possibile camuffamento)",
        "en": "Double extension detected (possible disguise)",
    },
    "att.mime_mismatch": {
        "it": "Tipo MIME dichiarato ≠ reale",
        "en": "Declared MIME type ≠ actual type",
    },
    "att.macro_ole": {
        "it": "Macro VBA rilevata in file Office (OLE2)",
        "en": "VBA macro detected in Office file (OLE2)",
    },
    "att.macro_ooxml": {
        "it": "Macro VBA rilevata in file Office (OOXML)",
        "en": "VBA macro detected in Office file (OOXML)",
    },
    "att.pdf_js": {
        "it": "JavaScript trovato nel PDF",
        "en": "JavaScript found in PDF",
    },
    "att.pdf_stream": {
        "it": "Stream PDF sospetto rilevato",
        "en": "Suspicious PDF stream detected",
    },

    # ── NLP ──────────────────────────────────────────────────────────────────────
    "body.nlp_phishing": {
        "it": "NLP: probabilità phishing {prob}% (confidenza: {confidence})",
        "en": "NLP: phishing probability {prob}% (confidence: {confidence})",
    },

    # ── Analysis / bulk-delete / notes ──────────────────────────────────────────
    "analysis.bulk_max": {
        "it": "Massimo 100 analisi per richiesta",
        "en": "Maximum 100 analyses per request",
    },
    "analysis.no_valid_ids": {
        "it": "Nessun job_id valido fornito",
        "en": "No valid job_id provided",
    },
    "analysis.notes_too_long": {
        "it": "Note troppo lunghe (max 10.000 caratteri)",
        "en": "Notes too long (max 10,000 characters)",
    },

    # ── Reputation route ─────────────────────────────────────────────────────────
    "reputation.timeout": {
        "it": "I servizi di reputazione non hanno risposto nel tempo previsto. Riprova.",
        "en": "Reputation services did not respond in time. Try again.",
    },

    # ── Settings route ───────────────────────────────────────────────────────────
    "settings.language_unsupported": {
        "it": "Lingua non supportata. Usa 'it' o 'en'.",
        "en": "Unsupported language. Use 'it' or 'en'.",
    },

    # ── Manual input ──────────────────────────────────────────────────────────
    "manual.parse_error": {
        "it": "Impossibile analizzare il testo fornito come email RFC 822",
        "en": "Unable to parse the provided text as RFC 822 email",
    },
    "manual.empty": {
        "it": "Testo sorgente vuoto",
        "en": "Empty source text",
    },
}


def t(key: str, lang: str = None, **kwargs) -> str:
    """
    Ritorna la stringa tradotta per la chiave data.
    lang: 'it' | 'en' — se None usa settings.LANGUAGE
    kwargs: variabili da sostituire con .format()
    """
    if lang is None:
        lang = getattr(settings, "LANGUAGE", "it")
    if lang not in ("it", "en"):
        lang = "it"

    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key  # chiave non trovata: ritorna la chiave stessa

    text = entry.get(lang) or entry.get("it") or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text