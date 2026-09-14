"""
core/intel/scheduler.py

Automazione (Wave 5) sopra il runner on-demand (Wave 4): un solo
asyncio.Task nel lifespan di FastAPI che, a intervalli, esegue i job
registrati con auto=True e is_due(). I feed IOC sono auto=True perché
run_fast_checks() li carica sincronamente in-request: un TTL scaduto si
paga altrimenti in latenza dentro l'analisi dell'utente. I bollettini
CERT-AGID sono auto=False: bacheca per un umano, nessun bisogno di
real-time, e aggiornarli in background aggiungerebbe solo traffico verso
un sito della PA senza rendere nessuna analisi più accurata.

Il loop non dorme mai per il tick intero: usa `stop_event.wait(timeout)`,
cancellabile immediatamente allo shutdown senza attese nei test o all'uscita
dell'app. `clock`/`tick_seconds` sono iniettabili per policy testabile senza
tempo reale (vedi core.intel.runner.next_due/next_backoff_minutes, pure).
"""

from __future__ import annotations

import asyncio
import logging

from core.intel import runner as intel_runner
from utils.config import settings

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


async def _loop(tick_seconds: float, startup_delay: float) -> None:
    assert _stop_event is not None
    try:
        await asyncio.wait_for(_stop_event.wait(), timeout=startup_delay)
        return  # stop richiesto durante il delay di avvio
    except asyncio.TimeoutError:
        pass  # delay scaduto normalmente, si procede

    while not _stop_event.is_set():
        for job in intel_runner.all_jobs():
            if not job.auto:
                continue
            if intel_runner.is_due(job.name):
                logger.debug("[intel.scheduler] Job '%s' dovuto, avvio refresh", job.name)
                intel_runner.run_job_now(job.name)
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=tick_seconds)
        except asyncio.TimeoutError:
            continue  # tick scaduto, si ricomincia
        break  # stop_event settato


def start(*, tick_seconds: float | None = None, startup_delay: float | None = None) -> None:
    """Da chiamare una sola volta nel lifespan, dopo aver registrato i job."""
    global _task, _stop_event
    if not settings.INTEL_AUTO_REFRESH:
        logger.info("[intel.scheduler] INTEL_AUTO_REFRESH=false — scheduler non avviato")
        return
    if _task is not None:
        return
    tick = tick_seconds if tick_seconds is not None else settings.INTEL_TICK_MINUTES * 60
    delay = startup_delay if startup_delay is not None else settings.INTEL_STARTUP_DELAY_SECONDS
    _stop_event = asyncio.Event()
    _task = asyncio.ensure_future(_loop(tick, delay))
    logger.info("[intel.scheduler] Scheduler avviato (tick=%ss, startup_delay=%ss)", tick, delay)


async def stop(*, timeout: float = 2.0) -> None:
    """Da chiamare nello shutdown del lifespan: cancellazione pulita, mai bloccante."""
    global _task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _task is not None:
        try:
            await asyncio.wait_for(asyncio.gather(_task, return_exceptions=True), timeout=timeout)
        except asyncio.TimeoutError:
            _task.cancel()
        _task = None
    intel_runner.shutdown_executor()


def is_running() -> bool:
    return _task is not None and not _task.done()
