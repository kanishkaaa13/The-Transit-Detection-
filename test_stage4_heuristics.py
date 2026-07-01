"""
test_stage4_heuristics.py
-------------------------
Unit tests for the standalone stage4_heuristics module.

Each of the five heuristic functions has at least:
  - one PASS case  (should_flag = False)
  - one FAIL case  (should_flag = True)

Run with:
    pytest test_stage4_heuristics.py -v
"""

import numpy as np
import pytest

from stage4_heuristics import (
    run_all_heuristics,
    test_blend_eb,
    test_density_consistency,
    test_odd_even_depth,
    test_radius_outlier,
    test_secondary_eclipse,
)


# ===========================================================================
# 1. test_blend_eb
# ===========================================================================

class TestBlendEB:
    def test_flagged_when_score_exceeds_threshold(self):
        """depth=0.08, contratio=0.5 → score=0.12 > 0.10 → flagged."""
        flagged, reason = test_blend_eb(depth=0.08, contratio=0.5)
        assert flagged is True
        assert "flag" in reason.lower()
        assert "0.120" in reason  # score to 3 d.p.

    def test_not_flagged_when_score_below_threshold(self):
        """depth=0.05, contratio=0.1 → score=0.055 ≤ 0.10 → clear."""
        flagged, reason = test_blend_eb(depth=0.05, contratio=0.1)
        assert flagged is False
        assert "clear" in reason.lower()

    def test_exactly_at_threshold_not_flagged(self):
        """score == threshold should NOT flag (strict >)."""
        flagged, _ = test_blend_eb(depth=0.1, contratio=0.0, threshold=0.1)
        assert flagged is False

    def test_custom_threshold(self):
        """Raises flag with a stricter custom threshold."""
        flagged, _ = test_blend_eb(depth=0.04, contratio=0.0, threshold=0.03)
        assert flagged is True

    def test_none_depth_returns_false(self):
        flagged, reason = test_blend_eb(depth=None, contratio=0.5)
        assert flagged is False
        assert "none" in reason.lower() or "insufficient" in reason.lower()

    def test_none_contratio_returns_false(self):
        flagged, _ = test_blend_eb(depth=0.2, contratio=None)
        assert flagged is False

    def test_zero_contratio(self):
        """contratio=0 → score equals depth exactly."""
        flagged, _ = test_blend_eb(depth=0.15, contratio=0.0, threshold=0.1)
        assert flagged is True

        flagged, _ = test_blend_eb(depth=0.05, contratio=0.0, threshold=0.1)
        assert flagged is False


# ===========================================================================
# 2. test_density_consistency
# ===========================================================================

class TestDensityConsistency:
    def test_flagged_on_large_mismatch(self):
        """30 % relative difference with default 30 % tolerance → exactly at boundary."""
        # |1.0 - 1.5| / 1.5 = 0.333 > 0.3 → should flag
        flagged, reason = test_density_consistency(rho_transit=1.0, rho_catalog=1.5)
        assert flagged is True
        assert "flag" in reason.lower()

    def test_not_flagged_on_small_mismatch(self):
        """|Δ|/ρ_cat = 0.05 / 1.05 ≈ 4.8 % < 30 % → clear."""
        flagged, reason = test_density_consistency(rho_transit=1.0, rho_catalog=1.05)
        assert flagged is False
        assert "consistent" in reason.lower()

    def test_perfect_match(self):
        flagged, _ = test_density_consistency(rho_transit=1.4, rho_catalog=1.4)
        assert flagged is False

    def test_custom_tight_tolerance(self):
        """|Δ|/ρ_cat = 0.05 < 0.30 but > 0.03 → flagged with tight tolerance."""
        flagged, _ = test_density_consistency(
            rho_transit=1.0, rho_catalog=1.05, tolerance=0.03
        )
        assert flagged is True

    def test_zero_catalog_density(self):
        flagged, reason = test_density_consistency(rho_transit=1.0, rho_catalog=0.0)
        assert flagged is False
        assert "zero" in reason.lower()

    def test_none_values(self):
        flagged, _ = test_density_consistency(rho_transit=None, rho_catalog=1.4)
        assert flagged is False

        flagged, _ = test_density_consistency(rho_transit=1.4, rho_catalog=None)
        assert flagged is False


