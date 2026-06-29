"""
score_candidates.py
-------------------
Stage 2 final step: combine BLS statistics and CNN confidence to flag
transit candidates.

For each star that has both a BLS result and a cleaned light curve the
script:

  1. Loads the cleaned light curve  (data/clean/lightcurves/TIC_<id>.csv)
  2. Phase-folds on the BLS period + t0
  3. Resamples to a uniform 201-point phase grid matching the CNN input
  4. Runs the trained CNN → produces a transit probability (0–1)
  5. Computes the empirical transit SNR from the light curve:

         scatter         = robust σ of out-of-transit residuals (NMAD)
         n_in_transit    = number of cadences inside transit windows
         n_transits      = ⌊ time_span / period ⌋   (observed transits)

         SNR  =  depth / scatter  ×  √n_in_transit

     This is the signal-detection SNR (not BLS power), stable against
     period aliases and independent of the BLS objective.

  6. Flags the star as a transit candidate when:
         CNN_score  > CNN_THRESH   (default 0.70)
         SNR        > SNR_THRESH   (default 7.0)

  7. Appends one row per star to:
         data/results/stage2_candidates.csv

     Columns:
       TIC_ID, period, depth, duration, t0, SNR, CNN_score, is_candidate

Usage
-----
    python -m src.score_candidates                    # all BLS rows
    python -m src.score_candidates --n 50             # first 50 by power
    python -m src.score_candidates --tic 468184895    # specific IDs
    python -m src.score_candidates --cnn-thresh 0.6   # looser CNN gate
    python -m src.score_candidates --snr-thresh 5     # looser SNR gate
    python -m src.score_candidates --overwrite        # recompute all

Dependencies
-------------
    torch>=2.0, numpy>=1.24, pandas>=2.0, scipy>=1.11,
    matplotlib>=3.7, tqdm>=4.65
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from scipy.stats import median_abs_deviation
from tqdm import tqdm

try:
    import torch
except ImportError as exc:
    sys.exit(f"PyTorch missing: {exc}")

from src.config import CFG
from src.transit_cnn import TransitCNN      # model class
from src.plot_phase_folds import phase_fold  # shared helper

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
        logging.FileHandler(CFG.LOG_DIR / "score_candidates.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_BLS_CSV:        Path = CFG.DATA_DIR / "results" / "bls_results.csv"
_CLEAN_LC_DIR:   Path = CFG.CLEAN_DIR / "lightcurves"
_WEIGHTS_PT:     Path = CFG.DATA_DIR  / "models" / "transit_cnn_weights.pt"
_CONFIG_JSON:    Path = CFG.DATA_DIR  / "models" / "transit_cnn_config.json"
_OUT_CSV:        Path = CFG.DATA_DIR  / "results" / "stage2_candidates.csv"
_PLOT_DIR:       Path = CFG.PLOT_DIR  / "candidates"

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_CNN_THRESH: float = 0.70   # minimum CNN transit probability
_SNR_THRESH: float = 7.0    # minimum empirical SNR

# Final output column order
_OUT_COLS: list[str] = [
    "TIC_ID", "period", "depth", "duration", "t0",
    "SNR", "CNN_score", "is_candidate",
]


# ============================================================================
# 1.  PHASE GRID RESAMPLER
# ============================================================================

def resample_to_grid(
    phase:      np.ndarray,
    flux:       np.ndarray,
    n_grid:     int  = 201,
    bin_width:  float | None = None,
) -> np.ndarray:
    """
    Resample a (phase, flux) pair onto a uniform phase grid of *n_grid*
    points spanning [-0.5, 0.5].

    Strategy
    --------
    * Divide the phase axis into *n_grid* equal bins.
    * Average all cadences that fall in each bin.
    * Fill empty bins with the linear interpolation from neighbouring bins,
      or with 1.0 (baseline flux) at the edges.

    This mirrors how the CNN's synthetic training data is structured — a
    uniform 201-point phase-folded light curve centred on the transit.

    Parameters
    ----------
    phase      : 1-D array of phase values in [-0.5, 0.5).
    flux       : Corresponding normalised flux values.
    n_grid     : Number of output points (must match CNN seq_len).
    bin_width  : Override bin width; inferred from n_grid if None.

    Returns
    -------
    grid_flux : float32 array of shape (n_grid,).
    """
    if bin_width is None:
        bin_width = 1.0 / n_grid

    edges      = np.linspace(-0.5, 0.5, n_grid + 1)
    grid_phase = 0.5 * (edges[:-1] + edges[1:])   # bin centres
    grid_flux  = np.full(n_grid, np.nan)

    for k in range(n_grid):
        mask = (phase >= edges[k]) & (phase < edges[k + 1])
        if mask.sum() > 0:
            grid_flux[k] = float(np.mean(flux[mask]))

    # Fill NaN gaps by linear interpolation between populated bins
    valid = np.isfinite(grid_flux)
    if valid.sum() >= 2:
        interp = interp1d(
            grid_phase[valid], grid_flux[valid],
            kind="linear", bounds_error=False,
            fill_value=(grid_flux[valid][0], grid_flux[valid][-1]),
        )
        grid_flux = interp(grid_phase)
    elif valid.sum() == 1:
        grid_flux[:] = grid_flux[valid][0]
    else:
        grid_flux[:] = 1.0    # pathological fallback

    return grid_flux.astype(np.float32)


# ============================================================================
# 2.  EMPIRICAL SNR CALCULATOR
# ============================================================================

def compute_snr(
    t:          np.ndarray,
    flux:       np.ndarray,
    period:     float,
    t0:         float,
    duration:   float,
    depth:      float,
) -> float:
    """
    Compute an empirical transit SNR from the light curve.

    Definition
    ----------
    scatter = NMAD of the out-of-transit flux residuals
              (Normalised Median Absolute Deviation — robust against
               remaining outliers and stellar activity)

    n_in    = number of 2-min cadences that fall inside *any* transit window

    SNR     = depth / scatter × √n_in

    This formulation is the standard signal-detection efficiency statistic
    (analogous to the TESS pipeline's MES metric).  It is independent of
    the BLS power and correctly handles the case where BLS locks on an alias.

    Parameters
    ----------
    t, flux  : Time (BTJD) and normalised flux arrays.
    period   : Orbital period in days.
    t0       : Reference mid-transit time in BTJD.
    duration : Transit duration in days.
    depth    : Transit depth (fractional).

    Returns
    -------
    float  — SNR value; 0.0 on degenerate inputs.
    """
    if period <= 0 or duration <= 0 or depth <= 0:
        return 0.0

    half_dur = 0.5 * duration
    phase    = phase_fold(t, period, t0)
    in_mask  = np.abs(phase) <= (half_dur / period)
    out_mask = ~in_mask

    n_in = int(in_mask.sum())
    if n_in == 0 or out_mask.sum() < 5:
        return 0.0

    # Robust scatter from out-of-transit points
    out_flux = flux[out_mask]
    mad      = float(median_abs_deviation(out_flux, scale="normal"))  # ≈ σ
    if mad <= 0:
        return 0.0

    snr = depth / mad * np.sqrt(n_in)
    return float(snr)


# ============================================================================
# 3.  CNN SCORER
# ============================================================================

def load_model(weights_pt: Path, config_json: Path) -> tuple[TransitCNN, int]:
    """
    Load the trained TransitCNN and return (model, seq_len).
    Model is placed in eval mode on CPU.
    """
    if not weights_pt.exists():
        raise FileNotFoundError(
            f"CNN weights not found: {weights_pt}\n"
            "Run  python -m src.transit_cnn  first."
        )
    if not config_json.exists():
        raise FileNotFoundError(f"CNN config not found: {config_json}")

    with open(config_json) as f:
        cfg = json.load(f)
    seq_len = int(cfg["seq_len"])

    model = TransitCNN.from_checkpoint(weights_pt, config_json)
    model.eval()
    log.info(
        "CNN loaded (seq_len=%d, val_auc=%.4f, test_auc=%.4f)",
        seq_len,
        cfg.get("best_val_auc", float("nan")),
        cfg.get("test_metrics", {}).get("roc_auc", float("nan")),
    )
    return model, seq_len


@torch.no_grad()
def cnn_score(
    model:       TransitCNN,
    grid_flux:   np.ndarray,
) -> float:
    """
    Run the CNN on a single resampled phase-folded light curve.

    Parameters
    ----------
    model      : TransitCNN in eval mode.
    grid_flux  : float32 array of shape (seq_len,)  ← output of resample_to_grid.

    Returns
    -------
    float in [0, 1] — transit probability.
    """
    x = torch.from_numpy(grid_flux[None, None, :])   # (1, 1, seq_len)
    return float(model.predict_proba(x).item())


# ============================================================================
# 4.  PER-STAR SCORING
# ============================================================================

def score_one(
    tic_id:    str,
    lc_path:   Path,
    period:    float,
    depth:     float,
    duration:  float,
    t0:        float,
    model:     TransitCNN,
    seq_len:   int,
) -> dict:
    """
    Score a single star.  Returns a dict with keys matching _OUT_COLS.

    Raises ValueError on unrecoverable problems (logged as warnings by
    the caller, which writes a NaN row instead).
    """
    # ── Load light curve ──────────────────────────────────────────────────────
    df = pd.read_csv(lc_path)
    required = {"time", "flux_norm"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns {required - set(df.columns)}")

    df = (df.dropna(subset=["time", "flux_norm"])
            .sort_values("time")
            .reset_index(drop=True))

    if len(df) < 50:
        raise ValueError(f"Only {len(df)} usable cadences.")

    t    = df["time"].to_numpy(np.float64)
    flux = df["flux_norm"].to_numpy(np.float64)

    # ── Phase fold ────────────────────────────────────────────────────────────
    phase = phase_fold(t, period, t0)

    # ── Empirical SNR ─────────────────────────────────────────────────────────
    snr = compute_snr(t, flux, period, t0, duration, depth)

    # ── CNN score ─────────────────────────────────────────────────────────────
    grid_flux  = resample_to_grid(phase, flux.astype(np.float32), n_grid=seq_len)
    score      = cnn_score(model, grid_flux)

    log.info(
        "[%s] P=%.4f d  δ=%.1f ppm  SNR=%.2f  CNN=%.3f",
        tic_id, period, depth * 1e6, snr, score,
    )

    return {
        "TIC_ID":       tic_id,
        "period":       round(period,   6),
        "depth":        round(depth,    8),
        "duration":     round(duration, 6),
        "t0":           round(t0,       6),
        "SNR":          round(snr,      3),
        "CNN_score":    round(score,    4),
        "is_candidate": int(score > _CNN_THRESH and snr > _SNR_THRESH),
    }


# ============================================================================
# 5.  DIAGNOSTIC PLOT FOR CANDIDATES
# ============================================================================

_DARK  = "#0f1117"
_BLUE  = "#4C72B0"
_RED   = "#C44E52"
_GREEN = "#2ca02c"
_ORG   = "#DD8452"
_WHITE = "#e8eaf0"
_GRID  = "#2a2d3a"


def _ax_dark(ax):
    ax.set_facecolor(_DARK)
    ax.tick_params(colors=_WHITE, labelsize=8)
    ax.xaxis.label.set_color(_WHITE)
    ax.yaxis.label.set_color(_WHITE)
    ax.title.set_color(_WHITE)
    for sp in ax.spines.values():
        sp.set_edgecolor("#444")
    ax.grid(True, color=_GRID, lw=0.4, ls="--")


def plot_candidate(
    tic_id:    str,
    lc_path:   Path,
    period:    float,
    depth:     float,
    duration:  float,
    t0:        float,
    snr:       float,
    cnn_score_val: float,
    seq_len:   int,
) -> None:
    """
    3-panel candidate summary figure:
      Left  : Phase-folded scatter + binned average + box model
      Right top   : CNN input (resampled grid) with score annotation
      Right bottom: Score bar chart (SNR vs threshold | CNN vs threshold)
    """
    df   = pd.read_csv(lc_path)
    df   = df.dropna(subset=["time","flux_norm"]).sort_values("time").reset_index(drop=True)
    t    = df["time"].to_numpy(np.float64)
    flux = df["flux_norm"].to_numpy(np.float64)

    phase     = phase_fold(t, period, t0)
    grid_flux = resample_to_grid(phase, flux.astype(np.float32), n_grid=seq_len)
    ph_grid   = np.linspace(-0.5, 0.5, seq_len)

    # Phase-bin raw scatter for the fold panel
    bin_edges = np.linspace(-0.5, 0.5, 201)
    bp, bf = [], []
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        m = (phase >= lo) & (phase < hi)
        if m.sum():
            bp.append(0.5*(lo+hi)); bf.append(np.mean(flux[m]))
    bp, bf = np.array(bp), np.array(bf)

    # Box model
    half_ph = 0.5 * duration / period
    ph_model = np.linspace(-0.5, 0.5, 2000)
    fl_model = np.where(np.abs(ph_model) <= half_ph, 1.0 - depth, 1.0)

    q1, q99 = np.nanpercentile(flux, [0.5, 99.5])
    y_pad   = (q99 - q1) * 0.15
    y_lo    = min(q1 - y_pad, 1.0 - depth - y_pad * 0.5)
    y_hi    = q99 + y_pad

    fig = plt.figure(figsize=(14, 5.5))
    fig.patch.set_facecolor(_DARK)

    gs = gridspec.GridSpec(2, 2, figure=fig, width_ratios=[1.7, 1],
                           hspace=0.40, wspace=0.28)
    ax_fold   = fig.add_subplot(gs[:, 0])    # tall left
    ax_cnn    = fig.add_subplot(gs[0, 1])    # top-right
    ax_scores = fig.add_subplot(gs[1, 1])    # bottom-right

    # ── Phase-fold panel ─────────────────────────────────────────────────────
    _ax_dark(ax_fold)
    ax_fold.scatter(phase, flux, s=0.8, alpha=0.20,
                    color=_BLUE, rasterized=True, zorder=1)
    ax_fold.plot(bp, bf, "o", ms=3.5, color=_RED, zorder=4,
                 label="Binned avg")
    ax_fold.plot(ph_model, fl_model, color=_GREEN, lw=2.2, zorder=5,
                 label=f"BLS box (δ={depth*1e6:.0f} ppm)")
    ax_fold.axvspan(-half_ph, half_ph, alpha=0.10, color=_ORG, zorder=0)
    ax_fold.axhline(1.0, color="#555", lw=0.5, ls=":")
    ax_fold.set_xlim(-0.5, 0.5)
    ax_fold.set_ylim(y_lo, y_hi)
    ax_fold.set_xlabel("Orbital phase", fontsize=9)
    ax_fold.set_ylabel("Normalised flux", fontsize=9)
    ax_fold.set_title(f"{tic_id}  —  Phase fold  (P = {period:.4f} d)",
                      fontsize=10)
    ax_fold.legend(fontsize=8, facecolor="#1a1d27",
                   edgecolor="#444", labelcolor=_WHITE, loc="lower right")

    param_txt = (
        f"P  = {period:.5f} d\n"
        f"δ  = {depth*1e6:.1f} ppm\n"
        f"T  = {duration*24:.2f} h\n"
        f"t₀ = {t0:.4f} BTJD"
    )
    ax_fold.text(0.02, 0.04, param_txt, transform=ax_fold.transAxes,
                 va="bottom", ha="left", color=_WHITE, fontsize=8,
                 family="monospace",
                 bbox=dict(boxstyle="round,pad=0.4", facecolor="#1a1d27",
                           edgecolor="#555", alpha=0.85))

    # ── CNN input panel ───────────────────────────────────────────────────────
    _ax_dark(ax_cnn)
    ax_cnn.plot(ph_grid, grid_flux, color=_ORG, lw=1.2)
    ax_cnn.axhline(1.0, color="#555", lw=0.5, ls=":")
    ax_cnn.axvspan(-half_ph, half_ph, alpha=0.10, color=_GREEN)
    ax_cnn.set_xlim(-0.5, 0.5)
    ax_cnn.set_xlabel("Phase", fontsize=8)
    ax_cnn.set_ylabel("Flux (resampled)", fontsize=8)
    ax_cnn.set_title(f"CNN input  (p = {cnn_score_val:.3f})", fontsize=9)

    # Colour the title red/green by candidate status
    colour = _GREEN if cnn_score_val > _CNN_THRESH else _RED
    ax_cnn.title.set_color(colour)

    # ── Score bar panel ───────────────────────────────────────────────────────
    _ax_dark(ax_scores)
    labels   = ["SNR", "CNN score"]
    values   = [min(snr / 30, 1.0),     cnn_score_val]   # normalised to [0,1]
    raw_vals = [snr,                     cnn_score_val]
    threshs  = [_SNR_THRESH / 30,       _CNN_THRESH]
    colours  = [
        _GREEN if snr > _SNR_THRESH else _RED,
        _GREEN if cnn_score_val > _CNN_THRESH else _RED,
    ]

    bars = ax_scores.barh(labels, values, color=colours, alpha=0.85, height=0.5)
    for i, (bar, raw, thresh) in enumerate(zip(bars, raw_vals, threshs)):
        ax_scores.axvline(thresh, ymin=i/len(labels) + 0.05,
                          ymax=(i+1)/len(labels) - 0.05,
                          color=_WHITE, lw=1.2, ls="--", alpha=0.7)
        ax_scores.text(
            min(values[i], 0.95), i,
            f"  {raw:.2f}", va="center", ha="left",
            color=_WHITE, fontsize=8.5, fontweight="bold",
        )

    ax_scores.set_xlim(0, 1.0)
    ax_scores.set_xlabel("Normalised score", fontsize=8)
    ax_scores.set_title("Candidate gates", fontsize=9)

    # CANDIDATE / REJECTED stamp
    is_cand = cnn_score_val > _CNN_THRESH and snr > _SNR_THRESH
    stamp   = "✓ CANDIDATE" if is_cand else "✗ REJECTED"
    colour  = _GREEN        if is_cand else _RED
    ax_scores.text(0.98, -0.35, stamp, transform=ax_scores.transAxes,
                   ha="right", va="bottom", fontsize=12,
                   fontweight="bold", color=colour)

    # ── Save ──────────────────────────────────────────────────────────────────
    _PLOT_DIR.mkdir(parents=True, exist_ok=True)
    out = _PLOT_DIR / f"{tic_id}.png"
    fig.suptitle(
        f"Stage 2 Scoring  —  {tic_id}",
        color=_WHITE, fontsize=12, fontweight="bold", y=1.01,
    )
    fig.savefig(out, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    log.info("Candidate plot → %s", out)


# ============================================================================
# 6.  POPULATION SUMMARY PLOT
# ============================================================================

def plot_population_summary(df: pd.DataFrame) -> None:
    """
    2-panel population figure:
      Left  : CNN score vs SNR scatter, coloured by depth, with threshold lines
      Right : Score-distribution histograms (CNN score + SNR)
    Highlights confirmed candidates in a distinct marker style.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    fig.patch.set_facecolor(_DARK)
    _ax_dark(ax1); _ax_dark(ax2)

    ok    = df[df["status"] == "ok"].copy() if "status" in df.columns else df.copy()
    cands = ok[ok["is_candidate"] == 1]
    rest  = ok[ok["is_candidate"] == 0]

    # Left: scatter
    if len(rest):
        sc = ax1.scatter(
            rest["SNR"], rest["CNN_score"],
            c=np.log10(rest["depth"].clip(1e-7) * 1e6),
            cmap="plasma", s=20, alpha=0.65, edgecolors="none",
            vmin=1, vmax=5,
        )
        cbar = fig.colorbar(sc, ax=ax1)
        cbar.set_label("log₁₀(depth [ppm])", color=_WHITE, fontsize=8)
        cbar.ax.yaxis.set_tick_params(color=_WHITE)
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color=_WHITE)

    if len(cands):
        ax1.scatter(
            cands["SNR"], cands["CNN_score"],
            c=_GREEN, s=80, alpha=0.9,
            edgecolors=_WHITE, linewidths=0.6,
            zorder=5, marker="*", label=f"Candidates ({len(cands)})",
        )
        for _, row in cands.iterrows():
            ax1.annotate(
                row["TIC_ID"].replace("TIC_", ""),
                (row["SNR"], row["CNN_score"]),
                fontsize=6, color="#a8c7f5",
                xytext=(4, 2), textcoords="offset points",
            )

    # Threshold lines
    ax1.axhline(_CNN_THRESH, color=_GREEN, lw=1.0, ls="--", alpha=0.7,
                label=f"CNN threshold ({_CNN_THRESH})")
    ax1.axvline(_SNR_THRESH, color=_ORG,   lw=1.0, ls="--", alpha=0.7,
                label=f"SNR threshold ({_SNR_THRESH})")

    # Shade the candidate quadrant
    x_max = max(ok["SNR"].max() * 1.05, _SNR_THRESH * 1.5) if len(ok) else 20
    ax1.fill_between(
        [_SNR_THRESH, x_max], _CNN_THRESH, 1.0,
        alpha=0.06, color=_GREEN,
    )

    ax1.set_xlabel("Empirical SNR", fontsize=10)
    ax1.set_ylabel("CNN transit probability", fontsize=10)
    ax1.set_title("Stage 2 candidate population", fontsize=11)
    ax1.set_ylim(-0.02, 1.05)
    ax1.legend(fontsize=8, facecolor="#1a1d27",
               edgecolor="#444", labelcolor=_WHITE)

    # Right: histograms
    if len(ok):
        ax2.hist(ok["CNN_score"].dropna(), bins=30,
                 color=_BLUE, alpha=0.75, label="CNN score", density=True)
        ax2r = ax2.twinx()
        ax2r.set_facecolor(_DARK)
        ax2r.tick_params(colors=_WHITE, labelsize=8)
        ax2r.hist(ok["SNR"].clip(0, 50).dropna(), bins=30,
                  color=_ORG, alpha=0.55, label="SNR (clipped ≤50)",
                  density=True)
        ax2.axvline(_CNN_THRESH, color=_GREEN, lw=1.2, ls="--")
        ax2.set_xlabel("Score", fontsize=10)
        ax2.set_ylabel("Density (CNN)", fontsize=9)
        ax2r.set_ylabel("Density (SNR)", fontsize=9, color=_ORG)
        ax2.set_title("Score distributions", fontsize=11)

        # combined legend
        handles  = [
            plt.Line2D([0],[0], color=_BLUE,  lw=6, alpha=0.75, label="CNN score"),
            plt.Line2D([0],[0], color=_ORG,   lw=6, alpha=0.55, label="SNR (÷ 50)"),
            plt.Line2D([0],[0], color=_GREEN,  lw=1.5, ls="--",  label=f"CNN thresh ({_CNN_THRESH})"),
        ]
        ax2.legend(handles=handles, fontsize=8, facecolor="#1a1d27",
                   edgecolor="#444", labelcolor=_WHITE)

    summary_txt = (
        f"Total scored : {len(ok)}\n"
        f"Candidates   : {len(cands)}\n"
        f"Yield        : {100*len(cands)/max(len(ok),1):.1f} %"
    )
    ax1.text(0.02, 0.98, summary_txt, transform=ax1.transAxes,
             va="top", ha="left", color=_WHITE, fontsize=9,
             family="monospace",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#1a1d27",
                       edgecolor="#555", alpha=0.85))

    fig.tight_layout()
    out = CFG.PLOT_DIR / "stage2_population.png"
    fig.savefig(out, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    log.info("Population summary → %s", out)


# ============================================================================
# 7.  BATCH RUNNER
# ============================================================================

def score_batch(
    bls_rows:       pd.DataFrame,
    model:          TransitCNN,
    seq_len:        int,
    cnn_thresh:     float = _CNN_THRESH,
    snr_thresh:     float = _SNR_THRESH,
    overwrite:      bool  = False,
    n_cand_plots:   int   = 20,
) -> pd.DataFrame:
    """
    Score all rows in *bls_rows* and return the Stage 2 results table.

    Parameters
    ----------
    bls_rows       : DataFrame with BLS parameters (must have status='ok').
    model          : Loaded TransitCNN in eval mode.
    seq_len        : CNN input length (from config).
    cnn_thresh     : CNN probability threshold for candidacy.
    snr_thresh     : Empirical SNR threshold for candidacy.
    overwrite      : Recompute rows already present in the output CSV.
    n_cand_plots   : Max number of candidate PNGs to generate.

    Returns
    -------
    pd.DataFrame with columns matching _OUT_COLS + "status".
    """
    # Update global thresholds so plots reflect CLI values
    global _CNN_THRESH, _SNR_THRESH
    _CNN_THRESH = cnn_thresh
    _SNR_THRESH = snr_thresh

    _PLOT_DIR.mkdir(parents=True, exist_ok=True)
    (CFG.DATA_DIR / "results").mkdir(parents=True, exist_ok=True)

    # Load existing results for incremental mode
    if _OUT_CSV.exists() and not overwrite:
        existing  = pd.read_csv(_OUT_CSV)
        done_ids  = set(existing["TIC_ID"].astype(str))
        log.info("Resuming: %d rows already in %s.", len(done_ids), _OUT_CSV)
    else:
        existing  = pd.DataFrame(columns=_OUT_COLS + ["status"])
        done_ids  = set()

    new_records: list[dict] = []

    for _, bls_row in tqdm(bls_rows.iterrows(), total=len(bls_rows),
                           desc="Scoring", unit="star"):
        tic_id = str(bls_row["tic_id"])

        if tic_id in done_ids:
            log.debug("[%s] Already scored — skipping.", tic_id)
            continue

        # Validate BLS parameters
        try:
            period   = float(bls_row["period_d"])
            depth    = float(bls_row["depth"])
            duration = float(bls_row["duration_d"])
            t0       = float(bls_row["t0_btjd"])
        except (KeyError, ValueError, TypeError) as exc:
            log.warning("[%s] Bad BLS params: %s", tic_id, exc)
            new_records.append(_nan_row(tic_id, f"bad_bls: {exc}"))
            continue

        if not all(np.isfinite([period, depth, duration, t0])) \
                or period <= 0 or depth <= 0 or duration <= 0:
            log.warning("[%s] Non-finite or non-positive BLS params — skipping.", tic_id)
            new_records.append(_nan_row(tic_id, "invalid_bls_params"))
            continue

        lc_path = _CLEAN_LC_DIR / f"{tic_id}.csv"
        if not lc_path.exists():
            log.warning("[%s] Cleaned LC not found: %s", tic_id, lc_path)
            new_records.append(_nan_row(tic_id, "no_lc"))
            continue

        # Score
        try:
            record = score_one(tic_id, lc_path, period, depth, duration,
                               t0, model, seq_len)
            record["status"] = "ok"
        except Exception as exc:    # noqa: BLE001
            log.warning("[%s] Scoring failed: %s", tic_id, exc)
            record = _nan_row(tic_id, f"failed: {exc}")

        new_records.append(record)

    # Merge + save
    new_df = pd.DataFrame(new_records)
    all_df = pd.concat([existing, new_df], ignore_index=True)
    for col in _OUT_COLS + ["status"]:
        if col not in all_df.columns:
            all_df[col] = np.nan
    all_df = all_df[_OUT_COLS + ["status"]]
    all_df.to_csv(_OUT_CSV, index=False)
    log.info("Stage 2 CSV saved → %s  (%d rows total)", _OUT_CSV, len(all_df))

    # Diagnostic plots for confirmed candidates (from this batch)
    ok_new    = new_df[new_df.get("status", pd.Series(dtype=str)) == "ok"] \
        if "status" in new_df.columns else new_df
    candidates = ok_new[ok_new["is_candidate"] == 1].sort_values(
        "CNN_score", ascending=False
    )
    log.info("New candidates this run: %d / %d", len(candidates), len(ok_new))

    for i, (_, row) in enumerate(candidates.iterrows()):
        if i >= n_cand_plots:
            break
        lc_path = _CLEAN_LC_DIR / f"{row['TIC_ID']}.csv"
        if not lc_path.exists():
            continue
        try:
            plot_candidate(
                tic_id=row["TIC_ID"],
                lc_path=lc_path,
                period=row["period"],
                depth=row["depth"],
                duration=row["duration"],
                t0=row["t0"],
                snr=row["SNR"],
                cnn_score_val=row["CNN_score"],
                seq_len=seq_len,
            )
        except Exception as exc:    # noqa: BLE001
            log.warning("Candidate plot failed for %s: %s", row["TIC_ID"], exc)

    return all_df


def _nan_row(tic_id: str, status: str) -> dict:
    row = {c: np.nan for c in _OUT_COLS}
    row["TIC_ID"]  = tic_id
    row["status"]  = status
    row["is_candidate"] = 0
    return row


# ============================================================================
# 8.  SUMMARY PRINTER
# ============================================================================

def _print_summary(df: pd.DataFrame) -> None:
    ok = df[df["status"] == "ok"] if "status" in df.columns else df
    cands = ok[ok["is_candidate"] == 1] if "is_candidate" in ok.columns else pd.DataFrame()

    log.info(
        "\n%s\n"
        " Stage 2 Candidate Summary\n"
        "%s\n"
        "  Total scored     : %d\n"
        "  Status=ok        : %d\n"
        "  Transit candidates (CNN>%.2f AND SNR>%.1f): %d\n"
        "%s",
        "=" * 60, "─" * 60,
        len(df), len(ok),
        _CNN_THRESH, _SNR_THRESH, len(cands),
        "=" * 60,
    )

    if len(cands):
        log.info(
            "  Candidate list:\n%s",
            cands[["TIC_ID","period","depth","duration","SNR","CNN_score"]]
            .sort_values("CNN_score", ascending=False)
            .to_string(index=False),
        )
        log.info("  Full table → %s", _OUT_CSV)


# ============================================================================
# 9.  CLI
# ============================================================================

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage 2 scoring: CNN + SNR → transit candidates.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--bls-csv",    default=str(_BLS_CSV),     metavar="FILE",
                   help=f"BLS results CSV.  Default: {_BLS_CSV}")
    p.add_argument("--lc-dir",     default=str(_CLEAN_LC_DIR), metavar="DIR",
                   help=f"Cleaned LC directory.  Default: {_CLEAN_LC_DIR}")
    p.add_argument("--weights",    default=str(_WEIGHTS_PT),   metavar="FILE",
                   help=f"CNN weights .pt file.  Default: {_WEIGHTS_PT}")
    p.add_argument("--config",     default=str(_CONFIG_JSON),  metavar="FILE",
                   help=f"CNN config JSON.  Default: {_CONFIG_JSON}")
    p.add_argument("--n",          type=int,   default=None,   metavar="N",
                   help="Score first N rows (sorted by BLS power, desc).")
    p.add_argument("--tic",        nargs="+",  type=int, default=None,
                   metavar="TIC_ID", help="Score specific TIC IDs.")
    p.add_argument("--cnn-thresh", type=float, default=_CNN_THRESH,
                   metavar="P",
                   help=f"CNN probability threshold.  Default: {_CNN_THRESH}")
    p.add_argument("--snr-thresh", type=float, default=_SNR_THRESH,
                   metavar="SNR",
                   help=f"Empirical SNR threshold.  Default: {_SNR_THRESH}")
    p.add_argument("--n-plots",    type=int,   default=20,     metavar="N",
                   help="Max candidate plots to generate.  Default: 20")
    p.add_argument("--overwrite",  action="store_true", default=False,
                   help="Recompute rows already in the output CSV.")
    return p.parse_args()


