"""Integration tests for the full turbojet solver."""

from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import TurbojetCycleInputs
from app.main import (
    simulate_turbojet,
    simulate_turbojet_from_profile,
    simulate_turbojet_sweep,
    turbojet_pdf_report,
)
from app.schemas import CustomJetProfileInput, TurbojetInput, TurbojetSweepInput


def test_default_turbojet_simulation_outputs_positive_performance() -> None:
    """Default cycle should produce positive thrust, fuel flow, and all stations."""

    result = simulate_turbojet_cycle(TurbojetCycleInputs())

    assert result["thrust_N"] > 0.0
    assert result["fuel_air_ratio"] > 0.0
    assert result["TSFC_kg_per_N_s"] > 0.0
    assert {0, 2, 3, 4, 5, 9}.issubset(result["station_table"])


def test_default_turbojet_tsfc_and_nozzle_metadata_are_reasonable() -> None:
    """Default case should expose reasonable TSFC units and nozzle metadata."""

    result = simulate_turbojet_cycle(TurbojetCycleInputs())

    assert 0.0 < result["TSFC_kg_per_kN_hr"] < 1000.0
    assert result["nozzle_exit_area_m2"] > 0.0
    assert result["estimated_nozzle_exit_area_m2"] > 0.0
    assert result["nozzle_throat_area_m2"] > 0.0
    assert result["nozzle_area_ratio"] >= 1.0
    assert result["nozzle_pressure_ratio"] > 1.0
    assert result["nozzle_expansion_status"] in {
        "Ideally expanded approximately",
        "Underexpanded",
        "Overexpanded",
    }


def test_old_turbojet_api_payload_remains_backward_compatible() -> None:
    """Older requests without new optional nozzle fields should still run."""

    output = simulate_turbojet(
        TurbojetInput(
            altitude_m=10000.0,
            mach=0.8,
            mass_flow_air_kg_s=50.0,
            compressor_pressure_ratio=12.0,
            turbine_inlet_temperature_K=1400.0,
        )
    )

    assert output.thrust_N > 0.0
    assert output.nozzle_exit_area_m2 is not None


def test_afterburning_turbojet_adds_reheat_station_and_fuel() -> None:
    """Afterburning variant should add station 7 and increase total fuel ratio."""

    dry_result = simulate_turbojet_cycle(TurbojetCycleInputs())
    afterburning_result = simulate_turbojet_cycle(
        TurbojetCycleInputs(
            engine_variant="afterburning_turbojet",
            afterburner_exit_temperature_K=1800.0,
        )
    )

    assert afterburning_result["engine_variant"] == "afterburning_turbojet"
    assert 7 in afterburning_result["station_table"]
    assert afterburning_result["afterburner_fuel_air_ratio"] > 0.0
    assert afterburning_result["fuel_air_ratio"] > dry_result["fuel_air_ratio"]
    assert afterburning_result["thrust_N"] > 0.0


def test_custom_profile_simulation_returns_named_output() -> None:
    """Custom profile endpoint helper should simulate user-defined profiles."""

    result = simulate_turbojet_from_profile(
        CustomJetProfileInput(
            name="Test Reheat Profile",
            engine_type="afterburning_turbojet",
            default_inputs=TurbojetInput(
                engine_variant="afterburning_turbojet",
                afterburner_exit_temperature_K=1750.0,
            ),
        )
    )

    assert result.profile_name == "Test Reheat Profile"
    assert result.engine_type == "afterburning_turbojet"
    assert result.output.thrust_N > 0.0
    assert result.output.afterburner_fuel_air_ratio > 0.0


def test_inlet_area_mass_flow_mode_changes_effective_mass_flow() -> None:
    """Inlet area mode should estimate mass flow from freestream conditions."""

    result = simulate_turbojet_cycle(
        TurbojetCycleInputs(
            mach=0.7,
            inlet_capture_area_m2=1.2,
            use_inlet_area_mass_flow=True,
        )
    )

    assert result["effective_mass_flow_air_kg_s"] > 0.0
    assert result["effective_mass_flow_air_kg_s"] != 50.0
    assert result["thrust_N"] > 0.0


def test_implausibly_large_inlet_capture_area_raises_caution() -> None:
    """A capture area far larger than any real engine should run but flag a caution."""

    result = simulate_turbojet_cycle(
        TurbojetCycleInputs(
            mach=0.7,
            inlet_capture_area_m2=500.0,
            use_inlet_area_mass_flow=True,
        )
    )

    assert any(
        "far larger than any real engine" in warning for warning in result["warnings"]
    )


def test_non_positive_areas_are_rejected_by_schema() -> None:
    """Zero or negative geometric areas must never reach the solver."""

    import pytest
    from pydantic import ValidationError

    for field in (
        "inlet_capture_area_m2",
        "nozzle_exit_area_m2",
        "nozzle_throat_area_m2",
    ):
        with pytest.raises(ValidationError):
            TurbojetInput(**{field: 0.0})
        with pytest.raises(ValidationError):
            TurbojetInput(**{field: -1.0})


def test_pdf_report_endpoint_returns_pdf_bytes() -> None:
    """PDF report helper should return a PDF response for valid inputs."""

    response = turbojet_pdf_report(TurbojetInput())

    assert response.media_type == "application/pdf"
    assert response.body.startswith(b"%PDF-")


def test_turbojet_sweep_returns_one_case_per_value() -> None:
    """Sweep endpoint helper should return successful outputs for valid values."""

    result = simulate_turbojet_sweep(
        TurbojetSweepInput(
            sweep_parameter="compressor_pressure_ratio",
            values=[8.0, 12.0, 16.0],
        )
    )

    assert len(result.cases) == 3
    assert result.summary.successful_cases == 3
    assert result.summary.failed_cases == 0
    assert result.summary.max_thrust_N is not None
    assert result.summary.max_thrust_N > 0.0


def test_turbojet_sweep_keeps_going_after_invalid_case() -> None:
    """Invalid sweep values should be reported per case instead of aborting."""

    result = simulate_turbojet_sweep(
        TurbojetSweepInput(
            sweep_parameter="compressor_pressure_ratio",
            values=[0.5, 12.0],
        )
    )

    assert len(result.cases) == 2
    assert result.summary.successful_cases == 1
    assert result.summary.failed_cases == 1
    assert result.cases[0].success is False
    assert result.cases[1].success is True
