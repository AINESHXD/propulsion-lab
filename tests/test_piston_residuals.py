"""Residual gas trapped in the clearance volume, and what overlap does to it.

The piston cannot sweep the clearance volume, so burned gas from the last cycle
is still there when the intake shuts. It is hot, so it raises the charge
temperature, and it is already burned, so it dilutes. Valve overlap connects the
intake and exhaust while both are open, which turns the pressure ratio across
them into either scavenging or backflow — and that is the whole reason a big-cam
engine idles badly but pulls hard under boost.
"""

from __future__ import annotations

import pytest

from app.engine_core.piston.cycle import PistonCycleInputs, simulate_piston_cycle
from app.engine_core.piston.valvetrain import (
    ValveGeometry,
    ValveTiming,
    residual_gas_mass_kg,
    trapped_charge_split,
)

# A 12 deg and a 70 deg overlap cam, everything else equal.
MILD = ValveTiming(intake_open_btdc_deg=6.0, exhaust_close_atdc_deg=6.0)
WILD = ValveTiming(intake_open_btdc_deg=35.0, exhaust_close_atdc_deg=35.0)

_CLEARANCE = 5.0e-5      # m^3
_IVC_VOLUME = 5.0e-4     # m^3


def _run(**kwargs):
    base = dict(fuel="gasoline")
    base.update(kwargs)
    return simulate_piston_cycle(PistonCycleInputs(**base))


# ------------------------------------------------------------ residual mass

def test_residual_mass_is_the_clearance_volume_at_exhaust_conditions() -> None:
    # With no overlap and no pressure difference it is simply the ideal-gas
    # mass sitting in the clearance volume.
    m = residual_gas_mass_kg(
        clearance_volume_m3=_CLEARANCE, exhaust_pressure_Pa=1.0e5,
        exhaust_temperature_K=1200.0, intake_pressure_Pa=1.0e5,
        valve_overlap_deg=0.0,
    )
    assert m == pytest.approx(1.0e5 * _CLEARANCE / (287.0 * 1200.0), rel=1e-9)


def test_a_hotter_exhaust_leaves_less_residual_mass() -> None:
    hot = residual_gas_mass_kg(_CLEARANCE, 1.0e5, 1500.0, 1.0e5, 0.0)
    cool = residual_gas_mass_kg(_CLEARANCE, 1.0e5, 900.0, 1.0e5, 0.0)
    assert hot < cool          # same volume, lower density


def test_overlap_does_nothing_without_a_pressure_difference() -> None:
    # Both valves open onto the same pressure: nothing is driven either way.
    none = residual_gas_mass_kg(_CLEARANCE, 1.0e5, 1200.0, 1.0e5, 0.0)
    lots = residual_gas_mass_kg(_CLEARANCE, 1.0e5, 1200.0, 1.0e5, 80.0)
    assert none == pytest.approx(lots)


def test_boost_plus_overlap_scavenges_the_residual_out() -> None:
    no_overlap = residual_gas_mass_kg(_CLEARANCE, 1.0e5, 1200.0, 2.0e5, 0.0)
    some = residual_gas_mass_kg(_CLEARANCE, 1.0e5, 1200.0, 2.0e5, 30.0)
    lots = residual_gas_mass_kg(_CLEARANCE, 1.0e5, 1200.0, 2.0e5, 80.0)
    assert lots < some < no_overlap


def test_throttling_plus_overlap_pulls_exhaust_back_in() -> None:
    no_overlap = residual_gas_mass_kg(_CLEARANCE, 1.0e5, 1200.0, 0.4e5, 0.0)
    some = residual_gas_mass_kg(_CLEARANCE, 1.0e5, 1200.0, 0.4e5, 30.0)
    lots = residual_gas_mass_kg(_CLEARANCE, 1.0e5, 1200.0, 0.4e5, 80.0)
    assert lots > some > no_overlap


# ------------------------------------------------------------- charge split

def test_the_split_conserves_mass_and_mixes_temperature() -> None:
    split = trapped_charge_split(
        ivc_volume_m3=_IVC_VOLUME, clearance_volume_m3=_CLEARANCE,
        intake_pressure_Pa=1.0e5, intake_temperature_K=330.0,
        exhaust_pressure_Pa=1.0e5, exhaust_temperature_K=1200.0,
        valve_overlap_deg=20.0,
    )
    assert split["fresh_mass_kg"] + split["residual_mass_kg"] == pytest.approx(
        split["total_mass_kg"], rel=1e-12
    )
    # Mixed temperature sits between the two streams.
    assert 330.0 < split["mixed_temperature_K"] < 1200.0
    assert 0.0 < split["residual_fraction"] < 1.0


def test_the_split_satisfies_the_ideal_gas_law_at_ivc() -> None:
    # The closed-form elimination has to reproduce p V = m R T for the mixture.
    split = trapped_charge_split(
        ivc_volume_m3=_IVC_VOLUME, clearance_volume_m3=_CLEARANCE,
        intake_pressure_Pa=1.2e5, intake_temperature_K=320.0,
        exhaust_pressure_Pa=1.1e5, exhaust_temperature_K=1100.0,
        valve_overlap_deg=25.0,
    )
    implied_p = (split["total_mass_kg"] * 287.0 * split["mixed_temperature_K"]
                 / _IVC_VOLUME)
    assert implied_p == pytest.approx(1.2e5, rel=1e-9)


