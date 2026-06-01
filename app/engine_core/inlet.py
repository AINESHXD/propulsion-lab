"""Freestream and inlet/diffuser station calculations."""

from __future__ import annotations

from app.engine_core.atmosphere import AtmosphereState
from app.engine_core.gas_properties import (
    speed_of_sound,
    stagnation_pressure,
    stagnation_temperature,
)
from app.engine_core.types import ComponentResult, CycleCalculationError, StationState


def calculate_freestream_state(atmosphere: AtmosphereState, mach: float) -> ComponentResult:
    """Create station 0 from ambient static atmosphere and flight Mach number."""

    if mach < 0.0:
        raise CycleCalculationError("Mach number must be non-negative.")

    velocity_m_s = mach * speed_of_sound(atmosphere.temperature_K)
    state = StationState(
        station=0,
        name="Ambient / freestream",
        static_temperature_K=atmosphere.temperature_K,
        static_pressure_Pa=atmosphere.pressure_Pa,
        stagnation_temperature_K=stagnation_temperature(atmosphere.temperature_K, mach),
        stagnation_pressure_Pa=stagnation_pressure(atmosphere.pressure_Pa, mach),
        mach=mach,
        velocity_m_s=velocity_m_s,
        notes=["ISA static state with perfect-gas stagnation properties."],
    )

    warnings: list[str] = []
    if mach > 1.5:
        warnings.append(
            "Freestream Mach number is high for this simple inlet recovery model; "
            "shock losses are not explicitly modelled."
        )
    return ComponentResult(state=state, warnings=warnings)


def calculate_inlet_exit(
    freestream_state: StationState,
    inlet_pressure_recovery: float,
) -> ComponentResult:
    """Calculate station 2 stagnation state after inlet total-pressure recovery."""

    if not 0.0 < inlet_pressure_recovery <= 1.0:
        raise CycleCalculationError("Inlet pressure recovery must be between 0 and 1.")

    state = StationState(
        station=2,
        name="Inlet / diffuser exit",
        stagnation_temperature_K=freestream_state.stagnation_temperature_K,
        stagnation_pressure_Pa=(
            freestream_state.stagnation_pressure_Pa * inlet_pressure_recovery
        ),
        notes=["No inlet heat transfer; stagnation temperature is conserved."],
    )

    warnings: list[str] = []
    if inlet_pressure_recovery < 0.9:
        warnings.append("Inlet pressure recovery is low for an educational clean inlet.")
    return ComponentResult(state=state, warnings=warnings)

