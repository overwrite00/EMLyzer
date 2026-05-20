# EMLyzer Reputation Services — Quick Reference

**For Developers, QA, and DevOps**

---

## API Key Setup (5 minutes)

### Minimum Required (High Priority)

```bash
# 1. AbuseIPDB (FREE)
# https://www.abuseipdb.com/register
# Add to .env:
ABUSEIPDB_API_KEY=your_key_here

# 2. VirusTotal (FREE, rate-limited)
# https://www.virustotal.com/gui/home/upload
# Add to .env:
VIRUSTOTAL_API_KEY=your_key_here

# 3. ABUSECH (FREE, covers 3 services)
# https://auth.abuse.ch/
# Add to .env:
ABUSECH_API_KEY=your_key_here
# Covers: URLhaus, MalwareBazaar, ThreatFox

# 4. PhishTank (FREE)
# https://www.phishtank.com/api_documentation.php
# Add to .env:
PHISHTANK_API_KEY=your_key_here
```

### Recommended (Medium Priority)

```bash
# 5. GreyNoise (FREE, reduces false positives)
GREYNOISE_API_KEY=your_key_here

# 6. CIRCL Passive DNS (FREE, informational)
# Format: username:password
CIRCL_API_KEY=user:password
```

### Optional (Low Priority)

```bash
# Hybrid Analysis, Criminal IP, URLScan, Pulsedive
HYBRID_ANALYSIS_API_KEY=...
CRIMINALIP_API_KEY=...
URLSCAN_API_KEY=...
PULSEDIVE_API_KEY=...

# ⚠️ SKIP: SecurityTrails (no free tier 2025+)
```

---

## Testing Reputation Services (10 minutes)

### 1. Check API Keys

```bash
cd backend

# View current configuration
python -c "from utils.config import settings; print(f'ABUSEIPDB: {bool(settings.ABUSEIPDB_API_KEY)}'); print(f'VT: {bool(settings.VIRUSTOTAL_API_KEY)}')"
```

### 2. Run Validator

```bash
# Simple test
python ../testing/reputation_services_validator.py

# Verbose output
python ../testing/reputation_services_validator.py --verbose

# Check report
cat ../testing/reputation_services_report.json | jq '.summary'
```

### 3. Test Via HTTP

```bash
# Upload a test email
curl -X POST http://localhost:8000/api/upload \
  -F "file=@samples/phishing_sample.eml"
# Returns: {"job_id": "abc-123-def"}

# Run analysis
curl -X POST http://localhost:8000/api/analysis/abc-123-def

# Check reputation (may still be "fast" phase)
curl http://localhost:8000/api/analysis/abc-123-def | jq '.reputation_results'

# Poll until complete (reputation_phase = "complete")
# See: reputation_results.reputation_phase
# See: reputation_results.service_registry[].status
```

### 4. Expected Results

```json
{
  "reputation_results": {
    "reputation_phase": "complete",
    "service_registry": [
      {
        "service": "Spamhaus DROP",
        "entity": "192.0.2.1",
        "status": "clean",
        "confidence": 0.0
      },
      {
        "service": "AbuseIPDB",
        "entity": "192.0.2.1",
        "status": "pending",      // Will transition to clean/malicious
        "confidence": 0.0
      }
    ],
    "reputation_score": 25
  }
}
```

---

## Service Status Meanings (Reference)

| Status | Meaning | Action |
|--------|---------|--------|
| `clean` | ✅ Checked, no threat | Normal operation |
| `malicious` | 🚨 Threat detected | Flag in UI |
| `pending` | ⏳ Still processing | Keep polling |
| `skipped` | 🔑 No API key | Add to .env, restart |
| `not_applicable` | ➖ Service irrelevant | No action |
| `error` | ⚠️ API/network failure | Check logs, retry |

---

## Common Issues & Fixes

### Issue: Services Show "PENDING" Forever

**Symptom**: After 5+ minutes, status still "pending"

**Fix**:
```python
# Check backend logs for errors
tail -f backend.log | grep -i "abuseipdb\|virustotal"

# Verify rate limiting isn't blocking
# (Should see log entries, not silence)
```

### Issue: All Services Show "SKIPPED"

**Symptom**: No API keys configured

**Fix**:
```bash
# Check .env file exists and is readable
cat backend/.env | grep API_KEY

# If empty, add keys and restart:
source backend/.env
python -c "from utils.config import settings; print(settings.ABUSEIPDB_API_KEY)"

# Restart backend
pkill -f uvicorn
./start.sh
```

### Issue: VirusTotal Always Slow (>30s)

**Symptom**: SLOW phase takes > 60 seconds

**Cause**: Rate limiting at 4 req/min due to free tier

**Fix**:
- Verify `_extract_priority_indicators()` limits URLs to max 4
- Check `slow_indicators.urls` length in response
- Consider limiting to 1-2 URLs for faster response

### Issue: Database Connection Error

**Symptom**: `flag_modified() not found`

**Fix**:
```python
# Ensure import is correct
from sqlalchemy.orm.attributes import flag_modified

# Always call before commit on JSON mutations
flag_modified(record, "reputation_results")
await db.commit()
```

---

## Performance Checklist

- [ ] FAST phase completes in < 15 seconds
- [ ] Frontend polling detects completion within 50 seconds
- [ ] No 429 (rate limit) errors in logs
- [ ] Reputation score calculated correctly (0-100)
- [ ] service_registry has 17+ entries (all services attempted)
- [ ] No stuck background tasks (check asyncio logs)
- [ ] Cache files exist: `backend/data/cache/spamhaus_drop.json`, `openphish_feed.json`

---

## Database Fields (Critical Names)

