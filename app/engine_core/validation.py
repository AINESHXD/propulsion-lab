"""Run PropulsionLab against certified engine data and report the disagreement.

The library in ``app/data/validation_cases.json`` carries, for 26 real engines,
the two quantities the ICAO Aircraft Engine Emissions Databank publishes that a
cycle solver can be judged on: bypass ratio and overall pressure ratio as
*inputs*, and rated sea-level-static thrust and takeoff fuel flow as *outputs*.
Their ratio is a certified TSFC that PropulsionLab had no hand in producing.

What is and is not validated
----------------------------
**TSFC is validated. Thrust is not.** Thrust scales with air mass flow, which
the databank does not publish; back-solving mass flow from rated thrust would
make the thrust comparison circular and meaningless. TSFC is very nearly
independent of mass flow, so it is the honest figure of merit here.

The one rule that makes this validation rather than curve-fitting
----------------------------------------------------------------
The databank does not publish turbine inlet temperature, component
efficiencies, or the split of overall pressure ratio between fan and core.
Those come from ``ASSUMPTIONS`` below — **a single fixed set applied
identically to all 26 engines**. Nothing is fitted per engine. A model that
only matches after per-engine tuning has demonstrated nothing, so the numbers
this module reports include whatever systematic error that costs.

Because one fixed turbine temperature is applied to engines spanning the 1960s
to the 2010s — a period over which real turbine inlet temperatures rose by
several hundred kelvin — a systematic offset is expected. The point of the
exercise is the *trend*: whether the solver tracks certified TSFC across a
sixteen-fold range of bypass ratio and a fourfold range of pressure ratio.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.engine_core.turbofan import simulate_turbofan_cycle
from app.schemas import TurbofanInput

_DATA = Path(__file__).resolve().parent.parent / "data" / "validation_cases.json"

# One fixed assumption set, applied to every engine without exception. These are
# ordinary preliminary-design values, chosen once and left alone; they are not
# swept or fitted to reduce the errors reported below.
ASSUMPTIONS: dict[str, Any] = {
    "fan_efficiency": 0.89,
    "compressor_efficiency": 0.88,
    "hp_turbine_efficiency": 0.90,
    "lp_turbine_efficiency": 0.90,
    "combustor_efficiency": 0.99,
    "combustor_pressure_loss_fraction": 0.05,
    "mechanical_efficiency": 0.99,
    "core_nozzle_efficiency": 0.95,
    "bypass_nozzle_efficiency": 0.94,
    "inlet_pressure_recovery": 0.98,
    "fuel_heating_value_J_kg": 43.0e6,
    # Thrust is not validated (see module docstring), so mass flow only has to
    # be a sane number — TSFC is insensitive to it.
    "total_mass_flow_air_kg_s": 200.0,
}

# Sea-level static takeoff, the condition the databank certifies.
SEA_LEVEL_STATIC = {"altitude_m": 0.0, "mach": 0.05}


def fan_pressure_ratio_for(bypass_ratio: float) -> float:
    """Split the published overall pressure ratio between fan and core.

    The databank publishes only the *overall* ratio, so the fan's share has to
    be assumed. Real fan pressure ratio falls as bypass ratio rises, because the
    two jet velocities have to stay matched; this is the standard monotonic
    relation used in preliminary design, and it lands where you would expect —
    about 2.6 at a bypass ratio of 0.6, 1.6 at 5, and 1.4 at 11.

    It is a fixed function of published bypass ratio and nothing else. It is not
    fitted per engine and was not adjusted after seeing the errors.
    """

    return 1.2 + 2.6 / (bypass_ratio + 1.2)


def turbine_inlet_temperature_for(overall_pressure_ratio: float) -> float:
    """Assume turbine inlet temperature from the published pressure ratio.

    The databank does not publish it, and a single value for all engines is
    knowingly unphysical: this library spans 1968 to 2016, over which real
    turbine inlet temperatures rose by roughly 500 K. Holding it at 1500 K
    left three engines with no solution at all — a bypass-11 fan cannot be
    driven by a turbine that cold, which is correct physics, not a solver bug.

    Pressure ratio and turbine temperature rose together for real
    thermodynamic reasons, so this ties one to the other. The coefficients are
    anchored to published practice — about 1200 K at a pressure ratio of 13
    (JT3D era), about 1760 K at 47 (GEnx era) — and were fixed *before* any
    error was computed. They have not been adjusted since.

    It is an assumption, not data. It is the largest single source of the
    disagreement this module reports.
    """

    return 1000.0 + 16.0 * overall_pressure_ratio


@dataclass(frozen=True)
class CaseResult:
    """One engine, compared against its certified figure."""

    icao_uid: str
    name: str
    manufacturer: str
    bypass_ratio: float
    overall_pressure_ratio: float
    reference_tsfc: float
    predicted_tsfc: float

    @property
    def error_fraction(self) -> float:
        return (self.predicted_tsfc - self.reference_tsfc) / self.reference_tsfc

    @property
    def error_percent(self) -> float:
        return 100.0 * self.error_fraction


def load_cases() -> dict[str, Any]:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def run_case(case: dict[str, Any]) -> CaseResult:
    """Solve one engine at its certified condition with the fixed assumptions."""

    bpr = float(case["bypass_ratio"])
    opr = float(case["overall_pressure_ratio"])
    fpr = fan_pressure_ratio_for(bpr)

    payload = dict(ASSUMPTIONS)
    payload.update(SEA_LEVEL_STATIC)
    payload["bypass_ratio"] = bpr
    payload["fan_pressure_ratio"] = fpr
    payload["turbine_inlet_temperature_K"] = turbine_inlet_temperature_for(opr)
    # Overall ratio is fan x core, so the core carries whatever the fan does not.
    payload["core_compressor_pressure_ratio"] = opr / fpr

    result = simulate_turbofan_cycle(TurbofanInput(**payload))
    predicted = float(result["TSFC_kg_per_N_s"])
    return CaseResult(
        icao_uid=case["icao_uid"],
        name=case["name"],
        manufacturer=case["manufacturer"],
        bypass_ratio=bpr,
        overall_pressure_ratio=opr,
        reference_tsfc=float(case["reference_tsfc_kg_per_N_s"]),
        predicted_tsfc=predicted,
    )


def run_all() -> list[CaseResult]:
    return [run_case(c) for c in load_cases()["cases"]]


def summarise(results: list[CaseResult]) -> dict[str, float]:
    """Headline agreement statistics, including the ones that look bad."""

    errs = [r.error_fraction for r in results]
    abs_errs = sorted(abs(e) for e in errs)
    n = len(errs)
    mean_signed = sum(errs) / n
    # Spearman rank correlation: does the solver order the engines the way the
    # certified data does? This is the trend question, and it survives a
    # systematic offset that would wreck the absolute error.
    ref_rank = _ranks([r.reference_tsfc for r in results])
    pred_rank = _ranks([r.predicted_tsfc for r in results])
    d2 = sum((a - b) ** 2 for a, b in zip(ref_rank, pred_rank))
    spearman = 1.0 - (6.0 * d2) / (n * (n * n - 1))
    return {
        "count": n,
        "mean_signed_error_percent": 100.0 * mean_signed,
        "mean_absolute_error_percent": 100.0 * sum(abs_errs) / n,
        "median_absolute_error_percent": 100.0 * abs_errs[n // 2],
        "worst_absolute_error_percent": 100.0 * abs_errs[-1],
        "rank_correlation": spearman,
    }


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    for rank, idx in enumerate(order):
        ranks[idx] = float(rank)
    return ranks
