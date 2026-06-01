"""Validation tests for the mission-profile schema (Day 15).

Day 15 is schema-only: a representative mission JSON must validate, and the
field bounds must reject malformed input. The integrator that flies the
profile arrives in Day 16.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    MissionProfileInput,
    MissionSegmentInput,
    TurbofanMissionInput,
    TurbojetMissionInput,
)


# A realistic narrowbody-style climb / cruise / descent profile.
_SAMPLE = {
    "name": "Short-haul cruise",
    "segments": [
        {"name": "climb", "altitude_m": 6000.0, "mach": 0.55, "throttle_K": 1500.0, "duration_s": 600.0},
        {"name": "cruise", "altitude_m": 10600.0, "mach": 0.80, "throttle_K": 1420.0, "duration_s": 5400.0},
        {"name": "descent", "altitude_m": 3000.0, "mach": 0.50, "throttle_K": 1200.0, "duration_s": 900.0},
    ],
}


def test_sample_mission_profile_validates() -> None:
    profile = MissionProfileInput.model_validate(_SAMPLE)
    assert profile.name == "Short-haul cruise"
    assert len(profile.segments) == 3
    assert profile.segments[1].name == "cruise"
    assert profile.segments[1].altitude_m == pytest.approx(10600.0)


def test_segment_defaults_fill_in() -> None:
    seg = MissionSegmentInput()
    assert seg.altitude_m == 10000.0
    assert seg.duration_s > 0.0
    assert seg.name is None


def test_turbojet_mission_input_validates_with_design() -> None:
    payload = TurbojetMissionInput.model_validate(
        {"design": {"compressor_pressure_ratio": 16.0}, "profile": _SAMPLE}
    )
    assert payload.design.compressor_pressure_ratio == 16.0
    assert len(payload.profile.segments) == 3


def test_turbofan_mission_input_defaults_design() -> None:
    payload = TurbofanMissionInput.model_validate({"profile": _SAMPLE})
    assert payload.design.bypass_ratio == 5.0  # turbofan default


def test_empty_segment_list_rejected() -> None:
    with pytest.raises(ValidationError):
        MissionProfileInput.model_validate({"segments": []})


def test_non_positive_duration_rejected() -> None:
    with pytest.raises(ValidationError):
        MissionSegmentInput.model_validate({"duration_s": 0.0})


def test_out_of_range_throttle_rejected() -> None:
    with pytest.raises(ValidationError):
        MissionSegmentInput.model_validate({"throttle_K": 250.0})


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        MissionSegmentInput.model_validate(
            {"altitude_m": 10000.0, "thrust_request_N": 50000.0}
        )


# ---------------------------------------------------------------------------
# Day 16 — mission integrator (engine-core)
# ---------------------------------------------------------------------------

from app.engine_core.mission import (  # noqa: E402
    MissionLeg,
    fly_turbofan_mission,
    fly_turbojet_mission,
)
from app.engine_core.turbofan import TurbofanCycleInputs  # noqa: E402
from app.engine_core.types import TurbojetCycleInputs  # noqa: E402
from app.main import mission_turbofan, mission_turbojet  # noqa: E402


def _turbojet_legs() -> list[MissionLeg]:
    return [
        MissionLeg(altitude_m=6000.0, mach=0.55, throttle_K=1450.0, duration_s=600.0, name="climb"),
        MissionLeg(altitude_m=10000.0, mach=0.80, throttle_K=1400.0, duration_s=3600.0, name="cruise"),
        MissionLeg(altitude_m=3000.0, mach=0.50, throttle_K=1300.0, duration_s=900.0, name="descent"),
    ]


def test_fly_turbojet_mission_accumulates_fuel_and_time() -> None:
    out = fly_turbojet_mission(
        TurbojetCycleInputs(turbine_inlet_temperature_K=1500.0), _turbojet_legs(), name="Test"
    )
    assert out["successful_segments"] == 3
    assert out["failed_segments"] == 0
    assert out["total_time_s"] == pytest.approx(600 + 3600 + 900)
    assert out["total_fuel_kg"] > 0.0

    # Per-segment fuel sums to the total; cumulative series is non-decreasing.
    segs = out["segments"]
    assert sum(s["fuel_burned_kg"] for s in segs) == pytest.approx(out["total_fuel_kg"])
    cum = [s["cumulative_fuel_kg"] for s in segs]
    assert cum == sorted(cum)
    times = [s["cumulative_time_s"] for s in segs]
    assert times == sorted(times)
    assert times[-1] == pytest.approx(out["total_time_s"])


def test_default_cruise_mission_returns_sensible_fuel() -> None:
    """Day 16 acceptance — a one-hour turbofan cruise burns a physically
    plausible amount of fuel (hundreds to a few thousand kg)."""

    legs = [MissionLeg(altitude_m=10000.0, mach=0.78, throttle_K=1550.0, duration_s=3600.0, name="cruise")]
    out = fly_turbofan_mission(TurbofanCycleInputs(), legs, name="Cruise")
    assert out["successful_segments"] == 1
    cruise = out["segments"][0]
    # fuel_burned == fuel_flow * duration, and fuel_flow back-computed from TSFC*thrust.
    assert cruise["fuel_burned_kg"] == pytest.approx(out["total_fuel_kg"])
    # Sensible magnitude for a single-engine 1-hour cruise.
    assert 300.0 < out["total_fuel_kg"] < 8000.0


def test_mission_failed_leg_is_captured_and_time_advances() -> None:
    """A leg that cannot be matched (throttle below the ram inlet temperature)
    is flagged as failed; time still advances and later legs still fly."""

    legs = [
        MissionLeg(altitude_m=10000.0, mach=0.8, throttle_K=1400.0, duration_s=600.0, name="ok"),
        MissionLeg(altitude_m=0.0, mach=2.5, throttle_K=800.0, duration_s=300.0, name="bad"),
        MissionLeg(altitude_m=10000.0, mach=0.8, throttle_K=1350.0, duration_s=600.0, name="ok2"),
    ]
    out = fly_turbojet_mission(TurbojetCycleInputs(turbine_inlet_temperature_K=1500.0), legs)
    assert out["failed_segments"] == 1
    assert out["successful_segments"] == 2
    bad = out["segments"][1]
    assert bad["success"] is False and bad["error"]
    assert bad["fuel_burned_kg"] is None
    # Total time counts every leg regardless of match success.
    assert out["total_time_s"] == pytest.approx(600 + 300 + 600)


# ---------------------------------------------------------------------------
# Day 16 — mission API endpoints
# ---------------------------------------------------------------------------


def test_mission_turbojet_endpoint() -> None:
    out = mission_turbojet(
        TurbojetMissionInput.model_validate(
            {"design": {"turbine_inlet_temperature_K": 1500.0}, "profile": _SAMPLE}
        )
    )
    assert out.engine_type == "turbojet"
    assert out.name == "Short-haul cruise"
    assert out.successful_segments >= 1
    assert out.total_fuel_kg is not None and out.total_fuel_kg > 0.0


def test_mission_turbofan_endpoint() -> None:
    out = mission_turbofan(TurbofanMissionInput.model_validate({"profile": _SAMPLE}))
    assert out.engine_type == "turbofan"
    assert out.total_time_s == pytest.approx(600 + 5400 + 900)
    assert out.total_fuel_kg is not None and out.total_fuel_kg > 0.0


# ---------------------------------------------------------------------------
# Day 20 — cross-check the integrator against the off-design solver directly
# ---------------------------------------------------------------------------

from app.engine_core.off_design import (  # noqa: E402
    calibrate_turbojet_reference,
    solve_turbojet_off_design,
)


def test_mission_all_legs_fail_is_graceful() -> None:
    """Edge case (Day 21) — if every leg is unmatched, the mission returns zero
    fuel with all legs failed and time still fully advanced (no crash)."""

    design = TurbojetCycleInputs(turbine_inlet_temperature_K=1500.0)
    # Mach 2.5 / sea level / throttle below the ram inlet temperature -> unmatched.
    legs = [MissionLeg(0.0, 2.5, 800.0, 300.0, "a"), MissionLeg(0.0, 2.5, 800.0, 300.0, "b")]
    out = fly_turbojet_mission(design, legs)
    assert out["successful_segments"] == 0
    assert out["failed_segments"] == 2
    assert out["total_fuel_kg"] == 0.0
    assert out["total_time_s"] == pytest.approx(600.0)
    assert all(s["fuel_burned_kg"] is None for s in out["segments"])


def test_mission_single_leg_fuel_equals_off_design_fuel_flow_times_duration() -> None:
    """A one-leg mission's fuel must equal the matched fuel flow × duration."""

    design = TurbojetCycleInputs(turbine_inlet_temperature_K=1500.0)
    ref = calibrate_turbojet_reference(design)
    point = solve_turbojet_off_design(
        ref, altitude_m=10000.0, mach=0.8, turbine_inlet_temperature_K=1400.0
    )
    duration_s = 1800.0
    out = fly_turbojet_mission(
        design, [MissionLeg(10000.0, 0.8, 1400.0, duration_s, "cruise")]
    )
    assert out["total_fuel_kg"] == pytest.approx(
        point["fuel_flow_kg_s"] * duration_s, rel=1e-9
    )
