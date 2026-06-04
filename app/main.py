"""FastAPI application for the PropulsionLab backend MVP."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

# Optional error monitoring. Active only when SENTRY_DSN is set at runtime *and*
# sentry-sdk is installed; otherwise it no-ops, so dev and test runs are
# unaffected and no third party is contacted without an explicit DSN.
_SENTRY_DSN = os.environ.get("SENTRY_DSN")
if _SENTRY_DSN:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        )
    except ImportError:  # pragma: no cover - sentry-sdk absent in dev/test
        pass

from app.engine_core.advanced_cycles import (
    simulate_ramjet_cycle,
    simulate_scramjet_cycle,
    simulate_turbofan_cycle,
    simulate_turboprop_cycle,
)
from app.engine_core.mission import (
    MissionLeg,
    fly_turbofan_mission,
    fly_turbojet_mission,
)
from app.engine_core.off_design import (
    calibrate_turbofan_reference,
    calibrate_turbojet_reference,
    solve_turbofan_off_design,
    solve_turbojet_off_design,
)
from app.engine_core.emissions import (
    ICAO_LTO_MODES,
    LTOModePoint,
    combustor_emissions,
    icao_lto_nox,
)
from app.engine_core.optimization import TurbojetDesignProblem, nsga2
from app.engine_core.sensitivity import turbojet_sensitivity
from app.cfd import CFDCase, cfd_enabled, service as cfd_service
from app.engine_core.compressor_maps import synthetic_compressor_map
from app.engine_core.map_matching import (
    default_maps_for_reference,
    match_turbojet_on_maps,
)
from app.engine_core.turbofan import TurbofanCycleInputs
from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import CycleCalculationError
from app.python_export import generate_python_script
from app.reporting import build_turbojet_pdf_report
from app.schemas import (
    AdvancedEngineOutput,
    AdvancedEngineSweepOutput,
    AdvancedEngineType,
    AdvancedSweepCaseOutput,
    AdvancedSweepSummary,
    CustomJetProfileInput,
    CustomJetProfileSimulationOutput,
    EngineComparisonCase,
    EngineComparisonInput,
    EngineComparisonOutput,
    MapMatchInput,
    MissionOutput,
    OffDesignEnvelopeOutput,
    OffDesignGridInput,
    OffDesignPointOutput,
    OffDesignSummary,
    PythonExportInput,
    AxialEmissionPoint,
    EmissionsInput,
    EmissionsOutput,
    LTOModeOutput,
    ParetoPoint,
    CFDJobOutput,
    CFDResultOutput,
    CFDSubmitInput,
    TurbojetLTOInput,
    TurbojetLTOOutput,
    TurbojetOptimizeInput,
    TurbojetOptimizeOutput,
    TurbojetSensitivityInput,
    TurbojetSensitivityOutput,
    TurbofanMissionInput,
    TurbojetMissionInput,
    RamjetInput,
    RamjetSweepInput,
    ScramjetInput,
    ScramjetSweepInput,
    TurbofanInput,
    TurbofanOffDesignInput,
    TurbofanSweepInput,
    TurbojetInput,
    TurbojetOffDesignInput,
    TurbojetOutput,
    TurbojetOverrideInput,
    TurbojetSweepCaseOutput,
    TurbojetSweepInput,
    TurbojetSweepOutput,
    TurbojetSweepSummary,
    TurbopropInput,
    TurbopropSweepInput,
)

MAX_ENVELOPE_POINTS = 400

APP_VERSION = "0.2.0"
PRESETS_PATH = Path(__file__).resolve().parent / "data" / "engine_presets.json"
STATIC_PATH = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="PropulsionLab API",
    version=APP_VERSION,
    description=(
        "Educational station-based gas-turbine and ramjet cycle simulation. "
        "Includes a mature turbojet model plus dedicated turbofan, turboprop, "
        "ramjet, and scramjet preliminary-design solvers, with sweeps and "
        "side-by-side comparison."
    ),
)
app.mount("/lab", StaticFiles(directory=STATIC_PATH, html=True), name="lab")


@app.get("/pro", include_in_schema=False)
@app.get("/pro/", include_in_schema=False)
def pro_stub() -> FileResponse:
    """Serve the PropulsionLab Pro teaser page at a clean /pro/ URL."""

    return FileResponse(STATIC_PATH / "pro" / "index.html")


@app.get("/piston", include_in_schema=False)
@app.get("/piston/", include_in_schema=False)
def piston_lab() -> FileResponse:
    """Serve the PistonLab reciprocating-engine console at a clean /piston/ URL.

    PistonLab is the DAS LABS sibling to PropulsionLab. It is in development and
    intentionally not yet linked from the portal (the portal still shows it as
    "coming soon"); the page is reachable directly so it can be built and shared
    for review before launch.
    """

    return FileResponse(STATIC_PATH / "piston" / "index.html")


def load_engine_presets() -> dict[str, Any]:
    """Load bundled educational engine presets from JSON."""

    with PRESETS_PATH.open("r", encoding="utf-8") as preset_file:
        return json.load(preset_file)


def find_preset(preset_name: str) -> dict[str, Any]:
    """Find a preset by case-insensitive name."""

    normalized_name = preset_name.casefold()
    for preset in load_engine_presets()["presets"]:
        if preset["name"].casefold() == normalized_name:
            return preset
    raise HTTPException(status_code=404, detail=f"Preset '{preset_name}' was not found.")


def run_turbojet_simulation(inputs: TurbojetInput) -> TurbojetOutput:
    """Run the core solver and translate calculation errors to API errors."""

    try:
        result = simulate_turbojet_cycle(inputs.to_cycle_inputs())
    except CycleCalculationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TurbojetOutput.model_validate(result)


@app.get("/", include_in_schema=False)
def portal() -> FileResponse:
    """DAS LABS portal — choose between PropulsionLab and PistonLab (coming soon)."""

    return FileResponse(STATIC_PATH / "portal.html")


@app.get("/api")
def root() -> dict[str, Any]:
    """Return API metadata and discoverable endpoints."""

    return {
        "project": "PropulsionLab",
        "version": APP_VERSION,
        "available_endpoints": [
            "GET /",
            "GET /lab",
            "GET /presets",
            "POST /simulate/turbojet",
            "POST /simulate/turbojet/sweep",
            "POST /simulate/turbojet/off-design",
            "POST /simulate/turbojet/map-match",
            "POST /simulate/turbojet/from-profile",
            "POST /simulate/turbofan",
            "POST /simulate/turbofan/sweep",
            "POST /simulate/turbofan/off-design",
            "POST /mission/turbojet",
            "POST /mission/turbofan",
            "POST /emissions/combustor",
            "POST /emissions/turbojet/lto",
            "POST /optimize/turbojet",
            "POST /analyze/turbojet/sensitivity",
            "POST /export/python",
            "GET /maps/compressor",
            "POST /simulate/turboprop",
            "POST /simulate/turboprop/sweep",
            "POST /simulate/ramjet",
            "POST /simulate/ramjet/sweep",
            "POST /simulate/scramjet",
            "POST /simulate/scramjet/sweep",
            "POST /compare/engines",
            "POST /reports/turbojet/pdf",
            "POST /reports/{engine_type}/pdf",
            "POST /simulate/turbojet/from-preset/{preset_name}",
            "POST /simulate/{engine_type}/from-preset/{preset_name}",
        ],
    }


# ---------------------------------------------------------------------------
# Turbojet (preserved)
# ---------------------------------------------------------------------------


@app.post("/simulate/turbojet", response_model=TurbojetOutput)
def simulate_turbojet(inputs: TurbojetInput) -> TurbojetOutput:
    """Simulate the v1 educational turbojet cycle."""

    return run_turbojet_simulation(inputs)


@app.post("/simulate/turbojet/sweep", response_model=TurbojetSweepOutput)
def simulate_turbojet_sweep(inputs: TurbojetSweepInput) -> TurbojetSweepOutput:
    """Run a one-parameter sweep for the v1 educational turbojet cycle."""

    cases: list[TurbojetSweepCaseOutput] = []
    for value in inputs.values:
        case_data = inputs.base_input.model_dump()
        case_data[inputs.sweep_parameter] = value
        try:
            case_input = TurbojetInput.model_validate(case_data)
            case_output = run_turbojet_simulation(case_input)
        except (HTTPException, ValidationError) as exc:
            error_detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            cases.append(
                TurbojetSweepCaseOutput(
                    input_value=value, success=False, error=str(error_detail)
                )
            )
            continue
        cases.append(
            TurbojetSweepCaseOutput(input_value=value, success=True, output=case_output)
        )

    successful = [c.output for c in cases if c.output is not None]
    summary = TurbojetSweepSummary(
        successful_cases=len(successful),
        failed_cases=len(cases) - len(successful),
        max_thrust_N=max((o.thrust_N for o in successful), default=None),
        min_TSFC_kg_per_kN_hr=min((o.TSFC_kg_per_kN_hr for o in successful), default=None),
        choked_cases=sum(1 for o in successful if o.nozzle_choked),
    )
    return TurbojetSweepOutput(
        sweep_parameter=inputs.sweep_parameter, cases=cases, summary=summary
    )


@app.post("/simulate/turbojet/from-profile", response_model=CustomJetProfileSimulationOutput)
def simulate_turbojet_from_profile(
    profile: CustomJetProfileInput,
) -> CustomJetProfileSimulationOutput:
    """Simulate a user-defined jet profile without storing it on the server."""

    profile_inputs = profile.default_inputs.model_copy(
        update={"engine_variant": profile.engine_type}
    )
    return CustomJetProfileSimulationOutput(
        profile_name=profile.name,
        engine_type=profile.engine_type,
        output=run_turbojet_simulation(profile_inputs),
    )


# ---------------------------------------------------------------------------
# Combustor emissions: reactor-network NOx / CO + ICAO LTO (Month-4 feature)
# ---------------------------------------------------------------------------


def _emissions_to_schema(result: Any) -> EmissionsOutput:
    """Map an engine-core EmissionResult onto the API schema."""

    pz = result.primary_zone_temperature_K
    return EmissionsOutput(
        ei_nox_g_per_kg=result.ei_nox_g_per_kg,
        ei_co_g_per_kg=result.ei_co_g_per_kg,
        ei_hc_g_per_kg=result.ei_hc_g_per_kg,
        ei_co2_g_per_kg=result.ei_co2_g_per_kg,
        ei_h2o_g_per_kg=result.ei_h2o_g_per_kg,
        soot_proxy=result.soot_proxy,
        primary_zone_temperature_K=None if (pz != pz) else pz,   # drop NaN
        phi_primary=result.phi_primary,
        phi_overall=result.phi_overall,
        fuel=result.fuel,
        source=result.source,
        axial_profile=[
            AxialEmissionPoint(
                x_fraction=p.x_fraction,
                temperature_K=p.temperature_K,
                no_ppm=p.no_ppm,
                co_ppm=p.co_ppm,
            )
            for p in result.axial_profile
        ],
        notes=result.notes,
    )


@app.post("/emissions/combustor", response_model=EmissionsOutput)
def emissions_combustor(inputs: EmissionsInput) -> EmissionsOutput:
    """Reactor-network emission indices for a combustor at a given inlet state."""

    try:
        result = combustor_emissions(
            inputs.combustor_inlet_temperature_K,
            inputs.combustor_inlet_pressure_Pa,
            inputs.fuel_air_ratio,
            fuel=inputs.fuel,
            phi_primary=inputs.phi_primary,
            tau_primary_s=inputs.tau_primary_s,
            tau_secondary_s=inputs.tau_secondary_s,
            n_dilution=inputs.n_dilution,
        )
    except (ValueError, CycleCalculationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _emissions_to_schema(result)


def _turbojet_combustor_inlet(result: dict[str, Any]) -> tuple[float, float, float, float, float]:
    """Pull (T3, P3, FAR, fuel_flow, thrust_kN) from a turbojet cycle result."""

    station3 = result["station_table"][3]
    t3 = float(station3["stagnation_temperature_K"])
    p3 = float(station3["stagnation_pressure_Pa"])
    far = float(result.get("core_fuel_air_ratio") or result["fuel_air_ratio"])
    return t3, p3, far, float(result["fuel_flow_kg_s"]), float(result["thrust_kN"])


@app.post("/emissions/turbojet/lto", response_model=TurbojetLTOOutput)
def emissions_turbojet_lto(inputs: TurbojetLTOInput) -> TurbojetLTOOutput:
    """Engine-coupled ICAO landing-takeoff NOx estimate for a turbojet deck.

    Evaluates the four ICAO modes sea-level static by throttling the
    turbine-inlet temperature to each thrust setting, computes the
    reactor-network EINOx and fuel flow at each, then aggregates Dp(NOx) and the
    Dp/Foo certification metric.
    """

    # ICAO LTO is defined sea-level static — pin altitude and Mach there.
    base = inputs.design.model_copy(update={"altitude_m": 0.0, "mach": 0.0})
    design_tit = base.turbine_inlet_temperature_K
    design_pr = base.compressor_pressure_ratio

    # Throttle schedule. A real spool slows at part power, dropping the overall
    # pressure ratio, the turbine-inlet temperature, AND the inducted air mass
    # flow together — that joint lapse both makes the combustor-inlet state (and
    # hence EINOx) fall toward idle and lets thrust reach the low idle setting.
    # The educational cycle holds all three fixed, so we impose a simple combined
    # schedule parametrised by s in [0, 1] (s = 1 is the design point):
    #   OPR(s) = 1 + (OPR_des - 1) * (0.12 + 0.88 s)
    #   Tt4(s) = Tt4_idle + (Tt4_des - Tt4_idle) * s
    #   Wair(s) = Wair_des * sqrt((OPR(s) - 1) / (OPR_des - 1))   [spool-speed proxy]
    # Documented as a schedule, not a matched off-design solution.
    tit_idle = max(800.0, min(design_tit - 50.0, 950.0))
    design_air = base.mass_flow_air_kg_s
    samples: list[dict[str, float]] = []
    n_sweep = 36
    for k in range(n_sweep + 1):
        s = k / n_sweep
        pr = 1.0 + (design_pr - 1.0) * (0.12 + 0.88 * s)
        tit = tit_idle + (design_tit - tit_idle) * s
        air = design_air * ((pr - 1.0) / (design_pr - 1.0)) ** 0.5
        if tit <= 0.0 or pr <= 1.0 or air <= 0.0:
            continue
        case = base.model_copy(update={
            "compressor_pressure_ratio": pr,
            "turbine_inlet_temperature_K": tit,
            "mass_flow_air_kg_s": air,
        })
        try:
            res = simulate_turbojet_cycle(case.to_cycle_inputs())
            t3, p3, far, wf, thr = _turbojet_combustor_inlet(res)
        except CycleCalculationError:
            continue
        samples.append({"tit": tit, "pr": pr, "t3": t3, "p3": p3, "far": far, "wf": wf, "thr": thr})

    if not samples:
        raise HTTPException(status_code=400, detail="Could not evaluate any throttle setting.")

    rated_thrust_kN = max(s["thr"] for s in samples)
    notes: list[str] = []
    mode_points: list[LTOModePoint] = []
    mode_rows: list[LTOModeOutput] = []
    for name, frac, time_s in ICAO_LTO_MODES:
        target = frac * rated_thrust_kN
        pick = min(samples, key=lambda s: abs(s["thr"] - target))
        achieved_frac = pick["thr"] / max(rated_thrust_kN, 1e-9)
        if abs(pick["thr"] - target) / max(rated_thrust_kN, 1e-9) > 0.06:
            notes.append(
                f"{name}: nearest achievable throttle is "
                f"{achieved_frac * 100:.0f}% F00 (target {frac * 100:.0f}%)."
            )
        emis = combustor_emissions(
            pick["t3"], pick["p3"], pick["far"],
            fuel=inputs.fuel, phi_primary=inputs.phi_primary,
        )
        mode_points.append(LTOModePoint(
            name=name, thrust_fraction=frac, time_in_mode_s=time_s,
            ei_nox_g_per_kg=emis.ei_nox_g_per_kg, fuel_flow_kg_s=pick["wf"],
        ))
        mode_rows.append(LTOModeOutput(
            name=name, thrust_fraction=frac, thrust_kN=pick["thr"],
            turbine_inlet_temperature_K=pick["tit"],
            combustor_inlet_temperature_K=pick["t3"],
            combustor_inlet_pressure_Pa=pick["p3"],
            fuel_air_ratio=pick["far"],
            ei_nox_g_per_kg=emis.ei_nox_g_per_kg, fuel_flow_kg_s=pick["wf"],
            time_in_mode_s=time_s,
            nox_g=emis.ei_nox_g_per_kg * pick["wf"] * time_s,
        ))

    agg = icao_lto_nox(mode_points, rated_thrust_kN=rated_thrust_kN)
    notes.insert(0, (
        "Estimate: reactor-network EINOx on a simplified throttle schedule "
        "(no off-design spool match, single primary-zone equivalence ratio, no "
        "fuel staging). The take-off EINOx is calibrated to modern combustors; "
        "part-power NOx is under-predicted, so Dp/Foo is order-of-magnitude, not "
        "a certification value."
    ))
    return TurbojetLTOOutput(
        rated_thrust_kN=rated_thrust_kN,
        dp_nox_g=agg.dp_nox_g,
        fuel_burn_kg=agg.fuel_burn_kg,
        dp_foo_g_per_kN=agg.dp_foo_g_per_kN,
        modes=mode_rows,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# NSGA-II multi-objective design optimisation (Month-5 feature)
# ---------------------------------------------------------------------------


@app.post("/optimize/turbojet", response_model=TurbojetOptimizeOutput)
def optimize_turbojet(inputs: TurbojetOptimizeInput) -> TurbojetOptimizeOutput:
    """Trace the Pareto front of competing turbojet design objectives with NSGA-II.

    Decision variables are the compressor pressure ratio and turbine-inlet
    temperature; the flight condition comes from the base deck. Objectives (all
    framed as minimisation; specific thrust is maximised) trade off against one
    another subject to a compressor-exit temperature cap and a fuel-air band.
    """

    if inputs.pr_min >= inputs.pr_max:
        raise HTTPException(status_code=400, detail="pr_min must be below pr_max.")
    if inputs.tit_min_K >= inputs.tit_max_K:
        raise HTTPException(status_code=400, detail="tit_min_K must be below tit_max_K.")
    if inputs.far_min >= inputs.far_max:
        raise HTTPException(status_code=400, detail="far_min must be below far_max.")

    base = inputs.design.to_cycle_inputs()
    problem = TurbojetDesignProblem(
        base=base,
        pr_bounds=(inputs.pr_min, inputs.pr_max),
        tit_bounds=(inputs.tit_min_K, inputs.tit_max_K),
        objectives=tuple(inputs.objectives),
        tt3_max_K=inputs.tt3_max_K,
        far_min=inputs.far_min,
        far_max=inputs.far_max,
    )
    result = nsga2(
        problem,
        pop_size=inputs.population_size,
        n_gen=inputs.generations,
        seed=inputs.seed,
    )

    # Re-run each Pareto design once to attach full display metrics, and sort the
    # front by the first objective so the curve plots cleanly.
    pts: list[ParetoPoint] = []
    for idx in result.pareto_indices:
        pr, tit = float(result.X[idx, 0]), float(result.X[idx, 1])
        try:
            r = simulate_turbojet_cycle(
                replace(base, compressor_pressure_ratio=pr,
                        turbine_inlet_temperature_K=tit)
            )
        except CycleCalculationError:
            continue
        pts.append(ParetoPoint(
            compressor_pressure_ratio=pr,
            turbine_inlet_temperature_K=tit,
            objective_values=[float(v) for v in result.F[idx]],
            thrust_kN=float(r["thrust_kN"]),
            TSFC_kg_per_kN_hr=float(r["TSFC_kg_per_kN_hr"]),
            specific_thrust_N_per_kg_s=float(r["specific_thrust_N_per_kg_s"]),
            compressor_exit_temperature_K=float(r["station_table"][3]["stagnation_temperature_K"]),
            fuel_air_ratio=float(r.get("core_fuel_air_ratio") or r["fuel_air_ratio"]),
            overall_efficiency_estimate=float(r["overall_efficiency_estimate"]),
        ))
    pts.sort(key=lambda p: p.objective_values[0])

    notes = [
        "Self-contained NSGA-II (non-dominated sort + crowding distance + SBX + "
        "polynomial mutation), constraint-dominated. Decision variables: "
        "compressor pressure ratio and turbine-inlet temperature.",
    ]
    if result.feasible_fraction < 1.0:
        notes.append(
            f"{result.feasible_fraction * 100:.0f}% of the final population is feasible "
            "(within the Tt3 cap and fuel-air band)."
        )

    return TurbojetOptimizeOutput(
        objective_keys=list(inputs.objectives),
        objective_labels=problem.objective_labels,
        pareto_front=pts,
        population_size=inputs.population_size,
        generations=inputs.generations,
        evaluations=result.n_evaluations,
        feasible_fraction=result.feasible_fraction,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# One-at-a-time sensitivity (tornado chart)
# ---------------------------------------------------------------------------


@app.post("/analyze/turbojet/sensitivity", response_model=TurbojetSensitivityOutput)
def analyze_turbojet_sensitivity(
    inputs: TurbojetSensitivityInput,
) -> TurbojetSensitivityOutput:
    """Rank turbojet design inputs by their local effect on a chosen output.

    Perturbs each input by +/- ``delta_fraction`` around the deck from the Cycle
    tab, re-runs the cycle, and returns the metric swings sorted largest-first
    for a tornado chart. Local, one-at-a-time finite differences, so it reports
    slope and sign near the operating point, not input interactions.
    """

    try:
        result = turbojet_sensitivity(
            inputs.design.to_cycle_inputs(),
            metric=inputs.metric,
            delta_fraction=inputs.delta_fraction,
        )
    except (ValueError, CycleCalculationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TurbojetSensitivityOutput.model_validate(result)


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Cloud-CFD job control plane (future / Pro — gated behind ENABLE_CFD)
# ---------------------------------------------------------------------------


def _require_cfd() -> None:
    """404 unless the CFD feature is switched on. Keeps it dark at launch."""

    if not cfd_enabled():
        raise HTTPException(status_code=404, detail="CFD feature is not enabled.")


@app.post("/cfd/jobs", response_model=CFDJobOutput)
def cfd_submit(inputs: CFDSubmitInput) -> CFDJobOutput:
    """Queue a nozzle CFD case and return the created job (gated)."""

    _require_cfd()
    job = cfd_service.submit(CFDCase(
        case_name=inputs.case_name,
        throat_area_m2=inputs.throat_area_m2,
        area_ratio=inputs.area_ratio,
        nozzle_pressure_ratio=inputs.nozzle_pressure_ratio,
        gamma=inputs.gamma,
        resolution=inputs.resolution,
    ))
    return CFDJobOutput(**job.to_dict())


@app.get("/cfd/jobs", response_model=list[CFDJobOutput])
def cfd_list() -> list[CFDJobOutput]:
    """List CFD jobs, most recent first (gated)."""

    _require_cfd()
    return [CFDJobOutput(**j.to_dict()) for j in cfd_service.list()]


@app.get("/cfd/jobs/{job_id}", response_model=CFDJobOutput)
def cfd_status(job_id: str) -> CFDJobOutput:
    """Poll a CFD job's status (gated)."""

    _require_cfd()
    job = cfd_service.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return CFDJobOutput(**job.to_dict())