def main() -> None:
    CFG.LOG_DIR.mkdir(parents=True, exist_ok=True)
    args = _parse_args()

    # ── Load BLS results ──────────────────────────────────────────────────────
    bls_csv = Path(args.bls_csv)
    if not bls_csv.exists():
        sys.exit(f"BLS results not found: {bls_csv}\nRun  python -m src.run_bls  first.")

    bls_df = pd.read_csv(bls_csv)
    bls_ok = bls_df[bls_df["status"] == "ok"].copy() \
        if "status" in bls_df.columns else bls_df.copy()
    log.info("BLS rows: %d total  /  %d with status=ok", len(bls_df), len(bls_ok))

    # ── Filters ───────────────────────────────────────────────────────────────
    if args.tic:
        tic_strs = {f"TIC_{t}" for t in args.tic}
        bls_ok   = bls_ok[bls_ok["tic_id"].isin(tic_strs)]
    else:
        bls_ok = bls_ok.sort_values("bls_power", ascending=False)
        if args.n:
            bls_ok = bls_ok.head(args.n)

    log.info("Scoring %d stars.", len(bls_ok))

    # ── Load CNN ──────────────────────────────────────────────────────────────
    model, seq_len = load_model(Path(args.weights), Path(args.config))

    # ── Score ─────────────────────────────────────────────────────────────────
    all_df = score_batch(
        bls_ok,
        model=model,
        seq_len=seq_len,
        cnn_thresh=args.cnn_thresh,
        snr_thresh=args.snr_thresh,
        overwrite=args.overwrite,
        n_cand_plots=args.n_plots,
    )

    _print_summary(all_df)

    # Population summary plot (whole scored set)
    try:
        plot_population_summary(all_df)
    except Exception as exc:   # noqa: BLE001
        log.warning("Population summary plot failed: %s", exc)


if __name__ == "__main__":
    main()
