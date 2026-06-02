"""DASLAB ML Suite — a from-scratch neural-net surrogate of the turbojet cycle.

The physics solver is fast and exact but still a function call per evaluation.
This module trains a small multilayer perceptron (MLP) to *approximate* the
cycle so performance can be predicted instantly — in microseconds, in pure
JavaScript in the browser, with no server round-trip — and so the NSGA-II loop
can evaluate thousands of candidate designs cheaply.

Everything here is hand-written NumPy: forward pass, backpropagation, and the
Adam optimiser. No third-party ML dependency. The trained network serialises to
plain JSON (weights + per-feature standardisation) so the identical forward pass
runs in the browser.

Honesty note
------------
The cycle is a smooth, deterministic, noise-free function, which is the *easy*
case for a neural network — high accuracy is expected, not impressive in itself.
What this demonstrates is the full ML workflow done correctly: space-filling
sampling, standardisation, a held-out test split, and reported R² / MAE per
output. Predictions are only trustworthy inside the sampled box and away from
infeasible corners; outside it the surrogate extrapolates and should not be
trusted. The exact solver remains the source of truth.

Input / output contract (shared with the browser)
--------------------------------------------------
Inputs  (4): compressor pressure ratio, turbine-inlet temperature [K],
             flight Mach, altitude [m].
Outputs (4): specific thrust [N·s/kg], TSFC [kg/kN·h], overall efficiency,
             compressor-exit (Tt3) temperature [K].

Specific (mass-flow-independent) outputs are predicted so the network generalises
across engine size; absolute thrust is just specific thrust × air mass flow.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import CycleCalculationError, TurbojetCycleInputs


# ---------------------------------------------------------------------------
# Input / output specification (kept in lockstep with the JS forward pass)
# ---------------------------------------------------------------------------

# (name, low, high) for each design / flight input.
SURROGATE_INPUTS: tuple[tuple[str, float, float], ...] = (
    ("compressor_pressure_ratio", 6.0, 40.0),
    ("turbine_inlet_temperature_K", 1100.0, 1800.0),
    ("mach", 0.0, 1.8),
    ("altitude_m", 0.0, 14000.0),
)

SURROGATE_OUTPUTS: tuple[str, ...] = (
    "specific_thrust_N_per_kg_s",
    "TSFC_kg_per_kN_hr",
    "overall_efficiency_estimate",
    "compressor_exit_temperature_K",
)

SURROGATE_OUTPUT_LABELS: tuple[str, ...] = (
    "Specific thrust [N·s/kg]",
    "TSFC [kg/kN·h]",
    "Overall efficiency",
    "Compressor-exit Tt3 [K]",
)

# Per-output target transform applied before standardisation. TSFC is positive
# and heavy-tailed (it blows up toward zero-thrust corners), so it is learned in
# log space and exponentiated back — standard practice for skewed targets.
SURROGATE_OUTPUT_TRANSFORMS: tuple[str, ...] = ("none", "log", "none", "none")


# ---------------------------------------------------------------------------
# Standardisation
# ---------------------------------------------------------------------------


@dataclass
class Standardizer:
    """Per-feature z-score standardiser ``(x - mean) / std``."""

    mean: np.ndarray
    std: np.ndarray

    @classmethod
    def fit(cls, X: np.ndarray) -> "Standardizer":
        mean = X.mean(axis=0)
        std = X.std(axis=0)
        std[std < 1e-9] = 1.0
        return cls(mean=mean, std=std)

    def transform(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mean) / self.std

    def inverse(self, Z: np.ndarray) -> np.ndarray:
        return Z * self.std + self.mean


# ---------------------------------------------------------------------------
# MLP with hand-written backprop + Adam
# ---------------------------------------------------------------------------


class MLPRegressor:
    """A small fully-connected network with tanh hidden layers, linear output.

    Trains on standardised inputs and targets so the optimiser sees well-scaled
    gradients; the public :meth:`predict` works in engineering units.
    """

    def __init__(self, layer_sizes: list[int], seed: int = 0) -> None:
        self.layer_sizes = list(layer_sizes)
        rng = np.random.default_rng(seed)
        self.weights: list[np.ndarray] = []
        self.biases: list[np.ndarray] = []
        for nin, nout in zip(layer_sizes[:-1], layer_sizes[1:]):
            # Glorot/Xavier init suits tanh activations.
            limit = np.sqrt(6.0 / (nin + nout))
            self.weights.append(rng.uniform(-limit, limit, size=(nin, nout)))
            self.biases.append(np.zeros(nout))
        self.x_scaler: Standardizer | None = None
        self.y_scaler: Standardizer | None = None
        self.output_transforms: list[str] = ["none"] * layer_sizes[-1]

    # ---- forward ---------------------------------------------------------
    def _forward_std(self, Xs: np.ndarray) -> tuple[np.ndarray, list[np.ndarray], list[np.ndarray]]:
        """Forward pass on standardised inputs; returns output + caches."""

        a = Xs
        pre_activations: list[np.ndarray] = []
        activations: list[np.ndarray] = [a]
        n_layers = len(self.weights)
        for i, (W, b) in enumerate(zip(self.weights, self.biases)):
            z = a @ W + b
            pre_activations.append(z)
            a = z if i == n_layers - 1 else np.tanh(z)   # linear output layer
            activations.append(a)
        return a, pre_activations, activations

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict outputs in engineering units for raw inputs ``X``."""

        if self.x_scaler is None or self.y_scaler is None:
            raise RuntimeError("Model is not trained.")
        X = np.atleast_2d(np.asarray(X, float))
        ys, _, _ = self._forward_std(self.x_scaler.transform(X))
        out = self.y_scaler.inverse(ys)
        for j, tf in enumerate(self.output_transforms):
            if tf == "log":
                out[:, j] = np.exp(out[:, j])
        return out

    # ---- training --------------------------------------------------------
    def train(
        self,
        X: np.ndarray,
        Y: np.ndarray,
        *,
        epochs: int = 4000,
        lr: float = 0.01,
        batch_size: int | None = 256,
        output_transforms: list[str] | None = None,
        seed: int = 0,
        verbose: bool = False,
    ) -> list[float]:
        """Fit the network with Adam on standardised data. Returns the loss curve."""

        if output_transforms is not None:
            self.output_transforms = list(output_transforms)
        # Apply per-output target transform (e.g. log) before standardising.
        Yt = np.asarray(Y, float).copy()
        for j, tf in enumerate(self.output_transforms):
            if tf == "log":
                Yt[:, j] = np.log(np.maximum(Yt[:, j], 1e-9))

        self.x_scaler = Standardizer.fit(X)
        self.y_scaler = Standardizer.fit(Yt)
        Xs = self.x_scaler.transform(X)
        Ys = self.y_scaler.transform(Yt)
        n = Xs.shape[0]
        rng = np.random.default_rng(seed)
        bs = batch_size or n

        # Adam state.
        mW = [np.zeros_like(W) for W in self.weights]
        vW = [np.zeros_like(W) for W in self.weights]
        mB = [np.zeros_like(b) for b in self.biases]
        vB = [np.zeros_like(b) for b in self.biases]
        b1, b2, eps = 0.9, 0.999, 1e-8
        t = 0
        losses: list[float] = []

        for epoch in range(epochs):
            order = rng.permutation(n)
            for start in range(0, n, bs):
                idx = order[start:start + bs]
                xb, yb = Xs[idx], Ys[idx]
                out, pre, acts = self._forward_std(xb)
                m = xb.shape[0]
                # MSE loss gradient w.r.t. linear output.
                delta = (out - yb) * (2.0 / m)
                gW: list[np.ndarray] = [None] * len(self.weights)  # type: ignore[list-item]
                gB: list[np.ndarray] = [None] * len(self.biases)   # type: ignore[list-item]
                for layer in reversed(range(len(self.weights))):
                    gW[layer] = acts[layer].T @ delta
                    gB[layer] = delta.sum(axis=0)
                    if layer > 0:
                        # backprop through tanh: 1 - tanh(z)^2
                        dtanh = 1.0 - np.tanh(pre[layer - 1]) ** 2
                        delta = (delta @ self.weights[layer].T) * dtanh
                # Adam update.
                t += 1
                for layer in range(len(self.weights)):
                    mW[layer] = b1 * mW[layer] + (1 - b1) * gW[layer]
                    vW[layer] = b2 * vW[layer] + (1 - b2) * gW[layer] ** 2
                    mB[layer] = b1 * mB[layer] + (1 - b1) * gB[layer]
                    vB[layer] = b2 * vB[layer] + (1 - b2) * gB[layer] ** 2
                    mW_hat = mW[layer] / (1 - b1 ** t)
                    vW_hat = vW[layer] / (1 - b2 ** t)
                    mB_hat = mB[layer] / (1 - b1 ** t)
                    vB_hat = vB[layer] / (1 - b2 ** t)
                    self.weights[layer] -= lr * mW_hat / (np.sqrt(vW_hat) + eps)
                    self.biases[layer] -= lr * mB_hat / (np.sqrt(vB_hat) + eps)
            if verbose and epoch % max(1, epochs // 10) == 0:
                full, _, _ = self._forward_std(Xs)
                losses.append(float(np.mean((full - Ys) ** 2)))
        # Final loss.
        full, _, _ = self._forward_std(Xs)
        losses.append(float(np.mean((full - Ys) ** 2)))
        return losses

    # ---- serialisation ---------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        if self.x_scaler is None or self.y_scaler is None:
            raise RuntimeError("Model is not trained.")
        return {
            "format": "daslab-mlp-1",
            "activation": "tanh",
            "layer_sizes": self.layer_sizes,
            "inputs": [name for name, _, _ in SURROGATE_INPUTS],
            "outputs": list(SURROGATE_OUTPUTS),
            "output_labels": list(SURROGATE_OUTPUT_LABELS),
            "output_transforms": list(self.output_transforms),
            "input_ranges": [[lo, hi] for _, lo, hi in SURROGATE_INPUTS],
            "x_mean": self.x_scaler.mean.tolist(),
            "x_std": self.x_scaler.std.tolist(),
            "y_mean": self.y_scaler.mean.tolist(),
            "y_std": self.y_scaler.std.tolist(),
            "weights": [W.tolist() for W in self.weights],
            "biases": [b.tolist() for b in self.biases],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MLPRegressor":
        net = cls(d["layer_sizes"])
        net.weights = [np.asarray(W, float) for W in d["weights"]]
        net.biases = [np.asarray(b, float) for b in d["biases"]]
        net.x_scaler = Standardizer(np.asarray(d["x_mean"]), np.asarray(d["x_std"]))
        net.y_scaler = Standardizer(np.asarray(d["y_mean"]), np.asarray(d["y_std"]))
        net.output_transforms = list(d.get("output_transforms", ["none"] * len(d["outputs"])))
        return net


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    """Coefficient of determination per output column."""

    ss_res = np.sum((y_true - y_pred) ** 2, axis=0)
    ss_tot = np.sum((y_true - y_true.mean(axis=0)) ** 2, axis=0)
    ss_tot[ss_tot < 1e-12] = 1e-12
    return 1.0 - ss_res / ss_tot


def mean_abs_pct_error(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    """Mean absolute percentage error per output column (guards small values)."""

    denom = np.maximum(np.abs(y_true), 1e-6)
    return np.mean(np.abs((y_true - y_pred) / denom), axis=0) * 100.0


# ---------------------------------------------------------------------------
# Dataset generation
# ---------------------------------------------------------------------------


def _base_inputs() -> TurbojetCycleInputs:
    from app.schemas import TurbojetInput
    return TurbojetInput(mass_flow_air_kg_s=50.0).to_cycle_inputs()


def build_training_set(n_samples: int = 6000, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Latin-Hypercube sample the design space and label it with the solver.

    Infeasible points (where the cycle raises) are dropped, so the returned set
    is slightly smaller than ``n_samples``.
    """

    from scipy.stats import qmc

    lows = np.array([lo for _, lo, _ in SURROGATE_INPUTS])
    highs = np.array([hi for _, _, hi in SURROGATE_INPUTS])
    sampler = qmc.LatinHypercube(d=len(SURROGATE_INPUTS), seed=seed)
    unit = sampler.random(n=n_samples)
    samples = qmc.scale(unit, lows, highs)

    base = _base_inputs()
    from dataclasses import replace

    X_rows: list[list[float]] = []
    Y_rows: list[list[float]] = []
    for row in samples:
        pr, tit, mach, alt = (float(v) for v in row)
        try:
            r = simulate_turbojet_cycle(
                replace(base, compressor_pressure_ratio=pr,
                        turbine_inlet_temperature_K=tit, mach=mach, altitude_m=alt)
            )
        except CycleCalculationError:
            continue
        spec = float(r["specific_thrust_N_per_kg_s"])
        tsfc = float(r["TSFC_kg_per_kN_hr"])
        # Keep the *useful* design envelope; drop degenerate near-zero-thrust
        # corners whose TSFC explodes and that no one would design to.
        if spec <= 60.0 or not (0.0 < tsfc < 250.0):
            continue
        X_rows.append([pr, tit, mach, alt])
        Y_rows.append([
            spec,
            float(r["TSFC_kg_per_kN_hr"]),
            float(r["overall_efficiency_estimate"]),
            float(r["station_table"][3]["stagnation_temperature_K"]),
        ])
    return np.asarray(X_rows, float), np.asarray(Y_rows, float)


@dataclass
class TrainingReport:
    """Held-out evaluation of a trained surrogate."""

    n_train: int
    n_test: int
    r2: dict[str, float]
    mape: dict[str, float]
    final_loss: float


def train_turbojet_surrogate(
    n_samples: int = 6000,
    hidden: tuple[int, ...] = (48, 48),
    epochs: int = 4000,
    lr: float = 0.01,
    test_fraction: float = 0.2,
    seed: int = 0,
) -> tuple[MLPRegressor, TrainingReport]:
    """Generate data, train the MLP, and evaluate on a held-out split."""

    X, Y = build_training_set(n_samples=n_samples, seed=seed)
    rng = np.random.default_rng(seed + 1)
    perm = rng.permutation(len(X))
    X, Y = X[perm], Y[perm]
    n_test = max(1, int(len(X) * test_fraction))
    Xte, Yte = X[:n_test], Y[:n_test]
    Xtr, Ytr = X[n_test:], Y[n_test:]

    net = MLPRegressor([len(SURROGATE_INPUTS), *hidden, len(SURROGATE_OUTPUTS)], seed=seed)
    losses = net.train(
        Xtr, Ytr, epochs=epochs, lr=lr, batch_size=256,
        output_transforms=list(SURROGATE_OUTPUT_TRANSFORMS), seed=seed,
    )

    pred = net.predict(Xte)
    r2 = r2_score(Yte, pred)
    mape = mean_abs_pct_error(Yte, pred)
    report = TrainingReport(
        n_train=len(Xtr),
        n_test=len(Xte),
        r2={name: float(v) for name, v in zip(SURROGATE_OUTPUTS, r2)},
        mape={name: float(v) for name, v in zip(SURROGATE_OUTPUTS, mape)},
        final_loss=float(losses[-1]),
    )
    return net, report


def default_artifact_path() -> Path:
    return Path(__file__).resolve().parent.parent / "static" / "models" / "surrogate_turbojet.json"
