"""Tests for the real-gas hot-section module (Day 18).

Day 18 acceptance: the mean-cp turbine drop at the HPT inlet matches the
real-gas enthalpy balance to within 0.1 %. Also checks that the real burned
gas is meaningfully stiffer than the constant-cp educational model, and that
the constant-cp fallback engages cleanly when Cantera is unavailable.
"""

from __future__ import annotations

import pytest

from app.engine_core import gas_service
from app.engine_core.constants import cp_gas
from app.engine_core.gas_service import frozen_gas_properties, is_cantera_available
from app.engine_core.real_gas import (
    constant_cp_exit_temperature,
    freeze_hot_section,
    hot_gas_cp,
    turbine_exit_temperature_enthalpy_balance,
    turbine_exit_temperature_mean_cp,
)

cantera_only = pytest.mark.skipif(
    not is_cantera_available(), reason="Cantera not installed"
)

# A spread of HPT-inlet conditions and turbine specific works.
_CASES = [
    (1600.0, 2.0e6, 280e3, 0.025),
    (1500.0, 1.6e6, 250e3, 0.022),
    (1700.0, 2.8e6, 320e3, 0.028),
]


@cantera_only
def test_mean_cp_drop_matches_enthalpy_balance_within_0p1pct() -> None:
    """Day 18 — mean-cp Tt drop ≈ enthalpy-balance Tt drop to < 0.1 %."""

    for Tt_in, P, work, far in _CASES:
        comp = freeze_hot_section(Tt_in, P, far)
        mean = turbine_exit_temperature_mean_cp(Tt_in, P, work, far, composition=comp)
        exact = turbine_exit_temperature_enthalpy_balance(Tt_in, P, work, far, composition=comp)
        drop_mean = Tt_in - mean.exit_temperature_K
        drop_exact = Tt_in - exact
        assert abs(drop_mean - drop_exact) / drop_exact < 1e-3
        assert mean.iterations < 12
        assert mean.source == "cantera"


@cantera_only
def test_real_gas_cp_exceeds_constant_model() -> None:
    """Burned-gas cp at turbine temperatures is well above the constant model."""

    comp = freeze_hot_section(1600.0, 2.0e6, 0.025)
    cp_hot = hot_gas_cp(comp, 1600.0, 2.0e6)
    assert cp_hot > cp_gas          # 1150 J/kg·K constant model
    assert 1250.0 < cp_hot < 1450.0  # physically sensible band


@cantera_only
def test_real_gas_drop_smaller_than_constant_cp() -> None:
    """Higher real cp means a smaller Tt drop for the same turbine work."""

    Tt_in, P, work, far = 1600.0, 2.0e6, 280e3, 0.025
    comp = freeze_hot_section(Tt_in, P, far)
    real_exit = turbine_exit_temperature_enthalpy_balance(Tt_in, P, work, far, composition=comp)
    const_exit = constant_cp_exit_temperature(Tt_in, work)
    # Real gas absorbs the work with less cooling -> higher exit temperature.
    assert real_exit > const_exit
    real_drop = Tt_in - real_exit
    const_drop = Tt_in - const_exit
    assert const_drop > real_drop


@cantera_only
def test_enthalpy_balance_round_trips() -> None:
    """The exact solver actually closes the enthalpy balance."""

    Tt_in, P, work, far = 1600.0, 2.0e6, 280e3, 0.025
    comp = freeze_hot_section(Tt_in, P, far)
    h_in = frozen_gas_properties(comp, Tt_in, P).h_J_per_kg
    exit_T = turbine_exit_temperature_enthalpy_balance(Tt_in, P, work, far, composition=comp)
    h_out = frozen_gas_properties(comp, exit_T, P).h_J_per_kg
    assert (h_in - h_out) == pytest.approx(work, rel=2e-5)


# ---------------------------------------------------------------------------
# Day 19 — hot section extended to LPT + nozzle; real_gas toggle
# ---------------------------------------------------------------------------

from app.engine_core.real_gas import hot_section_temperatures  # noqa: E402
from app.engine_core.turbojet import simulate_turbojet_cycle  # noqa: E402
from app.engine_core.types import TurbojetCycleInputs  # noqa: E402


