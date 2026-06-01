"""Tests for the variable-cycle / 3-stream turbofan extension (Day 38).

The mode switch must change the thrust split and SFC: opening the third stream
(high-efficiency mode) raises total airflow and lowers both specific thrust and
SFC versus the closed (high-thrust) mode, which itself must be identical to the
plain two-stream turbofan. The third stream is pumped by the fan, so the gain is
energy-consistent, not free thrust.
"""

import pytest

from app.engine_core.off_design import calibrate_turbofan_reference
from app.engine_core.turbofan import TurbofanCycleInputs, simulate_turbofan_cycle
from app.engine_core.types import CycleCalculationError
from app.main import simulate_turbofan
from app.schemas import TurbofanInput

_THIRD = dict(third_stream=True, third_stream_ratio=0.6, third_stream_pressure_ratio=1.3)


def test_default_turbofan_has_no_third_stream() -> None:
    r = simulate_turbofan_cycle(TurbofanCycleInputs())
    assert r["third_stream_thrust_N"] == 0.0
    assert r["extra"]["third_stream_active"] is False


def test_high_thrust_mode_matches_plain_two_stream() -> None:
    plain = simulate_turbofan_cycle(TurbofanCycleInputs())
    closed = simulate_turbofan_cycle(
        TurbofanCycleInputs(**_THIRD, variable_cycle_mode="high_thrust")
    )
    assert closed["thrust_kN"] == pytest.approx(plain["thrust_kN"], rel=1e-12)
    assert closed["TSFC_kg_per_kN_hr"] == pytest.approx(plain["TSFC_kg_per_kN_hr"], rel=1e-12)
    assert closed["third_stream_thrust_N"] == 0.0


def test_high_efficiency_mode_lowers_sfc_and_specific_thrust() -> None:
    closed = simulate_turbofan_cycle(
        TurbofanCycleInputs(**_THIRD, variable_cycle_mode="high_thrust")
    )
    openm = simulate_turbofan_cycle(
        TurbofanCycleInputs(**_THIRD, variable_cycle_mode="high_efficiency")
    )
    assert openm["TSFC_kg_per_kN_hr"] < closed["TSFC_kg_per_kN_hr"]
    assert openm["specific_thrust_N_per_kg_s"] < closed["specific_thrust_N_per_kg_s"]
    assert openm["third_stream_thrust_N"] > 0.0
    assert openm["extra"]["effective_bypass_ratio"] > openm["extra"]["bypass_ratio"]
    assert openm["extra"]["total_air_with_third_kg_s"] > closed["extra"]["total_air_with_third_kg_s"]
    # Third-stream nozzle station appears in the table.
    assert 29 in openm["station_table"]


def test_third_stream_thrust_is_not_free() -> None:
    """Opening the stream must cost LP-turbine work: core jet velocity drops."""

    closed = simulate_turbofan_cycle(
        TurbofanCycleInputs(**_THIRD, variable_cycle_mode="high_thrust")
    )
    openm = simulate_turbofan_cycle(
        TurbofanCycleInputs(**_THIRD, variable_cycle_mode="high_efficiency")
    )
    # Same core and fuel (third stream adds no fuel).
    assert openm["fuel_flow_kg_s"] == pytest.approx(closed["fuel_flow_kg_s"], rel=1e-9)
    # The LP turbine works harder, so the core nozzle exit velocity falls.
    assert openm["exit_velocity_m_s"] < closed["exit_velocity_m_s"]


def test_third_stream_rejected_with_mixed_flow() -> None:
    with pytest.raises(CycleCalculationError):
        simulate_turbofan_cycle(
            TurbofanCycleInputs(nozzle_configuration="mixed", **_THIRD)
        )


def test_third_stream_rejected_with_afterburner() -> None:
    with pytest.raises(CycleCalculationError):
        simulate_turbofan_cycle(
            TurbofanCycleInputs(
                use_afterburner=True, afterburner_exit_temperature_K=2000.0, **_THIRD
            )
        )


def test_third_stream_exposed_through_api() -> None:
    result = simulate_turbofan(TurbofanInput(**_THIRD))
    assert result.third_stream_thrust_N is not None and result.third_stream_thrust_N > 0.0
    assert result.extra["third_stream_active"] is True
    assert result.extra["variable_cycle_mode"] == "high_efficiency"


def test_off_design_rejects_open_third_stream() -> None:
    with pytest.raises(CycleCalculationError):
        calibrate_turbofan_reference(TurbofanCycleInputs(**_THIRD))
