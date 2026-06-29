"""
transit_cnn.py
--------------
Standalone Phase-5 module: train a 1-D convolutional neural network to
classify phase-folded light curves as *transit* (1) or *no-transit* (0).

This module is self-contained and does NOT depend on any earlier pipeline
step.  It generates its own synthetic training data via a parameterised
trapezoid-transit injector.

Architecture
------------
Input  : (batch, 1, SEQ_LEN)  — single-channel 1-D signal of length 201
         (the phase-folded, normalised flux sampled on a uniform phase grid)

  Conv1  : Conv1d(1  → 16, kernel=7, pad=3) → BatchNorm → GELU
  Pool1  : MaxPool1d(2)                                     → L/2

  Conv2  : Conv1d(16 → 32, kernel=5, pad=2) → BatchNorm → GELU
  Pool2  : MaxPool1d(2)                                     → L/4

  Conv3  : Conv1d(32 → 64, kernel=3, pad=1) → BatchNorm → GELU

  GAP    : AdaptiveAvgPool1d(1)                             → (batch, 64)

  Head   : Linear(64 → 32) → GELU → Dropout(0.3) → Linear(32 → 1)
  Output : sigmoid → scalar probability  p ∈ [0, 1]

Training
--------
* Synthetic dataset generated on-the-fly each epoch (no on-disk files).
* Positive examples : trapezoid transit injected at phase 0, with
  randomised depth, duration, ingress fraction, period-jitter, and
  white noise.
* Negative examples : flat + white noise + optional sinusoidal stellar
  variability; *no* transit signal.
* Loss : BCEWithLogitsLoss  (numerically stable; sigmoid in the head is
  bypassed during training).
* Optimiser : AdamW with cosine-annealing LR schedule.
* Metrics    : accuracy, precision, recall, F1, ROC-AUC (logged per epoch).

Saved artefacts
---------------
  data/models/transit_cnn_weights.pt   — state_dict (CPU-safe)
  data/models/transit_cnn_config.json  — hyper-parameters for reload
  plots/cnn_training_curves.png        — loss / accuracy / F1 history
  plots/cnn_roc_curve.png              — ROC on held-out test set
  plots/cnn_example_inputs.png         — sample positive & negative inputs

Usage
-----
    python -m src.transit_cnn                          # train with defaults
    python -m src.transit_cnn --epochs 50 --seq-len 201
    python -m src.transit_cnn --n-train 20000 --batch 256
    python -m src.transit_cnn --no-plots               # skip diagnostic plots

Dependencies (all in requirements.txt + torch)
-----------------------------------------------
    torch>=2.0, numpy>=1.24, matplotlib>=3.7, scikit-learn>=1.3
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
except ImportError as exc:
    sys.exit(
        "PyTorch is not installed.  Run:\n"
        "  pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
        f"Original error: {exc}"
    )

try:
    from sklearn.metrics import (
        accuracy_score, f1_score, precision_score,
        recall_score, roc_auc_score, roc_curve,
    )
except ImportError as exc:
    sys.exit(f"scikit-learn missing: {exc}")

from src.config import CFG

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(CFG.LOG_DIR / "transit_cnn.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_MODEL_DIR:  Path = CFG.DATA_DIR / "models"
_WEIGHTS_PT: Path = _MODEL_DIR   / "transit_cnn_weights.pt"
_CONFIG_JSON: Path = _MODEL_DIR  / "transit_cnn_config.json"
_PLOT_DIR:   Path = CFG.PLOT_DIR

# ---------------------------------------------------------------------------
# Default hyper-parameters
# ---------------------------------------------------------------------------

_SEQ_LEN:   int   = 201     # number of phase bins  (centred on transit)
_N_TRAIN:   int   = 10_000  # training examples
_N_VAL:     int   = 2_000   # validation examples
_N_TEST:    int   = 2_000   # held-out test examples
_BATCH:     int   = 128
_EPOCHS:    int   = 30
_LR:        float = 3e-4
_WEIGHT_DECAY: float = 1e-4
_DROPOUT:   float = 0.30


# ============================================================================
# 1.  SYNTHETIC DATA GENERATOR
# ============================================================================

def _trapezoid_transit(
    phase: np.ndarray,
    depth: float,
    total_dur: float,
    ingress_frac: float,
) -> np.ndarray:
    """
    Evaluate a symmetric trapezoid transit model on *phase* ∈ [-0.5, 0.5].

    The transit is centred at phase 0.  The model is parametrised by:

    Parameters
    ----------
    phase        : 1-D array of phase values in [-0.5, 0.5].
    depth        : Transit depth as a fractional flux drop (0 < depth < 1).
    total_dur    : Total transit duration in phase units.
    ingress_frac : Fraction of total_dur spent in ingress (0 → box, 1 → V).

    Returns
    -------
    flux model (1 - transit dip), same shape as *phase*.
    """
    half_total  = total_dur / 2.0
    half_flat   = half_total * (1.0 - ingress_frac)   # flat-bottom half-width

    flux = np.ones_like(phase)
    abs_ph = np.abs(phase)

    # Flat bottom
    in_flat = abs_ph <= half_flat
    flux[in_flat] = 1.0 - depth

    # Ingress / egress ramps
    in_ramp = (abs_ph > half_flat) & (abs_ph <= half_total)
    if in_ramp.any() and (half_total > half_flat):
        slope = depth / (half_total - half_flat)
        flux[in_ramp] = 1.0 - depth + slope * (abs_ph[in_ramp] - half_flat)

    return flux


def make_synthetic_dataset(
    n_samples:  int,
    seq_len:    int = _SEQ_LEN,
    pos_frac:   float = 0.5,
    rng:        np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate a balanced synthetic dataset of phase-folded light curves.

    Positive class (label = 1) — trapezoid transit injected at phase 0:
      depth        ~ Uniform(0.001, 0.030)  [0.1 % – 3 %]
      duration     ~ Uniform(0.01,  0.15)   [1 % – 15 % of period]
      ingress_frac ~ Uniform(0.10,  0.50)
      t0_jitter    ~ Uniform(-0.02, 0.02)   [sub-bin centering uncertainty]
      stellar var  ~ A·sin(2π·f·phase + φ), A ~ U(0, 0.001)

    Negative class (label = 0) — flat + stellar variability only:
      stellar var  ~ A·sin(2π·f·phase + φ), A ~ U(0, 0.002)
      (occasionally a secondary eclipse or v-shaped dip can appear, making
       the task harder and preventing trivial solutions)

    Both classes receive i.i.d. Gaussian white noise with σ ~ U(0.5, 2) mmag.

    Parameters
    ----------
    n_samples : Total number of examples.
    seq_len   : Length of each 1-D sequence.
    pos_frac  : Fraction of positive (transit) examples.
    rng       : Optional numpy Generator for reproducibility.

    Returns
    -------
    X : float32 array, shape (n_samples, seq_len), values ≈ 1.0 ± small.
    y : int8 array,   shape (n_samples,),          0 or 1.
    """
    if rng is None:
        rng = np.random.default_rng()

    phase = np.linspace(-0.5, 0.5, seq_len, dtype=np.float32)

    n_pos = int(n_samples * pos_frac)
    n_neg = n_samples - n_pos

    X = np.empty((n_samples, seq_len), dtype=np.float32)
    y = np.empty(n_samples,            dtype=np.int8)

    # ── Positive examples ──────────────────────────────────────────────────
    for i in range(n_pos):
        depth        = rng.uniform(0.001, 0.030)
        total_dur    = rng.uniform(0.010, 0.150)
        ingress_frac = rng.uniform(0.100, 0.500)
        jitter       = rng.uniform(-0.020, 0.020)

        flux = _trapezoid_transit(phase - jitter, depth, total_dur, ingress_frac)

        # Stellar variability sinusoid
        amp  = rng.uniform(0.0, 0.001)
        freq = rng.uniform(0.5, 4.0)
        phi  = rng.uniform(0, 2 * np.pi)
        flux += amp * np.sin(2 * np.pi * freq * phase + phi)

        # White noise
        sigma = rng.uniform(0.0005, 0.002)
        flux += rng.normal(0.0, sigma, seq_len).astype(np.float32)

        X[i] = flux
        y[i] = 1

    # ── Negative examples ──────────────────────────────────────────────────
    for i in range(n_neg):
        flux = np.ones(seq_len, dtype=np.float32)

        # Stellar variability (larger amplitude than positives)
        amp  = rng.uniform(0.0, 0.002)
        freq = rng.uniform(0.5, 6.0)
        phi  = rng.uniform(0, 2 * np.pi)
        flux += amp * np.sin(2 * np.pi * freq * phase + phi).astype(np.float32)

        # Occasional v-shaped / secondary dip as hard negatives
        if rng.random() < 0.15:
            neg_depth = rng.uniform(0.0005, 0.005)
            neg_phase = rng.uniform(0.1, 0.45)  # off-centre → secondary eclipse
            neg_dur   = rng.uniform(0.005, 0.05)
            dip = _trapezoid_transit(phase - neg_phase, neg_depth, neg_dur, 0.3)
            flux *= dip.astype(np.float32)

        # White noise
        sigma = rng.uniform(0.0005, 0.002)
        flux += rng.normal(0.0, sigma, seq_len).astype(np.float32)

        X[n_pos + i] = flux
        y[n_pos + i] = 0

    # Shuffle
    idx = rng.permutation(n_samples)
    return X[idx], y[idx]


