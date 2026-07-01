"""
stage4_heuristics.py
--------------------
Five deterministic false-positive vetting tests for Stage 4 of the
exoplanet detection pipeline.

Note: the public functions are named ``test_*`` by pipeline convention,
not because they are pytest tests.  Each function is explicitly marked
``__test__ = False`` at module level so pytest skips them during
collection.

Each test is a standalone function that returns a (bool, str) tuple:
  - bool  : True  → the flag is raised (false-positive indicator detected)
            False → target passes this test (no flag)
  - str   : human-readable reason / result description

None of these functions depend on stage4_features.py or any ML model.
They can be imported and tested independently.

Usage
-----
    from stage4_heuristics import run_all_heuristics

    result = run_all_heuristics({
        "depth": 0.08,
        "contratio": 0.5,
        "rho_transit": 2.5,
        "rho_catalog": 1.4,
        "r_planet_jupiter": 2.8,
        "secondary_eclipse_flag": True,
        "depth_odd": 0.01,
        "depth_even": 0.05,
    })
"""

from __future__ import annotations

import logging
from typing import Union

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Blend / Eclipsing-Binary depth test
# ---------------------------------------------------------------------------

def test_blend_eb(
    depth: float,
    contratio: float,
    threshold: float = 0.1,
) -> tuple[bool, str]:
    """
    Flag a likely diluted eclipsing binary or blended source.

    Uses the relation:  score = depth × (1 + contratio)

    A large ``contratio`` (flux contamination from a neighbour) amplifies
    the intrinsic depth of the diluted source.  If the de-diluted depth
    exceeds *threshold* the target is a candidate blend or EB.

    Parameters
    ----------
    depth : float
        Transit depth as a fraction (e.g. 0.01 for a 1 % dip).
    contratio : float
        Contamination ratio from the TIC catalog (dimensionless ≥ 0).
    threshold : float, optional
        De-diluted depth limit above which the flag is raised.
        Default: 0.1 (10 %).

    Returns
    -------
    (flagged, reason) : (bool, str)
        flagged is True if the blend/EB criterion is met.

    Examples
    --------
    >>> test_blend_eb(0.08, 0.5)
    (True, 'Blend/EB flag: depth*(1+contratio)=0.120 exceeds threshold 0.100')
    >>> test_blend_eb(0.05, 0.1)
    (False, 'Blend/EB clear: depth*(1+contratio)=0.055 ≤ threshold 0.100')
    """
    if depth is None or contratio is None:
        return False, "Blend/EB: insufficient data (depth or contratio is None)"

    score = float(depth) * (1.0 + float(contratio))
    if score > threshold:
        return (
            True,
            f"Blend/EB flag: depth*(1+contratio)={score:.3f} exceeds threshold {threshold:.3f}",
        )
    return (
        False,
        f"Blend/EB clear: depth*(1+contratio)={score:.3f} ≤ threshold {threshold:.3f}",
    )


# ---------------------------------------------------------------------------
# 2. Stellar-density consistency test
# ---------------------------------------------------------------------------

def test_density_consistency(
    rho_transit: float,
    rho_catalog: float,
    tolerance: float = 0.3,
) -> tuple[bool, str]:
    """
    Flag a density mismatch between the transit-derived stellar density and
    the catalog (TIC) stellar density.

    The transit light-curve encodes the stellar mean density via Kepler's
    third law.  A large discrepancy suggests a grazing geometry, a blended
    EB, or an incorrect stellar host.

    Parameters
    ----------
    rho_transit : float
        Stellar mean density inferred from the transit shape (g cm⁻³).
    rho_catalog : float
        Catalog stellar density from the TIC (g cm⁻³).
    tolerance : float, optional
        Maximum allowed fractional difference |Δρ|/ρ_cat before flagging.
        Default: 0.3 (30 %).

    Returns
    -------
    (flagged, reason) : (bool, str)
    """
    if rho_transit is None or rho_catalog is None:
        return False, "Density consistency: insufficient data (None value)"

    rho_cat = float(rho_catalog)
    rho_tr  = float(rho_transit)

    if rho_cat == 0.0:
        return False, "Density consistency: catalog density is zero — cannot compute ratio"

    rel_diff = abs(rho_tr - rho_cat) / abs(rho_cat)

    if rel_diff > tolerance:
        return (
            True,
            (
                f"Density mismatch flag: |Δρ|/ρ_cat={rel_diff:.3f} "
                f"exceeds tolerance {tolerance:.3f} "
                f"(transit={rho_tr:.3g}, catalog={rho_cat:.3g} g/cc)"
            ),
        )
    return (
        False,
        (
            f"Density consistent: |Δρ|/ρ_cat={rel_diff:.3f} "
            f"≤ tolerance {tolerance:.3f}"
        ),
    )


# ---------------------------------------------------------------------------
# 3. Planet-radius outlier test
# ---------------------------------------------------------------------------

