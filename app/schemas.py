"""Pydantic schemas for the PropulsionLab FastAPI boundary."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.engine_core.constants import fuel_heating_value_default
from app.engine_core.types import TurbojetCycleInputs

EngineVariant = Literal["turbojet", "afterburning_turbojet"]
AdvancedEngineType = Literal["turbofan", "turboprop", "ramjet", "scramjet"]


class TurbojetInput(BaseModel):
    """Validated input schema for the educational turbojet simulation."""

    model_config = ConfigDict(extra="forbid")

    engine_variant: EngineVariant = "turbojet"
    altitude_m: float = Field(default=10000.0, ge=-500.0, le=25000.0)
    mach: float = Field(default=0.8, ge=0.0, le=3.0)
    mass_flow_air_kg_s: float = Field(default=50.0, gt=0.0)
    inlet_capture_area_m2: float | None = Field(default=None, gt=0.0)
    use_inlet_area_mass_flow: bool = False
    compressor_pressure_ratio: float = Field(default=12.0, gt=1.0)
    compressor_efficiency: float = Field(default=0.86, gt=0.0, le=1.0)
    turbine_inlet_temperature_K: float = Field(default=1400.0, ge=700.0, le=2300.0)
    turbine_efficiency: float = Field(default=0.88, gt=0.0, le=1.0)
    combustor_efficiency: float = Field(default=0.99, gt=0.0, le=1.0)
    combustor_pressure_loss_fraction: float = Field(default=0.05, ge=0.0, le=0.3)
    mechanical_efficiency: float = Field(default=0.99, gt=0.0, le=1.0)
    nozzle_efficiency: float = Field(default=0.95, gt=0.0, le=1.0)
    inlet_pressure_recovery: float = Field(default=0.98, gt=0.0, le=1.0)
    fuel_heating_value_J_kg: float = Field(default=fuel_heating_value_default, gt=1e6)
    nozzle_exit_area_m2: float | None = Field(default=None, gt=0.0)
    nozzle_throat_area_m2: float | None = Field(default=None, gt=0.0)
    include_pressure_thrust: bool = True
    afterburner_exit_temperature_K: float | None = Field(default=None, ge=900.0, le=2400.0)
    afterburner_efficiency: float = Field(default=0.95, gt=0.0, le=1.0)
    afterburner_pressure_loss_fraction: float = Field(default=0.06, ge=0.0, le=0.25)
    use_equilibrium_combustion: bool = Field(
        default=False,
        description=(
            "If True, route the combustor through the Cantera equilibrium "
            "model instead of the constant-cp educational solver. Requires "
            "the `cantera` Python package."
        ),
    )
    equilibrium_fuel_species: str = Field(
        default="CH4",
        max_length=12,
        description=(
            "Cantera species name used by the equilibrium combustor. "
            "Defaults to methane as an educational hydrocarbon surrogate."
        ),
    )
    bleed_fraction_hpc_exit: float = Field(
        default=0.0,
        ge=0.0,
        le=0.25,
        description=(
            "Customer / overboard compressor bleed at HPC exit as a fraction "
            "of inlet air mass flow. Lost to the cycle; reduces combustor and "
            "turbine mass flow. Typical real engines: 0.03-0.12."
        ),
    )
    cooling_fraction_hpt_inlet: float = Field(
        default=0.0,
        ge=0.0,
        le=0.30,
        description=(
            "HP-turbine cooling air taken at HPC exit, routed around the "
            "combustor, and re-introduced at the turbine inlet. Lowers the "
            "effective Tt4 by mixing with hot combustion gas. Modern cooled "
            "turbines: 0.10-0.20."
        ),
    )
    real_gas: bool = Field(
        default=False,
        description=(
            "Attach a real-gas (variable-cp) hot-section correction to the "
            "result: turbine-exit and nozzle-exit temperatures recomputed with "
            "temperature-dependent burned-gas properties via Cantera. The core "
            "cycle stays constant-cp; this adds a `real_gas_hot_section` block."
        ),
    )

    def to_cycle_inputs(self) -> TurbojetCycleInputs:
        """Convert the API schema into the engine-core dataclass."""

        return TurbojetCycleInputs(**self.model_dump())


class TurbojetOverrideInput(BaseModel):
    """Optional override body for preset-based turbojet simulations."""

    model_config = ConfigDict(extra="forbid")

    engine_variant: EngineVariant | None = None
    altitude_m: float | None = Field(default=None, ge=-500.0, le=25000.0)
    mach: float | None = Field(default=None, ge=0.0, le=3.0)
    mass_flow_air_kg_s: float | None = Field(default=None, gt=0.0)
    inlet_capture_area_m2: float | None = Field(default=None, gt=0.0)
    use_inlet_area_mass_flow: bool | None = None
    compressor_pressure_ratio: float | None = Field(default=None, gt=1.0)
    compressor_efficiency: float | None = Field(default=None, gt=0.0, le=1.0)
    turbine_inlet_temperature_K: float | None = Field(default=None, ge=700.0, le=2300.0)
    turbine_efficiency: float | None = Field(default=None, gt=0.0, le=1.0)
    combustor_efficiency: float | None = Field(default=None, gt=0.0, le=1.0)
    combustor_pressure_loss_fraction: float | None = Field(default=None, ge=0.0, le=0.3)
    mechanical_efficiency: float | None = Field(default=None, gt=0.0, le=1.0)
    nozzle_efficiency: float | None = Field(default=None, gt=0.0, le=1.0)
    inlet_pressure_recovery: float | None = Field(default=None, gt=0.0, le=1.0)
    fuel_heating_value_J_kg: float | None = Field(default=None, gt=1e6)
    nozzle_exit_area_m2: float | None = Field(default=None, gt=0.0)
    nozzle_throat_area_m2: float | None = Field(default=None, gt=0.0)
    include_pressure_thrust: bool | None = None
    afterburner_exit_temperature_K: float | None = Field(default=None, ge=900.0, le=2400.0)
    afterburner_efficiency: float | None = Field(default=None, gt=0.0, le=1.0)
    afterburner_pressure_loss_fraction: float | None = Field(default=None, ge=0.0, le=0.25)
    use_equilibrium_combustion: bool | None = None
    equilibrium_fuel_species: str | None = Field(default=None, max_length=12)
    bleed_fraction_hpc_exit: float | None = Field(default=None, ge=0.0, le=0.25)
    cooling_fraction_hpt_inlet: float | None = Field(default=None, ge=0.0, le=0.30)


class StationData(BaseModel):
    """API representation of a gas turbine station."""

    station: int
    name: str
    static_temperature_K: float | None = None
    static_pressure_Pa: float | None = None
    stagnation_temperature_K: float
    stagnation_pressure_Pa: float
    mach: float | None = None
    velocity_m_s: float | None = None
    notes: list[str] | None = None


class TurbojetOutput(BaseModel):
    """Output schema for turbojet simulation results."""

    engine_variant: EngineVariant = "turbojet"
    thrust_N: float
    thrust_kN: float
    specific_thrust_N_per_kg_s: float
    effective_mass_flow_air_kg_s: float | None = None
    fuel_air_ratio: float
    core_fuel_air_ratio: float | None = None
    afterburner_fuel_air_ratio: float = 0.0
    fuel_flow_kg_s: float
    TSFC_kg_per_N_s: float
    TSFC_kg_per_kN_hr: float
    exit_velocity_m_s: float
    freestream_velocity_m_s: float
    nozzle_choked: bool
    nozzle_exit_pressure_Pa: float
    ambient_pressure_Pa: float
    nozzle_exit_area_m2: float | None = None
    estimated_nozzle_exit_area_m2: float | None = None
    nozzle_throat_area_m2: float | None = None
    nozzle_area_ratio: float | None = None
    nozzle_pressure_ratio: float | None = None
    nozzle_expansion_status: str | None = None
    pressure_thrust_N: float
    momentum_thrust_N: float
    thermal_efficiency_estimate: float
    propulsive_efficiency_estimate: float
    overall_efficiency_estimate: float
    bleed_fraction_hpc_exit: float = 0.0
    cooling_fraction_hpt_inlet: float = 0.0
    combustor_air_mass_flow_kg_s: float | None = None
    hpt_inlet_mass_flow_kg_s: float | None = None
    hpt_inlet_stagnation_temperature_K: float | None = None
    station_table: dict[int, StationData]
    real_gas_hot_section: dict[str, Any] | None = None
    warnings: list[str]


class AdvancedEngineOutput(BaseModel):
    """Common output schema for non-turbojet cycle models."""

    engine_type: AdvancedEngineType
    thrust_N: float
    thrust_kN: float
    specific_thrust_N_per_kg_s: float
    fuel_air_ratio: float
    fuel_flow_kg_s: float
    TSFC_kg_per_N_s: float
    TSFC_kg_per_kN_hr: float
    exit_velocity_m_s: float
    freestream_velocity_m_s: float
    nozzle_choked: bool
    momentum_thrust_N: float
    pressure_thrust_N: float
    thermal_efficiency_estimate: float
    propulsive_efficiency_estimate: float
    overall_efficiency_estimate: float
    # Turbofan-specific (None for other engine families)
    core_thrust_N: float | None = None
    bypass_thrust_N: float | None = None
    third_stream_thrust_N: float | None = None
    bypass_exit_velocity_m_s: float | None = None
    bypass_nozzle_choked: bool | None = None
    afterburner_fuel_air_ratio: float | None = None
    total_fuel_air_ratio: float | None = None
    # Turboprop-specific (None for other engine families)
    propeller_thrust_N: float | None = None
    jet_thrust_N: float | None = None
    shaft_power_W: float | None = None
    shaft_power_kW: float | None = None
    equivalent_shaft_power_W: float | None = None
    equivalent_shaft_power_kW: float | None = None
    BSFC_kg_per_kW_h: float | None = None
    station_table: dict[int, StationData]
    warnings: list[str]
    extra: dict[str, Any] = Field(default_factory=dict)


TurbofanNozzleConfiguration = Literal["separate", "mixed"]


class TurbofanInput(BaseModel):
    """Validated input schema for an educational two-spool turbofan."""

    model_config = ConfigDict(extra="forbid")

    engine_variant: Literal["turbofan"] = "turbofan"
    nozzle_configuration: TurbofanNozzleConfiguration = "separate"
    altitude_m: float = Field(default=10000.0, ge=-500.0, le=25000.0)
    mach: float = Field(default=0.78, ge=0.0, le=2.5)
    total_mass_flow_air_kg_s: float = Field(default=220.0, gt=0.0)
    bypass_ratio: float = Field(default=5.0, ge=0.0, le=15.0)
    fan_pressure_ratio: float = Field(default=1.55, gt=1.0, le=3.5)
    fan_efficiency: float = Field(default=0.89, gt=0.0, le=1.0)
    core_compressor_pressure_ratio: float = Field(default=18.0, gt=1.0, le=50.0)
    compressor_efficiency: float = Field(default=0.88, gt=0.0, le=1.0)
    turbine_inlet_temperature_K: float = Field(default=1550.0, ge=900.0, le=2300.0)
    hp_turbine_efficiency: float = Field(default=0.9, gt=0.0, le=1.0)
    lp_turbine_efficiency: float = Field(default=0.9, gt=0.0, le=1.0)
    combustor_efficiency: float = Field(default=0.99, gt=0.0, le=1.0)
    combustor_pressure_loss_fraction: float = Field(default=0.05, ge=0.0, le=0.3)
    mechanical_efficiency: float = Field(default=0.99, gt=0.0, le=1.0)
    core_nozzle_efficiency: float = Field(default=0.95, gt=0.0, le=1.0)
    bypass_nozzle_efficiency: float = Field(default=0.94, gt=0.0, le=1.0)
    inlet_pressure_recovery: float = Field(default=0.98, gt=0.0, le=1.0)
    fuel_heating_value_J_kg: float = Field(default=fuel_heating_value_default, gt=1e6)
    use_afterburner: bool = False
    afterburner_exit_temperature_K: float | None = Field(default=None, ge=900.0, le=2400.0)
    afterburner_efficiency: float = Field(default=0.95, gt=0.0, le=1.0)
    afterburner_pressure_loss_fraction: float = Field(default=0.06, ge=0.0, le=0.25)
    mixer_pressure_loss_fraction: float = Field(default=0.02, ge=0.0, le=0.2)
    use_equilibrium_combustion: bool = False
    equilibrium_fuel_species: str = Field(default="CH4", max_length=12)
    bleed_fraction_hpc_exit: float = Field(default=0.0, ge=0.0, le=0.25)
    cooling_fraction_hpt_inlet: float = Field(default=0.0, ge=0.0, le=0.30)
    # Variable-cycle / 3-stream adaptive engine (separate-flow only).
    third_stream: bool = False
    variable_cycle_mode: Literal["high_efficiency", "high_thrust"] = "high_efficiency"
    third_stream_ratio: float = Field(default=0.0, ge=0.0, le=2.0)
    third_stream_pressure_ratio: float | None = Field(default=None, gt=1.0, le=3.5)
    third_stream_nozzle_efficiency: float = Field(default=0.94, gt=0.0, le=1.0)


class TurbopropInput(BaseModel):
    """Validated input schema for a gas-generator + free-power-turbine turboprop."""

    model_config = ConfigDict(extra="forbid")

    engine_variant: Literal["turboprop"] = "turboprop"
    altitude_m: float = Field(default=5000.0, ge=-500.0, le=25000.0)
    mach: float = Field(default=0.35, ge=0.0, le=1.0)
    mass_flow_air_kg_s: float = Field(default=12.0, gt=0.0)
    compressor_pressure_ratio: float = Field(default=9.0, gt=1.0, le=30.0)
    compressor_efficiency: float = Field(default=0.84, gt=0.0, le=1.0)
    turbine_inlet_temperature_K: float = Field(default=1250.0, ge=700.0, le=1900.0)
    hp_turbine_efficiency: float = Field(default=0.88, gt=0.0, le=1.0)
    power_turbine_efficiency: float = Field(default=0.88, gt=0.0, le=1.0)
    combustor_efficiency: float = Field(default=0.99, gt=0.0, le=1.0)
    combustor_pressure_loss_fraction: float = Field(default=0.05, ge=0.0, le=0.3)
    mechanical_efficiency: float = Field(default=0.98, gt=0.0, le=1.0)
    gearbox_efficiency: float = Field(default=0.985, gt=0.5, le=1.0)
    propeller_diameter_m: float = Field(default=3.0, gt=0.5, le=8.0)
    propeller_rpm: float = Field(default=1200.0, gt=100.0, le=4000.0)
    peak_propeller_efficiency: float = Field(default=0.86, gt=0.3, le=0.95)
    advance_ratio_at_peak: float = Field(default=1.1, gt=0.1, le=3.0)
    minimum_core_nozzle_temperature_K: float = Field(default=700.0, ge=450.0, le=1200.0)
    nozzle_efficiency: float = Field(default=0.92, gt=0.0, le=1.0)
    inlet_pressure_recovery: float = Field(default=0.98, gt=0.0, le=1.0)
    fuel_heating_value_J_kg: float = Field(default=fuel_heating_value_default, gt=1e6)
    use_equilibrium_combustion: bool = False
    equilibrium_fuel_species: str = Field(default="CH4", max_length=12)
    bleed_fraction_hpc_exit: float = Field(default=0.0, ge=0.0, le=0.25)
    cooling_fraction_hpt_inlet: float = Field(default=0.0, ge=0.0, le=0.30)


class RamjetInput(BaseModel):
    """Validated input schema for a subsonic-combustion ramjet with MIL-spec inlet."""

    model_config = ConfigDict(extra="forbid")

    engine_variant: Literal["ramjet"] = "ramjet"
    altitude_m: float = Field(default=15000.0, ge=-500.0, le=30000.0)
    mach: float = Field(default=2.2, ge=0.0, le=6.0)
    mass_flow_air_kg_s: float = Field(default=25.0, gt=0.0)
    inlet_pressure_recovery: float = Field(default=0.9, gt=0.0, le=1.0)
    use_mil_spec_inlet_recovery: bool = True
    diffuser_efficiency: float = Field(default=0.95, gt=0.0, le=1.0)
    combustor_inlet_mach: float = Field(default=0.25, gt=0.05, lt=1.0)
    combustor_exit_temperature_K: float = Field(default=1900.0, ge=800.0, le=2600.0)
    combustor_efficiency: float = Field(default=0.96, gt=0.0, le=1.0)
    combustor_pressure_loss_fraction: float = Field(default=0.08, ge=0.0, le=0.3)
    nozzle_efficiency: float = Field(default=0.94, gt=0.0, le=1.0)
    nozzle_divergent_area_ratio: float = Field(default=1.0, ge=1.0, le=25.0)
    fuel_heating_value_J_kg: float = Field(default=fuel_heating_value_default, gt=1e6)
    use_equilibrium_combustion: bool = False
    equilibrium_fuel_species: str = Field(default="CH4", max_length=12)


class ScramjetInput(BaseModel):
    """Validated input schema for a reduced-order supersonic-combustion scramjet."""

    model_config = ConfigDict(extra="forbid")

    engine_variant: Literal["scramjet"] = "scramjet"
    altitude_m: float = Field(default=22000.0, ge=-500.0, le=35000.0)
    mach: float = Field(default=5.0, ge=2.5, le=15.0)
    mass_flow_air_kg_s: float = Field(default=18.0, gt=0.0)
    inlet_kinetic_energy_efficiency: float = Field(default=0.94, gt=0.0, le=1.0)
    combustor_mach: float = Field(default=2.2, ge=1.1, le=4.0)
    equivalence_ratio: float = Field(default=0.7, gt=0.05, lt=4.0)
    combustor_efficiency: float = Field(default=0.85, gt=0.0, le=1.0)
    combustor_pressure_loss_fraction: float = Field(default=0.18, ge=0.0, le=0.4)
    nozzle_efficiency: float = Field(default=0.93, gt=0.0, le=1.0)
    nozzle_divergent_area_ratio: float = Field(default=6.0, ge=1.0, le=25.0)
    fuel_heating_value_J_kg: float = Field(default=fuel_heating_value_default, gt=1e6)
    stoichiometric_fuel_air_ratio: float = Field(default=0.0685, gt=0.01, le=0.15)


SweepParameterName = Literal[
    "altitude_m",
    "mach",
    "mass_flow_air_kg_s",
    "inlet_capture_area_m2",
    "compressor_pressure_ratio",
    "compressor_efficiency",
    "turbine_inlet_temperature_K",
    "turbine_efficiency",
    "combustor_efficiency",
    "combustor_pressure_loss_fraction",
    "mechanical_efficiency",
    "nozzle_efficiency",
    "inlet_pressure_recovery",
    "fuel_heating_value_J_kg",
    "nozzle_exit_area_m2",
    "nozzle_throat_area_m2",
    "afterburner_exit_temperature_K",
    "afterburner_efficiency",
    "afterburner_pressure_loss_fraction",
]


class CustomJetProfileInput(BaseModel):
    """User-defined jet profile that can be simulated without server-side persistence."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    engine_type: EngineVariant = "turbojet"
    source_note: str | None = Field(default=None, max_length=240)
    default_inputs: TurbojetInput = Field(default_factory=TurbojetInput)


