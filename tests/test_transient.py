"""Tests for the transient spool-dynamics model."""

from __future__ import annotations

import pytest

from app.engine_core.off_design import (
    calibrate_turbojet_reference,
    solve_turbojet_off_design,
)
from app.engine_core.transient import (
    calibrate_spool_reference,
    simulate_spool_transient,
    step_throttle_schedule,
)
from app.engine_core.types import CycleCalculationError
from app.schemas import TurbojetInput


def _ref(**kw):
    return calibrate_spool_reference(TurbojetInput().to_cycle_inputs(), **kw)


def test_calibration_is_physical() -> None:
    ref = _ref()
    assert ref.tau0_s > 0
    # operating line ascends in both throttle and steady spool speed
    assert list(ref.tt4_grid) == sorted(ref.tt4_grid)
    assert list(ref.n_ss_grid) == sorted(ref.n_ss_grid)
    assert ref.n_ss_grid[-1] == pytest.approx(1.0, abs=1e-6)  # design point => n=1


def test_steady_in_steady_out() -> None:
    ref = _ref()
    sched = step_throttle_schedule(ref, idle_fraction=0.7, command_fraction=0.7, slam_time_s=1.0)
    out = simulate_spool_transient(ref, sched, total_time_s=5.0, dt_s=0.05)
    ns = [s["spool_fraction"] for s in out["samples"]]
    assert max(ns) - min(ns) < 1e-3  # no command change => spool holds


def test_slam_spools_up_monotonically_and_lags() -> None:
    ref = _ref()
    sched = step_throttle_schedule(ref, idle_fraction=0.7, command_fraction=1.0, slam_time_s=1.0)
    out = simulate_spool_transient(ref, sched, total_time_s=10.0, dt_s=0.02)
    samples = out["samples"]
    # final spool is the design speed; initial is idle
    assert out["final_spool_fraction"] > out["initial_spool_fraction"]
    assert out["final_spool_fraction"] == pytest.approx(1.0, abs=1e-3)

    after_slam = [s for s in samples if s["t_s"] >= 1.0]
    ns = [s["spool_fraction"] for s in after_slam]
    thr = [s["thrust_kN"] for s in after_slam]
    # monotonic non-decreasing spool + thrust through the acceleration
    assert all(b >= a - 1e-6 for a, b in zip(ns, ns[1:]))
    assert all(b >= a - 1e-6 for a, b in zip(thr, thr[1:]))
    # the lag: thrust just after the slam is well below the settled value
    just_after = next(s for s in samples if s["t_s"] >= 1.05)
    assert just_after["thrust_kN"] < 0.9 * thr[-1]


def test_more_inertia_spools_up_slower() -> None:
    light = _ref(polar_moment_of_inertia_kg_m2=10.0)
    heavy = _ref(polar_moment_of_inertia_kg_m2=60.0)
    sched_l = step_throttle_schedule(light, idle_fraction=0.6, command_fraction=1.0, slam_time_s=0.5)
    sched_h = step_throttle_schedule(heavy, idle_fraction=0.6, command_fraction=1.0, slam_time_s=0.5)
    out_l = simulate_spool_transient(light, sched_l, total_time_s=20.0, dt_s=0.04)
    out_h = simulate_spool_transient(heavy, sched_h, total_time_s=20.0, dt_s=0.04)
    assert heavy.tau0_s > light.tau0_s
    assert out_h["settling_time_s"] > out_l["settling_time_s"]


def test_endpoint_thrust_reproduces_steady_off_design() -> None:
    design = TurbojetInput()
    ref = calibrate_spool_reference(design.to_cycle_inputs())
    sched = step_throttle_schedule(ref, idle_fraction=0.7, command_fraction=1.0, slam_time_s=0.5)
    out = simulate_spool_transient(ref, sched, total_time_s=12.0, dt_s=0.02)
    settled_thrust = out["samples"][-1]["thrust_kN"]

    od = calibrate_turbojet_reference(design.to_cycle_inputs())
    steady = solve_turbojet_off_design(
        od, altitude_m=design.altitude_m, mach=design.mach,
        turbine_inlet_temperature_K=design.turbine_inlet_temperature_K,
    )
    assert settled_thrust == pytest.approx(steady["thrust_kN"], rel=0.02)


def test_bad_inertia_rejected() -> None:
    with pytest.raises(CycleCalculationError):
        _ref(polar_moment_of_inertia_kg_m2=-1.0)


def test_bad_idle_fraction_rejected() -> None:
    with pytest.raises(CycleCalculationError):
        _ref(idle_throttle_fraction=1.2)
