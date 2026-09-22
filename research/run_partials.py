"""
run_partials.py -- the one exit question the single-exit sweep could not answer.

Veer's observation, in his words: "our trades don't often hit 6 pound ... a
majority only reach 0 to 5 ... but sometimes it does go up there seen some
rockets go to 30 pound."

That is a MIXTURE, and no single exit rule can serve both halves of it:
  - a tight exit banks the 0-5 crowd and caps the rocket,
  - a loose trail pays on the rocket and hands the 0-5 crowd back to the market.

A scale-out serves both, but only if the arithmetic actually works, which is
what this file measures rather than assumes. Same entries, same bars, same
direction for every exit tested -- so any difference IS the exit.

Realism rules kept from measure.py:
  R1 entry at the OPEN of the bar after the signal, costs both sides
  R2 a partial target is a LIMIT: filled at the target, or better on a gap
  R3 the stop wins every tie -- checked before the target on the same bar
"""
import sys, numpy as np
sys.path.insert(0, "research")
import core, backtest as bt
from run_drift import detrend
from run_decisive import pullback_cont, sweep_cont, tstat, boot_ci
from run_meanrev import mr_signals

COST = 0.15                      # GOLD, per side
# per-side cost in PRICE units. 0.15 on EURUSD would be 1500 pips, which is why
# the first run of this file returned a 0% win rate on every FX row.
COSTS = {"GOLD": 0.15, "EURUSD": 0.00005, "GBPUSD": 0.00007, "US500": 0.25}

def all_entries(d):
    s = {}
    for fn in (pullback_cont, sweep_cont,
               lambda dd: [(i, -x) for i, x in mr_signals(dd, 50, 1.5, True)]):
        for i, sd in fn(d):
            s.setdefault(i, sd)
    return sorted(s.items())

def run_scaled(d, signals, legs, *, trail_atr=3.0, be_after_leg=0,
               be_offset=0.0, trail_after_leg=1, stop_fn=None, cost=COST,
               max_bars=120):
    """legs: list of (fraction, target_in_R or None). None = runner, trailed.
    be_after_leg: once this many legs have filled, ratchet the stop to
                  entry + be_offset*stop_d. 0 disables.
    trail_after_leg: legs that must fill before the ATR trail arms. 0 = armed
                  from the first bar (that is what a plain "ATR trail" means).
    Returns per-trade dicts in POINTS-PER-FULL-UNIT so every exit rule is
    directly comparable to the single-exit sweep."""
    stop_fn = stop_fn or bt.stop_struct(0.25)
    a = core.atr(d, 14); n = d["n"]; out = []
    assert abs(sum(f for f, _ in legs) - 1.0) < 1e-9, "leg fractions must sum to 1"
    for si, sd in signals:
        j = si + 1
        if j >= n - 1 or np.isnan(a[si]) or a[si] <= 0: continue
        e = d["o"][j] + sd * cost
        stop_d = stop_fn(d, si, sd, a[si])
        if stop_d <= 0: continue
        stop = e - sd * stop_d
        open_legs = list(legs)
        realised = 0.0          # points x fraction, gross of the exit cost
        filled = 0
        peak = 0.0; k = j
        for k in range(j, min(j + max_bars, n)):
            hi, lo, c_ = d["h"][k], d["l"][k], d["c"][k]
            fav = (hi - e) * sd if sd > 0 else (e - lo)
            if fav > peak: peak = fav
            # ---- R3: stop first, and it takes every remaining leg ----
            hit_s = lo <= stop if sd > 0 else hi >= stop
            if hit_s:
                px = d["o"][k] if (d["o"][k] - stop) * sd < 0 else stop
                rem = sum(f for f, _ in open_legs)
                realised += (px - e) * sd * rem
                open_legs = []
                break
            # ---- R2: targets are limits ----
            still = []
            for f, rr in open_legs:
                if rr is None: still.append((f, rr)); continue
                targ = e + sd * rr * stop_d
                hit_t = hi >= targ if sd > 0 else lo <= targ
                if hit_t:
                    px = d["o"][k] if (d["o"][k] - targ) * sd > 0 else targ
                    realised += (px - e) * sd * f
                    filled += 1
                else:
                    still.append((f, rr))
            open_legs = still
            if not open_legs:
                k += 1; break
            # ---- ratchets, on the close ----
            cand = stop
            if be_after_leg and filled >= be_after_leg:
                cand = e + sd * be_offset * stop_d
            if trail_atr and filled >= trail_after_leg:
                t_ = c_ - sd * trail_atr * a[k]
                cand = max(cand, t_) if sd > 0 else min(cand, t_)
            stop = max(stop, cand) if sd > 0 else min(stop, cand)
        if open_legs:                       # ran out of bars
            px = d["c"][min(k, n - 1)]
            realised += (px - e) * sd * sum(f for f, _ in open_legs)
        pts = realised - cost               # entry cost already in e
        out.append(dict(i=j, dir=sd, pts=pts, R=pts / stop_d, peak=peak,
                        peak_R=peak / stop_d, bars=k - j + 1, stop_d=stop_d))
    return out

