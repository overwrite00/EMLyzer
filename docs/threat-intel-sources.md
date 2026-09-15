# Wave 0 — External source verification (Threat Intelligence)

Checks performed on 2026-09-14.

## 1. Spamhaus DROP
- `https://www.spamhaus.org/drop/drop.txt` → **200 OK**, `Content-Type: text/plain; charset=UTF-8`.
- Format still active, no deprecation in progress. No schema change needed in Wave 2.

## 2. OpenPhish feed.txt
- `https://openphish.com/feed.txt` → **302 → 200** (redirect handled automatically by `requests`, which follows redirects on GET by default; `curl` without `-L` only shows the 302).
- Body reached: 300 lines of phishing URLs, unchanged format.
- Suggested initial `min_entries`: 150 (50% of the count observed in this sample).

## 3. URLhaus bulk (abuse.ch)
- `https://urlhaus.abuse.ch/downloads/csv_recent/` → **200 OK with no Auth-Key**, ~2.3 MB.
- Conclusion: the bulk CSV download **does not require** `ABUSECH_API_KEY` (unlike the live `check_url_urlhaus`/`_query_threatfox` APIs, which do). → **Wave 8: URLhaus bulk proceeds**, recommended `max_bytes` 32 MB.

## 4. CERT-AGID RSS — quantitative go/no-go
- `https://cert-agid.gov.it/feed/` → **200 OK**, `application/rss+xml`.
- Sample: 10 items, `pubDate` from 2026-08-11 to 2026-09-11 (≈ 1 month) → **10 items/month**, above the 6/month threshold.
- Observed titles: "False TARI refund... impersonating PagoPA", "New phishing campaign impersonating INPS...", "Phishing impersonating the Ministry of Health...", plus aggregated weekly summaries. **Recognizable brand in at least 80% of individual titles** (excluding aggregated weekly summaries only, which don't name a specific brand).
- **Threshold met (≥6 items/month, ≥50% titles with a recognizable brand) → Wave 7 proceeds as planned**, no fallback to a static link.
- Note: CERT-AGID content reuse licensing was not verified in detail at this stage — to confirm before Wave 7 (likely outcome: title + link + short excerpt only, never full text, as a precaution).

## 5. PhishTank — new key registration
- Not verified in this session (requires creating a PhishTank account, a manual action). **Remains conditional**: if the user has/obtains a `PHISHTANK_API_KEY`, the `online-valid.json.gz` bulk feed enters Wave 8 under the asymmetric rule (the local feed can only confirm `malicious`, never conclude `clean`). Otherwise Wave 8 proceeds with URLhaus bulk only.

## Overall outcome
| Feed | Outcome | Wave affected |
|---|---|---|
| Spamhaus DROP | unchanged | W2 |
| OpenPhish | unchanged | W2 |
| URLhaus bulk | GO, no key required | W8 |
| ThreatFox bulk | dropped (decided upfront in the plan) | — |
| PhishTank bulk | conditional on user key | W8 |
| CERT-AGID RSS | **GO** | W7 |
