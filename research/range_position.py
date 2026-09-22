"""
"how can we minimise loss not buying or selling at peaks of trends"

His brief, Finding 7, two facts that look contradictory until you separate
FADING an extreme from ENTERING at one:
  - fading extremes LOSES both ways (sell top of range -1.50, buy bottom -1.67)
  - "entries at 60-80% of the prior 30-min range, IN THE TREND DIRECTION,
     were the only clearly positive cohort in the book"

So the question is not "is the extreme special" but "where in the range should
a trend-direction entry happen". That is measurable. Bucket every trend-aligned
entry by WHERE in the prior range it fired, and look at what each bucket paid.
"""
import sys, numpy as np
sys.path.insert(0, "research")
import core, backtest as bt
from run_drift import detrend
from run_decisive import tstat, boot_ci

def range_pos(d, mins, tf_min):
    """Where is close inside the prior `mins` of range? 0 = low, 1 = high."""
    n = max(4, int(mins / tf_min))
    out = np.full(d["n"], np.nan)
    for i in range(n, d["n"]):
        hi = d["h"][i-n:i].max()
        lo = d["l"][i-n:i].min()
        if hi > lo:
            out[i] = (d["c"][i] - lo) / (hi - lo)
    return out

def trend_entries(d, ema_n=50, slope=3):
    """Every bar where the trend is defined, tagged with its direction.
    No pattern, no filter -- the ONLY variable under test is range position."""
    e = core.ema(d["c"], ema_n)
    out = []
    for i in range(ema_n + slope + 2, d["n"] - 1):
        if np.isnan(e[i]) or np.isnan(e[i-slope]):
            continue
        if e[i] > e[i-slope]:
            out.append((i, 1))
        elif e[i] < e[i-slope]:
            out.append((i, -1))
    return out

for sym, tf, tf_min in [("GOLD", "15m", 15), ("GOLD", "1h", 60)]:
    d = detrend(core.load(sym, tf))
    rp = range_pos(d, 30 if tf_min <= 15 else 120, tf_min)
    ents = trend_entries(d)
    print(f"\n{'='*92}")
    print(f"{sym} {tf} de-trended -- trend-direction entries bucketed by "
          f"POSITION IN THE PRIOR RANGE")
    print(f"exit: ATR-3 trail, stop struct+0.25ATR, cost $0.15/side. "
          f"{len(ents)} candidate bars")
    print(f"{'='*92}")
    print(f"  {'where in range':<26}{'n':>5}{'win%':>7}{'$/trade':>10}{'t':>7}"
          f"{'PF':>7}{'CI95':>18}")
    buckets = [(0.0,0.2,"0-20%  bottom"), (0.2,0.4,"20-40%"), (0.4,0.6,"40-60%  middle"),
               (0.6,0.8,"60-80%"), (0.8,1.01,"80-100% TOP")]
    for lo, hi, name in buckets:
        # LONGS entering in this slice of the range (and shorts mirrored, so
        # "top" always means "extended in the trade's own direction")
        sel = []
        for i, sd in ents:
            if np.isnan(rp[i]):
                continue
            p = rp[i] if sd > 0 else 1.0 - rp[i]
            if lo <= p < hi:
                sel.append((i, sd))
        if len(sel) < 40:
            print(f"  {name:<26}{len(sel):>5}   too few")
            continue
        # thin them so consecutive bars are not counted as separate decisions
        thin = [sel[k] for k in range(0, len(sel), 4)]
        r = bt.run(d, thin, stop_fn=bt.stop_struct(0.25),
                   exit_cfg=dict(mode="trail_atr", trail=3.0), cost=0.15, max_bars=120)
        s = r.stats()
        if not s.get("n") or s["n"] < 25:
            print(f"  {name:<26}{s.get('n',0):>5}   too few after thinning")
            continue
        pts = [x["pts"] for x in r.t]
        lo_, hi_ = boot_ci(pts)
        mark = "  <-- his 60-80% cohort" if name.startswith("60-80") else ""
        print(f"  {name:<26}{s['n']:>5}{100*s['win']:>7.1f}{s['pts']:>10.2f}"
              f"{tstat(pts):>7.2f}{s['pf']:>7.2f}  [{lo_:>6.2f},{hi_:>6.2f}]{mark}")
