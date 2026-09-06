"""The entry is a STOP order (price is beyond the level and comes BACK to it),
not a limit. The trigger bar overshoots the level by ~0.21 pts (0.87 ATR) on M1.
The shipped model fills at the level with zero slippage. How much of that
overshoot can you pay before the edge is gone?"""
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_harness as H
from engine import trail_level


def sim(s, SPC, cand, frac=0.0, ticks=0.0, give=0.25, hold=240, cooldown=5):
    out, busy = [], -1
    for (j, d, entry, sl0, kb, sw) in cand:
        if j <= busy: continue
        over = d * ((s.h[j] if d > 0 else s.l[j]) - entry)
        e = entry + d * (max(0.0, over) * frac + ticks)
        sl = sl0
        if (d > 0 and sl >= e) or (d < 0 and sl <= e): continue
        peak = e; px_out = kk = None
        for k in range(j, min(j + hold, len(s))):
            if (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k; break
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


for tf in ("M1", "M5"):
    s, SP, A, cs = H.ctx(tf)
    SPC = [x * cs for x in SP]
    c = H.sweep_candidates(s, A, SPC)
    ov = [abs((s.h[j] if d > 0 else s.l[j]) - e) for (j, d, e, sl, kb, sw) in c]
    print()
    print(f"  {tf}: mean overshoot of the trigger bar past the entry level "
          f"= {sum(ov)/len(ov):.4f} pts")
    H.hdr(f"{tf} — paying a FRACTION of the overshoot on the stop entry", 40)
    for f in (0.0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 1.00):
        H.line(f"pay {100*f:.0f}% of the overshoot", sim(s, SPC, c, frac=f), 40)
    print()
    H.hdr(f"{tf} — flat entry slippage in cents", 40)
    for t in (0.0, 0.01, 0.02, 0.03, 0.05, 0.07, 0.10):
        H.line(f"{100*t:.0f} cents adverse on entry", sim(s, SPC, c, ticks=t), 40)