def test_radius_outlier(
    r_planet_jupiter: float,
    limit: float = 2.0,
) -> tuple[bool, str]:
    """
    Flag if the inferred planet radius exceeds the physical planet limit.

    Objects larger than ~2 R_Jupiter are almost certainly low-mass stars
    or brown dwarfs rather than planets (eclipsing binary scenario).

    Parameters
    ----------
    r_planet_jupiter : float
        Estimated planet radius in Jupiter radii (R_Jup).
    limit : float, optional
        Upper radius limit in R_Jup.  Default: 2.0 R_Jup.

    Returns
    -------
    (flagged, reason) : (bool, str)
    """
    if r_planet_jupiter is None:
        return False, "Radius outlier: radius not available"

    r = float(r_planet_jupiter)
    if r > limit:
        return (
            True,
            (
                f"Radius outlier flag: R_planet={r:.2f} R_Jup "
                f"exceeds limit {limit:.2f} R_Jup — likely eclipsing binary"
            ),
        )
    return (
        False,
        f"Radius within limit: R_planet={r:.2f} R_Jup ≤ {limit:.2f} R_Jup",
    )


# ---------------------------------------------------------------------------
# 4. Secondary eclipse test
# ---------------------------------------------------------------------------

def test_secondary_eclipse(
    light_curve_or_flag: Union[bool, "np.ndarray", list],
    period: float | None = None,
    t0: float | None = None,
) -> tuple[bool, str]:
    """
    Flag if a secondary eclipse signal is present.

    Accepts two modes:
    * **Boolean flag** — pass a precomputed ``True``/``False`` value directly.
    * **Light-curve array** — pass a 1-D flux array; the function phase-folds
      it and checks for a significant dip near phase 0.5 (secondary eclipse
      position for a circular orbit), using a depth threshold of 0.05 (5 %).

    Parameters
    ----------
    light_curve_or_flag : bool, array-like, or None
        Either a precomputed boolean secondary-eclipse flag, or a 1-D array
        of normalised flux values.
    period : float, optional
        Orbital period in days.  Required when a flux array is supplied.
    t0 : float, optional
        Reference mid-transit time (BTJD).  Defaults to 0 if not provided.

    Returns
    -------
    (flagged, reason) : (bool, str)
    """
    # --- Mode 1: pre-computed boolean flag ---
    if isinstance(light_curve_or_flag, (bool, np.bool_)):
        if light_curve_or_flag:
            return True, "Secondary eclipse flag: pre-computed flag indicates secondary eclipse"
        return False, "Secondary eclipse clear: no secondary eclipse reported"

    # --- Mode 2: flux array --- 
    flux = light_curve_or_flag
    if flux is None:
        return False, "Secondary eclipse: no data provided"

    flux_arr = np.asarray(flux, dtype=float)
    if flux_arr.ndim != 1 or len(flux_arr) < 4:
        return False, "Secondary eclipse: insufficient flux data for analysis"

    if period is None or float(period) <= 0.0:
        return False, "Secondary eclipse: valid period required for flux-array analysis"

    t0_val = float(t0) if t0 is not None else 0.0
    period_val = float(period)

    # Build a synthetic time axis spanning exactly one period
    times = np.linspace(0.0, period_val, len(flux_arr), endpoint=False) + t0_val
    phases = np.mod((times - t0_val) / period_val, 1.0)

    # Find the flux value closest to phase 0.5
    idx = int(np.argmin(np.abs(phases - 0.5)))
    phase_flux = float(flux_arr[idx])

    # A 5 % secondary dip threshold (flux < 0.95 of normalised continuum)
    secondary_dip_threshold = 0.95
    if phase_flux < secondary_dip_threshold:
        return (
            True,
            (
                f"Secondary eclipse flag: flux={phase_flux:.3f} at phase~0.5 "
                f"(dip depth={(1.0 - phase_flux)*100:.1f} %) "
                f"exceeds detection threshold"
            ),
        )
    return (
        False,
        (
            f"Secondary eclipse clear: flux={phase_flux:.3f} at phase~0.5 "
            f"(no significant dip detected)"
        ),
    )


# ---------------------------------------------------------------------------
# 5. Odd/even transit depth test
# ---------------------------------------------------------------------------

