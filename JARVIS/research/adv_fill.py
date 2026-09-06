"""Is the edge the LEVEL, the DIRECTION, or the intrabar FILL CONVENTION?
Same candidates, only the entry fill changes."""
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_harness as H
from adv_control import cand_variant


def simulate_fill(s, SPC, cand, fillmode, give=0.25, hold=240, cooldown=5):
    out, busy = [], -1
    for (j, d, entry, sl0, kb, sw) in cand:
        if j <= busy:
            continue
        j0 = j
        if fillmode == "level":
            e = entry
        elif fillmode == "next_open":
            if j + 1 >= len(s): continue
            j0 = j + 1
            e = s.o[j0] + d * SPC[j0] / 2.0
        elif fillmode == "trigger_close":
            e = s.c[j] + d * SPC[j] / 2.0
        elif fillmode == "level_plus_1tick":       # 1 cent of adverse fill
            e = entry + d * 0.01
        sl = sl0
        if (d > 0 and sl >= e) or (d < 0 and sl <= e):
            continue
        peak = e; px_out = kk = None
        for k in range(j0, min(j0 + hold, len(s))):
            if (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k; break
            if k == j0:
                continue
            peak = max(peak, s.h[k]) if d > 0 else min(peak, s.l[k])
            from engine import trail_level
            nsl = trail_level(e, sl, peak, s.c[k], d, give)
            if nsl is None:
                px_out, kk = s.c[k], k; break
            sl = nsl
        if px_out is None:
            kk = min(j0 + hold, len(s) - 1); px_out = s.c[kk]
        out.append({"pts": d * ((px_out - d * SPC[kk] / 2.0) - e), "d": d,
                    "j": j, "kk": kk, "ts": s.ts[j], "risk": abs(e - sl0)})
        busy = kk + cooldown
    return out


for tf in ("M1", "M5"):
    s, SP, A, cs = H.ctx(tf)
    SPC = [x * cs for x in SP]
    print()
    H.hdr(f"{tf} — SAME setups, only the ENTRY FILL changes", 44)
    for mode, lbl in (("level", "fill AT the level (as shipped)"),
                      ("level_plus_1tick", "level + 1 cent adverse"),
                      ("trigger_close", "close of the trigger bar"),
                      ("next_open", "open of the NEXT bar (engine.py rule)")):
        H.line("REAL   " + lbl, simulate_fill(s, SPC, cand_variant(s, A, SPC, "real"), mode), 44)
    for mode, lbl in (("level", "fill AT the level"),
                      ("next_open", "open of the NEXT bar")):
        H.line("FAKE-LEVEL " + lbl, simulate_fill(s, SPC, cand_variant(s, A, SPC, "fakepivot", seed=0), mode), 44)
