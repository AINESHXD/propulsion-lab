"""Slider-crank cylinder geometry.

The instantaneous cylinder volume as the crank turns is what makes the P-V
loop *physical* instead of four straight textbook segments. Crank angle
``theta`` is measured from top dead centre (TDC = 0), positive in the
direction of rotation.

Definitions
-----------
* bore ``B``           — cylinder diameter [m]
* stroke ``S``         — full piston travel [m]; crank radius ``a = S/2``
* rod ratio ``R``      — connecting-rod length / crank radius, ``L/a``
                         (typical 3 - 4; longer rod = less secondary motion)
* compression ratio ``r`` — ``V_max / V_min``

Piston displacement from TDC (standard slider-crank kinematics)::

    s(theta) = a + L - [ a*cos(theta) + sqrt(L**2 - a**2 * sin(theta)**2) ]

so ``s(0) = 0`` (TDC) and ``s(pi) = 2a = S`` (BDC). The swept area is
``A = pi/4 * B**2`` and the volume is the clearance volume plus the swept
volume to that point::

    V(theta) = V_clearance + A * s(theta)
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class CylinderGeometry:
    """Fixed cylinder geometry for one cylinder."""

    bore_m: float
    stroke_m: float
    compression_ratio: float
    rod_ratio: float = 3.5            # connecting-rod length / crank radius

    def __post_init__(self) -> None:
        if self.bore_m <= 0 or self.stroke_m <= 0:
            raise ValueError("Bore and stroke must be positive.")
        if self.compression_ratio <= 1.0:
            raise ValueError("Compression ratio must exceed 1.")
        # The rod must be longer than the crank radius or the slider-crank
        # square-root term goes imaginary at mid-stroke.
        if self.rod_ratio <= 1.0:
            raise ValueError("Rod ratio (L/a) must exceed 1.")

    @property
    def crank_radius_m(self) -> float:
        return 0.5 * self.stroke_m

    @property
    def rod_length_m(self) -> float:
        return self.rod_ratio * self.crank_radius_m

    @property
    def bore_area_m2(self) -> float:
        return 0.25 * math.pi * self.bore_m**2

    @property
    def displacement_m3(self) -> float:
        return self.bore_area_m2 * self.stroke_m

    @property
    def clearance_m3(self) -> float:
        return self.displacement_m3 / (self.compression_ratio - 1.0)

    @property
    def volume_max_m3(self) -> float:
        """Cylinder volume at BDC (clearance + full displacement)."""

        return self.clearance_m3 + self.displacement_m3

    @property
    def volume_min_m3(self) -> float:
        """Cylinder volume at TDC (clearance volume)."""

        return self.clearance_m3


def displacement_volume(bore_m: float, stroke_m: float) -> float:
    """Swept (displacement) volume of one cylinder [m^3]."""

    if bore_m <= 0 or stroke_m <= 0:
        raise ValueError("Bore and stroke must be positive.")
    return 0.25 * math.pi * bore_m**2 * stroke_m


def clearance_volume(displacement_m3: float, compression_ratio: float) -> float:
    """Clearance (TDC) volume from displacement and compression ratio."""

    if compression_ratio <= 1.0:
        raise ValueError("Compression ratio must exceed 1.")
    return displacement_m3 / (compression_ratio - 1.0)


def piston_position_from_tdc(theta_rad: float, geom: CylinderGeometry) -> float:
    """Piston displacement from TDC [m] at crank angle ``theta_rad``."""

    a = geom.crank_radius_m
    L = geom.rod_length_m
    return a + L - (a * math.cos(theta_rad)
                    + math.sqrt(L * L - (a * math.sin(theta_rad)) ** 2))


def cylinder_volume(theta_rad: float, geom: CylinderGeometry) -> float:
    """Instantaneous cylinder volume [m^3] at crank angle ``theta_rad``.

    ``theta_rad`` measured from TDC. Returns ``volume_min`` at TDC and
    ``volume_max`` at BDC, varying with the true slider-crank motion in between.
    """

    return geom.clearance_m3 + geom.bore_area_m2 * piston_position_from_tdc(theta_rad, geom)
