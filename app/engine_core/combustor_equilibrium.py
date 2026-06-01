"""Cantera-backed equilibrium combustor.

Drop-in replacement for :func:`app.engine_core.combustor.calculate_combustor_exit`
that uses an equilibrium-product enthalpy balance instead of the constant-cp
educational model.

The existing :mod:`app.engine_core.combustor` module is untouched. This module
is invoked only when ``TurbojetInput.use_equilibrium_combustion`` is True.

Energy model
------------
For each trial fuel-air ratio ``f`` we ask Cantera to compute the adiabatic,
constant-pressure equilibrium flame temperature ``T_ad(f)``. Combustor
efficiency ``eta_b`` is then applied as a textbook linear derate

::

    T_actual = T3 + eta_b * (T_ad(f) - T3)

and ``f`` is root-found by Brent's method so that ``T_actual`` matches the
requested turbine inlet temperature ``T04``. This collapses to the perfect-gas
result for low ``f`` and moderate ``T04`` while capturing real-gas / dissociation
effects at the high-temperature end of the envelope.

Pressure loss is identical to the educational combustor:
``P04 = P03 * (1 - pressure_loss_fraction)``.

This module raises :class:`CycleCalculationError` with an actionable message
if Cantera is not installed and the equilibrium path is requested.
"""

from __future__ import annotations

from scipy.optimize import brentq  # type: ignore[import-not-found]

from app.engine_core.gas_service import (
    adiabatic_flame_temperature,
    equilibrium_products,
    is_cantera_available,
)
from app.engine_core.types import ComponentResult, CycleCalculationError, StationState


# Search bracket for the fuel-air-ratio root finder. The lower bound is well
# below blow-out and the upper bound sits a little above stoichiometric for
# methane (~0.058). Real lean turbojet combustors operate at 0.01-0.04.
_FUEL_AIR_RATIO_MIN = 1.0e-4
_FUEL_AIR_RATIO_MAX = 0.075


