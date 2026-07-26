"""Variable specific heats and two-zone combustion, on the full cycle.

The constant-gamma model was wrong in a specific direction: a fixed low ``cv``
turns the same heat release into far too much temperature rise, so peak
temperatures, peak pressures and indicated efficiency all came out flattering.
These tests pin the correction's *direction and size*, and check that the two
zones order themselves the way a flame front actually does.
"""

from __future__ import annotations

import pytest

from app.engine_core.piston.cycle import PistonCycleInputs, simulate_piston_cycle


def _run(**kwargs):
    base = dict(fuel="gasoline")
    base.update(kwargs)
    return simulate_piston_cycle(PistonCycleInputs(**base))


def _fixed():
    return _run()


def _variable():
    return _run(variable_specific_heats=True)


def _two_zone(**kwargs):
    return _run(variable_specific_heats=True, two_zone_combustion=True, **kwargs)


# --------------------------------------------------------- backward compatible

def test_the_old_constant_gamma_model_is_still_the_default() -> None:
    r = _fixed()
    assert r.variable_specific_heats is False
    assert r.two_zone_combustion is False
    assert r.mean_gamma is None
    assert r.peak_burned_temperature_K is None
    assert r.peak_unburned_temperature_K is None


def test_two_zone_needs_variable_specific_heats() -> None:
    # Asking for zones without real properties is contradictory; the model
    # declines rather than silently running a hybrid.
    r = _run(two_zone_combustion=True)
    assert r.two_zone_combustion is False


# ------------------------------------------------------- variable specific heats

def test_variable_specific_heats_bring_peak_temperature_down_hard() -> None:
    # This is the headline correction. A real charge soaks up far more energy
    # per kelvin at combustion temperatures than gamma = 1.35 allows for.
    fixed, variable = _fixed(), _variable()
    assert variable.peak_temperature_K < fixed.peak_temperature_K - 300.0
    # And into the band a real spark-ignition engine actually runs in.
    assert 2400.0 < variable.peak_temperature_K < 3000.0


def test_peak_pressure_and_efficiency_were_both_being_over_predicted() -> None:
    fixed, variable = _fixed(), _variable()
    assert variable.peak_pressure_Pa < fixed.peak_pressure_Pa
    assert variable.thermal_efficiency < fixed.thermal_efficiency
    # A naturally aspirated petrol engine peaks well under 80 bar.
    assert variable.peak_pressure_Pa / 1e5 < 75.0


def test_the_reported_mean_gamma_lands_below_the_old_constant() -> None:
    # Most of the cycle is spent hot, where gamma is well under 1.35.
    r = _variable()
    assert 1.25 < r.mean_gamma < 1.35


def test_the_first_law_still_closes_with_variable_properties() -> None:
    # Energy is marched directly and inverted for temperature, so composition
    # and property changes cannot leak energy.
    for r in (_variable(), _two_zone(),
              _two_zone(compression_ratio=14.0, intake_pressure_Pa=1.8e5,
                        aspiration="turbocharged")):
        assert abs(r.energy_residual_J) < 1e-6


def test_a_diesel_is_corrected_the_same_way() -> None:
    common = dict(fuel="diesel", compression_ratio=18.0, equivalence_ratio=0.7,
                  combustion_start_deg=-8.0)
    fixed = simulate_piston_cycle(PistonCycleInputs(**common))
    variable = simulate_piston_cycle(PistonCycleInputs(**common, variable_specific_heats=True))
    assert variable.peak_temperature_K < fixed.peak_temperature_K
    assert variable.thermal_efficiency < fixed.thermal_efficiency


# ---------------------------------------------------------------- two zones

def test_the_flame_front_orders_the_temperatures() -> None:
    # Burned gas behind the flame is hotter than the cylinder mean; unburned
    # end-gas ahead of it has only been compressed, so it is far cooler.
    r = _two_zone()
    assert r.peak_burned_temperature_K > r.peak_temperature_K
    assert r.peak_unburned_temperature_K < r.peak_temperature_K
    assert r.peak_unburned_temperature_K < r.peak_burned_temperature_K


def test_end_gas_is_compressed_not_burned() -> None:
    # It should sit in the band an isentropic compression reaches, hundreds of
    # kelvin below anything that has actually burned.
    r = _two_zone()
    assert 700.0 < r.peak_unburned_temperature_K < 1400.0


def test_end_gas_temperature_climbs_with_compression_ratio() -> None:
    # Which is precisely why compression ratio is knock-limited.
    temps = [_two_zone(compression_ratio=cr).peak_unburned_temperature_K
             for cr in (8.0, 10.0, 12.0, 14.0)]
    assert temps == sorted(temps)


