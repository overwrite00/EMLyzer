# ⚙️ Configuration — EMLyzer

Customize EMLyzer by configuring the `.env` file and optional reputation services.

> [!TIP]
> 💡 **Reputation services are completely optional.** EMLyzer works perfectly without them for core email analysis.

---

## 📂 The .env File

On first run, `start.bat` / `start.sh` automatically creates `backend/.env`.

Edit it with any text editor (Notepad on Windows, nano/gedit on Linux).

### 📍 File Locations

- **Windows:** `EMLyzer\backend\.env`
- **Linux/macOS:** `EMLyzer/backend/.env`

> [!NOTE]
> The file starts with a dot — on Windows, enable "Show hidden files" if you don't see it.

> [!IMPORTANT]
> After editing, restart the application to apply changes.

---

## ⚙️ Basic Settings

### 🐛 DEBUG
```env
DEBUG=false
```
Shows detailed technical logs. Keep `false` for normal use.

---

### 📦 MAX_UPLOAD_SIZE_MB
```env
MAX_UPLOAD_SIZE_MB=25
```
Maximum email file size in MB.

---

### 🌐 LANGUAGE
```env
LANGUAGE=it
```
Interface language: `it` (Italian) or `en` (English).

You can also change this from the IT/EN button in the app. Modify this file to make it permanent.

---

## 🌐 Reputation Services (Optional)

Threat intelligence services are **completely optional**. Services work without API keys:

✅ **Always free (no registration):**
- Spamhaus DROP
- ASN Lookup
- Shodan InternetDB
- OpenPhish
- Redirect Chain
- crt.sh

📋 **Free with registration:**
- CIRCL Passive DNS
- PhishTank
- abuse.ch services (URLhaus/ThreatFox/MalwareBazaar)

💰 **Free tier available:**
- AbuseIPDB
- VirusTotal
- GreyNoise Community
- URLScan.io
- Criminal IP
- Pulsedive
- Hybrid Analysis

---

## 📡 Configuring Each Service

<details open>
<summary><strong>⚠️ Important: Free Tier Status (2025 Update)</strong></summary>

Threat intel free plans change frequently. Always verify on the official website before configuring:

| 🌐 Service | 📊 Free Tier Status |
|---|---|
| **GreyNoise Community** | ✅ Free — ~50 searches/week |
| **URLScan.io** | ✅ Free — 1,000 searches/day with key |
| **Pulsedive** | ⚠️ Reduced — **10 req/day** (was 30/min before Mar 2024) |
| **Criminal IP** | ⚠️ Free with limited credits |
| **SecurityTrails** | ❌ **No free plan** — enterprise only (~$11k/year) |

</details>

### 🔴 AbuseIPDB

Checks reputation of IPs found in email headers.

