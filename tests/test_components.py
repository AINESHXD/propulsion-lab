"""Component-level tests for the turbojet cycle."""

from app.engine_core.atmosphere import isa_atmosphere
from app.engine_core.combustor import calculate_combustor_exit
from app.engine_core.compressor import calculate_compressor_exit
from app.engine_core.inlet import calculate_freestream_state, calculate_inlet_exit
from app.engine_core.nozzle import calculate_nozzle_exit
from app.engine_core.turbine import calculate_turbine_exit
from app.engine_core.types import TurbojetCycleInputs


def _default_component_chain() -> dict[str, object]:
    """Build a default component chain for component tests."""

    inputs = TurbojetCycleInputs()
    atmosphere = isa_atmosphere(inputs.altitude_m)
    freestream = calculate_freestream_state(atmosphere, inputs.mach)
    inlet = calculate_inlet_exit(freestream.state, inputs.inlet_pressure_recovery)
    compressor = calculate_compressor_exit(
        inlet.state,
        inputs.compressor_pressure_ratio,
        inputs.compressor_efficiency,
    )
    combustor = calculate_combustor_exit(
        compressor.state,
        inputs.turbine_inlet_temperature_K,
        inputs.combustor_efficiency,
        inputs.combustor_pressure_loss_fraction,
        inputs.fuel_heating_value_J_kg,
    )
    turbine = calculate_turbine_exit(
        combustor.state,
        float(compressor.metadata["compressor_specific_work_J_kg"]),
        float(combustor.metadata["fuel_air_ratio"]),
        inputs.mechanical_efficiency,
        inputs.turbine_efficiency,
        atmosphere.pressure_Pa,
    )
    nozzle = calculate_nozzle_exit(
        turbine.state,
        atmosphere.pressure_Pa,
        inputs.mass_flow_air_kg_s,
        float(combustor.metadata["fuel_air_ratio"]),
        inputs.nozzle_efficiency,
        inputs.nozzle_exit_area_m2,
        inputs.include_pressure_thrust,
    )
    return {
        "inputs": inputs,
        "atmosphere": atmosphere,
        "freestream": freestream,
        "inlet": inlet,
        "compressor": compressor,
        "combustor": combustor,
        "turbine": turbine,
        "nozzle": nozzle,
    }


def test_compressor_raises_temperature_and_pressure() -> None:
    """Compressor station 3 should have higher Tt and Pt than station 2."""

    chain = _default_component_chain()
    inlet = chain["inlet"]
    compressor = chain["compressor"]

    assert compressor.state.stagnation_temperature_K > inlet.state.stagnation_temperature_K
    assert compressor.state.stagnation_pressure_Pa > inlet.state.stagnation_pressure_Pa


def test_combustor_adds_heat_and_loses_pressure() -> None:
    """Combustor should raise Tt, lose Pt, and produce positive fuel-air ratio."""

    chain = _default_component_chain()
    compressor = chain["compressor"]
    combustor = chain["combustor"]

    assert combustor.state.stagnation_temperature_K > compressor.state.stagnation_temperature_K
    assert float(combustor.metadata["fuel_air_ratio"]) > 0.0
    assert combustor.state.stagnation_pressure_Pa < compressor.state.stagnation_pressure_Pa


def test_turbine_extracts_work_and_loses_pressure() -> None:
    """Turbine station 5 should have lower Tt and Pt than station 4."""

    chain = _default_component_chain()
    combustor = chain["combustor"]
    turbine = chain["turbine"]

    assert turbine.state.stagnation_temperature_K < combustor.state.stagnation_temperature_K
    assert turbine.state.stagnation_pressure_Pa < combustor.state.stagnation_pressure_Pa


def test_nozzle_exit_velocity_exceeds_default_freestream_velocity() -> None:
    """Default nozzle exit velocity should exceed freestream velocity."""

    chain = _default_component_chain()
    freestream = chain["freestream"]
    nozzle = chain["nozzle"]

    assert float(nozzle.metadata["exit_velocity_m_s"]) > freestream.state.velocity_m_s