@app.get("/cfd/jobs/{job_id}/result", response_model=CFDResultOutput)
def cfd_result(job_id: str) -> CFDResultOutput:
    """Fetch a completed CFD job's field result (gated)."""

    _require_cfd()
    job = cfd_service.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.result is None:
        raise HTTPException(status_code=409, detail=f"Job is {job.status.value}, no result yet.")
    return CFDResultOutput(id=job.id, status=job.status.value, result=job.result)


@app.post("/cfd/jobs/{job_id}/cancel", response_model=CFDJobOutput)
def cfd_cancel(job_id: str) -> CFDJobOutput:
    """Request cancellation of a running CFD job (gated)."""

    _require_cfd()
    job = cfd_service.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    cfd_service.cancel(job_id)
    return CFDJobOutput(**job.to_dict())


# ---------------------------------------------------------------------------
# Advanced engines — single-point simulation
# ---------------------------------------------------------------------------


def _run_advanced(engine_type: AdvancedEngineType, payload: Any) -> AdvancedEngineOutput:
    """Dispatch an advanced engine input to the right solver."""

    solver = {
        "turbofan": simulate_turbofan_cycle,
        "turboprop": simulate_turboprop_cycle,
        "ramjet": simulate_ramjet_cycle,
        "scramjet": simulate_scramjet_cycle,
    }[engine_type]
    try:
        result = solver(payload)
    except CycleCalculationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AdvancedEngineOutput.model_validate(result)


