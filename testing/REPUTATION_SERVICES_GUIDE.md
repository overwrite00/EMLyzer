# EMLyzer Reputation Services — Technical Validation Guide

**Version**: 0.14.1  
**Last Updated**: 2026-05-20  
**Document Type**: Technical Reference & Testing Guide

---

## Executive Summary

EMLyzer's reputation system integrates **19 threat intelligence services** across two execution phases:

- **FAST Phase** (15 services): Completes in 3-15 seconds, includes local feeds and fast public APIs
- **SLOW Phase** (2 services): Runs asynchronously in background, rate-limited to respect API quotas

The system is designed to provide maximum threat detection coverage without blocking user interactions or exceeding API rate limits.

---

## Service Inventory

### FAST Services (15)

| Service | Entity Type | API Key | Cache | Rate Limit | Notes |
|---------|------------|---------|-------|-----------|-------|
| **Spamhaus DROP** | IP | ❌ | 24h | None | High-confidence malicious CIDR blocks |
| **ASN Lookup** | IP | ❌ | None | 0.3s | Informational — organization info |
| **OpenPhish** | URL | ❌ | 12h | None | Hourly updated phishing feed |
| **PhishTank** | URL | ✅ | None | 0.5s | Community-verified phishing database |
| **MalwareBazaar** | Hash | ✅ | None | 0.7s | abuse.ch malware signatures |
| **crt.sh** | URL | ❌ | None | 2.5s | SSL/TLS certificate history (new domain detection) |
| **CIRCL Passive DNS** | IP+URL | ✅ | None | 0.5s | Domain-to-IP history (informational) |
| **GreyNoise Community** | IP | ✅ | None | 1.1s | Reduces false positives from scanners |
| **Criminal IP** | IP | ✅ | None | 1.1s | IP risk score 0-4 |
| **URLScan.io** | URL | ⚠️ | None | 1.0s | Searches existing scans (key optional) |
| **SecurityTrails** | URL | ✅ | None | 3.0s | ⚠️ Paid-only (no free tier as of 2025) |
| **Shodan InternetDB** | IP | ❌ | None | 0.3s | Port/service/CVE info (informational) |
| **Hybrid Analysis** | Hash | ✅ | None | 1.0s | Falcon Sandbox analysis results |
| **URLhaus** | URL | ✅ | None | 0.3s | ⚠️ Auth required as of June 2025 (use ABUSECH_API_KEY) |
| **ThreatFox** | IP+URL+Hash | ✅ | None | 0.3s | abuse.ch threat intel |
| **Redirect Chain** | URL | ❌ | None | 0.2s | Follows HTTP redirects |
| **Pulsedive** | IP+URL | ✅ | None | 2.5s | ⚠️ Severely rate-limited (10 req/day free) |

### SLOW Services (2)

| Service | Entity Type | API Key | Timeout | Rate Limit | Notes |
|---------|------------|---------|---------|-----------|-------|
| **AbuseIPDB** | IP | ✅ | 8s | 1.1s | Abuse score 0-100 (≥50 = malicious) |
| **VirusTotal** | IP+URL+Hash | ✅ | 8s | 15.5s | ⚠️ 4 req/min free tier (main bottleneck) |

---

## Two-Phase Architecture

### Phase 1: FAST (Synchronous)

```
POST /api/reputation/{job_id}
│
├─ Extract ALL indicators
│  ├─ IPs: received hops + x_originating_ip + URL hosts + resolved IPs
│  ├─ URLs: all discovered
│  └─ Hashes: all attachments
│
├─ Run 15 FAST services (in parallel/sequential per rate limits)
│
├─ Save partial results → DB
│
└─ Return to client + schedule Phase 2
   └─ Only if has_slow indicators (priority filtering applied)
```

**Response Time Target**: < 15 seconds (safe for 60s browser timeout)

**Service Registry State After Phase 1**:
- `clean` — service checked, no threat
- `malicious` — threat detected
- `skipped` — API key missing
- `pending` → (only for SLOW services if enabled)
- `error` — network/API failure

### Phase 2: SLOW (Asynchronous)

