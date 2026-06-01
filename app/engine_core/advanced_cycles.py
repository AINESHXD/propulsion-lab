"""Backward-compatible facade for the advanced (non-turbojet) cycle solvers.

The detailed implementations now live in dedicated modules:

* ``turbofan.py`` — two-spool turbofan with mixed/unmixed + optional AB.
* ``turboprop.py`` — gas-generator + free power turbine + propeller curve.
* ``ramjet.py``  — MIL-spec inlet recovery + Rayleigh thermal-choke check.
* ``scramjet.py`` — multi-shock inlet KE + supersonic combustor + reduced-order.

This module re-exports their entry points so callers that import
``simulate_turbofan_cycle`` etc. from ``advanced_cycles`` continue to work
unchanged. Older private helpers (``_isentropic_compression``,
``_expand_nozzle_stream``, ``_efficiencies``, ``_station_table``) are kept as
thin shims around the new shared utilities.
"""

from __future__ import annotations

from typing import Any

# Shared utilities — re-exported for any legacy importers.
from app.engine_core.streams import (  # noqa: F401
    NozzleStreamResult,
    compute_stream_efficiencies as _efficiencies_v2,
    expand_nozzle_stream as _expand_nozzle_stream_v2,
    station_table as _station_table_v2,
)

# Engine entry points (new modular implementations).
from app.engine_core.ramjet import simulate_ramjet_cycle  # noqa: F401
from app.engine_core.scramjet import simulate_scramjet_cycle  # noqa: F401
from app.engine_core.turbofan import simulate_turbofan_cycle  # noqa: F401
from app.engine_core.turboprop import simulate_turboprop_cycle  # noqa: F401

# ---- Legacy shims kept verbatim for old call sites ------------------------


def _station_table(*states: Any) -> dict[int, dict[str, Any]]:
    """Legacy alias for :func:`app.engine_core.streams.station_table`."""

    return _station_table_v2(*states)


def _efficiencies(
    thrust_N: float,
    freestream_velocity_m_s: float,
    fuel_flow_kg_s: float,
    fuel_heating_value_J_kg: float,
    jet_power_change_W: float,
    pressure_thrust_power_W: float,
) -> dict[str, float]:
    """Legacy alias for :func:`compute_stream_efficiencies`."""

    return _efficiencies_v2(
        thrust_N=thrust_N,
        freestream_velocity_m_s=freestream_velocity_m_s,
        fuel_flow_kg_s=fuel_flow_kg_s,
        fuel_heating_value_J_kg=fuel_heating_value_J_kg,
        jet_kinetic_power_change_W=jet_power_change_W,
        pressure_thrust_power_W=pressure_thrust_power_W,
    )


__all__ = [
    "simulate_turbofan_cycle",
    "simulate_turboprop_cycle",
    "simulate_ramjet_cycle",
    "simulate_scramjet_cycle",
    "_station_table",
    "_efficiencies",
]
