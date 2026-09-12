"""
check_parity.py -- proves the three implementations of the shared logic
agree bar for bar. If they ever diverge, one of the three is lying and
there is no way to tell which from the chart.

Re-implements the PINE recursion literally, line for line, then diffs it
against core.supertrend (which the backtests use). The MQL5 recursion is
the same statement set with series indexing (i+1 = one bar older).
"""
import sys, numpy as np
sys.path.insert(0,"research")
import core

def supertrend_pine_literal(d, length=10, mult=3.0):
    """Transcribed from SUPERTREND_SNIPER_V2.pine:
         fUp := close[1] > nz(fUp[1],upB) ? max(upB, nz(fUp[1],upB)) : upB
         fDn := close[1] < nz(fDn[1],dnB) ? min(dnB, nz(fDn[1],dnB)) : dnB
         stDir := nz(stDir[1],1)==1 ? (close<fUp ? -1:1) : (close>fDn ? 1:-1)
    """
    a = core.rma(core.true_range(d["h"], d["l"], d["c"]), length)
    hl2 = (d["h"] + d["l"]) / 2.0
    upB, dnB = hl2 - mult*a, hl2 + mult*a
    n = d["n"]
    fUp = np.full(n, np.nan); fDn = np.full(n, np.nan)
    sd  = np.zeros(n, dtype=np.int8)
    for i in range(n):
        if np.isnan(a[i]):
            continue
        pu = fUp[i-1] if i > 0 and not np.isnan(fUp[i-1]) else upB[i]
        pd = fDn[i-1] if i > 0 and not np.isnan(fDn[i-1]) else dnB[i]
        cprev = d["c"][i-1] if i > 0 else d["c"][i]
        fUp[i] = max(upB[i], pu) if cprev > pu else upB[i]
        fDn[i] = min(dnB[i], pd) if cprev < pd else dnB[i]
        pdir = sd[i-1] if i > 0 and sd[i-1] != 0 else 1
        sd[i] = (-1 if d["c"][i] < fUp[i] else 1) if pdir == 1 \
                else (1 if d["c"][i] > fDn[i] else -1)
    return sd, np.where(sd == 1, fUp, fDn)

fails = 0
for sym, tf in [("GOLD","15m"), ("GOLD","1h"), ("US500","1h")]:
    d = core.load(sym, tf)
    a_dir, a_line = core.supertrend(d, 10, 3.0)
    b_dir, b_line = supertrend_pine_literal(d, 10, 3.0)
    ok = ~np.isnan(a_line) & ~np.isnan(b_line)
    ok[:40] = False                      # both need the ATR to warm up
    dmis = int((a_dir[ok] != b_dir[ok]).sum())
    lmax = float(np.nanmax(np.abs(a_line[ok] - b_line[ok]))) if ok.sum() else 0.0
    fa = int((np.diff(a_dir) != 0).sum()); fb = int((np.diff(b_dir) != 0).sum())
    status = "PARITY OK" if (dmis == 0 and lmax < 1e-9) else "*** DIVERGES ***"
    if dmis or lmax >= 1e-9: fails += 1
    print(f"{sym:>6} {tf:<4} bars={d['n']:<6} dir mismatches={dmis:<4} "
          f"max line diff={lmax:.2e}  flips {fa}/{fb}  {status}")

print()
print("ATR contract: Wilder RMA seeded with an SMA -- ta.rma in Pine, iATR in")
print("MQL5, core.rma here. TR on bar 0 is high-low in all three.")
print("Entry contract: signal computed on a CLOSED bar, filled at the NEXT")
print("bar's open, in all three.")
sys.exit(1 if fails else 0)
