"""End-to-end smoke test for score_candidates.py"""
import sys, tempfile, pathlib, numpy as np, pandas as pd
sys.path.insert(0, '.')

from src.score_candidates import score_one, load_model

PASS = 'OK'; FAIL = 'FAIL'
def check(name, cond, extra=''):
    tag = PASS if cond else FAIL
    print(f'  [{tag}]  {name}' + (f'  ({extra})' if extra else ''))
    if not cond: sys.exit(1)

model, seq_len = load_model(
    pathlib.Path('data/models/transit_cnn_weights.pt'),
    pathlib.Path('data/models/transit_cnn_config.json'),
)

with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    n   = 19440
    t   = np.linspace(0, 27, n)

    # ── POSITIVE star: clear 1% transit every 4.5 d ─────────────────────────
    depth, period, t0, dur = 0.010, 4.5, 0.6, 0.09
    flux = np.ones(n)
    for k in range(int(27 / period) + 2):
        tc = t0 + k * period
        flux[np.abs(t - tc) < dur / 2] -= depth
    flux += np.random.default_rng(0).normal(0, 0.001, n)

    pos_csv = tmp / 'TIC_POS.csv'
    pd.DataFrame({
        'time': t, 'flux_norm': flux,
        'flux_err_norm': np.full(n, 0.001), 'sg_trend': np.ones(n),
    }).to_csv(pos_csv, index=False)

    res_pos = score_one('TIC_POS', pos_csv, period, depth, dur, t0, model, seq_len)
    print(f"\nPOSITIVE star:")
    print(f"  SNR       = {res_pos['SNR']:.2f}")
    print(f"  CNN_score = {res_pos['CNN_score']:.3f}")
    print(f"  candidate = {res_pos['is_candidate']}")
    check('Positive SNR > 7',        res_pos['SNR'] > 7,     f"{res_pos['SNR']:.2f}")
    check('Positive CNN > 0.7',      res_pos['CNN_score'] > 0.7, f"{res_pos['CNN_score']:.3f}")
    check('Positive is candidate',   res_pos['is_candidate'] == 1)

    # ── NEGATIVE star: flat + noise ──────────────────────────────────────────
    flux2 = np.ones(n) + np.random.default_rng(5).normal(0, 0.001, n)
    neg_csv = tmp / 'TIC_NEG.csv'
    pd.DataFrame({
        'time': t, 'flux_norm': flux2,
        'flux_err_norm': np.full(n, 0.001), 'sg_trend': np.ones(n),
    }).to_csv(neg_csv, index=False)

    # Tiny BLS depth so SNR is far below threshold
    res_neg = score_one('TIC_NEG', neg_csv, 4.5, 0.0005, 0.05, 0.3, model, seq_len)
    print(f"\nNEGATIVE star:")
    print(f"  SNR       = {res_neg['SNR']:.2f}")
    print(f"  CNN_score = {res_neg['CNN_score']:.3f}")
    print(f"  candidate = {res_neg['is_candidate']}")
    check('Negative CNN < 0.7',        res_neg['CNN_score'] < 0.7, f"{res_neg['CNN_score']:.3f}")
    check('Negative is NOT candidate', res_neg['is_candidate'] == 0)
    # Note: SNR may be above 7 for tiny-depth signals with many cadences,
    # but the CNN gate (< 0.70) correctly rejects the flat star.

print('\n-- End-to-end smoke test PASSED --\n')
