# EMLyzer Accuracy Validation Framework

## Overview

The accuracy validation framework is a comprehensive testing suite designed to measure how accurately EMLyzer identifies phishing, malware, spam, and other email threats. It evaluates detection accuracy across five key dimensions:

1. **Phishing Detection** — credential harvest, urgent CTAs, sender spoofing
2. **Malware/Attachment Risk** — executable files, macros, MIME mismatches
3. **Spam/Bulk Sender Detection** — authentication failures, bulk headers
4. **Risk Scoring Calibration** — score distribution and threshold tuning
5. **NLP Classifier Performance** — machine learning classification accuracy

---

## Quick Start

### Run Validation

```bash
cd D:\GitHub\EMLyzer
python testing/run_accuracy_validation.py
```

This script:
- Parses sample emails (`phishing_sample.eml`, `clean_sample.eml`)
- Runs them through all EMLyzer analyzers
- Populates `testing/accuracy_validation.json` with actual results
- Generates accuracy metrics (TP/FP/TN/FN)

### View Results

Results are saved in `testing/accuracy_validation.json` with the following structure:

```json
{
  "metadata": {...},
  "test_cases": [...],
  "actual_results": {
    "TC_001": { "status": "success", "filename": "phishing_sample.eml", ... },
    "TC_002": { "status": "success", "filename": "clean_sample.eml", ... }
  },
  "accuracy_assessment": {
    "phishing_detection": { "expected_label": "HIGH or CRITICAL", "actual_label": "...", "test_passed": true/false },
    "clean_detection": { "expected_label": "LOW", "actual_label": "...", "test_passed": true/false }
  }
}
```

---

## Test Cases

### TC_001: Phishing Sample (`phishing_sample.eml`)

**Threat Profile**: PayPal credential harvesting phishing email

**Key Indicators**:
- **Subject**: "URGENT: Your account has been suspended - Action Required"
- **Sender**: paypa1-support.com (typosquatting PayPal)
- **Authentication**: SPF=fail, DKIM=fail, DMARC=fail
- **Body Content**:
  - Urgency keywords: "suspended", "24 hours", "immediately", "verify account"
  - Phishing CTAs: "click here to verify", "verify now"
  - Credential requests: "provide your credentials and credit card information"
  - Forms: Embedded HTML form for stealing credentials
  - Obfuscated links: href points to `evil.com`, visible text shows `paypal.com`
  - JavaScript: Redirect to tracking domain
  - Hidden elements: "display:none" spam bypass content

**Expected Results**:
- **Risk Score**: 45–100 (HIGH or CRITICAL)
- **Findings**: 6+ HIGH severity, 3+ MEDIUM severity
- **NLP Classification**: phishing (confidence 0.5+)
- **Most Suspicious**: Obfuscated links, forms, auth failures, urgency + credentials

---

### TC_002: Clean Sample (`clean_sample.eml`)

**Threat Profile**: Legitimate GitHub pull request notification

**Key Indicators**:
- **Subject**: "[GitHub] Your pull request was merged"
- **Sender**: noreply@github.com (known legitimate)
- **Authentication**: SPF=pass, DKIM=pass, DMARC=pass
- **Body Content**:
  - No urgency keywords
  - No phishing CTAs (link to PR is verifiable)
  - No credential requests
  - No forms, no JavaScript
  - No obfuscated links
  - Clean, professional transactional tone

**Expected Results**:
- **Risk Score**: 0–20 (LOW)
- **Findings**: 0 HIGH, 0 MEDIUM (or minimal)
- **NLP Classification**: legitimate (confidence 0.5+)
- **Key Factor**: Authentication passes + known legitimate sender

---

## Validation Metrics

### 1. Phishing Detection

#### Expected Behaviors

