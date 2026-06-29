"""
Offline unit tests for run_bls.py — no TESS data required.
Injects a known transit signal and checks that BLS recovers it.

Run with:  $env:PYTHONUTF8=1; py -m src._test_run_bls
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import tempfile
import numpy as np
import pandas as pd
from src.run_bls import (
    _duration_grid, _period_grid, run_bls_one
)

PASS = "\033[92mOK\033[0m"
FAIL = "\033[91mFAIL\033[0m"

def check(name, cond, extra=""):
    tag = PASS if cond else FAIL
    print(f"  [{tag}]  {name}" + (f"  ({extra})" if extra else ""))
    if not cond:
        sys.exit(1)

# ──────────────────────────────────────────────────────────────────────────────
print("\n-- _duration_grid --")
dg = _duration_grid(0.5, 15.0, n=20)
check("20 durations returned",  len(dg) == 20)
check("All positive",            np.all(dg > 0))
check("Min <= 0.01*0.5",        dg[0] <= 0.01 * 0.5 + 1e-9)
check("Max >= 0.15*15*0.9",     dg[-1] >= 0.15 * 15 * 0.9)  # geomspace end

# ──────────────────────────────────────────────────────────────────────────────
print("\n-- _period_grid --")
rng  = np.random.default_rng(7)
t27  = np.sort(rng.uniform(0, 27, 19000))   # 27-day baseline
pg   = _period_grid(t27, p_min=0.5, p_max=15.0, min_n_transit=3)
check("Periods are ascending",          np.all(np.diff(pg) >= 0))
check("p_min respected",                pg[0] >= 0.5 - 1e-9)
check("p_max capped at baseline/3",    pg[-1] <= 27.0 / 3 + 1e-6)
check("At least 100 periods",          len(pg) >= 100)

# Short baseline — p_max should be clamped
t3   = np.linspace(0, 3, 2100)
pg3  = _period_grid(t3, 0.5, 15.0, min_n_transit=3)
check("Short baseline: max period <= 1 d",  pg3[-1] <= 1.0 + 1e-6)

# ──────────────────────────────────────────────────────────────────────────────
print("\n-- run_bls_one: transit recovery --")

# Build a synthetic 27-d, 2-min cadence light curve with a known transit
TRUE_PERIOD   = 4.123      # days
TRUE_DEPTH    = 0.010      # 1 % depth (10 000 ppm)
TRUE_DURATION = 0.10       # days (2.4 h)
TRUE_T0       = 1.5        # days

n = 19440          # 27 d × 720 pts/d
t = np.linspace(0, 27, n)
flux = np.ones(n)

# Inject square box transits
for k in range(int(27 / TRUE_PERIOD) + 2):
    tc = TRUE_T0 + k * TRUE_PERIOD
    mask = np.abs(t - tc) < TRUE_DURATION / 2
    flux[mask] -= TRUE_DEPTH

# Add white noise (1 mmag = 0.001)
rng2 = np.random.default_rng(42)
flux += rng2.normal(0, 0.001, n)

with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    csv = tmp / "TIC_99999.csv"
    pd.DataFrame({
        "time": t,
        "flux_norm": flux,
        "flux_err_norm": np.full(n, 0.001),
        "sg_trend": np.ones(n),
    }).to_csv(csv, index=False)

    res = run_bls_one(csv, p_min=0.5, p_max=15.0, min_n_transit=3)

    check("Status is ok",              res["status"] == "ok")
    # BLS may lock on an integer alias (P/2, P/3, 2P) — check all ratios
    aliases = [TRUE_PERIOD / r for r in [1, 2, 3, 4]] + [TRUE_PERIOD * r for r in [2, 3]]
    period_ok = any(abs(res["period_d"] - a) / a < 0.02 for a in aliases)
    check("Period or alias within 2%",  period_ok,
          f"got {res['period_d']:.4f} d, expected ~{TRUE_PERIOD} d (or alias)")
    check("Depth within 30% (rough)",  abs(res["depth"] - TRUE_DEPTH) / TRUE_DEPTH < 0.30,
          f"got {res['depth']:.5f}, expected {TRUE_DEPTH}")
    check("Duration within 50%",       abs(res["duration_d"] - TRUE_DURATION) < TRUE_DURATION * 0.5,
          f"got {res['duration_d']:.4f} d, expected {TRUE_DURATION} d")
    check("SNR > 3",                   res["snr"] > 3.0, f"snr={res['snr']:.2f}")
    check("bls_power > 0",             res["bls_power"] > 0)
    check("n_cadences correct",        res["n_cadences"] == n)
    check("t0 is finite",              np.isfinite(res["t0_btjd"]))
    check("time_span close to 27 d",   abs(res["time_span_d"] - 27) < 0.1,
          f"got {res['time_span_d']:.3f} d")

print("\n-- All BLS tests passed --\n")
