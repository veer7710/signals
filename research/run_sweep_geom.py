import sys, numpy as np
sys.path.insert(0, "research")
import core, measure

def sweep_trades(d, max_live=3, pierce=0.05, buf_atr=0.20, trend_filter=None):
    """Sweep entries with their NATURAL stop: just beyond the swept wick.
    Returns list of (entry_idx, dir, stop_dist_price, atr)."""
    a = core.atr(d, 14)
    pools = core.build_pools(d, 3, 3, max_live=max_live)
    n = d["n"]; consumed = set(); out = []
    for i in range(n):
        if np.isnan(a[i]) or a[i] <= 0 or i + 1 >= n: continue
        pe = pierce * a[i]; hp, lp = pools[i]
        sig = 0; wick = np.nan
        for p in lp:
            k = ("L", round(p["level"], 4))
            if k in consumed: continue
            if d["l"][i] <= p["level"] - pe and d["c"][i] > p["level"]:
                sig, wick = 1, d["l"][i]; consumed.add(k); break
        if sig == 0:
            for p in hp:
                k = ("H", round(p["level"], 4))
                if k in consumed: continue
                if d["h"][i] >= p["level"] + pe and d["c"][i] < p["level"]:
                    sig, wick = -1, d["h"][i]; consumed.add(k); break
        if sig == 0: continue
        if trend_filter is not None and trend_filter[i] != sig: continue
        entry = d["o"][i + 1]
        stop_d = abs(entry - wick) + buf_atr * a[i]
        if stop_d <= 0: continue
        out.append((i + 1, sig, stop_d, a[i]))
    return out

def run(d, trades, rr, max_bars, cost, label):
    if not trades: return None
    w = dec = 0; mfes = []; pts = []
    for j, sd, stop_d, av in trades:
        r = measure.first_touch(d, j, sd, stop_d, rr * stop_d, max_bars, cost)
        if not r: continue
        mfes.append(r[2] / stop_d)
        if r[0] != "timeout":
            dec += 1; w += (r[0] == "win")
        pts.append((r[4] - d["o"][j]) * sd - cost)
    if not dec: return None
    return dict(label=label, n=len(trades), win=w / dec, decided=dec,
                mfe_R=float(np.mean(mfes)), pts=float(np.mean(pts)),
                stopR=float(np.mean([t[2] / t[3] for t in trades])))

def matched_null(d, trades, rr, max_bars, cost, reps=150, seed=1):
    """Same stop distances (in ATR), same count, random bars + directions."""
    rng = np.random.default_rng(seed)
    a = core.atr(d, 14)
    ok = np.nonzero(~np.isnan(a) & (a > 0))[0]; ok = ok[ok < d["n"] - max_bars - 2]
    stops_atr = np.array([t[2] / t[3] for t in trades])
    out = []
    for _ in range(reps):
        idx = rng.choice(ok, size=len(trades), replace=True)
        dirs = rng.choice([-1, 1], size=len(trades))
        sa = rng.choice(stops_atr, size=len(trades))
        w = dec = 0
        for i, sd, s_atr in zip(idx, dirs, sa):
            stop_d = s_atr * a[i]
            r = measure.first_touch(d, i + 1, int(sd), stop_d, rr * stop_d,
                                    max_bars, cost)
            if r and r[0] != "timeout":
                dec += 1; w += (r[0] == "win")
        if dec: out.append(w / dec)
    return np.array(out)

if __name__ == "__main__":
    for sym, tf, cost in [("GOLD", "15m", 0.15), ("GOLD", "1h", 0.15)]:
        d = core.load(sym, tf)
        st, _ = core.supertrend(d, 10, 3.0)
        er = core.efficiency_ratio(d["c"], 20)
        print(f"\n{'='*86}\n{sym} {tf} -- SWEEP with structural stop (beyond wick "
              f"+0.2ATR), cost ${cost}/side\n{'='*86}")
        variants = {
            "sweep REVERSAL (long on low swept)":  dict(inv=False, tf_=None),
            "sweep CONTINUATION (short on low)":   dict(inv=True,  tf_=None),
            "sweep REVERSAL + ST trend agrees":    dict(inv=False, tf_=st),
            "sweep REVERSAL + ST trend against":   dict(inv=False, tf_=-st),
        }
        for rr in (1.0, 2.0):
            print(f"\n  --- target = {rr}R, hold <= 60 bars ---")
            print(f"  {'variant':<38}{'n':>5}{'win%':>8}{'null%':>8}{'lift':>7}"
                  f"{'$/trade':>9}{'stopATR':>9}")
            for name, cfg in variants.items():
                base = sweep_trades(d, trend_filter=cfg["tf_"])
                tr = [(j, -s if cfg["inv"] else s, sd, av) for j, s, sd, av in base]
                r = run(d, tr, rr, 60, cost, name)
                if not r: continue
                nl = matched_null(d, tr, rr, 60, cost)
                lift = r["win"] / nl.mean() if nl.mean() else float("nan")
                print(f"  {name:<38}{r['n']:>5}{100*r['win']:>8.1f}"
                      f"{100*nl.mean():>8.1f}{lift:>7.2f}{r['pts']:>9.2f}"
                      f"{r['stopR']:>9.2f}")
