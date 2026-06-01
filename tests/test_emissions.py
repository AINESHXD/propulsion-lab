"""Tests for the reactor-network combustor emissions model (Month-4 feature).

NOx is the calibrated, validated quantity: a two-zone Cantera reactor network
(equilibrate the primary zone, then grow Zeldovich NO kinetically) should give
EINOx in the modern-combustor band at take-off-class conditions and the correct
power lapse (high at take-off, collapsing toward idle). CO / soot are secondary
estimates. The ICAO LTO aggregation arithmetic is checked exactly; the engine-
coupled LTO is checked for physical shape, not a certification number (the
educational cycle cannot match a specific databank value without curve-fitting).
"""

from __future__ import annotations

import math

import pytest

from app.engine_core.emissions import (
    ICAO_LTO_MODES,
    LTOModePoint,
    combustor_emissions,
    equivalence_ratio,
    far_stoichiometric,
    icao_lto_nox,
)
from app.engine_core.gas_service import is_cantera_available

ATM = 101325.0
requires_cantera = pytest.mark.skipif(
    not is_cantera_available(), reason="Cantera not installed"
)


# ---------------------------------------------------------------------------
# Stoichiometry helpers
# ---------------------------------------------------------------------------


def test_far_stoichiometric_methane() -> None:
    # Methane-air stoichiometric FAR is ~0.058 by mass.
    assert far_stoichiometric("CH4") == pytest.approx(0.058, abs=0.003)


def test_equivalence_ratio_scales_with_far() -> None:
    fs = far_stoichiometric("CH4")
    assert equivalence_ratio(fs) == pytest.approx(1.0, rel=1e-6)
    assert equivalence_ratio(fs / 2.0) == pytest.approx(0.5, rel=1e-6)
    assert equivalence_ratio(0.0) == 0.0


# ---------------------------------------------------------------------------
# Reactor-network emission indices — 5 design points + trends
# ---------------------------------------------------------------------------

# (T3_K, P3_atm, FAR) spanning idle -> take-off-class combustor inlets.
_DESIGN_POINTS = [
    (480.0, 5.0, 0.010),
    (620.0, 12.0, 0.016),
    (720.0, 20.0, 0.019),
    (780.0, 25.0, 0.021),
    (820.0, 30.0, 0.0225),
]


@requires_cantera
@pytest.mark.parametrize("T3,P3atm,far", _DESIGN_POINTS)
def test_emissions_five_design_points_are_finite_and_sane(T3, P3atm, far) -> None:
    r = combustor_emissions(T3, P3atm * ATM, far)
    assert r.source == "reactor-network"
    # All emission indices finite and non-negative.
    for ei in (r.ei_nox_g_per_kg, r.ei_co_g_per_kg, r.ei_hc_g_per_kg,
               r.ei_co2_g_per_kg, r.ei_h2o_g_per_kg):
        assert math.isfinite(ei) and ei >= 0.0
    # CO2/H2O dominate the product slate.
    assert r.ei_co2_g_per_kg > 1000.0
    assert r.ei_h2o_g_per_kg > 500.0
    # Primary flame is hot; overall mixture is lean (turbojet combustor).
    assert 1800.0 < r.primary_zone_temperature_K < 2700.0
    assert 0.0 < r.phi_overall < 1.0
    # Axial profile has the primary point plus the dilution steps.
    assert len(r.axial_profile) >= 2


@requires_cantera
def test_takeoff_einox_in_modern_combustor_band() -> None:
    r = combustor_emissions(820.0, 30.0 * ATM, 0.0225)
    # Modern combustors sit ~15-40 g/kg EINOx at take-off-class conditions.
    assert 15.0 <= r.ei_nox_g_per_kg <= 40.0


@requires_cantera
def test_einox_rises_with_inlet_temperature_and_pressure() -> None:
    # Thermal (Zeldovich) NOx is exponentially sensitive to flame temperature,
    # which climbs with combustor-inlet T3 and pressure.
    low = combustor_emissions(620.0, 12.0 * ATM, 0.018)
    high = combustor_emissions(820.0, 30.0 * ATM, 0.018)
    assert high.ei_nox_g_per_kg > low.ei_nox_g_per_kg
    assert high.ei_nox_g_per_kg > 5.0 * low.ei_nox_g_per_kg  # steep, not marginal


@requires_cantera
def test_einox_rises_with_primary_equivalence_ratio() -> None:
    lean = combustor_emissions(820.0, 30.0 * ATM, 0.0225, phi_primary=0.65)
    rich = combustor_emissions(820.0, 30.0 * ATM, 0.0225, phi_primary=0.80)
    assert rich.ei_nox_g_per_kg > lean.ei_nox_g_per_kg


