"""
clean_lightcurves.py
--------------------
Phase 2b of the transit-detection pipeline: clean and detrend raw TESS
2-minute light curves that were saved by ``fetch_lightcurves.py``.

Processing steps applied to every light curve
----------------------------------------------
1. Load CSV  (columns: time, flux, flux_err)
2. Drop rows with NaN in **time** or **flux**
3. Sort by time (guard against out-of-order sectors)
4. Sigma-clip outliers at ±N sigma  (default: 5σ, iterative, 3 passes)
5. Median-normalise flux   →  flux_norm  ≈ 1.0 baseline
6. Propagate normalisation to flux_err_norm
7. Savitzky-Golay high-pass filter to remove long-term stellar variability
   - window length  ≈ 3 days at 2-min cadence  (default: 2161 pts, rounded
     up to nearest odd integer)
   - polynomial order: 2
   - residual  = flux_norm / sg_trend   (multiplicative, preserves depth)
8. Save cleaned light curve to  data/clean/lightcurves/TIC_<id>.csv
   Columns: time, flux_norm, flux_err_norm, sg_trend

Usage
-----
    python -m src.clean_lightcurves                # all raw CSVs
    python -m src.clean_lightcurves --n 5          # first 5 files
    python -m src.clean_lightcurves --tic 468184895 290492819
    python -m src.clean_lightcurves --overwrite    # reprocess existing

Dependencies (all in requirements.txt)
---------------------------------------
    numpy>=1.24, pandas>=2.0, scipy>=1.11, matplotlib>=3.7, tqdm>=4.65
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
from scipy.signal import savgol_filter
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
        logging.FileHandler(CFG.LOG_DIR / "clean_lightcurves.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=RuntimeWarning)

# ---------------------------------------------------------------------------
# Constants & derived paths
# ---------------------------------------------------------------------------

_RAW_LC_DIR:   Path  = CFG.RAW_DIR   / "lightcurves"   # input  CSVs
_CLEAN_LC_DIR: Path  = CFG.CLEAN_DIR / "lightcurves"   # output CSVs
_PLOT_DIR:     Path  = CFG.PLOT_DIR                     # diagnostic plots

# Cadence of 2-min TESS data in days
_CADENCE_DAYS: float = 2.0 / (60.0 * 24.0)             # ≈ 0.001389 d

# Savitzky-Golay defaults
_SG_WINDOW_DAYS:  float = 3.0        # remove trends longer than ~3 d
_SG_POLY_ORDER:   int   = 2          # quadratic fit within each window

# Sigma-clipping defaults
_SIGMA:           float = 5.0        # rejection threshold
_SIGMA_MAXITER:   int   = 3          # maximum iterative passes


# ---------------------------------------------------------------------------
# Step helpers
# ---------------------------------------------------------------------------

def _drop_nans(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows where time or flux is NaN, then sort by time."""
    before = len(df)
    df = df.dropna(subset=["time", "flux"]).copy()
    df = df.sort_values("time").reset_index(drop=True)
    dropped = before - len(df)
    if dropped:
        log.debug("  Dropped %d NaN row(s); %d remain.", dropped, len(df))
    return df


def _sigma_clip(
    flux: np.ndarray,
    sigma: float = _SIGMA,
    maxiter: int = _SIGMA_MAXITER,
) -> np.ndarray:
    """
    Iterative sigma-clipping.  Returns a boolean mask — True = KEEP.

    Parameters
    ----------
    flux:    1-D array of flux values (already NaN-free).
    sigma:   Rejection threshold in units of the running MAD-based σ.
    maxiter: Maximum number of clipping passes.

    Notes
    -----
    Uses the **median absolute deviation** (MAD) estimator for robustness:
        σ_robust = MAD / 0.6745
    This is far less sensitive to the outliers we are trying to remove than
    the sample standard deviation.
    """
    keep = np.ones(len(flux), dtype=bool)

    for _ in range(maxiter):
        f = flux[keep]
        if len(f) < 10:
            break
        median = np.median(f)
        mad    = np.median(np.abs(f - median))
        sigma_est = mad / 0.6745          # robust σ estimator

        if sigma_est == 0:
            break                          # all points identical → stop

        new_keep = keep.copy()
        new_keep[keep] = np.abs(flux[keep] - median) <= sigma * sigma_est

        if np.array_equal(new_keep, keep):
            break                          # converged
        keep = new_keep

    return keep


