"""
api/routes/settings.py

Endpoint per leggere/impostare la lingua e le impostazioni dell'app.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from utils.config import settings
from utils.i18n import t

router = APIRouter()


@router.get("/")
async def get_settings():
    return {
        "language": settings.LANGUAGE,
        "app_name": settings.APP_NAME,
        "version": settings.VERSION,
        "max_upload_mb": settings.MAX_UPLOAD_SIZE_MB,
        "allowed_extensions": settings.ALLOWED_EXTENSIONS,
        "reputation_keys": {
            "AbuseIPDB":         bool(settings.ABUSEIPDB_API_KEY),
            "VirusTotal":        bool(settings.VIRUSTOTAL_API_KEY),
            "PhishTank":         bool(settings.PHISHTANK_API_KEY),
            "URLhaus":           bool(settings.ABUSECH_API_KEY),
            "ThreatFox":         bool(settings.ABUSECH_API_KEY),
            "MalwareBazaar":     bool(settings.ABUSECH_API_KEY or settings.MALWAREBAZAAR_API_KEY),
            "CIRCL Passive DNS": bool(settings.CIRCL_API_KEY),
        },
    }


class LangUpdate(BaseModel):
    language: str  # "it" | "en"


@router.post("/language")
async def set_language(body: LangUpdate):
    """
    Cambia la lingua a runtime (sessione corrente).
    Per rendere il cambio permanente, modifica LANGUAGE nel file .env.
    """
    if body.language not in ("it", "en"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=t("settings.language_unsupported"))
    settings.LANGUAGE = body.language
    return {"language": settings.LANGUAGE, "ok": True}