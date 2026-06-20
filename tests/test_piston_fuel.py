"""PistonLab Day 7 — fuel thermochemistry.

The cycle solver no longer takes a raw heat-per-kg knob as its only fuelling
input. Instead a real fuel (gasoline / diesel / ethanol / methanol) plus a
mixture strength (equivalence ratio phi) set the heat release from the fuel's
own chemistry:

    AFR_stoich  <- C/H/O mass balance of combustion
    f = phi / AFR_stoich            (fuel-air ratio)
    q_per_kg_charge = f * LHV * eta_combustion

These tests check the chemistry (stoichiometric AFR matches the textbook values
as a *derived* quantity) and the cycle integration (richer mixtures release more
heat and make more work; lambda = 1/phi; the legacy raw-heat path still works).
"""

from __future__ import annotations

import pytest

from app.engine_core.piston import (
    PistonCycleInputs,
    fuel_air_ratio,
    get_fuel,
    lambda_from_phi,
    simulate_piston_cycle,
    specific_heat_release_J_per_kg_charge,
    stoichiometric_afr,
)


# ---------------------------------------------------------------------------
# Fuel chemistry (no cycle)
# ---------------------------------------------------------------------------


def test_stoichiometric_afr_matches_textbook() -> None:
    # Derived from the combustion mass balance, not hard-coded — yet it lands on
    # the well-known numbers.
    assert stoichiometric_afr("gasoline") == pytest.approx(14.7, abs=0.3)
    assert stoichiometric_afr("diesel") == pytest.approx(14.5, abs=0.3)
    assert stoichiometric_afr("ethanol") == pytest.approx(9.0, abs=0.3)
    assert stoichiometric_afr("methanol") == pytest.approx(6.4, abs=0.3)


def test_case_insensitive_and_unknown_fuel() -> None:
    assert stoichiometric_afr("Gasoline") == stoichiometric_afr("gasoline")
    with pytest.raises(ValueError):
        get_fuel("rocket")
    with pytest.raises(ValueError):
        stoichiometric_afr("kerosene-blend-x")


def test_oxygenated_fuels_need_less_air() -> None:
    # Alcohols carry their own oxygen, so they need far less air per kg of fuel.
    assert stoichiometric_afr("ethanol") < stoichiometric_afr("gasoline")
    assert stoichiometric_afr("methanol") < stoichiometric_afr("ethanol")


def test_fuel_air_ratio_scales_with_phi() -> None:
    f1 = fuel_air_ratio("gasoline", 1.0)
    assert f1 == pytest.approx(1.0 / stoichiometric_afr("gasoline"), rel=1e-12)
    # Linear in phi: doubling phi doubles the fuel-air ratio.
    assert fuel_air_ratio("gasoline", 2.0) == pytest.approx(2.0 * f1, rel=1e-12)
    assert fuel_air_ratio("gasoline", 0.5) == pytest.approx(0.5 * f1, rel=1e-12)


def test_lambda_is_inverse_of_phi() -> None:
    assert lambda_from_phi(1.0) == pytest.approx(1.0)
    assert lambda_from_phi(0.8) == pytest.approx(1.25)
    assert lambda_from_phi(1.25) == pytest.approx(0.8)
    with pytest.raises(ValueError):
        lambda_from_phi(0.0)


def test_specific_heat_release_chains_through() -> None:
    fuel = get_fuel("gasoline")
    q = specific_heat_release_J_per_kg_charge("gasoline", 1.0, 1.0)
    assert q == pytest.approx(fuel_air_ratio("gasoline", 1.0) * fuel.lower_heating_value_J_per_kg, rel=1e-12)
    # Combustion efficiency scales it linearly.
    assert specific_heat_release_J_per_kg_charge("gasoline", 1.0, 0.9) == pytest.approx(0.9 * q, rel=1e-12)
    with pytest.raises(ValueError):
        specific_heat_release_J_per_kg_charge("gasoline", 1.0, 0.0)


# ---------------------------------------------------------------------------
# Cycle integration
# ---------------------------------------------------------------------------


