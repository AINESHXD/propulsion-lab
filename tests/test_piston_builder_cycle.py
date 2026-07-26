"""The custom-engine inputs, end to end through the cycle solver.

Two things are being protected here. First, that supplying none of the new
inputs leaves the solver behaving exactly as it did — the builder is additive,
not a rewrite. Second, that when the inputs *are* supplied they move the answer
in the direction the physics says they should, and that the first law still
closes while they do it.
"""

from __future__ import annotations

import pytest

from app.engine_core.piston.cycle import PistonCycleInputs, simulate_piston_cycle
from app.engine_core.piston.layout import EngineLayout
from app.engine_core.piston.valvetrain import ValveGeometry, ValveTiming

BASE = dict(fuel="gasoline", equivalence_ratio=1.0, compression_ratio=10.5, rpm=5000.0)


def _run(**kwargs):
    return simulate_piston_cycle(PistonCycleInputs(**{**BASE, **kwargs}))


def _four_valve(**kwargs) -> ValveGeometry:
    return ValveGeometry(**kwargs)


def _two_valve(**kwargs) -> ValveGeometry:
    return ValveGeometry(
        intake_valves_per_cylinder=1, exhaust_valves_per_cylinder=1,
        intake_valve_diameter_ratio=0.45, exhaust_valve_diameter_ratio=0.39,
        **kwargs,
    )


# ------------------------------------------------------- backward compatible

def test_without_builder_inputs_the_extras_stay_absent() -> None:
    r = _run()
    assert r.layout is None
    assert r.volumetric_efficiency is None
    assert r.effective_compression_ratio is None
    assert r.inlet_mach_index is None
    assert r.layout_friction_scale is None


def test_a_layout_alone_does_not_touch_the_thermodynamics() -> None:
    # Arrangement changes friction, not the gas cycle: every cylinder still
    # runs the same crank-angle solve.
    plain = _run()
    with_layout = _run(layout=EngineLayout(kind="inline", cylinders=4))
    assert with_layout.imep_Pa == pytest.approx(plain.imep_Pa, rel=1e-12)
    assert with_layout.peak_pressure_Pa == pytest.approx(plain.peak_pressure_Pa, rel=1e-12)
    # An inline-four is the friction reference, so brake is untouched too.
    assert with_layout.layout_friction_scale == pytest.approx(1.0, abs=1e-9)
    assert with_layout.brake_power_W == pytest.approx(plain.brake_power_W, rel=1e-9)


# -------------------------------------------------------------- valve timing

def test_valve_timing_moves_the_integration_window_off_bdc() -> None:
    timing = ValveTiming(intake_close_abdc_deg=45.0, exhaust_open_bbdc_deg=50.0)
    r = _run(valve_timing=timing)
    assert r.closed_period_deg == pytest.approx(265.0)
    assert r.valve_overlap_deg == pytest.approx(20.0)
    # Charge is trapped after BDC, so the ratio that does work is below geometric.
    assert r.effective_compression_ratio < 10.5


def test_a_miller_cam_trades_power_for_a_lower_effective_ratio() -> None:
    normal = _run(valve_timing=ValveTiming())
    miller = _run(valve_timing=ValveTiming(intake_close_abdc_deg=90.0))
    assert miller.effective_compression_ratio < normal.effective_compression_ratio
    assert miller.brake_power_W < normal.brake_power_W
    # Expansion is untouched by intake timing, so the cycle now expands further
    # than it compressed -- the Atkinson trait.
    assert miller.effective_expansion_ratio > miller.effective_compression_ratio


def test_the_first_law_still_closes_with_every_builder_input_on() -> None:
    r = _run(
        cylinders=8,
        layout=EngineLayout(kind="vee", cylinders=8, bank_angle_deg=90),
        valve_timing=ValveTiming(intake_close_abdc_deg=55.0),
        valve_geometry=_four_valve(exhaust_restriction=2.0),
    )
    # Residual is heat_in - (work + wall loss + dU); it must stay at round-off.
    assert abs(r.energy_residual_J) < 1e-6
    assert r.brake_power_W > 0.0


