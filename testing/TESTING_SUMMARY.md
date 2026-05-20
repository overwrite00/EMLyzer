# EMLyzer Testing — Quick Reference Summary

## Current State
- **Test Count**: 119 tests in `backend/tests/test_core.py`
- **Coverage**: Email parser, headers, body, URL, attachments, scoring modules
- **Critical Gap**: No accuracy validation, reputation effectiveness, or security injection tests

## Key Statistics

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| Phishing Detection Accuracy | Unknown | >90% | **Critical** |
| False Positive Rate | Unknown | <10% | **Critical** |
| API Response Time SLA | Not measured | <5-10s | **High** |
| Security Test Coverage | 0% | >80% | **Critical** |
| Reputation Service Hit Rate | Unknown | >50% | **High** |

## Top 5 Priority Fixes

| # | Issue | Impact | Effort | Status |
|---|-------|--------|--------|--------|
| 1 | Email parser OOM on large attachments (>100MB) | **P0 Critical** | 2h | TODO |
| 2 | URL injection (null bytes, Punycode bypass) | **P0 Critical** | 2h | TODO |
| 3 | Zip bomb protection (attachment safety) | **P0 Critical** | 2h | TODO |
| 4 | Accuracy confusion matrix missing | **P0 Critical** | 4h | TODO |
| 5 | NLP classifier v0.14.0 untested | **P1 High** | 3h | TODO |

## Test Gaps by Module

### Email Parser ✅ (Mostly Complete)
- ✅ RFC 2047 decoding
- ✅ Hash consistency
- ✅ Multi-format support
- ❌ Large files (>50MB)
- ❌ Malformed MIME structures
- ❌ Deep nesting (20+ levels)

### Header Analysis ⚠️ (Partial)
- ✅ SPF/DKIM/DMARC
- ✅ Identity mismatch
- ✅ Bulk sender
- ❌ List-Unsubscribe (v0.13.0)
- ❌ X-Campaign-ID (v0.13.0)
- ❌ ARC chain (v0.13.0)
- ❌ IPv6 extraction edge cases

### Body Analysis ⚠️ (Partial)
- ✅ Urgency/CTA patterns
- ✅ Obfuscated links
- ✅ Forms/JS detection
- ❌ Homoglyph detection (v0.14.0)
- ❌ LanguageTool integration (v0.14.0)
- ❌ Non-English pattern completeness
- ❌ NLP classifier accuracy (v0.14.0)

### URL Analysis ⚠️ (Partial)
- ✅ IP direct detection
- ✅ Shortener detection
- ✅ Punycode detection
- ❌ Domain age calculation
- ❌ Parallel analysis validation
- ❌ URL injection handling
- ❌ Performance benchmarks

### Attachment Analysis ⚠️ (Partial)
- ✅ Dangerous extensions
- ✅ MIME mismatch
- ✅ VBA macros
- ✅ PDF JS detection
- ❌ Zip bomb protection
- ❌ Polyglot files
- ❌ Null byte handling

### Risk Scoring ✅ (Complete)
- ✅ Score bounds
- ✅ Floor thresholds
- ✅ Explanation generation
- ⚠️ Weight calibration unknown (4 tests but no data on accuracy impact)

### Reputation Services ❌ (Not Tested)
- ❌ Service effectiveness
- ❌ Hit rates
- ❌ Latency/SLA
- ❌ Rate limiting under load
- ❌ Fallback strategies
- ❌ Concurrent request handling

## Sample Test Commands

### Run all tests
```bash
pytest backend/tests/test_core.py -v
```

### Run with coverage
```bash
pytest backend/tests/ --cov=backend/core --cov-report=html
```

### Run specific module
```bash
pytest backend/tests/test_core.py::TestBodyAnalyzer -v
```

### Run with timeout protection
```bash
pytest backend/tests/ --timeout=300 -v
```

## How to Add Tests

### 1. Create Test Sample Email
```python
def create_test_eml(subject="Test", from_addr="sender@test.com", body_text=""):
    """Generate minimal EML for testing."""
    return f"""From: {from_addr}
To: recipient@test.com
Subject: {subject}
MIME-Version: 1.0
Content-Type: text/plain; charset="UTF-8"

{body_text}""".encode('utf-8')
```

### 2. Add Test Class
```python
class TestNewFeature:
    
    def test_feature_basic(self):
        eml = create_test_eml(subject="Test Feature")
        parsed = parse_email_file(eml, "test.eml")
        result = analyze_feature(parsed)
        
        assert result is not None
        assert result.some_field == expected_value
```

### 3. Run and Verify
```bash
pytest backend/tests/test_core.py::TestNewFeature::test_feature_basic -v
```

## Recommended Test Additions (Priority Order)

### Week 1 — Security
- [ ] Large attachment handling (OOM prevention)
- [ ] URL injection attacks
- [ ] Binary attachment safety (zip bombs)

### Week 2 — Accuracy
- [ ] Confusion matrix (TP/FP/TN/FN)
- [ ] NLP classifier validation
- [ ] Reputation service effectiveness

### Week 3 — Features
- [ ] Homoglyph detection validation
- [ ] List-Unsubscribe analysis
- [ ] ARC chain validation
- [ ] Domain age calculation

### Week 4 — Performance
- [ ] Parallel URL analysis
- [ ] API response SLA
- [ ] Rate limiting stress test

## Key Metrics to Track

```python
# In CI/CD pipeline, after each test run:
print(f"Test Count: {len(all_tests)}")
print(f"Pass Rate: {passed}/{total}")
print(f"Coverage: {coverage_pct}%")
print(f"Phishing Accuracy: {tp}/{tp+fn}")
print(f"Clean Accuracy: {tn}/{tn+fp}")
print(f"False Positive Rate: {fp}/{tn+fp}%")
```

## Files to Update When Adding Tests

| File | Purpose |
|------|---------|
| `backend/tests/test_core.py` | Main test suite |
| `backend/tests/conftest.py` | Fixtures and fixtures |
| `samples/` | Test email files (EML format) |
| `CHANGELOG.md` | Document testing improvements |

## Debugging Failed Tests

### Test hangs (timeout)
1. Check for DNS lookups without timeout
2. Check for WHOIS queries (can block for 30s)
3. Check for infinite loops in regex patterns

### Test fails with encoding errors
1. Verify UTF-8 handling in `email_parser.py`
2. Check `_decode_rfc2047()` for edge cases
3. Ensure JSON serialization uses `ensure_ascii=False`

### Test fails with import errors
1. Run `pip install -e backend/`
2. Check `sys.path` includes `backend/` directory
3. Verify all dependencies in `requirements.txt`

## External Resources

- [pytest documentation](https://docs.pytest.org)
- [RFC 5322 (Email format)](https://tools.ietf.org/html/rfc5322)
- [RFC 2047 (Encoded words)](https://tools.ietf.org/html/rfc2047)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide)

---

**Last Updated**: 2026-05-20
**Maintained by**: EMLyzer Development Team
