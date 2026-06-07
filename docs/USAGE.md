# 📖 Usage Guide — EMLyzer

Learn how to analyze suspicious emails, interpret results, and generate professional reports.

> [!TIP]
> 💡 **First time?** Start with the [Installation](./INSTALLATION.md) and [Configuration](./CONFIGURATION.md) guides first.

---

## 📚 Table of Contents

1. [🌐 Open the Interface](#-open-the-interface)
2. [📧 Upload & Analyze Email](#-upload--analyze-an-email)
3. [📊 Understanding Risk Score](#-understanding-the-risk-score)
4. [🔍 Analysis Tabs](#-the-analysis-tabs)
5. [📝 Analyst Notes](#-save-analyst-notes)
6. [📄 Generate Word Report](#-generate-word-report)
7. [📋 Search & Filter](#-search-and-filter-analyses)
8. [🕸 Campaign Detection](#-campaign-detection)
9. [🌐 Change Language](#-change-language)
10. [💡 Practical Examples](#-practical-examples)

---

## 🌐 Open the Interface

After starting the application (`start.bat` on Windows / `./start.sh` on Linux), open your browser:

**http://localhost:8000**

You should see:
- ✅ Email upload area
- ✅ Campaign detection panel
- ✅ Recent analyses list
- ✅ Language selector (IT/EN, top right)

---

## 📧 Upload & Analyze an Email

### 🔄 Option 1: Upload .eml or .msg File

**How to export email from your client:**

| 📧 Client | 📝 Instructions |
|---|---|
| **Gmail** | Open email → three dots ⋮ → **"Download message"** → save `.eml` |
| **Outlook desktop** | Drag email to desktop → creates `.msg` automatically |
| **Outlook web** | Open email → three dots → **"View message source"** → save as `.eml` |
| **Thunderbird** | Menu **File** → **Save As** → **File** → save as `.eml` |
| **Apple Mail** | Menu **File** → **Save As** → format **Message Source** |

**How to upload:**
- **Drag & drop:** drag file into the dotted zone
- **Click:** click zone → select file from your computer

Analysis starts automatically. Results panel opens when done.

---

### 📝 Option 2: Paste Email Source

Useful when you can't save the file.

1. Click **"Paste source"** tab
2. In your email client, get the complete source:
   - **Gmail:** open email → three dots → **"Show original"** → select all → copy
   - **Outlook:** open email → **File** → **Properties** → copy content
3. Paste into the text area
4. Click **"🔍 Analyze source"**

> [!NOTE]
> Text must start with email headers (lines like `From:`, `To:`, `Subject:`).

---

### ⚙️ WHOIS Option (Domain Age Analysis)

The **"🌐 Enable WHOIS (domain age)"** checkbox is **enabled by default**.

The system queries WHOIS servers to verify when each domain in the email was registered. Domains registered < 30 days are a strong phishing signal.

Uncheck only if you want faster analysis and don't care about domain age.

> [!WARNING]
> ⚠️ With WHOIS enabled, analysis takes 20–60 seconds longer.

---

## 📊 Understanding the Risk Score

Every email gets a **0–100 score** and a **label**:

| 🎨 Label | 📊 Score | 📝 Action |
|---|---|---|
| 🟢 **Low** | 0–20 | Probably legitimate |
| 🟡 **Medium** | 20–45 | Verify before clicking links |
| 🔴 **High** | 45–70 | Treat with extreme caution |
| 🟣 **Critical** | 70–100 | Don't click anything, don't open attachments |

### How It's Calculated

The score combines four modules with **adaptive weights:**
- Header 35%
- Body 35%
- URL 20%
- Attachment 10%

Non-applicable modules (e.g., no URLs) don't dilute the score — weights redistribute to present modules.

**Guaranteed minimums** for critical indicators:
- Mismatch From ↔ Return-Path (HIGH) → ≥ Medium score
- VBA macros in attachment → ≥ 25 points
- Dangerous executable → ≥ 40 points

Reputation checks can add up to +30 points.

> [!IMPORTANT]
> ℹ️ Score is a support tool, not a verdict. Always use critical judgment alongside technical data.

---

## 🔍 The Analysis Tabs

Click an analysis in the list to open a panel with **six tabs.**

---

### 📋 Summary Tab

Main overview. Contains:

- **Risk gauge** — semicircular chart with score and module bars
- **Email metadata** — sender, recipient, subject, date, Message-ID, file hash
- **Risk explanation** — list of main indicators with severity
- **Analyst notes** — free-text area (see dedicated section)

---

### 📧 Header Tab

Analyzes email technical headers.

**SPF / DKIM / DMARC Authentication:**

Three verification systems that guarantee the email comes from the claimed domain.

| ✓ Result | 📝 Meaning |
|---|---|
| ✓ Green | Check passed |
| ✗ Red | Check failed — possible spoofing |

Legitimate emails from major organizations (banks, PayPal, Google) pass **all three**.

**Identity Mismatch:**

Compares `From` domain with `Return-Path` and `Reply-To`. If different, replies go to a different address — classic phishing technique.

Suspicious example:
```
From:        security@paypal.com
Return-Path: bounce@evil-domain.ru    ← Different!
Reply-To:    collect@fake-site.com    ← Different!
```

**SMTP Path:** the chain of servers the email traveled through, with IPs and timestamps.

---

### 📝 Body Tab

Analyzes email content.

**Statistics:**

| 📊 Field | 📝 What It Is |
|---|---|
| **Urgency patterns** | Phrases like "urgent", "immediately", "pending", "expires in" |
| **Suspicious CTAs** | "Click here", "Sign in now", "Verify immediately" |
| **Credential keywords** | Requests for password, credit card, IBAN, PIN |
| **HTML forms** | Data collection forms in HTML — **legitimate emails never have these** |
| **JavaScript** | JavaScript code in HTML — abnormal for email |
| **Hidden elements** | Invisible text using CSS to bypass spam filters |
| **Obfuscated links** | Links where visible text ≠ actual destination |

**NLP Analysis:**

Machine learning classifier analyzes text and produces:
- Phishing probability (0–100%)
- Confidence level
- Keywords that influenced the classification

**Hidden HTML Content:**

If present, shows:
- Number of hidden elements
- Actual hidden text
- CSS techniques used (often used to evade spam filters)

**Obfuscated Links:**

```
Visible text:     http://www.paypal.com/verify
Actual target:    http://185.220.101.47/phish/login.php
```

---

### 🔗 URL Tab

Lists and analyzes every link in the email.

**Risk Tags:**

| 🏷️ Tag | ⚠️ Why Suspicious |
|---|---|
| `Direct IP` | Legitimate sites use domain names, not numeric IPs |
| `Shortener` | Hides real destination (e.g., `bit.ly/...`) |
| `Punycode` | Simulates known domains with special chars |
| `HTTP` | Unencrypted — sites asking for data use HTTPS |

---

### 📎 Attachment Tab

Static analysis of attached files (no files are executed).

| 📊 Indicator | 🔴 Severity | 📝 Meaning |
|---|---|---|
| MIME mismatch | High | File disguises itself as different type |
| VBA macros | **Critical** | Dangerous macros in Office files |
| JavaScript in PDF | **Critical** | Executable code hidden in PDF |
| Double extension | High | E.g., `invoice.pdf.exe` — hides dangerous extension |
| Dangerous extension | **Critical** | `.exe`, `.bat`, `.ps1`, `.vbs`, `.js`, `.msi`, etc. |

Each attachment also shows **SHA256 hash** — useful for manual lookup on VirusTotal.

---

### 🌐 Reputation Tab

Checks IP, URL, and hash against public threat databases.

**Before running:** preview of all 19 services with API key status indicator.

**After clicking "Run reputation check"**, results arrive in two phases:

✅ **Phase 1** (< 15s):  
Spamhaus, ASN Lookup, Shodan InternetDB, CIRCL Passive DNS, Criminal IP, OpenPhish, PhishTank, Redirect Chain, URLhaus, URLScan.io, ThreatFox, MalwareBazaar, Hybrid Analysis, Pulsedive

🔄 **Phase 2** (background, auto-updating):  
AbuseIPDB, VirusTotal, crt.sh, GreyNoise, SecurityTrails

**Status Icons:**

| 🔴 Icon | 📝 Status | 📝 Meaning |
|---|---|---|
| ✅ | Clean | Analyzed, no threats found |
| 🔴 | **MALICIOUS** | Found in threat database |
| ⏳ | In progress | SLOW service running (auto-updates) |
| 🔑 | Key missing | API key not configured (see [Configuration](./CONFIGURATION.md)) |
| ➖ | Not applicable | Active but email has no entities of this type |
| ⚠️ | Error | Service connection problem |

**Always-active services (no key required):**
- 🟢 **Spamhaus DROP** — blocklist for malicious IPs
- 🟢 **ASN Lookup** — Autonomous System for each IP
- 🟢 **Shodan InternetDB** — open ports, CVE, tags *(informational)*
- 🟢 **OpenPhish** — phishing URL feed
- 🟢 **URLScan.io** — existing scans for URLs/domains
- 🟢 **Redirect Chain** — follows URL shortener redirects
- 🟢 **crt.sh** — TLS certificates for domain

**Services requiring API key:**
See [Configuration Guide](./CONFIGURATION.md) for setup instructions.

---

## 📝 Save Analyst Notes

In the **Summary** tab, bottom of the page, find **"Analyst Notes"** area.

Useful examples:
```
Sender already reported 01/12/2025.
IP 185.220.101.47 — Tor exit node, reported to SOC.
Attachment sent to sandbox — detected Trojan.AgentTesla.
User informed, password change initiated.
```

Click **"Save notes"** — button shows **"✓ Saved"** for confirmation.

Notes are included in the .docx report. Limit: 10,000 characters.

---

## 📄 Generate Word Report

Click **"📄 Report .docx"** button (top right) in the analysis panel.

Document contains:

| 📄 Section | 📝 Content |
|---|---|
| 1. Executive Summary | Score, label, main indicators |
| 2. Email Metadata | All technical fields |
| 3. Technical Indicators | Header findings and SMTP chain |
| 4. Content Analysis | Body, obfuscated URLs |
| 5. Attachments | Hashes and findings |
| 6. Reputation | Reputation check results (if run) |
| 7. Risk Assessment | Score per module |
| 8. Analyst Notes | Manual observations |

Compatible with Microsoft Word, LibreOffice Writer, Google Docs.

---

## 📋 Search and Filter Analyses

### 🔍 Search Bar

Type any text to filter by subject or sender in real-time.

Found text highlights **yellow** in the list.

> [!NOTE]
> ℹ️ Subjects decode correctly even with emoji, non-ASCII chars, or exotic charsets (RFC 2047).

---

### 🎨 Risk Filters

Click one or more buttons: 🟢 Low · 🟡 Medium · 🔴 High · 🟣 Critical.

Remove filters by clicking ✕ or clicking the active filter again.

---

### 📊 Emails Per Page

Dropdown menu lets you choose display size: **10 / 25 / 50 / 100** per page.

---

### 📥 Export CSV

Click **"📥 Export CSV"** to download current list (openable in Excel or LibreOffice).

---

### 🔘 Pagination

Use navigation buttons:
- **«** → first page
- **← Prev** → previous page
- **Next →** → next page
- **»** → last page

---

### 🗑️ Delete Analysis

Click trash icon 🗑 on the right of a row to delete. Confirmation window appears. Deletion removes record **and associated files** (email file and .docx report).

---

### 🗑️ Bulk Delete

To delete multiple analyses at once:

1. **Select** analyses using checkboxes in first column
2. Header checkbox selects/deselects all on current page
3. When ≥1 selected, **floating action bar** appears at bottom with:
   - Count of selected
   - **"Delete selected"** button (red) — requires confirmation
   - **"Deselect all"** button
4. Selection resets when you change page/filters

> [!CAUTION]
> ⚠️ Deletion is **irreversible**: removes record from DB, email from `uploads/`, and .docx from `reports/`. Max 100 per operation.

---

## 🕸️ Campaign Detection

The **"🕸 Detected Campaigns"** section groups similar emails to identify coordinated attacks.

Click **"Analyze campaigns"** to run analysis on all emails in the database.

System groups emails sharing:

| 🔍 Criterion | 📝 Explanation |
|---|---|
| Identical body | Same text (same template) |
| X-Campaign-ID | Same header identifier |
| Message-ID pattern | Same domain in Message-ID |
| Similar subject | Very similar subjects (threshold-based) |
| Sender domain | Same domain for high-risk emails |

**Threshold slider:** controls subject similarity:
- 30% = many clusters, less precise
- 60% = balanced (default)
- 90% = nearly identical emails only

Each cluster shows: correlation type, common value, email count, max risk, first/last date.

---

## 🌐 Change Language

Buttons **IT** / **EN** (top right) in the interface.

To make permanent, edit `backend/.env`:
```env
LANGUAGE=it
```
or `LANGUAGE=en`, then restart.

---

## 💡 Practical Examples

### 💡 Example 1: Bank Phishing Email

1. Save email as `.eml` from your client
2. Upload to EMLyzer
3. **Check score** — if High or Critical, don't interact with email
4. **Header tab** — SPF/DKIM/DMARC must all PASS for legitimate bank email
5. **URL tab** — links must point to official domain, not numeric IPs
6. If confirmed phishing: don't click anything, add notes, generate report

---

### 💡 Example 2: Suspicious Attachment

1. Upload email
2. **Attachments tab** — check for **"VBA Macros"** or **"JavaScript"** badges
3. Copy **SHA256** and verify on MalwareBazaar and VirusTotal in Reputation tab
4. Never open attachment if critical findings

---

### 💡 Example 3: Company Campaign

1. Upload all suspicious emails (one at a time)
2. Click **"Analyze campaigns"**
3. Expand clusters to see correlated emails
4. Use information to block domain on firewall or report to authorities

---

## ✅ What's Next?

- **Need API keys?** → [Configuration Guide](./CONFIGURATION.md)
- **Using the API?** → [API Reference](./API.md)
- **Having issues?** → [Requirements & Troubleshooting](./REQUIREMENTS.md)

---

*Last updated: 2026-06-07*
*← [Configuration](./CONFIGURATION.md) | [API →](./API.md)*
