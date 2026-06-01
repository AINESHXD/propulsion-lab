"""Validation harness + conservation-law verification (Day 22).

Code-to-theory verification with no external dataset dependency: the turbojet
solution must conserve spool power, combustor energy, and momentum/thrust to
numerical precision. Also exercises the generic ValidationCase runner so the
Day 25 page can rely on its pass/fail logic.
"""

from __future__ import annotations

from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import TurbojetCycleInputs
from app.validation import (
    CONSERVATION_CASES,
    ReferenceMetric,
    ValidationCase,
    run_conservation_suite,
    run_validation_case,
    verify_turbojet_conservation,
)

TIGHT = 1e-6  # percent — machine-precision conservation gate


def test_conservation_suite_all_points_pass() -> None:
    """Every representative operating point conserves all three laws."""

    results = run_conservation_suite(tolerance_pct=TIGHT)
    assert len(results) == len(CONSERVATION_CASES)
    for r in results:
        assert r.passed, (
            f"{r.name}: spool={r.spool_power_residual_pct:.2e}% "
            f"comb={r.combustor_energy_residual_pct:.2e}% "
            f"thrust={r.thrust_reconstruction_residual_pct:.2e}%"
        )


def test_conservation_each_residual_is_machine_precision() -> None:
    res = verify_turbojet_conservation(
        "check",
        TurbojetCycleInputs(
            altitude_m=10000.0, mach=0.85, compressor_pressure_ratio=14.0,
            turbine_inlet_temperature_K=1500.0,
        ),
        tolerance_pct=TIGHT,
    )
    assert res.spool_power_residual_pct < TIGHT
    assert res.combustor_energy_residual_pct < TIGHT
    assert res.thrust_reconstruction_residual_pct < TIGHT


def test_conservation_holds_without_pressure_thrust() -> None:
    """Thrust reconstruction must still close when pressure thrust is excluded."""

    res = verify_turbojet_conservation(
        "no-pressure-thrust",
        TurbojetCycleInputs(
            altitude_m=10000.0, mach=0.85, compressor_pressure_ratio=14.0,
            turbine_inlet_temperature_K=1500.0, include_pressure_thrust=False,
        ),
    )
    assert res.passed


def test_conservation_rejects_non_turbojet() -> None:
    import pytest
    with pytest.raises(ValueError):
        verify_turbojet_conservation(
            "ab", TurbojetCycleInputs(engine_variant="afterburning_turbojet")
        )


# --- generic ValidationCase runner -----------------------------------------


def _self_referential_case(reference_thrust_kN: float, tol_pct: float) -> ValidationCase:
    return ValidationCase(
        name="self-check", kind="analytical", source="solver self-consistency",
        citation="internal", description="reference = solver's own output",
        engine="turbojet",
        inputs=dict(altitude_m=10000.0, mach=0.8, compressor_pressure_ratio=12.0,
                    turbine_inlet_temperature_K=1500.0),
        metrics=[ReferenceMetric("thrust_kN", "Net thrust", reference_thrust_kN, "kN", tol_pct)],
    )


def test_validation_runner_passes_on_matching_reference() -> None:
    truth = simulate_turbojet_cycle(TurbojetCycleInputs(
        altitude_m=10000.0, mach=0.8, compressor_pressure_ratio=12.0,
        turbine_inlet_temperature_K=1500.0))["thrust_kN"]
    result = run_validation_case(_self_referential_case(truth, tol_pct=0.01))
    assert result.passed
    assert result.metrics[0].deviation_pct < 0.01


def test_validation_runner_fails_on_wrong_reference() -> None:
    result = run_validation_case(_self_referential_case(1.0, tol_pct=3.0))
    assert not result.passed
    assert result.metrics[0].deviation_pct > 3.0


def test_validation_runner_reports_solver_errors() -> None:
    bad = ValidationCase(
        name="bad", kind="analytical", source="x", citation="x",
        description="impossible Tt4 below compressor exit",
        engine="turbojet",
        inputs=dict(altitude_m=0.0, mach=0.0, compressor_pressure_ratio=40.0,
                    turbine_inlet_temperature_K=700.0),
        metrics=[ReferenceMetric("thrust_kN", "Thrust", 10.0, "kN", 3.0)],
    )
    result = run_validation_case(bad)
    assert not result.passed
    assert result.error is not None
