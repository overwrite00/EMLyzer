# 📋 System Requirements — EMLyzer

Complete system requirements and prerequisites for deploying EMLyzer on Windows, macOS, and Linux.

> [!TIP]
> 🚀 **New to EMLyzer?** Start with the [Installation Guide](./INSTALLAZIONE.md) after reviewing requirements here.

---

## 📊 Quick Reference

| 📦 Component | ✅ Minimum | ⭐ Recommended | 📝 Notes |
|---|---|---|---|
| **Python** | 3.11 | **3.13** | See Python Version section |
| **Memory** | 512 MB | 1 GB | NLP classifier uses ~150 MB |
| **Disk Space** | 500 MB | 1 GB | Python + dependencies + SQLite |
| **Network** | Optional | — | Required only for reputation services |

---

## 🐍 Python Version

<details open>
<summary><strong>❓ Which Python version do I need?</strong></summary>

### Supported Versions

- ✅ **Python 3.13** — Recommended (stable until 2029)
- ✅ **Python 3.12** — Fully supported
- ✅ **Python 3.11** — Fully supported
- ⚠️ **Python 3.14+** — Not recommended (dependencies not yet updated)
- ❌ **Python 3.10 or earlier** — Not supported

### 🔍 Verify Your Installation

**Windows** — Open Command Prompt:
```cmd
python --version
```

**macOS / Linux** — Open Terminal:
```bash
python3 --version
```

Expected output: `Python 3.13.x`

</details>

