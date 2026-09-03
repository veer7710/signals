"""
E-094 — SIDEWAYS DETECTION. Veer asked for this explicitly and it was never built.

His description, verbatim: distinguishing a real range - "just up down volume
candles" - from a trend, using only CLOSED bars.

E-053 already tried once and failed: "the regime is real, the filter is not, and
the actual problem is COST". So the bar this has to clear is not "does the
detector describe the market" - it plainly does - but the standing rule:

    A FILTER EARNS ITS PLACE ONLY IF THE TRADES IT REFUSES ARE WORSE THAN THE
    ONES IT ALLOWS.

Six candidate detectors, all computable from closed bars with no look-ahead,
all scale-free so they read the same at 0.5 points and at 40:

  rangepos   E-084's range position: where in the last N bars' range this bar
             closed. The known one. Middle = the market changing its mind.
  effratio   Kaufman efficiency: |net move| / summed absolute move over N bars.
             1.0 = a straight line, 0.0 = pure round trip.
  flipdens   SuperTrend flips in the last N bars. A range whipsaws the line.
  spacing    the Pine's own ClusterRangeNow: spread of the last k signal prices
             divided by the path travelled between them.
  contain    (highest high - lowest low) over N bars divided by the SUM of the
             individual bar ranges. Low = the bars overlap each other, which is
             what a range LOOKS like.
  alternate  the literal reading of "up down candles": the share of the last N
             bars whose direction differs from the bar before.

Each is measured against the SuperTrend EA's own trades, in POINTS (E-074), one
vote per trade (E-073), and split out of sample.

Run:  python3 JARVIS/research/sideways.py
"""
from __future__ import annotations
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import Series, atr as watr
from pine_ea_parity import ea_supertrend_at, ea_dema_at

ATRL, MULT, DEMAL, WARM, SPREAD = 7, 1.2, 200, 400, 0.46


# ------------------------------------------------------------- the detectors
def rangepos(s, i, n=20):
    hi = max(s.h[i - n + 1:i + 1]); lo = min(s.l[i - n + 1:i + 1])
    return (s.c[i] - lo) / (hi - lo) if hi > lo else 0.5


def effratio(s, i, n=20):
    path = sum(abs(s.c[j] - s.c[j - 1]) for j in range(i - n + 1, i + 1))
    return abs(s.c[i] - s.c[i - n]) / path if path > 0 else 0.0


def contain(s, i, n=20):
    hi = max(s.h[i - n + 1:i + 1]); lo = min(s.l[i - n + 1:i + 1])
    tot = sum(s.h[j] - s.l[j] for j in range(i - n + 1, i + 1))
    return (hi - lo) / tot if tot > 0 else 1.0


def alternate(s, i, n=20):
    d = [1 if s.c[j] > s.o[j] else -1 for j in range(i - n, i + 1)]
    return sum(1 for k in range(1, len(d)) if d[k] != d[k - 1]) / (len(d) - 1)


def flipdens(flips, i, n=20):
    return sum(flips[max(0, i - n + 1):i + 1]) / n


def spacing(sig_px, k=5):
    if len(sig_px) < k:
        return 1.0
    w = sig_px[-k:]
    path = sum(abs(w[j] - w[j - 1]) for j in range(1, len(w)))
    return (max(w) - min(w)) / path if path > 0 else 1.0


# ------------------------------------------------------------------ trades
def trades(s, stop_atr=2.0, trail=3.0, maxbars=50):
    A = watr(s, ATRL)
    n = len(s)
    start = max(WARM + 10, DEMAL * 4 + 20)
    flips = [0] * n
    out, sig_px, busy = [], [], -1
    for i in range(start, n - 1):
        d, dp = ea_supertrend_at(s, i, ATRL, MULT, WARM)
        up, dn = d == -1 and dp == 1, d == 1 and dp == -1
        if up or dn:
            flips[i] = 1
        if not (up or dn) or i <= busy:
            continue
        side = 1 if up else -1
        en, ep = ea_dema_at(s, i, DEMAL, 1), ea_dema_at(s, i, DEMAL, 3)
        if en is None or ep is None:
            continue
        if (side > 0 and en < ep) or (side < 0 and en > ep):
            continue
        a = A[i]
        if not a or a <= 0:
            continue
        sig_px.append(s.c[i])
        feats = {"rangepos": rangepos(s, i), "effratio": effratio(s, i),
                 "contain": contain(s, i), "alternate": alternate(s, i),
                 "flipdens": flipdens(flips, i), "spacing": spacing(sig_px)}
        entry = s.o[i + 1] + side * SPREAD / 2.0
        stop = entry - side * stop_atr * a
        peak, i_out, px = entry, None, None
        for j in range(i + 1, min(i + 1 + maxbars, n)):
            if (side > 0 and s.l[j] <= stop) or (side < 0 and s.h[j] >= stop):
                i_out, px = j, stop - side * SPREAD / 2.0
                break
            peak = max(peak, s.h[j]) if side > 0 else min(peak, s.l[j])
            t = peak - side * trail * a
            stop = max(stop, t) if side > 0 else min(stop, t)
        if i_out is None:
            i_out = min(i + maxbars, n - 1)
            px = s.c[i_out] - side * SPREAD / 2.0
        out.append({"i": i, "side": side, "pts": side * (px - entry), "f": feats})
        busy = i_out
    return out


# ------------------------------------------------------------------ report
def quintiles(tr, key):
    vals = sorted(t["f"][key] for t in tr)
    if not vals:
        return []
    cuts = [vals[int(len(vals) * q / 5)] for q in range(1, 5)]
    buckets = [[] for _ in range(5)]
    for t in tr:
        v = t["f"][key]
        b = sum(1 for c in cuts if v >= c)
        buckets[b].append(t["pts"])
    return buckets