@requires_cantera
def test_emissions_runs_quickly() -> None:
    import time
    t0 = time.time()
    combustor_emissions(820.0, 30.0 * ATM, 0.0225)
    assert time.time() - t0 < 0.6  # PSR + PFR network well under ~0.5 s


def test_emissions_input_validation() -> None:
    with pytest.raises(ValueError):
        combustor_emissions(-1.0, 30.0 * ATM, 0.02)
    with pytest.raises(ValueError):
        combustor_emissions(820.0, 30.0 * ATM, 0.0)
    with pytest.raises(ValueError):
        combustor_emissions(820.0, 30.0 * ATM, 0.02, phi_primary=2.0)


# ---------------------------------------------------------------------------
# ICAO LTO aggregation — exact arithmetic
# ---------------------------------------------------------------------------


def test_icao_lto_modes_are_the_standard_four() -> None:
    names = [m[0] for m in ICAO_LTO_MODES]
    assert names == ["Take-off", "Climb-out", "Approach", "Idle"]
    # Standard times-in-mode (seconds).
    times = {m[0]: m[2] for m in ICAO_LTO_MODES}
    assert times["Take-off"] == pytest.approx(42.0)
    assert times["Idle"] == pytest.approx(1560.0)


def test_icao_lto_aggregation_is_exact() -> None:
    modes = [
        LTOModePoint("Take-off", 1.00, 42.0, 30.0, 1.00),
        LTOModePoint("Climb-out", 0.85, 132.0, 24.0, 0.80),
        LTOModePoint("Approach", 0.30, 240.0, 10.0, 0.30),
        LTOModePoint("Idle", 0.07, 1560.0, 4.0, 0.10),
    ]
    res = icao_lto_nox(modes, rated_thrust_kN=100.0)
    expected_nox = (30 * 1.0 * 42) + (24 * 0.8 * 132) + (10 * 0.3 * 240) + (4 * 0.1 * 1560)
    expected_fuel = (1.0 * 42) + (0.8 * 132) + (0.3 * 240) + (0.1 * 1560)
    assert res.dp_nox_g == pytest.approx(expected_nox)
    assert res.fuel_burn_kg == pytest.approx(expected_fuel)
    assert res.dp_foo_g_per_kN == pytest.approx(expected_nox / 100.0)
    assert len(res.per_mode) == 4


def test_icao_lto_without_rated_thrust_omits_dp_foo() -> None:
    res = icao_lto_nox([LTOModePoint("Idle", 0.07, 1560.0, 4.0, 0.1)])
    assert res.dp_foo_g_per_kN is None
    assert res.dp_nox_g == pytest.approx(4.0 * 0.1 * 1560.0)


# ---------------------------------------------------------------------------
# Engine-coupled LTO endpoint — physical shape (not a certification number)
# ---------------------------------------------------------------------------


@requires_cantera
def test_turbojet_lto_endpoint_has_correct_power_lapse() -> None:
    from app.main import emissions_turbojet_lto
    from app.schemas import TurbojetInput, TurbojetLTOInput

    out = emissions_turbojet_lto(TurbojetLTOInput(
        design=TurbojetInput(
            compressor_pressure_ratio=30.0,
            turbine_inlet_temperature_K=1600.0,
            mass_flow_air_kg_s=120.0,
            compressor_efficiency=0.88,
            turbine_efficiency=0.90,
        )
    ))
    assert out.rated_thrust_kN and out.rated_thrust_kN > 0.0
    assert out.dp_nox_g > 0.0 and out.dp_foo_g_per_kN is not None
    by_name = {m.name: m for m in out.modes}
    take_off = by_name["Take-off"]
    idle = by_name["Idle"]
    # Take-off EINOx is realistic and NOx lapses hard toward idle.
    assert 15.0 <= take_off.ei_nox_g_per_kg <= 45.0
    assert idle.ei_nox_g_per_kg < take_off.ei_nox_g_per_kg
    # Combustor-inlet temperature falls with power (OPR lapse).
    assert idle.combustor_inlet_temperature_K < take_off.combustor_inlet_temperature_K
    # Dp/Foo is in a physically plausible order-of-magnitude band.
    assert 20.0 <= out.dp_foo_g_per_kN <= 150.0
    # The output is transparent about being an estimate.
    assert any("Estimate" in n for n in out.notes)
