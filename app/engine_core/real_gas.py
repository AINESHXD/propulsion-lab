"""Real-gas hot-section properties (Day 18).

The educational cycle uses a single constant ``cp_gas`` for all combustion-gas
stations. In reality the specific heat of burned gas rises strongly with
temperature (≈ 1150 J/kg·K cold, ≈ 1300+ J/kg·K at turbine-inlet temperatures),
so a constant-cp turbine drop is noticeably off in the hot section.

This module looks up the *temperature-dependent* specific heat and enthalpy of
the equilibrium burned gas (via Cantera, through :mod:`gas_service`) and offers
two ways to compute a turbine temperature drop for a required specific work:

* :func:`turbine_exit_temperature_mean_cp` — practical "cp(T,P) lookup" method:
  evaluate cp at the mean of inlet and exit temperature and iterate
  ``dT = work / cp_mean``. One property lookup per iteration, converges in a
  few steps.
* :func:`turbine_exit_temperature_enthalpy_balance` — the reference: invert the
  real-gas enthalpy function directly so that ``h(Tt_in) − h(Tt_exit) = work``
  exactly (Newton on temperature).

Day 18 pins the HPT inlet: the mean-cp drop must match the enthalpy balance to
within 0.1 %. When Cantera is unavailable both methods fall back to the constant
``cp_gas`` model and agree identically.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.engine_core.constants import cp_air, cp_gas, gamma_air
from app.engine_core.gas_service import (
    air_isentropic_exit_temperature,
    air_properties,
    equilibrium_products,
    freeze_combustion_products,
    frozen_gas_properties,
    is_cantera_available,
    isentropic_exit_temperature,
)


@dataclass(slots=True, frozen=True)
class TurbineDropResult:
    """Outcome of a real-gas turbine temperature-drop calculation."""

    exit_temperature_K: float
    cp_mean_J_per_kg_K: float
    enthalpy_drop_J_per_kg: float
    iterations: int
    source: str                      # "cantera" or "constant-cp"


def freeze_hot_section(inlet_temperature_K: float, pressure_Pa: float,
                       fuel_air_ratio: float, fuel: str = "CH4"):
    """Frozen burned-gas composition for the hot section (turbine + nozzle).

    Equilibrate once at the combustor-exit state, then hold the composition
    fixed for all downstream property lookups (frozen-flow expansion).
    """

    return freeze_combustion_products(inlet_temperature_K, pressure_Pa, fuel_air_ratio, fuel)


def hot_gas_cp(composition, temperature_K: float, pressure_Pa: float) -> float:
    """Frozen-composition specific heat cp(T) [J/kg·K]."""

    return frozen_gas_properties(composition, temperature_K, pressure_Pa).cp_J_per_kg_K


def hot_gas_enthalpy(composition, temperature_K: float, pressure_Pa: float) -> float:
    """Frozen-composition mass-specific enthalpy h(T) [J/kg]."""

    return frozen_gas_properties(composition, temperature_K, pressure_Pa).h_J_per_kg


def turbine_exit_temperature_mean_cp(
    inlet_temperature_K: float,
    pressure_Pa: float,
    specific_work_J_per_kg: float,
    fuel_air_ratio: float,
    fuel: str = "CH4",
    composition=None,
    max_iterations: int = 12,
    tolerance_K: float = 1e-6,
) -> TurbineDropResult:
    """Turbine exit Tt from a mean-cp lookup of the frozen burned gas.

    cp is evaluated at the mean of the inlet and current exit temperature and
    the drop refined as ``dT = work / cp_mean``. With a frozen composition
    ``cp`` is exactly ``dh/dT``, so this midpoint-rule estimate matches the full
    enthalpy integral to well under 0.1 % over a turbine drop.
    """

    if specific_work_J_per_kg <= 0.0:
        raise ValueError("Specific work must be positive.")
    if inlet_temperature_K <= 0.0 or pressure_Pa <= 0.0:
        raise ValueError("Temperature and pressure must be positive.")

    if composition is None:
        composition = freeze_hot_section(inlet_temperature_K, pressure_Pa, fuel_air_ratio, fuel)

    cp_in = hot_gas_cp(composition, inlet_temperature_K, pressure_Pa)
    exit_temperature_K = inlet_temperature_K - specific_work_J_per_kg / cp_in
    cp_mean = cp_in
    iterations = 0
    for iterations in range(1, max_iterations + 1):
        mean_T = 0.5 * (inlet_temperature_K + exit_temperature_K)
        cp_mean = hot_gas_cp(composition, mean_T, pressure_Pa)
        new_exit = inlet_temperature_K - specific_work_J_per_kg / cp_mean
        if abs(new_exit - exit_temperature_K) < tolerance_K:
            exit_temperature_K = new_exit
            break
        exit_temperature_K = new_exit

    if exit_temperature_K <= 0.0:
        raise ValueError("Turbine work extraction produced non-positive exit T.")

    return TurbineDropResult(
        exit_temperature_K=exit_temperature_K,
        cp_mean_J_per_kg_K=cp_mean,
        enthalpy_drop_J_per_kg=cp_mean * (inlet_temperature_K - exit_temperature_K),
        iterations=iterations,
        source="cantera" if is_cantera_available() else "constant-cp",
    )


def turbine_exit_temperature_enthalpy_balance(
    inlet_temperature_K: float,
    pressure_Pa: float,
    specific_work_J_per_kg: float,
    fuel_air_ratio: float,
    fuel: str = "CH4",
    composition=None,
    max_iterations: int = 60,
    tolerance_J_per_kg: float = 1.0,
) -> float:
    """Exact frozen-gas exit Tt: invert ``h(Tt_in) − h(Tt_exit) = work``.

    Newton on temperature with the local cp as the derivative (``dh/dT = cp``).
    This is the enthalpy-balance reference the mean-cp method is checked against;
    it uses the *same* frozen composition so the two are directly comparable.
    """

    if specific_work_J_per_kg <= 0.0:
        raise ValueError("Specific work must be positive.")

    if composition is None:
        composition = freeze_hot_section(inlet_temperature_K, pressure_Pa, fuel_air_ratio, fuel)

    h_in = hot_gas_enthalpy(composition, inlet_temperature_K, pressure_Pa)
    cp_in = hot_gas_cp(composition, inlet_temperature_K, pressure_Pa)
    temperature_K = inlet_temperature_K - specific_work_J_per_kg / cp_in
    for _ in range(max_iterations):
        state = frozen_gas_properties(composition, temperature_K, pressure_Pa)
        residual = (h_in - state.h_J_per_kg) - specific_work_J_per_kg
        if abs(residual) < tolerance_J_per_kg:
            break
        # residual'(T) = -cp(T)  ->  Newton step  T += residual / cp
        temperature_K += residual / state.cp_J_per_kg_K
    if temperature_K <= 0.0:
        raise ValueError("Enthalpy balance produced non-positive exit T.")
    return temperature_K


def constant_cp_exit_temperature(
    inlet_temperature_K: float,
    specific_work_J_per_kg: float,
) -> float:
    """Constant-cp baseline exit Tt (the original educational model)."""

    return inlet_temperature_K - specific_work_J_per_kg / cp_gas


# ---------------------------------------------------------------------------
# Cold-section walk: variable-cp compressor (real-gas whole-cycle, cold side)
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class CompressorRealGasResult:
    """Variable-cp compressor exit state for a required pressure ratio."""

    exit_temperature_K: float
    cp_mean_J_per_kg_K: float
    specific_work_J_per_kg: float
    source: str                      # "cantera" or "constant-cp"


def _air_T_for_enthalpy(h_target: float, pressure_Pa: float, guess_T: float,
                        max_it: int = 60, tol: float = 1.0) -> float:
    """Solve air h(T) = h_target for T (Newton with cp as the derivative)."""

    T = guess_T
    for _ in range(max_it):
        st = air_properties(T, pressure_Pa)
        residual = st.h_J_per_kg - h_target
        if abs(residual) < tol:
            break
        T -= residual / st.cp_J_per_kg_K
    if T <= 0.0:
        raise ValueError("Air enthalpy inversion produced non-positive T.")
    return T


def compressor_exit_temperature_real_gas(
    inlet_temperature_K: float,
    inlet_pressure_Pa: float,
    pressure_ratio: float,
    compressor_efficiency: float,
) -> CompressorRealGasResult:
    """Compressor exit stagnation T with temperature-dependent air properties.

    The cold-side counterpart of :func:`hot_section_temperatures`. For the given
    total-pressure ratio and isentropic efficiency, the ideal (isentropic)
    enthalpy rise is found from a real-gas entropy hold, divided by the
    efficiency for the actual enthalpy rise, and the exit temperature is the
    air temperature carrying that enthalpy. cp of air climbs from ~1004 J/kg·K
    cold toward ~1080+ J/kg·K at compressor-exit temperatures, so the variable-cp
    exit is a little cooler than the constant-cp deck for the same pressure ratio.
    Falls back to the constant-cp model when Cantera is unavailable.
    """

    if pressure_ratio <= 1.0:
        raise ValueError("Compressor pressure ratio must exceed 1.")
    if not 0.0 < compressor_efficiency <= 1.0:
        raise ValueError("Compressor efficiency must be in (0, 1].")
    if inlet_temperature_K <= 0.0 or inlet_pressure_Pa <= 0.0:
        raise ValueError("Inlet temperature and pressure must be positive.")

    if not is_cantera_available():
        ratio = pressure_ratio ** ((gamma_air - 1.0) / gamma_air)
        exit_T = inlet_temperature_K + (
            inlet_temperature_K * ratio - inlet_temperature_K
        ) / compressor_efficiency
        work = cp_air * (exit_T - inlet_temperature_K)
        return CompressorRealGasResult(
            exit_temperature_K=exit_T,
            cp_mean_J_per_kg_K=cp_air,
            specific_work_J_per_kg=work,
            source="constant-cp",
        )

    exit_pressure_Pa = inlet_pressure_Pa * pressure_ratio
    inlet = air_properties(inlet_temperature_K, inlet_pressure_Pa)
    isentropic_T = air_isentropic_exit_temperature(
        inlet_temperature_K, inlet_pressure_Pa, exit_pressure_Pa
    )
    h_isentropic = air_properties(isentropic_T, exit_pressure_Pa).h_J_per_kg
    ideal_rise = h_isentropic - inlet.h_J_per_kg
    actual_rise = ideal_rise / compressor_efficiency
    h_exit = inlet.h_J_per_kg + actual_rise
    exit_T = _air_T_for_enthalpy(
        h_exit, exit_pressure_Pa, guess_T=inlet_temperature_K + actual_rise / inlet.cp_J_per_kg_K
    )
    cp_mean = actual_rise / (exit_T - inlet_temperature_K)
    return CompressorRealGasResult(
        exit_temperature_K=exit_T,
        cp_mean_J_per_kg_K=cp_mean,
        specific_work_J_per_kg=actual_rise,
        source="cantera",
    )


# ---------------------------------------------------------------------------
# Whole hot-section walk: HPT -> LPT -> nozzle (Day 19)
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class HotSectionResult:
    """Real-gas hot-section station temperatures for one operating point."""

    hpt_exit_temperature_K: float
    lpt_exit_temperature_K: float
    nozzle_exit_static_temperature_K: float
    nozzle_exit_velocity_m_s: float
    mode: str                        # "frozen" or "equilibrium"
    source: str                      # "cantera" or "constant-cp"


def _props(mode, composition, far, fuel, temperature_K, pressure_Pa):
    """Gas state by mode: frozen (fixed composition) or re-equilibrated."""

    if mode == "equilibrium":
        return equilibrium_products(temperature_K, pressure_Pa, far, fuel)
    return frozen_gas_properties(composition, temperature_K, pressure_Pa)


def _exit_T_for_work(props_at, h_in, cp_in, inlet_T, work, max_it=60, tol=1.0):
    """Solve h_in - h(T) = work for T (Newton); props_at(T) -> GasState."""

    T = inlet_T - work / cp_in
    for _ in range(max_it):
        st = props_at(T)
        residual = (h_in - st.h_J_per_kg) - work
        if abs(residual) < tol:
            break
        T += residual / st.cp_J_per_kg_K
    return T


def _exit_T_for_enthalpy(props_at, h_target, cp_guess, guess_T, max_it=60, tol=1.0):
    """Solve h(T) = h_target for T (Newton); props_at(T) -> GasState."""

    T = guess_T
    for _ in range(max_it):
        st = props_at(T)
        residual = st.h_J_per_kg - h_target
        if abs(residual) < tol:
            break
        T -= residual / st.cp_J_per_kg_K
    return T


def hot_section_temperatures(
    turbine_inlet_temperature_K: float,
    turbine_inlet_pressure_Pa: float,
    hpt_exit_pressure_Pa: float,
    lpt_exit_pressure_Pa: float,
    nozzle_exit_pressure_Pa: float,
    hpt_specific_work_J_per_kg: float,
    lpt_specific_work_J_per_kg: float,
    fuel_air_ratio: float,
    nozzle_efficiency: float,
    fuel: str = "CH4",
    mode: str = "frozen",
) -> HotSectionResult:
    """Walk the hot section HPT -> LPT -> nozzle with real-gas properties.

    Turbine drops come from a real-gas enthalpy balance for the given specific
    work (per unit gas). The nozzle expansion is real-gas isentropic to the exit
    pressure, then derated by ``nozzle_efficiency``. Set ``lpt_specific_work`` to
    zero for a single-turbine engine (the turbojet).
    """

    composition = None
    if mode != "equilibrium":
        composition = freeze_combustion_products(
            turbine_inlet_temperature_K, turbine_inlet_pressure_Pa, fuel_air_ratio, fuel
        )

    # HPT drop.
    inlet = _props(mode, composition, fuel_air_ratio, fuel,
                   turbine_inlet_temperature_K, turbine_inlet_pressure_Pa)
    hpt_exit_T = _exit_T_for_work(
        lambda T: _props(mode, composition, fuel_air_ratio, fuel, T, hpt_exit_pressure_Pa),
        inlet.h_J_per_kg, inlet.cp_J_per_kg_K,
        turbine_inlet_temperature_K, hpt_specific_work_J_per_kg,
    )

    # LPT drop (zero work -> no drop).
    if lpt_specific_work_J_per_kg > 0.0:
        h45 = _props(mode, composition, fuel_air_ratio, fuel, hpt_exit_T, hpt_exit_pressure_Pa)
        lpt_exit_T = _exit_T_for_work(
            lambda T: _props(mode, composition, fuel_air_ratio, fuel, T, lpt_exit_pressure_Pa),
            h45.h_J_per_kg, h45.cp_J_per_kg_K, hpt_exit_T, lpt_specific_work_J_per_kg,
        )
    else:
        lpt_exit_T = hpt_exit_T

    # Nozzle: real-gas isentropic to exit pressure, then nozzle efficiency.
    nozzle_inlet_T = lpt_exit_T
    h5 = _props(mode, composition, fuel_air_ratio, fuel, nozzle_inlet_T, lpt_exit_pressure_Pa)
    T_exit_s = isentropic_exit_temperature(
        nozzle_inlet_T, lpt_exit_pressure_Pa, nozzle_exit_pressure_Pa,
        fuel_air_ratio, fuel, mass_fractions=composition, equilibrium=(mode == "equilibrium"),
    )
    h_exit_s = _props(mode, composition, fuel_air_ratio, fuel, T_exit_s, nozzle_exit_pressure_Pa)
    ideal_drop = h5.h_J_per_kg - h_exit_s.h_J_per_kg
    actual_drop = max(nozzle_efficiency * ideal_drop, 0.0)
    h_exit = h5.h_J_per_kg - actual_drop
    exit_T = _exit_T_for_enthalpy(
        lambda T: _props(mode, composition, fuel_air_ratio, fuel, T, nozzle_exit_pressure_Pa),
        h_exit, h5.cp_J_per_kg_K, T_exit_s,
    )
    exit_velocity = (2.0 * actual_drop) ** 0.5

    return HotSectionResult(
        hpt_exit_temperature_K=hpt_exit_T,
        lpt_exit_temperature_K=lpt_exit_T,
        nozzle_exit_static_temperature_K=exit_T,
        nozzle_exit_velocity_m_s=exit_velocity,
        mode=mode,
        source="cantera" if is_cantera_available() else "constant-cp",
    )
