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
  "detail.reanalyze_btn": { it: "↻ Ri-analizza", en: "↻ Re-analyze" },
  "detail.reanalyzing": { it: "Ri-analisi in corso…", en: "Re-analyzing…" },
  "detail.reanalyze_hint": {
    it: "Rilancia l'analisi su questa email con le regole/campagne attuali (utile dopo aver creato o modificato una campagna nota). Note e controlli di reputazione già fatti non vengono persi.",
    en: "Re-runs the analysis on this email with the current rules/campaigns (useful after creating or editing a known campaign). Existing notes and reputation checks are preserved.",
  },
  "detail.reanalyze_error": { it: "Ri-analisi fallita", en: "Re-analysis failed" },
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
  "header.auth_absent_val": { it: "assente", en: "absent" },
  "header.auth_detail_client_ip":    { it: "Client IP",           en: "Client IP" },
  "header.auth_detail_envelope":     { it: "Envelope-From",       en: "Envelope-From" },
  "header.auth_detail_spf_dns":      { it: "Record SPF (DNS)",    en: "SPF record (DNS)" },
  "header.auth_detail_dkim_algo":    { it: "Algoritmo",           en: "Algorithm" },
  "header.auth_detail_dkim_canon":   { it: "Canonicalization",    en: "Canonicalization" },
  "header.auth_detail_dkim_headers": { it: "Header firmati",      en: "Signed headers" },
  "header.auth_detail_dkim_bh":      { it: "Body hash (bh=)",     en: "Body hash (bh=)" },
  "header.auth_detail_dkim_key":     { it: "Chiave DNS",          en: "DNS key" },
  "header.auth_detail_dkim_key_ok":  { it: "trovata",             en: "found" },
  "header.auth_detail_dkim_key_ko":  { it: "non trovata",         en: "not found" },
  "header.auth_detail_dmarc_from":   { it: "From domain",         en: "From domain" },
  "header.auth_detail_dmarc_policy": { it: "Policy (p=)",         en: "Policy (p=)" },
  "header.auth_detail_dmarc_sp":     { it: "Sottodomini (sp=)",   en: "Subdomain policy (sp=)" },
  "header.auth_detail_dmarc_adkim":  { it: "Allineamento DKIM",   en: "DKIM alignment" },
  "header.auth_detail_dmarc_aspf":   { it: "Allineamento SPF",    en: "SPF alignment" },
  "header.auth_detail_dmarc_pct":    { it: "Copertura (pct=)",    en: "Coverage (pct=)" },
  "header.auth_detail_dmarc_rua":    { it: "Report (rua=)",       en: "Report URI (rua=)" },
  "header.auth_detail_dmarc_dns":    { it: "Record DMARC (DNS)",  en: "DMARC record (DNS)" },
  "header.auth_detail_dns_error":    { it: "Errore DNS",          en: "DNS error" },
  "header.auth_detail_no_dns":       { it: "record non trovato",  en: "record not found" },
  "header.auth_detail_sig":          { it: "Firma",               en: "Signature" },
  "header.auth_detail_selector":     { it: "Selector DNS",        en: "DNS selector" },
  "header.auth_detail_failure_reason": { it: "Motivo",            en: "Reason" },
  "header.auth_detail_dkim_fail_key":  { it: "Chiave pubblica non trovata nel DNS", en: "Public key not found in DNS" },
  "header.auth_detail_dkim_fail_sig":  { it: "Verifica firma fallita", en: "Signature verification failed" },
  "header.spf_desc": {
    it: "Verifica che il server di invio sia autorizzato dal dominio dichiarato nel From (via DNS TXT record)",
    en: "Verifies that the sending server is authorized by the domain declared in From (via DNS TXT record)",
  },
  "header.dkim_desc": {
    it: "Verifica la firma crittografica dell'email: garantisce integrità del contenuto e autenticità del mittente",
    en: "Verifies the cryptographic signature of the email: ensures content integrity and sender authenticity",
  },
  "header.dmarc_desc": {
    it: "Policy del dominio mittente che definisce come gestire le email che falliscono SPF e/o DKIM",
    en: "Sender domain policy that defines how to handle emails that fail SPF and/or DKIM checks",
  },
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
    it: "scikit-learn non installato — installa con: pip install scikit-learn",
    en: "scikit-learn not installed — install with: pip install scikit-learn",
  },
  "body.nlp_top_features": { it: "Feature principali", en: "Top features" },

  "body.hidden_section": { it: "Contenuto HTML Nascosto", en: "Hidden HTML Content" },
  "body.hidden_count": { it: "{n} elementi nascosti tramite CSS", en: "{n} elements hidden via CSS" },
  "body.hidden_technique": { it: "Tecnica: {technique}", en: "Technique: {technique}" },
  "body.hidden_content_label": { it: "Testo nascosto estratto:", en: "Extracted hidden text:" },
  "body.hidden_evidence": { it: "Elementi nascosti tramite CSS o stili inline rilevati nel body HTML.", en: "Elements hidden via CSS or inline styles detected in HTML body." },
  "body.yes": { it: "Sì", en: "Yes" },
  "body.no": { it: "No", en: "No" },
  "body.campaign_detected": { it: "🎯 Campagna di Phishing Rilevata", en: "🎯 Known Campaign Detected" },
  "body.campaign_known_threat": { it: "Questa email corrisponde a una campagna di phishing nota. Rivedi con attenzione tutti gli indicatori.", en: "This email matches a known phishing campaign. Review all indicators carefully." },
  "body.language_mismatch": { it: "🌐 Disallineamento Linguistico Rilevato", en: "🌐 Language Mismatch Detected" },
  "body.language_mismatch_title": { it: "Lingua Inaspettata Rilevata", en: "Unexpected Language Detected" },
  "body.language_mismatch_desc": { it: "La lingua del corpo email non corrisponde alla lingua attesa dell'utente. Questo potrebbe indicare un account compromesso o una mailing non autorizzata.", en: "Email body language does not match expected user language. This may indicate a compromised account or unauthorized mailing." },
  "body.detected_language": { it: "Lingua rilevata", en: "Detected language" },

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
  "rep.service.circl_pdns":     { it: "CIRCL Passive DNS", en: "CIRCL Passive DNS" },

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
  // v0.17: rinominato in UI per disambiguare dal nuovo concetto di
  // "Campagne note" (pattern curati, sezione intel.known.*) — questo pannello
  // resta il clustering interno grezzo sul corpus dell'utente.
  "camp.title":         { it: "Cluster Simili", en: "Similar Clusters" },
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

  // ── Threat Intelligence (v0.17) ──────────────────────────────────────────
  "intel.title":            { it: "Threat Intelligence", en: "Threat Intelligence" },
  "intel.tab.feeds":        { it: "Feed IOC", en: "IOC Feeds" },
  "intel.tab.campaigns":    { it: "Campagne Note", en: "Known Campaigns" },
  "intel.tab.bulletins":    { it: "Bollettini CERT-AGID", en: "CERT-AGID Bulletins" },
  "intel.refresh_all":      { it: "Aggiorna tutto", en: "Refresh all" },
  "intel.refresh_one":      { it: "Aggiorna", en: "Refresh" },
  "intel.refreshing":       { it: "Aggiornamento…", en: "Refreshing…" },
  "intel.state.ok":            { it: "Aggiornato", en: "Up to date" },
  "intel.state.stale":         { it: "Obsoleto", en: "Stale" },
  "intel.state.unavailable":   { it: "Non disponibile", en: "Unavailable" },
  "intel.state.never_fetched": { it: "Mai scaricato", en: "Never fetched" },
  "intel.entries":          { it: "{n} voci", en: "{n} entries" },
  "intel.age":              { it: "{h}h fa", en: "{h}h ago" },
  "intel.needs_key":        { it: "Richiede API key non configurata", en: "Requires unconfigured API key" },
  "intel.error_prefix":     { it: "Errore:", en: "Error:" },
  "intel.token_hint": {
    it: "Le operazioni di scrittura da fuori localhost richiedono un token (vedi console di avvio o backend/data/admin_token).",
    en: "Write operations from outside localhost require a token (see startup console or backend/data/admin_token).",
  },

  // Campagne note — CRUD
  "intel.known.new":            { it: "+ Nuova campagna", en: "+ New campaign" },
  "intel.known.edit":           { it: "Modifica", en: "Edit" },
  "intel.known.delete":         { it: "Elimina", en: "Delete" },
  "intel.known.restore":        { it: "Ripristina versione di sistema", en: "Restore system version" },
  "intel.known.save":           { it: "Salva", en: "Save" },
  "intel.known.cancel":         { it: "Annulla", en: "Cancel" },
  "intel.known.source.builtin": { it: "Sistema", en: "Built-in" },
  "intel.known.source.user":    { it: "Personalizzata", en: "Custom" },
  "intel.known.source.local-learning": { it: "Auto-apprendimento", en: "Auto-learned" },
  "intel.known.overridden":     { it: "Override utente attivo", en: "User override active" },
  "intel.known.field.id":        { it: "ID (es. brand-2026)", en: "ID (e.g. brand-2026)" },
  "intel.known.field.name":      { it: "Nome", en: "Name" },
  "intel.known.field.keywords":  { it: "Keyword (una per riga)", en: "Keywords (one per line)" },
  "intel.known.field.required_keywords": { it: "Keyword obbligatorie (opzionale)", en: "Required keywords (optional)" },
  "intel.known.field.risk":      { it: "Peso rischio (0-50)", en: "Risk weight (0-50)" },
  "intel.known.field.enabled":   { it: "Attiva", en: "Enabled" },
  "intel.known.field.description": { it: "Descrizione", en: "Description" },
  "intel.known.field.reference_url": { it: "Link di riferimento", en: "Reference link" },
  "intel.known.empty":           { it: "Nessuna campagna nota configurata.", en: "No known campaigns configured." },
  "intel.known.delete_confirm":  { it: "Eliminare questa campagna personalizzata?", en: "Delete this custom campaign?" },

  // Placeholder di esempio nel form (aiutano l'analista a capire il formato atteso)
  "intel.known.placeholder.id":       { it: "es. banca-esempio-2026", en: "e.g. example-bank-2026" },
  "intel.known.placeholder.name":     { it: "es. Phishing Banca Esempio 2026", en: "e.g. Example Bank Phishing 2026" },
  "intel.known.placeholder.keywords": {
    it: "es.\nbanca esempio\nverifica account\naccesso sospetto\nconferma identità\nblocco carta",
    en: "e.g.\nexample bank\nverify account\nsuspicious access\nconfirm identity\ncard blocked",
  },
  "intel.known.placeholder.required_keywords": { it: "es. banca esempio", en: "e.g. example bank" },
  "intel.known.placeholder.description": {
    it: "es. Email che imitano comunicazioni di Banca Esempio, chiedendo di verificare l'account tramite un link a un sito clone.",
    en: "e.g. Emails impersonating Example Bank, asking to verify the account via a link to a cloned site.",
  },
  "intel.known.placeholder.reference_url": { it: "es. https://cert-agid.gov.it/news/...", en: "e.g. https://cert-agid.gov.it/news/..." },

  // Micro-suggerimenti sotto i campi più delicati
  "intel.known.hint.id": {
    it: "Solo minuscole, cifre e trattino, 3-64 caratteri. Non modificabile dopo la creazione.",
    en: "Lowercase letters, digits and hyphen only, 3-64 characters. Not editable after creation.",
  },
  "intel.known.hint.keywords": {
    it: "La campagna scatta se una parte sufficiente di queste keyword compare nel testo dell'email (soglia proporzionale automatica). Preferisci termini specifici del brand a parole generiche come \"pagamento\" o \"urgente\".",
    en: "The campaign fires when enough of these keywords appear in the email text (automatic proportional threshold). Prefer brand-specific terms over generic words like \"payment\" or \"urgent\".",
  },
  "intel.known.hint.required_keywords": {
    it: "Se compili questo campo, la campagna scatta SOLO se almeno una di queste è presente — utile per ancorare il match al brand ed evitare falsi positivi.",
    en: "If filled in, the campaign only fires when at least one of these is present — useful to anchor the match to the brand and avoid false positives.",
  },
  "intel.known.hint.risk": {
    it: "Punti aggiunti al rischio dell'email in caso di match. 25 = soglia standard per phishing di brand; 40-50 = campagne malware/APT più pericolose.",
    en: "Points added to the email's risk score on a match. 25 = standard threshold for brand phishing; 40-50 = more dangerous malware/APT campaigns.",
  },

  // Mini-guida collassabile
  "intel.known.guide.toggle": { it: "Come compilare questo form", en: "How to fill in this form" },
  "intel.known.guide.id": {
    it: "un identificativo univoco e stabile per questa campagna, es. \"brand-2026\".",
    en: "a unique, stable identifier for this campaign, e.g. \"brand-2026\".",
  },
  "intel.known.guide.keywords": {
    it: "le parole/frasi che il sistema cerca nel testo dell'email. Più sono specifiche del brand, meno falsi positivi genereranno.",
    en: "the words/phrases the system looks for in the email text. The more brand-specific they are, the fewer false positives they'll generate.",
  },
  "intel.known.guide.required_keywords": {
    it: "opzionale, ma consigliato: almeno una di queste deve essere presente perché la campagna scatti.",
    en: "optional but recommended: at least one of these must be present for the campaign to fire.",
  },
  "intel.known.guide.risk": {
    it: "quanto pesa un match sul punteggio di rischio finale dell'email (scala 0-50).",
    en: "how much a match weighs on the email's final risk score (0-50 scale).",
  },
  "intel.known.guide.backtest_tip": {
    it: "Esegui sempre il backtest prima di salvare: ti mostra subito se le keyword catturano email che dovrebbero essere considerate innocue.",
    en: "Always run the backtest before saving: it immediately shows whether the keywords catch emails that should be considered harmless.",
  },

  // Backtest
  "intel.backtest.title":        { it: "Backtest sul corpus", en: "Backtest against corpus" },
  "intel.backtest.run":          { it: "Esegui backtest", en: "Run backtest" },
  "intel.backtest.running":      { it: "Analisi in corso…", en: "Analyzing…" },
  "intel.backtest.coverage":     { it: "Copertura:", en: "Coverage:" },
  "intel.backtest.matched":      { it: "{n} email matcherebbero", en: "{n} emails would match" },
  "intel.backtest.false_positive_warning": {
    it: "⚠ {n} delle email matchate hanno rischio basso — probabili falsi positivi. Rivedi le keyword prima di salvare.",
    en: "⚠ {n} of the matched emails are low-risk — likely false positives. Review keywords before saving.",
  },
  "intel.backtest.ok": { it: "✓ Nessun falso positivo evidente sul corpus disponibile.", en: "✓ No obvious false positives on the available corpus." },

  // Bollettini CERT-AGID
  "intel.bulletins.description": {
    it: "Bacheca di bollettini pubblici CERT-AGID a tema phishing. Le keyword non vengono mai generate automaticamente: crea la campagna a mano partendo dallo spunto.",
    en: "Board of public CERT-AGID phishing bulletins. Keywords are never auto-generated: create the campaign by hand starting from the lead.",
  },
  "intel.bulletins.create_from": { it: "Crea campagna da questo bollettino", en: "Create campaign from this bulletin" },
  "intel.bulletins.empty":       { it: "Nessun bollettino recente a tema phishing.", en: "No recent phishing-related bulletins." },
  "intel.bulletins.source_note": { it: "Fonte: cert-agid.gov.it — solo titolo, data e link, mai il testo integrale.", en: "Source: cert-agid.gov.it — title, date and link only, never the full text." },

  // Proposte auto-apprendimento (Wave 9)
  "intel.proposals.title":       { it: "Proposte auto-generate", en: "Auto-generated proposals" },
  "intel.proposals.generate":    { it: "Cerca nuovi pattern", en: "Search for new patterns" },
  "intel.proposals.empty":       { it: "Nessuna proposta in attesa di revisione.", en: "No proposals pending review." },
  "intel.proposals.approve":     { it: "Approva → apri form", en: "Approve → open form" },
  "intel.proposals.reject":      { it: "Rifiuta", en: "Reject" },
  "intel.proposals.stale":       { it: "Obsoleta (email di riferimento cancellate)", en: "Stale (referenced emails deleted)" },
  "intel.proposals.seen_count":  { it: "Osservata {n} volte", en: "Seen {n} times" },

  // ── Language switcher ─────────────────────────────────────────────────────────
  "lang.it": { it: "Italiano", en: "Italian" },
  "lang.en": { it: "English", en: "English" },

  // ── App credits ───────────────────────────────────────────────────────────────
  "app.credits": { it: "Sviluppato da Graziano Mariella", en: "Developed by Graziano Mariella" },
  "app.license": { it: "Distribuito con licenza MIT",     en: "Distributed under the MIT license" },

  // ── Table column # ────────────────────────────────────────────────────────────
  "col.num": { it: "#", en: "#" },

  // ── Pagination ────────────────────────────────────────────────────────────────
  "filter.per_page": { it: "per pagina", en: "per page" },
  "filter.first":    { it: "«", en: "«" },
  "filter.last":     { it: "»", en: "»" },

  // ── Actions ───────────────────────────────────────────────────────────────────
  "action.delete":         { it: "Elimina analisi", en: "Delete analysis" },
  "action.delete_confirm": {
    it: "Eliminare l'analisi '{subject}'? Verranno rimossi anche i file associati.",
    en: "Delete analysis '{subject}'? Associated files will also be removed.",
  },
  "action.select_all":     { it: "Seleziona tutto", en: "Select all" },
  "action.deselect_all":   { it: "Deseleziona tutto", en: "Deselect all" },
  "action.delete_selected": { it: "Elimina selezionati", en: "Delete selected" },
  "action.selected_count": { it: "{n} selezionati", en: "{n} selected" },
  "action.bulk_delete_confirm": {
    it: "Eliminare {n} analisi selezionate? Verranno rimossi anche i file associati. L'operazione non è reversibile.",
    en: "Delete {n} selected analyses? Associated files will also be removed. This action cannot be undone.",
  },
  "action.bulk_delete_success": { it: "{n} analisi eliminate", en: "{n} analyses deleted" },
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
