# Changelog

Tutte le modifiche significative al progetto sono documentate in questo file.

Il formato segue [Keep a Changelog](https://keepachangelog.com/it/1.0.0/).

---

## [0.3.3] — 2026

### Modificato
- **MalwareBazaar ora richiede API key** — il servizio ha introdotto l'obbligo di registrazione (marzo 2026); aggiunta la chiave `MALWAREBAZAAR_API_KEY` in `config.py` e `.env.example`; il connettore invia ora l'header `Auth-Key`; la documentazione è stata aggiornata con le istruzioni di registrazione

### Corretto
- **Stato "Pulito" mostrato in presenza di errori** — la condizione `elif errors and queried == 0` mostrava errore solo se nessuna chiamata era stata completata; con `queried=1` ed errore presente il servizio mostrava "Pulito"; corretto in `elif errors`

---

## [0.3.2] — 2026

### Corretto
- **Bug WHOIS — checkbox ignorata** — `doWhois` mancava nelle dipendenze di `useCallback` in `UploadZone.jsx`: la funzione di upload veniva creata una volta sola con il valore iniziale `false`, ignorando qualsiasi modifica successiva alla checkbox. La checkbox appariva attiva ma il parametro `do_whois=false` veniva sempre inviato al backend
- **Bug URL vuoti nello storico** — `_build_response_from_record` restituiva gli URL con i nomi dei campi del dataclass Python (`original_url`, `is_ip_address`, `https_used`) invece di quelli attesi dal frontend (`url`, `is_ip`, `https`); le card URL apparivano vuote riaprendo un'analisi dallo storico
- **Bug badge WHOIS — `whois_attempted` non persistito nel DB** — il campo veniva aggiunto alla risposta JSON del POST ma non salvato in `url_indicators` nel database; il GET dallo storico non lo trovava e mostrava sempre "WHOIS non eseguito"
- **Bug badge WHOIS — campo mancante nelle analisi vecchie** — le analisi create prima dell'introduzione di `whois_attempted` non avevano il campo nel DB; il frontend ora gestisce correttamente l'assenza del campo mostrando "WHOIS non eseguito"

---

## [0.3.1] — 2026

### Corretto
- **Bug WHOIS — dati non visibili nella UI** — i campi `domain_age_days` e `whois_creation_date` venivano calcolati correttamente ma non inclusi nella risposta API; il frontend non li riceveva mai e la checkbox "Abilita WHOIS" non produceva alcun risultato visibile
- **Rinomina progetto** — da OpenMailForensics a **EMLyzer** in tutti i file (sorgenti Python, frontend React, script di avvio, documentazione, cartella radice); prefissi `omf_` → `eml_`; chiave localStorage `omf_lang` → `emlyzer_lang`; database `omf.db` → `emlyzer.db`

### Aggiunto
- **Badge età dominio nella scheda URL** — quando WHOIS è abilitato, ogni URL mostra un badge colorato con l'età del dominio: 🔴 meno di 30 giorni (nuovo), 🟡 tra 30 e 90 giorni (recente), ✅ oltre 90 giorni; badge grigio se nessun dato WHOIS disponibile
- **Documentazione completa** — `README.md`, `CHANGELOG.md`, `LICENSE` (MIT), `docs/REQUISITI.md`, `docs/INSTALLAZIONE.md`, `docs/UTILIZZO.md`, `docs/CONFIGURAZIONE.md`, `docs/API.md`; orientata a utenti non esperti con istruzioni passo-passo per Windows e Linux

---

## [0.3.0] — 2026

### Aggiunto
- **Note dell'analista** — area di testo nella scheda Riepilogo per salvare osservazioni manuali; persistenza nel database; incluse nel report .docx; endpoint `PATCH /api/analysis/{job_id}/notes`
- **WHOIS opzionale dalla UI** — checkbox "Abilita WHOIS" nella zona upload per attivare la verifica dell'età dei domini; disponibile anche per l'input manuale
- **Classificatore NLP** — modello Naive Bayes + TF-IDF per calcolo della probabilità phishing nel testo; sezione dedicata nella scheda Body con barra di probabilità e feature words rilevanti; contribuisce fino a +40 punti al risk score; `scikit-learn` e `nltk` ora inclusi nei requisiti
- **Filtro, ricerca e paginazione** nella lista analisi — barra di ricerca full-text con evidenziazione del termine trovato; filtri rapidi per livello di rischio; paginazione 25 elementi/pagina; esportazione CSV; endpoint `GET /api/analysis/` aggiornato con parametri `q`, `risk`, `page`, `page_size`
- **Rilevamento campagne** — clustering automatico per body hash, X-Campaign-ID, Message-ID pattern, subject simile (Jaccard), dominio mittente; pannello "Campagne Rilevate" in dashboard; slider soglia similarità; endpoint `GET /api/campaigns/`
- **Stato `not_applicable`** nella scheda Reputazione — distinzione tra servizi non configurati (🔑 `skipped`) e servizi attivi ma non pertinenti per questa email (➖ `not_applicable`)
- **Correzione critica** — `GET /api/analysis/{job_id}` ora restituisce la stessa struttura di `POST`, risolvendo il problema dei dettagli vuoti al click sulle analisi in lista

### Migliorato
- Suite di test: da 79 a **94 test**
- Campo NLP salvato nel database e recuperato correttamente al GET

---

## [0.2.0] — 2026

### Aggiunto
- **Localizzazione italiano/inglese** — tutta l'interfaccia e i messaggi di analisi; pulsante IT/EN nella navbar; impostazione permanente via `LANGUAGE` nel file `.env`; endpoint `POST /api/settings/language`
- **Input manuale sorgente email** — scheda "Incolla sorgente" per analizzare email senza salvare un file; endpoint `POST /api/manual/`
- **HTML nascosto espanso** — sezione dedicata nella scheda Body con testo effettivamente nascosto estratto, tecniche CSS usate e conteggio elementi; campo `raw_hidden_content` nell'API
- **VirusTotal** — implementazione completa del connettore con analisi di IP, URL e hash degli allegati
- **Registro servizi reputazione** — stato visibile per ogni servizio (interrogato, skipped, errore, pulito, malevolo) indipendentemente dai risultati
- Endpoint `GET /api/settings/` per leggere la configurazione corrente

### Migliorato
- `start.bat` / `start.sh` — selezione automatica della versione Python corretta tra più versioni installate; rigenerazione automatica del venv se la versione cambia
- Dipendenze aggiornate per compatibilità con Python 3.13
- Rimosso warning deprecation Pydantic v2
- Suite di test: da 52 a **79 test**

### Corretto
- `lxml` sostituito con `html.parser` (stdlib) — elimina la dipendenza da Visual C++ su Windows
- `sqlalchemy==2.0.30` aggiornato a `2.0.48` — fix compatibilità con Python 3.14 (`__firstlineno__`)
- `pytest-asyncio==0.23.6` aggiornato a `1.3.0` — fix conflitto con `pytest==9.x`
- `start.bat` — rimosso `--reload` che causava crash con `multiprocessing` su Python 3.14 + Windows

---

## [0.1.0] — 2026

### Prima release

- **Parser email** — supporto completo `.eml` e `.msg`; estrazione di tutti i campi header; multipart e allegati
- **Analisi header** — SPF/DKIM/DMARC, mismatch identità, percorso SMTP, header injection, tool invio massivo
- **Analisi body** — pattern urgenza, CTA sospette, keyword credenziali, link offuscati, form HTML, JavaScript, CSS invisibile, Base64 inline
- **Analisi URL** — IP diretto, URL shortener, Punycode/IDN, DNS lookup, WHOIS età dominio (opzionale)
- **Analisi allegati** — hash MD5/SHA1/SHA256, MIME mismatch, macro VBA (OLE2 e OOXML), JavaScript in PDF, stream sospetti, doppia estensione
- **Risk scoring** — punteggio 0–100 spiegabile, etichette low/medium/high/critical, contributo per modulo
- **Reputazione** — AbuseIPDB, OpenPhish, PhishTank, MalwareBazaar; connettori disattivabili; fallback offline
- **Report .docx** — 8 sezioni, editabile, include note analista
- **Dashboard web** — upload drag & drop, lista analisi, dettaglio con 6 schede
- **Database** — SQLite (default), PostgreSQL opzionale
- **Cross-platform** — Windows 10/11 e Linux; script avvio automatico
- **Suite di test** — 52 test pytest