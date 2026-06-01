"""Educational two-spool turbofan cycle solver.

The model is a preliminary-design steady 1D perfect-gas cycle with:

* Two-spool work balance — HPT supplies HPC work, LPT supplies fan work.
* Optional mixed-flow or separate-flow configuration.
* Optional afterburner downstream of the LPT (mixed-flow) or downstream of the
  mixer (mixed-flow) — never on the bypass stream.
* Station numbering follows standard ARP-755 convention:
  0 / 2 / 13 / 21 / 3 / 4 / 45 / 5 / 7 / 9 / 19.

What this model does *not* include
----------------------------------
* No fan or compressor maps; pressure ratios are user inputs.
* HPC-exit customer bleed and HP-turbine cooling air ARE modelled (shared
  ``secondary_air`` helper); other secondary flows are not.
* No mixer pressure loss other than total-pressure mass-weighted blending.
* No variable cycle, no geared-fan reduction-ratio physics.

These limitations are surfaced as warnings in the result payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.engine_core.atmosphere import isa_atmosphere
from app.engine_core.combustor import calculate_combustor_exit
from app.engine_core.combustor_equilibrium import calculate_combustor_exit_equilibrium
from app.engine_core.compressor import calculate_compressor_exit
from app.engine_core.constants import (
    R_air,
    cp_air,
    cp_gas,
    gamma_air,
    gamma_gas,
)
from app.engine_core.inlet import calculate_freestream_state, calculate_inlet_exit
from app.engine_core.secondary_air import apply_bleed_and_cooling
from app.engine_core.streams import (
    NozzleStreamResult,
    compute_stream_efficiencies,
    expand_nozzle_stream,
    merge_warnings,
    station_table,
)
from app.engine_core.types import (
    ComponentResult,
    CycleCalculationError,
    StationState,
)

NozzleStream = NozzleStreamResult


# ---------------------------------------------------------------------------
# Inputs container — kept as a dataclass so the solver does not depend on
# Pydantic at the engine-core level (matches turbojet pattern).
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class TurbofanCycleInputs:
    """Validated turbofan inputs (dataclass mirror of TurbofanInput)."""

    engine_variant: str = "turbofan"
    nozzle_configuration: str = "separate"  # "separate" or "mixed"
    altitude_m: float = 10000.0
    mach: float = 0.78
    total_mass_flow_air_kg_s: float = 220.0
    bypass_ratio: float = 5.0
    fan_pressure_ratio: float = 1.55
    fan_efficiency: float = 0.89
    core_compressor_pressure_ratio: float = 18.0
    compressor_efficiency: float = 0.88
    turbine_inlet_temperature_K: float = 1550.0
    hp_turbine_efficiency: float = 0.9
    lp_turbine_efficiency: float = 0.9
    combustor_efficiency: float = 0.99
    combustor_pressure_loss_fraction: float = 0.05
    mechanical_efficiency: float = 0.99
    core_nozzle_efficiency: float = 0.95
    bypass_nozzle_efficiency: float = 0.94
    inlet_pressure_recovery: float = 0.98
    fuel_heating_value_J_kg: float = 43e6
    use_afterburner: bool = False
    afterburner_exit_temperature_K: float | None = None
    afterburner_efficiency: float = 0.95
    afterburner_pressure_loss_fraction: float = 0.06
    mixer_pressure_loss_fraction: float = 0.02
    use_equilibrium_combustion: bool = False
    equilibrium_fuel_species: str = "CH4"
    bleed_fraction_hpc_exit: float = 0.0
    cooling_fraction_hpt_inlet: float = 0.0
    # Variable-cycle / 3-stream adaptive engine (separate-flow only).
    third_stream: bool = False
    variable_cycle_mode: str = "high_efficiency"  # "high_efficiency" | "high_thrust"
    third_stream_ratio: float = 0.0               # m_third / m_core when open
    third_stream_pressure_ratio: float | None = None  # outer-fan PR; None -> fan PR
    third_stream_nozzle_efficiency: float = 0.94


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fan_exit_state(
    inlet_state: StationState,
    fan_pressure_ratio: float,
    fan_efficiency: float,
) -> ComponentResult:
    """Compute fan exit (station 13) for the combined fan face."""

    if fan_pressure_ratio <= 1.0:
        raise CycleCalculationError("Fan pressure ratio must exceed 1.")
    if not 0.0 < fan_efficiency <= 1.0:
        raise CycleCalculationError("Fan efficiency must be in (0, 1].")
    temperature_ratio_s = fan_pressure_ratio ** ((gamma_air - 1.0) / gamma_air)
    Tt13s = inlet_state.stagnation_temperature_K * temperature_ratio_s
    Tt13 = inlet_state.stagnation_temperature_K + (
        Tt13s - inlet_state.stagnation_temperature_K
    ) / fan_efficiency
    Pt13 = inlet_state.stagnation_pressure_Pa * fan_pressure_ratio
    state = StationState(
        station=13,
        name="Fan exit",
        stagnation_temperature_K=Tt13,
        stagnation_pressure_Pa=Pt13,
        notes=["Adiabatic fan, perfect-gas, specified isentropic efficiency."],
    )
    fan_specific_work_J_kg = cp_air * (Tt13 - inlet_state.stagnation_temperature_K)
    return ComponentResult(
        state=state,
        metadata={
            "fan_specific_work_J_kg": fan_specific_work_J_kg,
            "Tt13s": Tt13s,
        },
    )


def _hpt_lpt_split(
    combustor_state: StationState,
    hpc_specific_work_J_kg: float,
    fan_specific_work_per_core_air_J_kg: float,
    fuel_air_ratio: float,
    mechanical_efficiency: float,
    hp_turbine_efficiency: float,
    lp_turbine_efficiency: float,
    gas_mass_flow_ratio: float | None = None,
) -> tuple[StationState, StationState, dict[str, float]]:
    """Split turbine work into HPT (drives HPC) and LPT (drives fan).

    Returns station 45 (HPT exit) and station 5 (LPT exit) plus diagnostics.
    The split conserves stagnation enthalpy in each spool's energy balance and
    applies isentropic efficiencies for the Pt drop.

    ``gas_mass_flow_ratio`` (``m_HPT / m_core_air``) overrides the historical
    ``1 + fuel_air_ratio`` factor in the work-balance denominators so bleed and
    HPT cooling air are reflected in the turbine temperature drops. When
    omitted it falls back to ``1 + fuel_air_ratio``.
    """

    if hpc_specific_work_J_kg <= 0.0:
        raise CycleCalculationError("HPC specific work must be positive.")
    if fan_specific_work_per_core_air_J_kg <= 0.0:
        raise CycleCalculationError(
            "Fan specific work referred to core flow must be positive."
        )
    if fuel_air_ratio <= 0.0:
        raise CycleCalculationError("Fuel-air ratio must be positive.")

    mass_ratio = (
        gas_mass_flow_ratio if gas_mass_flow_ratio is not None else 1.0 + fuel_air_ratio
    )

    # HPT drop (drives HPC).
    Tt4 = combustor_state.stagnation_temperature_K
    drop_hpt_K = hpc_specific_work_J_kg / (
        mass_ratio * cp_gas * mechanical_efficiency
    )
    Tt45 = Tt4 - drop_hpt_K
    if Tt45 <= 0.0:
        raise CycleCalculationError("HPT work extraction produced non-positive T45.")
    Tt45s = Tt4 - drop_hpt_K / hp_turbine_efficiency
    if Tt45s <= 0.0:
        raise CycleCalculationError("HPT isentropic exit temperature non-positive.")
    Pt45 = combustor_state.stagnation_pressure_Pa * (
        Tt45s / Tt4
    ) ** (gamma_gas / (gamma_gas - 1.0))

    # LPT drop (drives fan).
    drop_lpt_K = fan_specific_work_per_core_air_J_kg / (
        mass_ratio * cp_gas * mechanical_efficiency
    )
    Tt5 = Tt45 - drop_lpt_K
    if Tt5 <= 0.0:
        raise CycleCalculationError("LPT work extraction produced non-positive T5.")
    Tt5s = Tt45 - drop_lpt_K / lp_turbine_efficiency
    if Tt5s <= 0.0:
        raise CycleCalculationError("LPT isentropic exit temperature non-positive.")
    Pt5 = Pt45 * (Tt5s / Tt45) ** (gamma_gas / (gamma_gas - 1.0))

    state_45 = StationState(
        station=45,
        name="HP turbine exit / LPT inlet",
        stagnation_temperature_K=Tt45,
        stagnation_pressure_Pa=Pt45,
        notes=["HPT supplies HPC work through mechanical efficiency."],
    )
    state_5 = StationState(
        station=5,
        name="LP turbine exit",
        stagnation_temperature_K=Tt5,
        stagnation_pressure_Pa=Pt5,
        notes=["LPT supplies fan work through mechanical efficiency."],
    )
    return state_45, state_5, {
        "hpt_drop_K": drop_hpt_K,
        "lpt_drop_K": drop_lpt_K,
        "Tt45s": Tt45s,
        "Tt5s": Tt5s,
    }


def _mix_streams(
    core_state: StationState,
    bypass_state: StationState,
    core_mass_flow_kg_s: float,
    bypass_mass_flow_kg_s: float,
    fuel_air_ratio: float,
    mixer_pressure_loss_fraction: float,
) -> StationState:
    """Educational constant-pressure mixer.

    The mixer conserves stagnation enthalpy. The exit stagnation pressure is
    mass-weighted between the two stream stagnation pressures and then derated
    by ``mixer_pressure_loss_fraction``. This is the standard preliminary
    design simplification used in Mattingly and Hill & Peterson.
    """

    if not 0.0 <= mixer_pressure_loss_fraction <= 0.2:
        raise CycleCalculationError("Mixer pressure loss must be in [0, 0.2].")

    m_core = core_mass_flow_kg_s * (1.0 + fuel_air_ratio)
    m_bypass = bypass_mass_flow_kg_s
    m_total = m_core + m_bypass
    if m_total <= 0.0:
        raise CycleCalculationError("Mixer total mass flow is non-positive.")

    Tt7 = (
        m_core * cp_gas * core_state.stagnation_temperature_K
        + m_bypass * cp_air * bypass_state.stagnation_temperature_K
    ) / (m_core * cp_gas + m_bypass * cp_air)
    Pt7_blend = (
        m_core * core_state.stagnation_pressure_Pa
        + m_bypass * bypass_state.stagnation_pressure_Pa
    ) / m_total
    Pt7 = Pt7_blend * (1.0 - mixer_pressure_loss_fraction)

    return StationState(
        station=7,
        name="Mixer exit",
        stagnation_temperature_K=Tt7,
        stagnation_pressure_Pa=Pt7,
        notes=[
            "Educational constant-pressure mixer with mass-weighted Pt blending.",
        ],
    )


def _apply_afterburner(
    inlet_state: StationState,
    incoming_fuel_air_ratio: float,
    exit_temperature_K: float,
    efficiency: float,
    pressure_loss_fraction: float,
    fuel_heating_value_J_kg: float,
) -> tuple[StationState, float]:
    """Educational afterburner / mixer-AB downstream of the LPT or mixer."""

    if exit_temperature_K <= inlet_state.stagnation_temperature_K:
        raise CycleCalculationError(
            "Afterburner exit temperature must exceed inlet temperature."
        )
    if not 0.0 < efficiency <= 1.0:
        raise CycleCalculationError("Afterburner efficiency must be in (0, 1].")
    if not 0.0 <= pressure_loss_fraction <= 0.25:
        raise CycleCalculationError(
            "Afterburner pressure loss must be in [0, 0.25]."
        )
    denominator = efficiency * fuel_heating_value_J_kg - cp_gas * exit_temperature_K
    if denominator <= 0.0:
        raise CycleCalculationError(
            "Afterburner energy balance impossible — heat release too low."
        )
    ab_far = (
        (1.0 + incoming_fuel_air_ratio)
        * cp_gas
        * (exit_temperature_K - inlet_state.stagnation_temperature_K)
        / denominator
    )
    if ab_far <= 0.0:
        raise CycleCalculationError(
            "Afterburner produced non-positive added fuel-air ratio."
        )
    Pt7 = inlet_state.stagnation_pressure_Pa * (1.0 - pressure_loss_fraction)
    state = StationState(
        station=7,
        name="Afterburner exit / final nozzle inlet",
        stagnation_temperature_K=exit_temperature_K,
        stagnation_pressure_Pa=Pt7,
        notes=["Educational reheat — no flame stability or liner cooling."],
    )
    return state, ab_far


# ---------------------------------------------------------------------------
# Engine-class warning checks
# ---------------------------------------------------------------------------


def _engine_class_warnings(
    inputs: TurbofanCycleInputs,
    core_nozzle: NozzleStream,
    bypass_nozzle: NozzleStream | None,
    fan_tip_velocity_m_s: float | None,
) -> list[str]:
    """Heuristic engine-class checks for turbofan inputs."""

    warnings: list[str] = []
    # Fan pressure ratio sanity
    if inputs.fan_pressure_ratio < 1.2:
        warnings.append(
            "CAUTION: Fan pressure ratio is unusually low — check fan stage count."
        )
    if inputs.fan_pressure_ratio > 2.2:
        warnings.append(
            "CAUTION: Fan pressure ratio is very high for a single-stage fan."
        )
    # Bypass ratio vs class
    if inputs.bypass_ratio < 0.3 and inputs.fan_pressure_ratio < 2.0:
        warnings.append(
            "CAUTION: Low bypass ratio + low FPR — closer to a turbojet than turbofan."
        )
    if inputs.bypass_ratio > 12.0:
        warnings.append(
            "INFO: Very high bypass ratio — geared fan reduction is not modelled here."
        )
    # Nozzle behavior
    if not core_nozzle.choked:
        warnings.append(
            "INFO: Core nozzle is unchoked at this operating point."
        )
    if bypass_nozzle is not None and not bypass_nozzle.choked:
        warnings.append(
            "INFO: Bypass nozzle is unchoked at this operating point."
        )
    # Fan tip Mach
    if fan_tip_velocity_m_s is not None and fan_tip_velocity_m_s > 450.0:
        warnings.append(
            "CAUTION: Implied fan-tip velocity is high; transonic-fan losses are not modelled."
        )
    return warnings


# ---------------------------------------------------------------------------
# Top-level solver
# ---------------------------------------------------------------------------


def simulate_turbofan_cycle(inputs: Any) -> dict[str, Any]:
    """Run the full two-spool turbofan cycle.

    Accepts either ``TurbofanCycleInputs`` or any object exposing the same
    attribute names (the Pydantic ``TurbofanInput`` schema works directly).
    """

    cycle = _coerce_inputs(inputs)
    atmosphere = isa_atmosphere(cycle.altitude_m)
    freestream = calculate_freestream_state(atmosphere, cycle.mach)
    inlet = calculate_inlet_exit(freestream.state, cycle.inlet_pressure_recovery)

    core_mass_flow_kg_s = cycle.total_mass_flow_air_kg_s / (1.0 + cycle.bypass_ratio)
    bypass_mass_flow_kg_s = cycle.total_mass_flow_air_kg_s - core_mass_flow_kg_s

    # ---- Variable-cycle third stream (adaptive engine) --------------------
    # An optional outer bypass stream gated by a mode switch. In
    # "high_efficiency" mode the stream is open (effective ratio =
    # third_stream_ratio), adding low-velocity bypass thrust and raising total
    # airflow; in "high_thrust" mode it is closed and the engine reverts to the
    # two-stream turbofan. The stream is pumped by the fan, so its work is
    # debited from the LP turbine below (no free thrust).
    third_stream_open = bool(getattr(cycle, "third_stream", False)) and (
        getattr(cycle, "variable_cycle_mode", "high_efficiency") == "high_efficiency"
    )
    third_stream_ratio = getattr(cycle, "third_stream_ratio", 0.0)
    if third_stream_ratio < 0.0:
        raise CycleCalculationError("third_stream_ratio must be non-negative.")
    effective_third_ratio = third_stream_ratio if third_stream_open else 0.0
    third_mass_flow_kg_s = effective_third_ratio * core_mass_flow_kg_s
    if third_mass_flow_kg_s > 0.0:
        if cycle.nozzle_configuration != "separate":
            raise CycleCalculationError(
                "The third stream is supported with separate-flow nozzles only."
            )
        if cycle.use_afterburner:
            raise CycleCalculationError(
                "The third stream is not supported together with the afterburner."
            )
    third_stream_pr = (
        getattr(cycle, "third_stream_pressure_ratio", None) or cycle.fan_pressure_ratio
    )

    fan = _fan_exit_state(
        inlet.state, cycle.fan_pressure_ratio, cycle.fan_efficiency
    )
    third_fan = (
        _fan_exit_state(inlet.state, third_stream_pr, cycle.fan_efficiency)
        if third_mass_flow_kg_s > 0.0
        else None
    )
    hpc = calculate_compressor_exit(
        fan.state,
        cycle.core_compressor_pressure_ratio,
        cycle.compressor_efficiency,
    )
    # Combustor
    if cycle.use_equilibrium_combustion:
        combustor = calculate_combustor_exit_equilibrium(
            hpc.state,
            cycle.turbine_inlet_temperature_K,
            cycle.combustor_efficiency,
            cycle.combustor_pressure_loss_fraction,
            cycle.fuel_heating_value_J_kg,
            fuel=cycle.equilibrium_fuel_species,
        )
    else:
        combustor = calculate_combustor_exit(
            hpc.state,
            cycle.turbine_inlet_temperature_K,
            cycle.combustor_efficiency,
            cycle.combustor_pressure_loss_fraction,
            cycle.fuel_heating_value_J_kg,
        )
    fuel_air_ratio = float(combustor.metadata["fuel_air_ratio"])

    # ---- HPC-exit bleed + HPT cooling air (shared helper) -----------------
    # Fractions are taken relative to the CORE air flow. Customer bleed and
    # cooling are not yet supported together with the afterburner.
    bleed_fraction = getattr(cycle, "bleed_fraction_hpc_exit", 0.0)
    cooling_fraction = getattr(cycle, "cooling_fraction_hpt_inlet", 0.0)
    if (bleed_fraction > 0.0 or cooling_fraction > 0.0) and cycle.use_afterburner:
        raise CycleCalculationError(
            "Bleed and cooling fractions are not yet supported with the afterburner."
        )
    secondary = apply_bleed_and_cooling(
        reference_air_kg_s=core_mass_flow_kg_s,
        compressor_exit_state=hpc.state,
        combustor_exit_state=combustor.state,
        fuel_air_ratio=fuel_air_ratio,
        bleed_fraction=bleed_fraction,
        cooling_fraction=cooling_fraction,
    )
    core_gas_ratio = secondary.gas_mass_flow_ratio  # m_HPT / m_core_air

    hpc_work = float(hpc.metadata["compressor_specific_work_J_kg"])
    fan_work_per_core_air = float(fan.metadata["fan_specific_work_J_kg"]) * (
        1.0 + cycle.bypass_ratio
    )
    if third_fan is not None:
        # The outer fan stage pumps the third stream; the LP turbine pays for it.
        fan_work_per_core_air += (
            float(third_fan.metadata["fan_specific_work_J_kg"]) * effective_third_ratio
        )

    state_45, state_5, turbine_meta = _hpt_lpt_split(
        secondary.turbine_inlet_state,
        hpc_work,
        fan_work_per_core_air,
        fuel_air_ratio,
        cycle.mechanical_efficiency,
        cycle.hp_turbine_efficiency,
        cycle.lp_turbine_efficiency,
        gas_mass_flow_ratio=core_gas_ratio,
    )

    afterburner_state: StationState | None = None
    afterburner_fuel_air_ratio = 0.0
    core_far_into_nozzle = fuel_air_ratio
    extra_ab_warnings: list[str] = []
    third_nozzle = None

    if cycle.nozzle_configuration not in {"separate", "mixed"}:
        raise CycleCalculationError(
            "nozzle_configuration must be 'separate' or 'mixed'."
        )

    # --- Separate-flow path -------------------------------------------------
    if cycle.nozzle_configuration == "separate":
        # Optional AB on core stream only (before core nozzle).
        core_nozzle_inlet = state_5
        if cycle.use_afterburner:
            ab_T = cycle.afterburner_exit_temperature_K or 1850.0
            afterburner_state, afterburner_fuel_air_ratio = _apply_afterburner(
                state_5,
                fuel_air_ratio,
                ab_T,
                cycle.afterburner_efficiency,
                cycle.afterburner_pressure_loss_fraction,
                cycle.fuel_heating_value_J_kg,
            )
            core_nozzle_inlet = afterburner_state
            extra_ab_warnings.append(
                "Afterburner active on core stream (separate-flow turbofan)."
            )

        # Effective fuel-air ratio for the core nozzle so its exit mass equals
        # the HPT-inlet flow (combustion gas + cooling air, less bleed) plus any
        # afterburner fuel. Ram drag stays on the full core air. With no bleed
        # and no AB this reduces to the plain fuel-air ratio.
        core_far_into_nozzle = (core_gas_ratio - 1.0) + afterburner_fuel_air_ratio

        core_nozzle = expand_nozzle_stream(
            core_nozzle_inlet,
            atmosphere.pressure_Pa,
            core_mass_flow_kg_s,
            core_far_into_nozzle,
            freestream.state.velocity_m_s or 0.0,
            cycle.core_nozzle_efficiency,
            9,
            "Core nozzle exit",
            gamma_gas,
            cp_gas,
        )
        bypass_nozzle = expand_nozzle_stream(
            fan.state,
            atmosphere.pressure_Pa,
            bypass_mass_flow_kg_s,
            0.0,
            freestream.state.velocity_m_s or 0.0,
            cycle.bypass_nozzle_efficiency,
            19,
            "Bypass nozzle exit",
            gamma_air,
            cp_air,
        )
        if third_fan is not None:
            third_nozzle = expand_nozzle_stream(
                third_fan.state,
                atmosphere.pressure_Pa,
                third_mass_flow_kg_s,
                0.0,
                freestream.state.velocity_m_s or 0.0,
                cycle.third_stream_nozzle_efficiency,
                29,
                "Third-stream nozzle exit",
                gamma_air,
                cp_air,
            )
    # --- Mixed-flow path ----------------------------------------------------
    else:
        # Core gas entering the mixer is the HPT-inlet flow; pass (gas_ratio-1)
        # so the mixer's internal m*(1+f) sees the right core mass.
        mixer = _mix_streams(
            state_5,
            fan.state,
            core_mass_flow_kg_s,
            bypass_mass_flow_kg_s,
            core_gas_ratio - 1.0,
            cycle.mixer_pressure_loss_fraction,
        )
        m_total_air = core_mass_flow_kg_s + bypass_mass_flow_kg_s

        nozzle_inlet = mixer
        if cycle.use_afterburner:
            mixed_far = (core_gas_ratio - 1.0) * core_mass_flow_kg_s / m_total_air
            ab_T = cycle.afterburner_exit_temperature_K or 2000.0
            afterburner_state, afterburner_fuel_air_ratio = _apply_afterburner(
                mixer,
                mixed_far,
                ab_T,
                cycle.afterburner_efficiency,
                cycle.afterburner_pressure_loss_fraction,
                cycle.fuel_heating_value_J_kg,
            )
            nozzle_inlet = afterburner_state
            extra_ab_warnings.append(
                "Afterburner active downstream of mixer (mixed-flow turbofan)."
            )

        # Mixed nozzle exit mass = HPT-inlet core gas + bypass air + AB fuel.
        ab_fuel_mass = afterburner_fuel_air_ratio * m_total_air
        mixed_exit_kg_s = secondary.hpt_inlet_kg_s + bypass_mass_flow_kg_s + ab_fuel_mass
        core_far_into_nozzle = mixed_exit_kg_s / m_total_air - 1.0

        core_nozzle = expand_nozzle_stream(
            nozzle_inlet,
            atmosphere.pressure_Pa,
            m_total_air,
            core_far_into_nozzle,
            freestream.state.velocity_m_s or 0.0,
            cycle.core_nozzle_efficiency,
            9,
            "Mixed nozzle exit",
            gamma_gas,
            cp_gas,
        )
        bypass_nozzle = None

    # --- Performance bookkeeping --------------------------------------------
    V0 = freestream.state.velocity_m_s or 0.0
    total_air_with_third = cycle.total_mass_flow_air_kg_s + third_mass_flow_kg_s
    third_thrust_N = 0.0
    if cycle.nozzle_configuration == "separate":
        momentum_thrust_N = (
            core_nozzle.momentum_thrust_N + bypass_nozzle.momentum_thrust_N
        )
        pressure_thrust_N = (
            core_nozzle.pressure_thrust_N + bypass_nozzle.pressure_thrust_N
        )
        core_thrust_N = (
            core_nozzle.momentum_thrust_N + core_nozzle.pressure_thrust_N
        )
        bypass_thrust_N = (
            bypass_nozzle.momentum_thrust_N + bypass_nozzle.pressure_thrust_N
        )
        if third_nozzle is not None:
            third_thrust_N = (
                third_nozzle.momentum_thrust_N + third_nozzle.pressure_thrust_N
            )
            momentum_thrust_N += third_nozzle.momentum_thrust_N
            pressure_thrust_N += third_nozzle.pressure_thrust_N
    else:
        momentum_thrust_N = core_nozzle.momentum_thrust_N
        pressure_thrust_N = core_nozzle.pressure_thrust_N
        # In mixed-flow the streams are no longer separable. We allocate by
        # mass flow share for display only.
        m_total = core_mass_flow_kg_s + bypass_mass_flow_kg_s
        core_thrust_N = (
            (momentum_thrust_N + pressure_thrust_N) * core_mass_flow_kg_s / m_total
        )
        bypass_thrust_N = (
            (momentum_thrust_N + pressure_thrust_N) - core_thrust_N
        )

    thrust_N = momentum_thrust_N + pressure_thrust_N
    if thrust_N <= 0.0:
        raise CycleCalculationError(
            "Turbofan cycle produced non-positive net thrust."
        )

    # Core combustion fuel is taken against the (bleed-reduced) combustor air;
    # afterburner fuel rides on the full mixed/core stream.
    fuel_flow_kg_s = (
        secondary.fuel_flow_kg_s
        + afterburner_fuel_air_ratio
        * (core_mass_flow_kg_s + bypass_mass_flow_kg_s)
    )

    if cycle.nozzle_configuration == "separate":
        third_ke_W = (
            third_mass_flow_kg_s * third_nozzle.exit_velocity_m_s**2
            if third_nozzle is not None
            else 0.0
        )
        third_pressure_N = (
            third_nozzle.pressure_thrust_N if third_nozzle is not None else 0.0
        )
        jet_kinetic_power_change_W = 0.5 * (
            core_mass_flow_kg_s * (1.0 + core_far_into_nozzle) * core_nozzle.exit_velocity_m_s**2
            + bypass_mass_flow_kg_s * bypass_nozzle.exit_velocity_m_s**2
            + third_ke_W
            - total_air_with_third * V0**2
        )
        pressure_power_W = (
            core_nozzle.pressure_thrust_N
            + bypass_nozzle.pressure_thrust_N
            + third_pressure_N
        ) * V0
    else:
        m_total = core_mass_flow_kg_s + bypass_mass_flow_kg_s
        jet_kinetic_power_change_W = 0.5 * (
            mixed_exit_kg_s * core_nozzle.exit_velocity_m_s**2 - m_total * V0**2
        )
        pressure_power_W = core_nozzle.pressure_thrust_N * V0

    efficiencies = compute_stream_efficiencies(
        thrust_N=thrust_N,
        freestream_velocity_m_s=V0,
        fuel_flow_kg_s=fuel_flow_kg_s,
        fuel_heating_value_J_kg=cycle.fuel_heating_value_J_kg,
        jet_kinetic_power_change_W=jet_kinetic_power_change_W,
        pressure_thrust_power_W=pressure_power_W,
    )

    # Approximate fan-tip velocity for warning purposes only — uses an
    # educational tip-radius proxy (not a real design value).
    fan_tip_velocity_m_s: float | None = None

    cycle_warnings = _engine_class_warnings(
        cycle, core_nozzle, bypass_nozzle, fan_tip_velocity_m_s
    )

    states = [
        freestream.state,
        inlet.state,
        fan.state,
        hpc.state,
        combustor.state,
        state_45,
        state_5,
    ]
    if afterburner_state is not None:
        states.append(afterburner_state)
    states.append(core_nozzle.state)
    if bypass_nozzle is not None:
        states.append(bypass_nozzle.state)
    if third_nozzle is not None:
        states.append(third_nozzle.state)

    warnings = merge_warnings(
        freestream.warnings,
        inlet.warnings,
        hpc.warnings,
        combustor.warnings,
        extra_ab_warnings,
        cycle_warnings,
        [
            "Two-spool turbofan model; no fan or compressor maps. HPC bleed and HPT cooling air are modelled."
        ],
    )

    return {
        "engine_type": "turbofan",
        "thrust_N": thrust_N,
        "thrust_kN": thrust_N / 1000.0,
        "core_thrust_N": core_thrust_N,
        "bypass_thrust_N": bypass_thrust_N,
        "third_stream_thrust_N": third_thrust_N,
        "specific_thrust_N_per_kg_s": thrust_N / total_air_with_third,
        "fuel_air_ratio": fuel_air_ratio,
        "afterburner_fuel_air_ratio": afterburner_fuel_air_ratio,
        "total_fuel_air_ratio": fuel_air_ratio + afterburner_fuel_air_ratio,
        "fuel_flow_kg_s": fuel_flow_kg_s,
        "TSFC_kg_per_N_s": fuel_flow_kg_s / thrust_N,
        "TSFC_kg_per_kN_hr": fuel_flow_kg_s / thrust_N * 1000.0 * 3600.0,
        "exit_velocity_m_s": core_nozzle.exit_velocity_m_s,
        "bypass_exit_velocity_m_s": (
            bypass_nozzle.exit_velocity_m_s if bypass_nozzle is not None else None
        ),
        "freestream_velocity_m_s": V0,
        "nozzle_choked": core_nozzle.choked,
        "bypass_nozzle_choked": (
            bypass_nozzle.choked if bypass_nozzle is not None else None
        ),
        "momentum_thrust_N": momentum_thrust_N,
        "pressure_thrust_N": pressure_thrust_N,
        **efficiencies,
        "station_table": station_table(*states),
        "warnings": warnings,
        "extra": {
            "nozzle_configuration": cycle.nozzle_configuration,
            "core_mass_flow_kg_s": core_mass_flow_kg_s,
            "bypass_mass_flow_kg_s": bypass_mass_flow_kg_s,
            "third_stream_active": third_nozzle is not None,
            "variable_cycle_mode": getattr(cycle, "variable_cycle_mode", "high_efficiency"),
            "third_stream_mass_flow_kg_s": third_mass_flow_kg_s,
            "third_stream_ratio_effective": effective_third_ratio,
            "third_stream_pressure_ratio": third_stream_pr if third_nozzle is not None else None,
            "total_air_with_third_kg_s": total_air_with_third,
            "effective_bypass_ratio": (bypass_mass_flow_kg_s + third_mass_flow_kg_s)
            / core_mass_flow_kg_s,
            "bypass_ratio": cycle.bypass_ratio,
            "fan_pressure_ratio": cycle.fan_pressure_ratio,
            "core_pressure_ratio": cycle.core_compressor_pressure_ratio,
            "overall_pressure_ratio": cycle.fan_pressure_ratio
            * cycle.core_compressor_pressure_ratio,
            "hpt_drop_K": turbine_meta["hpt_drop_K"],
            "lpt_drop_K": turbine_meta["lpt_drop_K"],
            "core_nozzle_choked": core_nozzle.choked,
            "bypass_nozzle_choked": (
                bypass_nozzle.choked if bypass_nozzle is not None else False
            ),
            "afterburner_active": cycle.use_afterburner,
            "bleed_fraction_hpc_exit": bleed_fraction,
            "cooling_fraction_hpt_inlet": cooling_fraction,
            "combustor_air_mass_flow_kg_s": secondary.combustor_air_kg_s,
            "hpt_inlet_mass_flow_kg_s": secondary.hpt_inlet_kg_s,
            "hpt_inlet_stagnation_temperature_K": secondary.metadata[
                "hpt_inlet_stagnation_temperature_K"
            ],
        },
    }


# ---------------------------------------------------------------------------
# Input coercion — accept Pydantic schema, plain object, or dataclass
# ---------------------------------------------------------------------------


_FIELDS = TurbofanCycleInputs.__dataclass_fields__.keys()


def _coerce_inputs(inputs: Any) -> TurbofanCycleInputs:
    """Normalise inputs into a TurbofanCycleInputs dataclass."""

    if isinstance(inputs, TurbofanCycleInputs):
        return inputs
    # Accept Pydantic schema instances and plain objects with the same attrs.
    kwargs: dict[str, Any] = {}
    defaults = TurbofanCycleInputs()
    for name in _FIELDS:
        if hasattr(inputs, name):
            kwargs[name] = getattr(inputs, name)
        else:
            kwargs[name] = getattr(defaults, name)
    return TurbofanCycleInputs(**kwargs)