```
FastAPI BackgroundTask (no client timeout)
│
├─ Extract PRIORITY indicators only
│  ├─ IPs: ONLY received hops + x_originating_ip
│  │  └─ NOT resolved_ip (too many CDN IPs would exceed quota)
│  ├─ URLs: max 4, only suspicious
│  │  └─ shortener OR new_domain OR is_ip OR punycode OR score≥25 OR obfuscated
│  └─ Hashes: all attachments
│
├─ Run 2 SLOW services
│  ├─ AbuseIPDB (1.1s per IP)
│  ├─ VirusTotal (15.5s per entity)
│  └─ Respect 4 req/min VirusTotal free tier quota
│
└─ Update DB when complete
   └─ reputation_phase: "complete"
   └─ Frontend polls GET /api/analysis/{job_id} until this changes
```

**Frontend Polling**: Every 5 seconds, checks `reputation_results.reputation_phase`
- While `"fast"` → Phase 2 still running
- When `"complete"` → All done

---

## API Key Configuration

### Required Keys (11 services)

```env
# Critical for threat detection
ABUSEIPDB_API_KEY=...              # Free: 1000/day
VIRUSTOTAL_API_KEY=...             # Free: 4 req/min (main bottleneck)

# Covers 3 services (URLhaus, MalwareBazaar, ThreatFox)
ABUSECH_API_KEY=...                # Free: auth.abuse.ch

# Phishing-specific
PHISHTANK_API_KEY=...              # Free: phishtank.com

# Passive DNS history
CIRCL_API_KEY=user:password        # Free: circl.lu/pdns (registration required)

# IP classification
GREYNOISE_API_KEY=...              # Free: 100 req/day (reduces false positives)
CRIMINALIP_API_KEY=...             # Free: limited credits

# DNS/certificate info
SECURITYTRAILS_API_KEY=...         # ⚠️ PAID ONLY (no free tier 2025+)

# Sandbox & misc
HYBRID_ANALYSIS_API_KEY=...        # Free: hybrid-analysis.com
URLSCAN_API_KEY=...                # Optional: unlocks higher rate limits
PULSEDIVE_API_KEY=...              # ⚠️ USELESS: 10 req/day free
```

### Free Services (No API Key)

- Spamhaus DROP (public blocklist)
- ASN Lookup (ipinfo.io)
- OpenPhish (public feed)
- crt.sh (certificate database)
- Shodan InternetDB (free API)
- Redirect Chain (local analysis)

---

## Rate Limiting Strategy

Each service has a minimum interval between requests (thread-safe via `threading.Lock`):

```python
_RATE_INTERVALS = {
    "virustotal":       15.5,   # 4 req/min free → critical bottleneck
    "abuseipdb":        1.1,    # 1000/day free
    "crtsh":            2.5,    # 2.5s per request
    "pulsedive":        2.5,    # 10 req/day (negligible)
    "securitytrails":   3.0,    # Conservative (no free tier)
    "circl":            0.5,    # CIRCL Passive DNS
    "greynoise":        1.1,    # 100 req/day
    "criminalip":       1.1,    # Limited free
    "urlscan":          1.0,    # 1000/day
    "hybridanalysis":   1.0,
    "malwarebazaar":    0.7,
    "threatfox":        0.3,
    "phishtank":        0.5,
    "urlhaus":          0.3,
    "asnlookup":        0.3,
    "shodaninternetdb": 0.3,
    "redirectchain":    0.2,
    "openphish":        0.0,    # Local cache
    "spamhaus":         0.0,    # Local cache
}
```

**Retry Strategy**:
- On 429 (too many requests): Wait `Retry-After` header (max 30s)
- On 502/503/504: Exponential backoff 2s → 4s (max 2 retries)
- Timeout: 8 seconds per request

---

## Indicator Extraction Logic

### FAST Phase (Inclusivity)

Extract **ALL** indicators to maximize detection:

```python
ips = [
    hop["ip"] for hop in header_indicators.received_hops if not hop.private_ip
] + [x_originating_ip] + [
    url.host for url in url_indicators.urls if url.is_ip_address
] + [
    url.resolved_ip for url in url_indicators.urls if url.resolved_ip
]

urls = [url.original_url for url in url_indicators.urls]

hashes = [att.hash_sha256 for att in attachment_indicators.attachments]
```

### SLOW Phase (Selective)

Only high-value indicators to respect rate limits:

