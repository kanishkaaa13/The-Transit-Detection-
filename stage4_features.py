"""
stage4_features.py
------------------
Stage 4 feature loading and matrix preparation module for exoplanet false-positive classification.
"""

from pathlib import Path
import logging
import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_stage3_output(path: str | Path) -> pd.DataFrame:
    """
    Load the Stage 3 parameter estimation output from a CSV file.

    Parameters
    ----------
    path : str or Path
        Path to the CSV file containing target and transit features.

    Returns
    -------
    pd.DataFrame
        Loaded dataframe containing target and transit statistics.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Stage 3 output file not found at: {path}")
    logger.info(f"Loading Stage 3 output from: {path}")
    return pd.read_csv(path)


def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Select ML-relevant columns and perform median imputation on missing values.

    ML-relevant columns:
    Tmag, Teff, logg, rad, mass, rho, contratio, ebv, d, depth, duration, period, SNR

    Parameters
    ----------
    df : pd.DataFrame
        The input dataframe containing target and transit parameters.

    Returns
    -------
    pd.DataFrame
        Cleaned feature matrix containing only ML-relevant columns.
    """
    feature_cols = [
        "Tmag", "Teff", "logg", "rad", "mass", "rho", 
        "contratio", "ebv", "d", "depth", "duration", "period", "SNR"
    ]
    
    # Direct copy of the input dataframe to avoid modifying the original
    df_copy = df.copy()
    
    # Map common aliases if the requested column name is missing but an alias exists
    aliases = {
        "period": ["period_days", "Period"],
        "depth": ["Depth"],
        "duration": ["duration_hours", "Duration"],
        "SNR": ["snr", "Snr"]
    }
    
    for col in feature_cols:
        if col not in df_copy.columns:
            found = False
            if col in aliases:
                for alias in aliases[col]:
                    if alias in df_copy.columns:
                        df_copy[col] = df_copy[alias]
                        found = True
                        break
            if not found:
                df_copy[col] = np.nan

    # Subset only the requested features
    feature_df = df_copy[feature_cols].copy()

    # Handle missing values using median imputation
    for col in feature_cols:
        # Count NaNs in this column
        missing_count = feature_df[col].isna().sum()
        if missing_count > 0:
            median_val = feature_df[col].median()
            
            # Fallback if the entire column is NaN
            if pd.isna(median_val):
                default_vals = {
                    "Tmag": 10.0, "Teff": 5800.0, "logg": 4.4, "rad": 1.0, "mass": 1.0,
                    "rho": 1.4, "contratio": 0.0, "ebv": 0.0, "d": 100.0, "depth": 0.001,
                    "duration": 2.0, "period": 3.0, "SNR": 10.0
                }
                median_val = default_vals.get(col, 0.0)
                
            feature_df[col] = feature_df[col].fillna(median_val)
            logger.info(f"Imputed {missing_count} missing values in column '{col}' with median: {median_val}")

    return feature_df.astype(float)


if __name__ == "__main__":
    # Create a mock Stage 3 output file for demo / testing if real ones aren't available
    demo_path = Path("stage3_sample_demo.csv")
    
    # Try to load real data to construct a high-fidelity sample file
    pt_path = Path("data/clean/prime_targets.csv")
    cand_path = Path("data/results/stage2_candidates.csv")
    
    if pt_path.exists() and cand_path.exists():
        logger.info("Building demo dataset from real telemetry files...")
        pt_df = pd.read_csv(pt_path)
        cand_df = pd.read_csv(cand_path)
        
        # Format candidate IDs to match prime target IDs
        cand_df["ID"] = cand_df["TIC_ID"].astype(str).str.replace("TIC_", "").astype(float)
        pt_df["ID"] = pt_df["ID"].astype(float)
        
        # Merge on ID
        merged_df = pd.merge(cand_df, pt_df, on="ID", how="inner")
        
        # Add some missing values intentionally to demonstrate imputation
        if len(merged_df) > 5:
            merged_df.loc[0, "Teff"] = np.nan
            merged_df.loc[2, "rho"] = np.nan
            merged_df.loc[4, "contratio"] = np.nan
            
        merged_df.to_csv(demo_path, index=False)
    else:
        logger.info("Generating fully synthetic demo dataset...")
        synthetic_data = {
            "TIC": ["10001", "10002", "10003", "10004", "10005"],
            "period": [3.5, 12.4, 1.25, 28.4, 42.5],
            "depth": [0.0035, 0.0820, 0.0012, 0.0045, np.nan],  # NaN injected
            "duration": [2.45, 4.8, 1.8, 12.2, 3.82],
            "t0": [1628.4, 1628.3, 1629.1, 1639.5, 2043.1],
            "R_planet": [11.2, 0.0, 0.0, 0.0, 1.62],
            "orbit_a": [0.05, 0.12, 0.02, 0.18, 0.25],
            "SNR": [14.2, 92.5, 5.8, np.nan, 9.8],             # NaN injected
            "Tmag": [10.5, 12.0, 7.6, 8.6, 9.1],
            "Teff": [5800, 7400, np.nan, 8400, 6700],          # NaN injected
            "logg": [4.4, 3.7, 4.1, 4.3, 3.6],
            "rad": [1.02, 2.8, 1.3, 1.5, 2.9],
            "mass": [1.0, 1.7, 1.0, 2.1, 1.4],
            "rho": [1.4, 0.07, 0.39, 0.54, np.nan],            # NaN injected
            "contratio": [0.0, 0.01, 90.0, 0.09, 0.0],
            "ebv": [0.0, 0.03, 0.0, 0.06, 0.09],
            "d": [120.5, 840.0, 1450.0, 245.0, 45.2]
        }
        pd.DataFrame(synthetic_data).to_csv(demo_path, index=False)
        
    try:
        # Load the stage 3 output
        df = load_stage3_output(demo_path)
        
        # Build the ML feature matrix
        feature_matrix = build_feature_matrix(df)
        
        print("\n" + "=" * 60)
        print("STAGE 4 FEATURE PREPARATION RUN SUCCESSFUL")
        print("=" * 60)
        print(f"Feature Matrix Shape: {feature_matrix.shape}")
        print("\nFeature Matrix Head:")
        print(feature_matrix.head())
        print("=" * 60)
        
    finally:
        # Clean up demo file
        if demo_path.exists():
            demo_path.unlink()
            logger.info("Cleaned up demo sample file.")
