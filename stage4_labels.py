"""
stage4_labels.py
----------------
Builds training labels for the Stage 4 false-positive classifier by joining
our Stage 1-3 candidate table with the NASA/MIT TOI catalog CSV.

Pipeline context
----------------
Stage 1 : sky-survey / MAST query   -> prime_targets.csv
Stage 2 : light-curve download
Stage 3 : BLS transit search        -> candidates dataframe
Stage 4 : this module (labelling)   -> labelled_candidates.csv
          then heuristics / ML

The TOI catalog is downloaded from:
    https://exofop.ipac.caltech.edu/tess/download_toi.php?sort=toi&output=csv

It contains one row per planet candidate per TIC target. The three comment
lines at the top (lines starting with #) must be skipped before CSV parsing.

Disposition -> class mapping
----------------------------
  CP  "Confirmed Planet"        -> "planet"
  KP  "Known Planet"            -> "planet"
  PC  "Planet Candidate"        -> "planet_candidate"   (weak positive)
  EB  "Eclipsing Binary"        -> "eclipsing_binary"
  FP  "False Positive"          -> "false_positive"
  O   "Other"                   -> "noise"
  V   "Variable"                -> "noise"
  IS  "Instrument Systematic"   -> "noise"

Usage
-----
    python stage4_labels.py \
        --candidates data/results/stage3_candidates.csv \
        --toi        toi/toi-catalog_2026-06-30.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Disposition -> class mapping table
# ---------------------------------------------------------------------------

#: Complete mapping of every raw TOI Disposition code to an internal class.
DISPOSITION_MAP: dict[str, str] = {
    "CP": "planet",             # Confirmed Planet
    "KP": "planet",             # Known Planet (previously confirmed elsewhere)
    "PC": "planet_candidate",   # Planet Candidate — uncertain, kept separate
    "EB": "eclipsing_binary",   # Eclipsing Binary
    "FP": "false_positive",     # False Positive (catch-all FP category)
    "O":  "noise",              # Other / unclassified
    "V":  "noise",              # Stellar variability / variable star
    "IS": "noise",              # Instrument Systematic
}

#: TOI catalog columns we retain in the merged output (in addition to TIC and TOI Disposition).
TOI_KEEP_COLS: list[str] = [
    "Full TOI ID",
    "Orbital Period (days) Value",
    "Transit Depth Value",
    "Transit Duration (hours) Value",
    "Signal-to-noise",
    "Star Radius Value",
    "Planet Radius Value",
]


# ---------------------------------------------------------------------------
# 1. Load TOI catalog
# ---------------------------------------------------------------------------

def load_toi_catalog(path: str | Path) -> pd.DataFrame:
    """
    Read the NASA/MIT TESS TOI catalog CSV, skipping the 3 leading comment lines.

    The catalog header looks like::

        # toi-catalog
        # Generated on 2026-06-30
        # Collection PK: 193
        pk,Parameter Source Pipeline,...

    Parameters
    ----------
    path : str or Path
        Path to the downloaded TOI catalog CSV file.

    Returns
    -------
    pd.DataFrame
        Parsed TOI catalog with ``TIC`` cast to ``int64``.

    Raises
    ------
    FileNotFoundError
        If the file does not exist at *path*.
    ValueError
        If the file contains fewer than 4 lines (3 comments + 1 header).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"TOI catalog not found at: {path}")

    log.info("Loading TOI catalog from: %s", path)
    df = pd.read_csv(path, skiprows=3, low_memory=False)

    if "TIC" not in df.columns:
        raise ValueError(
            f"Expected a 'TIC' column after skipping 3 comment lines in {path}. "
            f"Found columns: {list(df.columns[:8])} …"
        )

    df["TIC"] = pd.to_numeric(df["TIC"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["TIC"])
    df["TIC"] = df["TIC"].astype("int64")

    log.info(
        "TOI catalog loaded: %d rows, %d columns. "
        "Dispositions present: %s",
        len(df),
        len(df.columns),
        df["TOI Disposition"].value_counts().to_dict(),
    )
    return df


# ---------------------------------------------------------------------------
# 2. Disposition -> class mapping
# ---------------------------------------------------------------------------

def map_disposition_to_class(disposition: str) -> str:
    """
    Map a raw TOI Disposition string to one of our five target class labels.

    Parameters
    ----------
    disposition : str
        Raw disposition code from the TOI catalog (e.g. ``"CP"``, ``"EB"``).
        Leading/trailing whitespace is stripped and the value is upper-cased
        before lookup, so minor formatting differences are tolerated.

    Returns
    -------
    str
        One of: ``"planet"``, ``"planet_candidate"``, ``"eclipsing_binary"``,
        ``"false_positive"``, ``"noise"``.
        Unknown codes fall back to ``"noise"`` with a warning.

    Examples
    --------
    >>> map_disposition_to_class("CP")
    'planet'
    >>> map_disposition_to_class("EB")
    'eclipsing_binary'
    >>> map_disposition_to_class("PC")
    'planet_candidate'
    """
    code = str(disposition).strip().upper()
    mapped = DISPOSITION_MAP.get(code)
    if mapped is None:
        log.warning(
            "Unknown TOI disposition '%s' — falling back to 'noise'. "
            "Update DISPOSITION_MAP if this code is intentional.",
            disposition,
        )
        return "noise"
    return mapped


# ---------------------------------------------------------------------------
# 3. Join candidates with TOI labels
# ---------------------------------------------------------------------------

def join_candidates_with_labels(
    candidates_df: pd.DataFrame,
    toi_df: pd.DataFrame,
    candidates_tic_col: str = "ID",
) -> pd.DataFrame:
    """
    Merge the Stage 3 candidate table with TOI catalog dispositions.

    Matching strategy
    ~~~~~~~~~~~~~~~~~
    * Left-join on TIC ID so **all** pipeline candidates are retained,
      including those with no TOI counterpart.
    * Candidates with no match receive ``label = "unlabelled"`` — they
      can be used for inference but must be excluded from supervised training.
    * If a TIC appears multiple times in the TOI catalog (multiple planet
      candidates), the row with the best ``Signal-to-noise`` is kept so the
      join remains 1-to-1.

    Parameters
    ----------
    candidates_df : pd.DataFrame
        Stage 3 output table.  Must contain a TIC column (default name: ``ID``).
    toi_df : pd.DataFrame
        TOI catalog loaded by :func:`load_toi_catalog`.
    candidates_tic_col : str, optional
        Name of the TIC column in *candidates_df*.  Default: ``"ID"``.

    Returns
    -------
    pd.DataFrame
        Merged dataframe with an additional ``label`` column and selected
        TOI metadata columns.

    Raises
    ------
    KeyError
        If *candidates_tic_col* is not found in *candidates_df*.
    """
    if candidates_tic_col not in candidates_df.columns:
        raise KeyError(
            f"Column '{candidates_tic_col}' not found in candidates_df. "
            f"Available columns: {list(candidates_df.columns)}"
        )

    # --- Prepare TOI side -------------------------------------------------

    # Keep only columns we care about
    # Exclude 'TOI Disposition' from TOI_KEEP_COLS to avoid duplication
    toi_cols_available = ["TIC", "TOI Disposition"] + [
        c for c in TOI_KEEP_COLS
        if c in toi_df.columns and c not in ("TIC", "TOI Disposition")
    ]
    # Always work on a fresh copy so pandas never treats it as a view
    toi_work = toi_df[toi_cols_available].copy(deep=True)

    # De-duplicate: per TIC, keep the row with the highest SNR
    snr_col = "Signal-to-noise"
    if snr_col in toi_work.columns:
        toi_work[snr_col] = pd.to_numeric(toi_work[snr_col], errors="coerce")
        toi_work = (
            toi_work
            .sort_values(snr_col, ascending=False, na_position="last")
            .drop_duplicates(subset="TIC", keep="first")
            .reset_index(drop=True)
            .copy()   # guarantee a non-view copy after chaining
        )
    else:
        toi_work = (
            toi_work
            .drop_duplicates(subset="TIC", keep="first")
            .reset_index(drop=True)
            .copy()
        )

    # Add mapped label column via assign() — avoids SettingWithCopyWarning
    disp_series = toi_work["TOI Disposition"].astype(str).str.strip().str.upper()
    toi_slim = toi_work.assign(
        label=disp_series.map(DISPOSITION_MAP).fillna("noise")
    )

    log.info(
        "TOI table after de-duplication: %d unique TIC IDs", len(toi_slim)
    )

    # --- Prepare candidates side ------------------------------------------
    cand = candidates_df.copy()
    cand["_tic_key"] = pd.to_numeric(cand[candidates_tic_col], errors="coerce").astype("Int64")

    # --- Merge ------------------------------------------------------------
    merged = cand.merge(
        toi_slim.rename(columns={"TIC": "_tic_key"}),
        on="_tic_key",
        how="left",
    )
    merged = merged.drop(columns=["_tic_key"])

    # Fill missing labels
    merged["label"] = merged["label"].fillna("unlabelled")

    # --- Summary ----------------------------------------------------------
    n_total    = len(merged)
    n_matched  = (merged["label"] != "unlabelled").sum()
    n_unlabel  = (merged["label"] == "unlabelled").sum()

    log.info(
        "Join complete: %d candidates total | %d matched to TOI | %d unlabelled",
        n_total, n_matched, n_unlabel,
    )

    _print_class_balance(merged["label"])
    return merged


# ---------------------------------------------------------------------------
# Helper: class balance summary
# ---------------------------------------------------------------------------

def _print_class_balance(label_series: pd.Series) -> None:
    """Print a formatted class-balance table to stdout."""
    counts = label_series.value_counts()
    total  = counts.sum()

    print("\n" + "=" * 52)
    print("  CLASS BALANCE SUMMARY")
    print("=" * 52)
    print(f"  {'Class':<22} {'Count':>6}  {'%':>6}")
    print("-" * 52)
    for cls, cnt in counts.items():
        pct = 100.0 * cnt / total if total > 0 else 0.0
        print(f"  {cls:<22} {cnt:>6}  {pct:>5.1f}%")
    print("-" * 52)
    print(f"  {'TOTAL':<22} {total:>6}")
    print("=" * 52 + "\n")

    # Imbalance warning
    if "planet" in counts.index and "unlabelled" not in counts.index:
        minority = counts.min()
        majority = counts.max()
        ratio    = majority / minority if minority > 0 else float("inf")
        if ratio > 5:
            log.warning(
                "Class imbalance ratio is %.1fx — consider class_weight='balanced' "
                "or oversampling the minority class when training.",
                ratio,
            )


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Join Stage 3 candidates with TOI catalog labels.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--candidates",
        default="data/clean/prime_targets.csv",
        help="Path to Stage 3 candidates CSV (must contain a TIC column).",
    )
    p.add_argument(
        "--toi",
        default="toi/toi-catalog_2026-06-30.csv",
        help="Path to the downloaded TOI catalog CSV.",
    )
    p.add_argument(
        "--tic-col",
        default="ID",
        help="Name of the TIC column in the candidates CSV.",
    )
    p.add_argument(
        "--output",
        default="data/results/labelled_candidates.csv",
        help="Where to save the labelled candidates CSV.",
    )
    return p


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()

    # Load inputs
    toi_df        = load_toi_catalog(args.toi)
    candidates_df = pd.read_csv(args.candidates)

    log.info(
        "Candidates loaded: %d rows from %s", len(candidates_df), args.candidates
    )

    # Join and label
    labelled = join_candidates_with_labels(
        candidates_df, toi_df, candidates_tic_col=args.tic_col
    )

    # Save output
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    labelled.to_csv(out_path, index=False)
    log.info("Labelled candidates saved -> %s  (%d rows)", out_path, len(labelled))
    sys.exit(0)