@app.post("/simulate/turbofan", response_model=AdvancedEngineOutput)
def simulate_turbofan(inputs: TurbofanInput) -> AdvancedEngineOutput:
    """Simulate a two-spool turbofan cycle (separate or mixed flow, optional AB)."""

    return _run_advanced("turbofan", inputs)


@app.post("/simulate/turboprop", response_model=AdvancedEngineOutput)
def simulate_turboprop(inputs: TurbopropInput) -> AdvancedEngineOutput:
    """Simulate a gas-generator + free-power-turbine turboprop cycle."""

    return _run_advanced("turboprop", inputs)


@app.post("/simulate/ramjet", response_model=AdvancedEngineOutput)
def simulate_ramjet(inputs: RamjetInput) -> AdvancedEngineOutput:
    """Simulate a subsonic-combustion ramjet cycle with MIL-spec inlet recovery."""

    return _run_advanced("ramjet", inputs)


@app.post("/simulate/scramjet", response_model=AdvancedEngineOutput)
def simulate_scramjet(inputs: ScramjetInput) -> AdvancedEngineOutput:
    """Simulate a reduced-order supersonic-combustion scramjet cycle."""

    return _run_advanced("scramjet", inputs)


# ---------------------------------------------------------------------------
# Advanced engines — one-parameter sweeps
# ---------------------------------------------------------------------------


