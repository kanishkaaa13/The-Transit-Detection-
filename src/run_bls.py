"""
run_bls.py
----------
Phase 3 of the transit-detection pipeline: Box Least Squares (BLS)
periodogram search on cleaned, detrended TESS light curves.

For every cleaned CSV the script:
  1. Loads  time / flux_norm / flux_err_norm
  2. Converts time to an astropy Time object (BTJD format)
  3. Builds an astropy.timeseries.BoxLeastSquares model
  4. Searches periods  [P_min, P_max]  on a frequency grid with
     ``minimum_n_transit`` transits required per period
  5. Extracts the best-fit parameters at the peak power:
       - P        best period   [d]
       - depth    transit depth δ  (fractional, 0 < δ < 1)
       - duration transit duration T  [d]
       - t0       mid-transit reference time  [BTJD]
       - power    BLS power (signal-detection efficiency, SDE proxy)
       - snr      depth / depth_err  (signal-to-noise)
  6. Appends one row per star to ``data/results/bls_results.csv``
  7. Saves a diagnostic phase-fold plot for the top N stars by BLS power
     to ``plots/bls_fold_TIC_<id>.png``

Output file (data/results/bls_results.csv)
------------------------------------------
Columns:
  tic_id, period_d, depth, duration_d, t0_btjd, bls_power, snr,
  n_cadences, time_span_d, status

Usage
-----
    python -m src.run_bls                      # all cleaned CSVs
    python -m src.run_bls --n 20               # first 20 stars
    python -m src.run_bls --tic 468184895 ...  # specific TIC IDs
    python -m src.run_bls --p-min 1.0 --p-max 10.0   # custom period range
    python -m src.run_bls --overwrite          # recompute existing rows

Dependencies (all in requirements.txt)
---------------------------------------
    astropy>=5.0, numpy>=1.24, pandas>=2.0,
    matplotlib>=3.7, scipy>=1.11, tqdm>=4.65
"""

from __future__ import annotations

import argparse
import logging
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tqdm import tqdm

# astropy BLS — primary dependency of this module
try:
    from astropy import units as u
    from astropy.time import Time
    from astropy.timeseries import BoxLeastSquares
