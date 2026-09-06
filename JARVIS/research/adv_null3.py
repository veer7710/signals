"""On a driftless walk, E[gross] = 0 for ANY bounded stopping rule (optional
stopping). Split the machinery in half to find which half breaks it."""
import os, sys, random, statistics, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_harness as H
from adv_null import synth
from engine import atr as watr, trail_level

s0, SP0, A0, cs0 = H.ctx("M1")
rr = sorted(s0.h[i] - s0.l[i] for i in range(len(s0)))
med_rng = rr[len(rr) // 2]; ticks = 120
sig = med_rng / (2.0 * math.sqrt(ticks))
for _ in range(14):
    t = synth(20000, sig, ticks, 1)
    m = sorted(t.h[i] - t.l[i] for i in range(len(t)))[10000]
    sig *= (med_rng / m) ** 0.5


def exit_only(s, cand, give=0.25, hold=240):
    """SHIPPED EXIT, but entry is at the trigger bar's CLOSE (a price the bar
    certainly traded, with no intrabar-touch assumption)."""
    out, busy = [], -1
    for (j, d, _e, sl0, kb, sw) in cand:
        if j <= busy: continue
        entry = s.c[j]
        sl = sl0
        if (d > 0 and sl >= entry) or (d < 0 and sl <= entry): continue
        peak = entry; px_out = kk = None
        for k in range(j + 1, min(j + 1 + hold, len(s))):
            if (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k; break
            peak = max(peak, s.h[k]) if d > 0 else min(peak, s.l[k])
            nsl = trail_level(entry, sl, peak, s.c[k], d, give)
            if nsl is None:
                px_out, kk = s.c[k], k; break
            sl = nsl
        if px_out is None:
            kk = min(j + 1 + hold, len(s) - 1); px_out = s.c[kk]
        out.append(d * (px_out - entry)); busy = kk + 5
    return out


def entry_only(s, cand, nbars=10):
    """SHIPPED ENTRY (fill AT the level on the touch bar), exit unconditionally
    at the close nbars later. No trail, no stop, nothing to blame but the fill."""
    out, busy = [], -1
    for (j, d, _e, sl0, kb, sw) in cand:
        if j <= busy: continue
        kk = min(j + nbars, len(s) - 1)
        px = _e   # the shipped entry price includes half-spread; strip it
        out.append(d * (s.c[kk] - px)); busy = kk + 5
    return out


def entry_only_close(s, cand, nbars=10):
    """Same, but entered at the trigger bar's CLOSE instead of at the level."""
    out, busy = [], -1
    for (j, d, _e, sl0, kb, sw) in cand:
        if j <= busy: continue
        kk = min(j + nbars, len(s) - 1)
        out.append(d * (s.c[kk] - s.c[j])); busy = kk + 5
    return out


def m(r):
    n = len(r); mu = sum(r) / n
    sd = (sum((x - mu) ** 2 for x in r) / (n - 1)) ** 0.5
    return n, mu, mu / (sd / n ** 0.5)


print("  DRIFTLESS RANDOM WALK — 4 series of 157,051 bars. Zero-cost GROSS points/trade.")
print("  Optional stopping says every line below must be 0 within noise.\n")
print(f"  {'component':<52}{'n':>8}{'gross/tr':>12}{'t':>8}")
acc = {k: [] for k in ("full", "exit", "e5", "e10", "e60", "c10")}
for sd in range(4):
    ss = synth(len(s0), sig, ticks, 300 + sd)
    AA = watr(ss, 14); SPC = [0.0] * len(ss)          # ZERO COST: pure geometry
    c = H.sweep_candidates(ss, AA, SPC)
    acc["full"] += [x["pts"] for x in H.simulate(ss, SPC, c)]
    acc["exit"] += exit_only(ss, c)
    acc["e5"] += entry_only(ss, c, 5)
    acc["e10"] += entry_only(ss, c, 10)
    acc["e60"] += entry_only(ss, c, 60)
    acc["c10"] += entry_only_close(ss, c, 10)
LAB = [("full", "SHIPPED: level fill + give-back trail + stop"),
       ("exit", "EXIT ONLY: entry at the trigger bar's CLOSE, shipped exit"),
       ("e5", "ENTRY ONLY: fill AT the level, flat exit 5 bars later"),
       ("e10", "ENTRY ONLY: fill AT the level, flat exit 10 bars later"),
       ("e60", "ENTRY ONLY: fill AT the level, flat exit 60 bars later"),
       ("c10", "ENTRY at the trigger bar's CLOSE, flat exit 10 bars later")]
for k, lbl in LAB:
    n, mu, t = m(acc[k])
    print(f"  {lbl:<52}{n:>8}{mu:>+12.5f}{t:>8.2f}")
