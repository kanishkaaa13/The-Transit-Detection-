"""
stage4_labels.py
----------------
Builds training labels for the Stage 4 false-positive classifier by joining
our Stage 1-3 candidate table with the TOI catalog CSV.

Requirements:
- Function load_toi_catalog(path) -> pd.DataFrame that reads the CSV, skipping
  the 3 leading comment lines (lines starting with #)
- Function map_disposition_to_class(disposition: str) -> str mapping raw TOI
  Disposition values to our 5 target classes:
    - "CP" or "KP" -> "planet"
    - "EB" -> "eclipsing_binary"
    - "PC" -> "planet_candidate" (uncertain, kept separate)
    - "FP" -> "false_positive"
    - "O", "V", "IS" -> "noise"
- Function join_candidates_with_labels(candidates_df, toi_df) -> pd.DataFrame
  that merges on TIC and attaches the mapped class as a 'label' column
- Print a class balance summary (value_counts of the resulting label column)

Do not train any model in this file — labels only.
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

DISPOSITION_MAP: dict[str, str] = {
    "CP": "planet",             # Confirmed Planet
    "KP": "planet",             # Known Planet (previously confirmed elsewhere)
    "PC": "planet_candidate",   # Planet Candidate — uncertain, kept separate
    "EB": "eclipsing_binary",   # Eclipsing Binary
    "FP": "false_positive",     # False Positive
    "O":  "noise",              # Other
    "V":  "noise",              # Variable
    "IS": "noise",              # Instrument Systematic
}


def load_toi_catalog(path: str | Path) -> pd.DataFrame:
    """
    Reads the TOI catalog CSV, skipping the 3 leading comment lines.
    Casts the TIC column to int64 for clean merging.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"TOI catalog not found at: {path}")

    log.info("Loading TOI catalog from: %s", path)
    # Skipping the 3 leading comment lines
    df = pd.read_csv(path, skiprows=3, low_memory=False)

    if "TIC" not in df.columns:
        raise ValueError(
            f"Expected a 'TIC' column after skipping 3 comment lines in {path}. "
            f"Found columns: {list(df.columns[:8])} ..."
        )

    # Cast TIC to int64, filtering out any invalid/NaN values
    df["TIC"] = pd.to_numeric(df["TIC"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["TIC"])
    df["TIC"] = df["TIC"].astype("int64")

    log.info("TOI catalog loaded: %d rows", len(df))
    return df


def map_disposition_to_class(disposition: str) -> str:
    """
    Maps raw TOI Disposition values to our 5 target classes:
      - "CP" or "KP" -> "planet"
      - "EB" -> "eclipsing_binary"
      - "PC" -> "planet_candidate"
      - "FP" -> "false_positive"
      - "O", "V", "IS" -> "noise"
    Unknown or missing dispositions fall back to "noise".
    """
    if pd.isna(disposition):
        return "noise"
    
    disp = str(disposition).strip().upper()
    mapped = DISPOSITION_MAP.get(disp)
    if mapped is None:
        log.warning("Unknown TOI disposition '%s' — mapping to 'noise'", disposition)
        return "noise"
    return mapped


def join_candidates_with_labels(
    candidates_df: pd.DataFrame,
    toi_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normalizes candidate TIC IDs, maps dispositions, and merges on TIC.
    Attaches the mapped class as a 'label' column.
    Prints a class balance summary.
    """
    # 1. Normalize candidates TIC ID column
    tic_col = None
    for potential_col in ["tic_id", "tic", "id", "TIC_ID", "TIC", "ID"]:
        for col in candidates_df.columns:
            if col.strip().lower() == potential_col.lower():
                tic_col = col
                break
        if tic_col:
            break

    if tic_col is None:
        raise KeyError(
            f"No TIC column found in candidates dataframe. "
            f"Columns available: {list(candidates_df.columns)}"
        )

    log.info("Using column '%s' as TIC identifier in candidates table", tic_col)
    candidates_copy = candidates_df.copy()

    # Strip prefixes like "TIC_" or "TIC-" if string, then convert to int64
    clean_tic = candidates_copy[tic_col].astype(str).str.replace(r"^TIC[-_]?", "", regex=True, case=False)
    candidates_copy["TIC"] = pd.to_numeric(clean_tic, errors="coerce").astype("Int64")
    
    # Drop rows where TIC is missing
    candidates_copy = candidates_copy.dropna(subset=["TIC"])
    candidates_copy["TIC"] = candidates_copy["TIC"].astype("int64")

    # 2. Prepare and de-duplicate the TOI table
    toi_slim = toi_df.copy()
    toi_slim["label"] = toi_slim["TOI Disposition"].apply(map_disposition_to_class)

    # De-duplicate per TIC, keeping highest Signal-to-noise if present
    if "Signal-to-noise" in toi_slim.columns:
        toi_slim["Signal-to-noise"] = pd.to_numeric(toi_slim["Signal-to-noise"], errors="coerce")
        toi_slim = toi_slim.sort_values("Signal-to-noise", ascending=False, na_position="last")
    
    toi_slim = toi_slim.drop_duplicates(subset=["TIC"], keep="first")

    # 3. Merge candidates with labels and select relevant TOI columns
    toi_cols = [
        "TIC",
        "label",
        "TOI Disposition",
        "Orbital Period (days) Value",
        "Transit Depth Value",
        "Transit Duration (hours) Value",
    ]
    # Filter to only keep columns that actually exist in toi_slim
    toi_cols = [col for col in toi_cols if col in toi_slim.columns]

    merged = candidates_copy.merge(
        toi_slim[toi_cols],
        on="TIC",
        how="left"
    )

    # Fill unlabelled candidates with 'unlabelled'
    merged["label"] = merged["label"].fillna("unlabelled")

    # 4. Print class balance summary
    _print_class_balance(merged["label"])

    return merged


def _print_class_balance(label_series: pd.Series) -> None:
    """Prints a formatted class balance summary table."""
    counts = label_series.value_counts()
    total = counts.sum()

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


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Join Stage 3 candidates with TOI catalog labels.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--candidates",
        default="data/results/stage2_candidates.csv",
        help="Path to candidates CSV (must contain a TIC column).",
    )
    p.add_argument(
        "--toi",
        default="toi/toi-catalog_2026-06-30.csv",
        help="Path to the downloaded TOI catalog CSV.",
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
    toi_df = load_toi_catalog(args.toi)
    candidates_df = pd.read_csv(args.candidates)

    log.info("Candidates loaded: %d rows from %s", len(candidates_df), args.candidates)

    # Join and label
    labelled = join_candidates_with_labels(candidates_df, toi_df)

    # Save output
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    labelled.to_csv(out_path, index=False)
    log.info("Labelled candidates saved -> %s  (%d rows)", out_path, len(labelled))
    sys.exit(0)
