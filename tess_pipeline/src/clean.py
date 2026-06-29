"""
clean.py
--------
Column-level cleaning utilities for the TESS pipeline.

Functions
---------
drop_null_columns(df, null_threshold=0.99, config=None)
    Remove near-empty columns and produce a null-statistics report.

cast_column_types(df)
    Cast TIC columns to their correct pandas dtypes using errors='coerce'.

compute_bprp(df)
    Derive the Gaia BP-RP colour index column.

fit_teff_calibration(df, degree=3)
    Fit a polynomial Ridge regression to predict Teff from BP-RP colour.

impute_teff(df, model)
    Fill missing Teff values using the fitted calibration model.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures

from src.config import Config

# ---------------------------------------------------------------------------
# Columns to always remove regardless of their null percentage
# ---------------------------------------------------------------------------

_HARDCODED_DROP: list[str] = [
    "HIP",
    "KIC",
    "SDSS",
    "umag",
    "e_umag",
    "gmag",
    "e_gmag",
    "rmag",
    "e_rmag",
    "imag",
    "e_imag",
    "zmag",
    "e_zmag",
    "MH",
    "e_MH",
    "starchareFlag",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def drop_null_columns(
    df: pd.DataFrame,
    null_threshold: float = 0.99,
    config: Config | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Remove near-empty columns from a TIC DataFrame and produce a null report.

    Parameters
    ----------
    df:
        Raw TIC DataFrame as loaded from ``data/raw/tic_southern_polar.csv``.
    null_threshold:
        Columns whose null fraction is >= this value are dropped.
        Default is 0.99 (≥ 99 % null).
    config:
        Pipeline config used to resolve the output path for the null report.
        If *None*, the report is saved relative to the current working
        directory at ``data/clean/null_report.csv``.

    Returns
    -------
    cleaned_df:
        DataFrame with identified columns removed.
    null_report:
        DataFrame cataloguing null statistics for every column that was
        present *before* cleaning, sorted by ``null_pct`` descending.
        Columns: ``column``, ``null_count``, ``null_pct``, ``fill_pct``,
        ``dtype``, ``n_unique``.
    """
    n_rows = len(df)

    # ── Step 1: null fraction for every column ─────────────────────────────────
    null_pct: pd.Series = df.isnull().mean()

    # ── Step 2: columns identified by threshold ────────────────────────────────
    threshold_drops: list[str] = null_pct[null_pct >= null_threshold].index.tolist()

    # ── Step 3: union with hardcoded list (keep only columns that exist in df) ──
    hardcoded_present: list[str] = [c for c in _HARDCODED_DROP if c in df.columns]
    all_drops: list[str] = list(dict.fromkeys(threshold_drops + hardcoded_present))

    # ── Step 4: build the null_report BEFORE dropping anything ────────────────
    report_rows: list[dict] = []
    for col in df.columns:
        nc = int(df[col].isnull().sum())
        np_ = nc / n_rows if n_rows else 0.0
        report_rows.append(
            {
                "column": col,
                "null_count": nc,
                "null_pct": round(np_, 6),
                "fill_pct": round(1.0 - np_, 6),
                "dtype": str(df[col].dtype),
                "n_unique": int(df[col].nunique(dropna=False)),
            }
        )

    null_report: pd.DataFrame = (
        pd.DataFrame(report_rows)
        .sort_values("null_pct", ascending=False)
        .reset_index(drop=True)
    )

    # ── Step 5: actually drop the columns ──────────────────────────────────────
    cleaned_df: pd.DataFrame = df.drop(columns=all_drops, errors="ignore")

    # ── Step 6: save null_report ───────────────────────────────────────────────
    if config is not None:
        report_path = config.CLEAN_DIR / "null_report.csv"
        config.CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    else:
        from pathlib import Path
        report_path = Path("data/clean/null_report.csv")
        report_path.parent.mkdir(parents=True, exist_ok=True)

    null_report.to_csv(report_path, index=False)

    # ── Step 7: progress print ─────────────────────────────────────────────────
    n_original = len(df.columns)
    n_dropped = len(all_drops)
    n_remaining = len(cleaned_df.columns)

    print(
        f"[clean] drop_null_columns:\n"
        f"  threshold   : null_pct >= {null_threshold:.0%}\n"
        f"  by threshold: {len(threshold_drops)} columns\n"
        f"  hardcoded   : {len(hardcoded_present)} columns  "
        f"({sum(1 for c in hardcoded_present if c not in threshold_drops)} "
        f"additional beyond threshold)\n"
        f"  ─────────────────────────────────\n"
        f"  total dropped  : {n_dropped} / {n_original}\n"
        f"  columns remain : {n_remaining}\n"
        f"  null report saved → {report_path}"
    )

    return cleaned_df, null_report


