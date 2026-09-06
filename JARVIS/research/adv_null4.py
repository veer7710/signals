"""Is the +0.057 entry artefact an artefact of MY synthetic's tick size, or of
the rule? Refine the tick path (same bar range, 4x and 16x more ticks) and see
whether it shrinks. Then measure the same quantity on the real series."""
import os, sys, math, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_harness as H
from adv_null import synth
from engine import atr as watr

s0, SP0, A0, cs0 = H.ctx("M1")
rr = sorted(s0.h[i] - s0.l[i] for i in range(len(s0)))
med_rng = rr[len(rr) // 2]


def calib(ticks, n=20000):
    sig = med_rng / (2.0 * math.sqrt(ticks))
    for _ in range(12):
        t = synth(n, sig, ticks, 1)
        m = sorted(t.h[i] - t.l[i] for i in range(len(t)))[n // 2]
        sig *= (med_rng / m) ** 0.5
    return sig


def entry_only(s, cand, nbars, at_level=True):
    out, busy = [], -1
    for (j, d, e, sl0, kb, sw) in cand:
        if j <= busy: continue
        kk = min(j + nbars, len(s) - 1)
        px = e if at_level else s.c[j]
        out.append(d * (s.c[kk] - px)); busy = kk + 5
    return out


def m(r):
    n = len(r); mu = sum(r) / n
    sd = (sum((x - mu) ** 2 for x in r) / (n - 1)) ** 0.5
    return n, mu, mu / (sd / n ** 0.5)


NB = 10
print(f"  ENTRY-ONLY test: fill at the level, flat exit {NB} bars later, ZERO cost.")
print(f"  On a driftless walk this must be 0. Bar range held at the real "
      f"median {med_rng:.4f} throughout.\n")
print(f"  {'path':<40}{'tick sd':>10}{'n':>8}{'gross/tr':>12}{'t':>8}")
NBARS = 60000
for ticks in (120, 480, 1920, 7680):
    sig = calib(ticks)
    acc = []
    for sd in range(3):
        ss = synth(NBARS, sig, ticks, 700 + sd)
        AA = watr(ss, 14); SPC = [0.0] * len(ss)
        acc += entry_only(ss, H.sweep_candidates(ss, AA, SPC), NB)
    n, mu, t = m(acc)
    print(f"  {'synthetic, '+str(ticks)+' ticks/bar':<40}{sig:>10.5f}{n:>8}{mu:>+12.5f}{t:>8.2f}")

SPCr = [x * cs0 for x in SP0]
cr = H.sweep_candidates(s0, A0, SPCr)
n, mu, t = m(entry_only(s0, cr, NB, True))
print(f"\n  {'REAL M1 gold, fill AT the level':<40}{'':>10}{n:>8}{mu:>+12.5f}{t:>8.2f}")
n, mu, t = m(entry_only(s0, cr, NB, False))
print(f"  {'REAL M1 gold, fill at trigger bar CLOSE':<40}{'':>10}{n:>8}{mu:>+12.5f}{t:>8.2f}")
