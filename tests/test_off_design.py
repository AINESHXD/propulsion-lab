"""Tests for the turbojet off-design matching solver.

Pins the three things that matter for Day 8:

1. The solver converges quickly (monotonic bisection on the work balance).
2. At the design throttle + design flight condition it reproduces the
   design-point solver within tolerance (the calibration is self-consistent).
3. Reducing the throttle (Tt4) reduces thrust — the basic off-design trend.
"""

from __future__ import annotations

import pytest

from app.engine_core.off_design import (
    calibrate_turbofan_reference,
    calibrate_turbojet_reference,
    solve_turbofan_off_design,
    solve_turbojet_off_design,
)
from app.engine_core.turbofan import TurbofanCycleInputs, simulate_turbofan_cycle
from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import CycleCalculationError, TurbojetCycleInputs


def _design():
    return TurbojetCycleInputs(
        altitude_m=10000.0, mach=0.8, compressor_pressure_ratio=12.0,
        turbine_inlet_temperature_K=1400.0,
    )


def test_off_design_converges() -> None:
    ref = calibrate_turbojet_reference(_design())
    out = solve_turbojet_off_design(
        ref, altitude_m=10000.0, mach=0.8, turbine_inlet_temperature_K=1400.0
    )
    assert out["off_design"]["converged"]
    assert out["off_design"]["iterations"] < 20


def test_off_design_reproduces_design_point() -> None:
    """At the design throttle + condition the matched point == design point."""

    design_inputs = _design()
    ref = calibrate_turbojet_reference(design_inputs)
    design = simulate_turbojet_cycle(design_inputs)
    matched = solve_turbojet_off_design(
        ref,
        altitude_m=design_inputs.altitude_m,
        mach=design_inputs.mach,
        turbine_inlet_temperature_K=design_inputs.turbine_inlet_temperature_K,
    )
    # Compressor pressure ratio recovered to the design input.
    assert matched["compressor_pressure_ratio"] == pytest.approx(
        design_inputs.compressor_pressure_ratio, rel=5e-3
    )
    # Mass flow and thrust within 0.5 % of the design-point solver.
    assert matched["effective_mass_flow_air_kg_s"] == pytest.approx(
        design["effective_mass_flow_air_kg_s"], rel=5e-3
    )
    assert matched["thrust_N"] == pytest.approx(design["thrust_N"], rel=5e-3)


def test_off_design_throttle_down_reduces_thrust() -> None:
    ref = calibrate_turbojet_reference(_design())
    full = solve_turbojet_off_design(
        ref, altitude_m=10000.0, mach=0.8, turbine_inlet_temperature_K=1400.0
    )
    part = solve_turbojet_off_design(
        ref, altitude_m=10000.0, mach=0.8, turbine_inlet_temperature_K=1250.0
    )
    assert part["thrust_N"] < full["thrust_N"]
    # Lower throttle -> lower compressor pressure ratio (engine spins down).
    assert part["compressor_pressure_ratio"] < full["compressor_pressure_ratio"]


def test_off_design_throttle_below_inlet_temp_raises() -> None:
    """A throttle below the ram-heated inlet stagnation temperature is
    unphysical (no heat could be added) and must be refused. At Mach 2.5,
    sea level, the inlet stagnation temperature is ~650 K."""

    ref = calibrate_turbojet_reference(_design())
    with pytest.raises(CycleCalculationError):
        solve_turbojet_off_design(
            ref, altitude_m=0.0, mach=2.5, turbine_inlet_temperature_K=500.0
        )


def test_off_design_thrust_lapses_with_altitude() -> None:
    """At fixed Mach + throttle, thrust falls with altitude (thinner air)."""

    ref = calibrate_turbojet_reference(_design())
    low = solve_turbojet_off_design(
        ref, altitude_m=3000.0, mach=0.8, turbine_inlet_temperature_K=1400.0
    )
    high = solve_turbojet_off_design(
        ref, altitude_m=11000.0, mach=0.8, turbine_inlet_temperature_K=1400.0
    )
    assert high["thrust_N"] < low["thrust_N"]


# A spread of operating points used by the residual gates below: design point,
# a throttled-down point, and higher/lower altitude points.
_POINTS = [
    {"altitude_m": 10000.0, "mach": 0.8, "turbine_inlet_temperature_K": 1400.0},
    {"altitude_m": 10000.0, "mach": 0.8, "turbine_inlet_temperature_K": 1250.0},
    {"altitude_m": 11000.0, "mach": 0.85, "turbine_inlet_temperature_K": 1380.0},
    {"altitude_m": 6000.0, "mach": 0.6, "turbine_inlet_temperature_K": 1350.0},
]


