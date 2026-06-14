"""PistonLab Day 4 — friction (Chen-Flynn FMEP) and the indicated->brake split.

Everything the cycle reports up to now is *indicated*. Real crankshaft output
is *brake*: indicated minus friction. These tests check the Chen-Flynn FMEP
model and the brake performance it produces — brake is always below indicated,
and friction grows with both engine speed and peak cylinder pressure.
"""

from __future__ import annotations

import math

import pytest

from app.engine_core.piston import (
    PistonCycleInputs,
    chen_flynn_fmep_Pa,
    simulate_piston_cycle,
)


# ---------------------------------------------------------------------------
# Chen-Flynn FMEP in isolation
# ---------------------------------------------------------------------------


def test_fmep_positive_and_in_band() -> None:
    fmep = chen_flynn_fmep_Pa(peak_pressure_Pa=70.0e5, mean_piston_speed_m_s=12.0)
    # Passenger-car FMEP is roughly 0.5 - 2.5 bar.
    assert 0.5e5 < fmep < 2.5e5


def test_fmep_rises_with_speed_and_peak_pressure() -> None:
    base = chen_flynn_fmep_Pa(60.0e5, 8.0)
    faster = chen_flynn_fmep_Pa(60.0e5, 16.0)
    harder = chen_flynn_fmep_Pa(110.0e5, 8.0)
    assert faster > base
    assert harder > base


def test_fmep_multiplier_scales_and_validates() -> None:
    one = chen_flynn_fmep_Pa(60.0e5, 10.0, multiplier=1.0)
    two = chen_flynn_fmep_Pa(60.0e5, 10.0, multiplier=2.0)
    assert two == pytest.approx(2.0 * one, rel=1e-9)
    with pytest.raises(ValueError):
        chen_flynn_fmep_Pa(60.0e5, 10.0, multiplier=-1.0)
    with pytest.raises(ValueError):
        chen_flynn_fmep_Pa(-1.0, 10.0)


# ---------------------------------------------------------------------------
# Brake performance on the full cycle
# ---------------------------------------------------------------------------


def test_brake_is_always_below_indicated() -> None:
    r = simulate_piston_cycle(PistonCycleInputs())
    assert r.bmep_Pa < r.imep_Pa
    assert r.brake_work_J < r.indicated_work_J
    assert r.brake_power_W < r.indicated_power_W
    assert r.brake_torque_Nm < r.indicated_torque_Nm
    assert 0.0 < r.mechanical_efficiency < 1.0
    assert r.brake_thermal_efficiency < r.thermal_efficiency


def test_zero_friction_makes_brake_equal_indicated() -> None:
    r = simulate_piston_cycle(PistonCycleInputs(friction_multiplier=0.0))
    assert r.fmep_Pa == 0.0
    assert r.bmep_Pa == pytest.approx(r.imep_Pa, rel=1e-12)
    assert r.brake_power_W == pytest.approx(r.indicated_power_W, rel=1e-12)
    assert r.mechanical_efficiency == pytest.approx(1.0, rel=1e-12)


def test_fmep_rises_with_engine_speed_on_cycle() -> None:
    fmeps = [
        simulate_piston_cycle(PistonCycleInputs(rpm=n)).fmep_Pa
        for n in (1500, 3000, 5000, 7000)
    ]
    assert fmeps == sorted(fmeps)
    assert all(b > a for a, b in zip(fmeps, fmeps[1:]))


def test_mechanical_efficiency_falls_with_speed() -> None:
    slow = simulate_piston_cycle(PistonCycleInputs(rpm=1500))
    fast = simulate_piston_cycle(PistonCycleInputs(rpm=7000))
    # Friction takes a bigger share of indicated work as speed climbs.
    assert fast.mechanical_efficiency < slow.mechanical_efficiency


def test_fmep_rises_with_peak_pressure_on_cycle() -> None:
    lo = simulate_piston_cycle(PistonCycleInputs(heat_release_J_per_kg=1.5e6))
    hi = simulate_piston_cycle(PistonCycleInputs(heat_release_J_per_kg=3.0e6))
    assert hi.peak_pressure_Pa > lo.peak_pressure_Pa
    assert hi.fmep_Pa > lo.fmep_Pa


def test_more_friction_means_less_brake() -> None:
    light = simulate_piston_cycle(PistonCycleInputs(friction_multiplier=1.0))
    heavy = simulate_piston_cycle(PistonCycleInputs(friction_multiplier=2.0))
    assert heavy.brake_power_W < light.brake_power_W
    assert heavy.mechanical_efficiency < light.mechanical_efficiency


def test_brake_power_torque_consistency() -> None:
    inp = PistonCycleInputs(rpm=4000.0)
    r = simulate_piston_cycle(inp)
    omega = 2.0 * math.pi * inp.rpm / 60.0
    assert r.brake_power_W == pytest.approx(r.brake_torque_Nm * omega, rel=1e-9)


def test_bsfc_is_positive_and_sane() -> None:
    r = simulate_piston_cycle(PistonCycleInputs())
    # Brake specific fuel consumption for an SI engine is a few hundred g/kWh.
    assert 120.0 < r.bsfc_g_per_kWh < 450.0
    assert r.fuel_mass_per_cycle_kg > 0.0


def test_friction_inputs_validated() -> None:
    with pytest.raises(ValueError):
        PistonCycleInputs(friction_multiplier=-0.1)
    with pytest.raises(ValueError):
        PistonCycleInputs(fuel_lhv_J_per_kg=0.0)
