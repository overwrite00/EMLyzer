"""
api/routes/upload.py

Upload sicuro di file .eml / .msg.
- Validazione estensione e dimensione
- Nessuna esecuzione del file
- Salvataggio in directory isolata (pathlib cross-platform)
- Ritorna un job_id per il polling dell'analisi
"""

import uuid
import hashlib
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse

from utils.config import settings

router = APIRouter()

MAX_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/")
async def upload_email(file: UploadFile = File(...)):
    # 1. Validazione nome file e estensione
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nome file mancante")

    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato non supportato: '{ext}'. Formati accettati: {settings.ALLOWED_EXTENSIONS}",
        )

    # 2. Lettura e validazione dimensione
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="File vuoto")
    if len(raw) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File troppo grande: max {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    # 3. Calcola hash SHA256 del file caricato
    sha256 = hashlib.sha256(raw).hexdigest()

    # 4. Salva in directory upload isolata con nome sicuro (UUID, non il nome originale)
    job_id = str(uuid.uuid4())
    safe_filename = f"{job_id}{ext}"
    dest_path: Path = settings.UPLOAD_DIR / safe_filename

    try:
        dest_path.write_bytes(raw)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio file: {e}")

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "job_id": job_id,
            "original_filename": file.filename,
            "size_bytes": len(raw),
            "sha256": sha256,
            "message": "File caricato con successo. Avvia l'analisi con POST /api/analysis/{job_id}",
        },
    )
