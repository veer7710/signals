"""
E-144 — BREAK AND RETEST: "if price disrespected them and goes above we should
look for entry to buy or sell accordingly, probably wait for small pullback or
retest and get a sniper entry in".

That is the S/R flip, and it is a THIRD signal type - distinct from the sweep
(which fades the level) because this one TRADES WITH the break. The two are
opposites, which is exactly why both can be true: a level either holds or it
does not, and the sweep filter (a wick, body <= 0.646 of range) is what
separates the two cases.

E-100 already rejected "S/R flip". THAT REJECTION IS NOT ADMISSIBLE, for the
third time in this project and for the same three reasons: E-100 used GOLD 15m
and 1h ONLY (no M1/M5 data existed), it charged spread 0.46 when the tick data
later measured 0.229, and it predates the E-110 fill-convention fix.

THE RULE, defined before any outcome is looked at:
    BREAK    a bar CLOSES through a confirmed swing level by `brk` ATR. A close
             is required - a wick through is the sweep setup, not this one.
    RETEST   price comes back to the level within `wait` bars and holds it: it
             touches within `tol` ATR and closes back on the break side.
    ENTRY    a stop order in the direction of the break, at the retest bar's
             extreme, so we are filled as it resumes rather than guessing.
    STOP     beyond the retest extreme + 0.30 ATR
    CAP      refuse if the stop is wider than 1.2 ATR (E-138)
    EXIT     give back 25% (E-137)

Identical stop, cap and exit to the shipped sweep system, so the only thing
being compared is the SIGNAL.

CONTROL: geometry kept, timing destroyed - same stop distance, same exit, same
direction, entered at market on an unrelated bar, drawn per-run with its own
seed and sorted into time order before the cooldown is applied. All three of
those details are things that have broken a control in this project already.
"""
from __future__ import annotations
import os, sys, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from liq_m1 import load, GBP
from sweep_winrate import pivots

TODAY = 7.38
GBP_PT = TODAY * GBP
BPD = {"M1": 1440, "M5": 288, "M15": 96}


def run(tf="M1", pk=5, brk=0.10, tol=0.20, wait=60, buf=0.30, give=0.25,
        max_risk_atr=1.2, hold=240, cooldown=5, cost_frac=0.11, slip=0.0,
        subset=None, control=False, seed=1):
    s, SP = load(tf)
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    cs = cost_frac / (statistics.median(SP) / va[len(va) // 2])
    rng = random.Random(seed)

    plan = []
    for (kb, px, side) in pivots(s, pk):
        a = A[kb]
        if not a or a <= 0:
            continue
        # side +1 is a swing HIGH: breaking it UP is a bullish break -> BUY
        d = side
        bb = None
        for k in range(kb + 1, min(kb + wait, len(s))):
            through = (s.c[k] > px + brk * a) if d > 0 else (s.c[k] < px - brk * a)
            if through:
                bb = k
                break
        if bb is None:
            continue
        # THE RETEST: back to the level, and closing on the break side again
        rt = None
        for k in range(bb + 1, min(bb + wait, len(s))):
            touched = (s.l[k] <= px + tol * a) if d > 0 else (s.h[k] >= px - tol * a)
            held = (s.c[k] > px) if d > 0 else (s.c[k] < px)
            gone = (s.c[k] < px - tol * a) if d > 0 else (s.c[k] > px + tol * a)
            if gone:
                break                      # the break failed; this is not a retest
            if touched and held:
                rt = k
                break
        if rt is None:
            continue
        # enter as it resumes: a stop order at the retest bar's extreme
        trig = s.h[rt] if d > 0 else s.l[rt]
        ext = s.l[rt] if d > 0 else s.h[rt]
        sl0 = ext - d * buf * a
        risk = abs(trig - sl0)
        if risk <= 0 or risk > max_risk_atr * a:
            continue

        if control:
            j = rng.randrange(300, len(s) - 300)
            entry = s.c[j] + d * SP[j] * cs / 2.0
            plan.append((j, d, entry, entry - d * risk))
            continue

        j = None
        for k in range(rt + 1, min(rt + wait, len(s))):
            if (s.h[k] >= trig) if d > 0 else (s.l[k] <= trig):
                j = k
                break
            # if it comes back through the level the setup is dead
            if (s.c[k] < px - tol * a) if d > 0 else (s.c[k] > px + tol * a):
                break
        if j is None:
            continue
        if subset and not (subset[0] <= j < subset[1]):
            continue
        plan.append((j, d, trig + d * SP[j] * cs / 2.0, sl0))
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
    for tf in ("M1", "M5"):
        s, _ = load(tf)
        n = len(s)
        days = n / BPD[tf]
        print("=" * 92)
        print(f"  E-144 — BREAK AND RETEST on {tf} (E-100 rejected this on 15m/1h")
        print("          only, at double the real spread, before the E-110 fix)")
        print("=" * 92)
        base = run(tf)
        N, W, P, PT = stats(base)
        if N < 40:
            print("  too few trades")
            continue
        print(f"  {N} trades, {N/days:.1f}/day, {W:.1f}% win, {P:+.1f} points, "
              f"{PT:+.4f}/trade, {P*GBP_PT:+.2f} GBP")
        a = stats(run(tf, subset=(0, n // 2)))
        b = stats(run(tf, subset=(n // 2, n)))
        print(f"  IS  {a[0]:>5} trades {a[2]:>8.1f} pts {a[3]:+.4f}/tr    "
              f"OOS {b[0]:>5} trades {b[2]:>8.1f} pts {b[3]:+.4f}/tr")
        ctrl = []
        for sd in range(12):
            r = run(tf, control=True, seed=6100 + sd)
            if r:
                ctrl.append(stats(r)[3])
        cm = sum(ctrl) / len(ctrl)
        cse = (sum((x - cm) ** 2 for x in ctrl) / (len(ctrl) - 1)) ** 0.5 / len(ctrl) ** 0.5
        print(f"  control {cm:+.4f}/trade  se {cse:.4f}  "
              f"EDGE {PT-cm:+.4f} = {(PT-cm)/cse:.1f} control se")
        for sl in (0.02, 0.05):
            print(f"  slippage {sl:.2f}: {stats(run(tf, slip=sl))[2]:>8.1f} pts")
        for c in (0.165, 0.220):
            print(f"  spread/ATR {c:.3f}: {stats(run(tf, cost_frac=c))[2]:>8.1f} pts")
        lo = [x for x in base if x[1] > 0]
        sh = [x for x in base if x[1] < 0]
        print(f"  long {len(lo)} {sum(x[0] for x in lo):+.1f} pts   "
              f"short {len(sh)} {sum(x[0] for x in sh):+.1f} pts")
        print()


if __name__ == "__main__":
    main()