class CustomJetProfileSimulationOutput(BaseModel):
    """Simulation result for a user-defined jet profile."""

    profile_name: str
    engine_type: EngineVariant
    output: TurbojetOutput


class TurbojetSweepInput(BaseModel):
    """Request schema for sweeping one turbojet input parameter over fixed values."""

    model_config = ConfigDict(extra="forbid")

    base_input: TurbojetInput = Field(default_factory=TurbojetInput)
    sweep_parameter: SweepParameterName = "compressor_pressure_ratio"
    values: list[float] = Field(default=[6.0, 10.0, 14.0, 18.0], min_length=1, max_length=100)


class TurbojetSweepCaseOutput(BaseModel):
    """Result for a single sweep case."""

    input_value: float
    success: bool
    output: TurbojetOutput | None = None
    error: str | None = None


class TurbojetSweepSummary(BaseModel):
    """Compact summary of successful sweep cases."""

    successful_cases: int
    failed_cases: int
    max_thrust_N: float | None = None
    min_TSFC_kg_per_kN_hr: float | None = None
    choked_cases: int = 0


class TurbojetSweepOutput(BaseModel):
    """Output schema for a one-parameter turbojet sweep."""

    sweep_parameter: SweepParameterName
    cases: list[TurbojetSweepCaseOutput]
    summary: TurbojetSweepSummary


