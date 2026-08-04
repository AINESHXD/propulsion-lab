"""Inverse cycle solver: recovering hidden parameters from observable telemetry.

The central technique here is the **twin experiment**: run the forward solver
with a known truth, hand only its observable outputs to the inverse solver, and
check whether it finds the truth back. That is the only honest way to test an
inverse method, because on real data the answer is unknown by definition.

The second thing under test is just as important as the first: that the solver
refuses to sound confident when it has no right to be. An inverse problem will
happily return a perfect-looking fit that means nothing, and most of these tests
exist to prove that case is caught rather than served.
"""

from __future__ import annotations

import pytest

from app.engine_core.inverse import (
    Measurement,
    OBSERVABLE_KEYS,
    SOLVABLE_PARAMETERS,
    Unknown,
    observe,
    solve_inverse_cycle,
)
from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import TurbojetCycleInputs

# A rich measurement set: thrust and fuel flow plus two gas-path temperatures,
# which is roughly what a real test cell gives you.
RICH = (
    "thrust_N",
    "fuel_flow_kg_s",
    "station_3_stagnation_temperature_K",
    "station_5_stagnation_temperature_K",
)


def _telemetry(truth: TurbojetCycleInputs, keys=RICH, sigma_fraction: float | None = None):
    """Forward-run a known truth and return it as measurements."""

    result = simulate_turbojet_cycle(truth)
    out = []
    for k in keys:
        v = observe(result, k)
        out.append(Measurement(k, v, sigma=abs(v) * sigma_fraction if sigma_fraction else None))
    return out


# ------------------------------------------------------------ twin experiments

def test_a_single_hidden_efficiency_is_recovered() -> None:
    # One unknown, several measurements, everything else known exactly: the
    # solver should land on the truth.
    truth = TurbojetCycleInputs(compressor_efficiency=0.831)
    measurements = _telemetry(truth)
    result = solve_inverse_cycle(
        TurbojetCycleInputs(), measurements, [Unknown("compressor_efficiency")],
    )
    assert result.converged
    assert result.determined
    recovered = result.parameters[0]
    assert recovered.value == pytest.approx(0.831, abs=2e-3)
    assert recovered.identifiable


def test_a_degraded_pressure_ratio_is_recovered() -> None:
    # Compressor fouling shows up as lost pressure ratio; that is the classic
    # thing gas-path analysis is asked to detect.
    truth = TurbojetCycleInputs(compressor_pressure_ratio=10.4)
    result = solve_inverse_cycle(
        TurbojetCycleInputs(), _telemetry(truth), [Unknown("compressor_pressure_ratio")],
    )
    assert result.parameters[0].value == pytest.approx(10.4, rel=5e-3)


def test_the_solver_finds_the_truth_from_a_deliberately_poor_start() -> None:
    # The starting guess is far from the answer; a working solver does not care.
    truth = TurbojetCycleInputs(turbine_efficiency=0.905)
    result = solve_inverse_cycle(
        TurbojetCycleInputs(), _telemetry(truth),
        [Unknown("turbine_efficiency", initial=0.62)],
    )
    assert result.parameters[0].value == pytest.approx(0.905, abs=3e-3)


def test_residuals_close_on_a_recoverable_case() -> None:
    truth = TurbojetCycleInputs(compressor_efficiency=0.855)
    result = solve_inverse_cycle(
        TurbojetCycleInputs(), _telemetry(truth), [Unknown("compressor_efficiency")],
    )
    assert result.max_absolute_relative_error < 1e-3
    for r in result.residuals:
        assert r.modelled == pytest.approx(r.measured, rel=1e-3)


# ------------------------------------------------- refusing to oversell itself

def test_an_underdetermined_fit_is_flagged_not_served() -> None:
    # Three unknowns against two measurements: infinitely many exact fits exist,
    # so the result must say so however good the residual looks.
    truth = TurbojetCycleInputs(compressor_efficiency=0.842)
    measurements = _telemetry(truth, keys=("thrust_N", "fuel_flow_kg_s"))
    result = solve_inverse_cycle(TurbojetCycleInputs(), measurements, [
        Unknown("compressor_efficiency"),
        Unknown("turbine_efficiency"),
        Unknown("compressor_pressure_ratio"),
    ])
    assert result.determined is False
    assert "underdetermined" in result.verdict.lower()
    assert any("Underdetermined" in w for w in result.warnings)
    # And no parameter may be advertised as pinned down.
    assert all(not p.identifiable for p in result.parameters)


def test_collinear_parameters_are_reported_as_inseparable() -> None:
    # Compressor and turbine efficiency and pressure ratio act on the same few
    # observables, so even with enough measurements the split between them is
    # not recoverable. A tiny residual must not be presented as success.
    truth = TurbojetCycleInputs(compressor_efficiency=0.842, turbine_efficiency=0.873,
                                compressor_pressure_ratio=11.3)
    result = solve_inverse_cycle(TurbojetCycleInputs(), _telemetry(truth), [
        Unknown("compressor_efficiency"),
        Unknown("turbine_efficiency"),
        Unknown("compressor_pressure_ratio"),
    ])
    assert result.rms_normalised_residual < 1.0      # fits the data beautifully...
    assert result.well_conditioned is False          # ...and means nothing
    assert all(not p.identifiable for p in result.parameters)
    assert "separable" in result.verdict.lower()


