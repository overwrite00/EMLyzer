# 📡 API Reference — EMLyzer

Complete REST API documentation for integrating EMLyzer into scripts, pipelines, and external systems.

> [!TIP]
> 💡 **Interactive API docs:** Open **http://localhost:8000/docs** when the server is running. You can test every endpoint directly in the browser without writing code.

---

## 🌐 Base URL

```
http://localhost:8000/api
```

All responses are **JSON** format. On error:

```json
{"detail": "Error message"}
```

---

## 📋 Available Endpoints

### 🏥 GET `/api/health`

Verifies server is running.

**Response:**
```json
{"status": "ok", "version": "0.15.1", "app": "EMLyzer"}
```

---

### 📤 POST `/api/upload/`

Uploads an email file. Returns `job_id` for use in subsequent steps.

**Request:** `multipart/form-data`  
Field: `file` (.eml or .msg, max 25 MB)

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "original_filename": "suspicious.eml",
  "size_bytes": 14823,
  "sha256": "a3f5c2..."
}
```

---

### 🔍 POST `/api/analysis/{job_id}`

Runs complete email analysis.

**Query parameters:**
- `do_whois` (default: `true`) — queries WHOIS for domain age. Pass `do_whois=false` to skip and speed up.

**Response:**
```json
{
  "job_id": "550e8400-...",
  "status": "completed",
  "email": {
    "subject": "URGENT: verify your account",
    "from": "fake@phish.com",
    "to": ["victim@example.com"],
    "date": "Mon, 01 Jan 2024 10:00:00 +0000",
    "message_id": "<fake@phish.com>",
    "file_hash_sha256": "a3f5c2..."
  },
  "risk": {
    "score": 72.5,
    "label": "critical",
    "label_text": "Critical risk",
    "explanation": [
      "[Header/HIGH] Mismatch between From and Return-Path domains",
      "[Body/HIGH] HTML form embedded in email body"
    ],
    "contributions": [
      {"module": "header", "raw_score": 65.0, "weighted_score": 16.25},
      {"module": "body",   "raw_score": 100.0, "weighted_score": 25.0},
      {"module": "url",    "raw_score": 55.0,  "weighted_score": 13.75},
      {"module": "attachment", "raw_score": 0.0, "weighted_score": 0.0}
    ]
  },
  "header_analysis": {"findings": [...]},
  "body_analysis": {"urgency_count": 9, "forms_found": 1},
  "url_analysis": {"total_urls": 5, "high_risk_count": 2},
  "attachment_analysis": {"total": 0, "critical_count": 0}
}
```

---

### 📖 GET `/api/analysis/{job_id}`

Retrieves results of already-run analysis. Same structure as POST.

---

### 📋 GET `/api/analysis/`

Lists analyses with pagination and filters.

**Query parameters:**

| 🔤 Parameter | 📊 Default | 📝 Description |
|---|---|---|
| `q` | `""` | Search in subject and sender |
| `risk` | `""` | Filter by label: `low`, `medium`, `high`, `critical` (comma-separated) |
| `page` | `1` | Page number |
| `page_size` | `25` | Items per page (max 100) |

**Response:**
```json
{
  "total": 42,
  "page": 1,
  "page_size": 25,
  "pages": 2,
  "items": [
    {
      "job_id": "550e8400-...",
      "subject": "URGENT: verify",
      "from": "fake@phish.com",
      "risk_score": 72.5,
      "risk_label": "critical",
      "analyzed_at": "2024-01-01T10:00:00"
    }
  ]
}
```

---

### 📨 POST `/api/manual/`

Analyzes pasted email source (without uploading a file).

**Request:**
```json
{
  "source": "From: a@b.com\nTo: c@d.com\nSubject: Test\n\nBody...",
  "filename": "manual_input.eml",
  "do_whois": false
}
```

**Response:** Same structure as `POST /api/analysis/{job_id}`

---

### 🗑️ DELETE `/api/analysis/{job_id}`

Deletes the analysis record from database **and associated files** (.eml/.msg from `uploads/`, .docx from `reports/`).

**Response:**
```json
{
  "status": "deleted",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "files_removed": 2
}
```

---

### 🗑️ POST `/api/analysis/bulk-delete`

Deletes multiple analyses in one request. Max 100 per request.

**Request:**
```json
{
  "job_ids": [
    "550e8400-e29b-41d4-a716-446655440000",
    "660f9500-f39c-52e5-b827-557766551111"
  ]
}
```

**Response:**
```json
{
  "status": "deleted",
  "requested": 2,
  "deleted": 2,
  "files_removed": 4
}
```

---

### 📝 PATCH `/api/analysis/{job_id}/notes`

Saves analyst notes.

**Request:**
```json
{"notes": "IP blocked. Reported to SOC on 2024-01-01."}
```

---

### 🌐 POST `/api/reputation/{job_id}`

Runs reputation checks in two phases:

✅ **Phase 1** (< 15s, synchronous):  
Spamhaus, ASN Lookup, Shodan InternetDB, CIRCL Passive DNS, Criminal IP, OpenPhish, PhishTank, Redirect Chain, URLhaus, URLScan.io, ThreatFox, MalwareBazaar, Hybrid Analysis, Pulsedive

🔄 **Phase 2** (background):  
AbuseIPDB, VirusTotal, crt.sh, GreyNoise, SecurityTrails

Field `slow_running: true` indicates Phase 2 in progress. Poll `GET /api/analysis/{job_id}` and check `reputation_results.reputation_phase === "complete"` when done.

**Response:**
```json
{
  "reputation_score": 85.0,
  "malicious_count": 2,
  "service_registry": [
    {
      "name": "AbuseIPDB",
      "state": "malicious",
      "state_detail": "1 malicious indicators on 1 entity",
      "queried_count": 1,
      "malicious_count": 1
    },
    {
      "name": "OpenPhish",
      "state": "clean",
      "state_detail": "3 entities analyzed — no malicious indicators",
      "queried_count": 3,
      "malicious_count": 0
    }
  ]
}
```

---

### 📄 GET `/api/report/{job_id}`

Downloads the Word report (.docx).

**Response:** binary file `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

