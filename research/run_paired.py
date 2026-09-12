import sys, numpy as np
sys.path.insert(0,"research")
import core, backtest as bt
from run_drift import detrend
from run_exits import all_entries, EXITS
from run_decisive import tstat, boot_ci

def pts_by_entry(d, sig, cfg):
    """Map entry-bar -> pnl, so two exits can be compared TRADE BY TRADE."""
    r = bt.run(d, sig, stop_fn=bt.stop_struct(0.25), exit_cfg=cfg,
               cost=0.15, max_bars=120, one_at_a_time=False)
    return {x["i"]: x["pts"] for x in r.t}

print("="*100)
print("PAIRED TEST -- same entry, two exits. Difference tested trade by trade.")
print("Paired removes entry noise entirely, so this is the powerful test.")
print("="*100)
BASE = "giveback 60% (CURRENT SNIPER)"
for sym,tf in [("GOLD","1h"),("GOLD","15m")]:
    d = detrend(core.load(sym,tf)); sig = all_entries(d)
    base = pts_by_entry(d, sig, EXITS[BASE])
    print(f"\n--- {sym} {tf}: {len(base)} paired trades vs '{BASE}' ---")
    print(f"  {'alternative exit':<32}{'mean diff $':>13}{'t(paired)':>11}"
          f"{'CI95 of diff':>22}{'better%':>9}")
    rows=[]
    for name,cfg in EXITS.items():
        if name==BASE: continue
        alt = pts_by_entry(d, sig, cfg)
        keys = sorted(set(base) & set(alt))
        if len(keys) < 30: continue
        diff = np.array([alt[k]-base[k] for k in keys])
        lo,hi = boot_ci(diff)
        rows.append((diff.mean(), name, tstat(diff), lo, hi,
                     float((diff>0).mean()), len(keys)))
    for m,name,t_,lo,hi,bp,nk in sorted(rows, reverse=True):
        sig_flag = "  SIGNIFICANT" if lo>0 else ("  (negative)" if hi<0 else "")
        print(f"  {name:<32}{m:>13.2f}{t_:>11.2f}"
              f"   [{lo:>7.2f},{hi:>7.2f}]{100*bp:>8.0f}%{sig_flag}")

print("\n"+"="*100)
print("COST / FREQUENCY FRONTIER -- why 'hundreds of trades a day' is the problem")
print("="*100)
print("0.01 lot XAUUSD = 1oz; $1 of gold price = $1 P/L = about GBP 0.787")
print(f"\n  {'target':>8}{'spread':>9}{'cost/gross':>12}{'BE win% @1:1':>14}"
      f"{'net/day @50 trd':>17}{'net/day @300 trd':>18}")
for targ in (1,2,3,5,10,20):
    for spr in (0.20, 0.35):
        cost = spr + 0.05          # spread + slippage, round trip, in $
        be = (targ+cost)/(2*targ)
        # net per day at a REALISTIC 52% win rate on a 1:1 geometry
        p = 0.52
        edge = p*targ - (1-p)*targ - cost
        print(f"  {targ:>7}${spr:>8.2f}{100*cost/targ:>11.0f}%{100*be:>13.1f}%"
              f"{edge*50*0.787:>16.2f}{edge*300*0.787:>17.2f}")
