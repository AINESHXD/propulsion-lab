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

import math
import time
from dataclasses import replace
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.engine_core.piston import (
    FUEL_NAMES,
    PistonCycleInputs,
    PistonCycleResult,
    simulate_piston_cycle,
)
from app.engine_core.piston.geometry import bore_stroke_from_displacement
from app.engine_core.piston.layout import EngineLayout
from app.engine_core.piston.valvetrain import ValveGeometry, ValveTiming

AspirationMode = Literal["naturally_aspirated", "turbocharged", "supercharged"]
FuelName = Literal["gasoline", "diesel", "ethanol", "methanol"]
LayoutKind = Literal["single", "inline", "vee", "flat", "w", "radial"]
CrankType = Literal["flat_plane", "cross_plane"]


class PistonLayoutIn(BaseModel):
    """How the cylinders are arranged.

    The cylinder count and stroke count are deliberately *not* repeated here —
    they come from the parent input, so the two can never disagree.
    """

    model_config = ConfigDict(extra="forbid")

    kind: LayoutKind = "inline"
    bank_angle_deg: float = Field(default=0.0, ge=0.0, le=180.0)
    crankpin_offset_deg: float = Field(default=0.0, ge=-180.0, le=180.0)
    crank_type: CrankType = "flat_plane"

    def to_engine_layout(self, cylinders: int, strokes_per_cycle: int,
                         rod_ratio: float) -> EngineLayout:
        return EngineLayout(
            kind=self.kind,
            cylinders=cylinders,
            bank_angle_deg=self.bank_angle_deg,
            crankpin_offset_deg=self.crankpin_offset_deg,
            strokes_per_cycle=strokes_per_cycle,
            rod_ratio=rod_ratio,
            crank_type=self.crank_type,
        )


class PistonValveTimingIn(BaseModel):
    """Cam card, in the usual workshop convention."""

    model_config = ConfigDict(extra="forbid")

    intake_open_btdc_deg: float = Field(default=10.0, ge=-60.0, le=120.0)
    intake_close_abdc_deg: float = Field(default=40.0, ge=-60.0, le=120.0)
    exhaust_open_bbdc_deg: float = Field(default=45.0, ge=-60.0, le=120.0)
    exhaust_close_atdc_deg: float = Field(default=10.0, ge=-60.0, le=120.0)

    def to_valve_timing(self) -> ValveTiming:
        return ValveTiming(
            intake_open_btdc_deg=self.intake_open_btdc_deg,
            intake_close_abdc_deg=self.intake_close_abdc_deg,
            exhaust_open_bbdc_deg=self.exhaust_open_bbdc_deg,
            exhaust_close_atdc_deg=self.exhaust_close_atdc_deg,
        )


