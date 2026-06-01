"""Educational ramjet cycle solver with MIL-spec inlet recovery and Rayleigh
heat-addition checks.

The ramjet has no rotating machinery — all compression comes from decelerating
the supersonic freestream through an inlet system. The model:

* Computes inlet total-pressure recovery from MIL-E-5008B as a function of
  flight Mach for M > 1 (Ranney curve), capped by the user input.
* Sets the diffuser (station 2 → 3) as a near-subsonic ramped diffuser with
  small additional total-pressure loss.
* Heats the gas to a user-specified combustor exit temperature with energy
  balance and combustor pressure loss.
* Performs a Rayleigh-flow consistency check — if the combustor inlet Mach is
  high and heat addition would drive the flow toward M = 1, a thermal-choke
  warning is emitted.
* Expands through a convergent nozzle to ambient.

This solver targets the ramjet operating envelope of Mach 1.5–6.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.engine_core.atmosphere import isa_atmosphere
from app.engine_core.combustor import calculate_combustor_exit
from app.engine_core.combustor_equilibrium import calculate_combustor_exit_equilibrium
from app.engine_core.constants import cp_gas, gamma_air, gamma_gas
from app.engine_core.gas_properties import (
    speed_of_sound,
    stagnation_pressure,
    stagnation_temperature,
)
from app.engine_core.inlet import calculate_freestream_state
from app.engine_core.streams import (
    compute_stream_efficiencies,
    expand_nozzle_stream,
    merge_warnings,
    station_table,
)
from app.engine_core.types import (
    CycleCalculationError,
    StationState,
)


@dataclass(slots=True, frozen=True)
class RamjetCycleInputs:
    """Validated ramjet inputs."""

    altitude_m: float = 15000.0
    mach: float = 2.2
    mass_flow_air_kg_s: float = 25.0
    inlet_pressure_recovery: float = 0.9
    use_mil_spec_inlet_recovery: bool = True
    diffuser_efficiency: float = 0.95
    combustor_inlet_mach: float = 0.25
    combustor_exit_temperature_K: float = 1900.0
    combustor_efficiency: float = 0.96
    combustor_pressure_loss_fraction: float = 0.08
    nozzle_efficiency: float = 0.94
    nozzle_divergent_area_ratio: float = 1.0
    fuel_heating_value_J_kg: float = 43e6
    use_equilibrium_combustion: bool = False
    equilibrium_fuel_species: str = "CH4"


def _mil_spec_inlet_recovery(freestream_mach: float) -> float:
    """MIL-E-5008B inlet total-pressure recovery curve.

    For M >= 1 the curve is::

        eta_r = 1 - 0.075 * (M - 1)**1.35

    Below M = 1 the recovery is 1.0 (ideal). Above M ≈ 5 the curve has dropped
    below 0.5 and the model loses fidelity, which we surface as a warning.
    """

    if freestream_mach <= 1.0:
        return 1.0
    return max(0.05, 1.0 - 0.075 * (freestream_mach - 1.0) ** 1.35)


def _rayleigh_thermal_choke_factor(
    inlet_mach: float, T_ratio_total: float
) -> tuple[float, bool]:
    """Estimate downstream Mach after Rayleigh heat addition.

    For frictionless constant-area heat addition with stagnation-temperature
    ratio ``T_ratio_total = Tt_out / Tt_in``, returns the achievable downstream
    Mach M_out. If the requested heat addition would push M_out beyond 1.0 at
    constant area, the flow is thermally choked.
    """

    if inlet_mach <= 0.0:
        return 0.0, False
    g = gamma_gas
    # Rayleigh Tt/Tt* relation:
    Tt_ratio_to_star_in = (
        (g + 1.0) * inlet_mach**2 * (2.0 + (g - 1.0) * inlet_mach**2)
        / (1.0 + g * inlet_mach**2) ** 2
    )
    Tt_ratio_to_star_out = Tt_ratio_to_star_in * T_ratio_total
    if Tt_ratio_to_star_out >= 1.0:
        return 1.0, True
    # Solve Rayleigh function for M_out via bisection on the function:
    def f(M: float) -> float:
        return (
            (g + 1.0) * M**2 * (2.0 + (g - 1.0) * M**2) / (1.0 + g * M**2) ** 2
            - Tt_ratio_to_star_out
        )

    lo, hi = max(inlet_mach, 1e-3), 1.0
    if f(lo) > 0.0:
        return inlet_mach, False
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if f(mid) < 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi), False


def simulate_ramjet_cycle(inputs: Any) -> dict[str, Any]:
    """Run the educational ramjet cycle."""

    cycle = _coerce_inputs(inputs)
    if cycle.mach <= 0.0:
        raise CycleCalculationError("Ramjet flight Mach must be > 0.")
    if cycle.mach < 1.0:
        # The solver still runs but ram compression is poor.
        pass

    atmosphere = isa_atmosphere(cycle.altitude_m)
    freestream = calculate_freestream_state(atmosphere, cycle.mach)

    # ---- Inlet total-pressure recovery ------------------------------------
    if cycle.use_mil_spec_inlet_recovery:
        mil_recovery = _mil_spec_inlet_recovery(cycle.mach)
        inlet_recovery = min(cycle.inlet_pressure_recovery, mil_recovery)
    else:
        inlet_recovery = cycle.inlet_pressure_recovery

    Pt2 = freestream.state.stagnation_pressure_Pa * inlet_recovery
    Tt2 = freestream.state.stagnation_temperature_K
    state_2 = StationState(
        station=2,
        name="Inlet exit",
        stagnation_temperature_K=Tt2,
        stagnation_pressure_Pa=Pt2,
        notes=[
            "Inlet recovery taken from MIL-E-5008B"
            if cycle.use_mil_spec_inlet_recovery
            else "Inlet recovery as specified by user.",
        ],
    )

    # ---- Diffuser to combustor inlet Mach ---------------------------------
    # Decelerate isentropically with diffuser efficiency on dynamic pressure.
    # Solve for combustor-inlet static state from stagnation state at the
    # requested combustor inlet Mach.
    Mc = cycle.combustor_inlet_mach
    if not 0.05 < Mc < 1.0:
        raise CycleCalculationError(
            "Combustor inlet Mach must be subsonic and > 0.05 for ramjet."
        )
    Tc_static = Tt2 / (1.0 + (gamma_air - 1.0) / 2.0 * Mc**2)
    Pc_static_isentropic = Pt2 / (
        (1.0 + (gamma_air - 1.0) / 2.0 * Mc**2) ** (gamma_air / (gamma_air - 1.0))
    )
    # Apply diffuser efficiency as a small Pt loss in the diffuser duct.
    Pt3 = Pt2 * (cycle.diffuser_efficiency ** 0.5)  # gentle Pt loss
    Pc_static = Pt3 / (
        (1.0 + (gamma_air - 1.0) / 2.0 * Mc**2) ** (gamma_air / (gamma_air - 1.0))
    )
    state_3 = StationState(
        station=3,
        name="Diffuser exit / combustor inlet",
        static_temperature_K=Tc_static,
        static_pressure_Pa=Pc_static,
        stagnation_temperature_K=Tt2,
        stagnation_pressure_Pa=Pt3,
        mach=Mc,
        velocity_m_s=Mc * speed_of_sound(Tc_static),
        notes=["Subsonic combustor inlet from diffuser deceleration."],
    )

    # ---- Combustor --------------------------------------------------------
    if cycle.use_equilibrium_combustion:
        combustor = calculate_combustor_exit_equilibrium(
            state_3,
            cycle.combustor_exit_temperature_K,
            cycle.combustor_efficiency,
            cycle.combustor_pressure_loss_fraction,
            cycle.fuel_heating_value_J_kg,
            fuel=cycle.equilibrium_fuel_species,
        )
    else:
        combustor = calculate_combustor_exit(
            state_3,
            cycle.combustor_exit_temperature_K,
            cycle.combustor_efficiency,
            cycle.combustor_pressure_loss_fraction,
            cycle.fuel_heating_value_J_kg,
        )
    fuel_air_ratio = float(combustor.metadata["fuel_air_ratio"])

    # ---- Rayleigh thermal-choke check -------------------------------------
    T_ratio_total = (
        combustor.state.stagnation_temperature_K / state_3.stagnation_temperature_K
    )
    M_out, thermal_choked = _rayleigh_thermal_choke_factor(Mc, T_ratio_total)

    # ---- Nozzle expansion -------------------------------------------------
    nozzle = expand_nozzle_stream(
        combustor.state,
        atmosphere.pressure_Pa,
        cycle.mass_flow_air_kg_s,
        fuel_air_ratio,
        freestream.state.velocity_m_s or 0.0,
        cycle.nozzle_efficiency,
        9,
        "Ramjet nozzle exit",
        gamma_gas,
        cp_gas,
        divergent_area_ratio=cycle.nozzle_divergent_area_ratio,
    )

    V0 = freestream.state.velocity_m_s or 0.0
    thrust_N = nozzle.momentum_thrust_N + nozzle.pressure_thrust_N
    if thrust_N <= 0.0:
        raise CycleCalculationError("Ramjet produced non-positive net thrust.")

    fuel_flow_kg_s = fuel_air_ratio * cycle.mass_flow_air_kg_s
    jet_kinetic_power_change_W = 0.5 * cycle.mass_flow_air_kg_s * (
        (1.0 + fuel_air_ratio) * nozzle.exit_velocity_m_s**2 - V0**2
    )
    pressure_power_W = nozzle.pressure_thrust_N * V0
    efficiencies = compute_stream_efficiencies(
        thrust_N=thrust_N,
        freestream_velocity_m_s=V0,
        fuel_flow_kg_s=fuel_flow_kg_s,
        fuel_heating_value_J_kg=cycle.fuel_heating_value_J_kg,
        jet_kinetic_power_change_W=jet_kinetic_power_change_W,
        pressure_thrust_power_W=pressure_power_W,
    )

    warnings: list[str] = [
        "Educational ramjet model; subsonic combustion only, no isolator.",
    ]
    if cycle.mach < 1.5:
        warnings.append(
            "CAUTION: Ramjets are inefficient below ~M1.5 — ram compression is insufficient."
        )
    if cycle.mach > 5.0:
        warnings.append(
            "CAUTION: Inlet recovery model loses fidelity above ~M5."
        )
    if cycle.combustor_pressure_loss_fraction > 0.15:
        warnings.append(
            "CAUTION: Combustor pressure loss is high for a preliminary ramjet cycle."
        )
    if inlet_recovery < 0.5:
        warnings.append(
            "CAUTION: Inlet total-pressure recovery is degraded; shock losses are simplified."
        )
    if not nozzle.choked:
        warnings.append("INFO: Nozzle is unchoked at this operating point.")
    if nozzle.metadata.get("shock_in_nozzle"):
        warnings.append(
            "CAUTION: Nozzle is heavily over-expanded — a normal shock sits in "
            "the divergent section (subsonic exit). Reduce the area ratio or "
            "raise the nozzle pressure ratio."
        )
    if thermal_choked:
        warnings.append(
            "CRITICAL: Heat addition is at or near Rayleigh thermal choking — reduce T04."
        )
    elif M_out > 0.95:
        warnings.append(
            "CAUTION: Combustor exit Mach approaches 1 — close to thermal choking."
        )

    states = [
        freestream.state,
        state_2,
        state_3,
        combustor.state,
        nozzle.state,
    ]

    return {
        "engine_type": "ramjet",
        "thrust_N": thrust_N,
        "thrust_kN": thrust_N / 1000.0,
        "specific_thrust_N_per_kg_s": thrust_N / cycle.mass_flow_air_kg_s,
        "fuel_air_ratio": fuel_air_ratio,
        "fuel_flow_kg_s": fuel_flow_kg_s,
        "TSFC_kg_per_N_s": fuel_flow_kg_s / thrust_N,
        "TSFC_kg_per_kN_hr": fuel_flow_kg_s / thrust_N * 1000.0 * 3600.0,
        "exit_velocity_m_s": nozzle.exit_velocity_m_s,
        "freestream_velocity_m_s": V0,
        "nozzle_choked": nozzle.choked,
        "momentum_thrust_N": nozzle.momentum_thrust_N,
        "pressure_thrust_N": nozzle.pressure_thrust_N,
        **efficiencies,
        "station_table": station_table(*states),
        "warnings": merge_warnings(freestream.warnings, warnings),
        "extra": {
            "combustor_mode": "subsonic",
            "applied_inlet_recovery": inlet_recovery,
            "mil_spec_inlet_recovery": _mil_spec_inlet_recovery(cycle.mach),
            "combustor_exit_mach_estimate": M_out,
            "rayleigh_thermal_choke": thermal_choked,
            "ram_pressure_ratio": Pt2 / atmosphere.pressure_Pa,
        },
    }


_FIELDS = RamjetCycleInputs.__dataclass_fields__.keys()


def _coerce_inputs(inputs: Any) -> RamjetCycleInputs:
    """Normalise inputs into a RamjetCycleInputs dataclass."""

    if isinstance(inputs, RamjetCycleInputs):
        return inputs
    defaults = RamjetCycleInputs()
    kwargs: dict[str, Any] = {}
    for name in _FIELDS:
        if hasattr(inputs, name):
            kwargs[name] = getattr(inputs, name)
        else:
            kwargs[name] = getattr(defaults, name)
    return RamjetCycleInputs(**kwargs)