def _normalise(
    flux: np.ndarray,
    flux_err: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Divide flux and flux_err by the median flux.

    Returns (flux_norm, flux_err_norm).
    """
    median = np.median(flux)
    if median == 0 or not np.isfinite(median):
        raise ValueError("Median flux is zero or non-finite — cannot normalise.")
    return flux / median, flux_err / median


def _savgol_window(cadence_days: float, window_days: float, poly_order: int) -> int:
    """
    Compute the Savitzky-Golay window length in *samples* from a desired
    duration in days, rounded up to the nearest odd integer ≥ poly_order + 2.

    Parameters
    ----------
    cadence_days: Sampling interval in days (2/1440 for 2-min TESS).
    window_days:  Desired filter half-baseline in days.
    poly_order:   SG polynomial order (window must be > poly_order).
    """
    n = int(np.ceil(window_days / cadence_days))
    if n % 2 == 0:
        n += 1                             # enforce odd length
    min_n = poly_order + 2
    if min_n % 2 == 0:
        min_n += 1
    return max(n, min_n)


def _detrend_savgol(
    time:     np.ndarray,
    flux_norm: np.ndarray,
    flux_err_norm: np.ndarray,
    window_days: float = _SG_WINDOW_DAYS,
    poly_order:  int   = _SG_POLY_ORDER,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Apply a Savitzky-Golay high-pass filter to remove long-term stellar
    variability and instrumental trends.

    Strategy
    --------
    * Estimate the cadence from the *median* time-step (robust to gaps).
    * Compute the window size = ceil(window_days / cadence).
    * If the window exceeds the array length, clamp it to the longest
      valid odd window that fits.
    * Compute  sg_trend  = SG smooth of flux_norm.
    * Return   residual  = flux_norm / sg_trend   (multiplicative removal
      preserves fractional transit depths exactly).

    Returns
    -------
    residual      : detrended flux (dimensionless, centred near 1.0)
    flux_err_norm : propagated error (divided by sg_trend element-wise)
    sg_trend      : the smooth trend itself (saved for diagnostics)
    """
    # Robust cadence estimate from the median dt
    dt_med = float(np.median(np.diff(time)))
    if dt_med <= 0:
        raise ValueError(f"Non-positive median time-step: {dt_med}")

    win = _savgol_window(dt_med, window_days, poly_order)

    # Clamp to array length
    max_win = len(flux_norm) if len(flux_norm) % 2 == 1 else len(flux_norm) - 1
    if win > max_win:
        win = max_win
        log.debug("  SG window clamped to %d (light curve too short).", win)

    sg_trend  = savgol_filter(flux_norm, window_length=win, polyorder=poly_order)

    # Guard against near-zero trend values (shouldn't happen for real data)
    sg_trend  = np.where(np.abs(sg_trend) < 1e-6, 1.0, sg_trend)

    residual       = flux_norm    / sg_trend
    err_detrended  = flux_err_norm / sg_trend

    log.debug(
        "  SG window = %d pts ≈ %.2f d  (poly_order=%d)",
        win, win * dt_med, poly_order,
    )
    return residual, err_detrended, sg_trend


# ---------------------------------------------------------------------------
# Per-star pipeline
# ---------------------------------------------------------------------------

def clean_one(
    csv_path:   Path,
    out_path:   Path,
    sigma:      float = _SIGMA,
    window_days: float = _SG_WINDOW_DAYS,
    poly_order: int   = _SG_POLY_ORDER,
) -> dict:
    """
    Run the full cleaning pipeline on a single raw light-curve CSV.

    Parameters
    ----------
    csv_path:    Path to the raw CSV (time, flux, flux_err).
    out_path:    Destination path for the cleaned CSV.
    sigma:       Sigma-clipping threshold.
    window_days: SG filter window in days.
    poly_order:  SG polynomial order.

    Returns
    -------
    dict with keys:
        tic_id, n_raw, n_after_nan, n_after_clip, n_clean,
        clip_pct, median_flux, sg_window_days
    """
    tic_id = csv_path.stem  # "TIC_<id>"

    # ── 1. Load ──────────────────────────────────────────────────────────────
    df = pd.read_csv(csv_path)
    if not {"time", "flux", "flux_err"}.issubset(df.columns):
        raise ValueError(
            f"{csv_path.name} is missing required columns "
            f"(need: time, flux, flux_err)."
        )
    n_raw = len(df)

    # ── 2. Drop NaNs & sort ───────────────────────────────────────────────────
    df = _drop_nans(df)
    n_after_nan = len(df)

    if n_after_nan < 10:
        raise ValueError(
            f"Only {n_after_nan} valid rows after NaN removal — skipping."
        )

    time     = df["time"].to_numpy(dtype=np.float64)
    flux     = df["flux"].to_numpy(dtype=np.float64)
    flux_err = df["flux_err"].to_numpy(dtype=np.float64)

    # Replace NaN flux_err with the median error (non-critical column)
    if not np.all(np.isfinite(flux_err)):
        med_err  = np.nanmedian(flux_err)
        flux_err = np.where(np.isfinite(flux_err), flux_err, med_err)

    # ── 3. Sigma-clip ────────────────────────────────────────────────────────
    keep = _sigma_clip(flux, sigma=sigma)
    time, flux, flux_err = time[keep], flux[keep], flux_err[keep]
    n_after_clip = int(keep.sum())
    clip_pct = (n_after_nan - n_after_clip) / n_after_nan * 100.0

    log.debug(
        "  [%s] sigma-clip: removed %d / %d pts (%.1f%%)",
        tic_id, n_after_nan - n_after_clip, n_after_nan, clip_pct,
    )

    # ── 4. Median normalise ──────────────────────────────────────────────────
    median_flux = float(np.median(flux))
    flux_norm, flux_err_norm = _normalise(flux, flux_err)

    # ── 5. Savitzky-Golay detrend ────────────────────────────────────────────
    residual, err_detrended, sg_trend = _detrend_savgol(
        time, flux_norm, flux_err_norm,
        window_days=window_days,
        poly_order=poly_order,
    )

    # ── 6. Build output DataFrame ────────────────────────────────────────────
    out_df = pd.DataFrame(
        {
            "time":         time,
            "flux_norm":    residual,       # detrended, normalised flux
            "flux_err_norm": err_detrended, # propagated uncertainty
            "sg_trend":     sg_trend,       # long-term trend (diagnostic)
        }
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False, float_format="%.10f")
    n_clean = len(out_df)

    return {
        "tic_id":         tic_id,
        "n_raw":          n_raw,
        "n_after_nan":    n_after_nan,
        "n_after_clip":   n_after_clip,
        "n_clean":        n_clean,
        "clip_pct":       round(clip_pct, 2),
        "median_flux":    round(median_flux, 6),
        "sg_window_days": window_days,
    }


# ---------------------------------------------------------------------------
# Diagnostic plot (first successfully cleaned star)
# ---------------------------------------------------------------------------

def _plot_cleaning_summary(
    raw_csv:   Path,
    clean_csv: Path,
    tic_id:    str,
) -> None:
    """
    4-panel diagnostic figure showing the effect of each cleaning step.

    Panels
    ------
    1. Raw flux vs time
    2. Sigma-clipped & median-normalised flux
    3. SG trend overlaid on normalised flux
    4. Final detrended residual (what enters transit search)
    """
    raw   = pd.read_csv(raw_csv)
    clean = pd.read_csv(clean_csv)

    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=False)
    fig.suptitle(
        f"Light-curve cleaning summary  —  {tic_id}",
        fontsize=13, fontweight="bold", y=0.98,
    )

    _DOT = dict(s=1.2, alpha=0.3, rasterized=True)

    # ── Panel 1: raw flux ──────────────────────────────────────────────────
    ax = axes[0]
    ax.scatter(raw["time"], raw["flux"], color="#4C72B0", **_DOT)
    ax.set_ylabel("Raw flux", fontsize=9)
    ax.set_title("1 · Raw flux (straight from download)", fontsize=9, loc="left")
    ax.grid(True, linewidth=0.3, alpha=0.5)

    # ── Panel 2: sigma-clip + normalise ───────────────────────────────────
    # Reconstruct by showing trend × residual (= flux_norm)
    ax = axes[1]
    flux_norm_reconstructed = clean["flux_norm"] * clean["sg_trend"]
    ax.scatter(clean["time"], flux_norm_reconstructed, color="#55A868", **_DOT)
    ax.set_ylabel("Flux / median", fontsize=9)
    ax.set_title(
        f"2 · After NaN removal + {_SIGMA}σ sigma-clipping + median normalisation",
        fontsize=9, loc="left",
    )
    ax.grid(True, linewidth=0.3, alpha=0.5)

    # ── Panel 3: SG trend overlay ──────────────────────────────────────────
    ax = axes[2]
    ax.scatter(clean["time"], flux_norm_reconstructed, color="#55A868", **_DOT,
               label="flux_norm")
    ax.plot(clean["time"], clean["sg_trend"], color="#C44E52", lw=1.2,
            label=f"SG trend  (window ≈ {_SG_WINDOW_DAYS} d)")
    ax.set_ylabel("Flux / median", fontsize=9)
    ax.set_title(
        f"3 · Savitzky-Golay trend  (window ≈ {_SG_WINDOW_DAYS} d, "
        f"poly_order={_SG_POLY_ORDER})",
        fontsize=9, loc="left",
    )
    ax.legend(loc="upper right", fontsize=8, markerscale=4)
    ax.grid(True, linewidth=0.3, alpha=0.5)

    # ── Panel 4: detrended residual ────────────────────────────────────────
    ax = axes[3]
    ax.scatter(clean["time"], clean["flux_norm"], color="#DD8452", **_DOT)
    ax.axhline(1.0, color="k", lw=0.6, ls="--", alpha=0.5)
    # 200-point running median overlay
    window = min(201, len(clean) // 2 | 1)   # ensure odd, at most half length
    from scipy.signal import medfilt
    smooth = medfilt(clean["flux_norm"].to_numpy(), kernel_size=window)
    ax.plot(clean["time"], smooth, color="#8172B2", lw=0.9,
            label=f"median filter (w={window})")
    ax.set_ylabel("Detrended flux", fontsize=9)
    ax.set_xlabel("Time  [BTJD − 2 457 000 d]", fontsize=9)
    ax.set_title("4 · Final detrended residual  (ready for transit search)", fontsize=9, loc="left")
    ax.legend(loc="upper right", fontsize=8, markerscale=4)
    ax.grid(True, linewidth=0.3, alpha=0.5)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    _PLOT_DIR.mkdir(parents=True, exist_ok=True)
    out = _PLOT_DIR / f"cleaning_summary_{tic_id}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info("Diagnostic plot saved -> %s", out)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def clean_lightcurves(
    raw_paths:   list[Path],
    overwrite:   bool  = False,
    sigma:       float = _SIGMA,
    window_days: float = _SG_WINDOW_DAYS,
    poly_order:  int   = _SG_POLY_ORDER,
) -> pd.DataFrame:
    """
    Run the cleaning pipeline over a list of raw light-curve CSVs.

    Parameters
    ----------
    raw_paths:   List of input CSV paths.
    overwrite:   If False, skip files whose cleaned CSV already exists.
    sigma:       Sigma-clipping rejection threshold.
    window_days: SG filter window in days.
    poly_order:  SG polynomial order.

    Returns
    -------
    pd.DataFrame
        Per-star summary table (one row per processed file).
    """
    _CLEAN_LC_DIR.mkdir(parents=True, exist_ok=True)
    CFG.LOG_DIR.mkdir(parents=True, exist_ok=True)

    records:  list[dict] = []
    first_plot_done = False

    for raw_path in tqdm(raw_paths, desc="Cleaning light curves", unit="star"):
        tic_id    = raw_path.stem          # "TIC_<number>"
        out_path  = _CLEAN_LC_DIR / raw_path.name

        # ── Cache check ──────────────────────────────────────────────────────
        if out_path.exists() and not overwrite:
            log.info("[%s] Already cleaned — skipping (use --overwrite to redo).", tic_id)
            records.append({"tic_id": tic_id, "status": "skipped"})
            continue

        # ── Process ──────────────────────────────────────────────────────────
        try:
            info = clean_one(
                raw_path, out_path,
                sigma=sigma,
                window_days=window_days,
                poly_order=poly_order,
            )
            info["status"] = "cleaned"
            records.append(info)
            log.info(
                "[%s] ✓  %d → %d pts  (clipped %.1f%%, median flux=%.4f)",
                tic_id,
                info["n_raw"],
                info["n_clean"],
                info["clip_pct"],
                info["median_flux"],
            )

            # Diagnostic plot for the first star
            if not first_plot_done:
                try:
                    _plot_cleaning_summary(raw_path, out_path, tic_id)
                    first_plot_done = True
                except Exception as exc:  # noqa: BLE001
                    log.warning("Plot failed for %s: %s", tic_id, exc)

        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] FAILED: %s", tic_id, exc)
            records.append({"tic_id": tic_id, "status": "failed", "error": str(exc)})

    summary = pd.DataFrame(records)
    return summary


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_summary(df: pd.DataFrame) -> None:
    total    = len(df)
    cleaned  = int((df["status"] == "cleaned").sum())  if "status" in df.columns else 0
    skipped  = int((df["status"] == "skipped").sum())  if "status" in df.columns else 0
    failed   = int((df["status"] == "failed").sum())   if "status" in df.columns else 0

    log.info(
        "\n%s\n"
        "[clean_lightcurves] Summary\n"
        "%s\n"
        "  Total files    : %d\n"
        "  Cleaned (new)  : %d\n"
        "  Skipped (cache): %d\n"
        "  Failed         : %d\n"
        "%s",
        "=" * 55,
        "─" * 55,
        total, cleaned, skipped, failed,
        "=" * 55,
    )

    if "clip_pct" in df.columns and cleaned:
        clean_rows = df[df["status"] == "cleaned"]
        log.info(
            "  Median clipped  : %.2f%%\n"
            "  Median n_clean  : %d pts",
            clean_rows["clip_pct"].median(),
            int(clean_rows["n_clean"].median()),
        )

    failed_ids = df.loc[df.get("status", pd.Series()) == "failed", "tic_id"].tolist() \
        if "status" in df.columns else []
    if failed_ids:
        log.warning("Failed: %s", ", ".join(str(x) for x in failed_ids))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Clean and detrend raw TESS 2-min light-curve CSVs:\n"
            "  NaN removal → sigma-clipping → normalisation → SG detrending"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--input-dir",
        default=str(_RAW_LC_DIR),
        metavar="DIR",
        help=(
            f"Directory containing raw TIC_*.csv files.\n"
            f"Default: {_RAW_LC_DIR}"
        ),
    )
    parser.add_argument(
        "--n",
        type=int,
        default=None,
        metavar="N",
        help="Process only the first N files (useful for quick tests).",
    )
    parser.add_argument(
        "--tic",
        nargs="+",
        type=int,
        default=None,
        metavar="TIC_ID",
        help="Process only the listed TIC IDs (overrides --n).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Re-clean and overwrite existing output files.",
    )
    parser.add_argument(
        "--sigma",
        type=float,
        default=_SIGMA,
        help=f"Sigma-clipping rejection threshold.  Default: {_SIGMA}",
    )
    parser.add_argument(
        "--window-days",
        type=float,
        default=_SG_WINDOW_DAYS,
        dest="window_days",
        help=(
            f"Savitzky-Golay filter window in days.\n"
            f"Signals longer than this are removed as variability.\n"
            f"Default: {_SG_WINDOW_DAYS}"
        ),
    )
    parser.add_argument(
        "--poly-order",
        type=int,
        default=_SG_POLY_ORDER,
        dest="poly_order",
        help=f"Savitzky-Golay polynomial order.  Default: {_SG_POLY_ORDER}",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    input_dir = Path(args.input_dir)

    if not input_dir.exists():
        sys.exit(
            f"[clean_lightcurves] Input directory not found: {input_dir}\n"
            "Run  python -m src.fetch_lightcurves  first."
        )

    # ── Resolve file list ──────────────────────────────────────────────────
    if args.tic:
        raw_paths = []
        for tid in args.tic:
            p = input_dir / f"TIC_{tid}.csv"
            if p.exists():
                raw_paths.append(p)
            else:
                log.warning("Raw CSV not found for TIC %d: %s", tid, p)
        log.info("Processing %d user-specified TIC file(s).", len(raw_paths))
    else:
        raw_paths = sorted(input_dir.glob("TIC_*.csv"))
        if args.n is not None:
            raw_paths = raw_paths[: args.n]
            log.info(
                "Processing first %d of %d available file(s).",
                len(raw_paths),
                len(sorted(input_dir.glob("TIC_*.csv"))),
            )
        else:
            log.info("Processing all %d file(s) in %s.", len(raw_paths), input_dir)

    if not raw_paths:
        sys.exit(
            f"[clean_lightcurves] No TIC_*.csv files found in {input_dir}.\n"
            "Run  python -m src.fetch_lightcurves  first."
        )

    # ── Log active parameters ──────────────────────────────────────────────
    log.info(
        "Parameters: sigma=%.1f | window=%.1f d | poly_order=%d | overwrite=%s",
        args.sigma, args.window_days, args.poly_order, args.overwrite,
    )

    # ── Run ────────────────────────────────────────────────────────────────
    summary = clean_lightcurves(
        raw_paths,
        overwrite=args.overwrite,
        sigma=args.sigma,
        window_days=args.window_days,
        poly_order=args.poly_order,
    )

    # ── Save summary table ─────────────────────────────────────────────────
    summary_path = CFG.CLEAN_DIR / "cleaning_summary.csv"
    CFG.CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    log.info("Per-star summary saved -> %s", summary_path)

    _print_summary(summary)


if __name__ == "__main__":
    main()
