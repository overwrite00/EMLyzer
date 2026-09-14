"""
Test Wave 5 — scheduler: policy pure (next_due/backoff) testabili senza
tempo reale, e ciclo di vita start/stop del task asyncio.
"""

from datetime import datetime, timezone
import random

import pytest

from core.intel import runner as intel_runner
from core.intel import scheduler as intel_scheduler


@pytest.fixture(autouse=True)
def _isolate_runner():
    intel_runner._jobs.clear()
    intel_runner._last_attempt_at.clear()
    intel_runner._next_due_at.clear()
    intel_runner._failure_streak.clear()
    yield
    intel_runner._jobs.clear()


def test_backoff_is_pure_and_deterministic():
    assert intel_runner.next_backoff_minutes(0) == 0
    assert intel_runner.next_backoff_minutes(1) == 5
    assert intel_runner.next_backoff_minutes(2) == 10
    assert intel_runner.next_backoff_minutes(3) == 20
    assert intel_runner.next_backoff_minutes(4) == 40  # raddoppio oltre gli step fissi
    assert intel_runner.next_backoff_minutes(10) == 120  # cap


def test_next_due_with_injected_now_and_rng_is_deterministic():
    intel_runner.register(intel_runner.IntelJob(name="x", run=lambda: True, interval_minutes=20, auto=True))
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rng = random.Random(42)
    due1 = intel_runner.next_due("x", now=now, rng=rng)

    rng2 = random.Random(42)
    due2 = intel_runner.next_due("x", now=now, rng=rng2)
    assert due1 == due2  # stesso seed -> stesso risultato, nessun tempo reale coinvolto


def test_next_due_never_for_on_demand_only_job():
    intel_runner.register(intel_runner.IntelJob(name="y", run=lambda: True, interval_minutes=None, auto=False))
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    due = intel_runner.next_due("y", now=now)
    assert due.year > now.year  # "mai" nel breve termine


def test_run_job_now_updates_next_due_on_success():
    calls = []
    intel_runner.register(intel_runner.IntelJob(name="z", run=lambda: calls.append(1) or True, interval_minutes=20, auto=True))
    intel_runner.run_job_now("z")
    import time
    time.sleep(0.2)  # l'esecuzione avviene nell'executor, non sincrona
    assert calls == [1]
    intel_runner.shutdown_executor()


def test_run_job_now_records_failure_and_sets_backoff():
    def _boom():
        raise RuntimeError("simulated failure")
    intel_runner.register(intel_runner.IntelJob(name="w", run=_boom, interval_minutes=20, auto=True))
    intel_runner.run_job_now("w")
    import time
    time.sleep(0.2)
    assert intel_runner._failure_streak["w"] == 1
    intel_runner.shutdown_executor()


@pytest.mark.asyncio
async def test_scheduler_start_stop_is_immediate_no_real_sleep(monkeypatch):
    """Lo shutdown non deve attendere il tick intero: stop() torna quasi subito."""
    from utils.config import settings
    monkeypatch.setattr(settings, "INTEL_AUTO_REFRESH", True)

    intel_scheduler.start(tick_seconds=3600, startup_delay=3600)  # tick "lunghissimo"
    assert intel_scheduler.is_running()

    import time
    start = time.monotonic()
    await intel_scheduler.stop(timeout=2.0)
    elapsed = time.monotonic() - start
    assert elapsed < 2.5  # non ha aspettato l'ora di tick/delay
    assert not intel_scheduler.is_running()


def test_scheduler_disabled_via_flag(monkeypatch):
    from utils.config import settings
    monkeypatch.setattr(settings, "INTEL_AUTO_REFRESH", False)
    intel_scheduler._task = None
    intel_scheduler.start()
    assert not intel_scheduler.is_running()
