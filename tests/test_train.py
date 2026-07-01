import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.preprocessing import LabelEncoder
from stage4_train import prepare_dataset, train_xgboost_classifier


def test_prepare_dataset(tmp_path):
    # Create a mock TOI catalog with comment lines
    catalog_content = (
        "# toi-catalog\n"
        "# Generated on 2026-06-30\n"
        "# Collection PK: 193\n"
        "pk,TIC,TOI Disposition,TMag Value,Effective Temperature Value,Surface Gravity Value,Star Radius Value,Orbital Period (days) Value,Transit Depth Value,Transit Duration (hours) Value,Signal-to-noise\n"
        "1,1234567,CP,10.0,5800.0,4.4,1.0,10.0,1000.0,2.5,25.0\n"
        "2,2345678,EB,12.0,6000.0,4.3,1.2,5.5,5000.0,4.0,15.0\n"
        # planet candidates
        "3,3456789,PC,11.5,5700.0,4.4,0.9,3.0,500.0,2.0,12.0\n"
        "4,4567890,PC,10.8,5900.0,4.5,1.1,4.5,800.0,3.0,18.0\n"
        "5,5678901,PC,11.2,5850.0,4.4,1.0,7.0,1200.0,2.8,20.0\n"
        "6,6789012,PC,12.5,5500.0,4.2,0.8,8.2,1500.0,3.5,22.0\n"
        "7,7890123,PC,10.2,6100.0,4.3,1.3,12.0,600.0,1.8,10.0\n"
        # noise classes
        "8,8901234,O,9.5,6200.0,4.1,1.5,15.0,200.0,1.2,5.0\n"
        "9,9012345,O,9.8,6300.0,4.0,1.6,20.0,300.0,1.5,6.0\n"
    )
    catalog_file = tmp_path / "mock_toi_catalog.csv"
    catalog_file.write_text(catalog_content)

    # Prepare dataset with low min_class_count to prevent folding standard categories
    X, y, le = prepare_dataset(catalog_file, min_class_count=2)

    assert len(X) == 9
    assert len(y) == 9
    assert isinstance(le, LabelEncoder)
    # Check features are present
    assert list(X.columns) == [
        "Tmag", "Teff", "logg", "rad", "mass", "rho",
        "contratio", "ebv", "d", "depth", "duration", "period", "SNR"
    ]
    # Check Tmag values match
    assert X.loc[0, "Tmag"] == 10.0
    # Imputed features should have no NaN
    assert not X.isna().any().any()


def test_train_xgboost_classifier(tmp_path):
    # Build simple synthetic dataset
    # We need enough samples to perform stratified split
    classes = ["planet", "eclipsing_binary", "planet_candidate", "noise"]
    # Repeat to ensure enough samples per class
    y_raw = classes * 10
    X_dict = {
        "Tmag": np.random.uniform(8.0, 15.0, 40),
        "Teff": np.random.uniform(4000.0, 7000.0, 40),
        "logg": np.random.uniform(3.5, 4.8, 40),
        "rad": np.random.uniform(0.5, 3.0, 40),
        "mass": np.random.uniform(0.5, 2.0, 40),
        "rho": np.random.uniform(0.1, 2.0, 40),
        "contratio": np.random.uniform(0.0, 0.1, 40),
        "ebv": np.random.uniform(0.0, 0.2, 40),
        "d": np.random.uniform(50.0, 500.0, 40),
        "depth": np.random.uniform(0.0001, 0.05, 40),
        "duration": np.random.uniform(1.0, 5.0, 40),
        "period": np.random.uniform(0.5, 30.0, 40),
        "SNR": np.random.uniform(5.0, 50.0, 40),
    }
    X = pd.DataFrame(X_dict)

    le = LabelEncoder()
    y = pd.Series(le.fit_transform(y_raw), name="label")

    model_path = tmp_path / "test_model.json"

    # Train model, should complete without error
    train_xgboost_classifier(X, y, le, model_path)

    # Check model file exists
    assert model_path.exists()
