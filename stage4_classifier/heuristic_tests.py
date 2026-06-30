"""Heuristic test stubs for Stage 4 classification."""


def depth_contratio_test(depth=None, contratio=None):
    """Evaluate the blend/EB heuristic based on depth and contrast ratio.

    Inputs:
        depth: Transit depth.
        contratio: Contrast ratio.

    Outputs:
        bool: True when the heuristic flags a blend or EB candidate.
    """
    raise NotImplementedError


def density_consistency_test(rho_transit=None, rho_catalog=None):
    """Compare transit-derived density with catalog density.

    Inputs:
        rho_transit: Density inferred from the transit fit.
        rho_catalog: Density from the catalog or stellar parameters.

    Outputs:
        bool: True when the density check indicates inconsistency.
    """
    raise NotImplementedError


def radius_test(r_planet=None):
    """Evaluate whether the inferred planet radius exceeds the EB threshold.

    Inputs:
        r_planet: Inferred planet radius.

    Outputs:
        bool: True when the radius indicates an eclipsing binary.
    """
    raise NotImplementedError


def secondary_eclipse_test(has_secondary_eclipse=None):
    """Evaluate the presence of a secondary eclipse signal.

    Inputs:
        has_secondary_eclipse: Boolean flag indicating whether a secondary eclipse exists.

    Outputs:
        bool: True when a secondary eclipse suggests an eclipsing binary.
    """
    raise NotImplementedError


def odd_even_depth_test(depth_even=None, depth_odd=None):
    """Compare odd- and even-transit depths for an EB signal.

    Inputs:
        depth_even: Depth of even-numbered transits.
        depth_odd: Depth of odd-numbered transits.

    Outputs:
        bool: True when the odd/even depth difference suggests an eclipsing binary.
    """
    raise NotImplementedError