except ImportError as exc:
    sys.exit(
        "astropy is not installed or outdated. Run:\n"
        "  pip install 'astropy>=5.0'\n"
        f"Original error: {exc}"
    )

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
        logging.FileHandler(CFG.LOG_DIR / "run_bls.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

_CLEAN_LC_DIR: Path = CFG.CLEAN_DIR / "lightcurves"    # input CSVs
_RESULTS_DIR:  Path = CFG.DATA_DIR  / "results"        # output directory
_RESULTS_CSV:  Path = _RESULTS_DIR  / "bls_results.csv"
_PLOT_DIR:     Path = CFG.PLOT_DIR                      # diagnostic plots

# ── BLS search grid defaults ──────────────────────────────────────────────
_P_MIN:              float = 0.5    # days — minimum period
_P_MAX:              float = 15.0   # days — maximum period
_MIN_N_TRANSIT:      int   = 3      # require at least this many transits
_DURATION_GRID_LEN:  int   = 20     # number of trial durations to test
_FREQ_FACTOR:        float = 10.0   # oversampling relative to the BLS default

# ── Duration grid (linear, fraction of period) ───────────────────────────
# 0.01 P → 0.15 P covers durations from ~7 min (P=0.5d) to 54 h (P=15d)
_DUR_MIN_FRAC: float = 0.01
_DUR_MAX_FRAC: float = 0.15

# ── Results output columns ────────────────────────────────────────────────
_RESULT_COLS: list[str] = [
    "tic_id", "period_d", "depth", "duration_d", "t0_btjd",
    "bls_power", "snr", "n_cadences", "time_span_d", "status",
]


# ---------------------------------------------------------------------------
# Duration grid helper
# ---------------------------------------------------------------------------

def _duration_grid(p_min: float, p_max: float, n: int = _DURATION_GRID_LEN) -> np.ndarray:
    """
    Build a 1-D array of trial transit durations [days].

    The grid spans from  _DUR_MIN_FRAC * P_min  to  _DUR_MAX_FRAC * P_max,
    spaced uniformly on a log scale so that short and long durations are
    sampled equally well.
    """
    d_lo = _DUR_MIN_FRAC * p_min   # e.g. 0.01 × 0.5 d  ≈ 7.2 min
    d_hi = _DUR_MAX_FRAC * p_max   # e.g. 0.15 × 15 d   = 2.25 d
    return np.geomspace(d_lo, d_hi, n)


# ---------------------------------------------------------------------------
# Period grid helper
# ---------------------------------------------------------------------------

def _period_grid(
    t: np.ndarray,
    p_min: float,
    p_max: float,
    min_n_transit: int = _MIN_N_TRANSIT,
) -> np.ndarray:
    """
    Build an evenly-spaced-in-frequency period grid guaranteed to produce
    at least *min_n_transit* transits within the observed baseline.

    The Nyquist-like frequency resolution is:
        df = 1 / (time_span * frequency_factor)

    We also enforce that p_max ≤ time_span / min_n_transit so that every
    period in the grid actually permits the minimum required transit count.
    """
    time_span = float(t.max() - t.min())
    if time_span <= 0:
        raise ValueError("Time array has zero or negative span.")

    # Cap p_max so we always have ≥ min_n_transit transits
    p_max_eff = min(p_max, time_span / min_n_transit)
    if p_max_eff < p_min:
        raise ValueError(
            f"Time span ({time_span:.1f} d) is too short to fit "
            f"{min_n_transit} transits at P_min={p_min} d."
        )

    f_min = 1.0 / p_max_eff
    f_max = 1.0 / p_min
    df    = 1.0 / (time_span * _FREQ_FACTOR)
    n_f   = int(np.ceil((f_max - f_min) / df)) + 1

    freqs   = np.linspace(f_min, f_max, n_f)
    periods = 1.0 / freqs
    return np.sort(periods)          # ascending periods


# ---------------------------------------------------------------------------
# Core BLS runner
# ---------------------------------------------------------------------------

def run_bls_one(
    csv_path:      Path,
    p_min:         float = _P_MIN,
    p_max:         float = _P_MAX,
    min_n_transit: int   = _MIN_N_TRANSIT,
) -> dict:
    """
    Run a full BLS periodogram search on one cleaned light-curve CSV.

    Parameters
    ----------
    csv_path      : Path to cleaned CSV (time, flux_norm, flux_err_norm, …).
    p_min         : Minimum trial period in days.
    p_max         : Maximum trial period in days.
    min_n_transit : Minimum number of transits required per period.

    Returns
    -------
    dict with keys matching *_RESULT_COLS*.
    """
    tic_id = csv_path.stem   # "TIC_<number>"

    # ── 1. Load ──────────────────────────────────────────────────────────────
    df = pd.read_csv(csv_path)
    required = {"time", "flux_norm"}
    if not required.issubset(df.columns):
        raise ValueError(
            f"{csv_path.name}: missing columns {required - set(df.columns)}"
        )

    df = df.dropna(subset=["time", "flux_norm"]).sort_values("time").reset_index(drop=True)
    if len(df) < 50:
        raise ValueError(f"Only {len(df)} usable cadences — skipping.")

    t     = df["time"].to_numpy(dtype=np.float64)
    flux  = df["flux_norm"].to_numpy(dtype=np.float64)

    # Use flux_err_norm if present; otherwise estimate from scatter
    if "flux_err_norm" in df.columns:
        ferr = df["flux_err_norm"].to_numpy(dtype=np.float64)
        # Replace any NaN / non-positive errors with the median
        med_err = float(np.nanmedian(ferr[ferr > 0])) if np.any(ferr > 0) else 1e-3
        ferr = np.where(np.isfinite(ferr) & (ferr > 0), ferr, med_err)
    else:
        # Rough scatter estimate from consecutive differences
        ferr = np.full(len(flux), np.std(np.diff(flux)) / np.sqrt(2))

    n_cadences  = len(t)
    time_span_d = float(t.max() - t.min())

    # ── 2. Build period & duration grids ─────────────────────────────────────
    try:
        periods = _period_grid(t, p_min, p_max, min_n_transit)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    # Duration grid: max duration must be strictly < the shortest period
    # (astropy BLS requirement). We cap at 0.9 × min(periods) for safety.
    p_min_eff = float(periods.min())
    durations = _duration_grid(p_min_eff, p_max)
    durations = durations[durations < 0.9 * p_min_eff]  # enforce constraint
    if len(durations) == 0:
        # Fallback: single duration = 2% of shortest period
        durations = np.array([0.02 * p_min_eff])

    log.debug(
        "[%s] BLS grid: %d periods [%.2f–%.2f d], %d durations",
        tic_id, len(periods), periods.min(), periods.max(), len(durations),
    )

    # ── 3. Run BLS ────────────────────────────────────────────────────────────
    # BTJD = BJD - 2457000.  astropy Time does not know 'btjd' natively,
    # so we convert to JD and carry the offset.
    _BTJD_OFFSET = 2_457_000.0
    t_jd    = t + _BTJD_OFFSET
    t_ap    = Time(t_jd, format="jd", scale="tdb")
    flux_ap = flux * u.dimensionless_unscaled
    ferr_ap = ferr * u.dimensionless_unscaled

    bls = BoxLeastSquares(t_ap, flux_ap, dy=ferr_ap)

    # Pass durations as a Quantity in days
    result = bls.power(
        periods * u.day,
        durations * u.day,
        method="fast",          # O(N·P) — numerically equivalent to full
        objective="snr",        # maximise depth / depth_err (less biased than likelihood)
    )

    # ── 4. Extract best parameters ────────────────────────────────────────────
    best_idx = int(np.argmax(result.power))

    best_period   = float(result.period[best_idx].to(u.day).value)
    best_power    = float(result.power[best_idx])

    # BLS stats at the peak period
    stats = bls.compute_stats(
        result.period[best_idx],
        result.duration[best_idx],
        result.transit_time[best_idx],
    )

    best_depth    = float(stats["depth"][0])          # transit depth δ
    best_depth_err = float(stats["depth"][1])          # 1-σ uncertainty on δ
    best_duration = float(result.duration[best_idx].to(u.day).value)
    best_t0       = float(result.transit_time[best_idx].jd) - _BTJD_OFFSET  # back to BTJD

    # SNR = depth / depth_err  (guard against zero)
    snr = best_depth / best_depth_err if best_depth_err > 0 else 0.0

    log.info(
        "[%s] P=%.4f d  δ=%.5f  T=%.3f d  t₀=%.4f  power=%.3f  snr=%.1f",
        tic_id, best_period, best_depth, best_duration,
        best_t0, best_power, snr,
    )

    return {
        "tic_id":       tic_id,
        "period_d":     round(best_period,   6),
        "depth":        round(best_depth,    8),
        "duration_d":   round(best_duration, 6),
        "t0_btjd":      round(best_t0,       6),
        "bls_power":    round(best_power,    6),
        "snr":          round(snr,           3),
        "n_cadences":   n_cadences,
        "time_span_d":  round(time_span_d,   3),
        "status":       "ok",
    }


# ---------------------------------------------------------------------------
# Diagnostic phase-fold plot
# ---------------------------------------------------------------------------

def _plot_phase_fold(
    csv_path:  Path,
    tic_id:    str,
    period:    float,
    t0:        float,
    depth:     float,
    duration:  float,
) -> None:
    """
    Save a phase-folded light curve at the best BLS period.

    The transit is centred at phase 0; a shaded band marks the
    expected transit duration.  A 15-minute binned overlay is drawn
    for visibility.
    """
    df   = pd.read_csv(csv_path)
    t    = df["time"].to_numpy(dtype=np.float64)
    flux = df["flux_norm"].to_numpy(dtype=np.float64)

    # Phase-fold
    phase = ((t - t0) / period) % 1.0
    phase[phase > 0.5] -= 1.0                  # centre transit at 0

    # Sort for cleaner binned overlay
    idx   = np.argsort(phase)
    ph_s  = phase[idx]
    fl_s  = flux[idx]

    # 15-minute bins (15 / (period * 1440) in phase units)
    bin_width = 15.0 / (period * 1440.0)
    bins      = np.arange(-0.5, 0.5 + bin_width, bin_width)
    bin_phase, bin_flux, bin_err = [], [], []
    for i in range(len(bins) - 1):
        mask = (ph_s >= bins[i]) & (ph_s < bins[i + 1])
        if mask.sum() > 0:
            bin_phase.append(0.5 * (bins[i] + bins[i + 1]))
            bin_flux.append(np.mean(fl_s[mask]))
            bin_err.append(np.std(fl_s[mask]) / np.sqrt(mask.sum()))

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.scatter(ph_s, fl_s, s=1.2, alpha=0.25, color="#4C72B0",
               rasterized=True, label="2-min cadence")
    ax.errorbar(
        bin_phase, bin_flux, yerr=bin_err,
        fmt="o", ms=4, color="#C44E52", elinewidth=1,
        capsize=2, label="15-min bin", zorder=5,
    )

    # Shade transit window
    half_dur = 0.5 * duration / period
    ax.axvspan(-half_dur, half_dur, alpha=0.12, color="#DD8452",
               label=f"Transit window (T={duration*24:.1f} h)")
    ax.axhline(1.0,         color="k",        lw=0.6, ls="--", alpha=0.4)
    ax.axhline(1.0 - depth, color="#55A868",  lw=1.0, ls="--",
               alpha=0.8, label=f"Depth δ={depth*1e6:.0f} ppm")

    ax.set_xlim(-0.5, 0.5)
    ax.set_xlabel("Orbital phase  (P = {:.4f} d)".format(period), fontsize=10)
    ax.set_ylabel("Normalised flux", fontsize=10)
    ax.set_title(
        f"BLS phase fold  —  {tic_id}\n"
        f"P = {period:.4f} d  |  δ = {depth*1e6:.0f} ppm  |  "
        f"T = {duration*24:.1f} h  |  t₀ = {t0:.4f} BTJD",
        fontsize=10,
    )
    ax.legend(loc="lower right", fontsize=8, markerscale=3)
    ax.grid(True, linewidth=0.3, alpha=0.5)

    _PLOT_DIR.mkdir(parents=True, exist_ok=True)
    out = _PLOT_DIR / f"bls_fold_{tic_id}.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info("Phase-fold plot saved → %s", out)


# ---------------------------------------------------------------------------
# BLS periodogram power plot
# ---------------------------------------------------------------------------

def _plot_periodogram(
    csv_path: Path,
    tic_id:   str,
    p_min:    float,
    p_max:    float,
    best_period: float,
) -> None:
    """
    Save a BLS power-vs-period plot with the best period marked.
    Runs a lightweight BLS scan with a coarser grid (fast, for plotting only).
    """
    df    = pd.read_csv(csv_path)
    df    = df.dropna(subset=["time","flux_norm"]).sort_values("time")
    t     = df["time"].to_numpy(float)
    flux  = df["flux_norm"].to_numpy(float)
    ferr  = df.get("flux_err_norm", pd.Series(np.full(len(df), 1e-3))).to_numpy(float)
    ferr  = np.where(np.isfinite(ferr) & (ferr > 0), ferr, np.nanmedian(ferr[ferr > 0] if np.any(ferr>0) else [1e-3]))

    t_ap    = Time(t + 2_457_000.0, format="jd", scale="tdb")
    bls     = BoxLeastSquares(t_ap, flux * u.dimensionless_unscaled,
                              dy=ferr * u.dimensionless_unscaled)
    periods = _period_grid(t, p_min, p_max)
    durs    = _duration_grid(p_min, p_max, n=8)   # coarser for speed

    result = bls.power(periods * u.day, durs * u.day,
                       method="fast", objective="snr")

    fig, ax = plt.subplots(figsize=(11, 3.5))
    ax.plot(result.period.to(u.day).value,
            result.power, lw=0.6, color="#4C72B0", alpha=0.8)
    ax.axvline(best_period, color="#C44E52", lw=1.2, ls="--",
               label=f"Best P = {best_period:.4f} d")
    ax.set_xlabel("Period [d]", fontsize=10)
    ax.set_ylabel("BLS power (SNR)", fontsize=10)
    ax.set_title(f"BLS Periodogram  —  {tic_id}", fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(True, linewidth=0.3, alpha=0.5)

    out = _PLOT_DIR / f"bls_pgram_{tic_id}.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info("Periodogram plot saved → %s", out)


# ---------------------------------------------------------------------------
# Main batch runner
# ---------------------------------------------------------------------------

def run_bls_batch(
    clean_paths:    list[Path],
    p_min:          float = _P_MIN,
    p_max:          float = _P_MAX,
    min_n_transit:  int   = _MIN_N_TRANSIT,
    overwrite:      bool  = False,
    n_plots:        int   = 5,
) -> pd.DataFrame:
    """
    Run BLS on a list of cleaned light-curve CSVs and return a results table.

    Parameters
    ----------
    clean_paths   : List of cleaned CSV paths.
    p_min, p_max  : Period search range in days.
    min_n_transit : Minimum transit count required per period.
    overwrite     : If False, skip TIC IDs already in the results CSV.
    n_plots       : Number of top-power stars to save diagnostic plots for.

    Returns
    -------
    pd.DataFrame
        Full results table (all stars, including skipped and failed).
    """
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CFG.LOG_DIR.mkdir(parents=True, exist_ok=True)
    CFG.PLOT_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing results to support incremental runs
    if _RESULTS_CSV.exists() and not overwrite:
        existing = pd.read_csv(_RESULTS_CSV)
        done_ids = set(existing["tic_id"].astype(str))
        log.info("Found %d previously computed results.", len(done_ids))
    else:
        existing  = pd.DataFrame(columns=_RESULT_COLS)
        done_ids  = set()

    new_records: list[dict] = []

    for csv_path in tqdm(clean_paths, desc="BLS search", unit="star"):
        tic_id = csv_path.stem

        if tic_id in done_ids:
            log.info("[%s] Already processed — skipping.", tic_id)
            continue

        try:
            record = run_bls_one(
                csv_path,
                p_min=p_min,
                p_max=p_max,
                min_n_transit=min_n_transit,
            )
        except Exception as exc:    # noqa: BLE001
            log.warning("[%s] FAILED: %s", tic_id, exc)
            record = {
                "tic_id":       tic_id,
                "period_d":     np.nan,
                "depth":        np.nan,
                "duration_d":   np.nan,
                "t0_btjd":      np.nan,
                "bls_power":    np.nan,
                "snr":          np.nan,
                "n_cadences":   np.nan,
                "time_span_d":  np.nan,
                "status":       f"failed: {exc}",
            }

        new_records.append(record)

    # Merge with existing and persist
    new_df  = pd.DataFrame(new_records, columns=_RESULT_COLS)
    all_df  = pd.concat([existing, new_df], ignore_index=True)

    # Ensure column order
    for col in _RESULT_COLS:
        if col not in all_df.columns:
            all_df[col] = np.nan
    all_df  = all_df[_RESULT_COLS]

    all_df.to_csv(_RESULTS_CSV, index=False)
    log.info("Results saved → %s  (%d rows)", _RESULTS_CSV, len(all_df))

    # ── Diagnostic plots for top-N by BLS power ─────────────────────────────
    if n_plots > 0:
        ok_rows = new_df[new_df["status"] == "ok"].copy()
        if not ok_rows.empty:
            top = ok_rows.nlargest(min(n_plots, len(ok_rows)), "bls_power")
            for _, row in top.iterrows():
                tic_id  = row["tic_id"]
                src_csv = _CLEAN_LC_DIR / f"{tic_id}.csv"
                if not src_csv.exists():
                    continue
                try:
                    _plot_phase_fold(
                        src_csv, tic_id,
                        period=row["period_d"],
                        t0=row["t0_btjd"],
                        depth=row["depth"],
                        duration=row["duration_d"],
                    )
                    _plot_periodogram(
                        src_csv, tic_id,
                        p_min=p_min, p_max=p_max,
                        best_period=row["period_d"],
                    )
                except Exception as exc:    # noqa: BLE001
                    log.warning("Plot failed for %s: %s", tic_id, exc)

    return all_df


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_summary(df: pd.DataFrame) -> None:
    ok      = int((df["status"] == "ok").sum())   if "status" in df.columns else 0
    skipped = int((df["status"].str.startswith("skip") if "status" in df.columns
                   else pd.Series(False)).sum())
    failed  = int(df["status"].str.startswith("failed").sum()) if "status" in df.columns else 0

    log.info(
        "\n%s\n"
        "[run_bls] Summary\n"
        "%s\n"
        "  Total rows      : %d\n"
        "  BLS OK          : %d\n"
        "  Skipped (cache) : %d\n"
        "  Failed          : %d\n"
        "%s",
        "=" * 55, "─" * 55,
        len(df), ok, skipped, failed,
        "=" * 55,
    )

    if ok > 0:
        ok_df = df[df["status"] == "ok"]
        log.info(
            "  Period range    : %.3f – %.3f d\n"
            "  Median depth    : %.1f ppm\n"
            "  Median SNR      : %.1f\n"
            "  Top 10 by power →\n%s",
            ok_df["period_d"].min(), ok_df["period_d"].max(),
            ok_df["depth"].median() * 1e6,
            ok_df["snr"].median(),
            ok_df.nlargest(10, "bls_power")[
                ["tic_id","period_d","depth","duration_d","snr","bls_power"]
            ].to_string(index=False),
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run BLS transit search on cleaned TESS light curves.\n"
            "Outputs: data/results/bls_results.csv"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--input-dir",
        default=str(_CLEAN_LC_DIR),
        metavar="DIR",
        help=f"Directory of cleaned TIC_*.csv files.\nDefault: {_CLEAN_LC_DIR}",
    )
    parser.add_argument(
        "--n",
        type=int, default=None, metavar="N",
        help="Process only the first N files.",
    )
    parser.add_argument(
        "--tic",
        nargs="+", type=int, default=None, metavar="TIC_ID",
        help="Process specific TIC IDs (overrides --n).",
    )
    parser.add_argument(
        "--p-min",
        type=float, default=_P_MIN, metavar="DAYS",
        help=f"Minimum search period in days.  Default: {_P_MIN}",
    )
    parser.add_argument(
        "--p-max",
        type=float, default=_P_MAX, metavar="DAYS",
        help=f"Maximum search period in days.  Default: {_P_MAX}",
    )
    parser.add_argument(
        "--min-n-transit",
        type=int, default=_MIN_N_TRANSIT, dest="min_n_transit", metavar="N",
        help=f"Minimum transit count required.  Default: {_MIN_N_TRANSIT}",
    )
    parser.add_argument(
        "--n-plots",
        type=int, default=5, dest="n_plots", metavar="N",
        help="Save phase-fold + periodogram plots for the top N stars.  Default: 5",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true", default=False,
        help="Recompute results even if the CSV already contains this TIC ID.",
    )
    return parser.parse_args()


def main() -> None:
    args      = _parse_args()
    input_dir = Path(args.input_dir)

    if not input_dir.exists():
        sys.exit(
            f"[run_bls] Input directory not found: {input_dir}\n"
            "Run  python -m src.clean_lightcurves  first."
        )

    # ── Resolve file list ──────────────────────────────────────────────────
    if args.tic:
        clean_paths = []
        for tid in args.tic:
            p = input_dir / f"TIC_{tid}.csv"
            if p.exists():
                clean_paths.append(p)
            else:
                log.warning("Cleaned CSV not found for TIC %d: %s", tid, p)
        log.info("Processing %d user-specified TIC file(s).", len(clean_paths))
    else:
        clean_paths = sorted(input_dir.glob("TIC_*.csv"))
        if args.n is not None:
            clean_paths = clean_paths[: args.n]
        log.info(
            "Processing %d file(s) from %s.", len(clean_paths), input_dir,
        )

    if not clean_paths:
        sys.exit(
            f"[run_bls] No TIC_*.csv files found in {input_dir}.\n"
            "Run  python -m src.clean_lightcurves  first."
        )

    log.info(
        "BLS parameters: P=[%.2f, %.2f] d | min_transits=%d | n_plots=%d | overwrite=%s",
        args.p_min, args.p_max, args.min_n_transit, args.n_plots, args.overwrite,
    )

    # ── Run ────────────────────────────────────────────────────────────────
    results = run_bls_batch(
        clean_paths,
        p_min=args.p_min,
        p_max=args.p_max,
        min_n_transit=args.min_n_transit,
        overwrite=args.overwrite,
        n_plots=args.n_plots,
    )

    _print_summary(results)


if __name__ == "__main__":
    main()
