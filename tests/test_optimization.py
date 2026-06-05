"""Tests for the self-contained NSGA-II optimiser (Month-5 feature).

The operators are checked on hand examples and a problem with a known Pareto
set; the turbojet design optimisation is checked for a non-empty, feasible,
correctly-traded Pareto front that is reproducible under a fixed seed.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.engine_core.optimization import (
    TurbojetDesignProblem,
    constraint_violation,
    crowding_distance,
    fast_non_dominated_sort,
    nsga2,
)
from app.schemas import TurbojetInput


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------


def test_fast_non_dominated_sort_simple() -> None:
    # A dominates B and C; B and C are mutually non-dominated; D is dominated by all.
    F = np.array([[1.0, 1.0],   # A
                  [2.0, 1.0],   # B
                  [1.0, 2.0],   # C
                  [3.0, 3.0]])  # D
    CV = np.zeros(4)
    fronts = fast_non_dominated_sort(F, CV)
    assert set(fronts[0].tolist()) == {0}
    assert set(fronts[1].tolist()) == {1, 2}
    assert set(fronts[2].tolist()) == {3}


def test_crowding_distance_boundaries_are_infinite() -> None:
    F = np.array([[0.0, 2.0], [1.0, 1.0], [2.0, 0.0]])
    d = crowding_distance(F, np.array([0, 1, 2]))
    assert np.isinf(d[0]) and np.isinf(d[2])     # extremes preserved
    assert np.isfinite(d[1])                      # interior point finite


def test_constraint_domination_prefers_feasible() -> None:
    # Infeasible point with a "better" objective must NOT make front 0 alone.
    F = np.array([[0.0, 0.0],   # infeasible but low objectives
                  [5.0, 5.0]])  # feasible, worse objectives
    G = np.array([[10.0], [-1.0]])     # row0 violates, row1 feasible
    CV = constraint_violation(G)
    assert CV[0] > 0 and CV[1] == 0
    fronts = fast_non_dominated_sort(F, CV)
    assert fronts[0].tolist() == [1]   # the feasible solution dominates


def test_constraint_violation_sums_positive_parts() -> None:
    G = np.array([[-1.0, 2.0, 0.5], [-3.0, -1.0, 0.0]])
    cv = constraint_violation(G)
    assert cv[0] == pytest.approx(2.5)
    assert cv[1] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Convergence on a problem with a known Pareto set
# ---------------------------------------------------------------------------


class _Schaffer:
    """min f1 = sum x^2, f2 = sum (x-2)^2 over [-3, 3]^2. Pareto set: x in [0, 2]."""

    xl = np.array([-3.0, -3.0])
    xu = np.array([3.0, 3.0])

    def evaluate(self, X: np.ndarray):
        f1 = np.sum(X**2, axis=1)
        f2 = np.sum((X - 2.0) ** 2, axis=1)
        return np.column_stack([f1, f2]), np.empty((X.shape[0], 0))


def test_nsga2_converges_to_known_pareto_set() -> None:
    res = nsga2(_Schaffer(), pop_size=40, n_gen=40, seed=1)
    pareto = res.X[res.pareto_indices]
    # Every Pareto-optimal variable should lie in [0, 2] (small numerical slack).
    assert pareto.min() >= -0.05
    assert pareto.max() <= 2.05
    # The front should span a good chunk of that range, not collapse to a point.
    assert pareto[:, 0].max() - pareto[:, 0].min() > 1.0


def test_nsga2_is_reproducible_with_seed() -> None:
    a = nsga2(_Schaffer(), pop_size=20, n_gen=15, seed=7)
    b = nsga2(_Schaffer(), pop_size=20, n_gen=15, seed=7)
    assert np.allclose(a.F, b.F)


# ---------------------------------------------------------------------------
# Turbojet design problem
# ---------------------------------------------------------------------------


def _base():
    return TurbojetInput(altitude_m=0.0, mach=0.0, mass_flow_air_kg_s=50.0).to_cycle_inputs()


def test_turbojet_pareto_front_is_feasible_and_traded() -> None:
    prob = TurbojetDesignProblem(base=_base(), tt3_max_K=950.0)
    res = nsga2(prob, pop_size=40, n_gen=30, seed=0)
    assert res.pareto_indices.size >= 5
    assert res.feasible_fraction == pytest.approx(1.0, abs=0.0) or res.feasible_fraction > 0.5

    F = res.F[res.pareto_indices]
    tsfc = F[:, 0]
    spec_thrust = -F[:, 1]               # objective stores negated specific thrust
    order = np.argsort(tsfc)
    # Classic trade: as TSFC rises along the front, specific thrust rises too.
    assert np.all(np.diff(spec_thrust[order]) >= -1.0)
    # A real spread, not a single design.
    assert tsfc.max() - tsfc.min() > 5.0


def test_turbojet_constraints_are_respected() -> None:
    prob = TurbojetDesignProblem(base=_base(), tt3_max_K=900.0, far_max=0.05)
    res = nsga2(prob, pop_size=40, n_gen=30, seed=2)
    # Every reported (feasible) Pareto design honours the constraints.
    for idx in res.pareto_indices:
        pr, tit = res.X[idx]
        F, G = prob._evaluate_one(float(pr), float(tit))
        assert all(g <= 1e-6 for g in G)


def test_three_objective_problem_runs() -> None:
    prob = TurbojetDesignProblem(
        base=_base(),
        objectives=("tsfc", "specific_thrust", "compressor_exit_temperature"),
    )
    res = nsga2(prob, pop_size=24, n_gen=12, seed=0)
    assert res.F.shape[1] == 3
    assert res.pareto_indices.size >= 3


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


def test_optimize_endpoint_returns_sorted_front() -> None:
    from app.main import optimize_turbojet
    from app.schemas import TurbojetOptimizeInput

    out = optimize_turbojet(TurbojetOptimizeInput(
        design=TurbojetInput(altitude_m=0.0, mach=0.0, mass_flow_air_kg_s=50.0),
        population_size=24, generations=15, seed=0,
    ))
    assert len(out.pareto_front) >= 4
    assert out.evaluations == 24 * 16   # pop * (gen + 1)
    assert len(out.objective_labels) == 2
    tsfc = [p.objective_values[0] for p in out.pareto_front]
    assert tsfc == sorted(tsfc)         # front sorted by first objective
    for p in out.pareto_front:
        assert p.compressor_exit_temperature_K <= 950.0 + 1e-6


# ---------------------------------------------------------------------------
# Regression: mixed feasible / infeasible populations must not crash
# ---------------------------------------------------------------------------


def _mixed_problem() -> TurbojetDesignProblem:
    # Wide bounds so the population contains both feasible designs and ones the
    # cycle solver rejects (high pressure ratio + low turbine temperature drives
    # the compressor exit above the turbine inlet, so combustion is impossible).
    return TurbojetDesignProblem(
        base=TurbojetInput().to_cycle_inputs(),
        pr_bounds=(5.0, 40.0),
        tit_bounds=(600.0, 2400.0),
        objectives=("tsfc", "specific_thrust"),
        tt3_max_K=950.0,
        far_min=0.005,
        far_max=0.05,
    )


def test_evaluate_returns_uniform_constraint_shape() -> None:
    prob = _mixed_problem()
    X = np.array([[12.0, 1400.0],   # feasible
                  [40.0, 600.0]])    # infeasible (Tt3 > Tt4)
    F, G = prob.evaluate(X)
    assert F.shape == (2, 2)
    # Both rows must carry the same number of constraints (the original bug
    # returned 1 for infeasible vs 3 for feasible -> ragged array -> 500).
    assert G.shape == (2, 3)


def test_nsga2_runs_with_infeasible_members_in_population() -> None:
    prob = _mixed_problem()
    result = nsga2(prob, pop_size=24, n_gen=4, seed=0)  # must not raise
    assert result.F.shape[1] == 2
    assert result.X.shape[1] == 2
    assert 0.0 <= result.feasible_fraction <= 1.0


# ---------------------------------------------------------------------------
# Turbofan design optimisation (NSGA-II over bypass ratio + fan PR)
# ---------------------------------------------------------------------------

from app.engine_core.optimization import TurbofanDesignProblem  # noqa: E402
from app.engine_core.turbofan import TurbofanCycleInputs  # noqa: E402


def test_turbofan_optimise_traces_a_feasible_front() -> None:
    prob = TurbofanDesignProblem(base=TurbofanCycleInputs())
    res = nsga2(prob, pop_size=24, n_gen=8, seed=0)
    assert len(res.pareto_indices) > 0
    assert res.F.shape[1] == 2
    assert res.X.shape[1] == 2
    # decision variables stay within the bypass / fan-PR bounds
    assert prob.bpr_bounds[0] <= res.X[:, 0].min() and res.X[:, 0].max() <= prob.bpr_bounds[1]
    assert prob.fpr_bounds[0] <= res.X[:, 1].min() and res.X[:, 1].max() <= prob.fpr_bounds[1]


def test_turbofan_evaluate_uniform_constraint_shape() -> None:
    prob = TurbofanDesignProblem(
        base=TurbofanCycleInputs(), bpr_bounds=(1.0, 14.0), fpr_bounds=(1.1, 2.6),
        tt3_max_K=820.0, thrust_min_kN=35.0,
    )
    import numpy as np
    X = np.array([[5.0, 1.6], [14.0, 2.6]])
    F, G = prob.evaluate(X)
    assert F.shape == (2, 2)
    assert G.shape == (2, 2)  # Tt3 cap + thrust floor, uniform for feasible/infeasible
