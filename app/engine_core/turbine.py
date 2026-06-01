"""Turbine station calculation."""

from __future__ import annotations

from app.engine_core.constants import cp_gas, gamma_gas
from app.engine_core.types import ComponentResult, CycleCalculationError, StationState


def calculate_turbine_exit(
    combustor_exit_state: StationState,
    compressor_specific_work_J_kg: float,
    fuel_air_ratio: float,
    mechanical_efficiency: float,
    turbine_efficiency: float,
    ambient_pressure_Pa: float | None = None,
    gas_mass_flow_ratio: float | None = None,
) -> ComponentResult:
    """Calculate station 5 from compressor work balance and turbine efficiency.

    ``gas_mass_flow_ratio`` (optional) is the ratio of mass actually passing
    through the turbine to the engine inlet air mass — i.e. ``m_HPT / m_air``.
    When supplied it overrides ``(1 + fuel_air_ratio)`` in the work-balance
    denominator. This is how bleed and cooling air are reflected in the
    turbine work: customer bleed reduces the gas seen by the turbine, while
    HPT cooling air adds back to it. When omitted, the historical
    ``1 + fuel_air_ratio`` behaviour is preserved.
    """

    if compressor_specific_work_J_kg <= 0.0:
        raise CycleCalculationError("Compressor specific work must be positive.")
    if fuel_air_ratio <= 0.0:
        raise CycleCalculationError("Fuel-air ratio must be positive.")
    if not 0.0 < mechanical_efficiency <= 1.0:
        raise CycleCalculationError("Mechanical efficiency must be between 0 and 1.")
    if not 0.0 < turbine_efficiency <= 1.0:
        raise CycleCalculationError("Turbine efficiency must be between 0 and 1.")

    effective_mass_ratio = (
        gas_mass_flow_ratio
        if gas_mass_flow_ratio is not None
        else 1.0 + fuel_air_ratio
    )
    if effective_mass_ratio <= 0.0:
        raise CycleCalculationError(
            "Turbine gas mass flow ratio must be positive — check bleed and cooling."
        )

    turbine_temperature_drop_K = compressor_specific_work_J_kg / (
        effective_mass_ratio * cp_gas * mechanical_efficiency
    )
    stagnation_temperature_5_K = (
        combustor_exit_state.stagnation_temperature_K - turbine_temperature_drop_K
    )
    if stagnation_temperature_5_K <= 0.0:
        raise CycleCalculationError("Turbine work extraction produced non-positive T05.")

    stagnation_temperature_5s_K = combustor_exit_state.stagnation_temperature_K - (
        combustor_exit_state.stagnation_temperature_K - stagnation_temperature_5_K
    ) / turbine_efficiency
    if stagnation_temperature_5s_K <= 0.0:
        raise CycleCalculationError("Turbine isentropic exit temperature is non-positive.")

    pressure_ratio = (
        stagnation_temperature_5s_K / combustor_exit_state.stagnation_temperature_K
    ) ** (gamma_gas / (gamma_gas - 1.0))
    stagnation_pressure_5_Pa = combustor_exit_state.stagnation_pressure_Pa * pressure_ratio
    if stagnation_pressure_5_Pa <= 0.0:
        raise CycleCalculationError("Turbine exit pressure is non-positive.")

    state = StationState(
        station=5,
        name="Turbine exit / nozzle inlet",
        stagnation_temperature_K=stagnation_temperature_5_K,
        stagnation_pressure_Pa=stagnation_pressure_5_Pa,
        notes=["Turbine supplies compressor work through specified mechanical efficiency."],
    )

    warnings: list[str] = []
    if ambient_pressure_Pa is not None and stagnation_pressure_5_Pa <= ambient_pressure_Pa:
        warnings.append(
            "Turbine exit stagnation pressure is at or below ambient pressure; "
            "the nozzle has little useful expansion available."
        )
    if stagnation_temperature_5_K < 500.0:
        warnings.append("Turbine exit temperature is low; check pressure ratio and TIT.")

    return ComponentResult(
        state=state,
        warnings=warnings,
        metadata={"stagnation_temperature_5s_K": stagnation_temperature_5s_K},
    )

