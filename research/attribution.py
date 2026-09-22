"""
attribution.py -- "why are we losing: entry, exit, setup, or conditions?"

Not a win-rate backtest. Every trade is decomposed into an EXACT identity, so
the loss can be assigned rather than guessed at:

    actual = setup_max - entry_cost - exit_cost - spread

  setup_max   what the setup offered AT BEST: the peak, measured from the best
              fill available in the entry window. The ceiling on the idea.
  entry_cost  how much worse the actual fill was than that best fill.
              This is "we are not hitting top tick", in money.
  exit_cost   how much of the peak was handed back. The give-back.
  spread      the fee, which is certain.

If setup_max is at or below spread, the SETUP was never viable and no amount of
execution work saves it. That is the case the other three numbers cannot show.
"""
import sys, numpy as np
sys.path.insert(0, "research")
import core, backtest as bt
from run_drift import detrend
from run_decisive import pullback_cont, sweep_cont
from run_meanrev import mr_signals

COST = 0.15          # per side
ENTRY_WIN = 3        # bars in which a better fill was realistically available

def attribute(d, signals, exit_cfg, entry_win=ENTRY_WIN, max_bars=120):
    a = core.atr(d, 14)
    rows = []
    r = bt.run(d, signals, stop_fn=bt.stop_struct(0.25), exit_cfg=exit_cfg,
               cost=COST, max_bars=max_bars)
    for t in r.t:
        i, sd = t["i"], t["dir"]
        if i + entry_win >= d["n"]:
            continue
        act_entry = d["o"][i] + sd * COST
        # the best fill actually available in the entry window -- not a fantasy
        # price, a price that traded
        w = slice(i, i + entry_win + 1)
        best_entry = (d["l"][w].min() if sd > 0 else d["h"][w].max())
        entry_cost = max(0.0, (act_entry - best_entry) * sd)
        peak_from_act = t["peak"]
        actual = t["pts"]
        exit_cost = max(0.0, peak_from_act - actual - COST)
        setup_max = peak_from_act + entry_cost
        rows.append(dict(setup=setup_max, entry=entry_cost, exit=exit_cost,
                         cost=2 * COST, actual=actual, atr=a[i - 1] if i > 0 else a[i],
                         peak=peak_from_act, R=t["R"]))
    return rows

def report(name, rows):
    if not rows:
        print(f"  {name}: no trades"); return
    n = len(rows)
    S = sum(r["setup"] for r in rows)
    E = sum(r["entry"] for r in rows)
    X = sum(r["exit"] for r in rows)
    C = sum(r["cost"] for r in rows)
    A = sum(r["actual"] for r in rows)
    dead = sum(1 for r in rows if r["setup"] <= r["cost"])
    print(f"\n  {name}   ({n} trades)")
    print(f"    the setup offered          {S:>9.1f} pts   ({S/n:+.2f}/trade)")
    print(f"    lost to ENTRY (not top tick) {-E:>7.1f} pts   ({-E/n:+.2f}/trade)"
          f"   {100*E/max(S,1e-9):>5.1f}% of what was offered")
    print(f"    lost to EXIT  (give-back)    {-X:>7.1f} pts   ({-X/n:+.2f}/trade)"
          f"   {100*X/max(S,1e-9):>5.1f}%")
    print(f"    lost to SPREAD               {-C:>7.1f} pts   ({-C/n:+.2f}/trade)"
          f"   {100*C/max(S,1e-9):>5.1f}%")
    print(f"    ------------------------------------------------")
    print(f"    actually kept              {A:>9.1f} pts   ({A/n:+.2f}/trade)")
    print(f"    setups that were NEVER viable (offered <= spread): "
          f"{dead}/{n} = {100*dead/n:.0f}%")
    # counterfactuals
    print(f"    if entry were perfect:     {A+E:>9.1f} pts")
    print(f"    if exit  were perfect:     {A+X:>9.1f} pts")
    print(f"    if both:                   {A+E+X:>9.1f} pts")

EXITS = {
 "ATR-3 trail":        dict(mode="trail_atr", trail=3.0),
 "giveback .60 arm 0": dict(mode="giveback", give=0.60, arm=0.0),
}

