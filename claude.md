# EMLyzer — Memoria di Progetto per Claude

Questo file è la fonte di verità per Claude su tutto ciò che riguarda EMLyzer.
Va aggiornato ogni volta che viene implementata una funzionalità significativa,
correcto un bug importante, o modificata l'architettura.

---

## Identità del progetto

- **Nome**: EMLyzer (rinominato da OpenMailForensics nella v0.3.1)
- **Versione corrente**: 0.3.5 — fonte di verità: `backend/utils/config.py` → `VERSION`
- **Tipo**: piattaforma open-source di email forensics & threat analysis
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

**Risk scoring**:
- `low`: 0–20, `medium`: 20–45, `high`: 45–70, `critical`: 70–100
- Pesi moduli: header 25%, body 25%, url 25%, attachment 25%
- NLP (MultinomialNB + TF-IDF) contribuisce fino a +40pt al body score

---

## Analizzatori — dettagli chiave

### email_parser
Supporta `.eml` (mail-parser) e `.msg` (extract-msg). Estrae tutti i campi in `ParsedEmail`:
`filename, file_hash_md5/sha1/sha256, mail_from/to/cc/subject/date, message_id, return_path, reply_to, x_mailer, x_originating_ip, x_campaign_id, list_unsubscribe, received_chain, spf/dkim/dmarc_result, body_text, body_html, attachments, parse_errors`

### header_analyzer
Funzioni interne: `_check_auth`, `_check_bulk_sender`, `_check_header_injection`, `_check_identity_mismatch`, `_check_missing_fields`, `_check_originating_ip`
Finding severities: `info`, `low`, `medium`, `high`
**Nota**: `list_unsubscribe` e `x_campaign_id` sono estratti dal parser ma NON ancora analizzati dall'header analyzer (voce in roadmap).

### body_analyzer
Rileva: urgency_count, phishing_cta_count, credential_keyword_count, obfuscated_links (href≠testo), forms_found, js_found, invisible_elements (CSS nascosto), base64_inline_count, raw_hidden_content
Finding categories: `text`, `html`, `base64`, `nlp`

### url_analyzer
Per ogni URL estrae: original_url, scheme, host, path, domain, subdomain, tld, is_ip_address, is_shortener, is_punycode, resolved_ip, dns_error, whois_creation_date, domain_age_days, is_new_domain, https_used, findings, risk_score
WHOIS è opzionale (`do_whois` param). DNS lookup sempre eseguito.

### attachment_analyzer
Calcola hash MD5/SHA1/SHA256, rileva MIME mismatch, doppia estensione, macro VBA (OLE2 e OOXML), JavaScript embedded, stream PDF sospetti. Solo analisi statica, nessuna esecuzione.

### campaign_detector
Tipi di cluster: `subject` (similarità Jaccard), `body_hash`, `message_id` (pattern dominio), `campaign_id` (X-Campaign-ID), `sender_domain`

---

## Sistema reputazione

### Architettura
- `reputation.py` (route) → `_extract_indicators()` → `run_reputation_checks()` (connectors)
- Esecuzione **parallela** con `ThreadPoolExecutor(max_workers=8)`
- Chiamata **non bloccante** per FastAPI via `await loop.run_in_executor()`
- Timeout globale 50s → HTTP 504 se superato
- Pre-carica feed con cache (OpenPhish, Spamhaus DROP) prima di avviare i thread

### Estrazione indicatori (da `_extract_indicators`)
Fonti IP: `received_hops` (SMTP chain, solo pubblici), `record.x_originating_ip` (colonna diretta!), `url.host` dove `is_ip_address=True`, `url.resolved_ip`
Fonti URL: `url_indicators.urls[].original_url`, `body_indicators.obfuscated_links[].actual_href`
Deduplicazione via set Python — ogni IP/URL/hash appare una sola volta

### Servizi attivi (9 totali)

