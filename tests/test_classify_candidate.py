import numpy as np

from stage4_classifier.features import build_feature_vector
from stage4_classifier.model import train_classifier
from stage4_classifier.pipeline import classify_candidate


def test_classify_candidate_end_to_end():
    star_data = {
        "Tmag": 10.5,
        "Teff": 5800,
        "logg": 4.44,
        "rad": 1.0,
        "mass": 1.0,
        "rho": 1.4,
        "contratio": 0.01,
        "ebv": 0.02,
        "d": 100.0,
    }
    transit_data = {
        "depth": 0.01,
        "duration": 0.2,
        "period": 3.0,
        "SNR": 20.0,
    }
    light_curve = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 0.98, 1.0, 1.0, 1.0, 1.0])

    model = train_classifier(
        [
            {"depth": 0.01, "duration": 0.2, "period": 3.0, "SNR": 20.0, "rho": 1.4},
            {"depth": 0.2, "duration": 0.3, "period": 2.0, "SNR": 8.0, "rho": 0.8},
            {"depth": 0.05, "duration": 0.1, "period": 1.5, "SNR": 10.0, "rho": 1.2},
            {"depth": 0.01, "duration": 0.2, "period": 5.0, "SNR": 4.0, "rho": 1.0},
        ],
        ["planet", "EB", "blend", "noise"],
    )

    result = classify_candidate(star_data, transit_data, light_curve, t0=0.0, model=model)

    assert "event" in result
    assert "confidence" in result
    assert result["period"] == 3.0
    assert result["depth"] == 0.01
    assert result["snr"] == 20.0
    assert result["heuristic_flags"]["blend_eb"] is False
