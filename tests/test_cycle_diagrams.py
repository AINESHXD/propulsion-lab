"""Cycle-diagram thermodynamics (T-s / P-v).

The T-s and P-v diagrams in the console are drawn from a stagnation-property
computation in the frontend (``stationThermoProperties`` in app.js):

    s = cp·ln(Tt/Tref) − R·ln(Pt/Pref)        [relative datum]
    v = R·Tt / Pt                              (ideal gas, stagnation)

There is no JS test runner in this project, so this module mirrors that exact
formula in Python and asserts the diagrams' UNDERLYING thermodynamics produce a
correct Brayton cycle topology on real solver output. It catches a regression in
the station data that would make the plotted cycle physically wrong.
"""

from __future__ import annotations

import math

from app.engine_core.constants import R_air, cp_air, cp_gas
from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import TurbojetCycleInputs

_TREF_K = 288.15
_PREF_PA = 101325.0


def _stations() -> dict[int, dict]:
    result = simulate_turbojet_cycle(TurbojetCycleInputs(
        altitude_m=10000.0, mach=0.85, compressor_pressure_ratio=14.0,
        turbine_inlet_temperature_K=1500.0))
    return result["station_table"]


def _cp(station: int) -> float:
    return cp_gas if (station >= 4 and station not in (13, 19)) else cp_air


def _entropy(st: dict, station: int) -> float:
    Tt = st[station]["stagnation_temperature_K"]
    Pt = st[station]["stagnation_pressure_Pa"]
    return _cp(station) * math.log(Tt / _TREF_K) - R_air * math.log(Pt / _PREF_PA)


def _specific_volume(st: dict, station: int) -> float:
    Tt = st[station]["stagnation_temperature_K"]
    Pt = st[station]["stagnation_pressure_Pa"]
    return R_air * Tt / Pt


def test_specific_volume_is_ideal_gas_and_positive() -> None:
    st = _stations()
    for station, data in st.items():
        v = _specific_volume(st, station)
        expected = R_air * data["stagnation_temperature_K"] / data["stagnation_pressure_Pa"]
        assert v == expected and v > 0.0


def test_compression_reduces_specific_volume_and_raises_pressure() -> None:
    st = _stations()
    assert st[3]["stagnation_pressure_Pa"] > st[2]["stagnation_pressure_Pa"]
    assert st[3]["stagnation_temperature_K"] > st[2]["stagnation_temperature_K"]
    assert _specific_volume(st, 3) < _specific_volume(st, 2)


def test_combustion_adds_entropy_and_expands_gas() -> None:
    st = _stations()
    assert st[4]["stagnation_temperature_K"] > st[3]["stagnation_temperature_K"]
    assert _entropy(st, 4) > _entropy(st, 3)            # heat addition raises s
    assert _specific_volume(st, 4) > _specific_volume(st, 3)


def test_turbine_expands_and_cools() -> None:
    st = _stations()
    assert st[5]["stagnation_temperature_K"] < st[4]["stagnation_temperature_K"]
    assert st[5]["stagnation_pressure_Pa"] < st[4]["stagnation_pressure_Pa"]
    assert _specific_volume(st, 5) > _specific_volume(st, 4)


def test_entropy_is_monotonic_non_decreasing_through_core() -> None:
    """Each component is irreversible, so stagnation entropy never falls along
    the core path 2 -> 3 -> 4 -> 5."""

    st = _stations()
    chain = [_entropy(st, s) for s in (2, 3, 4, 5)]
    for earlier, later in zip(chain, chain[1:]):
        assert later >= earlier - 1e-9
    # Combustion is the dominant entropy rise.
    assert (_entropy(st, 4) - _entropy(st, 3)) > 0.5 * (chain[-1] - chain[0])