def summarise(name, t):
    if not t: return None
    pts = np.array([x["pts"] for x in t])
    pk = np.array([x["peak"] for x in t])
    pkR = np.array([x["peak_R"] for x in t])
    R = np.array([x["R"] for x in t])
    w = pts > 0
    good = pkR >= 0.5
    cap = float(np.nanmean(R[good] / pkR[good])) if good.sum() else float("nan")
    n1 = (pkR >= 1.0).sum()
    gave = float(((pkR >= 1.0) & (R <= 0)).sum() / n1) if n1 else float("nan")
    eq = np.cumsum(pts); dd = float((np.maximum.accumulate(eq) - eq).max())
    # the rocket test: what did we keep on the biggest 5% of excursions?
    if len(pkR) > 20:
        cut = np.quantile(pkR, 0.95)
        rock = pkR >= cut
        rock_keep = float(np.nanmean(R[rock] / pkR[rock]))
        rock_pts = float(pts[rock].mean())
    else:
        rock_keep = rock_pts = float("nan")
    return dict(name=name, n=len(t), win=float(w.mean()), pts=float(pts.mean()),
                t=tstat(pts), cap=cap, gave=gave, dd=dd,
                rock_keep=rock_keep, rock_pts=rock_pts,
                avgW=float(pts[w].mean()) if w.any() else 0.0,
                avgL=float(pts[~w].mean()) if (~w).any() else 0.0)

# ---- the candidate exits -------------------------------------------------
# single-exit references, run through the same engine as one 100% runner
SINGLE = {
 "ATR trail 3.0 (no partial)":  dict(legs=[(1.0, None)], trail_atr=3.0, trail_after_leg=0),
 "ATR trail 2.0 (no partial)":  dict(legs=[(1.0, None)], trail_atr=2.0, trail_after_leg=0),
 "ATR trail 1.5 (no partial)":  dict(legs=[(1.0, None)], trail_atr=1.5, trail_after_leg=0),
 "hold 120 bars, stop only":   dict(legs=[(1.0, None)], trail_atr=0.0),
 "fixed 1R (no partial)":       dict(legs=[(1.0, 1.0)],  trail_atr=0.0),
 "fixed 2R (no partial)":       dict(legs=[(1.0, 2.0)],  trail_atr=0.0),
}
SCALED = {
 "50% @1R + 50% trail3, BE":    dict(legs=[(0.5,1.0),(0.5,None)], trail_atr=3.0, be_after_leg=1),
 "50% @1R + 50% trail3, no BE": dict(legs=[(0.5,1.0),(0.5,None)], trail_atr=3.0, be_after_leg=0),
 "50% @0.5R + 50% trail3, BE":  dict(legs=[(0.5,0.5),(0.5,None)], trail_atr=3.0, be_after_leg=1),
 "70% @1R + 30% trail3, BE":    dict(legs=[(0.7,1.0),(0.3,None)], trail_atr=3.0, be_after_leg=1),
 "30% @1R + 70% trail3, BE":    dict(legs=[(0.3,1.0),(0.7,None)], trail_atr=3.0, be_after_leg=1),
 "50% @1R + 50% trail2, BE":    dict(legs=[(0.5,1.0),(0.5,None)], trail_atr=2.0, be_after_leg=1),
 "50% @1R + 50% @3R, BE":       dict(legs=[(0.5,1.0),(0.5,3.0)],  trail_atr=0.0, be_after_leg=1),
 "1/3 @1R,1/3 @2R,1/3 trail3":  dict(legs=[(1/3,1.0),(1/3,2.0),(1/3,None)], trail_atr=3.0, be_after_leg=1),
 "50% @1R + 50% trail3, BE+.25":dict(legs=[(0.5,1.0),(0.5,None)], trail_atr=3.0, be_after_leg=1, be_offset=0.25),
}

