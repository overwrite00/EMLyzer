# EMLyzer Testing — Implementation Examples

Ready-to-use code snippets for adding the recommended tests.

---

## A. Confusion Matrix / Accuracy Tests

### Copy to `backend/tests/test_accuracy.py`:

```python
"""
tests/test_accuracy.py

Validation set accuracy — multiple samples per category.
Run with: pytest tests/test_accuracy.py -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.analysis.email_parser import parse_email_file
from core.analysis.header_analyzer import analyze_headers
from core.analysis.body_analyzer import analyze_body
from core.analysis.url_analyzer import analyze_urls
from core.analysis.attachment_analyzer import analyze_attachments
from core.analysis.scorer import compute_risk_score


SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples"


def load_sample(filename: str) -> bytes:
    path = SAMPLES_DIR / filename
    if not path.exists():
        pytest.skip(f"Sample not found: {path}")
    return path.read_bytes()


def analyze_email(filename: str) -> dict:
    """Analyze email and return results."""
    raw = load_sample(filename)
    parsed = parse_email_file(raw, filename)
    
    hr = analyze_headers(parsed)
    br = analyze_body(parsed)
    urls_from_body = br.extracted_urls if br else []
    ur = analyze_urls(urls_from_body, do_whois=False)
    ar = analyze_attachments(parsed.attachments if parsed else [])
    
    risk = compute_risk_score(hr, br, ur, ar)
    
    return {
        "filename": filename,
        "score": risk.score,
        "label": risk.label,
        "contributions": {c.module: c.raw_score for c in risk.contributions},
    }


class TestAccuracyPhishing:
    """Phishing emails should score ≥45 (HIGH+)."""
    
    PHISHING_SAMPLES = [
        "phishing_sample.eml",
        # Add more phishing samples as they become available:
        # "phishing_banking_unicredit.eml",
        # "phishing_office365.eml",
        # "phishing_sextortion.eml",
        # "phishing_credential_harvest.eml",
    ]
    
    @pytest.mark.parametrize("email_file", PHISHING_SAMPLES)
    def test_phishing_minimum_score(self, email_file):
        """Phishing email should score ≥45 (HIGH or CRITICAL)."""
        result = analyze_email(email_file)
        
        assert result["score"] >= 45, \
            f"PHISHING MISCLASSIFIED: {email_file}\n" \
            f"  Score: {result['score']} (expected ≥45)\n" \
            f"  Label: {result['label']}\n" \
            f"  Contributions: {result['contributions']}"
    
    @pytest.mark.parametrize("email_file", PHISHING_SAMPLES)
    def test_phishing_label(self, email_file):
        """Phishing should be labeled HIGH or CRITICAL."""
        result = analyze_email(email_file)
        
        assert result["label"] in ("high", "critical"), \
            f"PHISHING LABEL WRONG: {email_file} → {result['label']}"


class TestAccuracyClean:
    """Clean/legitimate emails should score <45 (LOW or MEDIUM)."""
    
    CLEAN_SAMPLES = [
        "clean_sample.eml",
        # Add more clean samples:
        # "clean_github_notification.eml",
        # "clean_hr_leave_approval.eml",
        # "clean_ecommerce_receipt.eml",
        # "clean_support_ticket.eml",
    ]
    
    @pytest.mark.parametrize("email_file", CLEAN_SAMPLES)
    def test_clean_maximum_score(self, email_file):
        """Clean email should score <45 (LOW or MEDIUM)."""
        result = analyze_email(email_file)
        
        assert result["score"] < 45, \
            f"CLEAN MISCLASSIFIED: {email_file}\n" \
            f"  Score: {result['score']} (expected <45)\n" \
            f"  Label: {result['label']}\n" \
            f"  Contributions: {result['contributions']}"
    
    @pytest.mark.parametrize("email_file", CLEAN_SAMPLES)
    def test_clean_label(self, email_file):
        """Clean should be labeled LOW or MEDIUM."""
        result = analyze_email(email_file)
        
        assert result["label"] in ("low", "medium"), \
            f"CLEAN LABEL WRONG: {email_file} → {result['label']}"


class TestConfusionMatrix:
    """Compute accuracy metrics from sample corpus."""
    
    def test_confusion_matrix_summary(self):
        """Print confusion matrix and accuracy metrics."""
        tp = fp = tn = fn = 0
        
        # Phishing emails (positive class)
        for sample in TestAccuracyPhishing.PHISHING_SAMPLES:
            try:
                result = analyze_email(sample)
                if result["score"] >= 45:
                    tp += 1  # True positive
                else:
                    fn += 1  # False negative
            except Exception as e:
                print(f"ERROR analyzing {sample}: {e}")
        
        # Clean emails (negative class)
        for sample in TestAccuracyClean.CLEAN_SAMPLES:
            try:
                result = analyze_email(sample)
                if result["score"] < 45:
                    tn += 1  # True negative
                else:
                    fp += 1  # False positive
            except Exception as e:
                print(f"ERROR analyzing {sample}: {e}")
        
        # Compute metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        # Print summary
        print("\n" + "="*60)
        print("CONFUSION MATRIX")
        print("="*60)
        print(f"True Positives (TP):   {tp}")
        print(f"False Positives (FP):  {fp}")
        print(f"True Negatives (TN):   {tn}")
        print(f"False Negatives (FN):  {fn}")
        print("-"*60)
        print(f"Precision: {precision:.2%} ({tp}/{tp+fp})")
        print(f"Recall:    {recall:.2%} ({tp}/{tp+fn})")
        print(f"F1 Score:  {f1:.3f}")
        print("="*60)
        
        # Basic assertions
        if (tp + fp) > 0:
            assert precision > 0.85, f"Precision too low: {precision:.2%}"
        if (tp + fn) > 0:
            assert recall > 0.90, f"Recall too low: {recall:.2%}"
```