# ---------------------------------------------------------------------------
# Advanced-engine sweeps and comparison
# ---------------------------------------------------------------------------


class AdvancedSweepCaseOutput(BaseModel):
    """One case in a non-turbojet engine sweep."""

    input_value: float
    success: bool
    output: AdvancedEngineOutput | None = None
    error: str | None = None


class AdvancedSweepSummary(BaseModel):
    """Compact summary of an advanced-engine sweep."""

    successful_cases: int
    failed_cases: int
    max_thrust_N: float | None = None
    min_TSFC_kg_per_kN_hr: float | None = None


class TurbofanSweepInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_input: TurbofanInput = Field(default_factory=TurbofanInput)
    sweep_parameter: str = Field(default="bypass_ratio", min_length=1, max_length=60)
    values: list[float] = Field(default=[1.0, 3.0, 5.0, 8.0, 11.0], min_length=1, max_length=100)


class TurbopropSweepInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_input: TurbopropInput = Field(default_factory=TurbopropInput)
    sweep_parameter: str = Field(default="mach", min_length=1, max_length=60)
    values: list[float] = Field(default=[0.0, 0.2, 0.35, 0.5, 0.65], min_length=1, max_length=100)


class RamjetSweepInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_input: RamjetInput = Field(default_factory=RamjetInput)
    sweep_parameter: str = Field(default="mach", min_length=1, max_length=60)
    values: list[float] = Field(default=[1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0], min_length=1, max_length=100)


class ScramjetSweepInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_input: ScramjetInput = Field(default_factory=ScramjetInput)
    sweep_parameter: str = Field(default="mach", min_length=1, max_length=60)
    values: list[float] = Field(default=[4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0], min_length=1, max_length=100)


class AdvancedEngineSweepOutput(BaseModel):
    engine_type: AdvancedEngineType
    sweep_parameter: str
    cases: list[AdvancedSweepCaseOutput]
    summary: AdvancedSweepSummary


class EngineSpec(BaseModel):
    """One engine entry in a comparison run."""

    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=60)
    engine_type: Literal["turbojet", "turbofan", "turboprop", "ramjet", "scramjet"]
    turbojet_input: TurbojetInput | None = None
    turbofan_input: TurbofanInput | None = None
    turboprop_input: TurbopropInput | None = None
    ramjet_input: RamjetInput | None = None
    scramjet_input: ScramjetInput | None = None


class EngineComparisonInput(BaseModel):
    """Compare 2-5 engine specs side-by-side at their own design points."""

    model_config = ConfigDict(extra="forbid")
    specs: list[EngineSpec] = Field(min_length=2, max_length=5)


class EngineComparisonCase(BaseModel):
    """One row in the comparison output."""

    label: str
    engine_type: str
    success: bool
    thrust_kN: float | None = None
    TSFC_kg_per_kN_hr: float | None = None
    thermal_efficiency_estimate: float | None = None
    propulsive_efficiency_estimate: float | None = None
    overall_efficiency_estimate: float | None = None
    fuel_air_ratio: float | None = None
    nozzle_choked: bool | None = None
    error: str | None = None


