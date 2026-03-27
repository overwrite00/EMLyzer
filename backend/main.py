"""
EMLyzer - Backend Entry Point
Cross-platform: Windows + Linux

Il backend serve anche il frontend compilato (cartella static/).
Non è necessario Node.js a runtime: basta avviare uvicorn e aprire
http://localhost:8000 nel browser.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path

from api.routes import upload, analysis, reputation, report, health, manual, settings as settings_route, campaigns
from models.database import init_db
from utils.config import settings

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    await init_db()
    yield


app = FastAPI(
    title="EMLyzer",
    description="Open-source email forensics & threat analysis platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes — devono stare PRIMA del mount degli static files
app.include_router(health.router,      prefix="/api",            tags=["health"])
app.include_router(upload.router,      prefix="/api/upload",     tags=["upload"])
app.include_router(analysis.router,    prefix="/api/analysis",   tags=["analysis"])
app.include_router(reputation.router,  prefix="/api/reputation", tags=["reputation"])
app.include_router(report.router,      prefix="/api/report",     tags=["report"])
app.include_router(manual.router,         prefix="/api/manual",    tags=["manual"])
app.include_router(settings_route.router, prefix="/api/settings",  tags=["settings"])
app.include_router(campaigns.router,       prefix="/api/campaigns",  tags=["campaigns"])

# Serve il frontend compilato (assets JS/CSS/immagini)
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    # SPA fallback: qualsiasi URL non-API restituisce index.html
    # (necessario per il routing lato client di React)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = STATIC_DIR / "index.html"
        return FileResponse(str(index))
