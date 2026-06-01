"""Combustor station calculation and fuel-air ratio estimate."""

from __future__ import annotations

from app.engine_core.constants import cp_air, cp_gas
from app.engine_core.types import ComponentResult, CycleCalculationError, StationState


def calculate_combustor_exit(
    compressor_exit_state: StationState,
    turbine_inlet_temperature_K: float,
    combustor_efficiency: float,
    pressure_loss_fraction: float,
    fuel_heating_value_J_kg: float,
) -> ComponentResult:
    """Calculate station 4 and fuel-air ratio from an energy balance.

    The v1 combustor does not perform chemical equilibrium. It treats the fuel
    lower heating value and combustor efficiency as an effective heat release.
    """

    if not 0.0 < combustor_efficiency <= 1.0:
        raise CycleCalculationError("Combustor efficiency must be between 0 and 1.")
    if not 0.0 <= pressure_loss_fraction <= 0.3:
        raise CycleCalculationError("Combustor pressure loss fraction must be 0 to 0.3.")
    if fuel_heating_value_J_kg <= 1e6:
        raise CycleCalculationError("Fuel heating value must exceed 1e6 J/kg.")
    if turbine_inlet_temperature_K <= compressor_exit_state.stagnation_temperature_K:
        raise CycleCalculationError(
            "Turbine inlet temperature must exceed compressor exit temperature."
        )

    numerator = (
        cp_gas * turbine_inlet_temperature_K
        - cp_air * compressor_exit_state.stagnation_temperature_K
    )
    denominator = (
        combustor_efficiency * fuel_heating_value_J_kg
        - cp_gas * turbine_inlet_temperature_K
    )
    if denominator <= 0.0:
        raise CycleCalculationError(
            "Combustor energy balance is impossible because fuel heat release is too low."
        )

    fuel_air_ratio = numerator / denominator
    if fuel_air_ratio <= 0.0:
        raise CycleCalculationError(
            "Combustor produced a non-positive fuel-air ratio; check T04 and compressor exit."
        )

    stagnation_pressure_4_Pa = compressor_exit_state.stagnation_pressure_Pa * (
        1.0 - pressure_loss_fraction
    )
    if stagnation_pressure_4_Pa <= 0.0:
        raise CycleCalculationError("Combustor pressure loss produced non-positive pressure.")

    state = StationState(
        station=4,
        name="Combustor exit / turbine inlet",
        stagnation_temperature_K=turbine_inlet_temperature_K,
        stagnation_pressure_Pa=stagnation_pressure_4_Pa,
        notes=["Specified turbine inlet temperature with pressure loss and heat addition."],
    )

    warnings: list[str] = []
    if fuel_air_ratio > 0.06:
        warnings.append("Fuel-air ratio is high for a simple lean turbojet calculation.")
    if pressure_loss_fraction > 0.1:
        warnings.append("Combustor pressure loss is high for a preliminary cycle model.")

    return ComponentResult(
        state=state,
        warnings=warnings,
        metadata={"fuel_air_ratio": fuel_air_ratio},
    )

