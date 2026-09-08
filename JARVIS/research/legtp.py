"""
E-186 — DOES TP1 PAY FROM THE LEG CATCHER? The P&L question, finally asked of
the right entry.

Veer, showing two M1 charts: "see how price is reacting in the clean moves and
even when the moves don't last that that long we are still profitable yk easily
hit tp 1".

That is a modest, precise and testable claim, and it is exactly the gap left by
the last two studies:
  E-184  the leg catcher marks leg STARTS at 1.5-2.2x the base rate
  E-185  the next HTF level is REACHED 54.5% of the time from those signals
  ...neither measured money, and I said so both times.

E-172 did test fixed targets and found every one of them sat on zero - but that
was the SWEEP entry, which E-184 has since scored at 1.00 as a leg-start marker,
i.e. no better than a random bar. Nobody has tested a target on an entry that
actually lands where moves begin. That is this file.

WHAT IS CHARGED AND WHAT IS ENFORCED
  * cost: 0.02 ATR a trade, and a sensitivity table, because these files carry
    no spread column
  * the stop is checked BEFORE the target on every bar - ties lose, which is
    the honest way round
  * E-110: the entry bar may not book its own favourable extreme
  * one position at a time, with a cooldown, so a single move cannot be counted
    five times (E-073)
"""
from __future__ import annotations
import os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, Series
from regime import load_plain, resample
from liq_m1 import load as load_spread
from legcatch import features

COST = 0.02


def signals(s, A, V=None, need=3):
    F = features(s, A, V)
    keep = ["stretched from 50 EMA", "premium / discount",
            "60%+ rejection wick", "equal highs taken", "equal lows taken"]
    if V:
        keep.append("volume x2 at the bar")
    keep = [k for k in keep if k in F]
    out = []
    for i in range(len(s)):
        up = sum(1 for k in keep if F[k][i] > 0)
        dn = sum(1 for k in keep if F[k][i] < 0)
        if up >= need and up > dn:
            out.append((i, 1))
        elif dn >= need and dn > up:
            out.append((i, -1))
    return out


def book(s, A, sig, stopAtr=1.5, tpR=1.0, hold=240, cool=5, cost=COST):
    """Enter at the next open, stop at stopAtr ATR, target at tpR x risk."""
    out, busy = [], -1
    for (i, t) in sig:
        if i <= busy or i + 1 >= len(s):
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
            # the stop is tested FIRST: a bar that touches both is a loss
            if (s.l[k] <= sl) if t > 0 else (s.h[k] >= sl):
                px, kk = sl, k
                break
            # E-110: not on the entry bar
            if k > i + 1 and ((s.h[k] >= tp) if t > 0 else (s.l[k] <= tp)):
                px, kk = tp, k
                break
        if px is None:
            kk = min(i + 1 + hold, len(s) - 1)
            px = s.c[kk]
        out.append(t * (px - entry) / a - cost)
        busy = kk + cool
    return out


def line(lbl, r):
    if len(r) < 30:
        print(f"  {lbl:<30}  only {len(r)} trades")
        return None
    m = statistics.fmean(r)
    t = m / (statistics.pstdev(r) / len(r) ** 0.5)
    w = 100.0 * sum(1 for x in r if x > 0) / len(r)
    print(f"  {lbl:<30}{len(r):>7}{w:>8.1f}%{m:>+10.4f}{t:>+7.2f}{sum(r):>10.1f}")
    return (len(r), w, m, t)


def grid(label, s, V=None, need=3):
    A = watr(s, 14)
    sig = signals(s, A, V, need)
    if len(sig) < 60:
        print(f"\n  {label}: only {len(sig)} signals")
        return
    print(f"\n  ---- {label} — {len(sig)} signals, catcher needs {need} ----")
    print(f"  {'stop / target':<30}{'n':>7}{'win%':>9}{'ATR/trd':>10}{'t':>7}"
          f"{'total':>10}")
    print("  " + "-" * 73)
    for stopAtr in (1.0, 1.5, 2.0):
        for tpR in (0.5, 1.0, 1.5, 2.0):
            line(f"stop {stopAtr:.1f} ATR, TP {tpR:.1f}R",
                 book(s, A, sig, stopAtr=stopAtr, tpR=tpR))
        print()


