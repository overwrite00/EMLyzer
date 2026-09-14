# Wave 0 — Verifiche esterne (Threat Intelligence)

Verifiche eseguite il 2026-09-14.

## 1. Spamhaus DROP
- `https://www.spamhaus.org/drop/drop.txt` → **200 OK**, `Content-Type: text/plain; charset=UTF-8`.
- Formato ancora attivo, nessuna dismissione in corso. Nessun cambio di schema necessario in Wave 2.

## 2. OpenPhish feed.txt
- `https://openphish.com/feed.txt` → **302 → 200** (redirect gestito automaticamente da `requests`, che segue i redirect su GET di default; `curl` senza `-L` mostra solo il 302).
- Corpo raggiunto: 300 righe di URL phishing, formato invariato.
- `min_entries` iniziale suggerito: 150 (50% del conteggio osservato in questo campione).

## 3. URLhaus bulk (abuse.ch)
- `https://urlhaus.abuse.ch/downloads/csv_recent/` → **200 OK senza Auth-Key**, ~2.3 MB.
- Conclusione: il download bulk CSV **non richiede** `ABUSECH_API_KEY` (a differenza delle API live `check_url_urlhaus`/`_query_threatfox` che la richiedono). → **Wave 8: URLhaus bulk procede**, `max_bytes` consigliato 32 MB.

## 4. CERT-AGID RSS — go/no-go quantitativo
- `https://cert-agid.gov.it/feed/` → **200 OK**, `application/rss+xml`.
- Campione: 10 item, `pubDate` da 2026-08-11 a 2026-09-11 (≈ 1 mese) → **10 item/mese**, sopra la soglia di 6/mese.
- Titoli osservati: "Falso rimborso TARI... ai danni di PagoPA", "Nuova campagna di phishing ai danni di INPS...", "Phishing ai danni del Ministero della Salute...", più sintesi settimanali aggregate. **Brand riconoscibile in almeno l'80% dei titoli individuali** (esclusi i soli riepiloghi settimanali aggregati, che non nominano un brand specifico).
- **Soglia superata (≥6 item/mese, ≥50% titoli con brand riconoscibile) → Wave 7 procede come pianificata**, non degrada a link statico.
- Nota: la licenza di riuso dei contenuti CERT-AGID non è stata verificata in dettaglio in questa fase — da confermare prima di Wave 7 (probabile: solo titolo + link + estratto breve, mai testo integrale, per prudenza).

## 5. PhishTank — registrazione nuove chiavi
- Non verificato in questa sessione (richiede creazione di un account PhishTank, azione manuale). **Rimane condizionato**: se l'utente ha/ottiene una `PHISHTANK_API_KEY`, il bulk `online-valid.json.gz` entra in Wave 8 con la regola asimmetrica (il feed locale può solo confermare `malicious`, mai concludere `clean`). Altrimenti Wave 8 procede solo con URLhaus bulk.

## Esito complessivo
| Feed | Esito | Wave interessata |
|---|---|---|
| Spamhaus DROP | invariato | W2 |
| OpenPhish | invariato | W2 |
| URLhaus bulk | GO, no key richiesta | W8 |
| ThreatFox bulk | scartato (deciso a priori nel piano) | — |
| PhishTank bulk | condizionato a chiave utente | W8 |
| CERT-AGID RSS | **GO** | W7 |