def calculate_combustor_exit_equilibrium(
    compressor_exit_state: StationState,
    turbine_inlet_temperature_K: float,
    combustor_efficiency: float,
    pressure_loss_fraction: float,
    fuel_heating_value_J_kg: float,
    *,
    fuel: str = "CH4",
) -> ComponentResult:
    """Equilibrium-products combustor with the same return contract as v1.

    Parameters
    ----------
    compressor_exit_state
        Station 3 stagnation state.
    turbine_inlet_temperature_K
        Requested T04. The solver derives the fuel-air ratio that lands here
        after the combustor efficiency derate is applied to the equilibrium
        adiabatic flame temperature.
    combustor_efficiency
        Fraction of the equilibrium temperature rise that actually appears at
        the combustor exit. ``0 < eta_b <= 1``.
    pressure_loss_fraction
        ``ΔP / P`` across the combustor. ``0 <= ΔP/P <= 0.3``.
    fuel_heating_value_J_kg
        Carried for warnings only — the equilibrium model uses the species
        enthalpies of formation that Cantera already knows about.
    fuel
        Cantera species name. Defaults to methane as an educational
        hydrocarbon surrogate. Pass ``"C2H6"``, ``"H2"``, etc. for variants.

    Returns
    -------
    ComponentResult with the same shape as the perfect-gas combustor:

    - ``state`` is the station-4 StationState
    - ``metadata["fuel_air_ratio"]`` is the root-found mass FAR
    - ``metadata["adiabatic_flame_temperature_K"]`` (extra) is the ideal Tad
    - ``metadata["combustor_model"] = "equilibrium"``
    - ``metadata["product_cp_J_per_kg_K"]`` and ``["product_gamma"]`` carry
      the local combustor-exit gas properties for downstream consumers.
    """

    if not is_cantera_available():
        raise CycleCalculationError(
            "Equilibrium combustor requested but Cantera is not installed. "
            "Run `pip install cantera` to enable this model, or disable "
            "`use_equilibrium_combustion` to fall back to the perfect-gas model."
        )

    # Mirror the perfect-gas combustor's input validation so the failure modes
    # are identical from a caller's perspective.
    if not 0.0 < combustor_efficiency <= 1.0:
        raise CycleCalculationError("Combustor efficiency must be between 0 and 1.")
    if not 0.0 <= pressure_loss_fraction <= 0.3:
        raise CycleCalculationError("Combustor pressure loss fraction must be 0 to 0.3.")
    if fuel_heating_value_J_kg <= 1e6:
        raise CycleCalculationError("Fuel heating value must exceed 1e6 J/kg.")
    if turbine_inlet_temperature_K <= compressor_exit_state.stagnation_temperature_K:
        raise CycleCalculationError(
            "Turbine inlet temperature must exceed compressor exit temperature."
        )

    T3_K = compressor_exit_state.stagnation_temperature_K
    P3_Pa = compressor_exit_state.stagnation_pressure_Pa
    P4_Pa = P3_Pa * (1.0 - pressure_loss_fraction)
    if P4_Pa <= 0.0:
        raise CycleCalculationError("Combustor pressure loss produced non-positive pressure.")

    target_T4_K = turbine_inlet_temperature_K

    # --------------------------------------------------------------
    # Root-find the fuel-air ratio.
    #
    # For a trial f, the adiabatic equilibrium flame temperature T_ad(f) is
    # monotonic in f over the lean-to-near-stoichiometric range we operate in,
    # so a single Brent root suffices. The derated combustor exit is
    #
    #     T_actual(f) = T3 + eta_b * (T_ad(f) - T3)
    #
    # We solve T_actual(f) - target_T4 = 0.
    # --------------------------------------------------------------
    def _residual(f: float) -> float:
        T_ad = adiabatic_flame_temperature(T3_K, P3_Pa, f, fuel=fuel)
        T_actual = T3_K + combustor_efficiency * (T_ad - T3_K)
        return T_actual - target_T4_K

    try:
        r_lo = _residual(_FUEL_AIR_RATIO_MIN)
        r_hi = _residual(_FUEL_AIR_RATIO_MAX)
    except Exception as exc:                                # noqa: BLE001
        raise CycleCalculationError(
            f"Equilibrium combustion solver failed during bracket evaluation: {exc}"
        ) from exc

    if r_lo * r_hi > 0.0:
        # The target T04 lies outside what equilibrium can deliver in the
        # bracket. Tell the caller something actionable instead of crashing.
        raise CycleCalculationError(
            "Requested turbine inlet temperature lies outside the equilibrium "
            f"combustor bracket f∈[{_FUEL_AIR_RATIO_MIN}, {_FUEL_AIR_RATIO_MAX}]. "
            "Try a lower T04, a higher combustor efficiency, or check inlet "
            "conditions."
        )

    fuel_air_ratio = float(
        brentq(_residual, _FUEL_AIR_RATIO_MIN, _FUEL_AIR_RATIO_MAX, xtol=1.0e-7)
    )

    # Real adiabatic ceiling for reporting
    adiabatic_T_K = float(
        adiabatic_flame_temperature(T3_K, P3_Pa, fuel_air_ratio, fuel=fuel)
    )

    # Equilibrium product properties at the *actual* combustor exit state. The
    # downstream perfect-gas turbine/nozzle modules don't consume these yet,
    # but they're exposed in metadata so future refinements can pick them up
    # without touching this file.
    products = equilibrium_products(
        target_T4_K, P4_Pa, fuel_air_ratio, fuel=fuel
    )

    state = StationState(
        station=4,
        name="Combustor exit / turbine inlet",
        stagnation_temperature_K=target_T4_K,
        stagnation_pressure_Pa=P4_Pa,
        notes=[
            "Equilibrium combustion: f was root-found so that "
            "T3 + eta_b * (T_ad(f) - T3) matches the requested T04.",
            f"Adiabatic ceiling T_ad = {adiabatic_T_K:.1f} K at f = "
            f"{fuel_air_ratio:.5f} ({fuel} / air).",
        ],
    )

    warnings: list[str] = []
    if fuel_air_ratio > 0.06:
        warnings.append(
            "Fuel-air ratio is high; equilibrium model is approaching the rich "
            "limit for hydrocarbon-air mixtures."
        )
    if pressure_loss_fraction > 0.1:
        warnings.append("Combustor pressure loss is high for a preliminary cycle model.")
    if adiabatic_T_K < target_T4_K:
        # eta_b > 1 territory; only reachable with input data error.
        warnings.append(
            "INFO: Equilibrium adiabatic temperature is below the requested T04; "
            "the combustor efficiency derate would have to exceed 1.0."
        )

    return ComponentResult(
        state=state,
        warnings=warnings,
        metadata={
            "fuel_air_ratio": fuel_air_ratio,
            "adiabatic_flame_temperature_K": adiabatic_T_K,
            "combustor_model": "equilibrium",
            "product_cp_J_per_kg_K": products.cp_J_per_kg_K,
            "product_gamma": products.gamma,
            "product_R_J_per_kg_K": products.R_J_per_kg_K,
            "product_h_J_per_kg": products.h_J_per_kg,
            "fuel_species": fuel,
        },
    )
