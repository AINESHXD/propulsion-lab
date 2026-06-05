"""One-at-a-time sensitivity (tornado) analysis for the turbojet cycle.

Perturbs each design input by +/- a fixed fraction around the baseline deck,
re-runs the cycle, and measures the change in a chosen output metric. The rows
are returned sorted by *swing* (largest mover first), which the frontend draws
as a tornado chart.

This is a *local* sensitivity: it varies one input at a time and reports the
finite-difference response, so it captures the slope and sign of each input near
the operating point, not interactions between inputs. That is exactly what a
tornado chart is meant to show, and we say so on the page.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.engine_core.advanced_cycles import simulate_turbofan_cycle
from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import CycleCalculationError, TurbojetCycleInputs

# (field, label, is_fraction). Fraction-type inputs (efficiencies, recoveries)
# are clamped to (0, 1] so a +perturbation can't push them past unity.
SENSITIVITY_PARAMS: list[tuple[str, str, bool]] = [
    ("compressor_pressure_ratio", "Compressor PR", False),
    ("turbine_inlet_temperature_K", "Turbine inlet T", False),
    ("mass_flow_air_kg_s", "Air mass flow", False),
    ("mach", "Flight Mach", False),
    ("altitude_m", "Altitude", False),
    ("compressor_efficiency", "Compressor η", True),
    ("turbine_efficiency", "Turbine η", True),
    ("combustor_efficiency", "Combustor η", True),
    ("nozzle_efficiency", "Nozzle η", True),
    ("inlet_pressure_recovery", "Inlet recovery", True),
]

# Two-spool separate-flow turbofan. Same idea, different design variables.
TURBOFAN_SENSITIVITY_PARAMS: list[tuple[str, str, bool]] = [
    ("turbine_inlet_temperature_K", "Turbine inlet T", False),
    ("bypass_ratio", "Bypass ratio", False),
    ("fan_pressure_ratio", "Fan PR", False),
    ("core_compressor_pressure_ratio", "Core PR", False),
    ("total_mass_flow_air_kg_s", "Air mass flow", False),
    ("mach", "Flight Mach", False),
    ("altitude_m", "Altitude", False),
    ("fan_efficiency", "Fan η", True),
    ("compressor_efficiency", "Compressor η", True),
    ("hp_turbine_efficiency", "HP turbine η", True),
    ("lp_turbine_efficiency", "LP turbine η", True),
    ("combustor_efficiency", "Combustor η", True),
]

METRIC_LABELS: dict[str, str] = {
    "thrust_kN": "Thrust",
    "TSFC_kg_per_kN_hr": "TSFC",
    "specific_thrust_N_per_kg_s": "Specific thrust",
    "overall_efficiency_estimate": "Overall efficiency",
}


def _sensitivity(
    base_inputs: Any,
    simulate_fn: Any,
    params: list[tuple[str, str, bool]],
    metric: str,
    delta_fraction: float,
) -> dict[str, Any]:
    """Engine-agnostic one-at-a-time sensitivity (tornado) over ``params``.

    Each row carries the input's low/high perturbed values and the resulting
    change in ``metric`` relative to the baseline run. A perturbation that drives
    the solver outside its valid envelope is reported as ``None`` rather than
    aborting the whole analysis.
    """

    if metric not in METRIC_LABELS:
        raise ValueError(f"Unknown metric '{metric}'.")
    if not 0.0 < delta_fraction < 0.9:
        raise ValueError("delta_fraction must be between 0 and 0.9.")

    base_metric = float(simulate_fn(base_inputs)[metric])

    def run(field: str, value: float) -> float | None:
        try:
            return float(simulate_fn(replace(base_inputs, **{field: value}))[metric])
        except CycleCalculationError:
            return None

    rows: list[dict[str, Any]] = []
    for field, label, is_fraction in params:
        base_val = getattr(base_inputs, field, None)
        if base_val is None or base_val == 0:
            continue  # nothing to scale (e.g. sea-level Mach 0); skip cleanly
        low_v = base_val * (1.0 - delta_fraction)
        high_v = base_val * (1.0 + delta_fraction)
        if is_fraction:
            low_v = min(max(low_v, 1e-3), 0.999)
            high_v = min(high_v, 0.999)

        lo, hi = run(field, low_v), run(field, high_v)
        d_lo = None if lo is None else lo - base_metric
        d_hi = None if hi is None else hi - base_metric
        swing = max((abs(d) for d in (d_lo, d_hi) if d is not None), default=0.0)
        rows.append({
            "parameter": field,
            "label": label,
            "base_value": float(base_val),
            "low_value": float(low_v),
            "high_value": float(high_v),
            "low_metric": lo,
            "high_metric": hi,
            "delta_low": d_lo,
            "delta_high": d_hi,
            "swing": swing,
        })

    rows.sort(key=lambda r: r["swing"], reverse=True)
    return {
        "metric": metric,
        "metric_label": METRIC_LABELS[metric],
        "base_metric": base_metric,
        "delta_fraction": delta_fraction,
        "rows": rows,
    }


def turbojet_sensitivity(
    base_inputs: TurbojetCycleInputs,
    metric: str = "thrust_kN",
    delta_fraction: float = 0.1,
    params: list[tuple[str, str, bool]] | None = None,
) -> dict[str, Any]:
    """Tornado-chart sensitivity payload for the turbojet cycle."""

    return _sensitivity(
        base_inputs, simulate_turbojet_cycle, params or SENSITIVITY_PARAMS, metric, delta_fraction
    )


def turbofan_sensitivity(
    base_inputs: Any,
    metric: str = "thrust_kN",
    delta_fraction: float = 0.1,
    params: list[tuple[str, str, bool]] | None = None,
) -> dict[str, Any]:
    """Tornado-chart sensitivity payload for the separate-flow turbofan cycle."""

    return _sensitivity(
        base_inputs, simulate_turbofan_cycle, params or TURBOFAN_SENSITIVITY_PARAMS, metric, delta_fraction
    )
