"""PistonLab Day 5 — the part-load pumping loop.

A throttled spark-ignition engine pulls the intake stroke against a partial
vacuum and pushes the exhaust stroke against atmosphere, so the gas-exchange
loop does net-negative work. That pumping loss is the main reason an SI engine
is so inefficient at part throttle (city driving). These tests check the
pumping MEP, the net-vs-gross indicated split, and the part-load efficiency
penalty.
"""

from __future__ import annotations

import pytest

from app.engine_core.piston import PistonCycleInputs, simulate_piston_cycle


def test_wide_open_throttle_has_no_pumping_loss() -> None:
    # Intake == exhaust (default): the pumping loop vanishes and net == gross.
    r = simulate_piston_cycle(PistonCycleInputs())
    assert r.pmep_Pa == pytest.approx(0.0, abs=1.0)
    assert r.pumping_work_J == pytest.approx(0.0, abs=1e-9)
    assert r.net_indicated_work_J == pytest.approx(r.indicated_work_J, rel=1e-12)


def test_pmep_equals_exhaust_minus_intake() -> None:
    r = simulate_piston_cycle(PistonCycleInputs(
        intake_pressure_Pa=0.5e5, exhaust_pressure_Pa=1.05e5))
    assert r.pmep_Pa == pytest.approx(1.05e5 - 0.5e5, rel=1e-9)
    assert r.net_imep_Pa == pytest.approx(r.imep_Pa - r.pmep_Pa, rel=1e-9)
    assert r.net_indicated_work_J < r.indicated_work_J     # pumping subtracts


def test_closing_throttle_raises_pumping_loss() -> None:
    pmeps = [
        simulate_piston_cycle(PistonCycleInputs(
            intake_pressure_Pa=p, exhaust_pressure_Pa=1.05e5)).pmep_Pa
        for p in (1.0e5, 0.7e5, 0.5e5, 0.35e5)
    ]
    assert pmeps == sorted(pmeps)                           # monotonically rising
    assert all(b > a for a, b in zip(pmeps, pmeps[1:]))


def test_throttling_reduces_brake_efficiency() -> None:
    wot = simulate_piston_cycle(PistonCycleInputs(
        intake_pressure_Pa=1.0e5, exhaust_pressure_Pa=1.05e5))
    part = simulate_piston_cycle(PistonCycleInputs(
        intake_pressure_Pa=0.4e5, exhaust_pressure_Pa=1.05e5))
    # The pumping loss plus the fixed friction is a bigger share of a smaller
    # output at part load, so brake thermal efficiency falls.
    assert part.brake_thermal_efficiency < wot.brake_thermal_efficiency
    assert part.brake_power_W < wot.brake_power_W
    assert part.bsfc_g_per_kWh > wot.bsfc_g_per_kWh        # drinks more per kWh


def test_throttling_reduces_trapped_mass_and_gross_work() -> None:
    wot = simulate_piston_cycle(PistonCycleInputs(intake_pressure_Pa=1.0e5))
    part = simulate_piston_cycle(PistonCycleInputs(intake_pressure_Pa=0.5e5))
    # Less manifold pressure -> less dense charge -> less mass and gross work.
    assert part.trapped_mass_kg < wot.trapped_mass_kg
    assert part.indicated_work_J < wot.indicated_work_J


def test_boosted_intake_gives_pumping_gain() -> None:
    # Intake above exhaust (a supercharger/turbo, previewing Day 6) makes the
    # pumping loop do positive work: PMEP is negative, net > gross.
    r = simulate_piston_cycle(PistonCycleInputs(
        intake_pressure_Pa=1.6e5, exhaust_pressure_Pa=1.1e5))
    assert r.pmep_Pa < 0.0
    assert r.net_indicated_work_J > r.indicated_work_J


def test_brake_now_accounts_for_pumping() -> None:
    # With a pumping loss present, BMEP = net IMEP - FMEP (not gross - FMEP).
    r = simulate_piston_cycle(PistonCycleInputs(
        intake_pressure_Pa=0.5e5, exhaust_pressure_Pa=1.05e5))
    assert r.bmep_Pa == pytest.approx(r.net_imep_Pa - r.fmep_Pa, rel=1e-9)
    assert r.bmep_Pa < r.net_imep_Pa < r.imep_Pa


def test_pressures_validated() -> None:
    with pytest.raises(ValueError):
        PistonCycleInputs(exhaust_pressure_Pa=0.0)
    with pytest.raises(ValueError):
        PistonCycleInputs(intake_pressure_Pa=-1.0)
