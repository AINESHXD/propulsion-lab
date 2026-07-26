"""Turbocharger back-pressure from the shaft power balance.

A turbo is not free. Its compressor costs the crankshaft nothing, but the
turbine driving it can only make shaft power by expanding the exhaust across
itself, and that raises the pressure the piston has to push against on the
exhaust stroke. The expansion ratio is *solved* from the shaft power balance
rather than assumed, so these tests check the balance behaves the way the
thermodynamics says it must.
"""

from __future__ import annotations

import pytest

from app.engine_core.piston.aspiration import (
    compressor_power_W,
    supercharger_power_W,
    turbine_back_pressure_Pa,
    turbine_expansion_ratio,
)
from app.engine_core.piston.cycle import PistonCycleInputs, simulate_piston_cycle


def _turbo(**kwargs):
    base = dict(fuel="gasoline", aspiration="turbocharged", intake_pressure_Pa=1.8e5)
    base.update(kwargs)
    return simulate_piston_cycle(PistonCycleInputs(**base))


# --------------------------------------------------------- the shaft balance

def test_no_boost_needs_no_expansion() -> None:
    ratio, ok = turbine_expansion_ratio(0.0, 0.05, 1200.0)
    assert ratio == pytest.approx(1.0)
    assert ok is True


def test_a_hungrier_compressor_needs_more_expansion() -> None:
    low, _ = turbine_expansion_ratio(3000.0, 0.05, 1200.0)
    high, _ = turbine_expansion_ratio(9000.0, 0.05, 1200.0)
    assert high > low > 1.0


def test_hotter_exhaust_carries_more_enthalpy_so_costs_less() -> None:
    # The turbine extracts from cp * T; a hotter stream needs less pressure drop
    # for the same shaft power. This is why a turbo works better under load.
    cool, _ = turbine_expansion_ratio(6000.0, 0.05, 900.0)
    hot, _ = turbine_expansion_ratio(6000.0, 0.05, 1400.0)
    assert hot < cool


def test_more_exhaust_flow_costs_less_expansion() -> None:
    thin, _ = turbine_expansion_ratio(6000.0, 0.03, 1200.0)
    fat, _ = turbine_expansion_ratio(6000.0, 0.09, 1200.0)
    assert fat < thin


def test_a_better_turbine_costs_less_back_pressure() -> None:
    poor, _ = turbine_expansion_ratio(6000.0, 0.05, 1200.0, turbine_efficiency=0.55)
    good, _ = turbine_expansion_ratio(6000.0, 0.05, 1200.0, turbine_efficiency=0.85)
    assert good < poor


def test_boost_beyond_the_exhaust_enthalpy_is_flagged_not_silently_clamped() -> None:
    # Ask for far more shaft power than the stream can supply: the turbo would
    # never spool to it, and the result says so rather than returning a
    # plausible-looking number.
    ratio, ok = turbine_expansion_ratio(500_000.0, 0.01, 600.0)
    assert ok is False
    assert ratio < float("inf")          # clamped, not divergent
    modest, ok2 = turbine_expansion_ratio(2_000.0, 0.05, 1200.0)
    assert ok2 is True
    assert modest < ratio


def test_the_manifold_sits_above_whatever_is_downstream() -> None:
    # Restriction first, turbine on top -- the physical order.
    p_low, ratio, _ = turbine_back_pressure_Pa(6000.0, 0.05, 1200.0, 1.0e5)
    p_high, ratio2, _ = turbine_back_pressure_Pa(6000.0, 0.05, 1200.0, 1.4e5)
    assert ratio == pytest.approx(ratio2)
    assert p_low == pytest.approx(1.0e5 * ratio)
    assert p_high == pytest.approx(1.4e5 * ratio)
    assert p_high > p_low


def test_the_two_compressors_do_identical_work() -> None:
    # Belt-driven or exhaust-driven, compressing air to a pressure ratio costs
    # the same; only who pays differs.
    args = (0.05, 320.0, 1.8, 0.7)
    assert compressor_power_W(*args) == pytest.approx(supercharger_power_W(*args))