---

### 🕸️ GET `/api/campaigns/`

Detects malicious campaigns among emails in database.

**Query parameters:**

| 🔤 Parameter | 📊 Default | 📝 Description |
|---|---|---|
| `threshold` | `0.6` | Jaccard similarity threshold (0.1–1.0) |
| `min_size` | `2` | Minimum cluster size |

**Response:**
```json
{
  "total_emails_analyzed": 15,
  "clusters_found": 2,
  "isolated_emails": 8,
  "clusters": [
    {
      "cluster_id": "C001",
      "similarity_type": "body_hash",
      "description": "Identical body (same template)",
      "email_count": 4,
      "job_ids": ["uuid1", "uuid2", "uuid3", "uuid4"],
      "max_risk_score": 78.0,
      "first_seen": "2024-01-01T08:00:00+00:00",
      "last_seen": "2024-01-01T14:30:00+00:00"
    }
  ]
}
```

---

### ⚙️ GET `/api/settings/`

Returns current configuration (language, active plugins, etc.).

**Response:**
```json
{
  "language": "it",
  "version": "0.15.1",
  "max_upload_mb": 25,
  "reputation_plugins": {
    "abuseipdb": true,
    "virustotal": false,
    "phishtank": false,
    "circl_pdns": false,
    "greynoise": false,
    "urlscan": true,
    "pulsedive": false,
    "criminal_ip": false,
    "securitytrails": false,
    "hybrid_analysis": false
  }
}
```

---

### 🌐 POST `/api/settings/language`

Changes language for current session (`"it"` or `"en"`).

**Request:**
```json
{"language": "en"}
```

---

## 🐍 Python Example

