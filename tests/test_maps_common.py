"""Direct unit tests for the shared beta-line map core (Day 39).

The compressor and turbine maps exercise these functions indirectly; here they
are tested in isolation against closed form: cell location + clamping, bilinear
value and gradient, the 2-D inverse (round-trip + out-of-range), and the grid
validator.
"""

import pytest

from app.engine_core.maps_common import (
    MapInversion,
    bilinear,
    bilinear_partials,
    invert_grid,
    locate_cell,
    validate_beta_line,
)
from app.engine_core.types import CycleCalculationError

SPEEDS = [0.5, 1.0, 1.5]
BETA = [0.0, 0.5, 1.0]


def _field(fn):
    """Build a 2-D grid over (SPEEDS, BETA) from a scalar function fn(s, b)."""

    return [[fn(s, b) for b in BETA] for s in SPEEDS]


def test_locate_cell_interior() -> None:
    i, frac, clamped = locate_cell(SPEEDS, 0.75)
    assert i == 0
    assert frac == pytest.approx(0.5)
    assert clamped is False


def test_locate_cell_nodes_and_clamping() -> None:
    # Exact interior node.
    i, frac, clamped = locate_cell(SPEEDS, 1.0)
    assert (i, clamped) == (1, False)
    assert frac == pytest.approx(0.0)
    # Below range -> clamp to first cell, flagged.
    i, frac, clamped = locate_cell(SPEEDS, 0.2)
    assert (i, frac, clamped) == (0, 0.0, True)
    # Above range -> clamp to last cell, flagged.
    i, frac, clamped = locate_cell(SPEEDS, 9.0)
    assert (i, frac, clamped) == (1, 1.0, True)


def test_bilinear_matches_manual_average() -> None:
    field = _field(lambda s, b: 2.0 + 3.0 * s + 4.0 * b + 5.0 * s * b)
    # Cell (0,0), midpoint -> average of the four corners.
    value = bilinear(field, 0, 0, 0.5, 0.5)
    assert value == pytest.approx(2.0 + 3.0 * 0.75 + 4.0 * 0.25 + 5.0 * 0.75 * 0.25)


def test_bilinear_partials_match_analytic() -> None:
    field = _field(lambda s, b: 2.0 + 3.0 * s + 4.0 * b + 5.0 * s * b)
    ds = SPEEDS[1] - SPEEDS[0]
    db = BETA[1] - BETA[0]
    d_speed, d_beta = bilinear_partials(field, 0, 0, 0.5, 0.5, ds, db)
    # df/ds = 3 + 5b at b = 0.25 ; df/db = 4 + 5s at s = 0.75.
    assert d_speed == pytest.approx(3.0 + 5.0 * 0.25)
    assert d_beta == pytest.approx(4.0 + 5.0 * 0.75)


def test_invert_grid_round_trip() -> None:
    field_a = _field(lambda s, b: 10.0 + 5.0 * s - 2.0 * b + 1.0 * s * b)
    field_b = _field(lambda s, b: 2.0 + 1.0 * s + 0.5 * b + 0.3 * s * b)
    s0, b0 = 0.9, 0.4
    target_a = 10.0 + 5.0 * s0 - 2.0 * b0 + 1.0 * s0 * b0
    target_b = 2.0 + 1.0 * s0 + 0.5 * b0 + 0.3 * s0 * b0
    inv = invert_grid(field_a, field_b, SPEEDS, BETA, target_a, target_b)
    assert isinstance(inv, MapInversion)
    assert inv.in_range
    assert inv.corrected_speed == pytest.approx(s0, abs=2e-3)
    assert inv.beta == pytest.approx(b0, abs=2e-3)


def test_invert_grid_out_of_range_flagged() -> None:
    field_a = _field(lambda s, b: 10.0 + 5.0 * s - 2.0 * b + 1.0 * s * b)
    field_b = _field(lambda s, b: 2.0 + 1.0 * s + 0.5 * b + 0.3 * s * b)
    # Targets evaluated well beyond the grid (s = 4) cannot be reproduced.
    target_a = 10.0 + 5.0 * 4.0 - 2.0 * 0.5 + 1.0 * 4.0 * 0.5
    target_b = 2.0 + 1.0 * 4.0 + 0.5 * 0.5 + 0.3 * 4.0 * 0.5
    inv = invert_grid(field_a, field_b, SPEEDS, BETA, target_a, target_b)
    assert inv.in_range is False


def test_validate_beta_line_passes_and_rejects() -> None:
    good_mass = _field(lambda s, b: 10.0 + s)
    good_ratio = _field(lambda s, b: 2.0 + s)
    good_eff = _field(lambda s, b: 0.85)
    # Valid grid: no exception.
    validate_beta_line(SPEEDS, BETA, good_mass, good_ratio, good_eff, CycleCalculationError)
    # Non-positive mass flow.
    with pytest.raises(CycleCalculationError):
        validate_beta_line(
            SPEEDS, BETA, _field(lambda s, b: -1.0), good_ratio, good_eff, CycleCalculationError
        )
    # Pressure/expansion ratio <= 1.
    with pytest.raises(CycleCalculationError):
        validate_beta_line(
            SPEEDS, BETA, good_mass, _field(lambda s, b: 0.9), good_eff, CycleCalculationError
        )
    # Efficiency out of (0, 1].
    with pytest.raises(CycleCalculationError):
        validate_beta_line(
            SPEEDS, BETA, good_mass, good_ratio, _field(lambda s, b: 1.2), CycleCalculationError
        )
