# EMLyzer Email Analysis Test - Quick Start

## One-Command Start

```batch
cd D:\GitHub\EMLyzer && run_analysis.bat
```

Done! Results will be in `testing\analysis_results.json`

## What It Does (60 Second Overview)

1. **Finds** 7,911 email samples in `D:\Documenti\Email per test analisi\`
2. **Selects** 60 diverse samples (small/medium/large mix)
3. **Analyzes** each email for threats:
   - Header validation (SPF/DKIM/DMARC)
   - Body phishing indicators
   - URL risk assessment
   - Attachment threats
4. **Scores** each 0-100 (low/medium/high/critical)
5. **Reports** statistics and saves JSON results

## Expected Output (Example)

```
Total samples: 60
Successful: 58
Success rate: 96.7%
Total time: 125.43s

Risk Distribution:
  LOW:       27 ( 46.6%)
  MEDIUM:    18 ( 31.0%)
  HIGH:       9 ( 15.5%)
  CRITICAL:   4 (  6.9%)

Detected Indicators:
  Header findings:      94 (avg 1.62 per email)
  Body findings:       156 (avg 2.69 per email)
  URL findings:        42 (in 89 total URLs)
  Attachment findings: 18 (in 12 total files)
```

## Results File

Location: `D:\GitHub\EMLyzer\testing\analysis_results.json`

Open with:
- Any text editor
- VSCode (recommended, has JSON support)
- Python: `json.load(open('testing/analysis_results.json'))`
- PowerShell: `Get-Content testing\analysis_results.json | ConvertFrom-Json`

## Manual Run (No Batch)

```batch
cd D:\GitHub\EMLyzer
.venv\Scripts\python.exe analyze_email_samples.py
```

## Verify Setup First

```batch
cd D:\GitHub\EMLyzer
.venv\Scripts\python.exe test_import.py
```

Expected output:
```
✓ Config imported: EMLyzer v0.14.1
✓ Email parser imported
✓ Header analyzer imported
✓ Body analyzer imported
✓ URL analyzer imported
✓ Attachment analyzer imported
✓ Scorer imported

✓ All imports successful!
```

## Troubleshooting

### "Virtual environment not found"
→ Run `start.bat` first

### "Module not found"
→ Run from `D:\GitHub\EMLyzer` directory

### "No .eml files found"
→ Check `D:\Documenti\Email per test analisi\` exists

### Too slow?
→ Edit `analyze_email_samples.py` and change `SAMPLE_SIZE = 60` to `30`

### Out of memory?
→ Reduce `SAMPLE_SIZE` to 20 or run in smaller batches

## What Gets Analyzed

For each of 60 emails:

| Component | What's Tested |
|-----------|---------------|
| Headers | SPF/DKIM/DMARC, injection, spoofing, auth chains |
| Body | Phishing CTAs, credential keywords, urgency, hidden content |
| URLs | Domain age, shorteners, IP addresses, threats |
| Attachments | Macros, MIME mismatches, dangerous extensions |

## Timing

- Small emails: 0.8-1.2 seconds each
- Medium emails: 1.5-2.5 seconds each
- Large emails: 2.5-5.0 seconds each
- **Total: ~2-5 minutes for 60 samples**

## Output Fields (Per Email)

```json
{
  "filename": "sample-8.eml",
  "file_size_bytes": 1373,
  "success": true,
  "risk_score": 42.5,
  "risk_label": "medium",
  "risk_explanation": ["reason 1", "reason 2"],
  "detected_indicators": {
    "header_findings": 2,
    "body_findings": 3,
    "url_findings": 1,
    "attachment_findings": 0,
    "total_urls": 5,
    "total_attachments": 0
  },
  "email_metadata": {
    "from": "sender@example.com",
    "to": "victim@example.com",
    "subject": "Urgent Action Required"
  }
}
```

## Key Insights to Look For

1. **Risk Distribution**
   - Normal: 40-50% low, 25-35% medium, 10-15% high, 5-10% critical
   - If skewed: may indicate tuning opportunities

2. **Detected Indicators**
   - Header findings: should average 1.5-2.5 per email
   - Body findings: should average 2.0-3.5 per email
   - URL findings: depends on number of URLs in emails
   - Attachment findings: depends on number of attachments

3. **Analysis Time**
   - Should average 2-3 seconds per email
   - Faster = good optimization
   - Slower = check DNS/WHOIS lookups

4. **Success Rate**
   - Should be >95%
   - Failures indicate parsing or analysis issues

## Advanced: Customize Sample Size

Edit `analyze_email_samples.py`:
```python
SAMPLE_SIZE = 60  # Change to 30, 50, 100, etc.
```

## Advanced: Skip WHOIS Lookups (Faster)

In `analyze_email_samples.py`, change:
```python
url_result = analyze_urls(body_result.extracted_urls)
```

To:
```python
url_result = analyze_urls(body_result.extracted_urls, do_whois=False)
```

Saves ~0.5 seconds per URL analyzed.

## Advanced: Disable NLP

Edit `.env`:
```ini
# Comment out or leave empty to disable:
# LANGUAGETOOL_API_URL=http://localhost:8081
```

Saves ~0.1-0.5 seconds per email.

## Files Reference

| Script | Purpose | Speed | Server Required |
|--------|---------|-------|-----------------|
| `analyze_email_samples.py` | Direct analysis | Fast (2-5 min) | No ✓ |
| `email_analysis_test.py` | API-based test | Slow (5-10 min) | Yes |
| `test_import.py` | Verify setup | <1 sec | No |

## Getting Help

- **Full Documentation**: See `EMAIL_ANALYSIS_TEST_README.md`
- **Setup Summary**: See `TESTING_SETUP_SUMMARY.md`
- **Architecture**: See `CLAUDE.md`
- **Code Examples**: See `backend/tests/test_core.py`

---

**TL;DR**: Run `run_analysis.bat` and wait 3-5 minutes ☕
