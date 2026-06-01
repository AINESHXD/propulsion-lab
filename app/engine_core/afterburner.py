"""Afterburner station calculation for optional turbojet reheat."""

from __future__ import annotations

from app.engine_core.constants import cp_gas
from app.engine_core.types import ComponentResult, CycleCalculationError, StationState


def calculate_afterburner_exit(
    turbine_exit_state: StationState,
    core_fuel_air_ratio: float,
    afterburner_exit_temperature_K: float,
    afterburner_efficiency: float,
    pressure_loss_fraction: float,
    fuel_heating_value_J_kg: float,
) -> ComponentResult:
    """Calculate station 7 for a simple afterburning turbojet option.

    The v1.3 afterburner is a steady 1D reheat control volume. It adds fuel
    after the turbine, applies a total-pressure loss, and does not model flame
    stability, spray combustion, liner cooling, or variable-area nozzle control.
    """

    if core_fuel_air_ratio <= 0.0:
        raise CycleCalculationError("Core fuel-air ratio must be positive before afterburning.")
    if afterburner_exit_temperature_K <= turbine_exit_state.stagnation_temperature_K:
        raise CycleCalculationError(
            "Afterburner exit temperature must exceed turbine exit temperature."
        )
    if not 0.0 < afterburner_efficiency <= 1.0:
        raise CycleCalculationError("Afterburner efficiency must be between 0 and 1.")
    if not 0.0 <= pressure_loss_fraction <= 0.25:
        raise CycleCalculationError("Afterburner pressure loss fraction must be 0 to 0.25.")

    denominator = (
        afterburner_efficiency * fuel_heating_value_J_kg
        - cp_gas * afterburner_exit_temperature_K
    )
    if denominator <= 0.0:
        raise CycleCalculationError(
            "Afterburner energy balance is impossible because fuel heat release is too low."
        )

    afterburner_fuel_air_ratio = (
        (1.0 + core_fuel_air_ratio)
        * cp_gas
        * (afterburner_exit_temperature_K - turbine_exit_state.stagnation_temperature_K)
        / denominator
    )
    if afterburner_fuel_air_ratio <= 0.0:
        raise CycleCalculationError("Afterburner produced non-positive added fuel-air ratio.")

    total_fuel_air_ratio = core_fuel_air_ratio + afterburner_fuel_air_ratio
    stagnation_pressure_7_Pa = turbine_exit_state.stagnation_pressure_Pa * (
        1.0 - pressure_loss_fraction
    )
    if stagnation_pressure_7_Pa <= 0.0:
        raise CycleCalculationError("Afterburner pressure loss produced non-positive pressure.")

    state = StationState(
        station=7,
        name="Afterburner exit / nozzle inlet",
        stagnation_temperature_K=afterburner_exit_temperature_K,
        stagnation_pressure_Pa=stagnation_pressure_7_Pa,
        notes=[
            "Simple reheat model with specified exit temperature and pressure loss.",
        ],
    )

    warnings: list[str] = [
        "Afterburner option is educational only; variable-area nozzle scheduling is not modelled."
    ]
    if afterburner_fuel_air_ratio > core_fuel_air_ratio:
        warnings.append("Afterburner fuel addition exceeds core combustor fuel-air ratio.")
    if pressure_loss_fraction > 0.1:
        warnings.append("Afterburner pressure loss is high for a preliminary cycle model.")

    return ComponentResult(
        state=state,
        warnings=warnings,
        metadata={
            "afterburner_fuel_air_ratio": afterburner_fuel_air_ratio,
            "total_fuel_air_ratio": total_fuel_air_ratio,
        },
    )
