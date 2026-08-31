"""
DOES A CONFLUENCE SCORE ACTUALLY SEPARATE WINNERS FROM LOSERS?

Veer, after a live day: "ive made profit of 8 pound which is nothing because
idk what setups to take ... ive spotted toooo many opportunities".

That is not a signal-generation problem. He has more setups than he can take
and no way to rank them. The fix is a score - but a score is worthless unless
higher scores actually produce higher expectancy, and that is measurable.

So: build the score out of factors that were ALREADY measured in this repo,
then bucket every historical signal by its score and compare expectancy across
buckets. If the buckets do not separate, the score is decoration and saying so
is the finding.

THE COMPONENTS, and where each comes from:
  ADX at entry      E-0xx: ADX<20 measured +0.304R, ADX>=35 measured -0.132R,
                    and that split held out-of-sample. Strongest single factor.
  ATR vs its median volatility CONTRACTION precedes expansion: ATR<=median
                    preceded a 3+ ATR move ~90% of the time, ATR>=2x median 25%.
  Trend agreement   the DEMA slope filter already in the strategy.
  Room to run       distance to the recent swing the trade is aiming at, in R.
  Session           04-12 UTC measured best on gold; included but weighted low
                    because it was measured on one instrument.

Nothing here is invented weighting: each component is a factor with a measured
direction, and the score is their unweighted sum so no fitting happens.

Run:  python3 JARVIS/research/setup_score.py
"""
from __future__ import annotations
import os, sys, math, statistics as st
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, strategies as S
from engine import Series


def costs_for(sym):
    return study.COSTS.get(sym, engine.Costs())


def score_signal(s, ctx, i, side, A, AM, ADX, D):
    """0-7. Every component is knowable at bar i's close."""
    pts, why = 0, []
    a = A[i]

    adx = ADX[i]
    if adx is not None:
        if adx < 20:
            pts += 2; why.append("ADX<20")
        elif adx < 35:
            pts += 1; why.append("ADX<35")

    if AM[i] and AM[i] > 0 and a:
        rel = a / AM[i]
        if rel <= 1.0:
            pts += 2; why.append("quiet")
        elif rel <= 1.3:
            pts += 1; why.append("normal")

    if D[i] is not None and D[i - 2] is not None:
        if (side > 0 and D[i] > D[i - 2]) or (side < 0 and D[i] < D[i - 2]):
            pts += 1; why.append("trend")

    # room: how far to the last opposing swing extreme, in units of risk
    look = 50
    if i > look and a:
        tgt = max(s.h[i - look:i]) if side > 0 else min(s.l[i - look:i])
        room = abs(tgt - s.c[i]) / (1.5 * a)
        if room >= 2.0:
            pts += 1; why.append("room")

    hr = datetime.fromtimestamp(s.ts[i], timezone.utc).hour
    if 4 <= hr < 12 or 13 <= hr < 20:
        pts += 1; why.append("session")

    return pts, why


def collect(s, sym, stop_atr=1.5, rr=3.0, horizon=50):
    A = engine.atr(s, 14)
    AM = engine.rolling_median(A, 50)
    ADX, _, _ = engine.adx_di(s, 14)
    D = S.dema(s.c, 200)
    d, _, _ = S.supertrend_dir(s, 7, 1.2)
    c = costs_for(sym)
    cost = c.spread + 2 * c.slippage

    rows = []
    for i in range(300, len(s) - 2):
        if d[i] == 0 or d[i - 1] == 0:
            continue
        up = d[i] == -1 and d[i - 1] == 1
        dn = d[i] == 1 and d[i - 1] == -1
        if not (up or dn):
            continue
        a = A[i]
        if a is None or a <= 0:
            continue
        side = 1 if up else -1
        sc, why = score_signal(s, None, i, side, A, AM, ADX, D)

        en = s.o[i + 1]
        risk = stop_atr * a
        stop = en - side * risk
        tgt = en + side * rr * risk
        r = 0.0
        for j in range(i + 1, min(i + 1 + horizon, len(s))):
            hs_ = (s.l[j] <= stop) if side == 1 else (s.h[j] >= stop)
            ht_ = (s.h[j] >= tgt) if side == 1 else (s.l[j] <= tgt)
            if hs_:                      # ties lose
                r = -1.0 - cost / risk
                break
            if ht_:
                r = rr - cost / risk
                break
        else:
            k = min(i + 1 + horizon, len(s)) - 1
            r = ((s.c[k] - en) * side) / risk
        rows.append((i, sc, r))
    return rows