class PistonValveGeometryIn(BaseModel):
    """Port and valve sizing, as ratios of the bore."""

    model_config = ConfigDict(extra="forbid")

    intake_valves_per_cylinder: int = Field(default=2, ge=1, le=4)
    exhaust_valves_per_cylinder: int = Field(default=2, ge=1, le=4)
    intake_valve_diameter_ratio: float = Field(default=0.38, ge=0.15, le=0.60)
    exhaust_valve_diameter_ratio: float = Field(default=0.33, ge=0.15, le=0.60)
    max_lift_ratio: float = Field(default=0.25, ge=0.10, le=0.40)
    discharge_coefficient: float = Field(default=0.35, ge=0.15, le=0.80)
    exhaust_restriction: float = Field(default=1.0, ge=0.0, le=4.0)

    def to_valve_geometry(self) -> ValveGeometry:
        return ValveGeometry(
            intake_valves_per_cylinder=self.intake_valves_per_cylinder,
            exhaust_valves_per_cylinder=self.exhaust_valves_per_cylinder,
            intake_valve_diameter_ratio=self.intake_valve_diameter_ratio,
            exhaust_valve_diameter_ratio=self.exhaust_valve_diameter_ratio,
            max_lift_ratio=self.max_lift_ratio,
            discharge_coefficient=self.discharge_coefficient,
            exhaust_restriction=self.exhaust_restriction,
        )


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
    compressor_efficiency: float = Field(default=0.72, gt=0.0, le=1.0)
    turbine_efficiency: float = Field(default=0.70, gt=0.0, le=1.0)
    turbo_mechanical_efficiency: float = Field(default=0.98, gt=0.0, le=1.0)

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

    # --- Custom engine builder ---
    # A builder thinks in capacity, not millimetres. Supplying both of these
    # derives bore and stroke server-side and overrides the pair above, so the
    # geometry has exactly one source of truth.
    displacement_L: float | None = Field(default=None, gt=0.05, le=100.0)
    bore_stroke_ratio: float | None = Field(default=None, gt=0.4, le=2.5)

    layout: PistonLayoutIn | None = None
    valve_timing: PistonValveTimingIn | None = None
    valve_geometry: PistonValveGeometryIn | None = None

    # --- Gas model. On by default here: the browser should get the honest
    # model without having to ask for it. The engine-core dataclass keeps
    # them off so a direct solver call is unchanged. ---
    variable_specific_heats: bool = True
    two_zone_combustion: bool = True

    # Numerical control
    #
    # The crank-angle step is the resolution of the integration itself, not a
    # physical property of the engine. It was previously fixed at 0.5 deg and
    # unreachable from the API, which meant a caller had no way to check whether
    # an answer was converged or an artefact of the step. Exposing it makes that
    # checkable — see /simulate/piston/convergence.
    d_theta_deg: float = Field(
        0.5,
        gt=0.0,
        le=5.0,
        description=(
            "Crank-angle step for the integration, in degrees. Smaller is more "
            "accurate and slower; 0.5 deg is converged for most cases. This is a "
            "numerical setting, not a physical one — changing it should barely "
            "move the answer, and if it does the answer was not converged."
        ),
    )

    # Output control
    include_trace: bool = True

    @model_validator(mode="after")
    def _capacity_needs_a_ratio(self) -> "PistonSimulateInput":
        if (self.displacement_L is None) != (self.bore_stroke_ratio is None):
            raise ValueError(
                "displacement_L and bore_stroke_ratio must be given together: "
                "a capacity alone does not fix the bore and stroke."
            )
        return self

    def resolved_bore_stroke_m(self) -> tuple[float, float]:
        """Bore and stroke actually used, after any capacity-driven override."""

        if self.displacement_L is None or self.bore_stroke_ratio is None:
            return self.bore_m, self.stroke_m
        return bore_stroke_from_displacement(
            total_displacement_m3=self.displacement_L * 1.0e-3,
            cylinders=self.cylinders,
            bore_stroke_ratio=self.bore_stroke_ratio,
        )

    def to_cycle_inputs(self) -> PistonCycleInputs:
        """Build the engine-core inputs, including the integration step."""

        bore_m, stroke_m = self.resolved_bore_stroke_m()
        return PistonCycleInputs(
            d_theta_deg=self.d_theta_deg,
            bore_m=bore_m,
            stroke_m=stroke_m,
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
            compressor_efficiency=self.compressor_efficiency,
            turbine_efficiency=self.turbine_efficiency,
            turbo_mechanical_efficiency=self.turbo_mechanical_efficiency,
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
            layout=(
                self.layout.to_engine_layout(
                    cylinders=self.cylinders,
                    strokes_per_cycle=self.strokes_per_cycle,
                    rod_ratio=self.rod_ratio,
                )
                if self.layout is not None else None
            ),
            valve_timing=(
                self.valve_timing.to_valve_timing() if self.valve_timing is not None else None
            ),
            valve_geometry=(
                self.valve_geometry.to_valve_geometry()
                if self.valve_geometry is not None else None
            ),
            variable_specific_heats=self.variable_specific_heats,
            two_zone_combustion=self.two_zone_combustion,
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
    burned_fraction: float = 0.0
    # Present only on a two-zone solve; the console draws the flame front from
    # the volume fraction and tints each zone by its own temperature.
    burned_volume_fraction: float | None = None
    unburned_temperature_K: float | None = None
    burned_temperature_K: float | None = None


class PistonBalanceOut(BaseModel):
    """Dimensionless shaking residuals: 0 cancels, 1 is one bare cylinder."""

    primary_force: float
    secondary_force: float
    primary_couple: float
    secondary_couple: float
    secondary_force_ratio: float


class PistonLayoutOut(BaseModel):
    """Firing and balance analysis for the chosen arrangement."""

    kind: str
    cylinders: int
    banks: int
    cylinders_per_bank: int
    bank_angle_deg: float
    crankpin_offset_deg: float
    crank_throws: int
    main_bearings: int
    cylinder_heads: int
    ideal_firing_interval_deg: float
    firing_intervals_deg: list[float]
    even_fire: bool
    balance: PistonBalanceOut
    balance_verdict: str
    friction_scale: float
    description: str


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
    exhaust_pressure_Pa: float = 1.0e5
    compressor_power_W: float = 0.0
    turbine_pressure_ratio: float | None = None
    boost_sustainable: bool = True
    exhaust_temperature_K: float = 0.0
    residual_fraction: float | None = None
    fresh_mass_kg: float | None = None
    mixed_temperature_K: float | None = None
    variable_specific_heats: bool = False
    two_zone_combustion: bool = False
    mean_gamma: float | None = None
    peak_unburned_temperature_K: float | None = None
    peak_burned_temperature_K: float | None = None
    # Fuelling
    fuel: str
    equivalence_ratio: float
    lambda_air: float
    fuel_air_ratio: float
    air_fuel_ratio: float
    operating_warnings: list[PistonOperatingWarningOut]
    # --- Builder extras. Null unless the matching input was supplied. ---
    effective_compression_ratio: float | None = None
    effective_expansion_ratio: float | None = None
    volumetric_efficiency: float | None = None
    inlet_mach_index: float | None = None
    exhaust_mach_index: float | None = None
    valve_overlap_deg: float | None = None
    closed_period_deg: float | None = None
    breathing_verdict: str | None = None
    layout: PistonLayoutOut | None = None
    layout_friction_scale: float | None = None
    # Resolved geometry, so a capacity-driven build can read back what it got.
    bore_m: float | None = None
    stroke_m: float | None = None
    total_displacement_m3: float | None = None
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


# --------------------------------------------------------------------------- #
# numerical convergence
# --------------------------------------------------------------------------- #
class ConvergenceStepOutput(BaseModel):
    """One rung of the refinement ladder."""

    d_theta_deg: float = Field(..., description="Crank-angle step used for this run.")
    steps_per_cycle: int = Field(..., description="Integration steps in one full cycle.")
    brake_power_W: float
    imep_Pa: float
    peak_pressure_Pa: float
    thermal_efficiency: float
    solve_ms: float = Field(..., description="Wall-clock time for this run.")
    power_change_percent: float | None = Field(
        None,
        description=(
            "Change in brake power against the previous, coarser step. This is "
            "the number that matters: once it stops moving, refining further "
            "buys nothing."
        ),
    )


class ConvergenceReportOutput(BaseModel):
    """Whether the answer is a property of the engine or of the step size."""

    steps: list[ConvergenceStepOutput]
    converged: bool = Field(
        ...,
        description=(
            "True when halving the step moves brake power by less than the "
            "tolerance, i.e. the answer is set by the physics rather than by "
            "the discretisation."
        ),
    )
    tolerance_percent: float
    recommended_d_theta_deg: float = Field(
        ...,
        description="Coarsest step that still meets the tolerance — the cheapest converged answer.",
    )
    finest_vs_default_percent: float = Field(
        ...,
        description=(
            "How far the default 0.5 deg step sits from the finest step tried. "
            "This is the honest size of the discretisation error you accept by "
            "using the default."
        ),
    )
    observed_order: float | None = Field(
        None,
        description=(
            "Observed order of convergence, from how fast the change shrinks as "
            "the step halves. A first-order march should give about 1.0. If it "
            "comes out far below that, the integration is not behaving as its "
            "scheme says it should — which is worth knowing."
        ),
    )
    verdict: str


def run_piston_simulation(payload: PistonSimulateInput) -> PistonSimulateOutput:
    """Run one point, translating solver ValueErrors to the caller."""

    result = simulate_piston_cycle(payload.to_cycle_inputs())
    return PistonSimulateOutput.from_result(result, include_trace=payload.include_trace)


# Refinement ladder, coarse to fine. Each rung halves the step, so the change
# between rungs is directly the discretisation error being removed.
CONVERGENCE_LADDER: tuple[float, ...] = (4.0, 2.0, 1.0, 0.5, 0.25, 0.125)
CONVERGENCE_TOLERANCE_PERCENT = 0.1
DEFAULT_D_THETA_DEG = 0.5


def run_piston_convergence(
    payload: PistonSimulateInput,
    tolerance_percent: float = CONVERGENCE_TOLERANCE_PERCENT,
) -> ConvergenceReportOutput:
    """Re-solve one engine down a refinement ladder and report grid independence.

    A number a solver prints is only meaningful if it is a property of the
    engine rather than of the step size used to integrate it. This runs the same
    engine at successively halved crank-angle steps and shows how much the
    answer actually moves, so the caller can see the discretisation error rather
    than take it on trust.
    """

    steps: list[ConvergenceStepOutput] = []
    previous_power: float | None = None
    for d_theta in CONVERGENCE_LADDER:
        started = time.perf_counter()
        result = simulate_piston_cycle(
            replace(payload.to_cycle_inputs(), d_theta_deg=d_theta)
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        power = float(result.brake_power_W)
        change = (
            None
            if previous_power is None or previous_power == 0.0
            else 100.0 * (power - previous_power) / abs(previous_power)
        )
        steps.append(
            ConvergenceStepOutput(
                d_theta_deg=d_theta,
                steps_per_cycle=int(round(360.0 * payload.strokes_per_cycle / 2.0 / d_theta)),
                brake_power_W=power,
                imep_Pa=float(result.imep_Pa),
                peak_pressure_Pa=float(result.peak_pressure_Pa),
                thermal_efficiency=float(result.thermal_efficiency),
                solve_ms=elapsed_ms,
                power_change_percent=change,
            )
        )
        previous_power = power

    # Converged when the finest refinement stopped changing the answer.
    finest_change = steps[-1].power_change_percent
    converged = finest_change is not None and abs(finest_change) < tolerance_percent

    # Cheapest step whose *next* refinement changed nothing material.
    recommended = steps[-1].d_theta_deg
    for index in range(1, len(steps)):
        change = steps[index].power_change_percent
        if change is not None and abs(change) < tolerance_percent:
            recommended = steps[index - 1].d_theta_deg
            break

    default_power = next(
        (s.brake_power_W for s in steps if s.d_theta_deg == DEFAULT_D_THETA_DEG),
        steps[-1].brake_power_W,
    )
    finest_power = steps[-1].brake_power_W
    finest_vs_default = (
        0.0 if finest_power == 0.0 else 100.0 * (default_power - finest_power) / abs(finest_power)
    )

    # Observed order: halving the step should shrink the change by 2**p. Read it
    # off the finest pair available, where the asymptotic behaviour is cleanest.
    observed_order: float | None = None
    changes = [abs(s.power_change_percent) for s in steps if s.power_change_percent]
    if len(changes) >= 2 and changes[-1] > 0.0:
        ratio = changes[-2] / changes[-1]
        if ratio > 0.0:
            observed_order = math.log2(ratio)

    if not converged:
        verdict = (
            f"Not converged: halving the step from {steps[-2].d_theta_deg}° to "
            f"{steps[-1].d_theta_deg}° still moved brake power by "
            f"{abs(finest_change or 0.0):.2f}%. Treat this operating point as "
            f"step-dependent and refine further."
        )
    else:
        verdict = (
            f"Converged. The default {DEFAULT_D_THETA_DEG}° step sits "
            f"{abs(finest_vs_default):.2f}% from the finest step tried, and "
            f"{recommended}° already meets the {tolerance_percent}% tolerance — "
            f"anything finer costs time and buys nothing."
        )

    return ConvergenceReportOutput(
        steps=steps,
        converged=converged,
        tolerance_percent=tolerance_percent,
        recommended_d_theta_deg=recommended,
        finest_vs_default_percent=finest_vs_default,
        observed_order=observed_order,
        verdict=verdict,
    )


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
