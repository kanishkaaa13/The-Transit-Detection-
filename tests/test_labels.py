import pytest
import pandas as pd
from pathlib import Path
from stage4_labels import (
    load_toi_catalog,
    map_disposition_to_class,
    join_candidates_with_labels,
)


def test_load_toi_catalog(tmp_path):
    # Create a mock TOI catalog with 3 comment lines
    catalog_content = (
        "# toi-catalog\n"
        "# Generated on 2026-06-30\n"
        "# Collection PK: 193\n"
        "pk,TIC,TOI Disposition,Orbital Period (days) Value,Transit Depth Value,Transit Duration (hours) Value\n"
        "1,1234567,CP,10.0,1000.0,2.5\n"
        "2,2345678,EB,5.5,5000.0,4.0\n"
        "3,3456789,PC,2.0,150.0,1.2\n"
    )
    catalog_file = tmp_path / "mock_toi_catalog.csv"
    catalog_file.write_text(catalog_content)

    df = load_toi_catalog(catalog_file)
    assert len(df) == 3
    assert list(df["TIC"]) == [1234567, 2345678, 3456789]
    assert list(df["TOI Disposition"]) == ["CP", "EB", "PC"]


def test_map_disposition_to_class():
    assert map_disposition_to_class("CP") == "planet"
    assert map_disposition_to_class("KP") == "planet"
    assert map_disposition_to_class("EB") == "eclipsing_binary"
    assert map_disposition_to_class("PC") == "planet_candidate"
    assert map_disposition_to_class("FP") == "false_positive"
    assert map_disposition_to_class("O") == "noise"
    assert map_disposition_to_class("V") == "noise"
    assert map_disposition_to_class("IS") == "noise"
    assert map_disposition_to_class("UNKNOWN") == "noise"
    assert map_disposition_to_class(None) == "noise"


def test_join_candidates_with_labels():
    candidates_data = {
        "TIC_ID": ["TIC_1234567", "TIC_2345678", "TIC_9999999"],
        "period": [10.0, 5.5, 99.9],
    }
    candidates_df = pd.DataFrame(candidates_data)

    toi_data = {
        "TIC": [1234567, 2345678],
        "TOI Disposition": ["CP", "EB"],
        "Orbital Period (days) Value": [10.0, 5.5],
        "Transit Depth Value": [1000.0, 5000.0],
        "Transit Duration (hours) Value": [2.5, 4.0],
    }
    toi_df = pd.DataFrame(toi_data)

    merged = join_candidates_with_labels(candidates_df, toi_df)

    assert len(merged) == 3
    # Check labels mapping
    assert merged.loc[merged["TIC"] == 1234567, "label"].values[0] == "planet"
    assert merged.loc[merged["TIC"] == 2345678, "label"].values[0] == "eclipsing_binary"
    assert merged.loc[merged["TIC"] == 9999999, "label"].values[0] == "unlabelled"

    # Check that it attaches other TOI columns
    assert merged.loc[merged["TIC"] == 1234567, "Transit Depth Value"].values[0] == 1000.0
    assert merged.loc[merged["TIC"] == 2345678, "Transit Duration (hours) Value"].values[0] == 4.0