def test_end_gas_temperature_climbs_with_boost() -> None:
    temps = [_two_zone(intake_pressure_Pa=p, aspiration="turbocharged").peak_unburned_temperature_K
             for p in (1.0e5, 1.5e5, 2.0e5, 2.5e5)]
    assert temps == sorted(temps)


def test_a_cooler_charge_gives_cooler_end_gas() -> None:
    # Intercooling buys knock margin, and now the model shows why.
    hot = _two_zone(intake_temperature_K=400.0)
    cool = _two_zone(intake_temperature_K=300.0)
    assert cool.peak_unburned_temperature_K < hot.peak_unburned_temperature_K


def test_two_zone_barely_moves_the_bulk_answer() -> None:
    # Splitting the charge redistributes temperature; it does not invent work.
    # Brake power should agree with the single-zone variable-cp run closely.
    single, split = _variable(), _two_zone()
    assert split.brake_power_W == pytest.approx(single.brake_power_W, rel=0.10)


def test_zone_temperatures_are_reported_only_when_zones_are_modelled() -> None:
    r = _two_zone()
    assert r.two_zone_combustion is True
    assert r.peak_burned_temperature_K is not None
    assert r.peak_unburned_temperature_K is not None
    payload = r.to_dict()
    for key in ("variable_specific_heats", "two_zone_combustion", "mean_gamma",
                "peak_unburned_temperature_K", "peak_burned_temperature_K"):
        assert key in payload


# ------------------------------------------------- knock on the tracked end gas

def _knock(result) -> str:
    return next((w["severity"] for w in result.operating_warnings if w["kind"] == "knock"),
                "clear")


def test_knock_still_arrives_with_compression_ratio() -> None:
    # The headline behaviour has to survive the model change: raise compression
    # far enough on pump petrol and the end gas lights itself.
    assert _knock(_two_zone(compression_ratio=9.0)) == "clear"
    assert _knock(_two_zone(compression_ratio=14.0)) == "warning"


def test_intercooling_buys_knock_margin() -> None:
    # A cooler charge starts the compression lower and ends it lower, which is
    # the entire reason intercoolers exist.
    hot = _two_zone(compression_ratio=12.0, intake_temperature_K=380.0)
    cool = _two_zone(compression_ratio=12.0, intake_temperature_K=300.0)
    assert cool.peak_unburned_temperature_K < hot.peak_unburned_temperature_K
    assert _knock(cool) == "clear"
    assert _knock(hot) == "warning"


def test_residual_dilution_is_visible_to_the_knock_model() -> None:
    # This is what the old proxy structurally could not see: it compressed the
    # *manifold* temperature, so hot residual raising the charge temperature at
    # IVC was invisible to it. The tracked end gas starts from the real state.
    from app.engine_core.piston.valvetrain import ValveTiming

    wild = ValveTiming(intake_open_btdc_deg=35.0, exhaust_close_atdc_deg=35.0)
    diluted = _two_zone(compression_ratio=12.0, valve_timing=wild,
                        intake_pressure_Pa=0.6e5)
    clean = _two_zone(compression_ratio=12.0, intake_temperature_K=330.0)
    assert diluted.residual_fraction > 0.05
    assert diluted.mixed_temperature_K > 330.0
    assert diluted.peak_unburned_temperature_K > clean.peak_unburned_temperature_K


def test_high_octane_fuel_tolerates_what_petrol_cannot() -> None:
    # Ethanol's octane and charge cooling let it run compression that knocks on
    # gasoline, which the end-gas comparison should reflect.
    petrol = _two_zone(compression_ratio=14.0, fuel="gasoline")
    ethanol = _two_zone(compression_ratio=14.0, fuel="ethanol")
    assert _knock(petrol) == "warning"
    assert _knock(ethanol) in ("clear", "caution")


def test_a_diesel_is_judged_on_smoke_not_knock() -> None:
    rich = _two_zone(fuel="diesel", compression_ratio=18.0, equivalence_ratio=0.95,
                     combustion_start_deg=-8.0)
    kinds = {w["kind"] for w in rich.operating_warnings}
    assert "smoke" in kinds
    assert "knock" not in kinds


def test_the_solver_stays_stable_across_a_wide_sweep() -> None:
    # The two-zone split solves a nonlinear system every step; it has to hold up
    # across the whole envelope, not just the nominal point.
    for rpm in (1000.0, 4000.0, 8000.0):
        for cr in (8.0, 12.0, 16.0):
            r = _two_zone(rpm=rpm, compression_ratio=cr)
            assert r.peak_burned_temperature_K > r.peak_unburned_temperature_K
            assert abs(r.energy_residual_J) < 1e-6
            assert r.peak_pressure_Pa > 0.0
