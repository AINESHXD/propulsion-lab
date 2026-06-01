"""Tests for the optional Cantera-backed equilibrium combustor.

The whole module is skipped when Cantera is not installed so a vanilla
``pip install -r requirements.txt`` continues to pass the test suite.
"""

from __future__ import annotations

import pytest

# Skip the entire module if Cantera isn't available — the educational
# constant-cp combustor is fully covered by tests/test_components.py.
pytest.importorskip("cantera")

from app.engine_core.atmosphere import isa_atmosphere  # noqa: E402
from app.engine_core.combustor import calculate_combustor_exit  # noqa: E402
from app.engine_core.combustor_equilibrium import (  # noqa: E402
    calculate_combustor_exit_equilibrium,
)
from app.engine_core.compressor import calculate_compressor_exit  # noqa: E402
from app.engine_core.inlet import (  # noqa: E402
    calculate_freestream_state,
    calculate_inlet_exit,
)
from app.engine_core.turbojet import simulate_turbojet_cycle  # noqa: E402
from app.engine_core.types import (  # noqa: E402
    CycleCalculationError,
    TurbojetCycleInputs,
)


def _compressor_exit_state():
    """Build a representative compressor exit state (PLab-01 baseline)."""

    inputs = TurbojetCycleInputs()
    atmosphere = isa_atmosphere(inputs.altitude_m)
    freestream = calculate_freestream_state(atmosphere, inputs.mach)
    inlet = calculate_inlet_exit(freestream.state, inputs.inlet_pressure_recovery)
    compressor = calculate_compressor_exit(
        inlet.state,
        inputs.compressor_pressure_ratio,
        inputs.compressor_efficiency,
    )
    return inputs, compressor.state


# ---------------------------------------------------------------------------
# 1. Sanity: the equilibrium model returns a station-4 state with the same
#    target T04 and the requested pressure drop.
# ---------------------------------------------------------------------------


def test_equilibrium_combustor_hits_requested_T04():
    inputs, compressor_state = _compressor_exit_state()
    target_T04 = 1450.0

    result = calculate_combustor_exit_equilibrium(
        compressor_state,
        target_T04,
        inputs.combustor_efficiency,
        inputs.combustor_pressure_loss_fraction,
        inputs.fuel_heating_value_J_kg,
    )

    assert result.state.station == 4
    assert result.state.stagnation_temperature_K == pytest.approx(target_T04, rel=1e-9)
    expected_P4 = compressor_state.stagnation_pressure_Pa * (
        1.0 - inputs.combustor_pressure_loss_fraction
    )
    assert result.state.stagnation_pressure_Pa == pytest.approx(expected_P4, rel=1e-9)


# ---------------------------------------------------------------------------
# 2. Cross-check: at a moderate T04 the equilibrium fuel-air ratio should be
#    of the same order as the constant-cp model. We allow a generous tolerance
#    because the underlying physics genuinely differ: the perfect-gas model
#    uses cp_gas = 1150 and a calorific energy balance, while the equilibrium
#    model uses Cantera enthalpies of formation and species-specific cp(T).
#    20% agreement is the right tolerance for "the two models tell the same
#    story" at preliminary-design temperatures.
# ---------------------------------------------------------------------------


def test_equilibrium_and_perfect_gas_agree_at_moderate_T():
    inputs, compressor_state = _compressor_exit_state()
    target_T04 = 1400.0

    perfect = calculate_combustor_exit(
        compressor_state,
        target_T04,
        inputs.combustor_efficiency,
        inputs.combustor_pressure_loss_fraction,
        inputs.fuel_heating_value_J_kg,
    )
    equilibrium = calculate_combustor_exit_equilibrium(
        compressor_state,
        target_T04,
        inputs.combustor_efficiency,
        inputs.combustor_pressure_loss_fraction,
        inputs.fuel_heating_value_J_kg,
    )

    f_perfect = float(perfect.metadata["fuel_air_ratio"])
    f_equil = float(equilibrium.metadata["fuel_air_ratio"])

    # Sane lean turbojet range
    assert 0.005 < f_perfect < 0.05
    assert 0.005 < f_equil < 0.05

    # Same story within 20 % — the two models *should* differ at high T04 due
    # to dissociation; at 1400 K they agree closely.
    assert abs(f_equil - f_perfect) / f_perfect < 0.20


