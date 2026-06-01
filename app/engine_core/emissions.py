"""Reactor-network combustor emissions: NOx, CO, unburned HC (Month-4 feature).

The cycle modules (``combustor.py`` / ``combustor_equilibrium.py``) answer *how
hot* the combustor runs and *how much fuel* it burns. They say nothing about
*pollutants*, because emission indices are set by finite-rate chemistry, not by
an energy balance. This module adds that layer with a small two-zone Cantera
reactor network and reports emission indices (EI, grams of pollutant per kg of
fuel) plus an ICAO landing–takeoff (LTO) NOx aggregation.

Model
-----
Real combustors are staged: a near-stoichiometric **primary zone** anchors the
flame and produces almost all the thermal (Zeldovich) NOx, then **dilution air**
quenches the gas down to the turbine-inlet temperature, freezing the NOx and
burning out CO. We mirror that:

1. **Primary zone (well-stirred reactor).** Burn at an effective primary-zone
   equivalence ratio ``phi_primary`` and equilibrate adiabatically to obtain the
   flame temperature ``T_pz``. The equilibrium NOx is then *discarded* and NO is
   re-grown kinetically from zero for a residence time ``tau_primary`` — thermal
   NOx is rate-limited (the Zeldovich mechanism is slow), so a finite residence
   gives realistic, sub-equilibrium NO rather than the much larger equilibrium
   value.

2. **Dilution zone (plug-flow reactor).** The remaining air is injected in
   ``n_dilution`` axial slugs. Each slug mixes adiabatically (cooling the gas),
   then chemistry advances for ``tau_secondary / n_dilution``. NO freezes as the
   temperature falls; CO oxidises toward CO2. The axial T / NO / CO profile is
   returned for visualisation.

``phi_primary`` is a calibration constant, not a measured quantity: it is tuned
so EINOx at modern-combustor takeoff conditions (T3 ~ 820 K, P3 ~ 30 atm) lands
in the ICAO databank band (~20–35 g/kg). NOx is the quantity this module is
calibrated and validated on; CO and unburned-HC are reported as lower-fidelity
secondary estimates, and soot is a qualitative proxy (GRI-Mech 3.0 has no soot
chemistry).

Without Cantera the module falls back to a documented P3–T3 NOx correlation so
callers always get a number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Final

from app.engine_core.gas_service import is_cantera_available

try:                                # pragma: no cover - import-time branch
    import cantera as ct            # type: ignore[import-not-found]
except ImportError:                 # pragma: no cover
    ct = None                       # type: ignore[assignment]


# Air composition shared with gas_service (mole basis).
_AIR_X: Final[str] = "O2:0.21, N2:0.79"

# Default calibration of the reactor network. ``phi_primary`` is chosen so that
# EINOx at takeoff-class inlet conditions sits inside the ICAO databank band.
PHI_PRIMARY_DEFAULT: Final[float] = 0.73
TAU_PRIMARY_S_DEFAULT: Final[float] = 0.002
TAU_SECONDARY_S_DEFAULT: Final[float] = 0.004
N_DILUTION_DEFAULT: Final[int] = 6

# N-bearing pollutant species reset to zero before the kinetic NO clock starts.
_NOX_RESET_SPECIES: Final[tuple[str, ...]] = (
    "NO", "NO2", "N2O", "N", "NH", "NH2", "NH3", "HNO", "NNH", "HCN", "CN", "NCO",
)


@dataclass(frozen=True)
class AxialPoint:
    """One station along the combustor for the axial emissions profile."""

    x_fraction: float          # 0 = primary-zone exit, 1 = combustor exit
    temperature_K: float
    no_ppm: float
    co_ppm: float


@dataclass(frozen=True)
class EmissionResult:
    """Emission indices (g pollutant / kg fuel) and supporting detail."""

    ei_nox_g_per_kg: float
    ei_co_g_per_kg: float
    ei_hc_g_per_kg: float
    ei_co2_g_per_kg: float
    ei_h2o_g_per_kg: float
    soot_proxy: float                       # 0 (clean) .. 1 (sooty), qualitative
    primary_zone_temperature_K: float
    phi_primary: float
    phi_overall: float
    fuel: str
    source: str                             # "reactor-network" or "correlation"
    axial_profile: list[AxialPoint] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stoichiometry helpers
# ---------------------------------------------------------------------------

# Mass stoichiometric fuel-air ratio for fuels we support without Cantera.
_FAR_STOICH_FALLBACK: Final[dict[str, float]] = {
    "CH4": 0.0584, "C2H6": 0.0625, "C3H8": 0.0640, "H2": 0.0292, "C2H4": 0.0680,
}


@lru_cache(maxsize=8)
def far_stoichiometric(fuel: str = "CH4") -> float:
    """Stoichiometric mass fuel-air ratio for ``fuel`` burning in air."""

    if is_cantera_available() and ct is not None:
        gas = _solution()
        gas.set_equivalence_ratio(1.0, fuel, _AIR_X)
        y_fuel = float(gas[fuel].Y[0]) if fuel in gas.species_names else 0.0
        if 0.0 < y_fuel < 1.0:
            return y_fuel / (1.0 - y_fuel)
    if fuel in _FAR_STOICH_FALLBACK:
        return _FAR_STOICH_FALLBACK[fuel]
    return _FAR_STOICH_FALLBACK["CH4"]


def equivalence_ratio(fuel_air_ratio: float, fuel: str = "CH4") -> float:
    """Overall equivalence ratio ``phi`` from the mass fuel-air ratio."""

    if fuel_air_ratio <= 0.0:
        return 0.0
    return fuel_air_ratio / far_stoichiometric(fuel)


# ---------------------------------------------------------------------------
# Cantera Solution dedicated to the reactor network
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _solution():
    """One cached GRI-Mech 3.0 Solution for the emissions reactor network.

    Kept separate from ``gas_service._solution`` so attaching reactors here never
    perturbs the equilibrium-combustor property lookups.
    """

    if not (is_cantera_available() and ct is not None):
        return None
    return ct.Solution("gri30.yaml")


def _ei(mass_fraction: float, mixture_mass_per_kg_fuel: float) -> float:
    """Emission index (g / kg fuel) from a species mass fraction."""

    return max(0.0, mass_fraction) * mixture_mass_per_kg_fuel * 1000.0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def combustor_emissions(
    combustor_inlet_temperature_K: float,
    combustor_inlet_pressure_Pa: float,
    fuel_air_ratio: float,
    *,
    fuel: str = "CH4",
    phi_primary: float = PHI_PRIMARY_DEFAULT,
    tau_primary_s: float = TAU_PRIMARY_S_DEFAULT,
    tau_secondary_s: float = TAU_SECONDARY_S_DEFAULT,
    n_dilution: int = N_DILUTION_DEFAULT,
) -> EmissionResult:
    """Emission indices for a combustor running at the given inlet state + FAR.

    Parameters
    ----------
    combustor_inlet_temperature_K, combustor_inlet_pressure_Pa
        Compressor-exit (combustor-inlet, station 3) stagnation state.
    fuel_air_ratio
        Overall mass fuel-air ratio delivered by the cycle.
    fuel
        Cantera species name (methane is the educational kerosene surrogate).
    phi_primary
        Effective primary-zone equivalence ratio (calibration constant).
    tau_primary_s, tau_secondary_s
        Residence times of the primary and dilution zones.
    n_dilution
        Number of axial dilution-air injection steps (PFR discretisation).
    """

    if combustor_inlet_temperature_K <= 0.0 or combustor_inlet_pressure_Pa <= 0.0:
        raise ValueError("Combustor inlet temperature and pressure must be positive.")
    if fuel_air_ratio <= 0.0:
        raise ValueError("Fuel-air ratio must be positive.")
    if not 0.3 <= phi_primary <= 1.6:
        raise ValueError("Primary-zone equivalence ratio must be between 0.3 and 1.6.")

    phi_overall = equivalence_ratio(fuel_air_ratio, fuel)

    if is_cantera_available() and ct is not None:
        return _reactor_network(
            combustor_inlet_temperature_K,
            combustor_inlet_pressure_Pa,
            fuel_air_ratio,
            phi_overall,
            fuel,
            phi_primary,
            tau_primary_s,
            tau_secondary_s,
            max(1, int(n_dilution)),
        )
    return _correlation_fallback(
        combustor_inlet_temperature_K,
        combustor_inlet_pressure_Pa,
        phi_overall,
        fuel,
        phi_primary,
    )


def _reactor_network(
    T3_K: float,
    P_Pa: float,
    far_overall: float,
    phi_overall: float,
    fuel: str,
    phi_primary: float,
    tau_primary_s: float,
    tau_secondary_s: float,
    n_dilution: int,
) -> EmissionResult:
    gas = _solution()
    idx = {s: gas.species_index(s) for s in ("NO", "NO2", "CO", "CO2", "H2O")}
    mw = gas.molecular_weights
    fuel_idx = gas.species_index(fuel) if fuel in gas.species_names else None

    far_stoich = far_stoichiometric(fuel)
    notes: list[str] = []

    # ---- Primary zone: adiabatic flame, then kinetic NO from zero ----------
    gas.set_equivalence_ratio(phi_primary, fuel, _AIR_X)
    gas.TP = T3_K, P_Pa
    gas.equilibrate("HP")
    primary_flame_K = float(gas.T)

    X = gas.X
    for sp in _NOX_RESET_SPECIES:
        if sp in gas.species_names:
            X[gas.species_index(sp)] = 0.0
    gas.TPX = primary_flame_K, P_Pa, X            # renormalises, NO clock at zero

    reactor = ct.IdealGasConstPressureReactor(gas, clone=False)
    net = ct.ReactorNet([reactor])
    try:
        net.advance(tau_primary_s)
    except Exception as exc:                       # pragma: no cover - solver guard
        notes.append(f"Primary-zone integration truncated: {exc}")

    # Masses per kg of fuel.
    m_primary = 1.0 + (1.0 / far_stoich) / phi_primary
    m_total = 1.0 + 1.0 / far_overall
    m_dilution = max(0.0, m_total - m_primary)

    # Air enthalpy + composition for adiabatic mixing (captured once).
    y_stream = gas.Y.copy()
    h_stream = float(gas.enthalpy_mass)
    gas.TPX = T3_K, P_Pa, _AIR_X
    h_air = float(gas.enthalpy_mass)
    y_air = gas.Y.copy()

    profile: list[AxialPoint] = [
        AxialPoint(0.0, primary_flame_K,
                   _ppm(gas, y_stream, "NO"), _ppm(gas, y_stream, "CO"))
    ]

    # ---- Dilution zone: axial plug-flow with staged air injection ----------
    m_cur = m_primary
    if m_dilution > 0.0 and n_dilution > 0:
        dm = m_dilution / n_dilution
        dt = tau_secondary_s / n_dilution
        for i in range(n_dilution):
            y_mix = (m_cur * y_stream + dm * y_air) / (m_cur + dm)
            h_mix = (m_cur * h_stream + dm * h_air) / (m_cur + dm)
            gas.HPY = h_mix, P_Pa, y_mix
            reactor = ct.IdealGasConstPressureReactor(gas, clone=False)
            net = ct.ReactorNet([reactor])
            try:
                net.advance(dt)
            except Exception as exc:               # pragma: no cover - solver guard
                notes.append(f"Dilution step {i + 1} truncated: {exc}")
            m_cur += dm
            y_stream = gas.Y.copy()
            h_stream = float(gas.enthalpy_mass)
            profile.append(AxialPoint(
                (i + 1) / n_dilution, float(gas.T),
                _ppm(gas, y_stream, "NO"), _ppm(gas, y_stream, "CO"),
            ))
    else:
        notes.append(
            "Overall mixture is richer than the primary zone; no dilution air added."
        )

    # ---- Emission indices from the final (diluted) stream ------------------
    y_no = float(y_stream[idx["NO"]])
    y_no2 = float(y_stream[idx["NO2"]])
    no2_equiv = y_no * (mw[idx["NO2"]] / mw[idx["NO"]]) + y_no2
    ei_nox = _ei(no2_equiv, m_total)
    ei_co = _ei(float(y_stream[idx["CO"]]), m_total)
    ei_hc = _ei(float(y_stream[fuel_idx]), m_total) if fuel_idx is not None else 0.0
    ei_co2 = _ei(float(y_stream[idx["CO2"]]), m_total)
    ei_h2o = _ei(float(y_stream[idx["H2O"]]), m_total)

    if ei_nox > 45.0:
        notes.append("EINOx is high — primary zone is running hot; expect a NOx-heavy combustor.")
    if T3_K < 600.0:
        notes.append("Low combustor-inlet temperature (part-power); CO burnout is incomplete.")

    return EmissionResult(
        ei_nox_g_per_kg=ei_nox,
        ei_co_g_per_kg=ei_co,
        ei_hc_g_per_kg=ei_hc,
        ei_co2_g_per_kg=ei_co2,
        ei_h2o_g_per_kg=ei_h2o,
        soot_proxy=_soot_proxy(phi_primary, P_Pa),
        primary_zone_temperature_K=primary_flame_K,
        phi_primary=phi_primary,
        phi_overall=phi_overall,
        fuel=fuel,
        source="reactor-network",
        axial_profile=profile,
        notes=notes,
    )


def _ppm(gas, mass_fractions, species: str) -> float:
    """Mole-fraction ppm of ``species`` for a frozen mass-fraction vector."""

    if species not in gas.species_names:
        return 0.0
    mw = gas.molecular_weights
    i = gas.species_index(species)
    mean_mw = 1.0 / sum(mass_fractions[j] / mw[j] for j in range(len(mass_fractions)))
    x_i = mass_fractions[i] / mw[i] * mean_mw
    return max(0.0, x_i) * 1.0e6


def _soot_proxy(phi_primary: float, pressure_Pa: float) -> float:
    """Qualitative soot index in [0, 1].

    GRI-Mech 3.0 has no soot chemistry, so this is a correlation, not a species
    result: soot rises sharply once the primary zone goes rich and grows with
    pressure. Lean primary zones (phi < ~0.9) are essentially smoke-free.
    """

    richness = max(0.0, phi_primary - 0.9)
    p_atm = pressure_Pa / 101325.0
    return float(min(1.0, 2.5 * richness * (p_atm / 30.0) ** 0.5))


def _correlation_fallback(
    T3_K: float,
    P_Pa: float,
    phi_overall: float,
    fuel: str,
    phi_primary: float,
) -> EmissionResult:
    """P3–T3 NOx correlation used when Cantera is unavailable.

    Exponential temperature dependence (thermal NOx is Arrhenius-like) and a
    square-root pressure dependence, anchored to ~27 g/kg at takeoff-class
    conditions (T3 = 820 K, P3 = 30 atm). CO is given a rough part-power rise.
    """

    p_atm = P_Pa / 101325.0
    ei_nox = 27.0 * (p_atm / 30.0) ** 0.5 * math.exp((T3_K - 820.0) / 90.0)
    ei_co = 8.0 + 60.0 * math.exp(-(T3_K - 450.0) / 110.0)   # high at idle, low at power
    return EmissionResult(
        ei_nox_g_per_kg=max(0.0, ei_nox),
        ei_co_g_per_kg=max(0.0, ei_co),
        ei_hc_g_per_kg=max(0.0, 0.15 * ei_co),
        ei_co2_g_per_kg=3150.0,                  # ~complete hydrocarbon combustion
        ei_h2o_g_per_kg=1240.0,
        soot_proxy=_soot_proxy(phi_primary, P_Pa),
        primary_zone_temperature_K=float("nan"),
        phi_primary=phi_primary,
        phi_overall=phi_overall,
        fuel=fuel,
        source="correlation",
        axial_profile=[],
        notes=["Cantera not available; EINOx from the P3–T3 correlation fallback."],
    )


# ---------------------------------------------------------------------------
# ICAO landing–takeoff (LTO) NOx aggregation
# ---------------------------------------------------------------------------

# Standard ICAO LTO reference cycle: thrust setting and time-in-mode (seconds).
ICAO_LTO_MODES: Final[tuple[tuple[str, float, float], ...]] = (
    ("Take-off", 1.00, 0.7 * 60.0),
    ("Climb-out", 0.85, 2.2 * 60.0),
    ("Approach", 0.30, 4.0 * 60.0),
    ("Idle", 0.07, 26.0 * 60.0),
)


@dataclass(frozen=True)
class LTOModePoint:
    """One LTO mode: model EINOx and fuel flow at that thrust setting."""

    name: str
    thrust_fraction: float
    time_in_mode_s: float
    ei_nox_g_per_kg: float
    fuel_flow_kg_s: float


@dataclass(frozen=True)
class LTOResult:
    """Aggregated ICAO LTO NOx result."""

    dp_nox_g: float                       # total NOx mass over the cycle (g)
    fuel_burn_kg: float                   # total fuel over the cycle (kg)
    dp_foo_g_per_kN: float | None         # certification metric Dp(NOx)/Foo
    rated_thrust_kN: float | None
    per_mode: list[dict[str, float]] = field(default_factory=list)


def icao_lto_nox(
    modes: list[LTOModePoint],
    rated_thrust_kN: float | None = None,
) -> LTOResult:
    """Aggregate per-mode EINOx and fuel flow into the ICAO LTO NOx total.

    ``Dp(NOx) = Σ EINOx_mode · Wf_mode · t_mode`` and the certification metric
    ``Dp/Foo`` divides that by the engine's rated sea-level thrust. Pass
    ``rated_thrust_kN`` to get ``dp_foo_g_per_kN`` (None otherwise).
    """

    dp_nox_g = 0.0
    fuel_burn_kg = 0.0
    per_mode: list[dict[str, float]] = []
    for m in modes:
        mode_nox_g = m.ei_nox_g_per_kg * m.fuel_flow_kg_s * m.time_in_mode_s
        mode_fuel_kg = m.fuel_flow_kg_s * m.time_in_mode_s
        dp_nox_g += mode_nox_g
        fuel_burn_kg += mode_fuel_kg
        per_mode.append({
            "name": m.name,
            "thrust_fraction": m.thrust_fraction,
            "ei_nox_g_per_kg": m.ei_nox_g_per_kg,
            "fuel_flow_kg_s": m.fuel_flow_kg_s,
            "time_in_mode_s": m.time_in_mode_s,
            "nox_g": mode_nox_g,
            "fuel_kg": mode_fuel_kg,
        })

    dp_foo = (dp_nox_g / rated_thrust_kN) if rated_thrust_kN else None
    return LTOResult(
        dp_nox_g=dp_nox_g,
        fuel_burn_kg=fuel_burn_kg,
        dp_foo_g_per_kN=dp_foo,
        rated_thrust_kN=rated_thrust_kN,
        per_mode=per_mode,
    )
