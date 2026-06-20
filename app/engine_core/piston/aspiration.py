"""Aspiration: naturally aspirated, turbocharged, supercharged.

Boost raises the manifold (intake) pressure, which packs a denser charge into
the cylinder, so more fuel can be burned and both IMEP and power rise. The
crucial difference between the two ways of making boost is *who pays for it*:

* **Turbocharger** — the compressor is driven by a turbine in the exhaust, i.e.
  by energy that would otherwise leave as waste heat. To a first cut it costs
  the crankshaft nothing (the real penalty is exhaust back-pressure, modelled
  separately through the exhaust pressure / pumping loop).
* **Supercharger** — the compressor is belt-driven straight off the crankshaft,
  so its compression work is a **parasitic load that comes straight out of
  brake power**.

This module computes the supercharger's parasitic power: the (isentropic,
efficiency-derated) work to compress the inducted air from ambient up to the
manifold pressure.
"""

from __future__ import annotations

ASPIRATION_MODES = ("naturally_aspirated", "turbocharged", "supercharged")

_GAMMA_AIR = 1.4          # fresh air being compressed (not burned charge)


def supercharger_power_W(
    air_mass_flow_kg_s: float,
    inlet_temperature_K: float,
    pressure_ratio: float,
    efficiency: float,
    gas_constant_J_per_kg_K: float = 287.0,
) -> float:
    """Parasitic power [W] to drive a supercharger to ``pressure_ratio``.

    Isentropic compression work per unit mass, derated by the supercharger's
    isentropic efficiency, times the air mass flow it delivers. Returns 0 when
    there is no boost (pressure ratio <= 1).
    """

    if efficiency <= 0.0 or efficiency > 1.0:
        raise ValueError("Supercharger efficiency must be in (0, 1].")
    if pressure_ratio <= 1.0 or air_mass_flow_kg_s <= 0.0:
        return 0.0

    cp = _GAMMA_AIR * gas_constant_J_per_kg_K / (_GAMMA_AIR - 1.0)
    ideal_work_per_kg = cp * inlet_temperature_K * (
        pressure_ratio ** ((_GAMMA_AIR - 1.0) / _GAMMA_AIR) - 1.0
    )
    return air_mass_flow_kg_s * ideal_work_per_kg / efficiency
