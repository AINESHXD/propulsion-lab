"""Engine friction (Chen-Flynn FMEP) and the indicated -> brake split.

Everything :mod:`cycle` reports is *indicated* — work the gas does on the
piston. What a crankshaft actually delivers is *brake* power: indicated minus
the work lost rubbing the rings, bearings and valvetrain and driving the
accessories. That loss is modelled as a friction mean effective pressure
(FMEP) with the standard **Chen-Flynn** correlation::

    FMEP = A + B * p_max + C * Sp_mean + D * Sp_mean**2

* ``A``          — constant term (accessories, idle rubbing)
* ``B * p_max``  — load term: ring/bearing friction rises with peak pressure
* ``C * Sp``     — speed term: hydrodynamic rubbing, linear in piston speed
* ``D * Sp**2``  — speed term: grows quadratically at high speed

The brake mean effective pressure is then ``BMEP = IMEP - FMEP``, and brake
power/torque follow. This is where PistonLab stops flattering itself: brake
numbers are always below indicated, and the gap widens with speed.
"""

from __future__ import annotations

# Chen-Flynn coefficients, tuned to a passenger-car SI band (~1-2.5 bar FMEP).
# Working in bar with p_max in bar and mean piston speed in m/s, then converted
# to Pa on the way out. These are model parameters, not measured for any engine.
_A_BAR = 0.40            # constant / accessory term
_B = 0.004              # per bar of peak pressure (load term)
_C_BAR_S_PER_M = 0.04   # per m/s of mean piston speed
_D_BAR_S2_PER_M2 = 9.0e-4   # per (m/s)^2


def chen_flynn_fmep_Pa(
    peak_pressure_Pa: float,
    mean_piston_speed_m_s: float,
    multiplier: float = 1.0,
) -> float:
    """Friction mean effective pressure [Pa] from peak pressure and piston speed.

    Rises with both the peak cylinder pressure (load on the rings and bearings)
    and the mean piston speed (rubbing). ``multiplier`` scales the whole FMEP for
    sweeps / a tighter or looser engine. Clamped at zero.
    """

    if peak_pressure_Pa < 0.0 or mean_piston_speed_m_s < 0.0:
        raise ValueError("Peak pressure and piston speed must be non-negative.")
    if multiplier < 0.0:
        raise ValueError("Friction multiplier must be >= 0.")

    p_max_bar = peak_pressure_Pa / 1.0e5
    cm = mean_piston_speed_m_s
    fmep_bar = (
        _A_BAR
        + _B * p_max_bar
        + _C_BAR_S_PER_M * cm
        + _D_BAR_S2_PER_M2 * cm * cm
    )
    return max(0.0, fmep_bar * multiplier) * 1.0e5
