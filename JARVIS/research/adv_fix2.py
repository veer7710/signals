"""The charitable reading: if the market never actually came BACK to the level,
there was no setup. Skip those instead of filling them at the market."""
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_harness as H
from adv_fix import sim


def filt(s, cand, mode):
    out = []
    for t in cand:
        (j, d, e, sl, kb, sw) = t
        beyond = d * (s.o[j] - e) > 0
        if mode == "clean" and beyond: continue
        if mode == "dirty" and not beyond: continue
        out.append(t)
    return out


for tf in ("M1", "M5"):
    s, SP, A, cs = H.ctx(tf)
    SPC = [x * cs for x in SP]
    c = H.sweep_candidates(s, A, SPC)
    nsw = sum(1 for (j, d, e, sl, kb, sw) in c if j == sw + 1)
    beyond = sum(1 for (j, d, e, sl, kb, sw) in c if d * (s.o[j] - e) > 0)
    both = sum(1 for (j, d, e, sl, kb, sw) in c if j == sw + 1 and d * (s.o[j] - e) > 0)
    print(f"\n  {tf}: {len(c)} candidates. entry bar == sweep bar + 1: {nsw} "
          f"({100*nsw/len(c):.0f}%). already past the level at that bar's open: "
          f"{beyond} ({100*beyond/len(c):.0f}%). both: {both} ({100*both/len(c):.0f}%)")
    H.hdr(f"{tf} — split by whether price ACTUALLY returned to the level", 46)
    H.line("as shipped, ALL", sim(s, SPC, c, False, False), 46)
    H.line("as shipped, price really did return", sim(s, SPC, filt(s, c, "clean"), False, False), 46)
    H.line("as shipped, price NEVER left the level", sim(s, SPC, filt(s, c, "dirty"), False, False), 46)
    H.line("ONLY REAL RETURNS, achievable fills", sim(s, SPC, filt(s, c, "clean"), True, True), 46)
