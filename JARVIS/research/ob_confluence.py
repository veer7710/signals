"""
E-145 — VEER'S CONFLUENCE: AN ORDER BLOCK *AT* SWEPT LIQUIDITY.

"orderblock entries maybe can be combined w liquidity entries, like after a big
sell or buy a top tick entry or bottom tick entry is often shown by orderblock
yk, and thats when liquidity is swept and the high or low is broken"

That is a precise claim and it is the right shape of idea: the order block says
WHERE the last opposing orders sat, the sweep says the level was just cleared of
stops. If both point at the same price, the block is sitting on freshly emptied
liquidity.

Order block alone is the weakest of the three shipped signals (+0.0163/trade on
M1 against the sweep's +0.1200), so this is exactly the signal that needs help.

THE TEST: take the validated order-block trade unchanged and label each one with
whether a swing level was SWEPT near the block shortly before it formed.

    SWEPT      a confirmed swing pivot whose price was exceeded by a WICK -
               high through a swing high, or low through a swing low - within
               `look` bars before the block confirmed
    NEAR       that level sits within `tol` ATR of the block's zone

Then compare the two books. A confluence rule earns its place only if what it
REFUSES is worse than what it allows - that is the CLAUDE.md rule and it is the
one that kills most of these.
"""
from __future__ import annotations
import os, sys, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from liq_m1 import load, GBP
from sweep_winrate import pivots
from orderblock import blocks

TODAY = 7.38
GBP_PT = TODAY * GBP
BPD = {"M1": 1440, "M5": 288, "M15": 96}


def run(tf="M1", periods=3, usewicks=True, buf=0.30, give=0.25,
        max_risk_atr=1.2, life=240, hold=240, cooldown=5, cost_frac=0.11,
        look=120, tol=0.50, subset=None):
    s, SP = load(tf)
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    cs = cost_frac / (statistics.median(SP) / va[len(va) // 2])
    obs = blocks(s, periods, 0.0, usewicks)

    # every sweep event: (bar it happened, level price, side)
    sweeps = []
    for (kb, px, side) in pivots(s, 5):
        a = A[kb]
        if not a or a <= 0:
            continue
        for k in range(kb + 1, min(kb + 120, len(s))):
            hit = (s.h[k] >= px) if side > 0 else (s.l[k] <= px)
            closed_through = (s.c[k] > px) if side > 0 else (s.c[k] < px)
            if hit:
                if not closed_through:          # a WICK took it, not a close
                    sweeps.append((k, px, side))
                break
    sweeps.sort()

    out, busy = [], -1
    si = 0
    live = []
    for (kb, top, bot, d) in obs:
        a = A[kb]
        if not a or a <= 0:
            continue
        # keep a rolling window of recent sweeps
        while si < len(sweeps) and sweeps[si][0] <= kb:
            live.append(sweeps[si])
            si += 1
        live = [x for x in live if kb - x[0] <= look]
        mid = (top + bot) / 2.0
        conf = any(abs(px - mid) <= tol * a for (_, px, _) in live)

        lvl = top if d > 0 else bot
        far = bot if d > 0 else top
        sl0 = far - d * buf * a
        risk = abs(lvl - sl0)
        if risk <= 0 or risk > max_risk_atr * a:
            continue
        j = None
        for k in range(kb, min(kb + life, len(s))):
            if (s.l[k] <= lvl) if d > 0 else (s.h[k] >= lvl):
                j = k
                break
        if j is None or j <= busy:
            continue
        if subset and not (subset[0] <= j < subset[1]):
            continue
        entry = lvl + d * SP[j] * cs / 2.0
        sl = sl0
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
        out.append((d * ((px_out - d * SP[kk] * cs / 2.0) - entry), conf, d))
        busy = kk + cooldown
    return out


def show(rows, label):
    if not rows:
        print(f"  {label:<34} none")
        return
    p = sum(x[0] for x in rows)
    w = 100.0 * sum(1 for x in rows if x[0] > 0) / len(rows)
    print(f"  {label:<34}{len(rows):>7}{w:>7.1f}%{p:>10.1f}{p/len(rows):>+12.4f}")


def main():
    for tf in ("M1", "M5"):
        s, _ = load(tf)
        n = len(s)
        days = n / BPD[tf]
        rows = run(tf)
        print("=" * 84)
        print(f"  E-145 — {tf}: an order block sitting on SWEPT liquidity")
        print("=" * 84)
        print(f"  {'book':<34}{'n':>7}{'win%':>7}{'points':>10}{'per trade':>12}")
        print("  " + "-" * 70)
        show(rows, "all order blocks")
        show([r for r in rows if r[1]], "AT swept liquidity")
        show([r for r in rows if not r[1]], "...it would refuse")
        conf = [r for r in rows if r[1]]
        if conf:
            print(f"  confluence is {100.0*len(conf)/len(rows):.1f}% of blocks, "
                  f"{len(conf)/days:.1f}/day")
        print("\n  out of sample")
        for lbl, sub in (("first half ", (0, n // 2)), ("SECOND half", (n // 2, n))):
            r = run(tf, subset=sub)
            c = [x for x in r if x[1]]
            nc = [x for x in r if not x[1]]
            if c and nc:
                print(f"    {lbl}  confluence {len(c):>4} {sum(x[0] for x in c):>7.1f} pts "
                      f"{sum(x[0] for x in c)/len(c):+.4f}/tr   |   rest {len(nc):>4} "
                      f"{sum(x[0] for x in nc):>7.1f} pts {sum(x[0] for x in nc)/len(nc):+.4f}/tr")
        print()


if __name__ == "__main__":
    main()
