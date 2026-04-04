"""
EMLyzer - Backend Entry Point
Cross-platform: Windows + Linux

Il backend serve anche il frontend compilato (cartella static/).
Non è necessario Node.js a runtime: basta avviare uvicorn e aprire
http://localhost:8000 nel browser.
"""

import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path

from api.routes import upload, analysis, reputation, report, health, manual, settings as settings_route, campaigns
from models.database import init_db
from utils.config import settings

# ── Filtro log: sopprime messaggi non-critici che inquinano la console ────────
#
# 1. "Error trying to connect to socket: closing socket - [WinError 10054]"
#    Origine: python-whois (logger 'whois.whois') durante query WHOIS su Windows.
#    Causa: i server WHOIS chiudono il socket TCP dopo la risposta — comportamento
#    normale per TCP half-close, non un errore applicativo.
#
# 2. "[WinError 10054] Connessione interrotta forzatamente"
#    Stessa origine: python-whois o uvicorn su Windows quando il browser chiude
#    la connessione prima che il server finisca di inviare.
#
# Soluzione: filtro installato su tutti i logger coinvolti (whois, whois.whois,
# uvicorn, root) e sul lastResort handler di Python (usato quando non ci sono
# handler configurati). Installazione sia all'import che nel lifespan per
# coprire tutti i casi di inizializzazione.

class _NoiseFilter(logging.Filter):
    """Filtra messaggi di log non-critici che non richiedono azione dell'operatore."""
    _SUPPRESS = (
        "WinError 10054",
        "closing socket",
        "Error trying to connect to socket",
        "ConnectionResetError",
    )
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        return not any(marker in msg for marker in self._SUPPRESS)


def _install_noise_filters() -> None:
    """Installa il filtro su tutti i logger che possono emettere questi messaggi."""
    _filter = _NoiseFilter()
    targets = [
        "",                          # root logger
        "whois",                     # python-whois __init__
        "whois.whois",               # python-whois NICClient
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.websockets",
    ]
    for name in targets:
        lg = logging.getLogger(name)
        # Evita duplicati
        if not any(isinstance(f, _NoiseFilter) for f in lg.filters):
            lg.addFilter(_filter)
        # Installa anche sugli handler esistenti
        for handler in lg.handlers:
            if not any(isinstance(f, _NoiseFilter) for f in handler.filters):
                handler.addFilter(_filter)

    # lastResort: handler di fallback Python 3 (usato quando root non ha handler)
    if logging.lastResort and not any(isinstance(f, _NoiseFilter)
                                      for f in logging.lastResort.filters):
        logging.lastResort.addFilter(_filter)


# Installazione immediata all'import (copre i logger già configurati)
_install_noise_filters()
# ─────────────────────────────────────────────────────────────────────────────

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    await init_db()
    # Re-installa i filtri DOPO che uvicorn ha configurato i suoi handler
    _install_noise_filters()

    yield

    # ── Shutdown pulito ────────────────────────────────────────────────────
    # Chiude l'executor di default di asyncio con wait=False per evitare
    # che threading._shutdown() blocchi su CTRL+C aspettando i thread
    # della fase 2 (VirusTotal/AbuseIPDB possono impiegare decine di secondi).
    #
    # Nota: _default_executor è un attributo privato non disponibile su tutti
    # i loop asyncio (manca su alcune implementazioni Linux/Python 3.13+).
    # Usiamo getattr con fallback silenzioso per compatibilità cross-platform.
    loop = asyncio.get_event_loop()
    executor = getattr(loop, "_default_executor", None)
    if executor is not None:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass  # shutdown non critico: il processo termina comunque


app = FastAPI(
    title="EMLyzer",
    description="Open-source email forensics & threat analysis platform",
    version=settings.VERSION,
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