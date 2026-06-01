"""Shared compressor-bleed and HP-turbine cooling-air accounting.

Every gas-turbine engine in PropulsionLab (turbojet, turbofan, turboprop)
extracts air at the HP-compressor exit for two purposes:

* **Customer / overboard bleed** — air taken for the airframe (ECS, anti-ice)
  or simply spilled. It leaves the engine at the HPC exit and never reaches
  the combustor or turbine.
* **HP-turbine cooling air** — air routed *around* the combustor and
  re-introduced at the turbine inlet to cool the blades. It bypasses heat
  addition, so when it mixes back in it depresses the effective turbine-inlet
  stagnation temperature below the configured Tt4.

This module centralises that mass-and-energy bookkeeping so the three engine
solvers share one implementation instead of each carrying its own copy. The
fractions are taken relative to a *reference* compressor-exit air flow, which
is the engine inlet air for a turbojet / turboprop and the **core** air for a
turbofan.

The mixing is a constant-pressure stagnation-enthalpy balance:

    Tt_mixed = (m_hot·cp_gas·Tt_hot + m_cool·cp_air·Tt_cool)
               / (m_hot·cp_gas      + m_cool·cp_air)

When the cooling fraction is zero this reduces exactly to ``Tt_mixed = Tt_hot``
(both numerator and denominator collapse to ``m_hot·cp_gas``), so the no-bleed
path is numerically identical to the pre-bleed model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.engine_core.constants import cp_air, cp_gas
from app.engine_core.types import CycleCalculationError, StationState

# Combined bleed + cooling must leave a viable combustor flow.
MAX_SECONDARY_FRACTION = 0.95


@dataclass(slots=True, frozen=True)
class SecondaryAirResult:
    """Mass + energy result of applying bleed and cooling air."""

    turbine_inlet_state: StationState
    combustor_air_kg_s: float
    cooling_air_kg_s: float
    hpt_inlet_kg_s: float
    gas_mass_flow_ratio: float  # hpt_inlet / reference_air
    fuel_flow_kg_s: float
    metadata: dict[str, float] = field(default_factory=dict)


def apply_bleed_and_cooling(
    reference_air_kg_s: float,
    compressor_exit_state: StationState,
    combustor_exit_state: StationState,
    fuel_air_ratio: float,
    bleed_fraction: float,
    cooling_fraction: float,
) -> SecondaryAirResult:
    """Apply HPC-exit bleed and HPT cooling air to a combustor exit.

    ``reference_air_kg_s`` is the compressor-exit air flow the fractions apply
    to (engine inlet air for turbojet/turboprop, core air for turbofan).
    Returns the cooling-mixed turbine-inlet station plus the mass-flow figures
    the turbine, nozzle, and performance bookkeeping need.
    """

    if not 0.0 <= bleed_fraction <= 0.25:
        raise CycleCalculationError("Bleed fraction must be in [0, 0.25].")
    if not 0.0 <= cooling_fraction <= 0.30:
        raise CycleCalculationError("Cooling fraction must be in [0, 0.30].")
    if bleed_fraction + cooling_fraction >= MAX_SECONDARY_FRACTION:
        raise CycleCalculationError(
            "Total bleed + cooling fraction must be < 0.95 to leave a viable "
            "combustor flow."
        )
    if reference_air_kg_s <= 0.0:
        raise CycleCalculationError("Reference air mass flow must be positive.")

    combustor_air_kg_s = reference_air_kg_s * (1.0 - bleed_fraction - cooling_fraction)
    cooling_air_kg_s = reference_air_kg_s * cooling_fraction
    hot_gas_kg_s = combustor_air_kg_s * (1.0 + fuel_air_ratio)
    hpt_inlet_kg_s = hot_gas_kg_s + cooling_air_kg_s

    Tt_hot = combustor_exit_state.stagnation_temperature_K
    Tt_cool = compressor_exit_state.stagnation_temperature_K
    Tt_mixed = (
        hot_gas_kg_s * cp_gas * Tt_hot + cooling_air_kg_s * cp_air * Tt_cool
    ) / (hot_gas_kg_s * cp_gas + cooling_air_kg_s * cp_air)

    if cooling_fraction > 0.0:
        turbine_inlet_state = StationState(
            station=combustor_exit_state.station,
            name="Combustor exit (after HPT cooling mix)",
            stagnation_temperature_K=Tt_mixed,
            stagnation_pressure_Pa=combustor_exit_state.stagnation_pressure_Pa,
            notes=[
                *combustor_exit_state.notes,
                (
                    f"Mixed with {cooling_fraction:.1%} HPC cooling air: "
                    f"Tt dropped from {Tt_hot:.0f} K to {Tt_mixed:.0f} K."
                ),
            ],
        )
    else:
        turbine_inlet_state = combustor_exit_state

    return SecondaryAirResult(
        turbine_inlet_state=turbine_inlet_state,
        combustor_air_kg_s=combustor_air_kg_s,
        cooling_air_kg_s=cooling_air_kg_s,
        hpt_inlet_kg_s=hpt_inlet_kg_s,
        gas_mass_flow_ratio=hpt_inlet_kg_s / reference_air_kg_s,
        fuel_flow_kg_s=fuel_air_ratio * combustor_air_kg_s,
        metadata={
            "bleed_fraction": bleed_fraction,
            "cooling_fraction": cooling_fraction,
            "hpt_inlet_stagnation_temperature_K": Tt_mixed,
        },
    )
