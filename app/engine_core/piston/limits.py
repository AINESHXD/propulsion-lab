"""Operating limits for PistonLab (Day 8).

A cycle can solve cleanly and still describe an engine that would destroy itself.
This module flags the two limits that bound real engines, as *warnings*, never
hard failures, so the solver still returns a result you can learn from:

* **SI knock** (spark-ignition). The unburned end-gas ahead of the flame is
  compressed to the peak cylinder pressure; if it gets hot enough it
  autoignites and the engine knocks. Knock gets worse with compression ratio
  and boost (both raise the end-gas state) and with hotter intake air, and
  better with octane. We estimate the end-gas temperature and compare it to an
  octane- and pressure-dependent autoignition temperature.

* **CI smoke** (compression-ignition / diesel). A diesel cannot burn near
  stoichiometric because fuel and air never fully mix in the time available;
  pushing the fuelling past a smoke-limited equivalence ratio makes soot. We
  flag the over-fuelled region in phi.

These are reduced-order proxies, transparently calibrated, not chemical-kinetics
predictions: they tell the right *story* (which way each knob pushes the limit)
without pretending to a precision they do not have.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.engine_core.piston.fuel import get_fuel

# --- SI knock: end-gas autoignition proxy ---------------------------------
# Effective end-gas autoignition temperature for RON 95 at the reference peak
# pressure, then shifted by octane (higher RON resists knock) and by peak
# pressure (higher pressure shortens the ignition delay, easing autoignition).
_T_AUTOIGNITION_REF_K = 1050.0
_RON_REF = 95.0
_OCTANE_SENSITIVITY_K = 6.0          # K of autoignition headroom per RON point
_KNOCK_PRESSURE_COEFF_K = 35.0       # K lost per e-fold of peak pressure
_KNOCK_P_REF_PA = 75.0e5             # reference peak pressure (~NA, CR 10.5)
_KNOCK_CAUTION_BAND_K = 25.0         # within this margin -> caution, below 0 -> knock

# --- CI smoke and SI lean misfire (equivalence-ratio limits) --------------
_SMOKE_CAUTION_PHI = 0.70            # diesel approaches the smoke limit (lambda ~1.43)
_SMOKE_WARNING_PHI = 0.85            # heavy smoke / over-fuelled (lambda ~1.18)
_LEAN_CAUTION_PHI = 0.65            # SI mixture getting lean (lambda ~1.54)
_LEAN_WARNING_PHI = 0.50            # SI lean misfire likely (lambda ~2.0)


@dataclass(frozen=True, slots=True)
class OperatingWarning:
    """One flagged operating-limit condition."""

    kind: str            # "knock" | "smoke" | "lean_misfire"
    severity: str        # "caution" | "warning"
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "severity": self.severity, "message": self.message}


def end_gas_temperature_K(
    intake_temperature_K: float,
    peak_pressure_Pa: float,
    intake_pressure_Pa: float,
    gamma: float,
) -> float:
    """End-gas temperature from isentropic compression of the trapped charge to
    the peak cylinder pressure: ``T_eg = T_ivc * (p_peak / p_ivc) ** ((g-1)/g)``."""

    return intake_temperature_K * (peak_pressure_Pa / intake_pressure_Pa) ** ((gamma - 1.0) / gamma)


def autoignition_temperature_K(research_octane_number: float, peak_pressure_Pa: float) -> float:
    """Effective end-gas autoignition temperature for a given octane and peak
    pressure. Rises with octane, falls (knock easier) with peak pressure."""

    return (
        _T_AUTOIGNITION_REF_K
        + _OCTANE_SENSITIVITY_K * (research_octane_number - _RON_REF)
        - _KNOCK_PRESSURE_COEFF_K * math.log(peak_pressure_Pa / _KNOCK_P_REF_PA)
    )


def knock_margin_K(
    fuel_name: str,
    intake_temperature_K: float,
    peak_pressure_Pa: float,
    intake_pressure_Pa: float,
    gamma: float,
) -> float | None:
    """Autoignition margin (autoignition T minus end-gas T) in kelvin.

    Positive is safe, negative means knock. Returns ``None`` for a
    compression-ignition fuel, where spark knock does not apply.
    """

    fuel = get_fuel(fuel_name)
    if fuel.research_octane_number is None:
        return None
    t_eg = end_gas_temperature_K(intake_temperature_K, peak_pressure_Pa, intake_pressure_Pa, gamma)
    t_ai = autoignition_temperature_K(fuel.research_octane_number, peak_pressure_Pa)
    return t_ai - t_eg


def evaluate_operating_limits(
    fuel_name: str | None,
    equivalence_ratio: float,
    intake_temperature_K: float,
    peak_pressure_Pa: float,
    intake_pressure_Pa: float,
    gamma: float,
) -> list[OperatingWarning]:
    """Return any knock / smoke / lean-misfire warnings for an operating point.

    Limits are judged from the fuel's character: spark-ignition fuels are checked
    for knock and lean misfire, compression-ignition fuels for smoke. With no
    fuel selected (the raw-heat path) there is nothing to judge, so the list is
    empty.
    """

    if not fuel_name or fuel_name == "manual":
        return []
    fuel = get_fuel(fuel_name)
    warnings: list[OperatingWarning] = []
    lam = 1.0 / equivalence_ratio if equivalence_ratio > 0 else float("inf")

    if fuel.ignition == "spark":
        margin = knock_margin_K(fuel_name, intake_temperature_K, peak_pressure_Pa, intake_pressure_Pa, gamma)
        if margin is not None:
            if margin < 0.0:
                warnings.append(OperatingWarning(
                    "knock", "warning",
                    f"Knock likely: end-gas autoignites with {-margin:.0f} K to spare past the "
                    f"RON {fuel.research_octane_number:.0f} limit. Lower CR or boost, enrich, "
                    f"retard spark, or run higher octane.",
                ))
            elif margin < _KNOCK_CAUTION_BAND_K:
                warnings.append(OperatingWarning(
                    "knock", "caution",
                    f"Knock margin thin ({margin:.0f} K) for RON {fuel.research_octane_number:.0f}; "
                    f"close to the autoignition limit at this CR/boost.",
                ))
        if equivalence_ratio < _LEAN_WARNING_PHI:
            warnings.append(OperatingWarning(
                "lean_misfire", "warning",
                f"Lean misfire likely: phi={equivalence_ratio:.2f} (lambda={lam:.2f}) is past the "
                f"stable spark-ignition limit.",
            ))
        elif equivalence_ratio < _LEAN_CAUTION_PHI:
            warnings.append(OperatingWarning(
                "lean_misfire", "caution",
                f"Mixture lean: phi={equivalence_ratio:.2f} (lambda={lam:.2f}); combustion stability "
                f"degrades approaching the lean limit.",
            ))

    elif fuel.ignition == "compression":
        if equivalence_ratio > _SMOKE_WARNING_PHI:
            warnings.append(OperatingWarning(
                "smoke", "warning",
                f"Over-fuelled: phi={equivalence_ratio:.2f} (lambda={lam:.2f}) is past the diesel "
                f"smoke limit; heavy soot. Lean out the fuelling.",
            ))
        elif equivalence_ratio > _SMOKE_CAUTION_PHI:
            warnings.append(OperatingWarning(
                "smoke", "caution",
                f"Approaching the smoke limit: phi={equivalence_ratio:.2f} (lambda={lam:.2f}); "
                f"a diesel cannot mix enough air to burn this much fuel cleanly.",
            ))

    return warnings