HDR = (f"  {'exit rule':<32}{'n':>5}{'win%':>7}{'$/trd':>8}{'t':>6}"
       f"{'capt':>6}{'gave':>7}{'rockKeep':>10}{'rock$':>8}{'avgW':>7}{'avgL':>7}{'maxDD':>7}")

def line(s, mark=""):
    return (f"  {s['name']:<32}{s['n']:>5}{100*s['win']:>7.1f}{s['pts']:>8.2f}"
            f"{s['t']:>6.2f}{s['cap']:>6.2f}{100*s['gave']:>6.0f}%"
            f"{s['rock_keep']:>10.2f}{s['rock_pts']:>8.2f}"
            f"{s['avgW']:>7.2f}{s['avgL']:>7.2f}{s['dd']:>7.0f}{mark}")

if __name__ == "__main__":
    sets = [("GOLD","1h"),("GOLD","15m"),("EURUSD","1h"),("GBPUSD","1h"),("US500","1h")]
    agg = {}
    for sym, tf in sets:
        raw = core.load(sym, tf); d = detrend(raw)
        cost = COSTS[sym]
        unit = float(np.nanmedian(core.atr(d, 14)))   # 1 unit = 1 median ATR
        sig = all_entries(d)
        print(f"\n{'='*118}")
        print(f"{sym} {tf} DE-TRENDED -- {len(sig)} entries, identical for every row. "
              f"Only the exit changes. cost {cost}/side, 1 ATR = {unit:.5f}")
        print(f"{'='*118}")
        print(HDR)
        rows = []
        for group in (SINGLE, SCALED):
            for name, cfg in group.items():
                t = run_scaled(d, sig, cost=cost, **cfg)
                s = summarise(name, t)
                if s: rows.append((s["pts"], s, name in SCALED))
                if s: agg.setdefault(name, []).append(s["pts"] / unit)
        for _, s, is_scaled in sorted(rows, key=lambda r: -r[0]):
            print(line(s, "  <<" if is_scaled else ""))
        print("  capt = kept/offered on trades that reached >=0.5R  |  "
              "gave = reached +1R then closed at a LOSS")
        print("  rockKeep/rock$ = kept/offered and $ on the TOP 5% of excursions (the rockets)")
    print(f"\n{'='*118}")
    print("ACROSS ALL FIVE SETS -- mean profit per trade in ATR UNITS (instruments\n  priced 1.09 to 5196 cannot be averaged in points), and how many sets were positive")
    print(f"{'='*118}")
    for name, v in sorted(agg.items(), key=lambda kv: -np.mean(kv[1])):
        v = np.array(v)
        print(f"  {name:<32}{v.mean():>8.3f} ATR   positive on {int((v>0).sum())}/{len(v)}"
              f"   worst {v.min():>7.3f}")