def test_fuel_mode_reports_stoichiometric_afr_at_phi_one() -> None:
    r = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", equivalence_ratio=1.0))
    assert r.fuel == "gasoline"
    assert r.equivalence_ratio == pytest.approx(1.0)
    assert r.lambda_air == pytest.approx(1.0)
    # At phi = 1 the actual AFR equals the stoichiometric AFR.
    assert r.air_fuel_ratio == pytest.approx(stoichiometric_afr("gasoline"), rel=1e-6)
    assert r.fuel_air_ratio == pytest.approx(1.0 / stoichiometric_afr("gasoline"), rel=1e-6)


def test_lambda_tracks_phi_in_cycle() -> None:
    lean = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", equivalence_ratio=0.8))
    rich = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", equivalence_ratio=1.2))
    assert lean.lambda_air == pytest.approx(1.25, rel=1e-6)   # 1/0.8
    assert rich.lambda_air == pytest.approx(1.0 / 1.2, rel=1e-6)
    assert lean.air_fuel_ratio > rich.air_fuel_ratio          # leaner = more air


def test_richer_mixture_releases_more_heat_and_work() -> None:
    lean = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", equivalence_ratio=0.7))
    stoich = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", equivalence_ratio=1.0))
    assert stoich.heat_released_J > lean.heat_released_J
    assert stoich.imep_Pa > lean.imep_Pa
    assert stoich.peak_temperature_K > lean.peak_temperature_K


def test_lambda_sweep_is_monotonic_and_sane() -> None:
    phis = [0.7, 0.8, 0.9, 1.0, 1.1, 1.2]
    runs = [simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", equivalence_ratio=p)) for p in phis]
    heats = [r.heat_released_J for r in runs]
    imeps = [r.imep_Pa for r in runs]
    # Strictly increasing fuelling -> strictly increasing heat and work.
    assert all(b > a for a, b in zip(heats, heats[1:]))
    assert all(b > a for a, b in zip(imeps, imeps[1:]))
    # Every case stays physical and closes the first law.
    for r in runs:
        assert r.indicated_work_J > 0.0
        assert abs(r.energy_residual_J) < 1e-6 * r.heat_released_J
        assert r.bsfc_g_per_kWh > 0.0


def test_combustion_efficiency_scales_heat_release() -> None:
    full = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", combustion_efficiency=1.0))
    poor = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", combustion_efficiency=0.9))
    # Heat released scales exactly with combustion efficiency (same burn shape).
    assert poor.heat_released_J == pytest.approx(0.9 * full.heat_released_J, rel=1e-9)


def test_fuel_mass_is_consistent_with_air_fuel_ratio() -> None:
    r = simulate_piston_cycle(PistonCycleInputs(fuel="diesel", equivalence_ratio=0.9))
    assert r.fuel_mass_per_cycle_kg == pytest.approx(r.trapped_mass_kg * r.fuel_air_ratio, rel=1e-9)
    assert r.air_fuel_ratio == pytest.approx(stoichiometric_afr("diesel") / 0.9, rel=1e-6)


def test_fuel_path_reduces_to_raw_heat_path() -> None:
    # Driving the legacy raw-heat input with exactly the fuel-derived q must give
    # the identical cycle — proving the fuel layer only computes q, nothing else.
    q = specific_heat_release_J_per_kg_charge("gasoline", 1.0, 0.98)
    legacy = simulate_piston_cycle(PistonCycleInputs(heat_release_J_per_kg=q))   # fuel=None
    fueled = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", equivalence_ratio=1.0, combustion_efficiency=0.98))
    assert legacy.fuel == "manual"
    assert legacy.heat_released_J == pytest.approx(fueled.heat_released_J, rel=1e-9)
    assert legacy.imep_Pa == pytest.approx(fueled.imep_Pa, rel=1e-9)


def test_fuel_mode_ignores_raw_heat_input() -> None:
    # With a fuel selected, the raw heat_release_J_per_kg is overridden.
    a = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", equivalence_ratio=1.0))
    b = simulate_piston_cycle(PistonCycleInputs(
        fuel="gasoline", equivalence_ratio=1.0, heat_release_J_per_kg=9.9e9))
    assert a.heat_released_J == pytest.approx(b.heat_released_J, rel=1e-12)


def test_fuel_inputs_validated() -> None:
    with pytest.raises(ValueError):
        PistonCycleInputs(fuel="rocket")
    with pytest.raises(ValueError):
        PistonCycleInputs(equivalence_ratio=0.0)
    with pytest.raises(ValueError):
        PistonCycleInputs(combustion_efficiency=1.5)
