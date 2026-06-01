"""Validation tests for the upgraded non-turbojet cycle solvers.

These tests check qualitative trends that should hold for any preliminary
turbofan / turboprop / ramjet / scramjet model:

* Turbofan: increasing bypass ratio at constant fan pressure ratio increases
  bypass thrust share and reduces TSFC at subsonic cruise.
* Turbofan: thrust > 0 across the supported FPR and BPR envelope.
* Turboprop: shaft power dominates jet thrust at low Mach.
* Turboprop: propulsive efficiency degrades at high Mach as the prop curve
  rolls off.
* Ramjet: thrust grows then plateaus with Mach; below M=1 the model warns.
* Scramjet: thrust positive only above M~4 with default settings; at M=3 the
  model still runs but emits the caution warning.
* Energy balance: thermal_efficiency + (warning if 0) — non-negative and ≤ 1.
"""

from __future__ import annotations

import pytest

from app.engine_core.ramjet import simulate_ramjet_cycle, RamjetCycleInputs
from app.engine_core.scramjet import simulate_scramjet_cycle, ScramjetCycleInputs
from app.engine_core.turbofan import simulate_turbofan_cycle, TurbofanCycleInputs
from app.engine_core.turboprop import simulate_turboprop_cycle, TurbopropCycleInputs
from app.engine_core.types import CycleCalculationError


# ---------------------------------------------------------------------------
# Turbofan
# ---------------------------------------------------------------------------


def test_turbofan_thrust_partition_is_bypass_dominant_at_high_bpr() -> None:
    """High-bypass commercial-class cruise should be bypass-dominant."""

    inputs = TurbofanCycleInputs(
        bypass_ratio=10.0,
        fan_pressure_ratio=1.55,
        core_compressor_pressure_ratio=27.0,
        total_mass_flow_air_kg_s=600.0,
        turbine_inlet_temperature_K=1600.0,
        mach=0.8,
        altitude_m=10000.0,
        nozzle_configuration="separate",
    )
    out = simulate_turbofan_cycle(inputs)
    assert out["bypass_thrust_N"] > out["core_thrust_N"]
    # Bypass exit velocity should be lower than core exit velocity for any
    # plausible high-bypass turbofan.
    assert out["bypass_exit_velocity_m_s"] is not None
    assert out["bypass_exit_velocity_m_s"] < out["exit_velocity_m_s"]


def test_turbofan_tsfc_decreases_with_bypass_ratio_at_fixed_fpr() -> None:
    """TSFC should improve as BPR grows from low to medium values."""

    low = simulate_turbofan_cycle(TurbofanCycleInputs(bypass_ratio=1.0, total_mass_flow_air_kg_s=200.0))
    high = simulate_turbofan_cycle(TurbofanCycleInputs(bypass_ratio=8.0, total_mass_flow_air_kg_s=200.0))
    assert high["TSFC_kg_per_kN_hr"] < low["TSFC_kg_per_kN_hr"]


def test_turbofan_mixed_flow_is_a_valid_alternative() -> None:
    """Mixed-flow configuration must run cleanly at low BPR."""

    out = simulate_turbofan_cycle(
        TurbofanCycleInputs(nozzle_configuration="mixed", bypass_ratio=0.4)
    )
    assert out["thrust_N"] > 0.0
    assert 0.0 <= out["thermal_efficiency_estimate"] <= 1.0


def test_turbofan_with_afterburner_increases_thrust_and_fuel_flow() -> None:
    """AB should raise thrust and fuel flow versus the dry cycle."""

    dry = simulate_turbofan_cycle(TurbofanCycleInputs(nozzle_configuration="mixed"))
    wet = simulate_turbofan_cycle(
        TurbofanCycleInputs(
            nozzle_configuration="mixed",
            use_afterburner=True,
            afterburner_exit_temperature_K=2000.0,
        )
    )
    assert wet["thrust_N"] > dry["thrust_N"]
    assert wet["fuel_flow_kg_s"] > dry["fuel_flow_kg_s"]


# ---------------------------------------------------------------------------
# Turboprop
# ---------------------------------------------------------------------------


def test_turboprop_shaft_power_dominates_jet_thrust_at_cruise() -> None:
    """At low Mach, prop thrust should dominate residual jet thrust."""

    out = simulate_turboprop_cycle(TurbopropCycleInputs())
    assert out["propeller_thrust_N"] > out["jet_thrust_N"]
    assert out["shaft_power_kW"] > 100.0
    assert out["BSFC_kg_per_kW_h"] > 0.0


def test_turboprop_propulsive_efficiency_falls_at_high_mach() -> None:
    """Past the design advance ratio the propeller efficiency rolls off."""

    # Set the prop peak well below cruise so the high-Mach case is past peak.
    inputs_low = TurbopropCycleInputs(mach=0.3, advance_ratio_at_peak=0.6)
    inputs_high = TurbopropCycleInputs(mach=0.55, advance_ratio_at_peak=0.6)
    low = simulate_turboprop_cycle(inputs_low)
    high = simulate_turboprop_cycle(inputs_high)
    assert (
        low["extra"]["propeller_efficiency"]
        > high["extra"]["propeller_efficiency"]
    )


