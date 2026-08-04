"""Pydantic schemas for the inverse cycle solver.

The forward API asks "what does this engine do?". This one asks the question a
test engineer actually has: "here is what I measured — what is the engine's
internal condition?". Kept in its own module the way the PistonLab surface is,
so the inverse problem's vocabulary does not leak into the forward schemas.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.engine_core.inverse import (
    OBSERVABLE_KEYS,
    SOLVABLE_PARAMETERS,
    InverseResult,
    Measurement,
    Unknown,
    solve_inverse_cycle,
)
from app.engine_core.types import TurbojetCycleInputs

ObservableKey = Literal[OBSERVABLE_KEYS]        # type: ignore[valid-type]
ParameterKey = Literal[tuple(SOLVABLE_PARAMETERS)]  # type: ignore[valid-type]


class MeasurementIn(BaseModel):
    """One observed quantity and the uncertainty it was measured to."""

    model_config = ConfigDict(extra="forbid")

    key: ObservableKey
    value: float
    sigma: float | None = Field(
        default=None, gt=0.0,
        description="1-sigma absolute uncertainty. Defaults to 1% of the reading.",
    )

    def to_measurement(self) -> Measurement:
        return Measurement(key=self.key, value=self.value, sigma=self.sigma)


class UnknownIn(BaseModel):
    """One internal parameter to recover, optionally bounded by the caller."""

    model_config = ConfigDict(extra="forbid")

    key: ParameterKey
    initial: float | None = None
    lower: float | None = None
    upper: float | None = None

    def to_unknown(self) -> Unknown:
        return Unknown(key=self.key, initial=self.initial,
                       lower=self.lower, upper=self.upper)


class InverseSolveInput(BaseModel):
    """A complete inverse problem: what was fixed, measured, and is being sought."""

    model_config = ConfigDict(extra="forbid")

    # Flight condition and everything else held fixed. Starting values for the
    # unknowns are taken from here unless the caller overrides them.
    altitude_m: float = Field(default=10000.0, ge=0.0, le=30000.0)
    mach: float = Field(default=0.8, ge=0.0, le=4.0)
    mass_flow_air_kg_s: float = Field(default=50.0, gt=0.0, le=2000.0)
    compressor_pressure_ratio: float = Field(default=12.0, gt=1.0, le=60.0)
    compressor_efficiency: float = Field(default=0.86, gt=0.0, le=1.0)
    turbine_inlet_temperature_K: float = Field(default=1400.0, gt=300.0, le=2400.0)
    turbine_efficiency: float = Field(default=0.88, gt=0.0, le=1.0)
    combustor_efficiency: float = Field(default=0.99, gt=0.0, le=1.0)
    combustor_pressure_loss_fraction: float = Field(default=0.05, ge=0.0, le=0.3)
    mechanical_efficiency: float = Field(default=0.99, gt=0.0, le=1.0)
    nozzle_efficiency: float = Field(default=0.95, gt=0.0, le=1.0)
    inlet_pressure_recovery: float = Field(default=0.98, gt=0.0, le=1.0)

    measurements: list[MeasurementIn] = Field(min_length=1, max_length=20)
    unknowns: list[UnknownIn] = Field(min_length=1, max_length=8)
    max_evaluations: int = Field(default=400, ge=20, le=5000)

    @model_validator(mode="after")
    def _no_duplicates(self) -> "InverseSolveInput":
        m = [x.key for x in self.measurements]
        u = [x.key for x in self.unknowns]
        if len(set(m)) != len(m):
            raise ValueError("The same observable cannot be measured twice.")
        if len(set(u)) != len(u):
            raise ValueError("The same parameter cannot be solved for twice.")
        return self

    def to_cycle_inputs(self) -> TurbojetCycleInputs:
        return TurbojetCycleInputs(
            altitude_m=self.altitude_m,
            mach=self.mach,
            mass_flow_air_kg_s=self.mass_flow_air_kg_s,
            compressor_pressure_ratio=self.compressor_pressure_ratio,
            compressor_efficiency=self.compressor_efficiency,
            turbine_inlet_temperature_K=self.turbine_inlet_temperature_K,
            turbine_efficiency=self.turbine_efficiency,
            combustor_efficiency=self.combustor_efficiency,
            combustor_pressure_loss_fraction=self.combustor_pressure_loss_fraction,
            mechanical_efficiency=self.mechanical_efficiency,
            nozzle_efficiency=self.nozzle_efficiency,
            inlet_pressure_recovery=self.inlet_pressure_recovery,
        )


class RecoveredParameterOut(BaseModel):
    key: str
    value: float
    standard_error: float | None
    relative_error: float | None
    identifiable: bool
    at_bound: bool
    lower_bound: float
    upper_bound: float


class ResidualOut(BaseModel):
    key: str
    measured: float
    modelled: float
    sigma: float
    normalised_residual: float


class InverseSolveOutput(BaseModel):
    """The recovered engine condition, with everything needed to judge it."""

    converged: bool
    determined: bool
    well_conditioned: bool
    parameters: list[RecoveredParameterOut]
    residuals: list[ResidualOut]
    rms_normalised_residual: float
    max_absolute_relative_error: float
    jacobian_condition_number: float | None
    function_evaluations: int
    message: str
    verdict: str
    warnings: list[str]

    @classmethod
    def from_result(cls, result: InverseResult) -> "InverseSolveOutput":
        return cls.model_validate(result.to_dict())


class InverseCatalogueOutput(BaseModel):
    """What the solver can be asked for, so the UI never has to hard-code it."""

    observables: list[str]
    parameters: dict[str, list[float]]


def inverse_catalogue() -> InverseCatalogueOutput:
    return InverseCatalogueOutput(
        observables=list(OBSERVABLE_KEYS),
        parameters={k: [lo, hi] for k, (lo, hi) in SOLVABLE_PARAMETERS.items()},
    )


def run_inverse_solve(payload: InverseSolveInput) -> InverseSolveOutput:
    """Solve one inverse problem, translating solver errors to the caller."""

    result = solve_inverse_cycle(
        base_inputs=payload.to_cycle_inputs(),
        measurements=[m.to_measurement() for m in payload.measurements],
        unknowns=[u.to_unknown() for u in payload.unknowns],
        max_evaluations=payload.max_evaluations,
    )
    return InverseSolveOutput.from_result(result)
