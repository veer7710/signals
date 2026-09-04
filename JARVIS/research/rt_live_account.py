import json,random,statistics
RM=json.load(open('/home/user/signals/JARVIS/research/findings/RM.json'))
GBP_PT=0.787

def run(start=60.0, stop_pts=4.40, days=9, trades_per_day=6,
        daily_pct=3.0, dd_pct=6.0, guards=True, trials=20000, seed=7,
        mean_shift=0.0):
    rng=random.Random(seed)
    risk=stop_pts*GBP_PT
    ends=[];permlock=0;daylock_days=0;tot_days=0;ntr=[]
    for _ in range(trials):
        eq=start; peak=start; locked=False; trades=0
        for d in range(days):
            dstart=eq; dloss_allow=dstart*daily_pct/100.0
            if locked: break
            st=rng.randrange(len(RM)); k=0
            for t in range(trades_per_day):
                r,mae=RM[(st+k)%len(RM)]; k+=1
                r=r+mean_shift
                if k%5==0: st=rng.randrange(len(RM))
                rem=dloss_allow-(dstart-eq)
                if rem<=0: break
                gR=-rem/risk           # R at which the daily guard flattens
                if guards and mae<=gR:
                    pnl=gR*risk         # flattened at the guard
                else:
                    pnl=r*risk
                    # perm-lock can also flatten intraday
                    if guards:
                        permR=-(peak*(1-dd_pct/100.0)-eq)/risk*-1
                        pass
                eq+=pnl; trades+=1
                peak=max(peak,eq)
                if guards and eq<=peak*(1-dd_pct/100.0):
                    locked=True; permlock+=1; break
                if guards and (dstart-eq)>=dloss_allow: break
            tot_days+=1
            if locked: break
        ends.append(eq); ntr.append(trades)
    ends.sort()
    return dict(median=ends[len(ends)//2],
                p5=ends[int(0.05*len(ends))], p95=ends[int(0.95*len(ends))],
                pct_hit260=100.0*sum(1 for e in ends if e>=260)/len(ends),
                pct_permlock=100.0*permlock/trials,
                pct_below_start=100.0*sum(1 for e in ends if e<start)/len(ends),
                mean_trades=statistics.mean(ntr))

print("="*100)
print("  LIVE SIM: 60 GBP, 0.01 lots fixed, XAUUSD M1, 9 trading days, target 260")
print("  R/MAE distribution = SuperTrendSniper's own shipped exit stack, GOLD 15m (n=112, +0.181R)")
print("="*100)
for label,kw in [
  ("GUARDS ON  (InpDailyLossPct=3, InpMaxDDPct=6)  as shipped", dict(guards=True)),
  ("GUARDS OFF (hypothetical: both set to 100)",                 dict(guards=False)),
]:
    print("\n  "+label)
    print(f"   {'stop pts':>9}{'risk GBP':>10}{'risk %':>8}{'trades/day':>11}"
          f"{'median end':>12}{'5th':>8}{'95th':>8}{'P(>=260)':>10}{'P(perm lock)':>14}{'P(end<60)':>11}{'avg trades':>11}")
    print("   "+"-"*112)
    for stop in (2.72,4.40,5.45):
        for tpd in (3,6,12):
            r=run(stop_pts=stop,trades_per_day=tpd,**kw)
            print(f"   {stop:>9.2f}{stop*GBP_PT:>10.2f}{100*stop*GBP_PT/60:>7.1f}%{tpd:>11}"
                  f"{r['median']:>12.2f}{r['p5']:>8.2f}{r['p95']:>8.2f}{r['pct_hit260']:>9.2f}%"
                  f"{r['pct_permlock']:>13.1f}%{r['pct_below_start']:>10.1f}%{r['mean_trades']:>11.1f}")

print("\n\n  SAME, BUT AT E-089's HONEST M1 EXPECTANCY (+0.041R instead of +0.181R)")
print(f"   {'stop pts':>9}{'trades/day':>11}{'median end':>12}{'P(>=260)':>10}{'P(perm lock)':>14}{'P(end<60)':>11}")
print("   "+"-"*70)
for stop in (4.40,):
    for tpd in (3,6,12):
        r=run(stop_pts=stop,trades_per_day=tpd,guards=True,mean_shift=-0.140)
        print(f"   {stop:>9.2f}{tpd:>11}{r['median']:>12.2f}{r['pct_hit260']:>9.2f}%{r['pct_permlock']:>13.1f}%{r['pct_below_start']:>10.1f}%")
