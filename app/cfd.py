"""Cloud-CFD job orchestration backend (future / Pro feature — gated off).

This is the *control plane* for a computational-fluid-dynamics pipeline: it
accepts a nozzle/blade-row case, tracks it through a job state machine
(queued → meshing → solving → done / failed / cancelled), and returns the field
result. The actual solve is delegated to a pluggable ``Runner``:

- :class:`MockRunner` runs locally with no external dependency. It "meshes" and
  "solves" a converging–diverging nozzle with a cheap quasi-1D area–Mach model
  and returns a physically-plausible field summary. It exists so the whole
  control plane — submission, status polling, cancellation, results — is
  testable and demoable without any cloud infrastructure.
- :class:`CloudRunner` is the production hook (AWS Batch / a containerised SU2 or
  OpenFOAM solve, GMSH meshing, VTK result extraction). It is intentionally a
  stub here; wiring it up is out of scope for the first launch.

The whole feature is **disabled by default** and only exposed when the
``ENABLE_CFD`` environment variable is set, so it ships dark and adds nothing to
the public launch surface. The in-memory job store is fine for a single-process
demo; a real deployment would back it with Redis + a Celery/RQ worker.
"""

from __future__ import annotations

import math
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Protocol


def cfd_enabled() -> bool:
    """Whether the CFD feature is switched on (off for the first launch)."""

    return os.environ.get("ENABLE_CFD", "0") not in ("0", "", "false", "False")


# ---------------------------------------------------------------------------
# Job model + state machine
# ---------------------------------------------------------------------------


class CFDStatus(str, Enum):
    QUEUED = "queued"
    MESHING = "meshing"
    SOLVING = "solving"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


_TERMINAL = {CFDStatus.DONE, CFDStatus.FAILED, CFDStatus.CANCELLED}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class CFDCase:
    """A converging–divergent nozzle CFD case (the unit of work)."""

    case_name: str = "nozzle"
    throat_area_m2: float = 0.05
    area_ratio: float = 2.0                  # exit area / throat area
    nozzle_pressure_ratio: float = 6.0       # Pt_inlet / p_back
    gamma: float = 1.33
    resolution: str = "medium"               # coarse | medium | fine

    def cell_count(self) -> int:
        return {"coarse": 4_000, "medium": 20_000, "fine": 80_000}.get(self.resolution, 20_000)


@dataclass
class CFDJob:
    """A tracked CFD job and its evolving status."""

    id: str
    case: CFDCase
    status: CFDStatus = CFDStatus.QUEUED
    progress: float = 0.0                     # 0..1
    message: str = "queued"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    result: dict[str, Any] | None = None
    error: str | None = None
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "case_name": self.case.case_name,
            "status": self.status.value,
            "progress": round(self.progress, 3),
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "cells": self.case.cell_count(),
            "has_result": self.result is not None,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Runner interface + implementations
# ---------------------------------------------------------------------------


# Called by a runner to publish progress: (status, progress 0..1, message).
ProgressCallback = Callable[[CFDStatus, float, str], None]


class Runner(Protocol):
    name: str

    def run(self, job: CFDJob, progress: ProgressCallback) -> dict[str, Any]: ...


def _supersonic_mach_from_area_ratio(area_ratio: float, gamma: float) -> float:
    """Invert the isentropic A/A* relation on the supersonic branch (bisection)."""

    g = gamma

    def area_ratio_of(mach: float) -> float:
        term = (2.0 / (g + 1.0)) * (1.0 + 0.5 * (g - 1.0) * mach * mach)
        return (1.0 / mach) * term ** ((g + 1.0) / (2.0 * (g - 1.0)))

    lo, hi = 1.0001, 12.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if area_ratio_of(mid) < area_ratio:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


