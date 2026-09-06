"""Where does a MARTINGALE make money? By optional stopping, gross expectancy
of any bounded stopping rule on a driftless walk is EXACTLY ZERO. Anything
non-zero is a fill the path did not offer. Decompose by exit reason."""
import os, sys, random, statistics, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_harness as H
from adv_null import synth
from engine import atr as watr, trail_level


def sim(s, SPC, cand, give=0.25, hold=240, cooldown=5, check=True):
    out, busy = [], -1
    bad = 0
    for (j, d, entry, sl0, kb, sw) in cand:
        if j <= busy: continue
        sl = sl0; peak = entry; px_out = kk = None; why = None
        for k in range(j, min(j + hold, len(s))):
            if (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl):
                px_out, kk, why = sl, k, "stop"; break
            if k == j: continue
            peak = max(peak, s.h[k]) if d > 0 else min(peak, s.l[k])
            nsl = trail_level(entry, sl, peak, s.c[k], d, give)
            if nsl is None:
                px_out, kk, why = s.c[k], k, "trailclose"; break
            sl = nsl
        if px_out is None:
            kk = min(j + hold, len(s) - 1); px_out = s.c[kk]; why = "time"
        if check and not (s.l[kk] - 1e-9 <= px_out <= s.h[kk] + 1e-9):
            bad += 1
        out.append({"g": d * (px_out - entry), "why": why, "d": d, "kk": kk,
                    "hold": kk - j, "pts": d * (px_out - d * SPC[kk] / 2.0 - entry)})
        busy = kk + cooldown
    return out, bad


def report(tag, r, bad):
    n = len(r); g = sum(x["g"] for x in r) / n
    print(f"\n  {tag}: n={n}  GROSS/trade {g:+.5f}  NET/trade "
          f"{sum(x['pts'] for x in r)/n:+.5f}   fills outside the exit bar's range: {bad}")
    print(f"    {'exit reason':<14}{'n':>6}{'share':>8}{'gross/tr':>11}{'total gross':>13}{'avg bars':>10}")
    for w in ("stop", "trailclose", "time"):
        b = [x for x in r if x["why"] == w]
        if not b: continue
        print(f"    {w:<14}{len(b):>6}{100*len(b)/n:>7.1f}%"
              f"{sum(x['g'] for x in b)/len(b):>+11.5f}{sum(x['g'] for x in b):>13.2f}"
              f"{sum(x['hold'] for x in b)/len(b):>10.1f}")


s, SP, A, cs = H.ctx("M1")
SPC0 = [x * cs for x in SP]
med_sp = statistics.median(SPC0)
rr = sorted(s.h[i] - s.l[i] for i in range(len(s)))
med_rng = rr[len(rr) // 2]
ticks = 120
sig = med_rng / (2.0 * math.sqrt(ticks))
for _ in range(14):
    t = synth(20000, sig, ticks, 1)
    m = sorted(t.h[i] - t.l[i] for i in range(len(t)))[10000]
    sig *= (med_rng / m) ** 0.5

print("=" * 92)
print("  DRIFTLESS RANDOM WALK. Gross expectancy of ANY bounded stopping rule = 0 exactly.")
print("=" * 92)
for give, lbl in ((0.25, "give-back 0.25 (shipped)"), (0.0, "NO TRAIL - stop + 240-bar timeout only")):
    allr, allbad = [], 0
    for sd in range(4):
        ss = synth(len(s), sig, ticks, 100 + sd)
        AA = watr(ss, 14); SPC = [med_sp] * len(ss)
        r, bad = sim(ss, SPC, H.sweep_candidates(ss, AA, SPC), give=give)
        allr += r; allbad += bad
    report("SYNTH  " + lbl, allr, allbad)

print("\n" + "=" * 92)
print("  and the same decomposition on the REAL series")
print("=" * 92)
for give, lbl in ((0.25, "give-back 0.25 (shipped)"), (0.0, "NO TRAIL")):
    r, bad = sim(s, SPC0, H.sweep_candidates(s, A, SPC0), give=give)
    report("REAL   " + lbl, r, bad)
