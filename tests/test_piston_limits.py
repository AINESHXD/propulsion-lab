"""PistonLab Day 8 — operating limits (knock / smoke / lean misfire).

These are flagged *warnings*, never hard failures: a knocking or smoking point
still returns a full result you can learn from. The two headline limits:

* SI **knock** worsens with compression ratio and boost (both raise the end-gas
  state) and improves with octane.
* CI **smoke** appears when a diesel is over-fuelled past its mixing-limited
  equivalence ratio.
"""

from __future__ import annotations

import pytest

from app.engine_core.piston import (
    PistonCycleInputs,
    autoignition_temperature_K,
    end_gas_temperature_K,
    evaluate_operating_limits,
    knock_margin_K,
    simulate_piston_cycle,
)


def _kinds(result) -> set[str]:
    return {w["kind"] for w in result.operating_warnings}


def _has(result, kind: str, severity: str | None = None) -> bool:
    return any(
        w["kind"] == kind and (severity is None or w["severity"] == severity)
        for w in result.operating_warnings
    )


# ---------------------------------------------------------------------------
# Knock-model building blocks
# ---------------------------------------------------------------------------


def test_end_gas_temperature_rises_with_pressure_and_intake_temp() -> None:
    lo = end_gas_temperature_K(330.0, 80e5, 1e5, 1.35)
    hi = end_gas_temperature_K(330.0, 120e5, 1e5, 1.35)
    hot = end_gas_temperature_K(360.0, 80e5, 1e5, 1.35)
    assert hi > lo > 0.0
    assert hot > lo


def test_autoignition_temperature_rises_with_octane_falls_with_pressure() -> None:
    assert autoignition_temperature_K(108.0, 80e5) > autoignition_temperature_K(95.0, 80e5)
    # Higher peak pressure shortens the ignition delay -> lower effective limit.
    assert autoignition_temperature_K(95.0, 120e5) < autoignition_temperature_K(95.0, 60e5)


def test_knock_margin_is_none_for_compression_ignition() -> None:
    # Diesel has no RON; spark knock does not apply.
    assert knock_margin_K("diesel", 330.0, 100e5, 1e5, 1.35) is None
    assert knock_margin_K("gasoline", 330.0, 100e5, 1e5, 1.35) is not None


def test_evaluate_with_no_fuel_is_empty() -> None:
    assert evaluate_operating_limits(None, 1.0, 330.0, 100e5, 1e5, 1.35) == []
    assert evaluate_operating_limits("manual", 1.0, 330.0, 100e5, 1e5, 1.35) == []


# ---------------------------------------------------------------------------
# Knock on the full cycle
# ---------------------------------------------------------------------------


def test_default_gasoline_point_is_within_limits() -> None:
    r = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", compression_ratio=10.5))
    assert r.operating_warnings == []


def test_high_compression_ratio_triggers_knock() -> None:
    r = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", compression_ratio=13.0))
    assert _has(r, "knock", "warning")


def test_boost_triggers_knock() -> None:
    r = simulate_piston_cycle(PistonCycleInputs(
        fuel="gasoline", compression_ratio=10.5,
        intake_pressure_Pa=1.8e5, intake_temperature_K=345, aspiration="turbocharged"))
    assert _has(r, "knock", "warning")


def test_octane_resists_knock() -> None:
    common = dict(compression_ratio=12.0, intake_pressure_Pa=1.8e5,
                  intake_temperature_K=345, aspiration="turbocharged")
    gas = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", **common))
    eth = simulate_piston_cycle(PistonCycleInputs(fuel="ethanol", **common))
    # Same CR and boost: pump gasoline knocks, high-octane ethanol does not.
    assert _has(gas, "knock", "warning")
    assert not _has(eth, "knock", "warning")


def test_knock_is_a_warning_not_a_failure() -> None:
    # A knocking point still returns a complete, physical result.
    r = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", compression_ratio=14.0))
    assert _has(r, "knock")
    assert r.indicated_work_J > 0.0
    assert r.imep_Pa > 0.0


# ---------------------------------------------------------------------------
# Smoke (diesel) and lean misfire (SI)
# ---------------------------------------------------------------------------


def test_diesel_overfuelling_triggers_smoke() -> None:
    rich = simulate_piston_cycle(PistonCycleInputs(fuel="diesel", compression_ratio=18.0, equivalence_ratio=0.95))
    lean = simulate_piston_cycle(PistonCycleInputs(fuel="diesel", compression_ratio=18.0, equivalence_ratio=0.6))
    assert _has(rich, "smoke", "warning")
    assert not _has(lean, "smoke")


def test_diesel_does_not_get_a_knock_flag() -> None:
    # Compression ignition is judged on smoke, never spark knock.
    r = simulate_piston_cycle(PistonCycleInputs(fuel="diesel", compression_ratio=20.0, equivalence_ratio=0.8))
    assert not _has(r, "knock")


def test_lean_mixture_flags_misfire() -> None:
    r = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", equivalence_ratio=0.45))
    assert _has(r, "lean_misfire", "warning")


def test_manual_fuel_reports_no_limits() -> None:
    r = simulate_piston_cycle(PistonCycleInputs())   # fuel=None
    assert r.operating_warnings == []


def test_warning_records_are_well_formed() -> None:
    r = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", compression_ratio=13.0))
    assert r.operating_warnings
    for w in r.operating_warnings:
        assert set(w) == {"kind", "severity", "message"}
        assert w["severity"] in ("caution", "warning")
        assert w["message"]
