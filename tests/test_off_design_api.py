"""Tests for the off-design envelope API endpoints (Day 12).

The endpoint functions are exercised directly (no HTTP layer needed): each
returns its Pydantic response model and raises ``HTTPException`` on bad input.
Covers single-point evaluation, the 100-point envelope grid (and its timing),
the point cap, and rejection of unsupported turbofan configurations.
"""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from app.main import (
    simulate_turbofan_off_design,
    simulate_turbojet_off_design,
)
from app.schemas import (
    OffDesignGridInput,
    TurbofanInput,
    TurbofanOffDesignInput,
    TurbojetInput,
    TurbojetOffDesignInput,
)


# ---------------------------------------------------------------------------
# Turbojet
# ---------------------------------------------------------------------------


def test_turbojet_off_design_single_point_defaults_to_design() -> None:
    """With an empty grid the envelope is a single point at the design condition."""

    out = simulate_turbojet_off_design(TurbojetOffDesignInput(design=TurbojetInput()))
    assert out.engine_type == "turbojet"
    assert out.summary.points == 1
    assert out.summary.successful == 1
    point = out.points[0]
    assert point.success and point.converged is True
    assert point.thrust_kN is not None and point.thrust_kN > 0.0
    assert point.compressor_pressure_ratio is not None


def test_turbojet_off_design_100_point_envelope_is_fast() -> None:
    """A 100-node grid evaluates quickly and (mostly) converges."""

    grid = OffDesignGridInput(
        machs=[0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.82, 0.84, 0.86],
        throttles_K=[1250, 1280, 1310, 1340, 1370, 1400, 1430, 1460, 1490, 1500],
    )
    payload = TurbojetOffDesignInput(design=TurbojetInput(), grid=grid)
    start = time.perf_counter()
    out = simulate_turbojet_off_design(payload)
    elapsed = time.perf_counter() - start

    assert out.summary.points == 100
    assert elapsed < 5.0
    # The vast majority of nodes converge; low-throttle/high-Mach corners may
    # unchoke and are reported as failures rather than aborting the grid.
    assert out.summary.successful >= 90
    assert out.summary.max_thrust_kN is not None


def test_turbojet_off_design_throttle_axis_is_monotonic() -> None:
    """Thrust rises with throttle along a fixed-condition axis."""

    grid = OffDesignGridInput(machs=[0.8], throttles_K=[1300, 1400, 1500])
    out = simulate_turbojet_off_design(
        TurbojetOffDesignInput(design=TurbojetInput(), grid=grid)
    )
    thrusts = [p.thrust_kN for p in out.points]
    assert thrusts[0] < thrusts[1] < thrusts[2]


# ---------------------------------------------------------------------------
# Turbofan
# ---------------------------------------------------------------------------


def test_turbofan_off_design_single_point_defaults_to_design() -> None:
    out = simulate_turbofan_off_design(TurbofanOffDesignInput(design=TurbofanInput()))
    assert out.engine_type == "turbofan"
    assert out.summary.successful == 1
    point = out.points[0]
    assert point.success and point.converged is True
    assert point.thrust_kN is not None and point.thrust_kN > 0.0
    assert point.fan_pressure_ratio is not None
    assert point.overall_pressure_ratio is not None


def test_turbofan_off_design_envelope_grid() -> None:
    grid = OffDesignGridInput(
        machs=[0.6, 0.7, 0.78, 0.82],
        throttles_K=[1450, 1500, 1550, 1600],
    )
    out = simulate_turbofan_off_design(
        TurbofanOffDesignInput(design=TurbofanInput(), grid=grid)
    )
    assert out.summary.points == 16
    assert out.summary.successful == 16


def test_turbofan_off_design_rejects_mixed_flow() -> None:
    with pytest.raises(HTTPException) as exc:
        simulate_turbofan_off_design(
            TurbofanOffDesignInput(
                design=TurbofanInput(nozzle_configuration="mixed")
            )
        )
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Shared behaviour
# ---------------------------------------------------------------------------


def test_turbofan_off_design_zero_bypass_rejected() -> None:
    """Edge case (Day 21) — a zero-bypass turbofan can't calibrate (the bypass
    nozzle has no flow); the endpoint returns a clean 400, not a crash."""

    with pytest.raises(HTTPException) as exc:
        simulate_turbofan_off_design(
            TurbofanOffDesignInput(design=TurbofanInput(bypass_ratio=0.0))
        )
    assert exc.value.status_code == 400


def test_off_design_envelope_point_cap_enforced() -> None:
    """A grid whose cartesian product exceeds the cap is rejected (400)."""

    grid = OffDesignGridInput(
        altitudes_m=[0, 2000, 4000, 6000, 8000, 10000, 11000],
        machs=[0.4, 0.5, 0.6, 0.7, 0.8, 0.82, 0.84],
        throttles_K=[1200, 1250, 1300, 1350, 1400, 1450, 1480, 1500, 1520, 1540],
    )
    with pytest.raises(HTTPException) as exc:
        simulate_turbojet_off_design(
            TurbojetOffDesignInput(design=TurbojetInput(), grid=grid)
        )
    assert exc.value.status_code == 400
