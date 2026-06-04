"""Tests for variable-area nozzle scheduling + afterburner flame stability."""

from __future__ import annotations

import math

import pytest

from app.engine_core.types import TurbojetCycleInputs
from app.engine_core.variable_geometry import (
    afterburner_stability,
    choked_throat_area,
    variable_geometry_analysis,
)


def test_choked_area_matches_closed_form() -> None:
    # A* = m sqrt(Tt) / (Pt * Gamma); check Gamma is the standard choked parameter.
    g, R = 1.33, 285.0
    mdot, Tt, Pt = 50.0, 1100.0, 200000.0
    gamma_param = math.sqrt(g / R) * (2.0 / (g + 1.0)) ** ((g + 1.0) / (2.0 * (g - 1.0)))
    expected = mdot * math.sqrt(Tt) / (Pt * gamma_param)
    assert choked_throat_area(mdot, Tt, Pt, g, R) == pytest.approx(expected)


def test_nozzle_opens_when_reheat_lights() -> None:
    out = variable_geometry_analysis(TurbojetCycleInputs(), afterburner_exit_temperature_K=1900.0)
    van = out["van"]
    # reheat is hotter -> larger throat; the schedule must open (ratio > 1)
    assert van["reheat_throat_area_m2"] > van["dry_throat_area_m2"]
    assert van["area_ratio"] > 1.0
    assert van["percent_open"] > 0.0
    # and reheat augments thrust
    assert out["thrust_augmentation"] > 1.0


def test_hotter_reheat_opens_the_nozzle_more() -> None:
    cool = variable_geometry_analysis(TurbojetCycleInputs(), afterburner_exit_temperature_K=1700.0)
    hot = variable_geometry_analysis(TurbojetCycleInputs(), afterburner_exit_temperature_K=2100.0)
    assert hot["van"]["area_ratio"] > cool["van"]["area_ratio"]


def test_stability_lean_and_rich_blowout() -> None:
    p = 101325.0
    # very lean -> lean blowout
    lean = afterburner_stability(0.05, p)
    assert lean["status"] == "lean_blowout" and not lean["stable"]
    # very rich -> rich blowout
    rich = afterburner_stability(3.0, p)
    assert rich["status"] == "rich_blowout" and not rich["stable"]
    # near stoichiometric at sea level -> stable
    ok = afterburner_stability(1.0, p)
    assert ok["stable"] and ok["status"] == "stable"


def test_low_pressure_blows_the_flame_out() -> None:
    out = afterburner_stability(1.0, 5000.0)  # below the relight floor
    assert out["status"] == "pressure_blowout" and not out["stable"]


def test_lean_limit_climbs_with_altitude() -> None:
    out = variable_geometry_analysis(TurbojetCycleInputs(), afterburner_exit_temperature_K=1900.0)
    env = out["envelope"]
    limits = [e["phi_lean_limit"] for e in env]
    # the lean-blowout equivalence ratio rises monotonically with altitude
    assert all(b >= a - 1e-9 for a, b in zip(limits, limits[1:]))
    assert env[-1]["phi_lean_limit"] > env[0]["phi_lean_limit"]
