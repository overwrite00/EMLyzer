# Requisiti di sistema — EMLyzer

Questa pagina descrive tutto ciò che è necessario installare prima di poter usare EMLyzer.

---

## Requisiti minimi

| Componente | Versione minima | Consigliata | Note |
|---|---|---|---|
| **Python** | 3.11 | **3.13** | Vedi sezione dedicata sotto |
| **RAM** | 512 MB liberi | 1 GB | Il classificatore NLP usa ~150 MB |
| **Spazio disco** | 500 MB | 1 GB | Per Python, dipendenze e database |
| **Connessione** | Opzionale | — | Solo per servizi reputazione |

**Non è necessario installare:**
- Node.js *(il frontend è già compilato e incluso)*
- Docker
- Un database separato *(usa SQLite integrato)*
- Account o abbonamenti a pagamento

---

## Python — versione raccomandata

### Perché Python 3.13?

EMLyzer è stato sviluppato e testato con **Python 3.13**, la versione stabile attuale (supportata con aggiornamenti di sicurezza fino al 2029).

- **Python 3.11 e 3.12** → funzionano correttamente
- **Python 3.13** → versione raccomandata ✅
- **Python 3.14** → non consigliato (versione troppo recente, alcune librerie non ancora aggiornate)
- **Python 3.10 o precedente** → non supportato

### Come verificare se Python è già installato

Apri il terminale e digita:

**Windows** — apri il *Prompt dei comandi* (tasto `Windows` → scrivi `cmd` → Invio):
```
python --version
```

**Linux / macOS** — apri il *Terminale*:
```bash
python3 --version
```

Se ottieni un risultato come `Python 3.13.2` sei a posto e puoi passare direttamente all'installazione.

Se ottieni `Python 3.9.x` o precedente → aggiorna Python seguendo le istruzioni in [INSTALLAZIONE.md](INSTALLAZIONE.md).

Se ottieni `'python' non è riconosciuto` → Python non è installato oppure non è nel PATH — segui le istruzioni in [INSTALLAZIONE.md](INSTALLAZIONE.md).

---

## Sistema operativo

| Sistema | Versione minima | Note |
|---|---|---|
| **Windows** | 10 (64 bit) | Testato su Windows 10 e 11 |
| **Ubuntu / Debian** | Ubuntu 20.04 / Debian 11 | |
| **Fedora / RHEL** | Fedora 38 / RHEL 9 | |
| **macOS** | 12 Monterey | |

---

## Browser web

L'interfaccia funziona con qualsiasi browser moderno. Non servono estensioni o plugin:

- Google Chrome 90+
- Mozilla Firefox 88+
- Microsoft Edge 90+
- Safari 14+

---

## Dipendenze Python

Le dipendenze vengono installate **automaticamente** da `start.bat` / `start.sh` alla prima esecuzione. Non è necessario installarle manualmente.

Per chi vuole sapere cosa viene installato:

| Libreria | Scopo |
|---|---|
| `fastapi` | Framework web del backend |
| `uvicorn` | Server web |
| `mail-parser` | Parsing file `.eml` |
| `extract-msg` | Parsing file `.msg` (Outlook) |
| `beautifulsoup4` | Analisi HTML del corpo email |
| `tldextract` | Estrazione dominio dagli URL |
| `dnspython` | Risoluzione DNS |
| `python-whois` | Interrogazione WHOIS (età dominio) |
| `requests` | Chiamate ai servizi di reputazione |
| `scikit-learn` + `nltk` | Classificatore NLP anti-phishing |
| `python-docx` | Generazione report Word (.docx) |
| `sqlalchemy` + `aiosqlite` | Database locale SQLite |

---

## Privacy e sicurezza dei dati

- Le email analizzate **non vengono mai inviate a server esterni** (salvo attivazione esplicita dei servizi di reputazione)
- Tutti i dati sono salvati **localmente** nel file `backend/data/emlyzer.db`
- I file caricati vengono conservati in `backend/uploads/` con nome anonimizzato
- Non esiste telemetria o raccolta dati verso terzi di alcun tipo

---

## Chiavi API opzionali

Per usare i servizi di reputazione è necessaria una registrazione gratuita:

| Servizio | Analizza | Registrazione |
|---|---|---|
| **AbuseIPDB** | IP sospetti | [abuseipdb.com/account/api](https://www.abuseipdb.com/account/api) |
| **VirusTotal** | IP, URL, hash | [virustotal.com](https://www.virustotal.com) → Account → API Key |
| **PhishTank** | URL phishing | [phishtank.com/api_register.php](https://www.phishtank.com/api_register.php) |
| **OpenPhish** | URL phishing | *(nessuna chiave — gratuito automaticamente)* |
| **MalwareBazaar** | Hash allegati | *(nessuna chiave — gratuito automaticamente)* |

La configurazione è descritta in [UTILIZZO.md](UTILIZZO.md#configurazione-api-opzionali).

---

*← [README](../README.md) | Avanti: [INSTALLAZIONE →](INSTALLAZIONE.md)*
