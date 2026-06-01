"""Tests for the turbine map (Day 36-37), mirroring the compressor-map tests.

The turbine map shares the numerical core with the compressor map, so these
focus on the turbine-specific structure: a near-flat (choked) corrected mass
flow, expansion ratio rising along beta, the design point, lookup/invert
round-tripping, and validation.
"""

import numpy as np
import pytest

from app.engine_core.turbine_maps import TurbineMap, synthetic_turbine_map
from app.engine_core.types import CycleCalculationError


def test_synthetic_turbine_map_builds_and_validates() -> None:
    m = synthetic_turbine_map()
    assert m.is_synthetic is True
    assert m.source == "synthetic-parametric"
    assert m.mass_flow.shape == (len(m.speeds), len(m.beta))
    assert np.all(m.pressure_ratio > 1.0)
    assert np.all(m.mass_flow > 0.0)
    assert np.all((m.efficiency > 0.0) & (m.efficiency <= 1.0))


def test_turbine_design_point_reproduced_exactly() -> None:
    m = synthetic_turbine_map(
        design_expansion_ratio=3.8,
        design_corrected_mass_flow=20.0,
        design_efficiency=0.91,
    )
    dp = m.design_point()
    assert dp is not None
    assert dp.expansion_ratio == pytest.approx(3.8, abs=1e-9)
    assert dp.corrected_mass_flow == pytest.approx(20.0, abs=1e-9)
    assert dp.efficiency == pytest.approx(0.91, abs=1e-9)


def test_turbine_corrected_flow_is_nearly_flat_and_expansion_rises() -> None:
    m = synthetic_turbine_map()
    low = m.lookup(1.0, 0.1)
    high = m.lookup(1.0, 0.9)
    # Expansion ratio rises along beta.
    assert high.expansion_ratio > low.expansion_ratio
    # Corrected mass flow is nearly constant (choked turbine): < 5% spread.
    spread = abs(high.corrected_mass_flow - low.corrected_mass_flow) / low.corrected_mass_flow
    assert spread < 0.05


def test_turbine_lookup_exact_at_nodes() -> None:
    m = synthetic_turbine_map()
    for i, sp in enumerate(m.speeds):
        for j, bt in enumerate(m.beta):
            p = m.lookup(float(sp), float(bt))
            assert p.expansion_ratio == pytest.approx(m.pressure_ratio[i, j], abs=1e-9)
            assert p.efficiency == pytest.approx(m.efficiency[i, j], abs=1e-9)


def test_turbine_invert_round_trips() -> None:
    m = synthetic_turbine_map()
    for sp, bt in [(0.8, 0.3), (1.0, 0.5), (0.9, 0.8)]:
        p = m.lookup(sp, bt)
        inv = m.invert(p.corrected_mass_flow, p.expansion_ratio)
        assert inv.in_range
        assert inv.corrected_speed == pytest.approx(sp, abs=3e-3)
        assert inv.beta == pytest.approx(bt, abs=3e-3)


def test_turbine_to_dict_round_trips() -> None:
    m = synthetic_turbine_map()
    d = m.to_dict()
    rebuilt = TurbineMap(
        name=d["name"],
        speeds=np.array(d["speeds"]),
        beta=np.array(d["beta"]),
        mass_flow=np.array(d["mass_flow"]),
        pressure_ratio=np.array(d["pressure_ratio"]),
        efficiency=np.array(d["efficiency"]),
    )
    a = rebuilt.lookup(0.85, 0.4)
    b = m.lookup(0.85, 0.4)
    assert a.expansion_ratio == pytest.approx(b.expansion_ratio, abs=1e-12)


def test_turbine_gradient_matches_finite_difference() -> None:
    m = synthetic_turbine_map()
    s, b, h = 0.82, 0.42, 1e-5
    grad = m.gradient(s, b)
    # Central differences within the same cell (h small) for expansion ratio.
    er_ds = (m.lookup(s + h, b).expansion_ratio - m.lookup(s - h, b).expansion_ratio) / (2 * h)
    er_db = (m.lookup(s, b + h).expansion_ratio - m.lookup(s, b - h).expansion_ratio) / (2 * h)
    assert grad["expansion_ratio"][0] == pytest.approx(er_ds, abs=1e-4)
    assert grad["expansion_ratio"][1] == pytest.approx(er_db, abs=1e-4)


def test_turbine_invalid_expansion_ratio_rejected() -> None:
    with pytest.raises(CycleCalculationError):
        TurbineMap(
            name="bad",
            speeds=np.array([0.5, 1.0]),
            beta=np.array([0.0, 1.0]),
            mass_flow=np.array([[1.0, 1.0], [1.0, 1.0]]),
            pressure_ratio=np.array([[0.9, 0.9], [0.9, 0.9]]),  # <= 1 invalid
            efficiency=np.array([[0.9, 0.9], [0.9, 0.9]]),
        )
