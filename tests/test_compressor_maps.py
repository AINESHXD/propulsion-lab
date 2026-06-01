"""Tests for the compressor-map beta-line lookup engine (Day 31-32).

These cover the interpolation math (bilinear exactness + analytic gradients),
the qualitative trends of the synthetic map, range clamping, the surge-margin
helper, and the input validation. No real manufacturer data is involved; the
synthetic map is explicitly labelled.
"""

import numpy as np
import pytest

from app.engine_core.compressor_maps import (
    CompressorMap,
    synthetic_compressor_map,
)
from app.engine_core.types import CycleCalculationError


def _linear_field_map() -> CompressorMap:
    """A map whose fields are exact bilinear functions of (speed, beta).

    Bilinear interpolation reproduces a bilinear function exactly, so this map
    lets us check the lookup values and gradients against closed form.
    """

    speeds = np.array([0.5, 1.0, 1.5])
    beta = np.array([0.0, 0.5, 1.0])
    s = speeds[:, None]
    b = beta[None, :]
    pressure_ratio = 2.0 + 1.0 * s + 0.5 * b + 0.3 * s * b
    mass_flow = 10.0 + 5.0 * s - 2.0 * b + 1.0 * s * b
    efficiency = 0.60 + 0.10 * s + 0.05 * b + 0.02 * s * b
    return CompressorMap(
        name="linear-test",
        speeds=speeds,
        beta=beta,
        mass_flow=mass_flow,
        pressure_ratio=pressure_ratio,
        efficiency=efficiency,
        source="test-linear",
    )


# -- synthetic map structure --------------------------------------------------


def test_synthetic_map_builds_and_validates() -> None:
    m = synthetic_compressor_map()
    assert m.is_synthetic is True
    assert m.source == "synthetic-parametric"
    assert m.mass_flow.shape == (len(m.speeds), len(m.beta))
    assert np.all(np.diff(m.speeds) > 0)
    assert np.all(np.diff(m.beta) > 0)
    assert np.all(m.pressure_ratio > 1.0)
    assert np.all(m.mass_flow > 0.0)
    assert np.all((m.efficiency > 0.0) & (m.efficiency <= 1.0))


def test_synthetic_map_reproduces_design_point_exactly() -> None:
    m = synthetic_compressor_map(
        design_pressure_ratio=14.0,
        design_corrected_mass_flow=42.0,
        design_efficiency=0.88,
    )
    dp = m.design_point()
    assert dp is not None
    assert dp.pressure_ratio == pytest.approx(14.0, abs=1e-9)
    assert dp.corrected_mass_flow == pytest.approx(42.0, abs=1e-9)
    assert dp.efficiency == pytest.approx(0.88, abs=1e-9)
    assert dp.in_range is True


def test_synthetic_map_trends() -> None:
    m = synthetic_compressor_map()
    # Along a speed line: pressure ratio rises and mass flow falls toward surge.
    low_beta = m.lookup(1.0, 0.1)
    high_beta = m.lookup(1.0, 0.9)
    assert high_beta.pressure_ratio > low_beta.pressure_ratio
    assert high_beta.corrected_mass_flow < low_beta.corrected_mass_flow
    # Across speed at fixed beta: both pressure ratio and mass flow rise.
    slow = m.lookup(0.7, 0.5)
    fast = m.lookup(1.0, 0.5)
    assert fast.pressure_ratio > slow.pressure_ratio
    assert fast.corrected_mass_flow > slow.corrected_mass_flow
    # Efficiency peaks at the design point.
    assert m.lookup(1.0, 0.5).efficiency >= m.lookup(0.6, 0.2).efficiency


# -- interpolation math -------------------------------------------------------


