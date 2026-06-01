"""Turbine map representation, mirroring the compressor-map architecture.

A turbine map is gridded over ``(corrected_speed, beta)`` exactly like the
compressor map (:mod:`app.engine_core.compressor_maps`) and shares the same
numerical core (:mod:`app.engine_core.maps_common`): bilinear lookup, analytic
gradients, and a 2-D inverse. The fields differ in meaning:

    - ``mass_flow``      corrected mass flow m * sqrt(theta) / delta
    - ``pressure_ratio`` turbine **expansion ratio** Pt_inlet / Pt_exit (> 1)
    - ``efficiency``     turbine isentropic efficiency

Turbines behave differently from compressors: they choke, so corrected mass
flow is nearly flat (weakly dependent on speed and expansion ratio) once the
turbine nozzle is choked, and there is no surge boundary. The reduced-order
off-design solver already treats the HP turbine as choked (constant temperature
and pressure ratios); this map is the structure a measured turbine
characteristic would load into, and it lets the matching read a turbine
efficiency consistent with the operating point.

Integrity note: as with the compressor map, the synthetic generator here is a
clearly-labelled qualitative characteristic, not manufacturer data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.engine_core.maps_common import (
    MapInversion,
    bilinear,
    bilinear_partials,
    invert_grid,
    locate_cell,
    validate_beta_line,
)
from app.engine_core.types import CycleCalculationError


@dataclass(frozen=True)
class TurbineMapPoint:
    """A single interpolated operating point read off a turbine map."""

    corrected_speed: float
    beta: float
    corrected_mass_flow: float
    expansion_ratio: float
    efficiency: float
    in_range: bool


@dataclass
class TurbineMap:
    """A turbine map gridded over corrected speed and the beta coordinate.

    ``pressure_ratio`` is the turbine expansion ratio Pt_inlet / Pt_exit (> 1).
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
        validate_beta_line(
            self.speeds,
            self.beta,
            self.mass_flow,
            self.pressure_ratio,
            self.efficiency,
            CycleCalculationError,
        )

    def lookup(self, corrected_speed: float, beta: float) -> TurbineMapPoint:
        """Bilinearly interpolate the map at ``(corrected_speed, beta)``."""

        i, ts, speed_clamped = locate_cell(self.speeds, corrected_speed)
        j, tb, beta_clamped = locate_cell(self.beta, beta)
        return TurbineMapPoint(
            corrected_speed=float(corrected_speed),
            beta=float(beta),
            corrected_mass_flow=bilinear(self.mass_flow, i, j, ts, tb),
            expansion_ratio=bilinear(self.pressure_ratio, i, j, ts, tb),
            efficiency=bilinear(self.efficiency, i, j, ts, tb),
            in_range=not (speed_clamped or beta_clamped),
        )

    def gradient(self, corrected_speed: float, beta: float) -> dict[str, tuple[float, float]]:
        """Return ``{field: (d/d_speed, d/d_beta)}`` from the bilinear cell."""

        i, ts, _ = locate_cell(self.speeds, corrected_speed)
        j, tb, _ = locate_cell(self.beta, beta)
        ds = self.speeds[i + 1] - self.speeds[i]
        db = self.beta[j + 1] - self.beta[j]
        return {
            "corrected_mass_flow": bilinear_partials(self.mass_flow, i, j, ts, tb, ds, db),
            "expansion_ratio": bilinear_partials(self.pressure_ratio, i, j, ts, tb, ds, db),
            "efficiency": bilinear_partials(self.efficiency, i, j, ts, tb, ds, db),
        }

    def invert(self, corrected_mass_flow: float, expansion_ratio: float) -> MapInversion:
        """Recover ``(corrected_speed, beta)`` from a mass flow + expansion ratio."""

        return invert_grid(
            self.mass_flow,
            self.pressure_ratio,
            self.speeds,
            self.beta,
            corrected_mass_flow,
            expansion_ratio,
        )

    def design_point(self) -> TurbineMapPoint | None:
        """Look up the stored design point, if the map declares one."""

        if self.design_speed is None or self.design_beta is None:
            return None
        return self.lookup(self.design_speed, self.design_beta)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready representation (parallel to the compressor map)."""

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


def synthetic_turbine_map(
    *,
    name: str = "synthetic HP turbine",
    design_expansion_ratio: float = 3.5,
    design_corrected_mass_flow: float = 18.0,
    design_efficiency: float = 0.90,
    speed_lines: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.05),
    n_beta: int = 21,
    beta_design: float = 0.5,
    expansion_beta_spread: float = 0.45,
    mass_flow_beta_spread: float = 0.04,
    mass_flow_speed_exponent: float = 0.05,
    efficiency_speed_falloff: float = 4.0,
    efficiency_beta_falloff: float = 1.2,
) -> TurbineMap:
    """Build a qualitative, clearly-labelled parametric turbine map.

    Reproduces the design point exactly at ``(corrected_speed = 1.0,
    beta = beta_design)`` and follows turbine trends: corrected mass flow is
    nearly flat (the choked turbine swallows almost the same corrected flow
    regardless of operating point), expansion ratio rises along the beta
    coordinate, and efficiency forms an island around the design point. The
    numbers are illustrative, not measured.
    """

    if not 0.0 <= beta_design <= 1.0:
        raise CycleCalculationError("beta_design must lie in [0, 1].")
    if 1.0 not in speed_lines:
        raise CycleCalculationError(
            "speed_lines must include the design corrected speed 1.0."
        )

    speeds = np.asarray(speed_lines, dtype=float)
    beta = np.linspace(0.0, 1.0, n_beta)
    s = speeds[:, None]
    b = beta[None, :]
    db = b - beta_design

    # Expansion ratio is independent of corrected speed (choked turbine); the
    # ``0.0 * s`` term broadcasts it across the speed lines to the full grid.
    expansion_ratio = (
        1.0 + (design_expansion_ratio - 1.0) * (1.0 + expansion_beta_spread * db) + 0.0 * s
    )
    mass_flow = (
        design_corrected_mass_flow
        * s**mass_flow_speed_exponent
        * (1.0 + mass_flow_beta_spread * db)
    )
    efficiency = design_efficiency * np.exp(
        -efficiency_speed_falloff * (s - 1.0) ** 2 - efficiency_beta_falloff * db**2
    )

    return TurbineMap(
        name=name,
        speeds=speeds,
        beta=beta,
        mass_flow=mass_flow,
        pressure_ratio=expansion_ratio,
        efficiency=efficiency,
        source="synthetic-parametric",
        is_synthetic=True,
        design_speed=1.0,
        design_beta=beta_design,
    )