| Indicator | TC_001 (Phishing) | TC_002 (Clean) |
|-----------|-------------------|----------------|
| `body.urgency_count` | ≥ 3 | 0 |
| `body.phishing_cta_count` | ≥ 2 | 0 |
| `body.credential_keyword_count` | ≥ 1 | 0 |
| `body.forms_found` | ≥ 1 | 0 |
| `body.obfuscated_links` | ≥ 1 | 0 |
| `header.auth_failures` | 3 (SPF, DKIM, DMARC) | 0 |
| `header.return_path_mismatch` | YES | NO |
| `header.x_originating_ip` | 185.220.101.47 (suspicious) | N/A |
| `url.shortener_detected` | YES (bit.ly) | NO |
| `url.direct_ip` | YES (http://185.220.101.47/...) | NO |

#### Accuracy Calculation

- **True Positive (TP)**: TC_001 scored HIGH+, flags phishing indicators ✓
- **True Negative (TN)**: TC_002 scored LOW, no phishing flags ✓
- **False Positive (FP)**: TC_002 scored HIGH (incorrectly)
- **False Negative (FN)**: TC_001 scored LOW (incorrectly)

**Target Metrics**:
- Phishing TP Rate: ≥ 95%
- Phishing FP Rate: < 2%

---

### 2. Malware/Attachment Risk

**Status**: Framework ready (test samples have no attachments)

**Coverage Testing** (when attachments are added):

| Threat Type | Detection Method | Expected Finding |
|-----------|-----------------|------------------|
| `.exe` executable | Extension check | HIGH |
| `.zip` with nested executables | Archive scanning | MEDIUM |
| Macro-enabled Office docs | OLE2/OOXML detection | HIGH |
| MIME mismatch (e.g., .txt → application/x-executable) | MIME type comparison | MEDIUM |
| PDF with embedded streams | PDF stream analysis | HIGH |
| Double extension (file.pdf.exe) | Filename parsing | HIGH |

---

### 3. Spam/Bulk Sender Detection

#### TC_001 Phishing Sample

```
Authentication-Results: mx.example.com;
    spf=fail (sender IP is 185.220.101.47) smtp.mailfrom=paypa1-support.com;
    dkim=fail header.d=paypa1-support.com;
    dmarc=fail action=none header.from=paypa1-support.com
X-Mailer: PHPMailer 6.5.0
```

**Bulk Sender Indicators**:
- ✓ SPF=fail → HIGH severity
- ✓ DKIM=fail → HIGH severity
- ✓ DMARC=fail → HIGH severity
- ✓ PHPMailer user-agent → Known phishing vector
- ✓ No List-Unsubscribe header → Likely spam/phishing

**Expected Spam Score**: HIGH (90+% confidence)

#### TC_002 Clean Sample

```
Authentication-Results: mx.example.com;
    spf=pass (sender IP is 192.30.252.0) smtp.mailfrom=github.com;
    dkim=pass header.d=github.com;
    dmarc=pass action=none header.from=github.com
X-Mailer: GitHub.com
```

**Bulk Sender Indicators**:
- ✓ SPF=pass → INFO
- ✓ DKIM=pass → INFO
- ✓ DMARC=pass → INFO
- ✓ GitHub official user-agent → Legitimate
- ✓ Transactional sender → No spam list

**Expected Spam Score**: LOW (< 10%)

**Metrics**:
- Authentication failure TPR: ≥ 98% (highly correlated with spam/phishing)
- Legitimate pass TNR: ≥ 95% (few false positives)

---

### 4. Risk Scoring Calibration

EMLyzer uses adaptive weighting and deterministic floor rules to ensure emails with critical indicators are not under-scored.

#### Expected Score Ranges

| Category | TC_001 | TC_002 |
|----------|--------|--------|
| Score Range | 45–100 | 0–20 |
| Expected Label | HIGH or CRITICAL | LOW |
| Header Weight | 35% | 35% |
| Body Weight | 35% | 35% |
| URL Weight | 20% | 20% |

#### Scoring Floor Rules

**If TC_001 (phishing) exhibits**:
- 1 HIGH header finding → floor = 20
- 3+ HIGH findings → floor = 45 (guaranteed HIGH label)
- High body findings + NLP phishing → floor = 35

**Expected Result**: TC_001 should score ≥ 45 due to:
- ≥ 3 HIGH header findings (return-path mismatch, auth failures, originating IP)
- ≥ 3 HIGH body findings (forms, obfuscated links, credentials)
- URL indicators (shortener, IP-based URL)

---

### 5. NLP Classifier Performance

EMLyzer uses scikit-learn LogisticRegression + TF-IDF vectorizer to classify email bodies as:
- **phishing** — credential harvest, urgent action requests
- **sextortion** — blackmail, "I have video of you"
- **banking** — account lockout, payment fraud claims
- **legitimate** — transactional, informational

#### Expected Classifications

| Sample | Expected Class | Confidence | Evidence |
|--------|-----------------|------------|----------|
| TC_001 (phishing) | phishing | 0.70+ | urgency + credentials + impersonation |
| TC_002 (clean) | legitimate | 0.70+ | transactional content + known sender |

#### False Positive Risks

**Legitimate emails misclassified as phishing**:
- Password reset links (legitimate but mentions password, credentials)
- High-priority security alerts (urgency keywords)
- Account verification emails (legitimate requests to confirm identity)

**Mitigation**: NLP is one input; header/body/URL context prevents flagging legitimate alerts as phishing.

---

## Interpreting Results

### Success Criteria

#### ✓ Phishing Detection PASSED
```json
{
  "test_id": "TC_001",
  "risk_score": {
    "score": 62.5,
    "label": "high"
  },
  "analysis_results": {
    "header": { "high_count": 4 },
    "body": { "high_count": 3, "phishing_cta_count": 2, "credential_keyword_count": 1 },
    "url": { "high_count": 2 }
  }
}
```

**Reasoning**: Score ≥ 45 (HIGH), multiple HIGH findings across header/body/url, phishing CTA + credentials detected.

#### ✓ Clean Detection PASSED
```json
{
  "test_id": "TC_002",
  "risk_score": {
    "score": 8.3,
    "label": "low"
  },
  "analysis_results": {
    "header": { "high_count": 0, "medium_count": 0 },
    "body": { "high_count": 0, "urgency_count": 0, "phishing_cta_count": 0 },
    "url": { "high_count": 0 }
  }
}
```

**Reasoning**: Score < 20 (LOW), no HIGH findings, authentication passes, no suspicious patterns.

---

### Failure Scenarios

#### ✗ Phishing Under-Detected (Score < 45)

**Potential Causes**:
1. Header findings not counted (auth failures not detected)
   - **Check**: Are SPF/DKIM/DMARC failures parsed correctly?
   - **Fix**: Verify `Authentication-Results` header parsing in `email_parser.py`

2. Body findings insufficient
   - **Check**: Are urgency patterns matched? CTA patterns?
   - **Fix**: Review regex patterns in `body_analyzer.py` URGENCY_PATTERNS, PHISHING_CTAS

3. Floor rules not applied
   - **Check**: Are ≥3 HIGH findings triggering floor = 45?
   - **Fix**: Review floor calculation in `scorer.py` _compute_floors()

#### ✗ Clean Email Over-Detected (Score > 20)

**Potential Causes**:
1. False positive in header analysis
   - **Check**: Is GitHub domain being flagged as suspicious?
   - **Fix**: Review domain reputation checks in `header_analyzer.py`

2. False positive in body analysis
   - **Check**: Does "View the pull request" trigger phishing CTA?
   - **Fix**: Review CTA patterns; may need to exclude legitimate call-to-action phrases

3. False positive in URL analysis
   - **Check**: Is github.com being flagged as new domain?
   - **Fix**: Review domain age checks and exclude known legitimate domains

---

## Expanding the Test Corpus

### To Improve Coverage, Add Samples For:

#### Phishing Variants
- [ ] BEC (Business Email Compromise) — no urgency, CEO impersonation
- [ ] Typosquatting — amazon.com → amaz0n.com, microsft.com
- [ ] Spoofed legitimate sender — claims to be from support@yourbank.com
- [ ] Plain text phishing — no HTML obfuscation, pure text attack
- [ ] Image-based phishing — payload in embedded image, no text

#### Legitimate Variants
- [ ] Company newsletter — bulk sender but legitimate
- [ ] Transactional alerts — urgency keywords but legitimate (password reset, payment confirmation)
- [ ] Marketing email — multiple CTAs but legitimate brand
- [ ] Mailing list — Reply-To different from From (legitimate for list management)
- [ ] Forwarded mail — multiple Received headers, legitimate forwarding

#### Malware-Bearing
- [ ] `.exe` attachment (quarantine before adding)
- [ ] Macro-enabled `.docm` with malicious VBA
- [ ] `.zip` with nested `.exe`
- [ ] `.pdf` with embedded executable stream
- [ ] Double extension `.pdf.exe` or `.txt.scr`

#### Spam & Bulk Sender
- [ ] Newsletter from Amazon (legitimate bulk)
- [ ] Notification from multiple senders (legitimate transactional)
- [ ] Unsubscribe link variations (list-unsubscribe header)
- [ ] Forwarded spam (Received chain analysis)

### Running Expanded Validation

```bash
# Add new samples to samples/ directory
cp /path/to/new_sample.eml samples/

# Update test_cases in accuracy_validation.json
{
  "id": "TC_XXX",
  "filename": "new_sample.eml",
  "expected_threat_type": "...",
  "expected_risk_range": "..."
}

# Re-run validation
python testing/run_accuracy_validation.py
```

---

## Performance Benchmarks

### Expected Accuracy (with 2-test baseline)

| Metric | Target | Status |
|--------|--------|--------|
| Phishing TP Rate | ≥ 95% | Pending |
| Phishing FP Rate | < 2% | Pending |
| Spam Detection TPR | ≥ 98% | Pending (auth-based) |
| Spam FP Rate | < 3% | Pending |
| Average Score Accuracy | ± 10% | Pending |

### Execution Time (per email)

| Stage | Expected Duration |
|-------|-------------------|
| Email parsing | < 100ms |
| Header analysis | < 50ms |
| Body analysis | < 200ms (includes NLP) |
| URL analysis (5 URLs) | < 1000ms (includes DNS/WHOIS) |
| Attachment analysis | < 100ms (no extraction) |
| Risk scoring | < 10ms |
| **Total** | < 2s (per email) |

---

## Troubleshooting

### Script Fails to Run

```
ModuleNotFoundError: No module named 'core'
```

**Solution**: Ensure you're in the `D:\GitHub\EMLyzer` directory and have installed dependencies:
```bash
cd D:\GitHub\EMLyzer
python -m pip install -r backend/requirements.txt
python testing/run_accuracy_validation.py
```

### Sample Files Not Found

```
AssertionError: Sample not found: D:\GitHub\EMLyzer\samples\phishing_sample.eml
```

**Solution**: Verify sample files exist:
```bash
ls -la D:\GitHub\EMLyzer\samples/
# Should show: phishing_sample.eml, clean_sample.eml
```

### Results Not Saving

Verify write permissions to `testing/` directory and that JSON is valid:
```bash
python -m json.tool testing/accuracy_validation.json > /dev/null
```

---

## Integration with CI/CD

### GitHub Actions Workflow Example

```yaml
name: Accuracy Validation

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: pip install -r backend/requirements.txt
      - name: Run accuracy validation
        run: python testing/run_accuracy_validation.py
      - name: Check results
        run: |
          python -c "
          import json
          with open('testing/accuracy_validation.json') as f:
              data = json.load(f)
          assessment = data.get('accuracy_assessment', {})
          phishing_pass = assessment.get('phishing_detection', {}).get('test_passed', False)
          clean_pass = assessment.get('clean_detection', {}).get('test_passed', False)
          if not (phishing_pass and clean_pass):
              exit(1)
          "
```

---

## References

- EMLyzer CLAUDE.md — Project memory and risk scoring algorithm
- `backend/core/analysis/scorer.py` — Detailed floor rules and weighting
- `backend/core/analysis/body_analyzer.py` — Phishing pattern detection
- `backend/core/analysis/header_analyzer.py` — Authentication and sender validation

---

## Contributing Test Cases

Have a sample email you'd like to contribute?

1. Sanitize (remove real email addresses, company names)
2. Save as `.eml` in `samples/` directory
3. Document expected indicators in `accuracy_validation.json`
4. Submit PR with results

---

**Last Updated**: 2026-05-20  
**Validation Framework Version**: 1.0  
**Status**: Ready for execution