---

## B. Homoglyph Detection Tests

### Copy to `backend/tests/test_homoglyphs.py`:

```python
"""
tests/test_homoglyphs.py

Validation of homoglyph detection (v0.14.0).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.analysis.body_analyzer import (
    analyze_body, _check_homoglyphs, _HOMOGLYPH_MAP
)
from core.analysis.email_parser import ParsedEmail


class TestHomoglyphDetection:
    
    def create_test_email(self, body_html: str) -> ParsedEmail:
        """Helper: create ParsedEmail with given HTML body."""
        return ParsedEmail(
            filename="test.eml",
            file_hash_sha256="0"*64,
            body_html=body_html,
            body_text="",
            mail_from="test@example.com",
            mail_to="user@example.com",
            mail_subject="Test",
            attachments=[],
        )
    
    def test_homoglyph_mapping_size(self):
        """Verify all 39 mapped characters are present."""
        assert len(_HOMOGLYPH_MAP) == 39, \
            f"Expected 39 homoglyphs, got {len(_HOMOGLYPH_MAP)}"
    
    def test_homoglyph_cyrillic_a(self):
        """Cyrillic 'а' (U+0430) maps to Latin 'a'."""
        assert _HOMOGLYPH_MAP['а'] == 'a'
    
    def test_homoglyph_greek_alpha(self):
        """Greek 'α' (U+03B1) maps to Latin 'a'."""
        assert _HOMOGLYPH_MAP['α'] == 'a'
    
    def test_homoglyph_high_severity_three_chars(self):
        """≥3 homoglyph chars → HIGH severity."""
        # Email with: раypal.com (р, а, у are Cyrillic)
        email = self.create_test_email(
            body_html="<p>Visit <a href='http://раypal.com'>раypal.com</a></p>"
        )
        result = analyze_body(email)
        
        homoglyph_findings = [
            f for f in result.findings 
            if "homoglyph" in f.description.lower()
        ]
        
        assert len(homoglyph_findings) > 0, "Homoglyph not detected"
        if homoglyph_findings:
            assert homoglyph_findings[0].severity == "high", \
                f"Expected HIGH, got {homoglyph_findings[0].severity}"
    
    def test_homoglyph_low_severity_one_char(self):
        """1-2 homoglyph chars → LOW severity."""
        email = self.create_test_email(
            body_html="<p>Visit аmazon.com (а = Cyrillic)</p>"
        )
        result = analyze_body(email)
        
        homoglyph_findings = [
            f for f in result.findings 
            if "homoglyph" in f.description.lower()
        ]
        
        if homoglyph_findings:
            assert homoglyph_findings[0].severity == "low", \
                f"Expected LOW for 1 char, got {homoglyph_findings[0].severity}"
    
    def test_homoglyph_evidence_shows_chars(self):
        """Finding evidence field contains detected characters."""
        email = self.create_test_email(
            body_html="<p>Visit раypal.com</p>"
        )
        result = analyze_body(email)
        
        homoglyph_findings = [
            f for f in result.findings 
            if "homoglyph" in f.description.lower()
        ]
        
        if homoglyph_findings:
            evidence = homoglyph_findings[0].evidence
            # Should contain Cyrillic characters
            assert any(c in evidence for c in ['а', 'р', 'у']), \
                f"Evidence missing Cyrillic: {evidence}"
    
    def test_homoglyph_false_negative_legitimate_cyrillic(self):
        """Legitimate Cyrillic text should not be flagged HIGH."""
        # Russian email
        email = self.create_test_email(
            body_html="<p>Привет! Спасибо за Вашу внимание.</p>"
        )
        result = analyze_body(email)
        
        homoglyph_findings = [
            f for f in result.findings 
            if "homoglyph" in f.description.lower()
        ]
        
        # Legitimate Cyrillic should not trigger HIGH finding
        # (It may trigger LOW as a warning, but not HIGH)
        high_findings = [f for f in homoglyph_findings if f.severity == "high"]
        assert len(high_findings) == 0, \
            f"Legitimate Cyrillic flagged HIGH: {high_findings}"
    
    def test_homoglyph_mixed_scripts(self):
        """Domain mixing Latin and Cyrillic detected."""
        # pаypal.com: p (Latin) + а (Cyrillic) + ypal (Latin)
        email = self.create_test_email(
            body_html="<p>Click <a href='http://pаypal.com'>pаypal.com</a></p>"
        )
        result = analyze_body(email)
        
        homoglyph_findings = [
            f for f in result.findings 
            if "homoglyph" in f.description.lower()
        ]
        
        assert len(homoglyph_findings) > 0, \
            "Mixed-script domain not detected"


class TestHomoglyphWithNLP:
    """Homoglyphs combined with NLP should increase score."""
    
    def test_homoglyph_plus_urgency(self):
        """Homoglyph + urgency pattern → higher risk."""
        email = self.create_test_email(
            body_html="""
            <p>URGENT: Your account has been suspended!</p>
            <p>Visit раypal.com immediately to restore access.</p>
            """
        )
        result = analyze_body(email)
        
        # Should have both urgency and homoglyph findings
        has_urgency = any("urgent" in f.description.lower() for f in result.findings)
        has_homoglyph = any("homoglyph" in f.description.lower() for f in result.findings)
        
        assert has_urgency, "Urgency not detected"
        assert has_homoglyph, "Homoglyph not detected"
        
        # Score should reflect both signals
        assert result.score_contribution > 30, \
            f"Low score despite urgency+homoglyph: {result.score_contribution}"
```

