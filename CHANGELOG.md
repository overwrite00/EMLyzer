# Changelog

Tutte le modifiche significative al progetto sono documentate in questo file.

Il formato segue [Keep a Changelog](https://keepachangelog.com/it/1.0.0/).

---

## [0.3.0] — 2025

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

## [0.2.0] — 2025

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

## [0.1.0] — 2025

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
