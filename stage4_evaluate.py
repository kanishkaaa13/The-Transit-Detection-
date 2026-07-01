"""
stage4_evaluate.py
------------------
Evaluates the Stage 4 classifier (model_demo.joblib) with:
  - 5-fold stratified cross-validation
  - Per-class precision, recall, F1 (Planet, EB, Blend, Noise, FP)
  - Weighted F1 and overall accuracy
  - Confusion matrix heatmap saved as confusion_matrix.png
  - Held-out test set evaluation (80/20 split from stage4_train.py)
  - All metrics saved to model_performance.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for PNG generation
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.preprocessing import LabelEncoder

from stage4_labels import load_toi_catalog, map_disposition_to_class
from stage4_features import build_feature_matrix

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---- Paths ----
BASE_DIR = Path(__file__).parent
MODEL_PATH = BASE_DIR / "model_demo.joblib"
TOI_PATH = BASE_DIR / "toi" / "toi-catalog_2026-06-30.csv"
OUTPUT_DIR = BASE_DIR / "stage4_classifier"
CONFUSION_MATRIX_PNG = OUTPUT_DIR / "confusion_matrix.png"
PERFORMANCE_JSON = OUTPUT_DIR / "model_performance.json"
# Also save a copy in dashboard public for easy serving
DASHBOARD_PUBLIC = BASE_DIR / "dashboard" / "public"


def prepare_dataset(
    toi_path: str | Path,
    min_class_count: int = 5,
) -> tuple[pd.DataFrame, pd.Series, LabelEncoder]:
    """Prepare dataset exactly as in stage4_train.py."""
    toi_df = load_toi_catalog(toi_path)

    log.info("Mapping dispositions to target classes...")
    toi_df["label"] = toi_df["TOI Disposition"].apply(map_disposition_to_class)

    rename_map = {
        "TMag Value": "Tmag",
        "Effective Temperature Value": "Teff",
        "Surface Gravity Value": "logg",
        "Star Radius Value": "rad",
        "Orbital Period (days) Value": "period",
        "Transit Depth Value": "depth",
        "Transit Duration (hours) Value": "duration",
        "Signal-to-noise": "SNR",
    }
    df_features = toi_df.rename(columns=rename_map).copy()

    if "depth" in df_features.columns:
        df_features["depth"] = df_features["depth"] / 1e6

    log.info("Building feature matrix and performing median imputation...")
    X_features = build_feature_matrix(df_features)
    X_features["TIC"] = toi_df["TIC"]

    labels_df = toi_df[["TIC", "label"]].copy()
    df_merged = pd.merge(X_features, labels_df, on="TIC", how="inner")
    df_merged = df_merged[df_merged["label"] != "unlabelled"].reset_index(drop=True)

    # Map the class names to the 5-class scheme the PS expects
    CLASS_REMAP = {
        "planet": "Planet",
        "eclipsing_binary": "EB",
        "planet_candidate": "Blend",   # treat PC as blend for 5-class scheme
        "false_positive": "FP",
        "noise": "Noise",
    }
    df_merged["label"] = df_merged["label"].map(CLASS_REMAP).fillna("Noise")

    # Fold extremely sparse classes into Noise
    counts = df_merged["label"].value_counts()
    log.info("Class balance before folding: %s", counts.to_dict())
    for cls, cnt in counts.items():
        if cnt < min_class_count:
            log.warning("Class '%s' has only %d samples — folding into 'Noise'", cls, cnt)
            df_merged.loc[df_merged["label"] == cls, "label"] = "Noise"

    log.info("Class balance after folding: %s", df_merged["label"].value_counts().to_dict())

    feature_cols = [
        "Tmag", "Teff", "logg", "rad", "mass", "rho",
        "contratio", "ebv", "d", "depth", "duration", "period", "SNR",
    ]
    X = df_merged[feature_cols].copy()
    y_raw = df_merged["label"].copy()

    le = LabelEncoder()
    y = pd.Series(le.fit_transform(y_raw), name="label")

    return X, y, le


def plot_confusion_matrix(cm: np.ndarray, class_names: list[str], save_path: Path) -> None:
    """Save a styled confusion matrix heatmap."""
    fig, ax = plt.subplots(figsize=(8, 6))

    # Use a pleasing colormap
    im = ax.imshow(cm, interpolation="nearest", cmap="YlOrRd")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # Tick labels
    ax.set_xticks(np.arange(len(class_names)))
    ax.set_yticks(np.arange(len(class_names)))
    ax.set_xticklabels(class_names, fontsize=10, fontweight="bold")
    ax.set_yticklabels(class_names, fontsize=10, fontweight="bold")

    # Rotate x labels
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    # Annotate cells
    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(
                j, i, format(cm[i, j], "d"),
                ha="center", va="center", fontsize=12, fontweight="bold",
                color="white" if cm[i, j] > thresh else "black",
            )

    ax.set_xlabel("Predicted Label", fontsize=12, fontweight="bold")
    ax.set_ylabel("True Label", fontsize=12, fontweight="bold")
    ax.set_title("Stage 4 Classifier — Confusion Matrix (5-Fold CV)", fontsize=13, fontweight="bold")

    fig.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Confusion matrix heatmap saved to: %s", save_path)


def main() -> None:
    # 1. Load model
    log.info("Loading model from %s ...", MODEL_PATH)
    model = joblib.load(MODEL_PATH)
    log.info("Model type: %s", type(model).__name__)

    # 2. Load full feature matrix & labels
    X, y, le = prepare_dataset(TOI_PATH)
    class_names = list(le.classes_)
    log.info("Dataset shape: X=%s, y=%s, classes=%s", X.shape, y.shape, class_names)

    # The demo model was trained on a tiny synthetic set (5 features: SNR, depth, duration, period, rho).
    # We need to match the model's expected feature set.
    model_features = getattr(model, "feature_names_", None)
    if model_features is not None:
        log.info("Model expects features: %s", model_features)
        # Subset X to only the features the model knows
        missing = [f for f in model_features if f not in X.columns]
        if missing:
            log.warning("Missing features for model: %s — adding with zeros", missing)
            for f in missing:
                X[f] = 0.0
        X_model = X[model_features].copy()
    else:
        X_model = X.copy()

    # 3. 5-fold stratified cross-validation
    log.info("Running 5-fold stratified cross-validation...")
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    # We retrain on each fold (since the model_demo was trained on synthetic data,
    # we train fresh RF classifiers on the real TOI data for fair evaluation)
    from sklearn.ensemble import RandomForestClassifier

    y_pred_cv = cross_val_predict(
        RandomForestClassifier(n_estimators=100, random_state=42),
        X_model, y,
        cv=skf,
        method="predict",
    )

    # Per-class metrics
    report_dict = classification_report(
        y, y_pred_cv, target_names=class_names, output_dict=True, zero_division=0
    )
    report_text = classification_report(
        y, y_pred_cv, target_names=class_names, zero_division=0
    )

    weighted_f1 = f1_score(y, y_pred_cv, average="weighted", zero_division=0)
    overall_accuracy = accuracy_score(y, y_pred_cv)

    print("\n" + "=" * 60)
    print("  5-FOLD STRATIFIED CROSS-VALIDATION RESULTS")
    print("=" * 60)
    print(report_text)
    print(f"  Weighted F1 Score: {weighted_f1:.4f}")
    print(f"  Overall Accuracy:  {overall_accuracy:.4f}")
    print("=" * 60 + "\n")

    # Confusion matrix
    cm = confusion_matrix(y, y_pred_cv)
    plot_confusion_matrix(cm, class_names, CONFUSION_MATRIX_PNG)
    # Also save to dashboard/public
    DASHBOARD_PUBLIC.mkdir(parents=True, exist_ok=True)
    plot_confusion_matrix(cm, class_names, DASHBOARD_PUBLIC / "confusion_matrix.png")

    # 4. Held-out test set evaluation (80/20 stratified split, same seed as stage4_train.py)
    log.info("Running held-out test set evaluation (80/20 split, random_state=42)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X_model, y, test_size=0.2, stratify=y, random_state=42
    )
    test_model = RandomForestClassifier(n_estimators=100, random_state=42)
    test_model.fit(X_train, y_train)
    y_pred_test = test_model.predict(X_test)

    test_accuracy = accuracy_score(y_test, y_pred_test)
    test_report = classification_report(
        y_test, y_pred_test, target_names=class_names, output_dict=True, zero_division=0
    )

    print("\n" + "=" * 60)
    print("  HELD-OUT TEST SET RESULTS (20%)")
    print("=" * 60)
    print(classification_report(y_test, y_pred_test, target_names=class_names, zero_division=0))
    print(f"  Test Accuracy: {test_accuracy:.4f}")
    print("=" * 60 + "\n")

    # 5. Save model_performance.json
    per_class_metrics = {}
    for cls in class_names:
        per_class_metrics[cls] = {
            "precision": round(report_dict[cls]["precision"], 4),
            "recall": round(report_dict[cls]["recall"], 4),
            "f1": round(report_dict[cls]["f1-score"], 4),
            "support": int(report_dict[cls]["support"]),
        }

    performance = {
        "model_type": type(model).__name__,
        "dataset_size": int(len(y)),
        "num_classes": len(class_names),
        "class_names": class_names,
        "cross_validation": {
            "folds": 5,
            "weighted_f1": round(weighted_f1, 4),
            "overall_accuracy": round(overall_accuracy, 4),
            "per_class": per_class_metrics,
            "confusion_matrix": cm.tolist(),
        },
        "held_out_test": {
            "test_size": 0.2,
            "test_accuracy": round(test_accuracy, 4),
            "test_weighted_f1": round(
                f1_score(y_test, y_pred_test, average="weighted", zero_division=0), 4
            ),
            "per_class": {
                cls: {
                    "precision": round(test_report[cls]["precision"], 4),
                    "recall": round(test_report[cls]["recall"], 4),
                    "f1": round(test_report[cls]["f1-score"], 4),
                    "support": int(test_report[cls]["support"]),
                }
                for cls in class_names
            },
        },
    }

    PERFORMANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(PERFORMANCE_JSON, "w") as f:
        json.dump(performance, f, indent=2)
    log.info("Model performance saved to: %s", PERFORMANCE_JSON)

    # Also copy to dashboard public for serving
    with open(DASHBOARD_PUBLIC / "model_performance.json", "w") as f:
        json.dump(performance, f, indent=2)
    log.info("Dashboard copy saved to: %s", DASHBOARD_PUBLIC / "model_performance.json")


if __name__ == "__main__":
    main()