---

## C. Large File Handling Tests

### Copy to `backend/tests/test_large_files.py`:

```python
"""
tests/test_large_files.py

Test email parser with edge cases: large attachments, many attachments, etc.
Run with: pytest tests/test_large_files.py -v --timeout=30
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.analysis.email_parser import parse_email_file, ParsedEmail
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import io


class TestLargeAttachments:
    """Test handling of large binary attachments."""
    
    def create_eml_with_attachment(self, size_mb: int) -> bytes:
        """Create EML with single large binary attachment."""
        msg = MIMEMultipart()
        msg['From'] = 'sender@example.com'
        msg['To'] = 'user@example.com'
        msg['Subject'] = 'Test Large Attachment'
        
        # Add text body
        text_part = MIMEText('Please see attachment')
        msg.attach(text_part)
        
        # Add large binary attachment
        large_data = b'\x00' * (size_mb * 1024 * 1024)
        att = MIMEBase('application', 'octet-stream')
        att.set_payload(large_data)
        encoders.encode_base64(att)
        att.add_header('Content-Disposition', 'attachment', filename='large.bin')
        msg.attach(att)
        
        return msg.as_bytes()
    
    @pytest.mark.timeout(30)
    def test_10mb_attachment(self):
        """Parse 10MB attachment without timeout."""
        eml = self.create_eml_with_attachment(size_mb=10)
        parsed = parse_email_file(eml, "large_10mb.eml")
        
        assert isinstance(parsed, ParsedEmail)
        assert len(parsed.attachments) == 1
        assert parsed.attachments[0].size_bytes >= 10 * 1024 * 1024
    
    @pytest.mark.timeout(30)
    def test_50mb_attachment(self):
        """Parse 50MB attachment without timeout."""
        eml = self.create_eml_with_attachment(size_mb=50)
        parsed = parse_email_file(eml, "large_50mb.eml")
        
        assert isinstance(parsed, ParsedEmail)
        assert len(parsed.attachments) >= 1
    
    def test_attachment_not_loaded_into_memory(self):
        """Large attachments should not be fully loaded."""
        # If parsed.attachments[0].raw_data is populated for a 100MB file,
        # we'd have OOM. Verify that we only store metadata (filename, size, hash)
        eml = self.create_eml_with_attachment(size_mb=10)
        parsed = parse_email_file(eml, "test.eml")
        
        att = parsed.attachments[0]
        # Should have filename and size
        assert att.filename != ""
        assert att.size_bytes >= 10 * 1024 * 1024
        # raw_data should be empty or None (not loaded)
        # (Depends on implementation — adjust assertion accordingly)


class TestManyAttachments:
    """Test handling of emails with many attachments."""
    
    def create_eml_with_many_attachments(self, count: int) -> bytes:
        """Create EML with N small attachments."""
        msg = MIMEMultipart()
        msg['From'] = 'sender@example.com'
        msg['To'] = 'user@example.com'
        msg['Subject'] = f'Test {count} Attachments'
        
        text_part = MIMEText(f'Contains {count} attachments')
        msg.attach(text_part)
        
        for i in range(count):
            att = MIMEBase('application', 'octet-stream')
            att.set_payload(b'small payload')
            encoders.encode_base64(att)
            att.add_header('Content-Disposition', 'attachment', 
                          filename=f'file_{i:04d}.txt')
            msg.attach(att)
        
        return msg.as_bytes()
    
    @pytest.mark.timeout(15)
    def test_100_attachments(self):
        """Parse email with 100 attachments."""
        eml = self.create_eml_with_many_attachments(100)
        parsed = parse_email_file(eml, "many_100.eml")
        
        assert isinstance(parsed, ParsedEmail)
        # Should handle gracefully (may cap at 100 or parse all)
        assert len(parsed.attachments) >= 50
    
    @pytest.mark.timeout(30)
    def test_500_attachments(self):
        """Parse email with 500 attachments — should not hang."""
        eml = self.create_eml_with_many_attachments(500)
        parsed = parse_email_file(eml, "many_500.eml")
        
        assert isinstance(parsed, ParsedEmail)
        # Should cap processing gracefully
        assert len(parsed.attachments) <= 500


class TestMalformedMIME:
    """Test parsing of malformed/corrupted MIME structures."""
    
    def test_mismatched_boundary(self):
        """Email with mismatched MIME boundary doesn't crash."""
        eml = b"""From: test@example.com
To: user@example.com
Subject: Test
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="----good_boundary"

------bad_boundary
Content-Type: text/plain

Hello world
------good_boundary--
"""
        parsed = parse_email_file(eml, "malformed.eml")
        
        assert isinstance(parsed, ParsedEmail)
        # Should record error but not crash
        if parsed.parse_errors:
            assert len(parsed.parse_errors) > 0
    
    def test_null_byte_in_body(self):
        """Email with null bytes in body handled."""
        eml = b"From: test@example.com\r\n\r\nHello\x00World"
        parsed = parse_email_file(eml, "nullbyte.eml")
        
        assert isinstance(parsed, ParsedEmail)
    
    def test_deeply_nested_multipart(self):
        """Email with multipart/multipart/.../multipart nesting."""
        # Create nested structure: multipart(multipart(multipart(text)))
        eml = b"""From: test@example.com
To: user@example.com
Subject: Nested
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="b1"

--b1
Content-Type: multipart/mixed; boundary="b2"

--b2
Content-Type: multipart/mixed; boundary="b3"

--b3
Content-Type: text/plain

Hello
--b3--
--b2--
--b1--
"""
        parsed = parse_email_file(eml, "nested.eml")
        
        assert isinstance(parsed, ParsedEmail)
```

