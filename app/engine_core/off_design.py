"""Off-design matching solver for the educational turbojet.

The design-point solver (:func:`simulate_turbojet_cycle`) *specifies* the
compressor pressure ratio, turbine inlet temperature, and mass flow and then
computes one operating point. A real fixed-geometry engine does the opposite:
you set a throttle (here, the turbine inlet temperature Tt4) and a flight
condition, and the engine *finds* the operating point where the spool work
balances and mass flow is continuous through every choked station.

Reduced-order matching model
----------------------------
For a fixed-geometry turbojet with a **choked HP-turbine nozzle and a choked
exhaust nozzle**, two classic results hold (Mattingly, *Elements of Gas
Turbine Propulsion*, ch. 5):

* the turbine **temperature ratio** ``tau_t = Tt5 / Tt4`` is constant, and
* the turbine **pressure ratio** ``pi_t = Pt5 / Pt4`` is constant,

independent of the operating point — they are set by the (fixed) turbine and
nozzle throat areas. We calibrate both, plus the turbine corrected-flow
constant ``K_t = m_dot * sqrt(Tt4) / Pt4`` and the nozzle corrected-flow
constant ``K_n = m_dot * sqrt(Tt5) / Pt5``, from a single design-point run.

Off-design, given a throttle ``Tt4`` and flight condition we solve the spool
work balance for the compressor temperature ratio ``tau_c`` by Newton-Raphson
with a bisection safeguard (the residual is smooth and monotonic, so this
converges in a handful of iterations), then recover the pressure ratio, mass
flow, and exhaust state.

Two matching constraints are checked explicitly and reported as **relative
residuals** in the result:

* **Compressor↔turbine work matching** — the converged spool-work residual
  ``|W_c - W_t| / W_c`` (Day 9), driven below ``1e-6``.
* **Mass-flow continuity through the choked nozzle** — the matched mass flow
  must satisfy the *same* fixed-area choked-nozzle corrected-flow constant
  ``K_n`` as the design point; the residual ``|K_n - K_n,design| / K_n,design``
  (Day 10) is ~0 by construction, confirming the choked-turbine + choked-nozzle
  matching conserves continuity.

Honest limitations
------------------
* No compressor/turbine **maps** — the constant-``tau_t``/``pi_t`` result is the
  reduced-order stand-in. Surge margin and corrected-speed effects are not
  modelled. Real maps slot in later behind the same interface.
* Assumes the exhaust nozzle stays choked. If the matched ``Pt5`` falls to or
  below ambient (very low throttle / very high altitude) the model says so and
  refuses rather than returning a non-physical point.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.engine_core.atmosphere import isa_atmosphere
from app.engine_core.constants import cp_air, cp_gas, gamma_air, gamma_gas
from app.engine_core.inlet import calculate_freestream_state, calculate_inlet_exit
from app.engine_core.nozzle import calculate_nozzle_exit
from app.engine_core.performance import compute_turbojet_performance
from app.engine_core.streams import compute_stream_efficiencies, expand_nozzle_stream
from app.engine_core.turbofan import TurbofanCycleInputs, simulate_turbofan_cycle
from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import (
    CycleCalculationError,
    StationState,
    TurbojetCycleInputs,
)

_GAMMA_EXP = (gamma_air - 1.0) / gamma_air


@dataclass(slots=True, frozen=True)
class TurbojetOffDesignReference:
    """Calibration constants captured from a single design-point run."""

    design_inputs: TurbojetCycleInputs
    turbine_temp_ratio: float        # tau_t = Tt5 / Tt4  (constant, choked)
    turbine_pressure_ratio: float    # pi_t  = Pt5 / Pt4  (constant, choked)
    turbine_flow_constant: float     # K_t = m_dot * sqrt(Tt4) / Pt4  (choked HPT)
    nozzle_flow_constant: float      # K_n = m_dot * sqrt(Tt5) / Pt5  (choked nozzle)
    design_tt4_K: float
    design_mass_flow_kg_s: float


def calibrate_turbojet_reference(
    design_inputs: TurbojetCycleInputs,
) -> TurbojetOffDesignReference:
    """Run the design point once and extract the off-design matching constants."""

    if design_inputs.engine_variant != "turbojet":
        raise CycleCalculationError(
            "Off-design matching currently supports the dry turbojet only."
        )
    result = simulate_turbojet_cycle(design_inputs)
    stations = result["station_table"]
    Tt4 = float(stations[4]["stagnation_temperature_K"])
    Pt4 = float(stations[4]["stagnation_pressure_Pa"])
    Tt5 = float(stations[5]["stagnation_temperature_K"])
    Pt5 = float(stations[5]["stagnation_pressure_Pa"])
    mass_flow_air = float(result["effective_mass_flow_air_kg_s"])
    far = float(result["core_fuel_air_ratio"])
    mass_flow_turbine = mass_flow_air * (1.0 + far)

    return TurbojetOffDesignReference(
        design_inputs=design_inputs,
        turbine_temp_ratio=Tt5 / Tt4,
        turbine_pressure_ratio=Pt5 / Pt4,
        turbine_flow_constant=mass_flow_turbine * math.sqrt(Tt4) / Pt4,
        nozzle_flow_constant=mass_flow_turbine * math.sqrt(Tt5) / Pt5,
        design_tt4_K=Tt4,
        design_mass_flow_kg_s=mass_flow_air,
    )


def _fuel_air_ratio(Tt3_K: float, Tt4_K: float, inputs: TurbojetCycleInputs) -> float:
    """Constant-cp combustor fuel-air ratio (matches calculate_combustor_exit)."""

    numerator = cp_gas * Tt4_K - cp_air * Tt3_K
    denominator = (
        inputs.combustor_efficiency * inputs.fuel_heating_value_J_kg - cp_gas * Tt4_K
    )
    if denominator <= 0.0:
        raise CycleCalculationError(
            "Combustor energy balance impossible at this Tt4 (heat release too low)."
        )
    return numerator / denominator


def solve_turbojet_off_design(
    reference: TurbojetOffDesignReference,
    *,
    altitude_m: float,
    mach: float,
    turbine_inlet_temperature_K: float,
    max_iterations: int = 60,
    work_tolerance: float = 1e-12,
) -> dict[str, Any]:
    """Solve the matched off-design operating point for a fixed-geometry turbojet.

    ``turbine_inlet_temperature_K`` is the throttle setting. Returns the same
    shape of result dict as the design-point solver, plus an ``off_design``
    block with the solver diagnostics.
    """

    inputs = reference.design_inputs
    atmosphere = isa_atmosphere(altitude_m)
    freestream = calculate_freestream_state(atmosphere, mach)
    inlet = calculate_inlet_exit(freestream.state, inputs.inlet_pressure_recovery)
    Tt2 = inlet.state.stagnation_temperature_K
    Pt2 = inlet.state.stagnation_pressure_Pa

    Tt4 = turbine_inlet_temperature_K
    tau_t = reference.turbine_temp_ratio
    Tt5 = tau_t * Tt4

    # Spool work-balance residual in the compressor temperature ratio tau_c:
    #   cp_air * Tt2 * (tau_c - 1)  ==  (1 + f) * cp_gas * (Tt4 - Tt5) * eta_m
    # with f = f(Tt3 = Tt2 * tau_c, Tt4). LHS rises with tau_c, RHS falls
    # slightly (f drops), so the residual is monotonic -> Newton-Raphson.
    def compressor_specific_work(tau_c: float) -> float:
        return cp_air * Tt2 * (tau_c - 1.0)

    def residual(tau_c: float) -> float:
        Tt3 = Tt2 * tau_c
        far = _fuel_air_ratio(Tt3, Tt4, inputs)
        turbine_work = (
            (1.0 + far) * cp_gas * (Tt4 - Tt5) * inputs.mechanical_efficiency
        )
        return compressor_specific_work(tau_c) - turbine_work

    # Bracket: tau_c in (1, Tt4/Tt2) — the upper bound keeps Tt3 < Tt4.
    lo, hi = 1.0 + 1e-6, Tt4 / Tt2 - 1e-6
    if hi <= lo:
        raise CycleCalculationError(
            "Throttle Tt4 is not above the inlet stagnation temperature."
        )
    if residual(lo) > 0.0:
        raise CycleCalculationError(
            "Throttle is too low to sustain the compressor at this condition."
        )

    # Newton-Raphson (finite-difference derivative) with a bisection safeguard:
    # if a Newton step leaves the bracket, fall back to the bracket midpoint.
    # The residual is smooth and monotonic, so this converges in a handful of
    # iterations. Convergence is judged on the *relative* spool-work residual
    # |W_c - W_t| / W_c (dimensionless), so the gate is independent of the
    # ~1e5 J/kg absolute work scale.
    tau_c = 0.5 * (lo + hi)
    iterations = 0
    work_residual_relative = 1.0
    for iterations in range(1, max_iterations + 1):
        r = residual(tau_c)
        if r < 0.0:
            lo = tau_c
        else:
            hi = tau_c
        comp_work = compressor_specific_work(tau_c)
        work_residual_relative = abs(r) / comp_work if comp_work > 0.0 else abs(r)
        if work_residual_relative < work_tolerance:
            break
        h = 1e-7 * tau_c
        slope = (residual(tau_c + h) - r) / h
        step = r / slope if slope != 0.0 else 0.0
        next_tau = tau_c - step
        if not (lo < next_tau < hi):
            next_tau = 0.5 * (lo + hi)
        tau_c = next_tau
    work_residual = residual(tau_c)
    comp_work = compressor_specific_work(tau_c)
    work_residual_relative = abs(work_residual) / comp_work if comp_work > 0.0 else abs(work_residual)

    # Recover the operating point from the matched tau_c.
    Tt3 = Tt2 * tau_c
    far = _fuel_air_ratio(Tt3, Tt4, inputs)
    # pi_c from tau_c and the compressor isentropic efficiency:
    #   tau_c = 1 + (pi_c**x - 1) / eta_c   ->   pi_c = (1 + eta_c (tau_c-1))**(1/x)
    pi_c = (1.0 + inputs.compressor_efficiency * (tau_c - 1.0)) ** (1.0 / _GAMMA_EXP)
    Pt3 = pi_c * Pt2
    Pt4 = Pt3 * (1.0 - inputs.combustor_pressure_loss_fraction)
    Pt5 = reference.turbine_pressure_ratio * Pt4

    # Mass flow from the choked-turbine corrected-flow constant.
    mass_flow_turbine = reference.turbine_flow_constant * Pt4 / math.sqrt(Tt4)
    mass_flow_air = mass_flow_turbine / (1.0 + far)
    if mass_flow_air <= 0.0:
        raise CycleCalculationError("Matched mass flow is non-positive.")

    # Day 10 — mass-flow continuity through the choked exhaust nozzle. The
    # nozzle throat area is fixed and the nozzle stays choked, so its
    # corrected-flow constant K_n = m_dot * sqrt(Tt5) / Pt5 must equal the
    # design-point value. With Tt5 = tau_t*Tt4 and Pt5 = pi_t*Pt4 both held
    # constant, this is satisfied identically — the residual confirms the
    # choked-turbine and choked-nozzle continuity statements agree.
    nozzle_flow_constant = mass_flow_turbine * math.sqrt(Tt5) / Pt5
    mass_residual_relative = abs(
        nozzle_flow_constant - reference.nozzle_flow_constant
    ) / reference.nozzle_flow_constant

    if Pt5 <= atmosphere.pressure_Pa:
        raise CycleCalculationError(
            "Matched turbine-exit pressure has fallen to ambient — the exhaust "
            "nozzle would unchoke and the constant-pressure-ratio off-design "
            "assumption no longer holds. Raise the throttle or lower the altitude."
        )

    turbine_exit_state = StationState(
        station=5,
        name="Turbine exit / nozzle inlet (off-design)",
        stagnation_temperature_K=Tt5,
        stagnation_pressure_Pa=Pt5,
        notes=["Off-design matched state (choked turbine, constant pi_t)."],
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

    # Day 9/10 acceptance: both matching constraints below 1e-6 (relative).
    converged = work_residual_relative < 1e-6 and mass_residual_relative < 1e-6

    return {
        **performance,
        "engine_variant": "turbojet",
        "altitude_m": altitude_m,
        "mach": mach,
        "turbine_inlet_temperature_K": Tt4,
        "effective_mass_flow_air_kg_s": mass_flow_air,
        "compressor_pressure_ratio": pi_c,
        "compressor_temp_ratio": tau_c,
        "nozzle_choked": bool(nozzle.metadata["nozzle_choked"]),
        "nozzle_exit_pressure_Pa": float(nozzle.metadata["nozzle_exit_pressure_Pa"]),
        "ambient_pressure_Pa": atmosphere.pressure_Pa,
        "exit_velocity_m_s": float(nozzle.metadata["exit_velocity_m_s"]),
        "freestream_velocity_m_s": freestream.state.velocity_m_s or 0.0,
        "off_design": {
            "converged": converged,
            "iterations": iterations,
            "work_residual": work_residual,
            "work_residual_relative": work_residual_relative,
            "mass_residual_relative": mass_residual_relative,
            "turbine_temp_ratio": tau_t,
            "turbine_pressure_ratio": reference.turbine_pressure_ratio,
        },
        "warnings": performance_warnings,
    }


# ===========================================================================
# Two-spool turbofan off-design (Day 11)
# ===========================================================================
#
# A fixed-geometry two-spool turbofan has *two* coupled work balances:
#
#   HP spool:  HPC work  =  HPT work
#   LP spool:  fan work (core + bypass)  =  LPT work
#
# With a choked HP-turbine nozzle and a choked LP turbine/exhaust, both turbine
# temperature ratios (tau_tH = Tt45/Tt4, tau_tL = Tt5/Tt45) and pressure ratios
# (pi_tH, pi_tL) are constant, calibrated once at the design point. Off-design,
# given a throttle Tt4 and flight condition, we solve the two balances
# simultaneously for the fan and HPC temperature ratios (tau_f, tau_cH).
#
# Because both turbine drops are fixed multiples of Tt4, each balance gives one
# unknown explicitly as a function of the fuel-air ratio f; f in turn depends on
# the HPC-exit temperature Tt3 = Tt2·tau_f·tau_cH. The system therefore reduces
# to a single fixed-point iteration on f, which contracts in a few steps. The
# bypass ratio is held at its design value — a real BPR shift needs a fan map
# and a bypass-nozzle flow function, which this reduced-order model does not have.


@dataclass(slots=True, frozen=True)
class TurbofanOffDesignReference:
    """Calibration constants for two-spool turbofan off-design matching."""

    design_inputs: TurbofanCycleInputs
    hpt_temp_ratio: float        # tau_tH = Tt45 / Tt4   (constant, choked HPT)
    hpt_pressure_ratio: float    # pi_tH  = Pt45 / Pt4
    lpt_temp_ratio: float        # tau_tL = Tt5 / Tt45   (constant, choked LPT)
    lpt_pressure_ratio: float    # pi_tL  = Pt5 / Pt45
    hpt_flow_constant: float     # K_H = m_HPT * sqrt(Tt4) / Pt4
    bypass_ratio: float          # held at the design value off-design
    design_tt4_K: float


def calibrate_turbofan_reference(
    design_inputs: TurbofanCycleInputs,
) -> TurbofanOffDesignReference:
    """Run the design turbofan once and extract the matching constants.

    Restricted to the separate-flow, dry, no-bleed configuration — the regime
    in which the constant-ratio choked-turbine result is clean. The solver
    raises for mixed-flow / afterburning / bled designs rather than returning a
    point outside the model's stated assumptions.
    """

    if getattr(design_inputs, "nozzle_configuration", "separate") != "separate":
        raise CycleCalculationError(
            "Turbofan off-design matching currently supports separate-flow only."
        )
    if getattr(design_inputs, "use_afterburner", False):
        raise CycleCalculationError(
            "Turbofan off-design matching does not support the afterburner."
        )
    if (
        getattr(design_inputs, "bleed_fraction_hpc_exit", 0.0) > 0.0
        or getattr(design_inputs, "cooling_fraction_hpt_inlet", 0.0) > 0.0
    ):
        raise CycleCalculationError(
            "Turbofan off-design matching does not support bleed/cooling air yet."
        )
    if (
        getattr(design_inputs, "third_stream", False)
        and getattr(design_inputs, "variable_cycle_mode", "high_efficiency") == "high_efficiency"
        and getattr(design_inputs, "third_stream_ratio", 0.0) > 0.0
    ):
        raise CycleCalculationError(
            "Turbofan off-design matching does not support the variable-cycle third stream yet."
        )

    result = simulate_turbofan_cycle(design_inputs)
    stations = result["station_table"]
    Tt4 = float(stations[4]["stagnation_temperature_K"])
    Pt4 = float(stations[4]["stagnation_pressure_Pa"])
    Tt45 = float(stations[45]["stagnation_temperature_K"])
    Pt45 = float(stations[45]["stagnation_pressure_Pa"])
    Tt5 = float(stations[5]["stagnation_temperature_K"])
    Pt5 = float(stations[5]["stagnation_pressure_Pa"])

    far = float(result["fuel_air_ratio"])
    core_air = float(result["extra"]["core_mass_flow_kg_s"])
    mass_flow_hpt = core_air * (1.0 + far)

    return TurbofanOffDesignReference(
        design_inputs=design_inputs,
        hpt_temp_ratio=Tt45 / Tt4,
        hpt_pressure_ratio=Pt45 / Pt4,
        lpt_temp_ratio=Tt5 / Tt45,
        lpt_pressure_ratio=Pt5 / Pt45,
        hpt_flow_constant=mass_flow_hpt * math.sqrt(Tt4) / Pt4,
        bypass_ratio=design_inputs.bypass_ratio,
        design_tt4_K=Tt4,
    )


def solve_turbofan_off_design(
    reference: TurbofanOffDesignReference,
    *,
    altitude_m: float,
    mach: float,
    turbine_inlet_temperature_K: float,
    max_iterations: int = 60,
    far_tolerance: float = 1e-12,
) -> dict[str, Any]:
    """Solve the matched two-spool turbofan operating point (separate flow).

    ``turbine_inlet_temperature_K`` is the throttle. Returns a turbofan-shaped
    result dict plus an ``off_design`` block with both spool work residuals and
    the solver diagnostics.
    """

    inputs = reference.design_inputs
    bpr = reference.bypass_ratio
    eta_m = inputs.mechanical_efficiency
    x_air = _GAMMA_EXP

    atmosphere = isa_atmosphere(altitude_m)
    freestream = calculate_freestream_state(atmosphere, mach)
    inlet = calculate_inlet_exit(freestream.state, inputs.inlet_pressure_recovery)
    Tt2 = inlet.state.stagnation_temperature_K
    Pt2 = inlet.state.stagnation_pressure_Pa
    V0 = freestream.state.velocity_m_s or 0.0

    Tt4 = turbine_inlet_temperature_K
    tau_tH = reference.hpt_temp_ratio
    tau_tL = reference.lpt_temp_ratio
    Tt45 = tau_tH * Tt4
    Tt5 = tau_tL * Tt45

    if Tt4 <= Tt2:
        raise CycleCalculationError(
            "Throttle Tt4 is not above the inlet stagnation temperature."
        )

    # Fixed turbine work per unit core-air, divided by (1+f) — constants given Tt4.
    hpt_work_over_gas = cp_gas * (Tt4 - Tt45) * eta_m          # = HPC work / (1+f)
    lpt_work_over_gas = cp_gas * (Tt45 - Tt5) * eta_m          # = fan work / (1+f)

    # Fixed-point on the fuel-air ratio f. Each spool balance gives one ratio:
    #   LP:  cp_air*Tt2*(tau_f-1)*(1+BPR) = (1+f)*lpt_work_over_gas
    #   HP:  cp_air*(Tt2*tau_f)*(tau_cH-1) = (1+f)*hpt_work_over_gas
    # then f = f(Tt3 = Tt2*tau_f*tau_cH, Tt4).
    far = 0.02
    tau_f = tau_cH = 1.0
    iterations = 0
    far_residual = 1.0
    for iterations in range(1, max_iterations + 1):
        tau_f = 1.0 + (1.0 + far) * lpt_work_over_gas / (
            cp_air * Tt2 * (1.0 + bpr)
        )
        tau_cH = 1.0 + (1.0 + far) * hpt_work_over_gas / (cp_air * Tt2 * tau_f)
        Tt3 = Tt2 * tau_f * tau_cH
        far_new = _fuel_air_ratio(Tt3, Tt4, inputs)
        far_residual = abs(far_new - far)
        far = far_new
        if far_residual < far_tolerance:
            break

    if far <= 0.0:
        raise CycleCalculationError(
            "Throttle too low to sustain combustion at this condition."
        )

    # Recover pressures from the matched temperature ratios.
    pi_f = (1.0 + inputs.fan_efficiency * (tau_f - 1.0)) ** (1.0 / x_air)
    pi_cH = (1.0 + inputs.compressor_efficiency * (tau_cH - 1.0)) ** (1.0 / x_air)
    Pt13 = pi_f * Pt2
    Pt3 = pi_cH * Pt13
    Pt4 = Pt3 * (1.0 - inputs.combustor_pressure_loss_fraction)
    Pt45 = reference.hpt_pressure_ratio * Pt4
    Pt5 = reference.lpt_pressure_ratio * Pt45

    # Mass flow from the choked-HPT corrected-flow constant.
    mass_flow_hpt = reference.hpt_flow_constant * Pt4 / math.sqrt(Tt4)
    core_air = mass_flow_hpt / (1.0 + far)
    bypass_air = bpr * core_air
    total_air = core_air + bypass_air
    if core_air <= 0.0:
        raise CycleCalculationError("Matched core mass flow is non-positive.")

    if Pt5 <= atmosphere.pressure_Pa or Pt13 <= atmosphere.pressure_Pa:
        raise CycleCalculationError(
            "Matched nozzle-inlet pressure has fallen to ambient — a nozzle would "
            "unchoke and the constant-ratio off-design assumption no longer holds."
        )

    # Spool-work residuals (relative) — both are satisfied by construction; we
    # report them to confirm the simultaneous match closed.
    hpc_work = cp_air * Tt2 * tau_f * (tau_cH - 1.0)
    fan_work = cp_air * Tt2 * (tau_f - 1.0) * (1.0 + bpr)
    hp_residual_rel = abs(hpc_work - (1.0 + far) * hpt_work_over_gas) / hpc_work
    lp_residual_rel = abs(fan_work - (1.0 + far) * lpt_work_over_gas) / fan_work

    # Exhaust streams (separate flow): core nozzle from station 5, bypass from fan.
    core_inlet = StationState(
        station=5, name="LP turbine exit (off-design)",
        stagnation_temperature_K=Tt5, stagnation_pressure_Pa=Pt5,
        notes=["Off-design matched core state (choked turbines, constant ratios)."],
    )
    fan_state = StationState(
        station=13, name="Fan exit (off-design)",
        stagnation_temperature_K=Tt2 * tau_f, stagnation_pressure_Pa=Pt13,
        notes=["Off-design matched fan exit."],
    )
    core_nozzle = expand_nozzle_stream(
        core_inlet, atmosphere.pressure_Pa, core_air, far, V0,
        inputs.core_nozzle_efficiency, 9, "Core nozzle exit", gamma_gas, cp_gas,
    )
    bypass_nozzle = expand_nozzle_stream(
        fan_state, atmosphere.pressure_Pa, bypass_air, 0.0, V0,
        inputs.bypass_nozzle_efficiency, 19, "Bypass nozzle exit", gamma_air, cp_air,
    )

    momentum_thrust_N = core_nozzle.momentum_thrust_N + bypass_nozzle.momentum_thrust_N
    pressure_thrust_N = core_nozzle.pressure_thrust_N + bypass_nozzle.pressure_thrust_N
    thrust_N = momentum_thrust_N + pressure_thrust_N
    if thrust_N <= 0.0:
        raise CycleCalculationError("Matched turbofan produced non-positive thrust.")
    core_thrust_N = core_nozzle.momentum_thrust_N + core_nozzle.pressure_thrust_N
    bypass_thrust_N = bypass_nozzle.momentum_thrust_N + bypass_nozzle.pressure_thrust_N

    fuel_flow_kg_s = far * core_air
    jet_kinetic_power_change_W = 0.5 * (
        core_air * (1.0 + far) * core_nozzle.exit_velocity_m_s**2
        + bypass_air * bypass_nozzle.exit_velocity_m_s**2
        - total_air * V0**2
    )
    pressure_power_W = pressure_thrust_N * V0
    efficiencies = compute_stream_efficiencies(
        thrust_N=thrust_N,
        freestream_velocity_m_s=V0,
        fuel_flow_kg_s=fuel_flow_kg_s,
        fuel_heating_value_J_kg=inputs.fuel_heating_value_J_kg,
        jet_kinetic_power_change_W=jet_kinetic_power_change_W,
        pressure_thrust_power_W=pressure_power_W,
    )

    converged = (
        far_residual < 1e-6 and hp_residual_rel < 1e-6 and lp_residual_rel < 1e-6
    )

    return {
        **efficiencies,
        "engine_type": "turbofan",
        "altitude_m": altitude_m,
        "mach": mach,
        "turbine_inlet_temperature_K": Tt4,
        "thrust_N": thrust_N,
        "thrust_kN": thrust_N / 1000.0,
        "core_thrust_N": core_thrust_N,
        "bypass_thrust_N": bypass_thrust_N,
        "specific_thrust_N_per_kg_s": thrust_N / total_air,
        "fuel_air_ratio": far,
        "fuel_flow_kg_s": fuel_flow_kg_s,
        "TSFC_kg_per_kN_hr": fuel_flow_kg_s / thrust_N * 1000.0 * 3600.0,
        "effective_mass_flow_air_kg_s": total_air,
        "core_mass_flow_kg_s": core_air,
        "bypass_mass_flow_kg_s": bypass_air,
        "bypass_ratio": bpr,
        "fan_pressure_ratio": pi_f,
        "core_compressor_pressure_ratio": pi_cH,
        "overall_pressure_ratio": pi_f * pi_cH,
        "nozzle_choked": core_nozzle.choked,
        "bypass_nozzle_choked": bypass_nozzle.choked,
        "exit_velocity_m_s": core_nozzle.exit_velocity_m_s,
        "bypass_exit_velocity_m_s": bypass_nozzle.exit_velocity_m_s,
        "freestream_velocity_m_s": V0,
        "momentum_thrust_N": momentum_thrust_N,
        "pressure_thrust_N": pressure_thrust_N,
        "off_design": {
            "converged": converged,
            "iterations": iterations,
            "far_residual": far_residual,
            "hp_work_residual_relative": hp_residual_rel,
            "lp_work_residual_relative": lp_residual_rel,
            "fan_temp_ratio": tau_f,
            "hpc_temp_ratio": tau_cH,
            "hpt_temp_ratio": tau_tH,
            "lpt_temp_ratio": tau_tL,
            "hpt_pressure_ratio": reference.hpt_pressure_ratio,
            "lpt_pressure_ratio": reference.lpt_pressure_ratio,
        },
        "warnings": [
            "Two-spool turbofan off-design (separate flow); bypass ratio held at "
            "the design value. No fan/compressor maps; choked-turbine constant-"
            "ratio matching.",
        ],
    }