def test_lookup_is_exact_at_grid_nodes() -> None:
    m = synthetic_compressor_map()
    for i, sp in enumerate(m.speeds):
        for j, bt in enumerate(m.beta):
            p = m.lookup(float(sp), float(bt))
            assert p.pressure_ratio == pytest.approx(m.pressure_ratio[i, j], abs=1e-9)
            assert p.corrected_mass_flow == pytest.approx(m.mass_flow[i, j], abs=1e-9)
            assert p.efficiency == pytest.approx(m.efficiency[i, j], abs=1e-9)


def test_bilinear_matches_closed_form_on_linear_field() -> None:
    m = _linear_field_map()
    rng = np.random.default_rng(0)
    for _ in range(25):
        sq = float(rng.uniform(0.5, 1.5))
        bq = float(rng.uniform(0.0, 1.0))
        p = m.lookup(sq, bq)
        assert p.pressure_ratio == pytest.approx(
            2.0 + 1.0 * sq + 0.5 * bq + 0.3 * sq * bq, abs=1e-9
        )
        assert p.corrected_mass_flow == pytest.approx(
            10.0 + 5.0 * sq - 2.0 * bq + 1.0 * sq * bq, abs=1e-9
        )


def test_gradient_matches_closed_form_on_linear_field() -> None:
    m = _linear_field_map()
    sq, bq = 1.1, 0.4
    grad = m.gradient(sq, bq)
    # d(PR)/d(speed) = 1.0 + 0.3*beta ; d(PR)/d(beta) = 0.5 + 0.3*speed
    assert grad["pressure_ratio"][0] == pytest.approx(1.0 + 0.3 * bq, abs=1e-9)
    assert grad["pressure_ratio"][1] == pytest.approx(0.5 + 0.3 * sq, abs=1e-9)
    # d(mass)/d(speed) = 5.0 + 1.0*beta ; d(mass)/d(beta) = -2.0 + 1.0*speed
    assert grad["corrected_mass_flow"][0] == pytest.approx(5.0 + 1.0 * bq, abs=1e-9)
    assert grad["corrected_mass_flow"][1] == pytest.approx(-2.0 + 1.0 * sq, abs=1e-9)


def test_invert_round_trips_lookup() -> None:
    m = synthetic_compressor_map()
    for sp, bt in [(0.85, 0.40), (1.0, 0.5), (0.70, 0.70), (1.05, 0.25)]:
        p = m.lookup(sp, bt)
        inv = m.invert(p.corrected_mass_flow, p.pressure_ratio)
        assert inv.in_range
        assert inv.corrected_speed == pytest.approx(sp, abs=2e-3)
        assert inv.beta == pytest.approx(bt, abs=2e-3)


def test_synthetic_gradient_signs() -> None:
    m = synthetic_compressor_map()
    grad = m.gradient(0.9, 0.5)
    assert grad["pressure_ratio"][0] > 0.0      # PR rises with speed
    assert grad["pressure_ratio"][1] > 0.0      # PR rises toward surge
    assert grad["corrected_mass_flow"][1] < 0.0  # mass falls toward surge


# -- range handling -----------------------------------------------------------


def test_out_of_range_speed_is_clamped_and_flagged() -> None:
    m = synthetic_compressor_map()
    below = m.lookup(0.1, 0.5)   # below lowest speed line
    above = m.lookup(9.9, 0.5)   # above highest speed line
    assert below.in_range is False
    assert above.in_range is False
    # Clamped to the edge speed-line values.
    assert below.pressure_ratio == pytest.approx(m.lookup(m.speeds[0], 0.5).pressure_ratio)
    assert above.pressure_ratio == pytest.approx(m.lookup(m.speeds[-1], 0.5).pressure_ratio)


def test_beta_out_of_range_is_clamped() -> None:
    m = synthetic_compressor_map()
    p = m.lookup(1.0, 1.5)  # beta past surge edge
    assert p.in_range is False
    assert p.pressure_ratio == pytest.approx(m.lookup(1.0, m.beta[-1]).pressure_ratio)


# -- derived quantities -------------------------------------------------------


