"""
plot_phase_folds.py
-------------------
Phase 4 of the transit-detection pipeline: visual inspection plots.

For every star in the BLS results table (data/results/bls_results.csv) this
script:

  1. Loads the cleaned light curve  (data/clean/lightcurves/TIC_<id>.csv)
  2. Phase-folds on the BLS best-fit period P and mid-transit time t₀
  3. Computes a phase-binned light curve (adjustable bin width)
  4. Constructs the BLS box-model overlay from depth δ and duration T
  5. Produces a 2-panel figure:
       Top   : full time-series with transit markers at multiples of P
       Bottom : phase-folded light curve + binned average + BLS box model
  6. Saves each figure as  plots/phase_folds/TIC_<id>.png

No classification or ML — this is purely for visual inspection.

Usage
-----
    python -m src.plot_phase_folds                  # all BLS results
    python -m src.plot_phase_folds --n 20           # first 20
    python -m src.plot_phase_folds --tic 468184895  # specific TIC IDs
    python -m src.plot_phase_folds --min-snr 5      # only snr >= 5
    python -m src.plot_phase_folds --min-power 10   # only high-power candidates
    python -m src.plot_phase_folds --overwrite      # re-plot existing PNGs

Output
------
    plots/phase_folds/TIC_<id>.png    — one figure per star
    plots/phase_folds/_summary.png    — SNR vs BLS-power scatter overview

Dependencies (all in requirements.txt)
---------------------------------------
    numpy>=1.24, pandas>=2.0, matplotlib>=3.7, scipy>=1.11, tqdm>=4.65
"""

from __future__ import annotations

import argparse
import logging
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from scipy.signal import medfilt
from tqdm import tqdm