def summarise(rows, label):
    if not rows:
        print(f"  {label}: no signals"); return
    buckets = {}
    for _, sc, r in rows:
        buckets.setdefault(sc, []).append(r)
    print(f"\n  {label}   {len(rows)} signals")
    print(f"     {'score':>6}{'n':>7}{'win%':>8}{'exp R':>9}{'t':>7}")
    for sc in sorted(buckets):
        rs = buckets[sc]
        n = len(rs)
        m = sum(rs) / n
        sd = math.sqrt(sum((x - m) ** 2 for x in rs) / n) if n > 1 else 0.0
        t = m / (sd / math.sqrt(n)) if n > 1 and sd else 0.0
        w = 100.0 * sum(1 for x in rs if x > 0) / n
        print(f"     {sc:>6}{n:>7}{w:>7.1f}%{m:>+9.3f}{t:>+7.2f}")
    # the question that matters: do HIGH scores beat LOW scores?
    lo = [r for _, sc, r in rows if sc <= 3]
    hi = [r for _, sc, r in rows if sc >= 5]
    if len(lo) >= 20 and len(hi) >= 20:
        ml, mh = sum(lo) / len(lo), sum(hi) / len(hi)
        sl = math.sqrt(sum((x - ml) ** 2 for x in lo) / len(lo))
        sh = math.sqrt(sum((x - mh) ** 2 for x in hi) / len(hi))
        se = math.sqrt(sl * sl / len(lo) + sh * sh / len(hi))
        t = (mh - ml) / se if se else 0.0
        print(f"     LOW (<=3) {ml:+.3f} on {len(lo)}   vs   "
              f"HIGH (>=5) {mh:+.3f} on {len(hi)}   gap t {t:+.2f}")
        return mh - ml, t
    return None, None


def split(s, frac=0.70):
    k = int(len(s) * frac)
    return (Series(s.ts[:k], s.o[:k], s.h[:k], s.l[:k], s.c[:k]),
            Series(s.ts[k:], s.o[k:], s.h[k:], s.l[k:], s.c[k:]))


if __name__ == "__main__":
    print(__doc__)
    gaps = []
    for sym in ("GOLD", "US500", "EURUSD", "GBPUSD"):
        for tf in ("15m", "1h"):
            try:
                s = engine.load(sym, tf)
            except FileNotFoundError:
                continue
            ins, oos = split(s)
            print(f"\n{'='*70}\n  {sym} {tf}\n{'='*70}")
            summarise(collect(ins, sym), "IN SAMPLE")
            g, t = summarise(collect(oos, sym), "OUT OF SAMPLE")
            if g is not None:
                gaps.append((f"{sym} {tf}", g, t))
    print(f"\n{'='*70}\n  DOES THE SCORE SEPARATE? (out-of-sample only)\n{'='*70}")
    pos = 0
    for name, g, t in gaps:
        mark = "yes" if g > 0 else "NO"
        pos += 1 if g > 0 else 0
        print(f"     {name:<14} high-minus-low {g:+.3f}R   t {t:+.2f}   {mark}")
    if gaps:
        print(f"\n     separated in {pos} of {len(gaps)} markets")
        print("     A score that does not separate is decoration. Read the t")
        print("     values against this repo's ~3.65 luck threshold.")


# ============================================================================
#  WHICH COMPONENT ACTUALLY CARRIES THE SIGNAL?
# ============================================================================
# The unweighted sum separated in only 5 of 8 markets and ran BACKWARDS on gold
# 15m, so it is not usable as a grade. That does not mean every component is
# worthless - it means adding them together buried whichever one works.
#
# So each factor is tested on its own: expectancy when the condition is TRUE
# minus expectancy when it is FALSE, out-of-sample, across all 8 markets. A
# factor that helps in 7 of 8 is worth a filter. One that helps in 4 of 8 is a
# coin flip and belongs nowhere near a live chart.