def test_odd_even_depth(
    depth_odd: Union[float, list, "np.ndarray"],
    depth_even: Union[float, list, "np.ndarray"],
    tolerance: float = 0.1,
) -> tuple[bool, str]:
    """
    Flag if odd-numbered and even-numbered transit depths differ significantly.

    In a true planetary system all transits have the same depth.
    An alternating depth pattern is the hallmark of an unresolved eclipsing
    binary where the primary and secondary eclipses are misidentified as
    consecutive transits of a single object.

    Parameters
    ----------
    depth_odd : float or array-like
        Depth(s) measured at odd-numbered transit events (dimensionless fraction).
    depth_even : float or array-like
        Depth(s) measured at even-numbered transit events.
    tolerance : float, optional
        Absolute difference threshold between mean odd and even depths.
        Default: 0.1 (10 percentage points).

    Returns
    -------
    (flagged, reason) : (bool, str)
    """
    if depth_odd is None or depth_even is None:
        return False, "Odd/even test: insufficient data (None value)"

    # Accept both scalar and array inputs
    odd_arr  = np.atleast_1d(np.asarray(depth_odd,  dtype=float))
    even_arr = np.atleast_1d(np.asarray(depth_even, dtype=float))

    if odd_arr.size == 0 or even_arr.size == 0:
        return False, "Odd/even test: empty depth arrays"

    odd_mean  = float(np.nanmean(odd_arr))
    even_mean = float(np.nanmean(even_arr))
    diff = abs(odd_mean - even_mean)

    if diff > tolerance:
        return (
            True,
            (
                f"Odd/even depth flag: |mean_odd - mean_even|={diff:.4f} "
                f"exceeds tolerance {tolerance:.4f} "
                f"(odd={odd_mean:.4f}, even={even_mean:.4f}) — possible EB"
            ),
        )
    return (
        False,
        (
            f"Odd/even depths consistent: |Δ|={diff:.4f} "
            f"≤ tolerance {tolerance:.4f}"
        ),
    )


# ---------------------------------------------------------------------------
# Wrapper: run all five heuristics
# ---------------------------------------------------------------------------

def run_all_heuristics(row: dict) -> dict:
    """
    Run all five false-positive heuristic tests against a single target row.

    The ``row`` dict should contain the following keys (missing keys are
    handled gracefully by each individual test):

    =========================================  ======================================
    Key                                        Description
    =========================================  ======================================
    depth                                      Transit depth fraction
    contratio                                  TIC contamination ratio
    rho_transit                                Transit-derived stellar density (g/cc)
    rho_catalog                                Catalog stellar density (g/cc)
    r_planet_jupiter                           Inferred planet radius (R_Jup)
    secondary_eclipse_flag  *or* light_curve   Pre-computed bool or flux array
    period                                     Orbital period (days) — for LC array
    t0                                         Mid-transit epoch — for LC array
    depth_odd                                  Odd-transit depth(s)
    depth_even                                 Even-transit depth(s)
    =========================================  ======================================

    Parameters
    ----------
    row : dict
        Dict of parameters for one candidate target.

    Returns
    -------
    dict
        ``{test_name: (flagged: bool, reason: str)}`` for all five tests.
    """
    results: dict[str, tuple[bool, str]] = {}

    # 1. Blend / EB depth test
    results["blend_eb"] = test_blend_eb(
        depth=row.get("depth"),
        contratio=row.get("contratio"),
    )

    # 2. Density consistency
    results["density_consistency"] = test_density_consistency(
        rho_transit=row.get("rho_transit"),
        rho_catalog=row.get("rho_catalog"),
    )

    # 3. Radius outlier
    results["radius_outlier"] = test_radius_outlier(
        r_planet_jupiter=row.get("r_planet_jupiter"),
    )

    # 4. Secondary eclipse — accept pre-computed flag OR raw light curve
    sec_input = row.get("secondary_eclipse_flag", row.get("light_curve"))
    results["secondary_eclipse"] = test_secondary_eclipse(
        light_curve_or_flag=sec_input,
        period=row.get("period"),
        t0=row.get("t0"),
    )

    # 5. Odd/even depth
    results["odd_even_depth"] = test_odd_even_depth(
        depth_odd=row.get("depth_odd"),
        depth_even=row.get("depth_even"),
    )

    n_flags = sum(flagged for flagged, _ in results.values())
    logger.debug(
        "run_all_heuristics: %d / %d tests flagged", n_flags, len(results)
    )
    return results


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Prevent pytest from collecting the public test_* API functions as fixtures
# ---------------------------------------------------------------------------

test_blend_eb.__test__ = False          # type: ignore[attr-defined]
test_density_consistency.__test__ = False  # type: ignore[attr-defined]
test_radius_outlier.__test__ = False    # type: ignore[attr-defined]
test_secondary_eclipse.__test__ = False  # type: ignore[attr-defined]
test_odd_even_depth.__test__ = False    # type: ignore[attr-defined]


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    sample_row = {
        "depth":                  0.09,
        "contratio":              0.5,
        "rho_transit":            2.8,
        "rho_catalog":            1.4,
        "r_planet_jupiter":       2.5,
        "secondary_eclipse_flag": True,
        "depth_odd":              [0.01, 0.012],
        "depth_even":             [0.05, 0.055],
    }

    print("\n" + "=" * 70)
    print("STAGE 4 HEURISTIC VETTING — SMOKE TEST")
    print("=" * 70)
    all_results = run_all_heuristics(sample_row)
    for test_name, (flagged, reason) in all_results.items():
        flag_str = "🚩 FLAGGED" if flagged else "✅ PASS   "
        print(f"  {flag_str}  [{test_name:25s}]  {reason}")
    print("=" * 70)
