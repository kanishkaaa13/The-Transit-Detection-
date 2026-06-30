"""Scikit-learn model helpers for Stage 4 classification."""

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier


CLASS_NAMES = ["planet", "EB", "blend", "noise", "false_positive"]


def _feature_matrix_from_records(records):
    """Convert a sequence of feature dictionaries into a 2D feature matrix."""
    if not records:
        return np.empty((0, 0), dtype=float)

    feature_names = sorted(records[0].keys())
    return np.array([[record.get(name, 0.0) for name in feature_names] for record in records], dtype=float)


def _coerce_feature_vector(features, feature_names=None):
    """Coerce a feature mapping into a 2D array using the expected feature order."""
    if isinstance(features, dict):
        if feature_names is None:
            feature_names = sorted(features.keys())
        return np.array([[features.get(name, 0.0) for name in feature_names]], dtype=float)
    return np.asarray(features, dtype=float).reshape(1, -1)


def train_classifier(X, y, model_type="random_forest"):
    """Train a scikit-learn classifier on a feature matrix and label vector."""
    if model_type != "random_forest":
        raise ValueError("Only random_forest is supported")

    X_matrix = _feature_matrix_from_records(X) if isinstance(X, (list, tuple)) else np.asarray(X, dtype=float)
    y_array = np.asarray(y)

    if X_matrix.ndim != 2:
        raise ValueError("X must be a 2D feature matrix or a list of feature dictionaries")
    if len(X_matrix) != len(y_array):
        raise ValueError("X and y must contain the same number of samples")

    model = RandomForestClassifier(random_state=42, n_estimators=100)
    model.fit(X_matrix, y_array)
    model.feature_names_ = sorted(X[0].keys()) if isinstance(X, (list, tuple)) and X and isinstance(X[0], dict) else None
    return model


def save_model(model, path):
    """Persist a trained model to disk with joblib."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    return path


def load_model(path):
    """Load a trained model from disk with joblib."""
    return joblib.load(path)


def predict_proba(model, features: dict) -> dict:
    """Return per-class probabilities for a single feature dictionary."""
    if isinstance(features, dict):
        feature_names = getattr(model, "feature_names_", None)
        if feature_names is None:
            feature_names = sorted(features.keys())
        sample = _coerce_feature_vector(features, feature_names=feature_names)
    else:
        sample = np.asarray(features, dtype=float).reshape(1, -1)

    probabilities = model.predict_proba(sample)[0]
    return dict(zip(CLASS_NAMES, probabilities))


def classify_candidate(features=None):
    """Classify a candidate into one of the Stage 4 output classes.

    Inputs:
        features: Feature dictionary produced by the feature extraction step.

    Outputs:
        str: One of the supported classes: planet, EB, blend, noise, or false_positive.
    """
    raise NotImplementedError


if __name__ == "__main__":
    synthetic_X = [
        {"depth": 0.01, "duration": 0.2, "period": 3.0, "SNR": 20.0, "rho": 1.4},
        {"depth": 0.2, "duration": 0.3, "period": 2.0, "SNR": 8.0, "rho": 0.8},
        {"depth": 0.05, "duration": 0.1, "period": 1.5, "SNR": 10.0, "rho": 1.2},
        {"depth": 0.01, "duration": 0.2, "period": 5.0, "SNR": 4.0, "rho": 1.0},
    ]
    synthetic_y = ["planet", "EB", "blend", "noise"]

    model = train_classifier(synthetic_X, synthetic_y)
    probs = predict_proba(model, synthetic_X[0])
    save_model(model, "model_demo.joblib")
    loaded_model = load_model("model_demo.joblib")
    loaded_probs = predict_proba(loaded_model, synthetic_X[0])

    print({"trained": True, "probs": probs, "loaded_probs": loaded_probs})
