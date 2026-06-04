"""Variable geometry for the afterburning turbojet.

Two effects a fixed-geometry model misses, both tied to lighting the afterburner:

1. **Variable-area nozzle (VAN) scheduling.** When the afterburner lights, the
   exhaust gets much hotter, so the same mass flow needs a *larger* sonic throat
   to pass without backing pressure up onto the turbine. A real engine opens the
   nozzle as you select reheat; the ratio of the reheat throat area to the dry
   throat area is the schedule. We compute both choked throat areas from the
   one-dimensional choked-flow relation and report how far the nozzle must open.

2. **Afterburner flame stability.** The reheat flame only stays anchored inside a
   loop in (equivalence ratio, pressure, velocity) space. Too lean and it blows
   out; too rich and it blows out; too fast or too low-pressure (high altitude)
   and the flameholder cannot hold it. We assess the operating point against a
   reduced-order stability loop and report the margins, plus how the lean limit
   climbs with altitude until the burner can no longer relight.

Both are reduced-order, clearly-labelled educational models, not combustor CFD.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from app.engine_core.atmosphere import isa_atmosphere
from app.engine_core.constants import cp_gas, gamma_gas
from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import CycleCalculationError, TurbojetCycleInputs

_R_GAS = cp_gas * (gamma_gas - 1.0) / gamma_gas
_FAR_STOICH_JET = 0.068          # kerosene/Jet-A stoichiometric fuel-air ratio
_AB_INLET_MACH = 0.25            # representative diffused afterburner-inlet Mach
_P_REF = 101325.0

# Reduced-order afterburner stability-loop constants.
_PHI_LBO_REF = 0.40              # lean-blowout equivalence ratio at sea level
_PHI_RICH_LIMIT = 1.60           # rich-blowout equivalence ratio
_AB_MACH_MAX = 0.50              # flameholder velocity limit
_AB_PRESSURE_FLOOR_PA = 15000.0  # below this the burner cannot relight


def choked_throat_area(mdot_kg_s: float, Tt_K: float, Pt_Pa: float,
                       gamma: float = gamma_gas, R: float = _R_GAS) -> float:
    """Sonic (choked) throat area from 1-D compressible flow.

    A* = m_dot * sqrt(Tt) / (Pt * Gamma),  with the choked-flow parameter
    Gamma = sqrt(gamma/R) * (2/(gamma+1))**((gamma+1)/(2(gamma-1))).
    """

    if Pt_Pa <= 0.0 or Tt_K <= 0.0 or mdot_kg_s <= 0.0:
        raise CycleCalculationError("Non-physical state for throat-area calculation.")
    flow_param = math.sqrt(gamma / R) * (2.0 / (gamma + 1.0)) ** (
        (gamma + 1.0) / (2.0 * (gamma - 1.0))
    )
    return mdot_kg_s * math.sqrt(Tt_K) / (Pt_Pa * flow_param)


def _static_pressure(Pt_Pa: float, mach: float, gamma: float = gamma_gas) -> float:
    return Pt_Pa / (1.0 + 0.5 * (gamma - 1.0) * mach * mach) ** (gamma / (gamma - 1.0))


def afterburner_stability(
    phi: float,
    inlet_static_pressure_Pa: float,
    inlet_mach: float = _AB_INLET_MACH,
) -> dict[str, Any]:
    """Assess a reheat operating point against a reduced-order stability loop."""

    # Lean blowout needs a richer mixture as pressure falls (harder to hold).
    phi_lean = min(_PHI_LBO_REF * math.sqrt(_P_REF / max(inlet_static_pressure_Pa, 1.0)), 1.3)
    phi_rich = _PHI_RICH_LIMIT

    status = "stable"
    if inlet_static_pressure_Pa < _AB_PRESSURE_FLOOR_PA:
        status = "pressure_blowout"
    elif inlet_mach > _AB_MACH_MAX:
        status = "velocity_blowout"
    elif phi < phi_lean:
        status = "lean_blowout"
    elif phi > phi_rich:
        status = "rich_blowout"
    stable = status == "stable"

    return {
        "phi": phi,
        "phi_lean_limit": phi_lean,
        "phi_rich_limit": phi_rich,
        "inlet_static_pressure_Pa": inlet_static_pressure_Pa,
        "inlet_mach": inlet_mach,
        "lean_margin": phi - phi_lean,
        "rich_margin": phi_rich - phi,
        "stable": stable,
        "status": status,
    }


def _run(inputs: TurbojetCycleInputs) -> dict[str, Any]:
    try:
        return simulate_turbojet_cycle(inputs)
    except CycleCalculationError:
        raise


def variable_geometry_analysis(
    design_inputs: TurbojetCycleInputs,
    afterburner_exit_temperature_K: float,
    *,
    afterburner_efficiency: float | None = None,
) -> dict[str, Any]:
    """VAN schedule + afterburner stability for a turbojet deck with reheat."""

    dry_inputs = replace(design_inputs, engine_variant="turbojet")
    reheat_kwargs: dict[str, Any] = {
        "engine_variant": "afterburning_turbojet",
        "afterburner_exit_temperature_K": afterburner_exit_temperature_K,
    }
    if afterburner_efficiency is not None:
        reheat_kwargs["afterburner_efficiency"] = afterburner_efficiency
    reheat_inputs = replace(design_inputs, **reheat_kwargs)

    dry = _run(dry_inputs)
    reheat = _run(reheat_inputs)

    mass_air = float(dry["effective_mass_flow_air_kg_s"])
    far_core = float(dry.get("core_fuel_air_ratio") or dry["fuel_air_ratio"])

    # Dry: choked throat at the turbine-exit state (station 5).
    s5 = dry["station_table"][5]
    Tt5 = float(s5["stagnation_temperature_K"])
    Pt5 = float(s5["stagnation_pressure_Pa"])
    mdot_dry = mass_air * (1.0 + far_core)
    a_dry = choked_throat_area(mdot_dry, Tt5, Pt5)

    # Reheat: choked throat at the afterburner-exit state (station 7).
    s7 = reheat["station_table"][7]
    Tt7 = float(s7["stagnation_temperature_K"])
    Pt7 = float(s7["stagnation_pressure_Pa"])
    total_far = float(reheat.get("total_fuel_air_ratio") or reheat["fuel_air_ratio"])
    mdot_reheat = mass_air * (1.0 + total_far)
    a_reheat = choked_throat_area(mdot_reheat, Tt7, Pt7)

    area_ratio = a_reheat / a_dry

    # Afterburner stability at the design flight condition.
    phi = total_far / _FAR_STOICH_JET
    p_static_ab = _static_pressure(Pt5, _AB_INLET_MACH)
    stability = afterburner_stability(phi, p_static_ab)

    # How the lean-blowout limit climbs with altitude (AB-inlet static pressure
    # taken to scale with ambient at fixed Mach/throttle).
    p_ambient_design = float(dry["ambient_pressure_Pa"])
    envelope: list[dict[str, Any]] = []
    for k in range(0, 13):
        alt = 1500.0 * k
        p_amb = isa_atmosphere(alt).pressure_Pa
        p_inlet = p_static_ab * (p_amb / p_ambient_design)
        leg = afterburner_stability(phi, p_inlet)
        envelope.append({
            "altitude_m": alt,
            "inlet_static_pressure_Pa": p_inlet,
            "phi_lean_limit": leg["phi_lean_limit"],
            "stable": leg["stable"],
            "can_relight": p_inlet >= _AB_PRESSURE_FLOOR_PA,
        })

    notes = [
        "Variable-area nozzle: the choked throat must open by the area ratio shown "
        "when reheat is selected, so the hotter, faster exhaust passes without "
        "raising back-pressure on the turbine.",
        "Afterburner stability uses a reduced-order loop (lean/rich blowout, a "
        "flameholder velocity limit, and a relight pressure floor), not combustor "
        "chemistry; treat the limits as trend-correct, not certified.",
    ]

    return {
        "dry_thrust_kN": float(dry["thrust_kN"]),
        "reheat_thrust_kN": float(reheat["thrust_kN"]),
        "thrust_augmentation": float(reheat["thrust_kN"]) / float(dry["thrust_kN"]),
        "van": {
            "dry_throat_area_m2": a_dry,
            "reheat_throat_area_m2": a_reheat,
            "area_ratio": area_ratio,
            "percent_open": (area_ratio - 1.0) * 100.0,
            "dry_nozzle_inlet_temperature_K": Tt5,
            "reheat_nozzle_inlet_temperature_K": Tt7,
        },
        "stability": stability,
        "envelope": envelope,
        "notes": notes,
    }
