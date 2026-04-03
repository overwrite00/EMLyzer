# Changelog

Tutte le modifiche significative al progetto sono documentate in questo file.
Il formato segue [Keep a Changelog](https://keepachangelog.com/it/1.0.0/).

---

## [Unreleased] — Roadmap

Questa sezione raccoglie tutto ciò che è pianificato ma non ancora implementato.
Le funzionalità sono ordinate per priorità di implementazione.
Ogni voce passa a una sezione con numero di versione quando viene completata.

### Reputazione — nuovi servizi (priorità alta)

- [ ] **Shodan InternetDB** — porte aperte e CVE per IP; no API key, endpoint JSON pubblico
- [ ] **Abuse.ch URLhaus** — database URL malware attivi; no API key, stesso ecosistema di MalwareBazaar
- [ ] **ThreatFox** (abuse.ch) — IOC unificati (URL, IP, hash, domini); no API key
- [ ] **CIRCL Passive DNS** — storico risoluzione DNS per IP e domini; gratuito con registrazione
- [ ] **GreyNoise Community** — distingue scanner innocui da attori malevoli, riduce falsi positivi; free tier 100 req/g
- [ ] **URLScan.io** — analisi completa URL con screenshot; free tier 100 req/h
- [ ] **Pulsedive** — threat intel aggregata su IP/URL/domini; free tier 30 req/min
- [ ] **Criminal IP** — threat score IP con geolocalizzazione; free tier
- [ ] **SecurityTrails** — Passive DNS e WHOIS storico per tracciare infrastrutture; 50 req/mese free
- [ ] **Hybrid Analysis** — analisi statica avanzata hash allegati; gratuito con registrazione

### Header analysis (priorità media)

- [ ] **List-Unsubscribe** — analisi link di unsubscribe (dominio diverso dal mittente, URL sospetti)
- [ ] **X-Campaign-ID** — analisi del campo già estratto: correlazione campagne bulk, pattern sospetti
- [ ] **ARC chain** (Authenticated Received Chain) — rilevante per phishing via account compromessi e forwarding
- [ ] **DKIM-Signature parsing** — estrazione selettore, dominio firmatario, algoritmo; ora si verifica solo il risultato

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
- Rinomina progetto: OpenMailForensics → **EMLyzer**

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