# ===========================================================================
# 3. test_radius_outlier
# ===========================================================================

class TestRadiusOutlier:
    def test_flagged_above_limit(self):
        """2.5 R_Jup > 2.0 limit → EB candidate."""
        flagged, reason = test_radius_outlier(r_planet_jupiter=2.5)
        assert flagged is True
        assert "flag" in reason.lower() or "exceeds" in reason.lower()

    def test_not_flagged_within_limit(self):
        """1.2 R_Jup ≤ 2.0 → valid planet radius."""
        flagged, reason = test_radius_outlier(r_planet_jupiter=1.2)
        assert flagged is False
        assert "within" in reason.lower() or "limit" in reason.lower()

    def test_exactly_at_limit_not_flagged(self):
        """Strict > means exactly at limit should not flag."""
        flagged, _ = test_radius_outlier(r_planet_jupiter=2.0, limit=2.0)
        assert flagged is False

    def test_custom_limit(self):
        flagged, _ = test_radius_outlier(r_planet_jupiter=1.5, limit=1.0)
        assert flagged is True

    def test_none_radius(self):
        flagged, reason = test_radius_outlier(r_planet_jupiter=None)
        assert flagged is False
        assert "not available" in reason.lower() or "none" in reason.lower()

    def test_very_small_radius(self):
        """Earth-sized planet (~0.09 R_Jup) should clearly pass."""
        flagged, _ = test_radius_outlier(r_planet_jupiter=0.09)
        assert flagged is False


# ===========================================================================
# 4. test_secondary_eclipse
# ===========================================================================

class TestSecondaryEclipse:
    # ---- Boolean-flag mode ---------------------------------------------------

    def test_bool_true_flags(self):
        flagged, reason = test_secondary_eclipse(True)
        assert flagged is True
        assert "pre-computed" in reason.lower() or "flag" in reason.lower()

    def test_bool_false_clears(self):
        flagged, reason = test_secondary_eclipse(False)
        assert flagged is False
        assert "clear" in reason.lower() or "no" in reason.lower()

    # ---- Flux-array mode -----------------------------------------------------

    def test_flux_array_with_secondary_dip(self):
        """Place a 20 % dip at phase 0.5 → should be flagged."""
        flux = np.ones(100)
        flux[50] = 0.80   # deep secondary eclipse
        flagged, reason = test_secondary_eclipse(flux, period=1.0, t0=0.0)
        assert flagged is True
        assert "flag" in reason.lower() or "dip" in reason.lower()

    def test_flux_array_no_dip(self):
        """Flat light curve → no secondary eclipse."""
        flux = np.ones(100)
        flagged, reason = test_secondary_eclipse(flux, period=1.0, t0=0.0)
        assert flagged is False
        assert "clear" in reason.lower() or "no" in reason.lower()

    def test_flux_array_shallow_dip_not_flagged(self):
        """Dip of only 2 % (flux=0.98) should not trigger the 5 % threshold."""
        flux = np.ones(100)
        flux[50] = 0.98
        flagged, _ = test_secondary_eclipse(flux, period=1.0, t0=0.0)
        assert flagged is False

    def test_flux_array_missing_period(self):
        """If period not provided for flux-array mode, return False gracefully."""
        flux = np.ones(10)
        flux[5] = 0.8
        flagged, reason = test_secondary_eclipse(flux, period=None, t0=0.0)
        assert flagged is False
        assert "period" in reason.lower()

    def test_flux_array_too_short(self):
        """Arrays shorter than 4 points should return False gracefully."""
        flagged, reason = test_secondary_eclipse([0.8, 1.0, 0.8], period=1.0, t0=0.0)
        assert flagged is False

    def test_none_input(self):
        flagged, reason = test_secondary_eclipse(None)
        assert flagged is False


# ===========================================================================
# 5. test_odd_even_depth
# ===========================================================================

