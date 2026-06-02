"""Tests for the DASLAB ML Suite turbojet surrogate (Month-5 feature).

Covers the hand-written MLP (forward/backprop learns a known function),
standardisation, JSON round-trip parity (the browser runs the same forward
pass), and — most importantly — that the committed model agrees with the exact
physics solver on a held-out sample.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from app.engine_core.surrogate import (
    SURROGATE_INPUTS,
    SURROGATE_OUTPUTS,
    MLPRegressor,
    Standardizer,
    build_training_set,
    default_artifact_path,
    mean_abs_pct_error,
    r2_score,
    train_turbojet_surrogate,
)


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


def test_standardizer_round_trip() -> None:
    X = np.array([[1.0, 100.0], [3.0, 300.0], [5.0, 500.0]])
    s = Standardizer.fit(X)
    assert np.allclose(s.inverse(s.transform(X)), X)
    assert np.allclose(s.transform(X).mean(axis=0), 0.0, atol=1e-12)


def test_r2_and_mape_on_known_arrays() -> None:
    y = np.array([[1.0], [2.0], [3.0], [4.0]])
    assert r2_score(y, y)[0] == pytest.approx(1.0)
    # Predicting the mean gives R^2 = 0.
    assert r2_score(y, np.full_like(y, y.mean()))[0] == pytest.approx(0.0, abs=1e-9)
    assert mean_abs_pct_error(y, y)[0] == pytest.approx(0.0)


def test_mlp_learns_a_nonlinear_function() -> None:
    rng = np.random.default_rng(0)
    X = rng.uniform(-1, 1, size=(400, 2))
    Y = (np.sin(3 * X[:, 0]) * X[:, 1]).reshape(-1, 1)   # smooth nonlinear target
    net = MLPRegressor([2, 24, 24, 1], seed=0)
    net.train(X, Y, epochs=500, lr=0.01, seed=0)
    pred = net.predict(X)
    assert r2_score(Y, pred)[0] > 0.95


def test_json_round_trip_is_bit_for_bit() -> None:
    rng = np.random.default_rng(1)
    X = rng.uniform(0, 1, size=(120, 2))
    Y = np.column_stack([X[:, 0] + X[:, 1], np.exp(X[:, 0])])
    net = MLPRegressor([2, 16, 2], seed=0)
    net.train(X, Y, epochs=200, lr=0.01, output_transforms=["none", "log"], seed=0)
    clone = MLPRegressor.from_dict(json.loads(json.dumps(net.to_dict())))
    Xq = rng.uniform(0, 1, size=(10, 2))
    assert np.max(np.abs(net.predict(Xq) - clone.predict(Xq))) == 0.0
    assert clone.output_transforms == ["none", "log"]


# ---------------------------------------------------------------------------
# End-to-end training (small + fast)
# ---------------------------------------------------------------------------


def test_small_training_run_is_accurate() -> None:
    net, rep = train_turbojet_surrogate(
        n_samples=1500, hidden=(32, 32), epochs=300, lr=0.01, seed=0
    )
    # Even a quick run should track the smooth cycle well.
    assert rep.r2["specific_thrust_N_per_kg_s"] > 0.95
    assert rep.r2["TSFC_kg_per_kN_hr"] > 0.90
    assert rep.r2["compressor_exit_temperature_K"] > 0.95


def test_training_set_respects_input_ranges() -> None:
    X, Y = build_training_set(n_samples=200, seed=3)
    assert X.shape[1] == len(SURROGATE_INPUTS)
    assert Y.shape[1] == len(SURROGATE_OUTPUTS)
    for j, (_, lo, hi) in enumerate(SURROGATE_INPUTS):
        assert X[:, j].min() >= lo - 1e-6 and X[:, j].max() <= hi + 1e-6


# ---------------------------------------------------------------------------
# Committed artifact: structure + agreement with the exact solver
# ---------------------------------------------------------------------------


def _artifact() -> dict:
    return json.loads(default_artifact_path().read_text(encoding="utf-8"))


def test_committed_artifact_exists_and_is_well_formed() -> None:
    d = _artifact()
    assert d["format"] == "daslab-mlp-1"
    assert d["inputs"] == [name for name, _, _ in SURROGATE_INPUTS]
    assert d["outputs"] == list(SURROGATE_OUTPUTS)
    assert d["output_transforms"][1] == "log"          # TSFC learned in log space
    # Embedded honest accuracy metrics are strong on this smooth function.
    for name in SURROGATE_OUTPUTS:
        assert d["metrics"][name]["r2"] > 0.99


def test_committed_artifact_matches_physics_solver() -> None:
    from dataclasses import replace

    from app.engine_core.surrogate import _base_inputs
    from app.engine_core.turbojet import simulate_turbojet_cycle

    net = MLPRegressor.from_dict(_artifact())
    rng = np.random.default_rng(123)
    base = _base_inputs()
    X, truth = [], []
    while len(X) < 60:
        pr = rng.uniform(8, 38); tit = rng.uniform(1150, 1750)
        mach = rng.uniform(0, 1.6); alt = rng.uniform(0, 13000)
        try:
            r = simulate_turbojet_cycle(replace(
                base, compressor_pressure_ratio=pr, turbine_inlet_temperature_K=tit,
                mach=mach, altitude_m=alt))
        except Exception:
            continue
        spec = float(r["specific_thrust_N_per_kg_s"])
        if spec <= 60.0:
            continue
        X.append([pr, tit, mach, alt])
        truth.append([spec, float(r["TSFC_kg_per_kN_hr"]),
                      float(r["station_table"][3]["stagnation_temperature_K"])])
    X = np.asarray(X); truth = np.asarray(truth)
    pred = net.predict(X)[:, [0, 1, 3]]   # spec thrust, TSFC, Tt3
    mape = mean_abs_pct_error(truth, pred)
    # Surrogate tracks the solver to within a few percent on held-out designs.
    assert mape[0] < 4.0    # specific thrust
    assert mape[1] < 4.0    # TSFC
    assert mape[2] < 3.0    # Tt3
