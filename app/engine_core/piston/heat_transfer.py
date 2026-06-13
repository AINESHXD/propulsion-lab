"""In-cylinder wall heat transfer (Woschni correlation).

The closed cycle of :mod:`cycle` is adiabatic — all the fuel energy goes to work
or stays in the gas. A real engine dumps a large share of the heat into the
cylinder walls, which is why measured efficiency is well below the air-standard
ceiling. This module adds that loss with the standard **Woschni** convective
heat-transfer coefficient::

    h = C * B**(-0.2) * p**0.8 * T**(-0.53) * w**0.8        [W/m^2.K]

with bore ``B`` [m], pressure ``p`` [kPa], gas temperature ``T`` [K] and a
characteristic gas velocity ``w`` [m/s]. The velocity has a piston-motion term
and a combustion-driven term::

    w = C1 * Sp_mean + C2 * (V_d * T_ivc) / (p_ivc * V_ivc) * (p - p_motored)

``Sp_mean`` is the mean piston speed; the second term switches on during
combustion and expansion (``p`` above the motored pressure ``p_motored``) and is
zero during pure compression. ``p_motored`` is the isentropic motored reference
``p_ivc * (V_ivc / V)**gamma``.

The instantaneous heat-loss surface is the head, the piston crown and the
exposed liner::

    A_wall(V) = pi/2 * B**2 + 4 * V / B
"""

from __future__ import annotations

import math

# Woschni constants (SI, pressure in kPa).
_C = 3.26
_C1 = 2.28           # piston-motion term (compression / combustion / expansion)
_C2 = 3.24e-3        # combustion term (active once burning)


def wall_surface_area_m2(volume_m3: float, bore_m: float) -> float:
    """Heat-loss surface (head + crown + exposed liner) at cylinder ``volume``."""

    return 0.5 * math.pi * bore_m**2 + 4.0 * volume_m3 / bore_m


def woschni_velocity(
    mean_piston_speed_m_s: float,
    pressure_Pa: float,
    motored_pressure_Pa: float,
    displacement_m3: float,
    ref_temperature_K: float,
    ref_pressure_Pa: float,
    ref_volume_m3: float,
    burning: bool,
) -> float:
    """Woschni characteristic gas velocity ``w`` [m/s].

    The combustion term is included only while ``burning`` (during combustion
    and expansion); during compression it is zero and ``w`` is just the
    piston-motion term.
    """

    w = _C1 * mean_piston_speed_m_s
    if burning:
        w += (
            _C2
            * (displacement_m3 * ref_temperature_K) / (ref_pressure_Pa * ref_volume_m3)
            * max(0.0, pressure_Pa - motored_pressure_Pa)
        )
    return w


def woschni_coefficient(
    bore_m: float,
    pressure_Pa: float,
    temperature_K: float,
    gas_velocity_m_s: float,
) -> float:
    """Woschni convective heat-transfer coefficient ``h`` [W/m^2.K].

    Pressure is converted to kPa for the classic ``C = 3.26`` constant. Returns
    0 for a non-positive velocity (e.g. a motionless reference state).
    """

    if gas_velocity_m_s <= 0.0 or pressure_Pa <= 0.0 or temperature_K <= 0.0:
        return 0.0
    p_kpa = pressure_Pa / 1000.0
    return (
        _C
        * bore_m ** (-0.2)
        * p_kpa ** 0.8
        * temperature_K ** (-0.53)
        * gas_velocity_m_s ** 0.8
    )
