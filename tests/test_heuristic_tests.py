import numpy as np

from stage4_classifier.heuristic_tests import (
    test_blend_eb,
    test_density_consistency,
    test_radius_eb,
    test_secondary_eclipse,
    test_odd_even_depth,
)


def test_blend_eb_flags_and_not_flags():
    assert test_blend_eb(0.2, 0.5) == (True, "depth*(1+contratio) exceeds threshold")
    assert test_blend_eb(0.05, 0.1) == (False, "depth*(1+contratio) below threshold")


def test_density_consistency_flags_and_not_flags():
    assert test_density_consistency(1.0, 1.5) == (True, "density mismatch exceeds tolerance")
    assert test_density_consistency(1.0, 1.05) == (False, "density mismatch within tolerance")


def test_radius_eb_flags_and_not_flags():
    assert test_radius_eb(3.0) == (True, "radius exceeds EB threshold")
    assert test_radius_eb(1.5) == (False, "radius below EB threshold")


def test_secondary_eclipse_flags_and_not_flags():
    t = np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    flux = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 0.8, 1.0, 1.0, 1.0, 1.0])
    assert test_secondary_eclipse(flux, period=1.0, t0=0.0) == (
        True,
        "secondary eclipse detected near phase 0.5",
    )

    flux_no_dip = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 0.98, 1.0, 1.0, 1.0, 1.0])
    assert test_secondary_eclipse(flux_no_dip, period=1.0, t0=0.0) == (
        False,
        "no secondary eclipse detected",
    )


def test_odd_even_depth_flags_and_not_flags():
    assert test_odd_even_depth([0.01, 0.012], [0.02, 0.021], tolerance=0.1) == (
        False,
        "odd/even depths similar",
    )
    assert test_odd_even_depth([0.01, 0.012], [0.02, 0.2], tolerance=0.05) == (
        True,
        "odd/even depths differ significantly",
    )
