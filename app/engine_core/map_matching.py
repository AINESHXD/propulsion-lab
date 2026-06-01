"""Map-based off-design matching for the educational turbojet (Day 36-37).

The reduced-order off-design solver (:func:`solve_turbojet_off_design`) holds the
turbine and nozzle ratios constant (the choked-turbine result) and derives the
compressor pressure ratio from the matched temperature ratio using a *constant*
compressor efficiency taken from the design inputs. This module replaces that
single fixed efficiency with one read off a compressor **map**, so the operating
point is driven onto the compressor characteristic.

How the operating point converges on the map
---------------------------------------------
The spool work balance fixes the compressor temperature ratio ``tau_c``
independently of efficiency (it is an energy balance). Efficiency enters only
when ``tau_c`` is converted to a pressure ratio ``pi_c`` and hence to the matched
mass flow. So we iterate:

1. with the current efficiency, recover ``pi_c`` and the corrected mass flow
   ``mc`` of the matched point;
2. **invert** the compressor map to find the ``(corrected_speed, beta)`` whose
   characteristic passes through ``(mc, pi_c)`` (a 2-D Newton solve on the map's
   bilinear surfaces);
3. read the map efficiency there and feed it back to step 1.

At the design throttle and flight condition the point sits at the map centre
with the design efficiency, so the residual is zero; off-design it migrates
across the map and the efficiency follows the island, which feeds back into the
matched mass flow and thrust. The turbine map is read at the (choked) turbine
operating point for a consistent turbine efficiency and is reported alongside.

This solver is additive: the constant-ratio :func:`solve_turbojet_off_design`
is unchanged and still backs the off-design endpoints. Map matching is offered
as a higher-fidelity path.
"""

from __future__ import annotations

import math
from typing import Any

from app.engine_core.atmosphere import isa_atmosphere
from app.engine_core.compressor_maps import CompressorMap, synthetic_compressor_map
from app.engine_core.constants import gamma_air, gamma_gas
from app.engine_core.inlet import calculate_freestream_state, calculate_inlet_exit
from app.engine_core.nozzle import calculate_nozzle_exit
from app.engine_core.off_design import (
    TurbojetOffDesignReference,
    _fuel_air_ratio,
    solve_turbojet_off_design,
)
from app.engine_core.performance import compute_turbojet_performance
from app.engine_core.turbine_maps import TurbineMap, synthetic_turbine_map
from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import CycleCalculationError, StationState

_GAMMA_EXP_AIR = (gamma_air - 1.0) / gamma_air
_GAMMA_EXP_GAS = (gamma_gas - 1.0) / gamma_gas
_T_REF = 288.15
_P_REF = 101325.0


def _corrected_mass_flow(mass_flow_kg_s: float, Tt_K: float, Pt_Pa: float) -> float:
    """Corrected mass flow m * sqrt(Tt/Tref) / (Pt/Pref)."""

    return mass_flow_kg_s * math.sqrt(Tt_K / _T_REF) / (Pt_Pa / _P_REF)


def default_maps_for_reference(
    reference: TurbojetOffDesignReference,
) -> tuple[CompressorMap, TurbineMap]:
    """Build synthetic maps sized to the engine's design point.

    The maps are centred on the design operating point so the matched point
    starts on the characteristic. Both are clearly-labelled synthetic maps; a
    measured dataset can be passed to :func:`match_turbojet_on_maps` instead.
    """

    inputs = reference.design_inputs
    design = simulate_turbojet_cycle(inputs)
    stations = design["station_table"]
    Tt2 = float(stations[2]["stagnation_temperature_K"])
    Pt2 = float(stations[2]["stagnation_pressure_Pa"])
    Tt4 = float(stations[4]["stagnation_temperature_K"])
    Pt4 = float(stations[4]["stagnation_pressure_Pa"])
    Pt5 = float(stations[5]["stagnation_pressure_Pa"])
    mass_air = float(design["effective_mass_flow_air_kg_s"])
    far = float(design["core_fuel_air_ratio"])
    mass_gas = mass_air * (1.0 + far)

    mc_compressor = _corrected_mass_flow(mass_air, Tt2, Pt2)
    pi_c = float(inputs.compressor_pressure_ratio)

    compressor_map = synthetic_compressor_map(
        name="synthetic core compressor (design-sized)",
        design_pressure_ratio=pi_c,
        design_corrected_mass_flow=mc_compressor,
        design_efficiency=inputs.compressor_efficiency,
    )

    # Turbine design point: expansion ratio Pt4/Pt5 and corrected flow at station 4.
    expansion_ratio = Pt4 / Pt5
    mc_turbine = _corrected_mass_flow(mass_gas, Tt4, Pt4)
    # Isentropic turbine efficiency implied by the calibrated constant ratios:
    #   eta_t = (1 - tau_t) / (1 - pi_t**((g-1)/g))
    tau_t = reference.turbine_temp_ratio
    pi_t = reference.turbine_pressure_ratio
    eta_t = (1.0 - tau_t) / (1.0 - pi_t**_GAMMA_EXP_GAS)
    eta_t = min(max(eta_t, 0.5), 0.999)

    turbine_map = synthetic_turbine_map(
        name="synthetic HP turbine (design-sized)",
        design_expansion_ratio=expansion_ratio,
        design_corrected_mass_flow=mc_turbine,
        design_efficiency=eta_t,
    )
    return compressor_map, turbine_map