# ---------------------------------------------------------------------------
# Type casting
# ---------------------------------------------------------------------------

#: Columns to cast to pandas nullable Int64
_INT64_COLS: list[str] = [
    "ID",
    "objID",
]

#: Columns to cast to pandas nullable Int8
_INT8_COLS: list[str] = [
    "wdflag",
    "raddflag",
]

#: Columns to cast to float64
#  Note: "plx" and "e_plx" appear twice in the spec; deduplication is handled
#  inside the function so casting each column only once.
_FLOAT64_COLS: list[str] = [
    "ra", "dec", "pmRA", "e_pmRA", "pmDEC", "e_pmDEC", "plx", "e_plx",
    "gallong", "gallat", "eclong", "eclat",
    "Bmag", "e_Bmag", "Vmag", "e_Vmag",
    "Jmag", "e_Jmag", "Hmag", "e_Hmag", "Kmag", "e_Kmag",
    "w1mag", "e_w1mag", "w2mag", "e_w2mag", "w3mag", "e_w3mag", "w4mag", "e_w4mag",
    "GAIAmag", "e_GAIAmag", "gaiabp", "e_gaiabp", "gaiarp", "e_gaiarp",
    "Tmag", "e_Tmag", "Teff", "e_Teff", "logg", "e_logg",
    "rad", "e_rad", "mass", "e_mass", "rho", "e_rho", "lum", "e_lum",
    "d", "e_d", "ebv", "e_ebv", "contratio", "priority",
    "eneg_Mass", "epos_Mass", "eneg_Rad", "epos_Rad",
    "eneg_rho", "epos_rho", "eneg_logg", "epos_logg",
    "eneg_lum", "epos_lum", "eneg_dist", "epos_dist",
    "eneg_Teff", "epos_Teff", "eneg_EBV", "epos_EBV",
    "e_RA", "e_Dec", "RA_orig", "Dec_orig", "e_RA_orig", "e_Dec_orig",
]


def cast_column_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cast TIC DataFrame columns to their correct pandas dtypes.

    Casting is applied only to columns that are *present* in ``df``; missing
    columns are silently skipped.  All numeric conversions use
    ``pd.to_numeric(errors='coerce')`` so malformed or non-numeric cell values
    become ``NaN`` rather than raising an exception.

    Type mapping
    ------------
    * ``Int64`` (nullable integer) : ID, objID
    * ``Int8``  (nullable integer) : wdflag, raddflag
    * ``float64``                  : all astrometric, photometric, and
                                     stellar-parameter columns
                                     (see ``_FLOAT64_COLS``)

    Parameters
    ----------
    df:
        DataFrame to cast. A copy is made; the original is not mutated.

    Returns
    -------
    pd.DataFrame
        DataFrame with updated dtypes.
    """
    df = df.copy()
    n_cast = 0

    # ── Int64 (nullable) ───────────────────────────────────────────────────────
    for col in _INT64_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            n_cast += 1

    # ── Int8 (nullable) ────────────────────────────────────────────────────────
    for col in _INT8_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int8")
            n_cast += 1

    # ── float64 ───────────────────────────────────────────────────────────────
    # Deduplicate _FLOAT64_COLS while preserving order so each column is only
    # cast once even though the spec lists "plx"/"e_plx" twice.
    seen: set[str] = set()
    for col in _FLOAT64_COLS:
        if col in df.columns and col not in seen:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
            seen.add(col)
            n_cast += 1

    n_int64_found  = sum(1 for c in _INT64_COLS  if c in df.columns)
    n_int8_found   = sum(1 for c in _INT8_COLS   if c in df.columns)
    n_float64_found = len(seen)

    print(
        f"[clean] cast_column_types: successfully cast {n_cast} column(s)  "
        f"(Int64={n_int64_found}, Int8={n_int8_found}, float64={n_float64_found}; "
        f"skipped any absent columns)"
    )

    return df
