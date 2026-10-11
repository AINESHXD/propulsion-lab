"""PistonLab feasibility analysis.

The report makes three kinds of claim, and each is tested against the solver
rather than against itself:

* that a check passes or fails: compared with the solver's own outputs and
  warnings, so the report can never disagree with the console;
* that a recommended change cures the engine: the recommended engine is run
  back through the analysis independently, and must not fail anything;
* that the cost figures are what they say they are: the fuel cost is
  recomputed from first principles, and the build index is anchored to its
  stated baseline.
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from app.engine_core.piston.fuel import get_fuel
from app.main import piston_feasibility
from app.piston_feasibility import (
    BASELINE, BURNED_GAS_GAMMA, FUEL_PRICE_GBP_PER_L, analyse,
)
from app.schemas_piston import PistonSimulateInput, run_piston_simulation

OVERSTRESSED = dict(fuel="gasoline", cylinders=4, displacement_L=2.0, bore_stroke_ratio=0.85,
                    compression_ratio=13.0, rpm=7000, aspiration="turbocharged", intake_pressure_Pa=2.6e5)
SMOKY_DIESEL = dict(fuel="diesel", cylinders=4, displacement_L=2.0, bore_stroke_ratio=0.9,
                    compression_ratio=11.0, rpm=3000, equivalence_ratio=1.0, combustion_start_deg=-8)
OVERREVVED = dict(fuel="gasoline", cylinders=4, displacement_L=2.0, bore_stroke_ratio=0.8,
                  compression_ratio=10.5, rpm=9000)


@pytest.fixture(scope="module")
def baseline():
    return analyse(PistonSimulateInput(**BASELINE))


@pytest.fixture(scope="module")
def overstressed():
    return analyse(PistonSimulateInput(**OVERSTRESSED))


@pytest.fixture(scope="module")
def diesel():
    return analyse(PistonSimulateInput(**SMOKY_DIESEL))


def _check(report, key, verified=False):
    return next(c for c in (report.verified_checks if verified else report.checks) if c.key == key)


# --------------------------------------------------------------------------- #
# verdicts agree with the solver
# --------------------------------------------------------------------------- #
def test_an_ordinary_engine_is_feasible_and_left_alone(baseline) -> None:
    assert baseline.verdict == "feasible"
    assert baseline.recommendations == []
    assert baseline.recommended_inputs == {}


def test_the_knock_check_agrees_with_the_solvers_own_warning(overstressed) -> None:
    # The report must never contradict the console. The solver flags knock when
    # its margin goes negative; the report's knock check must fail exactly then.
    solved = run_piston_simulation(PistonSimulateInput(**OVERSTRESSED))
    solver_knocks = any(w.kind == "knock" and w.severity == "warning" for w in solved.operating_warnings)
    assert solver_knocks
    assert _check(overstressed, "knock_margin").status == "fail"
    assert _check(overstressed, "knock_margin").value < 0


def test_peak_pressure_is_the_solvers_peak_pressure(overstressed) -> None:
    solved = run_piston_simulation(PistonSimulateInput(**OVERSTRESSED))
    assert _check(overstressed, "peak_pressure").value == pytest.approx(solved.peak_pressure_Pa / 1e5)


def test_piston_speed_is_twice_stroke_times_revs(overstressed) -> None:
    solved = run_piston_simulation(PistonSimulateInput(**OVERSTRESSED))
    assert _check(overstressed, "piston_speed").value == pytest.approx(2 * solved.stroke_m * 7000 / 60)


def test_the_exhaust_estimate_is_blowdown_from_valve_opening() -> None:
    # The solver's exhaust temperature is the gas in the cylinder at exhaust-
    # valve opening. What reaches the manifold has expanded to back-pressure,
    # so the estimate must sit below it by exactly the isentropic ratio.
    spec = dict(BASELINE, include_trace=True)
    solved = run_piston_simulation(PistonSimulateInput(**spec))
    p_evo = solved.trace[-1].pressure_Pa
    expect = solved.exhaust_temperature_K * (solved.exhaust_pressure_Pa / p_evo) ** (
        (BURNED_GAS_GAMMA - 1) / BURNED_GAS_GAMMA) - 273.15
    got = _check(analyse(PistonSimulateInput(**BASELINE)), "exhaust_T").value
    assert got == pytest.approx(expect)
    assert got < solved.exhaust_temperature_K - 273.15


def test_every_check_states_its_basis(overstressed) -> None:
    for c in overstressed.checks:
        assert len(c.basis) > 40, c.key


# --------------------------------------------------------------------------- #
# recommendations really cure the engine
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("spec", [OVERSTRESSED, SMOKY_DIESEL, OVERREVVED], ids=["turbo", "diesel", "revs"])
def test_the_recommended_engine_passes_when_checked_independently(spec) -> None:
    # The strongest claim the report makes. Take the engine it recommends and
    # run it back through the analysis from scratch: nothing may fail.
    report = analyse(PistonSimulateInput(**spec))
    assert report.verdict == "not_feasible"
    assert report.recommended_inputs, "a failing engine must get a recommendation"
    fixed = analyse(PistonSimulateInput(**{**spec, **report.recommended_inputs}))
    assert all(c.status != "fail" for c in fixed.checks), [c.key for c in fixed.checks if c.status == "fail"]
    assert fixed.verdict == report.verified_verdict


def test_cures_are_applied_most_severe_first(overstressed) -> None:
    # Knock destroys an engine; peak pressure is a structural envelope. Curing
    # knock first with compression also lowers peak pressure, so the boost cut
    # that follows is smaller than it would be if both were sized independently.
    steps = [r.check_key for r in overstressed.recommendations if r.resolved]
    assert steps[0] == "knock_margin"
    assert overstressed.after.brake_power_kW > 0.6 * overstressed.before.brake_power_kW


def test_each_step_reports_what_the_re_solve_measured(overstressed) -> None:
    for r in overstressed.recommendations:
        if not r.resolved:
            continue
        assert r.metric_before is not None and r.metric_after is not None
        assert r.metric_after != pytest.approx(r.metric_before)
        assert "re-solving" in r.rationale


def test_one_change_that_cures_several_checks_says_so(diesel) -> None:
    # Leaning a smoking diesel out also cuts its exhaust temperature and BMEP.
    resolved = [r for r in diesel.recommendations if r.resolved]
    assert len(resolved) == 1 and resolved[0].lever == "equivalence_ratio"
    assert resolved[0].also_cured
    assert "also brings" in resolved[0].rationale


# --------------------------------------------------------------------------- #
# the proof graphs are real solver sweeps
# --------------------------------------------------------------------------- #
def test_each_proof_sweep_crosses_the_limit(overstressed) -> None:
    for pr in overstressed.proofs:
        assert len(pr.x) == 9 and len(pr.metric) == 9
        assert min(pr.x) <= min(pr.current_x, pr.recommended_x) + 1e-9
        assert max(pr.x) >= max(pr.current_x, pr.recommended_x) - 1e-9
        vals = [v for v in pr.metric if v is not None]
        if pr.limit is not None and pr.metric_key != "boost":
            assert min(vals) <= pr.limit <= max(vals) or min(vals) <= (pr.caution or pr.limit) <= max(vals)


# --------------------------------------------------------------------------- #
# cost
# --------------------------------------------------------------------------- #
def test_the_baseline_engine_is_the_index_origin(baseline) -> None:
    assert baseline.cost_before.build_cost_index == pytest.approx(100.0)
    assert baseline.cost_before.cost_index_per_kW == pytest.approx(1.0)
    assert sum(l.points for l in baseline.cost_before.breakdown) == pytest.approx(100.0)


def test_fuel_cost_is_bsfc_times_power_over_density_times_price(baseline) -> None:
    b = baseline.before
    density = get_fuel("gasoline").density_kg_per_m3 / 1000
    litres_per_h = b.bsfc_g_per_kWh * b.brake_power_kW / 1000 / density
    assert baseline.cost_before.fuel_L_per_h == pytest.approx(litres_per_h)
    assert baseline.cost_before.fuel_cost_gbp_per_h == pytest.approx(litres_per_h * FUEL_PRICE_GBP_PER_L["gasoline"])


def test_hardware_shows_up_in_the_cost(overstressed, diesel, baseline) -> None:
    items = {l.item for l in overstressed.cost_before.breakdown}
    assert {"Turbocharger", "Intercooler", "Uprated internals"} <= items
    assert diesel.cost_before.build_cost_index > baseline.cost_before.build_cost_index


# --------------------------------------------------------------------------- #
# the endpoint
# --------------------------------------------------------------------------- #
def test_the_endpoint_returns_the_report() -> None:
    body = piston_feasibility(PistonSimulateInput(**OVERREVVED)).model_dump()
    assert body["verdict"] == "not_feasible"
    assert body["recommended_inputs"]["rpm"] < 9000
    assert body["proofs"] and body["assumptions"]


def test_an_impossible_engine_is_rejected_before_any_analysis() -> None:
    with pytest.raises(ValidationError):
        PistonSimulateInput(**{**BASELINE, "compression_ratio": 1.0})