```python
# IPs: ONLY internal sources (not resolved_ip from URLs — too many CDNs)
slow_ips = [
    hop["ip"] for hop in header_indicators.received_hops if not hop.private_ip
] + [x_originating_ip]

# URLs: max 4, only suspicious ones
slow_urls = [
    url.original_url for url in url_indicators.urls
    if url.is_ip_address or url.is_shortener or url.is_new_domain 
       or url.is_punycode or url.risk_score >= 25
][:4]  # Hard cap at 4 URLs (VirusTotal free = 4 req/min)

# Hashes: all attachments (usually small number)
slow_hashes = [att.hash_sha256 for att in attachment_indicators.attachments]
```

---

## Service Status Registry

After each phase, services report their status:

```python
[
    {
        "service": "Spamhaus DROP",
        "entity": "192.0.2.1",
        "entity_type": "ip",
        "status": "clean|malicious|pending|skipped|not_applicable|error",
        "confidence": 95.0,
        "detail": "IP in Spamhaus DROP (192.0.2.0/24)"
    },
    ...
]
```

### Status Meanings

| Status | Meaning | Cause |
|--------|---------|-------|
| `clean` | Service checked, no threat found | Normal completion |
| `malicious` | Threat indicators detected | Matching service database |
| `pending` | Still running (SLOW services only) | Background task in progress |
| `skipped` | Service not run | Missing API key |
| `not_applicable` | Service irrelevant for entity | e.g., IP → PhishTank |
| `error` | Network/API error | Timeout, HTTP error, malformed response |

### Status Distribution

For a typical email with URL + sender IP:

```json
{
  "clean": 8,
  "malicious": 0,
  "pending": 2,          // AbuseIPDB, VirusTotal (SLOW services)
  "skipped": 3,          // Missing API keys
  "not_applicable": 5,   // Service not relevant to entities
  "error": 1             // Network timeout
}
```

---

## Database Integration

### Affected Columns

```python
class EmailAnalysis(Base):
    # Direct columns
    x_originating_ip: str  # <- IP for SLOW phase

    # JSON columns (serialized dataclass fields)
    header_indicators: dict  # HeaderAnalysisResult
    url_indicators: dict     # URLAnalysisResult
    body_indicators: dict    # BodyAnalysisResult
    attachment_indicators: dict  # AttachmentAnalysisResult
    reputation_results: dict  # ReputationSummary (updated by reputation routes)
```

### Critical Field Names

⚠️ **Common Mistakes** (these will break reputation extraction):

```python
# WRONG ❌
url.url           # Should be: url.original_url
url.is_ip         # Should be: url.is_ip_address

# RIGHT ✅
url.original_url
url.is_ip_address
x_originating_ip  # Top-level column, not nested in header_indicators
```

### SQLAlchemy JSON Mutation (SQLite)

```python
# CRITICAL: Must flag JSON mutation before commit
record.reputation_results = new_dict
flag_modified(record, "reputation_results")  # ← Required for SQLite
await db.commit()

# Without flag_modified(), SQLite won't detect the change
```

---

## Testing & Validation

### Test Scenarios

#### Scenario 1: Email with Sender IP

```
Input: Email from 192.0.2.1 (known spam IP)
Expected:
  ✓ FAST: Spamhaus DROP = malicious
  ✓ FAST: ASN Lookup = informational
  ✓ SLOW: AbuseIPDB = malicious (if key configured)
  Result: HIGH reputation risk
```

#### Scenario 2: Email with Phishing URL

```
Input: Email with URL from OpenPhish feed
Expected:
  ✓ FAST: OpenPhish = malicious
  ✓ FAST: PhishTank = malicious (if key configured)
  ✓ SLOW: VirusTotal = malicious (if key configured)
  Result: MALICIOUS threat detected
```

#### Scenario 3: Benign Email

```
Input: Email from GitHub
Expected:
  ✓ FAST/SLOW: All services = clean
  Result: LOW reputation risk (0-20)
```

#### Scenario 4: No Indicators

```
Input: Email with no URLs, attachments, suspicious IPs
Expected:
  ✓ Many services = not_applicable
  ✓ Only header analysis = available threat data
  Result: Based on header indicators only
```

### Running Validation

```bash
# Full validation with API keys
cd backend
python ../testing/reputation_services_validator.py --verbose

# Test with verbose logging
python ../testing/reputation_services_validator.py --verbose --test-known-bad

# Results saved to: testing/reputation_services_report.json
```

---

## Frontend Integration

### Polling for Completion

