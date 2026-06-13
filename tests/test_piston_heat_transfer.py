"""PistonLab Day 3 — in-cylinder wall heat transfer (Woschni).

The adiabatic closed cycle overstates efficiency; a real engine loses a large
share of the fuel energy to the cylinder walls. These tests check the Woschni
heat-transfer model in isolation and its effect on the full cycle: efficiency
must fall monotonically as the heat-transfer multiplier rises, and the energy
balance (fuel = work + wall loss + change in internal energy) must close.
"""

from __future__ import annotations

import pytest

from app.engine_core.piston import PistonCycleInputs, simulate_piston_cycle
from app.engine_core.piston.heat_transfer import (
    wall_surface_area_m2,
    woschni_coefficient,
    woschni_velocity,
)

_R, _GAMMA = 287.0, 1.35
_CV = _R / (_GAMMA - 1.0)


# ---------------------------------------------------------------------------
# Woschni model in isolation
# ---------------------------------------------------------------------------


def test_wall_area_grows_with_volume() -> None:
    bore = 0.086
    small = wall_surface_area_m2(5.0e-5, bore)
    large = wall_surface_area_m2(5.0e-4, bore)
    assert large > small
    assert small > 0.0


def test_woschni_coefficient_is_positive_and_sane() -> None:
    # Mid-compression-ish state: a few MPa, ~1500 K, a few m/s.
    h = woschni_coefficient(bore_m=0.086, pressure_Pa=3.0e6,
                            temperature_K=1500.0, gas_velocity_m_s=10.0)
    # Woschni coefficients for a running engine are hundreds to low thousands.
    assert 100.0 < h < 5000.0


def test_woschni_coefficient_zero_for_zero_velocity() -> None:
    assert woschni_coefficient(0.086, 3.0e6, 1500.0, 0.0) == 0.0


def test_woschni_velocity_combustion_term_raises_velocity() -> None:
    args = dict(mean_piston_speed_m_s=12.0, pressure_Pa=6.0e6,
                motored_pressure_Pa=3.0e6, displacement_m3=5.0e-4,
                ref_temperature_K=330.0, ref_pressure_Pa=1.0e5, ref_volume_m3=5.5e-4)
    motoring = woschni_velocity(**args, burning=False)
    burning = woschni_velocity(**args, burning=True)
    # During combustion (p above motored) the velocity is higher.
    assert burning > motoring
    assert motoring == pytest.approx(2.28 * 12.0, rel=1e-9)


# ---------------------------------------------------------------------------
# Effect on the full cycle
# ---------------------------------------------------------------------------


def test_zero_multiplier_is_adiabatic() -> None:
    r = simulate_piston_cycle(PistonCycleInputs(wall_heat_transfer_multiplier=0.0))
    assert r.wall_heat_loss_J == 0.0
    # Matches the adiabatic closed-cycle efficiency (no wall path at all).
    assert r.thermal_efficiency > 0.5


def test_wall_loss_lowers_efficiency_monotonically() -> None:
    effs = [
        simulate_piston_cycle(
            PistonCycleInputs(wall_heat_transfer_multiplier=m)
        ).thermal_efficiency
        for m in (0.0, 0.5, 1.0, 2.0)
    ]
    assert effs == sorted(effs, reverse=True)        # strictly falling
    assert all(a > b for a, b in zip(effs, effs[1:]))


def test_wall_loss_lowers_peak_temperature() -> None:
    adiabatic = simulate_piston_cycle(PistonCycleInputs(wall_heat_transfer_multiplier=0.0))
    cooled = simulate_piston_cycle(PistonCycleInputs(wall_heat_transfer_multiplier=1.0))
    assert cooled.peak_temperature_K < adiabatic.peak_temperature_K
    assert cooled.wall_heat_loss_J > 0.0


def test_energy_balance_closes_with_wall_loss() -> None:
    inp = PistonCycleInputs(wall_heat_transfer_multiplier=1.0)
    r = simulate_piston_cycle(inp)
    # Residual of  work == heat_in - wall_loss - delta_U  is machine-precision.
    assert abs(r.energy_residual_J) < 1e-6
    # And the explicit balance: fuel = work + wall loss + change in internal energy.
    delta_u = r.trapped_mass_kg * _CV * (
        r.trace[-1]["temperature_K"] - r.trace[0]["temperature_K"]
    )
    assert r.heat_released_J == pytest.approx(
        r.indicated_work_J + r.wall_heat_loss_J + delta_u, rel=1e-6
    )


def test_hotter_wall_loses_less_heat() -> None:
    cool_wall = simulate_piston_cycle(PistonCycleInputs(wall_temperature_K=350.0))
    hot_wall = simulate_piston_cycle(PistonCycleInputs(wall_temperature_K=550.0))
    # A hotter wall means a smaller gas-to-wall delta-T, so less heat is lost
    # and efficiency is (slightly) higher.
    assert hot_wall.wall_heat_loss_J < cool_wall.wall_heat_loss_J
    assert hot_wall.thermal_efficiency > cool_wall.thermal_efficiency


def test_negative_multiplier_rejected() -> None:
    with pytest.raises(ValueError):
        PistonCycleInputs(wall_heat_transfer_multiplier=-0.5)
    with pytest.raises(ValueError):
        PistonCycleInputs(wall_temperature_K=0.0)