def _run_advanced_sweep(
    engine_type: AdvancedEngineType,
    input_model: type[BaseModel],
    base_input: BaseModel,
    sweep_parameter: str,
    values: list[float],
) -> AdvancedEngineSweepOutput:
    """Generic advanced-engine sweep loop."""

    cases: list[AdvancedSweepCaseOutput] = []
    for value in values:
        case_data = base_input.model_dump()
        if sweep_parameter not in case_data:
            cases.append(
                AdvancedSweepCaseOutput(
                    input_value=value,
                    success=False,
                    error=f"Unknown parameter '{sweep_parameter}' for {engine_type}.",
                )
            )
            continue
        case_data[sweep_parameter] = value
        try:
            case_input = input_model.model_validate(case_data)
            case_output = _run_advanced(engine_type, case_input)
        except (HTTPException, ValidationError) as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            cases.append(
                AdvancedSweepCaseOutput(
                    input_value=value, success=False, error=str(detail)
                )
            )
            continue
        cases.append(
            AdvancedSweepCaseOutput(input_value=value, success=True, output=case_output)
        )
    successful = [c.output for c in cases if c.output is not None]
    summary = AdvancedSweepSummary(
        successful_cases=len(successful),
        failed_cases=len(cases) - len(successful),
        max_thrust_N=max((o.thrust_N for o in successful), default=None),
        min_TSFC_kg_per_kN_hr=min((o.TSFC_kg_per_kN_hr for o in successful), default=None),
    )
    return AdvancedEngineSweepOutput(
        engine_type=engine_type, sweep_parameter=sweep_parameter, cases=cases, summary=summary
    )


