# EMLyzer Accuracy Validation — Quick Reference Card

## One-Liner Execution

```bash
cd D:\GitHub\EMLyzer && python testing/run_accuracy_validation.py
```

## Expected Output

```
✓ Risk score computed: 62.5 (high)          [TC_001 PASS]
✓ Risk score computed: 8.3 (low)             [TC_002 PASS]
✓ Validation Results Saved
```

## Files at a Glance

| File | Purpose | Size |
|------|---------|------|
| `accuracy_validation.json` | Test definitions + results | 2.5 KB |
| `run_accuracy_validation.py` | Executable test runner | 8.2 KB |
| `VALIDATION_GUIDE.md` | Complete setup & interpretation guide | 18 KB |
| `TEST_CASE_SPECIFICATIONS.md` | Detailed test specs | 24 KB |
| `README.md` | Quick start overview | 9 KB |
| `FRAMEWORK_SUMMARY.txt` | Full delivery summary | 8 KB |

## Test Cases at a Glance

### TC_001: Phishing Email
- **File**: `samples/phishing_sample.eml`
- **Threat**: PayPal typosquatting + credential harvesting
- **Expected Score**: HIGH (45–70) ✓
- **Key Indicators**: Urgency (4), CTA (2), Credentials (1), Forms (1), Obfuscated links (2), Auth failures (3)

### TC_002: Clean Email
- **File**: `samples/clean_sample.eml`
- **Threat**: None (legitimate GitHub notification)
- **Expected Score**: LOW (0–20) ✓
- **Key Indicators**: No suspicious patterns, auth passes

## Validation Dimensions

```
1. PHISHING DETECTION
   ✓ CTA patterns ✓ Urgency ✓ Credentials ✓ Obfuscation ✓ Forms
   Target TP: ≥95% | Target FP: <2%

2. MALWARE/ATTACHMENT
   ✓ .exe ✓ Macros ✓ MIME mismatch ✓ PDF streams
   Target TP: ≥90% | Target FP: <1%

3. SPAM/BULK SENDER
   ✓ Auth failures ✓ Return-path ✓ List-Unsubscribe
   Target TP: ≥98% | Target FP: <3%

4. RISK SCORING
   ✓ Adaptive weights ✓ Floor rules ✓ Label accuracy
   Target: ±10% deviation from benchmark

5. NLP CLASSIFIER
   ✓ Phishing detection ✓ Sextortion ✓ Banking ✓ Legitimate
   Target TP: ≥85% | Target FP: <5%
```

## Success Criteria

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| TC_001 Score | ≥45 | ? | Run test |
| TC_002 Score | <20 | ? | Run test |
| Both Pass? | YES | ? | Pending |

## Debug Checklist

If test FAILS:

**TC_001 under-detected (score < 45)?**
- [ ] Check header parsing: SPF/DKIM/DMARC failures detected?
- [ ] Check body parsing: Urgency count ≥3? CTA count ≥2?
- [ ] Check floor rules: Are ≥3 HIGH headers triggering floor=45?

**TC_002 over-detected (score > 20)?**
- [ ] Check if github.com domain flagged as suspicious
- [ ] Check if legitimate CTA ("View") matching phishing patterns
- [ ] Check if auth headers misparsed

## Result Interpretation

### ✓ Both Pass (Ideal)

```json
"accuracy_assessment": {
  "phishing_detection": { "test_passed": true, "actual_score": 62.5 },
  "clean_detection": { "test_passed": true, "actual_score": 8.3 }
}
```

**Action**: Framework validated ✓ No changes needed

### ✗ TC_001 Fails (Phishing under-detected)

```json
"phishing_detection": { "test_passed": false, "actual_score": 18.5 }
```

**Action**: 
1. Run `python -c "import json; print(json.dumps(json.load(open('testing/accuracy_validation.json'))['actual_results']['TC_001'], indent=2))"`
2. Check header.high_count and body.high_count
3. Review `backend/core/analysis/body_analyzer.py` patterns
4. Review `backend/core/analysis/scorer.py` floor rules

### ✗ TC_002 Fails (Clean over-detected)

```json
"clean_detection": { "test_passed": false, "actual_score": 35.2 }
```

**Action**:
1. Run same JSON inspection
2. Identify which module scored high (header/body/url)
3. Review that analyzer for false positives
4. Check domain list in header/url analyzers

## Key Code Locations

| Component | File |
|-----------|------|
| Urgency patterns | `backend/core/analysis/body_analyzer.py:22-31` |
| Phishing CTAs | `backend/core/analysis/body_analyzer.py:33-40` |
| Risk scoring | `backend/core/analysis/scorer.py` |
| Header validation | `backend/core/analysis/header_analyzer.py` |
| URL analysis | `backend/core/analysis/url_analyzer.py` |
| Floor rules | `backend/core/analysis/scorer.py:114-200` |

## Performance Targets

| Stage | Expected | Actual |
|-------|----------|--------|
| Parse | <100ms | ? |
| Header | <50ms | ? |
| Body | <200ms | ? |
| URL | <1000ms | ? |
| Attach | <100ms | ? |
| Score | <10ms | ? |
| **Total** | **<2s** | ? |

## CI/CD Integration

```yaml
- name: Validate Accuracy
  run: |
    python testing/run_accuracy_validation.py
    python -c "import json; d=json.load(open('testing/accuracy_validation.json')); 
      exit(0 if d['accuracy_assessment']['phishing_detection']['test_passed'] else 1)"
```

## Common Issues & Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| ModuleNotFoundError | `pip install -r backend/requirements.txt` |
| Sample not found | `ls samples/` → verify phishing_sample.eml exists |
| JSON parse error | `python -m json.tool testing/accuracy_validation.json` |
| Score mismatch | Check floor rules in `scorer.py:_compute_floors()` |

## Reference Docs

- **Full Guide**: `VALIDATION_GUIDE.md` (18 KB)
- **Specifications**: `TEST_CASE_SPECIFICATIONS.md` (24 KB)
- **Overview**: `README.md` (9 KB)
- **Project Docs**: `D:\GitHub\EMLyzer\CLAUDE.md`

## When to Run Validation

✓ Before every release  
✓ After modifying any analyzer  
✓ When debugging false positives  
✓ When investigating detection gaps  
✓ In CI/CD pipeline (before merge)  

## Expected Execution Time

- Install dependencies: 1 minute
- Run tests: < 1 minute
- Review results: 5 minutes
- **Total**: ~10 minutes

---

**Last Updated**: 2026-05-20  
**Status**: ✓ Framework Ready  
**Next Step**: `python testing/run_accuracy_validation.py`
