# EMLyzer — Memoria di Progetto per Claude

Questo file è la fonte di verità per Claude su tutto ciò che riguarda EMLyzer.
Va aggiornato ogni volta che viene implementata una funzionalità significativa,
correcto un bug importante, o modificata l'architettura.

---

## Identità del progetto

- **Nome**: EMLyzer
- **Versione corrente**: 0.10.0 — fonte di verità: `backend/utils/config.py` → `VERSION`
- **Tipo**: piattaforma open-source di email threat analysis
- **Filosofia**: nessuna dipendenza obbligatoria da API proprietarie; API a pagamento solo come plugin opzionali configurati dal singolo utente; analisi offline-first
- **Repository**: GitHub (distribuzione pubblica)
- **Licenza**: MIT
- **Test**: 94 test in `backend/tests/test_core.py` — devono passare tutti prima di ogni commit

---

## Stack tecnologico

| Layer | Tecnologia |
|---|---|
| Backend | Python 3.13 (range accettabile: 3.11–3.13; >3.13 non supportato), FastAPI, SQLAlchemy async, aiosqlite |
| Frontend | React 19, Vite 8, nessuna libreria UI esterna |
| Database | SQLite (default) — file `backend/data/emlyzer.db` |
| Report | python-docx |
| NLP | scikit-learn (MultinomialNB + TfidfVectorizer + Pipeline), nltk |
| Test | pytest, pytest-asyncio, httpx |

---

## Struttura della repository

```
EMLyzer/
├── start.sh / start.bat          # avvio Linux/macOS e Windows
├── run_tests.sh / run_tests.bat  # esecuzione test suite
├── CHANGELOG.md                  # storia versioni + roadmap [Unreleased]
├── claude.md                     # questo file — memoria progetto
├── README.md / docs/             # documentazione utente
├── backend/
│   ├── main.py                   # app FastAPI, mount static, lifespan
│   ├── utils/config.py           # Settings Pydantic — UNICA fonte versione
│   ├── utils/i18n.py             # helper traduzioni it/en
│   ├── models/database.py        # ORM EmailAnalysis + init_db
│   ├── api/routes/               # route FastAPI (una per dominio)
│   ├── core/analysis/            # analizzatori (parser, header, body, url, att, nlp, scorer, campaigns)
│   ├── core/reputation/          # connettori servizi reputazione
│   ├── core/reporting/           # generatore report .docx
│   ├── static/                   # bundle frontend compilato (index.js, index.css, index.html)
│   ├── uploads/                  # file caricati dagli utenti (non in git)
│   ├── reports/                  # report .docx generati (non in git)
│   ├── data/                     # database SQLite (non in git)
│   └── tests/                    # test_core.py (94 test), conftest.py
└── frontend/
    ├── vite.config.js            # output fisso: assets/index.js + assets/index.css
    ├── src/App.jsx               # root React con LangContext provider
    ├── src/pages/Dashboard.jsx   # pagina principale, legge versione da /api/health
    ├── src/components/           # AnalysisDetail, TabReputation, UploadZone, CampaignsPanel, ...
    ├── src/i18n/                 # LangContext.jsx + translations.js (160 chiavi it/en)
    └── src/api/client.js         # axios instance baseURL=/api, timeout=60s
```

---

## Database — modello EmailAnalysis

Ogni analisi è una riga in `EmailAnalysis`. Colonne principali:

| Campo | Tipo | Nota |
|---|---|---|
| `id` | UUID string PK | job_id usato in tutti gli endpoint |
| `filename` | str | nome file originale |
| `file_hash_sha256` | str | hash del file, indicizzato |
| `created_at` | datetime | UTC |
| `mail_from/to/subject/date` | Optional[str] | metadati email |
| `message_id/return_path/reply_to` | Optional[str] | header specifici |
| `x_mailer/x_originating_ip/x_campaign_id` | Optional[str] | header estesi |
| `spf_result/dkim_result/dmarc_result` | Optional[str] | risultati auth |
| `header_indicators` | JSON | output `HeaderAnalysisResult` |
| `body_indicators` | JSON | output `BodyAnalysisResult` |
| `url_indicators` | JSON | output `URLAnalysisResult` con lista `urls[]` |
| `attachment_indicators` | JSON | output `AttachmentAnalysisResult` |
| `reputation_results` | JSON | output `ReputationSummary` |
| `risk_score/risk_label/risk_explanation` | float/str/JSON | scoring finale |
| `analyst_notes` | Optional[str] | note libere analista |

