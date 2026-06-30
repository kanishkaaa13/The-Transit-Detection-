"""Rule-based pipeline helpers for Stage 4 classification."""

from stage4_classifier.features import build_feature_vector
from stage4_classifier.heuristic_tests import (
    test_blend_eb,
    test_density_consistency,
    test_odd_even_depth,
    test_radius_eb,
    test_secondary_eclipse,
)
from stage4_classifier.model import predict_proba


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


def classify_candidate(star_data, transit_data, light_curve, t0, model) -> dict:
    """Run the full Stage 4 classification flow for a single star candidate.

    Inputs:
        star_data: Dictionary containing stellar properties used by build_feature_vector.
        transit_data: Dictionary containing transit properties used by build_feature_vector.
        light_curve: Array-like light-curve flux values used for heuristic screening.
        t0: Reference time used for phase folding.
        model: Trained scikit-learn classifier used for probability scoring.

    Outputs:
        dict: A final classification payload with the selected event label,
            confidence, key transit parameters, and heuristic flags.
    """
    features = build_feature_vector(star_data, transit_data)
    heuristic_result = run_heuristic_screen(features, light_curve=light_curve, t0=t0)
    probabilities = predict_proba(model, features)

    ml_label = max(probabilities, key=probabilities.get)
    ml_confidence = max(probabilities.values())

    confidence = float(ml_confidence)
    if heuristic_result["any_flag_triggered"]:
        confidence *= 0.8

    if heuristic_result["flags"]["blend_eb"]:
        confidence *= 0.9
    if heuristic_result["flags"]["density"]:
        confidence *= 0.9
    if heuristic_result["flags"]["radius_eb"]:
        confidence *= 0.9
    if heuristic_result["flags"]["secondary_eclipse"]:
        confidence *= 0.9
    if heuristic_result["flags"]["odd_even_depth"]:
        confidence *= 0.9

    if heuristic_result["flags"]["blend_eb"] and ml_label == "planet":
        event_label = "blend"
    elif heuristic_result["flags"]["radius_eb"] or heuristic_result["flags"]["secondary_eclipse"] or heuristic_result["flags"]["odd_even_depth"]:
        event_label = "EB"
    elif heuristic_result["flags"]["density"] and ml_label == "planet":
        event_label = "false_positive"
    else:
        event_label = ml_label

    return {
        "tic_id": star_data.get("tic_id"),
        "event": "Exoplanet Transit" if event_label == "planet" else event_label,
        "confidence": max(0.0, min(1.0, confidence)),
        "period": transit_data.get("period"),
        "depth": transit_data.get("depth"),
        "r_planet": features.get("rad"),
        "a": features.get("d"),
        "in_hz": transit_data.get("period"),
        "snr": transit_data.get("SNR"),
        "heuristic_flags": heuristic_result["flags"],
        "ml_probabilities": probabilities,
    }


def run_pipeline(candidate=None):
    """Run the Stage 4 classification pipeline for a candidate.

    Inputs:
        candidate: Candidate object or dictionary containing the necessary transit metadata.

    Outputs:
        dict: A classification result containing the selected label and supporting metadata.
    """
    raise NotImplementedError
