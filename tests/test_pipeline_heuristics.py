import numpy as np

from stage4_classifier.pipeline import run_heuristic_screen


def test_run_heuristic_screen_triggers_multiple_flags():
    features = {
        "depth": 0.2,
        "contratio": 0.5,
        "rho": 1.0,
        "rho_transit": 1.5,
        "r_planet_rjup": 3.0,
        "odd_transit_depths": [0.01, 0.012],
        "even_transit_depths": [0.02, 0.3],
    }
    light_curve = np.array([1.0, 1.0, 0.9, 1.0, 1.0, 0.8, 1.0, 1.0, 1.0, 1.0])

    result = run_heuristic_screen(features, light_curve=light_curve, t0=0.0)

    assert result["any_flag_triggered"] is True
    assert result["flags"]["blend_eb"] is True
    assert result["flags"]["density"] is True
    assert result["flags"]["radius_eb"] is True
    assert result["flags"]["secondary_eclipse"] is True
    assert result["flags"]["odd_even_depth"] is True
    assert set(result["likely_classes"]) >= {"EB", "blend"}


def test_run_heuristic_screen_triggers_none():
    features = {
        "depth": 0.01,
        "contratio": 0.01,
        "rho": 1.0,
        "rho_transit": 1.05,
        "r_planet_rjup": 1.5,
        "odd_transit_depths": [0.01, 0.011],
        "even_transit_depths": [0.01, 0.011],
    }
    light_curve = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 0.98, 1.0, 1.0, 1.0, 1.0])

    result = run_heuristic_screen(features, light_curve=light_curve, t0=0.0)

    assert result["any_flag_triggered"] is False
    assert all(value is False for value in result["flags"].values())
    assert result["likely_classes"] == []
