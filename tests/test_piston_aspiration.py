"""PistonLab Day 6 — aspiration (naturally aspirated / turbo / supercharged).

Boost raises the manifold pressure, packs in a denser charge, and lifts IMEP
and power. The difference between turbo and supercharger is who pays: a
supercharger is belt-driven and its compression work comes straight out of
brake power; a turbo (first cut) is driven by waste exhaust energy and costs
the crank nothing.
"""

from __future__ import annotations

import pytest

from app.engine_core.piston import (
    PistonCycleInputs,
    simulate_piston_cycle,
    supercharger_power_W,
)


# ---------------------------------------------------------------------------
# Supercharger compression power in isolation
# ---------------------------------------------------------------------------


def test_supercharger_power_zero_without_boost() -> None:
    assert supercharger_power_W(0.05, 300.0, pressure_ratio=1.0, efficiency=0.65) == 0.0
    assert supercharger_power_W(0.0, 300.0, pressure_ratio=2.0, efficiency=0.65) == 0.0


def test_supercharger_power_rises_with_boost_and_flow() -> None:
    base = supercharger_power_W(0.05, 300.0, 1.5, 0.65)
    more_boost = supercharger_power_W(0.05, 300.0, 2.2, 0.65)
    more_flow = supercharger_power_W(0.10, 300.0, 1.5, 0.65)
    assert more_boost > base > 0.0
    assert more_flow == pytest.approx(2.0 * base, rel=1e-9)


def test_supercharger_efficiency_validated() -> None:
    with pytest.raises(ValueError):
        supercharger_power_W(0.05, 300.0, 1.5, efficiency=0.0)
    with pytest.raises(ValueError):
        supercharger_power_W(0.05, 300.0, 1.5, efficiency=1.5)


# ---------------------------------------------------------------------------
# Aspiration on the full cycle
# ---------------------------------------------------------------------------


def test_boost_raises_imep_and_power_over_na() -> None:
    na = simulate_piston_cycle(PistonCycleInputs())
    boosted = simulate_piston_cycle(PistonCycleInputs(
        intake_pressure_Pa=1.8e5, aspiration="turbocharged"))
    assert boosted.imep_Pa > na.imep_Pa
    assert boosted.indicated_power_W > na.indicated_power_W
    assert boosted.brake_power_W > na.brake_power_W
    assert boosted.trapped_mass_kg > na.trapped_mass_kg     # denser charge


def test_supercharger_debits_brake_but_turbo_does_not() -> None:
    common = dict(intake_pressure_Pa=1.8e5, exhaust_pressure_Pa=1.2e5)
    turbo = simulate_piston_cycle(PistonCycleInputs(aspiration="turbocharged", **common))
    sc = simulate_piston_cycle(PistonCycleInputs(aspiration="supercharged", **common))
    # Same indicated work (same trapped charge), but the supercharger's
    # parasitic load lowers its brake power by exactly that power.
    assert turbo.supercharger_power_W == 0.0
    assert sc.supercharger_power_W > 0.0
    assert sc.indicated_power_W == pytest.approx(turbo.indicated_power_W, rel=1e-9)
    assert sc.brake_power_W < turbo.brake_power_W
    assert turbo.brake_power_W - sc.brake_power_W == pytest.approx(
        sc.supercharger_power_W, rel=1e-6
    )


def test_supercharger_lowers_brake_efficiency_vs_turbo() -> None:
    common = dict(intake_pressure_Pa=1.8e5, exhaust_pressure_Pa=1.2e5)
    turbo = simulate_piston_cycle(PistonCycleInputs(aspiration="turbocharged", **common))
    sc = simulate_piston_cycle(PistonCycleInputs(aspiration="supercharged", **common))
    assert sc.brake_thermal_efficiency < turbo.brake_thermal_efficiency
    assert sc.bsfc_g_per_kWh > turbo.bsfc_g_per_kWh
    assert sc.mechanical_efficiency < turbo.mechanical_efficiency


def test_boost_gauge_pressure_reported() -> None:
    r = simulate_piston_cycle(PistonCycleInputs(
        intake_pressure_Pa=1.8e5, ambient_pressure_Pa=1.0e5, aspiration="turbocharged"))
    assert r.boost_pressure_Pa == pytest.approx(0.8e5, rel=1e-9)
    assert r.aspiration == "turbocharged"


def test_na_default_has_no_supercharger_load() -> None:
    r = simulate_piston_cycle(PistonCycleInputs())
    assert r.aspiration == "naturally_aspirated"
    assert r.supercharger_power_W == 0.0


def test_tighter_supercharger_efficiency_costs_more() -> None:
    common = dict(intake_pressure_Pa=2.0e5, aspiration="supercharged")
    good = simulate_piston_cycle(PistonCycleInputs(supercharger_efficiency=0.75, **common))
    poor = simulate_piston_cycle(PistonCycleInputs(supercharger_efficiency=0.50, **common))
    # A less efficient blower needs more crank power for the same boost.
    assert poor.supercharger_power_W > good.supercharger_power_W
    assert poor.brake_power_W < good.brake_power_W


def test_aspiration_inputs_validated() -> None:
    with pytest.raises(ValueError):
        PistonCycleInputs(aspiration="rocket")
    with pytest.raises(ValueError):
        PistonCycleInputs(supercharger_efficiency=0.0)
    with pytest.raises(ValueError):
        PistonCycleInputs(ambient_pressure_Pa=-1.0)