# ----------------------------------------------------------------- breathing

def test_four_valves_beat_two_at_speed() -> None:
    timing = ValveTiming()
    four = _run(rpm=8000.0, valve_timing=timing, valve_geometry=_four_valve())
    two = _run(rpm=8000.0, valve_timing=timing, valve_geometry=_two_valve())
    assert four.volumetric_efficiency > two.volumetric_efficiency
    assert four.inlet_mach_index < two.inlet_mach_index
    assert four.brake_power_W > two.brake_power_W


def test_breathing_falls_away_as_the_engine_revs() -> None:
    ve = [
        _run(rpm=rpm, valve_timing=ValveTiming(), valve_geometry=_two_valve()).volumetric_efficiency
        for rpm in (2000.0, 5000.0, 8000.0, 11000.0)
    ]
    assert ve == sorted(ve, reverse=True)
    assert ve[-1] < ve[0]


def test_a_choked_inlet_traps_less_charge() -> None:
    timing = ValveTiming()
    open_head = _run(rpm=9000.0, valve_timing=timing, valve_geometry=_four_valve())
    choked = _run(rpm=9000.0, valve_timing=timing, valve_geometry=_two_valve())
    assert choked.trapped_mass_kg < open_head.trapped_mass_kg


# ------------------------------------------------------------ exhaust side

def test_a_restrictive_exhaust_costs_pumping_work_and_power() -> None:
    timing = ValveTiming()
    free = _run(valve_timing=timing, valve_geometry=_four_valve(exhaust_restriction=0.0))
    blocked = _run(valve_timing=timing, valve_geometry=_four_valve(exhaust_restriction=4.0))
    assert blocked.pmep_Pa > free.pmep_Pa
    assert blocked.brake_power_W < free.brake_power_W
    # A free-flowing system at ambient leaves no pumping penalty from the exhaust.
    assert free.pmep_Pa == pytest.approx(0.0, abs=1e-6)


# -------------------------------------------------------------- layout knock-on

def test_more_bearings_and_heads_cost_more_friction() -> None:
    i4 = _run(layout=EngineLayout(kind="inline", cylinders=4))
    v8 = _run(cylinders=8, layout=EngineLayout(kind="vee", cylinders=8, bank_angle_deg=90))
    assert v8.fmep_Pa > i4.fmep_Pa
    assert v8.layout_friction_scale > i4.layout_friction_scale


def test_the_layout_report_rides_along_with_the_result() -> None:
    r = _run(cylinders=6, layout=EngineLayout(kind="inline", cylinders=6))
    assert r.layout["description"] == "inline-6"
    assert r.layout["even_fire"] is True
    assert r.layout["main_bearings"] == 7
    assert "balanced" in r.layout["balance_verdict"].lower()


def test_layout_and_cycle_must_agree_on_the_cylinder_count() -> None:
    with pytest.raises(ValueError, match="cylinders"):
        PistonCycleInputs(cylinders=4, layout=EngineLayout(kind="vee", cylinders=8,
                                                           bank_angle_deg=90))


def test_layout_and_cycle_must_agree_on_strokes_per_cycle() -> None:
    with pytest.raises(ValueError, match="strokes"):
        PistonCycleInputs(
            cylinders=4, strokes_per_cycle=2,
            layout=EngineLayout(kind="inline", cylinders=4, strokes_per_cycle=4),
        )


# ----------------------------------------------------------------- reporting

def test_to_dict_carries_every_builder_field() -> None:
    payload = _run(
        cylinders=6,
        layout=EngineLayout(kind="flat", cylinders=6),
        valve_timing=ValveTiming(),
        valve_geometry=_four_valve(),
    ).to_dict()
    for key in ("effective_compression_ratio", "effective_expansion_ratio",
                "volumetric_efficiency", "inlet_mach_index", "exhaust_mach_index",
                "valve_overlap_deg", "closed_period_deg", "breathing_verdict",
                "layout", "layout_friction_scale"):
        assert key in payload, key
    assert payload["layout"]["description"] == "flat-6"
    assert isinstance(payload["breathing_verdict"], str)
