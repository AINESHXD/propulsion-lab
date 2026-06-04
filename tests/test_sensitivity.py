"""Tests for the one-at-a-time turbojet sensitivity (tornado) analysis."""

from __future__ import annotations

import pytest

from app.engine_core.sensitivity import (
    METRIC_LABELS,
    SENSITIVITY_PARAMS,
    turbojet_sensitivity,
)
from app.engine_core.turbojet import simulate_turbojet_cycle
from app.schemas import TurbojetInput


def _base():
    return TurbojetInput().to_cycle_inputs()


def test_baseline_metric_matches_a_direct_run() -> None:
    base = _base()
    out = turbojet_sensitivity(base, metric="thrust_kN")
    direct = float(simulate_turbojet_cycle(base)["thrust_kN"])
    assert out["base_metric"] == pytest.approx(direct)


def test_rows_sorted_by_swing_descending() -> None:
    out = turbojet_sensitivity(_base(), metric="thrust_kN")
    swings = [r["swing"] for r in out["rows"]]
    assert swings == sorted(swings, reverse=True)
    assert all(s >= 0 for s in swings)


def test_hotter_turbine_raises_thrust() -> None:
    out = turbojet_sensitivity(_base(), metric="thrust_kN", delta_fraction=0.1)
    row = next(r for r in out["rows"] if r["parameter"] == "turbine_inlet_temperature_K")
    # +10% TIT must increase thrust; -10% must decrease it.
    assert row["delta_high"] is not None and row["delta_high"] > 0
    assert row["delta_low"] is not None and row["delta_low"] < 0


def test_top_movers_for_thrust_are_tit_and_mass_flow() -> None:
    # Physically, turbojet thrust is driven hardest by turbine-inlet temperature
    # and inducted air mass flow; pressure ratio mostly trades into TSFC. The
    # ranking should reflect that, not a hand-wave.
    out = turbojet_sensitivity(_base(), metric="thrust_kN")
    top_labels = [r["parameter"] for r in out["rows"][:3]]
    assert "turbine_inlet_temperature_K" in top_labels
    assert "mass_flow_air_kg_s" in top_labels


def test_fraction_params_are_clamped_below_unity() -> None:
    # A big perturbation must not push an efficiency past 1.0.
    out = turbojet_sensitivity(_base(), metric="thrust_kN", delta_fraction=0.5)
    for row in out["rows"]:
        if row["parameter"].endswith("efficiency") or row["parameter"] == "inlet_pressure_recovery":
            assert row["high_value"] <= 0.999 + 1e-9


def test_tsfc_metric_runs_and_is_labelled() -> None:
    out = turbojet_sensitivity(_base(), metric="TSFC_kg_per_kN_hr")
    assert out["metric_label"] == "TSFC"
    assert out["rows"]


def test_unknown_metric_rejected() -> None:
    with pytest.raises(ValueError):
        turbojet_sensitivity(_base(), metric="not_a_metric")


def test_delta_fraction_bounds_enforced() -> None:
    for bad in (0.0, -0.1, 1.0):
        with pytest.raises(ValueError):
            turbojet_sensitivity(_base(), delta_fraction=bad)


def test_all_default_params_are_known_metrics_and_fields() -> None:
    assert set(METRIC_LABELS) >= {"thrust_kN", "TSFC_kg_per_kN_hr"}
    # every default param resolves on the cycle inputs
    base = _base()
    for field, _label, _frac in SENSITIVITY_PARAMS:
        assert hasattr(base, field), f"unknown field {field}"
