"""
fetch_lightcurves.py
--------------------
Phase 2 of the transit-detection pipeline: download and persist 2-minute
cadence TESS light curves for every prime target.

Workflow
--------
1. Read TIC IDs from  data/clean/prime_targets.csv  (column "ID").
2. For each TIC ID:
   a. Search MAST for all available 2-min SPOC light-curve products.
   b. Download them (skips anything already cached by lightkurve).
   c. Stitch all sectors into a single LightCurve (sigma-clipping outliers,
      normalising each sector individually before stitching).
   d. Save the stitched light curve to
      data/raw/lightcurves/TIC_<id>.csv  with columns:
        time [BTJD], flux [normalised], flux_err [normalised]
3. After the first successful download, produce a diagnostic plot:
      plots/lc_first_star.png
   showing raw normalised flux vs time for quick visual verification.

Usage
-----
    python -m src.fetch_lightcurves                # all prime targets
    python -m src.fetch_lightcurves --n 20         # first 20 targets only
    python -m src.fetch_lightcurves --tic 261136679 279799164   # specific IDs

Dependencies (all in requirements.txt)
---------------------------------------
    lightkurve>=2.4.0, pandas>=2.0, matplotlib>=3.7, numpy>=1.24, tqdm>=4.65
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")          # non-interactive backend; safe on headless servers
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tqdm import tqdm

# ── lightkurve imports ─────────────────────────────────────────────────────────
try:
    import lightkurve as lk
    from lightkurve import LightCurveCollection
except ImportError as _exc:
    sys.exit(
        "lightkurve is not installed. Run:  pip install lightkurve>=2.4.0\n"
        f"Original error: {_exc}"
    )

# ── project imports ────────────────────────────────────────────────────────────
from src.config import CFG

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(CFG.LOG_DIR / "fetch_lightcurves.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)

# Suppress noisy astropy / lightkurve warnings during downloads
warnings.filterwarnings("ignore", category=UserWarning, module="lightkurve")
warnings.filterwarnings("ignore", category=UserWarning, module="astropy")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LC_SUBDIR: Path = CFG.RAW_DIR / "lightcurves"    # where CSVs are saved
_PLOT_PATH:  Path = CFG.PLOT_DIR / "lc_first_star.png"
_EXPTIME:    int  = 120                            # 2-minute cadence (seconds)
_AUTHOR:     str  = "SPOC"                        # highest-quality pipeline
_STITCH_SIGMA: float = 5.0                        # sigma-clip threshold for stitching
_SLEEP_BETWEEN: float = 1.0                       # polite delay between MAST requests (s)


# ---------------------------------------------------------------------------
# Core download & stitch
# ---------------------------------------------------------------------------

def _search_and_download(tic_id: int) -> LightCurveCollection | None:
    """
    Search MAST for 2-min SPOC light curves for *tic_id* and download them.

    Returns
    -------
    LightCurveCollection | None
        Collection of per-sector LightCurve objects, or None if nothing found.
    """
    target_str = f"TIC {tic_id}"
    log.debug("Searching MAST for %s …", target_str)

    try:
        search_result = lk.search_lightcurve(
            target_str,
            mission="TESS",
            author=_AUTHOR,
            exptime=_EXPTIME,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("MAST search failed for %s: %s", target_str, exc)
        return None

    if len(search_result) == 0:
        log.info("  No 2-min SPOC data found for %s.", target_str)
        return None

    log.info(
        "  Found %d sector(s) for %s. Downloading …",
        len(search_result),
        target_str,
    )

    try:
        lcc: LightCurveCollection = search_result.download_all(
            quality_bitmask="default"
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Download failed for %s: %s", target_str, exc)
        return None

    return lcc


def _stitch_collection(lcc: LightCurveCollection) -> lk.LightCurve | None:
    """
    Normalise each sector, sigma-clip outliers, then stitch into one curve.

    Each sector is divided by its own median so that the stitched flux
    is dimensionless and centred near 1.0 (before any transit).

    Returns
    -------
    lk.LightCurve | None
        Stitched light curve, or None on failure.
    """
    try:
        # normalise & stitch ─ lightkurve's stitch() does per-sector normalisation
        stitched: lk.LightCurve = lcc.stitch(corrector_func=lambda lc: lc.normalize())
    except Exception as exc:  # noqa: BLE001
        log.warning("Stitch failed: %s", exc)
        return None

    # Remove NaNs and sigma-clip gross outliers
    stitched = stitched.remove_nans()
    try:
        stitched = stitched.remove_outliers(sigma=_STITCH_SIGMA)
    except Exception:  # noqa: BLE001
        pass  # non-fatal – proceed without sigma-clipping

    if len(stitched) == 0:
        log.warning("Stitched light curve is empty after cleaning.")
        return None

    return stitched


def _save_lightcurve(lc: lk.LightCurve, tic_id: int) -> Path:
    """
    Persist *lc* as a three-column CSV (time, flux, flux_err).

    Returns
    -------
    Path
        Path to the written CSV file.
    """
    _LC_SUBDIR.mkdir(parents=True, exist_ok=True)
    out_path = _LC_SUBDIR / f"TIC_{tic_id}.csv"

    time_vals  = np.array(lc.time.value,          dtype=np.float64)
    flux_vals  = np.array(lc.flux.value,          dtype=np.float64)

    # flux_err may not exist in every lightkurve version / product
    try:
        ferr_vals = np.array(lc.flux_err.value,   dtype=np.float64)
    except AttributeError:
        ferr_vals = np.full_like(flux_vals, np.nan)

    df = pd.DataFrame(
        {"time": time_vals, "flux": flux_vals, "flux_err": ferr_vals}
    )
    df.to_csv(out_path, index=False)
    log.info("  Saved %d cadences -> %s", len(df), out_path)
    return out_path


# ---------------------------------------------------------------------------
# Diagnostic plot
# ---------------------------------------------------------------------------

def _plot_first_star(lc: lk.LightCurve, tic_id: int) -> None:
    """
    Save a publication-quality diagnostic plot of the stitched light curve
    for the first successfully downloaded target.
    """
    CFG.PLOT_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(14, 4))

    time_arr = np.array(lc.time.value)
    flux_arr = np.array(lc.flux.value)

    # Scatter plot – small alpha dots so crowded regions stay readable
    ax.scatter(
        time_arr,
        flux_arr,
        s=1.5,
        alpha=0.35,
        color="#4C72B0",
        rasterized=True,
        label="raw flux (normalised)",
    )

    # Running median overlay (window ≈ 13-point = ~26 minutes)
    window = min(13, len(flux_arr) // 4)
    if window >= 3:
        from scipy.signal import medfilt  # local import – optional dependency
        smoothed = medfilt(flux_arr, kernel_size=window if window % 2 else window + 1)
        ax.plot(time_arr, smoothed, color="#C44E52", lw=0.8, label=f"median filter (w={window})")

    ax.set_xlabel("Time  [BTJD − 2 457 000 d]", fontsize=11)
    ax.set_ylabel("Normalised Flux", fontsize=11)
    ax.set_title(
        f"TESS 2-min light curve  —  TIC {tic_id}\n"
        f"({len(time_arr):,} cadences, "
        f"{time_arr.min():.1f} – {time_arr.max():.1f} d)",
        fontsize=12,
    )
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, linewidth=0.4, alpha=0.5)

    fig.tight_layout()
    fig.savefig(_PLOT_PATH, dpi=150)
    plt.close(fig)
    log.info("Diagnostic plot saved -> %s", _PLOT_PATH)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def fetch_lightcurves(
    tic_ids: list[int],
    overwrite: bool = False,
) -> dict[int, str]:
    """
    Download, stitch, and save light curves for all *tic_ids*.

    Parameters
    ----------
    tic_ids:
        List of integer TIC IDs to process.
    overwrite:
        If False (default), skip any TIC whose CSV already exists.

    Returns
    -------
    dict[int, str]
        Mapping  {tic_id: status}  where status is one of:
        ``"saved"``, ``"skipped"``, ``"no_data"``, ``"failed"``.
    """
    _LC_SUBDIR.mkdir(parents=True, exist_ok=True)

    results: dict[int, str] = {}
    first_plot_done = False

    for tic_id in tqdm(tic_ids, desc="Downloading light curves", unit="star"):
        csv_path = _LC_SUBDIR / f"TIC_{tic_id}.csv"

        # ── Cache hit ──────────────────────────────────────────────────────────
        if csv_path.exists() and not overwrite:
            log.info("[TIC %d] Cache hit – skipping.", tic_id)
            results[tic_id] = "skipped"
            continue

        log.info("[TIC %d] Processing …", tic_id)

        # ── Search & download ──────────────────────────────────────────────────
        lcc = _search_and_download(tic_id)
        if lcc is None:
            results[tic_id] = "no_data"
            time.sleep(_SLEEP_BETWEEN)
            continue

        # ── Stitch ────────────────────────────────────────────────────────────
        stitched = _stitch_collection(lcc)
        if stitched is None:
            results[tic_id] = "failed"
            time.sleep(_SLEEP_BETWEEN)
            continue

        # ── Persist CSV ───────────────────────────────────────────────────────
        _save_lightcurve(stitched, tic_id)
        results[tic_id] = "saved"

        # ── First-star diagnostic plot ────────────────────────────────────────
        if not first_plot_done:
            try:
                _plot_first_star(stitched, tic_id)
                first_plot_done = True
            except Exception as exc:  # noqa: BLE001
                log.warning("Could not produce diagnostic plot: %s", exc)

        time.sleep(_SLEEP_BETWEEN)

    return results


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------

def _print_summary(results: dict[int, str]) -> None:
    saved   = sum(1 for v in results.values() if v == "saved")
    skipped = sum(1 for v in results.values() if v == "skipped")
    no_data = sum(1 for v in results.values() if v == "no_data")
    failed  = sum(1 for v in results.values() if v == "failed")
    total   = len(results)

    log.info(
        "\n%s\n"
        "[fetch_lightcurves] Summary\n"
        "%s\n"
        "  Total targets  : %d\n"
        "  Saved (new)    : %d\n"
        "  Skipped (cache): %d\n"
        "  No 2-min data  : %d\n"
        "  Failed         : %d\n"
        "%s",
        "=" * 55,
        "─" * 55,
        total, saved, skipped, no_data, failed,
        "=" * 55,
    )

    # List any failures for easy follow-up
    failed_ids = [str(k) for k, v in results.items() if v == "failed"]
    if failed_ids:
        log.warning("Failed TIC IDs: %s", ", ".join(failed_ids))


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download 2-min TESS SPOC light curves for prime targets "
            "and save them as per-star CSVs."
        )
    )
    parser.add_argument(
        "--input",
        default=str(CFG.CLEAN_DIR / "prime_targets.csv"),
        help="Path to the prime-targets CSV (must contain an 'ID' column). "
             f"Default: {CFG.CLEAN_DIR / 'prime_targets.csv'}",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=None,
        metavar="N",
        help="Process only the first N targets (useful for quick tests).",
    )
    parser.add_argument(
        "--tic",
        nargs="+",
        type=int,
        default=None,
        metavar="TIC_ID",
        help="Process only the specified TIC IDs (overrides --n).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Re-download and overwrite existing CSV files.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # ── Resolve target list ────────────────────────────────────────────────────
    if args.tic:
        tic_ids = args.tic
        log.info("Running on %d user-specified TIC ID(s).", len(tic_ids))
    else:
        input_path = Path(args.input)
        if not input_path.exists():
            sys.exit(
                f"[fetch_lightcurves] Input file not found: {input_path}\n"
                "Run  python -m src.export_targets  first."
            )
        df_targets = pd.read_csv(input_path, low_memory=False)
        if "ID" not in df_targets.columns:
            sys.exit(
                f"[fetch_lightcurves] 'ID' column missing from {input_path}."
            )
        tic_ids = df_targets["ID"].dropna().astype(int).tolist()

        if args.n is not None:
            tic_ids = tic_ids[: args.n]
            log.info("Running on first %d / %d target(s).", len(tic_ids), len(df_targets))
        else:
            log.info("Running on all %d target(s).", len(tic_ids))

    # ── Run ────────────────────────────────────────────────────────────────────
    results = fetch_lightcurves(tic_ids, overwrite=args.overwrite)

    # ── Report ─────────────────────────────────────────────────────────────────
    _print_summary(results)


if __name__ == "__main__":
    main()
