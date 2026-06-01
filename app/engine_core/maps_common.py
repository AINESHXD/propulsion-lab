"""Shared numerical core for beta-line component maps (compressor + turbine).

Both the compressor map (:mod:`app.engine_core.compressor_maps`) and the turbine
map (:mod:`app.engine_core.turbine_maps`) are gridded over ``(corrected_speed,
beta)`` and read by the same operations: locate the bracketing cell, bilinearly
interpolate a field, take the bilinear partial derivatives, and — for off-design
matching — invert two fields simultaneously to recover ``(speed, beta)`` from a
target ``(field_a, field_b)`` pair.

Keeping these as small free functions (rather than a class hierarchy) lets both
map types share the maths without coupling their public dataclasses. The
functions accept either NumPy arrays or nested lists, so they also work on the
``to_dict()`` payloads.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class MapInversion:
    """Result of inverting two map fields for ``(corrected_speed, beta)``."""

    corrected_speed: float
    beta: float
    residual: float
    in_range: bool


def locate_cell(grid, value: float) -> tuple[int, float, bool]:
    """Return ``(cell_index, fraction, clamped)`` for ``value`` on ``grid``.

    ``grid`` must be strictly increasing. ``cell_index`` is the lower index of
    the bracketing cell; ``fraction`` is the position inside that cell in
    ``[0, 1]``. Out-of-range values clamp to the edge cell with ``clamped=True``.
    """

    n = len(grid)
    if value <= grid[0]:
        return 0, 0.0, value < grid[0]
    if value >= grid[-1]:
        return n - 2, 1.0, value > grid[-1]
    lo = 0
    hi = n - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if grid[mid] <= value:
            lo = mid
        else:
            hi = mid
    frac = (value - grid[lo]) / (grid[lo + 1] - grid[lo])
    return lo, float(frac), False


def bilinear(field, i: int, j: int, ts: float, tb: float) -> float:
    """Bilinear interpolation of ``field`` inside cell ``(i, j)``."""

    f00 = float(field[i][j])
    f10 = float(field[i + 1][j])
    f01 = float(field[i][j + 1])
    f11 = float(field[i + 1][j + 1])
    return (
        f00 * (1 - ts) * (1 - tb)
        + f10 * ts * (1 - tb)
        + f01 * (1 - ts) * tb
        + f11 * ts * tb
    )


def bilinear_partials(
    field, i: int, j: int, ts: float, tb: float, ds: float, db: float
) -> tuple[float, float]:
    """Return ``(d/d_speed, d/d_beta)`` of the bilinear surface in cell ``(i, j)``."""

    f00 = float(field[i][j])
    f10 = float(field[i + 1][j])
    f01 = float(field[i][j + 1])
    f11 = float(field[i + 1][j + 1])
    d_speed = ((f10 - f00) * (1 - tb) + (f11 - f01) * tb) / ds
    d_beta = ((f01 - f00) * (1 - ts) + (f11 - f10) * ts) / db
    return d_speed, d_beta


def invert_grid(
    field_a,
    field_b,
    speeds,
    beta,
    target_a: float,
    target_b: float,
    *,
    max_iterations: int = 60,
    tolerance: float = 1e-12,
) -> MapInversion:
    """Recover ``(corrected_speed, beta)`` so that the two fields hit their targets.

    A 2-D Newton iteration on the bilinear surfaces of ``field_a`` and
    ``field_b`` (using the analytic cell partials), with a clamp to the gridded
    range each step. Used by the off-design map matching to place a cycle
    operating point on the compressor characteristic. ``in_range`` is True when
    the converged point sits inside the grid and reproduces the targets to a
    small relative residual.
    """

    s = 0.5 * (speeds[0] + speeds[-1])
    b = 0.5 * (beta[0] + beta[-1])
    scale = abs(target_a) + abs(target_b) + 1.0
    clamped = False
    for _ in range(max_iterations):
        i, ts, sc = locate_cell(speeds, s)
        j, tb, bc = locate_cell(beta, b)
        clamped = sc or bc
        a_val = bilinear(field_a, i, j, ts, tb)
        b_val = bilinear(field_b, i, j, ts, tb)
        ra = a_val - target_a
        rb = b_val - target_b
        if math.hypot(ra, rb) < tolerance * scale:
            break
        ds = speeds[i + 1] - speeds[i]
        db = beta[j + 1] - beta[j]
        da_ds, da_db = bilinear_partials(field_a, i, j, ts, tb, ds, db)
        db_ds, db_db = bilinear_partials(field_b, i, j, ts, tb, ds, db)
        det = da_ds * db_db - da_db * db_ds
        if abs(det) < 1e-15:
            break
        step_s = (db_db * ra - da_db * rb) / det
        step_b = (-db_ds * ra + da_ds * rb) / det
        s = min(max(s - step_s, speeds[0]), speeds[-1])
        b = min(max(b - step_b, beta[0]), beta[-1])

    i, ts, sc = locate_cell(speeds, s)
    j, tb, bc = locate_cell(beta, b)
    a_val = bilinear(field_a, i, j, ts, tb)
    b_val = bilinear(field_b, i, j, ts, tb)
    residual = math.hypot(a_val - target_a, b_val - target_b)
    in_range = (not (sc or bc)) and residual < 1e-6 * scale
    return MapInversion(corrected_speed=s, beta=b, residual=residual, in_range=in_range)


def validate_beta_line(speeds, beta, mass_flow, pressure_ratio, efficiency, error_type):
    """Validate the shape, monotonicity and physical ranges of a beta-line map.

    ``error_type`` is the exception class to raise (so each map module raises its
    own domain error). Pressure ratio here means whichever ratio the map carries
    (compressor pressure ratio or turbine expansion ratio) and must exceed 1.
    """

    ns, nb = len(speeds), len(beta)
    if ns < 2 or nb < 2:
        raise error_type("A map needs at least 2 speed lines and 2 beta points.")
    expected = (ns, nb)
    for label, grid in (
        ("mass_flow", mass_flow),
        ("pressure_ratio", pressure_ratio),
        ("efficiency", efficiency),
    ):
        shape = (len(grid), len(grid[0])) if len(grid) else (0, 0)
        if shape != expected:
            raise error_type(
                f"Map field '{label}' has shape {shape}, expected {expected}."
            )
    if any(speeds[k + 1] <= speeds[k] for k in range(ns - 1)):
        raise error_type("Map corrected speeds must be strictly increasing.")
    if any(beta[k + 1] <= beta[k] for k in range(nb - 1)):
        raise error_type("Map beta coordinates must be strictly increasing.")
    if beta[0] < -1e-9 or beta[-1] > 1.0 + 1e-9:
        raise error_type("Map beta coordinates must lie within [0, 1].")
    for i in range(ns):
        for j in range(nb):
            if mass_flow[i][j] <= 0.0:
                raise error_type("Map corrected mass flow must be positive everywhere.")
            if pressure_ratio[i][j] <= 1.0:
                raise error_type("Map pressure/expansion ratio must exceed 1 everywhere.")
            if not (0.0 < efficiency[i][j] <= 1.0):
                raise error_type("Map efficiency must lie in (0, 1] everywhere.")
