"""Educational scramjet cycle solver — reduced-order, deliberately honest.

What this model includes
------------------------
* Multi-shock inlet compression using kinetic-energy efficiency (eta_KE).
* Supersonic combustor with constant-area heat addition expressed through a
  Rayleigh-like Tt rise. The combustor inlet Mach is preserved subject to a
  total-pressure loss.
* Equivalence-ratio input rather than a target Tt4 — the combustor Tt rise is
  determined by fuel chemical energy (phi * f_stoich * LHV * eta_b) and
  cp_gas. This is the right control for scramjet operating-line studies.
* Convergent nozzle expansion using stream utilities.

What this model deliberately does NOT include
---------------------------------------------
* No finite-rate chemistry or dissociation.
* No isolator pressure recovery curve, no shock-train modelling.
* No fuel-air mixing length or ignition-delay constraint.
* No real-gas effects above T ~ 2500 K.

These are surfaced as `educational reduced-order` warnings in the result.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.engine_core.atmosphere import isa_atmosphere
from app.engine_core.constants import (
    R_air,
    cp_air,
    cp_gas,
    gamma_air,
    gamma_gas,
)
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

# Stoichiometric f for kerosene/methane-class hydrocarbon fuel in air.
F_STOICH_HYDROCARBON = 0.0685


@dataclass(slots=True, frozen=True)
class ScramjetCycleInputs:
    """Validated scramjet inputs."""

    altitude_m: float = 22000.0
    mach: float = 5.0
    mass_flow_air_kg_s: float = 18.0
    inlet_kinetic_energy_efficiency: float = 0.94
    combustor_mach: float = 2.2
    equivalence_ratio: float = 0.7
    combustor_efficiency: float = 0.85
    combustor_pressure_loss_fraction: float = 0.18
    nozzle_efficiency: float = 0.93
    # A real scramjet always has a long divergent nozzle — default to a
    # supersonic-exit CD nozzle rather than the (unphysical) convergent cap.
    nozzle_divergent_area_ratio: float = 6.0
    fuel_heating_value_J_kg: float = 43e6
    stoichiometric_fuel_air_ratio: float = F_STOICH_HYDROCARBON


def _inlet_compression(
    freestream_state: StationState,
    freestream_static_T_K: float,
    freestream_static_P_Pa: float,
    freestream_mach: float,
    combustor_mach: float,
    eta_ke: float,
) -> tuple[StationState, StationState, dict[str, float]]:
    """Decelerate the supersonic freestream to ``combustor_mach``.

    Uses the kinetic-energy efficiency definition::

        eta_KE = (Vs**2 - V2**2) / (V0**2 - V2**2)

    where ``Vs`` is the velocity that would result from an isentropic
    compression to the same static pressure as the actual exit state. We
    invert this into a stagnation-pressure recovery and produce stations 2
    (inlet exit) and 3 (combustor inlet).
    """

    if combustor_mach >= freestream_mach:
        raise CycleCalculationError(
            "Combustor Mach must be lower than freestream Mach for an inlet compression."
        )

    # Conserve stagnation temperature (adiabatic).
    Tt0 = freestream_state.stagnation_temperature_K
    Pt0 = freestream_state.stagnation_pressure_Pa

    # Apparent Pt loss from KE efficiency (Heiser & Pratt p. 117-style):
    # pi_inlet ~ [1 - (1 - eta_ke) * (1 - 1/(1 + (g-1)/2 M0^2))] ** (g/(g-1))
    g = gamma_air
    factor = 1.0 - (1.0 - eta_ke) * (
        1.0 - 1.0 / (1.0 + (g - 1.0) / 2.0 * freestream_mach**2)
    )
    pi_inlet = max(0.01, factor ** (g / (g - 1.0)))
    Pt2 = Pt0 * pi_inlet

    # Combustor inlet (station 3) — same Pt as station 2, static state set by
    # combustor_mach.
    T3 = Tt0 / (1.0 + (g - 1.0) / 2.0 * combustor_mach**2)
    P3 = Pt2 / (
        (1.0 + (g - 1.0) / 2.0 * combustor_mach**2) ** (g / (g - 1.0))
    )
    V3 = combustor_mach * speed_of_sound(T3)

    state_2 = StationState(
        station=2,
        name="Inlet exit",
        stagnation_temperature_K=Tt0,
        stagnation_pressure_Pa=Pt2,
        notes=[
            f"Multi-shock inlet, kinetic energy efficiency {eta_ke:.2f}.",
        ],
    )
    state_3 = StationState(
        station=3,
        name="Supersonic combustor inlet",
        static_temperature_K=T3,
        static_pressure_Pa=P3,
        stagnation_temperature_K=Tt0,
        stagnation_pressure_Pa=Pt2,
        mach=combustor_mach,
        velocity_m_s=V3,
        notes=["Supersonic combustor inlet state — no isolator pressure recovery modelled."],
    )
    return state_2, state_3, {
        "inlet_pressure_recovery": pi_inlet,
        "combustor_inlet_static_T_K": T3,
        "combustor_inlet_static_P_Pa": P3,
        "combustor_inlet_velocity_m_s": V3,
    }


def _supersonic_combustor(
    inlet_state: StationState,
    equivalence_ratio: float,
    stoich_far: float,
    eta_b: float,
    pressure_loss_fraction: float,
    fuel_heating_value_J_kg: float,
) -> tuple[StationState, float, dict[str, float]]:
    """Heat the supersonic stream at approximately constant Mach.

    Computes the Tt rise from the actual fuel-air ratio and heat release,
    then drops Pt by ``pressure_loss_fraction`` (combined wall friction and
    Rayleigh stagnation pressure loss). The combustor Mach is approximately
    preserved so the user-specified ``combustor_mach`` carries forward.
    """

    if not 0.05 < equivalence_ratio < 4.0:
        raise CycleCalculationError(
            "Equivalence ratio must be in (0.05, 4.0)."
        )
    if not 0.0 < eta_b <= 1.0:
        raise CycleCalculationError(
            "Combustor efficiency must be in (0, 1]."
        )
    if not 0.0 <= pressure_loss_fraction <= 0.4:
        raise CycleCalculationError(
            "Combustor pressure loss must be in [0, 0.4]."
        )
    fuel_air_ratio = equivalence_ratio * stoich_far
    # Energy balance: cp_gas * Tt_out = cp_air * Tt_in + eta_b * f * LHV / (1 + f)
    Tt_in = inlet_state.stagnation_temperature_K
    Tt_out = (
        cp_air * Tt_in
        + eta_b * fuel_air_ratio * fuel_heating_value_J_kg / (1.0 + fuel_air_ratio)
    ) / cp_gas

    Pt_out = inlet_state.stagnation_pressure_Pa * (1.0 - pressure_loss_fraction)
    if Tt_out <= Tt_in:
        raise CycleCalculationError(
            "Supersonic combustor heat addition produced no Tt rise."
        )
    state = StationState(
        station=4,
        name="Supersonic combustor exit",
        stagnation_temperature_K=Tt_out,
        stagnation_pressure_Pa=Pt_out,
        notes=[
            "Constant-Mach heat addition; Rayleigh-style total-pressure loss.",
        ],
    )
    return state, fuel_air_ratio, {
        "Tt_rise_K": Tt_out - Tt_in,
        "Tt_ratio": Tt_out / Tt_in,
    }


def simulate_scramjet_cycle(inputs: Any) -> dict[str, Any]:
    """Run the reduced-order scramjet cycle."""

    cycle = _coerce_inputs(inputs)
    if cycle.mach <= 1.0:
        raise CycleCalculationError(
            "Scramjet flight Mach must be > 1.0; recommended > 4."
        )
    atmosphere = isa_atmosphere(cycle.altitude_m)
    freestream = calculate_freestream_state(atmosphere, cycle.mach)

    state_2, state_3, inlet_meta = _inlet_compression(
        freestream.state,
        atmosphere.temperature_K,
        atmosphere.pressure_Pa,
        cycle.mach,
        cycle.combustor_mach,
        cycle.inlet_kinetic_energy_efficiency,
    )

    state_4, fuel_air_ratio, comb_meta = _supersonic_combustor(
        state_3,
        cycle.equivalence_ratio,
        cycle.stoichiometric_fuel_air_ratio,
        cycle.combustor_efficiency,
        cycle.combustor_pressure_loss_fraction,
        cycle.fuel_heating_value_J_kg,
    )

    nozzle = expand_nozzle_stream(
        state_4,
        atmosphere.pressure_Pa,
        cycle.mass_flow_air_kg_s,
        fuel_air_ratio,
        freestream.state.velocity_m_s or 0.0,
        cycle.nozzle_efficiency,
        9,
        "Scramjet nozzle exit",
        gamma_gas,
        cp_gas,
        divergent_area_ratio=cycle.nozzle_divergent_area_ratio,
    )

    V0 = freestream.state.velocity_m_s or 0.0
    thrust_N = nozzle.momentum_thrust_N + nozzle.pressure_thrust_N
    if thrust_N <= 0.0:
        raise CycleCalculationError(
            "Scramjet produced non-positive net thrust — combustor too weak or inlet recovery too low."
        )
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
        "Educational reduced-order scramjet approximation active.",
        "No isolator, no finite-rate chemistry, no real-gas dissociation modelled.",
    ]
    if cycle.mach < 4.0:
        warnings.append(
            "CAUTION: Scramjet below efficient operating Mach (~M4)."
        )
    if cycle.combustor_mach < 1.5:
        warnings.append(
            "CAUTION: Combustor Mach low; mode is closer to ramjet — check isolator assumption."
        )
    if state_4.stagnation_temperature_K > 3000.0:
        warnings.append(
            "CRITICAL: Combustor stagnation temperature exceeds 3000 K — dissociation losses are unmodelled."
        )
    if state_3.static_temperature_K is not None and state_3.static_temperature_K > 1700.0:
        warnings.append(
            "CAUTION: Combustor inlet static temperature is high — autoignition margin shrinks."
        )
    if cycle.equivalence_ratio > 1.3:
        warnings.append(
            "CAUTION: Equivalence ratio above 1.3 — rich operation; thrust/TSFC trends questionable."
        )
    if not nozzle.choked:
        warnings.append("INFO: Nozzle is unchoked at this operating point.")
    if nozzle.metadata.get("shock_in_nozzle"):
        warnings.append(
            "CAUTION: Expansion nozzle is over-expanded — a normal shock sits "
            "in the divergent section (subsonic exit). Reduce the area ratio."
        )

    states = [freestream.state, state_2, state_3, state_4, nozzle.state]

    return {
        "engine_type": "scramjet",
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
            "combustor_mode": "supersonic",
            "combustor_mach": cycle.combustor_mach,
            "equivalence_ratio": cycle.equivalence_ratio,
            "inlet_pressure_recovery": inlet_meta["inlet_pressure_recovery"],
            "combustor_inlet_static_T_K": inlet_meta["combustor_inlet_static_T_K"],
            "combustor_inlet_static_P_Pa": inlet_meta["combustor_inlet_static_P_Pa"],
            "combustor_inlet_velocity_m_s": inlet_meta["combustor_inlet_velocity_m_s"],
            "Tt_rise_K": comb_meta["Tt_rise_K"],
            "Tt_ratio": comb_meta["Tt_ratio"],
            "ram_pressure_ratio": freestream.state.stagnation_pressure_Pa
            / atmosphere.pressure_Pa,
        },
    }


_FIELDS = ScramjetCycleInputs.__dataclass_fields__.keys()


def _coerce_inputs(inputs: Any) -> ScramjetCycleInputs:
    """Normalise inputs into a ScramjetCycleInputs dataclass."""

    if isinstance(inputs, ScramjetCycleInputs):
        return inputs
    defaults = ScramjetCycleInputs()
    kwargs: dict[str, Any] = {}
    for name in _FIELDS:
        if hasattr(inputs, name):
            kwargs[name] = getattr(inputs, name)
        else:
            kwargs[name] = getattr(defaults, name)
    return ScramjetCycleInputs(**kwargs)