from src.config import CFG

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(CFG.LOG_DIR / "plot_phase_folds.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)
warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_CLEAN_LC_DIR:  Path = CFG.CLEAN_DIR / "lightcurves"
_BLS_CSV:       Path = CFG.DATA_DIR  / "results" / "bls_results.csv"
_OUT_DIR:       Path = CFG.PLOT_DIR  / "phase_folds"

# ---------------------------------------------------------------------------
# Plot aesthetics — single source of truth
# ---------------------------------------------------------------------------

_STYLE = {
    # colours
    "c_scatter":  "#4C72B0",   # raw 2-min cadence
    "c_bin":      "#C44E52",   # phase-binned points
    "c_model":    "#2ca02c",   # BLS box model
    "c_ts_lc":    "#4C72B0",   # time-series line
    "c_transit":  "#DD8452",   # transit marker shading
    "c_ingress":  "#8172B2",   # ingress / egress verticals
    # sizes / widths
    "s_scatter":  1.0,
    "lw_model":   2.0,
    "lw_ts":      0.5,
    "alpha_raw":  0.22,
    "alpha_ts":   0.40,
    "alpha_shade":0.13,
    # figure
    "dpi":        150,
    "fig_w":      13,
    "fig_h":      9,
}

# Default phase-bin width in units of the period (adjustable via --bin-width)
_DEFAULT_BIN_WIDTH: float = 0.005    # 0.5 % of period


# ---------------------------------------------------------------------------
# Phase-fold helper
# ---------------------------------------------------------------------------

def phase_fold(
    time: np.ndarray,
    period: float,
    t0: float,
) -> np.ndarray:
    """
    Return phases in [-0.5, +0.5) with the transit centred at 0.

    Parameters
    ----------
    time:    Time array in days (BTJD).
    period:  Orbital period in days.
    t0:      Mid-transit reference time in days (BTJD).
    """
    phase = ((time - t0) / period) % 1.0
    phase[phase > 0.5] -= 1.0
    return phase


# ---------------------------------------------------------------------------
# Phase-bin helper
# ---------------------------------------------------------------------------

def phase_bin(
    phase: np.ndarray,
    flux:  np.ndarray,
    ferr:  np.ndarray | None,
    bin_width: float = _DEFAULT_BIN_WIDTH,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute phase-binned flux with propagated uncertainty.

    Parameters
    ----------
    phase:     Phase array in [-0.5, 0.5).
    flux:      Flux array (normalised).
    ferr:      Flux-error array, or None (falls back to scatter).
    bin_width: Bin width in phase units (default 0.5 % of period).

    Returns
    -------
    bin_phase, bin_flux, bin_err  — centres, means, uncertainties of each bin.
    """
    edges = np.arange(-0.5, 0.5 + bin_width, bin_width)
    bin_phase, bin_flux, bin_err = [], [], []

    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (phase >= lo) & (phase < hi)
        n = int(mask.sum())
        if n == 0:
            continue
        f_vals = flux[mask]
        bin_phase.append(0.5 * (lo + hi))
        bin_flux.append(float(np.mean(f_vals)))
        if ferr is not None and np.any(np.isfinite(ferr[mask])):
            # Quadrature mean of individual errors, divided by sqrt(n)
            e_vals = ferr[mask]
            e_vals = np.where(np.isfinite(e_vals) & (e_vals > 0), e_vals, np.nanmedian(e_vals))
            bin_err.append(float(np.sqrt(np.sum(e_vals**2)) / n))
        else:
            bin_err.append(float(np.std(f_vals) / np.sqrt(n)))

    return (
        np.array(bin_phase),
        np.array(bin_flux),
        np.array(bin_err),
    )


# ---------------------------------------------------------------------------
# BLS box model
# ---------------------------------------------------------------------------

def bls_box_model(
    phase: np.ndarray,
    depth: float,
    duration_d: float,
    period_d: float,
) -> np.ndarray:
    """
    Evaluate the BLS box-transit model on a phase grid.

    The model is 1.0 outside transit and (1.0 - depth) inside,
    where the transit half-width in phase is  (duration_d / period_d) / 2.

    Parameters
    ----------
    phase:       Phase values in [-0.5, 0.5).
    depth:       Transit depth δ (fractional).
    duration_d:  Transit duration in days.
    period_d:    Orbital period in days.
    """
    half_dur_phase = 0.5 * duration_d / period_d
    model = np.where(np.abs(phase) <= half_dur_phase, 1.0 - depth, 1.0)
    return model


# ---------------------------------------------------------------------------
# Main plot function
# ---------------------------------------------------------------------------

def plot_one(
    tic_id:     str,
    lc_path:    Path,
    period:     float,
    depth:      float,
    duration:   float,
    t0:         float,
    bls_power:  float,
    snr:        float,
    out_path:   Path,
    bin_width:  float = _DEFAULT_BIN_WIDTH,
) -> None:
    """
    Produce a 2-panel inspection figure for one star.

    Top panel   : full light curve (time-series) with vertical lines at
                  each predicted transit centre.
    Bottom panel: phase-folded light curve, phase-binned average,
                  and BLS box-model overlay.

    Parameters
    ----------
    tic_id:    Human-readable identifier (e.g. "TIC_468184895").
    lc_path:   Path to cleaned CSV (time, flux_norm, flux_err_norm, sg_trend).
    period:    BLS best-fit period [d].
    depth:     BLS transit depth δ (fractional).
    duration:  BLS transit duration [d].
    t0:        BLS mid-transit reference time [BTJD].
    bls_power: BLS peak power (SNR objective).
    snr:       depth / depth_err.
    out_path:  Destination PNG path.
    bin_width: Phase-bin width in phase units.
    """
    # ── Load light curve ──────────────────────────────────────────────────────
    df = pd.read_csv(lc_path)
    df = df.dropna(subset=["time", "flux_norm"]).sort_values("time").reset_index(drop=True)

    t    = df["time"].to_numpy(dtype=np.float64)
    flux = df["flux_norm"].to_numpy(dtype=np.float64)
    ferr = (df["flux_err_norm"].to_numpy(dtype=np.float64)
            if "flux_err_norm" in df.columns
            else None)

    if ferr is not None:
        bad = ~(np.isfinite(ferr) & (ferr > 0))
        if bad.any():
            med = float(np.nanmedian(ferr[~bad])) if (~bad).any() else 1e-3
            ferr[bad] = med

    n_pts      = len(t)
    time_span  = float(t.max() - t.min())
    depth_ppm  = depth * 1e6

    # ── Phase fold ────────────────────────────────────────────────────────────
    phase = phase_fold(t, period, t0)

    # ── Phase bins ────────────────────────────────────────────────────────────
    bp, bf, be = phase_bin(phase, flux, ferr, bin_width=bin_width)

    # ── BLS model on a dense phase grid ───────────────────────────────────────
    ph_model = np.linspace(-0.5, 0.5, 4000)
    fl_model = bls_box_model(ph_model, depth, duration, period)

    # ── Running median for time-series panel (smooth trend visibility) ────────
    smooth_win = min(201, n_pts // 4 | 1)   # odd, at most n/4
    ts_smooth  = medfilt(flux, kernel_size=smooth_win)

    # ── Transit centre times within the observed baseline ─────────────────────
    k_lo = int(np.floor((t.min() - t0) / period))
    k_hi = int(np.ceil( (t.max() - t0) / period)) + 1
    transit_times = np.array([t0 + k * period for k in range(k_lo, k_hi + 1)])
    transit_times = transit_times[(transit_times >= t.min()) & (transit_times <= t.max())]

    # ── Flux axis limits (robust) ─────────────────────────────────────────────
    q1, q99 = np.nanpercentile(flux, [0.5, 99.5])
    y_pad   = (q99 - q1) * 0.15
    y_lo    = q1 - y_pad
    y_hi    = q99 + y_pad
    # Make sure the box model bottom is visible
    model_bottom = 1.0 - depth
    if model_bottom < y_lo:
        y_lo = model_bottom - y_pad * 0.5

    # ── Build figure ──────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(_STYLE["fig_w"], _STYLE["fig_h"]), constrained_layout=False)
    fig.patch.set_facecolor("#0f1117")          # dark background

    gs = gridspec.GridSpec(
        3, 1,
        figure=fig,
        height_ratios=[1.0, 0.05, 1.6],        # top | spacer | bottom
        hspace=0.0,
    )
    ax_ts   = fig.add_subplot(gs[0])            # full time-series
    ax_fold = fig.add_subplot(gs[2])            # phase fold

    _axis_style(ax_ts)
    _axis_style(ax_fold)

    # ─────────────────────────── TOP PANEL: time series ─────────────────────
    ax_ts.scatter(
        t, flux,
        s=_STYLE["s_scatter"], alpha=_STYLE["alpha_ts"],
        color=_STYLE["c_ts_lc"], rasterized=True, zorder=1,
    )
    ax_ts.plot(t, ts_smooth, color="#a8c7f5", lw=0.7, alpha=0.7, zorder=2)

    # Shade half-duration around each predicted transit
    half_dur = 0.5 * duration
    for tc in transit_times:
        ax_ts.axvspan(
            tc - half_dur, tc + half_dur,
            alpha=_STYLE["alpha_shade"], color=_STYLE["c_transit"], zorder=0,
        )

    ax_ts.set_xlim(t.min(), t.max())
    ax_ts.set_ylim(y_lo, y_hi)
    ax_ts.set_ylabel("Normalised flux", color="white", fontsize=10)
    ax_ts.set_xlabel("")
    ax_ts.xaxis.set_visible(False)
    ax_ts.text(
        0.01, 0.96,
        f"Full light curve  ({n_pts:,} pts  ·  {time_span:.1f} d baseline)",
        transform=ax_ts.transAxes, va="top", ha="left",
        color="#a8c7f5", fontsize=8.5,
    )
    # Transit count label
    ax_ts.text(
        0.99, 0.96,
        f"{len(transit_times)} predicted transit(s)  shown",
        transform=ax_ts.transAxes, va="top", ha="right",
        color=_STYLE["c_transit"], fontsize=8,
    )

    # ─────────────────────────── BOTTOM PANEL: phase fold ───────────────────
    # Raw scatter
    ax_fold.scatter(
        phase, flux,
        s=_STYLE["s_scatter"], alpha=_STYLE["alpha_raw"],
        color=_STYLE["c_scatter"], rasterized=True, zorder=1, label="2-min cadence",
    )

    # Phase-binned average with error bars
    ax_fold.errorbar(
        bp, bf, yerr=be,
        fmt="o", ms=4.5, color=_STYLE["c_bin"],
        elinewidth=1.0, capsize=2.5, ecolor="#e88080",
        zorder=4, label=f"Binned  (Δφ = {bin_width:.3f})",
    )

    # BLS box model
    ax_fold.plot(
        ph_model, fl_model,
        color=_STYLE["c_model"], lw=_STYLE["lw_model"],
        zorder=5, label=f"BLS box model  (δ = {depth_ppm:.0f} ppm)",
    )

    # Transit-window shading and ingress/egress lines
    half_dur_ph = 0.5 * duration / period
    ax_fold.axvspan(
        -half_dur_ph, half_dur_ph,
        alpha=_STYLE["alpha_shade"] * 1.5, color=_STYLE["c_transit"], zorder=0,
    )
    for x in (-half_dur_ph, half_dur_ph):
        ax_fold.axvline(x, color=_STYLE["c_ingress"], lw=0.9, ls="--", alpha=0.7)

    ax_fold.axhline(1.0,           color="white",           lw=0.5, ls=":", alpha=0.4)
    ax_fold.axhline(1.0 - depth,   color=_STYLE["c_model"], lw=0.8, ls="--", alpha=0.6)

    ax_fold.set_xlim(-0.5, 0.5)
    ax_fold.set_ylim(y_lo, y_hi)
    ax_fold.set_xlabel("Orbital phase  (transit at 0)", color="white", fontsize=10)
    ax_fold.set_ylabel("Normalised flux", color="white", fontsize=10)

    legend = ax_fold.legend(
        loc="lower right", fontsize=8.5,
        facecolor="#1a1d27", edgecolor="#444", labelcolor="white",
        markerscale=3,
    )

    # Annotation box: BLS parameters
    param_txt = (
        f"P  = {period:.5f} d\n"
        f"δ  = {depth_ppm:.1f} ppm\n"
        f"T  = {duration * 24:.2f} h\n"
        f"t₀ = {t0:.4f} BTJD\n"
        f"SNR      = {snr:.1f}\n"
        f"BLS pwr  = {bls_power:.2f}"
    )
    ax_fold.text(
        0.01, 0.04, param_txt,
        transform=ax_fold.transAxes,
        va="bottom", ha="left",
        color="white", fontsize=8.5,
        bbox=dict(
            boxstyle="round,pad=0.5",
            facecolor="#1a1d27",
            edgecolor="#555",
            alpha=0.85,
        ),
        family="monospace",
    )

    # ── Super-title ───────────────────────────────────────────────────────────
    fig.suptitle(
        f"{tic_id}   —   Phase-folded TESS 2-min light curve",
        color="white", fontsize=13, fontweight="bold", y=0.98,
    )

    # ── Save ──────────────────────────────────────────────────────────────────
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        out_path,
        dpi=_STYLE["dpi"],
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
    )
    plt.close(fig)


# ---------------------------------------------------------------------------
# Shared axis styling helper
# ---------------------------------------------------------------------------

def _axis_style(ax: plt.Axes) -> None:
    """Apply dark-theme styling to an axes object."""
    ax.set_facecolor("#0f1117")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    ax.tick_params(colors="white", which="both", labelsize=8)
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.grid(True, color="#2a2d3a", linewidth=0.4, linestyle="--")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.4f"))


# ---------------------------------------------------------------------------
# Summary scatter plot (overview of the full candidate list)
# ---------------------------------------------------------------------------

def plot_summary(df: pd.DataFrame) -> None:
    """
    SNR vs BLS-power scatter coloured by transit depth.

    Gives a quick at-a-glance overview of the whole candidate population.
    """
    ok = df[df["status"] == "ok"].copy()
    if ok.empty:
        log.warning("No 'ok' rows in BLS results — skipping summary plot.")
        return

    fig, ax = plt.subplots(figsize=(9, 6))
    fig.patch.set_facecolor("#0f1117")
    _axis_style(ax)

    sc = ax.scatter(
        ok["bls_power"], ok["snr"],
        c=np.log10(ok["depth"].clip(1e-6) * 1e6),   # log10(depth ppm)
        cmap="plasma", s=30, alpha=0.8, edgecolors="none",
    )
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("log₁₀(depth [ppm])", color="white", fontsize=9)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

    ax.set_xlabel("BLS power (SNR objective)", color="white", fontsize=10)
    ax.set_ylabel("Depth SNR  (δ / σ_δ)", color="white", fontsize=10)
    ax.set_title("BLS candidate overview", color="white", fontsize=12)

    # Label top-10 by power
    top10 = ok.nlargest(10, "bls_power")
    for _, row in top10.iterrows():
        ax.annotate(
            row["tic_id"].replace("TIC_", ""),
            (row["bls_power"], row["snr"]),
            fontsize=6.5, color="#a8c7f5",
            xytext=(4, 2), textcoords="offset points",
        )

    out = _OUT_DIR / "_summary.png"
    fig.tight_layout()
    fig.savefig(out, dpi=_STYLE["dpi"], facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    log.info("Summary scatter saved → %s", out)


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def plot_all(
    rows:       pd.DataFrame,
    bin_width:  float = _DEFAULT_BIN_WIDTH,
    overwrite:  bool  = False,
) -> dict[str, int]:
    """
    Generate phase-fold plots for every row in *rows*.

    Parameters
    ----------
    rows:      Subset of the BLS results table to plot.
    bin_width: Phase-bin width in phase units.
    overwrite: If False, skip stars whose PNG already exists.

    Returns
    -------
    dict with keys ``plotted``, ``skipped``, ``failed``.
    """
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    counts = {"plotted": 0, "skipped": 0, "failed": 0}

    for _, row in tqdm(rows.iterrows(), total=len(rows),
                       desc="Plotting phase folds", unit="star"):
        tic_id  = str(row["tic_id"])
        out_png = _OUT_DIR / f"{tic_id}.png"

        # ── Cache hit ────────────────────────────────────────────────────────
        if out_png.exists() and not overwrite:
            log.debug("[%s] PNG exists — skipping.", tic_id)
            counts["skipped"] += 1
            continue

        # ── Validate BLS parameters ──────────────────────────────────────────
        try:
            period   = float(row["period_d"])
            depth    = float(row["depth"])
            duration = float(row["duration_d"])
            t0       = float(row["t0_btjd"])
            power    = float(row["bls_power"])
            snr      = float(row["snr"])
        except (KeyError, ValueError, TypeError) as exc:
            log.warning("[%s] Bad BLS parameters: %s", tic_id, exc)
            counts["failed"] += 1
            continue

        if not all(np.isfinite([period, depth, duration, t0])):
            log.warning("[%s] NaN BLS parameter — skipping.", tic_id)
            counts["failed"] += 1
            continue

        if period <= 0 or depth <= 0 or duration <= 0:
            log.warning(
                "[%s] Non-positive parameter (P=%.4f, δ=%.6f, T=%.4f) — skipping.",
                tic_id, period, depth, duration,
            )
            counts["failed"] += 1
            continue

        # ── Locate cleaned light curve ────────────────────────────────────────
        lc_path = _CLEAN_LC_DIR / f"{tic_id}.csv"
        if not lc_path.exists():
            log.warning("[%s] Cleaned CSV not found: %s", tic_id, lc_path)
            counts["failed"] += 1
            continue

        # ── Plot ──────────────────────────────────────────────────────────────
        try:
            plot_one(
                tic_id=tic_id,
                lc_path=lc_path,
                period=period,
                depth=depth,
                duration=duration,
                t0=t0,
                bls_power=power,
                snr=snr,
                out_path=out_png,
                bin_width=bin_width,
            )
            log.info("[%s] Saved → %s", tic_id, out_png)
            counts["plotted"] += 1
        except Exception as exc:    # noqa: BLE001
            log.warning("[%s] Plot failed: %s", tic_id, exc)
            counts["failed"] += 1

    return counts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate phase-fold inspection plots from BLS results.\n"
            "Output: plots/phase_folds/TIC_<id>.png"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--bls-csv",
        default=str(_BLS_CSV),
        metavar="FILE",
        help=f"BLS results CSV.  Default: {_BLS_CSV}",
    )
    parser.add_argument(
        "--lc-dir",
        default=str(_CLEAN_LC_DIR),
        metavar="DIR",
        help=f"Cleaned light-curve directory.  Default: {_CLEAN_LC_DIR}",
    )
    parser.add_argument(
        "--n",
        type=int, default=None, metavar="N",
        help="Plot only the first N rows (sorted by BLS power, descending).",
    )
    parser.add_argument(
        "--tic",
        nargs="+", type=int, default=None, metavar="TIC_ID",
        help="Plot specific TIC IDs (overrides --n).",
    )
    parser.add_argument(
        "--min-snr",
        type=float, default=None, metavar="SNR",
        help="Only plot rows with SNR >= this value.",
    )
    parser.add_argument(
        "--min-power",
        type=float, default=None, metavar="POWER",
        help="Only plot rows with bls_power >= this value.",
    )
    parser.add_argument(
        "--bin-width",
        type=float, default=_DEFAULT_BIN_WIDTH, metavar="PHASE",
        dest="bin_width",
        help=(
            f"Phase-bin width in phase units [0, 1].\n"
            f"Smaller = more bins = noisier but higher resolution.\n"
            f"Default: {_DEFAULT_BIN_WIDTH}"
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true", default=False,
        help="Re-generate plots even if the PNG already exists.",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true", default=False,
        help="Skip the population summary scatter plot.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # ── Load BLS results ──────────────────────────────────────────────────────
    bls_csv = Path(args.bls_csv)
    if not bls_csv.exists():
        sys.exit(
            f"[plot_phase_folds] BLS results not found: {bls_csv}\n"
            "Run  python -m src.run_bls  first."
        )

    bls_df = pd.read_csv(bls_csv)
    log.info("Loaded %d BLS rows from %s", len(bls_df), bls_csv)

    # Keep only successfully processed rows
    ok_mask = bls_df["status"] == "ok" if "status" in bls_df.columns \
        else pd.Series(True, index=bls_df.index)
    bls_df = bls_df[ok_mask].copy()
    log.info("  %d rows with status='ok'", len(bls_df))

    if bls_df.empty:
        sys.exit("[plot_phase_folds] No 'ok' BLS rows to plot.")

    # ── Filters ───────────────────────────────────────────────────────────────
    if args.tic:
        tic_strs = {f"TIC_{tid}" for tid in args.tic}
        bls_df = bls_df[bls_df["tic_id"].isin(tic_strs)]
        log.info("After --tic filter: %d rows", len(bls_df))
    else:
        if args.min_snr is not None:
            bls_df = bls_df[bls_df["snr"] >= args.min_snr]
            log.info("After --min-snr %.1f: %d rows", args.min_snr, len(bls_df))
        if args.min_power is not None:
            bls_df = bls_df[bls_df["bls_power"] >= args.min_power]
            log.info("After --min-power %.1f: %d rows", args.min_power, len(bls_df))

        # Sort by BLS power descending (best candidates first)
        bls_df = bls_df.sort_values("bls_power", ascending=False)

        if args.n is not None:
            bls_df = bls_df.head(args.n)
            log.info("After --n %d: %d rows", args.n, len(bls_df))

    if bls_df.empty:
        sys.exit("[plot_phase_folds] No rows remain after filters.")

    # ── Summary scatter (before per-star plots) ───────────────────────────────
    if not args.no_summary:
        full_ok = pd.read_csv(bls_csv)
        full_ok = full_ok[full_ok.get("status", pd.Series("ok")) == "ok"] \
            if "status" in full_ok.columns else full_ok
        try:
            plot_summary(full_ok)
        except Exception as exc:   # noqa: BLE001
            log.warning("Summary plot failed: %s", exc)

    # ── Per-star plots ────────────────────────────────────────────────────────
    # Override lc dir if user specified
    global _CLEAN_LC_DIR
    _CLEAN_LC_DIR = Path(args.lc_dir)

    counts = plot_all(bls_df, bin_width=args.bin_width, overwrite=args.overwrite)

    # ── Final report ──────────────────────────────────────────────────────────
    log.info(
        "\n%s\n"
        "[plot_phase_folds] Done\n"
        "%s\n"
        "  Plotted : %d\n"
        "  Skipped : %d  (already existed)\n"
        "  Failed  : %d\n"
        "  Output  : %s\n"
        "%s",
        "=" * 50, "─" * 50,
        counts["plotted"], counts["skipped"], counts["failed"],
        _OUT_DIR, "=" * 50,
    )


if __name__ == "__main__":
    main()