```python
import requests
import time

BASE = "http://localhost:8000/api"

# 1️⃣ Upload file
with open("email_suspicious.eml", "rb") as f:
    r = requests.post(f"{BASE}/upload/", files={"file": f})
r.raise_for_status()
job_id = r.json()["job_id"]
print(f"Upload complete: {job_id}")

# 2️⃣ Run analysis
r = requests.post(f"{BASE}/analysis/{job_id}")
result = r.json()
print(f"Risk score: {result['risk']['score']} ({result['risk']['label']})")

# 3️⃣ Reputation check (optional)
r = requests.post(f"{BASE}/reputation/{job_id}")
print(f"Malicious indicators: {r.json()['malicious_count']}")

# 4️⃣ Download report
r = requests.get(f"{BASE}/report/{job_id}")
with open("report.docx", "wb") as f:
    f.write(r.content)
print("Report saved as report.docx")

# 5️⃣ Analyst notes
requests.patch(f"{BASE}/analysis/{job_id}/notes", 
    json={"notes": "Confirmed phishing, forwarded to SOC."})

# 6️⃣ List analyses
r = requests.get(f"{BASE}/analysis/", params={"risk": "high,critical"})
for email in r.json()["items"]:
    print(f"{email['from']:30} {email['risk_score']:5.1f} {email['risk_label']}")
```

---

## 🎯 Common Workflows

### Analyze Email & Get Score

```python
# Step 1: Upload
job = requests.post(f"{BASE}/upload/", files={"file": f})
job_id = job.json()["job_id"]

# Step 2: Analyze
result = requests.post(f"{BASE}/analysis/{job_id}").json()
print(f"Score: {result['risk']['score']}")
```

### Batch Analyze Multiple Emails

```python
import glob

for eml_file in glob.glob("emails/*.eml"):
    with open(eml_file, "rb") as f:
        job = requests.post(f"{BASE}/upload/", files={"file": f})
        job_id = job.json()["job_id"]
    
    result = requests.post(f"{BASE}/analysis/{job_id}").json()
    print(f"{eml_file}: {result['risk']['score']}")
```

### Search for High-Risk Emails

```python
# Find all high and critical emails
r = requests.get(f"{BASE}/analysis/", 
    params={"risk": "high,critical", "page_size": 100})

for email in r.json()["items"]:
    print(f"{email['from']} — {email['subject'][:50]} ({email['risk_score']:.1f})")
```

### Generate Reports for All Suspicious Emails

```python
# Get all critical emails
r = requests.get(f"{BASE}/analysis/", 
    params={"risk": "critical", "page_size": 100})

for email in r.json()["items"]:
    # Download report
    report = requests.get(f"{BASE}/report/{email['job_id']}")
    filename = f"report_{email['job_id'][:8]}.docx"
    with open(filename, "wb") as f:
        f.write(report.content)
```

---

## ⚠️ Error Handling

All endpoints return HTTP status codes:

| 🔴 Code | 📝 Meaning |
|---|---|
| **200** | Success |
| **400** | Bad request (invalid parameters) |
| **404** | Not found (job_id doesn't exist) |
| **413** | File too large (> max_upload_mb) |
| **500** | Server error |

Always check status code and `detail` field on error:

```python
r = requests.post(f"{BASE}/analysis/{job_id}")
if r.status_code != 200:
    print(f"Error {r.status_code}: {r.json()['detail']}")
```

---

## 🔐 Security Notes

- ✅ API runs on **localhost only** (no remote access by default)
- ✅ No authentication required (local-only deployment)
- ✅ Analyze via network tunnel if remote access needed (SSH, VPN)
- ✅ Store API responses securely (contain email metadata)

---

## 📚 More Information

- **Usage Guide:** [USAGE.md](./USAGE.md)
- **Configuration:** [CONFIGURATION.md](./CONFIGURATION.md)
- **Installation:** [INSTALLATION.md](./INSTALLATION.md)
- **Interactive Docs:** http://localhost:8000/docs (when server running)

---

*← [Usage Guide](./USAGE.md) | [Requirements](./REQUIREMENTS.md)*
