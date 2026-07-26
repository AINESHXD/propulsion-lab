"""Valve timing, breathing and exhaust restriction.

The timing results are pure geometry and are asserted exactly. The breathing
results come from a reduced-order correlation, so they are asserted on
*behaviour* -- monotonicity, ordering, limits -- rather than on numbers that
would only be pinning a fit in place.
"""

from __future__ import annotations

import pytest

from app.engine_core.piston.geometry import CylinderGeometry
from app.engine_core.piston.valvetrain import (
    ValveGeometry,
    ValveTiming,
    breathing_report,
    effective_compression_ratio,
    effective_expansion_ratio,
    exhaust_back_pressure_Pa,
    mach_index,
    speed_of_sound_m_s,
    volumetric_efficiency_from_mach_index,
)

BORE = 0.086
STROKE = 0.086


def _geom(compression_ratio: float = 10.5) -> CylinderGeometry:
    return CylinderGeometry(
        bore_m=BORE, stroke_m=STROKE, compression_ratio=compression_ratio,
    )


def _four_valve() -> ValveGeometry:
    return ValveGeometry()


def _two_valve() -> ValveGeometry:
    return ValveGeometry(
        intake_valves_per_cylinder=1, exhaust_valves_per_cylinder=1,
        intake_valve_diameter_ratio=0.45, exhaust_valve_diameter_ratio=0.39,
    )


def _mean_piston_speed(rpm: float) -> float:
    return 2.0 * STROKE * rpm / 60.0


# ------------------------------------------------------------------ timing

def test_closing_the_intake_at_bdc_recovers_the_geometric_ratio() -> None:
    # With IVC exactly at BDC there is no spill-back, so effective == geometric.
    geom = _geom()
    r_eff = effective_compression_ratio(geom, ValveTiming(
        intake_close_abdc_deg=0.0,
    ).ivc_theta_deg)
    assert r_eff == pytest.approx(geom.compression_ratio, rel=1e-9)


def test_late_intake_close_lowers_the_effective_compression_ratio() -> None:
    # The Miller effect, straight out of the slider-crank volume.
    geom = _geom()
    ratios = [
        effective_compression_ratio(
            geom, ValveTiming(intake_close_abdc_deg=ivc).ivc_theta_deg,
        )
        for ivc in (0.0, 30.0, 60.0, 90.0)
    ]
    assert ratios == sorted(ratios, reverse=True)
    assert ratios[-1] < 0.75 * geom.compression_ratio


def test_early_exhaust_open_shortens_expansion_below_compression() -> None:
    # Opening the exhaust before BDC gives up part of the power stroke.
    geom = _geom()
    timing = ValveTiming(intake_close_abdc_deg=0.0, exhaust_open_bbdc_deg=60.0)
    r_exp = effective_expansion_ratio(geom, timing.evo_theta_deg)
    r_comp = effective_compression_ratio(geom, timing.ivc_theta_deg)
    assert r_exp < r_comp


def test_an_atkinson_cam_expands_more_than_it_compresses() -> None:
    # Very late intake close with a normal exhaust event: expansion ratio now
    # exceeds compression ratio, which is the defining Atkinson trait.
    geom = _geom()
    timing = ValveTiming(intake_close_abdc_deg=90.0, exhaust_open_bbdc_deg=40.0)
    assert (effective_expansion_ratio(geom, timing.evo_theta_deg)
            > effective_compression_ratio(geom, timing.ivc_theta_deg))


def test_valve_events_map_onto_the_solver_crank_axis() -> None:
    timing = ValveTiming(
        intake_open_btdc_deg=12.0, intake_close_abdc_deg=45.0,
        exhaust_open_bbdc_deg=50.0, exhaust_close_atdc_deg=8.0,
    )
    assert timing.ivc_theta_deg == pytest.approx(-135.0)
    assert timing.evo_theta_deg == pytest.approx(130.0)
    assert timing.closed_period_deg == pytest.approx(265.0)
    assert timing.valve_overlap_deg == pytest.approx(20.0)


def test_timing_that_leaves_no_closed_cycle_is_rejected() -> None:
    with pytest.raises(ValueError):
        ValveTiming(intake_close_abdc_deg=120.0, exhaust_open_bbdc_deg=120.0)


# --------------------------------------------------------------- breathing

def test_four_small_valves_out_flow_two_big_ones() -> None:
    # The whole argument for multi-valve heads: more curtain area for the same
    # bore, so a lower Mach index and better breathing at the same speed.
    assert _four_valve().intake_flow_area_m2(BORE) > _two_valve().intake_flow_area_m2(BORE)

    sp = _mean_piston_speed(7000)
    four = breathing_report(_geom(), ValveTiming(), _four_valve(), sp, 330.0, 1e5)
    two = breathing_report(_geom(), ValveTiming(), _two_valve(), sp, 330.0, 1e5)
    assert four["inlet_mach_index"] < two["inlet_mach_index"]
    assert four["volumetric_efficiency"] > two["volumetric_efficiency"]


