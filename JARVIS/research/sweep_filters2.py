"""
E-159 — WHAT SEPARATES A GOOD SWEEP FROM A BAD ONE, ASKED WITH THE SHIPPED EXIT.

E-135 asked this against a FIXED TARGET. What ships is a give-back trail, and
until E-151 that trail was filling at prices no order could rest at. So the
question has never actually been asked of the strategy that runs.

Veer wants "proper good entry exit" and takes a handful of trades a day where
this takes 24. If any feature knowable AT ENTRY separates his handful from the
rest, that is the single biggest available improvement - it costs nothing to
refuse a trade.

FEATURES, none of which uses a bar later than the entry bar:
  stop width      risk / ATR - how far the sweep ran past the level
  sweep depth     the same distance minus the buffer: the raw overshoot
  atr regime      ATR at entry over its own 500-bar median
  range position  where entry sits in the last 200 bars, 0 = low, 1 = high
  level age       bars the pivot stood before it was taken
  room            distance to the next opposing pivot, in ATR
  hour            hour of the day at entry
  direction       long or short

PROTOCOL. Quartiles are formed on the FIRST HALF only. A feature earns a filter
only if (a) the ladder is monotone across all four quartiles, (b) the filter
then wins on the SECOND half, which it has never seen, and (c) the trades it
REFUSES are genuinely worse than the ones it keeps - the CLAUDE.md rule, and the
one that kills most of these. Minimum 100 trades in the unseen half.
"""
from __future__ import annotations
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, trail_level
from liq_m1 import load
from sweep_winrate import pivots
import combined as C

BUF = 0.30
_M = {}


