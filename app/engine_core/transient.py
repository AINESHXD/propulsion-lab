"""Transient spool dynamics for the fixed-geometry turbojet.

The off-design solver (:mod:`app.engine_core.off_design`) finds the *steady*
operating point at a throttle setting: the speed at which turbine power exactly
balances compressor power. A real engine cannot jump between steady points,
the rotating spool has inertia, so when you slam the throttle the fuel (and
turbine inlet temperature) responds almost at once but the **spool speed lags**,
and thrust lags with it. That lag is why a jet does not make full thrust the
instant you push the lever.

Model
-----
Newton's second law for the rotor, written in spool-speed fraction
``n = N / N_design``:

    I * Omega * dOmega/dt = P_turbine(n, Tt4) - P_compressor(n).

Two standard reduced-order scalings close it. Compressor work rises with the
square of speed (Euler turbomachinery, dTt_c proportional to U^2 proportional to
N^2) and inducted flow rises roughly linearly with speed, so compressor power
scales as ``n^3``. At a fixed throttle the turbine power is linear in flow,
hence in ``n``. Matching both to the steady point ``n_ss(Tt4)`` (where the two
powers are equal) collapses the balance to

    dn/dt = ( n_ss(Tt4)^2 - n^2 ) / tau0,      tau0 = I * Omega_design^2 / P_spool,design.

``n_ss(Tt4)`` is read straight from the validated steady off-design solver (so
the endpoints of any transient reproduce it exactly), and ``tau0`` is built from
the rotor polar moment of inertia, the design spool speed and the design spool
power, all physical quantities. Instantaneous thrust is taken quasi-steadily
along the spool's operating line: the thrust the steady solver gives at the
current spool speed.

Honest limitations
------------------
* **No fuel-control accel schedule.** Real controllers deliberately ramp fuel to
  protect surge margin and turbine temperature during a slam, which makes the
  observed spool-up *slower* than raw inertia alone. This is the bare inertial
  response; the page says so.
* **Quasi-steady performance.** Thrust/TSFC track the steady operating line at
  the current spool speed rather than a fully unbalanced cycle, so the brief
  turbine-temperature overshoot during a slam is not resolved.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from app.engine_core.off_design import (
    TurbojetOffDesignReference,
    calibrate_turbojet_reference,
    solve_turbojet_off_design,
)
from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import CycleCalculationError, TurbojetCycleInputs

MAX_TIME_STEPS = 20000


@dataclass(slots=True, frozen=True)
class SpoolReference:
    """Everything the transient integrator needs, calibrated once."""

    reference: TurbojetOffDesignReference
    altitude_m: float
    mach: float
    design_tt4_K: float
    tau_c_design: float           # Tt3/Tt2 at the design point
    tau0_s: float                 # spool time constant I*Omega^2 / P_spool
    # Steady operating-line samples (ascending in Tt4), used for lookups.
    tt4_grid: tuple[float, ...]
    n_ss_grid: tuple[float, ...]  # steady spool fraction n = sqrt((tau_c-1)/(tau_c_des-1))
    thrust_grid: tuple[float, ...]
    tsfc_grid: tuple[float, ...]


def _interp(x: float, xs: tuple[float, ...], ys: tuple[float, ...]) -> float:
    """Clamped linear interpolation on an ascending grid."""

    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    lo, hi = 0, len(xs) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    span = xs[hi] - xs[lo]
    if span <= 0:
        return ys[lo]
    frac = (x - xs[lo]) / span
    return ys[lo] + frac * (ys[hi] - ys[lo])


def calibrate_spool_reference(
    design_inputs: TurbojetCycleInputs,
    *,
    polar_moment_of_inertia_kg_m2: float = 20.0,
    design_spool_speed_rpm: float = 12000.0,
    idle_throttle_fraction: float = 0.7,
    n_samples: int = 28,
) -> SpoolReference:
    """Build the steady operating-line table and the spool time constant."""

    if polar_moment_of_inertia_kg_m2 <= 0:
        raise CycleCalculationError("Rotor inertia must be positive.")
    if design_spool_speed_rpm <= 0:
        raise CycleCalculationError("Design spool speed must be positive.")
    if not 0.3 <= idle_throttle_fraction < 1.0:
        raise CycleCalculationError("Idle throttle fraction must be in [0.3, 1.0).")

    reference = calibrate_turbojet_reference(design_inputs)
    design = simulate_turbojet_cycle(design_inputs)
    stations = design["station_table"]
    Tt2_des = float(stations[2]["stagnation_temperature_K"])
    Tt3_des = float(stations[3]["stagnation_temperature_K"])
    tau_c_design = Tt3_des / Tt2_des
    mdot_des = float(design["effective_mass_flow_air_kg_s"])

    # Design spool power P = m_dot * cp_air * (Tt3 - Tt2). cp_air from constants
    # via the cycle: use the enthalpy rise directly.
    from app.engine_core.constants import cp_air

    p_spool_design = mdot_des * cp_air * (Tt3_des - Tt2_des)
    omega_des = 2.0 * math.pi * design_spool_speed_rpm / 60.0
    tau0 = polar_moment_of_inertia_kg_m2 * omega_des * omega_des / max(p_spool_design, 1.0)

    altitude_m = design_inputs.altitude_m
    mach = design_inputs.mach
    design_tt4 = design_inputs.turbine_inlet_temperature_K

    # Sweep the throttle from idle up to the design point, matching each steady
    # point; drop any that fall outside the solver's valid (choked) envelope.
    tt4_lo = idle_throttle_fraction * design_tt4
    tt4s: list[float] = []
    n_ss: list[float] = []
    thrust: list[float] = []
    tsfc: list[float] = []
    for k in range(n_samples):
        tt4 = tt4_lo + (design_tt4 - tt4_lo) * k / (n_samples - 1)
        try:
            res = solve_turbojet_off_design(
                reference, altitude_m=altitude_m, mach=mach,
                turbine_inlet_temperature_K=tt4,
            )
        except CycleCalculationError:
            continue
        tau_c = float(res["compressor_temp_ratio"])
        ratio = (tau_c - 1.0) / (tau_c_design - 1.0)
        if ratio <= 0:
            continue
        tt4s.append(tt4)
        n_ss.append(math.sqrt(ratio))
        thrust.append(float(res["thrust_kN"]))
        tsfc.append(float(res["TSFC_kg_per_kN_hr"]))

    if len(tt4s) < 3:
        raise CycleCalculationError(
            "Could not build a steady operating line for the transient "
            "(the off-design solver matched too few throttle settings)."
        )

    return SpoolReference(
        reference=reference,
        altitude_m=altitude_m,
        mach=mach,
        design_tt4_K=design_tt4,
        tau_c_design=tau_c_design,
        tau0_s=tau0,
        tt4_grid=tuple(tt4s),
        n_ss_grid=tuple(n_ss),
        thrust_grid=tuple(thrust),
        tsfc_grid=tuple(tsfc),
    )


def _n_ss_for_throttle(ref: SpoolReference, tt4: float) -> float:
    return _interp(tt4, ref.tt4_grid, ref.n_ss_grid)


def _thrust_for_speed(ref: SpoolReference, n: float) -> float:
    # n_ss_grid is ascending with tt4_grid, so interpolate thrust against it.
    return _interp(n, ref.n_ss_grid, ref.thrust_grid)


def _tsfc_for_speed(ref: SpoolReference, n: float) -> float:
    return _interp(n, ref.n_ss_grid, ref.tsfc_grid)


def simulate_spool_transient(
    ref: SpoolReference,
    throttle_schedule: Callable[[float], float],
    *,
    total_time_s: float = 8.0,
    dt_s: float = 0.02,
) -> dict[str, Any]:
    """Integrate the spool ODE under a throttle schedule (RK4).

    ``throttle_schedule(t) -> Tt4_command_K``. Returns time series of spool
    fraction, thrust, TSFC, the commanded throttle and its steady spool target,
    plus the settling time to 95% of the final spool speed.
    """

    if total_time_s <= 0 or dt_s <= 0:
        raise CycleCalculationError("total_time and dt must be positive.")
    steps = int(round(total_time_s / dt_s))
    if steps > MAX_TIME_STEPS:
        raise CycleCalculationError(
            f"Transient would take {steps} steps, exceeding the {MAX_TIME_STEPS} limit; "
            "increase dt or shorten the run."
        )

    tau0 = ref.tau0_s

    def dndt(n: float, t: float) -> float:
        n_target = _n_ss_for_throttle(ref, throttle_schedule(t))
        return (n_target * n_target - n * n) / tau0

    # Start at the steady spool speed for the initial throttle command.
    n = _n_ss_for_throttle(ref, throttle_schedule(0.0))

    samples: list[dict[str, float]] = []
    final_n = _n_ss_for_throttle(ref, throttle_schedule(total_time_s))

    def record(t: float, n_val: float) -> None:
        n_clamped = max(ref.n_ss_grid[0], min(ref.n_ss_grid[-1], n_val))
        samples.append({
            "t_s": t,
            "throttle_K": throttle_schedule(t),
            "spool_fraction": n_val,
            "spool_target": _n_ss_for_throttle(ref, throttle_schedule(t)),
            "thrust_kN": _thrust_for_speed(ref, n_clamped),
            "TSFC_kg_per_kN_hr": _tsfc_for_speed(ref, n_clamped),
        })

    record(0.0, n)
    settling_time: float | None = None
    for i in range(1, steps + 1):
        t = i * dt_s
        t0 = (i - 1) * dt_s
        # RK4 on dn/dt
        k1 = dndt(n, t0)
        k2 = dndt(n + 0.5 * dt_s * k1, t0 + 0.5 * dt_s)
        k3 = dndt(n + 0.5 * dt_s * k2, t0 + 0.5 * dt_s)
        k4 = dndt(n + dt_s * k3, t)
        n = n + (dt_s / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        record(t, n)
        if (
            settling_time is None
            and abs(final_n - samples[0]["spool_fraction"]) > 1e-6
            and abs(n - final_n) <= 0.05 * abs(final_n - samples[0]["spool_fraction"])
        ):
            settling_time = t

    return {
        "tau0_s": tau0,
        "samples": samples,
        "settling_time_s": settling_time,
        "initial_spool_fraction": samples[0]["spool_fraction"],
        "final_spool_fraction": final_n,
        "spool_min": ref.n_ss_grid[0],
        "spool_max": ref.n_ss_grid[-1],
    }


def step_throttle_schedule(
    ref: SpoolReference,
    *,
    idle_fraction: float,
    command_fraction: float,
    slam_time_s: float,
) -> Callable[[float], float]:
    """A throttle that holds at idle then steps to the commanded setting.

    Fractions are of the design Tt4. Useful default schedule for a slam
    acceleration (idle -> max) or a chop deceleration (max -> idle).
    """

    tt4_des = ref.design_tt4_K
    lo = idle_fraction * tt4_des
    hi = command_fraction * tt4_des

    def schedule(t: float) -> float:
        return hi if t >= slam_time_s else lo

    return schedule