class TestOddEvenDepth:
    def test_flagged_on_large_difference(self):
        """Alternating depths of 1 % vs 20 % → clear EB pattern."""
        flagged, reason = test_odd_even_depth(
            depth_odd=[0.01, 0.012],
            depth_even=[0.20, 0.21],
        )
        assert flagged is True
        assert "flag" in reason.lower()

    def test_not_flagged_on_similar_depths(self):
        """Depths differ by ~0.001 → genuine planet signal."""
        flagged, reason = test_odd_even_depth(
            depth_odd=[0.010, 0.011],
            depth_even=[0.010, 0.012],
        )
        assert flagged is False
        assert "consistent" in reason.lower()

    def test_scalar_inputs(self):
        """Accept plain float scalars as well as lists."""
        flagged, _ = test_odd_even_depth(depth_odd=0.01, depth_even=0.20, tolerance=0.05)
        assert flagged is True

        flagged, _ = test_odd_even_depth(depth_odd=0.01, depth_even=0.015, tolerance=0.05)
        assert flagged is False

    def test_custom_strict_tolerance(self):
        """tolerance=0.001 catches tiny alternating signals."""
        flagged, _ = test_odd_even_depth(
            depth_odd=0.010, depth_even=0.011, tolerance=0.0005
        )
        assert flagged is True

    def test_none_inputs(self):
        flagged, _ = test_odd_even_depth(depth_odd=None, depth_even=[0.01])
        assert flagged is False

        flagged, _ = test_odd_even_depth(depth_odd=[0.01], depth_even=None)
        assert flagged is False

    def test_numpy_array_inputs(self):
        """Accept numpy arrays."""
        odd  = np.array([0.01, 0.012, 0.011])
        even = np.array([0.20, 0.21,  0.19])
        flagged, _ = test_odd_even_depth(odd, even, tolerance=0.1)
        assert flagged is True


# ===========================================================================
# 6. run_all_heuristics wrapper
# ===========================================================================

class TestRunAllHeuristics:
    def _clear_row(self) -> dict:
        return {
            "depth": 0.01,
            "contratio": 0.0,
            "rho_transit": 1.4,
            "rho_catalog": 1.4,
            "r_planet_jupiter": 1.0,
            "secondary_eclipse_flag": False,
            "depth_odd": [0.01, 0.010],
            "depth_even": [0.01, 0.011],
        }

    def test_returns_dict_with_all_five_keys(self):
        result = run_all_heuristics(self._clear_row())
        expected_keys = {
            "blend_eb",
            "density_consistency",
            "radius_outlier",
            "secondary_eclipse",
            "odd_even_depth",
        }
        assert set(result.keys()) == expected_keys

    def test_all_values_are_bool_str_tuples(self):
        result = run_all_heuristics(self._clear_row())
        for key, val in result.items():
            assert isinstance(val, tuple) and len(val) == 2, \
                f"{key} should return a 2-tuple"
            assert isinstance(val[0], (bool, np.bool_)), \
                f"{key}[0] should be bool, got {type(val[0])}"
            assert isinstance(val[1], str), \
                f"{key}[1] should be str"

    def test_all_clear_for_good_candidate(self):
        result = run_all_heuristics(self._clear_row())
        for key, (flagged, _) in result.items():
            assert flagged is False, f"{key} should be clear for a good candidate"

    def test_all_flagged_for_obvious_eb(self):
        eb_row = {
            "depth": 0.15,
            "contratio": 1.0,
            "rho_transit": 10.0,
            "rho_catalog": 1.4,
            "r_planet_jupiter": 3.5,
            "secondary_eclipse_flag": True,
            "depth_odd": [0.01],
            "depth_even": [0.30],
        }
        result = run_all_heuristics(eb_row)
        for key, (flagged, _) in result.items():
            assert flagged is True, f"{key} should be flagged for an obvious EB"

    def test_empty_row_does_not_crash(self):
        """Graceful handling of a completely empty dict."""
        result = run_all_heuristics({})
        assert len(result) == 5
        for _, (flagged, _) in result.items():
            assert flagged is False
