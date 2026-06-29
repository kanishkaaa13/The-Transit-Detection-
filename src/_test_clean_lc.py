"""
Offline unit tests for clean_lightcurves.py — no TESS data required.
Run with:  py -m src._test_clean_lc
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import numpy as np
import tempfile, pathlib
import pandas as pd
from src.clean_lightcurves import (
    _drop_nans, _sigma_clip, _normalise, _savgol_window, _detrend_savgol, clean_one
)

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

def check(name, cond):
    print(f"  {PASS if cond else FAIL}  {name}")
    if not cond:
        sys.exit(1)

print("\n── _drop_nans ──────────────────────────────────────────────")
df = pd.DataFrame({"time":[1,2,np.nan,4], "flux":[1.0,np.nan,3.0,4.0], "flux_err":[0.1]*4})
out = _drop_nans(df)
check("2 NaN rows removed", len(out) == 2)
check("Sorted by time", list(out["time"]) == sorted(out["time"]))

print("\n── _sigma_clip ─────────────────────────────────────────────")
rng = np.random.default_rng(42)
flux = np.concatenate([rng.normal(1.0, 0.01, 1000), [100.0, -100.0]])  # 2 outliers
keep = _sigma_clip(flux, sigma=5.0)
check("1000 good points kept", keep[:1000].all())
check("2 outliers rejected", ~keep[1000:].any())

print("\n── _normalise ──────────────────────────────────────────────")
f  = np.array([2.0, 4.0, 6.0])
fe = np.array([0.1, 0.2, 0.3])
fn, fen = _normalise(f, fe)
check("Normalised median ≈ 1.0", abs(np.median(fn) - 1.0) < 1e-10)
check("Error scaled correctly", abs(fen[1] - 0.2/np.median(f)) < 1e-10)

print("\n── _savgol_window ──────────────────────────────────────────")
win = _savgol_window(cadence_days=2/1440, window_days=3.0, poly_order=2)
check("Window is odd", win % 2 == 1)
check("Window ≈ 2160 pts for 3d @ 2min", 2150 <= win <= 2165)
check("Window > poly_order", win > 2)

print("\n── _detrend_savgol ─────────────────────────────────────────")
t = np.linspace(0, 27, 19440)          # 27 d at 2-min cadence
trend = 1.0 + 0.05 * np.sin(2*np.pi*t/14)   # slow 14-d sinusoid
transit_mask = ((t % 5) < 0.1)               # shallow transits every 5 d
signal = trend.copy()
signal[transit_mask] *= 0.99          # 1% depth transits
flux_n  = signal / np.median(signal)
ferr_n  = np.full_like(flux_n, 0.001)

residual, err_d, sg = _detrend_savgol(t, flux_n, ferr_n, window_days=3.0)
check("Residual mean ≈ 1.0",   abs(residual.mean() - 1.0) < 0.005)
check("Residual std < raw std", residual.std() < flux_n.std())
check("SG trend shape matches", sg.shape == flux_n.shape)
check("Error propagated",       err_d.shape == ferr_n.shape)

print("\n── clean_one (end-to-end) ──────────────────────────────────")
with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir = pathlib.Path(tmpdir)

    # Write a fake raw CSV
    raw_path = tmpdir / "TIC_999999.csv"
    n = 5000
    t2 = np.linspace(0, 10, n)
    f2 = 1.0 + 0.02 * np.sin(2*np.pi*t2/7) + np.random.default_rng(0).normal(0, 0.002, n)
    f2[42] = 50.0      # deliberate outlier
    pd.DataFrame({"time": t2, "flux": f2, "flux_err": np.full(n, 0.002)}).to_csv(raw_path, index=False)

    out_path = tmpdir / "TIC_999999_clean.csv"
    info = clean_one(raw_path, out_path, sigma=5.0, window_days=3.0)

    result = pd.read_csv(out_path)
    check("Output CSV exists",              out_path.exists())
    check("Expected columns present",       {"time","flux_norm","flux_err_norm","sg_trend"}.issubset(result.columns))
    check("Fewer rows than raw (outlier removed)", len(result) < n)
    check("flux_norm mean ≈ 1.0",          abs(result["flux_norm"].mean() - 1.0) < 0.01)
    check("clip_pct recorded",             "clip_pct" in info)
    check("Outlier row removed",           info["n_after_clip"] < info["n_after_nan"])

print("\n── All tests passed ────────────────────────────────────────\n")
