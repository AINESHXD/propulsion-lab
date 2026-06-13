"""PistonLab crank-angle cycle solver — geometry, Wiebe, first-law integrator.

These are the Day 1-2 physics tests: the slider-crank geometry, the Wiebe
finite heat-release law, and the crank-angle first-law integrator that turns
the textbook air-standard toy into a credible engine cycle. Python is the
source of truth; the console mirrors it.
"""

from __future__ import annotations

import math

import pytest

from app.engine_core.piston import (
    CylinderGeometry,
    PistonCycleInputs,
    clearance_volume,
    cylinder_volume,
    displacement_volume,
    simulate_piston_cycle,
    wiebe_burn_fraction,
    wiebe_burn_rate,
)

_DEG = math.pi / 180.0


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def test_volume_at_tdc_and_bdc_match_compression_ratio() -> None:
    g = CylinderGeometry(bore_m=0.086, stroke_m=0.086, compression_ratio=10.5)
    v_tdc = cylinder_volume(0.0, g)
    v_bdc = cylinder_volume(180.0 * _DEG, g)
    assert v_tdc == pytest.approx(g.volume_min_m3, rel=1e-9)
    assert v_bdc == pytest.approx(g.volume_max_m3, rel=1e-9)
    # The TDC/BDC volume ratio IS the compression ratio.
    assert v_bdc / v_tdc == pytest.approx(10.5, rel=1e-6)


def test_displacement_and_clearance_volumes() -> None:
    bore, stroke, r = 0.086, 0.086, 10.5
    vd = displacement_volume(bore, stroke)
    assert vd == pytest.approx(0.25 * math.pi * bore**2 * stroke, rel=1e-12)
    vc = clearance_volume(vd, r)
    assert vc == pytest.approx(vd / (r - 1.0), rel=1e-12)
    # Volume is symmetric about TDC (slider-crank depends on |theta|).
    g = CylinderGeometry(bore_m=bore, stroke_m=stroke, compression_ratio=r)
    assert cylinder_volume(40.0 * _DEG, g) == pytest.approx(
        cylinder_volume(-40.0 * _DEG, g), rel=1e-12
    )


def test_geometry_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError):
        CylinderGeometry(bore_m=0.08, stroke_m=0.08, compression_ratio=1.0)
    with pytest.raises(ValueError):
        CylinderGeometry(bore_m=0.08, stroke_m=0.08, compression_ratio=10.0, rod_ratio=0.9)
    with pytest.raises(ValueError):
        CylinderGeometry(bore_m=-1.0, stroke_m=0.08, compression_ratio=10.0)


# ---------------------------------------------------------------------------
# Wiebe heat release
# ---------------------------------------------------------------------------


def test_wiebe_bounds_and_monotonic() -> None:
    start, dur = -15.0, 50.0
    assert wiebe_burn_fraction(-20.0, start, dur) == 0.0          # before SOC
    end_val = wiebe_burn_fraction(start + dur, start, dur, a=5.0)
    assert end_val == pytest.approx(1.0 - math.exp(-5.0), abs=1e-6)  # ~0.9933
    # Monotonically increasing through the burn.
    prev = -1.0
    for th in range(-15, 36, 5):
        x = wiebe_burn_fraction(float(th), start, dur)
        assert x >= prev
        prev = x


def test_wiebe_rate_integrates_to_fraction() -> None:
    start, dur, a, m = -15.0, 50.0, 5.0, 2.0
    # Trapezoidal integral of the rate over the burn window.
    n = 5000
    total = 0.0
    th0 = start
    r0 = wiebe_burn_rate(th0, start, dur, a, m)
    for k in range(1, n + 1):
        th1 = start + dur * k / n
        r1 = wiebe_burn_rate(th1, start, dur, a, m)
        total += 0.5 * (r0 + r1) * (th1 - th0)
        th0, r0 = th1, r1
    assert total == pytest.approx(
        wiebe_burn_fraction(start + dur, start, dur, a, m), abs=1e-3
    )


def test_wiebe_rate_zero_outside_window() -> None:
    assert wiebe_burn_rate(-30.0, -15.0, 50.0) == 0.0
    assert wiebe_burn_rate(60.0, -15.0, 50.0) == 0.0


# ---------------------------------------------------------------------------
# Crank-angle first-law cycle
# ---------------------------------------------------------------------------