**Attenzione nomi campi JSON**: i dataclass Python vengono serializzati con i loro nomi originali. Non usare alias abbreviati nei route che leggono dal DB:
- URL: `original_url` (non `url`), `is_ip_address` (non `is_ip`), `https_used` (non `https`)
- `x_originating_ip` è colonna diretta di `EmailAnalysis`, NON dentro `header_indicators`

---

## API Routes

| Metodo | Path | Funzione |
|---|---|---|
| GET | `/api/health` | `{"status","version","app"}` — versione da `settings.VERSION` |
| POST | `/api/upload/` | salva file, ritorna `{job_id}` |
| POST | `/api/manual/` | analisi da sorgente incollato |
| POST | `/api/analysis/{job_id}` | esegue analisi completa, salva nel DB |
| GET | `/api/analysis/{job_id}` | recupera risultati analisi (stessa struttura del POST) |
| GET | `/api/analysis/` | lista paginata con filtri `q`, `risk`, `page`, `page_size` |
| PATCH | `/api/analysis/{job_id}/notes` | salva note analista |
| DELETE | `/api/analysis/{job_id}` | elimina DB record + file email + report .docx |
| POST | `/api/analysis/bulk-delete` | elimina più analisi in blocco (max 100); body `{"job_ids": [...]}` |
| POST | `/api/reputation/{job_id}` | esegue check reputazionali (separato dall'analisi) |
| GET | `/api/report/{job_id}` | scarica report .docx |
| GET | `/api/campaigns/` | clustering campagne con parametri `threshold`, `min_size` |
| GET | `/api/settings/` | configurazione corrente |
| POST | `/api/settings/language` | cambia lingua (it/en) |

---

## Pipeline di analisi

Ordine di esecuzione in `POST /api/analysis/{job_id}`:

```
upload file → parse_email_file()
                    ↓
         ┌──────────┼──────────────┬─────────────────┐
    analyze_headers  analyze_body  analyze_urls  analyze_attachments
         └──────────┴──────────────┴─────────────────┘
                    ↓
             compute_risk_score()    ← pesi uguali: 25% ciascuno
                    ↓
              classify_text() (NLP)  ← contribuisce al body score
                    ↓
              salva in DB
```

**Risk scoring** (v2 — normalizzazione adattiva):
- `low`: 0–20, `medium`: 20–45, `high`: 45–70, `critical`: 70–100
- Pesi base: header 35%, body 35%, url 20%, attachment 10%
- Normalizzazione adattiva: denominatore = somma pesi moduli ATTIVI (url solo se ha URL; allegati solo se ha allegati)
- Floor deterministici: 1 HIGH header → ≥20; HIGH+NLP≥50% → ≥35; 3+ HIGH → ≥45; URL≥75 → ≥20; allegato HIGH → ≥25; allegato CRITICAL → ≥40; 2+ body HIGH → ≥30
- NLP (MultinomialNB + TF-IDF) contribuisce al body score_contribution

---

## Analizzatori — dettagli chiave

### email_parser
Supporta `.eml` (mail-parser) e `.msg` (extract-msg). Estrae tutti i campi in `ParsedEmail`:
`filename, file_hash_md5/sha1/sha256, mail_from/to/cc/subject/date, message_id, return_path, reply_to, x_mailer, x_originating_ip, x_campaign_id, list_unsubscribe, received_chain, spf/dkim/dmarc_result, body_text, body_html, attachments, parse_errors`
**Decodifica RFC 2047**: `get_header()` e `get_headers()` usano entrambi `_decode_rfc2047()` — decodificano automaticamente `=?UTF-8?Q?...?=`, `=?UTF-8?B?...?=` e `=?iso-8859-1?...?=` in tutti i campi header, inclusi quelli multi-valore. Il dizionario `raw_headers` applica surrogate-escape recovery per gestire byte UTF-8 grezzi prodotti dalla policy compat32. **Fallback raw-bytes** (v0.9.1): quando compat32 produce U+FFFD (byte non-ASCII non-RFC2047, es. `ü` come `\xc3\xbc` diretto), `get_header()` e il loop `raw_headers` chiamano `_decode_header_raw_fallback(raw, name)` che estrae il valore dai byte grezzi del file e prova UTF-8 → Windows-1252.

### header_analyzer
Funzioni interne: `_check_auth`, `_check_bulk_sender`, `_check_header_injection`, `_check_identity_mismatch`, `_check_missing_fields`, `_check_originating_ip`
Finding severities: `info`, `low`, `medium`, `high`
**IPv6**: `_extract_ip_from_received(received)` → estrae IP (v4 e v6) dai Received header; `_is_private_ip(ip)` usa `ipaddress` stdlib. Formati supportati: `[IPv6:addr]`, `[addr]`, `[x.x.x.x]`.
**Ordine hop**: i Received header vengono invertiti (`reversed()`) in `_parse_received_chain` — hop 1 = mittente originale, hop N = server di destinazione finale (RFC 5321: ogni server aggiunge in cima).
**Nota**: `list_unsubscribe` e `x_campaign_id` sono estratti dal parser ma NON ancora analizzati dall'header analyzer (voce in roadmap).
**AuthDetail** (v0.7.0): nuovo dataclass `AuthDetail` con 16 campi per SPF/DKIM/DMARC sub-fields. Campo `auth_detail: AuthDetail` aggiunto a `HeaderAnalysisResult`, serializzato automaticamente in `header_indicators` JSON. Funzioni DNS: `_query_spf_record`, `_query_dmarc_record`, `_query_dkim_key` (timeout 2s, `dnspython`). `_build_auth_detail()` chiamata alla fine di `_check_auth()`. Campi `dkim_signatures_raw`, `received_spf_raw`, `auth_results_raw` aggiunti a `ParsedEmail`.

### body_analyzer
Rileva: urgency_count, phishing_cta_count, credential_keyword_count, obfuscated_links (href≠testo), forms_found, js_found, invisible_elements (CSS nascosto), base64_inline_count, raw_hidden_content
Finding categories: `text`, `html`, `base64`, `nlp`

### url_analyzer
Per ogni URL estrae: original_url, scheme, host, path, domain, subdomain, tld, is_ip_address, is_shortener, is_punycode, resolved_ip, dns_error, whois_creation_date, domain_age_days, is_new_domain, https_used, findings, risk_score
WHOIS è abilitato di default (`do_whois=True` dalla v0.8.0). DNS lookup sempre eseguito.

### attachment_analyzer
Calcola hash MD5/SHA1/SHA256, rileva MIME mismatch, doppia estensione, macro VBA (OLE2 e OOXML), JavaScript embedded, stream PDF sospetti. Solo analisi statica, nessuna esecuzione.

### campaign_detector
Tipi di cluster: `subject` (similarità Jaccard), `body_hash`, `message_id` (pattern dominio), `campaign_id` (X-Campaign-ID), `sender_domain`

---

## Sistema reputazione

### Architettura a due fasi
- **Fase 1** `POST /api/reputation/{job_id}` → `run_fast_checks()` — risposta garantita < 5s, timeout route 50s
- **Fase 2** FastAPI `BackgroundTask` → `run_slow_checks()` — nessun timeout, aggiorna DB quando finisce
- Frontend fa polling `GET /api/analysis/{job_id}` ogni 5s finché `reputation_results.reputation_phase === "complete"`
- **CRITICO**: usare `flag_modified(record, "reputation_results")` prima di ogni `commit()` con JSON su SQLite
- Background task usa `asyncio.get_running_loop()` (non `get_event_loop()`, deprecato Python 3.10+)
- **`finalize_fast_only(summary)`** (v0.9.4): chiamata dalla route quando `has_slow=False`; rimuove i placeholder "in elaborazione" e ricalcola `service_registry`; senza di essa AbuseIPDB/VirusTotal/crt.sh restano bloccati in "pending" per email senza indicatori SLOW
- **Disk cache feed** (v0.9.4): Spamhaus DROP (TTL 24h) e OpenPhish (TTL 12h) vengono salvati in `backend/data/cache/` come JSON; al riavvio si leggono da disco senza ri-scaricare; se il download fallisce si usa la cache scaduta come fallback
- **`slow_indicators`** (v0.9.4): campo in `reputation_results` con IP/URL/hash passati ai servizi SLOW; usato dal frontend per diagnostica nel tab Reputazione

### Classificazione servizi
**FAST** (`_FAST_SERVICES`): Spamhaus DROP, ASN Lookup, OpenPhish, PhishTank, Redirect Chain, MalwareBazaar
**SLOW** (`_SLOW_SERVICES`): AbuseIPDB (1.1s/req), VirusTotal (15.5s/req), crt.sh (2.5s/req)

### Estrazione indicatori
- `_extract_indicators()` → tutti gli IP/URL/hash (per FAST: Spamhaus, ASN, OpenPhish, ecc.)
- `_extract_priority_indicators()` → selettivo per SLOW (max 4 URL, solo sospetti; IP solo da header)
  - IP: SOLO `received_hops` + `x_originating_ip` — NON i `resolved_ip` degli URL (CDN normali)
  - URL: solo `is_shortener`, `is_new_domain`, `is_ip_address`, `is_punycode`, `risk_score >= 25`

### Nomi servizi — mappa obbligatoria `_FN_TO_SOURCE`
Mappa `fn.__name__` → nome corretto per `_build_service_registry`:
- `check_ip_abuseipdb` → `"AbuseIPDB"`, `check_*_virustotal` → `"VirusTotal"`, `check_domain_crtsh` → `"crt.sh"`
- SENZA questa mappa i placeholder usano nomi sbagliati (es. `"Ip Abuseipdb"`) → stato `not_applicable`

### Stati `service_registry`
- `clean` ✅ — check completato, nessun indicatore malevolo
- `malicious` ❌ — indicatori malevoli trovati
- `pending` ⏳ — servizio SLOW in elaborazione background
- `skipped` 🔑 — API key non configurata
- `not_applicable` ➖ — servizio non pertinente per questa email
- `error` ⚠️ — errore durante il check

### Servizi attivi (9 totali)

| Servizio | Tipo | Chiave | Fase | Note |
|---|---|---|---|---|
| AbuseIPDB | IP | `ABUSEIPDB_API_KEY` | SLOW | Score 0-100, 1.1s rate |
| VirusTotal | IP+URL+hash | `VIRUSTOTAL_API_KEY` | SLOW | 4 req/min free, 15.5s rate |
| Spamhaus DROP | IP | nessuna | FAST | Feed CIDR cachato |
| ASN Lookup | IP | nessuna | FAST | ipinfo.io, 50k/mese |
| Shodan InternetDB | IP | nessuna | FAST | Porte, CVE, tag — informativo |
| OpenPhish | URL | nessuna | FAST | Feed cachato |
| PhishTank | URL | `PHISHTANK_API_KEY` | FAST | Community verified |
| Redirect Chain | URL | nessuna | FAST | Solo shortener e HTTP |
| crt.sh | URL/dominio | nessuna | SLOW | 2.5s rate, certificati TLS |
| URLhaus | URL | `ABUSECH_API_KEY` | FAST | abuse.ch, auth richiesta da giu 2025 |
| MalwareBazaar | hash | `ABUSECH_API_KEY` (o `MALWAREBAZAAR_API_KEY` legacy) | FAST | auth.abuse.ch |
| ThreatFox | IP+URL+hash | `ABUSECH_API_KEY` | FAST | abuse.ch, auth richiesta da giu 2025 |

### Rate limiter thread-safe
`threading.Lock` per connettore + `_RATE_INTERVALS`. Retry backoff 2s/4s su 429/5xx.

### Frontend — banner API key
`TabReputation` carica `GET /api/settings/reputation_keys` via `useEffect` al mount.
`ServicePreview` riceve `apiKeys = { "AbuseIPDB": bool, ... }` — indipendente dall'analisi corrente.

Servizi informativi (ASN, crt.sh, Redirect Chain, Shodan InternetDB): mostrano `ℹ️` nella UI invece di `✅`.
Timeout richieste: 6s per servizi sicurezza, 2s per servizi informativi (`REQUEST_TIMEOUT_INFO`).

---

## Report Word (.docx)

Struttura 8 sezioni generate da `docx_reporter.py`:
1. Executive Summary (risk score + spiegazione)
2. Email Metadata (tutti i campi header)
3. Indicatori Tecnici — Header
4. Analisi del Contenuto (body + link offuscati + URL)
5. Allegati
6. Reputazione (tutti i 12 servizi, separati per categoria IP/URL/hash, entità analizzate)
7. Valutazione del Rischio (score + contributo per modulo)
8. Note dell'Analista (sezione editabile)

**Titolo usa `settings.VERSION`** — si aggiorna automaticamente.
**Manca**: sezione Campagne Rilevate (voce in roadmap).

---

## Frontend

### Versione nella navbar
`Dashboard.jsx` legge la versione da `GET /api/health` al mount — non è hardcoded nel bundle.

### Bundle
`vite.config.js` produce sempre `assets/index.js` e `assets/index.css` (nome fisso, no hash).
Deploy: `cd frontend && npm run build && cp -r dist/. ../backend/static/`

### Localizzazione
207 chiavi in `translations.js` (it/en). Lingua salvata in `localStorage['emlyzer_lang']` e in `.env` via `POST /api/settings/language`.

### Schede AnalysisDetail
1. Riepilogo, 2. Header, 3. Body, 4. URL, 5. Allegati, 6. Reputazione

---

## Script di avvio

### start.sh (Linux/macOS)
- Rileva distro da `/etc/os-release` → famiglie: ubuntu, debian, fedora, rhel, arch, opensuse, macos
- Cerca Python 3.13 (target); accetta 3.11–3.13 come fallback; rifiuta >3.13 e installa 3.13 in parallelo
- `_resolve_python()`: cerca in PATH, percorsi assoluti (`/usr/bin/python3.13`), pyenv (`~/.pyenv/`), RHEL SCL (`/opt/rh/`)
- Variabili versione (righe 13-16): `PYTHON_TARGET`, `PYTHON_TARGET_MINOR`, `PYTHON_MIN_MINOR`, `PYTHON_MAX_MINOR`
- Se bundle `static/assets/index.js` assente e Node.js disponibile: compila frontend automaticamente
- Porta: 8000, verifica libera con `ss`/`netstat`/`/dev/tcp`

### start.bat (Windows)
- Priorità 1: Python Launcher `py -3.13`, poi `py -3.12`, `py -3.11`
- Priorità 2: `python.exe` generico con controllo versione via `python -c "import sys; exit(...)`
- Legge versione da `config.py` via Python dopo averlo trovato
- Versione fallback hardcoded: aggiornare a ogni nuova release
- Se bundle assente e Node disponibile: `npm run build` + `xcopy`

### Regola fondamentale per aggiornare la versione
Modificare **solo** `backend/utils/config.py` → `VERSION`. Tutto il resto si aggiorna automaticamente:
- `/api/health` risposta
- Navbar frontend (fetch al mount)
- User-Agent HTTP nei connettori
- Titolo report Word
- Metadati FastAPI (`/docs`)
- Script di avvio (letti da config.py a runtime)

---

## Configurazione (.env)

Chiavi disponibili in `.env.example`:

```ini
DEBUG=False
MAX_UPLOAD_SIZE_MB=25
ABUSEIPDB_API_KEY=         # obbligatoria per AbuseIPDB
VIRUSTOTAL_API_KEY=        # obbligatoria per VirusTotal
PHISHTANK_API_KEY=         # obbligatoria per PhishTank
ABUSECH_API_KEY=           # copre URLhaus + ThreatFox + MalwareBazaar (auth.abuse.ch, gratuito)
MALWAREBAZAAR_API_KEY=     # legacy — usare ABUSECH_API_KEY per i nuovi account
RATE_LIMIT_PER_MINUTE=30
LANGUAGE=it                # it o en
```

---

## Bug noti risolti — pattern da non ripetere

1. **Nomi campi JSON dal DB**: i dataclass Python serializzati usano i nomi originali Python. Non assumere alias abbreviati. Verificare sempre con `_dataclass_to_dict()` prima di leggere dal DB.
2. **`x_originating_ip`** è colonna diretta di `EmailAnalysis`, non dentro `header_indicators`.
3. **Circular import**: non mettere import di moduli pesanti (concurrent.futures, sklearn) dentro funzioni — metterli al top-level.
4. **FastAPI + funzioni sincrone bloccanti**: usare sempre `await loop.run_in_executor()` per chiamate requests/HTTP sincrone negli handler async.
5. **Versione hardcoded**: non scrivere mai `"0.3.X"` direttamente in nessun file. Usare `settings.VERSION`.
6. **Variable scope subshell bash**: `$()` crea una subshell, le variabili assegnate dentro non propagano al padre. Usare variabili globali (`_RESOLVED_BIN`, `_RESOLVED_MINOR`) invece di `echo` + cattura.
7. **SQLAlchemy JSON mutation**: con SQLite, riassegnare un dict JSON a una colonna non garantisce che SQLAlchemy tracci la modifica. Usare sempre `flag_modified(record, "reputation_results")` prima del `commit()`.
8. **`_FN_TO_SOURCE` obbligatoria**: i placeholder "in elaborazione" nei servizi SLOW devono usare la mappa `_FN_TO_SOURCE` per ottenere il nome corretto (es. "AbuseIPDB" non "Ip Abuseipdb"). Senza di essa `_build_service_registry` non trova il servizio e mostra "non applicabile".
9. **`GET /api/analysis` deve includere `reputation_results`**: `_build_response_from_record` deve restituire `"reputation_results": record.reputation_results` altrimenti il polling del frontend non può mai rilevare `reputation_phase === "complete"`.
10. **`asyncio.get_running_loop()`**: nei background task FastAPI usare `get_running_loop()` non `get_event_loop()` (deprecato Python 3.10+, può creare un loop nuovo invece di usare quello di uvicorn).
11. **Banner API key prima dell'analisi**: `ServicePreview` non può leggere lo stato chiavi dal `service_registry` (assente prima dell'analisi). Caricare da `GET /api/settings/reputation_keys` via `useEffect` al mount del componente.
12. **`Received-SPF` regex con keyword vuota**: `_extract_auth_results(list, "")` con keyword `""` fa sì che il regex `r"=(\S+)"` matchi il PRIMO `=` qualsiasi nell'header (es. `client-ip=1.2.3.4` → restituisce `1.2.3.4` invece del risultato SPF). Usare sempre `re.search(r"^(\w+)", raw.strip(), re.IGNORECASE)` per estrarre il primo token del risultato Received-SPF.
13. **`auth_detail` assente in analisi vecchie**: il campo `auth_detail` è stato aggiunto in v0.7.0. Il frontend deve gestire la sua assenza (`e.auth_detail || {}`) per le analisi pre-v0.7.0 già in DB. I sotto-dettagli semplicemente non vengono mostrati.
14. **ThreatFox `illegal_search_term` e `no_result`**: ThreatFox restituisce `illegal_search_term` per URL con formato non riconosciuto (non è un errore) e `no_result` (singolare) come variante di `no_results`. Entrambi vanno aggiunti alla lista dei casi "non trovato" in `_parse_threatfox_result`, altrimenti cadono nell'`else` e mostrano `Status: ...` nella UI.
15. **`start.bat` versione fallback hardcoded**: la riga `set "VERSION=x.y.z"` in `start.bat` va aggiornata a ogni nuova release, altrimenti il titolo della finestra mostra la versione precedente durante l'avvio (prima che Python legga `config.py`).
16. **`get_headers()` deve decodificare RFC 2047**: la funzione `get_headers()` in `email_parser.py` deve chiamare `_decode_rfc2047()` su ogni valore, come fa `get_header()`. Senza questa decodifica, gli header multi-valore (Authentication-Results, DKIM-Signature) possono contenere token RFC 2047 grezzi.
17. **`ensure_ascii=False` in serializzazione JSON**: `_dataclass_to_dict()` in `analysis.py` deve usare `json.dumps(..., ensure_ascii=False)` per preservare emoji e caratteri non-ASCII nella risposta API. Il default `ensure_ascii=True` escapa i caratteri Unicode in `\uXXXX`.
18. **Collision nomi variabili nel bundle minificato**: quando si patchano manualmente file bundle Vite (senza npm), i nomi a due lettere (`Wn`, `Vn`, ecc.) possono essere riutilizzati in scope diversi dello stesso file. Usare sempre nomi con prefisso underscore (`_Wn`, `_Bn`) che non compaiono nell'originale. Verificare con `grep -c '\bNOME\b' index.js` prima di scegliere un nome. Il `useState(new Set)` passato a React viene interpretato come lazy initializer e chiama `Set()` senza `new` → TypeError; usare sempre `useState(()=>new Set())`. Analogamente, `setState(new Set)` nei callback è corretto perché React non tratta gli oggetti come initializer.
19. **`bleach.css_sanitizer` richiede `tinycss2`**: bleach 6.x lancia `NoCssSanitizerWarning` quando `style` è in `ALLOWED_ATTRS` ma `css_sanitizer` non è passato a `bleach.clean()`. Soluzione: aggiungere `tinycss2>=1.3.0` a `requirements.txt` e passare un'istanza di `CSSSanitizer(allowed_css_properties=[...])` a `bleach.clean()`. Creare `_CSS_SANITIZER` a livello di modulo (non dentro la funzione) per evitare ricreazioni ad ogni chiamata.

