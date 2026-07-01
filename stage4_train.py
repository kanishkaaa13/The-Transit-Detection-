"""
stage4_train.py
----------------
Trains a multiclass false-positive classifier using XGBoost on the TOI catalog features.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.metrics import classification_report
from xgboost import XGBClassifier

from stage4_labels import load_toi_catalog, map_disposition_to_class
from stage4_features import build_feature_matrix

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def prepare_dataset(
    toi_path: str | Path,
    min_class_count: int = 5,
) -> tuple[pd.DataFrame, pd.Series, LabelEncoder]:
    """
    Loads the TOI catalog, extracts features and labels, merges them,
    imputes missing features, folds extremely sparse classes, and encodes labels.
    """
    # 1. Load TOI catalog
    toi_df = load_toi_catalog(toi_path)

    # 2. Map dispositions to target classes
    log.info("Mapping dispositions to target classes...")
    toi_df["label"] = toi_df["TOI Disposition"].apply(map_disposition_to_class)

    # 3. Rename columns for feature matrix extraction
    # build_feature_matrix expects: Tmag, Teff, logg, rad, mass, rho, contratio, ebv, d, depth, duration, period, SNR
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

    # Convert Transit Depth from ppm to fraction (0 to 1)
    if "depth" in df_features.columns:
        df_features["depth"] = df_features["depth"] / 1e6

    # 4. Extract feature matrix using stage4_features helper (which performs imputation)
    log.info("Building feature matrix and performing median imputation...")
    X_features = build_feature_matrix(df_features)
    X_features["TIC"] = toi_df["TIC"]

    # 5. Select labels and inner-join on TIC
    labels_df = toi_df[["TIC", "label"]].copy()
    
    # Perform inner join
    df_merged = pd.merge(X_features, labels_df, on="TIC", how="inner")
    
    # Filter out unlabelled rows (we only train on labeled data)
    df_merged = df_merged[df_merged["label"] != "unlabelled"].reset_index(drop=True)

    # 6. Fold extremely sparse classes into "noise"
    counts = df_merged["label"].value_counts()
    log.info("Class balance before folding: %s", counts.to_dict())

    for cls, cnt in counts.items():
        if cnt < min_class_count:
            log.warning(
                "Class '%s' has only %d samples (below threshold %d) — folding into 'noise'",
                cls, cnt, min_class_count
            )
            df_merged.loc[df_merged["label"] == cls, "label"] = "noise"

    log.info("Class balance after folding: %s", df_merged["label"].value_counts().to_dict())

    # Extract clean X and y
    feature_cols = [
        "Tmag", "Teff", "logg", "rad", "mass", "rho",
        "contratio", "ebv", "d", "depth", "duration", "period", "SNR"
    ]
    X = df_merged[feature_cols].copy()
    y_raw = df_merged["label"].copy()

    # Encode target labels
    le = LabelEncoder()
    y = pd.Series(le.fit_transform(y_raw), name="label")

    return X, y, le


def train_xgboost_classifier(
    X: pd.DataFrame,
    y: pd.Series,
    le: LabelEncoder,
    model_output_path: str | Path,
) -> None:
    """
    Splits data, computes class weights, trains XGBClassifier, saves model, and evaluates.
    """
    # 1. Stratified train/test split (80/20)
    log.info("Splitting dataset into 80/20 train/test sets...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    # 2. Compute sample weights for class balancing
    log.info("Computing sample weights for class balancing...")
    sample_weights = compute_sample_weight(class_weight="balanced", y=y_train)

    # 3. Train XGBoost Multiclass Classifier
    log.info("Training XGBClassifier multiclass model...")
    model = XGBClassifier(
        objective="multi:softprob",
        eval_metric="mlogloss",
        random_state=42,
        use_label_encoder=False,
    )
    
    model.fit(X_train, y_train, sample_weight=sample_weights)

    # 4. Save trained model
    model_output_path = Path(model_output_path)
    model_output_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(model_output_path))
    log.info("Trained model saved to: %s", model_output_path)

    # 5. Evaluate on test set
    log.info("Evaluating model on test set...")
    y_pred = model.predict(X_test)

    # Decode labels back to strings
    target_names = [str(cls) for cls in le.classes_]
    report = classification_report(
        y_test, y_pred, target_names=target_names, zero_division=0
    )

    print("\n" + "=" * 60)
    print("  STAGE 4 MODEL TEST PERFORMANCE")
    print("=" * 60)
    print(report)
    print("=" * 60 + "\n")


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Train Stage 4 XGBoost Multiclass Classifier.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--toi",
        default="toi/toi-catalog_2026-06-30.csv",
        help="Path to the TOI catalog CSV file.",
    )
    p.add_argument(
        "--min-class-count",
        type=int,
        default=5,
        help="Class count threshold below which a class is folded into 'noise'.",
    )
    p.add_argument(
        "--output",
        default="models/stage4_classifier.json",
        help="Path to save the trained XGBoost model (JSON format).",
    )
    return p


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()

    # Prepare features and labels
    X, y, le = prepare_dataset(args.toi, min_class_count=args.min_class_count)

    # Train and evaluate model
    train_xgboost_classifier(X, y, le, args.output)
