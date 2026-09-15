"""
core/intel/runner.py

Esecuzione dei job di Threat Intelligence (refresh feed, fetch bollettini),
sia on-demand (Wave 4, endpoint di refresh manuale) sia automatica (Wave 5,
scheduler). Un solo executor dedicato per entrambi i percorsi, separato da
quello di default usato dall'analisi email — main.py lo chiude allo shutdown
con cancel_futures=True: un fetch di feed condiviso lì verrebbe ucciso a
metà (innocuo grazie alla scrittura atomica della cache, ma rumoroso, e
comunque non è lo scopo di quell'executor).

Policy separata dal meccanismo (Wave 5): next_due()/on_failure() sono
funzioni pure con `now` iniettato, testabili senza dormire minuti interi.
"""

from __future__ import annotations

import logging
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from core.intel import runs as intel_runs
from utils.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IntelJob:
    name: str
    run: Callable[[], bool]   # bloccante — gira sempre nell'executor dedicato
    interval_minutes: int | None  # None = solo on-demand, mai schedulato
    auto: bool                # True = lo scheduler lo esegue da solo quando è dovuto


_jobs: dict[str, IntelJob] = {}
_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()

# Stato di scheduling per-job (letto/scritto solo dal loop dello scheduler,
# Wave 5 — vive qui perché runner e scheduler condividono lo stesso registro).
_last_attempt_at: dict[str, datetime] = {}
_next_due_at: dict[str, datetime] = {}
_failure_streak: dict[str, int] = {}

_BACKOFF_STEPS_MIN = [5, 10, 20]
_BACKOFF_CAP_MIN = 120


def register(job: IntelJob) -> None:
    _jobs[job.name] = job
    _next_due_at.setdefault(job.name, datetime.now(timezone.utc))
    _failure_streak.setdefault(job.name, 0)


def get_job(name: str) -> IntelJob | None:
    return _jobs.get(name)


def all_jobs() -> list[IntelJob]:
    return list(_jobs.values())


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="emlyzer-intel")
        return _executor


def shutdown_executor() -> None:
    global _executor
    with _executor_lock:
        if _executor is not None:
            _executor.shutdown(wait=False)
            _executor = None


def run_job_now(name: str) -> int:
    """
    Esegue subito il job `name` nell'executor dedicato (non blocca il
    chiamante). Ritorna il run_id per il tracciamento in /api/intel/status.
    Solleva KeyError se il job non esiste.
    """
    job = _jobs[name]
    run = intel_runs.start_run(name)
    executor = _get_executor()

    def _wrapped():
        try:
            ok = job.run()
            intel_runs.finish_run(run, result="ok" if ok else "failed")
            if ok:
                _failure_streak[name] = 0
                _next_due_at[name] = _now() + timedelta(minutes=job.interval_minutes or 0)
            else:
                _record_failure(name)
        except Exception as e:
            logger.error("[intel.runner] Job '%s' fallito con eccezione: %s", name, e)
            intel_runs.finish_run(run, result="failed", error_category=type(e).__name__)
            _record_failure(name)

    executor.submit(_wrapped)
    return run.run_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _record_failure(name: str) -> None:
    _failure_streak[name] = _failure_streak.get(name, 0) + 1
    delay_min = next_backoff_minutes(_failure_streak[name])
    _next_due_at[name] = _now() + timedelta(minutes=delay_min)


def next_backoff_minutes(failure_streak: int) -> float:
    """Pura, testabile senza tempo reale: 5 -> 10 -> 20 -> raddoppio fino al cap."""
    if failure_streak <= 0:
        return 0.0
    step = min(failure_streak - 1, len(_BACKOFF_STEPS_MIN) - 1)
    base = _BACKOFF_STEPS_MIN[step]
    extra_doublings = max(0, failure_streak - len(_BACKOFF_STEPS_MIN))
    return min(base * (2 ** extra_doublings), _BACKOFF_CAP_MIN)


def next_due(job_name: str, *, now: datetime | None = None, jitter_fraction: float = 0.1,
             rng: random.Random | None = None) -> datetime:
    """
    Pura rispetto a `now`/`rng` iniettati: calcola quando il job è dovuto di
    nuovo, con un jitter proporzionale per non martellare i feed gratuiti
    tutti allo stesso secondo.
    """
    job = _jobs[job_name]
    now = now or _now()
    rng = rng or random
    if job.interval_minutes is None:
        return now + timedelta(days=3650)  # mai, se non on-demand
    jitter = job.interval_minutes * jitter_fraction * (rng.random() * 2 - 1)
    return now + timedelta(minutes=job.interval_minutes + jitter)


def is_due(job_name: str, *, now: datetime | None = None) -> bool:
    now = now or _now()
    return now >= _next_due_at.get(job_name, now)
