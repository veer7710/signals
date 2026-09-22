"""
TPO VALUE-AREA ROTATION -- the "80% rule".

Why this one and not another SMC object: a TPO profile is built from TIME, not
volume, so unlike absorption/delta/footprint it is genuinely computable from
OHLC. It has a structural rationale (auction theory: price rotates inside an
accepted range until it is rejected), it is a ROTATION strategy -- which is the
ping-pong behaviour asked for -- and it has never been tested on this project.

THE RULE, as normally stated: if price opens OUTSIDE the prior session's value
area, trades back INSIDE it, and is ACCEPTED (two consecutive periods closing
inside), then it has a high probability of traversing to the far side of that
value area.

No lookahead: the value area comes from the PRIOR session only.
"""
import sys, numpy as np, datetime as dt
sys.path.insert(0, "research")
import core, measure
from run_drift import detrend
from run_decisive import tstat, boot_ci

def sessions(d):
    days = np.array([int(t) // 86400 for t in d["t"]])
    out, cur, start = [], days[0], 0
    for i in range(1, d["n"]):
        if days[i] != cur:
            if i - start >= 6:
                out.append((start, i))
            cur, start = days[i], i
    return out

def value_area(d, lo_i, hi_i, bucket, frac=0.70):
    """Standard TPO value area: expand from the POC, taking the heavier pair of
    buckets each step, until `frac` of all TPO counts is enclosed."""
    counts = {}
    for i in range(lo_i, hi_i):
        b0 = int(np.floor(d["l"][i] / bucket))
        b1 = int(np.floor(d["h"][i] / bucket))
        for b in range(b0, b1 + 1):
            counts[b] = counts.get(b, 0) + 1
    if not counts:
        return None
    total = sum(counts.values())
    poc = max(counts, key=lambda k: counts[k])
    lo = hi = poc
    acc = counts[poc]
    keys = sorted(counts)
    while acc < frac * total:
        up1 = counts.get(hi + 1, 0) + counts.get(hi + 2, 0)
        dn1 = counts.get(lo - 1, 0) + counts.get(lo - 2, 0)
        if up1 == 0 and dn1 == 0:
            break
        if up1 >= dn1:
            acc += up1
            hi += 2
        else:
            acc += dn1
            lo -= 2
    return (lo * bucket, (hi + 1) * bucket, poc * bucket)

def signals(d, frac=0.70, accept=2):
    a = core.atr(d, 14)
    ss = sessions(d)
    out = []
    for k in range(1, len(ss)):
        p0, p1 = ss[k - 1]
        c0, c1 = ss[k]
        med = np.nanmedian(a[p0:p1])
        if not np.isfinite(med) or med <= 0:
            continue
        bucket = max(med / 4.0, 1e-6)
        va = value_area(d, p0, p1, bucket, frac)
        if va is None:
            continue
        val, vah, poc = va
        if vah <= val:
            continue
        outside = None          # which side we came from
        inside_run = 0
        for i in range(c0, c1):
            c = d["c"][i]
            if c > vah:
                outside, inside_run = 1, 0
            elif c < val:
                outside, inside_run = -1, 0
            else:
                if outside is not None:
                    inside_run += 1
                    if inside_run == accept:
                        # accepted back inside -> traverse toward the FAR side
                        dirn = -1 if outside == 1 else 1
                        tgt = val if dirn < 0 else vah
                        out.append((i, dirn, tgt, val, vah))
                        outside = None
                        inside_run = 0
    return out

def run(d, sig, cost=0.15, stop_atr=1.0, max_bars=48):
    a = core.atr(d, 14)
    wins = losses = 0
    pts = []
    for i, dirn, tgt, val, vah in sig:
        j = i + 1
        if j >= d["n"] - 2 or np.isnan(a[i]) or a[i] <= 0:
            continue
        e = d["o"][j] + dirn * cost
        room = (tgt - e) * dirn
        if room <= 0:
            continue
        stop = e - dirn * stop_atr * a[i]
        hit = None
        for k in range(j, min(j + max_bars, d["n"])):
            if (d["l"][k] <= stop) if dirn > 0 else (d["h"][k] >= stop):
                hit = -stop_atr * a[i] - cost
                break
            if (d["h"][k] >= tgt) if dirn > 0 else (d["l"][k] <= tgt):
                hit = room - cost
                break
        if hit is None:
            kk = min(j + max_bars, d["n"]) - 1
            hit = (d["c"][kk] - e) * dirn - cost
        pts.append(hit)
        if hit > 0: wins += 1
        else: losses += 1
    return np.array(pts), wins, losses

for sym, tf in [("GOLD", "1h"), ("GOLD", "15m")]:
    raw = core.load(sym, tf)
    d = detrend(raw)
    print(f"\n{'='*84}\n{sym} {tf} de-trended -- TPO VALUE-AREA ROTATION (80% rule)\n{'='*84}")
    print(f"  {'value area':<14}{'accept':>8}{'n':>6}{'win%':>8}{'$/trade':>10}{'t':>7}{'CI95':>18}")
    for frac in (0.70, 0.80):
        for acc in (1, 2):
            sig = signals(d, frac, acc)
            if len(sig) < 25:
                print(f"  {frac:<14.2f}{acc:>8}{len(sig):>6}   too few"); continue
            pts, w, l = run(d, sig)
            if len(pts) < 25: continue
            lo, hi = boot_ci(pts)
            print(f"  {frac:<14.2f}{acc:>8}{len(pts):>6}{100*w/max(w+l,1):>8.1f}"
                  f"{pts.mean():>10.2f}{tstat(pts):>7.2f}  [{lo:>6.2f},{hi:>6.2f}]")
    # the null this must beat: same count, same geometry, random bars
    sig = signals(d, 0.70, 2)
    if len(sig) >= 25:
        base = measure.random_baseline(d, len(sig), 1.0, 1.0, 48, reps=120)
        print(f"\n  random baseline at 1:1 geometry: {100*base.mean():.1f}% win")
        print(f"  NOTE: the traverse target is NOT 1:1 -- room varies per trade, so")
        print(f"  the honest comparison is the $/trade column and its CI, not win%.")
