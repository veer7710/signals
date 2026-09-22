"""
run_frontier.py -- "70% win rate AND leg to leg" is a frontier, not a setting.

Sweeps the only three knobs a scale-out actually has:
    f   fraction banked at the first target
    r1  where that first target sits, in R
    be  where the stop goes once the bank fills, in R from entry
and prints the whole frontier so the trade-off is visible instead of argued.

Everything else is held fixed: same entries, same stop, same ATR-3 trail on
the runner, same costs. Any difference in the table IS these three knobs.
"""
import sys, numpy as np
sys.path.insert(0, "research")
import core
from run_drift import detrend
from run_partials import all_entries, run_scaled, summarise, COSTS

def frontier(sym, tf, grid_f, grid_r1, grid_be):
    raw = core.load(sym, tf); d = detrend(raw)
    cost = COSTS[sym]; sig = all_entries(d)
    rows = []
    # references
    for nm, cfg in (("runner only, ATR3 trail", dict(legs=[(1.0,None)], trail_atr=3.0, trail_after_leg=0)),
                    ("fixed 1R, no runner",     dict(legs=[(1.0,1.0)],  trail_atr=0.0))):
        s = summarise(nm, run_scaled(d, sig, cost=cost, **cfg))
        if s: rows.append(s)
    for f in grid_f:
        for r1 in grid_r1:
            for be in grid_be:
                nm = f"bank {int(f*100)}% @{r1}R, stop->{be}R"
                t = run_scaled(d, sig, [(f, r1), (1-f, None)], cost=cost,
                               trail_atr=3.0, be_after_leg=1, be_offset=be,
                               trail_after_leg=1)
                s = summarise(nm, t)
                if s: rows.append(s)
    return d, sig, rows

HDR = (f"  {'exit rule':<30}{'n':>5}{'win%':>7}{'$/trd':>8}{'t':>6}"
       f"{'gave':>6}{'rockKeep':>10}{'rock$':>8}{'avgW':>7}{'avgL':>7}{'maxDD':>7}")

def show(title, rows, key):
    print(f"\n{'='*106}\n{title}\n{'='*106}")
    print(HDR)
    for s in sorted(rows, key=key):
        star = "  <-- >=70% win" if s["win"] >= 0.70 else ""
        print(f"  {s['name']:<30}{s['n']:>5}{100*s['win']:>7.1f}{s['pts']:>8.2f}"
              f"{s['t']:>6.2f}{100*s['gave']:>5.0f}%{s['rock_keep']:>10.2f}"
              f"{s['rock_pts']:>8.2f}{s['avgW']:>7.2f}{s['avgL']:>7.2f}"
              f"{s['dd']:>7.0f}{star}")

if __name__ == "__main__":
    F  = [0.25, 0.40, 0.50, 0.65, 0.80]
    R1 = [0.25, 0.4, 0.5, 0.75, 1.0]
    BE = [0.0, 0.1, 0.25]
    for sym, tf in (("GOLD","1h"), ("GOLD","15m")):
        d, sig, rows = frontier(sym, tf, F, R1, BE)
        n_bars = d["n"]; days = (d["t"][-1]-d["t"][0])/86400.0
        show(f"{sym} {tf}  ({n_bars} bars, {days:.0f} calendar days, {len(sig)} entries) "
             f"-- BY EXPECTANCY", rows, lambda s: -s["pts"])
        hi = [s for s in rows if s["win"] >= 0.65]
        if hi:
            show(f"{sym} {tf}  -- ONLY the rules at >=65% WIN RATE, best expectancy first",
                 hi, lambda s: -s["pts"])
        else:
            print(f"\n  {sym} {tf}: NOTHING in this grid reached a 65% win rate.")
        best = max(rows, key=lambda s: s["pts"])
        bw = max((s for s in rows if s["win"] >= 0.70), key=lambda s: s["pts"], default=None)
        print(f"\n  best expectancy : {best['name']}  {best['pts']:.2f}/trade at "
              f"{100*best['win']:.1f}% win, keeps {best['rock_keep']:.2f} of the rockets")
        if bw:
            print(f"  best >=70% win  : {bw['name']}  {bw['pts']:.2f}/trade at "
                  f"{100*bw['win']:.1f}% win, keeps {bw['rock_keep']:.2f} of the rockets")
            print(f"  price of the win rate: {best['pts']-bw['pts']:.2f}/trade "
                  f"({100*(1-bw['pts']/best['pts']):.0f}% of expectancy) and "
                  f"{best['rock_keep']-bw['rock_keep']:.2f} of rocket capture")
        else:
            print(f"  NO rule in this grid reached 70% win rate on {sym} {tf}.")
