# EMLyzer Reputation Services Testing Suite

**START HERE** for reputation services validation

**Project Version**: 0.14.1  
**Documentation Date**: 2026-05-20

---

## 📁 What's in This Directory?

Complete validation tools and documentation for EMLyzer's **19 threat intelligence services**:

### 🎯 Must-Read Documents (Start Here)

1. **`REPUTATION_QUICK_REFERENCE.md`** ⭐
   - 5-minute API key setup
   - Common issues & fixes
   - Copy-paste test commands
   - Status meanings explained

2. **`REPUTATION_SERVICES_GUIDE.md`**
   - Complete technical reference
   - Service descriptions
   - Architecture explanations
   - Database integration details

3. **`reputation_services_report.json`**
   - JSON data with service inventory
   - API key requirements
   - Performance benchmarks
   - Known issues documented

### 🛠️ Testing Tools

- **`reputation_services_validator.py`** — Run this to validate services
  ```bash
  python reputation_services_validator.py --verbose
  ```

---

## ⚡ 5-Minute Quick Start

### Step 1: Get API Keys (minimum)

```bash
# Visit these and register (all free):
# 1. https://www.abuseipdb.com/register → ABUSEIPDB_API_KEY
# 2. https://www.virustotal.com → VIRUSTOTAL_API_KEY
# 3. https://auth.abuse.ch/ → ABUSECH_API_KEY
# 4. https://www.phishtank.com → PHISHTANK_API_KEY
```

### Step 2: Add to .env

```bash
# Edit: backend/.env
ABUSEIPDB_API_KEY=your_key_here
VIRUSTOTAL_API_KEY=your_key_here
ABUSECH_API_KEY=your_key_here
PHISHTANK_API_KEY=your_key_here
```

### Step 3: Test

```bash
# Run validator
cd backend
python ../testing/reputation_services_validator.py --verbose

# Or test via API
curl -X POST http://localhost:8000/api/upload \
  -F "file=@../samples/phishing_sample.eml"
# Returns: {"job_id": "abc-123"}

# Check reputation
curl http://localhost:8000/api/analysis/abc-123 | jq '.reputation_results.reputation_phase'
# Wait for: "complete"
```

---

## 📊 Service Overview

### 15 FAST Services (3-15 seconds)
- ✅ Spamhaus DROP (IP blocklist)
- ✅ OpenPhish (URL feed)
- ✅ ASN Lookup (IP organization)
- ✅ PhishTank (phishing database)
- ✅ crt.sh (SSL certificates)
- ✅ MalwareBazaar (hash signatures)
- ✅ And 9 more...

### 2 SLOW Services (30-60 seconds, background)
- ⚠️ AbuseIPDB (IP scoring)
- ⚠️ VirusTotal (multi-engine scan)

**Total**: 19 services, 4-6 API keys needed

---

## 🚦 Service Status Reference

| Status | Meaning | Icon |
|--------|---------|------|
| `clean` | ✅ Checked, no threat | ✅ |
| `malicious` | 🚨 Threat detected | ❌ |
| `pending` | ⏳ Still running | ⏳ |
| `skipped` | 🔑 No API key | 🔑 |
| `not_applicable` | ➖ Service doesn't apply | ➖ |
| `error` | ⚠️ API/network failed | ⚠️ |

---

## 🔴 Critical Database Field Names

⚠️ **THESE MUST BE EXACT** or reputation breaks:

```python
# ❌ WRONG (will fail)
url.url              # Should be: original_url
url.is_ip            # Should be: is_ip_address

# ✅ CORRECT (use these)
url.original_url
url.is_ip_address
x_originating_ip
```

---

## 🐛 Most Common Issues

### 1. Services Show "PENDING" Forever

**Fix**: Restart backend after adding API keys
```bash
pkill uvicorn
./start.sh
```

### 2. All Services Show "SKIPPED"

**Fix**: Check .env file has API keys
```bash
cat backend/.env | grep ABUSEIPDB
# Should show: ABUSEIPDB_API_KEY=your_key
```

### 3. VirusTotal Takes >30 Seconds

**Fix**: Expected behavior. It's rate-limited to 4 req/min free tier.
Normal timing: 30-60 seconds for 1 IP + 4 URLs.

### 4. Database Error "flag_modified not found"

**Fix**: Check import in reputation.py
```python
from sqlalchemy.orm.attributes import flag_modified
flag_modified(record, "reputation_results")  # ← Must call before commit
```

---

## ✅ Testing Checklist

