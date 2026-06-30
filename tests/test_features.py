import pytest

from stage4_classifier.features import build_feature_vector


def test_build_feature_vector_returns_expected_keys_and_values():
    star_data = {
        "Tmag": 10.5,
        "Teff": 5800,
        "logg": 4.44,
        "rad": 1.0,
        "mass": 1.0,
        "rho": 1.41,
        "contratio": 0.01,
        "ebv": 0.02,
        "d": 100.0,
    }
    transit_data = {
        "depth": 0.008,
        "duration": 0.2,
        "period": 3.5,
        "SNR": 25.0,
    }

    features = build_feature_vector(star_data, transit_data)

    assert features["Tmag"] == 10.5
    assert features["depth"] == 0.008
    assert features["period"] == 3.5
    assert features["SNR"] == 25.0
    assert set(features.keys()) == {
        "Tmag",
        "Teff",
        "logg",
        "rad",
        "mass",
        "rho",
        "contratio",
        "ebv",
        "d",
        "depth",
        "duration",
        "period",
        "SNR",
    }


def test_build_feature_vector_raises_for_missing_required_keys():
    star_data = {
        "Tmag": 10.5,
        "Teff": 5800,
        "logg": 4.44,
        "rad": 1.0,
        "mass": 1.0,
        "rho": 1.41,
        "contratio": 0.01,
        "ebv": 0.02,
    }
    transit_data = {
        "depth": 0.008,
        "duration": 0.2,
        "period": 3.5,
        "SNR": 25.0,
    }

    with pytest.raises(ValueError, match="missing required key"):
        build_feature_vector(star_data, transit_data)


def test_build_feature_vector_raises_for_invalid_values():
    star_data = {
        "Tmag": 10.5,
        "Teff": 5800,
        "logg": 4.44,
        "rad": 1.0,
        "mass": 1.0,
        "rho": 1.41,
        "contratio": 0.01,
        "ebv": 0.02,
        "d": 100.0,
    }
    transit_data = {
        "depth": 1.5,
        "duration": 0.2,
        "period": 0.0,
        "SNR": 25.0,
    }

    with pytest.raises(ValueError, match="depth"):
        build_feature_vector(star_data, transit_data)
