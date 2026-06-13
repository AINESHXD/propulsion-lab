"""Wiebe finite heat-release model.

Real combustion is not instantaneous: the charge burns over a finite span of
crank angle. The Wiebe function is the standard single-zone burn law — the
*mass-fraction burned* as a function of crank angle::

    x_b(theta) = 1 - exp( -a * ((theta - theta_soc) / delta_theta) ** (m + 1) )

* ``theta_soc``   — crank angle at start of combustion [deg]
* ``delta_theta`` — total burn duration [deg]
* ``a``           — efficiency factor; ``a = 5`` burns 99.3 % by the end of the
                    nominal duration, ``a = 6.908`` burns 99.9 %.
* ``m``           — form factor; ``m ~ 2`` for a typical SI engine (the burn
                    rate peaks partway through, not at the start).

The heat-release *rate* ``dx_b/dtheta`` is what the cycle integrator adds to the
gas each crank-angle step. Spreading the heat release over real crank angle —
rather than dumping it all at TDC — is exactly why a finite-burn engine falls
*below* the air-standard efficiency ceiling.
"""

from __future__ import annotations

import math


def wiebe_burn_fraction(
    theta_deg: float,
    start_deg: float,
    duration_deg: float,
    a: float = 5.0,
    m: float = 2.0,
) -> float:
    """Mass-fraction burned at crank angle ``theta_deg`` (0 before, ->1 after).

    Returns 0 before combustion starts and saturates toward 1 once the burn
    duration is complete. Continuous and monotonic in between.
    """

    if duration_deg <= 0.0:
        raise ValueError("Burn duration must be positive.")
    if a <= 0.0:
        raise ValueError("Wiebe efficiency factor 'a' must be positive.")

    frac = (theta_deg - start_deg) / duration_deg
    if frac <= 0.0:
        return 0.0
    if frac >= 1.0:
        # Past the nominal duration: hold the (near-unity) end value rather
        # than letting the exponential keep creeping, so the model is bounded.
        frac = 1.0
    return 1.0 - math.exp(-a * frac ** (m + 1.0))


def wiebe_burn_rate(
    theta_deg: float,
    start_deg: float,
    duration_deg: float,
    a: float = 5.0,
    m: float = 2.0,
) -> float:
    """Heat-release rate ``dx_b/dtheta`` [1/deg] at crank angle ``theta_deg``.

    The analytic derivative of :func:`wiebe_burn_fraction`. Zero outside the
    burn window; its integral over the window equals the total burned fraction
    ``x_b(end)`` (slightly under 1 for finite ``a``).
    """

    if duration_deg <= 0.0:
        raise ValueError("Burn duration must be positive.")

    frac = (theta_deg - start_deg) / duration_deg
    if frac <= 0.0 or frac >= 1.0:
        return 0.0
    return (
        a * (m + 1.0) / duration_deg
        * frac ** m
        * math.exp(-a * frac ** (m + 1.0))
    )