def components(s, sym, stop_atr=1.5, rr=3.0, horizon=50):
    A = engine.atr(s, 14)
    AM = engine.rolling_median(A, 50)
    ADX, _, _ = engine.adx_di(s, 14)
    D = S.dema(s.c, 200)
    d, _, _ = S.supertrend_dir(s, 7, 1.2)
    c = costs_for(sym)
    cost = c.spread + 2 * c.slippage
    out = []
    for i in range(300, len(s) - 2):
        if d[i] == 0 or d[i - 1] == 0:
            continue
        up = d[i] == -1 and d[i - 1] == 1
        dn = d[i] == 1 and d[i - 1] == -1
        if not (up or dn):
            continue
        a = A[i]
        if a is None or a <= 0:
            continue
        side = 1 if up else -1
        f = {}
        f["ADX < 20"] = ADX[i] is not None and ADX[i] < 20
        f["ADX < 35"] = ADX[i] is not None and ADX[i] < 35
        f["ATR <= median"] = bool(AM[i]) and a <= AM[i]
        f["ATR <= 1.3x med"] = bool(AM[i]) and a <= 1.3 * AM[i]
        f["DEMA agrees"] = (D[i] is not None and D[i - 2] is not None
                            and ((side > 0 and D[i] > D[i - 2])
                                 or (side < 0 and D[i] < D[i - 2])))
        look = 50
        if i > look:
            tgt = max(s.h[i - look:i]) if side > 0 else min(s.l[i - look:i])
            f["room >= 2R"] = abs(tgt - s.c[i]) / (1.5 * a) >= 2.0
        else:
            f["room >= 2R"] = False
        hr = datetime.fromtimestamp(s.ts[i], timezone.utc).hour
        f["session 4-12/13-20"] = (4 <= hr < 12) or (13 <= hr < 20)
        f["long"] = side > 0

        en = s.o[i + 1]
        risk = stop_atr * a
        stop = en - side * risk
        tp = en + side * rr * risk
        r = 0.0
        for j in range(i + 1, min(i + 1 + horizon, len(s))):
            hs_ = (s.l[j] <= stop) if side == 1 else (s.h[j] >= stop)
            ht_ = (s.h[j] >= tp) if side == 1 else (s.l[j] <= tp)
            if hs_:
                r = -1.0 - cost / risk
                break
            if ht_:
                r = rr - cost / risk
                break
        else:
            k = min(i + 1 + horizon, len(s)) - 1
            r = ((s.c[k] - en) * side) / risk
        out.append((f, r))
    return out


def component_report():
    names = ["ADX < 20", "ADX < 35", "ATR <= median", "ATR <= 1.3x med",
             "DEMA agrees", "room >= 2R", "session 4-12/13-20", "long"]
    tally = {n: [] for n in names}
    for sym in ("GOLD", "US500", "EURUSD", "GBPUSD"):
        for tf in ("15m", "1h"):
            try:
                s = engine.load(sym, tf)
            except FileNotFoundError:
                continue
            _, oos = split(s)
            rows = components(oos, sym)
            for n in names:
                on = [r for f, r in rows if f[n]]
                off = [r for f, r in rows if not f[n]]
                if len(on) < 20 or len(off) < 20:
                    continue
                tally[n].append(sum(on) / len(on) - sum(off) / len(off))
    print(f"\n{'='*74}\n  EACH FACTOR ON ITS OWN, out-of-sample, all markets"
          f"\n  (expectancy WITH the condition minus expectancy WITHOUT)\n{'='*74}")
    print(f"     {'factor':<22}{'markets':>9}{'helped':>8}{'median gap':>13}")
    for n in names:
        g = tally[n]
        if not g:
            print(f"     {n:<22}{'-':>9}{'-':>8}{'too few':>13}")
            continue
        helped = sum(1 for x in g if x > 0)
        print(f"     {n:<22}{len(g):>9}{helped:>5}/{len(g)}{st.median(g):>+13.3f}")
    print("\n     A factor that helps in 4 of 8 is a coin flip. Only something")
    print("     close to 7 or 8 of 8 is worth putting in front of real money.")


if "--components" in sys.argv:
    component_report()
