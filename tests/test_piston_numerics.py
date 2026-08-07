"""Numerical control: the crank-angle step, and proving it does not matter.

The step size was fixed at 0.5 deg inside the solver and unreachable from the
API, so a caller had no way to tell whether an answer was a property of the
engine or an artefact of the discretisation. These cover the exposed control and
the convergence study that makes it checkable.
"""

from __future__ import annotations

import pytest

from app.main import piston_convergence
from app.schemas_piston import (
    CONVERGENCE_LADDER,
    DEFAULT_D_THETA_DEG,
    PistonSimulateInput,
    run_piston_convergence,
    run_piston_simulation,
)


# --------------------------------------------------------------------------- #
# the control itself
# --------------------------------------------------------------------------- #
def test_the_step_is_reachable_from_the_api() -> None:
    assert "d_theta_deg" in PistonSimulateInput.model_fields


def test_the_step_actually_reaches_the_solver() -> None:
    # If the field existed but were dropped on the way through, the two runs
    # would be identical and the control would be decorative.
    coarse = run_piston_simulation(PistonSimulateInput(d_theta_deg=4.0))
    fine = run_piston_simulation(PistonSimulateInput(d_theta_deg=0.125))
    assert coarse.brake_power_W != fine.brake_power_W


def test_the_step_is_bounded() -> None:
    for bad in (0.0, -1.0, 5.5):
        with pytest.raises(ValueError):
            PistonSimulateInput(d_theta_deg=bad)


def test_the_default_is_unchanged() -> None:
    # Exposing a knob must not silently move everyone's answers.
    assert PistonSimulateInput().d_theta_deg == DEFAULT_D_THETA_DEG


# --------------------------------------------------------------------------- #
# the convergence study
# --------------------------------------------------------------------------- #
def test_the_ladder_halves_the_step_each_rung() -> None:
    # The change between rungs is only interpretable as discretisation error if
    # each rung is exactly half the last.
    for coarse, fine in zip(CONVERGENCE_LADDER, CONVERGENCE_LADDER[1:]):
        assert coarse == pytest.approx(2.0 * fine)


def test_the_study_reports_a_shrinking_change() -> None:
    report = run_piston_convergence(PistonSimulateInput())
    changes = [abs(s.power_change_percent) for s in report.steps if s.power_change_percent]
    assert len(changes) >= 4
    # Monotonically shrinking is what convergence looks like; growing would mean
    # the integration is diverging as it refines, which is a real alarm.
    assert changes == sorted(changes, reverse=True)


def test_the_march_converges_at_about_first_order() -> None:
    # The scheme is a first-order march, so halving the step should halve the
    # error. If the observed order collapses, the integration is not behaving
    # the way its own scheme claims.
    report = run_piston_convergence(PistonSimulateInput())
    assert report.observed_order is not None
    assert 0.7 < report.observed_order < 1.4


def test_the_default_step_is_converged() -> None:
    # The claim the console rests on: the number it prints by default is the
    # engine's, not the step's.
    report = run_piston_convergence(PistonSimulateInput())
    assert report.converged
    assert abs(report.finest_vs_default_percent) < 0.5


def test_a_finer_step_costs_more_time() -> None:
    report = run_piston_convergence(PistonSimulateInput())
    assert report.steps[-1].steps_per_cycle > report.steps[0].steps_per_cycle
    assert report.steps[-1].solve_ms > report.steps[0].solve_ms


def test_the_verdict_states_the_error_it_is_accepting() -> None:
    report = run_piston_convergence(PistonSimulateInput())
    assert "%" in report.verdict
    assert str(DEFAULT_D_THETA_DEG) in report.verdict


def test_the_endpoint_is_wired() -> None:
    report = piston_convergence(PistonSimulateInput())
    assert len(report.steps) == len(CONVERGENCE_LADDER)


def test_the_study_holds_for_a_harder_engine() -> None:
    # A boosted diesel at high speed is where a coarse step is most likely to
    # bite, so convergence there is the claim worth defending.
    hard = PistonSimulateInput(
        fuel="diesel",
        compression_ratio=18.0,
        rpm=4500.0,
        aspiration="turbocharged",
        intake_pressure_Pa=2.2e5,
    )
    report = run_piston_convergence(hard)
    assert report.converged, report.verdict
