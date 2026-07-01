"""
stage4_pipeline.py
------------------
Combines stage4_heuristics.py and the trained model from stage4_train.py
into one final exoplanet candidate classification pipeline.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from stage4_heuristics import run_all_heuristics
from stage4_features import build_feature_matrix

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Core class mappings corresponding to index output of XGBClassifier
CLASS_MAPPING = {
    0: "eclipsing_binary",
    1: "noise",
    2: "planet",
    3: "planet_candidate",
}


def classify_candidate(
    row: dict,
    model: XGBClassifier,
    planet_penalty: float = 0.3,
) -> dict:
    """
    Classify a single exoplanet candidate row by combining ML model probabilities
    and deterministic vetting heuristics.
    
    Parameters
    ----------
    row : dict
        Stellar and transit parameters for the candidate.
    model : XGBClassifier
        The trained XGBoost multiclass model.
    planet_penalty : float, optional
        Penalty factor applied to 'planet' probability if any heuristics are flagged.
        Default: 0.3.
        
    Returns
    -------
    dict
        Vetting results containing: predicted_class, confidence, probabilities, and failed_heuristics.
    """
    row_copy = row.copy()

    # 1. Derive parameters for heuristics if not directly present but derivable
    if "rho_catalog" not in row_copy and "rho" in row_copy:
        row_copy["rho_catalog"] = row_copy["rho"]
        
    if "r_planet_jupiter" not in row_copy and "rad" in row_copy and "depth" in row_copy:
        rad = row_copy["rad"]
        depth = row_copy["depth"]
        # If depth is in ppm (often > 1.0), convert to fraction for calculation
        if pd.notna(depth) and depth > 1.0:
            depth_frac = depth / 1e6
        else:
            depth_frac = depth

        if pd.notna(rad) and pd.notna(depth_frac) and depth_frac >= 0:
            # R_planet = R_star * sqrt(depth) in solar units
            # Convert to Jupiter units: R_Sun / R_Jup = 1.0 / 0.10049 = 9.95
            row_copy["r_planet_jupiter"] = float(rad) * np.sqrt(float(depth_frac)) * 9.95

    # 2. Run deterministic vetting heuristics
    heuristics_results = run_all_heuristics(row_copy)
    failed_heuristics = [
        test_name for test_name, (flagged, _) in heuristics_results.items() if flagged
    ]

    # 3. Format row for the ML model (running renaming, scaling, and median imputation)
    df_row = pd.DataFrame([row_copy])
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
    df_row = df_row.rename(columns=rename_map)

    # Scale depth if in ppm
    if "depth" in df_row.columns and df_row["depth"].iloc[0] > 1.0:
        df_row["depth"] = df_row["depth"] / 1e6

    # Build feature matrix (performs imputation)
    X_features = build_feature_matrix(df_row)

    # 4. Predict probabilities using ML model
    probs_arr = model.predict_proba(X_features)[0]

    # Map model class indices to their strings
    model_probs = {CLASS_MAPPING[i]: float(probs_arr[i]) for i in range(len(probs_arr))}

    # Construct the final 5-class output dictionary (initializing false_positive to 0.0)
    probabilities = {
        "planet": model_probs.get("planet", 0.0),
        "eclipsing_binary": model_probs.get("eclipsing_binary", 0.0),
        "planet_candidate": model_probs.get("planet_candidate", 0.0),
        "false_positive": 0.0,
        "noise": model_probs.get("noise", 0.0),
    }

    # 5. Apply penalty if any heuristics failed
    if failed_heuristics:
        probabilities["planet"] *= planet_penalty
        
        # Renormalize probabilities so they sum to 1.0
        total_prob = sum(probabilities.values())
        if total_prob > 0:
            for cls in probabilities:
                probabilities[cls] /= total_prob

    # 6. Determine final class prediction and confidence
    predicted_class = max(probabilities, key=probabilities.get)
    confidence = probabilities[predicted_class]

    return {
        "predicted_class": predicted_class,
        "confidence": round(confidence, 4),
        "probabilities": {k: round(v, 4) for k, v in probabilities.items()},
        "failed_heuristics": failed_heuristics,
    }


def classify_batch(
    df: pd.DataFrame,
    model: XGBClassifier,
    planet_penalty: float = 0.3,
) -> pd.DataFrame:
    """
    Applies the combined classification pipeline to a batch of candidates.
    Preserves the original columns (including the TIC identifier).
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame of candidate targets.
    model : XGBClassifier
        The trained XGBoost model.
    planet_penalty : float, optional
        Penalty factor applied to 'planet' probability if any heuristics are flagged.
        
    Returns
    -------
    pd.DataFrame
        DataFrame with classification columns attached.
    """
    df_copy = df.copy().reset_index(drop=True)
    results = []

    for _, row in df_copy.iterrows():
        row_dict = row.to_dict()
        res = classify_candidate(row_dict, model, planet_penalty=planet_penalty)
        results.append(res)

    res_df = pd.DataFrame(results)

    # Attach summary columns
    out_df = df_copy.copy()
    out_df["predicted_class"] = res_df["predicted_class"]
    out_df["confidence"] = res_df["confidence"]
    out_df["failed_heuristics"] = res_df["failed_heuristics"].apply(lambda x: ",".join(x))

    # Attach individual class probability columns
    for cls in ["planet", "eclipsing_binary", "planet_candidate", "false_positive", "noise"]:
        out_df[f"prob_{cls}"] = res_df["probabilities"].apply(lambda p: p.get(cls, 0.0))

    return out_df


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run Combined Heuristics + ML Classification Pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--candidates",
        default="data/results/stage2_candidates.csv",
        help="Path to candidates CSV file.",
    )
    p.add_argument(
        "--model",
        default="models/stage4_classifier.json",
        help="Path to trained XGBoost classifier (JSON format).",
    )
    p.add_argument(
        "--planet-penalty",
        type=float,
        default=0.3,
        help="Penalty factor applied to 'planet' probability if any heuristics fail.",
    )
    p.add_argument(
        "--output",
        default="data/results/pipeline_classifications.csv",
        help="Path to save classified output CSV.",
    )
    return p


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()

    # 1. Load trained model
    log.info("Loading trained classifier model from: %s", args.model)
    model = XGBClassifier()
    model.load_model(args.model)

    # 2. Load candidates
    log.info("Loading candidates dataset from: %s", args.candidates)
    cand_df = pd.read_csv(args.candidates)

    # 3. Merge with prime targets to populate stellar parameters if available
    targets_path = Path("data/clean/prime_targets.csv")
    if targets_path.exists():
        log.info("Stellar targets metadata found at %s — merging with candidates", targets_path)
        targets_df = pd.read_csv(targets_path)
        
        # Auto-detect TIC column in candidates
        tic_col = None
        for col in ["tic_id", "tic", "id", "TIC_ID", "TIC", "ID"]:
            if col in cand_df.columns:
                tic_col = col
                break
        
        if tic_col:
            log.info("Aligning TICs using column '%s'", tic_col)
            cand_df["TIC"] = cand_df[tic_col].astype(str).str.replace(r"^TIC[-_]?", "", regex=True, case=False)
            cand_df["TIC"] = pd.to_numeric(cand_df["TIC"], errors="coerce").astype("Int64")
            targets_df = targets_df.rename(columns={"ID": "TIC"})
            
            # Merge
            cand_df = pd.merge(cand_df, targets_df, on="TIC", how="left")
            # Drop temporary TIC helper if TIC was not in original columns
            if "TIC" not in cand_df.columns:
                cand_df = cand_df.drop(columns=["TIC"])
        else:
            log.warning("No TIC identifier column detected in candidates — proceeding without stellar metadata")
    else:
        log.warning("Stellar targets metadata not found — proceeding without stellar metadata")

    # 4. Classify batch
    log.info("Running pipeline batch classification...")
    classified_df = classify_batch(cand_df, model, planet_penalty=args.planet_penalty)

    # 5. Save output
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    classified_df.to_csv(out_path, index=False)
    log.info("Classifications saved -> %s  (%d rows)", out_path, len(classified_df))
