"""Tests for map-based turbojet off-design matching (Day 36-37).

The operating point must converge onto the compressor map: at the design
throttle and flight condition it sits at the map centre with the design
efficiency and reproduces the design thrust; off-design it migrates across the
map while staying converged and in range.
"""

import pytest

from app.engine_core.map_matching import (
    default_maps_for_reference,
    match_turbojet_on_maps,
)
from app.engine_core.off_design import (
    calibrate_turbojet_reference,
    solve_turbojet_off_design,
)
from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import TurbojetCycleInputs


def _reference() -> "object":
    return calibrate_turbojet_reference(TurbojetCycleInputs())


def test_default_maps_are_synthetic() -> None:
    comp, turb = default_maps_for_reference(_reference())
    assert comp.is_synthetic and turb.is_synthetic


def test_design_point_sits_at_map_centre() -> None:
    ref = _reference()
    res = match_turbojet_on_maps(
        ref,
        altitude_m=ref.design_inputs.altitude_m,
        mach=ref.design_inputs.mach,
        turbine_inlet_temperature_K=ref.design_tt4_K,
    )
    assert res["maps"]["converged"] is True
    comp = res["maps"]["compressor"]
    assert comp["corrected_speed"] == pytest.approx(1.0, abs=0.02)
    assert comp["beta"] == pytest.approx(0.5, abs=0.02)
    assert comp["efficiency"] == pytest.approx(
        ref.design_inputs.compressor_efficiency, abs=2e-3
    )
    assert comp["in_range"] is True
    assert comp["inverse_residual"] < 1e-6


def test_design_point_reproduces_design_thrust() -> None:
    ref = _reference()
    design = simulate_turbojet_cycle(ref.design_inputs)
    res = match_turbojet_on_maps(
        ref,
        altitude_m=ref.design_inputs.altitude_m,
        mach=ref.design_inputs.mach,
        turbine_inlet_temperature_K=ref.design_tt4_K,
    )
    assert res["thrust_kN"] == pytest.approx(design["thrust_kN"], rel=0.02)


def test_off_design_point_moves_on_map_and_stays_converged() -> None:
    ref = _reference()
    # Climb + throttle back: higher altitude keeps the nozzle choked (more
    # margin) while the operating point migrates across the map.
    res = match_turbojet_on_maps(
        ref,
        altitude_m=12000.0,
        mach=0.8,
        turbine_inlet_temperature_K=ref.design_tt4_K - 50.0,
    )
    assert res["maps"]["converged"] is True
    comp = res["maps"]["compressor"]
    assert comp["in_range"] is True
    # Throttled back: the operating point leaves the design centre.
    moved = abs(comp["corrected_speed"] - 1.0) + abs(comp["beta"] - 0.5)
    assert moved > 1e-3
    # Surge margin is defined and non-negative.
    assert comp["surge_margin"] >= 0.0


def test_running_line_is_monotonic_in_throttle() -> None:
    ref = _reference()
    comp, turb = default_maps_for_reference(ref)
    # Climb (more choke margin) and throttle up from the design point.
    throttles = [ref.design_tt4_K + d for d in (0.0, 20.0, 40.0, 60.0)]
    pr, mdot, thrust = [], [], []
    for tt4 in throttles:
        res = match_turbojet_on_maps(
            ref, altitude_m=12000.0, mach=0.8,
            turbine_inlet_temperature_K=tt4,
            compressor_map=comp, turbine_map=turb,
        )
        c = res["maps"]["compressor"]
        pr.append(c["pressure_ratio"])
        mdot.append(c["corrected_mass_flow"])
        thrust.append(res["thrust_kN"])
    assert pr == sorted(pr)
    assert mdot == sorted(mdot)
    assert thrust == sorted(thrust)


def test_map_match_agrees_with_constant_ratio_at_design() -> None:
    ref = _reference()
    constant_ratio = solve_turbojet_off_design(
        ref,
        altitude_m=ref.design_inputs.altitude_m,
        mach=ref.design_inputs.mach,
        turbine_inlet_temperature_K=ref.design_tt4_K,
    )
    mapped = match_turbojet_on_maps(
        ref,
        altitude_m=ref.design_inputs.altitude_m,
        mach=ref.design_inputs.mach,
        turbine_inlet_temperature_K=ref.design_tt4_K,
    )
    # At the design point the map efficiency equals the design efficiency, so the
    # two solvers must agree on thrust.
    assert mapped["thrust_kN"] == pytest.approx(constant_ratio["thrust_kN"], rel=0.02)


