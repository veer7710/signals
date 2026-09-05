"""
E-119 — LIQUIDITY ZONES FROM M15, EXECUTED ON M1. The architecture nobody built.

Veer, from the start: "liquidity entries are based on m15 5 and 1". D-010 records
it. It has never been tested, because until today there was no M1 data.

WHY THIS AND NOT M1 ZONES. The liquidity edge (E-076/E-077) is a limit resting
INSIDE a zone, filled by the sweep that takes the stops sitting there. That
depends on the zone being a level other traders can see. An M1 pivot is noise -
seven one-minute bars is not a level anyone is defending. An M15 pivot is.
So: find the zones on M15, rest the order, and let M1 do the execution, which is
what gives the precise fill and the small stop.

WHAT IS DIFFERENT FROM EVERY PREVIOUS TEST IN THIS REPO
  * real M1 bars from 18.8M bid/ask ticks, not 15m/1h
  * cost charged from EACH BAR'S OWN measured spread, not Costs.spread = 0.46
  * the E-110 fill-convention fix: a limit filled by a bar's ADVERSE extreme
    does not get to book that same bar's FAVOURABLE extreme
  * the control is matched on FILL CONVENTION - a limit control for a limit
    strategy. An open-entry control cannot falsify this and that error let six
    separate attacks pass in E-107.
"""
from __future__ import annotations
import os, sys, json, math, random, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import atr as watr

GBP = 0.787


def load(tf):
    rows = json.load(open(f"/home/user/signals/data/GOLD_{tf}_2018.json"))
    rows.sort(key=lambda r: r[0])
    s = engine.Series([r[0] for r in rows], [r[1] for r in rows],
                      [r[2] for r in rows], [r[3] for r in rows],
                      [r[4] for r in rows])
    return s, [r[5] for r in rows]


def pivots(s, k):
    """Confirmed swings: k bars either side, so a pivot is only KNOWN k bars
    after it forms. Returns (known_at_bar, price, kind)."""
    out = []
    for i in range(k, len(s)-k):
        if s.h[i] == max(s.h[i-k:i+k+1]): out.append((i+k, s.h[i], "high"))
        if s.l[i] == min(s.l[i-k:i+k+1]): out.append((i+k, s.l[i], "low"))
    return out


def build_zones(s15, k=5, life=200):
    """A zone is a confirmed M15 swing: the price level, the bar it became
    knowable, and the bar it expires. Sellside zones (lows) are where buy stops
    of longs sit; buyside zones (highs) are where sell stops sit."""
    z = []
    for (known, px, kind) in pivots(s15, k):
        z.append({"known_ts": s15.ts[known], "px": px,
                  "dead_ts": s15.ts[min(known+life, len(s15)-1)],
                  "dir": -1 if kind == "low" else 1})
    return z


def run(s1, SP1, A1, zones, past_atr, stop_atr, hold, give, tgt_r=0.0,
        maxwait=60, cost_scale=1.0):
    """
    dir = -1 (a swing LOW): the sweep takes it out downward, we BUY the wick.
          The limit rests `past_atr` BELOW the level - inside the zone, where
          E-077 found the edge, not at its edge.
    """
    idx = {t: i for i, t in enumerate(s1.ts)}
    out, busy = [], -1
    for z in zones:
        i0 = idx.get(z["known_ts"])
        if i0 is None:
            # M15 bar boundary may not exist in M1 if the hour was dropped
            continue
        if i0 <= busy:
            continue
        a = A1[i0]
        if not a or a <= 0:
            continue
        side = 1 if z["dir"] == -1 else -1
        lvl = z["px"] - side*past_atr*a          # a buy rests BELOW the low
        j = None
        for k in range(i0+1, min(i0+1+maxwait, len(s1))):
            if s1.ts[k] > z["dead_ts"]: break
            if (side == 1 and s1.l[k] <= lvl) or (side == -1 and s1.h[k] >= lvl):
                j = k; break
        if j is None:
            continue
        sp = SP1[j]*cost_scale
        entry = lvl + side*sp/2.0
        sl = entry - side*stop_atr*a
        tp = entry + side*tgt_r*stop_atr*a if tgt_r else None
        # E-110: the entry bar contributes favourable excursion only if it
        # OPENED beyond the limit, the one case where the fill is at the open.
        post = (s1.o[j] <= lvl) if side > 0 else (s1.o[j] >= lvl)
        peak = 0.0; armed = None; px = None
        for k in range(j, min(j+hold, len(s1))):
            if (side > 0 and s1.l[k] <= sl) or (side < 0 and s1.h[k] >= sl):
                px, kk = sl, k; break
            fav_ok = (k > j) or post
            if tp and fav_ok and ((side > 0 and s1.h[k] >= tp) or (side < 0 and s1.l[k] <= tp)):
                px, kk = tp, k; break
            if armed is not None:
                worst = s1.l[k] if side > 0 else s1.h[k]
                if side*(worst-armed) <= 0: px, kk = armed, k; break
            if give > 0 and fav_ok:
                fav = side*((s1.h[k] if side > 0 else s1.l[k]) - entry)
                if fav > peak:
                    peak = fav
                    if peak*(1-give) > SP1[k]*cost_scale:
                        armed = entry + side*peak*(1-give)
        if px is None:
            kk = min(j+hold, len(s1)-1); px = s1.c[kk]
        fill = px - side*SP1[kk]*cost_scale/2.0
        pts = side*(fill-entry)
        out.append({"pts": pts, "r": pts/(stop_atr*a), "in": j, "out": kk})
        busy = kk
    return out