> [!WARNING]
> ⚠️ If you have Python 3.10 or earlier, you must upgrade before proceeding.
> See [Installation Guide → Python 3.13](./INSTALLAZIONE.md#1-installare-python-313)

---

## 🖥️ Operating System Support

### 🪟 Windows
- **Minimum:** Windows 10 (64-bit)
- **Tested on:** Windows 10, Windows 11
- **Status:** ✅ Fully supported

### 🍎 macOS
- **Minimum:** macOS 12 Monterey
- **Tested on:** 12.x, 13.x, 14.x
- **Status:** ✅ Fully supported

### 🐧 Linux
- **Tested distributions:**
  - Ubuntu 20.04 LTS, 22.04 LTS, 24.04 LTS
  - Debian 11, 12
  - Fedora 38, 39, 40
  - RHEL 9+
- **Status:** ✅ Fully supported

---

## 💻 Hardware Requirements

### 📌 Minimum Configuration
| 🔧 Resource | 📊 Requirement |
|---|---|
| **Processor** | Any modern CPU (Intel Core i3 / AMD Ryzen 3 equivalent) |
| **RAM** | 512 MB free during analysis |
| **Storage** | 500 MB available disk space |

### ⭐ Recommended Configuration
| 🔧 Resource | 📊 Recommendation |
|---|---|
| **Processor** | Intel Core i5 / AMD Ryzen 5 or better |
| **RAM** | 1 GB+ (NLP classifier: ~150 MB) |
| **Storage** | 1 GB+ for database growth |
| **Network** | Broadband connection (for optional reputation services) |

### 🚀 For Batch Email Processing
| 🔧 Resource | 📊 Recommendation |
|---|---|
| **RAM** | 2+ GB |
| **CPU** | Multi-core processor (analysis is parallelized) |
| **Storage** | 2+ GB |

---

## 🌐 Browser Compatibility

The web interface requires a modern browser with ES2020+ JavaScript support.

| 🌍 Browser | 📌 Minimum Version | 💡 Notes |
|---|---|---|
| **Chrome** | 90+ | ⚡ Fastest performance |
| **Firefox** | 88+ | 🦊 Privacy-focused |
| **Safari** | 14+ | 🍎 macOS native |
| **Edge** | 90+ | 🪟 Windows native |

> [!NOTE]
> 📖 **Old browsers** (Internet Explorer 11, Safari 13) are not supported.
> Update your browser if you see layout issues.

---

## 📦 Python Dependencies

All dependencies are installed **automatically** during first run via `start.bat` / `start.sh`.

<details>
<summary><strong>📚 View all dependencies (20+ packages)</strong></summary>

### 🚀 Core Framework
- **fastapi** (0.135.2+) — REST API framework
- **uvicorn** (0.30.0+) — High-performance ASGI server

### 📧 Email Parsing
- **mail-parser** (3.15.0+) — RFC 5322 parser for .eml files
- **extract-msg** (0.41.1+) — Microsoft Outlook .msg parser
- **beautifulsoup4** (4.12.0+) — HTML parsing and analysis

### 🌐 URL & Domain Analysis
- **tldextract** (5.1.0+) — Domain and TLD extraction
- **dnspython** (2.6.0+) — DNS queries (SPF/DKIM/DMARC verification)
- **python-whois** (0.9.4+) — WHOIS lookups for domain age

### 🧠 Machine Learning & NLP
- **scikit-learn** (1.5.0+) — Random Forest phishing classifier
- **nltk** (3.8.1+) — Natural language processing utilities
- **langdetect** (1.0.9+) — Automatic language detection

### 🔗 External Integrations
- **requests** (2.32.0+) — HTTP client for reputation APIs
- **aiohttp** (3.9.0+) — Async HTTP for parallel requests

### 💾 Data Persistence
- **sqlalchemy** (2.0.34+) — ORM with async support
- **aiosqlite** (3.1.0+) — Async SQLite driver

### 📄 Report Generation
- **python-docx** (0.8.11+) — Word document (.docx) generation
- **tinycss2** (1.3.0+) — CSS parsing for HTML sanitization

**Total installation footprint:** ~200 MB after all dependencies are installed.

</details>

---

## ❌ What You DON'T Need

| ❌ | ℹ️ Why you don't need it |
|---|---|
| **Node.js** | Frontend is pre-compiled and bundled |
| **Docker** | Desktop installation only (no containerization required) |
| **PostgreSQL / MySQL** | SQLite is embedded and included |
| **Nginx / Apache** | Built-in web server included |
| **Paid licenses** | Free and open-source software |

---

## 🌐 Optional: Reputation Services

Email threat intelligence is **completely optional**. No registration required for core analysis.

### 🆓 Always Free (No Registration)
- 🟢 Spamhaus DROP
- 🟢 OpenPhish
- 🟢 ASN Lookup
- 🟢 Redirect Chain
- 🟢 crt.sh

### 📋 Free with Registration
- 🟡 PhishTank
- 🟡 abuse.ch services (URLhaus, ThreatFox, MalwareBazaar)
- 🟡 CIRCL Passive DNS
- 🟡 GreyNoise Community

### 💰 Free Tier Available
- 🟠 AbuseIPDB (1,000 requests/day)
- 🟠 VirusTotal (4 requests/minute)
- 🟠 URLScan.io (1,000 requests/day with API key)
- 🟠 Criminal IP, Pulsedive, Hybrid Analysis, Shodan InternetDB

> [!TIP]
> 💡 For detailed setup of any reputation service, see [Configuration Guide](./CONFIGURAZIONE.md)

---

## 🔒 Data Privacy & Security

> [!IMPORTANT]
> 🛡️ **Your data stays with you.** EMLyzer runs entirely locally.

- ✅ **No cloud transmission** — Email analysis happens on your machine only
- ✅ **No telemetry** — Zero data collection or external tracking
- ✅ **Full local storage** — All results stored in local SQLite database
- ✅ **Open source** — Complete source code available for security audit
- ✅ **Offline capable** — Works without internet connection (except reputation services)

### 💾 Data Storage Locations

| 📁 Data | 📍 Location | 📝 Notes |
|---|---|---|
| **Database** | `backend/data/emlyzer.db` | Local SQLite file |
| **Uploaded emails** | `backend/uploads/` | SHA256-named files |
| **Generated reports** | `backend/reports/` | .docx files |

---

## 🚀 Next Steps

1. **🆕 New to EMLyzer?** → [Installation Guide](./INSTALLAZIONE.md)
2. **⚙️ Already installed?** → [Configuration Guide](./CONFIGURAZIONE.md)
3. **📖 Ready to analyze?** → [Usage Guide](./UTILIZZO.md)
4. **💻 Developer?** → [API Reference](./API.md)

---

## ❓ Troubleshooting

<details>
<summary><strong>❌ Can't find Python on my system?</strong></summary>

**Windows:**
1. Open Command Prompt (Win + R → `cmd`)
2. Type: `python --version`
3. If not found, Python is not installed or not in PATH
4. Solution: [Install Python 3.13](./INSTALLAZIONE.md#1-installare-python-313)

**macOS / Linux:**
1. Open Terminal
2. Try: `python3 --version`
3. If not found, install via Homebrew: `brew install python@3.13`

</details>

<details>
<summary><strong>❌ I have Python 3.10. Can I use it?</strong></summary>

No. Python 3.11+ is required. Some dependencies don't support 3.10.

**Solution:** Upgrade to Python 3.13 following the [Installation Guide](./INSTALLAZIONE.md).

</details>

---

*← [README](../README.md) | Next: [INSTALLAZIONE →](./INSTALLAZIONE.md)*
