"""
core/intel/runs.py

Tracciamento in memoria delle esecuzioni recenti di un job (refresh feed,
fetch bollettini, ecc.), per rendere osservabile un refresh asincrono da
`GET /api/intel/status` (Wave 3/4): il client confronta il proprio run_id,
invece di dedurre l'esito da uno stato globale che il tick successivo
potrebbe già aver sovrascritto.

Non persistito su disco: è telemetria di processo, azzerata a ogni riavvio.
"""

from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

_MAX_RUNS_PER_JOB = 5
_id_counter = itertools.count(1)
_lock = threading.Lock()
_runs: dict[str, list["JobRun"]] = {}


@dataclass
class JobRun:
    run_id: int
    job_name: str
    started_at: datetime
    finished_at: datetime | None = None
    result: str = "running"  # running | ok | failed | skipped
    error_category: str = ""


def start_run(job_name: str) -> JobRun:
    with _lock:
        run = JobRun(run_id=next(_id_counter), job_name=job_name, started_at=datetime.now(timezone.utc))
        _runs.setdefault(job_name, []).insert(0, run)
        _runs[job_name] = _runs[job_name][:_MAX_RUNS_PER_JOB]
        return run


def finish_run(run: JobRun, *, result: str, error_category: str = "") -> None:
    with _lock:
        run.finished_at = datetime.now(timezone.utc)
        run.result = result
        run.error_category = error_category


def recent_runs(job_name: str) -> list[JobRun]:
    with _lock:
        return list(_runs.get(job_name, []))
