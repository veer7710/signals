"""
E-146 — DOES ANY OF THIS SURVIVE OFF XAUUSD 2018?

Two questions at once, and both are the ones that decide whether this is a
strategy or a curve fit.

  1. Veer: "can u make us run on nasdaq as well??? see if we can optimise this
     pine and ea for nasdaq if possibly it has clean moves". There is no NASDAQ
     series here, but there IS US500 - the same asset class, the same session
     structure, the same kind of clean trending move. If the edge is real it
     should show up there; if it is a gold artefact it will not.

  2. EVERY NUMBER IN THIS PROJECT COMES FROM 2018 H1 GOLD. These files are
     CURRENT: gold at 4189, timestamped June 2026. So they test today's
     volatility regime directly and the x7.38 scaling assumption drops out
     entirely.

ALL THREE SIGNALS, unchanged, on four instruments:
     SWEEP           level taken by a wick, price returns
     BREAK+RETEST    level taken by a close, price returns and holds
     ORDER BLOCK     price returns to the last opposing candle

COST is charged in the only unit that compares across instruments: spread as a
fraction of ATR. 0.11 is the base assumption every result here is quoted at;
0.22 is what Veer's 0.40 spread works out to on M1 gold (E-132). These files
carry no spread column, so it is assumed rather than measured - stated plainly
because it is the weakest part of this test.

NOTE THE TIMEFRAME: 15m and 1h only. The shipped system is an M1/M5 system, so
this is NOT a like-for-like reproduction - it is asking whether the same
GEOMETRY finds an edge elsewhere. A positive result here is corroboration, not
confirmation; a negative one on gold's own current data would be a serious
problem.
"""
from __future__ import annotations
import os, sys, json, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Series, atr as watr

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")


def load(name):
    rows = json.load(open(os.path.join(ROOT, name + ".json")))
    ts = [r[0] for r in rows]
    o = [r[1] for r in rows]
    h = [r[2] for r in rows]
    l = [r[3] for r in rows]
    c = [r[4] for r in rows]
    return Series(ts, o, h, l, c)


def pivots(s, k):
    out = []
    for i in range(k, len(s) - k):
        if s.h[i] == max(s.h[i - k:i + k + 1]):
            out.append((i + k, s.h[i], 1))
        if s.l[i] == min(s.l[i - k:i + k + 1]):
            out.append((i + k, s.l[i], -1))
    return out


def exit_run(s, j, d, entry, sl, give, hold):
    peak = entry
    for k in range(j, min(j + hold, len(s))):
        if (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl):
            return sl, k
        if k == j:
            continue
        peak = max(peak, s.h[k]) if d > 0 else min(peak, s.l[k])
        up = d * (peak - entry)
        if up > 0:
            c = entry + d * up * (1.0 - give)
            sl = max(sl, c) if d > 0 else min(sl, c)
    kk = min(j + hold, len(s) - 1)
    return s.c[kk], kk


def sig_sweep(s, A, cost, pk=5, sweep_atr=0.10, wick=0.6460, buf=0.30,
              give=0.25, cap=1.2, hold=240, cooldown=5):
    out, busy = [], -1
    for (kb, px, side) in pivots(s, pk):
        if kb <= busy:
            continue
        a = A[kb]
        if not a or a <= 0:
            continue
        t = -side
        need = px + side * sweep_atr * a
        sw, ext = None, None
        for k in range(kb + 1, min(kb + 120, len(s))):
            if (s.h[k] >= need) if side > 0 else (s.l[k] <= need):
                sw, ext = k, (s.h[k] if side > 0 else s.l[k])
                break
        if sw is None:
            continue
        rng = s.h[sw] - s.l[sw]
        if (abs(s.c[sw] - s.o[sw]) / rng if rng > 0 else 1.0) > wick:
            continue
        j = None
        for k in range(sw + 1, min(sw + 120, len(s))):
            if (s.h[k] >= px) if t > 0 else (s.l[k] <= px):
                j = k
                break
            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
        if j is None:
            continue
        entry = px
        sl = ext - t * buf * a
        if abs(entry - sl) > cap * a or abs(entry - sl) <= 0:
            continue
        px_out, kk = exit_run(s, j, t, entry, sl, give, hold)
        out.append(t * (px_out - entry) - cost * A[j])
        busy = kk + cooldown
    return out


def sig_br(s, A, cost, pk=5, brk=0.10, tol=0.20, wait=60, buf=0.30,
           give=0.25, cap=1.2, hold=240, cooldown=5):
    plan = []
    for (kb, px, side) in pivots(s, pk):
        a = A[kb]
        if not a or a <= 0:
            continue
        d = side
        bb = None
        for k in range(kb + 1, min(kb + wait, len(s))):
            if (s.c[k] > px + brk * a) if d > 0 else (s.c[k] < px - brk * a):
                bb = k
                break
        if bb is None:
            continue
        rt = None
        for k in range(bb + 1, min(bb + wait, len(s))):
            if (s.c[k] < px - tol * a) if d > 0 else (s.c[k] > px + tol * a):
                break
            touched = (s.l[k] <= px + tol * a) if d > 0 else (s.h[k] >= px - tol * a)
            held = (s.c[k] > px) if d > 0 else (s.c[k] < px)
            if touched and held:
                rt = k
                break
        if rt is None:
            continue
        trig = s.h[rt] if d > 0 else s.l[rt]
        ext = s.l[rt] if d > 0 else s.h[rt]
        sl = ext - d * buf * a
        if abs(trig - sl) > cap * a or abs(trig - sl) <= 0:
            continue
        j = None
        for k in range(rt + 1, min(rt + wait, len(s))):
            if (s.h[k] >= trig) if d > 0 else (s.l[k] <= trig):
                j = k
                break
            if (s.c[k] < px - tol * a) if d > 0 else (s.c[k] > px + tol * a):
                break
        if j is None:
            continue
        plan.append((j, d, trig, sl))
    plan.sort()
    out, busy = [], -1
    for (j, d, entry, sl) in plan:
        if j <= busy:
            continue
        px_out, kk = exit_run(s, j, d, entry, sl, give, hold)
        out.append(d * (px_out - entry) - cost * A[j])
        busy = kk + cooldown
    return out


