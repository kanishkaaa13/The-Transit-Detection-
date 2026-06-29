"""
download.py
-----------
Downloads the TESS Input Catalog (TIC) for the southern polar cap region.

Primary path  : astroquery.mast.Catalogs.query_region()
Fallback path : direct MAST REST API with paginated cone searches tiling the
                polar cap in six RA strips.

Usage
-----
    from src.config import CFG
    from src.download import download_tic_catalog

    df = download_tic_catalog(CFG)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests
from astropy import units as u
from astropy.coordinates import SkyCoord

from src.config import Config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Six RA centres that tile the full 360° polar cap in equal strips
_RA_CENTERS: list[float] = [30.0, 90.0, 150.0, 210.0, 270.0, 330.0]

_SLEEP_BETWEEN_PAGES: float = 0.5   # seconds
_SLEEP_BETWEEN_STRIPS: float = 1.0  # seconds


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _astroquery_download(config: Config) -> pd.DataFrame:
    """Primary path: use astroquery to fetch the TIC cone."""
    # Import lazily so that an ImportError is caught by the caller
    from astroquery.mast import Catalogs  # type: ignore

    coord = SkyCoord(ra=0.0, dec=config.DEC_CENTER, unit="deg")
    radius = config.SEARCH_RADIUS * u.deg

    print("  [astroquery] Querying TIC via astroquery.mast.Catalogs …")
    result = Catalogs.query_region(coord, radius=radius, catalog="TIC")
    df = result.to_pandas()
    print(f"  [astroquery] Retrieved {len(df):,} rows.")
    return df


def _mast_rest_download(config: Config) -> pd.DataFrame:
    """
    Fallback path: tile the polar cap with six RA-strip cone searches,
    paginating each strip through the MAST REST API.
    """
    all_frames: list[pd.DataFrame] = []

    for strip_idx, ra_center in enumerate(_RA_CENTERS, start=1):
        print(f"\n  [REST API] Strip {strip_idx}/{len(_RA_CENTERS)}  "
              f"(RA centre = {ra_center}°) …")

        page = 1
        strip_frames: list[pd.DataFrame] = []

        while True:
            params = {
                "service": "Mast.Catalogs.Tic.Cone",
                "params": {
                    "ra": ra_center,
                    "dec": config.DEC_CENTER,
                    "radius": config.SEARCH_RADIUS,
                },
                "format": "json",
                "pagesize": config.PAGESIZE,
                "page": page,
            }

            response = requests.post(
                config.MAST_URL,
                data={"request": json.dumps(params)},
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()

            rows = payload.get("data", [])
            n_rows = len(rows)
            print(f"    page {page:>4}  →  {n_rows:>6} rows fetched")

            if n_rows:
                strip_frames.append(pd.DataFrame(rows))

            if n_rows < config.PAGESIZE:
                # Last page for this strip
                break

            page += 1
            time.sleep(_SLEEP_BETWEEN_PAGES)

        if strip_frames:
            all_frames.append(pd.concat(strip_frames, ignore_index=True))

        time.sleep(_SLEEP_BETWEEN_STRIPS)

    if not all_frames:
        return pd.DataFrame()

    combined = pd.concat(all_frames, ignore_index=True)

    # Deduplicate on the TIC ID column
    if "ID" in combined.columns:
        before = len(combined)
        combined = combined.drop_duplicates(subset="ID").reset_index(drop=True)
        print(f"\n  [REST API] Deduplicated: {before:,} → {len(combined):,} rows.")

    return combined


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_tic_catalog(config: Config) -> pd.DataFrame:
    """
    Download the TIC southern polar-cap catalog and return it as a DataFrame.

    Behaviour
    ---------
    * If ``config.RAW_DIR / "tic_southern_polar.csv"`` already exists the file
      is loaded and returned immediately (no network request).
    * Otherwise the catalog is fetched via astroquery (primary) or the MAST
      REST API (fallback), then written to the CSV before returning.

    Parameters
    ----------
    config:
        Pipeline configuration (see ``src.config.Config``).

    Returns
    -------
    pd.DataFrame
        TIC rows for the southern polar cap region.
    """
    out_path: Path = config.RAW_DIR / "tic_southern_polar.csv"

    # ── Cache hit ──────────────────────────────────────────────────────────────
    if out_path.exists():
        print(f"[download] Cache hit — loading existing file: {out_path}")
        return pd.read_csv(out_path, low_memory=False)

    # ── Ensure output directory exists ─────────────────────────────────────────
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)

    # ── Primary: astroquery ────────────────────────────────────────────────────
    df: pd.DataFrame | None = None
    try:
        df = _astroquery_download(config)
    except Exception as exc:  # noqa: BLE001
        print(f"[download] astroquery failed ({exc}). Falling back to MAST REST API …")

    # ── Fallback: MAST REST API ────────────────────────────────────────────────
    if df is None or df.empty:
        try:
            df = _mast_rest_download(config)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Both download paths failed. Last error: {exc}"
            ) from exc

    # ── Persist ───────────────────────────────────────────────────────────────
    df.to_csv(out_path, index=False)
    print(f"\n[download] Saved {len(df):,} rows → {out_path}")

    return df


# ---------------------------------------------------------------------------
# __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from src.config import CFG

    df = download_tic_catalog(CFG)
    print("\n── Result ──────────────────────────────")
    print(f"Shape : {df.shape}")
    print(f"\nHead (3 rows):\n{df.head(3).to_string()}")
