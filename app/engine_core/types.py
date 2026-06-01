"""Shared types for station-based cycle calculations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.engine_core.constants import fuel_heating_value_default


class CycleCalculationError(ValueError):
    """Raised when requested cycle inputs create a nonphysical calculation."""


@dataclass(slots=True)
class StationState:
    """Thermodynamic state at a numbered engine station.

    Static properties are included where the model explicitly computes them.
    Stagnation properties are carried through each component because the cycle
    is a steady, one-dimensional preliminary performance model.
    """

    station: int
    name: str
    stagnation_temperature_K: float
    stagnation_pressure_Pa: float
    static_temperature_K: float | None = None
    static_pressure_Pa: float | None = None
    mach: float | None = None
    velocity_m_s: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready station dictionary without empty optional fields."""

        data: dict[str, Any] = {
            "station": self.station,
            "name": self.name,
            "stagnation_temperature_K": self.stagnation_temperature_K,
            "stagnation_pressure_Pa": self.stagnation_pressure_Pa,
        }
        optional_values = {
            "static_temperature_K": self.static_temperature_K,
            "static_pressure_Pa": self.static_pressure_Pa,
            "mach": self.mach,
            "velocity_m_s": self.velocity_m_s,
            "notes": self.notes or None,
        }
        for key, value in optional_values.items():
            if value is not None:
                data[key] = value
        return data


@dataclass(slots=True)
class ComponentResult:
    """Result container returned by each engine component calculation."""

    state: StationState
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, float | bool | str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class TurbojetCycleInputs:
    """Validated inputs consumed by the engine core turbojet solver."""

    engine_variant: str = "turbojet"
    altitude_m: float = 10000.0
    mach: float = 0.8
    mass_flow_air_kg_s: float = 50.0
    inlet_capture_area_m2: float | None = None
    use_inlet_area_mass_flow: bool = False
    compressor_pressure_ratio: float = 12.0
    compressor_efficiency: float = 0.86
    turbine_inlet_temperature_K: float = 1400.0
    turbine_efficiency: float = 0.88
    combustor_efficiency: float = 0.99
    combustor_pressure_loss_fraction: float = 0.05
    mechanical_efficiency: float = 0.99
    nozzle_efficiency: float = 0.95
    inlet_pressure_recovery: float = 0.98
    fuel_heating_value_J_kg: float = fuel_heating_value_default
    nozzle_exit_area_m2: float | None = None
    nozzle_throat_area_m2: float | None = None
    include_pressure_thrust: bool = True
    afterburner_exit_temperature_K: float | None = None
    afterburner_efficiency: float = 0.95
    afterburner_pressure_loss_fraction: float = 0.06
    use_equilibrium_combustion: bool = False
    equilibrium_fuel_species: str = "CH4"
    # Compressor bleed and HP-turbine cooling air, expressed as a fraction of
    # the HPC exit flow. Customer / overboard bleed leaves the engine and is
    # not re-introduced. HPT cooling air is routed around the combustor and
    # mixed back at the turbine inlet, depressing the effective Tt4 the blade
    # row sees while still passing through the turbine and nozzle.
    bleed_fraction_hpc_exit: float = 0.0
    cooling_fraction_hpt_inlet: float = 0.0
    # When True, attach a real-gas (variable-cp) hot-section correction to the
    # result: turbine-exit and nozzle-exit temperatures recomputed with
    # temperature-dependent burned-gas properties (Cantera, frozen composition).
    real_gas: bool = False
