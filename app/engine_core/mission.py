"""Mission integrator (Day 16).

Flies a mission profile — an ordered list of legs, each held at a fixed
off-design operating point (altitude, Mach, throttle Tt4, duration) — and
accumulates fuel burned and elapsed time.

The engine is calibrated *once* (the choked-turbine matching constants do not
change with operating point); each leg is then a cheap matched-point solve via
the Day 8/11 off-design solvers. Fuel for a leg is ``fuel_flow * duration`` at
the matched point. A leg that cannot be matched (e.g. a nozzle unchokes at a
very low throttle) is recorded as a failure with its error, time still advances,
and the integration continues.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.engine_core.off_design import (
    calibrate_turbofan_reference,
    calibrate_turbojet_reference,
    solve_turbofan_off_design,
    solve_turbojet_off_design,
)
from app.engine_core.turbofan import TurbofanCycleInputs
from app.engine_core.types import CycleCalculationError, TurbojetCycleInputs


@dataclass(slots=True, frozen=True)
class MissionLeg:
    """One leg of a mission held at a fixed off-design operating point."""

    altitude_m: float
    mach: float
    throttle_K: float        # turbine inlet temperature Tt4 (throttle)
    duration_s: float
    name: str | None = None


SolvePoint = Callable[[float, float, float], dict[str, Any]]


def _integrate(
    engine_type: str,
    name: str,
    solve_point: SolvePoint,
    legs: list[MissionLeg],
) -> dict[str, Any]:
    """Walk the legs, matching each point and accumulating fuel + time."""

    rows: list[dict[str, Any]] = []
    cumulative_fuel_kg = 0.0
    cumulative_time_s = 0.0
    successful = 0

    for leg in legs:
        cumulative_time_s += leg.duration_s
        base = {
            "name": leg.name,
            "altitude_m": leg.altitude_m,
            "mach": leg.mach,
            "throttle_K": leg.throttle_K,
            "duration_s": leg.duration_s,
            "cumulative_time_s": cumulative_time_s,
        }
        try:
            result = solve_point(leg.altitude_m, leg.mach, leg.throttle_K)
        except CycleCalculationError as exc:
            rows.append(
                {
                    **base,
                    "success": False,
                    "error": str(exc),
                    "thrust_kN": None,
                    "TSFC_kg_per_kN_hr": None,
                    "fuel_burned_kg": None,
                    "cumulative_fuel_kg": cumulative_fuel_kg,
                }
            )
            continue

        fuel_flow_kg_s = float(result["fuel_flow_kg_s"])
        fuel_burned_kg = fuel_flow_kg_s * leg.duration_s
        cumulative_fuel_kg += fuel_burned_kg
        successful += 1
        rows.append(
            {
                **base,
                "success": True,
                "thrust_kN": result.get("thrust_kN"),
                "TSFC_kg_per_kN_hr": result.get("TSFC_kg_per_kN_hr"),
                "fuel_burned_kg": fuel_burned_kg,
                "cumulative_fuel_kg": cumulative_fuel_kg,
            }
        )

    return {
        "engine_type": engine_type,
        "name": name,
        "segments": rows,
        "total_fuel_kg": cumulative_fuel_kg,
        "total_time_s": cumulative_time_s,
        "successful_segments": successful,
        "failed_segments": len(rows) - successful,
    }


def fly_turbojet_mission(
    design_inputs: TurbojetCycleInputs,
    legs: list[MissionLeg],
    name: str = "Mission",
) -> dict[str, Any]:
    """Calibrate the turbojet once, then fly every leg off-design."""

    reference = calibrate_turbojet_reference(design_inputs)

    def solve_point(altitude_m: float, mach: float, throttle_K: float) -> dict[str, Any]:
        return solve_turbojet_off_design(
            reference,
            altitude_m=altitude_m,
            mach=mach,
            turbine_inlet_temperature_K=throttle_K,
        )

    return _integrate("turbojet", name, solve_point, legs)


def fly_turbofan_mission(
    design_inputs: TurbofanCycleInputs,
    legs: list[MissionLeg],
    name: str = "Mission",
) -> dict[str, Any]:
    """Calibrate the turbofan once, then fly every leg off-design."""

    reference = calibrate_turbofan_reference(design_inputs)

    def solve_point(altitude_m: float, mach: float, throttle_K: float) -> dict[str, Any]:
        return solve_turbofan_off_design(
            reference,
            altitude_m=altitude_m,
            mach=mach,
            turbine_inlet_temperature_K=throttle_K,
        )

    return _integrate("turbofan", name, solve_point, legs)
