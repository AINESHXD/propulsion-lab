"""Perfect-gas helper functions used by the cycle model."""

from __future__ import annotations

import numpy as np

from app.engine_core.constants import R_air, gamma_air


def speed_of_sound(
    static_temperature_K: float,
    gamma: float = gamma_air,
    gas_constant: float = R_air,
) -> float:
    """Calculate speed of sound for a perfect gas."""

    return float(np.sqrt(gamma * gas_constant * static_temperature_K))


def stagnation_temperature(
    static_temperature_K: float,
    mach: float,
    gamma: float = gamma_air,
) -> float:
    """Calculate stagnation temperature from static temperature and Mach number."""

    return static_temperature_K * (1.0 + ((gamma - 1.0) / 2.0) * mach**2)


def stagnation_pressure(
    static_pressure_Pa: float,
    mach: float,
    gamma: float = gamma_air,
) -> float:
    """Calculate stagnation pressure from static pressure and Mach number."""

    pressure_ratio = (1.0 + ((gamma - 1.0) / 2.0) * mach**2) ** (
        gamma / (gamma - 1.0)
    )
    return static_pressure_Pa * pressure_ratio


def area_ratio_from_mach(mach: float, gamma: float = gamma_air) -> float:
    """Isentropic area ratio A/A* for a given Mach number.

    A* is the sonic (throat) area. Valid for both subsonic and supersonic
    Mach; returns 1.0 at M = 1.
    """

    if mach <= 0.0:
        raise ValueError("Mach number must be positive.")
    term = (2.0 / (gamma + 1.0)) * (1.0 + (gamma - 1.0) / 2.0 * mach**2)
    exponent = (gamma + 1.0) / (2.0 * (gamma - 1.0))
    return (1.0 / mach) * term**exponent


def normal_shock_pressure_ratio(mach: float, gamma: float = gamma_air) -> float:
    """Static-pressure ratio P2/P1 across a normal shock at upstream ``mach``.

    Rankine-Hugoniot relation. Returns 1.0 for M <= 1 (no shock).
    """

    if mach <= 1.0:
        return 1.0
    return 1.0 + (2.0 * gamma / (gamma + 1.0)) * (mach**2 - 1.0)


def normal_shock_stagnation_pressure_ratio(
    mach: float, gamma: float = gamma_air
) -> float:
    """Stagnation-pressure ratio Pt2/Pt1 across a normal shock.

    Captures the irreversible total-pressure loss of the shock. Returns 1.0
    for M <= 1 (no loss).
    """

    if mach <= 1.0:
        return 1.0
    m2 = mach**2
    term1 = ((gamma + 1.0) * m2 / (2.0 + (gamma - 1.0) * m2)) ** (
        gamma / (gamma - 1.0)
    )
    term2 = ((gamma + 1.0) / (2.0 * gamma * m2 - (gamma - 1.0))) ** (
        1.0 / (gamma - 1.0)
    )
    return term1 * term2


def subsonic_mach_from_pressure_ratio(
    stagnation_over_static: float, gamma: float = gamma_air
) -> float:
    """Subsonic Mach from a stagnation/static pressure ratio Pt/P.

    Returns 0 when the ratio is <= 1, and is clamped just below 1 if the ratio
    is supercritical (the caller is in a regime where it expects subsonic flow).
    """

    if stagnation_over_static <= 1.0:
        return 0.0
    m2 = (2.0 / (gamma - 1.0)) * (
        stagnation_over_static ** ((gamma - 1.0) / gamma) - 1.0
    )
    mach = m2**0.5
    return min(mach, 0.999)


def supersonic_mach_from_area_ratio(
    area_ratio: float,
    gamma: float = gamma_air,
    mach_max: float = 12.0,
) -> float:
    """Supersonic-branch Mach number for a convergent-divergent nozzle.

    Inverts the isentropic area-Mach relation ``A/A* = f(M)`` for the
    supersonic root (M > 1), where ``area_ratio`` is the divergent
    exit-to-throat area ratio. ``f(M)`` is monotonic for M > 1, so a simple
    bisection converges quickly and robustly.
    """

    if area_ratio <= 1.0:
        return 1.0
    lo, hi = 1.0 + 1e-6, mach_max
    # f(M) - area_ratio is monotonic increasing on (1, inf); bracket and bisect.
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if area_ratio_from_mach(mid, gamma) < area_ratio:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)

