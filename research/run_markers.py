import sys, numpy as np
sys.path.insert(0, "research")
import core, measure

def build_markers(d):
    st, _ = core.supertrend(d, 10, 3.0)
    flip = np.zeros(d["n"], dtype=np.int8)
    flip[1:] = np.where(st[1:] != st[:-1], st[1:], 0)
    disp = core.displacement(d, 1.5, 50)
    er = core.efficiency_ratio(d["c"], 20)

    pools = core.build_pools(d, 3, 3, max_live=3)
    sw, _, _ = core.sweeps(d, pools, 0.05)
    # deliberately broken variants, to test WHY the good one works
    pools40 = core.build_pools(d, 3, 3, max_live=40)
    sw40, _, _ = core.sweeps(d, pools40, 0.05)
    sw_nc = sweeps_no_consume(d, pools)

    m = {}
    m["ST flip (current EA entry)"] = flip
    m["ST flip, NOT on big candle"] = np.where(disp, 0, flip).astype(np.int8)
    m["ST flip, ON big candle"]     = np.where(disp, flip, 0).astype(np.int8)
    m["ST flip + ER>0.35 (trending)"] = np.where(er > 0.35, flip, 0).astype(np.int8)
    m["ST flip + ER<0.35 (chop)"]     = np.where(er <= 0.35, flip, 0).astype(np.int8)
    m["Sweep (consumed, nearest-3)"]  = sw
    m["Sweep, NOT consumed"]          = sw_nc
    m["Sweep, nearest-40 pools"]      = sw40
    m["FVG"]                          = core.fvg(d, 0.0)
    m["Displacement bar alone"]       = disp_dir(d, disp)
    return m

def sweeps_no_consume(d, pools, pierce_atr=0.05):
    a = core.atr(d, 14); n = d["n"]; sig = np.zeros(n, dtype=np.int8)
    for i in range(n):
        if np.isnan(a[i]) or a[i] <= 0: continue
        pe = pierce_atr * a[i]; hp, lp = pools[i]
        for p in lp:
            if d["l"][i] <= p["level"] - pe and d["c"][i] > p["level"]:
                sig[i] = 1; break
        if sig[i] == 0:
            for p in hp:
                if d["h"][i] >= p["level"] + pe and d["c"][i] < p["level"]:
                    sig[i] = -1; break
    return sig

def disp_dir(d, disp):
    s = np.zeros(d["n"], dtype=np.int8)
    s[disp] = np.where(d["c"][disp] > d["o"][disp], 1, -1)
    return s

def report(sym, tf, stop_atr, targ_atr, max_bars):
    d = core.load(sym, tf)
    m = build_markers(d)
    print(f"\n{'='*78}\n{sym} {tf} | {d['n']} bars | stop {stop_atr}ATR "
          f"target {targ_atr}ATR | hold<= {max_bars} bars\n{'='*78}")
    base = measure.random_baseline(d, 200, stop_atr, targ_atr, max_bars, reps=120)
    bmean = base.mean()
    bon = measure.best_of_n_line(base, len(m))
    print(f"random baseline winrate {bmean:.3f}  "
          f"(best-of-{len(m)} null line at 95%: {bon:.3f} -> lift {bon/bmean:.2f})")
    print(f"{'marker':<32}{'n':>5}{'/day':>7}{'win%':>8}{'lift':>7}{'MFE':>7}{'MAE':>7}")
    days = (d["t"][-1] - d["t"][0]) / 86400.0 * (5/7)
    rows = []
    for k, s in m.items():
        r = measure.score_marker(d, s, stop_atr, targ_atr, max_bars)
        if not r: continue
        lift = r["winrate"] / bmean
        rows.append((lift, k, r))
    for lift, k, r in sorted(rows, reverse=True):
        flag = "  <-- clears best-of-N" if lift > bon / bmean else ""
        print(f"{k:<32}{r['n']:>5}{r['n']/days:>7.1f}{100*r['winrate']:>8.1f}"
              f"{lift:>7.2f}{r['mfe']:>7.2f}{r['mae']:>7.2f}{flag}")

report("GOLD", "15m", 1.0, 1.0, 40)
report("GOLD", "1h",  1.0, 1.0, 40)
