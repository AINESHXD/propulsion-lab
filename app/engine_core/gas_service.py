"""Real-gas property + equilibrium combustion service.

Thin wrapper around Cantera. Stable interface so the rest of `engine_core`
stays agnostic about whether thermodynamic properties come from constant
perfect-gas constants or a real equilibrium solver.

Cantera is an optional dependency. If it is not installed the public
functions return a constant-cp/gamma fallback that matches the original
educational model. This preserves the contract documented in the README
and keeps all existing tests passing on a vanilla install.

References
----------
- Cantera 3.x  https://cantera.org/
- GRI-Mech 3.0 mechanism is bundled with Cantera and is sufficient for
  hydrocarbon-fuel equilibrium combustion at the temperatures of interest
  for an educational turbojet (<= 2300 K).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from app.engine_core.constants import (
    R_air,
    cp_air,
    cp_gas,
    gamma_air,
    gamma_gas,
)

try:                              # pragma: no cover - import-time branch
    import cantera as ct          # type: ignore[import-not-found]
    _CANTERA_AVAILABLE: Final[bool] = True
except ImportError:               # pragma: no cover - exercised on CI w/o cantera
    ct = None                     # type: ignore[assignment]
    _CANTERA_AVAILABLE = False


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class GasState:
    """Local gas state returned by the service.

    All values are mass-specific and SI. ``cp`` and ``cv`` come from the
    underlying property model; ``gamma = cp/cv`` so the perfect-gas relations
    used elsewhere in `engine_core` continue to apply with the *local* gas
    properties instead of the global constants.
    """

    cp_J_per_kg_K: float
    gamma: float
    h_J_per_kg: float
    R_J_per_kg_K: float
    temperature_K: float
    pressure_Pa: float
    source: str                      # "cantera" or "constant-cp"


def is_cantera_available() -> bool:
    """Return ``True`` if Cantera is importable in this environment."""

    return _CANTERA_AVAILABLE


# ---------------------------------------------------------------------------
# Cached Cantera Solution
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _solution():
    """Lazily build and cache one shared ``cantera.Solution`` object.

    Cantera Solution construction is non-trivial (~10s of ms) so the same
    object is reused across calls. The state is *not* shared between calls;
    each call sets `TPY` / `TPX` before reading properties, so there is no
    cross-talk between successive evaluations.
    """

    if not _CANTERA_AVAILABLE:
        return None
    # GRI-Mech 3.0 ships with Cantera. It covers C1-C3 combustion chemistry
    # which is more than enough for a kerosene surrogate at preliminary
    # design temperatures.
    return ct.Solution("gri30.yaml")


# ---------------------------------------------------------------------------
# Air properties (upstream of combustion: stations 0 / 2 / 3)
# ---------------------------------------------------------------------------


def air_properties(temperature_K: float, pressure_Pa: float) -> GasState:
    """Return real-air properties at the requested stagnation state.

    Uses dry-air composition O2/N2 = 0.21/0.79 by mole when Cantera is
    available. Falls back to the educational constants otherwise.
    """

    if temperature_K <= 0.0 or pressure_Pa <= 0.0:
        raise ValueError("Temperature and pressure must be positive.")

    if not _CANTERA_AVAILABLE:
        return GasState(
            cp_J_per_kg_K=cp_air,
            gamma=gamma_air,
            h_J_per_kg=cp_air * temperature_K,
            R_J_per_kg_K=R_air,
            temperature_K=temperature_K,
            pressure_Pa=pressure_Pa,
            source="constant-cp",
        )

    gas = _solution()
    gas.TPX = temperature_K, pressure_Pa, "O2:0.21, N2:0.79"
    cp = float(gas.cp_mass)
    cv = float(gas.cv_mass)
    return GasState(
        cp_J_per_kg_K=cp,
        gamma=cp / cv,
        h_J_per_kg=float(gas.enthalpy_mass),
        R_J_per_kg_K=cp - cv,
        temperature_K=temperature_K,
        pressure_Pa=pressure_Pa,
        source="cantera",
    )


# ---------------------------------------------------------------------------
# Equilibrium combustion products (downstream of combustion: stations 4 / 5 / 9)
# ---------------------------------------------------------------------------


def equilibrium_products(
    temperature_K: float,
    pressure_Pa: float,
    fuel_air_ratio: float,
    fuel: str = "CH4",
) -> GasState:
    """Equilibrium burned-gas properties at the requested state.

    Parameters
    ----------
    temperature_K, pressure_Pa
        The state at which to evaluate properties (typically the combustor
        exit stagnation state).
    fuel_air_ratio
        Mass fuel-air ratio of the original reactant mixture.
    fuel
        Cantera species name for the fuel. ``"CH4"`` is the default for
        a methane-air surrogate. ``"C2H6"`` and other GRI-Mech species
        also work. Note that GRI-Mech does not include Jet-A; methane is
        used as an educational kerosene surrogate.

    Returns
    -------
    GasState describing the burned mixture (cp, gamma, h, R) at (T, P).
    Falls back to the constant ``cp_gas`` / ``gamma_gas`` values if Cantera
    is not installed.
    """

    if fuel_air_ratio <= 0.0:
        raise ValueError("Fuel-air ratio must be positive.")

    if not _CANTERA_AVAILABLE:
        return GasState(
            cp_J_per_kg_K=cp_gas,
            gamma=gamma_gas,
            h_J_per_kg=cp_gas * temperature_K,
            R_J_per_kg_K=cp_gas - cp_gas / gamma_gas,
            temperature_K=temperature_K,
            pressure_Pa=pressure_Pa,
            source="constant-cp",
        )

    # Build reactant mass-fraction string. Air is 0.232 O2 / 0.768 N2 by mass.
    air_mass = 1.0
    fuel_mass = fuel_air_ratio * air_mass
    total = air_mass + fuel_mass
    y_air = air_mass / total
    y_fuel = fuel_mass / total
    composition = {
        fuel: y_fuel,
        "O2": 0.232 * y_air,
        "N2": 0.768 * y_air,
    }

    gas = _solution()
    gas.TPY = temperature_K, pressure_Pa, composition
    gas.equilibrate("TP")           # at the requested T and P
    cp = float(gas.cp_mass)
    cv = float(gas.cv_mass)
    return GasState(
        cp_J_per_kg_K=cp,
        gamma=cp / cv,
        h_J_per_kg=float(gas.enthalpy_mass),
        R_J_per_kg_K=cp - cv,
        temperature_K=temperature_K,
        pressure_Pa=pressure_Pa,
        source="cantera",
    )


def freeze_combustion_products(
    temperature_K: float,
    pressure_Pa: float,
    fuel_air_ratio: float,
    fuel: str = "CH4",
):
    """Equilibrate burned gas at (T, P) and return its *frozen* composition.

    Returns the mass-fraction vector of the equilibrium burned gas, to be held
    fixed for subsequent hot-section property lookups (the frozen-flow turbine /
    nozzle assumption — reactions do not have time to shift composition during
    the expansion). Returns ``None`` when Cantera is unavailable so callers can
    fall back to the constant-cp model.
    """

    if fuel_air_ratio <= 0.0:
        raise ValueError("Fuel-air ratio must be positive.")
    if not _CANTERA_AVAILABLE:
        return None

    air_mass = 1.0
    fuel_mass = fuel_air_ratio * air_mass
    total = air_mass + fuel_mass
    y_air = air_mass / total
    y_fuel = fuel_mass / total
    composition = {
        fuel: y_fuel,
        "O2": 0.232 * y_air,
        "N2": 0.768 * y_air,
    }
    gas = _solution()
    gas.TPY = temperature_K, pressure_Pa, composition
    gas.equilibrate("TP")
    return gas.Y.copy()


def frozen_gas_properties(
    mass_fractions,
    temperature_K: float,
    pressure_Pa: float,
) -> GasState:
    """Properties of a *fixed-composition* burned gas at (T, P).

    No re-equilibration: the mixture composition is held frozen, so
    ``cp_mass`` is exactly ``dh/dT`` along the path and the enthalpy integral is
    self-consistent. ``mass_fractions`` is a vector from
    :func:`freeze_combustion_products`; ``None`` selects the constant-cp model.
    """

    if temperature_K <= 0.0 or pressure_Pa <= 0.0:
        raise ValueError("Temperature and pressure must be positive.")
    if mass_fractions is None or not _CANTERA_AVAILABLE:
        return GasState(
            cp_J_per_kg_K=cp_gas,
            gamma=gamma_gas,
            h_J_per_kg=cp_gas * temperature_K,
            R_J_per_kg_K=cp_gas - cp_gas / gamma_gas,
            temperature_K=temperature_K,
            pressure_Pa=pressure_Pa,
            source="constant-cp",
        )

    gas = _solution()
    gas.TPY = temperature_K, pressure_Pa, mass_fractions
    cp = float(gas.cp_mass)
    cv = float(gas.cv_mass)
    return GasState(
        cp_J_per_kg_K=cp,
        gamma=cp / cv,
        h_J_per_kg=float(gas.enthalpy_mass),
        R_J_per_kg_K=cp - cv,
        temperature_K=temperature_K,
        pressure_Pa=pressure_Pa,
        source="cantera",
    )


def _reactant_composition(fuel_air_ratio: float, fuel: str) -> dict[str, float]:
    """Mass-fraction reactant mix (fuel + air) for a given fuel-air ratio."""

    air_mass = 1.0
    fuel_mass = fuel_air_ratio * air_mass
    total = air_mass + fuel_mass
    y_air = air_mass / total
    y_fuel = fuel_mass / total
    return {fuel: y_fuel, "O2": 0.232 * y_air, "N2": 0.768 * y_air}


def isentropic_exit_temperature(
    inlet_temperature_K: float,
    inlet_pressure_Pa: float,
    exit_pressure_Pa: float,
    fuel_air_ratio: float,
    fuel: str = "CH4",
    mass_fractions=None,
    equilibrium: bool = False,
) -> float:
    """Isentropic exit static temperature for an expansion to ``exit_pressure_Pa``.

    Real-gas (variable cp/gamma) via Cantera: hold entropy constant from the
    inlet state down to the exit pressure. With ``equilibrium=False`` (default)
    the composition is frozen (``mass_fractions`` from
    :func:`freeze_combustion_products`); with ``equilibrium=True`` the mixture is
    re-equilibrated along the expansion. Falls back to the constant-gamma
    isentropic relation when Cantera is unavailable.
    """

    if exit_pressure_Pa <= 0.0 or inlet_pressure_Pa <= 0.0:
        raise ValueError("Pressures must be positive.")
    if not _CANTERA_AVAILABLE:
        return inlet_temperature_K * (
            exit_pressure_Pa / inlet_pressure_Pa
        ) ** ((gamma_gas - 1.0) / gamma_gas)

    gas = _solution()
    if equilibrium:
        gas.TPY = inlet_temperature_K, inlet_pressure_Pa, _reactant_composition(
            fuel_air_ratio, fuel
        )
        gas.equilibrate("TP")
        entropy = float(gas.entropy_mass)
        gas.SP = entropy, exit_pressure_Pa
        gas.equilibrate("SP")
        return float(gas.T)

    composition = mass_fractions
    if composition is None:
        composition = freeze_combustion_products(
            inlet_temperature_K, inlet_pressure_Pa, fuel_air_ratio, fuel
        )
    gas.TPY = inlet_temperature_K, inlet_pressure_Pa, composition
    entropy = float(gas.entropy_mass)
    gas.SPY = entropy, exit_pressure_Pa, composition
    return float(gas.T)


def air_isentropic_exit_temperature(
    inlet_temperature_K: float,
    inlet_pressure_Pa: float,
    exit_pressure_Pa: float,
) -> float:
    """Isentropic exit temperature for dry air taken from inlet to exit pressure.

    Real-gas (variable cp/gamma) via Cantera: hold entropy constant from the
    inlet air state to the exit pressure, composition frozen (air does not react
    in the cold section). This is the cold-side counterpart of
    :func:`isentropic_exit_temperature`, used for the variable-cp compressor
    walk. Falls back to the constant-gamma isentropic relation when Cantera is
    unavailable, so it reduces exactly to the educational model.
    """

    if exit_pressure_Pa <= 0.0 or inlet_pressure_Pa <= 0.0:
        raise ValueError("Pressures must be positive.")
    if inlet_temperature_K <= 0.0:
        raise ValueError("Temperature must be positive.")

    if not _CANTERA_AVAILABLE:
        return inlet_temperature_K * (
            exit_pressure_Pa / inlet_pressure_Pa
        ) ** ((gamma_air - 1.0) / gamma_air)

    gas = _solution()
    gas.TPX = inlet_temperature_K, inlet_pressure_Pa, "O2:0.21, N2:0.79"
    entropy = float(gas.entropy_mass)
    # Composition is held (no equilibration): SP keeps the frozen air mixture.
    gas.SP = entropy, exit_pressure_Pa
    return float(gas.T)


def adiabatic_flame_temperature(
    inlet_temperature_K: float,
    pressure_Pa: float,
    fuel_air_ratio: float,
    fuel: str = "CH4",
) -> float:
    """Return the adiabatic, constant-pressure equilibrium flame temperature.

    Falls back to the constant-cp energy balance if Cantera is not installed.
    The fallback uses the same form as the educational model and is intended
    purely so callers can rely on a number without branching themselves.
    """

    if not _CANTERA_AVAILABLE:
        from app.engine_core.constants import fuel_heating_value_default
        # crude perfect-gas estimate: enthalpy gain = fuel_air_ratio * LHV
        return inlet_temperature_K + (
            fuel_air_ratio * fuel_heating_value_default
        ) / ((1.0 + fuel_air_ratio) * cp_gas)

    air_mass = 1.0
    fuel_mass = fuel_air_ratio * air_mass
    total = air_mass + fuel_mass
    y_air = air_mass / total
    y_fuel = fuel_mass / total
    composition = {
        fuel: y_fuel,
        "O2": 0.232 * y_air,
        "N2": 0.768 * y_air,
    }

    gas = _solution()
    gas.TPY = inlet_temperature_K, pressure_Pa, composition
    gas.equilibrate("HP")           # adiabatic, constant pressure
    return float(gas.T)