def main():
    for sym, tf in (("GOLD", "15m"), ("GOLD", "1h")):
        s = engine.load(sym, tf)
        tr = trades(s)
        tot = sum(t["pts"] for t in tr)
        print(f"\n{'='*94}\n  {sym} {tf} — {len(tr)} EA trades, {tot:+.1f} points total\n{'='*94}")
        print(f"  {'detector':<11} " + "".join(f"{'Q'+str(q+1):>15}" for q in range(5)))
        print(f"  {'':<11} " + "".join(f"{'(n, points)':>15}" for _ in range(5)))
        print("  " + "-" * 88)
        for key in ("rangepos", "effratio", "contain", "alternate",
                    "flipdens", "spacing"):
            bs = quintiles(tr, key)
            cells = "".join(f"{str(len(b))+', '+format(sum(b),'+.0f'):>15}" for b in bs)
            print(f"  {key:<11} {cells}")

        # the only test that matters: refuse the worst bucket, is the rest better?
        print(f"\n  THE FILTER TEST — refuse the worst quintile of each detector.")
        print(f"  {'detector':<11} {'refused n':>10} {'refused pts':>12} "
              f"{'kept n':>8} {'kept pts':>10} {'kept/trade':>11} {'verdict':>10}")
        print("  " + "-" * 78)
        base = tot / len(tr)
        for key in ("rangepos", "effratio", "contain", "alternate",
                    "flipdens", "spacing"):
            bs = quintiles(tr, key)
            worst = min(range(5), key=lambda q: sum(bs[q]))
            ref = bs[worst]
            kept = [p for q in range(5) if q != worst for p in bs[q]]
            kt = sum(kept) / len(kept) if kept else 0.0
            ok = "PAYS" if (sum(ref) < 0 and kt > base) else "no"
            print(f"  {key:<11} {len(ref):>10} {sum(ref):>+12.1f} {len(kept):>8} "
                  f"{sum(kept):>+10.1f} {kt:>+11.3f} {ok:>10}")
        print(f"  (baseline, refusing nothing: {base:+.3f} points per trade)")


if __name__ == "__main__":
    main()


# ---------------------------------------------------- the honest test
# The quintile table above is CHERRY-PICKED and must not be believed. "Refuse the
# worst quintile" chooses the bucket by looking at its answer, so the refused
# bucket is negative by construction - that is what "worst" means. Five of six
# detectors "PAY" on 15m by that test and it means nothing.
#
# The tell that it is noise: the detectors do not agree with THEMSELVES across
# the two markets. rangepos's worst quintile is Q4 on 15m and Q3 on 1h.
# contain's is Q1 on 15m (which is POSITIVE, +30) and Q5 on 1h. A real regime
# effect does not move.
#
# So: pick the threshold on the FIRST half of history and apply it, unchanged,
# to the second half. Four folds, walked forward. Nothing is chosen on data it
# is then scored on.
def walk_forward(tr, key, folds=4, quintile_cut=0.20):
    n = len(tr)
    fold = n // (folds + 1)
    rows = []
    for f in range(folds):
        train = tr[:fold * (f + 1)]
        test = tr[fold * (f + 1):fold * (f + 2)]
        if len(train) < 30 or len(test) < 15:
            continue
        # on TRAIN only: which side of the distribution is the bad one, and where
        vals = sorted(t["f"][key] for t in train)
        lo_cut = vals[int(len(vals) * quintile_cut)]
        hi_cut = vals[int(len(vals) * (1 - quintile_cut))]
        lo = [t["pts"] for t in train if t["f"][key] <= lo_cut]
        hi = [t["pts"] for t in train if t["f"][key] >= hi_cut]
        if sum(lo) <= sum(hi):
            side, cut = "low", lo_cut
            ref = [t["pts"] for t in test if t["f"][key] <= cut]
            kept = [t["pts"] for t in test if t["f"][key] > cut]
        else:
            side, cut = "high", hi_cut
            ref = [t["pts"] for t in test if t["f"][key] >= cut]
            kept = [t["pts"] for t in test if t["f"][key] < cut]
        base = sum(t["pts"] for t in test) / len(test)
        kt = (sum(kept) / len(kept)) if kept else 0.0
        rows.append((side, len(ref), sum(ref), len(kept), kt, base, kt > base))
    return rows


def honest():
    for sym, tf in (("GOLD", "15m"), ("GOLD", "1h")):
        s = engine.load(sym, tf)
        tr = trades(s)
        print(f"\n{'='*96}")
        print(f"  {sym} {tf} — WALK-FORWARD. Threshold set on past trades only, scored on the next block.")
        print(f"{'='*96}")
        print(f"  {'detector':<11} {'folds better than doing nothing':>34} "
              f"{'refused pts (test)':>20} {'verdict':>12}")
        print("  " + "-" * 82)
        for key in ("rangepos", "effratio", "contain", "alternate",
                    "flipdens", "spacing"):
            rows = walk_forward(tr, key)
            if not rows:
                continue
            good = sum(1 for r in rows if r[6])
            refp = sum(r[2] for r in rows)
            v = ("SUPPORTED" if good == len(rows) and refp < 0
                 else "no" if good <= len(rows) / 2 else "weak")
            print(f"  {key:<11} {str(good)+' of '+str(len(rows)):>34} "
                  f"{refp:>+20.1f} {v:>12}")


if __name__ == "__main__":
    main()
    honest()
