"""
clean.py
--------
Column-level cleaning utilities for the TESS pipeline.

Currently exposes a single function:

    drop_null_columns(df, null_threshold=0.99)
        → (cleaned_df, null_report)

No row filtering, type casting, or feature engineering is done here.
"""

from __future__ import annotations

import pandas as pd

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