def sig_ob(s, A, cost, periods=3, buf=0.30, give=0.25, cap=1.2, life=240,
           hold=240, cooldown=5):
    obp = periods + 1
    plan = []
    for i in range(obp + 1, len(s)):
        c0 = s.c[i - obp]
        if c0 == 0:
            continue
        ups = sum(1 for k in range(1, periods + 1) if s.c[i - k] > s.o[i - k])
        dns = sum(1 for k in range(1, periods + 1) if s.c[i - k] < s.o[i - k])
        j0 = i - obp
        d = 0
        if s.c[j0] < s.o[j0] and ups == periods:
            d, top, bot = 1, s.h[j0], s.l[j0]
        elif s.c[j0] > s.o[j0] and dns == periods:
            d, top, bot = -1, s.h[j0], s.l[j0]
        if d == 0:
            continue
        a = A[i]
        if not a or a <= 0:
            continue
        lvl = top if d > 0 else bot
        far = bot if d > 0 else top
        sl = far - d * buf * a
        if abs(lvl - sl) > cap * a or abs(lvl - sl) <= 0:
            continue
        j = None
        for k in range(i, min(i + life, len(s))):
            if (s.l[k] <= lvl) if d > 0 else (s.h[k] >= lvl):
                j = k
                break
        if j is None:
            continue
        plan.append((j, d, lvl, sl))
    plan.sort()
    out, busy = [], -1
    for (j, d, entry, sl) in plan:
        if j <= busy:
            continue
        px_out, kk = exit_run(s, j, d, entry, sl, give, hold)
        out.append(d * (px_out - entry) - cost * A[j])
        busy = kk + cooldown
    return out


def control(s, A, cost, n, give=0.25, cap=1.2, hold=240, cooldown=5, seed=1):
    """Geometry kept, timing destroyed: same stop distance in ATR, same exit,
    entered at the market on unrelated bars, sorted into time order first."""
    rng = random.Random(seed)
    plan = []
    for _ in range(n):
        j = rng.randrange(50, len(s) - 300)
        a = A[j]
        if not a or a <= 0:
            continue
        d = 1 if rng.random() < 0.5 else -1
        plan.append((j, d, s.c[j], s.c[j] - d * 0.9 * a))
    plan.sort()
    out, busy = [], -1
    for (j, d, entry, sl) in plan:
        if j <= busy:
            continue
        px_out, kk = exit_run(s, j, d, entry, sl, give, hold)
        out.append(d * (px_out - entry) - cost * A[j])
        busy = kk + cooldown
    return out


def main():
    SETS = [("GOLD_15m", "GOLD 15m"), ("GOLD_1h", "GOLD 1h"),
            ("US500_15m", "US500 15m"), ("US500_1h", "US500 1h"),
            ("EURUSD_15m", "EURUSD 15m"), ("GBPUSD_15m", "GBPUSD 15m")]
    print("=" * 96)
    print("  E-146 — the three signals on CURRENT data, four instruments")
    print("  Cost charged as spread/ATR = 0.11 (these files carry no spread")
    print("  column, so it is ASSUMED - the weakest part of this test).")
    print("=" * 96)
    for name, lbl in SETS:
        try:
            s = load(name)
        except Exception as e:
            print(f"  {lbl}: {e}")
            continue
        A = watr(s, 14)
        va = sorted(x for x in A[50:] if x)
        if len(va) < 100:
            continue
        cost = 0.11
        print(f"\n  ---------- {lbl}   {len(s)} bars ----------")
        print(f"  {'signal':<16}{'n':>6}{'win%':>8}{'pts/ATR':>10}"
              f"{'per trade':>12}{'ctrl':>10}{'edge se':>9}")
        print("  " + "-" * 62)
        med = va[len(va) // 2]
        for fn, sname in ((sig_sweep, "SWEEP"), (sig_br, "BREAK+RETEST"),
                          (sig_ob, "ORDER BLOCK")):
            r = fn(s, A, cost)
            if len(r) < 25:
                print(f"  {sname:<16}{len(r):>6}   too few")
                continue
            p = sum(r) / med          # express in ATRs so instruments compare
            pt = p / len(r)
            w = 100.0 * sum(1 for x in r if x > 0) / len(r)
            cs = []
            for sd in range(10):
                cr = control(s, A, cost, len(r), seed=900 + sd)
                if cr:
                    cs.append(sum(cr) / med / len(cr))
            cm = sum(cs) / len(cs)
            cse = (sum((x - cm) ** 2 for x in cs) / (len(cs) - 1)) ** 0.5 / len(cs) ** 0.5
            print(f"  {sname:<16}{len(r):>6}{w:>7.1f}%{p:>10.2f}{pt:>+12.4f}"
                  f"{cm:>+10.4f}{(pt-cm)/cse if cse else 0:>9.1f}")


if __name__ == "__main__":
    main()
