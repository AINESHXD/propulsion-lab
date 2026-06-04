"""On-map running-line matching for the two-spool separate-flow turbofan.

The turbojet matcher (:mod:`app.engine_core.map_matching`) drives a single
compressor onto its characteristic. A turbofan has two spools, so this extends
the idea to a **fan** map and a **core-compressor (HPC)** map at once.

How it works
------------
The constant-ratio off-design solver (:func:`solve_turbofan_off_design`) already
finds the matched operating point: it balances both spools and the two choked
turbines, returning the fan and HPC temperature ratios, pressure ratios and the
core/total mass flows. This module then projects that matched point onto the two
compressor maps:

* the **fan** sees the *total* airflow at the inlet state (station 2), so its
  corrected flow and pressure ratio give a point on the fan map;
* the **HPC** sees the *core* airflow at the fan-exit state (station 13), giving
  a point on the HPC map.

For each map we read the local efficiency and, more usefully, the **surge
margin**, and we report whether the point is inside the mapped region. Sweeping
the throttle traces a running line across both maps, with the fan and HPC moving
together.

Honest limitations
------------------
* The running line is the constant-ratio match *projected* onto the maps; the
  map efficiencies are read at the matched point rather than iterated back into
  the mass flow (the turbojet matcher does that single-spool feedback; the
  two-spool feedback is the natural next step).
* The **bypass ratio is held at the design value** by the underlying solver, so
  the fan does not yet shift the flow split via its own map.
* The maps are clearly-labelled *synthetic* characteristics sized to the design
  point, not measured data.
"""

from __future__ import annotations

from typing import Any

from app.engine_core.atmosphere import isa_atmosphere
from app.engine_core.compressor_maps import CompressorMap, synthetic_compressor_map
from app.engine_core.inlet import calculate_freestream_state, calculate_inlet_exit
from app.engine_core.map_matching import _corrected_mass_flow
from app.engine_core.off_design import (
    TurbofanOffDesignReference,
    solve_turbofan_off_design,
)
from app.engine_core.turbofan import simulate_turbofan_cycle
from app.engine_core.types import CycleCalculationError


def default_maps_for_turbofan(
    reference: TurbofanOffDesignReference,
) -> tuple[CompressorMap, CompressorMap]:
    """Build synthetic fan and HPC maps sized to the turbofan design point."""

    inputs = reference.design_inputs
    design = simulate_turbofan_cycle(inputs)
    stations = design["station_table"]
    Tt2 = float(stations[2]["stagnation_temperature_K"])
    Pt2 = float(stations[2]["stagnation_pressure_Pa"])
    Tt13 = float(stations[13]["stagnation_temperature_K"])
    Pt13 = float(stations[13]["stagnation_pressure_Pa"])

    core_air = float(design["extra"]["core_mass_flow_kg_s"])
    total_air = core_air * (1.0 + inputs.bypass_ratio)

    mc_fan = _corrected_mass_flow(total_air, Tt2, Pt2)
    mc_hpc = _corrected_mass_flow(core_air, Tt13, Pt13)

    fan_map = synthetic_compressor_map(
        name="synthetic fan (design-sized)",
        design_pressure_ratio=float(inputs.fan_pressure_ratio),
        design_corrected_mass_flow=mc_fan,
        design_efficiency=float(inputs.fan_efficiency),
    )
    hpc_map = synthetic_compressor_map(
        name="synthetic core compressor / HPC (design-sized)",
        design_pressure_ratio=float(inputs.core_compressor_pressure_ratio),
        design_corrected_mass_flow=mc_hpc,
        design_efficiency=float(inputs.compressor_efficiency),
    )
    return fan_map, hpc_map


def _project_onto_map(cmap: CompressorMap, mc: float, pi: float) -> dict[str, Any]:
    """Invert a compressor map at (corrected flow, pressure ratio) and read it."""

    inv = cmap.invert(mc, pi)
    point = cmap.lookup(inv.corrected_speed, inv.beta)
    return {
        "corrected_speed": inv.corrected_speed,
        "beta": inv.beta,
        "corrected_mass_flow": mc,
        "pressure_ratio": pi,
        "efficiency": point.efficiency,
        "surge_margin": cmap.surge_margin(inv.corrected_speed, inv.beta),
        "inverse_residual": inv.residual,
        "in_range": inv.in_range,
    }


def match_turbofan_on_maps(
    reference: TurbofanOffDesignReference,
    *,
    altitude_m: float,
    mach: float,
    turbine_inlet_temperature_K: float,
    fan_map: CompressorMap | None = None,
    hpc_map: CompressorMap | None = None,
) -> dict[str, Any]:
    """Match a turbofan operating point and project it onto the fan + HPC maps."""

    if fan_map is None or hpc_map is None:
        fan_map, hpc_map = default_maps_for_turbofan(reference)

    inputs = reference.design_inputs
    base = solve_turbofan_off_design(
        reference,
        altitude_m=altitude_m,
        mach=mach,
        turbine_inlet_temperature_K=turbine_inlet_temperature_K,
    )

    pi_f = float(base["fan_pressure_ratio"])
    pi_cH = float(base["core_compressor_pressure_ratio"])
    tau_f = float(base["off_design"]["fan_temp_ratio"])
    total_air = float(base["effective_mass_flow_air_kg_s"])
    core_air = float(base["core_mass_flow_kg_s"])

    atmosphere = isa_atmosphere(altitude_m)
    freestream = calculate_freestream_state(atmosphere, mach)
    inlet = calculate_inlet_exit(freestream.state, inputs.inlet_pressure_recovery)
    Tt2 = inlet.state.stagnation_temperature_K
    Pt2 = inlet.state.stagnation_pressure_Pa
    Tt13 = Tt2 * tau_f
    Pt13 = pi_f * Pt2

    if core_air <= 0.0 or total_air <= 0.0:
        raise CycleCalculationError("Map-matched turbofan mass flow is non-positive.")

    mc_fan = _corrected_mass_flow(total_air, Tt2, Pt2)
    mc_hpc = _corrected_mass_flow(core_air, Tt13, Pt13)

    fan_point = _project_onto_map(fan_map, mc_fan, pi_f)
    hpc_point = _project_onto_map(hpc_map, mc_hpc, pi_cH)

    warnings = list(base.get("warnings", []))
    for label, pt in (("fan", fan_point), ("HPC", hpc_point)):
        if not pt["in_range"]:
            warnings.append(
                f"CAUTION: matched {label} point lies outside its map; "
                "efficiency is clamped to the map edge."
            )
        if pt["surge_margin"] is not None and pt["surge_margin"] < 0.10:
            warnings.append(
                f"CAUTION: {label} surge margin is low "
                f"({pt['surge_margin'] * 100:.0f}%) at this throttle."
            )

    converged = (
        bool(base["off_design"]["converged"])
        and fan_point["in_range"]
        and hpc_point["in_range"]
    )

    return {
        **base,
        "maps": {
            "converged": converged,
            "fan": fan_point,
            "compressor": hpc_point,
            "synthetic_maps": fan_map.is_synthetic and hpc_map.is_synthetic,
        },
        "warnings": warnings,
    }
