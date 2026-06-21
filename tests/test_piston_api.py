"""PistonLab Day 9 — HTTP API (schemas + /piston/simulate, /piston/sweep).

The endpoints wrap the crank-angle solver for the browser. We exercise the
schema/run functions directly (the suite avoids pulling in httpx), plus a check
that the routes are actually registered on the app.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.main import app
from app.schemas_piston import (
    PistonSimulateInput,
    PistonSweepInput,
    run_piston_simulation,
    run_piston_sweep,
)


def test_simulate_default_returns_full_result() -> None:
    out = run_piston_simulation(PistonSimulateInput(fuel="gasoline"))
    assert out.brake_power_W > 0.0
    assert out.imep_Pa > 0.0
    assert out.air_fuel_ratio == pytest.approx(14.69, abs=0.1)
    assert len(out.trace) > 100          # full crank-angle trace for the P–V loop
    assert isinstance(out.operating_warnings, list)


def test_include_trace_false_trims_payload() -> None:
    out = run_piston_simulation(PistonSimulateInput(fuel="gasoline", include_trace=False))
    assert out.trace == []
    assert out.brake_power_W > 0.0       # everything else still present


def test_manual_fuel_has_no_limit_flags() -> None:
    out = run_piston_simulation(PistonSimulateInput())   # fuel=None
    assert out.fuel == "manual"
    assert out.operating_warnings == []


def test_simulate_flags_knock_at_high_cr() -> None:
    out = run_piston_simulation(PistonSimulateInput(fuel="gasoline", compression_ratio=13.0))
    assert any(w.kind == "knock" for w in out.operating_warnings)


def test_simulate_rejects_out_of_range_input() -> None:
    with pytest.raises(ValidationError):
        PistonSimulateInput(compression_ratio=100.0)
    with pytest.raises(ValidationError):
        PistonSimulateInput(aspiration="rocket")


def test_rpm_sweep_is_a_dyno_curve() -> None:
    payload = run_piston_sweep(PistonSweepInput(
        base_input=PistonSimulateInput(fuel="gasoline"),
        sweep_parameter="rpm",
        values=[1000, 2000, 3000, 4000, 5000, 6000],
    ))
    assert payload.summary.successful_cases == 6
    assert payload.summary.failed_cases == 0
    assert payload.summary.peak_brake_power_W > 0.0
    powers = [c.output.brake_power_W for c in payload.cases]
    # Brake power climbs with rpm across this range.
    assert powers[-1] > powers[0]
    # Sweep metrics carry no trace (kept compact for many points).
    assert not hasattr(payload.cases[0].output, "trace")


def test_compression_sweep_counts_knock_cases() -> None:
    payload = run_piston_sweep(PistonSweepInput(
        base_input=PistonSimulateInput(fuel="gasoline"),
        sweep_parameter="compression_ratio",
        values=[9, 11, 13, 15, 18],
    ))
    # The high-CR end knocks on pump gasoline.
    assert payload.summary.knock_cases >= 1


def test_endpoints_are_registered() -> None:
    paths = {route.path for route in app.routes}
    assert "/piston/simulate" in paths
    assert "/piston/sweep" in paths