def test_a_perfect_fit_does_not_produce_zero_uncertainty() -> None:
    # The trap this solver has to avoid: with noiseless twin data the residual
    # is ~0, and scaling the covariance by it would claim near-infinite
    # confidence in parameters that are not actually determined.
    truth = TurbojetCycleInputs(compressor_efficiency=0.842, turbine_efficiency=0.873)
    result = solve_inverse_cycle(TurbojetCycleInputs(), _telemetry(truth), [
        Unknown("compressor_efficiency"), Unknown("turbine_efficiency"),
    ])
    assert result.rms_normalised_residual < 1e-3
    for p in result.parameters:
        assert p.standard_error is not None
        assert p.standard_error > 1e-5, "a noiseless fit must not imply exact knowledge"


def test_error_bars_are_capped_at_the_parameter_range() -> None:
    # Beyond the allowed range the measurements add nothing over the bounds, so
    # the reported bar stops there instead of printing arithmetic noise.
    truth = TurbojetCycleInputs()
    result = solve_inverse_cycle(TurbojetCycleInputs(), _telemetry(truth), [
        Unknown("compressor_efficiency"),
        Unknown("turbine_efficiency"),
        Unknown("compressor_pressure_ratio"),
    ])
    for p in result.parameters:
        span = p.bounds[1] - p.bounds[0]
        assert p.standard_error <= span + 1e-9


def test_tighter_instrumentation_tightens_the_answer() -> None:
    # Better sensors must buy a narrower confidence band, or the uncertainty is
    # not actually propagating from the measurements.
    truth = TurbojetCycleInputs(compressor_efficiency=0.845)
    loose = solve_inverse_cycle(
        TurbojetCycleInputs(), _telemetry(truth, sigma_fraction=0.05),
        [Unknown("compressor_efficiency")],
    )
    tight = solve_inverse_cycle(
        TurbojetCycleInputs(), _telemetry(truth, sigma_fraction=0.001),
        [Unknown("compressor_efficiency")],
    )
    assert tight.parameters[0].standard_error < loose.parameters[0].standard_error


def test_inconsistent_measurements_are_called_out() -> None:
    # Thrust from one engine, fuel flow from a wildly different one: no
    # parameter set reproduces both, and the solver must say so.
    truth = TurbojetCycleInputs()
    measurements = _telemetry(truth, keys=("thrust_N", "fuel_flow_kg_s"))
    broken = [measurements[0],
              Measurement("fuel_flow_kg_s", measurements[1].value * 4.0,
                          sigma=measurements[1].value * 0.01)]
    result = solve_inverse_cycle(TurbojetCycleInputs(), broken,
                                 [Unknown("compressor_efficiency")])
    assert result.rms_normalised_residual > 3.0
    assert any("Residuals are large" in w for w in result.warnings)


# --------------------------------------------------------------- input contract

def test_unknown_observables_and_parameters_are_rejected() -> None:
    with pytest.raises(ValueError, match="not an observable"):
        Measurement("vibes", 1.0)
    with pytest.raises(ValueError, match="cannot be solved for"):
        Unknown("engine_variant")


def test_duplicates_are_rejected() -> None:
    truth = TurbojetCycleInputs()
    with pytest.raises(ValueError, match="twice"):
        solve_inverse_cycle(truth, _telemetry(truth),
                            [Unknown("compressor_efficiency")] * 2)
    m = _telemetry(truth, keys=("thrust_N",))
    with pytest.raises(ValueError, match="twice"):
        solve_inverse_cycle(truth, m * 2, [Unknown("compressor_efficiency")])


def test_empty_problems_are_rejected() -> None:
    truth = TurbojetCycleInputs()
    with pytest.raises(ValueError, match="measurement"):
        solve_inverse_cycle(truth, [], [Unknown("compressor_efficiency")])
    with pytest.raises(ValueError, match="unknown"):
        solve_inverse_cycle(truth, _telemetry(truth), [])


def test_bounds_are_honoured() -> None:
    truth = TurbojetCycleInputs(compressor_efficiency=0.95)
    result = solve_inverse_cycle(
        TurbojetCycleInputs(), _telemetry(truth),
        [Unknown("compressor_efficiency", lower=0.60, upper=0.80)],
    )
    p = result.parameters[0]
    assert 0.60 <= p.value <= 0.80
    assert p.at_bound
    assert any("bound" in w for w in result.warnings)


def test_every_advertised_parameter_can_actually_be_solved_for() -> None:
    # The catalogue the UI offers must not contain anything the solver chokes on.
    truth = TurbojetCycleInputs()
    for key in SOLVABLE_PARAMETERS:
        result = solve_inverse_cycle(truth, _telemetry(truth), [Unknown(key)])
        assert result.parameters[0].key == key
        assert result.function_evaluations > 0


def test_every_advertised_observable_can_actually_be_read() -> None:
    result = simulate_turbojet_cycle(TurbojetCycleInputs())
    for key in OBSERVABLE_KEYS:
        assert isinstance(observe(result, key), float)


def test_the_report_serialises() -> None:
    truth = TurbojetCycleInputs(compressor_efficiency=0.84)
    payload = solve_inverse_cycle(
        TurbojetCycleInputs(), _telemetry(truth), [Unknown("compressor_efficiency")],
    ).to_dict()
    for key in ("converged", "determined", "well_conditioned", "parameters",
                "residuals", "rms_normalised_residual", "jacobian_condition_number",
                "verdict", "warnings"):
        assert key in payload
    assert payload["parameters"][0]["key"] == "compressor_efficiency"
