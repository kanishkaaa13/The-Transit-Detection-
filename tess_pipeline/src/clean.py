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

add_derived_features(df)
    Add spectral type, brightness tier, colour indices, distance, proper
    motion, and the prime_target boolean flag.
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


# ---------------------------------------------------------------------------
# Colour index
# ---------------------------------------------------------------------------

def compute_bprp(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive the Gaia BP - RP colour index.

    Adds the column ``bp_rp = gaiabp - gaiarp`` to a copy of *df*.
    The result is NaN wherever either source magnitude is missing.
    The original ``gaiabp`` and ``gaiarp`` columns are preserved.

    Parameters
    ----------
    df:
        DataFrame containing ``gaiabp`` and ``gaiarp`` after
        ``cast_column_types`` has been applied.

    Returns
    -------
    pd.DataFrame
        Copy of the input DataFrame with the new ``bp_rp`` column appended.
    """
    df = df.copy()
    df["bp_rp"] = df["gaiabp"] - df["gaiarp"]
    return df


# ---------------------------------------------------------------------------
# Teff calibration model
# ---------------------------------------------------------------------------

def fit_teff_calibration(df: pd.DataFrame, degree: int = 3) -> Pipeline:
    """
    Fit a polynomial Ridge regression to predict Teff from Gaia BP-RP colour.

    Training set
    ------------
    Rows where both ``bp_rp`` and ``Teff`` are non-NaN **and** pass the
    quality cuts:

    * ``0.3 < bp_rp < 4.5``   (blue early-types through cool M-dwarfs)
    * ``2500 < Teff < 12000``  (excludes white dwarfs and extreme outliers)

    Model architecture
    ------------------
    ``PolynomialFeatures(degree=degree)`` → ``Ridge(alpha=1.0)``

    Parameters
    ----------
    df:
        DataFrame after ``compute_bprp`` has been applied.
    degree:
        Polynomial degree for the feature expansion.  Default is 3.

    Returns
    -------
    sklearn.pipeline.Pipeline
        Fitted calibration pipeline.  Pass directly to ``impute_teff``.
    """
    mask_train = (
        df["bp_rp"].notna()
        & df["Teff"].notna()
        & df["bp_rp"].between(0.3, 4.5, inclusive="neither")
        & df["Teff"].between(2500, 12000, inclusive="neither")
    )
    train = df.loc[mask_train]
    n_train = len(train)

    X_train = train["bp_rp"].to_numpy().reshape(-1, 1)
    y_train = train["Teff"].to_numpy()

    model = Pipeline([
        ("poly",  PolynomialFeatures(degree=degree, include_bias=True)),
        ("ridge", Ridge(alpha=1.0)),
    ])
    model.fit(X_train, y_train)

    r2 = model.score(X_train, y_train)

    cv_scores = cross_val_score(
        model, X_train, y_train,
        cv=5,
        scoring="neg_root_mean_squared_error",
    )
    cv_rmse = float(-cv_scores.mean())

    print(
        f"[clean] fit_teff_calibration:\n"
        f"  degree  : {degree}\n"
        f"  n_train : {n_train:,}\n"
        f"  R²      : {r2:.4f}\n"
        f"  CV RMSE : {cv_rmse:.1f} K  (5-fold neg_root_mean_squared_error)"
    )

    return model


# ---------------------------------------------------------------------------
# Teff imputation
# ---------------------------------------------------------------------------

def impute_teff(df: pd.DataFrame, model: Pipeline) -> pd.DataFrame:
    """
    Fill missing Teff values using the polynomial BP-RP calibration model.

    Procedure
    ---------
    1. Initialise ``Teff_source = 'catalog'`` and ``Teff_imputed = False``
       for every row.
    2. For rows where ``Teff`` is NaN **and** ``bp_rp`` is not NaN, predict
       Teff with *model* and clip predictions to [2300, 12 000] K.
    3. Fill those NaN cells with the clipped predictions.
    4. Mark imputed rows: ``Teff_source = 'bp_rp_poly'``,
       ``Teff_imputed = True``.
    5. Rows still NaN after imputation get ``Teff_source = 'missing'``.

    Parameters
    ----------
    df:
        DataFrame after ``compute_bprp`` (and optionally ``cast_column_types``).
    model:
        Fitted sklearn Pipeline returned by ``fit_teff_calibration``.

    Returns
    -------
    pd.DataFrame
        Copy of *df* with ``Teff`` partially filled and two new bookkeeping
        columns: ``Teff_source`` (str) and ``Teff_imputed`` (bool).
    """
    df = df.copy()
    n_total = len(df)

    # ── Bookkeeping columns ────────────────────────────────────────────────────
    df["Teff_source"]  = "catalog"
    df["Teff_imputed"] = False

    n_missing_before = int(df["Teff"].isna().sum())
    fill_rate_before = 1.0 - n_missing_before / n_total

    print(
        f"[clean] impute_teff:\n"
        f"  Teff fill rate BEFORE : {fill_rate_before:.2%}  "
        f"({n_total - n_missing_before:,} / {n_total:,} rows have Teff)"
    )

    # ── Imputation mask ────────────────────────────────────────────────────────
    mask_impute = df["Teff"].isna() & df["bp_rp"].notna()
    n_impute = int(mask_impute.sum())

    if n_impute > 0:
        X_pred = df.loc[mask_impute, "bp_rp"].to_numpy().reshape(-1, 1)
        y_pred = np.clip(model.predict(X_pred), 2300, 12000)

        df.loc[mask_impute, "Teff"]         = y_pred
        df.loc[mask_impute, "Teff_source"]  = "bp_rp_poly"
        df.loc[mask_impute, "Teff_imputed"] = True

    # ── Mark permanently missing ───────────────────────────────────────────────
    df.loc[df["Teff"].isna(), "Teff_source"] = "missing"

    n_missing_after = int(df["Teff"].isna().sum())
    fill_rate_after = 1.0 - n_missing_after / n_total

    print(
        f"  imputed               : {n_impute:,} rows\n"
        f"  Teff fill rate AFTER  : {fill_rate_after:.2%}  "
        f"({n_total - n_missing_after:,} / {n_total:,} rows have Teff)\n"
        f"  Teff_source breakdown :\n"
        f"{df['Teff_source'].value_counts().to_string()}"
    )

    return df


# ---------------------------------------------------------------------------
# Derived feature engineering
# ---------------------------------------------------------------------------

def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute and append a fixed set of derived columns to the TIC DataFrame.

    Columns added (in order)
    ------------------------
    SpType_est : str (categorical)
        Estimated spectral type binned from ``Teff``:

        ====  =========================
        Bin   Range (K)
        ====  =========================
        M     [0, 3700)
        K     [3700, 5200)
        G     [5200, 6000)
        F     [6000, 7500)
        A     [7500, 10000)
        B     [10000, 30000)
        O     [30000, ∞)
        ====  =========================

    Tmag_tier : str (categorical)
        TESS-magnitude brightness tier:
        ``<10``, ``10-12``, ``12-13``, ``13-14``, ``14-15``, ``>15``.

    bp_rp : float
        Gaia BP - RP colour (skipped if the column already exists from
        ``compute_bprp``).

    j_k : float
        Near-IR colour index ``Jmag - Kmag``.

    d_ly : float
        Catalogue distance converted to light-years (``d * 3.26156``).

    total_pm : float
        Total proper motion in mas yr⁻¹ (``sqrt(pmRA² + pmDEC²)``).
        NaN when either component is missing.

    prime_target : bool
        ``True`` for stars that are viable transit-search targets:

        * ``objType == "STAR"``
        * ``lumclass == "DWARF"``
        * ``wdflag != 1``
        * ``Tmag < 13.0``
        * ``disposition`` not in ``{"ARTIFACT", "DUPLICATE"}``
          (NaN disposition treated as "OK")

    Parameters
    ----------
    df:
        DataFrame after ``cast_column_types``, ``compute_bprp`` (optional),
        and ``impute_teff``.

    Returns
    -------
    pd.DataFrame
        Copy of *df* with the seven new columns appended.
    """
    df = df.copy()

    # ── 1. SpType_est ──────────────────────────────────────────────────────────
    _sp_bins   = [0, 3700, 5200, 6000, 7500, 10000, 30000, 1e9]
    _sp_labels = ["M", "K", "G", "F", "A", "B", "O"]
    df["SpType_est"] = pd.cut(
        df["Teff"],
        bins=_sp_bins,
        labels=_sp_labels,
        right=False,
    )

    # ── 2. Tmag_tier ───────────────────────────────────────────────────────────
    _tm_bins   = [float("-inf"), 10, 12, 13, 14, 15, float("inf")]
    _tm_labels = ["<10", "10-12", "12-13", "13-14", "14-15", ">15"]
    df["Tmag_tier"] = pd.cut(
        df["Tmag"],
        bins=_tm_bins,
        labels=_tm_labels,
    )

    # ── 3. bp_rp — skip if already present ────────────────────────────────────
    if "bp_rp" not in df.columns:
        df["bp_rp"] = df["gaiabp"] - df["gaiarp"]

    # ── 4. j_k ────────────────────────────────────────────────────────────────
    df["j_k"] = df["Jmag"] - df["Kmag"]

    # ── 5. d_ly ───────────────────────────────────────────────────────────────
    df["d_ly"] = df["d"] * 3.26156

    # ── 6. total_pm ───────────────────────────────────────────────────────────
    both_known = df["pmRA"].notna() & df["pmDEC"].notna()
    df["total_pm"] = np.where(
        both_known,
        np.sqrt(df["pmRA"] ** 2 + df["pmDEC"] ** 2),
        np.nan,
    )

    # ── 7. prime_target ───────────────────────────────────────────────────────
    # Fill NaN disposition with a neutral sentinel so the isin() check is safe
    disposition_safe = df["disposition"].fillna("OK") if "disposition" in df.columns \
        else pd.Series("OK", index=df.index)

    mask_prime = (
        (df["objType"].eq("STAR")   if "objType"   in df.columns else pd.Series(True, index=df.index))
        & (df["lumclass"].eq("DWARF") if "lumclass"  in df.columns else pd.Series(True, index=df.index))
        & (df["wdflag"].ne(1)         if "wdflag"    in df.columns else pd.Series(True, index=df.index))
        & (df["Tmag"].lt(13.0)        if "Tmag"      in df.columns else pd.Series(True, index=df.index))
        & ~disposition_safe.isin(["ARTIFACT", "DUPLICATE"])
    )
    df["prime_target"] = mask_prime

    # ── Progress prints ────────────────────────────────────────────────────────
    n_prime = int(df["prime_target"].sum())
    print(
        f"[clean] add_derived_features:\n"
        f"  prime_target == True : {n_prime:,} / {len(df):,} rows "
        f"({n_prime / len(df):.2%})\n"
        f"  SpType_est distribution:\n"
        f"{df['SpType_est'].value_counts().sort_index().to_string()}"
    )

    return df


# ---------------------------------------------------------------------------
# Master pipeline orchestrator
# ---------------------------------------------------------------------------

def run_cleaning_pipeline(config: Config) -> pd.DataFrame:
    """
    Run the full TIC cleaning pipeline end-to-end.

    Steps
    -----
    1. Load ``data/raw/tic_southern_polar.csv``
    2. Drop near-empty and hardcoded columns  (``drop_null_columns``)
    3. Cast columns to correct dtypes          (``cast_column_types``)
    4. Derive Gaia BP-RP colour index          (``compute_bprp``)
    5. Fit polynomial Teff calibration model   (``fit_teff_calibration``)
    6. Impute missing Teff values              (``impute_teff``)
    7. Add derived features & target flag      (``add_derived_features``)
    8. Save cleaned data to ``data/clean/tic_clean.parquet``
    9. Print final summary and return

    Parameters
    ----------
    config:
        Pipeline configuration (see ``src.config.Config``).

    Returns
    -------
    pd.DataFrame
        Fully cleaned and feature-engineered TIC DataFrame.
    """
    # ── Step 1: Load raw catalog ───────────────────────────────────────────────
    raw_path = config.RAW_DIR / "tic_southern_polar.csv"
    print(f"\n{'='*60}")
    print(f"[pipeline] Loading raw catalog: {raw_path}")
    df = pd.read_csv(raw_path, low_memory=False)
    print(f"[pipeline] Loaded {len(df):,} rows × {len(df.columns)} columns")

    # ── Step 2: Drop null-heavy and hardcoded columns ──────────────────────────
    print(f"\n{'─'*60}")
    df, _ = drop_null_columns(df, config=config)

    # ── Step 3: Cast to correct dtypes ────────────────────────────────────────
    print(f"\n{'─'*60}")
    df = cast_column_types(df)

    # ── Step 4: Derive BP-RP colour index ─────────────────────────────────────
    print(f"\n{'─'*60}")
    df = compute_bprp(df)

    # ── Step 5: Fit Teff calibration model ────────────────────────────────────
    print(f"\n{'─'*60}")
    model = fit_teff_calibration(df, degree=3)

    # ── Step 6: Impute missing Teff ───────────────────────────────────────────
    print(f"\n{'─'*60}")
    df = impute_teff(df, model)

    # ── Step 7: Add derived features ─────────────────────────────────────────
    print(f"\n{'─'*60}")
    df = add_derived_features(df)

    # ── Step 8: Save parquet ──────────────────────────────────────────────────
    config.CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.CLEAN_DIR / "tic_clean.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\n[pipeline] Saved cleaned data → {out_path}")

    # ── Step 9: Final summary ─────────────────────────────────────────────────
    n_prime       = int(df["prime_target"].sum()) if "prime_target" in df.columns else 0
    teff_fill_pct = df["Teff"].notna().mean() if "Teff" in df.columns else float("nan")

    print(
        f"\n{'='*60}\n"
        f"[pipeline] ✓ Cleaning complete\n"
        f"  Final shape      : {df.shape[0]:,} rows × {df.shape[1]} columns\n"
        f"  prime_target     : {n_prime:,} stars\n"
        f"  Teff fill rate   : {teff_fill_pct:.2%}\n"
        f"{'='*60}"
    )

    return df


# ---------------------------------------------------------------------------
# __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from src.config import Config as _Config

    _cfg = _Config()
    _df  = run_cleaning_pipeline(_cfg)
    print("Pipeline complete")
