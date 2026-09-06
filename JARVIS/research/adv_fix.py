"""THE ENTRY VERSION OF E-151.

The sweep's entry is an order resting AT the level, filled when the bar's
extreme touches it. But the code never checks that the market is on the
correct side of the level when the order is placed, and never checks that the
bar did not OPEN past it. 66% of M1 entries are booked at a price the market
had already left - the identical defect E-151 fixed on the trail and E-110/E-134
fixed once before on the sweep bar.

The fix is the same one line trail_apply() uses: a fill on the far side of the
market is not a fill. If the bar opens past the level, you get the open.
Applied to the entry AND to the stop (a bar that gaps through a stop fills at
its open, not at the stop)."""
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_harness as H
from engine import trail_level


def sim(s, SPC, cand, honest_entry=True, honest_stop=True, give=0.25,
        hold=240, cooldown=5):
    out, busy = [], -1
    for (j, d, entry, sl0, kb, sw) in cand:
        if j <= busy: continue
        e = entry
        if honest_entry and d * (s.o[j] - entry) > 0:
            # the bar OPENED past the level: the resting order is behind the
            # market and the achievable fill is the open
            e = s.o[j] + d * SPC[j] / 2.0
        sl = sl0
        if (d > 0 and sl >= e) or (d < 0 and sl <= e): continue
        peak = e; px_out = kk = None
        for k in range(j, min(j + hold, len(s))):
            if (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl):
                px_out = sl
                if honest_stop and (d * (s.o[k] - sl) < 0):
                    px_out = s.o[k]          # gapped through: you get the open
                kk = k; break
            if k == j: continue
            peak = max(peak, s.h[k]) if d > 0 else min(peak, s.l[k])
            nsl = trail_level(e, sl, peak, s.c[k], d, give)
            if nsl is None:
                px_out, kk = s.c[k], k; break
            sl = nsl
        if px_out is None:
            kk = min(j + hold, len(s) - 1); px_out = s.c[kk]
        out.append({"pts": d * (px_out - d * SPC[kk] / 2.0 - e), "d": d,
                    "j": j, "kk": kk, "ts": s.ts[j]})
        busy = kk + cooldown
    return out


for tf in ("M1", "M5", "M15"):
    s, SP, A, cs = H.ctx(tf)
    SPC = [x * cs for x in SP]
    c = H.sweep_candidates(s, A, SPC)
    print()
    H.hdr(f"{tf} SWEEP — the entry fill made achievable", 46)
    H.line("AS SHIPPED (E-151 numbers)", sim(s, SPC, c, False, False), 46)
    H.line("+ stop gap-through fills at the open", sim(s, SPC, c, False, True), 46)
    H.line("+ entry gap-through fills at the open", sim(s, SPC, c, True, False), 46)
    H.line("BOTH FIXED - achievable fills", sim(s, SPC, c, True, True), 46)
    r = sim(s, SPC, c, True, True)
    H.line("   of which LONG", [x for x in r if x['d'] > 0], 46)
    H.line("   of which SHORT", [x for x in r if x['d'] < 0], 46)
