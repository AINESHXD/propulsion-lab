"""Tests for the two-spool turbofan transient (HP core + LP fan spools)."""

from __future__ import annotations

import pytest

from app.engine_core.turbofan import TurbofanCycleInputs
from app.engine_core.turbofan_transient import (
    calibrate_two_spool_reference,
    simulate_two_spool_transient,
    step_throttle_schedule,
)
from app.engine_core.types import CycleCalculationError


def _ref(**kw):
    return calibrate_two_spool_reference(TurbofanCycleInputs(), **kw)


def test_calibration_is_physical() -> None:
    ref = _ref()
    assert ref.tau0_hp_s > 0 and ref.tau0_lp_s > 0
    # the light core spool has the smaller time constant (leads the heavy fan)
    assert ref.tau0_hp_s < ref.tau0_lp_s
    assert ref.nhp_ss_grid[-1] == pytest.approx(1.0, abs=1e-6)
    assert ref.nlp_ss_grid[-1] == pytest.approx(1.0, abs=1e-6)


def test_core_leads_the_fan_on_a_slam() -> None:
    ref = _ref()
    sched = step_throttle_schedule(ref, idle_fraction=0.7, command_fraction=1.0, slam_time_s=1.0)
    out = simulate_two_spool_transient(ref, sched, total_time_s=10.0, dt_s=0.02)
    after = [s for s in out["samples"] if 1.0 < s["t_s"] < 6.0]
    # through the acceleration the core spool is at or ahead of the fan spool
    assert all(s["spool_hp"] >= s["spool_lp"] - 1e-6 for s in after)
    # both rise monotonically and thrust lags (follows the fan)
    thr = [s["thrust_kN"] for s in out["samples"] if s["t_s"] >= 1.0]
    assert all(b >= a - 1e-6 for a, b in zip(thr, thr[1:]))
    just_after = next(s for s in out["samples"] if s["t_s"] >= 1.05)
    assert just_after["thrust_kN"] < 0.9 * thr[-1]
    # the core settles before the fan
    assert out["settling_time_hp_s"] is not None and out["settling_time_lp_s"] is not None
    assert out["settling_time_hp_s"] <= out["settling_time_lp_s"]


def test_more_fan_inertia_slows_the_fan() -> None:
    light = _ref(lp_inertia_kg_m2=30.0)
    heavy = _ref(lp_inertia_kg_m2=90.0)
    assert heavy.tau0_lp_s > light.tau0_lp_s
    sched_l = step_throttle_schedule(light, idle_fraction=0.6, command_fraction=1.0, slam_time_s=0.5)
    sched_h = step_throttle_schedule(heavy, idle_fraction=0.6, command_fraction=1.0, slam_time_s=0.5)
    out_l = simulate_two_spool_transient(light, sched_l, total_time_s=20.0, dt_s=0.04)
    out_h = simulate_two_spool_transient(heavy, sched_h, total_time_s=20.0, dt_s=0.04)
    assert out_h["settling_time_lp_s"] > out_l["settling_time_lp_s"]


def test_steady_in_steady_out() -> None:
    ref = _ref()
    sched = step_throttle_schedule(ref, idle_fraction=0.7, command_fraction=0.7, slam_time_s=1.0)
    out = simulate_two_spool_transient(ref, sched, total_time_s=5.0, dt_s=0.05)
    for key in ("spool_hp", "spool_lp"):
        vals = [s[key] for s in out["samples"]]
        assert max(vals) - min(vals) < 1e-3


def test_bad_inertia_rejected() -> None:
    with pytest.raises(CycleCalculationError):
        _ref(hp_inertia_kg_m2=-1.0)