def test_surge_margin_zero_on_surge_line_and_grows_toward_choke() -> None:
    m = synthetic_compressor_map()
    assert m.surge_margin(1.0, m.beta[-1]) == pytest.approx(0.0, abs=1e-9)
    near_surge = m.surge_margin(1.0, 0.8)
    near_choke = m.surge_margin(1.0, 0.2)
    assert near_choke > near_surge > 0.0


def test_to_dict_round_trips() -> None:
    m = synthetic_compressor_map()
    d = m.to_dict()
    rebuilt = CompressorMap(
        name=d["name"],
        speeds=np.array(d["speeds"]),
        beta=np.array(d["beta"]),
        mass_flow=np.array(d["mass_flow"]),
        pressure_ratio=np.array(d["pressure_ratio"]),
        efficiency=np.array(d["efficiency"]),
        source=d["source"],
    )
    probe = rebuilt.lookup(0.85, 0.4)
    original = m.lookup(0.85, 0.4)
    assert probe.pressure_ratio == pytest.approx(original.pressure_ratio, abs=1e-12)


# -- validation ---------------------------------------------------------------


def test_field_shape_mismatch_is_rejected() -> None:
    with pytest.raises(CycleCalculationError):
        CompressorMap(
            name="bad",
            speeds=np.array([0.5, 1.0]),
            beta=np.array([0.0, 1.0]),
            mass_flow=np.array([[1.0, 2.0, 3.0]]),  # wrong shape
            pressure_ratio=np.array([[2.0, 2.0], [3.0, 3.0]]),
            efficiency=np.array([[0.8, 0.8], [0.8, 0.8]]),
        )


def test_non_monotonic_speeds_rejected() -> None:
    with pytest.raises(CycleCalculationError):
        CompressorMap(
            name="bad",
            speeds=np.array([1.0, 0.5]),  # decreasing
            beta=np.array([0.0, 1.0]),
            mass_flow=np.array([[1.0, 1.0], [1.0, 1.0]]),
            pressure_ratio=np.array([[2.0, 2.0], [2.0, 2.0]]),
            efficiency=np.array([[0.8, 0.8], [0.8, 0.8]]),
        )


def test_efficiency_above_one_rejected() -> None:
    with pytest.raises(CycleCalculationError):
        CompressorMap(
            name="bad",
            speeds=np.array([0.5, 1.0]),
            beta=np.array([0.0, 1.0]),
            mass_flow=np.array([[1.0, 1.0], [1.0, 1.0]]),
            pressure_ratio=np.array([[2.0, 2.0], [2.0, 2.0]]),
            efficiency=np.array([[0.8, 1.2], [0.8, 0.8]]),  # 1.2 invalid
        )


def test_synthetic_map_requires_design_speed_line() -> None:
    with pytest.raises(CycleCalculationError):
        synthetic_compressor_map(speed_lines=(0.5, 0.7, 0.9))  # no 1.0


# -- API endpoint -------------------------------------------------------------


def test_compressor_map_endpoint_returns_synthetic_payload() -> None:
    from app.main import compressor_map

    payload = compressor_map(
        design_pressure_ratio=15.0,
        design_corrected_mass_flow=60.0,
        design_efficiency=0.87,
    )
    assert payload["is_synthetic"] is True
    assert payload["source"] == "synthetic-parametric"
    for key in ("speeds", "beta", "mass_flow", "pressure_ratio", "efficiency"):
        assert key in payload
    # The design point sits at corrected speed 1.0 / beta 0.5 of the returned grid.
    assert payload["design_speed"] == 1.0


def test_compressor_map_endpoint_rejects_bad_efficiency() -> None:
    from fastapi import HTTPException

    from app.main import compressor_map

    with pytest.raises(HTTPException) as excinfo:
        compressor_map(design_efficiency=1.5)  # efficiency island peak > 1
    assert excinfo.value.status_code == 400
