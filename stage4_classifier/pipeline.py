"""Rule-based pipeline helpers for Stage 4 classification."""

from stage4_classifier.heuristic_tests import (
    test_blend_eb,
    test_density_consistency,
    test_odd_even_depth,
    test_radius_eb,
    test_secondary_eclipse,
)


def run_heuristic_screen(features: dict, light_curve, t0) -> dict:
    """Run the rule-based heuristic layer for a candidate.

    Inputs:
        features: Dictionary containing the heuristic inputs such as depth,
            contratio, rho, rho_transit, r_planet_rjup, odd_transit_depths,
            and even_transit_depths.
        light_curve: Array-like light-curve flux values used for secondary-eclipse screening.
        t0: Reference time used for phase folding.

    Outputs:
        dict: A dictionary with the per-flag results, whether any flag fired,
            and a list of likely classes based on which rules triggered.
    """
    flags = {}

    blend_eb_flag, _ = test_blend_eb(
        features.get("depth"),
        features.get("contratio"),
    )
    flags["blend_eb"] = blend_eb_flag

    density_flag, _ = test_density_consistency(
        features.get("rho_transit", features.get("rho")),
        features.get("rho"),
    )
    flags["density"] = density_flag

    radius_eb_flag, _ = test_radius_eb(features.get("r_planet_rjup"))
    flags["radius_eb"] = radius_eb_flag

    secondary_flag, _ = test_secondary_eclipse(light_curve, period=1.0, t0=t0)
    flags["secondary_eclipse"] = secondary_flag

    odd_even_flag, _ = test_odd_even_depth(
        features.get("odd_transit_depths", []),
        features.get("even_transit_depths", []),
    )
    flags["odd_even_depth"] = odd_even_flag

    any_flag_triggered = any(flags.values())

    likely_classes = []
    if flags["blend_eb"]:
        likely_classes.append("blend")
    if flags["density"] or flags["radius_eb"] or flags["secondary_eclipse"] or flags["odd_even_depth"]:
        likely_classes.append("EB")

    return {
        "flags": flags,
        "any_flag_triggered": any_flag_triggered,
        "likely_classes": likely_classes,
    }


def run_pipeline(candidate=None):
    """Run the Stage 4 classification pipeline for a candidate.

    Inputs:
        candidate: Candidate object or dictionary containing the necessary transit metadata.

    Outputs:
        dict: A classification result containing the selected label and supporting metadata.
    """
    raise NotImplementedError
