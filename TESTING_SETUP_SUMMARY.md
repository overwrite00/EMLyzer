# EMLyzer Email Analysis Testing Setup - Summary

**Date**: 2026-05-20  
**Project**: EMLyzer v0.14.1  
**Task**: Email threat detection accuracy analysis on 60 diverse samples

## What Was Set Up

### Test Infrastructure

Created a comprehensive email threat detection testing framework consisting of:

1. **Primary Analysis Script**: `analyze_email_samples.py`
   - Direct module-based analysis (no server required)
   - Analyzes 60 diverse email samples
   - Produces detailed JSON results with threat indicators
   - Reports risk distribution, detection patterns, analysis metrics

2. **Helper Scripts**:
   - `test_import.py` - Verifies module imports and dependencies
   - `email_analysis_test.py` - Async HTTP API-based variant (if server is running)
   - `direct_email_analysis_test.py` - Async direct analysis variant
   - `run_analysis.bat` - Batch wrapper to run main script with correct Python environment

3. **Documentation**:
   - `EMAIL_ANALYSIS_TEST_README.md` - Comprehensive testing guide
   - This file - Setup summary

## Email Corpus

- **Location**: `D:\Documenti\Email per test analisi\`
- **Total Files**: 7,911 .eml files
- **Size Distribution**:
  - Small (<10KB): ~2,400 emails - spam/phishing indicators
  - Medium (10-100KB): ~4,500 emails - mixed threat types
  - Large (>100KB): ~1,000 emails - complex with attachments

## Sample Selection Strategy

From 7,911 available emails, the analysis script automatically selects 60 diverse samples:
- **18 small emails** (30%) - tests header/body phishing detection
- **24 medium emails** (40%) - tests balanced threat coverage
- **18 large emails** (30%) - tests attachment risk assessment

This ensures comprehensive coverage of all threat types in EMLyzer's detection pipeline.

## How to Run

### Quick Start (Windows)
```batch
cd D:\GitHub\EMLyzer
run_analysis.bat
```

### Manual Execution
```batch
cd D:\GitHub\EMLyzer
.venv\Scripts\python.exe analyze_email_samples.py
```

### Verify Dependencies
```batch
.venv\Scripts\python.exe test_import.py
```

## Expected Output

### Console Output (Real-time)
```
================================================================================
EMLyzer Email Threat Detection Analysis
================================================================================

Importing EMLyzer modules...
  EMLyzer v0.14.1

Discovering email files...
Found 7911 .eml files

Categorizing by size...
  Small (<10KB):       2400
  Medium (10-100KB):   4500
  Large (>100KB):      1000

Selecting 60 diverse samples...
Selected 60 emails for analysis

Analyzing 60 emails...
--------------------------------------------------------------------------------
[ 1/60] sample-8.eml                           (   1373 B) ✓ MEDIUM (42.5)
[ 2/60] sample-36.eml                          (   2145 B) ✓ LOW    (15.3)
...
--------------------------------------------------------------------------------

================================================================================
ANALYSIS SUMMARY
================================================================================

Total samples: 60
Successful: 58
Failed: 2
Success rate: 96.7%
Total time: 125.43s
Average time per email: 2.09s

Risk Level Distribution:
  LOW:      27 ( 46.6%)
  MEDIUM:   18 ( 31.0%)
  HIGH:      9 ( 15.5%)
  CRITICAL:  4 (  6.9%)

Detected Indicators Summary:
  Header findings:      94 (avg 1.62)
  Body findings:       156 (avg 2.69)
  URL findings:        42 (in 89 total URLs)
  Attachment findings: 18 (in 12 total files)

Risk Score Statistics:
  Min: 5.2
  Max: 92.1
  Avg: 38.7
  Med: 36.5

Saving results to D:\GitHub\EMLyzer\testing\analysis_results.json...
Results saved successfully!
  File: D:\GitHub\EMLyzer\testing\analysis_results.json
  Size: 45,234 bytes

