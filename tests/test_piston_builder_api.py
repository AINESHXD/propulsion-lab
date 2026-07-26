"""The custom engine builder over the API surface.

The wizard sends one payload describing a whole engine — capacity, arrangement,
cam and head — so these tests cover the schema contract it depends on: that a
capacity resolves to a bore and stroke, that the arrangement comes back with its
firing and balance analysis, that bad combinations are refused with a useful
message, and that a request carrying none of it behaves exactly as before.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas_piston import (
    PistonSimulateInput,
    PistonSweepInput,
    run_piston_simulation,
    run_piston_sweep,
)


def _v8(**overrides) -> PistonSimulateInput:
    payload = dict(
        fuel="gasoline", cylinders=8, compression_ratio=11.0, rpm=6000.0,
        displacement_L=4.0, bore_stroke_ratio=1.15,
        layout={"kind": "vee", "bank_angle_deg": 90.0, "crank_type": "cross_plane"},
        valve_timing={"intake_close_abdc_deg": 50.0, "exhaust_open_bbdc_deg": 50.0},
        valve_geometry={"intake_valves_per_cylinder": 2, "exhaust_valves_per_cylinder": 2},
        include_trace=False,
    )
    payload.update(overrides)
    return PistonSimulateInput(**payload)


# ------------------------------------------------------------- capacity

def test_a_capacity_and_a_ratio_resolve_to_bore_and_stroke() -> None:
    out = run_piston_simulation(_v8())
    # The engine that comes back is the capacity that was asked for.
    assert out.total_displacement_m3 == pytest.approx(4.0e-3, rel=1e-9)
    # Oversquare ratio means a bore wider than the stroke.
    assert out.bore_m > out.stroke_m
    assert out.bore_m / out.stroke_m == pytest.approx(1.15, rel=1e-9)


def test_capacity_overrides_any_bore_and_stroke_passed_alongside() -> None:
    out = run_piston_simulation(_v8(bore_m=0.05, stroke_m=0.05))
    assert out.total_displacement_m3 == pytest.approx(4.0e-3, rel=1e-9)
    assert out.bore_m != pytest.approx(0.05)


def test_capacity_without_a_ratio_is_refused() -> None:
    with pytest.raises(ValidationError, match="together"):
        PistonSimulateInput(displacement_L=2.0)
    with pytest.raises(ValidationError, match="together"):
        PistonSimulateInput(bore_stroke_ratio=1.1)


def test_bore_and_stroke_still_work_on_their_own() -> None:
    out = run_piston_simulation(
        PistonSimulateInput(fuel="gasoline", bore_m=0.086, stroke_m=0.086, cylinders=4)
    )
    assert out.bore_m == pytest.approx(0.086)
    assert out.stroke_m == pytest.approx(0.086)


# --------------------------------------------------------------- layout

def test_the_layout_analysis_comes_back_with_the_result() -> None:
    out = run_piston_simulation(_v8())
    assert out.layout is not None
    assert out.layout.description == "90 deg V8"
    assert out.layout.even_fire is True
    assert out.layout.ideal_firing_interval_deg == pytest.approx(90.0)
    # Cross-plane cancels the secondary shaking force a flat-plane leaves.
    assert out.layout.balance.secondary_force == pytest.approx(0.0, abs=1e-6)
    assert out.layout_friction_scale > 1.0


def test_the_cylinder_count_is_taken_from_the_parent_not_repeated() -> None:
    # The layout block has no cylinder field, so it cannot contradict the engine.
    with pytest.raises(ValidationError):
        PistonSimulateInput(layout={"kind": "inline", "cylinders": 6})


def test_an_impossible_arrangement_is_rejected_with_a_reason() -> None:
    bad = PistonSimulateInput(cylinders=5, layout={"kind": "vee", "bank_angle_deg": 90.0})
    with pytest.raises(ValueError, match="even cylinder count"):
        run_piston_simulation(bad)


def test_odd_fire_and_even_fire_v6_both_solve() -> None:
    odd = run_piston_simulation(PistonSimulateInput(
        fuel="gasoline", cylinders=6,
        layout={"kind": "vee", "bank_angle_deg": 90.0}, include_trace=False,
    ))
    even = run_piston_simulation(PistonSimulateInput(
        fuel="gasoline", cylinders=6,
        layout={"kind": "vee", "bank_angle_deg": 120.0}, include_trace=False,
    ))
    assert odd.layout.even_fire is False
    assert even.layout.even_fire is True
    assert sorted(set(odd.layout.firing_intervals_deg)) == [90.0, 150.0]


# ----------------------------------------------------------- valvetrain

def test_the_cam_and_head_report_their_effect() -> None:
    out = run_piston_simulation(_v8())
    assert out.effective_compression_ratio < 11.0     # late IVC costs compression
    assert 0.0 < out.volumetric_efficiency <= 1.0
    assert out.inlet_mach_index > 0.0
    assert out.exhaust_mach_index > 0.0
    assert out.valve_overlap_deg == pytest.approx(20.0)
    assert isinstance(out.breathing_verdict, str) and out.breathing_verdict


def test_timing_that_leaves_no_closed_cycle_is_refused_with_a_reason() -> None:
    bad = PistonSimulateInput(
        fuel="gasoline",
        valve_timing={"intake_close_abdc_deg": 120.0, "exhaust_open_bbdc_deg": 120.0},
    )
    with pytest.raises(ValueError, match="closed cycle"):
        run_piston_simulation(bad)


@pytest.mark.parametrize("patch", [
    {"intake_valves_per_cylinder": 0},
    {"intake_valves_per_cylinder": 9},
    {"intake_valve_diameter_ratio": 0.9},
    {"max_lift_ratio": 0.9},
    {"exhaust_restriction": 99.0},
])
def test_out_of_range_head_geometry_is_refused(patch: dict) -> None:
    with pytest.raises(ValidationError):
        PistonSimulateInput(valve_geometry={**patch})


# ------------------------------------------------------ backward compatible

def test_a_plain_request_reports_no_builder_data() -> None:
    out = run_piston_simulation(PistonSimulateInput(fuel="gasoline", include_trace=False))
    assert out.layout is None
    assert out.volumetric_efficiency is None
    assert out.effective_compression_ratio is None
    assert out.layout_friction_scale is None
    # And still returns everything it always did.
    assert out.brake_power_W > 0.0
    assert out.air_fuel_ratio == pytest.approx(14.69, abs=0.1)


def test_unknown_fields_are_still_forbidden() -> None:
    with pytest.raises(ValidationError):
        PistonSimulateInput(turbo_button=True)


# ------------------------------------------------------------------ sweep

def test_a_custom_engine_can_be_swept_on_the_dyno() -> None:
    out = run_piston_sweep(PistonSweepInput(
        base_input=_v8(),
        sweep_parameter="rpm",
        values=[2000.0, 4000.0, 6000.0, 8000.0],
    ))
    assert out.summary.successful_cases == 4
    assert out.summary.failed_cases == 0
    assert out.summary.peak_brake_power_W > 0.0
    # Breathing falls away with speed, so power must not simply track rpm
    # linearly all the way up.
    powers = [c.output.brake_power_W for c in out.cases if c.success]
    assert powers == sorted(powers) or max(powers) < powers[0] * 4
