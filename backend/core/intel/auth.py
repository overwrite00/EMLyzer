"""
core/intel/auth.py

Hardening minimo (Wave 3.5) per gli endpoint che scrivono configurazione
(refresh feed forzato, CRUD campagne note, backtest, approvazione proposte).

EMLyzer non ha un sistema di autenticazione: prima di questa Wave, un
endpoint mutante era protetto solo dal fatto che l'app ascoltava di default
su 0.0.0.0 "per comodità" — chiunque sulla stessa rete poteva alterare le
campagne (e quindi i verdetti di rischio) senza lasciare traccia.

Qui non si costruisce un sistema di login: si chiude il gap minimo. Un
endpoint mutante passa se:
  - il client è loopback (127.0.0.1 / ::1), OPPURE
  - l'header X-EMLyzer-Token corrisponde al token generato al primo avvio.

Il token vive in backend/data/admin_token (root-only per convenzione, già
coperto da .gitignore su backend/data/), è generato una sola volta e
stampato in console all'avvio — non richiede alcuna configurazione manuale
per l'uso locale (il caso comune: loopback passa sempre).
"""

from __future__ import annotations

import ipaddress
import logging
import secrets

from fastapi import HTTPException, Request

from utils.config import settings

logger = logging.getLogger(__name__)

_TOKEN_FILE_NAME = "admin_token"
_token_cache: str | None = None


def _token_path():
    return settings.DATA_DIR / _TOKEN_FILE_NAME


def get_or_create_token() -> str:
    """Legge il token da disco, generandolo al primo avvio se assente."""
    global _token_cache
    if _token_cache is not None:
        return _token_cache

    path = _token_path()
    try:
        if path.exists():
            _token_cache = path.read_text(encoding="utf-8").strip()
            if _token_cache:
                return _token_cache
    except Exception:
        pass

    token = secrets.token_urlsafe(32)
    try:
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(token, encoding="utf-8")
    except Exception as e:
        logger.warning("[intel.auth] Impossibile persistere il token admin su disco: %s", e)
    _token_cache = token
    return token


def _is_loopback(request: Request) -> bool:
    host = request.client.host if request.client else ""
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_loopback
    except ValueError:
        return host in ("localhost",)


async def require_trusted_client(request: Request) -> None:
    """
    Dependency FastAPI per ogni endpoint mutante di Threat Intelligence.
    Solleva 403 se il client non è loopback e non presenta il token corretto.
    """
    if _is_loopback(request):
        return

    provided = request.headers.get("X-EMLyzer-Token", "")
    expected = get_or_create_token()
    if provided and secrets.compare_digest(provided, expected):
        return

    raise HTTPException(
        status_code=403,
        detail=(
            "Accesso negato: questo endpoint modifica la configurazione dell'analisi "
            "e richiede una connessione da localhost oppure l'header X-EMLyzer-Token "
            "(vedi la console di avvio o backend/data/admin_token)."
        ),
    )
