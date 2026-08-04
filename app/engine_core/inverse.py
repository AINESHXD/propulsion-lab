"""Inverse cycle solver: recover hidden internal parameters from telemetry.

The forward solver answers "given these efficiencies, what thrust do I get?".
On a real engine the arrow points the other way. You can measure thrust, fuel
flow and a handful of gas-path temperatures and pressures; you cannot measure
the compressor's polytropic efficiency, and that is exactly the number that
tells you whether the engine is healthy. Working out the second from the first
is **gas-path analysis**, and it is how engine health monitoring actually works.

The method
----------
Wrap the forward cycle in a residual function and let a bounded least-squares
solver find the parameter set that reproduces what was measured::

    r_i = (model_i(x) - measured_i) / sigma_i

Residuals are divided by the measurement uncertainty before they are summed, so
a 36 kN thrust reading and a 1.3 kg/s fuel flow contribute on equal terms
instead of thrust swamping everything.

Why identifiability is reported, not assumed
--------------------------------------------
An inverse problem can return a confident-looking answer that means nothing.
Two failure modes matter here, and both are reported rather than hidden:

* **Underdetermined.** Solving for more unknowns than there are measurements
  admits infinitely many exact fits. The residual will be ~0 and the answer will
  still be meaningless.
* **Ill-conditioned.** Even with enough measurements, two parameters can have
  nearly the same effect on everything observable — compressor and turbine
  efficiency both mostly show up as thrust and fuel flow. The fit then trades
  one against the other freely, and a tight residual hides a wide range of
  equally good answers.

So the result carries a per-parameter standard error taken from the covariance
at the solution, the Jacobian's condition number, and a plain verdict. A number
without its uncertainty is not an answer to this kind of question.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import TurbojetCycleInputs

# Parameters worth solving for, with the physical range each is confined to.
# Bounds are not cosmetic: they keep the optimiser inside the region where the
# forward model is valid, so a bad measurement cannot walk it into nonsense.
SOLVABLE_PARAMETERS: dict[str, tuple[float, float]] = {
    "compressor_efficiency": (0.50, 0.995),
    "turbine_efficiency": (0.50, 0.995),
    "combustor_efficiency": (0.70, 1.0),
    "nozzle_efficiency": (0.70, 0.999),
    "inlet_pressure_recovery": (0.70, 1.0),
    "mechanical_efficiency": (0.80, 1.0),
    "combustor_pressure_loss_fraction": (0.0, 0.20),
    "compressor_pressure_ratio": (1.5, 60.0),
    "turbine_inlet_temperature_K": (600.0, 2200.0),
    "mass_flow_air_kg_s": (0.5, 2000.0),
}

# Observables a real test campaign can actually produce. Station quantities use
# ``station_<n>_<field>``; everything else is a top-level scalar of the forward
# result.
_STATION_FIELDS = ("stagnation_temperature_K", "stagnation_pressure_Pa")

OBSERVABLE_KEYS: tuple[str, ...] = (
    "thrust_N",
    "thrust_kN",
    "fuel_flow_kg_s",
    "TSFC_kg_per_kN_hr",
    "specific_thrust_N_per_kg_s",
    "exit_velocity_m_s",
    "nozzle_exit_pressure_Pa",
    "fuel_air_ratio",
    "station_3_stagnation_temperature_K",
    "station_3_stagnation_pressure_Pa",
    "station_5_stagnation_temperature_K",
    "station_5_stagnation_pressure_Pa",
    "station_9_stagnation_temperature_K",
)

# Default 1-sigma uncertainty when the caller does not supply one, as a
# fraction of the reading. Instrumentation is never perfect and pretending it is
# produces overconfident error bars.
_DEFAULT_RELATIVE_SIGMA = 0.01

# A parameter whose standard error exceeds this fraction of its own value is
# reported as not identifiable from the measurements given.
_IDENTIFIABLE_RELATIVE_SIGMA = 0.10

# Above this Jacobian condition number the parameters are effectively collinear.
_ILL_CONDITIONED = 1.0e6


@dataclass(slots=True, frozen=True)
class Measurement:
    """One observed quantity, with the uncertainty it was measured to."""

    key: str
    value: float
    sigma: float | None = None          # 1-sigma absolute; defaults to 1% of value

    def __post_init__(self) -> None:
        if self.key not in OBSERVABLE_KEYS:
            raise ValueError(
                f"{self.key!r} is not an observable. Choose from: {', '.join(OBSERVABLE_KEYS)}"
            )
        if self.sigma is not None and self.sigma <= 0.0:
            raise ValueError("sigma must be positive.")

    @property
    def effective_sigma(self) -> float:
        if self.sigma is not None:
            return self.sigma
        return max(abs(self.value) * _DEFAULT_RELATIVE_SIGMA, 1.0e-9)


@dataclass(slots=True, frozen=True)
class Unknown:
    """One parameter to solve for, optionally with a starting point and bounds."""

    key: str
    initial: float | None = None
    lower: float | None = None
    upper: float | None = None

    def __post_init__(self) -> None:
        if self.key not in SOLVABLE_PARAMETERS:
            raise ValueError(
                f"{self.key!r} cannot be solved for. Choose from: "
                f"{', '.join(SOLVABLE_PARAMETERS)}"
            )
        lo, hi = self.bounds
        if lo >= hi:
            raise ValueError(f"{self.key}: lower bound must be below upper bound.")

    @property
    def bounds(self) -> tuple[float, float]:
        lo, hi = SOLVABLE_PARAMETERS[self.key]
        return (self.lower if self.lower is not None else lo,
                self.upper if self.upper is not None else hi)


@dataclass(slots=True)
class RecoveredParameter:
    key: str
    value: float
    standard_error: float | None
    relative_error: float | None
    identifiable: bool
    at_bound: bool
    bounds: tuple[float, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "standard_error": self.standard_error,
            "relative_error": self.relative_error,
            "identifiable": self.identifiable,
            "at_bound": self.at_bound,
            "lower_bound": self.bounds[0],
            "upper_bound": self.bounds[1],
        }


@dataclass(slots=True)
class ResidualReport:
    key: str
    measured: float
    modelled: float
    sigma: float
    normalised_residual: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "measured": self.measured,
            "modelled": self.modelled,
            "sigma": self.sigma,
            "normalised_residual": self.normalised_residual,
        }


@dataclass(slots=True)
class InverseResult:
    converged: bool
    determined: bool                     # measurements >= unknowns
    well_conditioned: bool
    parameters: list[RecoveredParameter]
    residuals: list[ResidualReport]
    rms_normalised_residual: float
    max_absolute_relative_error: float
    jacobian_condition_number: float | None
    function_evaluations: int
    message: str
    verdict: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "converged": self.converged,
            "determined": self.determined,
            "well_conditioned": self.well_conditioned,
            "parameters": [p.to_dict() for p in self.parameters],
            "residuals": [r.to_dict() for r in self.residuals],
            "rms_normalised_residual": self.rms_normalised_residual,
            "max_absolute_relative_error": self.max_absolute_relative_error,
            "jacobian_condition_number": self.jacobian_condition_number,
            "function_evaluations": self.function_evaluations,
            "message": self.message,
            "verdict": self.verdict,
            "warnings": self.warnings,
        }


def observe(result: dict[str, Any], key: str) -> float:
    """Pull one observable out of a forward-solver result."""

    if key.startswith("station_"):
        _, number, field_name = key.split("_", 2)
        if field_name not in _STATION_FIELDS:
            raise ValueError(f"Unknown station field {field_name!r}.")
        table = result.get("station_table") or {}
        station = table.get(int(number))
        if station is None:
            raise ValueError(
                f"Station {number} is not present for this engine variant."
            )
        return float(station[field_name])
    if key not in result:
        raise ValueError(f"Observable {key!r} is not in the forward result.")
    return float(result[key])


def solve_inverse_cycle(base_inputs: TurbojetCycleInputs,
                        measurements: list[Measurement],
                        unknowns: list[Unknown],
                        max_evaluations: int = 400) -> InverseResult:
    """Recover ``unknowns`` from ``measurements`` around ``base_inputs``.

    ``base_inputs`` carries everything held fixed — flight condition, geometry,
    and starting values for the unknowns. Only the parameters named in
    ``unknowns`` are allowed to move.
    """

    if not measurements:
        raise ValueError("At least one measurement is required.")
    if not unknowns:
        raise ValueError("At least one unknown is required.")
    keys = [u.key for u in unknowns]
    if len(set(keys)) != len(keys):
        raise ValueError("The same parameter cannot be solved for twice.")
    m_keys = [m.key for m in measurements]
    if len(set(m_keys)) != len(m_keys):
        raise ValueError("The same observable cannot be measured twice.")

    start = np.array([
        u.initial if u.initial is not None else float(getattr(base_inputs, u.key))
        for u in unknowns
    ], dtype=float)
    lower = np.array([u.bounds[0] for u in unknowns], dtype=float)
    upper = np.array([u.bounds[1] for u in unknowns], dtype=float)
    start = np.clip(start, lower + 1e-12, upper - 1e-12)

    targets = np.array([m.value for m in measurements], dtype=float)
    sigmas = np.array([m.effective_sigma for m in measurements], dtype=float)

    # Solve in a normalised space so every parameter takes comparable steps
    # regardless of whether it is an efficiency (~0.9) or a mass flow (~50).
    span = upper - lower

    def denormalise(z: np.ndarray) -> np.ndarray:
        return lower + np.clip(z, 0.0, 1.0) * span

    def forward(values: np.ndarray) -> np.ndarray:
        overrides = {u.key: float(v) for u, v in zip(unknowns, values)}
        trial = replace_inputs(base_inputs, overrides)
        result = simulate_turbojet_cycle(trial)
        return np.array([observe(result, m.key) for m in measurements], dtype=float)

    def residual(z: np.ndarray) -> np.ndarray:
        try:
            modelled = forward(denormalise(z))
        except Exception:
            # An infeasible trial point: push the optimiser away rather than
            # letting the whole solve die on one bad step.
            return np.full(targets.shape, 1.0e3)
        return (modelled - targets) / sigmas

    z0 = (start - lower) / span
    solution = least_squares(
        residual, z0, bounds=(np.zeros_like(z0), np.ones_like(z0)),
        max_nfev=max_evaluations, xtol=1e-12, ftol=1e-12,
    )

    fitted = denormalise(solution.x)
    modelled = forward(fitted)

    residual_reports = [
        ResidualReport(
            key=m.key, measured=m.value, modelled=float(mod), sigma=float(sig),
            normalised_residual=float((mod - m.value) / sig),
        )
        for m, mod, sig in zip(measurements, modelled, sigmas)
    ]
    rms = float(np.sqrt(np.mean(np.square(solution.fun)))) if solution.fun.size else 0.0
    max_rel = max(
        (abs(r.modelled - r.measured) / abs(r.measured) if r.measured else 0.0)
        for r in residual_reports
    )

    determined = len(measurements) >= len(unknowns)
    errors, condition = _parameter_uncertainty(solution, span, len(measurements), len(unknowns))
    well_conditioned = condition is not None and condition < _ILL_CONDITIONED

    parameters: list[RecoveredParameter] = []
    for i, u in enumerate(unknowns):
        value = float(fitted[i])
        lo, hi = u.bounds
        err = float(errors[i]) if errors is not None else None
        # An error bar wider than the parameter's own allowed range means the
        # measurements constrain it no better than the bounds already did.
        # Reporting "+/- 243754" on an efficiency is arithmetic, not information,
        # so it is capped at the span and the parameter is called undetermined.
        if err is not None and err >= (hi - lo):
            err = hi - lo
        rel = (err / abs(value)) if (err is not None and value) else None
        at_bound = math.isclose(value, lo, rel_tol=1e-6) or math.isclose(value, hi, rel_tol=1e-6)
        parameters.append(RecoveredParameter(
            key=u.key, value=value, standard_error=err, relative_error=rel,
            identifiable=bool(determined and rel is not None
                              and rel < _IDENTIFIABLE_RELATIVE_SIGMA and not at_bound),
            at_bound=at_bound, bounds=(lo, hi),
        ))

    warnings = _collect_warnings(parameters, determined, well_conditioned, rms,
                                 len(measurements), len(unknowns))
    return InverseResult(
        converged=bool(solution.success),
        determined=determined,
        well_conditioned=well_conditioned,
        parameters=parameters,
        residuals=residual_reports,
        rms_normalised_residual=rms,
        max_absolute_relative_error=float(max_rel),
        jacobian_condition_number=condition,
        function_evaluations=int(solution.nfev),
        message=str(solution.message),
        verdict=_verdict(parameters, determined, well_conditioned, rms),
        warnings=warnings,
    )


def replace_inputs(base: TurbojetCycleInputs,
                   overrides: dict[str, float]) -> TurbojetCycleInputs:
    """Copy ``base`` with the named fields replaced."""

    data = {f: getattr(base, f) for f in base.__dataclass_fields__}
    data.update(overrides)
    return TurbojetCycleInputs(**data)


def _parameter_uncertainty(solution, span: np.ndarray, n_obs: int,
                           n_par: int) -> tuple[np.ndarray | None, float | None]:
    """Standard errors and conditioning from the Jacobian at the solution.

    The covariance is ``(J^T J)^-1``, which — because residuals are already
    divided by sigma — is the uncertainty implied by the *measurement*
    uncertainties propagated through the model's sensitivity.

    It is deliberately **not** rescaled by the residual variance in the usual
    way. Doing that collapses the error bars to zero whenever the data happens
    to be reproduced exactly, which is precisely the case where an
    ill-conditioned problem is most dangerous: a twin experiment with no noise
    fits perfectly while the recovered parameters are still wrong, and scaling
    by the residual would report near-infinite confidence in them.

    The one adjustment kept is inflation when the fit is *worse* than the stated
    uncertainties allow (chi-squared per degree of freedom above 1), because
    then the quoted sigmas are demonstrably too optimistic.
    """

    jac = getattr(solution, "jac", None)
    if jac is None or jac.size == 0:
        return None, None
    try:
        singular = np.linalg.svd(jac, compute_uv=False)
    except np.linalg.LinAlgError:       # pragma: no cover - numerically pathological
        return None, None
    if singular.size == 0 or singular[0] <= 0.0:
        return None, None
    smallest = singular[-1]
    condition = float(singular[0] / smallest) if smallest > 0 else float("inf")

    dof = max(1, n_obs - n_par)
    chi2_per_dof = float(np.sum(np.square(solution.fun))) / dof
    scale = max(1.0, chi2_per_dof)
    try:
        covariance = np.linalg.inv(jac.T @ jac) * scale
    except np.linalg.LinAlgError:
        return None, condition
    variances = np.diag(covariance)
    if np.any(variances < 0):
        return None, condition
    # Errors come back in the normalised space; rescale to physical units.
    return np.sqrt(variances) * span, condition


def _collect_warnings(parameters: list[RecoveredParameter], determined: bool,
                      well_conditioned: bool, rms: float,
                      n_obs: int, n_par: int) -> list[str]:
    out: list[str] = []
    if not determined:
        out.append(
            f"Underdetermined: {n_par} unknowns against {n_obs} measurements. "
            f"Infinitely many parameter sets reproduce this data exactly, so the "
            f"values below are one arbitrary member of that family, not the answer. "
            f"Measure at least {n_par - n_obs} more quantity(s) or solve for fewer."
        )
    if not well_conditioned:
        out.append(
            "Ill-conditioned: the chosen parameters have nearly the same effect on "
            "everything measured, so the fit can trade one against another almost "
            "freely. A low residual here does not mean the split between them is real."
        )
    for p in parameters:
        if p.at_bound:
            out.append(
                f"{p.key} converged onto its bound ({p.value:.4g}); the true value may "
                f"lie outside the range allowed, or the measurements may be inconsistent."
            )
    if rms > 3.0:
        out.append(
            f"Residuals are large (RMS {rms:.1f} sigma): no parameter set in range "
            f"reproduces these measurements. Check the flight condition and the fixed "
            f"inputs before trusting the fit."
        )
    return out


def _verdict(parameters: list[RecoveredParameter], determined: bool,
             well_conditioned: bool, rms: float) -> str:
    if not determined:
        return "Underdetermined — more measurements than unknowns are needed for this to mean anything."
    if rms > 3.0:
        return "No good fit — the model cannot reproduce these measurements within their stated uncertainty."
    if not well_conditioned:
        return "Fits the data, but the parameters are not separable from these measurements alone."
    named = [p.key for p in parameters if p.identifiable]
    if len(named) == len(parameters):
        return "Well posed — every parameter is pinned down by the measurements."
    if named:
        return (f"Partly determined — {', '.join(named)} recovered confidently; "
                f"the rest are not separable from this data.")
    return "Fits the data, but no individual parameter is pinned down by it."