**How to register:**
1. Go to [abuseipdb.com](https://www.abuseipdb.com)
2. Click **"Sign Up"** → create free account
3. Go to **"Account"** → **"API"** → copy key

```env
ABUSEIPDB_API_KEY=your_api_key_here
```

**Free limit:** 1,000 requests/day

---

### 🦠 VirusTotal

Analyzes IP, URL, and hash against 70+ antivirus engines.

**How to register:**
1. Go to [virustotal.com](https://www.virustotal.com)
2. Click **"Join our community"** → create free account
3. Click your profile → **"API key"** → copy

```env
VIRUSTOTAL_API_KEY=your_api_key_here
```

**Free limit:** 4 requests/minute, 500/day.  
EMLyzer automatically waits 15 seconds between requests.

---

### 🎣 PhishTank

Verified phishing URL database from the community.

**How to register:**
1. Go to [phishtank.com/register.php](https://www.phishtank.com/register.php)
2. Create free account
3. Go to [phishtank.com/api_register.php](https://www.phishtank.com/api_register.php)
4. Register app → copy key

```env
PHISHTANK_API_KEY=your_api_key_here
```

**Free limit:** 1,000 requests/day

---

### 🔍 CIRCL Passive DNS

Historical DNS resolution for IP and domains: shows which domains pointed to an IP, and which IPs a domain resolved to historically.

**How to register:**
1. Go to [circl.lu/pdns](https://www.circl.lu/pdns/)
2. Click **"Request access"** → fill form (free)
3. Receive username and password via email
4. Insert credentials in format `username:password`

```env
CIRCL_API_KEY=tuo_username:tua_password
```

> **Example:** if username is `mario.rossi@example.com` and password is `abc123`:
> `CIRCL_API_KEY=mario.rossi@example.com:abc123`

**Limit:** No official limit declared; EMLyzer applies conservative 2 req/s rate limit

---

### 🔮 GreyNoise Community

Classifies IP as `malicious`, `benign`, or `unknown`. Distinguishes normal internet scanners from malicious actors, reducing false positives.

**How to register:**
1. Go to [greynoise.io](https://www.greynoise.io/)
2. Click **"Sign Up"** → create free account
3. Dashboard → **"Account"** → **"API Keys"** → copy

```env
GREYNOISE_API_KEY=your_api_key_here
```

**Free limit:** ~50 searches/week (community tier)

---

### 📡 URLScan.io

Searches existing scans for URLs and domains in urlscan.io database. Shows verdict (`malicious`/`benign`), score, and tags.

> **Note:** Works without API key (public search with reduced limits). Key increases limit to 1,000 searches/day.

**How to register (optional):**
1. Go to [urlscan.io/user/signup](https://urlscan.io/user/signup)
2. Create free account
3. Go to **"Settings"** → **"API Keys"** → copy

```env
URLSCAN_API_KEY=your_api_key_here
```

**Free limit:** 1,000 searches/day with key; public access without key with reduced limits

---

### ⚡ Pulsedive

Aggregated threat intelligence for IP and URL: assigns risk level (`none`/`low`/`medium`/`high`/`critical`) with specific risk factors.

> [!WARNING]
> ⚠️ **Important:** Since **March 2024**, free tier reduced to **10 requests/day** (was 30/min). Large emails with many URLs can exhaust quota quickly.

**How to register:**
1. Go to [pulsedive.com](https://pulsedive.com/)
2. Create free account
3. Go to **"Dashboard"** → **"API"** → copy key

```env
PULSEDIVE_API_KEY=your_api_key_here
```

**Free limit:** 10 requests/day (reduced from March 2024)

---

### 🚨 Criminal IP

IP risk score 0-4 (Safe/Low/Medium/High/Critical) with geolocation. Effective for C&C and botnet infrastructure.

**How to register:**
1. Go to [criminalip.io](https://www.criminalip.io/)
2. Click **"Sign Up"** → create free account
3. Go to **"My Information"** → **"API Key"** → copy

```env
CRIMINALIP_API_KEY=your_api_key_here
```

**Free limit:** Free tier with limited credits. Uses credit system — check official site for current limits.

---

### 🛣️ SecurityTrails

Current DNS records for domains (A, MX, NS). Informational service.

> [!CAUTION]
> ❌ **SecurityTrails no longer offers a free plan.** Only temporary trial available (2,500 queries/month). Paid plans start ~$11,000/year (enterprise).
>
> If you don't have enterprise license or active trial, leave `SECURITYTRAILS_API_KEY` empty — EMLyzer works perfectly without it.

**To activate trial:**
1. Go to [securitytrails.com/app/account](https://securitytrails.com/app/account)
2. Create account and activate trial
3. Go to **"Account"** → **"API Key"** → copy

```env
SECURITYTRAILS_API_KEY=your_api_key_here
```

**Limit:** Temporary trial only (2,500 queries/month); no stable free plan

---

### 🔬 Hybrid Analysis (CrowdStrike Falcon)

Searches attachment hashes in Falcon sandbox database. Returns verdict (`no threat`/`suspicious`/`malicious`), file type, and behavioral tags.

**How to register:**
1. Go to [hybrid-analysis.com/signup](https://www.hybrid-analysis.com/signup)
2. Fill form (free with registration)
3. Once approved, go to **"Profile"** → **"API key"** → copy

```env
HYBRID_ANALYSIS_API_KEY=your_api_key_here
```

**Free limit:** Free with registration (limits on official site)

---

### 🧭 abuse.ch (URLhaus, ThreatFox, MalwareBazaar)

One API key covers three services:
- **URLhaus** — malware URL database
- **ThreatFox** — IOC database (IP, URL, malware hash)
- **MalwareBazaar** — malware sample hash database

**How to register:**
1. Go to [auth.abuse.ch](https://auth.abuse.ch/)
2. Create free account
3. Copy your API key

```env
ABUSECH_API_KEY=your_api_key_here
```

> **Note:** If you have `MALWAREBAZAAR_API_KEY` from an older version, it still works for MalwareBazaar. But `ABUSECH_API_KEY` is preferred and covers URLhaus and ThreatFox too.

---

## 📋 Complete .env Example

```env
# Basic settings
DEBUG=false
MAX_UPLOAD_SIZE_MB=25
LANGUAGE=it

# Reputation services (optional)
ABUSEIPDB_API_KEY=abc123def456ghi789jkl012
VIRUSTOTAL_API_KEY=xyz987uvw654rst321opq098
PHISHTANK_API_KEY=qrs111tuvw222xyz333abc444
ABUSECH_API_KEY=mnb555opr666stu777vwx888
CIRCL_API_KEY=username:password
GREYNOISE_API_KEY=abc111def222ghi333jkl444
URLSCAN_API_KEY=jkl888mno999pqr000stu111
PULSEDIVE_API_KEY=mno555pqr666stu777vwx888
CRIMINALIP_API_KEY=yz1112abc3334def5556ghi7
SECURITYTRAILS_API_KEY=vwx222yz3334abc5556def77
HYBRID_ANALYSIS_API_KEY=abc555def666ghi777jkl888
```

---

## 🔐 Security

<details>
<summary><strong>🔒 Protecting your .env file</strong></summary>

- ✅ **Don't commit to GitHub** — `.gitignore` excludes it automatically
- ✅ **Don't share via email or chat**
- ✅ **If a key is compromised, regenerate it** on the service website
- ✅ **Use strong, unique passwords** for each service
- ✅ **Rotate keys periodically** (at least annually)

</details>

---

## 🗄️ Advanced: PostgreSQL Database

For professional use with large analysis volumes.

> [!NOTE]
> For personal use, SQLite (default) is sufficient.

**Steps:**
1. Install PostgreSQL and create dedicated database
2. Install driver:
   ```bash
   pip install asyncpg
   ```
3. Add to `.env`:
   ```env
   DATABASE_URL=postgresql+asyncpg://user:password@localhost/emlyzer_db
   ```

---

## ✅ What's Next?

- **Ready to analyze?** → [Usage Guide](./USAGE.md)
- **Developer?** → [API Reference](./API.md)
- **Need help?** → [Troubleshooting](./REQUIREMENTS.md#-troubleshooting)

---

*Last updated: 2026-06-07*
*← [Installation](./INSTALLATION.md) | [Usage →](./USAGE.md)*
