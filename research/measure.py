"""
measure.py -- does a marker actually mark the start of a leg?

The only question that matters for an ENTRY: if I enter here with a stop S
and a target T, how often does T get hit FIRST? Compare that to entering at a
random bar with the same S and T. The ratio is the lift.

  lift > 1  the marker beats a coin flip at this geometry
  lift ~ 1  the marker is decoration
  lift < 1  the marker is worse than random -- you are entering late

Anything selected as "best of N" is compared against a best-of-N null,
because the maximum of N noisy estimates is biased upward. Skipping this is
how a repo ends up retracting its own findings.
"""
import numpy as np
import core

def first_touch(d, i0, dirn, stop_d, targ_d, max_bars, cost=0.0):
    """Enter at OPEN of bar i0 (R1). Walk forward bar by bar.
    R2: gap-through fills at the bar open, never better than the level.
    R3: if one bar spans both stop and target, the STOP wins.
    Returns (outcome, bars_held, mfe_points, mae_points, exit_price)."""
    n = d["n"]
    if i0 >= n: return None
    e = d["o"][i0] + dirn * cost          # pay the spread on entry
    stop = e - dirn * stop_d
    targ = e + dirn * targ_d
    mfe = mae = 0.0
    for k in range(i0, min(i0 + max_bars, n)):
        hi, lo = d["h"][k], d["l"][k]
        up = (hi - e) * dirn
        dnv = (e - lo) * dirn
        if dirn < 0: up, dnv = (e - lo) * 1.0, (hi - e) * 1.0
        mfe = max(mfe, up); mae = max(mae, dnv)
        hit_s = lo <= stop if dirn > 0 else hi >= stop
        hit_t = hi >= targ if dirn > 0 else lo <= targ
        if hit_s:                                   # R3 stop wins ties
            px = d["o"][k] if (d["o"][k] - stop) * dirn < 0 else stop
            return ("loss", k - i0 + 1, mfe, mae, px)
        if hit_t:
            px = d["o"][k] if (d["o"][k] - targ) * dirn > 0 else targ
            return ("win", k - i0 + 1, mfe, mae, px)
    k = min(i0 + max_bars, n) - 1
    return ("timeout", k - i0 + 1, mfe, mae, d["c"][k])


def score_marker(d, sig, stop_atr, targ_atr, max_bars, cost=0.0, delay=1):
    """sig[i] in {0,+1,-1} known at CLOSE of i -> entry at OPEN of i+delay."""
    a = core.atr(d, 14)
    rows = []
    for i in np.nonzero(sig)[0]:
        j = i + delay
        if j >= d["n"] or np.isnan(a[i]) or a[i] <= 0: continue
        r = first_touch(d, j, int(sig[i]), stop_atr * a[i], targ_atr * a[i],
                        max_bars, cost)
        if r: rows.append((r[0], r[1], r[2] / a[i], r[3] / a[i], a[i]))
    if not rows: return None
    wins = sum(1 for r in rows if r[0] == "win")
    dec  = sum(1 for r in rows if r[0] != "timeout")
    return dict(n=len(rows), decided=dec,
                winrate=wins / dec if dec else float("nan"),
                mfe=float(np.mean([r[2] for r in rows])),
                mae=float(np.mean([r[3] for r in rows])),
                bars=float(np.mean([r[1] for r in rows])))


def random_baseline(d, n_sig, stop_atr, targ_atr, max_bars, cost=0.0,
                    reps=200, seed=0):
    """Same geometry, same number of trades, random bars and random
    directions. This is what 'no skill' actually pays at this geometry --
    NOT 50%, because stop and target distances differ."""
    rng = np.random.default_rng(seed)
    a = core.atr(d, 14)
    ok = np.nonzero(~np.isnan(a) & (a > 0))[0]
    ok = ok[ok < d["n"] - max_bars - 2]
    out = []
    for _ in range(reps):
        idx = rng.choice(ok, size=min(n_sig, len(ok)), replace=False)
        dirs = rng.choice([-1, 1], size=len(idx))
        w = dd = 0
        for i, sd in zip(idx, dirs):
            r = first_touch(d, i + 1, int(sd), stop_atr * a[i],
                            targ_atr * a[i], max_bars, cost)
            if not r: continue
            if r[0] != "timeout":
                dd += 1
                if r[0] == "win": w += 1
        if dd: out.append(w / dd)
    return np.array(out)


def best_of_n_line(baseline, n_tested, pct=95):
    """If you test n_tested markers on noise, the BEST one lands here.
    A marker must clear this line, not the plain mean, to mean anything."""
    if len(baseline) == 0: return float("nan")
    sims = [np.max(np.random.default_rng(s).choice(baseline, n_tested))
            for s in range(400)]
    return float(np.percentile(sims, pct))
