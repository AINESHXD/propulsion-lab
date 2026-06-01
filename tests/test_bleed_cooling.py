"""Tests for HPC-exit bleed and HPT-inlet cooling air.

The model:

* ``bleed_fraction_hpc_exit`` is customer / overboard air — it leaves the
  engine at HPC exit and never sees the combustor or turbine.
* ``cooling_fraction_hpt_inlet`` is HPT cooling air — taken at HPC exit,
  routed around the combustor, then re-introduced at the turbine inlet and
  mixed with the hot combustion gas.

These tests pin the five behaviours that matter:

1. Both fractions default to zero and the cycle is bit-identical to the
   pre-bleed baseline.
2. Customer bleed reduces the actual fuel flow because the combustor sees
   less air (and TSFC suffers).
3. HPT cooling air drops the effective Tt4 the turbine sees below the
   configured turbine inlet temperature.
4. Asking for more than 95% combined bleed + cooling raises a clean
   CycleCalculationError instead of producing silent garbage.
5. Combining bleed/cooling with afterburning is rejected for v1 scope.
"""

from __future__ import annotations

import pytest

from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import CycleCalculationError, TurbojetCycleInputs


@pytest.fixture(scope="module")
def baseline_cycle() -> dict:
    """The pre-bleed baseline cycle, shared across tests that need it."""

    return simulate_turbojet_cycle(TurbojetCycleInputs())


def test_zero_bleed_zero_cooling_reproduces_baseline(baseline_cycle) -> None:
    """Defaults must be exactly bit-equivalent to the pre-bleed cycle."""

    baseline = baseline_cycle
    with_zeros = simulate_turbojet_cycle(
        TurbojetCycleInputs(
            bleed_fraction_hpc_exit=0.0,
            cooling_fraction_hpt_inlet=0.0,
        )
    )
    # Top-line numbers identical to floating-point precision.
    assert baseline["thrust_N"] == pytest.approx(with_zeros["thrust_N"], rel=1e-12)
    assert baseline["fuel_flow_kg_s"] == pytest.approx(
        with_zeros["fuel_flow_kg_s"], rel=1e-12
    )
    assert baseline["TSFC_kg_per_N_s"] == pytest.approx(
        with_zeros["TSFC_kg_per_N_s"], rel=1e-12
    )
    # Surfaced new fields must be coherent with a "no bleed" cycle.
    assert with_zeros["bleed_fraction_hpc_exit"] == 0.0
    assert with_zeros["cooling_fraction_hpt_inlet"] == 0.0
    assert with_zeros["combustor_air_mass_flow_kg_s"] == pytest.approx(
        TurbojetCycleInputs().mass_flow_air_kg_s, rel=1e-12
    )
    # HPT inlet Tt should equal Tt4 when no cooling is mixed in.
    assert with_zeros["hpt_inlet_stagnation_temperature_K"] == pytest.approx(
        TurbojetCycleInputs().turbine_inlet_temperature_K, rel=1e-12
    )


def test_customer_bleed_reduces_combustor_air_and_fuel_flow(baseline_cycle) -> None:
    """15% customer bleed should reduce combustor air by 15% and reduce fuel."""

    inputs = TurbojetCycleInputs(bleed_fraction_hpc_exit=0.15)
    bled = simulate_turbojet_cycle(inputs)
    baseline = baseline_cycle

    # Combustor flow exactly (1 - bleed) of the inlet air.
    expected_combustor_air = inputs.mass_flow_air_kg_s * 0.85
    assert bled["combustor_air_mass_flow_kg_s"] == pytest.approx(
        expected_combustor_air, rel=1e-9
    )
    # Fuel flow drops because we're burning less air at the same FAR.
    assert bled["fuel_flow_kg_s"] < baseline["fuel_flow_kg_s"]
    # Customer bleed degrades TSFC (less thrust per kg fuel — but more so per
    # unit air through the inlet).
    assert bled["TSFC_kg_per_N_s"] > baseline["TSFC_kg_per_N_s"]


def test_cooling_air_drops_effective_hpt_inlet_temperature() -> None:
    """HPT cooling air mixes back at Tt3, depressing the turbine inlet Tt."""

    Tt4 = 1700.0
    inputs = TurbojetCycleInputs(
        turbine_inlet_temperature_K=Tt4,
        cooling_fraction_hpt_inlet=0.15,
    )
    cooled = simulate_turbojet_cycle(inputs)

    # Effective HPT inlet Tt must be strictly less than the configured Tt4.
    assert cooled["hpt_inlet_stagnation_temperature_K"] < Tt4
    # And not absurdly low: cooling air comes from compressor exit, which is
    # well above ambient, so the mix shouldn't drop more than ~250 K for
    # a 15% cooling fraction at this Tt4.
    assert cooled["hpt_inlet_stagnation_temperature_K"] > Tt4 - 250.0


