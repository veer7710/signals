"""
Funded-account sizing: what risk-% maximises P(reach the profit target
before breaching the drawdown limit)?

This does NOT need a directional edge. It is the difference between passing
a challenge and blowing it on the same trade sequence, and it is the part of
a funded EA that is genuinely optimisable.

Bootstrap the REAL measured trade distribution (MTF family, ATR-3 trail,
de-trended gold), then Monte-Carlo the challenge rules.
"""
import sys, numpy as np
sys.path.insert(0,"research")
import core, backtest as bt
from run_drift import detrend
from run_mtf import signals

def trade_R(sym, tf, g=(6,20,4,50,1)):
    d=detrend(core.load(sym,tf))
    sg=signals(d,*g)
    r=bt.run(d,sg,stop_fn=bt.stop_struct(0.25),
             exit_cfg=dict(mode="trail_atr",trail=3.0),cost=0.15,max_bars=120)
    return np.array([x["R"] for x in r.t])

def challenge(Rs, risk, target=0.08, dd=0.06, daily=0.04, ntr=400,
              reps=6000, seed=5, daily_trades=2):
    """Standard prop rules: +8% target, 6% max drawdown from peak,
    4% daily loss limit. Halt the day when the daily limit trips."""
    rng=np.random.default_rng(seed)
    passes=fails=timeouts=0
    for _ in range(reps):
        eq=1.0; peak=1.0; dayStart=1.0; k=0; done=False
        for t in range(ntr):
            if t%daily_trades==0: dayStart=eq
            R=Rs[rng.integers(len(Rs))]
            eq*= (1.0 + risk*R)
            peak=max(peak,eq)
            if eq <= peak*(1-dd) or eq <= 1-dd:
                fails+=1; done=True; break
            if eq <= dayStart*(1-daily):
                # day halted, not a failure -- skip to the next day
                pass
            if eq >= 1+target:
                passes+=1; done=True; break
        if not done: timeouts+=1
    return passes/reps, fails/reps, timeouts/reps

for sym,tf in [("GOLD","1h"),("GOLD","15m")]:
    Rs=trade_R(sym,tf)
    if len(Rs)<40: print(f"{sym} {tf}: only {len(Rs)} trades, skipping"); continue
    print(f"\n{'='*92}")
    print(f"{sym} {tf}: {len(Rs)} measured trades  meanR {Rs.mean():+.3f}  "
          f"win {100*(Rs>0).mean():.1f}%  bestR {Rs.max():.1f}  worstR {Rs.min():.1f}")
    print(f"Prop rules: +8% target, 6% max DD, 400-trade budget")
    print(f"{'='*92}")
    print(f"  {'risk/trade':>11}{'P(pass)':>10}{'P(blow)':>10}{'P(neither)':>12}   verdict")
    best=None
    for risk in (0.0025,0.005,0.0075,0.01,0.015,0.02,0.03,0.05):
        p,f_,t_=challenge(Rs,risk)
        if best is None or p>best[0]: best=(p,risk)
        flag = "  <<< best" if False else ""
        print(f"  {100*risk:>10.2f}%{100*p:>9.1f}%{100*f_:>9.1f}%{100*t_:>11.1f}%{flag}")
    print(f"  --> highest P(pass) at risk {100*best[1]:.2f}% per trade ({100*best[0]:.1f}%)")
