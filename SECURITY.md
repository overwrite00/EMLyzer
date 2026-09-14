# 🔒 Security Policy

## Security Model

EMLyzer is designed with security-first principles:

- **Offline-first analysis** — All email parsing and analysis runs locally; no data is sent externally by default
- **No cloud dependencies** — Core functionality requires no internet connection or API keys
- **Optional reputation services** — External API integrations (AbuseIPDB, VirusTotal, etc.) are entirely optional and user-configured
- **Local-first database** — SQLite database stores results locally on disk
- **Transparent threat analysis** — All detection logic is open-source and auditable

---

## 🛡️ Privacy Principles

### What We Don't Do

- ❌ No user accounts or authentication required
- ❌ No telemetry or usage tracking
- ❌ No data collection or analytics
- ❌ No cloud processing or storage
- ❌ No third-party tracking scripts

### Data Control

- ✅ All email data stays on your machine
- ✅ You control which reputation services are used (or use none)
- ✅ You own your analysis database
- ✅ You can delete analyses at any time
- ✅ Full source code transparency

---

## 🔐 Technical Security

### Email Parsing

- Uses trusted, audited parsing libraries: `mail-parser` (EML) and `extract-msg` (MSG)
- Input validation on all parsed email fields
- HTML/JavaScript sanitization using `bleach` to prevent XSS in body analysis
- Safe handling of MIME encodings and nested structures

### URL Analysis

- Domain and IP address extraction and validation
- Punycode detection (homoglyph spoofing prevention)
- WHOIS and DNS queries use read-only lookups (no modification)
- Shortener detection and redirect chain analysis
- No automatic navigation to URLs (reporting only)

### Attachment Analysis

- **By design**: Attachments are NOT executed
- Hash computation (MD5, SHA1, SHA256) for integrity verification
- MIME type validation against file extension
- Detection of embedded macros and JavaScript in documents
- Stream analysis for suspicious PDF patterns

### Reputation Services

- Optional and configurable per service
- API keys stored locally in `.env` (not synced to git)
- All reputation lookups are read-only queries
- Rate limiting respected (no brute-force scanning)
- Requests authenticated with user-provided credentials only

### Threat Intelligence (feed IOC, campagne note) — v0.17

EMLyzer non implementa un sistema di autenticazione/login. A partire dalla
v0.17, alcuni endpoint modificano configurazione che influisce sul verdetto
di rischio delle analisi (forzare il refresh di un feed, creare/modificare
una campagna nota, approvare una proposta auto-generata):

- **Default di rete**: `start.sh`/`start.bat` ascoltano di default su
  `127.0.0.1` (loopback), non più `0.0.0.0`. Esporre l'app su altre
  interfacce è opt-in esplicito (`EMLYZER_BIND=0.0.0.0`) e stampa un
  avviso in console.
- **Token amministrativo locale**: gli endpoint che scrivono configurazione
  (`POST /api/intel/refresh`, `POST/PUT/DELETE /api/campaigns/known/*`,
  `POST /api/campaigns/proposals/*`) accettano richieste da localhost senza
  alcun token; da qualunque altro indirizzo richiedono l'header
  `X-EMLyzer-Token`, generato al primo avvio e salvato in
  `backend/data/admin_token` (mai in git). **Questo non è un sistema di
  autenticazione completo**: se si espone l'istanza oltre localhost, va
  messo un reverse proxy con autenticazione propria davanti.
- **Feed esterni**: il download dei feed IOC (OpenPhish, Spamhaus, URLhaus)
  e del bollettino RSS CERT-AGID usa URL costanti nel codice (mai
  configurabili via API o `.env`), con cap di dimensione, timeout/deadline
  dedicati e rifiuto di redirect verso indirizzi privati/loopback — a
  difesa da SSRF anche in caso di compromissione di uno di questi domini.
- **Dati persistiti per il backtest**: se `INTEL_STORE_CAMPAIGN_SURFACE` è
  attivo (default), ogni analisi salva token normalizzati e filtrati (anti-PII
  di base) del testo dell'email in `body_indicators.campaign_surface`, usati
  solo per validare nuove campagne contro lo storico. Disattivabile in `.env`.

### Temporary File Cleanup

- Uploaded emails: stored in `backend/uploads/` — deleted after analysis
- Generated reports: stored in `backend/reports/` — deleted when removed via UI
- SQLite database: persists in `backend/data/emlyzer.db` — user controls deletion

---

## 📢 Responsible Disclosure

If you discover a security vulnerability in EMLyzer:

### Reporting Process

1. **Do not open a public GitHub issue** — This exposes the vulnerability
2. **Use GitHub Security Advisory**:
   - Navigate to: https://github.com/overwrite00/EMLyzer/security/advisories
   - Click "Report a vulnerability"
   - Describe the vulnerability in detail

### Timeline

- **48 hours**: We will acknowledge receipt of your report
- **2 weeks** (critical): Target fix timeline for critical vulnerabilities
- **30 days** (high): Target fix timeline for high-severity vulnerabilities
- **Coordinated disclosure**: We will work with you on a disclosure timeline

### Recognition

We appreciate responsible disclosure and will credit you in our security advisory (unless you prefer anonymity).

---

## ⚠️ Known Limitations

### What EMLyzer Does NOT Do

- **Prevents spear-phishing if you visually trust the sender** — EMLyzer detects technical indicators but cannot override human judgment
- **Executes attachments** — By design, EMLyzer analyzes attachments without running them (safe-by-default approach)
- **Performs OCR on images** — Scanned PDFs or image-based phishing are not analyzed (future enhancement)
- **Detects zero-day exploits** — Reputation services have detection delays; new threats may not be flagged
- **Guarantees 100% accuracy** — Like all security tools, false positives and false negatives can occur

### Defense-in-Depth Recommended

EMLyzer is one layer of email security. For comprehensive protection, also use:

- Email gateway filters (at your email provider)
- DMARC/SPF/DKIM enforcement
- Endpoint protection software
- User security training
- Email authentication (2FA/MFA)

---

## 🚀 Future Security Work

Planned improvements (see [CHANGELOG.md](./CHANGELOG.md) for full roadmap):

- YARA rule engine for custom threat detection
- PostgreSQL support for enterprise deployments
- Plugin system for custom analyzers
- Machine learning model improvements
- Automated malware signature updates

---

## 🔄 Security Updates

- **Subscribe to releases**: Watch the [Releases](https://github.com/overwrite00/EMLyzer/releases) page
- **Check security advisories**: [GitHub Security Advisory](https://github.com/overwrite00/EMLyzer/security/advisories)
- **Update regularly**: Use the latest version for security patches

---

## 📚 Additional Resources

- [Code of Conduct](./CODE_OF_CONDUCT.md) — Community guidelines
- [Contributing Guide](./CONTRIBUTING.md) — How to contribute securely
- [REQUIREMENTS.md](./docs/REQUIREMENTS.md) — Dependency information
- [CHANGELOG.md](./CHANGELOG.md) — Version history and security fixes

---

*Last updated: 2026-06-07*
*← [Contributing](./CONTRIBUTING.md) | [Back to README →](./README.md)*