```javascript
// frontend/src/components/AnalysisDetail.jsx
useEffect(() => {
  const pollReputation = async () => {
    const response = await api.get(`/analysis/${jobId}`);
    const { reputation_results } = response.data;
    
    if (reputation_results.reputation_phase === "complete") {
      // All phases done — show full results
      clearInterval(pollingInterval);
      setRepResults(reputation_results);
    } else if (reputation_results.reputation_phase === "fast") {
      // Phase 1 done, Phase 2 running — show partial results
      setRepResults(reputation_results);
      // Continue polling...
    }
  };
  
  // Poll every 5 seconds
  const pollingInterval = setInterval(pollReputation, 5000);
  return () => clearInterval(pollingInterval);
}, [jobId]);
```

### Service Preview Badge

```javascript
// Show which services have API keys configured
// Read from GET /api/settings/reputation_keys (independent of analysis)

const ServicePreview = ({ apiKeys }) => {
  // apiKeys = { "AbuseIPDB": true, "VirusTotal": false, ... }
  
  return SERVICES.map(service => (
    <ServiceBadge
      service={service}
      hasKey={apiKeys[service.name]}
      icon={hasKey ? "✓" : "✗"}
    />
  ));
};
```

---

## Monitoring & Troubleshooting

### Common Issues

#### Issue 1: SLOW Phase Takes > 5 Minutes

**Cause**: VirusTotal rate limit (4 req/min with large URL list)

**Solution**:
- Monitor `slow_indicators.urls` length (should be max 4)
- Verify `_extract_priority_indicators()` is filtering correctly
- Check for DNS/network latency to VirusTotal API

#### Issue 2: Services Show "PENDING" Forever

**Cause**: Missing call to `finalize_fast_only()` when `has_slow=false`

**Solution**:
```python
# v0.9.4 fix: always call finalize_fast_only if no SLOW indicators
if not has_slow:
    summary = finalize_fast_only(summary)  # ← Required
```

#### Issue 3: API Key Not Recognized

**Cause**: Whitespace in .env file

**Solution**:
```python
# In connectors.py
api_key = settings.ABUSEIPDB_API_KEY.strip()  # ← Always strip()
if not api_key:  # Then check emptiness
    return ReputationResult(..., skipped=True)
```

#### Issue 4: Private IPs Being Sent to Services

**Cause**: Missing `_is_public_ip()` check in indicator extraction

**Solution**:
```python
# Only add if public
if _is_public_ip(ip):
    ips.append(ip)
```

### Performance Monitoring

```python
# Track response times per service
perf_stats = {
    "spamhaus": 0.15,      # Fast (local cache)
    "abuseipdb": 1.2,      # Slower (API + rate limit)
    "virustotal": 16.5,    # Slowest (rate limited)
}

# Alert thresholds
if any(t > 30 for t in perf_stats.values()):
    alert("Slow reputation service detected")
```

---

## Best Practices

### 1. API Key Management

```bash
# .env checklist
[ ] ABUSEIPDB_API_KEY — register abuseipdb.com
[ ] VIRUSTOTAL_API_KEY — register virustotal.com
[ ] ABUSECH_API_KEY — register auth.abuse.ch (covers 3 services)
[ ] PHISHTANK_API_KEY — register phishtank.com
[ ] GREYNOISE_API_KEY — register greynoise.io
[ ] CIRCL_API_KEY — register circl.lu/pdns (format: user:pass)

# Rotation every 6 months
cron: "0 0 1 */6 * * rotate_api_keys.sh"
```

### 2. Indicator Selection

- FAST phase: **Maximum coverage** — send all indicators
- SLOW phase: **Selective coverage** — only high-value indicators
- Never send resolved_ip from URLs to SLOW services (CDN clutter)

### 3. Rate Limit Handling

- Use `_http_get_with_retry()` with proper `rate_key` parameter
- Test with high concurrency (e.g., bulk analysis)
- Monitor API quota usage

### 4. Error Handling

```python
# Handle 429 (rate limit) gracefully
if response.status_code == 429:
    retry_after = response.headers.get("Retry-After", "5")
    sleep(min(float(retry_after), 30))  # Cap at 30s

# Handle 5xx (server error) with backoff
if response.status_code in (502, 503, 504):
    exponential_backoff(attempt)
```

### 5. Frontend Polling

- Poll every **5 seconds** (not 1s — too noisy)
- Stop polling when `reputation_phase === "complete"`
- Show progress indicator while `reputation_phase === "fast"`

---

## Service-Specific Notes

### VirusTotal (Bottleneck)

