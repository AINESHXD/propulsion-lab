"""Temperature-dependent specific heats for the in-cylinder charge.

Two layers of checking. The fits are hard-coded so the solver has no runtime
dependency on Cantera, so the first layer pins them against published anchor
values that do not move. The second layer re-derives the same quantities from
Cantera directly and demands the fit agree, which is skipped on an install that
does not have it — that is the check that would actually catch a mistyped
coefficient.
"""

from __future__ import annotations

import importlib.util

import pytest

from app.engine_core.piston import thermo as th

_HAS_CANTERA = importlib.util.find_spec("cantera") is not None

# Composition of the burned gas: the stoichiometric product of PistonLab's own
# gasoline model, C8H16 + 12 O2 -> 8 CO2 + 8 H2O, carrying its nitrogen.
_N2 = 12.0 * 79.0 / 21.0
_TOTAL = 8.0 + 8.0 + _N2
_AIR_X = "N2:0.7808, O2:0.2095, AR:0.0093, CO2:0.0004"
_PRODUCT_X = f"CO2:{8.0 / _TOTAL:.6f}, H2O:{8.0 / _TOTAL:.6f}, N2:{_N2 / _TOTAL:.6f}"


# ------------------------------------------------------------- anchor values

@pytest.mark.parametrize("temperature_K, expected_cp", [
    (300.0, 1003.5),
    (500.0, 1031.0),
    (1000.0, 1142.8),
    (1500.0, 1210.2),
    (2000.0, 1251.0),
    (2500.0, 1276.7),
])
def test_air_cp_matches_standard_tables(temperature_K: float, expected_cp: float) -> None:
    assert th.cp_J_per_kg_K(temperature_K, 0.0) == pytest.approx(expected_cp, rel=0.005)


def test_air_properties_at_room_temperature_are_the_familiar_ones() -> None:
    # cv ~ 718 J/kg/K and gamma ~ 1.40 for air: the numbers every textbook opens
    # with, and a sanity check that the polynomial is not subtly off.
    assert th.cv_J_per_kg_K(300.0, 0.0) == pytest.approx(717.0, abs=3.0)
    assert th.gamma(300.0, 0.0) == pytest.approx(1.400, abs=0.005)


def test_specific_heat_rises_with_temperature() -> None:
    # The whole point: vibrational modes activate, cp climbs, gamma falls.
    cps = [th.cp_J_per_kg_K(t, 0.0) for t in (300, 800, 1500, 2200, 2900)]
    assert cps == sorted(cps)
    gammas = [th.gamma(t, 0.0) for t in (300, 800, 1500, 2200, 2900)]
    assert gammas == sorted(gammas, reverse=True)


def test_burned_products_hold_more_heat_than_air() -> None:
    # CO2 and H2O are triatomic, so the products carry substantially more heat
    # per kelvin -- which is exactly why a single constant gamma overshoots the
    # peak temperature.
    for t in (1000.0, 2000.0, 2800.0):
        assert th.cp_J_per_kg_K(t, 1.0) > th.cp_J_per_kg_K(t, 0.0)
        assert th.gamma(t, 1.0) < th.gamma(t, 0.0)
    assert th.gamma(2000.0, 1.0) == pytest.approx(1.25, abs=0.02)


def test_the_old_constant_gamma_sits_between_the_extremes() -> None:
    # 1.35 was a reasonable single compromise, which is why it was chosen; it is
    # simply wrong at both ends of the cycle.
    assert th.gamma(300.0, 0.0) > 1.35 > th.gamma(2500.0, 1.0)


def test_properties_blend_linearly_with_burned_fraction() -> None:
    t = 1800.0
    half = th.cp_J_per_kg_K(t, 0.5)
    mean = 0.5 * (th.cp_J_per_kg_K(t, 0.0) + th.cp_J_per_kg_K(t, 1.0))
    assert half == pytest.approx(mean, rel=1e-12)
    assert th.mixture_gas_constant(0.5) == pytest.approx(
        0.5 * (th.R_AIR + th.R_PRODUCT), rel=1e-12
    )


# ------------------------------------------------------- energy bookkeeping

