# Guida all'Utilizzo

Questa guida spiega come analizzare email sospette, interpretare i risultati e generare report.

---

## Indice

- [Aprire l'interfaccia](#aprire-linterfaccia)
- [Come caricare un'email](#come-caricare-unemail-da-analizzare)
- [Interpretare il punteggio di rischio](#interpretare-il-punteggio-di-rischio)
- [Le schede di analisi](#le-schede-di-analisi)
- [Salvare le note dell'analista](#salvare-le-note-dellanalista)
- [Generare il report Word](#generare-il-report-word)
- [Lista analisi: ricerca e filtri](#lista-analisi-ricerca-e-filtri)
- [Rilevamento campagne](#rilevamento-campagne)
- [Cambiare la lingua](#cambiare-la-lingua)
- [Esempi pratici](#esempi-pratici)

---

## Aprire l'interfaccia

Dopo aver avviato il programma (`start.bat` su Windows / `./start.sh` su Linux), apri il browser su:

**http://localhost:8000**

---

## Come caricare un'email da analizzare

### Modalità 1 — Carica un file .eml o .msg

**Come esportare un'email come file:**

| Client | Procedura |
|---|---|
| **Gmail** | Apri l'email → tre puntini `⋮` → **"Scarica messaggio"** → salva `.eml` |
| **Outlook desktop** | Seleziona l'email e trascinala sul desktop → crea `.msg` automaticamente |
| **Outlook web** | Apri l'email → tre puntini → **"Visualizza sorgente"** → salva come `.eml` |
| **Thunderbird** | Menu **File** → **Salva come** → **File** → salva come `.eml` |
| **Apple Mail** | Menu **File** → **Salva come** → formato **Sorgente del messaggio** |

**Come caricare:**
- *Drag & drop:* trascina il file nella zona tratteggiata dell'interfaccia
- *Clic:* clicca sulla zona → seleziona il file dal tuo computer

L'analisi parte automaticamente dopo il caricamento. Al termine si apre il pannello dei risultati.

---

### Modalità 2 — Incolla il sorgente dell'email

Utile quando non riesci a salvare il file.

1. Clicca sulla scheda **"Incolla sorgente"**
2. Nel tuo client email, visualizza il sorgente completo:
   - **Gmail:** apri l'email → tre puntini → **"Mostra originale"** → seleziona tutto → copia
   - **Outlook:** apri l'email → **File** → **Proprietà** → copia il contenuto
3. Incolla nella grande area di testo
4. Clicca **"🔍 Analizza sorgente"**

Il testo deve iniziare con le intestazioni dell'email (righe tipo `From:`, `To:`, `Subject:`).

---

### Opzione WHOIS (analisi più approfondita)

La casella **"🌐 Abilita WHOIS (età dominio)"** è **attivata per default**.

Il programma interroga i server WHOIS per verificare quando è stato registrato ogni dominio trovato nell'email. Domini registrati da meno di 30 giorni sono un forte segnale di phishing.

Deselezionala solo se vuoi un'analisi più rapida e non ti interessa l'età dei domini.

> ⚠️ Con WHOIS attivato l'analisi richiede 20–60 secondi in più.

---

## Interpretare il punteggio di rischio

Ogni email riceve un **punteggio da 0 a 100** e un'**etichetta**:

| Etichetta | Punteggio | Cosa fare |
|---|---|---|
| 🟢 **Basso** | 0–20 | Probabilmente legittima |
| 🟡 **Moderato** | 20–45 | Verificare prima di cliccare link |
| 🔴 **Alto** | 45–70 | Trattare con estrema cautela |
| 🟣 **Critico** | 70–100 | Non cliccare nulla, non aprire allegati |

**Come viene calcolato:**
Il punteggio combina quattro moduli con **pesi adattivi**: Header 35% + Body 35% + URL 20% + Allegati 10%. I moduli non applicabili (es. URL assenti) non diluiscono il punteggio — il peso viene ridistribuito sui moduli presenti.

Inoltre sono attivi dei **livelli minimi garantiti** per indicatori critici ad alta confidenza: ad esempio, un mismatch tra From e Return-Path (finding HIGH) garantisce sempre almeno un punteggio Moderato, indipendentemente dal resto. Un allegato con macro VBA o un allegato CRITICAL (eseguibile camuffato) garantisce rispettivamente almeno 25 o 40 punti.

I controlli di reputazione possono aggiungere fino a +30 punti.

> ℹ️ Il punteggio è uno strumento di supporto, non una sentenza definitiva. Usa sempre il giudizio critico insieme ai dati tecnici.

---

## Le schede di analisi

Cliccando su un'analisi nella lista si apre un pannello con sei schede.

---

### Scheda Riepilogo

La panoramica principale. Contiene:

- **Misuratore di rischio** — grafico semicircolare con punteggio e barre per modulo
- **Metadati email** — mittente, destinatario, oggetto, data, Message-ID, hash del file
- **Spiegazione del rischio** — elenco degli indicatori principali con livello di gravità
- **Note dell'analista** — area di testo libero (vedi sezione dedicata)

---

### Scheda Header

Analizza le intestazioni tecniche dell'email.

**Autenticazione SPF / DKIM / DMARC:**

Tre sistemi di verifica che garantiscono che l'email provenga davvero dal dominio dichiarato.

| Risultato | Significato |
|---|---|
| ✓ verde | Controllo superato |
| ✗ rosso | Controllo fallito — possibile falsificazione |

Le email legittime di grandi organizzazioni (banche, PayPal, Google...) superano **tutti e tre** questi controlli.

**Mismatch di identità:**

Il programma confronta il dominio `From` con `Return-Path` e `Reply-To`. Se sono diversi, le risposte andrebbero a un indirizzo diverso da quello dichiarato — tecnica classica del phishing.

Esempio sospetto:
```
From:        security@paypal.com
Return-Path: bounce@evil-domain.ru    ← diverso!
Reply-To:    collect@fake-site.com    ← diverso!
```

**Percorso SMTP:** la catena dei server attraverso cui l'email è transitata, con IP e orari.

---

### Scheda Body

Analizza il contenuto dell'email.

**Statistiche:**

| Campo | Cos'è |
|---|---|
| Pattern urgenza | Espressioni come "urgente", "subito", "sospeso", "scade entro" |
| CTA sospette | "Clicca qui", "Accedi ora", "Verifica subito" |
| Keyword credenziali | Richieste di password, carta di credito, IBAN, PIN |
| Form HTML | Moduli di raccolta dati nell'HTML — **le email legittime non li contengono mai** |
| JavaScript | Codice JavaScript nell'HTML — anomalo per un'email |
| Elementi nascosti | Testo invisibile con CSS per aggirare i filtri antispam |
| Link offuscati | Link dove il testo visibile ≠ destinazione reale |

**Analisi NLP:**
Un classificatore machine learning analizza il testo e produce una probabilità di phishing (0–100%), un livello di confidenza e le parole chiave che hanno influenzato la classificazione.

**Contenuto HTML nascosto:**
Se presenti, vengono mostrati: numero di elementi nascosti, il testo effettivamente nascosto, le tecniche CSS usate. Questa tecnica viene usata per ingannare i filtri antispam.

**Link offuscati:**
```
Testo visibile:    http://www.paypal.com/verify
Destinazione reale: http://185.220.101.47/phish/login.php
```

---

### Scheda URL

Lista e analisi di ogni link trovato nell'email.

**Tag di rischio:**

| Tag | Perché è sospetto |
|---|---|
| `IP diretto` | I siti legittimi usano nomi di dominio, non IP numerici |
| `Shortener` | Nasconde la destinazione reale (es. `bit.ly/...`) |
| `Punycode` | Simula domini noti con caratteri speciali (es. `xn--pypal-4ve.com`) |
| `HTTP` | Connessione non cifrata — i siti che chiedono dati usano sempre HTTPS |

---

### Scheda Allegati

Analisi statica dei file allegati (nessun file viene eseguito).

| Indicatore | Gravità | Significato |
|---|---|---|
| MIME mismatch | Alto | Il file si spaccia per un tipo diverso |
| Macro VBA | Critico | Macro pericolose in file Office |
| JavaScript in PDF | Critico | Codice eseguibile nascosto nel PDF |
| Doppia estensione | Alto | Es. `fattura.pdf.exe` — nasconde l'estensione pericolosa |
| Estensione pericolosa | Critico | `.exe`, `.bat`, `.ps1`, `.vbs`, `.js`, `.msi`, ecc. |

Per ogni allegato viene mostrato anche il **hash SHA256** — utile per cercarlo manualmente su database come VirusTotal.

---

### Scheda Reputazione

Verifica IP, URL e hash su database pubblici di minacce.

**Prima dell'esecuzione:** anteprima di tutti i 19 servizi con indicazione se la API key è configurata o meno.

**Dopo aver cliccato "Avvia controllo reputazione"**, i risultati arrivano in due fasi:
- **Fase 1** (pochi secondi): Spamhaus, ASN Lookup, Shodan InternetDB, CIRCL Passive DNS, GreyNoise Community, Criminal IP, OpenPhish, PhishTank, Redirect Chain, URLhaus, URLScan.io, ThreatFox, MalwareBazaar, Hybrid Analysis, Pulsedive, SecurityTrails
- **Fase 2** (in background, aggiornamento automatico): AbuseIPDB, VirusTotal, crt.sh

| Icona | Stato | Significato |
|---|---|---|
| ✅ | Pulito | Analizzato, nessuna minaccia trovata |
| 🔴 | MALEVOLO | Trovato in un database di minacce |
| ⏳ | In elaborazione | Servizio SLOW in elaborazione background (si aggiorna automaticamente) |
| 🔑 | Chiave mancante | API key non configurata (vedi [Configurazione](CONFIGURAZIONE.md)) |
| ➖ | Non applicabile | Attivo ma questa email non ha entità del tipo analizzato (es. nessun URL shortener per Redirect Chain) |
| ⚠️ | Errore | Problema di connessione al servizio |

**Servizi sempre attivi (nessuna chiave richiesta):**
- **Spamhaus DROP** — blocklist IP malevoli di alto profilo
- **ASN Lookup** — Autonomous System Number per ogni IP (ipinfo.io)
- **Shodan InternetDB** — porte aperte, CVE e tag per ogni IP *(ℹ️ informativo)*
- **OpenPhish** — feed URL phishing aggiornato
- **URLScan.io** — scansioni esistenti per URL/domini *(search pubblico, chiave opzionale)*
- **Redirect Chain** — segue i redirect degli URL shortener
- **crt.sh** — certificati TLS del dominio (età, sottodomini)

**Servizi che richiedono API key:**
- **AbuseIPDB** — reputazione IP (header SMTP, X-Originating-IP) (`ABUSEIPDB_API_KEY`)
- **VirusTotal** — IP, URL e hash allegati (70+ engine) (`VIRUSTOTAL_API_KEY`)
- **PhishTank** — URL phishing verificati dalla community (`PHISHTANK_API_KEY`)
- **URLhaus** — database URL malware di abuse.ch (`ABUSECH_API_KEY`)
- **ThreatFox** — database IOC abuse.ch: IP, URL, hash malware (`ABUSECH_API_KEY`)
- **MalwareBazaar** — hash allegati nel database malware (`ABUSECH_API_KEY`)
- **CIRCL Passive DNS** — storico DNS per IP e domini (`CIRCL_API_KEY`) *(ℹ️ informativo)*
- **GreyNoise Community** — classifica IP come scanner/malevolo/benigno (`GREYNOISE_API_KEY`)
- **Criminal IP** — score rischio IP 0-4 con geolocalizzazione (`CRIMINALIP_API_KEY`)
- **Pulsedive** — threat intel aggregata IP e URL (`PULSEDIVE_API_KEY`)
- **SecurityTrails** — DNS attuale e storico per domini (`SECURITYTRAILS_API_KEY`) *(ℹ️ informativo)*
- **Hybrid Analysis** — analisi hash allegati nel database sandbox Falcon (`HYBRID_ANALYSIS_API_KEY`)

Clicca su un servizio per espanderlo e vedere il dettaglio di ogni entità analizzata.

---

## Salvare le note dell'analista

Nella scheda **Riepilogo**, in fondo alla pagina, trovi l'area **"Note dell'Analista"**.

Esempi di contenuto utile:
```
Mittente già segnalato il 12/01/2025.
IP 185.220.101.47 — exit node Tor, segnalato al SOC.
Allegato inviato a sandbox — rilevato Trojan.AgentTesla.
Utente informato, cambio password avviato.
```

Clicca **"Salva note"** — il pulsante mostra **"✓ Salvato"** per conferma.
Le note vengono incluse nel report .docx (sezione 8). Limite: 10.000 caratteri.

---

## Generare il report Word

Clicca il pulsante **"📄 Report .docx"** in alto a destra nel pannello dell'analisi.

Il documento contiene:

| Sezione | Contenuto |
|---|---|
| 1. Executive Summary | Punteggio, label, indicatori principali |
| 2. Email Metadata | Tutti i campi tecnici |
| 3. Indicatori Tecnici | Finding header e catena SMTP |
| 4. Analisi del Contenuto | Body, URL offuscati |
| 5. Allegati | Hash e finding |
| 6. Reputazione | Risultati dei controlli (se eseguiti) |
| 7. Valutazione del Rischio | Punteggio per modulo |
| 8. Note dell'Analista | Osservazioni manuali |

Compatibile con Microsoft Word, LibreOffice Writer, Google Docs.

---

## Lista analisi: ricerca e filtri

### Colonna numerazione `#`

La prima colonna della lista mostra il numero riga assoluto rispetto alla pagina corrente (es. pagina 2 con 25 risultati per pagina inizia da #26).

### Barra di ricerca

Digita qualsiasi testo per filtrare per oggetto o mittente in tempo reale.
Il termine trovato viene **evidenziato in giallo** nella lista.

> ℹ️ L'oggetto viene decodificato correttamente anche se contiene emoji, caratteri non-ASCII o charset esotici (RFC 2047 con fallback UTF-8 → Latin-1 → Windows-1252).

### Filtri per rischio

Clicca uno o più pulsanti: 🟢 Basso · 🟡 Moderato · 🔴 Alto · 🟣 Critico.
Per rimuovere i filtri clicca ✕ o clicca di nuovo sul filtro attivo.

### Selettore email per pagina

Il menu a tendina accanto ai filtri permette di scegliere quante analisi mostrare: **10 / 25 / 50 / 100** per pagina.

### Esporta CSV

Clicca **"📥 Esporta CSV"** per scaricare la lista corrente in formato CSV (apribile con Excel o LibreOffice).

### Paginazione

Usa i pulsanti di navigazione:
- **«** — vai alla prima pagina
- **← Prec** — pagina precedente
- **Succ →** — pagina successiva
- **»** — vai all'ultima pagina

### Eliminare un'analisi

Clicca l'icona 🗑 a destra della riga per eliminare il record. Una finestra di conferma chiede di verificare prima di procedere. L'eliminazione rimuove il record dal database **e i file fisici associati** (file email e report `.docx`).

### Eliminazione massiva

Per eliminare più analisi contemporaneamente:

1. **Seleziona** le analisi usando le checkbox nella prima colonna della tabella
2. La checkbox nell'intestazione seleziona/deseleziona tutte le analisi della pagina corrente
3. Quando almeno un'analisi è selezionata, appare una **barra azioni flottante** in basso al centro con:
   - Conteggio analisi selezionate
   - Pulsante **"Elimina selezionati"** (rosso) — richiede conferma
   - Pulsante **"Deseleziona tutto"**
4. La selezione viene resettata automaticamente quando cambi pagina o filtri

> ⚠️ L'eliminazione è **irreversibile**: rimuove il record dal DB, il file email da `uploads/` e il report `.docx` da `reports/`. Massimo 100 analisi per operazione.

---

## Rilevamento campagne

La sezione **"🕸 Campagne Rilevate"** raggruppa email simili per identificare attacchi coordinati.

**Clicca "Analizza campagne"** per avviare l'analisi su tutte le email nel database.

Il sistema raggruppa le email che condividono:

| Criterio | Spiegazione |
|---|---|
| Body identico | Stesso testo del corpo (stesso template) |
| X-Campaign-ID | Stesso identificatore negli header |
| Message-ID pattern | Stesso dominio nel Message-ID |
| Subject simile | Oggetti molto simili (soglia configurabile) |
| Dominio mittente | Stesso dominio per email ad alto rischio |

**Slider soglia:** controlla quanto devono essere simili i soggetti.
- 30% = molti cluster, meno precisi
- 60% = equilibrio (default)
- 90% = solo email quasi identiche

Ogni cluster mostra: tipo di correlazione, valore comune, numero email, rischio massimo, date prima/ultima occorrenza.

---

## Cambiare la lingua

Pulsanti **IT** / **EN** in alto a destra nell'interfaccia.

Per rendere la scelta permanente, modifica `backend/.env`:
```
LANGUAGE=it
```
oppure `LANGUAGE=en`, poi riavvia.

---

## Esempi pratici

### Esempio 1 — Email di phishing bancario

1. Salva l'email come `.eml` dal tuo client
2. Caricala su EMLyzer
3. **Controlla il punteggio** — se è Alto o Critico, non interagire con l'email
4. **Scheda Header** — SPF/DKIM/DMARC devono essere tutti PASS per un'email legittima di banca
5. **Scheda URL** — i link devono puntare al dominio ufficiale, non a IP numerici
6. Se confermato phishing: non cliccare nulla, inserisci note, genera report

### Esempio 2 — Allegato sospetto

1. Carica l'email
2. **Scheda Allegati** — controlla il badge **"Macro VBA"** o **"JavaScript"**
3. Copia il **SHA256** e usalo nella scheda Reputazione per verificarlo su MalwareBazaar e VirusTotal
4. Non aprire mai l'allegato in caso di finding critici

### Esempio 3 — Campagna aziendale

1. Carica tutte le email sospette ricevute (una per volta)
2. Clicca **"Analizza campagne"**
3. Espandi i cluster per vedere le email correlate
4. Usa le informazioni per bloccare il dominio sul firewall o segnalare agli organi competenti

---

*Prossimo passo → [Configurazione](CONFIGURAZIONE.md)*