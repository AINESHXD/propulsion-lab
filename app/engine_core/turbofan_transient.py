"""Two-spool transient spool dynamics for the separate-flow turbofan.

The turbojet transient (:mod:`app.engine_core.transient`) has a single spool. A
turbofan has two, mechanically independent, rotating assemblies:

* the **HP (core) spool** — the core compressor driven by the HP turbine, light
  and fast, and
* the **LP (fan) spool** — the fan driven by the LP turbine, heavy and slow.

When you slam the throttle the fuel responds at once, but each spool accelerates
on its own inertia. The light core spool comes up first; the heavy fan spool
lags well behind, and since the fan moves most of the air, thrust follows the
fan. That split, core leads, fan and thrust trail, is the thing a single-spool
model cannot show.

Model
-----
Each spool obeys the same reduced-order law as the turbojet (Euler scaling:
compressor work proportional to N^2, power proportional to N^3), in its own
speed fraction:

    dn_H/dt = ( n_H,ss(Tt4)^2 - n_H^2 ) / tau0_H,    tau0_H = I_H Omega_H^2 / P_HP,des
    dn_L/dt = ( n_L,ss(Tt4)^2 - n_L^2 ) / tau0_L,    tau0_L = I_L Omega_L^2 / P_LP,des

The steady speed maps come from the validated two-spool off-design solver: at
each throttle it returns the fan and core compressor temperature ratios, which
give n_L,ss and n_H,ss. Thrust is read quasi-steadily along the **fan** spool's
operating line (the dominant thrust driver).

Honest limitations
------------------
Same as the single-spool model: bare inertial response with no fuel-control
acceleration schedule, quasi-steady performance, and the bypass ratio held at
the design value by the underlying off-design solver.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from app.engine_core.constants import cp_air
from app.engine_core.off_design import (
    TurbofanOffDesignReference,
    calibrate_turbofan_reference,
    solve_turbofan_off_design,
)
from app.engine_core.transient import MAX_TIME_STEPS, _interp
from app.engine_core.turbofan import TurbofanCycleInputs, simulate_turbofan_cycle
from app.engine_core.types import CycleCalculationError


@dataclass(slots=True, frozen=True)
class TwoSpoolReference:
    """Calibrated two-spool operating line + per-spool time constants."""

    reference: TurbofanOffDesignReference
    altitude_m: float
    mach: float
    design_tt4_K: float
    tau0_hp_s: float
    tau0_lp_s: float
    tt4_grid: tuple[float, ...]
    nhp_ss_grid: tuple[float, ...]
    nlp_ss_grid: tuple[float, ...]
    thrust_grid: tuple[float, ...]
    tsfc_grid: tuple[float, ...]


def calibrate_two_spool_reference(
    design_inputs: TurbofanCycleInputs,
    *,
    hp_inertia_kg_m2: float = 4.0,
    hp_speed_rpm: float = 16000.0,
    lp_inertia_kg_m2: float = 45.0,
    lp_speed_rpm: float = 4500.0,
    idle_throttle_fraction: float = 0.7,
    n_samples: int = 26,
) -> TwoSpoolReference:
    """Build the steady fan/core operating line and both spool time constants."""

    for inertia in (hp_inertia_kg_m2, lp_inertia_kg_m2):
        if inertia <= 0:
            raise CycleCalculationError("Rotor inertia must be positive.")
    if hp_speed_rpm <= 0 or lp_speed_rpm <= 0:
        raise CycleCalculationError("Spool speeds must be positive.")
    if not 0.3 <= idle_throttle_fraction < 1.0:
        raise CycleCalculationError("Idle throttle fraction must be in [0.3, 1.0).")

    reference = calibrate_turbofan_reference(design_inputs)
    design = simulate_turbofan_cycle(design_inputs)
    stations = design["station_table"]
    Tt2 = float(stations[2]["stagnation_temperature_K"])
    Tt13 = float(stations[13]["stagnation_temperature_K"])  # fan exit
    Tt3 = float(stations[3]["stagnation_temperature_K"])     # HPC exit
    tau_f_des = Tt13 / Tt2
    tau_cH_des = Tt3 / Tt13

    core_air = float(design["extra"]["core_mass_flow_kg_s"])
    total_air = core_air * (1.0 + design_inputs.bypass_ratio)

    # Design spool powers: the fan pumps the *total* air through a small rise; the
    # core compressor pumps the *core* air through a large rise.
    p_lp_des = total_air * cp_air * (Tt13 - Tt2)
    p_hp_des = core_air * cp_air * (Tt3 - Tt13)
    omega_hp = 2.0 * math.pi * hp_speed_rpm / 60.0
    omega_lp = 2.0 * math.pi * lp_speed_rpm / 60.0
    tau0_hp = hp_inertia_kg_m2 * omega_hp * omega_hp / max(p_hp_des, 1.0)
    tau0_lp = lp_inertia_kg_m2 * omega_lp * omega_lp / max(p_lp_des, 1.0)

    altitude_m = design_inputs.altitude_m
    mach = design_inputs.mach
    design_tt4 = design_inputs.turbine_inlet_temperature_K
    tt4_lo = idle_throttle_fraction * design_tt4

    tt4s: list[float] = []
    nhp: list[float] = []
    nlp: list[float] = []
    thrust: list[float] = []
    tsfc: list[float] = []
    for k in range(n_samples):
        tt4 = tt4_lo + (design_tt4 - tt4_lo) * k / (n_samples - 1)
        try:
            res = solve_turbofan_off_design(
                reference, altitude_m=altitude_m, mach=mach,
                turbine_inlet_temperature_K=tt4,
            )
        except CycleCalculationError:
            continue
        tau_f = float(res["off_design"]["fan_temp_ratio"])
        tau_cH = float(res["off_design"]["hpc_temp_ratio"])
        rl = (tau_f - 1.0) / (tau_f_des - 1.0)
        rh = (tau_cH - 1.0) / (tau_cH_des - 1.0)
        if rl <= 0 or rh <= 0:
            continue
        tt4s.append(tt4)
        nlp.append(math.sqrt(rl))
        nhp.append(math.sqrt(rh))
        thrust.append(float(res["thrust_kN"]))
        tsfc.append(float(res["TSFC_kg_per_kN_hr"]))

    if len(tt4s) < 3:
        raise CycleCalculationError(
            "Could not build a two-spool operating line for the transient."
        )

    return TwoSpoolReference(
        reference=reference,
        altitude_m=altitude_m,
        mach=mach,
        design_tt4_K=design_tt4,
        tau0_hp_s=tau0_hp,
        tau0_lp_s=tau0_lp,
        tt4_grid=tuple(tt4s),
        nhp_ss_grid=tuple(nhp),
        nlp_ss_grid=tuple(nlp),
        thrust_grid=tuple(thrust),
        tsfc_grid=tuple(tsfc),
    )


def step_throttle_schedule(
    ref: TwoSpoolReference,
    *,
    idle_fraction: float,
    command_fraction: float,
    slam_time_s: float,
) -> Callable[[float], float]:
    """Throttle that holds at idle then steps to the commanded Tt4 fraction."""

    lo = idle_fraction * ref.design_tt4_K
    hi = command_fraction * ref.design_tt4_K
    return lambda t: hi if t >= slam_time_s else lo


def simulate_two_spool_transient(
    ref: TwoSpoolReference,
    throttle_schedule: Callable[[float], float],
    *,
    total_time_s: float = 8.0,
    dt_s: float = 0.04,
) -> dict[str, Any]:
    """Integrate both spool ODEs (RK4) under a throttle schedule."""

    if total_time_s <= 0 or dt_s <= 0:
        raise CycleCalculationError("total_time and dt must be positive.")
    steps = int(round(total_time_s / dt_s))
    if steps > MAX_TIME_STEPS:
        raise CycleCalculationError(
            f"Transient would take {steps} steps, exceeding the {MAX_TIME_STEPS} limit."
        )

    def nhp_ss(t: float) -> float:
        return _interp(throttle_schedule(t), ref.tt4_grid, ref.nhp_ss_grid)

    def nlp_ss(t: float) -> float:
        return _interp(throttle_schedule(t), ref.tt4_grid, ref.nlp_ss_grid)

    def step(n: float, target: float, tau0: float) -> float:
        return (target * target - n * n) / tau0

    n_hp = nhp_ss(0.0)
    n_lp = nlp_ss(0.0)
    samples: list[dict[str, float]] = []
    final_lp = nlp_ss(total_time_s)

    def thrust_at(n_lp_val: float) -> float:
        clamped = max(ref.nlp_ss_grid[0], min(ref.nlp_ss_grid[-1], n_lp_val))
        return _interp(clamped, ref.nlp_ss_grid, ref.thrust_grid)

    def tsfc_at(n_lp_val: float) -> float:
        clamped = max(ref.nlp_ss_grid[0], min(ref.nlp_ss_grid[-1], n_lp_val))
        return _interp(clamped, ref.nlp_ss_grid, ref.tsfc_grid)

    def record(t: float, nh: float, nl: float) -> None:
        samples.append({
            "t_s": t,
            "throttle_K": throttle_schedule(t),
            "spool_hp": nh,
            "spool_lp": nl,
            "spool_hp_target": nhp_ss(t),
            "spool_lp_target": nlp_ss(t),
            "thrust_kN": thrust_at(nl),
            "TSFC_kg_per_kN_hr": tsfc_at(nl),
        })

    record(0.0, n_hp, n_lp)
    settle_hp: float | None = None
    settle_lp: float | None = None
    n0_lp = samples[0]["spool_lp"]
    for i in range(1, steps + 1):
        t, t0 = i * dt_s, (i - 1) * dt_s
        # RK4 for each spool (independent ODEs sharing the throttle command).
        # HP spool
        k1 = step(n_hp, nhp_ss(t0), ref.tau0_hp_s)
        k2 = step(n_hp + 0.5 * dt_s * k1, nhp_ss(t0 + 0.5 * dt_s), ref.tau0_hp_s)
        k3 = step(n_hp + 0.5 * dt_s * k2, nhp_ss(t0 + 0.5 * dt_s), ref.tau0_hp_s)
        k4 = step(n_hp + dt_s * k3, nhp_ss(t), ref.tau0_hp_s)
        n_hp = n_hp + (dt_s / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        # LP spool
        l1 = step(n_lp, nlp_ss(t0), ref.tau0_lp_s)
        l2 = step(n_lp + 0.5 * dt_s * l1, nlp_ss(t0 + 0.5 * dt_s), ref.tau0_lp_s)
        l3 = step(n_lp + 0.5 * dt_s * l2, nlp_ss(t0 + 0.5 * dt_s), ref.tau0_lp_s)
        l4 = step(n_lp + dt_s * l3, nlp_ss(t), ref.tau0_lp_s)
        n_lp = n_lp + (dt_s / 6.0) * (l1 + 2 * l2 + 2 * l3 + l4)
        record(t, n_hp, n_lp)
        span = abs(final_lp - n0_lp)
        if settle_lp is None and span > 1e-6 and abs(n_lp - final_lp) <= 0.05 * span:
            settle_lp = t
        final_hp = nhp_ss(total_time_s)
        span_h = abs(final_hp - samples[0]["spool_hp"])
        if settle_hp is None and span_h > 1e-6 and abs(n_hp - final_hp) <= 0.05 * span_h:
            settle_hp = t

    return {
        "tau0_hp_s": ref.tau0_hp_s,
        "tau0_lp_s": ref.tau0_lp_s,
        "settling_time_hp_s": settle_hp,
        "settling_time_lp_s": settle_lp,
        "initial_spool_lp": samples[0]["spool_lp"],
        "final_spool_lp": final_lp,
        "spool_min": ref.nlp_ss_grid[0],
        "spool_max": max(ref.nhp_ss_grid[-1], ref.nlp_ss_grid[-1]),
        "samples": samples,
    }