def main():
    print("=" * 80)
    print("  E-186 — TP1 from the leg catcher. The P&L question, on the entry")
    print("  that E-184 showed actually marks leg starts.")
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
    grid("2018 M1, need 3", s1, V=V, need=3)
    grid("2018 M1, need 4", s1, V=V, need=4)
    grid("2024-2026 1h, need 3", load_plain("GOLD_1h.json"), need=3)




def book_level(s, A, sig, H, factor, stopAtr=1.5, hold=240, cool=5,
               cost=COST, minR=0.0, capR=99.0):
    """Same entry and stop. The TARGET is the next HTF swing level, not a ruler.

    E-186 part 1 shows why this is the cell that matters. At a fixed target the
    arithmetic is fixed too: the catcher lands on a leg start ~35% of the time
    against a 23% base, and 0.35 x 0.5R - 0.65 x 1R is deeply negative however
    good the entry is. A LEVEL target unfixes the reward - some setups have 3R
    of room to the next level, some have 0.4R - so the payoff varies with the
    setup instead of being the same every time.

    minR refuses a signal whose level is too close to be worth the spread; capR
    refuses one so far away it is a different trade.
    """
    piv, pv = {}, 3
    for i in range(pv, len(H) - pv):
        if H.h[i] == max(H.h[i-pv:i+pv+1]):
            piv.setdefault(i + pv, []).append(H.h[i])
        if H.l[i] == min(H.l[i-pv:i+pv+1]):
            piv.setdefault(i + pv, []).append(H.l[i])
    out, busy = [], -1
    live, seen = [], 0
    bySig = {i: t for (i, t) in sig}
    for i in range(len(s)):
        j = max(0, (i // factor) - 1)
        while seen <= j:
            live.extend(piv.get(seen, []))
            seen += 1
        live = live[-30:]
        t = bySig.get(i, 0)
        if t == 0 or i <= busy or i + 1 >= len(s) or not live:
            continue
        a = A[i]
        if not a or a <= 0:
            continue
        entry = s.o[i + 1]
        sl = entry - t * stopAtr * a
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        cand = [p for p in live if p > entry] if t > 0 else [p for p in live if p < entry]
        if not cand:
            continue
        tp = min(cand) if t > 0 else max(cand)
        rr = abs(tp - entry) / risk
        if rr < minR or rr > capR:
            continue
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
        out.append(t * (px - entry) / a - cost)
        busy = kk + cool
    return out


def levelgrid(label, s, factor, htfName, V=None, need=3):
    A = watr(s, 14)
    sig = signals(s, A, V, need)
    H = resample(s, factor)
    print(f"\n  ---- {label}: target = the next {htfName} level ----")
    print(f"  {'stop / room filter':<30}{'n':>7}{'win%':>9}{'ATR/trd':>10}{'t':>7}"
          f"{'total':>10}")
    print("  " + "-" * 73)
    for stopAtr in (1.0, 1.5, 2.0):
        for (lo, hi, nm) in ((0.0, 99.0, "any room"), (1.0, 99.0, "at least 1R"),
                             (1.5, 99.0, "at least 1.5R"), (2.0, 6.0, "2R to 6R")):
            line(f"stop {stopAtr:.1f} ATR, {nm}",
                 book_level(s, A, sig, H, factor, stopAtr=stopAtr,
                            minR=lo, capR=hi))
        print()


def main2():
    print("\n" + "=" * 80)
    print("  E-186 PART 2 — a LEVEL target instead of a ruler (E-185's finding)")
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
    levelgrid("2018 M1", s1, 60, "H1", V=V, need=3)


if __name__ == "__main__":
    main()
    main2()
