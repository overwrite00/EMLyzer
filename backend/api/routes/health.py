"""api/routes/health.py"""
from fastapi import APIRouter
from utils.config import settings

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok", "version": settings.VERSION, "app": settings.APP_NAME}
