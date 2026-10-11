"""Feasibility analysis for a PistonLab engine.

The solver answers "what does this engine do". This module answers the next
question an engineer would ask: "could it be built, and if not, what is the
smallest change that makes it buildable?"

Three rules keep it honest:

1. **Every number comes from the solver.** Checks are evaluated on a real
   crank-angle solve. Recommendations are found by bisecting the solver on one
   design lever at a time, and the proof sweeps are further solves. Nothing is
   taken from a correlation when the solver can answer directly.
2. **Every recommendation is verified.** All recommended changes are applied
   together and the engine is solved again, because levers interact (lowering
   compression to cure knock also cuts peak pressure, efficiency and exhaust
   temperature). If the combined engine still fails a check, the search runs
   again from that engine, and anything still unresolved is reported as such.
3. **Every limit and every cost coefficient is stated.** The limits are typical
   production design envelopes, not certification figures, and the build-cost
   model is a relative index built from declared coefficients, not supplier
   prices. Both are returned in the report so a reader can disagree with them.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.engine_core.piston.fuel import get_fuel
from app.engine_core.piston.limits import autoignition_temperature_K, knock_margin_K
from app.schemas_piston import PistonSimulateInput, PistonSimulateOutput, run_piston_simulation

Status = Literal["pass", "caution", "fail", "n/a"]

HEYWOOD = "Heywood, Internal Combustion Engine Fundamentals, 2nd ed."

# --------------------------------------------------------------------------- #
# limits
# --------------------------------------------------------------------------- #
# (caution, fail). "max" checks fail above the limit, "min" checks below it.
PEAK_PRESSURE_BAR = {"spark": (110.0, 140.0), "compression": (180.0, 220.0)}
EXHAUST_T_C = {"spark": (950.0, 1050.0), "compression": (750.0, 850.0)}
BMEP_BAR = {
    ("spark", False): (14.0, 17.0), ("spark", True): (24.0, 30.0),
    ("compression", False): (10.0, 12.0), ("compression", True): (26.0, 32.0),
}
PISTON_SPEED = (20.0, 25.0)
PRESSURE_RISE = (6.0, 10.0)
INLET_MACH = (0.50, 0.60)
MECH_EFF = (0.75, 0.65)
KNOCK_MARGIN = (25.0, 0.0)
SMOKE_PHI = (0.70, 0.85)
LEAN_PHI = (0.65, 0.50)
CI_IGNITION_T = (850.0, 800.0)

BURNED_GAS_GAMMA = 1.30          # for the isentropic blowdown estimate

# --------------------------------------------------------------------------- #
# cost assumptions (all returned in the report)
# --------------------------------------------------------------------------- #
FUEL_PRICE_GBP_PER_L = {"gasoline": 1.40, "diesel": 1.48, "ethanol": 1.20}
COST_COEFFICIENTS = {
    "structure_fixed": 20.0, "structure_per_cylinder": 5.0, "structure_per_litre": 6.0,
    "diesel_structure_factor": 1.35,
    "layout_factor": {"inline": 1.00, "vee": 1.12, "flat": 1.18, "w": 1.30},
    "per_valve": 0.9,
    "fuel_system": {"spark": 10.0, "compression": 28.0},
    "turbocharger": 18.0, "intercooler": 5.0, "supercharger": 22.0,
    "aftertreatment": {"spark": 8.0, "compression": 22.0},
    "uprated_internals_fraction": 0.20,
    "high_speed_valvetrain": 6.0,
}
BASELINE = dict(fuel="gasoline", cylinders=4, displacement_L=2.0, bore_stroke_ratio=1.0,
                compression_ratio=10.5, rpm=3000.0)

# --------------------------------------------------------------------------- #
# output models
# --------------------------------------------------------------------------- #


class FeasibilityCheck(BaseModel):
    key: str
    label: str
    value: float | None
    unit: str
    kind: Literal["max", "min", "flag"]
    caution: float | None
    limit: float | None
    status: Status
    utilisation: float | None = Field(None, description="1.0 = at the fail limit; above 1 fails.")
    margin_percent: float | None
    basis: str


class ProofSweep(BaseModel):
    lever: str
    lever_label: str
    lever_unit: str
    metric_key: str
    metric_label: str
    metric_unit: str
    x: list[float]
    metric: list[float | None]
    brake_power_kW: list[float | None]
    current_x: float
    recommended_x: float
    caution: float | None
    limit: float | None


class Recommendation(BaseModel):
    step: int = 0
    check_key: str
    check_label: str = ""
    metric_before: float | None = None
    metric_after: float | None = None
    metric_unit: str = ""
    limit: float | None = None
    brake_power_change_percent: float | None = None
    also_cured: list[str] = Field(default_factory=list)
    lever: str
    lever_label: str
    unit: str
    from_value: float
    to_value: float
    resolved: bool
    rationale: str


class EngineSnapshot(BaseModel):
    brake_power_kW: float
    brake_torque_Nm: float
    bmep_bar: float
    brake_thermal_efficiency: float
    bsfc_g_per_kWh: float
    peak_pressure_bar: float


class CostLine(BaseModel):
    item: str
    points: float
    basis: str


class CostReport(BaseModel):
    build_cost_index: float = Field(..., description="Relative; a 2.0 L NA petrol inline-4 is 100.")
    cost_index_per_kW: float = Field(..., description="Relative to the same baseline, per brake kW.")
    breakdown: list[CostLine]
    fuel_price_gbp_per_L: float
    fuel_L_per_h: float
    fuel_cost_gbp_per_h: float
    fuel_cost_gbp_per_kWh: float
    fuel_cost_gbp_per_1000h: float


class FeasibilityReport(BaseModel):
    verdict: Literal["feasible", "marginal", "not_feasible"]
    headline: str
    summary: str
    checks: list[FeasibilityCheck]
    recommendations: list[Recommendation]
    verified_checks: list[FeasibilityCheck]
    verified_verdict: Literal["feasible", "marginal", "not_feasible"]
    recommended_inputs: dict[str, Any]
    before: EngineSnapshot
    after: EngineSnapshot
    proofs: list[ProofSweep]
    cost_before: CostReport
    cost_after: CostReport
    assumptions: list[str]
    solves: int


# --------------------------------------------------------------------------- #
# solving and measuring
# --------------------------------------------------------------------------- #

class _Counter:
    n = 0


def _solve(spec: dict[str, Any], counter: _Counter) -> PistonSimulateOutput:
    counter.n += 1
    s = dict(spec)
    s["include_trace"] = True
    return run_piston_simulation(PistonSimulateInput(**s))


def _ignition(spec: dict[str, Any]) -> str:
    fuel = spec.get("fuel")
    if not fuel or fuel == "manual":
        return "spark"
    return get_fuel(fuel).ignition


def _boosted(spec: dict[str, Any]) -> bool:
    return (spec.get("aspiration") or "naturally_aspirated") != "naturally_aspirated"


def _metrics(spec: dict[str, Any], r: PistonSimulateOutput) -> dict[str, float | None]:
    """Every quantity a check needs, from one solve."""

    rpm = float(spec.get("rpm", 3000.0))
    trace = r.trace or []
    m: dict[str, float | None] = {}
    m["piston_speed"] = 2.0 * r.stroke_m * rpm / 60.0
    m["peak_pressure"] = r.peak_pressure_Pa / 1e5
    m["bmep"] = r.bmep_Pa / 1e5
    m["mech_eff"] = r.mechanical_efficiency
    m["inlet_mach"] = r.inlet_mach_index
    m["phi"] = r.equivalence_ratio
    m["boost_ok"] = 1.0 if r.boost_sustainable else 0.0

    # Knock margin, judged exactly as the solver judges it.
    m["knock_margin"] = None
    fuel = spec.get("fuel")
    if fuel and fuel != "manual" and get_fuel(fuel).ignition == "spark":
        ron = get_fuel(fuel).research_octane_number
        if r.two_zone_combustion and r.peak_unburned_temperature_K:
            m["knock_margin"] = autoignition_temperature_K(ron, r.peak_pressure_Pa) - r.peak_unburned_temperature_K
        else:
            m["knock_margin"] = knock_margin_K(
                fuel, float(spec.get("intake_temperature_K", 330.0)), r.peak_pressure_Pa,
                float(spec.get("intake_pressure_Pa", 1e5)), r.mean_gamma or 1.3)

    # Exhaust-manifold temperature. The solver's exhaust temperature is the gas
    # in the cylinder at exhaust-valve opening, which is the last trace point;
    # what reaches a turbine or catalyst has blown down to back-pressure. The
    # isentropic blowdown estimate is the textbook correction.
    m["exhaust_T"] = None
    if trace and r.exhaust_temperature_K:
        p_evo = trace[-1].pressure_Pa
        p_back = r.exhaust_pressure_Pa or 1e5
        ratio = min(1.0, p_back / p_evo) if p_evo > 0 else 1.0
        t_man = r.exhaust_temperature_K * ratio ** ((BURNED_GAS_GAMMA - 1.0) / BURNED_GAS_GAMMA)
        m["exhaust_T"] = t_man - 273.15

    # Peak rate of pressure rise, from the trace.
    m["pressure_rise"] = None
    if len(trace) > 2:
        rates = [
            (b.pressure_Pa - a.pressure_Pa) / 1e5 / max(1e-9, b.theta_deg - a.theta_deg)
            for a, b in zip(trace, trace[1:])
        ]
        m["pressure_rise"] = max(rates)

    # Compression ignition needs hot enough air at start of injection.
    m["ci_T"] = None
    if _ignition(spec) == "compression" and trace:
        soc = float(spec.get("combustion_start_deg", -8.0))
        pt = min(trace, key=lambda p: abs(p.theta_deg - soc))
        m["ci_T"] = pt.temperature_K
    return m


def _status(kind: str, value: float | None, caution: float | None, limit: float | None) -> Status:
    if value is None or limit is None:
        return "n/a"
    if kind == "max":
        return "fail" if value > limit else "caution" if value > caution else "pass"
    return "fail" if value < limit else "caution" if value < caution else "pass"


def _check(key, label, value, unit, kind, caution, limit, basis) -> FeasibilityCheck:
    st = _status(kind, value, caution, limit)
    util = margin = None
    if value is not None and limit not in (None, 0):
        if kind == "max":
            util = value / limit
            margin = (limit - value) / limit * 100.0
        else:
            util = limit / value if value else None
            margin = (value - limit) / abs(limit) * 100.0
    elif value is not None and limit == 0:            # knock margin: a K margin
        util = None
        margin = None
    return FeasibilityCheck(key=key, label=label, value=value, unit=unit, kind=kind, caution=caution,
                            limit=limit, status=st, utilisation=util, margin_percent=margin, basis=basis)


def _checks(spec: dict[str, Any], m: dict[str, float | None]) -> list[FeasibilityCheck]:
    ign = _ignition(spec)
    boosted = _boosted(spec)
    c: list[FeasibilityCheck] = []
    c.append(_check("piston_speed", "Mean piston speed", m["piston_speed"], "m/s", "max", *PISTON_SPEED,
             f"Inertia loads scale with speed squared and ring, skirt and bearing life fall with it. "
             f"Production engines rarely exceed about 20 m/s at rated speed; about 25 m/s is racing practice ({HEYWOOD}, ch. 2)."))
    pc, pf = PEAK_PRESSURE_BAR[ign]
    c.append(_check("peak_pressure", "Peak cylinder pressure", m["peak_pressure"], "bar", "max", pc, pf,
             "Sizes the head gasket, head bolts, piston pin and bearings. Typical design envelopes: production "
             "spark-ignition engines about 100 to 140 bar, light-duty diesels about 180 to 220 bar."))
    bc, bf = BMEP_BAR[(ign, boosted)]
    c.append(_check("bmep", "Brake mean effective pressure", m["bmep"], "bar", "max", bc, bf,
             "Specific load on the engine structure, independent of size. Limits are typical of current production "
             f"{'boosted' if boosted else 'naturally aspirated'} {'diesel' if ign == 'compression' else 'petrol'} engines."))
    c.append(_check("mech_eff", "Mechanical efficiency", m["mech_eff"], "", "min", *MECH_EFF,
             "Brake over net indicated work. Below about 0.7 friction is consuming a large share of the cycle "
             "work, usually from speed."))
    c.append(_check("pressure_rise", "Peak rate of pressure rise", m["pressure_rise"], "bar/°", "max", *PRESSURE_RISE,
             "Drives combustion noise and shock loading of the piston and bearings. Above about 10 bar per crank "
             "degree combustion is harsh and structurally damaging; production calibrations aim well below."))
    c.append(_check("exhaust_T", "Exhaust-manifold temperature (est.)", m["exhaust_T"], "°C", "max", *EXHAUST_T_C[ign],
             "Isentropic blowdown of the gas at exhaust-valve opening to back-pressure. Typical material limits for "
             "the manifold, turbine and catalyst: about 950 to 1050 °C petrol, 750 to 850 °C diesel."))
    c.append(_check("inlet_mach", "Inlet Mach index", m["inlet_mach"], "", "max", *INLET_MACH,
             f"Taylor's inlet Mach index. Volumetric efficiency falls away sharply above about 0.6 because the inlet "
             f"valves choke ({HEYWOOD}, ch. 6). Not assessed without valve geometry."))
    if ign == "spark":
        c.append(_check("knock_margin", "Knock margin", m["knock_margin"], "K", "min", *KNOCK_MARGIN,
                 "Autoignition temperature minus end-gas temperature, the solver's own knock model. Below zero the "
                 "end gas autoignites before the flame arrives."))
        c.append(_check("lean_phi", "Equivalence ratio (lean limit)", m["phi"], "", "min", *LEAN_PHI,
                 "Spark-ignition combustion becomes unstable and misfires as the mixture leans out."))
    else:
        c.append(_check("smoke_phi", "Equivalence ratio (smoke limit)", m["phi"], "", "max", *SMOKE_PHI,
                 "A diesel cannot mix enough air to burn rich of about φ 0.7 cleanly; past 0.85 it smokes heavily."))
        c.append(_check("ci_ignition", "Compression temperature at injection", m["ci_T"], "K", "min", *CI_IGNITION_T,
                 "Diesel fuel needs the compressed air above roughly 800 K at injection to self-ignite reliably, "
                 "with margin for cold starts."))
    if boosted:
        ok = m["boost_ok"]
        c.append(FeasibilityCheck(key="boost", label="Boost sustainable", value=ok, unit="", kind="flag",
                 caution=None, limit=1.0, status="pass" if ok else "fail", utilisation=None, margin_percent=None,
                 basis="Whether the exhaust energy can drive the compressor to the requested boost."))
    return c


def _verdict(checks: list[FeasibilityCheck]) -> str:
    st = {c.status for c in checks}
    return "not_feasible" if "fail" in st else "marginal" if "caution" in st else "feasible"


def _snapshot(r: PistonSimulateOutput) -> EngineSnapshot:
    return EngineSnapshot(brake_power_kW=r.brake_power_W / 1e3, brake_torque_Nm=r.brake_torque_Nm,
                          bmep_bar=r.bmep_Pa / 1e5, brake_thermal_efficiency=r.brake_thermal_efficiency,
                          bsfc_g_per_kWh=r.bsfc_g_per_kWh, peak_pressure_bar=r.peak_pressure_Pa / 1e5)


# --------------------------------------------------------------------------- #
# levers
# --------------------------------------------------------------------------- #
LEVER_INFO = {
    "rpm": ("Engine speed", "rpm", 50.0),
    "compression_ratio": ("Compression ratio", ":1", 0.1),
    "intake_pressure_Pa": ("Manifold pressure", "bar", 0.01e5),
    "equivalence_ratio": ("Equivalence ratio φ", "", 0.01),
    "burn_duration_deg": ("Burn duration", "°", 1.0),
}


def _lever_for(key: str, spec: dict[str, Any]) -> tuple[str, float] | None:
    """(lever, bound) that cures the check, moving from the current value toward the bound."""

    ign, boosted = _ignition(spec), _boosted(spec)
    amb = float(spec.get("ambient_pressure_Pa", 1e5))
    if key in ("piston_speed", "inlet_mach", "mech_eff"):
        return "rpm", 1000.0
    if key == "bmep":
        if boosted:
            return "intake_pressure_Pa", amb
        return ("equivalence_ratio", 0.30) if ign == "compression" else ("compression_ratio", 7.0)
    if key == "peak_pressure":
        return ("intake_pressure_Pa", amb) if boosted else ("compression_ratio", 7.0)
    if key == "knock_margin":
        return "compression_ratio", 7.0
    if key == "boost":
        return "intake_pressure_Pa", amb
    if key == "smoke_phi":
        return "equivalence_ratio", 0.30
    if key == "lean_phi":
        return "equivalence_ratio", 1.0
    if key == "ci_ignition":
        return "compression_ratio", 24.0
    if key == "exhaust_T":
        return ("equivalence_ratio", 1.25) if ign == "spark" else ("equivalence_ratio", 0.30)
    if key == "pressure_rise":
        return "burn_duration_deg", 100.0
    return None


def _round_toward(value: float, step: float, toward: float) -> float:
    q = value / step
    q = math.ceil(q) if toward > value else math.floor(q)
    return round(q * step, 10)


def _passes(key: str, spec: dict[str, Any], counter: _Counter) -> tuple[bool, dict, PistonSimulateOutput]:
    r = _solve(spec, counter)
    m = _metrics(spec, r)
    chk = next((c for c in _checks(spec, m) if c.key == key), None)
    return (chk is not None and chk.status == "pass"), m, r


def _find_cure(key: str, spec: dict[str, Any], counter: _Counter) -> Recommendation | None:
    lev = _lever_for(key, spec)
    if lev is None:
        return None
    lever, bound = lev
    label, unit, step = LEVER_INFO[lever]
    current = float(spec.get(lever, PistonSimulateInput.model_fields[lever].default))
    if math.isclose(current, bound):
        return Recommendation(check_key=key, lever=lever, lever_label=label, unit=unit, from_value=current,
                              to_value=current, resolved=False,
                              rationale=f"{label} is already at the end of its practical range.")

    def trial(v: float) -> bool:
        s = dict(spec); s[lever] = v
        try:
            return _passes(key, s, counter)[0]
        except ValueError:
            return False

    if not trial(bound):
        return Recommendation(check_key=key, lever=lever, lever_label=label, unit=unit, from_value=current,
                              to_value=bound, resolved=False,
                              rationale=f"Even at {_fmt_lever(lever, bound)} this check does not pass, so {label.lower()} "
                                        f"alone cannot cure it.")
    # bisect between the failing current value and the passing bound
    bad, good = current, bound
    for _ in range(11):
        mid = 0.5 * (bad + good)
        if trial(mid):
            good = mid
        else:
            bad = mid
        if abs(good - bad) < step:
            break
    to = _round_toward(good, step, bound)
    if (bound > current and to > bound) or (bound < current and to < bound):
        to = bound
    return Recommendation(check_key=key, lever=lever, lever_label=label, unit=unit, from_value=current,
                          to_value=to, resolved=True, rationale="")


def _fmt_lever(lever: str, v: float) -> str:
    if lever == "intake_pressure_Pa":
        return f"{v / 1e5:.2f} bar"
    if lever == "rpm":
        return f"{v:.0f} rpm"
    if lever == "compression_ratio":
        return f"{v:.1f}:1"
    if lever == "burn_duration_deg":
        return f"{v:.0f}°"
    return f"{v:.2f}"


# --------------------------------------------------------------------------- #
# cost
# --------------------------------------------------------------------------- #

def _raw_cost(spec: dict[str, Any], m: dict[str, float | None]) -> tuple[float, list[CostLine]]:
    k = COST_COEFFICIENTS
    ign = _ignition(spec)
    cyl = int(spec.get("cylinders", 4))
    litres = float(spec.get("displacement_L") or 0.0)
    if not litres:
        b, s = float(spec.get("bore_m", 0.086)), float(spec.get("stroke_m", 0.086))
        litres = math.pi / 4 * b * b * s * cyl * 1000.0
    layout = ((spec.get("layout") or {}).get("kind") or "inline")
    lines: list[CostLine] = []

    structure = k["structure_fixed"] + k["structure_per_cylinder"] * cyl + k["structure_per_litre"] * litres
    basis = f"{k['structure_fixed']:.0f} + {k['structure_per_cylinder']:.0f} per cylinder + {k['structure_per_litre']:.0f} per litre"
    if ign == "compression":
        structure *= k["diesel_structure_factor"]
        basis += f", x{k['diesel_structure_factor']} for a diesel's heavier block, crank and steel pistons"
    lf = k["layout_factor"].get(layout, 1.0)
    if lf != 1.0:
        structure *= lf
        basis += f", x{lf} for a {layout} layout (extra head, cams and machining)"
    lines.append(CostLine(item="Block, head, crank and rods", points=structure, basis=basis))

    vg = spec.get("valve_geometry") or {}
    valves = int(vg.get("intake_valves_per_cylinder", 2)) + int(vg.get("exhaust_valves_per_cylinder", 2))
    lines.append(CostLine(item="Valvetrain", points=k["per_valve"] * cyl * valves,
                          basis=f"{k['per_valve']} per valve, {valves} valves per cylinder"))
    lines.append(CostLine(item="Fuel system", points=k["fuel_system"][ign],
                          basis="Common-rail high-pressure injection" if ign == "compression" else "Port fuel injection"))

    asp = spec.get("aspiration") or "naturally_aspirated"
    if asp == "turbocharged":
        lines.append(CostLine(item="Turbocharger", points=k["turbocharger"], basis="Turbine, compressor and wastegate"))
        if float(spec.get("intake_pressure_Pa", 1e5)) > 1.2e5:
            lines.append(CostLine(item="Intercooler", points=k["intercooler"], basis="Charge cooling above about 1.2 bar"))
    elif asp == "supercharged":
        lines.append(CostLine(item="Supercharger", points=k["supercharger"], basis="Crank-driven compressor and drive"))

    lines.append(CostLine(item="Aftertreatment", points=k["aftertreatment"][ign],
                          basis="DOC, particulate filter and SCR" if ign == "compression" else "Three-way catalyst"))

    if ign == "spark" and (m.get("peak_pressure") or 0) > PEAK_PRESSURE_BAR["spark"][0]:
        lines.append(CostLine(item="Uprated internals", points=k["uprated_internals_fraction"] * structure,
                              basis=f"Forged pistons and rods and a reinforced block above {PEAK_PRESSURE_BAR['spark'][0]:.0f} bar"))
    if (m.get("piston_speed") or 0) > PISTON_SPEED[0]:
        lines.append(CostLine(item="High-speed valvetrain", points=k["high_speed_valvetrain"],
                              basis=f"Stiffer springs and lighter valves above {PISTON_SPEED[0]:.0f} m/s piston speed"))
    return sum(l.points for l in lines), lines


@lru_cache(maxsize=1)
def _baseline_cost_and_power() -> tuple[float, float]:
    r = run_piston_simulation(PistonSimulateInput(**BASELINE))
    m = _metrics(dict(BASELINE), r)
    raw, _ = _raw_cost(dict(BASELINE), m)
    return raw, r.brake_power_W / 1e3


def _cost(spec: dict[str, Any], m: dict[str, float | None], r: PistonSimulateOutput) -> CostReport:
    raw, lines = _raw_cost(spec, m)
    base_raw, base_kw = _baseline_cost_and_power()
    scale = 100.0 / base_raw
    for l in lines:
        l.points *= scale
    index = raw * scale
    kw = max(1e-6, r.brake_power_W / 1e3)
    fuel = spec.get("fuel") if spec.get("fuel") in FUEL_PRICE_GBP_PER_L else "gasoline"
    density = get_fuel(fuel).density_kg_per_m3 / 1000.0                # kg/L
    price = FUEL_PRICE_GBP_PER_L[fuel]
    bsfc = r.bsfc_g_per_kWh if math.isfinite(r.bsfc_g_per_kWh) else 0.0
    l_per_h = bsfc * kw / 1000.0 / density
    return CostReport(
        build_cost_index=index,
        cost_index_per_kW=(index / kw) / (100.0 / base_kw),
        breakdown=lines,
        fuel_price_gbp_per_L=price,
        fuel_L_per_h=l_per_h,
        fuel_cost_gbp_per_h=l_per_h * price,
        fuel_cost_gbp_per_kWh=bsfc / 1000.0 / density * price,
        fuel_cost_gbp_per_1000h=l_per_h * price * 1000.0,
    )


# --------------------------------------------------------------------------- #
# the report
# --------------------------------------------------------------------------- #
# Order in which failures are cured: the ones that would destroy the engine or
# stop it running first, then structural load, then refinement.
PRIORITY = ["knock_margin", "ci_ignition", "smoke_phi", "lean_phi", "boost", "peak_pressure", "exhaust_T",
            "bmep", "pressure_rise", "piston_speed", "inlet_mach", "mech_eff"]

_METRIC_FOR = {
    "piston_speed": "piston_speed", "peak_pressure": "peak_pressure", "bmep": "bmep", "mech_eff": "mech_eff",
    "pressure_rise": "pressure_rise", "exhaust_T": "exhaust_T", "inlet_mach": "inlet_mach",
    "knock_margin": "knock_margin", "lean_phi": "phi", "smoke_phi": "phi", "ci_ignition": "ci_T", "boost": "boost_ok",
}


def _proof(rec: Recommendation, chk: FeasibilityCheck, spec: dict[str, Any], counter: _Counter) -> ProofSweep:
    lo, hi = sorted((rec.from_value, rec.to_value))
    pad = max((hi - lo) * 0.35, LEVER_INFO[rec.lever][2] * 3)
    lo, hi = lo - pad, hi + pad
    f = PistonSimulateInput.model_fields[rec.lever]
    for meta in f.metadata:
        if hasattr(meta, "gt"): lo = max(lo, float(meta.gt) * 1.0001)
        if hasattr(meta, "ge"): lo = max(lo, float(meta.ge))
        if hasattr(meta, "le"): hi = min(hi, float(meta.le))
    if rec.lever == "intake_pressure_Pa":
        lo = max(lo, float(spec.get("ambient_pressure_Pa", 1e5)))
    xs = [lo + (hi - lo) * i / 8 for i in range(9)]
    ys: list[float | None] = []
    pw: list[float | None] = []
    for x in xs:
        s = dict(spec); s[rec.lever] = x
        try:
            r = _solve(s, counter)
            ys.append(_metrics(s, r)[_METRIC_FOR[chk.key]])
            pw.append(r.brake_power_W / 1e3)
        except ValueError:
            ys.append(None); pw.append(None)
    label, unit, _ = LEVER_INFO[rec.lever]
    scale = 1e-5 if rec.lever == "intake_pressure_Pa" else 1.0
    return ProofSweep(lever=rec.lever, lever_label=label, lever_unit=unit, metric_key=chk.key,
                      metric_label=chk.label, metric_unit=chk.unit, x=[v * scale for v in xs], metric=ys,
                      brake_power_kW=pw, current_x=rec.from_value * scale, recommended_x=rec.to_value * scale,
                      caution=chk.caution, limit=chk.limit)


def analyse(payload: PistonSimulateInput) -> FeasibilityReport:
    counter = _Counter()
    spec = payload.model_dump(exclude_none=True)
    spec.pop("include_trace", None)

    r0 = _solve(spec, counter)
    m0 = _metrics(spec, r0)
    checks0 = _checks(spec, m0)
    verdict0 = _verdict(checks0)

    # Cure one check at a time, most fundamental first, re-solving after each.
    # Levers interact (lowering compression to cure knock also cuts peak
    # pressure), so fixing everything independently and applying it together
    # over-corrects. Sequentially, each fix is sized for the engine as it is
    # after the fixes before it.
    current = dict(spec)
    all_recs: list[Recommendation] = []
    proofs: list[ProofSweep] = []
    checks_now, m_now, r_now = checks0, m0, r0
    tried: set[tuple[str, str]] = set()
    for step in range(1, 9):
        failing = sorted((c for c in checks_now if c.status == "fail"), key=lambda c: PRIORITY.index(c.key)
                         if c.key in PRIORITY else 99)
        failing = [c for c in failing if (c.key, (_lever_for(c.key, current) or ("", 0))[0]) not in tried]
        if not failing:
            break
        chk = failing[0]
        rc = _find_cure(chk.key, current, counter)
        tried.add((chk.key, rc.lever if rc else ""))
        if rc is None:
            continue
        rc.check_label = chk.label
        rc.metric_unit = chk.unit
        rc.limit = chk.limit
        rc.metric_before = chk.value
        if not rc.resolved:
            all_recs.append(rc)
            continue
        # Steps number the changes actually made, so the list reads 1, 2, 3.
        rc.step = 1 + sum(1 for x in all_recs if x.resolved)
        proofs.append(_proof(rc, chk, current, counter))
        p_before = r_now.brake_power_W
        failing_before = {c.key for c in checks_now if c.status == "fail"}
        current[rc.lever] = rc.to_value
        r_now = _solve(current, counter)
        m_now = _metrics(current, r_now)
        checks_now = _checks(current, m_now)
        after_chk = next((c for c in checks_now if c.key == chk.key), None)
        rc.metric_after = after_chk.value if after_chk else None
        rc.also_cured = [c.label for c in checks_now
                         if c.key in failing_before and c.key != chk.key and c.status != "fail"]
        rc.brake_power_change_percent = (r_now.brake_power_W / p_before - 1.0) * 100.0 if p_before else None
        all_recs.append(rc)

    # A check another fix happened to cure is not an open problem.
    final = {c.key: c for c in checks_now}
    all_recs = [rc for rc in all_recs if rc.resolved or final.get(rc.check_key, None) is None
                or final[rc.check_key].status == "fail"]

    for rc in all_recs:
        if rc.rationale or rc.metric_before is None or rc.metric_after is None:
            continue
        unit = (" " + rc.metric_unit) if rc.metric_unit else ""
        rc.rationale = (f"{rc.check_label} {rc.metric_before:.3g}{unit} to {rc.metric_after:.3g}{unit} "
                        f"against a limit of {rc.limit:.3g}{unit}, measured by re-solving the engine with this change.")
        if rc.also_cured:
            rc.rationale += " The same change also brings " + ", ".join(x.lower() for x in rc.also_cured) + " inside its limit."

    verdict1 = _verdict(checks_now)
    before, after = _snapshot(r0), _snapshot(r_now)
    cost0, cost1 = _cost(spec, m0, r0), _cost(current, m_now, r_now)

    fails = [c for c in checks0 if c.status == "fail"]
    cautions = [c for c in checks0 if c.status == "caution"]
    if verdict0 == "feasible":
        headline = "Feasible as specified: every check is inside its design envelope."
    elif verdict0 == "marginal":
        headline = (f"Feasible, but with thin margins on {len(cautions)} check{'s' * (len(cautions) != 1)}: "
                    + ", ".join(c.label.lower() for c in cautions) + ".")
    else:
        headline = (f"Not feasible as specified: {len(fails)} check{'s' * (len(fails) != 1)} past the limit: "
                    + ", ".join(c.label.lower() for c in fails) + ".")

    parts = []
    for c in fails:
        unit = (" " + c.unit) if c.unit else ""
        if c.kind == "flag":
            parts.append(f"{c.label}: no.")
        else:
            parts.append(f"{c.label} is {c.value:.3g}{unit} against a {'maximum' if c.kind == 'max' else 'minimum'} of {c.limit:.3g}{unit}.")
    changed = [rc for rc in all_recs if rc.resolved]
    if changed:
        dp = (after.brake_power_kW / before.brake_power_kW - 1) * 100 if before.brake_power_kW else 0.0
        db = (after.bsfc_g_per_kWh / before.bsfc_g_per_kWh - 1) * 100 if before.bsfc_g_per_kWh else 0.0
        moves = "; ".join(f"{rc.lever_label.lower()} {_fmt_lever(rc.lever, rc.from_value)} to {_fmt_lever(rc.lever, rc.to_value)}"
                          for rc in changed)
        parts.append(f"Recommended: {moves}. Re-solved together, the engine is "
                     f"{ {'feasible': 'feasible', 'marginal': 'feasible with thin margins', 'not_feasible': 'still not feasible'}[verdict1] }, "
                     f"at a cost of {dp:+.1f}% brake power and {db:+.1f}% fuel consumption per kWh.")
    unresolved = [rc for rc in all_recs if not rc.resolved]
    for rc in unresolved:
        parts.append(rc.rationale)
    summary = " ".join(parts) if parts else headline

    assumptions = [
        "Limits are typical production design envelopes, not certification values; each check states its basis.",
        "Recommendations cure one failing check at a time, most severe first: each finds the smallest change to one "
        "design lever by bisecting the solver, applies it, and re-solves before the next.",
        "Exhaust-manifold temperature is estimated by isentropic blowdown of the gas at exhaust-valve opening to back-pressure, "
        f"with γ = {BURNED_GAS_GAMMA}.",
        "Build cost is a relative index built from the coefficients listed in the breakdown; it ranks configurations and is not a price.",
        "Fuel prices are assumed UK pump prices: " + ", ".join(f"{k} £{v:.2f}/L" for k, v in FUEL_PRICE_GBP_PER_L.items()) + ".",
        "Fuel cost is computed at this single operating point; a duty cycle would weight several.",
    ]

    return FeasibilityReport(
        verdict=verdict0, headline=headline, summary=summary, checks=checks0,
        recommendations=all_recs, verified_checks=checks_now, verified_verdict=verdict1,
        recommended_inputs={k: current[k] for k in current if current.get(k) != spec.get(k)},
        before=before, after=after, proofs=proofs, cost_before=cost0, cost_after=cost1,
        assumptions=assumptions, solves=counter.n,
    )
