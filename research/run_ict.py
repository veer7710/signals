"""
run_ict.py -- test the ICT/SMC sweep models the way they are actually stated,
with the stop and target THEY specify, and report the one number every claim
in this space is missing: the RESIDUAL over geometry.

For a driftless series, P(target before stop) ~ S/(S+T). So a model with a
tight target and a wide stop is a high win rate before it has any edge at all.
Every row below therefore prints:

    win%    what actually happened
    geo%    S/(S+T) from that row's OWN average stop and target
    resid   win% - geo%    <-- THIS is the edge, and it is the only column
                               that cannot be manufactured by moving the target

A model with a 78% win rate and a 78% geometric expectation has found nothing.
A model with a 55% win rate and a 40% geometric expectation has found something.

Stops and targets are ICT's, not mine:
    stop   = beyond the sweep extreme, plus a buffer
    target = the OPPOSITE liquidity pool -- which is what "leg to leg" means
"""
import sys, numpy as np
sys.path.insert(0, "research")
import core, sessions as S, ict
from run_decisive import tstat

COST = 0.15

def run_model(d, f, sig, level_hi, level_lo, *, buf_atr=0.25, max_bars=60,
              cost=COST, min_rr=0.0, tgt_mode="pool", fixed_rr=2.0):
    """Entry next open (R1). Stop beyond the sweep leg. Target the opposite
    pool. Stop wins ties (R3). Gaps fill at the open (R2)."""
    a = core.atr(d, 14); n = d["n"]; out = []
    for i, sd in sig:
        j = i + 1
        if j >= n - 1 or np.isnan(a[i]) or a[i] <= 0: continue
        e = d["o"][j] + sd * cost
        # the stop lives beyond the extreme of the swing that did the sweeping
        w = slice(max(0, i - 6), i + 1)
        ext = d["l"][w].min() if sd > 0 else d["h"][w].max()
        stop = ext - sd * buf_atr * a[i]
        stop_d = (e - stop) * sd
        if stop_d <= 0: continue
        if tgt_mode == "pool":
            lv = level_hi[i] if sd > 0 else level_lo[i]
            if np.isnan(lv): continue
            targ = lv
        else:
            targ = e + sd * fixed_rr * stop_d
        targ_d = (targ - e) * sd
        if targ_d <= 0: continue
        if min_rr > 0 and targ_d / stop_d < min_rr: continue
        px = None; resolved = False
        for k in range(j, min(j + max_bars, n)):
            if (d["l"][k] <= stop) if sd > 0 else (d["h"][k] >= stop):
                px = d["o"][k] if (d["o"][k] - stop) * sd < 0 else stop
                resolved = True; break
            if (d["h"][k] >= targ) if sd > 0 else (d["l"][k] <= targ):
                px = d["o"][k] if (d["o"][k] - targ) * sd > 0 else targ
                resolved = True; break
        else:
            k = min(j + max_bars, n) - 1; px = d["c"][k]
        out.append(dict(pts=(px - e) * sd - cost, S=stop_d, T=targ_d, res=resolved,
                        R=((px - e) * sd - cost) / stop_d, bars=k - j + 1))
    return out

def summarise(name, t):
    if len(t) < 10: return None
    p = np.array([x["pts"] for x in t])
    Sd = np.array([x["S"] for x in t]); Td = np.array([x["T"] for x in t])
    rs = np.array([x["res"] for x in t], bool)
    # S/(S+T) is P(target before stop) for a RACE THAT FINISHES. A trade that
    # timed out never ran that race, so including it compares two different
    # experiments. The residual is therefore computed on RESOLVED trades only,
    # and res% is printed so a row that barely resolves cannot hide.
    if rs.sum() >= 5:
        win_r = float((p[rs] > 0).mean())
        geo_r = float(np.mean(Sd[rs] / (Sd[rs] + Td[rs])))
    else:
        win_r = geo_r = float("nan")
    return dict(name=name, n=len(t), res=float(rs.mean()),
                win=float((p > 0).mean()), win_r=win_r, geo=geo_r,
                resid=win_r - geo_r, pts=float(p.mean()), t=tstat(p),
                rr=float(np.mean(Td / Sd)),
                bars=float(np.mean([x["bars"] for x in t])))

