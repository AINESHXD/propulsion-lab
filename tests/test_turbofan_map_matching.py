"""Tests for two-spool turbofan on-map running-line matching."""

from __future__ import annotations

import pytest

from app.engine_core.off_design import calibrate_turbofan_reference
from app.engine_core.turbofan import TurbofanCycleInputs
from app.engine_core.turbofan_map_matching import (
    default_maps_for_turbofan,
    match_turbofan_on_maps,
)


def _ref():
    return calibrate_turbofan_reference(TurbofanCycleInputs())


def test_maps_are_sized_and_synthetic() -> None:
    fan, hpc = default_maps_for_turbofan(_ref())
    assert fan.is_synthetic and hpc.is_synthetic
    # fan pressure ratio is far below the core compressor's
    fan_pr = fan.lookup(fan.design_speed, fan.design_beta).pressure_ratio
    hpc_pr = hpc.lookup(hpc.design_speed, hpc.design_beta).pressure_ratio
    assert fan_pr < hpc_pr


def test_design_point_sits_on_both_maps_in_range() -> None:
    ref = _ref()
    res = match_turbofan_on_maps(
        ref, altitude_m=ref.design_inputs.altitude_m, mach=ref.design_inputs.mach,
        turbine_inlet_temperature_K=ref.design_tt4_K,
    )
    assert res["maps"]["fan"]["in_range"]
    assert res["maps"]["compressor"]["in_range"]
    # at the design point the matched fan/HPC pressure ratios are near design
    assert res["maps"]["fan"]["pressure_ratio"] == pytest.approx(
        ref.design_inputs.fan_pressure_ratio, rel=0.06
    )


def test_running_line_moves_up_with_throttle() -> None:
    ref = _ref()
    lo = match_turbofan_on_maps(ref, altitude_m=ref.design_inputs.altitude_m,
                                mach=ref.design_inputs.mach,
                                turbine_inlet_temperature_K=0.88 * ref.design_tt4_K)
    hi = match_turbofan_on_maps(ref, altitude_m=ref.design_inputs.altitude_m,
                                mach=ref.design_inputs.mach,
                                turbine_inlet_temperature_K=1.0 * ref.design_tt4_K)
    # more throttle -> higher fan & HPC pressure ratio, more corrected speed, more thrust
    assert hi["maps"]["fan"]["pressure_ratio"] > lo["maps"]["fan"]["pressure_ratio"]
    assert hi["maps"]["compressor"]["pressure_ratio"] > lo["maps"]["compressor"]["pressure_ratio"]
    assert hi["maps"]["fan"]["corrected_speed"] >= lo["maps"]["fan"]["corrected_speed"]
    assert hi["thrust_kN"] > lo["thrust_kN"]


def test_surge_margins_are_reported() -> None:
    ref = _ref()
    res = match_turbofan_on_maps(ref, altitude_m=ref.design_inputs.altitude_m,
                                 mach=ref.design_inputs.mach,
                                 turbine_inlet_temperature_K=ref.design_tt4_K)
    for spool in ("fan", "compressor"):
        sm = res["maps"][spool]["surge_margin"]
        assert sm is None or -1.0 < sm < 2.0
