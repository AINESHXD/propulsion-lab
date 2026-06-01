"""Turbojet performance bookkeeping."""

from __future__ import annotations

from app.engine_core.types import CycleCalculationError


def safe_divide(
    numerator: float,
    denominator: float,
    fallback: float,
    warning_message: str,
    warnings: list[str],
) -> float:
    """Divide with a fallback value and warning for zero or negative denominators."""

    if denominator <= 0.0:
        warnings.append(warning_message)
        return fallback
    return numerator / denominator


def compute_turbojet_performance(
    mass_flow_air_kg_s: float,
    fuel_air_ratio: float,
    fuel_heating_value_J_kg: float,
    freestream_velocity_m_s: float,
    exit_velocity_m_s: float,
    pressure_thrust_N: float,
    fuel_flow_kg_s_override: float | None = None,
    exit_mass_flow_kg_s_override: float | None = None,
) -> tuple[dict[str, float], list[str]]:
    """Compute thrust, TSFC, and simple efficiency estimates for the turbojet.

    The two ``*_override`` parameters let callers that track bleed and cooling
    air independently of the combustion fuel-air ratio supply both the actual
    fuel flow and the actual exit mass flow. When omitted the historical
    ``f * m_air`` and ``(1+f) * m_air`` shortcuts are used.
    """

    warnings: list[str] = []
    fuel_flow_kg_s = (
        fuel_flow_kg_s_override
        if fuel_flow_kg_s_override is not None
        else fuel_air_ratio * mass_flow_air_kg_s
    )
    exit_mass_flow_kg_s = (
        exit_mass_flow_kg_s_override
        if exit_mass_flow_kg_s_override is not None
        else mass_flow_air_kg_s * (1.0 + fuel_air_ratio)
    )
    momentum_thrust_N = (
        exit_mass_flow_kg_s * exit_velocity_m_s
        - mass_flow_air_kg_s * freestream_velocity_m_s
    )
    thrust_N = momentum_thrust_N + pressure_thrust_N
    if thrust_N <= 0.0:
        raise CycleCalculationError(
            "Cycle produced non-positive net thrust; TSFC is undefined."
        )

    tsfc_kg_per_N_s = fuel_flow_kg_s / thrust_N
    jet_kinetic_power_change_W = 0.5 * (
        exit_mass_flow_kg_s * exit_velocity_m_s**2
        - mass_flow_air_kg_s * freestream_velocity_m_s**2
    )
    pressure_thrust_power_W = pressure_thrust_N * freestream_velocity_m_s
    jet_power_available_W = jet_kinetic_power_change_W + pressure_thrust_power_W
    fuel_power_W = fuel_flow_kg_s * fuel_heating_value_J_kg
    propulsive_power_W = thrust_N * freestream_velocity_m_s

    thermal_efficiency = safe_divide(
        jet_power_available_W,
        fuel_power_W,
        0.0,
        "Thermal efficiency estimate is undefined because fuel power is non-positive.",
        warnings,
    )
    if jet_power_available_W <= 0.0:
        warnings.append("Jet power available to propulsion is non-positive.")
        thermal_efficiency = 0.0

    propulsive_efficiency = safe_divide(
        propulsive_power_W,
        jet_power_available_W,
        0.0,
        "Propulsive efficiency estimate is undefined for non-positive jet power.",
        warnings,
    )
    if freestream_velocity_m_s == 0.0:
        warnings.append(
            "Static case: propulsive and overall efficiency estimates are zero by definition."
        )
        propulsive_efficiency = 0.0

    overall_efficiency = safe_divide(
        propulsive_power_W,
        fuel_power_W,
        0.0,
        "Overall efficiency estimate is undefined because fuel power is non-positive.",
        warnings,
    )

    return (
        {
            "thrust_N": thrust_N,
            "thrust_kN": thrust_N / 1000.0,
            "specific_thrust_N_per_kg_s": thrust_N / mass_flow_air_kg_s,
            "fuel_air_ratio": fuel_air_ratio,
            "fuel_flow_kg_s": fuel_flow_kg_s,
            "TSFC_kg_per_N_s": tsfc_kg_per_N_s,
            "TSFC_kg_per_kN_hr": tsfc_kg_per_N_s * 1000.0 * 3600.0,
            "momentum_thrust_N": momentum_thrust_N,
            "pressure_thrust_N": pressure_thrust_N,
            "thermal_efficiency_estimate": thermal_efficiency,
            "propulsive_efficiency_estimate": propulsive_efficiency,
            "overall_efficiency_estimate": overall_efficiency,
        },
        warnings,
    )
