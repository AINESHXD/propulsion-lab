"""Educational gas-generator + free-power-turbine turboprop solver.

The cycle is:

* Inlet (station 2)
* Single-spool compressor (station 3)
* Combustor (station 4)
* Gas-generator (HP) turbine drives the compressor (station 45)
* Free power turbine (LP) extracts shaft power for the propeller (station 5)
* Residual convergent nozzle produces a small jet thrust (station 9)

Propeller modelling
-------------------
The propeller efficiency is computed from a simplified blade-element-lite
curve based on advance ratio ``J = V0 / (n * D)`` and tip Mach number. At
static / low-Mach the model degenerates to an actuator-disk approximation
because the advance-ratio curve is undefined there. Both regimes are labelled
in the output ``warnings`` list so the user knows which branch was used.

These are educational reduced-order approximations — they are not propeller
maps and they do not capture stall, helical-tip loss, or compressibility tip
loss past M_tip ≈ 0.95.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.engine_core.atmosphere import isa_atmosphere
from app.engine_core.combustor import calculate_combustor_exit
from app.engine_core.combustor_equilibrium import calculate_combustor_exit_equilibrium
from app.engine_core.compressor import calculate_compressor_exit
from app.engine_core.constants import cp_gas, gamma_gas
from app.engine_core.gas_properties import speed_of_sound
from app.engine_core.inlet import calculate_freestream_state, calculate_inlet_exit
from app.engine_core.secondary_air import apply_bleed_and_cooling
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
class TurbopropCycleInputs:
    """Validated turboprop inputs."""

    altitude_m: float = 5000.0
    mach: float = 0.35
    mass_flow_air_kg_s: float = 12.0
    compressor_pressure_ratio: float = 9.0
    compressor_efficiency: float = 0.84
    turbine_inlet_temperature_K: float = 1250.0
    hp_turbine_efficiency: float = 0.88
    power_turbine_efficiency: float = 0.88
    combustor_efficiency: float = 0.99
    combustor_pressure_loss_fraction: float = 0.05
    mechanical_efficiency: float = 0.98
    gearbox_efficiency: float = 0.985
    propeller_diameter_m: float = 3.0
    propeller_rpm: float = 1200.0
    peak_propeller_efficiency: float = 0.86
    advance_ratio_at_peak: float = 1.1
    minimum_core_nozzle_temperature_K: float = 700.0
    nozzle_efficiency: float = 0.92
    inlet_pressure_recovery: float = 0.98
    fuel_heating_value_J_kg: float = 43e6
    use_equilibrium_combustion: bool = False
    equilibrium_fuel_species: str = "CH4"
    bleed_fraction_hpc_exit: float = 0.0
    cooling_fraction_hpt_inlet: float = 0.0


def _propeller_efficiency(
    freestream_velocity_m_s: float,
    rpm: float,
    diameter_m: float,
    peak_efficiency: float,
    advance_ratio_at_peak: float,
    tip_mach: float,
) -> tuple[float, str, float]:
    """Return propeller efficiency, regime label, and advance ratio.

    Uses an analytic blunted-parabola curve in advance ratio J and a
    compressibility derate for tip Mach above 0.85. Returns 0.0 efficiency in
    the static case (and signals the caller to use actuator-disk thrust).
    """

    rev_per_s = rpm / 60.0
    if rev_per_s <= 0.0 or diameter_m <= 0.0:
        raise CycleCalculationError(
            "Propeller RPM and diameter must be positive."
        )

    if freestream_velocity_m_s < 5.0:
        return 0.0, "static-actuator-disk", 0.0

    advance_ratio = freestream_velocity_m_s / (rev_per_s * diameter_m)
    # Smooth bell curve peaking at advance_ratio_at_peak. Width chosen so the
    # 50% point falls roughly one advance ratio away from the peak — a
    # reasonable educational approximation for a constant-speed propeller.
    width = 1.1 * advance_ratio_at_peak
    raw_eta = peak_efficiency * math.exp(
        -0.5 * ((advance_ratio - advance_ratio_at_peak) / width) ** 2
    )
    # Compressibility derate above M_tip = 0.85.
    if tip_mach > 0.85:
        raw_eta *= max(0.4, 1.0 - 1.5 * (tip_mach - 0.85) ** 2)
    return max(0.0, min(raw_eta, peak_efficiency)), "advance-ratio", advance_ratio


def _actuator_disk_static_thrust(
    shaft_power_W: float,
    diameter_m: float,
    ambient_density_kg_m3: float,
) -> float:
    """Actuator-disk static thrust estimate (Froude momentum theory).

    F = (2 * rho * A * P^2)^(1/3) — the classical ideal limit for an actuator
    disk doing shaft work into still air.
    """

    if shaft_power_W <= 0.0 or diameter_m <= 0.0 or ambient_density_kg_m3 <= 0.0:
        return 0.0
    disk_area = math.pi * (diameter_m / 2.0) ** 2
    return (2.0 * ambient_density_kg_m3 * disk_area * shaft_power_W**2) ** (1.0 / 3.0)


def simulate_turboprop_cycle(inputs: Any) -> dict[str, Any]:
    """Run the educational turboprop cycle."""

    cycle = _coerce_inputs(inputs)
    atmosphere = isa_atmosphere(cycle.altitude_m)
    freestream = calculate_freestream_state(atmosphere, cycle.mach)
    inlet = calculate_inlet_exit(freestream.state, cycle.inlet_pressure_recovery)

    compressor = calculate_compressor_exit(
        inlet.state,
        cycle.compressor_pressure_ratio,
        cycle.compressor_efficiency,
    )
    if cycle.use_equilibrium_combustion:
        combustor = calculate_combustor_exit_equilibrium(
            compressor.state,
            cycle.turbine_inlet_temperature_K,
            cycle.combustor_efficiency,
            cycle.combustor_pressure_loss_fraction,
            cycle.fuel_heating_value_J_kg,
            fuel=cycle.equilibrium_fuel_species,
        )
    else:
        combustor = calculate_combustor_exit(
            compressor.state,
            cycle.turbine_inlet_temperature_K,
            cycle.combustor_efficiency,
            cycle.combustor_pressure_loss_fraction,
            cycle.fuel_heating_value_J_kg,
        )
    fuel_air_ratio = float(combustor.metadata["fuel_air_ratio"])

    # ---- HPC-exit bleed + HPT cooling air (shared helper) -----------------
    secondary = apply_bleed_and_cooling(
        reference_air_kg_s=cycle.mass_flow_air_kg_s,
        compressor_exit_state=compressor.state,
        combustor_exit_state=combustor.state,
        fuel_air_ratio=fuel_air_ratio,
        bleed_fraction=cycle.bleed_fraction_hpc_exit,
        cooling_fraction=cycle.cooling_fraction_hpt_inlet,
    )
    turbine_inlet = secondary.turbine_inlet_state
    gas_ratio = secondary.gas_mass_flow_ratio  # m_HPT / m_air

    # ---- HP turbine drives the compressor (station 45) --------------------
    compressor_work = float(combustor.metadata.get("compressor_specific_work_J_kg", 0.0))
    if compressor_work <= 0.0:
        compressor_work = float(compressor.metadata["compressor_specific_work_J_kg"])
    Tt4 = turbine_inlet.stagnation_temperature_K
    drop_hpt_K = compressor_work / (
        gas_ratio * cp_gas * cycle.mechanical_efficiency
    )
    Tt45 = Tt4 - drop_hpt_K
    if Tt45 <= 0.0:
        raise CycleCalculationError("HP turbine extracts more energy than available.")
    Tt45s = Tt4 - drop_hpt_K / cycle.hp_turbine_efficiency
    Pt45 = turbine_inlet.stagnation_pressure_Pa * (Tt45s / Tt4) ** (
        gamma_gas / (gamma_gas - 1.0)
    )
    state_45 = StationState(
        station=45,
        name="HP turbine exit (gas-gen)",
        stagnation_temperature_K=Tt45,
        stagnation_pressure_Pa=Pt45,
        notes=["HP turbine supplies compressor work."],
    )

    # ---- Free power turbine -----------------------------------------------
    # Bound the power-turbine work by either the minimum residual stagnation
    # temperature (keeps the nozzle viable) or by leaving Pt5 > ambient.
    max_drop_by_T_K = max(0.0, Tt45 - cycle.minimum_core_nozzle_temperature_K)
    # Iterate to find PT work such that Pt5 > 1.05 * ambient for a usable
    # residual nozzle:
    drop_pt_K = max_drop_by_T_K
    Tt5 = Tt45 - drop_pt_K
    Tt5s = Tt45 - drop_pt_K / cycle.power_turbine_efficiency
    Pt5 = Pt45 * (Tt5s / Tt45) ** (gamma_gas / (gamma_gas - 1.0))
    while Pt5 < 1.05 * atmosphere.pressure_Pa and drop_pt_K > 5.0:
        drop_pt_K *= 0.9
        Tt5 = Tt45 - drop_pt_K
        Tt5s = Tt45 - drop_pt_K / cycle.power_turbine_efficiency
        Pt5 = Pt45 * (Tt5s / Tt45) ** (gamma_gas / (gamma_gas - 1.0))

    if Tt5 <= 0.0 or Pt5 <= atmosphere.pressure_Pa:
        raise CycleCalculationError(
            "Power turbine work extraction left the residual nozzle unusable."
        )
    state_5 = StationState(
        station=5,
        name="Power turbine exit / nozzle inlet",
        stagnation_temperature_K=Tt5,
        stagnation_pressure_Pa=Pt5,
        notes=["Free power turbine supplies the propeller shaft."],
    )

    # Shaft power available at the prop shaft = m_dot_gas * cp_gas * drop_PT * eta_mech * eta_gb
    # m_dot_gas through the turbine is the HPT inlet flow (combustion gas +
    # re-introduced cooling air), reduced by any customer bleed.
    shaft_specific_work_J_kg = cp_gas * drop_pt_K * cycle.power_turbine_efficiency
    shaft_power_W = (
        secondary.hpt_inlet_kg_s
        * shaft_specific_work_J_kg
        * cycle.mechanical_efficiency
        * cycle.gearbox_efficiency
    )

    # ---- Propeller --------------------------------------------------------
    V0 = freestream.state.velocity_m_s or 0.0
    a_local = atmosphere.speed_of_sound_m_s
    tip_velocity = math.sqrt(
        V0**2 + (math.pi * cycle.propeller_diameter_m * cycle.propeller_rpm / 60.0) ** 2
    )
    tip_mach = tip_velocity / a_local

    eta_prop, regime, advance_ratio = _propeller_efficiency(
        V0,
        cycle.propeller_rpm,
        cycle.propeller_diameter_m,
        cycle.peak_propeller_efficiency,
        cycle.advance_ratio_at_peak,
        tip_mach,
    )
    if regime == "advance-ratio":
        propeller_thrust_N = eta_prop * shaft_power_W / max(V0, 1e-3)
    else:
        propeller_thrust_N = _actuator_disk_static_thrust(
            shaft_power_W, cycle.propeller_diameter_m, atmosphere.density_kg_m3
        )
        # back-compute an effective static efficiency for reporting only:
        if shaft_power_W > 0.0:
            # actuator-disk effective propulsion eff is undefined at V0=0, so
            # report the figure of merit (thrust per kW)
            eta_prop = 0.0

    # ---- Residual nozzle (small jet thrust) -------------------------------
    # Ram drag is on the core air that entered (mass_flow_air_kg_s); the gas
    # leaving the nozzle is the HPT-inlet flow. Passing (gas_ratio - 1) as the
    # effective fuel-air ratio makes the nozzle exit mass = m_air * gas_ratio
    # = HPT inlet flow, while keeping the ram term on the inlet air. With no
    # bleed this reduces exactly to the plain fuel-air ratio.
    nozzle = expand_nozzle_stream(
        state_5,
        atmosphere.pressure_Pa,
        cycle.mass_flow_air_kg_s,
        gas_ratio - 1.0,
        V0,
        cycle.nozzle_efficiency,
        9,
        "Residual core nozzle exit",
        gamma_gas,
        cp_gas,
    )
    jet_thrust_N = nozzle.momentum_thrust_N + nozzle.pressure_thrust_N

    thrust_N = propeller_thrust_N + jet_thrust_N
    if thrust_N <= 0.0:
        raise CycleCalculationError("Turboprop produced non-positive net thrust.")

    fuel_flow_kg_s = secondary.fuel_flow_kg_s

    # Equivalent shaft power: SHP + jet thrust * V0 (Hill & Peterson).
    equivalent_shaft_power_W = shaft_power_W + jet_thrust_N * V0
    # Brake specific fuel consumption — referred to shaft power (kg/kW/h).
    bsfc_kg_per_kW_h = (
        fuel_flow_kg_s * 3.6e6 / shaft_power_W if shaft_power_W > 0.0 else 0.0
    )

    jet_kinetic_power_change_W = 0.5 * (
        secondary.hpt_inlet_kg_s * nozzle.exit_velocity_m_s**2
        - cycle.mass_flow_air_kg_s * V0**2
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
        "Turboprop model uses a simplified propeller curve, not a propeller map.",
    ]
    if tip_mach > 0.92:
        warnings.append(
            "CAUTION: Propeller tip Mach number is high; tip losses are simplified."
        )
    if eta_prop < 0.4 and regime == "advance-ratio":
        warnings.append(
            "CAUTION: Propeller efficiency is low at this advance ratio."
        )
    if cycle.gearbox_efficiency < 0.95:
        warnings.append(
            "INFO: Gearbox efficiency below 0.95; loss is high for a healthy gearbox."
        )
    if regime == "static-actuator-disk":
        warnings.append(
            "INFO: Static / low-Mach regime — propeller thrust uses actuator-disk model."
        )

    states = [
        freestream.state,
        inlet.state,
        compressor.state,
        combustor.state,
        state_45,
        state_5,
        nozzle.state,
    ]

    return {
        "engine_type": "turboprop",
        "thrust_N": thrust_N,
        "thrust_kN": thrust_N / 1000.0,
        "propeller_thrust_N": propeller_thrust_N,
        "jet_thrust_N": jet_thrust_N,
        "specific_thrust_N_per_kg_s": thrust_N / cycle.mass_flow_air_kg_s,
        "fuel_air_ratio": fuel_air_ratio,
        "fuel_flow_kg_s": fuel_flow_kg_s,
        "TSFC_kg_per_N_s": fuel_flow_kg_s / thrust_N,
        "TSFC_kg_per_kN_hr": fuel_flow_kg_s / thrust_N * 1000.0 * 3600.0,
        "shaft_power_W": shaft_power_W,
        "shaft_power_kW": shaft_power_W / 1000.0,
        "equivalent_shaft_power_W": equivalent_shaft_power_W,
        "equivalent_shaft_power_kW": equivalent_shaft_power_W / 1000.0,
        "BSFC_kg_per_kW_h": bsfc_kg_per_kW_h,
        "exit_velocity_m_s": nozzle.exit_velocity_m_s,
        "freestream_velocity_m_s": V0,
        "nozzle_choked": nozzle.choked,
        "momentum_thrust_N": nozzle.momentum_thrust_N,
        "pressure_thrust_N": nozzle.pressure_thrust_N,
        **efficiencies,
        "station_table": station_table(*states),
        "warnings": merge_warnings(
            freestream.warnings,
            inlet.warnings,
            compressor.warnings,
            combustor.warnings,
            warnings,
        ),
        "extra": {
            "propeller_efficiency": eta_prop,
            "propeller_regime": regime,
            "advance_ratio": advance_ratio,
            "propeller_tip_mach": tip_mach,
            "propeller_tip_velocity_m_s": tip_velocity,
            "hpt_drop_K": drop_hpt_K,
            "power_turbine_drop_K": drop_pt_K,
            "core_nozzle_choked": nozzle.choked,
            "bleed_fraction_hpc_exit": cycle.bleed_fraction_hpc_exit,
            "cooling_fraction_hpt_inlet": cycle.cooling_fraction_hpt_inlet,
            "combustor_air_mass_flow_kg_s": secondary.combustor_air_kg_s,
            "hpt_inlet_mass_flow_kg_s": secondary.hpt_inlet_kg_s,
            "hpt_inlet_stagnation_temperature_K": secondary.metadata[
                "hpt_inlet_stagnation_temperature_K"
            ],
        },
    }


_FIELDS = TurbopropCycleInputs.__dataclass_fields__.keys()


def _coerce_inputs(inputs: Any) -> TurbopropCycleInputs:
    """Normalise inputs into a TurbopropCycleInputs dataclass."""

    if isinstance(inputs, TurbopropCycleInputs):
        return inputs
    defaults = TurbopropCycleInputs()
    kwargs: dict[str, Any] = {}
    for name in _FIELDS:
        if hasattr(inputs, name):
            kwargs[name] = getattr(inputs, name)
        else:
            kwargs[name] = getattr(defaults, name)
    return TurbopropCycleInputs(**kwargs)