def test_off_design_static_sea_level_is_finite_and_positive() -> None:
    """Edge case (Day 21) — a static (Mach 0) sea-level point still matches and
    gives finite, positive thrust."""

    import math

    ref = calibrate_turbojet_reference(_design())
    out = solve_turbojet_off_design(
        ref, altitude_m=0.0, mach=0.0, turbine_inlet_temperature_K=1400.0
    )
    assert out["off_design"]["converged"] is True
    assert out["thrust_N"] > 0.0
    assert math.isfinite(out["thrust_N"]) and math.isfinite(out["TSFC_kg_per_kN_hr"])


def test_off_design_work_matching_residual_below_1e6() -> None:
    """Day 9 — the compressor↔turbine spool-work balance closes to a relative
    residual below 1e-6 at every operating point, and the point is converged."""

    ref = calibrate_turbojet_reference(_design())
    for point in _POINTS:
        out = solve_turbojet_off_design(ref, **point)
        assert out["off_design"]["work_residual_relative"] < 1e-6
        assert out["off_design"]["converged"] is True


def test_off_design_mass_continuity_residual_below_1e6() -> None:
    """Day 10 — the matched mass flow satisfies the fixed-area choked-nozzle
    corrected-flow constant (continuity) to a relative residual below 1e-6."""

    ref = calibrate_turbojet_reference(_design())
    for point in _POINTS:
        out = solve_turbojet_off_design(ref, **point)
        assert out["off_design"]["mass_residual_relative"] < 1e-6


# ---------------------------------------------------------------------------
# Day 11 — two-spool turbofan off-design (HPC↔HPT + fan↔LPT simultaneously)
# ---------------------------------------------------------------------------


def _fan_design() -> TurbofanCycleInputs:
    return TurbofanCycleInputs()  # defaults: alt 10 km, M0.78, BPR5, FPR1.55, Tt4 1550


def test_turbofan_off_design_converges() -> None:
    ref = calibrate_turbofan_reference(_fan_design())
    out = solve_turbofan_off_design(
        ref, altitude_m=10000.0, mach=0.78, turbine_inlet_temperature_K=1550.0
    )
    assert out["off_design"]["converged"] is True
    assert out["off_design"]["iterations"] < 20


def test_turbofan_off_design_reproduces_design_point() -> None:
    """At the design throttle + condition the matched point == design point."""

    ins = _fan_design()
    ref = calibrate_turbofan_reference(ins)
    design = simulate_turbofan_cycle(ins)
    matched = solve_turbofan_off_design(
        ref, altitude_m=ins.altitude_m, mach=ins.mach,
        turbine_inlet_temperature_K=ins.turbine_inlet_temperature_K,
    )
    assert matched["fan_pressure_ratio"] == pytest.approx(
        ins.fan_pressure_ratio, rel=5e-3
    )
    assert matched["core_compressor_pressure_ratio"] == pytest.approx(
        ins.core_compressor_pressure_ratio, rel=5e-3
    )
    assert matched["thrust_N"] == pytest.approx(design["thrust_N"], rel=5e-3)
    assert matched["effective_mass_flow_air_kg_s"] == pytest.approx(
        ins.total_mass_flow_air_kg_s, rel=5e-3
    )


def test_turbofan_off_design_throttle_down_spins_both_spools_down() -> None:
    ref = calibrate_turbofan_reference(_fan_design())
    full = solve_turbofan_off_design(
        ref, altitude_m=10000.0, mach=0.78, turbine_inlet_temperature_K=1550.0
    )
    part = solve_turbofan_off_design(
        ref, altitude_m=10000.0, mach=0.78, turbine_inlet_temperature_K=1400.0
    )
    assert part["thrust_N"] < full["thrust_N"]
    # Both spools spin down: fan PR and core PR both drop.
    assert part["fan_pressure_ratio"] < full["fan_pressure_ratio"]
    assert part["core_compressor_pressure_ratio"] < full["core_compressor_pressure_ratio"]


def test_turbofan_off_design_both_spool_residuals_below_1e6() -> None:
    """Day 11 acceptance — both work balances close simultaneously."""

    ref = calibrate_turbofan_reference(_fan_design())
    points = [
        {"altitude_m": 10000.0, "mach": 0.78, "turbine_inlet_temperature_K": 1550.0},
        {"altitude_m": 10000.0, "mach": 0.78, "turbine_inlet_temperature_K": 1420.0},
        {"altitude_m": 8000.0, "mach": 0.6, "turbine_inlet_temperature_K": 1500.0},
    ]
    for point in points:
        out = solve_turbofan_off_design(ref, **point)["off_design"]
        assert out["hp_work_residual_relative"] < 1e-6
        assert out["lp_work_residual_relative"] < 1e-6
        assert out["converged"] is True


def test_turbofan_off_design_rejects_unsupported_config() -> None:
    with pytest.raises(CycleCalculationError):
        calibrate_turbofan_reference(
            TurbofanCycleInputs(nozzle_configuration="mixed")
        )
    with pytest.raises(CycleCalculationError):
        calibrate_turbofan_reference(
            TurbofanCycleInputs(bleed_fraction_hpc_exit=0.05)
        )
