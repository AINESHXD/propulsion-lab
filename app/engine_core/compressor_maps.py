"""Compressor map representation, beta-line parametrization, and bilinear lookup.

A compressor map relates four quantities along lines of constant *corrected
speed* N/sqrt(theta):

    - corrected mass flow      m * sqrt(theta) / delta
    - pressure ratio           Pt_exit / Pt_inlet
    - isentropic efficiency    eta

Raw maps are awkward to interpolate directly. Near choke the speed lines run
almost vertically (pressure ratio is nearly multi-valued in mass flow) and near
surge they fold back, so neither mass flow nor pressure ratio is a good
independent variable across the whole map. The standard fix is the *beta-line*
(auxiliary-coordinate) parametrization: a family of curves that cross every
speed line exactly once, turning the map into a single-valued function of
``(corrected_speed, beta)``. By the convention used here ``beta`` runs 0 -> 1
from the choke side to the surge side of each speed line.

This module provides:

    - :class:`CompressorMap` -- a map gridded over ``(speed, beta)`` with
      bilinear lookup and per-cell gradients (the gradients are what the
      off-design solver will need later to converge an operating point).
    - :func:`synthetic_compressor_map` -- a clearly-labelled *parametric* map so
      the lookup engine, the frontend plot, and the solver coupling can all be
      built and tested before a real, citable dataset is available.

Integrity note: no map in this module is taken from a manufacturer or a named
engine. The synthetic generator is qualitative -- it reproduces the correct
trends (pressure ratio rising with speed, mass flow falling toward surge, an
efficiency island around the design point) but the numbers are illustrative, and
``CompressorMap.source`` / ``is_synthetic`` say so. Real maps obtained from a
verifiable source can be loaded into the identical structure without changing
any of the lookup code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.engine_core.maps_common import MapInversion, invert_grid
from app.engine_core.types import CycleCalculationError


@dataclass(frozen=True)
class MapPoint:
    """A single interpolated operating point read off a compressor map."""

    corrected_speed: float
    beta: float
    corrected_mass_flow: float
    pressure_ratio: float
    efficiency: float
    in_range: bool


def _locate(grid: np.ndarray, value: float) -> tuple[int, float, bool]:
    """Return ``(cell_index, fraction, clamped)`` for ``value`` on ``grid``.

    ``grid`` must be strictly increasing. ``cell_index`` is the lower index of
    the bracketing cell and ``fraction`` is the position of ``value`` inside
    that cell in ``[0, 1]``. Out-of-range values are clamped to the edge cell
    and ``clamped`` is set True.
    """

    n = len(grid)
    if value <= grid[0]:
        return 0, 0.0, value < grid[0]
    if value >= grid[-1]:
        return n - 2, 1.0, value > grid[-1]
    upper = int(np.searchsorted(grid, value))
    i = max(0, min(upper - 1, n - 2))
    frac = (value - grid[i]) / (grid[i + 1] - grid[i])
    return i, float(frac), False


@dataclass
class CompressorMap:
    """A compressor map gridded over corrected speed and the beta coordinate.

    ``mass_flow``, ``pressure_ratio`` and ``efficiency`` are 2-D arrays of shape
    ``(len(speeds), len(beta))``. ``speeds`` and ``beta`` are strictly
    increasing 1-D arrays; ``beta`` lies in ``[0, 1]`` (0 = choke side,
    1 = surge side).
    """

    name: str
    speeds: np.ndarray
    beta: np.ndarray
    mass_flow: np.ndarray
    pressure_ratio: np.ndarray
    efficiency: np.ndarray
    source: str = "synthetic-parametric"
    is_synthetic: bool = True
    design_speed: float | None = None
    design_beta: float | None = None

    def __post_init__(self) -> None:
        self.speeds = np.asarray(self.speeds, dtype=float)
        self.beta = np.asarray(self.beta, dtype=float)
        self.mass_flow = np.asarray(self.mass_flow, dtype=float)
        self.pressure_ratio = np.asarray(self.pressure_ratio, dtype=float)
        self.efficiency = np.asarray(self.efficiency, dtype=float)

        ns, nb = len(self.speeds), len(self.beta)
        if ns < 2 or nb < 2:
            raise CycleCalculationError(
                "A compressor map needs at least 2 speed lines and 2 beta points."
            )
        expected = (ns, nb)
        for label, grid in (
            ("mass_flow", self.mass_flow),
            ("pressure_ratio", self.pressure_ratio),
            ("efficiency", self.efficiency),
        ):
            if grid.shape != expected:
                raise CycleCalculationError(
                    f"Compressor-map field '{label}' has shape {grid.shape}, "
                    f"expected {expected}."
                )
        if not np.all(np.diff(self.speeds) > 0):
            raise CycleCalculationError("Map corrected speeds must be strictly increasing.")
        if not np.all(np.diff(self.beta) > 0):
            raise CycleCalculationError("Map beta coordinates must be strictly increasing.")
        if self.beta[0] < -1e-9 or self.beta[-1] > 1.0 + 1e-9:
            raise CycleCalculationError("Map beta coordinates must lie within [0, 1].")
        if not np.all(self.mass_flow > 0.0):
            raise CycleCalculationError("Map corrected mass flow must be positive everywhere.")
        if not np.all(self.pressure_ratio > 1.0):
            raise CycleCalculationError("Map pressure ratio must exceed 1 everywhere.")
        if not np.all((self.efficiency > 0.0) & (self.efficiency <= 1.0)):
            raise CycleCalculationError("Map efficiency must lie in (0, 1] everywhere.")

    # -- lookup ---------------------------------------------------------------

    def _bilinear(self, field2d: np.ndarray, i: int, j: int, ts: float, tb: float) -> float:
        f00 = field2d[i, j]
        f10 = field2d[i + 1, j]
        f01 = field2d[i, j + 1]
        f11 = field2d[i + 1, j + 1]
        return float(
            f00 * (1 - ts) * (1 - tb)
            + f10 * ts * (1 - tb)
            + f01 * (1 - ts) * tb
            + f11 * ts * tb
        )

    def lookup(self, corrected_speed: float, beta: float) -> MapPoint:
        """Bilinearly interpolate the map at ``(corrected_speed, beta)``.

        Queries outside the gridded range are clamped to the edge and the
        returned :class:`MapPoint` has ``in_range = False`` so a caller (for
        example the off-design solver) can penalise the excursion rather than
        silently extrapolate.
        """

        i, ts, speed_clamped = _locate(self.speeds, corrected_speed)
        j, tb, beta_clamped = _locate(self.beta, beta)
        return MapPoint(
            corrected_speed=float(corrected_speed),
            beta=float(beta),
            corrected_mass_flow=self._bilinear(self.mass_flow, i, j, ts, tb),
            pressure_ratio=self._bilinear(self.pressure_ratio, i, j, ts, tb),
            efficiency=self._bilinear(self.efficiency, i, j, ts, tb),
            in_range=not (speed_clamped or beta_clamped),
        )

    def gradient(self, corrected_speed: float, beta: float) -> dict[str, tuple[float, float]]:
        """Return ``{field: (d/d_speed, d/d_beta)}`` from the bilinear cell.

        These are the analytic partial derivatives of the bilinear surface
        inside the bracketing cell. They are continuous within a cell (the
        "smooth derivatives" the off-design solver relies on) and finite
        everywhere on the map.
        """

        i, ts, _ = _locate(self.speeds, corrected_speed)
        j, tb, _ = _locate(self.beta, beta)
        ds = self.speeds[i + 1] - self.speeds[i]
        db = self.beta[j + 1] - self.beta[j]
        out: dict[str, tuple[float, float]] = {}
        for label, grid in (
            ("corrected_mass_flow", self.mass_flow),
            ("pressure_ratio", self.pressure_ratio),
            ("efficiency", self.efficiency),
        ):
            f00 = grid[i, j]
            f10 = grid[i + 1, j]
            f01 = grid[i, j + 1]
            f11 = grid[i + 1, j + 1]
            d_speed = ((f10 - f00) * (1 - tb) + (f11 - f01) * tb) / ds
            d_beta = ((f01 - f00) * (1 - ts) + (f11 - f10) * ts) / db
            out[label] = (float(d_speed), float(d_beta))
        return out

    # -- derived quantities ---------------------------------------------------

    def surge_margin(self, corrected_speed: float, beta: float) -> float:
        """Constant-speed surge margin at ``(corrected_speed, beta)``.

        Defined here as ``PR_surge / PR_operating - 1`` where ``PR_surge`` is the
        pressure ratio at the surge edge (``beta = 1``) of the same speed line.
        It is zero on the surge line and grows toward choke. This is a simple
        constant-corrected-speed definition, not the constant-flow definition
        some texts use; it is adequate for flagging proximity to surge.
        """

        operating = self.lookup(corrected_speed, beta).pressure_ratio
        surge = self.lookup(corrected_speed, self.beta[-1]).pressure_ratio
        return surge / operating - 1.0

    def invert(self, corrected_mass_flow: float, pressure_ratio: float) -> MapInversion:
        """Recover ``(corrected_speed, beta)`` from a target mass flow + pressure ratio.

        This is the inverse of :meth:`lookup` for the two flow fields, solved by
        a 2-D Newton iteration on the bilinear surfaces (the off-design map
        matching uses it to place a cycle operating point on the characteristic).
        """

        return invert_grid(
            self.mass_flow,
            self.pressure_ratio,
            self.speeds,
            self.beta,
            corrected_mass_flow,
            pressure_ratio,
        )

    def design_point(self) -> MapPoint | None:
        """Look up the stored design point, if the map declares one."""

        if self.design_speed is None or self.design_beta is None:
            return None
        return self.lookup(self.design_speed, self.design_beta)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready representation (used by the frontend map plot later)."""

        return {
            "name": self.name,
            "source": self.source,
            "is_synthetic": self.is_synthetic,
            "speeds": self.speeds.tolist(),
            "beta": self.beta.tolist(),
            "mass_flow": self.mass_flow.tolist(),
            "pressure_ratio": self.pressure_ratio.tolist(),
            "efficiency": self.efficiency.tolist(),
            "design_speed": self.design_speed,
            "design_beta": self.design_beta,
        }