@pytest.mark.parametrize("kwargs", [
    {"turbine_efficiency": 0.0},
    {"turbine_efficiency": 1.5},
    {"mechanical_efficiency": 0.0},
])
def test_invalid_turbine_efficiencies_are_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        turbine_expansion_ratio(6000.0, 0.05, 1200.0, **kwargs)


# ------------------------------------------------------------- on the cycle

def test_a_turbo_now_runs_exhaust_pressure_above_ambient() -> None:
    r = _turbo()
    assert r.turbine_pressure_ratio > 1.0
    assert r.exhaust_pressure_Pa > 1.0e5
    assert r.compressor_power_W > 0.0
    # Still nothing off the crank.
    assert r.supercharger_power_W == 0.0


def test_more_boost_costs_more_back_pressure() -> None:
    ratios = [_turbo(intake_pressure_Pa=p).exhaust_pressure_Pa
              for p in (1.2e5, 1.6e5, 2.0e5, 2.5e5)]
    assert ratios == sorted(ratios)


def test_a_worse_turbine_costs_brake_power() -> None:
    good = _turbo(turbine_efficiency=0.85)
    poor = _turbo(turbine_efficiency=0.55)
    assert poor.exhaust_pressure_Pa > good.exhaust_pressure_Pa
    assert poor.pmep_Pa > good.pmep_Pa
    assert poor.brake_power_W < good.brake_power_W


def test_a_well_matched_turbo_can_still_gain_from_gas_exchange() -> None:
    # When manifold pressure exceeds exhaust back-pressure the gas exchange
    # helps the piston, which is exactly why boosted engines pump positively.
    manifold = 1.8e5
    r = _turbo(intake_pressure_Pa=manifold)
    assert r.exhaust_pressure_Pa < manifold
    assert r.pmep_Pa < 0.0                     # negative PMEP == pumping gain


def test_boost_still_beats_natural_aspiration() -> None:
    na = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline"))
    boosted = _turbo()
    assert boosted.brake_power_W > na.brake_power_W
    assert boosted.trapped_mass_kg > na.trapped_mass_kg


def test_naturally_aspirated_and_supercharged_are_untouched() -> None:
    # The turbine model must only fire for turbos; everything else keeps the
    # exhaust pressure the caller asked for.
    na = simulate_piston_cycle(PistonCycleInputs(fuel="gasoline", exhaust_pressure_Pa=1.1e5))
    sc = simulate_piston_cycle(PistonCycleInputs(
        fuel="gasoline", aspiration="supercharged",
        intake_pressure_Pa=1.8e5, exhaust_pressure_Pa=1.1e5,
    ))
    for r in (na, sc):
        assert r.exhaust_pressure_Pa == pytest.approx(1.1e5)
        assert r.turbine_pressure_ratio is None
        assert r.boost_sustainable is True
    assert na.compressor_power_W == 0.0


def test_an_unboosted_turbo_selection_costs_nothing() -> None:
    # aspiration="turbocharged" at atmospheric manifold pressure is not boosted,
    # so there is no compressor work and no turbine to drive.
    r = simulate_piston_cycle(PistonCycleInputs(
        fuel="gasoline", aspiration="turbocharged", intake_pressure_Pa=1.0e5,
    ))
    assert r.compressor_power_W == 0.0
    assert r.turbine_pressure_ratio is None
    assert r.pmep_Pa == pytest.approx(0.0, abs=1e-6)


def test_back_pressure_composes_with_exhaust_restriction() -> None:
    # A restrictive system raises the pressure downstream of the turbine, and
    # the turbine's expansion then sits on top of that.
    from app.engine_core.piston.valvetrain import ValveGeometry, ValveTiming
    free = _turbo(valve_timing=ValveTiming(),
                  valve_geometry=ValveGeometry(exhaust_restriction=0.0))
    blocked = _turbo(valve_timing=ValveTiming(),
                     valve_geometry=ValveGeometry(exhaust_restriction=4.0))
    assert blocked.exhaust_pressure_Pa > free.exhaust_pressure_Pa
    assert blocked.brake_power_W < free.brake_power_W


def test_the_first_law_is_unaffected_by_the_turbine() -> None:
    # Back-pressure is a gas-exchange term; it must not disturb the closed-cycle
    # energy balance.
    r = _turbo(intake_pressure_Pa=2.4e5)
    assert abs(r.energy_residual_J) < 1e-6