def build(tf, give=0.25, cooldown=5, hold=240):
    """Every shipped sweep trade, with the features that were true at entry."""
    if tf in _M:
        return _M[tf]
    s, SP = load(tf)
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    cs = 0.11 / (statistics.median(SP) / va[len(va) // 2])
    piv = sorted(pivots(s, 5), key=lambda x: x[0])
    cand = [c for c in C.candidates(s, A, cs, SP, {C.SWEEP}) if c[1] == C.SWEEP]

    # running ATR median, so "regime" is scale-free and uses no future bar
    out, busy = [], -1
    pi = 0
    seen = []          # pivots confirmed so far, in order
    for (j, _, d, entry, sl0) in cand:
        while pi < len(piv) and piv[pi][0] < j:
            seen.append(piv[pi]); pi += 1
        if j <= busy:
            continue
        a = A[j] if A[j] else 0.0
        if a <= 0:
            continue
        risk = abs(entry - sl0)

        sl, peak, px_out, kk = sl0, entry, None, None
        for k in range(j, min(j + hold, len(s))):
            if (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k; break
            if k == j:
                continue
            peak = max(peak, s.h[k]) if d > 0 else min(peak, s.l[k])
            nsl = trail_level(entry, sl, peak, s.c[k], d, give)
            if nsl is None:
                px_out, kk = s.c[k], k; break
            sl = nsl
        if px_out is None:
            kk = min(j + hold, len(s) - 1); px_out = s.c[kk]
        pts = d * ((px_out - d * SP[kk] * cs / 2.0) - entry)

        lo = min(s.l[max(0, j - 200):j] or [entry])
        hi = max(s.h[max(0, j - 200):j] or [entry])
        med = statistics.median([x for x in A[max(100, j - 500):j] if x] or [a])
        # the pivot this trade came from, and the nearest one in the way
        age, room = 0, 0.0
        # the pivot this trade came from: the CLOSEST one by price among those
        # already confirmed. Matching on an exact tie found almost nothing and
        # left the quartiles degenerate, which read as "flat" when it was
        # really "not measured".
        bestd = None
        for (kb, px, side) in seen[-600:]:
            dd = abs(px - entry)
            if bestd is None or dd < bestd:
                bestd, age = dd, j - kb
        nxt = None
        for (kb, px, side) in seen[-400:]:
            if d * (px - entry) > 0 and (nxt is None or d * (px - nxt) < 0):
                nxt = px
        room = abs(nxt - entry) / a if nxt is not None else 0.0

        out.append({
            "j": j, "pts": pts, "d": d,
            "stopw": risk / a,
            "depth": max(0.0, risk / a - BUF),
            "regime": a / med if med else 1.0,
            "rpos": (entry - lo) / (hi - lo) if hi > lo else 0.5,
            "age": float(age),
            "room": room,
            "hour": float((s.ts[j] // 3600) % 24),   # E-161: these are SECONDS, not millis
        })
        busy = kk + cooldown
    _M[tf] = (out, len(s))
    return _M[tf]


FEATS = ["stopw", "depth", "regime", "rpos", "age", "room", "hour"]


def quartiles(rows, f):
    v = sorted(r[f] for r in rows)
    if len(v) < 40:
        return None
    q = [v[int(p * (len(v) - 1))] for p in (0.25, 0.50, 0.75)]
    buckets = [[], [], [], []]
    for r in rows:
        x = r[f]
        b = 0 if x <= q[0] else 1 if x <= q[1] else 2 if x <= q[2] else 3
        buckets[b].append(r["pts"])
    return q, buckets


def main():
    for tf in ("M1", "M5"):
        rows, n = build(tf)
        half = n // 2
        A = [r for r in rows if r["j"] < half]
        B = [r for r in rows if r["j"] >= half]
        print("=" * 100)
        print(f"  E-159 — {tf}: does anything knowable at entry separate the "
              f"sweeps? n={len(rows)} ({len(A)} in, {len(B)} unseen)")
        print("=" * 100)
        base = sum(r["pts"] for r in A) / len(A)
        print(f"  first half baseline: {base:+.4f}/trade over {len(A)} trades\n")
        print(f"  {'feature':<10}{'Q1':>10}{'Q2':>10}{'Q3':>10}{'Q4':>10}"
              f"{'spread':>10}  monotone?")
        keep = []
        for f in FEATS:
            r = quartiles(A, f)
            if not r:
                continue
            q, bk = r
            m = [sum(b) / len(b) if b else 0.0 for b in bk]
            up = all(m[i] < m[i + 1] for i in range(3))
            dn = all(m[i] > m[i + 1] for i in range(3))
            print(f"  {f:<10}" + "".join(f"{x:>+10.4f}" for x in m)
                  + f"{max(m)-min(m):>10.4f}  "
                  + ("YES up" if up else "YES down" if dn else "no"))
            if up or dn:
                keep.append((f, q, up))

        if not keep:
            print("\n  Nothing is monotone. No filter is proposed, and that IS "
                  "the finding: the sweep does not sort by any of these.")
            print()
            continue
        for (f, q, up) in keep:
            # keep the better HALF, refuse the worse half
            cut = q[1]
            kept = [r for r in B if (r[f] > cut) == up]
            refd = [r for r in B if (r[f] > cut) != up]
            if len(kept) < 100 or not refd:
                print(f"\n  {f}: only {len(kept)} unseen trades kept - not a result.")
                continue
            pk = sum(r["pts"] for r in kept) / len(kept)
            pr = sum(r["pts"] for r in refd) / len(refd)
            pall = sum(r["pts"] for r in B) / len(B)
            print(f"\n  FILTER on {f} (keep {'above' if up else 'below'} {cut:.3f})")
            print(f"    unseen kept    n={len(kept):<5} {sum(r['pts'] for r in kept):>8.1f} pts {pk:+.4f}/tr")
            print(f"    unseen REFUSED n={len(refd):<5} {sum(r['pts'] for r in refd):>8.1f} pts {pr:+.4f}/tr")
            print(f"    unfiltered     n={len(B):<5} {sum(r['pts'] for r in B):>8.1f} pts {pall:+.4f}/tr")
            if pr < pk and pk > pall:
                print("    -> the refused trades really are worse. CANDIDATE.")
            else:
                print("    -> REJECT: it does not hold, or it refuses good trades.")
        print()


if __name__ == "__main__":
    main()