def rep(name, tr, days):
    if len(tr) < 30:
        print(f"  {name:<32} {len(tr):>5}  too few"); return None
    n = len(tr); m = sum(t["r"] for t in tr)/n
    sd = (sum((t["r"]-m)**2 for t in tr)/(n-1))**0.5
    pts = sum(t["pts"] for t in tr)
    w = 100.0*sum(1 for t in tr if t["pts"] > 0)/n
    print(f"  {name:<32} {n:>5} {w:>6.1f}% {m:>+8.3f} {m/(sd/n**0.5):>6.2f} "
          f"{pts:>9.1f} {pts*GBP:>9.2f} {pts*GBP/days:>8.2f}")
    return m


def main():
    s1, SP1 = load("M1"); s15, _ = load("M15")
    A1 = watr(s1, 14)
    va = sorted(x for x in A1[100:] if x); med_a = va[len(va)//2]
    med_sp = statistics.median(SP1)
    days = len(s1)/1440
    # scale 2018's spread/ATR of 0.93 down to today's ECN 0.11
    cs = 0.11/(med_sp/med_a)
    print("="*104)
    print(f"  E-119 — M15 liquidity zones, M1 execution. {len(s1):,} M1 bars, "
          f"{len(s15):,} M15 bars")
    print(f"  cost scaled to today's ECN regime (spread/ATR 0.11); £ per 0.01 lot")
    print("="*104)
    print(f"  {'configuration':<32} {'n':>5} {'win%':>7} {'mean R':>8} {'t':>6} "
          f"{'points':>9} {'£ total':>9} {'£/day':>8}")
    print("  "+"-"*96)
    best = None
    for pk in (3, 5, 10):
        zones = build_zones(s15, k=pk)
        for past in (0.0, 0.5, 1.0):
            tr = run(s1, SP1, A1, zones, past, 2.0, 60, 0.25, cost_scale=cs)
            m = rep(f"pivot {pk}, limit {past:.1f}A past", tr, days)
            if m is not None and (best is None or m > best[0]):
                best = (m, pk, past, tr)
    if best is None:
        print("\n  nothing produced enough trades"); return
    _, pk, past, tr = best
    print(f"\n  BEST: M15 pivot {pk}, limit {past:.1f} ATR past the level")

    # exits, on the best zone set
    zones = build_zones(s15, k=pk)
    print(f"\n  EXIT COMPARISON on that zone set")
    print(f"  {'exit':<32} {'n':>5} {'win%':>7} {'mean R':>8} {'t':>6} "
          f"{'points':>9} {'£ total':>9} {'£/day':>8}")
    print("  "+"-"*96)
    for lab, kw in (("fixed 2R target", dict(give=0.0, tgt_r=2.0)),
                    ("no target, no trail", dict(give=0.0)),
                    ("25% giveback trail", dict(give=0.25)),
                    ("40% giveback trail", dict(give=0.40))):
        rep(lab, run(s1, SP1, A1, zones, past, 2.0, 60, cost_scale=cs, **kw), days)

    # THE CONTROL: a limit the same distance from price, random bar and side
    print(f"\n  CONTROL matched on FILL CONVENTION (random limit, same geometry)")
    real = run(s1, SP1, A1, zones, past, 2.0, 60, 0.25, cost_scale=cs)
    mr = sum(t["r"] for t in real)/len(real)
    means = []
    for sd_ in range(14):
        rng = random.Random(4000+sd_)
        zs = []
        for _ in range(len(zones)):
            b = rng.randrange(300, len(s15)-10)
            zs.append({"known_ts": s15.ts[b],
                       "px": s15.c[b],
                       "dead_ts": s15.ts[min(b+200, len(s15)-1)],
                       "dir": rng.choice((-1, 1))})
        zs.sort(key=lambda z: z["known_ts"])
        r = run(s1, SP1, A1, zs, past, 2.0, 60, 0.25, cost_scale=cs)
        if len(r) > 30: means.append(sum(t["r"] for t in r)/len(r))
    cm = sum(means)/len(means)
    cse = (sum((x-cm)**2 for x in means)/(len(means)-1))**0.5/len(means)**0.5
    print(f"  real zones   {mr:+.4f}R      control ({len(means)} seeds) {cm:+.4f}R "
          f" se {cse:.4f}")
    print(f"  EDGE OF THE ZONES: {mr-cm:+.4f}R = {(mr-cm)/cse:.1f} control se")


if __name__ == "__main__":
    main()