# ============================================================================
# 2.  MODEL DEFINITION
# ============================================================================

class TransitCNN(nn.Module):
    """
    1-D CNN for binary transit classification.

    Input shape  : (batch, 1, seq_len)
    Output shape : (batch, 1)   — raw logit before sigmoid
                   Use  torch.sigmoid(output) > 0.5  for predictions.

    Architecture
    ------------
    Block 1: Conv1d(1  →16, k=7, pad=3) → BN → GELU → MaxPool(2)
    Block 2: Conv1d(16 →32, k=5, pad=2) → BN → GELU → MaxPool(2)
    Block 3: Conv1d(32 →64, k=3, pad=1) → BN → GELU
    GAP    : AdaptiveAvgPool1d(1) → flatten to (batch, 64)
    Head   : Linear(64→32) → GELU → Dropout → Linear(32→1)
    """

    def __init__(
        self,
        seq_len:  int   = _SEQ_LEN,
        dropout:  float = _DROPOUT,
    ) -> None:
        super().__init__()
        self.seq_len = seq_len

        # ── Convolutional blocks ──────────────────────────────────────────
        self.conv_block1 = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=7, padding=3, bias=False),
            nn.BatchNorm1d(16),
            nn.GELU(),
            nn.MaxPool1d(2),
        )
        self.conv_block2 = nn.Sequential(
            nn.Conv1d(16, 32, kernel_size=5, padding=2, bias=False),
            nn.BatchNorm1d(32),
            nn.GELU(),
            nn.MaxPool1d(2),
        )
        self.conv_block3 = nn.Sequential(
            nn.Conv1d(32, 64, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm1d(64),
            nn.GELU(),
        )

        # ── Global average pooling ────────────────────────────────────────
        self.gap = nn.AdaptiveAvgPool1d(1)

        # ── Classification head ───────────────────────────────────────────
        self.head = nn.Sequential(
            nn.Linear(64, 32),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
            # No sigmoid here — BCEWithLogitsLoss is numerically stable
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # noqa: D401
        """Forward pass.  x: (batch, 1, seq_len)  → logit: (batch, 1)"""
        x = self.conv_block1(x)   # (B, 16, L/2)
        x = self.conv_block2(x)   # (B, 32, L/4)
        x = self.conv_block3(x)   # (B, 64, L/4)
        x = self.gap(x)           # (B, 64, 1)
        x = x.squeeze(-1)         # (B, 64)
        x = self.head(x)          # (B, 1)
        return x

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Return sigmoid probability.  Convenience wrapper."""
        return torch.sigmoid(self.forward(x))

    @staticmethod
    def from_checkpoint(weights_path: Path, config_path: Path) -> "TransitCNN":
        """Reload a saved model from weights + config JSON."""
        with open(config_path) as f:
            cfg = json.load(f)
        model = TransitCNN(seq_len=cfg["seq_len"], dropout=cfg["dropout"])
        model.load_state_dict(torch.load(weights_path, map_location="cpu"))
        model.eval()
        return model


# ============================================================================
# 3.  METRICS HELPER
# ============================================================================

def _compute_metrics(
    logits: np.ndarray,
    labels: np.ndarray,
    threshold: float = 0.5,
) -> dict[str, float]:
    """Compute a full set of binary classification metrics."""
    probs = 1.0 / (1.0 + np.exp(-logits))   # sigmoid
    preds = (probs >= threshold).astype(int)
    return {
        "accuracy":  float(accuracy_score(labels, preds)),
        "precision": float(precision_score(labels, preds, zero_division=0)),
        "recall":    float(recall_score(labels, preds, zero_division=0)),
        "f1":        float(f1_score(labels, preds, zero_division=0)),
        "roc_auc":   float(roc_auc_score(labels, probs)),
    }


# ============================================================================
# 4.  TRAINING LOOP
# ============================================================================

def train(
    seq_len:      int   = _SEQ_LEN,
    n_train:      int   = _N_TRAIN,
    n_val:        int   = _N_VAL,
    n_test:       int   = _N_TEST,
    batch_size:   int   = _BATCH,
    epochs:       int   = _EPOCHS,
    lr:           float = _LR,
    weight_decay: float = _WEIGHT_DECAY,
    dropout:      float = _DROPOUT,
    seed:         int   = 42,
    save_plots:   bool  = True,
) -> TransitCNN:
    """
    Generate synthetic data, train the CNN, evaluate on test set,
    save weights + config, and optionally plot training curves.

    Returns
    -------
    TransitCNN
        The trained model (on CPU, in eval mode).
    """
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info("Device: %s", device)

    # ── 4.1  Synthetic datasets ───────────────────────────────────────────────
    log.info("Generating synthetic datasets …")
    t0_gen = time.perf_counter()

    X_train, y_train = make_synthetic_dataset(n_train, seq_len=seq_len, rng=rng)
    X_val,   y_val   = make_synthetic_dataset(n_val,   seq_len=seq_len, rng=rng)
    X_test,  y_test  = make_synthetic_dataset(n_test,  seq_len=seq_len, rng=rng)

    log.info(
        "  train=%d  val=%d  test=%d  (%.1f s)",
        n_train, n_val, n_test, time.perf_counter() - t0_gen,
    )

    def to_loader(X, y, shuffle):
        Xt = torch.from_numpy(X[:, None, :])      # (N, 1, L)
        yt = torch.from_numpy(y.astype(np.float32)[:, None])  # (N, 1)
        return DataLoader(TensorDataset(Xt, yt), batch_size=batch_size,
                          shuffle=shuffle, num_workers=0, pin_memory=False)

    train_loader = to_loader(X_train, y_train, shuffle=True)
    val_loader   = to_loader(X_val,   y_val,   shuffle=False)
    test_loader  = to_loader(X_test,  y_test,  shuffle=False)

    # ── 4.2  Model, loss, optimiser ──────────────────────────────────────────
    model = TransitCNN(seq_len=seq_len, dropout=dropout).to(device)
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    log.info("Model: %d trainable parameters", n_params)

    criterion = nn.BCEWithLogitsLoss()
    optimiser = torch.optim.AdamW(model.parameters(), lr=lr,
                                   weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimiser, T_max=epochs, eta_min=lr / 20,
    )

    # ── 4.3  Training loop ────────────────────────────────────────────────────
    history: dict[str, list] = {
        "train_loss": [], "val_loss": [],
        "val_acc": [],    "val_f1":  [],
        "val_auc": [],    "lr":      [],
    }

    best_val_auc  = -1.0
    best_state    = None

    log.info(
        "\n%s\n  Epoch  │  Train Loss  │  Val Loss  │  Val Acc  │  Val F1  │  Val AUC\n%s",
        "─" * 72, "─" * 72,
    )

    for epoch in range(1, epochs + 1):
        # ── Train ─────────────────────────────────────────────────────────
        model.train()
        train_loss_sum = 0.0
        for Xb, yb in train_loader:
            Xb, yb = Xb.to(device), yb.to(device)
            optimiser.zero_grad()
            logits = model(Xb)
            loss   = criterion(logits, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimiser.step()
            train_loss_sum += loss.item() * len(Xb)

        train_loss = train_loss_sum / n_train
        scheduler.step()

        # ── Validate ──────────────────────────────────────────────────────
        model.eval()
        val_loss_sum = 0.0
        all_logits, all_labels = [], []
        with torch.no_grad():
            for Xb, yb in val_loader:
                Xb, yb = Xb.to(device), yb.to(device)
                logits = model(Xb)
                val_loss_sum += criterion(logits, yb).item() * len(Xb)
                all_logits.append(logits.cpu().numpy())
                all_labels.append(yb.cpu().numpy())

        val_loss    = val_loss_sum / n_val
        all_logits  = np.vstack(all_logits).ravel()
        all_labels  = np.vstack(all_labels).ravel()
        val_metrics = _compute_metrics(all_logits, all_labels)

        # ── Record ────────────────────────────────────────────────────────
        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_metrics["accuracy"])
        history["val_f1"].append(val_metrics["f1"])
        history["val_auc"].append(val_metrics["roc_auc"])
        history["lr"].append(scheduler.get_last_lr()[0])

        log.info(
            "  %5d  │  %.6f    │  %.6f  │  %.4f   │  %.4f  │  %.4f",
            epoch,
            train_loss, val_loss,
            val_metrics["accuracy"], val_metrics["f1"], val_metrics["roc_auc"],
        )

        # ── Best-model checkpoint ─────────────────────────────────────────
        if val_metrics["roc_auc"] > best_val_auc:
            best_val_auc = val_metrics["roc_auc"]
            best_state   = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    log.info("─" * 72)
    log.info("Best val AUC: %.4f", best_val_auc)

    # ── 4.4  Restore best weights & test evaluation ───────────────────────────
    model.load_state_dict(best_state)
    model.eval()

    test_logits, test_labels = [], []
    with torch.no_grad():
        for Xb, yb in test_loader:
            logits = model(Xb.to(device))
            test_logits.append(logits.cpu().numpy())
            test_labels.append(yb.numpy())

    test_logits = np.vstack(test_logits).ravel()
    test_labels = np.vstack(test_labels).ravel()
    test_metrics = _compute_metrics(test_logits, test_labels)

    log.info(
        "\n%s\n[test results]\n%s\n"
        "  Accuracy  : %.4f\n"
        "  Precision : %.4f\n"
        "  Recall    : %.4f\n"
        "  F1        : %.4f\n"
        "  ROC-AUC   : %.4f\n%s",
        "=" * 50, "─" * 50,
        test_metrics["accuracy"], test_metrics["precision"],
        test_metrics["recall"],   test_metrics["f1"],
        test_metrics["roc_auc"],
        "=" * 50,
    )

    # ── 4.5  Save weights & config ────────────────────────────────────────────
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)

    torch.save(best_state, _WEIGHTS_PT)
    log.info("Weights saved -> %s", _WEIGHTS_PT)

    config = {
        "seq_len":      seq_len,
        "dropout":      dropout,
        "n_train":      n_train,
        "n_val":        n_val,
        "n_test":       n_test,
        "batch_size":   batch_size,
        "epochs":       epochs,
        "lr":           lr,
        "weight_decay": weight_decay,
        "seed":         seed,
        "best_val_auc": round(best_val_auc, 6),
        "test_metrics": {k: round(v, 6) for k, v in test_metrics.items()},
    }
    with open(_CONFIG_JSON, "w") as f:
        json.dump(config, f, indent=2)
    log.info("Config saved -> %s", _CONFIG_JSON)

    # ── 4.6  Plots ────────────────────────────────────────────────────────────
    if save_plots:
        _plot_training_curves(history)
        _plot_roc(test_logits, test_labels)
        _plot_example_inputs(X_train, y_train, seq_len)

    return model


# ============================================================================
# 5.  DIAGNOSTIC PLOTS
# ============================================================================

_DARK_BG   = "#0f1117"
_GRID_COL  = "#2a2d3a"
_WHITE     = "#e8eaf0"
_BLUE      = "#4C72B0"
_RED       = "#C44E52"
_GREEN     = "#55A868"
_ORANGE    = "#DD8452"
_PURPLE    = "#8172B2"


def _ax_dark(ax):
    ax.set_facecolor(_DARK_BG)
    ax.tick_params(colors=_WHITE, labelsize=8)
    ax.xaxis.label.set_color(_WHITE)
    ax.yaxis.label.set_color(_WHITE)
    ax.title.set_color(_WHITE)
    for sp in ax.spines.values():
        sp.set_edgecolor("#444")
    ax.grid(True, color=_GRID_COL, lw=0.4, ls="--")


def _plot_training_curves(history: dict) -> None:
    """4-panel training history: loss, accuracy, F1, AUC + LR."""
    epochs = list(range(1, len(history["train_loss"]) + 1))
    fig, axes = plt.subplots(2, 2, figsize=(13, 7))
    fig.patch.set_facecolor(_DARK_BG)
    fig.suptitle("CNN Training History", color=_WHITE, fontsize=13,
                 fontweight="bold", y=0.99)

    pairs = [
        (axes[0, 0], "Loss",        "train_loss", "val_loss",  _BLUE,   _RED),
        (axes[0, 1], "Accuracy",    None,         "val_acc",   None,    _GREEN),
        (axes[1, 0], "F1 Score",    None,         "val_f1",    None,    _ORANGE),
        (axes[1, 1], "ROC-AUC",     None,         "val_auc",   None,    _PURPLE),
    ]

    for ax, title, train_key, val_key, tc, vc in pairs:
        _ax_dark(ax)
        if train_key:
            ax.plot(epochs, history[train_key], color=tc, lw=1.4,
                    label="Train", alpha=0.8)
        ax.plot(epochs, history[val_key], color=vc, lw=1.8,
                label="Val", alpha=0.9)
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("Epoch", fontsize=9)
        ax.legend(fontsize=8, facecolor="#1a1d27", edgecolor="#444",
                  labelcolor=_WHITE)

    # LR overlay on Loss panel
    ax2 = axes[0, 0].twinx()
    ax2.plot(epochs, history["lr"], color=_WHITE, lw=0.8, ls=":",
             alpha=0.5, label="LR")
    ax2.set_ylabel("LR", color=_WHITE, fontsize=7)
    ax2.tick_params(colors=_WHITE, labelsize=6)
    ax2.set_facecolor(_DARK_BG)

    fig.tight_layout()
    out = _PLOT_DIR / "cnn_training_curves.png"
    fig.savefig(out, dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    log.info("Training curves -> %s", out)


def _plot_roc(logits: np.ndarray, labels: np.ndarray) -> None:
    """ROC curve on the held-out test set."""
    probs = 1.0 / (1.0 + np.exp(-logits))
    fpr, tpr, _ = roc_curve(labels, probs)
    auc = roc_auc_score(labels, probs)

    fig, ax = plt.subplots(figsize=(6, 5))
    fig.patch.set_facecolor(_DARK_BG)
    _ax_dark(ax)

    ax.plot(fpr, tpr, color=_BLUE, lw=2.0, label=f"AUC = {auc:.4f}")
    ax.plot([0, 1], [0, 1], color="#555", lw=0.8, ls="--", label="Random")
    ax.fill_between(fpr, tpr, alpha=0.12, color=_BLUE)
    ax.set_xlabel("False Positive Rate", fontsize=10)
    ax.set_ylabel("True Positive Rate",  fontsize=10)
    ax.set_title("ROC Curve  (test set)", fontsize=11, color=_WHITE)
    ax.legend(fontsize=9, facecolor="#1a1d27", edgecolor="#444",
              labelcolor=_WHITE)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)

    out = _PLOT_DIR / "cnn_roc_curve.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    log.info("ROC curve -> %s", out)


def _plot_example_inputs(X: np.ndarray, y: np.ndarray, seq_len: int) -> None:
    """4 positive + 4 negative examples from the training set."""
    phase = np.linspace(-0.5, 0.5, seq_len)
    pos_idx = np.where(y == 1)[0][:4]
    neg_idx = np.where(y == 0)[0][:4]

    fig, axes = plt.subplots(2, 4, figsize=(14, 5), sharey=False)
    fig.patch.set_facecolor(_DARK_BG)
    fig.suptitle("Example CNN Inputs  (top: transit | bottom: no-transit)",
                 color=_WHITE, fontsize=11, y=0.99)

    for col, (pi, ni) in enumerate(zip(pos_idx, neg_idx)):
        for row, (idx, label, color) in enumerate([
            (pi, "Transit",    _ORANGE),
            (ni, "No-transit", _BLUE),
        ]):
            ax = axes[row, col]
            _ax_dark(ax)
            ax.plot(phase, X[idx], color=color, lw=0.9)
            ax.axhline(1.0, color="#555", lw=0.5, ls=":")
            ax.set_xlim(-0.5, 0.5)
            if col == 0:
                ax.set_ylabel(label, color=_WHITE, fontsize=9)
            ax.set_xlabel("Phase" if row == 1 else "", fontsize=8)
            ax.tick_params(labelsize=7)

    fig.tight_layout()
    out = _PLOT_DIR / "cnn_example_inputs.png"
    fig.savefig(out, dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    log.info("Example inputs -> %s", out)


# ============================================================================
# 6.  CLI
# ============================================================================

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train a 1-D CNN transit classifier on synthetic data.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--seq-len",      type=int,   default=_SEQ_LEN,
                   metavar="N",
                   help=f"Phase-grid length.  Default: {_SEQ_LEN}")
    p.add_argument("--n-train",      type=int,   default=_N_TRAIN,
                   metavar="N",
                   help=f"Training examples.  Default: {_N_TRAIN}")
    p.add_argument("--n-val",        type=int,   default=_N_VAL,
                   metavar="N",
                   help=f"Validation examples.  Default: {_N_VAL}")
    p.add_argument("--n-test",       type=int,   default=_N_TEST,
                   metavar="N",
                   help=f"Test examples.  Default: {_N_TEST}")
    p.add_argument("--batch",        type=int,   default=_BATCH,
                   metavar="N",
                   help=f"Mini-batch size.  Default: {_BATCH}")
    p.add_argument("--epochs",       type=int,   default=_EPOCHS,
                   metavar="N",
                   help=f"Training epochs.  Default: {_EPOCHS}")
    p.add_argument("--lr",           type=float, default=_LR,
                   help=f"Initial learning rate.  Default: {_LR}")
    p.add_argument("--dropout",      type=float, default=_DROPOUT,
                   help=f"Dropout probability.  Default: {_DROPOUT}")
    p.add_argument("--seed",         type=int,   default=42,
                   help="Random seed.  Default: 42")
    p.add_argument("--no-plots",     action="store_true", default=False,
                   help="Skip diagnostic plots.")
    return p.parse_args()


def main() -> None:
    CFG.LOG_DIR.mkdir(parents=True, exist_ok=True)
    _PLOT_DIR.mkdir(parents=True, exist_ok=True)

    args = _parse_args()
    log.info(
        "Starting CNN training\n"
        "  seq_len=%d  n_train=%d  epochs=%d  batch=%d  lr=%.2e  seed=%d",
        args.seq_len, args.n_train, args.epochs,
        args.batch, args.lr, args.seed,
    )

    train(
        seq_len=args.seq_len,
        n_train=args.n_train,
        n_val=args.n_val,
        n_test=args.n_test,
        batch_size=args.batch,
        epochs=args.epochs,
        lr=args.lr,
        dropout=args.dropout,
        seed=args.seed,
        save_plots=not args.no_plots,
    )


if __name__ == "__main__":
    main()