@app.post("/simulate/turbofan/sweep", response_model=AdvancedEngineSweepOutput)
def simulate_turbofan_sweep(inputs: TurbofanSweepInput) -> AdvancedEngineSweepOutput:
    """Sweep one parameter of the turbofan model."""

    return _run_advanced_sweep(
        "turbofan", TurbofanInput, inputs.base_input, inputs.sweep_parameter, inputs.values
    )


@app.post("/simulate/turboprop/sweep", response_model=AdvancedEngineSweepOutput)
def simulate_turboprop_sweep(inputs: TurbopropSweepInput) -> AdvancedEngineSweepOutput:
    """Sweep one parameter of the turboprop model."""

    return _run_advanced_sweep(
        "turboprop", TurbopropInput, inputs.base_input, inputs.sweep_parameter, inputs.values
    )


@app.post("/simulate/ramjet/sweep", response_model=AdvancedEngineSweepOutput)
def simulate_ramjet_sweep(inputs: RamjetSweepInput) -> AdvancedEngineSweepOutput:
    """Sweep one parameter of the ramjet model."""

    return _run_advanced_sweep(
        "ramjet", RamjetInput, inputs.base_input, inputs.sweep_parameter, inputs.values
    )


@app.post("/simulate/scramjet/sweep", response_model=AdvancedEngineSweepOutput)
def simulate_scramjet_sweep(inputs: ScramjetSweepInput) -> AdvancedEngineSweepOutput:
    """Sweep one parameter of the scramjet model."""

    return _run_advanced_sweep(
        "scramjet", ScramjetInput, inputs.base_input, inputs.sweep_parameter, inputs.values
    )


# ---------------------------------------------------------------------------
# Off-design matching envelopes
# ---------------------------------------------------------------------------


