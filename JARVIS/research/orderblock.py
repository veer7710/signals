"""
E-142 — THE ORDER BLOCK FINDER, MEASURED.

Veer: "this orderblock script i just sent u is so perfect, catches sooo many
good moves, possibly best indicator ive ever found... it catches real births of
alot of the massive trends".

The rule (wugamlo, MPL-2.0 - a permissive licence, so unlike the LuxAlgo
scripts this one can actually be used and modified in something shipped):

    BULLISH OB   a DOWN candle followed by `periods` consecutive UP candles,
                 where the move from the OB candle's close to the last of them
                 is at least `threshold` percent.
                 The zone is OPEN..LOW of that down candle (or HIGH..LOW).
    BEARISH OB   the mirror.

The claim being tested is not "does it mark nice places" - it does, that is what
made him notice it. The claim is that PRICE RETURNING TO THAT ZONE IS A TRADE.
That is falsifiable and it is what an EA would have to do with it.

THE TRADE, kept identical to the validated sweep system so the comparison is
about the SIGNAL and nothing else:
    entry   a limit at the zone's near edge when price returns to it
    stop    beyond the zone's far edge + 0.30 ATR
    cap     refuse the setup if that stop is wider than 1.2 ATR (E-138)
    exit    give back 25% (E-137: it beat every fixed target)
E-110 enforced: the bar that fills may not book a favourable exit.

CONTROL: geometry kept, timing destroyed - same stop distance, same exit, same
direction, entered at the market on an unrelated bar. Random entries are not a
fair control for a level strategy (E-076) and a shifted LEVEL is not either
(E-137 - that bug reported -16.6 se).
"""
from __future__ import annotations
import os, sys, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from liq_m1 import load, GBP

TODAY = 7.38
GBP_PT = TODAY * GBP
BPD = {"M1": 1440, "M5": 288, "M15": 96}


def blocks(s, periods, thresh_pct, usewicks):
    """Every order block, as (bar_confirmed, top, bottom, dir).
    The OB candle sits `periods+1` bars back from the confirmation bar, which is
    exactly how the indicator finds it - so the zone is known the moment the
    run of candles completes, and not one bar earlier."""
    out = []
    obp = periods + 1
    for i in range(obp + 1, len(s)):
        c0 = s.c[i - obp]
        if c0 == 0:
            continue
        move = abs(c0 - s.c[i - 1]) / c0 * 100.0
        if move < thresh_pct:
            continue
        ups = sum(1 for k in range(1, periods + 1) if s.c[i - k] > s.o[i - k])
        dns = sum(1 for k in range(1, periods + 1) if s.c[i - k] < s.o[i - k])
        j = i - obp
        if s.c[j] < s.o[j] and ups == periods:
            top = s.h[j] if usewicks else s.o[j]
            out.append((i, top, s.l[j], 1))
        elif s.c[j] > s.o[j] and dns == periods:
            bot = s.l[j] if usewicks else s.o[j]
            out.append((i, s.h[j], bot, -1))
    return out


def run(tf, periods=5, thresh=0.0, usewicks=False, entry_at="near",
        buf=0.30, give=0.25, max_risk_atr=1.2, life=240, hold=240,
        cooldown=5, cost_frac=0.11, slip=0.0, subset=None, control=False,
        seed=4242):
    s, SP = load(tf)
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    cs = cost_frac / (statistics.median(SP) / va[len(va) // 2])
    obs = blocks(s, periods, thresh, usewicks)
    rng = random.Random(seed)

    # build the trade list first so the control can be put in TIME ORDER before
    # the cooldown is applied - a cooldown assumes an ordered book, and feeding
    # it random bar indices silently discards an arbitrary subset.
    plan = []
    for (kb, top, bot, d) in obs:
        a = A[kb]
        if not a or a <= 0:
            continue
        mid = (top + bot) / 2.0
        lvl = (top if d > 0 else bot) if entry_at == "near" else mid
        far = bot if d > 0 else top
        sl0 = far - d * buf * a
        risk = abs(lvl - sl0)
        if risk > max_risk_atr * a or risk <= 0:
            continue
        if control:
            j = rng.randrange(300, len(s) - 300)
            entry = s.c[j] + d * SP[j] * cs / 2.0
            plan.append((j, d, entry, entry - d * risk))
        else:
            j = None
            for k in range(kb, min(kb + life, len(s))):
                if (s.l[k] <= lvl) if d > 0 else (s.h[k] >= lvl):
                    j = k
                    break
            if j is None:
                continue
            if subset and not (subset[0] <= j < subset[1]):
                continue
            plan.append((j, d, lvl + d * SP[j] * cs / 2.0, sl0))
    plan.sort()

    out, busy = [], -1
    for (j, d, entry, sl) in plan:
        if j <= busy:
            continue
        peak = entry
        px_out, kk = None, None
        for k in range(j, min(j + hold, len(s))):
            if (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k
                break
            if k == j:
                continue
            peak = max(peak, s.h[k]) if d > 0 else min(peak, s.l[k])
            up = d * (peak - entry)
            if up > 0:
                c = entry + d * up * (1.0 - give)
                sl = max(sl, c) if d > 0 else min(sl, c)
        if px_out is None:
            kk = min(j + hold, len(s) - 1)
            px_out = s.c[kk]
        out.append((d * ((px_out - d * SP[kk] * cs / 2.0) - entry) - slip, d))
        busy = kk + cooldown
    return out


def stats(r):
    if not r:
        return (0, 0.0, 0.0, 0.0)
    p = sum(x[0] for x in r)
    return (len(r), 100.0 * sum(1 for x in r if x[0] > 0) / len(r), p, p / len(r))


def main():
    print("=" * 100)
    print("  E-142 — the Order Block Finder as a TRADE, not as a picture")
    print("  Same stop, same risk cap, same give-back exit as the validated")
    print("  sweep system, so the only thing being compared is the SIGNAL.")
    print("=" * 100)

    for tf in ("M1", "M3", "M5", "M15"):
        if tf == "M3":
            continue
        s, _ = load(tf)
        days = len(s) / BPD[tf]
        print(f"\n  ---------- {tf} ----------")
        print(f"  {'periods':>8}{'thresh%':>9}{'zone':>10}{'entry':>8}"
              f"{'n':>7}{'/day':>7}{'win%':>7}{'points':>9}{'per trade':>11}{'GBP':>10}")
        print("  " + "-" * 86)
        best = None
        for per in (3, 5, 8):
            for th in (0.0, 0.1):
                for wick in (False, True):
                    for ent in ("near", "mid"):
                        r = run(tf, periods=per, thresh=th, usewicks=wick, entry_at=ent)
                        if len(r) < 40:
                            continue
                        n, w, p, pt = stats(r)
                        print(f"  {per:>8}{th:>9.1f}{'H/L' if wick else 'O/L':>10}"
                              f"{ent:>8}{n:>7}{n/days:>7.1f}{w:>6.1f}%{p:>9.1f}"
                              f"{pt:>+11.4f}{p*GBP_PT:>10.2f}")
                        if best is None or p > best[0]:
                            best = (p, per, th, wick, ent)
        if best:
            print(f"  BEST {tf}: periods {best[1]}, threshold {best[2]}, "
                  f"{'H/L' if best[3] else 'O/L'}, entry {best[4]} -> {best[0]:.1f} points")


if __name__ == "__main__":
    main()