def test_custom_maps_are_used() -> None:
    ref = _reference()
    comp, turb = default_maps_for_reference(ref)
    res = match_turbojet_on_maps(
        ref,
        altitude_m=ref.design_inputs.altitude_m,
        mach=ref.design_inputs.mach,
        turbine_inlet_temperature_K=ref.design_tt4_K,
        compressor_map=comp,
        turbine_map=turb,
    )
    assert res["maps"]["converged"] is True
    assert res["maps"]["compressor"]["corrected_speed"] == pytest.approx(1.0, abs=0.02)


def test_surge_margin_nonnegative_along_line() -> None:
    ref = _reference()
    comp, turb = default_maps_for_reference(ref)
    for tt4 in (ref.design_tt4_K, ref.design_tt4_K + 30.0, ref.design_tt4_K + 60.0):
        res = match_turbojet_on_maps(
            ref, altitude_m=12000.0, mach=0.8,
            turbine_inlet_temperature_K=tt4,
            compressor_map=comp, turbine_map=turb,
        )
        assert res["maps"]["compressor"]["surge_margin"] >= 0.0


def test_map_match_endpoint_returns_running_line() -> None:
    from app.main import map_match_turbojet
    from app.schemas import MapMatchInput, TurbojetInput

    payload = map_match_turbojet(MapMatchInput(design=TurbojetInput()))
    assert payload["engine_type"] == "turbojet"
    assert payload["synthetic"] is True
    assert "speeds" in payload["compressor_map"]
    assert len(payload["points"]) >= 1
    assert payload["design_index"] is not None
    pt = payload["points"][0]
    for key in ("throttle_K", "corrected_mass_flow", "pressure_ratio", "efficiency", "surge_margin"):
        assert key in pt
    # Running line is sorted by corrected mass flow.
    flows = [p["corrected_mass_flow"] for p in payload["points"]]
    assert flows == sorted(flows)


def test_map_match_endpoint_is_robust_to_extreme_decks() -> None:
    """Extreme but schema-valid decks must return a result or a clean 400 -

    never a bare unhandled exception (Day 40-41 stability hardening)."""

    from fastapi import HTTPException

    from app.main import map_match_turbojet
    from app.schemas import MapMatchInput, TurbojetInput

    extreme_decks = [
        TurbojetInput(compressor_pressure_ratio=39.0, turbine_inlet_temperature_K=900.0),
        TurbojetInput(compressor_pressure_ratio=1.5, turbine_inlet_temperature_K=2200.0),
        TurbojetInput(altitude_m=24000.0, mach=2.9, compressor_efficiency=0.5),
        TurbojetInput(altitude_m=-400.0, mach=0.0),
    ]
    for deck in extreme_decks:
        try:
            payload = map_match_turbojet(MapMatchInput(design=deck))
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            assert "points" in payload and "compressor_map" in payload


def test_map_match_endpoint_rejects_afterburning() -> None:
    from fastapi import HTTPException

    from app.main import map_match_turbojet
    from app.schemas import MapMatchInput, TurbojetInput

    afterburning = TurbojetInput(
        engine_variant="afterburning_turbojet",
        afterburner_exit_temperature_K=1900.0,
    )
    with pytest.raises(HTTPException) as excinfo:
        map_match_turbojet(MapMatchInput(design=afterburning))
    assert excinfo.value.status_code == 400


def test_turbine_operating_point_reported() -> None:
    ref = _reference()
    res = match_turbojet_on_maps(
        ref,
        altitude_m=ref.design_inputs.altitude_m,
        mach=ref.design_inputs.mach,
        turbine_inlet_temperature_K=ref.design_tt4_K,
    )
    turb = res["maps"]["turbine"]
    assert turb["expansion_ratio"] > 1.0
    assert 0.0 < turb["efficiency"] <= 1.0
    assert res["maps"]["synthetic_maps"] is True
