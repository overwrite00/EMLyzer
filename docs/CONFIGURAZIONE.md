# Configurazione

Questa guida spiega come personalizzare EMLyzer tramite il file `.env`.

---

## Il file .env

All'avvio, `start.bat` / `start.sh` crea automaticamente `backend/.env`.
Aprilo con qualsiasi editor di testo (Blocco Note su Windows, nano/gedit su Linux).

**Percorso:**
- Windows: `EMLyzer\backend\.env`
- Linux/macOS: `EMLyzer/backend/.env`

> Il file inizia con un punto — su Windows attiva "Mostra elementi nascosti" se non lo vedi.

> Dopo ogni modifica riavvia il programma per applicare le modifiche.

---

## Impostazioni disponibili

### DEBUG
```env
DEBUG=false
```
Mostra log tecnici dettagliati. Lascia `false` per uso normale.

---

### MAX_UPLOAD_SIZE_MB
```env
MAX_UPLOAD_SIZE_MB=25
```
Dimensione massima file email caricabili in MB.

---

### LANGUAGE
```env
LANGUAGE=it
```
Lingua dell'interfaccia: `it` (italiano) o `en` (English).
Puoi cambiare anche dal pulsante IT/EN nell'interfaccia. Per renderla permanente, modifica questo file.

---

## Configurare le API key per la reputazione

I servizi di reputazione sono **completamente opzionali**.
Due funzionano senza chiave: **OpenPhish** e **MalwareBazaar**.

---

### AbuseIPDB

Controlla la reputazione degli IP trovati negli header.

**Come registrarsi:**
1. Vai su [https://www.abuseipdb.com](https://www.abuseipdb.com)
2. Clicca **"Sign Up"** e crea un account gratuito
3. Vai su **"Account"** → **"API"** → copia la chiave

```env
ABUSEIPDB_API_KEY=incolla_qui_la_tua_chiave
```
**Limite gratuito:** 1.000 richieste al giorno.

---

### VirusTotal

Analizza IP, URL e hash con oltre 70 motori antivirus.

**Come registrarsi:**
1. Vai su [https://www.virustotal.com](https://www.virustotal.com)
2. Clicca **"Join our community"** e crea un account gratuito
3. Clicca sul tuo nome → **"API key"** → copia

```env
VIRUSTOTAL_API_KEY=incolla_qui_la_tua_chiave
```
**Limite gratuito:** 4 richieste al minuto, 500 al giorno.
EMLyzer attende automaticamente 15 secondi tra richieste consecutive.

---

### PhishTank

Database URL phishing verificati dalla community.

**Come registrarsi:**
1. Vai su [https://www.phishtank.com/register.php](https://www.phishtank.com/register.php)
2. Crea un account gratuito
3. Vai su [https://www.phishtank.com/api_register.php](https://www.phishtank.com/api_register.php)
4. Registra l'applicazione → copia la chiave

```env
PHISHTANK_API_KEY=incolla_qui_la_tua_chiave
```
**Limite gratuito:** 1.000 richieste al giorno.

---

## Esempio di .env completo

```env
DEBUG=false
MAX_UPLOAD_SIZE_MB=25
LANGUAGE=it

ABUSEIPDB_API_KEY=abc123def456ghi789jkl012
VIRUSTOTAL_API_KEY=xyz987uvw654rst321opq098
PHISHTANK_API_KEY=qrs111tuvw222xyz333abc444
```

---

## Database PostgreSQL (avanzato)

Per uso professionale con grandi volumi di analisi.

> Per uso personale SQLite (predefinito) è sufficiente.

1. Installa PostgreSQL e crea un database dedicato
2. Installa il driver:
   - Windows: `.venv\Scripts\pip install asyncpg`
   - Linux: `.venv/bin/pip install asyncpg`
3. Aggiungi al `.env`:

```env
DATABASE_URL=postgresql+asyncpg://utente:password@localhost/openmail_db
```

---

## Sicurezza del file .env

- **Non caricarlo su GitHub** — il `.gitignore` lo esclude automaticamente
- **Non condividerlo** via email o chat
- Se una chiave è compromessa, rigenerala sul sito del servizio

---

*Torna a → [Utilizzo](UTILIZZO.md) | [API REST](API.md)*