def _off_design_point_output(
    altitude_m: float,
    mach: float,
    throttle_K: float,
    result: dict[str, Any],
) -> OffDesignPointOutput:
    """Project a solver result dict onto the envelope point schema."""

    off = result.get("off_design", {})
    return OffDesignPointOutput(
        altitude_m=altitude_m,
        mach=mach,
        turbine_inlet_temperature_K=throttle_K,
        success=True,
        converged=off.get("converged"),
        thrust_kN=result.get("thrust_kN"),
        TSFC_kg_per_kN_hr=result.get("TSFC_kg_per_kN_hr"),
        overall_efficiency_estimate=result.get("overall_efficiency_estimate"),
        effective_mass_flow_air_kg_s=result.get("effective_mass_flow_air_kg_s"),
        compressor_pressure_ratio=result.get("compressor_pressure_ratio"),
        fan_pressure_ratio=result.get("fan_pressure_ratio"),
        overall_pressure_ratio=result.get("overall_pressure_ratio"),
        nozzle_choked=result.get("nozzle_choked"),
    )


def _build_off_design_envelope(
    engine_type: str,
    grid: OffDesignGridInput,
    *,
    design_altitude_m: float,
    design_mach: float,
    design_throttle_K: float,
    solve_point: Any,
) -> OffDesignEnvelopeOutput:
    """Evaluate the cartesian product of the operating-point grid.

    ``solve_point(altitude_m, mach, throttle_K) -> result dict`` runs one matched
    point; calibration is done once by the caller. Each axis falls back to the
    design value when omitted. Per-point solver failures are captured as
    ``success=False`` rows rather than aborting the whole envelope.
    """

    altitudes = grid.altitudes_m or [design_altitude_m]
    machs = grid.machs or [design_mach]
    throttles = grid.throttles_K or [design_throttle_K]
    total = len(altitudes) * len(machs) * len(throttles)
    if total > MAX_ENVELOPE_POINTS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Envelope grid has {total} points, exceeding the "
                f"{MAX_ENVELOPE_POINTS}-point limit. Reduce the axis lengths."
            ),
        )

    points: list[OffDesignPointOutput] = []
    for altitude_m in altitudes:
        for mach in machs:
            for throttle_K in throttles:
                try:
                    result = solve_point(altitude_m, mach, throttle_K)
                except CycleCalculationError as exc:
                    points.append(
                        OffDesignPointOutput(
                            altitude_m=altitude_m,
                            mach=mach,
                            turbine_inlet_temperature_K=throttle_K,
                            success=False,
                            error=str(exc),
                        )
                    )
                    continue
                points.append(
                    _off_design_point_output(altitude_m, mach, throttle_K, result)
                )

    successful = [p for p in points if p.success]
    summary = OffDesignSummary(
        points=len(points),
        successful=len(successful),
        failed=len(points) - len(successful),
        max_thrust_kN=max((p.thrust_kN for p in successful if p.thrust_kN is not None), default=None),
        min_TSFC_kg_per_kN_hr=min(
            (p.TSFC_kg_per_kN_hr for p in successful if p.TSFC_kg_per_kN_hr is not None),
            default=None,
        ),
    )
    return OffDesignEnvelopeOutput(engine_type=engine_type, points=points, summary=summary)


@app.post("/simulate/turbojet/off-design", response_model=OffDesignEnvelopeOutput)
def simulate_turbojet_off_design(inputs: TurbojetOffDesignInput) -> OffDesignEnvelopeOutput:
    """Matched off-design envelope for the fixed-geometry turbojet.

    Calibrates the choked-turbine matching constants from the ``design`` spec
    once, then solves the matched operating point at every node of the
    ``grid`` (altitude x Mach x throttle Tt4).
    """

    try:
        reference = calibrate_turbojet_reference(inputs.design.to_cycle_inputs())
    except CycleCalculationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def solve_point(altitude_m: float, mach: float, throttle_K: float) -> dict[str, Any]:
        return solve_turbojet_off_design(
            reference,
            altitude_m=altitude_m,
            mach=mach,
            turbine_inlet_temperature_K=throttle_K,
        )

    envelope = _build_off_design_envelope(
        "turbojet",
        inputs.grid,
        design_altitude_m=inputs.design.altitude_m,
        design_mach=inputs.design.mach,
        design_throttle_K=inputs.design.turbine_inlet_temperature_K,
        solve_point=solve_point,
    )
    envelope.design_thrust_kN = next(
        (p.thrust_kN for p in envelope.points if p.success), None
    )
    return envelope


@app.post("/simulate/turbojet/map-match")
def map_match_turbojet(inputs: MapMatchInput) -> dict[str, Any]:
    """Match a turbojet running line on synthetic compressor/turbine maps.

    Calibrates the off-design reference from the ``design`` deck, sizes the
    synthetic maps to it, then matches the operating point on the compressor map
    at each throttle of a sweep (failed/unchoked points are dropped). Returns the
    compressor map plus the matched running line with map coordinates, so the
    frontend can draw the operating line and marker directly on the map.
    """

    try:
        reference = calibrate_turbojet_reference(inputs.design.to_cycle_inputs())
        compressor_map, turbine_map = default_maps_for_reference(reference)
    except CycleCalculationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    altitude_m = inputs.altitude_m if inputs.altitude_m is not None else inputs.design.altitude_m
    mach = inputs.mach if inputs.mach is not None else inputs.design.mach
    design_tt4 = reference.design_tt4_K

    if inputs.throttles_K:
        throttles = list(inputs.throttles_K)
    else:
        fractions = [0.90 + 0.01 * k for k in range(0, 17)]  # 0.90 .. 1.06
        throttles = sorted({round(design_tt4 * f, 4) for f in fractions} | {design_tt4})

    points: list[dict[str, Any]] = []
    for throttle_K in throttles:
        try:
            result = match_turbojet_on_maps(
                reference,
                altitude_m=altitude_m,
                mach=mach,
                turbine_inlet_temperature_K=throttle_K,
                compressor_map=compressor_map,
                turbine_map=turbine_map,
            )
        except CycleCalculationError:
            continue
        comp = result["maps"]["compressor"]
        points.append(
            {
                "throttle_K": throttle_K,
                "corrected_speed": comp["corrected_speed"],
                "beta": comp["beta"],
                "corrected_mass_flow": comp["corrected_mass_flow"],
                "pressure_ratio": comp["pressure_ratio"],
                "efficiency": comp["efficiency"],
                "surge_margin": comp["surge_margin"],
                "in_range": comp["in_range"],
                "thrust_kN": result.get("thrust_kN"),
                "TSFC_kg_per_kN_hr": result.get("TSFC_kg_per_kN_hr"),
                "converged": result["maps"]["converged"],
            }
        )

    points.sort(key=lambda p: p["corrected_mass_flow"])
    # Index of the point closest to the design throttle (the default marker).
    design_index = (
        min(
            range(len(points)),
            key=lambda i: abs(points[i]["throttle_K"] - design_tt4),
        )
        if points
        else None
    )

    return {
        "engine_type": "turbojet",
        "altitude_m": altitude_m,
        "mach": mach,
        "design_throttle_K": design_tt4,
        "design_index": design_index,
        "synthetic": bool(compressor_map.is_synthetic),
        "compressor_map": compressor_map.to_dict(),
        "points": points,
    }