@cantera_only
def test_hot_section_frozen_within_2pct_of_equilibrium() -> None:
    """Day 19 — HPT, LPT and nozzle exit temperatures from the frozen model are
    within 2 % of the equilibrium-cp model."""

    kw = dict(
        turbine_inlet_temperature_K=1600.0, turbine_inlet_pressure_Pa=2.0e6,
        hpt_exit_pressure_Pa=1.0e6, lpt_exit_pressure_Pa=0.35e6,
        nozzle_exit_pressure_Pa=0.1e6,
        hpt_specific_work_J_per_kg=280e3, lpt_specific_work_J_per_kg=200e3,
        fuel_air_ratio=0.025, nozzle_efficiency=0.95,
    )
    frozen = hot_section_temperatures(mode="frozen", **kw)
    equilibrium = hot_section_temperatures(mode="equilibrium", **kw)
    for a, b in [
        (frozen.hpt_exit_temperature_K, equilibrium.hpt_exit_temperature_K),
        (frozen.lpt_exit_temperature_K, equilibrium.lpt_exit_temperature_K),
        (frozen.nozzle_exit_static_temperature_K, equilibrium.nozzle_exit_static_temperature_K),
    ]:
        assert abs(a - b) / b < 0.02


@cantera_only
def test_real_gas_toggle_attaches_block_and_raises_turbine_exit() -> None:
    """The real_gas toggle adds a hot-section block; the variable-cp turbine
    exit is hotter than the constant-cp one (higher cp -> smaller drop)."""

    base = dict(altitude_m=10000.0, mach=0.8, compressor_pressure_ratio=12.0,
                turbine_inlet_temperature_K=1500.0)
    off = simulate_turbojet_cycle(TurbojetCycleInputs(real_gas=False, **base))
    on = simulate_turbojet_cycle(TurbojetCycleInputs(real_gas=True, **base))

    assert off["real_gas_hot_section"] is None
    block = on["real_gas_hot_section"]
    assert block is not None and "error" not in block
    assert block["source"] == "cantera"
    assert block["turbine_exit_temperature_K"] > block["constant_cp_turbine_exit_temperature_K"]
    # Core constant-cp station table is untouched by the toggle.
    assert on["station_table"][5]["stagnation_temperature_K"] == pytest.approx(
        off["station_table"][5]["stagnation_temperature_K"]
    )


def test_real_gas_toggle_default_off_leaves_result_unchanged() -> None:
    """Default (no toggle) carries no real-gas block — backward compatible."""

    result = simulate_turbojet_cycle(TurbojetCycleInputs(turbine_inlet_temperature_K=1500.0))
    assert result["real_gas_hot_section"] is None


def test_constant_cp_fallback_when_cantera_unavailable(monkeypatch) -> None:
    """With Cantera off, both methods reduce to the constant-cp model."""

    monkeypatch.setattr(gas_service, "_CANTERA_AVAILABLE", False)
    Tt_in, work = 1600.0, 280e3
    # composition=None forces the constant-cp branch in frozen_gas_properties.
    mean = turbine_exit_temperature_mean_cp(Tt_in, 2.0e6, work, 0.025, composition=None)
    exact = turbine_exit_temperature_enthalpy_balance(Tt_in, 2.0e6, work, 0.025, composition=None)
    constant = constant_cp_exit_temperature(Tt_in, work)
    assert mean.source == "constant-cp"
    assert mean.exit_temperature_K == pytest.approx(constant, rel=1e-9)
    assert exact == pytest.approx(constant, rel=1e-6)


# ---------------------------------------------------------------------------
# Day 20 — consolidation: real-gas trends + nozzle behaviour
# ---------------------------------------------------------------------------


@cantera_only
def test_turbine_drop_gap_grows_with_inlet_temperature() -> None:
    """The real-gas correction (real exit hotter than constant-cp) grows with
    inlet temperature, because cp rises with T."""

    work, far, P = 280e3, 0.025, 2.0e6

    def gap(Tt_in: float) -> float:
        comp = freeze_hot_section(Tt_in, P, far)
        real = turbine_exit_temperature_enthalpy_balance(Tt_in, P, work, far, composition=comp)
        const = constant_cp_exit_temperature(Tt_in, work)
        return real - const

    assert gap(1700.0) > gap(1300.0) > 0.0


# ---------------------------------------------------------------------------
# Whole-cycle real gas — cold side (compressor) + the real_gas_cycle block
# ---------------------------------------------------------------------------

from app.engine_core.real_gas import (  # noqa: E402
    compressor_exit_temperature_real_gas,
)


