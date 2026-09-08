"""
E-187 — DO WITH-BIAS LEGS RUN FURTHER? Veer's own rule, tested.

Veer: "say h1 bias is bearish but m15 shows like an insane wick at a liquidity
level and a clear buy opportunity should i not take that then just cuz its not
in the bias don't mean we cant and m1 often just has big legs but continues down
towards bias yk most the time".

That is not the hypothesis E-185 tested and rejected. E-185 asked whether the
HTF makes the ENTRY better — it does not, ±0.02 across thirty cells. Veer is
asking something else and sharper:

    TAKE BOTH. But a counter-bias leg is SHORTER, so manage it differently.

If true it rescues the arithmetic that killed E-186. That failed because
35% x payoff could not beat 65% x 1R at a payoff fixed for every trade. If
with-bias legs are materially longer than counter-bias ones, the book splits
into two populations with different payoffs, and one of them may clear the bar
while the blended average never could.

Also tested, because he asked for it in the same breath: "sometimes it's not
always very very clean moves some are shorter and smaller we catch those too but
no random signals". So the leg-size floor is swept - does the catcher still mark
starts when the legs are small, or does it only work on the big obvious ones?
"""
from __future__ import annotations
import os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, ema
from regime import load_plain, resample
from liq_m1 import load as load_spread
from legcatch import legs, features, score
from legtp import signals, COST