def test_internal_energy_is_zero_at_the_datum_for_both_compositions() -> None:
    # Shared datum, so a change of composition at fixed temperature releases no
    # spurious energy. Combustion energy arrives as Wiebe heat instead.
    for x in (0.0, 0.5, 1.0):
        assert th.internal_energy_J_per_kg(th.REFERENCE_TEMPERATURE_K, x) == pytest.approx(
            0.0, abs=1e-9
        )


def test_internal_energy_inverts_exactly() -> None:
    # The integrator marches energy and inverts back for temperature, so this
    # round trip has to be tight or the first law will not close.
    for t in (300.0, 700.0, 1200.0, 1800.0, 2400.0, 2900.0):
        for x in (0.0, 0.35, 1.0):
            u = th.internal_energy_J_per_kg(t, x)
            assert th.temperature_from_internal_energy(u, x, guess_K=900.0) == pytest.approx(
                t, abs=1e-6
            )


def test_the_inversion_converges_from_a_poor_starting_guess() -> None:
    u = th.internal_energy_J_per_kg(2500.0, 0.8)
    for guess in (260.0, 1000.0, 2990.0):
        assert th.temperature_from_internal_energy(u, 0.8, guess_K=guess) == pytest.approx(
            2500.0, abs=1e-5
        )


def test_internal_energy_derivative_is_cv() -> None:
    # u is defined as the integral of cv, so a numerical derivative must return
    # cv. This is what makes the Newton inversion exact rather than approximate.
    t, x, h = 1600.0, 0.4, 0.05
    slope = (th.internal_energy_J_per_kg(t + h, x)
             - th.internal_energy_J_per_kg(t - h, x)) / (2.0 * h)
    assert slope == pytest.approx(th.cv_J_per_kg_K(t, x), rel=1e-6)


def test_the_fit_is_held_inside_the_range_it_was_made_over() -> None:
    # Beyond 3000 K the charge would be dissociating, which a frozen composition
    # does not model, so the polynomial is clamped rather than extrapolated.
    assert th.cp_J_per_kg_K(5000.0, 0.0) == pytest.approx(
        th.cp_J_per_kg_K(th.VALID_MAX_K, 0.0)
    )


def test_non_physical_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        th.cp_J_per_kg_K(0.0)
    with pytest.raises(ValueError):
        th.internal_energy_J_per_kg(-5.0)


# ------------------------------------------------- cross-check the fit itself

@pytest.mark.skipif(not _HAS_CANTERA, reason="Cantera not installed")
@pytest.mark.parametrize("temperature_K", [300.0, 600.0, 1000.0, 1500.0, 2000.0, 2500.0, 3000.0])
def test_air_fit_agrees_with_cantera(temperature_K: float) -> None:
    import cantera as ct

    gas = ct.Solution("gri30.yaml")
    gas.TPX = temperature_K, ct.one_atm, _AIR_X
    assert th.cp_J_per_kg_K(temperature_K, 0.0) == pytest.approx(gas.cp_mass, rel=0.005)


@pytest.mark.skipif(not _HAS_CANTERA, reason="Cantera not installed")
@pytest.mark.parametrize("temperature_K", [300.0, 1000.0, 1800.0, 2500.0, 3000.0])
def test_product_fit_agrees_with_cantera(temperature_K: float) -> None:
    import cantera as ct

    gas = ct.Solution("gri30.yaml")
    gas.TPX = temperature_K, ct.one_atm, _PRODUCT_X
    assert th.cp_J_per_kg_K(temperature_K, 1.0) == pytest.approx(gas.cp_mass, rel=0.005)


@pytest.mark.skipif(not _HAS_CANTERA, reason="Cantera not installed")
def test_gas_constants_agree_with_cantera() -> None:
    import cantera as ct

    gas = ct.Solution("gri30.yaml")
    gas.TPX = 300.0, ct.one_atm, _AIR_X
    assert th.R_AIR == pytest.approx(ct.gas_constant / gas.mean_molecular_weight, rel=1e-4)
    gas.TPX = 300.0, ct.one_atm, _PRODUCT_X
    assert th.R_PRODUCT == pytest.approx(ct.gas_constant / gas.mean_molecular_weight, rel=1e-4)
