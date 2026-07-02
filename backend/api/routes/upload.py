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

from fastapi import APIRouter, UploadFile, File, HTTPException, status, Request
from fastapi.responses import JSONResponse

from core.rate_limiting import limiter
from utils.config import settings
from utils.i18n import t

router = APIRouter()

MAX_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/")
@limiter.limit("10/minute")
async def upload_email(request: Request, file: UploadFile = File(...)):
    # 1. Validazione nome file e estensione
    if not file.filename:
        raise HTTPException(status_code=400, detail=t("upload.no_filename"))

    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=t("upload.unsupported_format", ext=ext, allowed=settings.ALLOWED_EXTENSIONS),
        )

    # 2. Lettura a chunk con controllo progressivo della dimensione.
    # Legge al massimo MAX_SIZE+1 byte prima di rifiutare: un client che
    # dichiara (o invia) un body enorme non riesce a far bufferizzare al
    # server più dati del limite configurato, indipendentemente dalla
    # dimensione reale della richiesta.
    _CHUNK_SIZE = 1024 * 1024  # 1 MB
    chunks: list[bytes] = []
    total_size = 0
    while True:
        chunk = await file.read(_CHUNK_SIZE)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > MAX_SIZE:
            raise HTTPException(
                status_code=413,
                detail=t("upload.too_large", max_mb=settings.MAX_UPLOAD_SIZE_MB),
            )
        chunks.append(chunk)
    raw = b"".join(chunks)

    if len(raw) == 0:
        raise HTTPException(status_code=400, detail=t("upload.empty_file"))

    # 3. Calcola hash SHA256 del file caricato
    sha256 = hashlib.sha256(raw).hexdigest()

    # 4. Salva in directory upload isolata con nome sicuro (UUID, non il nome originale)
    job_id = str(uuid.uuid4())
    safe_filename = f"{job_id}{ext}"
    dest_path: Path = settings.UPLOAD_DIR / safe_filename

    try:
        dest_path.write_bytes(raw)
    except OSError as e:
        raise HTTPException(status_code=500, detail=t("upload.save_error", error=e))

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "job_id": job_id,
            "original_filename": file.filename,
            "size_bytes": len(raw),
            "sha256": sha256,
            "message": t("upload.success", job_id=job_id),
        },
    )
