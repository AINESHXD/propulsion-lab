"""Integration tests for non-turbojet educational cycle solvers."""

from app.main import simulate_ramjet, simulate_scramjet, simulate_turbofan, simulate_turboprop
from app.schemas import RamjetInput, ScramjetInput, TurbofanInput, TurbopropInput


def test_turbofan_cycle_outputs_positive_performance() -> None:
    """Separate-flow turbofan route helper should produce thrust and core/bypass stations."""

    result = simulate_turbofan(TurbofanInput())

    assert result.engine_type == "turbofan"
    assert result.thrust_N > 0.0
    assert result.fuel_air_ratio > 0.0
    assert result.TSFC_kg_per_N_s > 0.0
    assert {0, 2, 13, 3, 4, 5, 9, 19}.issubset(result.station_table)
    assert result.extra["bypass_ratio"] == 5.0


def test_turboprop_cycle_outputs_shaft_power_and_thrust() -> None:
    """Turboprop route helper should include propeller thrust and shaft power."""

    result = simulate_turboprop(TurbopropInput())

    assert result.engine_type == "turboprop"
    assert result.thrust_N > 0.0
    assert result.fuel_air_ratio > 0.0
    assert result.shaft_power_W is not None
    assert result.shaft_power_W > 0.0
    assert result.propeller_thrust_N is not None
    assert result.propeller_thrust_N > 0.0
    assert {0, 2, 3, 4, 5, 9}.issubset(result.station_table)


def test_ramjet_cycle_outputs_positive_performance() -> None:
    """Ramjet route helper should produce useful thrust at supersonic flight speed."""

    result = simulate_ramjet(RamjetInput())

    assert result.engine_type == "ramjet"
    assert result.thrust_N > 0.0
    assert result.exit_velocity_m_s > result.freestream_velocity_m_s
    assert result.fuel_air_ratio > 0.0
    assert {0, 2, 4, 9}.issubset(result.station_table)


def test_scramjet_cycle_outputs_positive_performance() -> None:
    """Scramjet route helper should produce a valid first-order hypersonic cycle."""

    result = simulate_scramjet(ScramjetInput())

    assert result.engine_type == "scramjet"
    assert result.thrust_N > 0.0
    assert result.fuel_air_ratio > 0.0
    assert result.extra["combustor_mode"] == "supersonic"
    assert {0, 2, 3, 4, 9}.issubset(result.station_table)
