"""
api/routes/reputation.py

Esegue i check di reputazione su un'analisi già completata.
Separato dall'analisi core per permettere:
- Esecuzione selettiva (l'utente può scegliere se usare API esterne)
- Re-check con chiavi diverse
"""

import re
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session, EmailAnalysis
from core.reputation.connectors import run_reputation_checks
from dataclasses import asdict
import json

router = APIRouter()


@router.post("/{job_id}")
async def run_reputation(
    job_id: str,
    db: AsyncSession = Depends(get_session),
):
    if not re.match(r'^[0-9a-f-]{36}$', job_id):
        raise HTTPException(status_code=400, detail="job_id non valido")

    record = await db.get(EmailAnalysis, job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Analisi non trovata. Esegui prima POST /api/analysis/{job_id}")

    # Estrai IP, URL, hash dagli indicatori già salvati
    ips = []
    urls = []
    hashes = []

    if record.header_indicators:
        for hop in record.header_indicators.get("received_hops", []):
            if hop.get("ip") and not hop.get("private_ip"):
                ips.append(hop["ip"])

    if record.url_indicators:
        for u in record.url_indicators.get("urls", []):
            if u.get("url"):
                urls.append(u["url"])

    if record.attachment_indicators:
        for att in record.attachment_indicators.get("attachments", []):
            if att.get("hash_sha256"):
                hashes.append(att["hash_sha256"])

    summary = run_reputation_checks(ips=ips, urls=urls, hashes=hashes)

    # Salva i risultati
    rep_dict = json.loads(json.dumps(asdict(summary), default=str))
    record.reputation_results = rep_dict
    await db.commit()

    return {
        "job_id": job_id,
        "reputation_score": summary.reputation_score,
        "malicious_count": summary.malicious_count,
        "service_registry": rep_dict.get("service_registry", []),
        "results": rep_dict,
    }
