# TESS Exoplanet Transit Detection Pipeline

This repository contains an end-to-end astronomical pipeline designed to query, clean, process, search, and classify exoplanet transit signals in photometric data from NASA's Transiting Exoplanet Survey Satellite (TESS).

The pipeline is split into two primary phases:
1. **Catalog Phase**: Prepares candidate stars from the TESS Input Catalog (TIC), imputing missing data and filtering down to prime target dwarf stars.
2. **Signal Detection & ML Phase**: Retrieves 2-minute cadence light curves, filters and detrends stellar variability, runs a Box Least Squares (BLS) search, uses a custom 1D Convolutional Neural Network (CNN) to calculate transit probabilities, and scores candidate systems.

---

## 📂 Project Structure

The project has been restructured to live directly at the root of the repository as follows:

```
├── data/
│   ├── raw/
│   │   ├── .gitkeep
│   │   └── tic_southern_polar.csv          # Raw TIC query result
│   ├── clean/
│   │   ├── .gitkeep
│   │   ├── null_report.csv                 # Column completeness report
│   │   ├── tic_clean.parquet               # Cleaned/imputed TIC catalog (Parquet)
│   │   └── prime_targets.csv               # Bright dwarf target star hand-off
│   └── models/
│       ├── transit_cnn_config.json         # CNN model hyperparameters
│       └── transit_cnn_weights.pt          # Trained CNN state dict (CPU-safe)
├── plots/
│   ├── .gitkeep
│   ├── cnn_example_inputs.png              # Sample inputs shown to CNN
│   ├── cnn_roc_curve.png                   # CNN validation ROC curve
│   ├── cnn_training_curves.png             # CNN loss, accuracy, and F1 logs
│   ├── fig_01_null_rates.png               # Column completeness audit
│   ├── fig_02_classification.png           # Stellar classifications count
│   ├── fig_03_tmag.png                     # TESS magnitude distributions
│   ├── fig_04_teff.png                     # Effective temperature & Spectral types
│   ├── fig_05_logg.png                     # Surface gravity (dwarf vs. giant)
│   ├── fig_06_hr_proxy.png                 # HR diagram (Kiel proxy)
│   ├── fig_07_cmd.png                      # Gaia color-magnitude diagram (CMD)
│   ├── fig_08_distance.png                 # Target distance distribution
│   ├── fig_09_sky.png                      # Spatial footprint (RA/Dec)
│   ├── fig_10_funnel.png                   # Selection funnel plot
│   └── phase_folds/
│       └── TIC_DEMO_star.png               # Example phase fold visual plot
├── src/
│   ├── __init__.py
│   ├── config.py                           # Configuration and threshold definitions
│   ├── utils.py                            # Logging and workspace utility tools
│   ├── download.py                         # TIC catalog downloader (MAST API)
│   ├── clean.py                            # Column cleaning & Ridge Teff calibration
│   ├── eda_catalog.py                      # Exploratory Data Analysis & Plots
│   ├── export_targets.py                   # Outputs prime target catalog
│   ├── fetch_lightcurves.py                # Downloads TESS 2-min cadence light curves
│   ├── clean_lightcurves.py                # Sigma-clipping & Savitzky-Golay detrending
│   ├── run_bls.py                          # Box Least Squares periodogram search
│   ├── plot_phase_folds.py                 # Generates phase-folded light curve plots
│   ├── transit_cnn.py                      # 1D CNN architecture, training & dataset
│   ├── score_candidates.py                 # Scoring pipeline (Empirical SNR + CNN)
│   ├── _test_clean_lc.py                   # Smoke test for light curve cleaning
│   ├── _test_run_bls.py                    # Smoke test for BLS search
│   └── _test_score_candidates.py           # Smoke test for candidate scoring
├── logs/                                   # Workspace runtime execution logs
├── requirements.txt                        # Python dependencies
└── README.md                               # Project documentation (this file)
```

---

## 🛠️ Pipeline Stages & Workflow

### Phase 1: Target Catalog Preparation
1. **Config & Utils (`src/config.py`, `src/utils.py`)**: Centralizes parameters such as search coordinates, MAST URL, dwarf star parameters ($T_{mag} < 13.0$, $\log g \ge 4.0$), and folder directory mappings.
2. **Download Catalog (`src/download.py`)**: Fetches TIC entries in a cone search around the southern polar cap using `astroquery` (primary) or direct paginated REST API strips (fallback). Caches raw data in `data/raw/tic_southern_polar.csv`.
3. **Data Cleaning & Imputation (`src/clean.py`)**: Drops highly incomplete columns, fits a polynomial Ridge regression model to calibrate $T_{eff}$ from Gaia $BP-RP$ colors, imputes missing $T_{eff}$ parameters, adds derived features (spectral class `SpType_est`, proper motion), and flags high-priority targets (`prime_target`).
4. **Target Export (`src/export_targets.py`)**: Filters the clean TIC catalog for `prime_target == True` and exports the bright target stars to `data/clean/prime_targets.csv`.
5. **Plotting Suite (`src/eda_catalog.py`)**: Generates 10 diagnostic figures (saved in `plots/`) validating catalog quality, HR-diagram positions, distance, spatial coordinates, and the filtering funnel.