@app.post("/simulate/turbofan/off-design", response_model=OffDesignEnvelopeOutput)
def simulate_turbofan_off_design(inputs: TurbofanOffDesignInput) -> OffDesignEnvelopeOutput:
    """Matched off-design envelope for the two-spool turbofan (separate flow).

    Calibrates both spools' choked-turbine matching constants from the
    ``design`` spec once, then solves the matched point at every grid node.
    """

    try:
        design = TurbofanCycleInputs(**inputs.design.model_dump())
        reference = calibrate_turbofan_reference(design)
    except CycleCalculationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def solve_point(altitude_m: float, mach: float, throttle_K: float) -> dict[str, Any]:
        return solve_turbofan_off_design(
            reference,
            altitude_m=altitude_m,
            mach=mach,
            turbine_inlet_temperature_K=throttle_K,
        )

    envelope = _build_off_design_envelope(
        "turbofan",
        inputs.grid,
        design_altitude_m=inputs.design.altitude_m,
        design_mach=inputs.design.mach,
        design_throttle_K=inputs.design.turbine_inlet_temperature_K,
        solve_point=solve_point,
    )
    envelope.design_thrust_kN = next(
        (p.thrust_kN for p in envelope.points if p.success), None
    )
    return envelope


# ---------------------------------------------------------------------------
# Mission profiles
# ---------------------------------------------------------------------------


def _mission_legs(profile: Any) -> list[MissionLeg]:
    """Convert validated mission segments into engine-core mission legs."""

    return [
        MissionLeg(
            altitude_m=seg.altitude_m,
            mach=seg.mach,
            throttle_K=seg.throttle_K,
            duration_s=seg.duration_s,
            name=seg.name,
        )
        for seg in profile.segments
    ]


@app.post("/mission/turbojet", response_model=MissionOutput)
def mission_turbojet(inputs: TurbojetMissionInput) -> MissionOutput:
    """Fly a mission profile on a turbojet, accumulating fuel burn and time.

    Calibrates the engine once, then matches each leg off-design at its
    altitude / Mach / throttle and integrates ``fuel_flow * duration``.
    """

    try:
        result = fly_turbojet_mission(
            inputs.design.to_cycle_inputs(),
            _mission_legs(inputs.profile),
            name=inputs.profile.name,
        )
    except CycleCalculationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MissionOutput.model_validate(result)


@app.post("/mission/turbofan", response_model=MissionOutput)
def mission_turbofan(inputs: TurbofanMissionInput) -> MissionOutput:
    """Fly a mission profile on a two-spool turbofan (separate flow)."""

    try:
        design = TurbofanCycleInputs(**inputs.design.model_dump())
        result = fly_turbofan_mission(
            design,
            _mission_legs(inputs.profile),
            name=inputs.profile.name,
        )
    except CycleCalculationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MissionOutput.model_validate(result)


# ---------------------------------------------------------------------------
# Side-by-side comparison
# ---------------------------------------------------------------------------


@app.post("/compare/engines", response_model=EngineComparisonOutput)
def compare_engines(inputs: EngineComparisonInput) -> EngineComparisonOutput:
    """Compare 2-5 engine specs side by side at their own design points."""

    cases: list[EngineComparisonCase] = []
    warnings: list[str] = []
    for spec in inputs.specs:
        try:
            if spec.engine_type == "turbojet":
                tj_input = spec.turbojet_input or TurbojetInput()
                output = run_turbojet_simulation(tj_input)
                cases.append(
                    EngineComparisonCase(
                        label=spec.label,
                        engine_type=spec.engine_type,
                        success=True,
                        thrust_kN=output.thrust_kN,
                        TSFC_kg_per_kN_hr=output.TSFC_kg_per_kN_hr,
                        thermal_efficiency_estimate=output.thermal_efficiency_estimate,
                        propulsive_efficiency_estimate=output.propulsive_efficiency_estimate,
                        overall_efficiency_estimate=output.overall_efficiency_estimate,
                        fuel_air_ratio=output.fuel_air_ratio,
                        nozzle_choked=output.nozzle_choked,
                    )
                )
            else:
                payload = {
                    "turbofan": spec.turbofan_input or TurbofanInput(),
                    "turboprop": spec.turboprop_input or TurbopropInput(),
                    "ramjet": spec.ramjet_input or RamjetInput(),
                    "scramjet": spec.scramjet_input or ScramjetInput(),
                }[spec.engine_type]
                output = _run_advanced(spec.engine_type, payload)
                cases.append(
                    EngineComparisonCase(
                        label=spec.label,
                        engine_type=spec.engine_type,
                        success=True,
                        thrust_kN=output.thrust_kN,
                        TSFC_kg_per_kN_hr=output.TSFC_kg_per_kN_hr,
                        thermal_efficiency_estimate=output.thermal_efficiency_estimate,
                        propulsive_efficiency_estimate=output.propulsive_efficiency_estimate,
                        overall_efficiency_estimate=output.overall_efficiency_estimate,
                        fuel_air_ratio=output.fuel_air_ratio,
                        nozzle_choked=output.nozzle_choked,
                    )
                )
        except HTTPException as exc:
            cases.append(
                EngineComparisonCase(
                    label=spec.label,
                    engine_type=spec.engine_type,
                    success=False,
                    error=str(exc.detail),
                )
            )
    if len({c.engine_type for c in cases}) > 1:
        warnings.append(
            "Comparison spans different engine families; thrust definitions and "
            "design Mach envelopes differ."
        )
    return EngineComparisonOutput(cases=cases, warnings=warnings)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


