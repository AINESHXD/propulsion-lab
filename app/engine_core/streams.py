"""Shared stream-flow utilities for non-turbojet cycle solvers.

All four advanced engine families (turbofan / turboprop / ramjet / scramjet)
expand one or more gas streams through convergent nozzles, partition thrust
between momentum and pressure components, and compute thermal / propulsive /
overall efficiencies from the same energy bookkeeping. This module centralises
that physics so the per-engine solvers stay focused on their unique stations
and warnings.

Implementation notes
--------------------
* Convergent-only nozzle (no diverging section). Choked output reports M=1 at
  the throat; supersonic exit is not modelled. This matches the existing
  educational fidelity throughout PropulsionLab.
* Stream gas constant is configurable to allow air-side (R_air, gamma_air) and
  combustion-product (R ~= R_air, gamma_gas, cp_gas) streams in the same
  function. Real products have R closer to ~290 J/kg/K; we follow the rest of
  the code base in using R_air for both streams as a deliberate educational
  approximation.
* Efficiency definitions follow Hill & Peterson and Mattingly. The
  ``thermal_efficiency`` measure here is the *available jet power*
  (kinetic energy delta + pressure-thrust power) divided by fuel chemical
  power. The ``propulsive_efficiency`` measure is thrust * V0 divided by
  available jet power. Overall is the product.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.engine_core.constants import R_air
from app.engine_core.gas_properties import (
    normal_shock_pressure_ratio,
    normal_shock_stagnation_pressure_ratio,
    subsonic_mach_from_pressure_ratio,
    supersonic_mach_from_area_ratio,
)
from app.engine_core.types import CycleCalculationError, StationState


@dataclass(slots=True, frozen=True)
class NozzleStreamResult:
    """Convergent nozzle exit summary for a single gas stream."""

    state: StationState
    exit_velocity_m_s: float
    pressure_thrust_N: float
    momentum_thrust_N: float
    choked: bool
    exit_area_m2: float
    exit_pressure_Pa: float
    exit_temperature_K: float
    exit_mach: float
    metadata: dict[str, float | bool | str] = field(default_factory=dict)


def expand_nozzle_stream(
    inlet_state: StationState,
    ambient_pressure_Pa: float,
    mass_flow_in_kg_s: float,
    fuel_air_ratio: float,
    freestream_velocity_m_s: float,
    nozzle_efficiency: float,
    station: int,
    name: str,
    gamma: float,
    cp: float,
    gas_constant: float = R_air,
    include_pressure_thrust: bool = True,
    divergent_area_ratio: float = 1.0,
) -> NozzleStreamResult:
    """Expand a single stream through a convergent or convergent-divergent nozzle.

    With ``divergent_area_ratio == 1.0`` (default) this is a convergent nozzle:
    nozzle efficiency is applied to ideal kinetic energy and choking is detected
    through the critical-pressure ratio.

    With ``divergent_area_ratio > 1.0`` and a choked throat, a divergent section
    is present: the supersonic exit Mach is found from the isentropic
    area-Mach relation, and the gas expands supersonically to that Mach. This
    is what gives ramjet / scramjet / rocket-class nozzles a real supersonic
    exit instead of being capped at M = 1.
    """

    if inlet_state.stagnation_pressure_Pa <= ambient_pressure_Pa:
        raise CycleCalculationError(
            f"{name}: inlet stagnation pressure must exceed ambient pressure."
        )
    if mass_flow_in_kg_s <= 0.0:
        raise CycleCalculationError(f"{name}: nozzle mass flow must be positive.")
    if not 0.0 < nozzle_efficiency <= 1.0:
        raise CycleCalculationError(
            f"{name}: nozzle efficiency must be in (0, 1]."
        )
    if divergent_area_ratio < 1.0:
        raise CycleCalculationError(
            f"{name}: divergent area ratio must be >= 1."
        )

    critical_pressure_Pa = inlet_state.stagnation_pressure_Pa * (
        2.0 / (gamma + 1.0)
    ) ** (gamma / (gamma - 1.0))
    choked = critical_pressure_Pa > ambient_pressure_Pa

    shock_in_nozzle = False
    if choked and divergent_area_ratio > 1.0:
        # ---- Convergent-divergent nozzle -----------------------------------
        # Supersonic exit Mach implied by the area ratio, and the isentropic
        # supersonic exit static pressure.
        supersonic_mach = supersonic_mach_from_area_ratio(divergent_area_ratio, gamma)
        temp_ratio_super = 1.0 + (gamma - 1.0) / 2.0 * supersonic_mach**2
        pe_supersonic_Pa = inlet_state.stagnation_pressure_Pa / temp_ratio_super ** (
            gamma / (gamma - 1.0)
        )
        # Back-pressure at which a normal shock would sit exactly at the exit
        # plane. If ambient exceeds this, the shock moves UP into the divergent
        # section: the nozzle is heavily over-expanded and the exit is subsonic.
        pe_shock_at_exit_Pa = pe_supersonic_Pa * normal_shock_pressure_ratio(
            supersonic_mach, gamma
        )

        if ambient_pressure_Pa > pe_shock_at_exit_Pa:
            # ---- Normal shock inside the divergent section -----------------
            # The supersonic-exit assumption is invalid. A normal shock stands
            # in the divergent section, dropping the flow to subsonic with a
            # stagnation-pressure loss; downstream it diffuses to the ambient
            # back-pressure. Reduced-order model: apply the shock's total-
            # pressure loss (using the area-ratio supersonic Mach as the shock
            # strength), then take the SUBSONIC root that exits at ambient.
            shock_in_nozzle = True
            pt_after_shock_Pa = inlet_state.stagnation_pressure_Pa * (
                normal_shock_stagnation_pressure_ratio(supersonic_mach, gamma)
            )
            exit_pressure_Pa = ambient_pressure_Pa
            exit_mach = subsonic_mach_from_pressure_ratio(
                pt_after_shock_Pa / ambient_pressure_Pa, gamma
            )
            if exit_mach <= 1e-3:
                raise CycleCalculationError(
                    f"{name}: divergent area ratio is far too large for this "
                    f"pressure ratio — the post-shock flow cannot exit against "
                    f"ambient. Reduce the nozzle area ratio."
                )
            exit_temperature_K = inlet_state.stagnation_temperature_K / (
                1.0 + (gamma - 1.0) / 2.0 * exit_mach**2
            )
            exit_velocity_m_s = float(
                np.sqrt(nozzle_efficiency)
                * exit_mach
                * np.sqrt(gamma * gas_constant * exit_temperature_K)
            )
        else:
            # ---- Clean supersonic exit (full-flowing CD nozzle) ------------
            exit_temperature_ideal_K = (
                inlet_state.stagnation_temperature_K / temp_ratio_super
            )
            exit_pressure_Pa = pe_supersonic_Pa
            ideal_drop_K = inlet_state.stagnation_temperature_K - exit_temperature_ideal_K
            # Apply nozzle efficiency to the kinetic energy (same convention as
            # the subsonic branch); exit static pressure is set by geometry.
            exit_velocity_m_s = float(np.sqrt(2.0 * nozzle_efficiency * cp * ideal_drop_K))
            exit_temperature_K = inlet_state.stagnation_temperature_K - exit_velocity_m_s**2 / (
                2.0 * cp
            )
            exit_mach = exit_velocity_m_s / float(
                np.sqrt(gamma * gas_constant * exit_temperature_K)
            )
    elif choked:
        exit_pressure_Pa = critical_pressure_Pa
        exit_temperature_ideal_K = (
            inlet_state.stagnation_temperature_K * 2.0 / (gamma + 1.0)
        )
        exit_velocity_ideal_m_s = float(
            np.sqrt(gamma * gas_constant * exit_temperature_ideal_K)
        )
        exit_velocity_m_s = float(np.sqrt(nozzle_efficiency) * exit_velocity_ideal_m_s)
        exit_temperature_K = inlet_state.stagnation_temperature_K - exit_velocity_m_s**2 / (
            2.0 * cp
        )
        exit_mach = 1.0
    else:
        exit_pressure_Pa = ambient_pressure_Pa
        exit_temperature_isentropic_K = inlet_state.stagnation_temperature_K * (
            exit_pressure_Pa / inlet_state.stagnation_pressure_Pa
        ) ** ((gamma - 1.0) / gamma)
        available_drop_K = (
            inlet_state.stagnation_temperature_K - exit_temperature_isentropic_K
        )
        if available_drop_K <= 0.0:
            raise CycleCalculationError(
                f"{name}: no positive temperature drop available in nozzle."
            )
        exit_velocity_m_s = float(
            np.sqrt(2.0 * nozzle_efficiency * cp * available_drop_K)
        )
        exit_temperature_K = inlet_state.stagnation_temperature_K - exit_velocity_m_s**2 / (
            2.0 * cp
        )
        exit_mach = exit_velocity_m_s / float(
            np.sqrt(gamma * gas_constant * exit_temperature_K)
        )

    if exit_temperature_K <= 0.0:
        raise CycleCalculationError(f"{name}: exit static temperature is non-positive.")
    if exit_velocity_m_s <= 0.0:
        raise CycleCalculationError(f"{name}: exit velocity is non-positive.")

    mass_flow_out_kg_s = mass_flow_in_kg_s * (1.0 + fuel_air_ratio)
    exit_density_kg_m3 = exit_pressure_Pa / (gas_constant * exit_temperature_K)
    exit_area_m2 = mass_flow_out_kg_s / (exit_density_kg_m3 * exit_velocity_m_s)

    pressure_thrust_N = (
        (exit_pressure_Pa - ambient_pressure_Pa) * exit_area_m2
        if include_pressure_thrust
        else 0.0
    )
    momentum_thrust_N = mass_flow_out_kg_s * exit_velocity_m_s - (
        mass_flow_in_kg_s * freestream_velocity_m_s
    )

    if shock_in_nozzle:
        expansion_status = "Overexpanded (normal shock in nozzle)"
    elif abs(exit_pressure_Pa - ambient_pressure_Pa) / max(ambient_pressure_Pa, 1.0) < 0.03:
        expansion_status = "Ideally expanded approximately"
    elif exit_pressure_Pa > ambient_pressure_Pa:
        expansion_status = "Underexpanded"
    else:
        expansion_status = "Overexpanded"

    state = StationState(
        station=station,
        name=name,
        static_temperature_K=exit_temperature_K,
        static_pressure_Pa=exit_pressure_Pa,
        stagnation_temperature_K=inlet_state.stagnation_temperature_K,
        stagnation_pressure_Pa=inlet_state.stagnation_pressure_Pa,
        mach=exit_mach,
        velocity_m_s=exit_velocity_m_s,
        notes=[
            "Convergent-divergent nozzle: normal shock in divergent section "
            "(over-expanded, subsonic exit)."
            if shock_in_nozzle
            else "Choked convergent-divergent nozzle (supersonic exit)."
            if (choked and divergent_area_ratio > 1.0)
            else "Choked convergent nozzle."
            if choked
            else "Unchoked convergent nozzle."
        ],
    )

    return NozzleStreamResult(
        state=state,
        exit_velocity_m_s=exit_velocity_m_s,
        pressure_thrust_N=pressure_thrust_N,
        momentum_thrust_N=momentum_thrust_N,
        choked=choked,
        exit_area_m2=exit_area_m2,
        exit_pressure_Pa=exit_pressure_Pa,
        exit_temperature_K=exit_temperature_K,
        exit_mach=exit_mach,
        metadata={
            "expansion_status": expansion_status,
            "exit_density_kg_m3": exit_density_kg_m3,
            "shock_in_nozzle": shock_in_nozzle,
        },
    )


def compute_stream_efficiencies(
    thrust_N: float,
    freestream_velocity_m_s: float,
    fuel_flow_kg_s: float,
    fuel_heating_value_J_kg: float,
    jet_kinetic_power_change_W: float,
    pressure_thrust_power_W: float,
) -> dict[str, float]:
    """Estimate thermal / propulsive / overall efficiencies from energy balance.

    All three numbers are dimensionless and bounded to [0, 1] on output. The
    ``thermal`` number compares useful jet power to fuel chemical power. The
    ``propulsive`` number compares thrust * V0 to useful jet power. The
    ``overall`` number is the product (or zero if either input is undefined).
    """

    fuel_power_W = fuel_flow_kg_s * fuel_heating_value_J_kg
    useful_jet_power_W = jet_kinetic_power_change_W + pressure_thrust_power_W
    propulsive_power_W = thrust_N * freestream_velocity_m_s

    thermal = (
        useful_jet_power_W / fuel_power_W
        if fuel_power_W > 0.0 and useful_jet_power_W > 0.0
        else 0.0
    )
    propulsive = (
        propulsive_power_W / useful_jet_power_W
        if useful_jet_power_W > 0.0
        else 0.0
    )
    overall = (
        propulsive_power_W / fuel_power_W
        if fuel_power_W > 0.0
        else 0.0
    )
    # Clamp to [0, 1] so unphysical readings do not propagate to the dashboard.
    return {
        "thermal_efficiency_estimate": max(0.0, min(thermal, 1.0)),
        "propulsive_efficiency_estimate": max(0.0, min(propulsive, 1.0)),
        "overall_efficiency_estimate": max(0.0, min(overall, 1.0)),
    }


def station_table(*states: StationState) -> dict[int, dict[str, Any]]:
    """Build a JSON-ready station table keyed by station number.

    When the same station number appears twice (for example, a fan exit and a
    bypass duct entry that share station 13 in some texts), the *last* state in
    the sequence wins. Callers should pass states in the order they want to
    keep visible.
    """

    return {state.station: state.to_dict() for state in states}


def merge_warnings(*groups: list[str]) -> list[str]:
    """Merge warning lists preserving first occurrence order."""

    merged: list[str] = []
    for group in groups:
        for warning in group:
            if warning not in merged:
                merged.append(warning)
    return merged