def synthetic_compressor_map(
    *,
    name: str = "synthetic core compressor",
    design_pressure_ratio: float = 12.0,
    design_corrected_mass_flow: float = 50.0,
    design_efficiency: float = 0.86,
    speed_lines: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.05),
    n_beta: int = 21,
    beta_design: float = 0.5,
    pressure_ratio_beta_spread: float = 0.30,
    mass_flow_beta_spread: float = 0.35,
    speed_pressure_exponent: float = 2.0,
    speed_mass_flow_exponent: float = 1.0,
    efficiency_speed_falloff: float = 6.0,
    efficiency_beta_falloff: float = 1.5,
) -> CompressorMap:
    """Build a qualitative, clearly-labelled parametric compressor map.

    The map reproduces the supplied design point *exactly* at
    ``(corrected_speed = 1.0, beta = beta_design)`` and follows the expected
    trends around it:

    - pressure ratio rises with corrected speed (``~ speed**2`` by default) and
      rises from the choke side toward the surge side of each speed line;
    - corrected mass flow rises with speed and falls toward surge;
    - efficiency forms an island peaking at the design point and decaying with
      distance in both speed and beta.

    The numbers are illustrative, not measured. Replace this with a verified
    dataset when one is available -- the returned :class:`CompressorMap` has the
    same structure either way.
    """

    if not 0.0 <= beta_design <= 1.0:
        raise CycleCalculationError("beta_design must lie in [0, 1].")
    if 1.0 not in speed_lines:
        raise CycleCalculationError(
            "speed_lines must include the design corrected speed 1.0."
        )

    speeds = np.asarray(speed_lines, dtype=float)
    beta = np.linspace(0.0, 1.0, n_beta)

    s = speeds[:, None]          # (ns, 1)
    b = beta[None, :]            # (1, nb)
    db = b - beta_design

    pr_speed = s**speed_pressure_exponent
    pr_beta = 1.0 + pressure_ratio_beta_spread * db
    pressure_ratio = 1.0 + (design_pressure_ratio - 1.0) * pr_speed * pr_beta

    mf_speed = s**speed_mass_flow_exponent
    mf_beta = 1.0 - mass_flow_beta_spread * db
    mass_flow = design_corrected_mass_flow * mf_speed * mf_beta

    efficiency = design_efficiency * np.exp(
        -efficiency_speed_falloff * (s - 1.0) ** 2 - efficiency_beta_falloff * db**2
    )

    return CompressorMap(
        name=name,
        speeds=speeds,
        beta=beta,
        mass_flow=mass_flow,
        pressure_ratio=pressure_ratio,
        efficiency=efficiency,
        source="synthetic-parametric",
        is_synthetic=True,
        design_speed=1.0,
        design_beta=beta_design,
    )
