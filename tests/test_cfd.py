"""Tests for the gated Cloud-CFD control plane (future / Pro feature).

The solver is mocked (no cloud infra), so these exercise the job state machine,
the quasi-1D placeholder field, cancellation/failure handling, and — importantly
— that the API is dark unless ENABLE_CFD is set.
"""

from __future__ import annotations

import time

import pytest

from app.cfd import (
    CFDCase,
    CFDJob,
    CFDService,
    CFDStatus,
    MockRunner,
    _supersonic_mach_from_area_ratio,
    cfd_enabled,
)


# ---------------------------------------------------------------------------
# Quasi-1D placeholder physics
# ---------------------------------------------------------------------------


def test_area_mach_inversion_round_trips() -> None:
    g = 1.33
    for ar in (1.5, 2.0, 4.0, 8.0):
        m = _supersonic_mach_from_area_ratio(ar, g)
        assert m > 1.0
        # Forward isentropic A/A* of the recovered Mach should match the input.
        term = (2.0 / (g + 1.0)) * (1.0 + 0.5 * (g - 1.0) * m * m)
        ar_back = (1.0 / m) * term ** ((g + 1.0) / (2.0 * (g - 1.0)))
        assert ar_back == pytest.approx(ar, rel=1e-3)


# ---------------------------------------------------------------------------
# Job lifecycle
# ---------------------------------------------------------------------------


def test_job_runs_to_done_with_sensible_field() -> None:
    svc = CFDService(MockRunner(step_seconds=0.0))
    job = svc.submit(CFDCase(area_ratio=4.0, nozzle_pressure_ratio=30.0), background=False)
    assert job.status is CFDStatus.DONE
    assert job.progress == pytest.approx(1.0)
    res = job.result
    assert res is not None and res["placeholder"] is True
    # Supersonic exit, area-ratio 4 → Mach ~2.9 for gamma 1.33.
    assert res["summary"]["exit_mach"] > 1.5
    assert res["summary"]["expansion_state"] in {"under-expanded", "over-expanded", "ideally expanded"}
    # Mach grows monotonically from throat to exit along the field.
    machs = [s["mach"] for s in res["field_samples"]]
    assert machs[0] == pytest.approx(1.0, abs=1e-3)
    assert all(b >= a - 1e-6 for a, b in zip(machs, machs[1:]))
    assert machs[-1] == pytest.approx(res["summary"]["exit_mach"], rel=1e-3)


def test_expansion_state_tracks_pressure_ratio() -> None:
    svc = CFDService(MockRunner(step_seconds=0.0))
    low = svc.submit(CFDCase(area_ratio=3.0, nozzle_pressure_ratio=3.0), background=False)
    high = svc.submit(CFDCase(area_ratio=3.0, nozzle_pressure_ratio=80.0), background=False)
    assert low.result["summary"]["expansion_state"] == "over-expanded"
    assert high.result["summary"]["expansion_state"] == "under-expanded"


def test_resolution_sets_cell_count() -> None:
    assert CFDCase(resolution="coarse").cell_count() < CFDCase(resolution="fine").cell_count()


def test_cancellation_yields_cancelled_status() -> None:
    svc = CFDService(MockRunner(step_seconds=0.0))
    job = CFDJob(id="x", case=CFDCase())
    job._cancel.set()                       # cancel before it runs
    svc._jobs[job.id] = job
    svc._execute(job)
    assert job.status is CFDStatus.CANCELLED
    assert job.result is None


def test_cancel_returns_true_for_active_false_for_terminal() -> None:
    svc = CFDService(MockRunner(step_seconds=0.0))
    active = CFDJob(id="a", case=CFDCase())          # queued
    svc._jobs["a"] = active
    svc._order.append("a")
    assert svc.cancel("a") is True
    done = svc.submit(CFDCase(), background=False)    # terminal
    assert svc.cancel(done.id) is False
    assert svc.cancel("missing") is False


def test_failed_runner_is_reported() -> None:
    class Boom:
        name = "boom"

        def run(self, job, progress):
            raise RuntimeError("solver diverged")

    svc = CFDService(Boom())
    job = svc.submit(CFDCase(), background=False)
    assert job.status is CFDStatus.FAILED
    assert "diverged" in (job.error or "")


def test_background_submission_completes() -> None:
    svc = CFDService(MockRunner(step_seconds=0.001))
    job = svc.submit(CFDCase(), background=True)
    for _ in range(200):
        if job.status in {CFDStatus.DONE, CFDStatus.FAILED}:
            break
        time.sleep(0.01)
    assert job.status is CFDStatus.DONE


# ---------------------------------------------------------------------------
# Feature gate (must be dark for the first launch)
# ---------------------------------------------------------------------------


def test_feature_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_CFD", raising=False)
    assert cfd_enabled() is False


def test_endpoints_404_when_disabled(monkeypatch) -> None:
    from fastapi import HTTPException

    from app.main import cfd_list, cfd_submit
    from app.schemas import CFDSubmitInput

    monkeypatch.delenv("ENABLE_CFD", raising=False)
    with pytest.raises(HTTPException) as e1:
        cfd_submit(CFDSubmitInput())
    assert e1.value.status_code == 404
    with pytest.raises(HTTPException) as e2:
        cfd_list()
    assert e2.value.status_code == 404


def test_endpoints_work_when_enabled(monkeypatch) -> None:
    from app.main import cfd_result, cfd_status, cfd_submit
    from app.schemas import CFDSubmitInput

    monkeypatch.setenv("ENABLE_CFD", "1")
    out = cfd_submit(CFDSubmitInput(case_name="demo", area_ratio=2.5))
    assert out.id and out.case_name == "demo"
    # Drive to completion (shared service uses a zero-delay mock runner).
    for _ in range(200):
        st = cfd_status(out.id)
        if st.status in {"done", "failed"}:
            break
        time.sleep(0.01)
    assert cfd_status(out.id).status == "done"
    result = cfd_result(out.id)
    assert result.result["summary"]["exit_mach"] > 1.0
