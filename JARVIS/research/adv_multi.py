"""E-146 re-run with two controls the original never had:
   (a) FAKE LEVEL  - same machinery, level replaced by an unrelated old close
   (b) NEXT-OPEN FILL - engine.py's own stated no-look-ahead entry rule"""
import os, sys, random, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, trail_level
from multi_market import load, pivots, exit_run

SETS = [("GOLD_15m", "GOLD 15m"), ("GOLD_1h", "GOLD 1h"), ("US500_15m", "US500 15m"),
        ("US500_1h", "US500 1h"), ("EURUSD_15m", "EURUSD 15m"), ("GBPUSD_15m", "GBPUSD 15m")]


def sweep(s, A, cost, mode="real", seed=0, fill="level", pk=5, sweep_atr=0.10,
          wick=0.6460, buf=0.30, give=0.25, cap=1.2, hold=240, cooldown=5):
    rng = random.Random(500 + seed)
    out, busy = [], -1
    piv = pivots(s, pk)
    if mode == "fake":
        piv = [(kb, s.c[max(0, kb - rng.randrange(1, 120))], sd) for (kb, _, sd) in piv]
    for (kb, px, side) in piv:
        if kb <= busy:
            continue
        a = A[kb]
        if not a or a <= 0:
            continue
        t = -side
        need = px + side * sweep_atr * a
        sw = ext = None
        for k in range(kb + 1, min(kb + 120, len(s))):
            if (s.h[k] >= need) if side > 0 else (s.l[k] <= need):
                sw, ext = k, (s.h[k] if side > 0 else s.l[k]); break
        if sw is None: continue
        rg = s.h[sw] - s.l[sw]
        if (abs(s.c[sw] - s.o[sw]) / rg if rg > 0 else 1.0) > wick: continue
        j = None
        for k in range(sw + 1, min(sw + 120, len(s))):
            if (s.h[k] >= px) if t > 0 else (s.l[k] <= px):
                j = k; break
            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
        if j is None: continue
        entry = px
        sl = ext - t * buf * a
        if abs(entry - sl) > cap * a or abs(entry - sl) <= 0: continue
        j0 = j
        if fill == "next_open":
            if j + 1 >= len(s): continue
            j0 = j + 1; entry = s.o[j0]
            if (t > 0 and sl >= entry) or (t < 0 and sl <= entry): continue
        px_out, kk = exit_run(s, j0, t, entry, sl, give, hold)
        out.append((t * (px_out - entry) - cost * A[j]) / A[j])
        busy = kk + cooldown
    return out


def stat(r):
    n = len(r)
    if n < 5: return None
    m = sum(r) / n
    sd = (sum((x - m) ** 2 for x in r) / (n - 1)) ** 0.5
    return n, m, (m / (sd / n ** 0.5) if sd else 0)


print("  E-146 SWEEP re-run. per-trade in ATRs, cost 0.11 ATR, params unchanged.")
print(f"  {'set':<13}{'REAL n':>8}{'REAL/tr':>10}{'t':>7} | {'FAKE-LEVEL/tr (6 seeds)':>25}"
      f"{'gap':>9}{'ctl se':>8} | {'NEXT-OPEN n':>13}{'/tr':>9}{'t':>7}")
print("  " + "-" * 118)
for f, lbl in SETS:
    s = load(f); A = watr(s, 14)
    R = stat(sweep(s, A, 0.11))
    fk = [stat(sweep(s, A, 0.11, mode="fake", seed=i)) for i in range(6)]
    fk = [x for x in fk if x]
    fm = sum(x[1] for x in fk) / len(fk)
    fse = (sum((x[1] - fm) ** 2 for x in fk) / (len(fk) - 1)) ** 0.5 / len(fk) ** 0.5
    NO = stat(sweep(s, A, 0.11, fill="next_open"))
    print(f"  {lbl:<13}{R[0]:>8}{R[1]:>+10.4f}{R[2]:>7.1f} | {fm:>25.4f}"
          f"{R[1]-fm:>+9.4f}{(R[1]-fm)/fse if fse else 0:>8.1f} | "
          f"{NO[0]:>13}{NO[1]:>+9.4f}{NO[2]:>7.1f}")