class EngineComparisonOutput(BaseModel):
    """Side-by-side comparison summary."""

    cases: list[EngineComparisonCase]
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Off-design matching (Day 12)
# ---------------------------------------------------------------------------


class OffDesignGridInput(BaseModel):
    """Operating-point grid for an off-design envelope.

    Each axis defaults to the design value when omitted, so a single point is a
    1x1x1 grid. ``throttles_K`` are turbine inlet temperatures (Tt4) used as the
    throttle setting. The cartesian product is capped server-side.
    """

    model_config = ConfigDict(extra="forbid")

    altitudes_m: list[float] | None = Field(default=None, min_length=1, max_length=60)
    machs: list[float] | None = Field(default=None, min_length=1, max_length=60)
    throttles_K: list[float] | None = Field(default=None, min_length=1, max_length=60)


class TurbojetOffDesignInput(BaseModel):
    """Design spec + operating-point grid for turbojet off-design matching."""

    model_config = ConfigDict(extra="forbid")

    design: TurbojetInput = Field(default_factory=TurbojetInput)
    grid: OffDesignGridInput = Field(default_factory=OffDesignGridInput)


class MapMatchInput(BaseModel):
    """Design spec + flight condition + throttle sweep for map-based matching.

    The ``design`` deck calibrates the off-design reference and sizes the
    synthetic maps; ``altitude_m`` / ``mach`` default to the design values and
    set the flight condition for the throttle sweep. ``throttles_K`` are turbine
    inlet temperatures; when omitted a sweep around the design Tt4 is used.
    """

    model_config = ConfigDict(extra="forbid")

    design: TurbojetInput = Field(default_factory=TurbojetInput)
    altitude_m: float | None = Field(default=None, ge=-500.0, le=25000.0)
    mach: float | None = Field(default=None, ge=0.0, le=3.0)
    throttles_K: list[float] | None = Field(default=None, min_length=1, max_length=60)