@app.post("/reports/turbojet/pdf")
def turbojet_pdf_report(inputs: TurbojetInput) -> Response:
    """Generate a compact PDF performance report for a turbojet simulation."""

    try:
        result = simulate_turbojet_cycle(inputs.to_cycle_inputs())
    except CycleCalculationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=build_turbojet_pdf_report(result, inputs=inputs.model_dump()),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="propulsionlab-report.pdf"'},
    )


@app.post("/reports/{engine_type}/pdf")
def advanced_engine_pdf_report(
    engine_type: AdvancedEngineType,
    payload: Annotated[dict[str, Any], Body()] | None = None,
) -> Response:
    """Generate a compact PDF performance report for non-turbojet engines."""

    schema_by_engine = {
        "turbofan": TurbofanInput,
        "turboprop": TurbopropInput,
        "ramjet": RamjetInput,
        "scramjet": ScramjetInput,
    }
    solver_by_engine = {
        "turbofan": simulate_turbofan_cycle,
        "turboprop": simulate_turboprop_cycle,
        "ramjet": simulate_ramjet_cycle,
        "scramjet": simulate_scramjet_cycle,
    }
    try:
        inputs = schema_by_engine[engine_type].model_validate(payload or {})
        result = solver_by_engine[engine_type](inputs)
    except (CycleCalculationError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    title = f"PropulsionLab {engine_type.title()} Report"
    filename = f"propulsionlab-{engine_type}-report.pdf"
    return Response(
        content=build_turbojet_pdf_report(result, title, inputs.model_dump()),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Python-API export
# ---------------------------------------------------------------------------


_EXPORT_MAP: dict[str, tuple[type[BaseModel], str, str]] = {
    "turbojet": (TurbojetInput, "/simulate/turbojet", "Turbojet"),
    "afterburning_turbojet": (TurbojetInput, "/simulate/turbojet", "Afterburning turbojet"),
    "turbofan": (TurbofanInput, "/simulate/turbofan", "Turbofan"),
    "turboprop": (TurbopropInput, "/simulate/turboprop", "Turboprop"),
    "ramjet": (RamjetInput, "/simulate/ramjet", "Ramjet"),
    "scramjet": (ScramjetInput, "/simulate/scramjet", "Scramjet"),
}


@app.post("/export/python")
def export_python(payload: PythonExportInput) -> Response:
    """Render a runnable, stdlib-only Python API-client script from UI state.

    Inputs are validated against the matching engine schema (normalising
    defaults), so the script POSTs exactly what the UI would and reproduces the
    same numbers.
    """

    schema, endpoint, label = _EXPORT_MAP[payload.engine_type]
    try:
        validated = schema.model_validate(payload.inputs)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    script = generate_python_script(label, endpoint, validated.model_dump())
    filename = f"propulsionlab_{payload.engine_type}.py"
    return Response(
        content=script,
        media_type="text/x-python",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------


@app.get("/presets")
def presets() -> dict[str, Any]:
    """Return all bundled educational engine presets."""

    return load_engine_presets()


@app.get("/maps/compressor")
def compressor_map(
    design_pressure_ratio: float = 12.0,
    design_corrected_mass_flow: float = 50.0,
    design_efficiency: float = 0.86,
) -> dict[str, Any]:
    """Return a compressor map for the map viewer.

    The map is a clearly-labelled *synthetic, parametric* characteristic, not
    manufacturer data (see ``app/engine_core/compressor_maps.py``). Optional
    query parameters size it around a design point so the operating-point marker
    lands sensibly; the returned payload carries ``is_synthetic`` and ``source``.
    """

    try:
        cmap = synthetic_compressor_map(
            design_pressure_ratio=design_pressure_ratio,
            design_corrected_mass_flow=design_corrected_mass_flow,
            design_efficiency=design_efficiency,
        )
    except CycleCalculationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return cmap.to_dict()


@app.post("/simulate/turbojet/from-preset/{preset_name}", response_model=TurbojetOutput)
def simulate_turbojet_from_preset(
    preset_name: str,
    overrides: Annotated[TurbojetOverrideInput | None, Body()] = None,
) -> TurbojetOutput:
    """Simulate a turbojet preset with optional user overrides."""

    preset = find_preset(preset_name)
    if preset.get("engine_family", "turbojet") != "turbojet":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Preset '{preset_name}' is a {preset.get('engine_family')} preset; "
                "use /simulate/{engine_type}/from-preset/{preset_name} instead."
            ),
        )
    default_inputs = dict(preset["default_inputs"])
    if overrides is not None:
        default_inputs.update(overrides.model_dump(exclude_none=True))
    inputs = TurbojetInput.model_validate(default_inputs)
    return run_turbojet_simulation(inputs)


@app.post(
    "/simulate/{engine_type}/from-preset/{preset_name}",
    response_model=AdvancedEngineOutput,
)
def simulate_advanced_from_preset(
    engine_type: AdvancedEngineType,
    preset_name: str,
    overrides: Annotated[dict[str, Any] | None, Body()] = None,
) -> AdvancedEngineOutput:
    """Simulate an advanced-engine preset with optional user overrides."""

    preset = find_preset(preset_name)
    if preset.get("engine_family") != engine_type:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Preset '{preset_name}' is not a {engine_type} preset "
                f"(it is {preset.get('engine_family', preset.get('engine_type', 'unknown'))})."
            ),
        )
    default_inputs = dict(preset["default_inputs"])
    if overrides:
        default_inputs.update(
            {k: v for k, v in overrides.items() if v is not None}
        )
    schema_by_engine = {
        "turbofan": TurbofanInput,
        "turboprop": TurbopropInput,
        "ramjet": RamjetInput,
        "scramjet": ScramjetInput,
    }
    try:
        inputs = schema_by_engine[engine_type].model_validate(default_inputs)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _run_advanced(engine_type, inputs)
