import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from stage4_validate import validate_classifications


def test_validate_classifications(tmp_path):
    # 1. Create a mock pipeline output CSV
    pipe_content = (
        "TIC_ID,predicted_class,confidence\n"
        "TIC_12345,planet,0.95\n"
        "TIC_23456,eclipsing_binary,0.85\n"
        "TIC_34567,planet_candidate,0.75\n"
        "TIC_45678,noise,0.90\n"
    )
    pipe_file = tmp_path / "mock_pipeline_output.csv"
    pipe_file.write_text(pipe_content)

    # 2. Create a mock TOI catalog CSV
    toi_content = (
        "# toi-catalog\n"
        "# Generated on 2026-06-30\n"
        "# Collection PK: 193\n"
        "pk,TIC,TOI Disposition,TMag Value,Effective Temperature Value,Surface Gravity Value,Star Radius Value,Orbital Period (days) Value,Transit Depth Value,Transit Duration (hours) Value,Signal-to-noise\n"
        "1,12345,CP,10.0,5800.0,4.4,1.0,10.0,1000.0,2.5,25.0\n"
        "2,23456,EB,12.0,6000.0,4.3,1.2,5.5,5000.0,4.0,15.0\n"
        "3,34567,PC,11.5,5700.0,4.4,0.9,3.0,500.0,2.0,12.0\n"
        "4,45678,O,9.5,6200.0,4.1,1.5,15.0,200.0,1.2,5.0\n"
    )
    toi_file = tmp_path / "mock_toi_catalog.csv"
    toi_file.write_text(toi_content)

    plot_file = tmp_path / "plots" / "test_confusion_matrix.png"

    # Run validation function
    # It should print output and write confusion matrix png
    validate_classifications(pipe_file, toi_file, plot_file)

    # Check that confusion matrix image exists
    assert plot_file.exists()


def test_validate_classifications_no_overlap(tmp_path, capsys):
    # Pipeline TICs do not overlap with TOI TICs
    pipe_content = (
        "TIC_ID,predicted_class,confidence\n"
        "TIC_99999,planet,0.95\n"
    )
    pipe_file = tmp_path / "mock_pipeline_output.csv"
    pipe_file.write_text(pipe_content)

    toi_content = (
        "# toi-catalog\n"
        "# Generated on 2026-06-30\n"
        "# Collection PK: 193\n"
        "pk,TIC,TOI Disposition,TMag Value,Effective Temperature Value,Surface Gravity Value,Star Radius Value,Orbital Period (days) Value,Transit Depth Value,Transit Duration (hours) Value,Signal-to-noise\n"
        "1,12345,CP,10.0,5800.0,4.4,1.0,10.0,1000.0,2.5,25.0\n"
    )
    toi_file = tmp_path / "mock_toi_catalog.csv"
    toi_file.write_text(toi_content)

    plot_file = tmp_path / "plots" / "test_confusion_matrix.png"

    # Run validation
    validate_classifications(pipe_file, toi_file, plot_file)

    # Capturing stdout to verify that zero overlapping targets warning was printed
    captured = capsys.readouterr()
    assert "WARNING: 0 OVERLAPPING CANDIDATES FOUND" in captured.out
    assert not plot_file.exists()
