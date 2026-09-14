"""
core/intel/snapshot.py

Pattern "build-then-swap" per strutture in-memory ricaricabili senza
riavviare l'app. Generalizza un pattern che i feed IOC (OpenPhish/Spamhaus,
Wave 2) e il registry delle campagne note (Wave 6) avrebbero altrimenti
implementato due volte in modo leggermente diverso.

Regole non negoziabili incapsulate qui:
- I lettori chiamano get() e tengono il riferimento per tutta l'operazione
  (mai rileggere a metà): sotto il GIL, la riassegnazione di un riferimento
  Python è atomica, quindi get() non ha bisogno di lock.
- Gli scrittori costruiscono la struttura nuova COMPLETAMENTE a parte e la
  installano con un solo swap() finale — mai `.clear()` + ripopolamento, che
  esporrebbe ai lettori concorrenti uno stato a metà.
- swap() è serializzato da un threading.Lock (mai asyncio.Lock: se la
  scrittura avviene in un executor, come per i fetch di rete, un lock
  asyncio non protegge nulla lì; e un lock non va MAI tenuto attraverso un
  `await`, per evitare deadlock tra il loop asyncio e i thread dell'executor).
- try_begin_refresh()/end_refresh() prevengono il thundering herd (due
  richieste concorrenti che scaricano lo stesso feed scaduto) e riportano
  `started_at`: se un refresh resta bloccato oltre il doppio della deadline
  di download attesa, il flag si considera abbandonato e viene auto-
  reclamato con un log, invece di restare acceso per sempre.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

STATE_OK = "ok"
STATE_STALE = "stale"
STATE_UNAVAILABLE = "unavailable"
STATE_NEVER_FETCHED = "never_fetched"
STATE_DISABLED = "disabled"


@dataclass
class SnapshotMeta:
    state: str = STATE_NEVER_FETCHED
    loaded_at: datetime | None = None
    entry_count: int | None = None
    source: str = ""
    last_error_category: str = ""
    last_error_message: str = ""


class Snapshot(Generic[T]):
    """Contenitore thread-safe per una struttura in-memory ricaricabile."""

    def __init__(self, *, refresh_abandon_after: float = 240.0):
        self._value: T | None = None
        self._meta = SnapshotMeta()
        self._swap_lock = threading.Lock()
        self._refreshing = False
        self._refresh_started_at: float | None = None
        self._refresh_abandon_after = refresh_abandon_after

    def get(self) -> T | None:
        """Nessun lock: la lettura del riferimento è atomica sotto il GIL."""
        return self._value

    @property
    def meta(self) -> SnapshotMeta:
        return self._meta

    def swap(self, new_value: T, *, meta: SnapshotMeta) -> None:
        """Installa la nuova struttura con un solo riassegnamento, sotto lock."""
        with self._swap_lock:
            self._value = new_value
            self._meta = meta

    def mark_error(self, category: str, message: str, *, state: str = STATE_UNAVAILABLE) -> None:
        """Registra un errore senza toccare il valore corrente (il vecchio dato resta leggibile)."""
        with self._swap_lock:
            self._meta = SnapshotMeta(
                state=state if self._value is None else self._meta.state,
                loaded_at=self._meta.loaded_at,
                entry_count=self._meta.entry_count,
                source=self._meta.source,
                last_error_category=category,
                last_error_message=message,
            )

    def try_begin_refresh(self) -> bool:
        """
        True se questo chiamante può procedere col refresh (nessun altro in corso).
        Auto-reclama un flag rimasto acceso oltre refresh_abandon_after: un
        thread di fetch appeso (server lentissimo, connessione a metà) non deve
        poter tenere l'endpoint di refresh bloccato a 409 per sempre.
        """
        with self._swap_lock:
            now = time.monotonic()
            if self._refreshing and self._refresh_started_at is not None:
                elapsed = now - self._refresh_started_at
                if elapsed > self._refresh_abandon_after:
                    logger.warning(
                        "[intel.snapshot] Refresh abbandonato dopo %.0fs (soglia %.0fs) — "
                        "flag 'refreshing' auto-reclamato.",
                        elapsed, self._refresh_abandon_after,
                    )
                    self._refreshing = False
            if self._refreshing:
                return False
            self._refreshing = True
            self._refresh_started_at = now
            return True

    def end_refresh(self) -> None:
        """Da chiamare SEMPRE in un blocco finally dopo try_begin_refresh() riuscito."""
        with self._swap_lock:
            self._refreshing = False
            self._refresh_started_at = None

    @property
    def refreshing(self) -> bool:
        return self._refreshing
