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

> ⚠️ **Nota sui piani gratuiti (aggiornamento 2025)**
>
> I piani gratuiti dei servizi di threat intelligence cambiano nel tempo. Verifica sempre il sito ufficiale prima di configurare una chiave.
>
> | Servizio | Stato piano free |
> |---|---|
> | **GreyNoise Community** | ✅ Free — ~50 ricerche/settimana (community tier) |
> | **URLScan.io** | ✅ Free — 1.000 ricerche/g con chiave; search pubblico senza chiave |
> | **Pulsedive** | ⚠️ Free ridotto — **10 req/giorno** (era 30/min prima di marzo 2024) |
> | **Criminal IP** | ⚠️ Free con crediti — crediti iniziali limitati (verifica limiti aggiornati sul sito) |
> | **SecurityTrails** | ❌ **Nessun piano free** — solo trial temporaneo; prezzi enterprise da ~$11k/anno |

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

### GreyNoise Community

Classifica un IP come `malicious`, `benign` o `unknown`. Distingue i normali scanner di internet (crawlers, ricercatori di sicurezza) dagli attori malevoli, riducendo significativamente i falsi positivi nell'analisi degli header SMTP.

**Come registrarsi:**
1. Vai su [https://www.greynoise.io/](https://www.greynoise.io/)
2. Clicca **"Sign Up"** e crea un account gratuito
3. Nella dashboard vai su **"Account"** → **"API Keys"** → copia la chiave

```env
GREYNOISE_API_KEY=incolla_qui_la_tua_chiave
```

**Limite gratuito:** ~50 ricerche/settimana (community tier).

---

### URLScan.io

Ricerca scansioni esistenti per URL e domini nel database di urlscan.io. Mostra il verdetto (`malicious`/`benign`) dell'ultima scansione disponibile con score e tag.

> **Nota:** la ricerca funziona anche **senza API key** (accesso pubblico con limiti ridotti). La chiave aumenta il limite a 1.000 ricerche/giorno e sblocca funzioni avanzate.

**Come registrarsi (opzionale):**
1. Vai su [https://urlscan.io/user/signup](https://urlscan.io/user/signup)
2. Crea un account gratuito
3. Vai su **"Settings"** → **"API Keys"** → copia la chiave

```env
URLSCAN_API_KEY=incolla_qui_la_tua_chiave
```

**Limite gratuito:** 1.000 ricerche/giorno con chiave; accesso pubblico senza chiave con limiti ridotti.

---

### Pulsedive

Threat intelligence aggregata per IP e URL: assegna un livello di rischio (`none`/`low`/`medium`/`high`/`critical`) con i fattori di rischio specifici rilevati.

> ⚠️ **Attenzione:** a partire da **marzo 2024** il piano free è stato ridotto a **10 richieste al giorno** (era 30 req/min). Con email che contengono molti URL o IP, la quota può essere esaurita rapidamente.

**Come registrarsi:**
1. Vai su [https://pulsedive.com/](https://pulsedive.com/)
2. Crea un account gratuito
3. Vai su **"Dashboard"** → **"API"** → copia la chiave

```env
PULSEDIVE_API_KEY=incolla_qui_la_tua_chiave
```

**Limite gratuito:** 10 richieste al giorno (ridotto da marzo 2024).

---

### Criminal IP

Score di rischio IP su scala 0-4 (Safe / Low / Medium / High / Critical) con geolocalizzazione. Particolarmente efficace per rilevare IP di C&C e infrastrutture botnet.

**Come registrarsi:**
1. Vai su [https://www.criminalip.io/](https://www.criminalip.io/)
2. Clicca **"Sign Up"** e crea un account gratuito
3. Vai su **"My Information"** → **"API Key"** → copia la chiave

```env
CRIMINALIP_API_KEY=incolla_qui_la_tua_chiave
```

**Limite gratuito:** free tier con crediti iniziali limitati. Il piano usa un sistema a crediti — verifica i limiti aggiornati sul sito ufficiale.

---

### SecurityTrails

DNS attuale per domini: record A, MX, NS. Servizio **informativo** (come ASN Lookup e Shodan), utile per tracciare l'infrastruttura del mittente.

> ❌ **SecurityTrails non offre più un piano gratuito.** È disponibile solo un trial temporaneo (2.500 query/mese). I piani a pagamento partono da circa $11.000/anno (prezzi enterprise).
>
> Se non hai una licenza enterprise o un trial attivo, lascia `SECURITYTRAILS_API_KEY` vuota — EMLyzer funziona correttamente senza questo servizio.

**Come attivare il trial:**
1. Vai su [https://securitytrails.com/app/account](https://securitytrails.com/app/account)
2. Crea un account e attiva il trial
3. Vai su **"Account"** → **"API Key"** → copia la chiave

```env
SECURITYTRAILS_API_KEY=incolla_qui_la_tua_chiave
```

**Limite:** solo trial temporaneo (2.500 query/mese); nessun piano free stabile.

---

### Hybrid Analysis (CrowdStrike Falcon)

Ricerca hash degli allegati nel database della sandbox Falcon. Restituisce il verdict (`no specific threat`/`suspicious`/`malicious`), il tipo di file e i tag comportamentali rilevati durante l'analisi.

**Come registrarsi:**
1. Vai su [https://www.hybrid-analysis.com/signup](https://www.hybrid-analysis.com/signup)
2. Compila il modulo (è gratuito con registrazione)
3. Una volta approvato, vai su **"Profile"** → **"API key"** → copia la chiave

```env
HYBRID_ANALYSIS_API_KEY=incolla_qui_la_tua_chiave
```

**Limite:** gratuito con registrazione (limiti aggiornati sul sito).

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
GREYNOISE_API_KEY=abc111def222ghi333jkl444
PULSEDIVE_API_KEY=mno555pqr666stu777vwx888
CRIMINALIP_API_KEY=yz1112abc3334def5556ghi7
SECURITYTRAILS_API_KEY=jkl888mno999pqr000stu111
HYBRID_ANALYSIS_API_KEY=vwx222yz3334abc5556def77
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