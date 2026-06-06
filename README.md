# 🔍 EMLyzer

![EMLyzer](images/emlyzer_cover.png)

**Open-source email threat analysis platform** for identifying spam, phishing, and malicious content with precision.

EMLyzer analyzes suspicious emails by uploading `.eml` or `.msg` files, or pasting the raw source directly. In seconds, it delivers a **complete report** with explainable risk score, header analysis, body content assessment, URL evaluation, attachment inspection, and reputation service checks.

> [!TIP]
> 💡 **No API keys required to get started.** Integrations with external services (AbuseIPDB, VirusTotal, etc.) are optional and configurable later.

---

## 📚 Documentation Index

| 📄 Document | 📝 Purpose |
|---|---|
| [📋 REQUIREMENTS.md](docs/REQUIREMENTS.md) | System requirements and prerequisites |
| [🚀 INSTALLATION.md](docs/INSTALLATION.md) | Step-by-step installation guide |
| [⚙️ CONFIGURATION.md](docs/CONFIGURATION.md) | Environment setup and API keys |
| [📖 USAGE.md](docs/USAGE.md) | How to use the application |
| [📡 API.md](docs/API.md) | REST API reference for developers |

---

## ⚡ Quick Start

### 🪟 Windows
1. Install **Python 3.13** from [python.org](https://www.python.org/downloads/) *(check "Add Python to PATH")*
2. Download and extract the project
3. Double-click **`start.bat`**
4. Open your browser to **http://localhost:8000**

### 🐧 Linux / macOS
```bash
git clone https://github.com/0verwrite/EMLyzer.git
cd EMLyzer
chmod +x start.sh
./start.sh
```

Then open **http://localhost:8000**

> ⏱️ **First run** downloads and installs dependencies (~2-5 minutes). Subsequent runs start in seconds.

---

## 🎯 What It Does

```
Email (.eml / .msg / plain text)
         │
         ▼
┌─────────────────────────────────────────────┐
│  📧 Header Analysis    → SPF/DKIM/DMARC,    │
│                          identity mismatch,  │
│                          SMTP routing        │
│                                             │
│  📝 Body Analysis      → phishing patterns, │
│                          obfuscated links,   │
│                          hidden HTML, NLP   │
│                                             │
│  🔗 URL Analysis       → direct IPs,        │
│                          shorteners,         │
│                          Punycode, domain    │
│                          age (WHOIS)        │
│                                             │
│  📎 Attachment Analysis → hashes, VBA      │
│                          macros, JS in PDF  │
│                                             │
│  🌐 Reputation Checks  → AbuseIPDB,        │
│                          VirusTotal,        │
│                          OpenPhish, PhishTank
│                          Shodan, URLhaus... │
└─────────────────────────────────────────────┘
         │
         ▼
    📊 Risk Score 0–100 + 📄 Editable .docx Report
```

---

## ✨ Key Features

- 🔍 **Complete email analysis** — Headers, body, URLs, attachments
- 🧠 **AI-powered phishing detection** — Machine learning classifier (Random Forest)
- 🌐 **Multi-language support** — Italian 🇮🇹 and English 🇬🇧
- 🛡️ **19 reputation services** — AbuseIPDB, VirusTotal, crt.sh, Shodan, and more
- 📄 **Editable reports** — Generate professional Word (.docx) documents
- 🎨 **Modern web UI** — Clean, responsive interface (React 19 + Vite)
- 💾 **Offline-first** — No cloud dependencies, local SQLite database
- 🆓 **Free & open-source** — MIT license, MIT licensed dependencies only
- 🚀 **Fast analysis** — Email analyzed in seconds, not minutes
- 📱 **Cross-platform** — Windows, macOS, Linux

---

## 🔧 Version

**v0.15.1** — 🐛 Bugfix release: Campaign detection now includes visible HTML text (Silvercrest and other campaigns correctly detected), NLP score consistency fixed (both backend and frontend use standard mathematical rounding), removed duplicate emoji, cleaned debug logging. All 119 tests passing ✅, production-ready.

📖 **See full version history** → [CHANGELOG.md](./CHANGELOG.md)

---

## 📋 System Requirements

- **Python** 3.11–3.13 (3.13 recommended ⭐)
- **RAM** 512 MB minimum (1 GB recommended)
- **Disk** 500 MB for installation
- **Browser** Chrome, Firefox, Safari, or Edge (90+)

> [!IMPORTANT]
> ✅ For complete requirements, see [REQUIREMENTS.md](docs/REQUIREMENTS.md)

---

## 🚀 Getting Started

### 1️⃣ Install Requirements
Follow [INSTALLATION.md](docs/INSTALLATION.md) for step-by-step instructions.

### 2️⃣ Configure (Optional)
Set up optional reputation services in [CONFIGURATION.md](docs/CONFIGURATION.md).

### 3️⃣ Start Analyzing
Learn the interface in [USAGE.md](docs/USAGE.md).

### 💻 For Developers
Explore the API in [API.md](docs/API.md).

---

## 🏗️ Architecture

| Layer | Technology | Notes |
|---|---|---|
| **Backend** | Python 3.13, FastAPI, SQLAlchemy async | REST API + email analysis engine |
| **Frontend** | React 19, Vite 8, no external UI libs | Responsive web dashboard |
| **Database** | SQLite (local) | No external DB required |
| **Analysis** | scikit-learn NLP, dnspython, beautifulsoup4 | Phishing detection + URL parsing |
| **Reports** | python-docx | Editable Word documents |

---

## 📊 Test Suite

✅ **119 automated tests** — all passing, zero technical debt

- Unit tests for all analyzers
- Integration tests for API routes
- Reputation service mocking
- CI/CD on every commit (GitHub Actions)

Run locally:
```bash
./run_tests.sh    # Linux/macOS
run_tests.bat     # Windows
```

---

## 🔐 Privacy & Security

- 🛡️ **No cloud dependencies** — Everything runs locally
- 🔒 **No telemetry** — Zero data collection
- 📁 **Local SQLite** — Your data stays on your machine
- 🔓 **Open source** — Fully auditable code
- ⚡ **Offline capable** — Works without internet (except reputation services)

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit changes with clear messages
4. Push to your fork
5. Open a Pull Request to `develop` branch

> [!NOTE]
> 📖 All PRs should target the **`develop`** branch, not `main`.
> See [Development Guide](./CLAUDE.md) for details.

---

## 📜 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## 🙋 Support

- 📖 **Documentation:** See [docs/](docs/) folder
- 🐛 **Report issues:** [GitHub Issues](https://github.com/0verwrite/EMLyzer/issues)
- 💬 **Questions:** Open a [GitHub Discussion](https://github.com/0verwrite/EMLyzer/discussions)

---

## 👨‍💻 Credits

Developed by **Graziano Mariella**

Distributed with MIT License · [View License](LICENSE)

---

*Ready to get started?* → [Installation Guide](docs/INSTALLATION.md)