================================================================================
```

### JSON Output File
- **Path**: `D:\GitHub\EMLyzer\testing\analysis_results.json`
- **Format**: Structured JSON with metadata and per-email results
- **Size**: ~45 KB typical
- **Contents**:
  - Metadata (timestamps, counts, timing statistics)
  - Array of 60 email analysis results
  - Each result includes: filename, size, risk score, detected indicators, metadata

## Analysis Pipeline Covered

The test exercises EMLyzer's complete threat detection pipeline:

### 1. Email Parsing
- RFC 2822 compliance
- Header decoding (RFC 2047)
- Attachment extraction
- Body text/HTML separation

### 2. Header Analysis
- SPF/DKIM/DMARC validation
- Identity mismatch detection
- Header injection attempts
- Bulk sender tools detection
- Authentication results parsing
- IP address extraction and validation
- ARC chain verification

### 3. Body Analysis
- Urgency keywords (40+ patterns)
- Phishing CTAs (23+ patterns)
- Credential keywords (15+ patterns)
- Form detection (HTML form tags)
- JavaScript detection
- Hidden content (CSS visibility)
- Obfuscated link detection (href ≠ display text)
- Unicode homoglyph detection (39 characters)
- LanguageTool grammar checking (optional)
- NLP classification (LogisticRegression + TF-IDF)

### 4. URL Analysis
- Per-URL risk scoring
- Domain age calculation
- Shortener detection
- Punycode detection
- IP address classification
- DNS resolution
- WHOIS lookup (optional, ~0.5s per URL)
- Threat feed checking

### 5. Attachment Analysis
- VBA macro detection (OLE2 + OOXML)
- MIME type validation
- Double extension detection
- Dangerous extension lists
- PDF embedded stream analysis
- Hash calculation (MD5/SHA1/SHA256)

### 6. Risk Scoring
- Adaptive weighted normalization
- Deterministic floors for high-confidence signals
- Per-module contribution calculation
- Explanation generation
- Label assignment (low/medium/high/critical)

## Key Metrics Collected

For each email analyzed:
- **Timing**: How long analysis took
- **Risk Score**: 0-100 continuous scale
- **Risk Label**: low, medium, high, or critical
- **Findings Count**: Header/body/URL/attachment threats
- **Email Metadata**: From, To, Subject for context
- **Success Status**: Whether analysis completed without errors

## Reputation Service Status

The test captures but does not require reputation services:
- EMLyzer can analyze emails without external services
- Reputation phase is marked as "none" (not run during direct analysis)
- Server-based test (email_analysis_test.py) can do full reputation checks if backend is running

## Performance Expectations

- **Small emails**: 0.8-1.2 seconds
- **Medium emails**: 1.5-2.5 seconds
- **Large emails**: 2.5-5.0 seconds
- **Total for 60 samples**: ~2-5 minutes
- **Bottlenecks**: DNS queries (cached), WHOIS lookups (if enabled)

## Files Created

| File | Purpose |
|------|---------|
| `analyze_email_samples.py` | Main test script (primary) |
| `email_analysis_test.py` | API-based test script |
| `direct_email_analysis_test.py` | Async direct test |
| `test_import.py` | Dependency checker |
| `run_analysis.bat` | Windows batch wrapper |
| `run_email_analysis_test.py` | Server launcher |
| `EMAIL_ANALYSIS_TEST_README.md` | Comprehensive guide |
| `TESTING_SETUP_SUMMARY.md` | This file |

## Output Location

All results are saved to:
```
D:\GitHub\EMLyzer\testing\analysis_results.json
```

This directory is git-ignored (see `.gitignore` for local test data).

## Troubleshooting

### Import Errors
- Ensure `.venv` is activated
- Run from project root: `D:\GitHub\EMLyzer`
- Verify with: `test_import.py`

### Missing Email Files
- Check that `D:\Documenti\Email per test analisi` exists
- Verify it contains at least 60 .eml files
- Current corpus has 7,911 files - should be more than enough

### Out of Memory
- Reduce `SAMPLE_SIZE` from 60 to 30
- Skip WHOIS lookups in url_analyzer
- Disable NLP or LanguageTool

### Slow Performance
- Skip WHOIS lookups (default is `do_whois=True`)
- Disable LanguageTool API
- Use smaller sample size

## Next Steps

After running the analysis:

1. **Review Results**: Open `testing/analysis_results.json` to see threat distributions
2. **Check Statistics**: Verify success rate (target >95%)
3. **Validate Detections**: Cross-check high-risk emails with known threat databases
4. **Baseline Establishment**: Use results as baseline for future versions
5. **Performance Tuning**: Identify analysis bottlenecks
6. **Accuracy Metrics**: Calculate precision/recall against labeled dataset (if available)

## Integration Points

This testing framework can be integrated with:
- **CI/CD Pipelines**: GitHub Actions, GitLab CI, Jenkins
- **Continuous Monitoring**: Run periodically to track detection drift
- **Regression Testing**: Compare results across releases
- **Benchmarking**: Measure performance improvements
- **Model Validation**: Verify NLP classifier accuracy

## Configuration Options

Edit `analyze_email_samples.py` to customize:

```python
EMAIL_DIR = Path(r"D:\Documenti\Email per test analisi")  # Source directory
OUTPUT_DIR = Path(__file__).parent / "testing"            # Output directory
RESULTS_FILE = OUTPUT_DIR / "analysis_results.json"       # Results file
SAMPLE_SIZE = 60                                          # Number of samples
```

## Architecture Notes

The test uses EMLyzer's modular design:
- Each analyzer is independent and composable
- Results are dataclasses (typed, serializable)
- Scoring is deterministic and explainable
- No external API calls required (WHOIS/DNS are optional)

## Version Information

- **EMLyzer**: 0.14.1
- **Python**: 3.11+ (3.13 recommended)
- **Key Dependencies**:
  - FastAPI (backend only, not needed for tests)
  - python-docx (report generation, not needed for tests)
  - scikit-learn (NLP, required)
  - dnspython (DNS queries, required)
  - filemagic/filetype (MIME detection, required)

## Support and Questions

For issues or questions:
1. Check `EMAIL_ANALYSIS_TEST_README.md` for detailed documentation
2. Review `CLAUDE.md` for architecture and implementation notes
3. Check `backend/tests/test_core.py` for unit test examples
4. Review individual analyzer source files for implementation details

---

**Status**: Ready to run  
**Last Updated**: 2026-05-20  
**Created By**: Claude Code Assistant
