"""Pydantic schemas for the PistonLab HTTP API (Day 9).

PistonLab's physics lives in ``app/engine_core/piston`` as the source of truth.
These schemas wrap that solver for the browser the same way PropulsionLab's
schemas wrap its gas-turbine cycle: one ``/piston/simulate`` point and one
``/piston/sweep`` over a single parameter. The API is SI throughout; the
frontend converts for display.

Kept deliberately separate from the main ``schemas.py`` so the gated PistonLab
surface stays isolated until launch.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.engine_core.piston import (
    FUEL_NAMES,
    PistonCycleInputs,
    PistonCycleResult,
    simulate_piston_cycle,
)

AspirationMode = Literal["naturally_aspirated", "turbocharged", "supercharged"]
FuelName = Literal["gasoline", "diesel", "ethanol", "methanol"]


class PistonSimulateInput(BaseModel):
    """One operating point for the crank-angle solver, with API-side bounds."""

    model_config = ConfigDict(extra="forbid")

    # Geometry
    bore_m: float = Field(default=0.086, gt=0.02, le=0.5)
    stroke_m: float = Field(default=0.086, gt=0.02, le=0.6)
    compression_ratio: float = Field(default=10.5, gt=4.0, le=26.0)
    rod_ratio: float = Field(default=3.5, gt=1.2, le=6.0)
    cylinders: int = Field(default=4, ge=1, le=16)
    strokes_per_cycle: Literal[2, 4] = 4

    # Operating point
    rpm: float = Field(default=3000.0, gt=200.0, le=20000.0)

    # Gas + trapped state
    gamma: float = Field(default=1.35, gt=1.1, le=1.5)
    gas_constant_J_per_kg_K: float = Field(default=287.0, gt=150.0, le=400.0)
    intake_temperature_K: float = Field(default=330.0, gt=200.0, le=600.0)
    intake_pressure_Pa: float = Field(default=1.0e5, gt=1.0e4, le=5.0e5)
    exhaust_pressure_Pa: float = Field(default=1.0e5, gt=1.0e4, le=5.0e5)

    # Aspiration
    aspiration: AspirationMode = "naturally_aspirated"
    ambient_pressure_Pa: float = Field(default=1.0e5, gt=1.0e4, le=2.0e5)
    supercharger_efficiency: float = Field(default=0.65, gt=0.0, le=1.0)

    # Heat release (raw path; ignored when a fuel is set)
    heat_release_J_per_kg: float = Field(default=2.5e6, ge=0.0, le=5.0e6)

    # Fuel thermochemistry
    fuel: FuelName | None = None
    equivalence_ratio: float = Field(default=1.0, gt=0.0, le=2.5)
    combustion_efficiency: float = Field(default=0.98, gt=0.0, le=1.0)

    # Wiebe combustion
    combustion_start_deg: float = Field(default=-15.0, ge=-60.0, le=20.0)
    burn_duration_deg: float = Field(default=50.0, gt=5.0, le=120.0)
    wiebe_a: float = Field(default=5.0, gt=0.0, le=12.0)
    wiebe_m: float = Field(default=2.0, gt=0.0, le=6.0)

    # Wall heat transfer
    wall_temperature_K: float = Field(default=450.0, gt=300.0, le=700.0)
    wall_heat_transfer_multiplier: float = Field(default=1.0, ge=0.0, le=4.0)

    # Friction + fuel LHV (raw path)
    friction_multiplier: float = Field(default=1.0, ge=0.0, le=4.0)
    fuel_lhv_J_per_kg: float = Field(default=43.5e6, gt=1.0e6, le=1.4e8)

    # Output control
    include_trace: bool = True

    def to_cycle_inputs(self) -> PistonCycleInputs:
        """Build the engine-core inputs (integration window left at defaults)."""

        return PistonCycleInputs(
            bore_m=self.bore_m,
            stroke_m=self.stroke_m,
            compression_ratio=self.compression_ratio,
            rod_ratio=self.rod_ratio,
            cylinders=self.cylinders,
            strokes_per_cycle=self.strokes_per_cycle,
            rpm=self.rpm,
            gamma=self.gamma,
            gas_constant_J_per_kg_K=self.gas_constant_J_per_kg_K,
            intake_temperature_K=self.intake_temperature_K,
            intake_pressure_Pa=self.intake_pressure_Pa,
            exhaust_pressure_Pa=self.exhaust_pressure_Pa,
            aspiration=self.aspiration,
            ambient_pressure_Pa=self.ambient_pressure_Pa,
            supercharger_efficiency=self.supercharger_efficiency,
            heat_release_J_per_kg=self.heat_release_J_per_kg,
            fuel=self.fuel,
            equivalence_ratio=self.equivalence_ratio,
            combustion_efficiency=self.combustion_efficiency,
            combustion_start_deg=self.combustion_start_deg,
            burn_duration_deg=self.burn_duration_deg,
            wiebe_a=self.wiebe_a,
            wiebe_m=self.wiebe_m,
            wall_temperature_K=self.wall_temperature_K,
            wall_heat_transfer_multiplier=self.wall_heat_transfer_multiplier,
            friction_multiplier=self.friction_multiplier,
            fuel_lhv_J_per_kg=self.fuel_lhv_J_per_kg,
        )


class PistonOperatingWarningOut(BaseModel):
    kind: str
    severity: str
    message: str


class PistonTracePointOut(BaseModel):
    theta_deg: float
    volume_m3: float
    pressure_Pa: float
    temperature_K: float
    entropy_J_per_kg_K: float


class PistonSimulateOutput(BaseModel):
    """Full result for one operating point (mirrors PistonCycleResult)."""

    # Indicated
    indicated_work_J: float
    imep_Pa: float
    indicated_power_W: float
    indicated_torque_Nm: float
    thermal_efficiency: float
    air_standard_efficiency: float
    peak_pressure_Pa: float
    peak_temperature_K: float
    trapped_mass_kg: float
    heat_released_J: float
    wall_heat_loss_J: float
    energy_residual_J: float
    # Pumping
    pmep_Pa: float
    pumping_work_J: float
    net_imep_Pa: float
    net_indicated_work_J: float
    # Brake
    fmep_Pa: float
    bmep_Pa: float
    brake_work_J: float
    brake_power_W: float
    brake_torque_Nm: float
    mechanical_efficiency: float
    brake_thermal_efficiency: float
    bsfc_g_per_kWh: float
    fuel_mass_per_cycle_kg: float
    # Aspiration
    aspiration: str
    boost_pressure_Pa: float
    supercharger_power_W: float
    # Fuelling
    fuel: str
    equivalence_ratio: float
    lambda_air: float
    fuel_air_ratio: float
    air_fuel_ratio: float
    operating_warnings: list[PistonOperatingWarningOut]
    trace: list[PistonTracePointOut]

    @classmethod
    def from_result(cls, result: PistonCycleResult, include_trace: bool) -> "PistonSimulateOutput":
        data = result.to_dict()
        if not include_trace:
            data = {**data, "trace": []}
        return cls.model_validate(data)


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

# Parameters that make physical sense to sweep (a dyno is an rpm sweep).
SWEEPABLE_PARAMETERS = (
    "rpm",
    "compression_ratio",
    "equivalence_ratio",
    "intake_pressure_Pa",
    "combustion_start_deg",
    "burn_duration_deg",
    "wall_heat_transfer_multiplier",
)


class PistonSweepInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_input: PistonSimulateInput = Field(default_factory=PistonSimulateInput)
    sweep_parameter: Literal[SWEEPABLE_PARAMETERS] = "rpm"  # type: ignore[valid-type]
    values: list[float] = Field(default=[1000, 2000, 3000, 4000, 5000, 6000], min_length=1, max_length=80)


class PistonSweepMetrics(BaseModel):
    """Compact per-case metrics (no trace) for dyno / parameter curves."""

    indicated_power_W: float
    brake_power_W: float
    brake_torque_Nm: float
    imep_Pa: float
    bmep_Pa: float
    bsfc_g_per_kWh: float
    thermal_efficiency: float
    brake_thermal_efficiency: float
    peak_pressure_Pa: float
    peak_temperature_K: float
    operating_warnings: list[PistonOperatingWarningOut]

    @classmethod
    def from_result(cls, result: PistonCycleResult) -> "PistonSweepMetrics":
        d = result.to_dict()
        return cls(
            indicated_power_W=d["indicated_power_W"],
            brake_power_W=d["brake_power_W"],
            brake_torque_Nm=d["brake_torque_Nm"],
            imep_Pa=d["imep_Pa"],
            bmep_Pa=d["bmep_Pa"],
            bsfc_g_per_kWh=d["bsfc_g_per_kWh"] if d["bsfc_g_per_kWh"] != float("inf") else -1.0,
            thermal_efficiency=d["thermal_efficiency"],
            brake_thermal_efficiency=d["brake_thermal_efficiency"],
            peak_pressure_Pa=d["peak_pressure_Pa"],
            peak_temperature_K=d["peak_temperature_K"],
            operating_warnings=d["operating_warnings"],
        )


class PistonSweepCaseOutput(BaseModel):
    input_value: float
    success: bool
    output: PistonSweepMetrics | None = None
    error: str | None = None


class PistonSweepSummary(BaseModel):
    successful_cases: int
    failed_cases: int
    peak_brake_power_W: float | None = None
    peak_brake_torque_Nm: float | None = None
    min_bsfc_g_per_kWh: float | None = None
    knock_cases: int = 0


class PistonSweepOutput(BaseModel):
    sweep_parameter: str
    cases: list[PistonSweepCaseOutput]
    summary: PistonSweepSummary


def run_piston_simulation(payload: PistonSimulateInput) -> PistonSimulateOutput:
    """Run one point, translating solver ValueErrors to the caller."""

    result = simulate_piston_cycle(payload.to_cycle_inputs())
    return PistonSimulateOutput.from_result(result, include_trace=payload.include_trace)


def run_piston_sweep(payload: PistonSweepInput) -> PistonSweepOutput:
    """Sweep one parameter, collecting per-case metrics and a summary."""

    cases: list[PistonSweepCaseOutput] = []
    powers: list[float] = []
    torques: list[float] = []
    bsfcs: list[float] = []
    knock = 0
    for value in payload.values:
        merged = payload.base_input.model_copy(update={payload.sweep_parameter: value})
        try:
            result = simulate_piston_cycle(merged.to_cycle_inputs())
        except ValueError as exc:
            cases.append(PistonSweepCaseOutput(input_value=value, success=False, error=str(exc)))
            continue
        metrics = PistonSweepMetrics.from_result(result)
        cases.append(PistonSweepCaseOutput(input_value=value, success=True, output=metrics))
        powers.append(metrics.brake_power_W)
        torques.append(metrics.brake_torque_Nm)
        if metrics.bsfc_g_per_kWh > 0:
            bsfcs.append(metrics.bsfc_g_per_kWh)
        if any(w.kind == "knock" for w in metrics.operating_warnings):
            knock += 1

    summary = PistonSweepSummary(
        successful_cases=sum(1 for c in cases if c.success),
        failed_cases=sum(1 for c in cases if not c.success),
        peak_brake_power_W=max(powers) if powers else None,
        peak_brake_torque_Nm=max(torques) if torques else None,
        min_bsfc_g_per_kWh=min(bsfcs) if bsfcs else None,
        knock_cases=knock,
    )
    return PistonSweepOutput(sweep_parameter=payload.sweep_parameter, cases=cases, summary=summary)
