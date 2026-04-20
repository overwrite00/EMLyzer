# Changelog

Tutte le modifiche significative al progetto sono documentate in questo file.
Il formato segue [Keep a Changelog](https://keepachangelog.com/it/1.0.0/).

---

## [Unreleased] — Roadmap

Questa sezione raccoglie tutto ciò che è pianificato ma non ancora implementato.
Le funzionalità sono ordinate per priorità di implementazione.
Ogni voce passa a una sezione con numero di versione quando viene completata.

### Reputazione — nuovi servizi (priorità alta)

- [x] **CIRCL Passive DNS** — storico risoluzione DNS per IP e domini; gratuito con registrazione *(v0.11.0)*
- [x] **GreyNoise Community** — distingue scanner innocui da attori malevoli, riduce falsi positivi; free tier 100 req/g *(v0.12.0)*
- [x] **URLScan.io** — analisi completa URL con screenshot; free tier 100 req/h *(v0.12.0)*
- [x] **Pulsedive** — threat intel aggregata su IP/URL/domini; free tier 30 req/min *(v0.12.0)*
- [x] **Criminal IP** — threat score IP con geolocalizzazione; free tier *(v0.12.0)*
- [x] **SecurityTrails** — DNS attuale e storico per domini; 50 req/mese free *(v0.12.0)*
- [x] **Hybrid Analysis** — analisi statica avanzata hash allegati; gratuito con registrazione *(v0.12.0)*

### Header analysis (priorità media)

- [ ] **List-Unsubscribe** — analisi link di unsubscribe (dominio diverso dal mittente, URL sospetti)
- [ ] **X-Campaign-ID** — analisi del campo già estratto: correlazione campagne bulk, pattern sospetti
- [ ] **ARC chain** (Authenticated Received Chain) — rilevante per phishing via account compromessi e forwarding

### Body analysis (priorità media)

- [ ] **Rilevamento errori grammaticali** — integrazione LanguageTool (locale o API) per testi tradotti/generati automaticamente
- [ ] **Logistic regression NLP** — miglioramento classificatore attuale (Naive Bayes); migliore calibrazione probabilità
- [ ] **Dataset Enron/Nazario** — riaddestramento modello NLP con dataset pubblici per migliorare la generalizzazione
- [ ] **Omoglifi e Unicode spoofing** — rilevamento caratteri Unicode visivamente identici a caratteri latini nel testo (es. `а` cirillica)

### Report (priorità media)

- [ ] **Sezione Campagne nel .docx** — la sezione Campagne Rilevate esiste nella UI ma non viene inclusa nel report Word generato

### Infrastruttura (priorità bassa)

- [ ] **PostgreSQL** — supporto database alternativo a SQLite per deployment multi-utente
- [ ] **Sistema plugin** — architettura modulare per aggiungere connettori e analizzatori senza modificare il core
- [ ] **Regole YARA** — rilevamento pattern negli allegati tramite regole YARA personalizzabili
- [ ] **Integrazione SIEM** — export in formato compatibile con SIEM (CEF, JSON strutturato, syslog)
- [ ] **Sandbox esterna opzionale** — invio allegati a servizi sandbox (Cuckoo, Any.run) come plugin opzionale

---

## [0.12.0] — 2026-04-20

### Aggiunto
- **GreyNoise Community**: classifica IP come `malicious`, `benign` o `unknown`. Distingue scanner innocui (crawlers, ricercatori) da attori malevoli, riducendo i falsi positivi. Richiede `GREYNOISE_API_KEY` (100 req/g free). Fase FAST.
- **URLScan.io**: ricerca scansioni esistenti per URL/domini nel database urlscan.io. Mostra verdetto, score e tag dell'ultima scansione disponibile. `URLSCAN_API_KEY` opzionale (ricerca pubblica disponibile anche senza chiave). Fase FAST.
- **Pulsedive**: threat intel aggregata per IP e URL. Risk level `none`/`low`/`medium`/`high`/`critical` con risk factors dettagliati. Richiede `PULSEDIVE_API_KEY` (30 req/min free). Fase FAST.
- **Criminal IP**: score rischio IP 0-4 (Safe/Low/Medium/High/Critical) con geolocalizzazione. Richiede `CRIMINALIP_API_KEY` (free tier). Fase FAST.
- **SecurityTrails**: DNS attuale per domini — record A, MX, NS. Servizio informativo (icona ℹ️, come ASN Lookup e Shodan). Richiede `SECURITYTRAILS_API_KEY` (50 req/mese free). Fase FAST.
- **Hybrid Analysis** (CrowdStrike Falcon): ricerca hash allegati nel database sandbox. `threat_level` 0-2 (no threat/suspicious/malicious) con verdict, tipo file e tag. Richiede `HYBRID_ANALYSIS_API_KEY` (gratuito con registrazione). Fase FAST.

---

## [0.11.0] — 2026-04-19

### Aggiunto
- **CIRCL Passive DNS**: nuovo servizio reputazione informativo per IP e domini. Interroga `pdns.circl.lu` per lo storico di risoluzione DNS: per un IP mostra i domini che vi hanno puntato storicamente; per un dominio mostra gli IP a cui ha risolto e i record A/AAAA/MX/NS/CNAME. Gratuito con registrazione (CIRCL_API_KEY in formato `username:password`). Fase FAST, classificato come informativo (icona ℹ️ nel frontend, come ASN Lookup e Shodan InternetDB).

---

## [0.10.3] — 2026-04-18

### Aggiunto
- **Localizzazione script di avvio**: `start.sh`, `start.bat`, `run_tests.sh` e `run_tests.bat` rilevano automaticamente la lingua del sistema operativo (Windows UI culture / `$LANG`) e mostrano tutti i messaggi in italiano o in inglese. Nessuna modifica al file `.env` necessaria.
- **Completamento i18n API backend**: tutti gli endpoint FastAPI (`upload`, `analysis`, `report`, `reputation`, `settings`) usano ora `t()` da `utils/i18n.py` invece di stringhe hardcoded in italiano. Le risposte di errore rispettano il parametro `LANGUAGE` del file `.env`.

### Aggiornato
- **python-multipart 0.0.26** (da 0.0.22): compatibile con FastAPI 0.135.2 e Starlette 1.0.0 (`>=0.0.18`).

---

## [0.10.2] — 2026-04-14

### Sicurezza
- **pytest aggiornato a 9.0.3** (da 9.0.2): fix privilege escalation su UNIX via directory `/tmp/pytest-of-{user}` con permessi scrivibili da altri utenti locali (Dependabot alert #10, GHSA-jfh8-c2jp-jmjq)
- **follow-redirects aggiornato a 1.16.0** (da 1.15.11): fix leak di header di autenticazione personalizzati verso host cross-domain durante redirect HTTP; dipendenza transitiva di axios nel frontend (Dependabot alert #11, CVE-2025-46566)

---

## [0.10.1] — 2026-04-13

### Corretto
- **Timeout analisi su email con molti URL**: email con 40+ URL (es. newsletter HTML con immagini CDN da paypalobjects.com) causavano timeout di 60s nel frontend perché la query WHOIS veniva eseguita per ogni URL invece che per dominio unico. Con 42 URL dallo stesso dominio `paypalobjects.com` venivano eseguite 42 query WHOIS identiche (8s ognuna). Aggiunta cache WHOIS pre-calcolata per dominio unico in `analyze_urls()`: il tempo passa da 60s+ a ~12-15s (7 query invece di 42 per l'email di test)
- **Timeout frontend per `runAnalysis` e `analyzeManual`**: aumentato da 60s a 300s nel bundle e in `client.js` per garantire che email complesse completino l'analisi senza errore "timeout of 60000ms exceeded"

---

## [0.10.0] — 2026-04-13

### Aggiunto
- **Visualizzazione contenuto email nel tab Body**: nuova sezione "Contenuto email" che mostra il testo plain-text dell'email nello stesso stile della sezione "HTML nascosto" (sfondo scuro, font mono, scroll a 300px); caricato dinamicamente via `GET /api/analysis/{id}/body`
- **Anteprima HTML sicura nel tab Body**: nuova sezione "Anteprima HTML" con toggle espandi/comprimi che renderizza il corpo HTML dell'email in un `<iframe sandbox="" referrerPolicy="no-referrer">` con contenuto sanitizzato; i link sono disabilitati (`href="#"`, `pointer-events:none`), le immagini sostituite con GIF 1×1 trasparente, il CSS inline filtrato con allowlist di proprietà sicure
- **Endpoint `GET /api/analysis/{job_id}/body`**: nuovo endpoint che ri-parsa il file email caricato e restituisce `body_text` (max 50.000 caratteri) e `body_html_sanitized` (HTML sanitizzato pronto per iframe srcdoc)
- **`_sanitize_email_html()`**: helper di sanitizzazione con bleach (allowlist tag), `CSSSanitizer` con allowlist proprietà CSS, sostituzione img src con placeholder GIF, disabilitazione href, wrapper HTML con CSP `default-src 'none'`
- **Dipendenza `tinycss2`**: aggiunta a `requirements.txt` per supportare `bleach.css_sanitizer.CSSSanitizer` e filtrare il CSS inline in modo sicuro (fix `NoCssSanitizerWarning`)

---

## [0.9.4] — 2026-04-12

### Corretto
- **Servizi reputazione bloccati "in elaborazione"**: quando `_extract_priority_indicators()` non trova indicatori SLOW (nessun IP da `received_hops`, nessun URL sospetto), i placeholder creati da `run_fast_checks()` per AbuseIPDB/VirusTotal/crt.sh venivano salvati nel DB con `reputation_phase=complete` senza essere rimossi. Aggiunta `finalize_fast_only()` che pulisce i placeholder e ricalcola il `service_registry` prima del salvataggio → i servizi mostrano correttamente "➖ Non applicabile" anziché restare bloccati in "⏳ In elaborazione"

### Aggiunto
- **Cache su disco per Spamhaus DROP e OpenPhish**: i feed locali vengono salvati in `backend/data/cache/` con TTL 24h (Spamhaus) e 12h (OpenPhish); all'avvio successivo vengono letti da disco senza ri-scaricare; se il download fallisce ma esiste una cache scaduta viene usata come fallback
- **Diagnostica indicatori analizzati**: il campo `slow_indicators` viene ora incluso in `reputation_results`; il tab Reputazione mostra gli IP/URL/hash passati ai servizi avanzati, oppure un avviso "Nessun indicatore ad alta priorità" quando i servizi avanzati non vengono attivati

---

## [0.9.3] — 2026-04-11

### Sicurezza
- **urllib3 2.6.0 → 2.6.3**: fix CVE decompression-bomb bypass when following HTTP redirects (streaming API); versione 2.6.0 non sufficiente per questo alert
- **axios ^1.13.6 → ^1.15.0**: fix due CVE CRITICAL (cloud metadata header injection + NO_PROXY SSRF); entrambe non applicabili nel contesto browser-only di EMLyzer, ma constraint aggiornato per chiudere gli alert GitHub

---

## [0.9.2] — 2026-04-11

### Sicurezza
- **urllib3 2.5.0 → 2.6.0**: fix CVE unbounded decompression chain e streaming decompression DoS (CWE-409); la libreria è dipendenza transitiva di `requests` usato nei connettori reputazione
- **vite ^8.0.1 → ^8.0.5**: fix CVE `server.fs.deny` bypass e `.map` traversal nel dev server (impatto solo sviluppo, non produzione)
- **axios**: analizzato — NON vulnerabile nel contesto EMLyzer (uso browser-only, `NO_PROXY` è variabile Node.js non applicabile al browser)

---

## [0.9.1] — 2026-04-10

### Corretto
- **Encoding soggetti con byte UTF-8 grezzi**: aggiunto `_decode_header_raw_fallback()` — quando `compat32` produce U+FFFD per header con byte non-ASCII non-RFC2047 (es. `ü` come `\xc3\xbc` diretto), il parser legge i byte grezzi dell'header e decodifica come UTF-8 poi Windows-1252; si applica a tutti gli header (`Subject`, `From`, `To`, ecc.) e al dizionario `raw_headers`

---

## [0.9.0] — 2026-04-10

### Aggiunto
- **Eliminazione massiva analisi**: selezione multipla con checkbox nella lista analisi; barra azioni flottante con conteggio, eliminazione selezionati e deselezione; limite 100 analisi per richiesta
- **Endpoint `POST /api/analysis/bulk-delete`**: elimina più analisi in una singola richiesta (DB + file email + report .docx)
- **Pulizia file su eliminazione singola**: l'endpoint `DELETE /api/analysis/{job_id}` ora rimuove anche il file `.eml`/`.msg` da `uploads/` e il report `.docx` da `reports/`

### Corretto
- **Encoding header multi-valore**: `get_headers()` nel parser ora decodifica correttamente gli encoded-words RFC 2047 (prima restituivano token grezzi `=?...?=`)
- **Serializzazione JSON non-ASCII**: aggiunto `ensure_ascii=False` a `_dataclass_to_dict()` per preservare emoji e caratteri accentati nella risposta API
- **Raw headers con surrogate escapes**: il dizionario `raw_headers` ora gestisce i byte UTF-8 grezzi della policy compat32 senza produrre caratteri corrotti

---

## [0.8.2] — 2026-04-08

### Fixed
- **Email subject encoding**: decodifica RFC 2047 riscritta con fallback graceful per emoji, charset esotici e caratteri non-ASCII (UTF-8 → Latin-1 → Windows-1252); sostituisce `make_header()` che lanciava eccezioni su charset misti
- **Raw UTF-8 headers**: aggiunto surrogate-escape recovery in `_decode_rfc2047` — gestisce header con byte UTF-8 grezzi (senza wrapper `=?...?=`) che la policy `compat32` di Python codifica come surrogates; fix per soggetti come `cartão` che venivano mostrati come `cart??o`
- **To/CC header decoding**: anche i campi To e CC ora decodificano correttamente gli encoded-words RFC 2047
- **Allineamento colonne tabella**: aggiunto `gap: 8` all'intestazione della tabella analisi, che mancava rispetto alle righe dati causando disallineamento visivo
- **NaN in colonna `#`**: rimossa iniezione errata del div numero-riga nel componente `AnalysisDetail`; il div corretto rimane nel map della lista analisi

---

## [0.8.1] — 2026-04-08

### Corretto
- **DELETE rimuoveva file fisici**: l'endpoint `DELETE /api/analysis/{job_id}` cancellava anche il file `.eml`/`.msg` da `uploads/` e il report `.docx` da `reports/`. Comportamento corretto: si elimina solo il record DB; i file fisici restano per poter essere rianalizzati
- **WHOIS disabilitato per default nella UI**: il checkbox WHOIS in UploadZone era impostato a `false` anziché `true`; il backend aveva già il default corretto (`do_whois=True`)
- **Import fuori ordine in `analysis.py`**: gli import SQLAlchemy erano collocati dopo la definizione di `NotesUpdate`; spostati in cima al file
- **Import prima del docstring in `attachment_analyzer.py`**: `from utils.i18n import t` era la prima riga del file, prima del docstring di modulo; spostato dopo

---

## [0.8.0] — 2026-04-08

### Aggiunto
- **Crediti sviluppatore**: footer discreto in fondo alla home page con "Sviluppato da Graziano Mariella · Distribuito con licenza MIT"
- **Colonna numerazione `#`**: la lista analisi mostra ora il numero riga assoluto (basato sulla pagina corrente) nella prima colonna
- **Paginazione migliorata**: aggiunto selettore "email per pagina" (10/25/50/100) accanto ai filtri; aggiunta navigazione rapida con pulsanti prima pagina `«` e ultima pagina `»` oltre ai già presenti `← Prec` e `Succ →`
- **WHOIS abilitato di default**: `do_whois=True` in `url_analyzer.py`, `analysis.py` e nei client `runAnalysis`/`analyzeManual`
- **Eliminazione analisi**: pulsante 🗑 per riga nella lista; al clic mostra conferma e rimuove il record dal DB; se l'analisi eliminata è quella aperta in dettaglio, il pannello si chiude automaticamente
- **Endpoint `DELETE /api/analysis/{job_id}`**: rimuove il record da SQLite (i file fisici restano in `uploads/` e `reports/`)

---

## [0.7.0] — 2026-04-07

### Corretto
- **Versione frontend errata**: `start.bat` aveva la versione fallback hardcoded a `0.6.1`; aggiornata a `0.7.0`
- **ThreatFox `illegal_search_term`**: lo status restituito da ThreatFox per URL con formato non riconosciuto veniva mostrato come `Status: illegal_search_term` invece di essere trattato come "non trovato". Aggiunto alla lista dei casi non-malevoli insieme a `no_result` (variante singolare di `no_results`)
- **ThreatFox `no_result`**: variante singolare del campo `query_status` ora gestita come `no_results`

### Aggiunto
- **Motivo fallimento SPF/DKIM/DMARC**: quando un controllo non passa, la sezione di dettaglio mostra ora una riga "Motivo" che spiega il perché:
  - **SPF**: testo estratto dalla parentesi in `Authentication-Results` o `Received-SPF` (es. "domain of user@bad.com does not designate 1.2.3.4 as permitted sender")
  - **DKIM**: "Verifica firma fallita" quando la chiave DNS esiste ma la firma è invalida; se la chiave è assente il motivo è già evidente dalla riga DNS key (✗ non trovata); testo da parentesi `Authentication-Results` (es. "bad signature") se disponibile
  - **DMARC**: sintesi degli allineamenti falliti (es. "Allineamento fallito: SPF=fail, DKIM=fail")
  - 3 nuovi campi in `AuthDetail`: `spf_failure_reason`, `dkim_failure_reason`, `dmarc_failure_reason`
  - 3 nuove chiavi di traduzione it/en: `header.auth_detail_failure_reason`, `header.auth_detail_dkim_fail_key`, `header.auth_detail_dkim_fail_sig`

### Aggiunto (dalla sessione precedente)
- **SPF/DKIM/DMARC verboso con verifica DNS indipendente**: la sezione Autenticazione mostra ora tutti i sotto-campi di ciascun protocollo, analoghi a quelli di MXToolbox
  - **SPF**: client IP, Envelope-From, record TXT DNS (`v=spf1 …`) con query live su `dnspython`
  - **DKIM**: per ogni firma `DKIM-Signature` — selettore, algoritmo, canonicalization, header firmati, body hash (bh=), esistenza chiave pubblica DNS (`selector._domainkey.domain`)
  - **DMARC**: From domain, policy (p=) con codifica colore (reject=verde, quarantine=arancione, none=grigio), sp=, adkim=, aspf=, pct=, rua=, record TXT DNS (`v=DMARC1 …`)
  - La verifica DNS è **sempre attiva** (non opzionale) con timeout 2s/query: 3–5 query per email, max ~3s totali
  - Rileva contraddizioni tra `Authentication-Results` e DNS reali (utile contro header `spf=pass` contraffatti)
  - Tutti i dati memorizzati automaticamente in `header_indicators.auth_detail` (JSON) — nessun cambio schema DB
- **Nuovo dataclass `AuthDetail`** in `header_analyzer.py`: 16 campi strutturati per SPF/DKIM/DMARC, serializzato da `_dataclass_to_dict()`
- **Parsing `DKIM-Signature`**: `email_parser.py` ora raccoglie tutti gli header `DKIM-Signature` presenti nell'email (campo `dkim_signatures_raw`) e il primo `Received-SPF` grezzo
- **Fix bug `Received-SPF`**: regex precedente `r"=(\S+)"` con keyword vuota matchava il primo `=` qualsiasi; sostituito con `r"^(\w+)"` che estrae correttamente il primo token (pass/fail/softfail)
- **23 nuove chiavi di traduzione** it/en per tutti i sotto-campi auth (`header.auth_detail_*`)
- **UI aggiornata**: ogni riga SPF/DKIM/DMARC nel tab Header espone i sotto-campi in una griglia compatta sempre visibile (no click) con label + valore monospaciato

---

## [0.6.1] — 2026-04-06

### Corretto
- **URLhaus e ThreatFox richiedono API key**: abuse.ch ha reso obbligatoria l'autenticazione per tutti i propri servizi (stessa ondata di MalwareBazaar, fase completata a giugno 2025). Entrambi i connettori restituivano HTTP 401. Aggiunta chiave unificata `ABUSECH_API_KEY` che copre URLhaus, ThreatFox **e** MalwareBazaar (stesso portale `auth.abuse.ch`, gratuito). Header `Auth-Key` aggiunto alle chiamate HTTP. Senza chiave i servizi mostrano correttamente stato `skipped` (🔑) invece di errore 401
- **Retrocompatibilità MalwareBazaar**: `MALWAREBAZAAR_API_KEY` ancora accettata come fallback; i nuovi utenti devono usare solo `ABUSECH_API_KEY`
- `ServicePreview` e `_build_service_registry` aggiornati: URLhaus e ThreatFox ora classificati come `requires_key: true`

---

## [0.6.0] — 2026-04-06

### Aggiunto
- **Shodan InternetDB** — nuovo servizio reputazione IP (fase FAST): porte aperte, CVE, tag e hostname per ogni IP pubblico estratto dall'email. Gratuito, no API key, endpoint JSON pubblico `https://internetdb.shodan.io/{ip}`. Classificato come servizio informativo (ℹ️) nella UI e nel report .docx; segnala come malevolo se i tag includono `malware`, `c2`, `compromised`, `botnet`
- **Abuse.ch URLhaus** — nuovo servizio reputazione URL (fase FAST): controlla ogni URL nel database URLhaus di abuse.ch. Gratuito, no API key. Segnala URL attivi come `malware_download` o con status `online` con confidence 95%. Stesso ecosistema di MalwareBazaar
- **ThreatFox** (abuse.ch) — nuovo servizio reputazione multi-tipo (fase FAST): controlla IP, URL e hash SHA256 nel database IOC di ThreatFox. Gratuito, no API key. Riporta nome malware, tipo minaccia e livello di confidenza per ogni IOC trovato. Tre connettori distinti: `check_ip_threatfox`, `check_url_threatfox`, `check_hash_threatfox`
- Totale servizi reputazione: da 9 a 12

---

## [0.5.0] — 2026-04-03

### Corretto
- Shutdown CTRL+C su Linux con Python 3.13: `loop._default_executor` non esiste su alcune implementazioni del loop asyncio (variante C di CPython 3.13, uvloop). Sostituito con `getattr(loop, "_default_executor", None)` che restituisce `None` invece di sollevare `AttributeError`, con blocco `try/except` aggiuntivo per sicurezza. Su Windows il comportamento rimane invariato

---

## [0.4.9] — 2026-04-03

### Migliorato
- `scorer.py`: floor deterministici estesi ad allegati e body (`_compute_floors` ora riceve anche `attachment_result`)
  - Allegato con finding **HIGH** (macro VBA, MIME mismatch) → score ≥ 25 (MEDIUM), indipendentemente da header e body
  - Allegato con finding **CRITICAL** (eseguibile camuffato, macro in PDF) → score ≥ 40
  - Body con 2+ finding HIGH indipendenti (form nascosto + JS + NLP) → score ≥ 30
  - Prima questi casi ricadevano in LOW perché il peso allegati (10%) non era sufficiente da solo

---

## [0.4.8] — 2026-04-03

### Modificato
- `scorer.py`: algoritmo di scoring riscritto con **normalizzazione adattiva** e **floor deterministici** (issue GitHub)
  - **Normalizzazione adattiva**: il punteggio è calcolato dividendo per la somma dei pesi dei soli moduli con contenuto rilevante (header e body sempre; url solo se l'email ha URL; allegati solo se ha allegati). Prima i moduli assenti abbassavano artificialmente il punteggio: un'email con header falsificati e NLP al 53% otteneva 10/100 LOW invece di MEDIUM
  - **Pesi rivisti**: header=0.35, body=0.35, url=0.20, attachment=0.10 — header e body pesano di più perché sempre presenti e più affidabili per il phishing
  - **Floor deterministici**: soglie minime garantite in presenza di indicatori critici: 1 finding HIGH header → ≥20; HIGH header + NLP≥50% → ≥35; 3+ finding HIGH → ≥45; URL risk≥75 → ≥20
  - Caso della issue: email con mismatch From/Return-Path (HIGH) + NLP 53% (MEDIUM) ora classificata MEDIUM 35/100 invece di LOW 10/100

---

## [0.4.7] — 2026-04-03

### Migliorato
- `email_parser.py`: parsing di SPF/DKIM/DMARC ora robusto su email con header `Authentication-Results` multipli (un header per ogni MTA intermedio). Aggiunto helper `get_headers()` basato su `msg.get_all()`. Rinominata `_extract_auth_result(str)` in `_extract_auth_results(list[str])` che legge `values[-1]` — l'ultimo header aggiunto, cioè quello del server di ricezione finale, che è il più affidabile per la verifica di autenticità. ([proposta GitHub](https://github.com))

---

## [0.4.6] — 2026-04-03

### Corretto
- **Banner API key prima dell'analisi**: `ServicePreview` ora carica lo stato reale da `GET /api/settings/reputation_keys` via `useEffect` al mount — non dipende più dal `service_registry` (assente prima dell'analisi). Tutti i servizi con chiave mostrano "API key configurata" o "API key non configurata" in base al file `.env` effettivo
- **Scheda Reputazione non si aggiornava**: `GET /api/analysis/{job_id}` non includeva `reputation_results` nella risposta — il polling del frontend riceveva una struttura senza dati di reputazione e non poteva mai rilevare `reputation_phase === 'complete'`. Aggiunto `reputation_results: record.reputation_results` in `_build_response_from_record`
- **SQLAlchemy JSON mutation**: aggiunto `flag_modified(record, "reputation_results")` prima di ogni `commit()` che modifica il campo JSON, per forzare SQLAlchemy a tracciare la modifica con SQLite
- Background task usa `asyncio.get_running_loop()` invece di `get_event_loop()` (deprecato in Python 3.10+)
- Polling intervallo ridotto da 8s a 5s; in caso di errore background viene comunque salvato `reputation_phase="complete"` per fermare il polling

---

## [0.4.5] — 2026-04-02

### Corretto
- AbuseIPDB e VirusTotal mostravano "Non applicabile" invece di "In elaborazione": `slow_skips` in `run_fast_checks` generava nomi errati (`"Ip Abuseipdb"`, `"Ip Virustotal"`) che `_build_service_registry` non riconosceva. Aggiunta mappa `_FN_TO_SOURCE` con i nomi corretti (`"AbuseIPDB"`, `"VirusTotal"`, `"crt.sh"`). Stesso bug nella pulizia dei placeholder in `run_slow_checks`
- Aggiunto stato `"pending"` (⏳) per i servizi SLOW in elaborazione background, distinto da `"not_applicable"` (➖) per i servizi non pertinenti
- `_build_service_registry` ora riconosce `skip_reason` contenente "in elaborazione" e assegna stato `pending` invece di `not_applicable`

---

## [0.4.4] — 2026-04-02

### Corretto
- Polling infinito: il frontend confrontava `reputation_results` (sempre presente dalla fase 1) invece di un campo dedicato; aggiunto `reputation_phase` ("fast" / "complete") nel JSON salvato nel DB — il polling si ferma solo quando la fase 2 ha completato o non aveva entità da processare
- Scheda Reputazione non si aggiornava con i risultati di AbuseIPDB/VirusTotal: conseguenza diretta del polling infinito che non riconosceva il completamento
- Messaggio "Non applicabile" per AbuseIPDB/VirusTotal con chiave configurata ma email senza IP pubblici: testo cambiato da "nessun IP nei Received header" a "nessun IP pubblico in questa email"

---

## [0.4.3] — 2026-04-02

### Aggiunto
- Polling automatico nella scheda Reputazione: quando VirusTotal o AbuseIPDB sono in elaborazione background, il frontend interroga `GET /api/analysis/{job_id}` ogni 8s e aggiorna i risultati senza ricaricare la pagina
- `_extract_priority_indicators()`: estrae solo gli IP interni all'email (received_hops + X-Originating-IP, non i resolved_ip degli URL) e solo URL con indicatori di rischio per i servizi SLOW, con hard cap a 4 URL per rispettare il limite 4/min di VirusTotal

### Modificato
- Banner "chiave .env" → "API key configurata" (verde) o "API key non configurata" (arancione) in base allo stato reale dal `service_registry`
- crt.sh spostato in `_SLOW_SERVICES` (background): con molti URL il rate limit 2.5s serializzato causava timeout nella fase fast
- Messaggio "non applicabile" reso più preciso: Redirect Chain → "nessun URL shortener o HTTP", crt.sh → "in elaborazione (background)"

### Corretto
- Redirect Chain usava `_http_get_with_retry()` che non supporta `allow_redirects`/`stream`; ripristinato `requests.get()` diretto con `_rate_limit()` esplicito

---

## [0.4.2] — 2026-04-01

### Corretto
- Timeout "servizi non hanno risposto nel tempo previsto": crt.sh (2.5s rate × N domini) era in _FAST_SERVICES causando timeout con 8+ URL; spostato in _SLOW_SERVICES (background)
- Redirect Chain: `_http_get_with_retry()` non supporta `allow_redirects`/`stream`; sostituito con `requests.get()` diretto
- Timeout fase 1 portato da 25s a 50s (rimane sotto il timeout axios di 60s)
- Tempo effettivo fase 1 con 3 IP + 8 URL: ~2s (era 20s+)

---

## [0.4.1] — 2026-04-01

### Corretto
- CTRL+C non torna immediatamente al prompt (Windows): alla chiusura, `threading._shutdown()` chiamava `join()` sui thread del `ThreadPoolExecutor` della fase 2 (VirusTotal/AbuseIPDB potenzialmente attivi per decine di secondi), causando blocco e `KeyboardInterrupt`. Fix: tutti i pool usano `shutdown(wait=False, cancel_futures=True)` in un blocco `finally`, e il lifespan FastAPI chiude esplicitamente l'executor di default di asyncio allo shutdown

---

## [0.4.0] — 2026-04-01

### Modificato
- Sistema reputazione riscritto con architettura a **due fasi** per eliminare definitivamente il timeout:
  - **Fase 1** (`POST /api/reputation/{job_id}`): servizi fast (Spamhaus, ASN, OpenPhish, crt.sh, PhishTank, Redirect Chain, MalwareBazaar) — risposta garantita in < 15s indipendentemente dal numero di entità
  - **Fase 2** (background automatico): VirusTotal e AbuseIPDB eseguiti dopo la risposta, senza bloccare il browser; il DB viene aggiornato quando terminano
  - Frontend: banner ⏳ nella scheda Reputazione quando la fase 2 è in elaborazione
- `connectors.py`: aggiunta classificazione `_FAST_SERVICES` / `_SLOW_SERVICES`, funzioni `run_fast_checks()` e `run_slow_checks()`

---

## [0.3.9] — 2026-04-01

### Corretto
- Messaggio `Error trying to connect to socket: closing socket - [WinError 10054]` definitivamente eliminato dalla console: la causa reale era `python-whois` (non uvicorn) che usa `logger.error()` quando un server WHOIS chiude il socket TCP dopo la risposta (comportamento RFC normale). Fix a tre livelli: (1) `_NoiseFilter` installato su tutti i logger coinvolti (`whois`, `whois.whois`, `uvicorn.*`, root) e sul `lastResort` handler di Python sia all'import che nel lifespan; (2) `setLevel(CRITICAL)` su entrambi i logger whois durante ogni chiamata WHOIS; (3) filtro installato anche sugli handler degli stessi logger

---

## [0.3.8] — 2026-04-01

### Modificato
- Sistema reputazione completamente riscritto per robustezza e compatibilità Windows/Linux:
  - Rate limiter thread-safe: `threading.Lock` per connettore invece di dict non protetto; nessuna race condition con chiamate concorrenti
  - Intervalli configurati per servizio: VirusTotal 15.5s, crt.sh 2.5s, AbuseIPDB 1.1s, MalwareBazaar 0.7s
  - Helper `_http_get_with_retry()` e `_http_post_with_retry()`: retry con backoff esponenziale (2s, 4s) su 429/502/503/504; legge l'header `Retry-After` sui 429
  - Tutti i connettori aggiornati per usare gli helper (nessuna chiamata `requests.get/post` diretta)
  - Pool flat ridotto a 16 worker (era 32) per evitare spike di rete
  - Timeout route reputazione portato a 90s per accomodare la serializzazione VirusTotal

---

## [0.3.7] — 2026-04-01

### Modificato
- Ordine hop nella catena SMTP invertito: hop 1 = mittente originale, hop N = server di destinazione (prima era al contrario)
- Filtro WinError 10054 spostato nel lifespan FastAPI: viene installato dopo che uvicorn configura i propri handler, coprendo tutti i logger incluso `uvicorn.protocols.http`

### Corretto
- Header email con encoded words RFC 2047 (`=?UTF-8?Q?...?=`) non venivano decodificati: `From`, `Subject` e altri campi mostravano la forma raw invece di `🔒 Massimiliano Dal Cero <...>`
- crt.sh: errore HTTP 429 (rate limit) ora mostra "troppe richieste, riprova tra qualche minuto" invece di un errore generico

---

## [0.3.6] — 2026-04-01

### Aggiunto
- Supporto IPv6 nei Received header: `_extract_ip_from_received()` riconosce `[IPv6:addr]`, `[addr]` e IPv4; `_is_private_ip()` usa `ipaddress` stdlib
- Filtro log per WinError 10054 in `main.py`: l'errore `WSAECONNRESET` di uvicorn su Windows non compare più nei log (comportamento TCP normale, non un errore applicativo)

### Modificato
- Parallelizzazione reputazione riscritta: da executor annidati a un **unico pool flat** (`_build_flat_tasks` + `run_reputation_checks`) — tutti i task (entità × servizi) partono contemporaneamente su un unico `ThreadPoolExecutor`; compatibile con Windows senza overhead di creazione thread
- Timeout globale route reputazione ridotto da 55s a 35s
- `_is_public_ip()` gestisce il prefisso `IPv6:` e `is_unspecified`

### Corretto
- IPv6 SMTP nei Received header non venivano estratti né mostrati nella catena hop
- IPv6 non venivano inviati ai servizi di reputazione
- Timeout 504 frequente su Windows: executor annidati causavano overhead significativo sulla creazione di thread

---

## [0.3.5] — 2026-03-30

### Aggiunto
- Nuovi servizi (Spamhaus DROP, ASN Lookup, crt.sh, Redirect Chain) inclusi nel report Word
- Auto-compilazione frontend in `start.sh` / `start.bat` se il bundle è assente e Node.js disponibile

### Modificato
- Bundle frontend con nome fisso (`index.js` / `index.css`), sovrascrivibile senza eliminare i vecchi file
- Check reputazione ora paralleli (`ThreadPoolExecutor`) e non bloccanti per FastAPI; timeout globale 50s
- Versione letta da `config.py` in tutti i file che la espongono (User-Agent, report Word, navbar, metadati FastAPI, script di avvio)

### Corretto
- Circular import in `connectors.py`
- Timeout 60s del browser durante il check reputazione
- Errori 502/503/504 di crt.sh mostrati come stacktrace; ora retry automatico con messaggio utente
- Nomi campi errati nel report Word (`url` → `original_url`, `is_ip` → `is_ip_address`)

---

## [0.3.4] — 2026-03-29

### Aggiunto
- Nuovi servizi reputazionali gratuiti: Spamhaus DROP, ASN Lookup (ipinfo.io), crt.sh, Redirect Chain
- Estrazione completa degli indicatori: X-Originating-IP, IP diretti negli URL, IP risolti via DNS, link offuscati — tutti inviati ai servizi con deduplicazione
- UI: pill con conteggio entità analizzate (IP / URL / Hash), icone distinte per servizi informativi (ℹ️)

### Corretto
- `x_originating_ip` non estratto (colonna diretta del record, non dentro `header_indicators`)
- IP diretti negli URL mai inviati ad AbuseIPDB (campo `is_ip_address` ignorato)

---

## [0.3.3] — 2026-03-28

### Modificato
- MalwareBazaar richiede ora API key obbligatoria; aggiunto `MALWAREBAZAAR_API_KEY`

### Corretto
- Stato "Pulito" mostrato anche in presenza di errori di connessione

---

## [0.3.2] — 2026-03-26

### Corretto
- Checkbox WHOIS ignorata (dipendenza mancante in `useCallback`)
- URL e badge WHOIS vuoti riaprendo analisi dallo storico (nomi campi errati nella risposta GET)

---

## [0.3.1] — 2026-03-25

### Aggiunto
- Badge età dominio negli URL (🔴 < 30gg, 🟡 30–90gg, ✅ > 90gg)
- Documentazione completa (README, installazione, utilizzo, configurazione, API)

### Modificato
- Rinominato il progetto in **EMLyzer**

### Corretto
- Dati WHOIS calcolati ma mai inclusi nella risposta API

---

## [0.3.0] — 2026-03-20

### Aggiunto
- Note dell'analista (area testo libera, salvata nel DB, inclusa nel report)
- Checkbox WHOIS opzionale nell'upload
- Classificatore NLP (Naive Bayes + TF-IDF) per probabilità phishing
- Filtro, ricerca e paginazione nella lista analisi; esportazione CSV
- Rilevamento campagne malevole (clustering per body hash, subject, Campaign-ID, dominio)
- Suite di test ampliata a 94

---

## [0.2.0] — 2026-03-10

### Aggiunto
- Localizzazione italiano/inglese con pulsante IT/EN
- Input manuale sorgente email (incolla header + body)
- Connettore VirusTotal completo (IP, URL, hash)
- Registro stato servizi reputazione nella UI

### Corretto
- `lxml` sostituito con `html.parser` (nessuna dipendenza da Visual C++ su Windows)
- Compatibilità SQLAlchemy, pytest-asyncio, rimosso `--reload` su Windows

---

## [0.1.0] — 2026-03-01

### Aggiunto
- Prima release pubblica: parser `.eml`/`.msg`, analisi header/body/URL/allegati, risk score, reputazione (AbuseIPDB, OpenPhish, PhishTank, MalwareBazaar), report `.docx`, dashboard web, SQLite, cross-platform, 52 test