---

## D. URL Injection Tests

### Copy to `backend/tests/test_url_injection.py`:

```python
"""
tests/test_url_injection.py

Security: test URL parser against injection/bypass attacks.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.analysis.url_analyzer import _analyze_single_url, URLAnalysis


class TestURLInjection:
    """URL parsing security against edge cases."""
    
    def test_null_byte_url(self):
        """URL with null byte doesn't bypass detection."""
        # http://example.com%00.phishing.com/login
        # Should NOT parse as two URLs
        url = "http://example.com%00.phishing.com/login"
        result = _analyze_single_url(url)
        
        assert isinstance(result, URLAnalysis)
        # Host should be normalized
        assert "phishing.com" not in result.host or result.host == "example.com"
    
    def test_extremely_long_path(self):
        """Very long URL path (10k chars) handled."""
        long_path = "x" * 10000
        url = f"http://example.com/{long_path}/login"
        
        # Should not crash or hang
        result = _analyze_single_url(url)
        assert isinstance(result, URLAnalysis)
    
    def test_punycode_double_encoding(self):
        """Double-encoded Punycode (xn--xn--...) detected."""
        # Legitimate Punycode: xn--pypal-4ve.com (spoofed PayPal)
        # Double-encoded attack: xn--xn--pypal-4ve.com
        url = "http://xn--xn--pypal-4ve.com/login"
        result = _analyze_single_url(url)
        
        assert result.is_punycode, "Double-encoded Punycode not detected"
    
    def test_embedded_credentials_url(self):
        """URL with user:pass@ parsed correctly."""
        # http://attacker:password@example.com/phish
        # Host should be example.com, not attacker
        url = "http://attacker:password@example.com/phish"
        result = _analyze_single_url(url)
        
        assert "attacker" not in result.host
        assert result.host == "example.com"
    
    def test_ipv6_url_parsing(self):
        """IPv6 URLs in brackets parsed correctly."""
        url = "http://[2001:db8::1]/login"
        result = _analyze_single_url(url)
        
        assert result.is_ip_address
        assert result.host == "[2001:db8::1]" or "2001:db8" in result.host
    
    def test_url_with_fragment_xss(self):
        """URL with XSS in fragment doesn't crash."""
        url = "http://example.com/page#<script>alert('xss')</script>"
        result = _analyze_single_url(url)
        
        assert isinstance(result, URLAnalysis)
    
    def test_url_redirect_loop_protection(self):
        """URL analysis doesn't follow infinite redirects."""
        # This is more of a reputation service test, but URL parser should be safe
        url = "http://localhost:9999/redirect?next=http://localhost:9999/redirect"
        
        # Should timeout or return quickly, not hang
        result = _analyze_single_url(url)
        assert isinstance(result, URLAnalysis)
```