def bias_series(s, factor, look=50):
    """HTF trend at every base bar: +1 up, -1 down. lookahead_off by hand -
    bar i reads HTF bar (i//factor)-1, never the one still forming."""
    H = resample(s, factor)
    E = ema(H.c, look)
    n = len(s)
    out = [0] * n
    for i in range(n):
        j = max(0, (i // factor) - 1)
        if j < look or j >= len(H) or E[j] is None:
            continue
        out[i] = 1 if H.c[j] > E[j] else -1
    return out


def leg_lengths(label, s, factor, htfName, minAtr=2.0):
    """The question in its purest form: with the bias, how big is a leg?
    Against it, how big?"""
    A = watr(s, 14)
    lg = legs(s, A, pv=3, minAtr=minAtr)
    bias = bias_series(s, factor)
    with_, against = [], []
    for (b0, b1, d, size) in lg:
        b = bias[b0]
        if b == 0:
            continue
        (with_ if b == d else against).append(size)
    if len(with_) < 30 or len(against) < 30:
        print(f"\n  {label}: too few to split")
        return
    mw, ma = statistics.fmean(with_), statistics.fmean(against)
    sw = statistics.pstdev(with_) / len(with_) ** 0.5
    sa = statistics.pstdev(against) / len(against) ** 0.5
    t = (mw - ma) / ((sw ** 2 + sa ** 2) ** 0.5)
    print(f"\n  ---- {label}: leg size WITH vs AGAINST the {htfName} bias ----")
    print(f"  {'':<22}{'n':>7}{'mean ATR':>11}{'median':>9}{'75th pct':>10}")
    for nm, v in (("with the bias", with_), ("against it", against)):
        v2 = sorted(v)
        print(f"  {nm:<22}{len(v):>7}{statistics.fmean(v):>11.2f}"
              f"{v2[len(v2)//2]:>9.2f}{v2[int(0.75*(len(v2)-1))]:>10.2f}")
    print(f"  difference {mw - ma:+.2f} ATR, t {t:+.2f}   "
          f"{'WITH-bias legs ARE longer' if t > 2 else 'no reliable difference'}")


def split_book(label, s, factor, htfName, V=None, need=3,
               stopAtr=1.0, hold=240, cool=5):
    """E-186's book, split by bias, and each half given its own target sweep."""
    A = watr(s, 14)
    sig = signals(s, A, V, need)
    bias = bias_series(s, factor)

    def run(subset, tpR):
        out, busy = [], -1
        for (i, t) in sig:
            if i <= busy or i + 1 >= len(s):
                continue
            b = bias[i]
            if b == 0:
                continue
            if subset == "with" and b != t:
                continue
            if subset == "against" and b != -t:
                continue
            a = A[i]
            if not a or a <= 0:
                continue
            entry = s.o[i + 1]
            sl = entry - t * stopAtr * a
            risk = abs(entry - sl)
            if risk <= 0:
                continue
            tp = entry + t * tpR * risk
            px, kk = None, None
            for k in range(i + 1, min(i + 1 + hold, len(s))):
                if (s.l[k] <= sl) if t > 0 else (s.h[k] >= sl):
                    px, kk = sl, k
                    break
                if k > i + 1 and ((s.h[k] >= tp) if t > 0 else (s.l[k] <= tp)):
                    px, kk = tp, k
                    break
            if px is None:
                kk = min(i + 1 + hold, len(s) - 1)
                px = s.c[kk]
            out.append(t * (px - entry) / a - COST)
            busy = kk + cool
        return out

    print(f"\n  ---- {label}: the book split by {htfName} bias, stop {stopAtr} ATR ----")
    print(f"  {'subset / target':<28}{'n':>7}{'win%':>9}{'ATR/trd':>10}{'t':>7}"
          f"{'total':>10}")
    print("  " + "-" * 71)
    for subset in ("with", "against"):
        for tpR in (0.5, 1.0, 1.5, 2.0, 3.0):
            r = run(subset, tpR)
            if len(r) < 30:
                print(f"  {subset:<8} TP {tpR:.1f}R{'':<10}{len(r):>7}   too few")
                continue
            m = statistics.fmean(r)
            t = m / (statistics.pstdev(r) / len(r) ** 0.5)
            w = 100.0 * sum(1 for x in r if x > 0) / len(r)
            star = " <<<" if t >= 2.0 else ""
            print(f"  {subset:<8} TP {tpR:.1f}R{'':<10}{len(r):>7}{w:>8.1f}%"
                  f"{m:>+10.4f}{t:>+7.2f}{sum(r):>10.1f}{star}")
        print()


def small_legs(label, s, V=None, need=3):
    """"some are shorter and smaller we catch those too but no random signals"
    - does the catcher still mark starts when the legs are small?"""
    A = watr(s, 14)
    F = features(s, A, V)
    keep = [k for k in ["stretched from 50 EMA", "premium / discount",
                        "60%+ rejection wick", "equal highs taken",
                        "equal lows taken", "volume x2 at the bar"] if k in F]
    n = len(s)
    ser = [0] * n
    for i in range(n):
        up = sum(1 for k in keep if F[k][i] > 0)
        dn = sum(1 for k in keep if F[k][i] < 0)
        if up >= need and up > dn:
            ser[i] = 1
        elif dn >= need and dn > up:
            ser[i] = -1
    print(f"\n  ---- {label}: does it work on SMALL legs too? ----")
    print(f"  {'leg floor':<14}{'legs':>8}{'fires':>8}{'catches':>9}"
          f"{'control':>9}{'LIFT':>7}")
    print("  " + "-" * 56)
    for minAtr in (1.0, 1.5, 2.0, 3.0, 4.0):
        lg = legs(s, A, pv=3, minAtr=minAtr)
        if len(lg) < 40:
            continue
        rows, _, _ = score({"x": ser}, lg, n, slack=3)
        (_, fired, rate, ctrl, lift, _a) = rows[0]
        print(f"  >= {minAtr:.1f} ATR{'':<4}{len(lg):>8}{fired:>8}"
              f"{100*rate:>8.1f}%{100*ctrl:>8.1f}%{lift:>7.2f}")


def main():
    print("=" * 80)
    print("  E-187 — Veer's rule: take the counter-bias trade, but it is SHORTER")
    print("=" * 80)
    s1, _ = load_spread("M1")
    V = None
    try:
        import json
        rows = json.load(open("/home/user/signals/data/GOLD_M1_2018.json"))
        rows.sort(key=lambda r: r[0])
        V = [r[7] for r in rows] if len(rows[0]) > 7 else None
    except Exception:
        pass
    leg_lengths("2018 M1", s1, 60, "H1")
    leg_lengths("2018 M1", s1, 15, "M15")
    small_legs("2018 M1", s1, V=V)
    split_book("2018 M1", s1, 60, "H1", V=V)




def wide(label, s, factor, V=None, need=3):
    """The split book said something the whole project has been missing: the
    money climbs MONOTONICALLY with the target, 0.5R -> 3R, in both subsets.
    So the target has been too small all along, not too big. Push it out, and
    add the honest alternative - no target at all, ride to the opposite pivot.
    """
    A = watr(s, 14)
    sig = signals(s, A, V, need)
    bias = bias_series(s, factor)
    pv = 3
    piv = set()
    for i in range(pv, len(s) - pv):
        if s.h[i] == max(s.h[i-pv:i+pv+1]) or s.l[i] == min(s.l[i-pv:i+pv+1]):
            piv.add(i + pv)

    def run(subset, tpR, stopAtr, ride=False, hold=480, cool=5):
        out, busy = [], -1
        for (i, t) in sig:
            if i <= busy or i + 1 >= len(s):
                continue
            b = bias[i]
            if b == 0:
                continue
            if subset == "with" and b != t:
                continue
            if subset == "against" and b != -t:
                continue
            a = A[i]
            if not a or a <= 0:
                continue
            entry = s.o[i + 1]
            sl = entry - t * stopAtr * a
            risk = abs(entry - sl)
            if risk <= 0:
                continue
            tp = entry + t * tpR * risk if not ride else None
            px, kk = None, None
            for k in range(i + 1, min(i + 1 + hold, len(s))):
                if (s.l[k] <= sl) if t > 0 else (s.h[k] >= sl):
                    px, kk = sl, k
                    break
                if k > i + 1 and tp is not None:
                    if (s.h[k] >= tp) if t > 0 else (s.l[k] <= tp):
                        px, kk = tp, k
                        break
                # ride: exit on the first confirmed pivot AGAINST the trade
                if ride and k > i + 1 + pv and k in piv:
                    ext = s.h[k - pv] if t > 0 else s.l[k - pv]
                    isTop = (s.h[k - pv] == max(s.h[k-2*pv:k+1]))
                    if (t > 0 and isTop) or (t < 0 and not isTop):
                        px, kk = s.c[k], k
                        break
            if px is None:
                kk = min(i + 1 + hold, len(s) - 1)
                px = s.c[kk]
            out.append(t * (px - entry) / a - COST)
            busy = kk + cool
        return out

    print(f"\n  ---- {label}: pushing the target out ----")
    print(f"  {'subset / exit':<30}{'n':>7}{'win%':>9}{'ATR/trd':>10}{'t':>7}"
          f"{'total':>10}")
    print("  " + "-" * 73)
    for subset in ("with", "against"):
        for tpR in (3.0, 4.0, 6.0, 8.0):
            r = run(subset, tpR, 1.0)
            if len(r) < 30:
                continue
            m = statistics.fmean(r)
            t = m / (statistics.pstdev(r) / len(r) ** 0.5)
            w = 100.0 * sum(1 for x in r if x > 0) / len(r)
            print(f"  {subset:<8} TP {tpR:.0f}R, stop 1.0{'':<5}{len(r):>7}"
                  f"{w:>8.1f}%{m:>+10.4f}{t:>+7.2f}{sum(r):>10.1f}"
                  f"{' <<<' if t >= 2.0 else ''}")
        r = run(subset, 0, 1.0, ride=True)
        if len(r) >= 30:
            m = statistics.fmean(r)
            t = m / (statistics.pstdev(r) / len(r) ** 0.5)
            w = 100.0 * sum(1 for x in r if x > 0) / len(r)
            print(f"  {subset:<8} ride to the pivot{'':<4}{len(r):>7}"
                  f"{w:>8.1f}%{m:>+10.4f}{t:>+7.2f}{sum(r):>10.1f}"
                  f"{' <<<' if t >= 2.0 else ''}")
        print()


def main2():
    print("\n" + "=" * 80)
    print("  E-187 PART 2 — the target was too SMALL, not too big")
    print("=" * 80)
    s1, _ = load_spread("M1")
    V = None
    try:
        import json
        rows = json.load(open("/home/user/signals/data/GOLD_M1_2018.json"))
        rows.sort(key=lambda r: r[0])
        V = [r[7] for r in rows] if len(rows[0]) > 7 else None
    except Exception:
        pass
    wide("2018 M1, H1 bias", s1, 60, V=V)




def oos_wide():
    """THE HARD TEST, and it matters more here than anywhere else in this repo.

    E-187 part 2 produced the first t > 2 cells this project has ever had:
    against-bias, ride to the pivot, t +3.10; against-bias TP 8R, t +2.62. But
    by this point roughly forty cells have been examined, and the best of forty
    noise draws sits near t = 2.5 on its own. So the number means nothing until
    it repeats on data the search never touched.

    Nothing is re-derived: the two winning cells are carried over exactly as
    they came out, and measured on each half separately.
    """
    from engine import Series
    s1, _ = load_spread("M1")
    V = None
    try:
        import json
        rows = json.load(open("/home/user/signals/data/GOLD_M1_2018.json"))
        rows.sort(key=lambda r: r[0])
        V = [r[7] for r in rows] if len(rows[0]) > 7 else None
    except Exception:
        pass
    n = len(s1.c) // 2
    halves = [("FIRST half", Series(s1.ts[:n], s1.o[:n], s1.h[:n], s1.l[:n], s1.c[:n]),
               V[:n] if V else None),
              ("SECOND half - unseen", Series(s1.ts[n:], s1.o[n:], s1.h[n:], s1.l[n:],
                                              s1.c[n:]), V[n:] if V else None)]
    print("\n" + "=" * 80)
    print("  E-187 PART 3 — the two winning cells, on each half separately")
    print("  ~40 cells were examined to find them, so this is the only test")
    print("  that counts.")
    print("=" * 80)
    for lbl, s, v in halves:
        print(f"\n  ---- {lbl} ({len(s.c):,} bars) ----")
        wide(lbl, s, 60, V=v)


if __name__ == "__main__":
    oos_wide()