- **Free tier**: 4 requests per minute
- **Impact**: Can handle 1 IP + 3 URLs OR 4 URLs per email
- **Workaround**: Selective indicator extraction in SLOW phase (max 4 URLs)
- **Missing URLs**: Are queued for future scanning (returns detail "URL inviato a VirusTotal")

### Spamhaus DROP (High Confidence)

- **Confidence**: 95% when match found
- **Cache**: 24-hour disk cache (fallback if download fails)
- **Size**: ~1000 CIDR blocks

### OpenPhish (Hourly Updates)

- **Confidence**: 90% when URL in feed
- **Cache**: 12-hour disk cache
- **Size**: ~2000 phishing URLs

### crt.sh (Domain Age Detection)

- **Use Case**: Detect newly created phishing domains
- **Flag**: If ≤2 certificates + post-2024 = suspicious (30% confidence)
- **Rate Limit**: 2.5s per request

### CIRCL Passive DNS (Informational)

- **Use Case**: Historical domain-to-IP mappings
- **Format**: `username:password` in CIRCL_API_KEY
- **No Malicious Flag**: Just information

### GreyNoise Community (Reduce False Positives)

- **Key Feature**: Distinguishes scanners from attackers
- **Classifications**: malicious | benign | unknown
- **Flags**: riot=true (known benign), noise=true (scanner)

### Pulsedive (Deprecated)

- **Status**: 10 req/day free (severely limited as of March 2024)
- **Recommendation**: Consider removal from auto-checks

### SecurityTrails (Paid Only)

- **Status**: No free tier as of 2025
- **Trial**: May work temporarily but not reliable
- **Recommendation**: Skip unless licensed

---

## Performance Benchmarks

### FAST Phase

```
Test: 1 IP + 4 URLs + 0 hashes
Result: 8.3 seconds

Breakdown:
  - Spamhaus: 0.1s (cache)
  - OpenPhish: 0.1s (cache)
  - ASN: 0.8s (HTTP + ipinfo.io)
  - crt.sh: 2.5s (HTTP)
  - PhishTank: 0.5s (HTTP)
  - Others: 3.3s (parallel/serial)
```

### SLOW Phase

```
Test: 1 IP + 2 URLs (high-value)
Result: 32.5 seconds

Breakdown:
  - AbuseIPDB: 1.1s × 1 IP = 1.1s
  - VirusTotal: 15.5s × 1 IP + 15.5s × 1 URL = 31.0s
  - (Parallelized where rate limits allow)
```

### Total E2E

```
Email analysis with reputation: 40-45 seconds
  - Email parsing: 0.1s
  - Analysis (headers/body/URLs): 5s
  - FAST reputation: 8s
  - SLOW reputation: 30s (background)
  - Frontend polls: 40-45s total visible time (1s margin)
```

---

## Rollout Checklist

- [ ] All API keys obtained and configured in .env
- [ ] FAST phase response time < 15s confirmed
- [ ] SLOW phase background task completes successfully
- [ ] Frontend polling detects completion within 50s
- [ ] Service registry status distribution reasonable (< 20% error rate)
- [ ] Rate limiting respected (no 429 errors in logs)
- [ ] Database mutations tracked with flag_modified()
- [ ] Monitoring alerts set for slow/error services
- [ ] Documentation updated with deployment details

---

## References

- **Code**: `backend/core/reputation/connectors.py`
- **Routes**: `backend/api/routes/reputation.py`
- **Tests**: `backend/tests/test_core.py`
- **Config**: `backend/utils/config.py`
- **Report**: `testing/reputation_services_report.json`
- **Validator**: `testing/reputation_services_validator.py`

---

## Summary Table

| Aspect | Count | Notes |
|--------|-------|-------|
| Total Services | 19 | 15 FAST + 2 SLOW + 2 informational |
| API Keys Required | 11 | At least ABUSEIPDB + VIRUSTOTAL recommended |
| API Keys Optional | 8 | System works degraded without these |
| FAST Phase Target | <15s | Safe for 60s browser timeout |
| SLOW Phase Typical | 30-60s | Background, no client timeout |
| Max URLs (SLOW) | 4 | VirusTotal free tier rate limit |
| Max FAST Response | 50s | Before browser timeout (60s) |
| Disk Cache Services | 2 | Spamhaus (24h) + OpenPhish (12h) |
| Rate-Limited Services | 17 | Thread-safe per-service locks |
| Retry Strategy | 2 retries | Backoff 2s/4s on 429/5xx |

