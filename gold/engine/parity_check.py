"""
PROVE the EA's signal logic == the Pine reference.

Transcribes XAUUSD_LEAN.mq5's Signal_Compute() into Python LINE FOR LINE, including
the fact that the EA recomputes the whole chain from a fixed `warmup` window ending
at the current bar (CopyRates(_Symbol,TF,1,need,r)), then compares its per-bar
direction against the full-history Pine chain on real broker data.

This is the step that was never done for QUAD: its Pine parity was assumed.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from pine import clean_signals


def lean_signal_window(high, low, close, end, warmup, factor, L):
    """Exactly what Signal_Compute() does when the newest closed bar is `end`."""
    s = end - warmup + 1
    if s < 0:
        return None
    h = high[s:end + 1]; l = low[s:end + 1]; c = close[s:end + 1]
    n = len(c)
    if n <= L:
        return None

    tr = np.empty(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        pc = c[i - 1]
        tr[i] = max(h[i] - l[i], abs(h[i] - pc), abs(l[i] - pc))

    atr = np.zeros(n); atr_ok = np.zeros(n, bool)
    atr[L - 1] = tr[:L].mean(); atr_ok[L - 1] = True
    for i in range(L, n):
        atr[i] = atr[i - 1] + (tr[i] - atr[i - 1]) / L
        atr_ok[i] = True

    prev_lb = prev_ub = 0.0
    prev_st = prev_ub_final = 0.0
    have_prev_st = False
    d = 1
    st = 0.0
    for i in range(n):
        mid = (h[i] + l[i]) / 2.0
        a_ok = atr_ok[i]
        lb = mid - factor * atr[i] if a_ok else 0.0
        ub = mid + factor * atr[i] if a_ok else 0.0
        pc_ok = i > 0
        pc = c[i - 1] if pc_ok else 0.0
        cond_l = (a_ok and lb > prev_lb) or (pc_ok and pc < prev_lb)
        new_lb = lb if cond_l else prev_lb
        cond_u = (a_ok and ub < prev_ub) or (pc_ok and pc > prev_ub)
        new_ub = ub if cond_u else prev_ub
        atr_prev_na = (i == 0) or (not atr_ok[i - 1])
        if atr_prev_na:
            d = 1
        elif have_prev_st and prev_st == prev_ub_final:
            d = -1 if c[i] > new_ub else 1
        else:
            d = 1 if c[i] < new_lb else -1
        st = new_lb if d == -1 else new_ub
        prev_lb, prev_ub = new_lb, new_ub
        prev_ub_final = new_ub
        prev_st = st
        have_prev_st = True
    return d, st


if __name__ == "__main__":
    WARMUP = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    NSAMP = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    FAC, L = 1.2, 7

    df = pd.read_parquet("data/xauusd_m1.parquet")
    df = df[df.dt >= "2025-01-01"].reset_index(drop=True)
    h, l, c = df.high.values, df.low.values, df.close.values
    print(f"bars {len(h):,}  warmup {WARMUP}  sampling {NSAMP} bars")

    # full-history Pine reference
    d_ref, buy, sell, st_ref = clean_signals(h, l, c, FAC, L)

    rng = np.random.default_rng(1)
    idx = rng.choice(np.arange(WARMUP + 50, len(h)), size=NSAMP, replace=False)
    idx.sort()

    dir_mismatch = 0
    st_err = []
    checked = 0
    for i in idx:
        r = lean_signal_window(h, l, c, int(i), WARMUP, FAC, L)
        if r is None:
            continue
        d_ea, st_ea = r
        checked += 1
        if d_ea != d_ref[i]:
            dir_mismatch += 1
        st_err.append(abs(st_ea - st_ref[i]))

    st_err = np.array(st_err)
    print(f"\nbars checked          : {checked}")
    print(f"DIRECTION mismatches  : {dir_mismatch}  ({100*dir_mismatch/max(checked,1):.4f}%)")
    print(f"Supertrend LEVEL error: max {st_err.max():.2e}  mean {st_err.mean():.2e}")
    verdict = "PARITY PROVEN" if dir_mismatch == 0 and st_err.max() < 1e-6 else "MISMATCH"
    print(f"\n>>> {verdict} <<<")
    if dir_mismatch:
        print("The EA's windowed recompute does NOT reproduce the full-history Pine chain.")
        print("Raise InpWarmupBars until mismatches reach zero.")