# ---------------------------------------------------------------------------
# 3. High T04: the equilibrium model should still find a sensible f and the
#    adiabatic ceiling should be at or above the requested T04 (otherwise the
#    derate by eta_b < 1 cannot raise the gas to T04).
# ---------------------------------------------------------------------------


def test_equilibrium_at_high_T04_returns_sensible_fuel_air_ratio():
    inputs, compressor_state = _compressor_exit_state()
    target_T04 = 1850.0

    result = calculate_combustor_exit_equilibrium(
        compressor_state,
        target_T04,
        inputs.combustor_efficiency,
        inputs.combustor_pressure_loss_fraction,
        inputs.fuel_heating_value_J_kg,
    )

    f = float(result.metadata["fuel_air_ratio"])
    T_ad = float(result.metadata["adiabatic_flame_temperature_K"])

    assert 0.005 < f < 0.07
    # Derate model: T_actual = T3 + eta_b * (T_ad - T3), so for the math to
    # land at T04 with eta_b < 1, T_ad must exceed T04.
    assert T_ad >= target_T04
    assert result.metadata["combustor_model"] == "equilibrium"
    # Product properties should be physical
    assert 1000.0 < float(result.metadata["product_cp_J_per_kg_K"]) < 2500.0
    assert 1.20 < float(result.metadata["product_gamma"]) < 1.40


# ---------------------------------------------------------------------------
# 4. End-to-end: simulate_turbojet_cycle should produce numerically close
#    results in both modes at moderate T04, and the equilibrium-mode result
#    should advertise the new metadata via the station notes.
# ---------------------------------------------------------------------------


def test_simulate_turbojet_cycle_equilibrium_path_runs_and_is_close():
    perfect_inputs = TurbojetCycleInputs(turbine_inlet_temperature_K=1400.0)
    equilibrium_inputs = TurbojetCycleInputs(
        turbine_inlet_temperature_K=1400.0,
        use_equilibrium_combustion=True,
    )

    perfect_result = simulate_turbojet_cycle(perfect_inputs)
    equilibrium_result = simulate_turbojet_cycle(equilibrium_inputs)

    # Both should choose to choke or not consistently at this baseline
    assert perfect_result["nozzle_choked"] == equilibrium_result["nozzle_choked"]

    # Thrust within 15 %, TSFC within 25 % at moderate T04
    assert abs(equilibrium_result["thrust_kN"] - perfect_result["thrust_kN"]) \
        / perfect_result["thrust_kN"] < 0.15
    assert abs(
        equilibrium_result["TSFC_kg_per_kN_hr"] - perfect_result["TSFC_kg_per_kN_hr"]
    ) / perfect_result["TSFC_kg_per_kN_hr"] < 0.25

    # Equilibrium path should annotate the station-4 notes
    station_4_notes = equilibrium_result["station_table"][4].get("notes") or []
    assert any("equilibrium" in note.lower() for note in station_4_notes)


# ---------------------------------------------------------------------------
# 5. Bracket failure: an absurdly high T04 with low eta_b should refuse to
#    converge rather than silently producing garbage.
# ---------------------------------------------------------------------------


def test_equilibrium_combustor_raises_when_bracket_fails():
    inputs, compressor_state = _compressor_exit_state()
    # Demand more temperature rise than any plausible f can deliver after a
    # punishing efficiency derate.
    with pytest.raises(CycleCalculationError):
        calculate_combustor_exit_equilibrium(
            compressor_state,
            turbine_inlet_temperature_K=2299.0,
            combustor_efficiency=0.10,           # heavy derate
            pressure_loss_fraction=0.05,
            fuel_heating_value_J_kg=inputs.fuel_heating_value_J_kg,
        )