def test_excessive_bleed_plus_cooling_raises() -> None:
    """Asking for ≥95% combined bleed + cooling must fail cleanly."""

    with pytest.raises(CycleCalculationError):
        simulate_turbojet_cycle(
            TurbojetCycleInputs(
                bleed_fraction_hpc_exit=0.5,
                cooling_fraction_hpt_inlet=0.5,
            )
        )


def test_bleed_or_cooling_with_afterburner_raises() -> None:
    """V1 explicitly rejects bleed + afterburner combinations."""

    with pytest.raises(CycleCalculationError):
        simulate_turbojet_cycle(
            TurbojetCycleInputs(
                engine_variant="afterburning_turbojet",
                afterburner_exit_temperature_K=1800.0,
                bleed_fraction_hpc_exit=0.05,
            )
        )


# ---------------------------------------------------------------------------
# Day 3 — bleed + cooling generalised to turbofan and turboprop via the shared
# secondary_air helper. Same four invariants, per engine family.
# ---------------------------------------------------------------------------

from app.engine_core.turbofan import simulate_turbofan_cycle, TurbofanCycleInputs
from app.engine_core.turboprop import simulate_turboprop_cycle, TurbopropCycleInputs


def test_turbofan_zero_bleed_reproduces_baseline() -> None:
    base = simulate_turbofan_cycle(TurbofanCycleInputs())
    zeros = simulate_turbofan_cycle(
        TurbofanCycleInputs(bleed_fraction_hpc_exit=0.0, cooling_fraction_hpt_inlet=0.0)
    )
    assert base["thrust_N"] == pytest.approx(zeros["thrust_N"], rel=1e-12)
    assert base["fuel_flow_kg_s"] == pytest.approx(zeros["fuel_flow_kg_s"], rel=1e-12)


def test_turbofan_customer_bleed_reduces_fuel_flow() -> None:
    base = simulate_turbofan_cycle(TurbofanCycleInputs())
    bled = simulate_turbofan_cycle(TurbofanCycleInputs(bleed_fraction_hpc_exit=0.12))
    # Less core air through the combustor -> less fuel burned.
    assert bled["fuel_flow_kg_s"] < base["fuel_flow_kg_s"]
    assert bled["extra"]["combustor_air_mass_flow_kg_s"] < base["extra"]["core_mass_flow_kg_s"]


def test_turbofan_cooling_drops_hpt_inlet_temperature() -> None:
    Tt4 = 1700.0
    cooled = simulate_turbofan_cycle(
        TurbofanCycleInputs(turbine_inlet_temperature_K=Tt4, cooling_fraction_hpt_inlet=0.15)
    )
    assert cooled["extra"]["hpt_inlet_stagnation_temperature_K"] < Tt4
    assert cooled["extra"]["hpt_inlet_stagnation_temperature_K"] > Tt4 - 300.0


def test_turboprop_zero_bleed_reproduces_baseline() -> None:
    base = simulate_turboprop_cycle(TurbopropCycleInputs())
    zeros = simulate_turboprop_cycle(
        TurbopropCycleInputs(bleed_fraction_hpc_exit=0.0, cooling_fraction_hpt_inlet=0.0)
    )
    assert base["thrust_N"] == pytest.approx(zeros["thrust_N"], rel=1e-12)
    assert base["shaft_power_W"] == pytest.approx(zeros["shaft_power_W"], rel=1e-12)


def test_turboprop_bleed_reduces_shaft_power_and_fuel() -> None:
    base = simulate_turboprop_cycle(TurbopropCycleInputs())
    bled = simulate_turboprop_cycle(TurbopropCycleInputs(bleed_fraction_hpc_exit=0.12))
    # Less gas through the power turbine -> less shaft power; less combustor
    # air -> less fuel.
    assert bled["shaft_power_W"] < base["shaft_power_W"]
    assert bled["fuel_flow_kg_s"] < base["fuel_flow_kg_s"]


def test_turbofan_excessive_secondary_air_raises() -> None:
    # Exceeding the per-stream cap (bleed > 0.25) must fail cleanly.
    with pytest.raises(CycleCalculationError):
        simulate_turbofan_cycle(
            TurbofanCycleInputs(bleed_fraction_hpc_exit=0.5, cooling_fraction_hpt_inlet=0.5)
        )
