"""International Standard Atmosphere utilities for PropulsionLab.

The implementation covers the troposphere and lower stratosphere to 25 km,
which is enough for the v1 educational turbojet cycle envelope.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.engine_core.constants import P_SL, T_SL, L_lapse, R_air, g0, gamma_air
from app.engine_core.gas_properties import speed_of_sound


@dataclass(slots=True, frozen=True)
class AtmosphereState:
    """Static ambient atmosphere state."""

    temperature_K: float
    pressure_Pa: float
    density_kg_m3: float
    speed_of_sound_m_s: float


def isa_atmosphere(altitude_m: float) -> AtmosphereState:
    """Return ISA static atmosphere properties from sea level to 25 km.

    The troposphere model is used through 11 km. Above 11 km, the model uses an
    isothermal lower-stratosphere layer at 216.65 K.
    """

    if altitude_m <= 11000.0:
        temperature_K = T_SL - L_lapse * altitude_m
        pressure_Pa = P_SL * (temperature_K / T_SL) ** (g0 / (R_air * L_lapse))
    else:
        tropopause_temperature_K = T_SL - L_lapse * 11000.0
        tropopause_pressure_Pa = P_SL * (tropopause_temperature_K / T_SL) ** (
            g0 / (R_air * L_lapse)
        )
        temperature_K = tropopause_temperature_K
        pressure_Pa = tropopause_pressure_Pa * float(
            np.exp(-g0 * (altitude_m - 11000.0) / (R_air * temperature_K))
        )

    density_kg_m3 = pressure_Pa / (R_air * temperature_K)
    return AtmosphereState(
        temperature_K=temperature_K,
        pressure_Pa=pressure_Pa,
        density_kg_m3=density_kg_m3,
        speed_of_sound_m_s=speed_of_sound(temperature_K, gamma_air, R_air),
    )