for sym, tf in [("GOLD", "15m"), ("GOLD", "1h")]:
    d = detrend(core.load(sym, tf))
    fams = {
        "pullback continuation": pullback_cont(d),
        "sweep continuation":    sweep_cont(d),
        "momentum @1.5ATR":      [(i, -s) for i, s in mr_signals(d, 50, 1.5, True)],
    }
    print(f"\n{'='*86}\n{sym} {tf} de-trended -- WHERE THE MONEY GOES\n{'='*86}")
    for ename, ecfg in EXITS.items():
        print(f"\n--- exit: {ename} ---")
        for fname, sig in fams.items():
            if len(sig) < 30:
                continue
            report(f"{fname}", attribute(d, sig, ecfg))


# ====================================================================
#  REALISTIC version. "Perfect entry" and "perfect exit" are hindsight
#  ceilings nobody can hit, so they flatter every improvement. These are
#  bounded by what the two shipped mechanisms can actually deliver:
#    entry: the retail limit gets ONE noise band better, when it fills
#    exit : a disciplined trail keeps ~85% of peak, not 100%
# ====================================================================
def realistic(d, signals, exit_cfg, fill_rate=0.6, keep=0.85, max_bars=120):
    a = core.atr(d, 14)
    r = bt.run(d, signals, stop_fn=bt.stop_struct(0.25), exit_cfg=exit_cfg,
               cost=COST, max_bars=max_bars)
    base = gain_e = gain_x = 0.0
    n = 0
    for t in r.t:
        i, sd = t["i"], t["dir"]
        if i <= 0 or i >= d["n"] - 2: continue
        band = COST + 0.60 * (a[i-1] if not np.isnan(a[i-1]) else 0)
        if band <= 0: continue
        n += 1
        base += t["pts"]
        # entry: one band better, but only on the fraction that actually fills
        gain_e += band * fill_rate
        # exit: keep `keep` of peak instead of whatever was kept
        ideal = t["peak"] * keep - COST
        gain_x += max(0.0, ideal - t["pts"])
    return n, base, gain_e, gain_x

def regime_split(d, signals, exit_cfg):
    er = core.efficiency_ratio(d["c"], 30)
    out = {"RANGE": [0,0.0], "MIXED": [0,0.0], "TREND": [0,0.0]}
    r = bt.run(d, signals, stop_fn=bt.stop_struct(0.25), exit_cfg=exit_cfg,
               cost=COST, max_bars=120)
    for t in r.t:
        i = t["i"]
        e = er[i-1] if i > 0 and not np.isnan(er[i-1]) else np.nan
        if np.isnan(e): continue
        k = "RANGE" if e < 0.15 else ("TREND" if e > 0.30 else "MIXED")
        out[k][0] += 1
        out[k][1] += t["pts"]
    return out

print("\n\n" + "="*86)
print("REALISTIC CEILING -- bounded by what the shipped mechanisms can deliver")
print("  entry: retail limit, one band better, 60% fill rate")
print("  exit : disciplined trail keeping 85% of peak (not 100%)")
print("="*86)
for sym, tf in [("GOLD","15m"), ("GOLD","1h")]:
    d = detrend(core.load(sym, tf))
    fams = {"pullback continuation": pullback_cont(d),
            "sweep continuation": sweep_cont(d),
            "momentum @1.5ATR": [(i,-s) for i,s in mr_signals(d,50,1.5,True)]}
    print(f"\n--- {sym} {tf}, ATR-3 trail ---")
    print(f"  {'family':<26}{'n':>5}{'now':>9}{'+entry fix':>12}{'+exit fix':>11}{'both':>9}")
    for fname, sig in fams.items():
        if len(sig) < 30: continue
        n, base, ge, gx = realistic(d, sig, dict(mode="trail_atr", trail=3.0))
        print(f"  {fname:<26}{n:>5}{base:>9.0f}{base+ge:>12.0f}{base+gx:>11.0f}"
              f"{base+ge+gx:>9.0f}")
    print(f"\n  {'family':<26}{'RANGE n/pts':>18}{'MIXED n/pts':>18}{'TREND n/pts':>18}")
    for fname, sig in fams.items():
        if len(sig) < 30: continue
        rs = regime_split(d, sig, dict(mode="trail_atr", trail=3.0))
        cells = "".join(f"{rs[k][0]:>7}/{rs[k][1]:>9.0f}" for k in ("RANGE","MIXED","TREND"))
        print(f"  {fname:<26}{cells}")