def test_a_choked_head_reduces_the_charge_it_admits() -> None:
    full = trapped_charge_split(
        _IVC_VOLUME, _CLEARANCE, 1.0e5, 330.0, 1.0e5, 1200.0, 20.0,
        volumetric_efficiency=1.0,
    )
    choked = trapped_charge_split(
        _IVC_VOLUME, _CLEARANCE, 1.0e5, 330.0, 1.0e5, 1200.0, 20.0,
        volumetric_efficiency=0.6,
    )
    assert choked["fresh_mass_kg"] < full["fresh_mass_kg"]
    # Same residual, less fresh charge, so a bigger burned share.
    assert choked["residual_fraction"] > full["residual_fraction"]


def test_an_overwhelming_residual_is_clamped_not_allowed_to_diverge() -> None:
    # A tiny cylinder against a huge, hot clearance volume would drive the
    # closed form negative; it has to stay solvable instead.
    split = trapped_charge_split(
        ivc_volume_m3=6.0e-5, clearance_volume_m3=5.0e-5,
        intake_pressure_Pa=0.3e5, intake_temperature_K=300.0,
        exhaust_pressure_Pa=2.0e5, exhaust_temperature_K=1600.0,
        valve_overlap_deg=90.0,
    )
    assert 0.0 < split["residual_fraction"] <= 0.50
    assert split["fresh_mass_kg"] > 0.0
    assert split["total_mass_kg"] > 0.0


# ---------------------------------------------------------------- on the cycle

def test_residuals_stay_off_without_a_cam() -> None:
    # Overlap is a cam property; no cam, no residual model, exactly as before.
    r = _run()
    assert r.residual_fraction is None
    assert r.fresh_mass_kg is None
    assert r.mixed_temperature_K is None


def test_a_cam_turns_the_residual_on_and_reports_it() -> None:
    r = _run(valve_timing=MILD)
    assert 0.0 < r.residual_fraction < 0.2
    assert r.fresh_mass_kg < r.trapped_mass_kg
    assert r.mixed_temperature_K > 330.0        # hot residual warms the charge
    assert r.exhaust_temperature_K > 1000.0


def test_overlap_is_inert_at_wide_open_throttle() -> None:
    # Manifold and exhaust both at ambient: nothing to scavenge or draw back,
    # so the cam's overlap makes no difference to the residual.
    mild = _run(valve_timing=MILD)
    wild = _run(valve_timing=WILD)
    assert mild.residual_fraction == pytest.approx(wild.residual_fraction, rel=1e-6)


def test_a_big_cam_wrecks_a_throttled_engine() -> None:
    # The classic lumpy idle: throttling drops manifold pressure below exhaust,
    # and overlap then pulls burned gas back in and dilutes the charge.
    mild = _run(valve_timing=MILD, intake_pressure_Pa=0.5e5)
    wild = _run(valve_timing=WILD, intake_pressure_Pa=0.5e5)
    assert wild.residual_fraction > mild.residual_fraction * 2
    assert wild.mixed_temperature_K > mild.mixed_temperature_K
    assert wild.brake_power_W < mild.brake_power_W


def test_a_big_cam_helps_a_boosted_engine() -> None:
    # The other side of the same coin: boost blows the residual out through the
    # overlap window, so a wilder cam leaves a cleaner cylinder and makes more.
    common = dict(intake_pressure_Pa=2.0e5, aspiration="turbocharged")
    mild = _run(valve_timing=MILD, **common)
    wild = _run(valve_timing=WILD, **common)
    assert wild.residual_fraction < mild.residual_fraction
    assert wild.brake_power_W > mild.brake_power_W


def test_dilution_lowers_peak_temperature() -> None:
    # Burned gas cannot burn again, so a dilute cylinder releases less heat.
    mild = _run(valve_timing=MILD, intake_pressure_Pa=0.5e5)
    wild = _run(valve_timing=WILD, intake_pressure_Pa=0.5e5)
    assert wild.peak_temperature_K < mild.peak_temperature_K
    assert wild.heat_released_J < mild.heat_released_J


def test_air_fuel_ratio_is_reported_against_fresh_air_only() -> None:
    # The residual is not air, so it must not appear in the AFR.
    r = _run(valve_timing=WILD, intake_pressure_Pa=0.5e5, equivalence_ratio=1.0)
    assert r.air_fuel_ratio == pytest.approx(14.69, abs=0.1)
    assert r.residual_fraction > 0.05          # genuinely dilute, yet AFR holds


def test_the_first_law_still_closes_with_residuals() -> None:
    for kwargs in (
        dict(valve_timing=MILD),
        dict(valve_timing=WILD, intake_pressure_Pa=0.5e5),
        dict(valve_timing=WILD, intake_pressure_Pa=2.2e5, aspiration="turbocharged",
             valve_geometry=ValveGeometry()),
    ):
        r = _run(**kwargs)
        assert abs(r.energy_residual_J) < 1e-6


def test_the_two_pass_solve_is_deterministic() -> None:
    # Same inputs must give the same answer: the residual pass is a closed-form
    # correction, not a converging loop that could drift.
    a = _run(valve_timing=WILD, intake_pressure_Pa=0.6e5)
    b = _run(valve_timing=WILD, intake_pressure_Pa=0.6e5)
    assert a.residual_fraction == pytest.approx(b.residual_fraction, rel=1e-15)
    assert a.brake_power_W == pytest.approx(b.brake_power_W, rel=1e-15)