### Phase 2: Light Curve Processing & Transit Search
1. **Fetch Light Curves (`src/fetch_lightcurves.py`)**: Iterates through `prime_targets.csv` and queries MAST for 2-minute SPOC cadence data. It automatically stitches multi-sector observations and writes them to `data/raw/lightcurves/TIC_<id>.csv`.
2. **Stellar Detrending (`src/clean_lightcurves.py`)**: Applies iterative $\sigma$-clipping outlier removal, median-normalizes the flux, and executes a Savitzky-Golay high-pass filter (window length $\approx 3$ days) to subtract long-term stellar activity/rotation. Saves to `data/clean/lightcurves/TIC_<id>.csv`.
3. **Box Least Squares Search (`src/run_bls.py`)**: Uses the `astropy.timeseries.BoxLeastSquares` algorithm on detrended light curves to search a frequency grid for periodic box-like transits. Identifies best-fit period $P$, epoch $t_0$, depth $\delta$, and duration $T$. Outputs to `data/results/bls_results.csv`.
4. **Phase-Fold Plots (`src/plot_phase_folds.py`)**: Generates 2-panel inspection plots showing the full time-series and phase-folded light curves overlaid with the BLS box model.

### Phase 3: CNN Classification & Candidate Scoring
1. **1D Convolutional Neural Network (`src/transit_cnn.py`)**: 
   * Self-contained deep learning model trained on synthetic transit data generated on-the-fly via a parameterised trapezoid-transit injector.
   * Model architecture contains three 1D convolutional layers, batch normalization, GELU activations, global average pooling, and a fully connected classification head.
   * Training generates weights saved to `data/models/transit_cnn_weights.pt`.
2. **Candidate Scoring (`src/score_candidates.py`)**:
   * Folds each star's light curve on the BLS period and resamples it to a uniform 201-point phase grid.
   * Passes the folded light curve to the trained CNN to compute a transit probability score $P_{\text{transit}} \in [0, 1]$.
   * Computes the empirical transit signal-to-noise ratio ($SNR = \frac{\delta}{\sigma_{NMAD}} \times \sqrt{N_{\text{in-transit}}}$).
   * Identifies candidate planets based on threshold filters (typically $P_{\text{transit}} > 0.70$ and $SNR > 7.0$). Logs findings in `data/results/stage2_candidates.csv`.

---

## 📈 Summary of Changes Done Till Now

The repository has been updated with the following developments:
1. **Target Catalog Pipeline (Phase 1)**: Integrated raw MAST downloader, cleaning pipelines, Ridge-regression-based temperature imputation, target selection, and an exploratory charting suite.
2. **Nesting Directory Restructure**: Flattened the repository structure by moving all directories out of the nested `tess_pipeline` directory to the repository root to optimize script execution and imports.
3. **Stitching & Detrending (Phase 2)**: Added modules to stitch TESS sectors and detrend long-term rotational or instrumental signals using Savitzky-Golay filter.
4. **BLS Transit Search (Phase 3)**: Implemented Box Least Squares periodogram pipeline to locate transit parameters (period, depth, duration, epoch).
5. **1D CNN Classifier (Phase 4)**: Developed a 1D Convolutional Neural Network with synthetic trapezoid injectors to evaluate transit curves, producing model configs, training curves, ROC plots, and binary weights.
6. **Unified Scoring Pipeline (Phase 5)**: Constructed the candidate evaluator which computes empirical SNRs and combines them with CNN probability rankings to output candidates.
7. **Pipeline Verification**: Added automated smoke tests (`src/_test_*.py`) to ensure robustness of light curve detrending, BLS search, and CNN scoring modules.

---

## 🚀 How to Run

### Setup:
Install all required python packages:
```bash
pip install -r requirements.txt
```

### Run Tests:
To verify the pipelines are running correctly, run the automated smoke tests:
```bash
python src/_test_clean_lc.py
python src/_test_run_bls.py
python src/_test_score_candidates.py
```

### Execute the Pipeline:
1. **Download Target Catalog**:
   ```bash
   python -c "from src.config import CFG; from src.download import download_tic_catalog; download_tic_catalog(CFG)"
   ```
2. **Clean & Impute Catalog**:
   ```bash
   python -m src.clean
   ```
3. **Generate Catalog EDA Plots**:
   ```bash
   python -m src.eda_catalog
   ```
4. **Export Target Candidates List**:
   ```bash
   python -m src.export_targets
   ```
5. **Download Cadence Light Curves**:
   ```bash
   python -m src.fetch_lightcurves --n 20
   ```
6. **Detrend Light Curves**:
   ```bash
   python -m src.clean_lightcurves
   ```
7. **Perform BLS Transit Search**:
   ```bash
   python -m src.run_bls
   ```
8. **Plot Phase Folds**:
   ```bash
   python -m src.plot_phase_folds
   ```
9. **Train Transit CNN**:
   ```bash
   python -m src.transit_cnn --epochs 30
   ```
10. **Classify and Score Candidates**:
    ```bash
    python -m src.score_candidates
    ```