@cantera_only
def test_compressor_real_gas_cooler_than_constant_cp() -> None:
    """Variable-cp air (cp rises with T) gives a slightly smaller compressor
    temperature rise than the constant-cp model for the same PR and efficiency."""

    inlet_T, inlet_P, pr, eta = 280.0, 4.0e4, 12.0, 0.86
    rg = compressor_exit_temperature_real_gas(inlet_T, inlet_P, pr, eta)
    # constant-cp deck exit T for the same inputs
    from app.engine_core.constants import gamma_air
    ratio = pr ** ((gamma_air - 1.0) / gamma_air)
    cc_exit = inlet_T + (inlet_T * ratio - inlet_T) / eta
    assert rg.source == "cantera"
    assert rg.exit_temperature_K < cc_exit          # real gas a touch cooler
    assert (cc_exit - rg.exit_temperature_K) < 30.0  # but only modestly
    assert 1004.0 < rg.cp_mean_J_per_kg_K < 1120.0   # physical mean cp band


@cantera_only
def test_real_gas_cycle_block_spans_cold_and_hot() -> None:
    """The real_gas toggle attaches a whole-cycle block: compressor (cooler),
    turbine and nozzle (hotter), each paired against the constant-cp deck."""

    base = dict(altitude_m=10000.0, mach=0.8, compressor_pressure_ratio=12.0,
                turbine_inlet_temperature_K=1500.0)
    off = simulate_turbojet_cycle(TurbojetCycleInputs(real_gas=False, **base))
    on = simulate_turbojet_cycle(TurbojetCycleInputs(real_gas=True, **base))

    assert off["real_gas_cycle"] is None
    rg = on["real_gas_cycle"]
    assert rg is not None and "error" not in rg and rg["source"] == "cantera"
    by_station = {s["station"]: s for s in rg["stations"]}
    assert set(by_station) == {3, 5, 9}
    # Compressor (3) real gas cooler; turbine (5) and nozzle (9) hotter.
    assert by_station[3]["delta_K"] < 0.0
    assert by_station[5]["delta_K"] > 0.0
    assert by_station[9]["delta_K"] > 0.0
    # Constant-cp columns equal the actual deck station values.
    assert by_station[3]["constant_cp_K"] == pytest.approx(
        off["station_table"][3]["stagnation_temperature_K"]
    )
    assert by_station[5]["constant_cp_K"] == pytest.approx(
        off["station_table"][5]["stagnation_temperature_K"]
    )
    # The toggle does not perturb the core constant-cp deck.
    for st in (3, 5):
        assert on["station_table"][st]["stagnation_temperature_K"] == pytest.approx(
            off["station_table"][st]["stagnation_temperature_K"]
        )
    assert on["thrust_N"] == pytest.approx(off["thrust_N"])


def test_real_gas_cycle_default_off() -> None:
    """No toggle -> no whole-cycle block (backward compatible)."""

    result = simulate_turbojet_cycle(TurbojetCycleInputs(turbine_inlet_temperature_K=1500.0))
    assert result["real_gas_cycle"] is None


def test_compressor_real_gas_fallback_matches_constant_cp(monkeypatch) -> None:
    """With Cantera off, the compressor real-gas walk reduces to constant-cp."""

    monkeypatch.setattr(gas_service, "_CANTERA_AVAILABLE", False)
    from app.engine_core.constants import gamma_air
    inlet_T, inlet_P, pr, eta = 288.0, 1.0e5, 10.0, 0.88
    rg = compressor_exit_temperature_real_gas(inlet_T, inlet_P, pr, eta)
    ratio = pr ** ((gamma_air - 1.0) / gamma_air)
    cc_exit = inlet_T + (inlet_T * ratio - inlet_T) / eta
    assert rg.source == "constant-cp"
    assert rg.exit_temperature_K == pytest.approx(cc_exit, rel=1e-9)


@cantera_only
def test_hot_section_nozzle_cools_and_accelerates() -> None:
    """Gas cools monotonically through HPT, LPT and the nozzle, and leaves with
    positive velocity."""

    hs = hot_section_temperatures(
        turbine_inlet_temperature_K=1600.0, turbine_inlet_pressure_Pa=2.0e6,
        hpt_exit_pressure_Pa=1.0e6, lpt_exit_pressure_Pa=0.35e6,
        nozzle_exit_pressure_Pa=0.1e6,
        hpt_specific_work_J_per_kg=280e3, lpt_specific_work_J_per_kg=200e3,
        fuel_air_ratio=0.025, nozzle_efficiency=0.95,
    )
    assert hs.hpt_exit_temperature_K < 1600.0
    assert hs.lpt_exit_temperature_K < hs.hpt_exit_temperature_K
    assert hs.nozzle_exit_static_temperature_K < hs.lpt_exit_temperature_K
    assert hs.nozzle_exit_velocity_m_s > 0.0
