"""NSGA-II multi-objective design optimisation (Month-5 feature).

A self-contained implementation of the Non-dominated Sorting Genetic Algorithm
II (Deb et al., 2002) in NumPy — no third-party optimiser dependency. It drives
the turbojet cycle as a black box to trace the Pareto front of competing design
objectives (e.g. minimise TSFC while maximising specific thrust) subject to
engineering constraints (material temperature limit, fuel-air band).

The algorithm:

1. **Fast non-dominated sort** ranks the population into Pareto fronts using
   *constraint domination* (Deb's feasibility rules): a feasible solution beats
   any infeasible one; between two infeasible solutions the smaller total
   constraint violation wins; between two feasible solutions ordinary Pareto
   dominance applies.
2. **Crowding distance** preserves diversity along each front (boundary points
   are kept; interior points are ranked by the size of the cuboid spanning their
   neighbours).
3. **Binary tournament** selection (by rank, then crowding), **simulated binary
   crossover (SBX)** and **polynomial mutation** generate offspring.
4. **(μ + λ) environmental selection** keeps the best ``pop_size`` of the
   combined parent + offspring set each generation (elitist).

Everything is deterministic for a fixed ``seed`` so results are reproducible and
testable.

References
----------
- K. Deb, A. Pratap, S. Agarwal, T. Meyarivan, "A Fast and Elitist
  Multiobjective Genetic Algorithm: NSGA-II", IEEE Trans. Evol. Comput. 6(2),
  2002.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Protocol

import numpy as np

from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import CycleCalculationError, TurbojetCycleInputs


# ---------------------------------------------------------------------------
# Problem interface
# ---------------------------------------------------------------------------


class Problem(Protocol):
    """A multi-objective problem the optimiser can drive.

    ``xl`` / ``xu`` are the per-variable lower / upper bounds (shape ``(n_var,)``).
    ``evaluate`` maps a population matrix ``X`` of shape ``(n, n_var)`` to a pair
    ``(F, G)``: objectives ``F`` of shape ``(n, n_obj)`` (all *minimised*) and
    constraints ``G`` of shape ``(n, n_con)`` expressed as ``g(x) <= 0``
    (positive entries are violations). ``G`` may have zero columns.
    """

    xl: np.ndarray
    xu: np.ndarray

    def evaluate(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]: ...


# ---------------------------------------------------------------------------
# Core NSGA-II operators
# ---------------------------------------------------------------------------


def constraint_violation(G: np.ndarray) -> np.ndarray:
    """Total constraint violation per row (sum of positive parts of g <= 0)."""

    if G.size == 0:
        return np.zeros(G.shape[0])
    return np.sum(np.maximum(0.0, G), axis=1)


def _dominates(f1: np.ndarray, cv1: float, f2: np.ndarray, cv2: float) -> bool:
    """Constraint-domination (Deb): does (f1, cv1) dominate (f2, cv2)?"""

    feas1, feas2 = cv1 <= 0.0, cv2 <= 0.0
    if feas1 and not feas2:
        return True
    if feas2 and not feas1:
        return False
    if not feas1 and not feas2:
        return cv1 < cv2
    # Both feasible — ordinary Pareto dominance.
    return bool(np.all(f1 <= f2) and np.any(f1 < f2))


def fast_non_dominated_sort(F: np.ndarray, CV: np.ndarray) -> list[np.ndarray]:
    """Sort rows into Pareto fronts (front 0 is non-dominated)."""

    n = F.shape[0]
    dominated_by: list[list[int]] = [[] for _ in range(n)]
    domination_count = np.zeros(n, dtype=int)
    fronts: list[list[int]] = [[]]

    for p in range(n):
        for q in range(p + 1, n):
            if _dominates(F[p], CV[p], F[q], CV[q]):
                dominated_by[p].append(q)
                domination_count[q] += 1
            elif _dominates(F[q], CV[q], F[p], CV[p]):
                dominated_by[q].append(p)
                domination_count[p] += 1
        if domination_count[p] == 0:
            fronts[0].append(p)

    i = 0
    while fronts[i]:
        nxt: list[int] = []
        for p in fronts[i]:
            for q in dominated_by[p]:
                domination_count[q] -= 1
                if domination_count[q] == 0:
                    nxt.append(q)
        i += 1
        fronts.append(nxt)
    fronts.pop()  # last appended front is empty
    return [np.asarray(f, dtype=int) for f in fronts]


def crowding_distance(F: np.ndarray, front: np.ndarray) -> np.ndarray:
    """Crowding distance for the rows indexed by ``front`` (boundaries -> inf)."""

    m = len(front)
    if m == 0:
        return np.zeros(0)
    if m <= 2:
        return np.full(m, np.inf)

    dist = np.zeros(m)
    sub = F[front]
    for k in range(F.shape[1]):
        order = np.argsort(sub[:, k], kind="mergesort")
        dist[order[0]] = dist[order[-1]] = np.inf
        fmin, fmax = sub[order[0], k], sub[order[-1], k]
        span = fmax - fmin
        if span <= 0.0:
            continue
        for j in range(1, m - 1):
            dist[order[j]] += (sub[order[j + 1], k] - sub[order[j - 1], k]) / span
    return dist


def _rank_and_crowding(
    F: np.ndarray, CV: np.ndarray
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
    """Per-row Pareto rank and crowding distance (lower rank = better)."""

    fronts = fast_non_dominated_sort(F, CV)
    rank = np.zeros(F.shape[0], dtype=int)
    crowd = np.zeros(F.shape[0])
    for r, front in enumerate(fronts):
        rank[front] = r
        crowd[front] = crowding_distance(F, front)
    return rank, crowd, fronts


def _tournament(rank: np.ndarray, crowd: np.ndarray, rng: np.random.Generator) -> int:
    """Binary tournament: lower rank wins; ties broken by larger crowding."""

    a, b = rng.integers(0, len(rank), size=2)
    if rank[a] < rank[b]:
        return int(a)
    if rank[b] < rank[a]:
        return int(b)
    return int(a if crowd[a] >= crowd[b] else b)


def _sbx(
    p1: np.ndarray, p2: np.ndarray, xl: np.ndarray, xu: np.ndarray,
    rng: np.random.Generator, eta: float = 15.0, prob: float = 0.9,
) -> tuple[np.ndarray, np.ndarray]:
    """Simulated binary crossover for one pair of parents."""

    c1, c2 = p1.copy(), p2.copy()
    if rng.random() > prob:
        return c1, c2
    for i in range(len(p1)):
        if rng.random() > 0.5 or abs(p1[i] - p2[i]) < 1e-12:
            continue
        x1, x2 = min(p1[i], p2[i]), max(p1[i], p2[i])
        u = rng.random()
        beta = 1.0 + 2.0 * (x1 - xl[i]) / (x2 - x1)
        alpha = 2.0 - beta ** -(eta + 1.0)
        betaq = (u * alpha) ** (1.0 / (eta + 1.0)) if u <= 1.0 / alpha \
            else (1.0 / (2.0 - u * alpha)) ** (1.0 / (eta + 1.0))
        c1[i] = 0.5 * ((x1 + x2) - betaq * (x2 - x1))
        beta = 1.0 + 2.0 * (xu[i] - x2) / (x2 - x1)
        alpha = 2.0 - beta ** -(eta + 1.0)
        betaq = (u * alpha) ** (1.0 / (eta + 1.0)) if u <= 1.0 / alpha \
            else (1.0 / (2.0 - u * alpha)) ** (1.0 / (eta + 1.0))
        c2[i] = 0.5 * ((x1 + x2) + betaq * (x2 - x1))
    return np.clip(c1, xl, xu), np.clip(c2, xl, xu)


def _polynomial_mutation(
    x: np.ndarray, xl: np.ndarray, xu: np.ndarray,
    rng: np.random.Generator, eta: float = 20.0, prob: float | None = None,
) -> np.ndarray:
    """Polynomial mutation in place-safe copy."""

    y = x.copy()
    p = prob if prob is not None else 1.0 / len(x)
    for i in range(len(x)):
        if rng.random() > p or xu[i] <= xl[i]:
            continue
        delta1 = (y[i] - xl[i]) / (xu[i] - xl[i])
        delta2 = (xu[i] - y[i]) / (xu[i] - xl[i])
        u = rng.random()
        mut_pow = 1.0 / (eta + 1.0)
        if u < 0.5:
            xy = 1.0 - delta1
            val = 2.0 * u + (1.0 - 2.0 * u) * xy ** (eta + 1.0)
            deltaq = val ** mut_pow - 1.0
        else:
            xy = 1.0 - delta2
            val = 2.0 * (1.0 - u) + 2.0 * (u - 0.5) * xy ** (eta + 1.0)
            deltaq = 1.0 - val ** mut_pow
        y[i] = np.clip(y[i] + deltaq * (xu[i] - xl[i]), xl[i], xu[i])
    return y


@dataclass
class OptimizationResult:
    """Outcome of an NSGA-II run."""

    X: np.ndarray                 # decision variables of the final population
    F: np.ndarray                 # objective values (minimised)
    G: np.ndarray                 # constraint values (g <= 0)
    pareto_indices: np.ndarray    # rows of the feasible non-dominated front
    n_generations: int
    n_evaluations: int
    feasible_fraction: float
    hypervolume_proxy: float | None = None


def nsga2(
    problem: Problem,
    pop_size: int = 40,
    n_gen: int = 40,
    seed: int | None = 0,
    sbx_eta: float = 15.0,
    mutation_eta: float = 20.0,
) -> OptimizationResult:
    """Run NSGA-II on ``problem`` and return the final population + Pareto front."""

    rng = np.random.default_rng(seed)
    xl, xu = np.asarray(problem.xl, float), np.asarray(problem.xu, float)
    n_var = len(xl)
    if pop_size % 2 != 0:
        pop_size += 1  # offspring are produced in pairs

    X = xl + rng.random((pop_size, n_var)) * (xu - xl)
    F, G = problem.evaluate(X)
    CV = constraint_violation(G)
    n_eval = pop_size

    for _ in range(n_gen):
        rank, crowd, _ = _rank_and_crowding(F, CV)
        # --- Offspring via tournament + SBX + polynomial mutation ----------
        children = np.empty((pop_size, n_var))
        for k in range(0, pop_size, 2):
            i, j = _tournament(rank, crowd, rng), _tournament(rank, crowd, rng)
            c1, c2 = _sbx(X[i], X[j], xl, xu, rng, eta=sbx_eta)
            children[k] = _polynomial_mutation(c1, xl, xu, rng, eta=mutation_eta)
            children[k + 1] = _polynomial_mutation(c2, xl, xu, rng, eta=mutation_eta)
        Fc, Gc = problem.evaluate(children)
        CVc = constraint_violation(Gc)
        n_eval += pop_size

        # --- (μ + λ) elitist environmental selection -----------------------
        allX = np.vstack([X, children])
        allF = np.vstack([F, Fc])
        allG = np.vstack([G, Gc]) if G.size or Gc.size else np.empty((allX.shape[0], 0))
        allCV = np.concatenate([CV, CVc])
        fronts = fast_non_dominated_sort(allF, allCV)

        chosen: list[int] = []
        for front in fronts:
            if len(chosen) + len(front) <= pop_size:
                chosen.extend(front.tolist())
            else:
                d = crowding_distance(allF, front)
                order = np.argsort(-d, kind="mergesort")
                need = pop_size - len(chosen)
                chosen.extend(front[order[:need]].tolist())
                break
        sel = np.asarray(chosen, dtype=int)
        X, F, G, CV = allX[sel], allF[sel], allG[sel], allCV[sel]

    # Final feasible non-dominated front.
    fronts = fast_non_dominated_sort(F, CV)
    feasible = CV <= 0.0
    pareto = np.asarray([i for i in fronts[0] if feasible[i]], dtype=int)
    if pareto.size == 0:                     # nothing feasible — report front 0
        pareto = fronts[0]

    return OptimizationResult(
        X=X, F=F, G=G, pareto_indices=pareto,
        n_generations=n_gen, n_evaluations=n_eval,
        feasible_fraction=float(np.mean(feasible)),
    )


# ---------------------------------------------------------------------------
# Turbojet design problem
# ---------------------------------------------------------------------------

# Objectives the optimiser can target. Each maps a cycle-result dict to a value
# that is *minimised* (specific thrust is negated so it is maximised).
_OBJECTIVES: dict[str, tuple[str, Callable[[dict[str, Any]], float]]] = {
    "tsfc": ("Minimise TSFC [kg/kN·h]", lambda r: float(r["TSFC_kg_per_kN_hr"])),
    "specific_thrust": (
        "Maximise specific thrust [N·s/kg]",
        lambda r: -float(r["specific_thrust_N_per_kg_s"]),
    ),
    "compressor_exit_temperature": (
        "Minimise compressor-exit Tt3 [K]",
        lambda r: float(r["station_table"][3]["stagnation_temperature_K"]),
    ),
}

# Number of inequality constraints returned by ``_evaluate_one`` (Tt3 cap, lean
# floor, rich limit). Feasible and infeasible rows must both return this many.
_N_CONSTRAINTS = 3


@dataclass
class TurbojetDesignProblem:
    """Design-variable optimisation of the turbojet cycle.

    Decision variables are the compressor pressure ratio and the turbine-inlet
    temperature; the flight condition and all other settings come from ``base``.
    Objectives default to (minimise TSFC, maximise specific thrust) — the classic
    fuel-economy vs thrust-density trade. Constraints cap the compressor-exit
    (material) temperature and hold the fuel-air ratio inside a sensible band.
    """

    base: TurbojetCycleInputs
    pr_bounds: tuple[float, float] = (6.0, 40.0)
    tit_bounds: tuple[float, float] = (1100.0, 1800.0)
    objectives: tuple[str, ...] = ("tsfc", "specific_thrust")
    tt3_max_K: float = 950.0
    far_min: float = 0.005
    far_max: float = 0.05
    objective_labels: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for name in self.objectives:
            if name not in _OBJECTIVES:
                raise ValueError(f"Unknown objective: {name!r}")
        self.objective_labels = [_OBJECTIVES[n][0] for n in self.objectives]

    @property
    def xl(self) -> np.ndarray:
        return np.array([self.pr_bounds[0], self.tit_bounds[0]])

    @property
    def xu(self) -> np.ndarray:
        return np.array([self.pr_bounds[1], self.tit_bounds[1]])

    def _evaluate_one(self, pr: float, tit: float) -> tuple[list[float], list[float]]:
        inputs = replace(self.base, compressor_pressure_ratio=pr,
                         turbine_inlet_temperature_K=tit)
        try:
            r = simulate_turbojet_cycle(inputs)
        except CycleCalculationError:
            # Infeasible cycle: large objective values + large violation so the
            # constraint-domination keeps it out of the Pareto front. The
            # violation vector MUST be the same length as the feasible branch
            # below (one entry per constraint), otherwise mixing feasible and
            # infeasible rows produces a ragged array when they are stacked.
            big = [1.0e6] * len(self.objectives)
            return big, [1.0e3] * _N_CONSTRAINTS
        F = [_OBJECTIVES[name][1](r) for name in self.objectives]
        far = float(r.get("core_fuel_air_ratio") or r["fuel_air_ratio"])
        tt3 = float(r["station_table"][3]["stagnation_temperature_K"])
        G = [
            tt3 - self.tt3_max_K,            # material temperature limit
            self.far_min - far,              # lean blow-out floor
            far - self.far_max,              # rich limit
        ]
        assert len(G) == _N_CONSTRAINTS
        return F, [float(g) for g in G]

    def evaluate(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        F_rows, G_rows = [], []
        for row in X:
            F, G = self._evaluate_one(float(row[0]), float(row[1]))
            F_rows.append(F)
            G_rows.append(G)
        return np.asarray(F_rows, float), np.asarray(G_rows, float)
