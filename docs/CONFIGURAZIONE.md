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
Funzionano senza chiave: **Spamhaus DROP**, **ASN Lookup**, **Shodan InternetDB**, **OpenPhish**, **Redirect Chain**, **crt.sh**.
Richiedono registrazione gratuita: **CIRCL Passive DNS**, **PhishTank**, **URLhaus/ThreatFox/MalwareBazaar** (abuse.ch).
Richiedono account con piano free: **AbuseIPDB**, **VirusTotal**.

> ⚠️ **MalwareBazaar**, **URLhaus** e **ThreatFox** richiedono una API key abuse.ch. Registrati su [auth.abuse.ch](https://auth.abuse.ch/) (gratuito) e aggiungi `ABUSECH_API_KEY` nel file `.env` — una sola chiave copre tutti e tre i servizi.

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

### CIRCL Passive DNS

Storico delle risoluzioni DNS per IP e domini: mostra quali nomi di dominio hanno puntato a un IP e quali IP un dominio ha storicamente risolto. Servizio **informativo** (non emette giudizi malevolo/pulito), utile per la threat intelligence e per tracciare l'infrastruttura di un attaccante.

**Come registrarsi:**
1. Vai su [https://www.circl.lu/pdns/](https://www.circl.lu/pdns/)
2. Clicca **"Request access"** e compila il modulo (è gratuito)
3. Riceverai username e password via email
4. Inserisci le credenziali nel formato `username:password`

```env
CIRCL_API_KEY=tuo_username:tua_password
```

> **Esempio:** se lo username è `mario.rossi@example.com` e la password è `abc123`, scrivi:
> `CIRCL_API_KEY=mario.rossi@example.com:abc123`

**Limite:** nessun limite ufficiale dichiarato; EMLyzer applica un rate limit conservativo di 2 req/s.

---

## Esempio di .env completo

```env
DEBUG=false
MAX_UPLOAD_SIZE_MB=25
LANGUAGE=it

ABUSEIPDB_API_KEY=abc123def456ghi789jkl012
VIRUSTOTAL_API_KEY=xyz987uvw654rst321opq098
PHISHTANK_API_KEY=qrs111tuvw222xyz333abc444
ABUSECH_API_KEY=mnb555opr666stu777vwx888
CIRCL_API_KEY=tuo_username:tua_password
```

---

### abuse.ch — URLhaus, ThreatFox e MalwareBazaar

Una sola chiave copre tre servizi:
- **URLhaus** — database URL malware
- **ThreatFox** — database IOC (IP, URL, hash malware)
- **MalwareBazaar** — hash allegati nel database campioni malware

**Come registrarsi:**
1. Vai su [https://auth.abuse.ch/](https://auth.abuse.ch/)
2. Crea un account gratuito
3. Nella pagina account copia la tua API key

```env
ABUSECH_API_KEY=incolla_qui_la_tua_chiave
```

> Hai già `MALWAREBAZAAR_API_KEY` da una versione precedente? Continua a funzionare per MalwareBazaar, ma `ABUSECH_API_KEY` è preferita e copre anche URLhaus e ThreatFox.

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