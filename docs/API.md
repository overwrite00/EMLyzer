# API REST — EMLyzer

Riferimento per sviluppatori che vogliono integrare EMLyzer in script, pipeline o altri sistemi.

> La documentazione interattiva è disponibile su **http://localhost:8000/docs** quando il server è in esecuzione, e permette di provare ogni endpoint direttamente dal browser senza scrivere codice.

---

## Base URL

```
http://localhost:8000/api
```

Tutte le risposte sono in formato **JSON**. In caso di errore:

```json
{"detail": "Messaggio di errore"}
```

---

## Endpoint disponibili

### `GET /api/health`
Verifica che il server risponda.

```json
{"status": "ok", "version": "0.4.9", "app": "EMLyzer"}
```

---

### `POST /api/upload/`
Carica un file email. Restituisce un `job_id` da usare nei passi successivi.

**Richiesta:** `multipart/form-data`, campo `file` (.eml o .msg, max 25 MB)

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "original_filename": "sospetta.eml",
  "size_bytes": 14823,
  "sha256": "a3f5c2..."
}
```

---

### `POST /api/analysis/{job_id}`
Esegue l'analisi completa.

**Parametro query opzionale:** `do_whois=true` per interrogare WHOIS sull'età dei domini.

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
    "label_text": "Rischio critico",
    "explanation": [
      "[Header/HIGH] Mismatch tra dominio From e Return-Path",
      "[Body/HIGH] Form HTML embedded nel corpo email"
    ],
    "contributions": [
      {"module": "header", "raw_score": 65.0, "weighted_score": 16.25},
      {"module": "body",   "raw_score": 100.0, "weighted_score": 25.0},
      {"module": "url",    "raw_score": 55.0,  "weighted_score": 13.75},
      {"module": "attachment", "raw_score": 0.0, "weighted_score": 0.0}
    ]
  },
  "header_analysis": { "findings": [...], "spf_ok": false, ... },
  "body_analysis": { "urgency_count": 9, "forms_found": 1, "nlp": {...}, ... },
  "url_analysis": { "total_urls": 5, "high_risk_count": 2, "urls": [...] },
  "attachment_analysis": { "total": 0, "critical_count": 0, "attachments": [] }
}
```

---

### `GET /api/analysis/{job_id}`
Recupera i risultati di un'analisi già eseguita. Stessa struttura del POST.

---

### `GET /api/analysis/`
Lista analisi con filtri e paginazione.

**Parametri query:**

| Parametro | Default | Descrizione |
|---|---|---|
| `q` | `""` | Ricerca in oggetto e mittente |
| `risk` | `""` | Filtra per label: `low`, `medium`, `high`, `critical` (separati da virgola) |
| `page` | `1` | Numero pagina |
| `page_size` | `25` | Elementi per pagina (max 100) |

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

### `POST /api/manual/`
Analizza un sorgente email incollato come testo (senza upload file).

**Richiesta JSON:**

```json
{
  "source": "From: a@b.com\nTo: c@d.com\nSubject: Test\n\nCorpo...",
  "filename": "manual_input.eml",
  "do_whois": false
}
```

Risposta identica a `POST /api/analysis/{job_id}`.

---

### `PATCH /api/analysis/{job_id}/notes`
Salva le note dell'analista.

```json
{"notes": "IP bloccato. Segnalato al SOC il 2024-01-01."}
```

---

### `POST /api/reputation/{job_id}`
Avvia i controlli di reputazione in due fasi:
- **Fase 1** (risposta sincrona, < 15s): Spamhaus, ASN Lookup, Shodan InternetDB, OpenPhish, PhishTank, Redirect Chain, URLhaus, ThreatFox, MalwareBazaar
- **Fase 2** (background automatico): AbuseIPDB, VirusTotal, crt.sh — il campo `slow_running: true` indica che sono in corso; usare `GET /api/analysis/{job_id}` per il polling e controllare `reputation_results.reputation_phase === "complete"` per sapere quando sono terminati.

```json
{
  "reputation_score": 85.0,
  "malicious_count": 2,
  "service_registry": [
    {
      "name": "AbuseIPDB",
      "state": "malicious",
      "state_detail": "1 indicatori malevoli su 1 entità analizzate",
      "queried_count": 1,
      "malicious_count": 1
    },
    {
      "name": "OpenPhish",
      "state": "clean",
      "state_detail": "3 entità analizzate — nessun indicatore malevolo",
      "queried_count": 3,
      "malicious_count": 0
    }
  ]
}
```

---

### `GET /api/report/{job_id}`
Scarica il report Word (.docx).

Risposta: file binario `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

---

### `GET /api/campaigns/`
Rileva campagne malevole tra le email nel database.

**Parametri query:**

| Parametro | Default | Descrizione |
|---|---|---|
| `threshold` | `0.6` | Soglia similarità Jaccard (0.1–1.0) |
| `min_size` | `2` | Dimensione minima cluster |

```json
{
  "total_emails_analyzed": 15,
  "clusters_found": 2,
  "isolated_emails": 8,
  "clusters": [
    {
      "cluster_id": "C001",
      "similarity_type": "body_hash",
      "description": "Body identico (stesso template email)",
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

### `GET /api/settings/`
Configurazione corrente (lingua, plugin attivi, ecc.).

```json
{
  "language": "it",
  "version": "0.4.9",
  "max_upload_mb": 25,
  "reputation_plugins": {
    "abuseipdb": true,
    "virustotal": false,
    "phishtank": false
  }
}
```

### `POST /api/settings/language`
Cambia lingua per la sessione corrente (`"it"` o `"en"`).

```json
{"language": "en"}
```

---

## Esempio: analisi da script Python

```python
import requests

BASE = "http://localhost:8000/api"

# 1. Carica il file
with open("email_sospetta.eml", "rb") as f:
    r = requests.post(f"{BASE}/upload/", files={"file": f})
r.raise_for_status()
job_id = r.json()["job_id"]

# 2. Esegui l'analisi
r = requests.post(f"{BASE}/analysis/{job_id}")
result = r.json()
print(f"Score: {result['risk']['score']} ({result['risk']['label']})")

# 3. Controllo reputazione (opzionale)
r = requests.post(f"{BASE}/reputation/{job_id}")
print(f"Indicatori malevoli: {r.json()['malicious_count']}")

# 4. Scarica il report Word
r = requests.get(f"{BASE}/report/{job_id}")
with open("report.docx", "wb") as f:
    f.write(r.content)
```

---