def test_volumetric_efficiency_is_flat_then_falls_past_the_knee() -> None:
    # Below the knee the inlet is not the limit at all.
    assert volumetric_efficiency_from_mach_index(0.0) == pytest.approx(1.0)
    assert volumetric_efficiency_from_mach_index(0.4) == pytest.approx(1.0)
    # Past it, monotonically worse.
    high = [volumetric_efficiency_from_mach_index(z) for z in (0.6, 0.8, 1.0, 1.4)]
    assert high == sorted(high, reverse=True)
    assert high[0] < 1.0
    # And floored, so an absurd head still returns a solvable engine.
    assert volumetric_efficiency_from_mach_index(5.0) > 0.0


def test_breathing_degrades_monotonically_with_engine_speed() -> None:
    geom, timing, valves = _geom(), ValveTiming(), _two_valve()
    ve = [
        breathing_report(geom, timing, valves, _mean_piston_speed(rpm), 330.0, 1e5)[
            "volumetric_efficiency"
        ]
        for rpm in (2000, 5000, 8000, 11000)
    ]
    assert ve == sorted(ve, reverse=True)


def test_mach_index_rises_with_demand_and_falls_with_valve_area() -> None:
    base = mach_index(5.8e-3, 10.0, 6.0e-4, 360.0)
    assert mach_index(5.8e-3, 20.0, 6.0e-4, 360.0) > base     # faster piston
    assert mach_index(5.8e-3, 10.0, 1.2e-3, 360.0) < base     # bigger valve


def test_speed_of_sound_tracks_temperature() -> None:
    assert speed_of_sound_m_s(288.0) == pytest.approx(340.3, abs=1.0)
    assert speed_of_sound_m_s(900.0) > speed_of_sound_m_s(300.0)


# ----------------------------------------------------------- back pressure

def test_free_flowing_exhaust_sits_at_ambient() -> None:
    assert exhaust_back_pressure_Pa(1e5, 0.8, restriction=0.0) == pytest.approx(1e5)


def test_back_pressure_rises_with_speed_and_restriction() -> None:
    assert exhaust_back_pressure_Pa(1e5, 1.0, 1.0) > exhaust_back_pressure_Pa(1e5, 0.5, 1.0)
    assert exhaust_back_pressure_Pa(1e5, 1.0, 2.0) > exhaust_back_pressure_Pa(1e5, 1.0, 1.0)
    assert exhaust_back_pressure_Pa(1e5, 1.0, 1.0) > 1e5


def test_breathing_report_carries_everything_the_solver_needs() -> None:
    report = breathing_report(
        _geom(), ValveTiming(), _four_valve(), _mean_piston_speed(3000), 330.0, 1e5,
    )
    for key in ("inlet_mach_index", "exhaust_mach_index", "volumetric_efficiency",
                "exhaust_pressure_Pa", "effective_compression_ratio",
                "effective_expansion_ratio", "valve_overlap_deg",
                "ivc_theta_deg", "evo_theta_deg", "closed_period_deg",
                "breathing_verdict"):
        assert key in report
    assert report["exhaust_pressure_Pa"] >= 1e5
    assert 0.0 < report["volumetric_efficiency"] <= 1.0


def test_a_normal_cam_does_not_get_called_a_miller_cycle() -> None:
    # Every cam closes the intake a little after BDC; that is not news.
    normal = breathing_report(
        _geom(), ValveTiming(), _four_valve(), _mean_piston_speed(3000), 330.0, 1e5,
    )
    assert "Miller" not in normal["breathing_verdict"]
    assert "effective compression ratio" not in normal["breathing_verdict"]
    # A genuinely late-closing cam does get flagged.
    miller = breathing_report(
        _geom(), ValveTiming(intake_close_abdc_deg=90.0), _four_valve(),
        _mean_piston_speed(3000), 330.0, 1e5,
    )
    assert "effective compression ratio" in miller["breathing_verdict"]


# ------------------------------------------------------------- validation

@pytest.mark.parametrize("kwargs", [
    {"intake_valves_per_cylinder": 0},
    {"exhaust_valves_per_cylinder": 9},
    {"intake_valve_diameter_ratio": 0.05},
    {"exhaust_valve_diameter_ratio": 0.95},
    {"max_lift_ratio": 0.005},
    {"discharge_coefficient": 1.5},
    {"exhaust_restriction": -1.0},
])
def test_invalid_valve_geometry_is_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        ValveGeometry(**kwargs)


def test_invalid_valve_timing_is_rejected() -> None:
    with pytest.raises(ValueError):
        ValveTiming(intake_close_abdc_deg=300.0)