---

## Roadmap — prossime implementazioni

La roadmap completa con priorità è in `CHANGELOG.md` nella sezione `[Unreleased]`.

**Prossima funzionalità da implementare** (prima in lista): **CIRCL Passive DNS**
- Endpoint: `https://www.circl.lu/pdns/query/{ip_or_domain}` — JSON, gratuito con registrazione
- Tipo: IP+URL, informativo
- Aggiungere a `connectors.py` come `check_ip_circlpdns` / `check_domain_circlpdns`

---

## Regole di versioning — Semantic Versioning (`MAJOR.MINOR.PATCH`)

Schema: `MAJOR.MINOR.PATCH` — fonte di verità `backend/utils/config.py` → `VERSION`

| Componente | Quando bumpa | Esempi concreti |
|---|---|---|
| **PATCH** (`x.y.Z`) | Bug fix, hotfix, correzioni di comportamento errato | Fix CTRL+C, fix timeout, fix nomi servizi, fix polling |
| **MINOR** (`x.Y.0`) | Nuove feature, nuovi servizi/analyzer, refactor architetturale significativo, miglioramenti all'algoritmo | +3 servizi reputazione, nuovo scorer, two-phase reputation |
| **MAJOR** (`X.0.0`) | Breaking change API o schema DB, milestone di stabilità (es. 1.0) | Cambio schema risposta API, drop Python 3.11 |

