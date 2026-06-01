"""Top-level turbojet cycle orchestration."""

from __future__ import annotations

from typing import Any

from app.engine_core.afterburner import calculate_afterburner_exit
from app.engine_core.atmosphere import isa_atmosphere
from app.engine_core.combustor import calculate_combustor_exit
from app.engine_core.combustor_equilibrium import (
    calculate_combustor_exit_equilibrium,
)
from app.engine_core.compressor import calculate_compressor_exit
from app.engine_core.secondary_air import apply_bleed_and_cooling
from app.engine_core.inlet import calculate_freestream_state, calculate_inlet_exit
from app.engine_core.nozzle import calculate_nozzle_exit
from app.engine_core.performance import compute_turbojet_performance
from app.engine_core.real_gas import hot_section_temperatures
from app.engine_core.turbine import calculate_turbine_exit
from app.engine_core.types import CycleCalculationError, StationState, TurbojetCycleInputs


def _merge_warnings(*warning_groups: list[str]) -> list[str]:
    """Merge warning lists while preserving first occurrence order."""

    merged: list[str] = []
    for group in warning_groups:
        for warning in group:
            if warning not in merged:
                merged.append(warning)
    return merged


def _station_table(*states: StationState) -> dict[int, dict[str, Any]]:
    """Build a station table keyed by gas turbine station number."""

    return {state.station: state.to_dict() for state in states}


def _engineering_warnings(
    inputs: TurbojetCycleInputs,
    fuel_air_ratio: float,
    nozzle_metadata: dict[str, float | bool | str],
    performance: dict[str, float],
    ambient_pressure_Pa: float,
) -> list[str]:
    """Generate DAS LABS engineering checks from cycle-level results."""

    warnings: list[str] = []
    if inputs.turbine_inlet_temperature_K > 1650.0 and inputs.engine_variant == "turbojet":
        warnings.append(
            "CAUTION: Turbine inlet temperature is unusually high for an educational dry turbojet."
        )
    if inputs.compressor_pressure_ratio > 18.0 and inputs.engine_variant == "turbojet":
        warnings.append(
            "CAUTION: Compressor pressure ratio is high for a simple turbojet model."
        )
    if bool(nozzle_metadata["nozzle_choked"]):
        warnings.append("INFO: Nozzle is choked.")
    if fuel_air_ratio < 0.008 or fuel_air_ratio > 0.055:
        warnings.append("CAUTION: Fuel-air ratio is outside the typical educational range.")
    exit_pressure = float(nozzle_metadata["nozzle_exit_pressure_Pa"])
    if abs(exit_pressure - ambient_pressure_Pa) / ambient_pressure_Pa > 0.35:
        warnings.append(
            "CAUTION: Nozzle exit pressure differs strongly from ambient pressure."
        )
    if abs(performance["pressure_thrust_N"]) > abs(performance["momentum_thrust_N"]):
        warnings.append("CRITICAL: Pressure thrust exceeds momentum thrust; check nozzle area.")
    if inputs.inlet_pressure_recovery < 0.92 and inputs.mach > 1.0:
        warnings.append("CAUTION: Supersonic inlet recovery is low; shock losses are simplified.")
    return warnings


