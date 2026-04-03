# Guida all'installazione — EMLyzer

Questa guida ti accompagna passo dopo passo dall'installazione di Python fino al primo avvio dell'applicazione, sia su Windows che su Linux/macOS.

---

## Indice

1. [Installare Python 3.13](#1-installare-python-313)
   - [Windows](#windows)
   - [Linux (Ubuntu / Debian)](#linux-ubuntu--debian)
   - [macOS](#macos)
2. [Scaricare EMLyzer](#2-scaricare-openmailforensics)
   - [Scarica come archivio ZIP / TAR](#scarica-come-archivio-zip--tar)
   - [Clona con Git (alternativa)](#clona-con-git-alternativa)
3. [Primo avvio](#3-primo-avvio)
   - [Windows](#windows-1)
   - [Linux / macOS](#linux--macos)
4. [Cosa succede al primo avvio](#4-cosa-succede-al-primo-avvio)
5. [Verifica che funzioni](#5-verifica-che-funzioni)
6. [Risolvere problemi comuni](#6-risolvere-problemi-comuni)

---

## 1. Installare Python 3.13

### Windows

**Passo 1 — Scarica Python**

Vai su [https://www.python.org/downloads/](https://www.python.org/downloads/) e clicca sul pulsante giallo **"Download Python 3.13.x"** (la versione esatta potrebbe essere 3.13.1, 3.13.2 ecc. — qualunque 3.13.x va bene).

**Passo 2 — Avvia l'installer**

Fai doppio clic sul file scaricato (es. `python-3.13.2-amd64.exe`).

> ⚠️ **IMPORTANTE:** Prima di cliccare "Install Now", assicurati di spuntare la casella **"Add Python 3.13 to PATH"** in basso. Se non la spunti, il computer non troverà Python quando lo cerca.

![Schermata installer Python con casella PATH evidenziata]

Poi clicca **"Install Now"** e aspetta che finisca.

**Passo 3 — Verifica**

Apri il *Prompt dei comandi*: tasto `Windows` → scrivi `cmd` → Invio.

```
python --version
```

Dovresti vedere: `Python 3.13.x`

Se hai più versioni di Python installate e vuoi usare specificatamente la 3.13, puoi anche usare:
```
py -3.13 --version
```

---

### Linux (Ubuntu / Debian)

**Ubuntu 24.04** include Python 3.12 di default. Per installare Python 3.13:

```bash
sudo apt update
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.13 python3.13-venv -y
```

Verifica:
```bash
python3.13 --version
```

Se stai usando **Ubuntu 22.04 o Debian 12**, il comando sopra funziona ugualmente.

---

### macOS

**Metodo consigliato — Homebrew:**

Se non hai Homebrew installato:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Poi installa Python:
```bash
brew install python@3.13
```

Verifica:
```bash
python3.13 --version
```

**Alternativa — Installer ufficiale:**

Scarica il pacchetto `.pkg` da [https://www.python.org/downloads/macos/](https://www.python.org/downloads/macos/) e segui le istruzioni.

---

## 2. Scaricare EMLyzer

### Scarica come archivio ZIP / TAR

1. Vai alla pagina del progetto su GitHub
2. Clicca sul pulsante verde **"Code"** → **"Download ZIP"**
3. Estrai l'archivio in una cartella a tua scelta, ad esempio:
   - **Windows:** `C:\Users\TuoNome\EMLyzer\`
   - **Linux:** `/home/tuonome/EMLyzer/`

Se hai ricevuto il file come `.tar.gz`:

**Windows** — usa 7-Zip, WinRAR o il File Explorer di Windows 11 (supporta i .tar.gz nativamente).

**Linux / macOS:**
```bash
tar -xzf EMLyzer_v0.4.9.tar.gz
cd EMLyzer
```

### Clona con Git (alternativa)

Se hai Git installato:

```bash
git clone https://github.com/tuo-utente/EMLyzer.git
cd EMLyzer
```

---

## 3. Primo avvio

### Windows

Apri la cartella `EMLyzer` con Esplora File.

Fai doppio clic su **`start.bat`**.

Si aprirà una finestra nera (il Prompt dei comandi) che mostrerà i progressi:

```
============================================
  EMLyzer v0.4.9
============================================

[INFO] Python trovato:
Python 3.13.2

[INFO] Creazione virtual environment...
[INFO] Virtual environment creato.

[INFO] Installazione dipendenze (prima esecuzione: qualche minuto)...
[INFO] Dipendenze OK.

============================================
  Applicazione pronta
============================================

  Apri il browser su:  http://localhost:8000
  Documentazione API:  http://localhost:8000/docs
  Lingua:              pulsante IT/EN in alto a destra

  Premi CTRL+C per fermare
============================================
```

> ⏱️ La **prima esecuzione** scarica e installa tutte le dipendenze: può richiedere **2-5 minuti** a seconda della velocità della connessione. Le esecuzioni successive partono in **pochi secondi**.

### Linux / macOS

Apri il terminale nella cartella del progetto ed esegui:

```bash
chmod +x start.sh   # necessario solo la prima volta
./start.sh
```

L'output sarà simile a quello Windows.

---

## 4. Cosa succede al primo avvio

Lo script `start.bat` / `start.sh` esegue automaticamente questi passi:

1. **Individua la versione di Python** più adatta (cerca 3.13, poi 3.12, poi 3.11)
2. **Crea un virtual environment** isolato in `.venv/` — questo evita conflitti con altri programmi Python installati sul computer
3. **Installa le dipendenze** nel virtual environment (non tocca il Python di sistema)
4. **Crea il file `.env`** con la configurazione di default (copiato da `.env.example`)
5. **Avvia il server web** sulla porta 8000

Il virtual environment e le dipendenze vengono creati **una sola volta**. Le esecuzioni successive saltano questi passi e partono direttamente.

---

## 5. Verifica che funzioni

Dopo l'avvio, apri il browser e vai su:

**http://localhost:8000**

Dovresti vedere l'interfaccia di EMLyzer con:
- Una sezione "Analizza Email" con la zona di upload
- Una sezione "Campagne Rilevate"
- Una sezione "Analisi Recenti" (vuota inizialmente)

Per verificare che il backend risponda correttamente, puoi anche aprire:

**http://localhost:8000/api/health**

Dovresti vedere la risposta JSON:
```json
{"status": "ok", "version": "0.4.9", "app": "EMLyzer"}
```

---

## 6. Risolvere problemi comuni

### ❌ "Python non trovato nel PATH" (Windows)

**Causa:** Python è installato ma la casella "Add Python to PATH" non era spuntata durante l'installazione.

**Soluzione:**
1. Apri nuovamente l'installer di Python
2. Clicca su "Modify" (o disinstalla e reinstalla)
3. Assicurati di spuntare "Add Python 3.13 to PATH"

In alternativa, puoi aggiungere Python al PATH manualmente:
- Cerca "Modifica le variabili d'ambiente" nel menu Start
- In "Variabili di sistema" → "Path" → Aggiungi il percorso di Python (es. `C:\Users\TuoNome\AppData\Local\Programs\Python\Python313\`)

---

### ❌ "Installazione dipendenze fallita" — errore `lxml` o `scikit-learn`

**Causa:** Stai usando Python 3.14 oppure mancano i compilatori C sul sistema.

**Soluzione:** Usa Python 3.13 come descritto in questo documento.

Se hai più versioni di Python installate, lo script seleziona automaticamente quella giusta. Se il problema persiste, cancella il virtual environment e riprova:

**Windows:**
```
rmdir /s /q .venv
start.bat
```

**Linux:**
```bash
rm -rf .venv
./start.sh
```

---

### ❌ "Porta 8000 già in uso"

**Causa:** Un altro programma sta usando la porta 8000, oppure hai avviato EMLyzer due volte.

**Soluzione Windows:**
```
netstat -ano | findstr :8000
taskkill /PID [numero_pid] /F
```

**Soluzione Linux:**
```bash
lsof -i :8000
kill [numero_pid]
```

Poi riavvia `start.bat` / `start.sh`.

---

### ❌ La finestra si chiude subito (Windows)

**Causa:** Si è verificato un errore durante l'avvio e la finestra si è chiusa prima che potessi leggere il messaggio.

**Soluzione:** Apri il Prompt dei comandi manualmente, naviga nella cartella e avvia lo script da lì:

```
cd C:\Users\TuoNome\EMLyzer
start.bat
```

In questo modo la finestra rimane aperta e puoi leggere il messaggio di errore.

---

### ❌ Il browser mostra "Impossibile raggiungere il sito"

**Causa:** Il server non è ancora partito, oppure si è fermato.

**Soluzione:**
1. Controlla che la finestra del terminale con `start.bat` / `start.sh` sia ancora aperta e in esecuzione
2. Aspetta qualche secondo e ricarica la pagina
3. Verifica di stare usando l'indirizzo corretto: **http://localhost:8000** (non https, non port 80)

---

### ❌ "Permission denied" su Linux/macOS

**Causa:** Lo script non ha i permessi di esecuzione.

**Soluzione:**
```bash
chmod +x start.sh run_tests.sh
./start.sh
```

---

## Fermare l'applicazione

Per fermare il server, nella finestra del terminale dove è in esecuzione:

- **Tutti i sistemi:** premi `CTRL + C`

La finestra mostrerà `[INFO] Server fermato.` e poi si chiuderà (su Windows chiede di premere un tasto).

---

## Aggiornare EMLyzer

Per aggiornare a una nuova versione:

1. Scarica il nuovo archivio
2. Estrai nella stessa cartella **sovrascrivendo i file** (i dati nel database vengono preservati)
3. **Cancella il virtual environment** per forzare la reinstallazione delle dipendenze:

   **Windows:** `rmdir /s /q .venv`
   
   **Linux:** `rm -rf .venv`

4. Avvia normalmente con `start.bat` / `start.sh`

> ⚠️ Non sovrascrivere il file `backend/.env` se hai configurato le chiavi API — contiene le tue personalizzazioni.

---

*← [REQUISITI](REQUISITI.md) | Avanti: [UTILIZZO →](UTILIZZO.md)*