**Regole operative:**
- Più fix correlati nella stessa sessione = **una sola versione PATCH** (non una versione per fix)
- Più feature correlate nella stessa sessione = **una sola versione MINOR**
- Non bumpa MAJOR per aggiungere feature — solo per breaking change o 1.0 milestone
- **Non scrivere mai la versione hardcoded** fuori da `config.py`: tutto legge `settings.VERSION`

**Cosa bumpa MINOR (non PATCH):**
- Aggiunta di ≥1 nuovo servizio reputazione
- Aggiunta di un nuovo analyzer (header, body, URL, attachment)
- Rewrite di un algoritmo esistente (scoring, parsing)
- Aggiunta di funzionalità UI visibili all'utente (nuova tab, nuovo pannello)

**Cosa bumpa PATCH (non MINOR):**
- Fix di un bug in un connettore o analyzer
- Fix di comportamento errato nell'UI
- Correzione di un edge case nel parser
- Fix di compatibilità OS/Python

---

## Note operative per Claude

- Eseguire sempre `run_tests.sh` (o `python -m pytest tests/test_core.py -q --asyncio-mode=auto`) dopo ogni modifica backend
- Il frontend va ricompilato (`npm run build`) dopo ogni modifica a `frontend/src/`
- Ogni nuova funzionalità: aggiornare `CHANGELOG.md` (sposta da `[Unreleased]` a versione numerata), aggiornare `VERSION` in `config.py`, aggiornare questo file
- I file di output per GitHub vengono copiati in `/mnt/user-data/outputs/EMLyzer/` mantenendo la struttura della repo
- Il transcript delle sessioni precedenti è in `/mnt/transcripts/`