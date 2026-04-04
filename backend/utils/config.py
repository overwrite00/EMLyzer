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
    VERSION: str = "0.5.0"
    DEBUG: bool = False

    # CORS - frontend dev server
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",   # Vite default
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
    MALWAREBAZAAR_API_KEY: str = ""

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