class MockRunner:
    """Local stand-in solver: a quasi-1D area–Mach nozzle field.

    Not a real CFD solve — it is a cheap, deterministic placeholder so the
    control plane works end to end. The field it returns is physically sensible
    (isentropic CD-nozzle expansion) and clearly labelled as a placeholder.
    """

    name = "mock-quasi-1d"

    def __init__(self, step_seconds: float = 0.0, n_samples: int = 24) -> None:
        self.step_seconds = step_seconds
        self.n_samples = n_samples

    def run(self, job: CFDJob, progress: ProgressCallback) -> dict[str, Any]:
        case = job.case
        g = case.gamma

        # ---- Meshing stage -------------------------------------------------
        progress(CFDStatus.MESHING, 0.05, f"meshing {case.cell_count():,} cells")
        cells = case.cell_count()
        for k in range(1, 5):
            if job._cancel.is_set():
                raise _Cancelled()
            time.sleep(self.step_seconds)
            progress(CFDStatus.MESHING, 0.05 + 0.20 * k / 4, "building mesh")

        # ---- Solving stage -------------------------------------------------
        progress(CFDStatus.SOLVING, 0.30, "iterating to convergence")
        exit_mach = _supersonic_mach_from_area_ratio(case.area_ratio, g)
        # Static-to-total pressure at the exit (isentropic).
        p_exit_ratio = (1.0 + 0.5 * (g - 1.0) * exit_mach * exit_mach) ** (-g / (g - 1.0))
        design_npr = 1.0 / p_exit_ratio
        if case.nozzle_pressure_ratio > design_npr * 1.05:
            expansion = "under-expanded"
        elif case.nozzle_pressure_ratio < design_npr * 0.95:
            expansion = "over-expanded"
        else:
            expansion = "ideally expanded"

        samples: list[dict[str, float]] = []
        residual = 1.0
        for k in range(1, 11):
            if job._cancel.is_set():
                raise _Cancelled()
            time.sleep(self.step_seconds)
            residual *= 0.45                       # synthetic convergence history
            progress(CFDStatus.SOLVING, 0.30 + 0.65 * k / 10,
                     f"residual {residual:.2e}")

        # Axial field: area grows throat→exit, Mach follows the supersonic branch.
        for i in range(self.n_samples):
            x = i / (self.n_samples - 1)
            ar = 1.0 + (case.area_ratio - 1.0) * x
            m = 1.0 if ar <= 1.0 else _supersonic_mach_from_area_ratio(ar, g)
            pr = (1.0 + 0.5 * (g - 1.0) * m * m) ** (-g / (g - 1.0))
            samples.append({"x": round(x, 4), "area_ratio": round(ar, 4),
                            "mach": round(m, 4), "p_static_over_pt": round(pr, 5)})

        return {
            "solver": self.name,
            "placeholder": True,
            "note": ("Quasi-1D area–Mach placeholder field. The production "
                     "pipeline runs a containerised SU2/OpenFOAM solve on a "
                     "GMSH mesh; this stand-in keeps the control plane testable "
                     "without cloud infrastructure."),
            "mesh": {"cells": cells, "topology": "axisymmetric-cd-nozzle"},
            "summary": {
                "exit_mach": round(exit_mach, 4),
                "design_nozzle_pressure_ratio": round(design_npr, 3),
                "operating_nozzle_pressure_ratio": round(case.nozzle_pressure_ratio, 3),
                "expansion_state": expansion,
                "final_residual": residual,
            },
            "field_samples": samples,
        }


class CloudRunner:
    """Production runner (AWS Batch + containerised SU2/OpenFOAM). Stub for now."""

    name = "cloud-su2"

    def run(self, job: CFDJob, progress: ProgressCallback) -> dict[str, Any]:  # pragma: no cover
        raise NotImplementedError(
            "CloudRunner is not wired up in this build. It would submit a GMSH "
            "mesh + SU2 job to AWS Batch, stream solver residuals back through "
            "`progress`, and return the VTK-extracted field. Set up the compute "
            "environment and container image before enabling it."
        )


class _Cancelled(Exception):
    """Raised inside a runner when the job's cancel flag is set."""


# ---------------------------------------------------------------------------
# Job store + service
# ---------------------------------------------------------------------------


class CFDService:
    """In-memory job store + executor. Single-process; swap for Redis + a worker."""

    def __init__(self, runner: Runner | None = None, max_jobs: int = 200) -> None:
        self.runner: Runner = runner or MockRunner(step_seconds=0.0)
        self._jobs: dict[str, CFDJob] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self._max_jobs = max_jobs

    def submit(self, case: CFDCase, *, background: bool = True) -> CFDJob:
        job = CFDJob(id=uuid.uuid4().hex[:12], case=case)
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
            # Evict the oldest terminal jobs if we are over the cap.
            while len(self._order) > self._max_jobs:
                old = self._order.pop(0)
                self._jobs.pop(old, None)
        if background:
            threading.Thread(target=self._execute, args=(job,), daemon=True).start()
        else:
            self._execute(job)
        return job

    def _execute(self, job: CFDJob) -> None:
        def publish(status: CFDStatus, progress: float, message: str) -> None:
            job.status = status
            job.progress = progress
            job.message = message
            job.updated_at = _now()

        try:
            publish(CFDStatus.MESHING, 0.0, "starting")
            result = self.runner.run(job, publish)
            if job._cancel.is_set():
                publish(CFDStatus.CANCELLED, job.progress, "cancelled")
                return
            job.result = result
            publish(CFDStatus.DONE, 1.0, "complete")
        except _Cancelled:
            publish(CFDStatus.CANCELLED, job.progress, "cancelled")
        except Exception as exc:                       # noqa: BLE001 - report any solver error
            job.error = str(exc)
            publish(CFDStatus.FAILED, job.progress, f"failed: {exc}")

    def get(self, job_id: str) -> CFDJob | None:
        return self._jobs.get(job_id)

    def list(self) -> list[CFDJob]:
        with self._lock:
            return [self._jobs[i] for i in reversed(self._order) if i in self._jobs]

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None or job.status in _TERMINAL:
            return False
        job._cancel.set()
        return True


# Shared singleton used by the (gated) API endpoints.
service = CFDService()