def test_energy_closes_to_machine_precision() -> None:
    r = simulate_piston_cycle(PistonCycleInputs())
    # Indicated work == heat released - delta(internal energy): residual ~ 0.
    assert abs(r.energy_residual_J) < 1e-6
    assert abs(r.energy_residual_J) < 1e-6 * max(1.0, r.indicated_work_J)


def test_motored_cycle_returns_to_start() -> None:
    # No combustion and no wall loss: reversible adiabatic compression then
    # expansion must return to the start state and do ~zero net work.
    r = simulate_piston_cycle(PistonCycleInputs(
        heat_release_J_per_kg=0.0, wall_heat_transfer_multiplier=0.0))
    t0, t1 = r.trace[0], r.trace[-1]
    assert t1["temperature_K"] == pytest.approx(t0["temperature_K"], rel=1e-3)
    assert t1["pressure_Pa"] == pytest.approx(t0["pressure_Pa"], rel=1e-3)
    assert abs(r.indicated_work_J) < 1e-2          # ~0 J net
    assert r.thermal_efficiency == 0.0             # no heat in


def test_finite_burn_sits_below_air_standard_ceiling() -> None:
    # Spreading heat release over real crank angle costs efficiency relative to
    # the instantaneous-heat air-standard ideal.
    r = simulate_piston_cycle(PistonCycleInputs())
    assert 0.0 < r.thermal_efficiency < r.air_standard_efficiency


def test_higher_compression_ratio_is_more_efficient() -> None:
    lo = simulate_piston_cycle(PistonCycleInputs(compression_ratio=8.0))
    hi = simulate_piston_cycle(PistonCycleInputs(compression_ratio=13.0))
    assert hi.thermal_efficiency > lo.thermal_efficiency
    assert hi.air_standard_efficiency > lo.air_standard_efficiency


def test_power_torque_consistency() -> None:
    inp = PistonCycleInputs(rpm=3600.0)
    r = simulate_piston_cycle(inp)
    omega = 2.0 * math.pi * inp.rpm / 60.0
    assert r.indicated_power_W == pytest.approx(r.indicated_torque_Nm * omega, rel=1e-9)


def test_imep_equals_work_over_displacement() -> None:
    inp = PistonCycleInputs()
    r = simulate_piston_cycle(inp)
    vd = displacement_volume(inp.bore_m, inp.stroke_m)
    assert r.imep_Pa * vd == pytest.approx(r.indicated_work_J, rel=1e-9)


def test_firing_cycle_raises_peak_pressure_and_does_positive_work() -> None:
    inp = PistonCycleInputs()
    r = simulate_piston_cycle(inp)
    assert r.indicated_work_J > 0.0
    assert r.peak_pressure_Pa > 20.0 * inp.intake_pressure_Pa     # combustion spike
    assert r.peak_temperature_K > inp.intake_temperature_K


def test_more_heat_release_does_more_work() -> None:
    lean = simulate_piston_cycle(PistonCycleInputs(heat_release_J_per_kg=1.5e6))
    rich = simulate_piston_cycle(PistonCycleInputs(heat_release_J_per_kg=3.0e6))
    assert rich.indicated_work_J > lean.indicated_work_J
    assert rich.peak_pressure_Pa > lean.peak_pressure_Pa


def test_cycle_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError):
        PistonCycleInputs(strokes_per_cycle=3)
    with pytest.raises(ValueError):
        PistonCycleInputs(gamma=1.0)
    with pytest.raises(ValueError):
        PistonCycleInputs(rpm=0.0)
    with pytest.raises(ValueError):
        PistonCycleInputs(compression_ratio=1.0)


def test_two_stroke_makes_more_power_than_four_stroke_same_point() -> None:
    # A 2-stroke fires every revolution, so for the same indicated work per
    # cycle it makes ~twice the power of a 4-stroke at the same rpm.
    four = simulate_piston_cycle(PistonCycleInputs(strokes_per_cycle=4))
    two = simulate_piston_cycle(PistonCycleInputs(strokes_per_cycle=2))
    assert two.indicated_power_W == pytest.approx(2.0 * four.indicated_power_W, rel=1e-6)


def test_trace_is_a_closed_pv_loop() -> None:
    r = simulate_piston_cycle(PistonCycleInputs())
    assert len(r.trace) > 50
    # Starts and ends at the same volume (BDC -> BDC).
    assert r.trace[-1]["volume_m3"] == pytest.approx(r.trace[0]["volume_m3"], rel=1e-6)
    # Every sampled pressure and volume is positive.
    assert all(p["pressure_Pa"] > 0 and p["volume_m3"] > 0 for p in r.trace)