```
Phase 1: Setup
  [ ] API keys added to backend/.env
  [ ] Backend restarted
  [ ] Disk cache dir exists: backend/data/cache/

Phase 2: Validator
  [ ] Run: python reputation_services_validator.py
  [ ] Check output for errors
  [ ] Review: reputation_services_report.json

Phase 3: HTTP Test
  [ ] Upload email: curl -X POST /api/upload
  [ ] Get job_id
  [ ] Check reputation: curl /api/analysis/{job_id}
  [ ] Wait for reputation_phase: "complete"

Phase 4: Status Check
  [ ] service_registry has 15+ entries
  [ ] No excessive ERROR status
  [ ] Response times reasonable (<60s)
```

---

## 📋 Document Guide

| Need | Read |
|------|------|
| Quick setup | `REPUTATION_QUICK_REFERENCE.md` |
| API key details | `REPUTATION_QUICK_REFERENCE.md` → API Key Setup |
| Fix a problem | `REPUTATION_QUICK_REFERENCE.md` → Issues & Fixes |
| Database fields | `REPUTATION_QUICK_REFERENCE.md` → Database Fields |
| Full tech details | `REPUTATION_SERVICES_GUIDE.md` |
| Service inventory | `reputation_services_report.json` |
| Run tests | `reputation_services_validator.py` |

---

## 🎯 What You'll Validate

✅ **API Key Configuration**
- Which keys are needed
- Which are optional
- How to obtain them

✅ **Service Availability**
- All 19 services operational
- Rate limiting respected
- Retry logic working

✅ **Data Accuracy**
- Reputation scores calculated correctly
- Service status registry accurate
- Threat detection working

✅ **Performance**
- FAST phase < 15 seconds
- SLOW phase < 60 seconds
- No timeout errors

✅ **Database Integration**
- Field names correct
- JSON mutations tracked
- Data persisted correctly

✅ **Frontend Integration**
- Polling detects completion
- Service badges display
- No UI errors

---

## 🚀 Next Steps

1. **NOW** (2 min): Add 4 API keys to .env
2. **NEXT** (5 min): Run `python reputation_services_validator.py`
3. **THEN** (10 min): Test with sample email via API
4. **FINALLY** (optional): Read full `REPUTATION_SERVICES_GUIDE.md` for deep dive

---

## 📞 Quick Debugging

```bash
# Check if backend is running
curl http://localhost:8000/api/health

# View API key status
curl http://localhost:8000/api/settings | jq '.reputation_keys'

# Check for reputation errors in logs
tail -f backend.log | grep -i "reputation\|abuseipdb\|virustotal"

# Test a single service
python -c "
from backend.core.reputation.connectors import check_ip_spamhaus
result = check_ip_spamhaus('8.8.8.8')
print(f'Status: {result.error or result.detail}')
"
```

---

## 💡 Pro Tips

1. **VirusTotal is the bottleneck**: It's rate-limited to 4 req/min (free tier)
   - Plan for 30-60 second SLOW phase
   - Max 4 URLs sent to VirusTotal per email

2. **Disk caching helps**: Spamhaus and OpenPhish use local caches
   - Enables fallback if network down
   - Cache: `backend/data/cache/`

3. **Indicator extraction is selective**: SLOW phase only uses high-value indicators
   - FAST phase: All IPs/URLs
   - SLOW phase: Only suspicious ones + received headers

4. **Frontend polling is essential**: Check `reputation_results.reputation_phase`
   - `"fast"` = Phase 1 done, Phase 2 running
   - `"complete"` = All done

---

## 📈 Expected Numbers

| Metric | Value |
|--------|-------|
| Total Services | 19 |
| FAST Services | 15 |
| SLOW Services | 2 |
| Minimum API Keys | 4 |
| Recommended API Keys | 6 |
| FAST Phase Time | 3-15s |
| SLOW Phase Time | 30-60s |
| Service Registry Size | ~17 entries |
| Error Rate (target) | <10% |

---

## ✨ Summary

EMLyzer's reputation system is **production-ready** with proper API key configuration:

- ✅ 15 FAST services run synchronously
- ✅ 2 SLOW services run asynchronously
- ✅ Rate limiting prevents quota abuse
- ✅ Disk caching provides resilience
- ✅ Frontend polling detects completion
- ✅ Database integration tracked properly

**You're validating a sophisticated, well-architected threat intelligence pipeline.**

---

## 📚 Full Document Index

1. **`00_START_HERE.md`** (this file)
2. **`REPUTATION_QUICK_REFERENCE.md`** ← Read next
3. **`REPUTATION_SERVICES_GUIDE.md`** ← Deep dive
4. **`reputation_services_report.json`** ← Data reference
5. **`reputation_services_validator.py`** ← Run this
6. Other legacy/reference docs

---

**Status**: ✅ Ready for Testing  
**Last Updated**: 2026-05-20  
**Version**: 0.14.1

**Start with `REPUTATION_QUICK_REFERENCE.md` next!**

