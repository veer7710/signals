"""Out-of-sample check on the exit structures chosen from 160 candidates.
Tune half never sees the test half. 160 cells searched means the in-sample
winner is partly luck; only this table counts."""
import sys, numpy as np
sys.path.insert(0,"research")
import core, backtest as bt, staged
from run_drift import detrend
from run_apex import apex_signals
from run_mtf import split

MODES = {
 "WINRATE  tp1 0.25R f1 0.85 trail3": dict(tp1_R=0.25,f1=0.85,be_at_R=0.0,trail_atr=3.0,arm_R=1.0),
 "BALANCED tp1 0.50R f1 0.60 BE trail3": dict(tp1_R=0.50,f1=0.60,be_at_R=0.50,be_lock_R=0.05,trail_atr=3.0,arm_R=1.0),
 "MAXPROFIT tp1 1.0R f1 0.30 BE trail2": dict(tp1_R=1.0,f1=0.30,be_at_R=1.0,trail_atr=2.0,arm_R=1.0),
 "PURE TRAIL (no partial)":            dict(trail_atr=3.0,arm_R=1.0),
}
for sym,tf in [("GOLD","15m"),("GOLD","1h")]:
    d=detrend(core.load(sym,tf)); ins,oos=split(d)
    print(f"\n{'='*100}\n{sym} {tf}  IN-SAMPLE vs OUT-OF-SAMPLE (structures chosen in-sample)\n{'='*100}")
    print(f"  {'mode':<40}{'half':<6}{'n':>5}{'win%':>7}{'$/trd':>8}{'PF':>6}{'t':>6}{'/day':>7}")
    for name,cfg in MODES.items():
        for lbl,dd in [("IN",ins),("OOS",oos)]:
            sg=apex_signals(dd)
            if len(sg)<15: continue
            days=(dd["t"][-1]-dd["t"][0])/86400*5/7
            t=staged.run_staged(dd,sg,stop_fn=bt.stop_struct(0.25),cfg=cfg,
                                cost=0.15,max_bars=160)
            s=staged.summarise(t,days)
            if s["n"]<10: continue
            mark = "  <--" if lbl=="OOS" else ""
            print(f"  {name if lbl=='IN' else '':<40}{lbl:<6}{s['n']:>5}"
                  f"{100*s['win']:>7.1f}{s['pts']:>8.2f}{s['pf']:>6.2f}"
                  f"{s['t_']:>6.2f}{s['per_day']:>7.2f}{mark}")
