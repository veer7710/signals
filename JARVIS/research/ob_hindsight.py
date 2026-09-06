"""
E-148 — IS THE ORDER BLOCK'S "TOP TICK" REAL, OR IS IT DRAWN IN HINDSIGHT?

Veer, showing five XAUUSD M1 screenshots: "it catches top tick entrys and some
that we wouldnt missed or been late on... use logic when auditing, actually try
to disprove your point".

So here is the disproof attempt, and it is the one that matters.

LOOK AT WHERE THE MARKER IS DRAWN. wugamlo's indicator plots the triangle with
`offset = -ob_period`, which puts it back on the ORDER BLOCK CANDLE. But the
block is only IDENTIFIED after `periods` more candles have closed in the other
direction. On his settings that is 4 to 6 bars later.

So the triangle sits on the extreme of the move, and it was NOT KNOWABLE THERE.
By the time the signal exists, price has already gone. That is not a criticism
of the indicator - it is drawing history correctly - it is a warning about
reading entries off it, because the eye sees a marker at the top tick and
concludes the top tick was catchable.

THIS IS THE SAME CLASS OF ERROR AS E-110, which invalidated six separate
"validations" in this project.

THREE ENTRIES, on identical stops, identical risk cap, identical give-back exit.
Only the entry price differs:

  A  AT THE MARKER      the OB candle's own edge, on the bar it is drawn.
                        IMPOSSIBLE - the signal did not exist yet. Included
                        purely to measure the size of the illusion.
  B  AT DETECTION       market, on the bar the block is confirmed. This is the
                        earliest a human or an EA could act.
  C  ON THE RETURN      a limit at the zone edge when price comes back. What
                        E-142 measured and what the chart ships.

If A is huge and B is poor, the "top tick" is hindsight. If B holds up, then it
really does catch the birth of moves and it deserves to be a market entry.
"""
from __future__ import annotations
import os, sys, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from liq_m1 import load, GBP
from orderblock import blocks

TODAY = 7.38
GBP_PT = TODAY * GBP
BPD = {"M1": 1440, "M5": 288, "M15": 96}


def run(tf, mode, periods=3, usewicks=True, buf=0.30, give=0.25,
        max_risk_atr=1.2, life=240, hold=240, cooldown=5, cost_frac=0.11,
        subset=None):
    s, SP = load(tf)
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    cs = cost_frac / (statistics.median(SP) / va[len(va) // 2])
    obp = periods + 1
    plan = []
    for (kb, top, bot, d) in blocks(s, periods, 0.0, usewicks):
        a = A[kb]
        if not a or a <= 0:
            continue
        lvl = top if d > 0 else bot
        far = bot if d > 0 else top
        sl = far - d * buf * a
        if abs(lvl - sl) > max_risk_atr * a or abs(lvl - sl) <= 0:
            continue

        if mode == "marker":
            # the price the triangle is drawn at, on the bar it is drawn.
            # NOT REACHABLE - the block is only known obp bars later.
            j = kb - obp
            if j < 1:
                continue
            entry = lvl
        elif mode == "detect":
            # the first bar an EA or a human could act: market, at confirmation
            j = kb
            entry = s.c[kb] + d * SP[kb] * cs / 2.0
            sl = far - d * buf * a
            if abs(entry - sl) > max_risk_atr * a:
                continue
        else:
            j = None
            for k in range(kb, min(kb + life, len(s))):
                if (s.l[k] <= lvl) if d > 0 else (s.h[k] >= lvl):
                    j = k
                    break
            if j is None:
                continue
            entry = lvl + d * SP[j] * cs / 2.0
        if subset and not (subset[0] <= j < subset[1]):
            continue
        plan.append((j, d, entry, sl))
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
        out.append(d * ((px_out - d * SP[kk] * cs / 2.0) - entry))
        busy = kk + cooldown
    return out


def st(r):
    if not r:
        return (0, 0.0, 0.0, 0.0)
    p = sum(r)
    return (len(r), 100.0 * sum(1 for x in r if x > 0) / len(r), p, p / len(r))


def main():
    print("=" * 94)
    print("  E-148 — is the order block's 'top tick' real, or drawn in hindsight?")
    print("  Same stop, same cap, same give-back exit. ONLY the entry differs.")
    print("=" * 94)
    for tf in ("M1", "M5"):
        s, _ = load(tf)
        n = len(s)
        days = n / BPD[tf]
        print(f"\n  ---------- {tf} ----------")
        print(f"  {'entry':<40}{'n':>6}{'/day':>7}{'win%':>7}"
              f"{'points':>9}{'per trade':>12}{'GBP':>10}")
        print("  " + "-" * 82)
        for mode, lbl in (("marker", "A  AT THE MARKER — impossible"),
                          ("detect", "B  AT DETECTION — earliest actionable"),
                          ("return", "C  ON THE RETURN — what ships")):
            r = run(tf, mode)
            if len(r) < 30:
                print(f"  {lbl:<40}{len(r):>6}  too few")
                continue
            N, W, P, PT = st(r)
            print(f"  {lbl:<40}{N:>6}{N/days:>7.1f}{W:>6.1f}%{P:>9.1f}"
                  f"{PT:>+12.4f}{P*GBP_PT:>10.2f}")
        print("\n    out of sample (the two REACHABLE entries only)")
        for mode, lbl in (("detect", "B at detection"), ("return", "C on the return")):
            a = st(run(tf, mode, subset=(0, n // 2)))
            b = st(run(tf, mode, subset=(n // 2, n)))
            if a[0] and b[0]:
                print(f"      {lbl:<18} IS {a[2]:>7.1f} pts {a[3]:+.4f}/tr   "
                      f"OOS {b[2]:>7.1f} pts {b[3]:+.4f}/tr")


if __name__ == "__main__":
    main()
