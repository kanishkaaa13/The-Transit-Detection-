"""Heuristic tests for Stage 4 classification."""

import numpy as np


def test_blend_eb(depth, contratio, threshold=0.1):
    """Flag a likely blend or eclipsing binary from transit depth and contrast ratio."""
    score = depth * (1 + contratio)
    if score > threshold:
        return True, "depth*(1+contratio) exceeds threshold"
    return False, "depth*(1+contratio) below threshold"


def test_density_consistency(rho_transit, rho_catalog, tolerance=0.3):
    """Flag a density inconsistency between transit-derived and catalog densities."""
    if rho_catalog == 0:
        return False, "catalog density is zero"
    relative_diff = abs(rho_transit - rho_catalog) / abs(rho_catalog)
    if relative_diff > tolerance:
        return True, "density mismatch exceeds tolerance"
    return False, "density mismatch within tolerance"


def test_radius_eb(r_planet_rjup, threshold=2.0):
    """Flag an eclipsing binary candidate if the inferred radius is too large."""
    if r_planet_rjup > threshold:
        return True, "radius exceeds EB threshold"
    return False, "radius below EB threshold"


def test_secondary_eclipse(light_curve, period, t0):
    """Check for a secondary eclipse near phase 0.5 using simple phase folding."""
    if light_curve is None or len(light_curve) < 2:
        return False, "no secondary eclipse detected"

    if period is None or period <= 0:
        return False, "no secondary eclipse detected"

    if t0 is None:
        t0 = 0.0

    phase = ((np.arange(len(light_curve)) - t0) / period) % 1.0
    idx = int(np.argmin(np.abs(phase - 0.5)))
    if idx < len(light_curve) and light_curve[idx] < 0.95:
        return True, "secondary eclipse detected near phase 0.5"
    return False, "no secondary eclipse detected"


def test_odd_even_depth(odd_transit_depths, even_transit_depths, tolerance=0.1):
    """Flag a possible eclipsing binary if odd/even transit depths differ strongly."""
    odd_mean = float(np.mean(odd_transit_depths)) if odd_transit_depths else 0.0
    even_mean = float(np.mean(even_transit_depths)) if even_transit_depths else 0.0
    if abs(odd_mean - even_mean) > tolerance:
        return True, "odd/even depths differ significantly"
    return False, "odd/even depths similar"
