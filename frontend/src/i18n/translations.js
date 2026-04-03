// src/i18n/translations.js
// Tutte le stringhe UI in italiano e inglese

export const translations = {
  // ── App ─────────────────────────────────────────────────────────────────────
  "app.title": { it: "EMLyzer", en: "EMLyzer" },
  "app.version": { it: "versione", en: "version" },
  "app.analyses_count": { it: "{n} analisi", en: "{n} analyses" },

  // ── Dashboard ────────────────────────────────────────────────────────────────
  "dash.analyze_title": { it: "Analizza Email", en: "Analyze Email" },
  "dash.recent_title": { it: "Analisi Recenti", en: "Recent Analyses" },
  "dash.no_analyses": {
    it: "Nessuna analisi ancora. Carica un file .eml / .msg o incolla il sorgente.",
    en: "No analyses yet. Upload an .eml / .msg file or paste the raw source.",
  },

  // ── Upload zone ──────────────────────────────────────────────────────────────
  "upload.drag_title": { it: "Trascina un file .eml o .msg qui", en: "Drag an .eml or .msg file here" },
  "upload.drag_sub": { it: "oppure clicca per selezionare", en: "or click to select" },
  "upload.or": { it: "oppure", en: "or" },
  "upload.max_size": { it: "Max {mb} MB", en: "Max {mb} MB" },
  "upload.uploading": { it: "Caricamento…", en: "Uploading…" },
  "upload.analyzing": { it: "Analisi in corso…", en: "Analyzing…" },
  "upload.whois_toggle": { it: "Abilita WHOIS (età dominio)", en: "Enable WHOIS (domain age)" },
  "upload.whois_note":   { it: "più lento, interroga i server WHOIS", en: "slower, queries WHOIS servers" },
  "upload.unsupported": {
    it: "Formato non supportato: \"{ext}\". Usa .eml o .msg",
    en: "Unsupported format: \"{ext}\". Use .eml or .msg",
  },

  // ── Manual input ─────────────────────────────────────────────────────────────
  "manual.tab": { it: "Incolla sorgente", en: "Paste source" },
  "manual.file_tab": { it: "Carica file", en: "Upload file" },
  "manual.placeholder": {
    it: "Incolla qui il sorgente completo dell'email (header + body)…\n\nEsempio:\nFrom: mittente@esempio.com\nTo: destinatario@esempio.com\nSubject: Oggetto\nDate: Mon, 1 Jan 2024 10:00:00 +0000\n\nCorpo del messaggio…",
    en: "Paste the full email source here (headers + body)…\n\nExample:\nFrom: sender@example.com\nTo: recipient@example.com\nSubject: Subject line\nDate: Mon, 1 Jan 2024 10:00:00 +0000\n\nEmail body…",
  },
  "manual.analyze_btn": { it: "Analizza sorgente", en: "Analyze source" },
  "manual.empty_error": { it: "Incolla prima il sorgente dell'email.", en: "Please paste the email source first." },
  "manual.analyzing": { it: "Analisi in corso…", en: "Analyzing…" },

  // ── Search & filter ─────────────────────────────────────────────────────────
  "filter.search_placeholder": { it: "Cerca per oggetto o mittente…", en: "Search by subject or sender…" },
  "filter.all_risks":  { it: "Tutti i rischi", en: "All risks" },
  "filter.low":        { it: "Basso",    en: "Low" },
  "filter.medium":     { it: "Moderato", en: "Moderate" },
  "filter.high":       { it: "Alto",     en: "High" },
  "filter.critical":   { it: "Critico",  en: "Critical" },
  "filter.export_csv": { it: "Esporta CSV", en: "Export CSV" },
  "filter.page_of":    { it: "Pagina {page} di {pages}", en: "Page {page} of {pages}" },
  "filter.prev":       { it: "← Prec", en: "← Prev" },
  "filter.next":       { it: "Succ →", en: "Next →" },
  "filter.total_results": { it: "{n} analisi trovate", en: "{n} analyses found" },

  // ── Table columns ────────────────────────────────────────────────────────────
  "col.subject": { it: "Oggetto / Mittente", en: "Subject / Sender" },
  "col.date": { it: "Data", en: "Date" },
  "col.file": { it: "Tipo", en: "Type" },
  "col.score": { it: "Score", en: "Score" },
  "col.risk": { it: "Rischio", en: "Risk" },

  // ── Risk labels ──────────────────────────────────────────────────────────────
  "risk.low": { it: "Basso", en: "Low" },
  "risk.medium": { it: "Moderato", en: "Moderate" },
  "risk.high": { it: "Alto", en: "High" },
  "risk.critical": { it: "Critico", en: "Critical" },

  // ── Detail modal ─────────────────────────────────────────────────────────────
  "detail.no_subject": { it: "(nessun oggetto)", en: "(no subject)" },
  "detail.report_btn": { it: "Report .docx", en: ".docx Report" },
  "detail.tab_summary": { it: "Riepilogo", en: "Summary" },
  "detail.tab_header": { it: "Header", en: "Header" },
  "detail.tab_body": { it: "Body", en: "Body" },
  "detail.tab_url": { it: "URL", en: "URLs" },
  "detail.tab_attachments": { it: "Allegati", en: "Attachments" },
  "detail.tab_reputation": { it: "Reputazione", en: "Reputation" },

  // ── Summary tab ──────────────────────────────────────────────────────────────
  "summary.email_metadata": { it: "Metadati Email", en: "Email Metadata" },
  "summary.from": { it: "Da (From)", en: "From" },
  "summary.to": { it: "A (To)", en: "To" },
  "summary.subject": { it: "Oggetto", en: "Subject" },
  "summary.date": { it: "Data", en: "Date" },
  "summary.message_id": { it: "Message-ID", en: "Message-ID" },
  "summary.sha256": { it: "SHA256 file", en: "File SHA256" },
  "summary.risk_explanation": { it: "Spiegazione del Rischio", en: "Risk Explanation" },
  "summary.no_anomaly": { it: "Nessuna anomalia rilevata.", en: "No anomalies detected." },
  "summary.parse_warnings": { it: "Avvisi di Parsing", en: "Parse Warnings" },

  // ── Header tab ───────────────────────────────────────────────────────────────
  "header.auth": { it: "Autenticazione", en: "Authentication" },
  "header.auth_summary": { it: "Sommario autenticazione", en: "Auth summary" },
  "header.mismatches": { it: "Mismatch di Identità", en: "Identity Mismatches" },
  "header.bulk_sender": { it: "Tool di Invio Massivo", en: "Bulk Sending Tool" },
  "header.findings": { it: "Finding Header", en: "Header Findings" },
  "header.no_findings": { it: "Nessun finding header.", en: "No header findings." },
  "header.smtp_chain": { it: "Percorso SMTP (Received Chain)", en: "SMTP Path (Received Chain)" },
  "header.smtp_chain_note": { it: "Il percorso si legge dal mittente alla destinazione: hop 1 è il server di origine, l'ultimo hop è il server che ha ricevuto il messaggio.", en: "The path reads from sender to destination: hop 1 is the originating server, the last hop is the receiving server." },
  "header.hop_sender": { it: "mittente", en: "sender" },
  "header.hop_destination": { it: "destinazione", en: "destination" },
  "header.injection": { it: "Tentativi di Header Injection", en: "Header Injection Attempts" },

  // ── Body tab ─────────────────────────────────────────────────────────────────
  "body.stats": { it: "Statistiche", en: "Statistics" },
  "body.urgency": { it: "Pattern urgenza", en: "Urgency patterns" },
  "body.cta": { it: "CTA sospette", en: "Suspicious CTA" },
  "body.cred_kw": { it: "Keyword credenziali", en: "Credential keywords" },
  "body.forms": { it: "Form HTML", en: "HTML forms" },
  "body.javascript": { it: "JavaScript", en: "JavaScript" },
  "body.hidden": { it: "Elem. nascosti CSS", en: "CSS hidden elements" },
  "body.urls": { it: "URL estratti", en: "Extracted URLs" },
  "body.obfuscated": { it: "Link offuscati", en: "Obfuscated links" },
  "body.obfuscated_title": { it: "Link Offuscati", en: "Obfuscated Links" },
  "body.visible_text": { it: "Testo visibile:", en: "Visible text:" },
  "body.actual_href": { it: "Destinazione reale:", en: "Actual destination:" },
  "body.findings_title": { it: "Finding Body", en: "Body Findings" },
  "body.no_findings": { it: "Nessun finding body.", en: "No body findings." },
  "body.nlp_phishing":  {
    it: "NLP: probabilità phishing {prob}% (confidenza: {confidence})",
    en: "NLP: phishing probability {prob}% (confidence: {confidence})",
  },
  "body.nlp_label_phishing":   { it: "Phishing",    en: "Phishing" },
  "body.nlp_label_suspicious":  { it: "Sospetto",    en: "Suspicious" },
  "body.nlp_label_legitimate":  { it: "Legittima",   en: "Legitimate" },
  "body.nlp_label_unknown":     { it: "Sconosciuto", en: "Unknown" },
  "body.nlp_section":           { it: "Analisi NLP", en: "NLP Analysis" },
  "body.nlp_unavailable":       {
    it: "scikit-learn non installato — installa con: pip install scikit-learn nltk",
    en: "scikit-learn not installed — install with: pip install scikit-learn nltk",
  },

  "body.hidden_section": { it: "Contenuto HTML Nascosto", en: "Hidden HTML Content" },
  "body.hidden_count": { it: "{n} elementi nascosti tramite CSS", en: "{n} elements hidden via CSS" },
  "body.hidden_technique": { it: "Tecnica: {technique}", en: "Technique: {technique}" },
  "body.hidden_content_label": { it: "Testo nascosto estratto:", en: "Extracted hidden text:" },
  "body.hidden_evidence": { it: "Elementi nascosti tramite CSS o stili inline rilevati nel body HTML.", en: "Elements hidden via CSS or inline styles detected in HTML body." },
  "body.yes": { it: "Sì", en: "Yes" },
  "body.no": { it: "No", en: "No" },

  // ── URL tab ──────────────────────────────────────────────────────────────────
  "url.total": { it: "{n} URL analizzati", en: "{n} URLs analyzed" },
  "url.high_risk": { it: "{n} ad alto rischio", en: "{n} high risk" },
  "url.no_urls": { it: "Nessun URL trovato nel corpo email.", en: "No URLs found in email body." },
  "url.age_new":       { it: "🔴 Dominio {days}gg (nuovo!)",   en: "🔴 Domain {days}d (new!)" },
  "url.age_recent":    { it: "🟡 Dominio {days}gg (recente)",  en: "🟡 Domain {days}d (recent)" },
  "url.age_ok":        { it: "✅ Dominio {days}gg",             en: "✅ Domain {days}d" },
  "url.whois_no_data":      { it: "WHOIS: nessun dato",       en: "WHOIS: no data" },
  "url.whois_disabled":     { it: "WHOIS non eseguito",       en: "WHOIS not run" },
  "url.whois_disabled_hint":{ it: "Rianalizza con WHOIS abilitato per vedere l'età del dominio", en: "Re-analyze with WHOIS enabled to see domain age" },
  "url.https_ok": { it: "HTTPS", en: "HTTPS" },
  "url.http_only": { it: "HTTP", en: "HTTP" },
  "url.ip_direct": { it: "IP diretto", en: "Direct IP" },
  "url.shortener": { it: "Shortener", en: "Shortener" },
  "url.punycode": { it: "Punycode", en: "Punycode" },

  // ── Attachment tab ───────────────────────────────────────────────────────────
  "att.total": { it: "{n} allegati", en: "{n} attachments" },
  "att.critical": { it: "{n} critici", en: "{n} critical" },
  "att.no_attachments": { it: "Nessun allegato.", en: "No attachments." },
  "att.declared_mime": { it: "MIME dichiarato", en: "Declared MIME" },
  "att.real_mime": { it: "MIME reale", en: "Actual MIME" },
  "att.sha256": { it: "SHA256", en: "SHA256" },
  "att.mime_mismatch": { it: "MIME mismatch", en: "MIME mismatch" },
  "att.macro": { it: "Macro VBA", en: "VBA Macro" },
  "att.js": { it: "JavaScript", en: "JavaScript" },

  // ── Reputation tab ────────────────────────────────────────────────────────────
  "rep.description": {
    it: "Verifica IP (header SMTP, X-Originating-IP, IP negli URL), URL del body (inclusi link offuscati) e hash degli allegati tramite 9 fonti — 5 gratuite senza chiave.",
    en: "Checks IPs (SMTP headers, X-Originating-IP, direct IPs in URLs), body URLs (including obfuscated links) and attachment hashes via 9 sources — 5 free, no key required.",
  },
  "rep.run_btn": { it: "Avvia controllo reputazione", en: "Start reputation check" },
  "rep.slow_running": { it: "VirusTotal e AbuseIPDB in elaborazione in background — i risultati si aggiorneranno a breve.", en: "VirusTotal and AbuseIPDB running in background — results will update shortly." },
  "rep.rerun_btn": { it: "↻ Ri-esegui", en: "↻ Re-run" },
  "rep.score": { it: "Score reputazione", en: "Reputation score" },
  "rep.malicious": { it: "Indicatori malevoli", en: "Malicious indicators" },
  "rep.malicious_label": { it: "⚠ MALEVOLO", en: "⚠ MALICIOUS" },
  "rep.no_api_keys": {
    it: "Nessuna API key configurata. Imposta ABUSEIPDB_API_KEY nel file .env per abilitare i connettori a pagamento. I servizi gratuiti (Spamhaus, ASN, OpenPhish, Redirect Chain, crt.sh) funzionano sempre.",
    en: "No API keys configured. Set ABUSEIPDB_API_KEY in .env to enable paid connectors. Free services (Spamhaus, ASN, OpenPhish, Redirect Chain, crt.sh) always work.",
  },

  // Entità analizzate
  "rep.entities_ips":    { it: "IP analizzati",    en: "IPs analyzed" },
  "rep.entities_urls":   { it: "URL analizzati",   en: "URLs analyzed" },
  "rep.entities_hashes": { it: "Hash analizzati",  en: "Hashes analyzed" },

  // Etichette servizi specifici
  "rep.service.spamhaus":       { it: "Spamhaus DROP",  en: "Spamhaus DROP" },
  "rep.service.asn":            { it: "ASN Lookup",     en: "ASN Lookup" },
  "rep.service.redirect_chain": { it: "Redirect Chain", en: "Redirect Chain" },
  "rep.service.crtsh":          { it: "crt.sh",         en: "crt.sh" },

  // Fonti IP — tooltip
  "rep.ip_sources": {
    it: "IP estratti da: catena SMTP (Received), X-Originating-IP, IP diretti negli URL, IP risolti via DNS",
    en: "IPs extracted from: SMTP chain (Received), X-Originating-IP, direct IPs in URLs, DNS-resolved IPs",
  },
  // Fonti URL — tooltip
  "rep.url_sources": {
    it: "URL estratti da: body email, link offuscati (href ≠ testo visibile)",
    en: "URLs extracted from: email body, obfuscated links (href ≠ visible text)",
  },

  // ── Analyst notes
  "summary.analyst_notes":   { it: "Note dell'Analista", en: "Analyst Notes" },
  "summary.notes_placeholder": {
    it: "Inserisci qui le osservazioni manuali: IOC aggiuntivi, contesto dell'incidente, decisioni prese...",
    en: "Enter manual observations here: additional IOCs, incident context, decisions made...",
  },
  "summary.notes_save":  { it: "Salva note", en: "Save notes" },
  "summary.notes_saved": { it: "✓ Salvato",  en: "✓ Saved" },

  // ── Campaigns
  "camp.title":         { it: "Campagne Rilevate", en: "Detected Campaigns" },
  "camp.description":   {
    it: "Raggruppa le email analizzate per rilevare campagne malevole coordinate.",
    en: "Groups analyzed emails to detect coordinated malicious campaigns.",
  },
  "camp.run_btn":       { it: "Analizza campagne", en: "Analyze campaigns" },
  "camp.rerun_btn":     { it: "↻ Ri-analizza", en: "↻ Re-analyze" },
  "camp.loading":       { it: "Ricerca cluster in corso…", en: "Searching for clusters…" },
  "camp.no_clusters":   { it: "Nessuna campagna rilevata tra le email analizzate.", en: "No campaigns detected among analyzed emails." },
  "camp.total":         { it: "{n} email analizzate", en: "{n} emails analyzed" },
  "camp.found":         { it: "{n} campagne trovate", en: "{n} campaigns found" },
  "camp.isolated":      { it: "{n} email isolate", en: "{n} isolated emails" },
  "camp.emails_in_cluster": { it: "{n} email", en: "{n} emails" },
  "camp.threshold":     { it: "Soglia similarità:", en: "Similarity threshold:" },
  "camp.first_seen":    { it: "Prima vista:", en: "First seen:" },
  "camp.last_seen":     { it: "Ultima vista:", en: "Last seen:" },
  "camp.common_value":  { it: "Valore comune:", en: "Common value:" },
  "camp.max_risk":      { it: "Rischio max:", en: "Max risk:" },
  "camp.type.subject":      { it: "Subject simile",          en: "Similar subject" },
  "camp.type.body_hash":    { it: "Body identico",           en: "Identical body" },
  "camp.type.message_id":   { it: "Message-ID pattern",      en: "Message-ID pattern" },
  "camp.type.campaign_id":  { it: "X-Campaign-ID",           en: "X-Campaign-ID" },
  "camp.type.sender_domain":{ it: "Dominio mittente",        en: "Sender domain" },

  // ── Language switcher ─────────────────────────────────────────────────────────
  "lang.it": { it: "Italiano", en: "Italian" },
  "lang.en": { it: "English", en: "English" },
}

export function createT(lang) {
  return function t(key, vars = {}) {
    const entry = translations[key]
    if (!entry) return key
    let text = entry[lang] || entry.it || key
    Object.entries(vars).forEach(([k, v]) => {
      text = text.replaceAll(`{${k}}`, String(v))
    })
    return text
  }
}