"""
stage4_validate.py
------------------
Cross-checks the exoplanet pipeline's final classifications against the TOI catalog
ground truth to calculate accuracy metrics, draw a confusion matrix, and report the
confirmed planet agreement rate.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from stage4_labels import load_toi_catalog, map_disposition_to_class

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def validate_classifications(
    pipeline_output_path: str | Path,
    toi_path: str | Path,
    output_plot_path: str | Path,
) -> None:
    """
    Load pipeline output and ground truth TOI catalog, join on TIC,
    and compute evaluation metrics.
    """
    pipeline_output_path = Path(pipeline_output_path)
    toi_path = Path(toi_path)
    output_plot_path = Path(output_plot_path)

    # 1. Load pipeline output
    if not pipeline_output_path.exists():
        raise FileNotFoundError(f"Pipeline output file not found at: {pipeline_output_path}")
    log.info("Loading pipeline classifications from: %s", pipeline_output_path)
    pipe_df = pd.read_csv(pipeline_output_path)

    # Verify required columns are present
    required_pipe_cols = ["predicted_class", "confidence"]
    missing_cols = [c for c in required_pipe_cols if c not in pipe_df.columns]
    if missing_cols:
        raise KeyError(
            f"Missing required columns in pipeline output: {missing_cols}. "
            f"Found: {list(pipe_df.columns)}"
        )

    # Auto-detect TIC column in pipeline output
    tic_col = None
    for col in ["tic", "id", "tic_id", "TIC", "ID", "TIC_ID"]:
        if col in pipe_df.columns:
            tic_col = col
            break

    if tic_col is None:
        raise KeyError(
            f"Could not find a TIC/ID column in pipeline output. "
            f"Available: {list(pipe_df.columns)}"
        )

    # Clean TIC column to ensure integer matching
    pipe_df["TIC"] = pipe_df[tic_col].astype(str).str.replace(r"^TIC[-_]?", "", regex=True, case=False)
    pipe_df["TIC"] = pd.to_numeric(pipe_df["TIC"], errors="coerce").astype("Int64")
    pipe_df = pipe_df.dropna(subset=["TIC"])
    pipe_df["TIC"] = pipe_df["TIC"].astype("int64")

    # 2. Load TOI catalog
    toi_df = load_toi_catalog(toi_path)

    # Map dispositions to target classes
    toi_df["true_class"] = toi_df["TOI Disposition"].apply(map_disposition_to_class)

    # 3. Inner-join on TIC
    log.info("Joining pipeline output and TOI catalog on TIC...")
    joined_df = pd.merge(
        pipe_df[["TIC", "predicted_class", "confidence"]],
        toi_df[["TIC", "true_class", "TOI Disposition"]],
        on="TIC",
        how="inner",
    )

    log.info("Found %d overlapping candidates with TOI catalog", len(joined_df))

    if len(joined_df) == 0:
        log.warning("No overlapping candidate targets found between pipeline output and TOI catalog.")
        print("\n" + "=" * 60)
        print("  WARNING: 0 OVERLAPPING CANDIDATES FOUND")
        print("  Validation cannot proceed without shared TIC keys.")
        print("=" * 60 + "\n")
        return

    # 4. Compute overall metrics
    y_true = joined_df["true_class"]
    y_pred = joined_df["predicted_class"]

    accuracy = accuracy_score(y_true, y_pred)
    log.info("Overall Accuracy: %.2f%%", accuracy * 100.0)

    # Define standard unique labels in validation data
    classes = sorted(list(set(y_true) | set(y_pred)))

    # Classification report
    report = classification_report(
        y_true, y_pred, labels=classes, zero_division=0
    )

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=classes)
    cm_df = pd.DataFrame(
        cm,
        index=[f"True {c}" for c in classes],
        columns=[f"Pred {c}" for c in classes],
    )

    # 5. Output metrics and text confusion matrix
    print("\n" + "=" * 60)
    print("  PIPELINE EVALUATION SUMMARY VS TOI CATALOG")
    print("=" * 60)
    print(f"  Overall Accuracy: {accuracy*100.2:.2f}%")
    print("-" * 60)
    print("  CLASSIFICATION REPORT:")
    print(report)
    print("-" * 60)
    print("  CONFUSION MATRIX:")
    print(cm_df.to_string())
    print("=" * 60 + "\n")

    # 6. Save confusion matrix plot using matplotlib
    log.info("Saving confusion matrix plot to: %s", output_plot_path)
    output_plot_path.parent.mkdir(parents=True, exist_ok=True)
    
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    ax.figure.colorbar(im, ax=ax)

    ax.set(
        xticks=np.arange(cm.shape[1]),
        yticks=np.arange(cm.shape[0]),
        xticklabels=classes,
        yticklabels=classes,
        title="Confusion Matrix (TOI Vetting Validation)",
        ylabel="True Ground-Truth Class",
        xlabel="Predicted Pipeline Class",
    )

    # Rotate tick labels
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    # Annotate counts inside matrix cells
    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(
                j,
                i,
                format(cm[i, j], "d"),
                ha="center",
                va="center",
                color="white" if cm[i, j] > thresh else "black",
            )
            
    fig.tight_layout()
    plt.savefig(output_plot_path, dpi=150)
    plt.close()

    # 7. Compute high-confidence planet agreement rate
    # predicted class = planet, confidence > 0.8
    high_conf_planets = joined_df[
        (joined_df["predicted_class"] == "planet") & (joined_df["confidence"] > 0.8)
    ]
    n_high_conf = len(high_conf_planets)

    if n_high_conf > 0:
        confirmed_mask = high_conf_planets["TOI Disposition"].isin(["CP", "KP"])
        n_confirmed = confirmed_mask.sum()
        agreement_rate = (n_confirmed / n_high_conf) * 100.0
    else:
        agreement_rate = 0.0
        n_confirmed = 0

    print("=" * 60)
    print("  HIGH-CONFIDENCE PLANET AGREEMENT SUMMARY")
    print("=" * 60)
    print(f"  High-confidence (>0.80) predicted planets: {n_high_conf}")
    print(f"  Vetted in TOI as Confirmed/Known (CP/KP)  : {n_confirmed}")
    print(f"  Confirmed Planet Agreement Rate          : {agreement_rate:.1f}%")
    print("-" * 60)
    print(f"  Pitch Quote:")
    print(f"  \"Of {n_high_conf} high-confidence planet predictions, "
          f"{agreement_rate:.1f}% match TOI-confirmed planets.\"")
    print("=" * 60 + "\n")


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Cross-check exoplanet pipeline classifications against the TOI catalog.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--pipeline-output",
        default="data/results/pipeline_classifications.csv",
        help="Path to pipeline classifications CSV.",
    )
    p.add_argument(
        "--toi",
        default="toi/toi-catalog_2026-06-30.csv",
        help="Path to the TOI catalog CSV file.",
    )
    p.add_argument(
        "--output-plot",
        default="plots/confusion_matrix.png",
        help="Where to save the confusion matrix plot (PNG).",
    )
    return p


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    try:
        validate_classifications(
            args.pipeline_output,
            args.toi,
            args.output_plot,
        )
    except Exception as exc:
        log.exception("Validation failed: %s", exc)
        sys.exit(1)
    sys.exit(0)
