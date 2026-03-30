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