| Servizio | Tipo | Chiave | Note |
|---|---|---|---|
| AbuseIPDB | IP | `ABUSEIPDB_API_KEY` | Score 0-100 + ISP |
| VirusTotal | IP+URL+hash | `VIRUSTOTAL_API_KEY` | Rate limit 4 req/min free |
| Spamhaus DROP | IP | nessuna | Feed CIDR scaricato e cachato |
| ASN Lookup | IP | nessuna | ipinfo.io, 50k req/mese free |
| OpenPhish | URL | nessuna | Feed scaricato e cachato |
| PhishTank | URL | `PHISHTANK_API_KEY` | Community verified |
| Redirect Chain | URL | nessuna | Solo per shortener e HTTP |
| crt.sh | URL/dominio | nessuna | Certificati TLS; retry su 502/503/504 |
| MalwareBazaar | hash | `MALWAREBAZAAR_API_KEY` | Richiesta da marzo 2026 |

Servizi informativi (ASN, crt.sh, Redirect Chain): mostrano `ℹ️` nella UI invece di `✅`.
Timeout richieste: 6s per servizi sicurezza, 2s per servizi informativi (`REQUEST_TIMEOUT_INFO`).

---

## Report Word (.docx)

Struttura 8 sezioni generate da `docx_reporter.py`:
1. Executive Summary (risk score + spiegazione)
2. Email Metadata (tutti i campi header)
3. Indicatori Tecnici — Header
4. Analisi del Contenuto (body + link offuscati + URL)
5. Allegati
6. Reputazione (tutti i 9 servizi, separati per categoria IP/URL/hash, entità analizzate)
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
160 chiavi in `translations.js` (it/en). Lingua salvata in `localStorage['emlyzer_lang']` e in `.env` via `POST /api/settings/language`.

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
MALWAREBAZAAR_API_KEY=     # obbligatoria da marzo 2026
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

---

## Roadmap — prossime implementazioni

La roadmap completa con priorità è in `CHANGELOG.md` nella sezione `[Unreleased]`.

**Prossima funzionalità da implementare** (prima in lista):

### 1. Shodan InternetDB (priorità massima)
- Endpoint: `https://internetdb.shodan.io/{ip}` — JSON pubblico, no API key, no registrazione
- Risposta: `{ip, ports, cpes, hostnames, tags, vulns}`
- Da aggiungere a `connectors.py` come `check_ip_shodan_internetdb(ip)`
- Tipo: IP, gratuito, informativo (icona ℹ️)
- Aggiungere a `_SERVICE_DEFS` e a `_checks_for_ip()`
- Aggiornare `TabReputation.jsx` (ServicePreview), `translations.js`, `docx_reporter.py`
- Timeout: `REQUEST_TIMEOUT_INFO` (2s)

### 2. Abuse.ch URLhaus
- Endpoint: `https://urlhaus-api.abuse.ch/v1/url/` POST con `{"url": "..."}`
- No API key, stesso ecosistema di MalwareBazaar
- Da aggiungere come `check_url_urlhaus(url)` in `connectors.py`
- Tipo: URL, gratuito

### 3. ThreatFox (abuse.ch)
- Endpoint: `https://threatfox-api.abuse.ch/api/v1/` POST con `{"query":"search_ioc","search_term":"..."}`
- No API key, copre URL/IP/hash/domini
- Tipo: IP+URL+hash, gratuito

---

## Note operative per Claude

- Eseguire sempre `run_tests.sh` (o `python -m pytest tests/test_core.py -q --asyncio-mode=auto`) dopo ogni modifica backend
- Il frontend va ricompilato (`npm run build`) dopo ogni modifica a `frontend/src/`
- Ogni nuova funzionalità: aggiornare `CHANGELOG.md` (sposta da `[Unreleased]` a versione numerata), aggiornare `VERSION` in `config.py`, aggiornare questo file
- I file di output per GitHub vengono copiati in `/mnt/user-data/outputs/EMLyzer/` mantenendo la struttura della repo
- Il transcript delle sessioni precedenti è in `/mnt/transcripts/`