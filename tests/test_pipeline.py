import pytest
import pandas as pd
import numpy as np
from stage4_pipeline import classify_candidate, classify_batch


class MockXGBClassifier:
    """Mock XGBoost classifier that returns fixed probabilities."""
    def predict_proba(self, X):
        # Returns probabilities corresponding to:
        # [eclipsing_binary, noise, planet, planet_candidate]
        # index 0: eclipsing_binary = 0.1
        # index 1: noise = 0.1
        # index 2: planet = 0.5
        # index 3: planet_candidate = 0.3
        return np.array([[0.1, 0.1, 0.5, 0.3]])


def test_classify_candidate_no_penalty():
    model = MockXGBClassifier()
    # Row that passes all heuristics (no flags)
    row = {
        "depth": 0.001,
        "contratio": 0.0,
        "rad": 1.0,
        "period": 3.0,
        "SNR": 10.0,
        # passes radius outlier (radius ~0.3 R_jup, well under 2.0 limit)
        "r_planet_jupiter": 0.3,
        "secondary_eclipse_flag": False,
        "depth_odd": 0.001,
        "depth_even": 0.001,
    }

    result = classify_candidate(row, model, planet_penalty=0.3)

    assert result["predicted_class"] == "planet"
    # Unpenalized planet probability should be 0.5
    assert result["probabilities"]["planet"] == 0.5
    assert result["probabilities"]["planet_candidate"] == 0.3
    assert result["probabilities"]["eclipsing_binary"] == 0.1
    assert result["probabilities"]["noise"] == 0.1
    assert result["probabilities"]["false_positive"] == 0.0
    assert result["failed_heuristics"] == []


def test_classify_candidate_with_penalty():
    model = MockXGBClassifier()
    # Row that triggers radius outlier (> 2.0 limit) and secondary eclipse
    row = {
        "depth": 0.05,
        "contratio": 0.0,
        "rad": 3.0,
        "period": 3.0,
        "SNR": 10.0,
        "r_planet_jupiter": 5.0,  # flags radius outlier!
        "secondary_eclipse_flag": True,  # flags secondary eclipse!
        "depth_odd": 0.05,
        "depth_even": 0.05,
    }

    result = classify_candidate(row, model, planet_penalty=0.3)

    # Heuristics that failed
    assert "radius_outlier" in result["failed_heuristics"]
    assert "secondary_eclipse" in result["failed_heuristics"]

    # Planet probability starts at 0.5, gets multiplied by 0.3 -> 0.15
    # Original sum: 0.1 (EB) + 0.1 (noise) + 0.15 (planet) + 0.3 (candidate) = 0.65
    # Renormalized planet prob: 0.15 / 0.65 = 0.230769 -> 0.2308
    # Renormalized candidate prob: 0.3 / 0.65 = 0.4615
    assert result["probabilities"]["planet"] == pytest.approx(0.2308, abs=1e-3)
    assert result["probabilities"]["planet_candidate"] == pytest.approx(0.4615, abs=1e-3)
    # The predicted class shifts from planet (0.2308) to planet_candidate (0.4615)
    assert result["predicted_class"] == "planet_candidate"
    assert result["confidence"] == pytest.approx(0.4615, abs=1e-3)


def test_classify_batch():
    model = MockXGBClassifier()
    df_data = {
        "TIC_ID": ["TIC_101", "TIC_102"],
        "depth": [0.001, 0.05],
        "contratio": [0.0, 0.0],
        "rad": [1.0, 3.0],
        "period": [3.0, 3.0],
        "SNR": [10.0, 10.0],
        "r_planet_jupiter": [0.3, 5.0],
        "secondary_eclipse_flag": [False, True],
        "depth_odd": [0.001, 0.05],
        "depth_even": [0.001, 0.05],
    }
    df = pd.DataFrame(df_data)

    out_df = classify_batch(df, model, planet_penalty=0.3)

    assert len(out_df) == 2
    assert "TIC_ID" in out_df.columns
    assert "predicted_class" in out_df.columns
    assert "confidence" in out_df.columns
    assert "failed_heuristics" in out_df.columns
    assert "prob_planet" in out_df.columns
    assert "prob_planet_candidate" in out_df.columns
    assert "prob_eclipsing_binary" in out_df.columns
    assert "prob_noise" in out_df.columns
    assert "prob_false_positive" in out_df.columns

    # Check value mapping correctness
    assert out_df.loc[0, "predicted_class"] == "planet"
    assert out_df.loc[1, "predicted_class"] == "planet_candidate"
    assert out_df.loc[1, "failed_heuristics"] == "radius_outlier,secondary_eclipse"
