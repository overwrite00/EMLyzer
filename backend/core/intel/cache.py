"""
core/intel/cache.py

TTL disk cache versionata e generica, condivisa da feed IOC (Wave 2) e
bollettini CERT-AGID (Wave 7). Generalizza il pattern già esistente in
core/reputation/connectors.py (_cache_load/_cache_save), con tre differenze:

1. Payload con schema esplicito ("schema", "saved_at", "source_url", "data").
   Un payload legacy senza "schema" viene trattato come schema 0 e resta
   leggibile (compatibilità con le cache già presenti sul disco degli utenti:
   backend/data/cache/openphish_feed.json, spamhaus_drop.json).
2. Un mismatch di schema è un cache-miss pulito (torna None), mai un errore:
   se il formato di un feed cambia, la vecchia cache non viene interpretata
   male, semplicemente ignorata.
3. save() logga un WARNING la prima volta che fallisce (disco pieno, permessi),
   invece del `except Exception: pass` muto attuale — con uno scheduler che
   gira in background un fallimento silenzioso diventerebbe un refresh che
   "riesce" e non persiste mai, ripetuto a ogni tick per l'intera sessione.

Vincolo di compatibilità (testato): il payload scritto da save() resta un
superset di quello legacy — "saved_at" e "data" restano al livello radice con
lo stesso significato, così una versione precedente di EMLyzer che legga
questa cache (downgrade) continua a funzionare.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.config import settings

logger = logging.getLogger(__name__)

CURRENT_SCHEMA = 1

# Traccia (per nome cache) se il fallimento di save() è già stato loggato in
# questa sessione di processo, per evitare di inondare i log a ogni tick dello
# scheduler quando il disco è pieno o la directory non è scrivibile.
_save_failure_logged: set[str] = set()


@dataclass
class CacheEntry:
    data: Any
    saved_at: datetime
    source_url: str
    schema: int

    @property
    def age_hours(self) -> float:
        return (datetime.now(timezone.utc) - self.saved_at).total_seconds() / 3600


@dataclass
class CacheStat:
    exists: bool
    saved_at: datetime | None
    age_hours: float | None
    entry_count: int | None
    source_url: str
    schema: int | None


def _cache_path(name: str) -> Path:
    return settings.CACHE_DIR / f"{name}.json"


def load(name: str, *, ttl_hours: float | None = None, expected_schema: int | None = None) -> CacheEntry | None:
    """
    Carica una entry dal cache su disco.

    ttl_hours: se dato e l'entry è più vecchia, ritorna None (scaduta) —
      passare None per ignorare l'età (fallback su cache stale).
    expected_schema: se dato e lo schema salvato è diverso, ritorna None
      (cache-miss pulito, non un errore) — usato quando il formato di un
      feed cambia da una versione all'altra.
    """
    path = _cache_path(name)
    try:
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as f:
            raw = json.load(f)

        schema = raw.get("schema", 0)  # payload legacy senza "schema" = schema 0
        if expected_schema is not None and schema != expected_schema:
            return None

        saved_at = datetime.fromisoformat(raw["saved_at"])
        if saved_at.tzinfo is None:
            saved_at = saved_at.replace(tzinfo=timezone.utc)

        entry = CacheEntry(
            data=raw["data"],
            saved_at=saved_at,
            source_url=raw.get("source_url", ""),
            schema=schema,
        )
        if ttl_hours is not None and entry.age_hours > ttl_hours:
            return None
        return entry
    except Exception:
        return None  # cache assente/corrotta/illeggibile: comportarsi come cache-miss


def save(name: str, data: Any, *, source_url: str = "", schema: int = CURRENT_SCHEMA) -> bool:
    """
    Salva data su disco con scrittura atomica (tmp + os.replace).
    Ritorna True se la scrittura è riuscita, False altrimenti (loggato una
    sola volta per nome cache per sessione di processo).
    """
    try:
        settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path(name)
        payload = {
            "schema": schema,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "source_url": source_url,
            "data": data,
        }
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f)
        tmp.replace(path)
        _save_failure_logged.discard(name)
        return True
    except Exception as e:
        if name not in _save_failure_logged:
            logger.warning(
                "[intel.cache] Impossibile scrivere la cache '%s' su disco (%s: %s). "
                "Il refresh sembrerà riuscito ma non verrà persistito finché il "
                "problema non è risolto (disco pieno? permessi?).",
                name, type(e).__name__, e,
            )
            _save_failure_logged.add(name)
        return False


def stat(name: str) -> CacheStat:
    """Metadati di una cache senza doverne rileggere/deserializzare il contenuto intero per l'uso comune."""
    path = _cache_path(name)
    if not path.exists():
        return CacheStat(exists=False, saved_at=None, age_hours=None, entry_count=None, source_url="", schema=None)
    entry = load(name, ttl_hours=None)
    if entry is None:
        return CacheStat(exists=True, saved_at=None, age_hours=None, entry_count=None, source_url="", schema=None)
    try:
        count = len(entry.data)
    except TypeError:
        count = None
    return CacheStat(
        exists=True,
        saved_at=entry.saved_at,
        age_hours=entry.age_hours,
        entry_count=count,
        source_url=entry.source_url,
        schema=entry.schema,
    )