class TurbofanOffDesignInput(BaseModel):
    """Design spec + operating-point grid for turbofan off-design matching."""

    model_config = ConfigDict(extra="forbid")

    design: TurbofanInput = Field(default_factory=TurbofanInput)
    grid: OffDesignGridInput = Field(default_factory=OffDesignGridInput)


class OffDesignPointOutput(BaseModel):
    """One matched operating point in an off-design envelope."""

    altitude_m: float
    mach: float
    turbine_inlet_temperature_K: float
    success: bool
    error: str | None = None
    converged: bool | None = None
    thrust_kN: float | None = None
    TSFC_kg_per_kN_hr: float | None = None
    overall_efficiency_estimate: float | None = None
    effective_mass_flow_air_kg_s: float | None = None
    compressor_pressure_ratio: float | None = None  # turbojet
    fan_pressure_ratio: float | None = None          # turbofan
    overall_pressure_ratio: float | None = None      # turbofan
    nozzle_choked: bool | None = None


class OffDesignSummary(BaseModel):
    """Aggregate statistics across an off-design envelope."""

    points: int
    successful: int
    failed: int
    max_thrust_kN: float | None = None
    min_TSFC_kg_per_kN_hr: float | None = None


class OffDesignEnvelopeOutput(BaseModel):
    """Off-design envelope grid: the calibrated reference + per-point results."""

    engine_type: str
    design_thrust_kN: float | None = None
    points: list[OffDesignPointOutput]
    summary: OffDesignSummary


