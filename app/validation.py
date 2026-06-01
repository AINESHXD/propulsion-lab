"""Validation harness (Day 22+).

A validation case pins a model output against a *verifiable* reference: either a
published external figure (with a real, citable source) or a closed-form
analytical result. The runner reports the actual deviation and a pass/fail
against a per-metric tolerance — it never massages a result to pass.

Integrity rules for this module:

* Every external case MUST carry a real, checkable ``source`` and ``citation``.
  Reference values are transcribed from that source, never invented.
* Analytical cases derive their reference from stated equations (public
  textbook cycle relations), so anyone can reproduce them.
* The harness reports what it measures. A failing case stays failing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.engine_core.constants import cp_air, cp_gas
from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import TurbojetCycleInputs


@dataclass(slots=True, frozen=True)
class ReferenceMetric:
    """One reference quantity to check, with its tolerance."""

    key: str                      # key into the solver result dict
    label: str
    reference_value: float
    unit: str
    tolerance_pct: float


@dataclass(slots=True, frozen=True)
class ValidationCase:
    """A single validation case: inputs + reference metrics + provenance."""

    name: str
    kind: str                     # "analytical" or "published"
    source: str                   # human-readable source / citation
    citation: str                 # URL or document id (verifiable)
    description: str
    engine: str                   # "turbojet" (others added later)
    inputs: dict[str, Any]
    metrics: list[ReferenceMetric]


@dataclass(slots=True)
class MetricResult:
    label: str
    reference_value: float
    model_value: float
    unit: str
    tolerance_pct: float
    deviation_pct: float
    passed: bool


@dataclass(slots=True)
class CaseResult:
    name: str
    kind: str
    source: str
    citation: str
    passed: bool
    metrics: list[MetricResult] = field(default_factory=list)
    error: str | None = None


_SOLVERS: dict[str, Callable[[Any], dict[str, Any]]] = {
    "turbojet": lambda inp: simulate_turbojet_cycle(TurbojetCycleInputs(**inp)),
}


def run_validation_case(case: ValidationCase) -> CaseResult:
    """Run one validation case and compare every reference metric."""

    solver = _SOLVERS.get(case.engine)
    if solver is None:
        return CaseResult(case.name, case.kind, case.source, case.citation,
                          passed=False, error=f"No solver for engine '{case.engine}'.")
    try:
        result = solver(case.inputs)
    except Exception as exc:  # noqa: BLE001 - report any solver failure as a fail
        return CaseResult(case.name, case.kind, case.source, case.citation,
                          passed=False, error=str(exc))

    metric_results: list[MetricResult] = []
    all_passed = True
    for metric in case.metrics:
        model_value = float(result[metric.key])
        deviation = (
            abs(model_value - metric.reference_value)
            / abs(metric.reference_value)
            * 100.0
            if metric.reference_value
            else float("inf")
        )
        passed = deviation <= metric.tolerance_pct
        all_passed = all_passed and passed
        metric_results.append(
            MetricResult(
                label=metric.label,
                reference_value=metric.reference_value,
                model_value=model_value,
                unit=metric.unit,
                tolerance_pct=metric.tolerance_pct,
                deviation_pct=deviation,
                passed=passed,
            )
        )

    return CaseResult(
        name=case.name, kind=case.kind, source=case.source, citation=case.citation,
        passed=all_passed, metrics=metric_results,
    )


def run_all(cases: list[ValidationCase]) -> dict[str, Any]:
    """Run a list of validation cases and summarise pass/fail."""

    results = [run_validation_case(c) for c in cases]
    passed = sum(1 for r in results if r.passed)
    return {
        "cases": results,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
    }


# Registry — populated as VERIFIED references become available. Empty by design:
# a case is only added once its reference value is transcribed from a real,
# citable source (or derived from stated analytical equations).
VALIDATION_CASES: list[ValidationCase] = []


# ===========================================================================
# Conservation-law verification (Day 22)
# ===========================================================================
#
# Code-to-theory verification that does not depend on any external dataset: the
# turbojet solution must obey three conservation laws exactly (to numerical
# precision), independent of how the cycle is implemented:
#
#   1. Spool power balance — compressor power == turbine power x mechanical eff.
#   2. Combustor energy balance — fuel heat release == gas enthalpy rise.
#   3. Thrust reconstruction — reported thrust == momentum + pressure terms.
#
# A non-zero residual would expose a bookkeeping bug in the station march. This
# is a genuine verification methodology (checking conservation in the numerical
# solution), reproducible by anyone from the governing equations.


@dataclass(slots=True)
class ConservationResult:
    name: str
    spool_power_residual_pct: float
    combustor_energy_residual_pct: float
    thrust_reconstruction_residual_pct: float
    tolerance_pct: float
    passed: bool


def verify_turbojet_conservation(
    name: str,
    inputs: TurbojetCycleInputs,
    tolerance_pct: float = 1e-6,
) -> ConservationResult:
    """Check that a dry-turbojet solution conserves spool power, combustor
    energy, and momentum/thrust to within ``tolerance_pct`` (percent)."""

    if inputs.engine_variant != "turbojet":
        raise ValueError("Conservation verification supports the dry turbojet only.")

    result = simulate_turbojet_cycle(inputs)
    stations = result["station_table"]
    Tt2 = stations[2]["stagnation_temperature_K"]
    Tt3 = stations[3]["stagnation_temperature_K"]
    Tt4 = stations[4]["stagnation_temperature_K"]
    Tt5 = stations[5]["stagnation_temperature_K"]
    far = result["core_fuel_air_ratio"]
    mass_air = result["effective_mass_flow_air_kg_s"]
    mass_gas = mass_air * (1.0 + far)

    def rel(a: float, b: float) -> float:
        return abs(a - b) / abs(b) * 100.0 if b else float("inf")

    # 1. Spool power balance.
    compressor_power = cp_air * (Tt3 - Tt2)
    turbine_power = (1.0 + far) * cp_gas * (Tt4 - Tt5) * inputs.mechanical_efficiency
    spool_residual = rel(compressor_power, turbine_power)

    # 2. Combustor energy balance: f * eta_b * LHV == (1+f) cp_gas Tt4 - cp_air Tt3.
    heat_release = far * inputs.combustor_efficiency * inputs.fuel_heating_value_J_kg
    enthalpy_rise = (1.0 + far) * cp_gas * Tt4 - cp_air * Tt3
    combustor_residual = rel(heat_release, enthalpy_rise)

    # 3. Thrust reconstruction from reported exit state.
    V9 = result["exit_velocity_m_s"]
    V0 = result["freestream_velocity_m_s"]
    reconstructed = mass_gas * V9 - mass_air * V0
    if inputs.include_pressure_thrust:
        reconstructed += (
            result["nozzle_exit_pressure_Pa"] - result["ambient_pressure_Pa"]
        ) * result["nozzle_exit_area_m2"]
    thrust_residual = rel(reconstructed, result["thrust_N"])

    worst = max(spool_residual, combustor_residual, thrust_residual)
    return ConservationResult(
        name=name,
        spool_power_residual_pct=spool_residual,
        combustor_energy_residual_pct=combustor_residual,
        thrust_reconstruction_residual_pct=thrust_residual,
        tolerance_pct=tolerance_pct,
        passed=worst <= tolerance_pct,
    )


# Representative operating points spanning the turbojet envelope.
CONSERVATION_CASES: list[tuple[str, TurbojetCycleInputs]] = [
    ("Subsonic cruise", TurbojetCycleInputs(
        altitude_m=10000.0, mach=0.85, compressor_pressure_ratio=14.0,
        turbine_inlet_temperature_K=1500.0)),
    ("Supersonic", TurbojetCycleInputs(
        altitude_m=11000.0, mach=2.0, compressor_pressure_ratio=8.0,
        turbine_inlet_temperature_K=1600.0)),
    ("Low-speed sea level", TurbojetCycleInputs(
        altitude_m=0.0, mach=0.2, compressor_pressure_ratio=6.0,
        turbine_inlet_temperature_K=1300.0)),
    ("High pressure ratio", TurbojetCycleInputs(
        altitude_m=8000.0, mach=0.6, compressor_pressure_ratio=20.0,
        turbine_inlet_temperature_K=1550.0)),
]


def run_conservation_suite(
    tolerance_pct: float = 1e-6,
) -> list[ConservationResult]:
    """Run the conservation verification across all representative points."""

    return [
        verify_turbojet_conservation(name, inputs, tolerance_pct)
        for name, inputs in CONSERVATION_CASES
    ]