```python
# ❌ WRONG
url.url                                # Should be: original_url
url.is_ip                              # Should be: is_ip_address
header_indicators.x_originating_ip     # Should be: top-level column

# ✅ CORRECT
url.original_url
url.is_ip_address
x_originating_ip
record.reputation_results
```

---

## Rate Limit Breakdown

### Free Tier Quotas

| Service | Limit | Impact |
|---------|-------|--------|
| VirusTotal | 4 req/min | ⚠️ Bottleneck — max 4 URLs per email |
| AbuseIPDB | 1000/day (~1 req/s) | ✓ Acceptable |
| Pulsedive | 10/day | 🚫 Negligible |
| PhishTank | Generous | ✓ Acceptable |
| URLScan | 1000/day | ✓ Acceptable |

### SLOW Phase Timing

```
1 IP + 4 URLs (worst case):
  - AbuseIPDB × 1 IP = 1.1s
  - VirusTotal × 1 IP + 4 URLs = 15.5s + 15.5s + 15.5s + 15.5s + 15.5s
                                 = 77.5s ⚠️

Max practical: 1 IP + 2 URLs ≈ 32s
```

---

## Frontend Integration Checklist

- [ ] `TabReputation` polls every 5 seconds
- [ ] Stop polling when `reputation_phase === "complete"`
- [ ] Show spinner while `reputation_phase === "fast"`
- [ ] Display service status badges (✓ clean, ✗ malicious, ⏳ pending)
- [ ] Show `slow_indicators` for debugging (optional)
- [ ] Handle missing `reputation_results` gracefully
- [ ] Load API key status from `GET /api/settings/reputation_keys`

---

## Monitoring Alerts

```yaml
# Set up alerts for:

alert: ReputationServiceSlow
  if: reputation.response_time > 60s
  
alert: ReputationServiceError
  if: service_registry.error_count / total > 0.2
  
alert: SlowPhaseStuck
  if: reputation_phase = "fast" AND time_elapsed > 300s
  
alert: VTRateLimitHit
  if: error message contains "429"
```

---

## Testing Scenarios (Copy-Paste)

### Test 1: Benign Email

```bash
curl -X POST http://localhost:8000/api/analysis/abc-123 | jq '.reputation_results.service_registry[] | select(.status=="malicious")'
# Should return: (empty)
```

### Test 2: Check FAST Completion

```bash
curl http://localhost:8000/api/analysis/abc-123 | jq '.reputation_results.reputation_phase'
# Should return: "complete"
```

### Test 3: Service Coverage

```bash
curl http://localhost:8000/api/analysis/abc-123 | jq '.reputation_results.service_registry | length'
# Should return: ~17 (all services attempted)
```

### Test 4: API Key Status

```bash
curl http://localhost:8000/api/settings | jq '.reputation_keys'
# Shows which API keys are configured
```

---

## Log Patterns (Debugging)

```bash
# Watch for reputation phase transitions
grep -i "reputation_phase" backend.log

# Check for rate limit hits
grep "429\|retry" backend.log

# Monitor slow service completion
grep -i "slow_background\|virustotal\|abuseipdb" backend.log

# Database mutation tracking
grep "flag_modified" backend.log
```

---

## Deployment Checklist

- [ ] All required API keys in `.env`
- [ ] Backend restarted after `.env` changes
- [ ] FAST phase response < 15s verified
- [ ] SLOW phase background tasks running
- [ ] Frontend polling working (network tab)
- [ ] Disk cache directories writable (`backend/data/cache/`)
- [ ] Database mutations tracked (`flag_modified()` used)
- [ ] Monitoring/alerting configured
- [ ] Documentation updated for operations team

---

## Service Health Summary

```
READY FOR PRODUCTION:
  ✅ Spamhaus DROP (cache + high confidence)
  ✅ OpenPhish (cache + hourly updates)
  ✅ ASN Lookup (free + informational)
  ✅ crt.sh (domain age detection)
  ✅ PhishTank (with API key)
  ✅ GreyNoise (reduces false positives)

REQUIRES API KEY:
  ⚠️ AbuseIPDB (essential for IP scoring)
  ⚠️ VirusTotal (bottleneck, 4 req/min free)

OPTIONAL:
  ❓ CIRCL DNS (informational)
  ❓ Criminal IP (risk scoring)
  ❓ URLScan (scan results)
  ❓ Hybrid Analysis (sandbox results)
  ❓ Pulsedive (⚠️ 10 req/day = useless)

NOT RECOMMENDED:
  ❌ SecurityTrails (paid-only 2025+)
```

---

## Quick Diagnostics

```bash
# 1. Check Python path
python -c "import sys; print(sys.path)"

# 2. Verify config loads
python -c "from backend.utils.config import settings; print(settings.VERSION)"

# 3. Test service import
python -c "from backend.core.reputation.connectors import run_fast_checks; print('OK')"

# 4. Manual service test
python -c "
from backend.core.reputation.connectors import check_ip_spamhaus
result = check_ip_spamhaus('8.8.8.8')
print(f'Status: {result.error or result.detail}')
"

# 5. Check database schema
sqlite3 backend/data/emlyzer.db ".schema EmailAnalysis" | grep reputation
```

---

## Summary

| Component | Status | Action |
|-----------|--------|--------|
| FAST Services | ✅ Ready | All working with cache fallback |
| SLOW Services | ⚠️ Configured | Need API keys + monitoring |
| Rate Limiting | ✅ Implemented | Thread-safe per service |
| DB Integration | ✅ Tracked | flag_modified() required |
| Frontend | ✅ Polling | Every 5 seconds until complete |
| Monitoring | ⚠️ Missing | Set up alerting for errors |

**Next Steps**: 
1. Add API keys from "Minimum Required" section
2. Run validator: `python testing/reputation_services_validator.py`
3. Test with sample email via HTTP API
4. Set up monitoring for SLOW phase

