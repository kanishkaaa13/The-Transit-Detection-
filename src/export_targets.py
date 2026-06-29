"""
export_targets.py
-----------------
Exports the final list of prime transit-search targets from the cleaned TIC
catalog to data/clean/prime_targets.csv.

This CSV is the hand-off artifact between Phase 1 (catalog cleaning) and
Phase 2 (light-curve download).  No Phase 2 logic is included here.

Usage
-----
    python -m src.export_targets
"""

from __future__ import annotations

import pandas as pd

from src.config import Config

# ---------------------------------------------------------------------------
# Columns to include in the output CSV
# ---------------------------------------------------------------------------

_OUTPUT_COLS: list[str] = [
    # Identifiers
    "ID", "ra", "dec",
    # Photometry
    "Tmag", "e_Tmag",
    # Stellar parameters
    "Teff", "Teff_source", "Teff_imputed",
    "logg", "rad", "mass", "rho", "lum",
    # Astrometry / environment
    "d", "ebv", "contratio", "priority",
    # Derived features
    "SpType_est", "Tmag_tier", "bp_rp", "j_k", "total_pm",
    # Classification flags
    "wdflag", "lumclass", "objType", "disposition",
    # Cross-match IDs
    "GAIA", "TWOMASS", "ALLWISE",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_prime_targets(config: Config) -> pd.DataFrame:
    """
    Filter, sort, and export prime transit-search targets.

    Steps
    -----
    1. Load ``data/clean/tic_clean.parquet``.
    2. Keep rows where ``prime_target == True``.
    3. Sort by ``Tmag`` ascending (brightest first).
    4. Reset the index.
    5. Select the canonical output columns (skipping any absent ones).
    6. Save to ``data/clean/prime_targets.csv`` (no index).
    7. Print a diagnostic summary.

    Parameters
    ----------
    config:
        Pipeline configuration (see ``src.config.Config``).

    Returns
    -------
    pd.DataFrame
        Filtered and sorted prime-targets DataFrame (all selected columns).
    """
    # ── Step 1: Load cleaned catalog ──────────────────────────────────────────
    parquet_path = config.CLEAN_DIR / "tic_clean.parquet"
    print(f"\n{'='*60}")
    print(f"[export] Loading: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    print(f"[export] Full catalog: {len(df):,} rows × {len(df.columns)} columns")

    # ── Step 2: Filter prime targets ──────────────────────────────────────────
    if "prime_target" not in df.columns:
        raise KeyError(
            "'prime_target' column not found. "
            "Run src.clean.run_cleaning_pipeline first."
        )
    prime = df[df["prime_target"] == True].copy()

    # ── Step 3: Sort by Tmag ascending ────────────────────────────────────────
    if "Tmag" in prime.columns:
        prime = prime.sort_values("Tmag", ascending=True)

    # ── Step 4: Reset index ───────────────────────────────────────────────────
    prime = prime.reset_index(drop=True)

    # ── Step 5: Select output columns (only those present) ────────────────────
    available = [c for c in _OUTPUT_COLS if c in prime.columns]
    missing   = [c for c in _OUTPUT_COLS if c not in prime.columns]
    if missing:
        print(f"[export] Note: {len(missing)} requested column(s) not in DataFrame "
              f"and will be skipped: {missing}")
    prime_out = prime[available]

    # ── Step 6: Save CSV ───────────────────────────────────────────────────────
    config.CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.CLEAN_DIR / "prime_targets.csv"
    prime_out.to_csv(out_path, index=False)

    # ── Step 7: Diagnostic summary ────────────────────────────────────────────
    n_prime = len(prime_out)

    # Tmag range
    if "Tmag" in prime_out.columns:
        tmag_min = prime_out["Tmag"].min()
        tmag_max = prime_out["Tmag"].max()
        tmag_str = f"{tmag_min:.3f} → {tmag_max:.3f}"
    else:
        tmag_str = "N/A"

    # SpType_est distribution
    if "SpType_est" in prime_out.columns:
        sptype_str = prime_out["SpType_est"].value_counts().to_string()
    else:
        sptype_str = "  (SpType_est not available)"

    # Teff_source distribution
    if "Teff_source" in prime_out.columns:
        teff_src_str = prime_out["Teff_source"].value_counts().to_string()
    else:
        teff_src_str = "  (Teff_source not available)"

    # contratio fill
    n_contratio = int(prime_out["contratio"].notna().sum()) \
        if "contratio" in prime_out.columns else 0

    # rad fill  (needed for R_planet calculation)
    n_rad = int(prime_out["rad"].notna().sum()) \
        if "rad" in prime_out.columns else 0

    # mass fill  (needed for semi-major axis)
    n_mass = int(prime_out["mass"].notna().sum()) \
        if "mass" in prime_out.columns else 0

    print(
        f"\n{'='*60}\n"
        f"[export] ✓ Prime Targets Summary\n"
        f"{'─'*60}\n"
        f"  Total prime targets    : {n_prime:,}\n"
        f"  Tmag range             : {tmag_str}\n"
        f"  Output columns         : {len(available)}\n"
        f"  Saved →                : {out_path}\n"
        f"\n  SpType_est distribution:\n{sptype_str}\n"
        f"\n  Teff_source distribution:\n{teff_src_str}\n"
        f"\n  contratio filled       : {n_contratio:,} / {n_prime:,} "
        f"({n_contratio / n_prime:.1%})\n"
        f"  rad filled             : {n_rad:,} / {n_prime:,} "
        f"({n_rad / n_prime:.1%})  [needed for R_planet]\n"
        f"  mass filled            : {n_mass:,} / {n_prime:,} "
        f"({n_mass / n_prime:.1%})  [needed for semi-major axis]\n"
        f"{'='*60}"
    )

    return prime_out


# ---------------------------------------------------------------------------
# __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from src.config import Config as _Config

    _cfg = _Config()
    df   = export_prime_targets(_cfg)
    print(f"\nReturned DataFrame shape: {df.shape}")
