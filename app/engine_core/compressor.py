"""Compressor station calculation."""

from __future__ import annotations

from app.engine_core.constants import cp_air, gamma_air
from app.engine_core.types import ComponentResult, CycleCalculationError, StationState


def calculate_compressor_exit(
    inlet_exit_state: StationState,
    pressure_ratio: float,
    efficiency: float,
) -> ComponentResult:
    """Calculate station 3 and compressor specific work for a given pressure ratio."""

    if pressure_ratio <= 1.0:
        raise CycleCalculationError("Compressor pressure ratio must exceed 1.")
    if not 0.0 < efficiency <= 1.0:
        raise CycleCalculationError("Compressor efficiency must be between 0 and 1.")

    temperature_ratio_isentropic = pressure_ratio ** ((gamma_air - 1.0) / gamma_air)
    stagnation_temperature_3s_K = (
        inlet_exit_state.stagnation_temperature_K * temperature_ratio_isentropic
    )
    stagnation_temperature_3_K = inlet_exit_state.stagnation_temperature_K + (
        stagnation_temperature_3s_K - inlet_exit_state.stagnation_temperature_K
    ) / efficiency
    stagnation_pressure_3_Pa = inlet_exit_state.stagnation_pressure_Pa * pressure_ratio
    compressor_specific_work_J_kg = cp_air * (
        stagnation_temperature_3_K - inlet_exit_state.stagnation_temperature_K
    )

    state = StationState(
        station=3,
        name="Compressor exit",
        stagnation_temperature_K=stagnation_temperature_3_K,
        stagnation_pressure_Pa=stagnation_pressure_3_Pa,
        notes=["Adiabatic compressor with specified isentropic efficiency."],
    )

    warnings: list[str] = []
    if stagnation_temperature_3_K > 900.0:
        warnings.append("Compressor exit temperature is high for a simple turbojet cycle.")

    return ComponentResult(
        state=state,
        warnings=warnings,
        metadata={
            "compressor_specific_work_J_kg": compressor_specific_work_J_kg,
            "stagnation_temperature_3s_K": stagnation_temperature_3s_K,
        },
    )