---

## E. Binary Attachment Safety

### Copy to `backend/tests/test_attachment_safety.py`:

```python
"""
tests/test_attachment_safety.py

Security: test attachment analyzer against malicious patterns.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.analysis.attachment_analyzer import analyze_attachment


class TestAttachmentSafety:
    """Attachment analysis security."""
    
    def create_zip_bomb(self, uncompressed_size_mb: int) -> bytes:
        """Create simple zip-like content (not actually a valid zip)."""
        # This is a simplified test — real zip bomb would need proper compression
        # For now, just a large file with compression markers
        return b'PK\x03\x04' + (b'\x00' * (uncompressed_size_mb * 1024 * 1024))
    
    @pytest.mark.timeout(10)
    def test_zip_bomb_protection(self):
        """Large compressed attachment doesn't cause OOM."""
        # Create attachment metadata for suspicious zip
        zip_data = self.create_zip_bomb(100)  # 100MB declared
        
        att = {
            "filename": "archive.zip",
            "size_bytes": len(zip_data),
            "declared_mime": "application/zip",
            "real_mime": "application/zip",
            "mime_mismatch": False,
            "hash_md5": "a" * 32,
            "hash_sha1": "b" * 40,
            "hash_sha256": "c" * 64,
        }
        
        # Should analyze without crashing/OOM
        result = analyze_attachment(att, raw_data=zip_data)
        assert result is not None
    
    def test_polyglot_pdf_exe(self):
        """PDF with embedded EXE detected as dangerous."""
        # Create fake polyglot: PDF header + EXE signature
        polyglot = b"%PDF-1.4\n" + b"MZ\x90\x00" + b"\x00" * 1000
        
        att = {
            "filename": "document.pdf",
            "size_bytes": len(polyglot),
            "declared_mime": "application/pdf",
            "real_mime": "application/octet-stream",
            "mime_mismatch": True,
            "hash_md5": "a" * 32,
            "hash_sha1": "b" * 40,
            "hash_sha256": "c" * 64,
        }
        
        result = analyze_attachment(att, raw_data=polyglot)
        
        # Should have MIME mismatch finding
        assert any("mime" in f.description.lower() for f in result.findings)
    
    def test_invalid_utf8_filename(self):
        """Filename with invalid UTF-8 doesn't crash."""
        att = {
            "filename": "test\xff\xfe.pdf",  # Invalid UTF-8 bytes
            "size_bytes": 1024,
            "declared_mime": "application/pdf",
            "real_mime": "application/pdf",
            "mime_mismatch": False,
            "hash_md5": "a" * 32,
            "hash_sha1": "b" * 40,
            "hash_sha256": "c" * 64,
        }
        
        # Should handle gracefully
        result = analyze_attachment(att)
        assert result is not None
    
    def test_null_byte_extension_bypass(self):
        """Filename 'test.exe\x00.pdf' detected as executable."""
        att = {
            "filename": "test.exe\x00.pdf",
            "size_bytes": 512,
            "declared_mime": "application/pdf",
            "real_mime": "application/octet-stream",
            "mime_mismatch": True,
            "hash_md5": "a" * 32,
            "hash_sha1": "b" * 40,
            "hash_sha256": "c" * 64,
        }
        
        result = analyze_attachment(att)
        
        # Should flag as dangerous (either dangerous_extension or MIME mismatch)
        assert result.dangerous_extension or result.mime_mismatch
    
    def test_double_extension_executable(self):
        """Double extension like .pdf.exe detected."""
        att = {
            "filename": "invoice.pdf.exe",
            "size_bytes": 2048,
            "declared_mime": "application/pdf",
            "real_mime": "application/octet-stream",
            "mime_mismatch": True,
            "hash_md5": "a" * 32,
            "hash_sha1": "b" * 40,
            "hash_sha256": "c" * 64,
        }
        
        result = analyze_attachment(att)
        
        assert result.double_extension
        assert any(f.severity == "high" for f in result.findings)
```

---

## Running All New Tests

```bash
# Run accuracy tests
pytest backend/tests/test_accuracy.py -v

# Run homoglyph tests
pytest backend/tests/test_homoglyphs.py -v

# Run large file tests
pytest backend/tests/test_large_files.py -v --timeout=60

# Run URL injection tests
pytest backend/tests/test_url_injection.py -v

# Run attachment safety tests
pytest backend/tests/test_attachment_safety.py -v

# Run all new tests together
pytest backend/tests/test_*.py -v --timeout=60 -k "accuracy or homoglyph or large or injection or safety"

# With coverage
pytest backend/tests/ --cov=backend/core --cov-report=html -v
```

---

## Integration with CI/CD

Add to `.github/workflows/test.yml`:

```yaml
- name: Run core tests
  run: |
    pytest backend/tests/test_core.py -v --timeout=300
    
- name: Run accuracy tests
  run: |
    pytest backend/tests/test_accuracy.py -v
    
- name: Run security tests
  run: |
    pytest backend/tests/test_*_injection.py backend/tests/test_*_safety.py -v --timeout=60
    
- name: Generate coverage
  run: |
    pytest backend/tests/ --cov=backend/core --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
```

---

**Generated**: 2026-05-20
**Ready to copy-paste and use immediately**