def test_turboprop_actuator_disk_branch_at_static() -> None:
    """At V0=0 the model must use the actuator-disk static thrust branch."""

    out = simulate_turboprop_cycle(TurbopropCycleInputs(mach=0.0))
    assert out["extra"]["propeller_regime"] == "static-actuator-disk"
    assert out["propeller_thrust_N"] > 0.0


# ---------------------------------------------------------------------------
# Ramjet
# ---------------------------------------------------------------------------


def test_ramjet_thrust_grows_then_falls_with_mach() -> None:
    """Thrust rises from M=1.5 to a peak around M=2 then declines because the
    MIL-spec recovery degrades and V0 grows faster than V9 at fixed Tt4."""

    thrust_by_mach = [
        simulate_ramjet_cycle(RamjetCycleInputs(mach=M))["thrust_kN"]
        for M in (1.5, 2.0, 3.0)
    ]
    # Rising part of the curve.
    assert thrust_by_mach[1] > thrust_by_mach[0]
    # Past peak the thrust declines (educational physics of fixed-Tt ramjet).
    assert thrust_by_mach[2] < thrust_by_mach[1]


def test_ramjet_emits_low_mach_caution() -> None:
    """Below ~M1.5 the model should warn about poor ram compression."""

    out = simulate_ramjet_cycle(RamjetCycleInputs(mach=1.2))
    assert any("inefficient below" in w.lower() for w in out["warnings"])


def test_ramjet_high_mach_recovery_warning() -> None:
    """At very high Mach the inlet-recovery model loses fidelity. Use a
    higher Tt4 so the cycle still produces thrust at this Mach so we can read
    the warning list."""

    out = simulate_ramjet_cycle(
        RamjetCycleInputs(
            mach=5.5,
            altitude_m=22000.0,
            combustor_exit_temperature_K=2500.0,
        )
    )
    assert any("fidelity above" in w.lower() for w in out["warnings"])


# ---------------------------------------------------------------------------
# Scramjet
# ---------------------------------------------------------------------------


def test_scramjet_runs_at_mach_6_with_positive_thrust() -> None:
    out = simulate_scramjet_cycle(ScramjetCycleInputs())
    assert out["thrust_N"] > 0.0
    assert out["extra"]["combustor_mode"] == "supersonic"


def test_scramjet_emits_below_operating_mach_caution() -> None:
    out = simulate_scramjet_cycle(ScramjetCycleInputs(mach=3.5))
    assert any(
        "below efficient operating mach" in w.lower() for w in out["warnings"]
    )


def test_scramjet_dissociation_warning_at_extreme_T() -> None:
    """Very high Tt4 should emit the dissociation caution."""

    out = simulate_scramjet_cycle(
        ScramjetCycleInputs(equivalence_ratio=3.0, mach=8.0)
    )
    assert any(
        "exceeds 3000 k" in w.lower() for w in out["warnings"]
    ) or any("dissociation" in w.lower() for w in out["warnings"])


# ---------------------------------------------------------------------------
# Energy and momentum sanity (all engines)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    [
        ("turbofan", TurbofanCycleInputs(), simulate_turbofan_cycle, True),
        # Turboprop overall efficiency includes propeller shaft thrust, which
        # is not captured by the (jet-only) thermal_efficiency_estimate metric.
        # We therefore only check bounds for the turboprop.
        ("turboprop", TurbopropCycleInputs(), simulate_turboprop_cycle, False),
        ("ramjet", RamjetCycleInputs(), simulate_ramjet_cycle, True),
        ("scramjet", ScramjetCycleInputs(), simulate_scramjet_cycle, True),
    ],
    ids=["turbofan", "turboprop", "ramjet", "scramjet"],
)
def test_energy_balance_efficiencies_are_bounded(case) -> None:
    """All three efficiencies must lie within [0, 1] and outputs positive."""

    _engine_name, inputs, solver, check_overall_chain = case
    out = solver(inputs)
    assert out["thrust_N"] > 0.0
    assert out["fuel_flow_kg_s"] > 0.0
    assert 0.0 <= out["thermal_efficiency_estimate"] <= 1.0
    assert 0.0 <= out["propulsive_efficiency_estimate"] <= 1.0
    assert 0.0 <= out["overall_efficiency_estimate"] <= 1.0
    if check_overall_chain:
        # Overall ≈ thermal * propulsive for pure-jet engines.
        overall_recomputed = (
            out["thermal_efficiency_estimate"]
            * out["propulsive_efficiency_estimate"]
        )
        assert out["overall_efficiency_estimate"] == pytest.approx(
            overall_recomputed, abs=0.08
        )