def shuffled_null(d, f, sig, level_hi, level_lo, reps=40, seed=0, **kw):
    """The same NUMBER of trades, the same directions, on RANDOM bars inside
    the same time windows. If the model cannot beat this, the structure did
    no work -- only the clock and the geometry did."""
    rng = np.random.default_rng(seed)
    bars = np.array([i for i, _ in sig]); dirs = np.array([s for _, s in sig])
    pool = np.arange(20, d["n"] - 70)
    res = []
    for _ in range(reps):
        fake = list(zip(rng.choice(pool, size=len(bars), replace=False), dirs))
        t = run_model(d, f, sorted(fake), level_hi, level_lo, **kw)
        s = summarise("null", t)
        if s: res.append((s["win"], s["pts"], s["resid"]))
    if not res: return None
    r = np.array(res)
    return dict(win=r[:,0].mean(), pts=r[:,1].mean(), resid=r[:,2].mean(),
                win_p95=np.quantile(r[:,0], 0.95), pts_p95=np.quantile(r[:,1], 0.95))

HDR = (f"  {'model':<44}{'n':>5}{'res%':>6}{'win%':>7}{'geo%':>7}{'resid':>8}"
       f"{'$/trd':>8}{'t':>6}{'avgRR':>7}{'bars':>6}")

def line(s):
    flag = ""
    if np.isnan(s["resid"]): return f"  {s['name']:<44}{s['n']:>5}  too few resolved"
    if s["resid"] > 0.05 and s["t"] > 1.5: flag = "  <-- real edge?"
    elif s["resid"] < -0.02: flag = "  (worse than geometry)"
    return (f"  {s['name']:<44}{s['n']:>5}{100*s['res']:>6.0f}{100*s['win_r']:>7.1f}"
            f"{100*s['geo']:>7.1f}{100*s['resid']:>+8.1f}{s['pts']:>8.2f}"
            f"{s['t']:>6.2f}{s['rr']:>7.2f}{s['bars']:>6.1f}{flag}")

if __name__ == "__main__":
    for sym, tf in (("GOLD","1h"), ("GOLD","15m")):
        d = core.load(sym, tf); f = S.ny_fields(d)
        PDH, PDL = S.prior_day_levels(d, f)
        PWH, PWL = S.prior_week_levels(d, f)
        AH, AL   = S.session_levels(d, f, "asia_range")
        LH, LL   = S.session_levels(d, f, "london_kz")
        EQH, EQL = ict.equal_levels(d)
        POOLS = {"PDH/PDL": (PDH, PDL), "Asian range": (AH, AL),
                 "London range": (LH, LL), "EQH/EQL": (EQH, EQL),
                 "PWH/PWL": (PWH, PWL)}
        WINDOWS = [None, "london_kz", "ny_am_kz", "sb_london", "sb_am", "sb_pm", "ny_pm_kz"]
        print(f"\n{'='*118}")
        print(f"{sym} {tf}  --  sweep -> structure shift -> enter, stop beyond the "
              f"sweep, target the OPPOSITE pool")
        print(f"{'='*118}")
        print(HDR)
        rows = []
        for pn, (hi, lo) in POOLS.items():
            for w in WINDOWS:
                sig = ict.sweep_mss_entries(d, f, hi, lo, window=w)
                if len(sig) < 10: continue
                t = run_model(d, f, sig, hi, lo)
                s = summarise(f"{pn} sweep+MSS, {w or 'any hour'}", t)
                if s: rows.append((s, sig, hi, lo))
        rows_s = sorted(rows, key=lambda x: (-x[0]["resid"] if not np.isnan(x[0]["resid"]) else 9))
        for s, _, _, _ in rows_s:
            print(line(s))
        print("\n  res%  = share of trades that actually hit target or stop. The rest")
        print("          timed out, never ran the race, and are EXCLUDED from win%/geo%.")
        print("  resid = win% - S/(S+T)%. The only column a strategy cannot manufacture")
        print("          by moving its target closer. Big win% with resid ~ 0 is geometry.")

        # the decisive test, on whatever led: same count, same directions,
        # RANDOM bars. If the structure did no work, this matches it.
        print(f"\n  --- shuffled-bar null on the leading rows ({sym} {tf}) ---")
        for s, sig, hi, lo in rows_s[:4]:
            if s["n"] < 15 or np.isnan(s["resid"]): continue
            nl = shuffled_null(d, f, sig, hi, lo, reps=40)
            if not nl: continue
            beat = "BEATS" if s["pts"] > nl["pts_p95"] else "does NOT beat"
            print(f"    {s['name']:<44} real {s['pts']:>7.2f}/trd  "
                  f"null mean {nl['pts']:>7.2f}  null p95 {nl['pts_p95']:>7.2f}"
                  f"   -> {beat} the 95th pct of random")