# ---------------------------------------------------------------------------
# Mission profiles (Day 15)
# ---------------------------------------------------------------------------


class MissionSegmentInput(BaseModel):
    """One leg of a flight mission, held at a fixed off-design operating point.

    ``throttle_K`` is the turbine inlet temperature (Tt4) used as the throttle
    setting — the same throttle parameter the off-design solver matches on.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=40)
    altitude_m: float = Field(default=10000.0, ge=-500.0, le=25000.0)
    mach: float = Field(default=0.8, ge=0.0, le=3.0)
    throttle_K: float = Field(default=1400.0, ge=700.0, le=2300.0)
    duration_s: float = Field(default=600.0, gt=0.0, le=86400.0)


class MissionProfileInput(BaseModel):
    """An ordered list of mission segments to integrate end to end."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="Mission", max_length=80)
    segments: list[MissionSegmentInput] = Field(min_length=1, max_length=50)


class TurbojetMissionInput(BaseModel):
    """Turbojet design spec + a mission profile to fly on it."""

    model_config = ConfigDict(extra="forbid")

    design: TurbojetInput = Field(default_factory=TurbojetInput)
    profile: MissionProfileInput


class TurbofanMissionInput(BaseModel):
    """Turbofan design spec + a mission profile to fly on it."""

    model_config = ConfigDict(extra="forbid")

    design: TurbofanInput = Field(default_factory=TurbofanInput)
    profile: MissionProfileInput


class MissionSegmentOutput(BaseModel):
    """Per-segment result row from a flown mission (Day 16 fills these)."""

    name: str | None = None
    altitude_m: float
    mach: float
    throttle_K: float
    duration_s: float
    success: bool
    error: str | None = None
    thrust_kN: float | None = None
    TSFC_kg_per_kN_hr: float | None = None
    fuel_burned_kg: float | None = None
    cumulative_fuel_kg: float | None = None
    cumulative_time_s: float | None = None


class MissionOutput(BaseModel):
    """Integrated mission result: per-segment rows + cumulative totals."""

    engine_type: str
    name: str
    segments: list[MissionSegmentOutput]
    total_fuel_kg: float | None = None
    total_time_s: float | None = None
    successful_segments: int = 0
    failed_segments: int = 0


# ---------------------------------------------------------------------------
# Python-API export (Day 26)
# ---------------------------------------------------------------------------


class PythonExportInput(BaseModel):
    """Request to render a runnable Python API-client script from UI state."""

    model_config = ConfigDict(extra="forbid")

    engine_type: Literal[
        "turbojet", "afterburning_turbojet", "turbofan", "turboprop",
        "ramjet", "scramjet",
    ]
    inputs: dict[str, Any]


# ---------------------------------------------------------------------------
# Combustor emissions: reactor-network NOx / CO + ICAO LTO (Month-4 feature)
# ---------------------------------------------------------------------------


class EmissionsInput(BaseModel):
    """Combustor-inlet state + fuel-air ratio for an emissions calculation."""

    model_config = ConfigDict(extra="forbid")

    combustor_inlet_temperature_K: float = Field(default=820.0, gt=200.0, le=1200.0)
    combustor_inlet_pressure_Pa: float = Field(default=3.0e6, gt=1.0e4)
    fuel_air_ratio: float = Field(default=0.022, gt=0.0, le=0.075)
    fuel: str = Field(default="CH4", max_length=12)
    phi_primary: float = Field(default=0.73, ge=0.3, le=1.6)
    tau_primary_s: float = Field(default=0.002, gt=0.0, le=0.05)
    tau_secondary_s: float = Field(default=0.004, gt=0.0, le=0.05)
    n_dilution: int = Field(default=6, ge=1, le=30)


