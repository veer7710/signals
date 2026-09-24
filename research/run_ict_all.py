"""
run_ict_all.py -- the sample-size problem, solved the only honest way available.

GOLD 1h is 2.4 years and the best killzone row in run_ict.py is n=23. Nothing
can be concluded from 23 trades. But the CONCEPT -- "a sweep of a known
liquidity level followed by a structure shift has predictive power" -- is not
gold-specific. If it is real it should show a positive residual on instruments
that share no common driver with gold, and if it is a gold artefact it will not.

So every model is run on all five sets and the residual is POOLED. Pooling
across instruments is legitimate here in a way that pooling dollars is not,
because the residual is a probability, dimensionless, and comparable across
anything. Dollars are not, so dollars stay per-instrument.
"""
import sys, numpy as np
sys.path.insert(0, "research")
import core, sessions as S, ict
from run_ict import run_model, summarise, shuffled_null
from run_partials import COSTS
from run_decisive import tstat

SETS = [("GOLD","1h"), ("GOLD","15m"), ("EURUSD","1h"), ("EURUSD","15m"),
        ("GBPUSD","1h"), ("GBPUSD","15m"), ("US500","1h"), ("US500","15m")]

def build(sym, tf):
    d = core.load(sym, tf); f = S.ny_fields(d)
    PDH, PDL = S.prior_day_levels(d, f)
    PWH, PWL = S.prior_week_levels(d, f)
    AH, AL   = S.session_levels(d, f, "asia_range")
    EQH, EQL = ict.equal_levels(d)
    return d, f, {"PDH/PDL": (PDH, PDL), "PWH/PWL": (PWH, PWL),
                  "Asian range": (AH, AL), "EQH/EQL": (EQH, EQL)}

VARIANTS = {
    "sweep+MSS(disp)":      dict(use_displacement=True,  close_back=True),
    "sweep+MSS(close)":     dict(use_displacement=False, close_back=True),
    "breach+MSS(disp)":     dict(use_displacement=True,  close_back=False),
}
WINDOWS = [None, "london_kz", "ny_am_kz", "sb_am"]

if __name__ == "__main__":
    pooled = {}
    per_set = {}
    for sym, tf in SETS:
        try: d, f, POOLS = build(sym, tf)
        except Exception as e:
            print(f"  skip {sym} {tf}: {e}"); continue
        cost = COSTS[sym]
        for pn, (hi, lo) in POOLS.items():
            for vn, vk in VARIANTS.items():
                for w in WINDOWS:
                    sig = ict.sweep_mss_entries(d, f, hi, lo, window=w, **vk)
                    if len(sig) < 8: continue
                    t = run_model(d, f, sig, hi, lo, cost=cost)
                    s = summarise("x", t)
                    if not s or np.isnan(s["resid"]): continue
                    key = f"{pn} | {vn} | {w or 'any hour'}"
                    pooled.setdefault(key, []).append(
                        (s["resid"], s["n"], s["pts"], s["t"], f"{sym}{tf}"))
    print(f"\n{'='*112}")
    print("POOLED ACROSS 8 SETS -- residual over geometry, weighted by trade count")
    print("A concept that only works on gold is a gold artefact. One that shows a")
    print("positive residual on instruments sharing no driver is a candidate.")
    print(f"{'='*112}")
    print(f"  {'model':<46}{'sets':>5}{'trades':>8}{'wResid':>8}{'+ve':>6}"
          f"{'meanT':>7}   per-set residual")
    rows = []
    for k, v in pooled.items():
        r = np.array([x[0] for x in v]); n = np.array([x[1] for x in v])
        p = np.array([x[2] for x in v]); tt = np.array([x[3] for x in v])
        if n.sum() < 60: continue
        w = float((r * n).sum() / n.sum())
        rows.append((w, k, len(v), int(n.sum()), int((r > 0).sum()),
                     float(tt.mean()), r))
    for w, k, ns, nt, pos, mt, r in sorted(rows, reverse=True):
        det = " ".join(f"{100*x:+.0f}" for x in r)
        flag = "  <--" if (w > 0.03 and pos >= ns * 0.6) else ""
        print(f"  {k:<46}{ns:>5}{nt:>8}{100*w:>+8.1f}{pos:>3}/{ns:<2}{mt:>7.2f}   {det}{flag}")
    print("\n  wResid = trade-count-weighted mean of (win% - S/(S+T)%) across sets")
    print("  +ve    = how many of those sets had a POSITIVE residual")
    print("  A concept with wResid ~ 0 has no edge beyond where it put its target.")
