"""E-146's six cells, with the achievable entry fill."""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, trail_level
from multi_market import load, pivots, exit_run

SETS = [("GOLD_15m", "GOLD 15m"), ("GOLD_1h", "GOLD 1h"), ("US500_15m", "US500 15m"),
        ("US500_1h", "US500 1h"), ("EURUSD_15m", "EURUSD 15m"), ("GBPUSD_15m", "GBPUSD 15m")]


def sweep(s, A, cost, honest=False, pk=5, sweep_atr=0.10, wick=0.6460, buf=0.30,
          give=0.25, cap=1.2, hold=240, cooldown=5):
    out, busy = [], -1
    nbeyond = 0
    for (kb, px, side) in pivots(s, pk):
        if kb <= busy: continue
        a = A[kb]
        if not a or a <= 0: continue
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
        if t * (s.o[j] - px) > 0:
            nbeyond += 1
            if honest: entry = s.o[j]
        sl = ext - t * buf * a
        if abs(entry - sl) > cap * a or abs(entry - sl) <= 0: continue
        px_out, kk = exit_run(s, j, t, entry, sl, give, hold)
        out.append((t * (px_out - entry) - cost * A[j]) / A[j])
        busy = kk + cooldown
    return out, nbeyond


def stat(r):
    n = len(r); m = sum(r) / n
    sd = (sum((x - m) ** 2 for x in r) / (n - 1)) ** 0.5
    return n, m, m / (sd / n ** 0.5)


print("  E-146's six cells, per-trade in ATRs, cost 0.11 ATR.")
print(f"  {'set':<13}{'n':>6}{'% entries booked below the market':>36}"
      f"{'SHIPPED/tr':>13}{'t':>7}{'ACHIEVABLE/tr':>16}{'t':>7}")
print("  " + "-" * 100)
for f, lbl in SETS:
    s = load(f); A = watr(s, 14)
    r0, nb = sweep(s, A, 0.11, False)
    r1, _ = sweep(s, A, 0.11, True)
    a = stat(r0); b = stat(r1)
    print(f"  {lbl:<13}{a[0]:>6}{100*nb/max(1,a[0]):>35.0f}%"
          f"{a[1]:>+13.4f}{a[2]:>7.1f}{b[1]:>+16.4f}{b[2]:>7.1f}")