class AxialEmissionPoint(BaseModel):
    """One axial station in the combustor emissions profile."""

    x_fraction: float
    temperature_K: float
    no_ppm: float
    co_ppm: float


class EmissionsOutput(BaseModel):
    """Emission indices (g pollutant / kg fuel) and supporting detail."""

    ei_nox_g_per_kg: float
    ei_co_g_per_kg: float
    ei_hc_g_per_kg: float
    ei_co2_g_per_kg: float
    ei_h2o_g_per_kg: float
    soot_proxy: float
    primary_zone_temperature_K: float | None = None
    phi_primary: float
    phi_overall: float
    fuel: str
    source: str
    axial_profile: list[AxialEmissionPoint] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TurbojetLTOInput(BaseModel):
    """Turbojet deck + rated thrust for an ICAO landing–takeoff NOx estimate.

    The four ICAO modes (take-off / climb-out / approach / idle) are evaluated
    sea-level static by throttling the turbine-inlet temperature to hit each
    thrust setting, then the reactor-network EINOx and fuel flow at each mode are
    aggregated into Dp(NOx) and the Dp/Foo certification metric.
    """

    model_config = ConfigDict(extra="forbid")

    design: TurbojetInput = Field(default_factory=TurbojetInput)
    fuel: str = Field(default="CH4", max_length=12)
    phi_primary: float = Field(default=0.73, ge=0.3, le=1.6)


class LTOModeOutput(BaseModel):
    """One ICAO LTO mode result."""

    name: str
    thrust_fraction: float
    thrust_kN: float | None = None
    turbine_inlet_temperature_K: float | None = None
    combustor_inlet_temperature_K: float | None = None
    combustor_inlet_pressure_Pa: float | None = None
    fuel_air_ratio: float | None = None
    ei_nox_g_per_kg: float
    fuel_flow_kg_s: float
    time_in_mode_s: float
    nox_g: float


class TurbojetLTOOutput(BaseModel):
    """Aggregated ICAO LTO NOx result for a turbojet deck."""

    engine_type: str = "turbojet"
    rated_thrust_kN: float | None = None
    dp_nox_g: float
    fuel_burn_kg: float
    dp_foo_g_per_kN: float | None = None
    modes: list[LTOModeOutput]
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# NSGA-II multi-objective design optimisation (Month-5 feature)
# ---------------------------------------------------------------------------

OptimizationObjective = Literal["tsfc", "specific_thrust", "compressor_exit_temperature"]


class TurbojetOptimizeInput(BaseModel):
    """Design-space + algorithm settings for an NSGA-II turbojet optimisation."""

    model_config = ConfigDict(extra="forbid")

    design: TurbojetInput = Field(default_factory=TurbojetInput)
    objectives: list[OptimizationObjective] = Field(
        default_factory=lambda: ["tsfc", "specific_thrust"], min_length=2, max_length=3
    )
    pr_min: float = Field(default=6.0, gt=1.0, le=60.0)
    pr_max: float = Field(default=40.0, gt=1.0, le=60.0)
    tit_min_K: float = Field(default=1100.0, ge=700.0, le=2300.0)
    tit_max_K: float = Field(default=1800.0, ge=700.0, le=2300.0)
    tt3_max_K: float = Field(default=950.0, ge=600.0, le=1400.0)
    far_min: float = Field(default=0.005, ge=0.0, le=0.05)
    far_max: float = Field(default=0.05, ge=0.005, le=0.075)
    population_size: int = Field(default=40, ge=8, le=120)
    generations: int = Field(default=40, ge=5, le=120)
    seed: int | None = Field(default=0)


class ParetoPoint(BaseModel):
    """One non-dominated design on the Pareto front."""

    compressor_pressure_ratio: float
    turbine_inlet_temperature_K: float
    objective_values: list[float]
    thrust_kN: float
    TSFC_kg_per_kN_hr: float
    specific_thrust_N_per_kg_s: float
    compressor_exit_temperature_K: float
    fuel_air_ratio: float
    overall_efficiency_estimate: float


class TurbojetOptimizeOutput(BaseModel):
    """Pareto front + run metadata from an NSGA-II turbojet optimisation."""

    engine_type: str = "turbojet"
    objective_keys: list[str]
    objective_labels: list[str]
    pareto_front: list[ParetoPoint]
    population_size: int
    generations: int
    evaluations: int
    feasible_fraction: float
    notes: list[str] = Field(default_factory=list)
