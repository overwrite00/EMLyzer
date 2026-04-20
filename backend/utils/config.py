"""
Configuration settings for EMLyzer.
Uses pathlib.Path throughout for cross-platform compatibility (Windows + Linux).
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # App
    APP_NAME: str = "EMLyzer"
    VERSION: str = "0.14.0"
    DEBUG: bool = False

    # CORS - backend in produzione + Vite dev server
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:8000",   # backend in produzione (serve anche il frontend)
        "http://127.0.0.1:8000",
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # File upload
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: List[str] = [".eml", ".msg"]

    # Database (SQLite default - cross-platform, no server needed)
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'emlyzer.db'}"

    # Reports output
    REPORTS_DIR: Path = BASE_DIR / "reports"

    # Optional API keys for reputation plugins (empty = disabled)
    ABUSEIPDB_API_KEY: str = ""
    VIRUSTOTAL_API_KEY: str = ""
    PHISHTANK_API_KEY: str = ""
    # abuse.ch unified key — copre URLhaus, ThreatFox e MalwareBazaar (auth.abuse.ch)
    ABUSECH_API_KEY: str = ""
    # chiave legacy MalwareBazaar: ancora accettata per retrocompatibilità
    MALWAREBAZAAR_API_KEY: str = ""
    # CIRCL Passive DNS: formato "username:password" — registrazione gratuita su circl.lu/pdns
    CIRCL_API_KEY: str = ""
    # GreyNoise Community: https://www.greynoise.io/ (100 req/g free)
    GREYNOISE_API_KEY: str = ""
    # URLScan.io: https://urlscan.io/user/signup (100 req/h free — opzionale per search)
    URLSCAN_API_KEY: str = ""
    # Pulsedive: https://pulsedive.com/dashboard/ (30 req/min free)
    PULSEDIVE_API_KEY: str = ""
    # Criminal IP: https://www.criminalip.io/ (free tier)
    CRIMINALIP_API_KEY: str = ""
    # SecurityTrails: https://securitytrails.com/app/account (50 req/mese free)
    SECURITYTRAILS_API_KEY: str = ""
    # Hybrid Analysis: https://www.hybrid-analysis.com/signup (gratuito con registrazione)
    HYBRID_ANALYSIS_API_KEY: str = ""

    # LanguageTool — rilevamento errori grammaticali nel corpo email (opzionale)
    # Lasciare vuoto per disabilitare. URL server locale: http://localhost:8081
    # URL pubblico (con limiti): https://api.languagetool.org/v2/check
    LANGUAGETOOL_API_URL: str = ""

    # Lingua interfaccia: it (italiano) o en (english)
    LANGUAGE: str = "it"

    # Rate limiting (requests per minute per IP)
    RATE_LIMIT_PER_MINUTE: int = 30

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()

# Ensure required directories exist (pathlib handles OS-specific separators)
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)