def match_turbojet_on_maps(
    reference: TurbojetOffDesignReference,
    *,
    altitude_m: float,
    mach: float,
    turbine_inlet_temperature_K: float,
    compressor_map: CompressorMap | None = None,
    turbine_map: TurbineMap | None = None,
    max_iterations: int = 50,
    efficiency_tolerance: float = 1e-9,
) -> dict[str, Any]:
    """Match a turbojet operating point on the compressor (and turbine) maps.

    Returns a result dict shaped like :func:`solve_turbojet_off_design` with an
    added ``maps`` block holding the converged map coordinates, surge margin,
    turbine operating point, and convergence diagnostics.
    """

    if compressor_map is None or turbine_map is None:
        compressor_map, turbine_map = default_maps_for_reference(reference)

    inputs = reference.design_inputs

    # The spool work balance (efficiency-independent) gives tau_c; reuse the
    # constant-ratio solver for that and the flight-condition stations.
    base = solve_turbojet_off_design(
        reference,
        altitude_m=altitude_m,
        mach=mach,
        turbine_inlet_temperature_K=turbine_inlet_temperature_K,
    )
    tau_c = float(base["compressor_temp_ratio"])

    atmosphere = isa_atmosphere(altitude_m)
    freestream = calculate_freestream_state(atmosphere, mach)
    inlet = calculate_inlet_exit(freestream.state, inputs.inlet_pressure_recovery)
    Tt2 = inlet.state.stagnation_temperature_K
    Pt2 = inlet.state.stagnation_pressure_Pa

    Tt4 = turbine_inlet_temperature_K
    tau_t = reference.turbine_temp_ratio
    pi_t = reference.turbine_pressure_ratio
    Tt5 = tau_t * Tt4

    Tt3 = Tt2 * tau_c
    far = _fuel_air_ratio(Tt3, Tt4, inputs)

    loss = inputs.combustor_pressure_loss_fraction
    K_t = reference.turbine_flow_constant

    # Efficiency fixed point on the compressor map.
    eta_c = inputs.compressor_efficiency
    inversion = None
    iterations = 0
    eta_residual = 1.0
    pi_c = mass_flow_air = mc_compressor = Pt4 = 0.0
    for iterations in range(1, max_iterations + 1):
        pi_c = (1.0 + eta_c * (tau_c - 1.0)) ** (1.0 / _GAMMA_EXP_AIR)
        Pt3 = pi_c * Pt2
        Pt4 = Pt3 * (1.0 - loss)
        mass_flow_gas = K_t * Pt4 / math.sqrt(Tt4)
        mass_flow_air = mass_flow_gas / (1.0 + far)
        mc_compressor = _corrected_mass_flow(mass_flow_air, Tt2, Pt2)
        inversion = compressor_map.invert(mc_compressor, pi_c)
        eta_map = compressor_map.lookup(inversion.corrected_speed, inversion.beta).efficiency
        eta_residual = abs(eta_map - eta_c)
        if eta_residual < efficiency_tolerance:
            eta_c = eta_map
            break
        eta_c = eta_map

    if mass_flow_air <= 0.0:
        raise CycleCalculationError("Map-matched mass flow is non-positive.")

    Pt5 = pi_t * Pt4
    if Pt5 <= atmosphere.pressure_Pa:
        raise CycleCalculationError(
            "Map-matched turbine-exit pressure has fallen to ambient - the exhaust "
            "nozzle would unchoke and the constant-ratio assumption no longer holds."
        )

    # Recover the exhaust + performance at the converged (map) efficiency.
    turbine_exit_state = StationState(
        station=5,
        name="Turbine exit / nozzle inlet (map-matched)",
        stagnation_temperature_K=Tt5,
        stagnation_pressure_Pa=Pt5,
        notes=["Map-matched off-design state (choked turbine, map compressor)."],
    )
    nozzle = calculate_nozzle_exit(
        turbine_exit_state,
        atmosphere.pressure_Pa,
        mass_flow_air,
        far,
        inputs.nozzle_efficiency,
        None,
        inputs.include_pressure_thrust,
        None,
    )
    performance, performance_warnings = compute_turbojet_performance(
        mass_flow_air_kg_s=mass_flow_air,
        fuel_air_ratio=far,
        fuel_heating_value_J_kg=inputs.fuel_heating_value_J_kg,
        freestream_velocity_m_s=freestream.state.velocity_m_s or 0.0,
        exit_velocity_m_s=float(nozzle.metadata["exit_velocity_m_s"]),
        pressure_thrust_N=float(nozzle.metadata["pressure_thrust_N"]),
    )

    # Compressor operating point on the map.
    comp_point = compressor_map.lookup(inversion.corrected_speed, inversion.beta)
    surge_margin = compressor_map.surge_margin(inversion.corrected_speed, inversion.beta)

    # Turbine operating point (choked): expansion ratio Pt4/Pt5 and corrected
    # flow at station 4. Under the constant-ratio assumption these are nearly
    # fixed, so the turbine map efficiency is essentially the design value.
    mass_flow_gas = mass_flow_air * (1.0 + far)
    expansion_ratio = Pt4 / Pt5
    mc_turbine = _corrected_mass_flow(mass_flow_gas, Tt4, Pt4)
    turbine_inversion = turbine_map.invert(mc_turbine, expansion_ratio)
    turbine_point = turbine_map.lookup(
        turbine_inversion.corrected_speed, turbine_inversion.beta
    )

    converged = (
        eta_residual < 1e-6
        and inversion.in_range
        and bool(base["off_design"]["converged"])
    )

    warnings = list(performance_warnings)
    if not inversion.in_range:
        warnings.append(
            "CAUTION: matched operating point lies outside the compressor map; "
            "the map efficiency is clamped to the map edge."
        )

    return {
        **performance,
        "engine_variant": "turbojet",
        "altitude_m": altitude_m,
        "mach": mach,
        "turbine_inlet_temperature_K": Tt4,
        "effective_mass_flow_air_kg_s": mass_flow_air,
        "compressor_pressure_ratio": pi_c,
        "compressor_temp_ratio": tau_c,
        "compressor_efficiency_map": eta_c,
        "nozzle_choked": bool(nozzle.metadata["nozzle_choked"]),
        "nozzle_exit_pressure_Pa": float(nozzle.metadata["nozzle_exit_pressure_Pa"]),
        "ambient_pressure_Pa": atmosphere.pressure_Pa,
        "exit_velocity_m_s": float(nozzle.metadata["exit_velocity_m_s"]),
        "freestream_velocity_m_s": freestream.state.velocity_m_s or 0.0,
        "maps": {
            "converged": converged,
            "iterations": iterations,
            "efficiency_residual": eta_residual,
            "compressor": {
                "corrected_speed": inversion.corrected_speed,
                "beta": inversion.beta,
                "corrected_mass_flow": mc_compressor,
                "pressure_ratio": pi_c,
                "efficiency": comp_point.efficiency,
                "surge_margin": surge_margin,
                "inverse_residual": inversion.residual,
                "in_range": inversion.in_range,
            },
            "turbine": {
                "corrected_speed": turbine_inversion.corrected_speed,
                "beta": turbine_inversion.beta,
                "corrected_mass_flow": mc_turbine,
                "expansion_ratio": expansion_ratio,
                "efficiency": turbine_point.efficiency,
                "inverse_residual": turbine_inversion.residual,
                "in_range": turbine_inversion.in_range,
            },
            "synthetic_maps": compressor_map.is_synthetic and turbine_map.is_synthetic,
        },
        "warnings": warnings,
    }
