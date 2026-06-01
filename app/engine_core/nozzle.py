"""Nozzle station calculation."""

from __future__ import annotations

import numpy as np

from app.engine_core.constants import R_air, cp_gas, gamma_gas
from app.engine_core.types import ComponentResult, CycleCalculationError, StationState


def calculate_nozzle_exit(
    turbine_exit_state: StationState,
    ambient_pressure_Pa: float,
    mass_flow_air_kg_s: float,
    fuel_air_ratio: float,
    nozzle_efficiency: float,
    nozzle_exit_area_m2: float | None = None,
    include_pressure_thrust: bool = True,
    nozzle_throat_area_m2: float | None = None,
    gas_mass_flow_ratio: float | None = None,
) -> ComponentResult:
    """Calculate station 9 using convergent nozzle choking logic.

    The v1 nozzle is a steady, adiabatic, one-dimensional model. It applies
    nozzle efficiency to ideal kinetic energy and estimates exit area from
    continuity when the user does not specify an area.
    """

    if ambient_pressure_Pa <= 0.0:
        raise CycleCalculationError("Ambient pressure must be positive.")
    if mass_flow_air_kg_s <= 0.0:
        raise CycleCalculationError("Air mass flow must be positive.")
    if fuel_air_ratio <= 0.0:
        raise CycleCalculationError("Fuel-air ratio must be positive.")
    if not 0.0 < nozzle_efficiency <= 1.0:
        raise CycleCalculationError("Nozzle efficiency must be between 0 and 1.")
    if nozzle_exit_area_m2 is not None and nozzle_exit_area_m2 <= 0.0:
        raise CycleCalculationError("Nozzle exit area must be positive when supplied.")
    if nozzle_throat_area_m2 is not None and nozzle_throat_area_m2 <= 0.0:
        raise CycleCalculationError("Nozzle throat area must be positive when supplied.")
    if turbine_exit_state.stagnation_pressure_Pa <= ambient_pressure_Pa:
        raise CycleCalculationError(
            "Nozzle inlet stagnation pressure must exceed ambient pressure."
        )

    critical_pressure_Pa = turbine_exit_state.stagnation_pressure_Pa * (
        2.0 / (gamma_gas + 1.0)
    ) ** (gamma_gas / (gamma_gas - 1.0))
    nozzle_choked = critical_pressure_Pa > ambient_pressure_Pa

    if nozzle_choked:
        exit_pressure_Pa = critical_pressure_Pa
        exit_temperature_ideal_K = (
            turbine_exit_state.stagnation_temperature_K * 2.0 / (gamma_gas + 1.0)
        )
        exit_velocity_ideal_m_s = float(
            np.sqrt(gamma_gas * R_air * exit_temperature_ideal_K)
        )
        exit_velocity_m_s = float(np.sqrt(nozzle_efficiency) * exit_velocity_ideal_m_s)
        exit_temperature_K = turbine_exit_state.stagnation_temperature_K - (
            exit_velocity_m_s**2 / (2.0 * cp_gas)
        )
        exit_mach = 1.0
    else:
        exit_pressure_Pa = ambient_pressure_Pa
        exit_temperature_isentropic_K = turbine_exit_state.stagnation_temperature_K * (
            exit_pressure_Pa / turbine_exit_state.stagnation_pressure_Pa
        ) ** ((gamma_gas - 1.0) / gamma_gas)
        available_temperature_drop_K = (
            turbine_exit_state.stagnation_temperature_K - exit_temperature_isentropic_K
        )
        if available_temperature_drop_K <= 0.0:
            raise CycleCalculationError("Nozzle has no positive temperature drop available.")
        exit_velocity_m_s = float(
            np.sqrt(2.0 * nozzle_efficiency * cp_gas * available_temperature_drop_K)
        )
        exit_temperature_K = turbine_exit_state.stagnation_temperature_K - (
            exit_velocity_m_s**2 / (2.0 * cp_gas)
        )
        exit_speed_of_sound_m_s = float(np.sqrt(gamma_gas * R_air * exit_temperature_K))
        exit_mach = exit_velocity_m_s / exit_speed_of_sound_m_s

    if exit_temperature_K <= 0.0:
        raise CycleCalculationError("Nozzle exit static temperature is non-positive.")
    if exit_velocity_m_s <= 0.0:
        raise CycleCalculationError("Nozzle exit velocity is non-positive.")

    exit_density_kg_m3 = exit_pressure_Pa / (R_air * exit_temperature_K)
    effective_mass_ratio = (
        gas_mass_flow_ratio
        if gas_mass_flow_ratio is not None
        else 1.0 + fuel_air_ratio
    )
    total_mass_flow_kg_s = mass_flow_air_kg_s * effective_mass_ratio
    estimated_exit_area_m2 = total_mass_flow_kg_s / (
        exit_density_kg_m3 * exit_velocity_m_s
    )
    actual_exit_area_m2 = nozzle_exit_area_m2 or estimated_exit_area_m2
    actual_throat_area_m2 = nozzle_throat_area_m2 or (
        estimated_exit_area_m2 if nozzle_choked else actual_exit_area_m2
    )
    area_ratio = actual_exit_area_m2 / actual_throat_area_m2
    pressure_thrust_N = (
        (exit_pressure_Pa - ambient_pressure_Pa) * actual_exit_area_m2
        if include_pressure_thrust
        else 0.0
    )
    pressure_mismatch_fraction = (
        (exit_pressure_Pa - ambient_pressure_Pa) / ambient_pressure_Pa
    )
    if abs(pressure_mismatch_fraction) < 0.03:
        expansion_status = "Ideally expanded approximately"
    elif pressure_mismatch_fraction > 0.0:
        expansion_status = "Underexpanded"
    else:
        expansion_status = "Overexpanded"

    state = StationState(
        station=9,
        name="Nozzle exit",
        static_temperature_K=exit_temperature_K,
        static_pressure_Pa=exit_pressure_Pa,
        stagnation_temperature_K=turbine_exit_state.stagnation_temperature_K,
        stagnation_pressure_Pa=turbine_exit_state.stagnation_pressure_Pa,
        mach=exit_mach,
        velocity_m_s=exit_velocity_m_s,
        notes=[
            "Choked convergent nozzle." if nozzle_choked else "Unchoked convergent nozzle.",
        ],
    )

    warnings: list[str] = []
    if nozzle_exit_area_m2 is not None:
        area_delta_fraction = abs(nozzle_exit_area_m2 - estimated_exit_area_m2) / (
            estimated_exit_area_m2
        )
        if area_delta_fraction > 0.5:
            warnings.append(
                "Specified nozzle exit area differs substantially from continuity estimate."
            )
    if actual_exit_area_m2 <= 0.0 or actual_throat_area_m2 <= 0.0:
        warnings.append("Nozzle area calculation is nonphysical.")
    if area_ratio < 1.0:
        warnings.append("Nozzle exit area is smaller than throat area; check nozzle geometry.")
    if (
        include_pressure_thrust
        and abs(pressure_thrust_N) > 0.35 * total_mass_flow_kg_s * exit_velocity_m_s
    ):
        warnings.append(
            "Pressure thrust is a large share of nozzle thrust; "
            "check area and pressure matching."
        )

    return ComponentResult(
        state=state,
        warnings=warnings,
        metadata={
            "nozzle_choked": nozzle_choked,
            "nozzle_exit_pressure_Pa": exit_pressure_Pa,
            "nozzle_exit_area_m2": actual_exit_area_m2,
            "estimated_nozzle_exit_area_m2": estimated_exit_area_m2,
            "nozzle_throat_area_m2": actual_throat_area_m2,
            "nozzle_area_ratio": area_ratio,
            "nozzle_pressure_ratio": turbine_exit_state.stagnation_pressure_Pa
            / ambient_pressure_Pa,
            "nozzle_expansion_status": expansion_status,
            "pressure_thrust_N": pressure_thrust_N,
            "exit_velocity_m_s": exit_velocity_m_s,
        },
    )