def simulate_turbojet_cycle(inputs: TurbojetCycleInputs) -> dict[str, Any]:
    """Run the complete station-based turbojet cycle.

    The calculation is an educational steady 1D perfect-gas model. It includes
    component losses but does not include compressor maps, turbine maps,
    detailed chemical equilibrium, blade-row aerodynamics, or transient spool
    dynamics.
    """

    atmosphere = isa_atmosphere(inputs.altitude_m)

    freestream = calculate_freestream_state(atmosphere, inputs.mach)
    mass_flow_air_kg_s = inputs.mass_flow_air_kg_s
    mass_flow_warnings: list[str] = []
    if inputs.use_inlet_area_mass_flow:
        if inputs.inlet_capture_area_m2 is None:
            raise CycleCalculationError(
                "Inlet capture area must be supplied when inlet-area mass flow is enabled."
            )
        estimated_mass_flow_air_kg_s = (
            atmosphere.density_kg_m3
            * (freestream.state.velocity_m_s or 0.0)
            * inputs.inlet_capture_area_m2
        )
        if estimated_mass_flow_air_kg_s <= 0.0:
            raise CycleCalculationError(
                "Inlet-area mass flow estimate is non-positive; check Mach and area."
            )
        mass_flow_air_kg_s = estimated_mass_flow_air_kg_s
        mass_flow_warnings.append(
            "Air mass flow was estimated from ambient density, freestream velocity, "
            "and inlet capture area."
        )
        if inputs.inlet_capture_area_m2 > 25.0:
            mass_flow_warnings.append(
                "CAUTION: Inlet capture area is far larger than any real engine; "
                "the estimated air mass flow may be non-physical."
            )
    inlet = calculate_inlet_exit(freestream.state, inputs.inlet_pressure_recovery)
    compressor = calculate_compressor_exit(
        inlet.state,
        inputs.compressor_pressure_ratio,
        inputs.compressor_efficiency,
    )
    # ---- Bleed and cooling fractions (HPC exit) ---------------------------
    # Customer / overboard bleed leaves the engine; HPT cooling air is routed
    # around the combustor and re-introduced at the turbine inlet. Shared with
    # the turbofan and turboprop solvers via secondary_air.apply_bleed_and_cooling.
    bleed_fraction = inputs.bleed_fraction_hpc_exit
    cooling_fraction = inputs.cooling_fraction_hpt_inlet
    if (bleed_fraction > 0.0 or cooling_fraction > 0.0) and (
        inputs.engine_variant == "afterburning_turbojet"
    ):
        raise CycleCalculationError(
            "Bleed and cooling fractions are not yet supported with afterburning."
        )

    if inputs.use_equilibrium_combustion:
        combustor = calculate_combustor_exit_equilibrium(
            compressor.state,
            inputs.turbine_inlet_temperature_K,
            inputs.combustor_efficiency,
            inputs.combustor_pressure_loss_fraction,
            inputs.fuel_heating_value_J_kg,
            fuel=inputs.equilibrium_fuel_species,
        )
    else:
        combustor = calculate_combustor_exit(
            compressor.state,
            inputs.turbine_inlet_temperature_K,
            inputs.combustor_efficiency,
            inputs.combustor_pressure_loss_fraction,
            inputs.fuel_heating_value_J_kg,
        )
    fuel_air_ratio = float(combustor.metadata["fuel_air_ratio"])
    core_fuel_air_ratio = fuel_air_ratio
    afterburner_fuel_air_ratio = 0.0
    compressor_specific_work = float(compressor.metadata["compressor_specific_work_J_kg"])

    secondary = apply_bleed_and_cooling(
        reference_air_kg_s=mass_flow_air_kg_s,
        compressor_exit_state=compressor.state,
        combustor_exit_state=combustor.state,
        fuel_air_ratio=fuel_air_ratio,
        bleed_fraction=bleed_fraction,
        cooling_fraction=cooling_fraction,
    )
    combustor_air_kg_s = secondary.combustor_air_kg_s
    hpt_inlet_kg_s = secondary.hpt_inlet_kg_s

    turbine = calculate_turbine_exit(
        secondary.turbine_inlet_state,
        compressor_specific_work,
        fuel_air_ratio,
        inputs.mechanical_efficiency,
        inputs.turbine_efficiency,
        atmosphere.pressure_Pa,
        gas_mass_flow_ratio=secondary.gas_mass_flow_ratio,
    )

    nozzle_inlet_state = turbine.state
    afterburner_warnings: list[str] = []
    afterburner_state: StationState | None = None
    if inputs.engine_variant == "afterburning_turbojet":
        afterburner_exit_temperature_K = inputs.afterburner_exit_temperature_K or 1800.0
        afterburner = calculate_afterburner_exit(
            turbine.state,
            core_fuel_air_ratio,
            afterburner_exit_temperature_K,
            inputs.afterburner_efficiency,
            inputs.afterburner_pressure_loss_fraction,
            inputs.fuel_heating_value_J_kg,
        )
        fuel_air_ratio = float(afterburner.metadata["total_fuel_air_ratio"])
        afterburner_fuel_air_ratio = float(afterburner.metadata["afterburner_fuel_air_ratio"])
        nozzle_inlet_state = afterburner.state
        afterburner_state = afterburner.state
        afterburner_warnings = afterburner.warnings
    elif inputs.engine_variant != "turbojet":
        raise CycleCalculationError(f"Unsupported engine variant: {inputs.engine_variant}")

    # Exit mass flow = HPT mass flow + afterburner fuel (no further bleed).
    # The AB module currently defines its FAR against the engine inlet air;
    # since bleed/cooling + afterburner is rejected upstream, the air-basis
    # term is correct on the only reachable path.
    exit_mass_flow_kg_s = hpt_inlet_kg_s + afterburner_fuel_air_ratio * mass_flow_air_kg_s
    # Total combustion + reheat fuel flow (excludes customer bleed which never
    # sees the combustor).
    total_fuel_flow_kg_s = (
        core_fuel_air_ratio * combustor_air_kg_s
        + afterburner_fuel_air_ratio * mass_flow_air_kg_s
    )

    nozzle = calculate_nozzle_exit(
        nozzle_inlet_state,
        atmosphere.pressure_Pa,
        mass_flow_air_kg_s,
        fuel_air_ratio,
        inputs.nozzle_efficiency,
        inputs.nozzle_exit_area_m2,
        inputs.include_pressure_thrust,
        inputs.nozzle_throat_area_m2,
        gas_mass_flow_ratio=exit_mass_flow_kg_s / mass_flow_air_kg_s,
    )

    performance, performance_warnings = compute_turbojet_performance(
        mass_flow_air_kg_s=mass_flow_air_kg_s,
        fuel_air_ratio=fuel_air_ratio,
        fuel_heating_value_J_kg=inputs.fuel_heating_value_J_kg,
        freestream_velocity_m_s=freestream.state.velocity_m_s or 0.0,
        exit_velocity_m_s=float(nozzle.metadata["exit_velocity_m_s"]),
        pressure_thrust_N=float(nozzle.metadata["pressure_thrust_N"]),
        fuel_flow_kg_s_override=total_fuel_flow_kg_s,
        exit_mass_flow_kg_s_override=exit_mass_flow_kg_s,
    )

    warnings = _merge_warnings(
        freestream.warnings,
        mass_flow_warnings,
        inlet.warnings,
        compressor.warnings,
        combustor.warnings,
        turbine.warnings,
        afterburner_warnings,
        nozzle.warnings,
        performance_warnings,
        _engineering_warnings(
            inputs,
            fuel_air_ratio,
            nozzle.metadata,
            performance,
            atmosphere.pressure_Pa,
        ),
    )

    station_states = [
        freestream.state,
        inlet.state,
        compressor.state,
        combustor.state,
        turbine.state,
    ]
    if afterburner_state is not None:
        station_states.append(afterburner_state)
    station_states.append(nozzle.state)

    # ---- Optional real-gas hot-section correction (Day 19) ----------------
    # Recompute turbine-exit and nozzle-exit temperatures with variable-cp
    # burned-gas properties for the *same* turbine work. Additive and default
    # off; the core constant-cp station table above is unchanged. The dry
    # turbojet has a single turbine, so all the work is "HPT" and LPT work is 0.
    real_gas_hot_section: dict[str, Any] | None = None
    if getattr(inputs, "real_gas", False) and inputs.engine_variant == "turbojet" \
            and core_fuel_air_ratio > 0.0:
        turbine_specific_work = compressor_specific_work / (
            secondary.gas_mass_flow_ratio * inputs.mechanical_efficiency
        )
        try:
            hot = hot_section_temperatures(
                turbine_inlet_temperature_K=secondary.turbine_inlet_state.stagnation_temperature_K,
                turbine_inlet_pressure_Pa=combustor.state.stagnation_pressure_Pa,
                hpt_exit_pressure_Pa=turbine.state.stagnation_pressure_Pa,
                lpt_exit_pressure_Pa=turbine.state.stagnation_pressure_Pa,
                nozzle_exit_pressure_Pa=float(nozzle.metadata["nozzle_exit_pressure_Pa"]),
                hpt_specific_work_J_per_kg=turbine_specific_work,
                lpt_specific_work_J_per_kg=0.0,
                fuel_air_ratio=core_fuel_air_ratio,
                nozzle_efficiency=inputs.nozzle_efficiency,
                mode="frozen",
            )
            real_gas_hot_section = {
                "turbine_exit_temperature_K": hot.hpt_exit_temperature_K,
                "nozzle_exit_static_temperature_K": hot.nozzle_exit_static_temperature_K,
                "nozzle_exit_velocity_m_s": hot.nozzle_exit_velocity_m_s,
                "constant_cp_turbine_exit_temperature_K": turbine.state.stagnation_temperature_K,
                "source": hot.source,
            }
        except Exception as exc:  # pragma: no cover - defensive, never break the run
            real_gas_hot_section = {"error": str(exc)}

    return {
        **performance,
        "engine_variant": inputs.engine_variant,
        "effective_mass_flow_air_kg_s": mass_flow_air_kg_s,
        "core_fuel_air_ratio": core_fuel_air_ratio,
        "afterburner_fuel_air_ratio": afterburner_fuel_air_ratio,
        "bleed_fraction_hpc_exit": bleed_fraction,
        "cooling_fraction_hpt_inlet": cooling_fraction,
        "combustor_air_mass_flow_kg_s": combustor_air_kg_s,
        "hpt_inlet_mass_flow_kg_s": hpt_inlet_kg_s,
        "hpt_inlet_stagnation_temperature_K": secondary.turbine_inlet_state.stagnation_temperature_K,
        "exit_velocity_m_s": float(nozzle.metadata["exit_velocity_m_s"]),
        "freestream_velocity_m_s": freestream.state.velocity_m_s or 0.0,
        "nozzle_choked": bool(nozzle.metadata["nozzle_choked"]),
        "nozzle_exit_pressure_Pa": float(nozzle.metadata["nozzle_exit_pressure_Pa"]),
        "ambient_pressure_Pa": atmosphere.pressure_Pa,
        "nozzle_exit_area_m2": float(nozzle.metadata["nozzle_exit_area_m2"]),
        "estimated_nozzle_exit_area_m2": float(
            nozzle.metadata["estimated_nozzle_exit_area_m2"]
        ),
        "nozzle_throat_area_m2": float(nozzle.metadata["nozzle_throat_area_m2"]),
        "nozzle_area_ratio": float(nozzle.metadata["nozzle_area_ratio"]),
        "nozzle_pressure_ratio": float(nozzle.metadata["nozzle_pressure_ratio"]),
        "nozzle_expansion_status": str(nozzle.metadata["nozzle_expansion_status"]),
        "station_table": _station_table(*station_states),
        "real_gas_hot_section": real_gas_hot_section,
        "warnings": warnings,
    }
