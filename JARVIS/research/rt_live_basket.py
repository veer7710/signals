import sys,statistics
sys.path.insert(0,'/home/user/signals/JARVIS/research')
import engine
from engine import atr as watr
from pine_ea_parity import ea_supertrend_at, ea_dema_at
ATRL,MULT,DEMAL,WARM=7,1.2,200,400
GBP_PT=0.787

def run(sym="GOLD",tf="15m",spread=0.30,stop_atr=2.0,trail=3.0,maxbars=50,
        arm=1.0, eq=60.0, lots=0.01, basket=True, daily=True, intrabar=True,
        bk_arm_pct=0.40, bk_min=1.00, bk_give=0.20, daily_pct=3.0):
    s=engine.load(sym,tf); A=watr(s,ATRL); n=len(s)
    start=max(WARM+10,DEMAL*4+20); R=[];busy=-1
    gbp_pt = GBP_PT*(lots/0.01)
    bk_arm = min(max(eq*bk_arm_pct/100.0, 0.25), bk_min)
    day_lim = eq*daily_pct/100.0
    tags={}
    for i in range(start,n-1):
        if i<=busy: continue
        d,dp=ea_supertrend_at(s,i,ATRL,MULT,WARM)
        up,dn=d==-1 and dp==1, d==1 and dp==-1
        if not(up or dn): continue
        side=1 if up else -1
        en,ep=ea_dema_at(s,i,DEMAL,1),ea_dema_at(s,i,DEMAL,3)
        if en is None or ep is None: continue
        if (side>0 and en<ep) or (side<0 and en>ep): continue
        a=A[i]
        if not a or a<=0: continue
        entry=s.o[i+1]+side*spread/2.0
        risk=stop_atr*a; stop=entry-side*risk
        peak,i_out,px,mfe=entry,None,None,0.0
        bkpeak=0.0; tag=None
        for j in range(i+1,min(i+1+maxbars,n)):
            fav = s.h[j] if side>0 else s.l[j]
            adv = s.l[j] if side>0 else s.h[j]
            # daily-loss guard: floating loss vs day limit
            if daily:
                adv_money = side*(adv-entry)*gbp_pt
                if adv_money <= -day_lim:
                    i_out=j; px=entry-side*(day_lim/gbp_pt); tag="dailyguard"; break
            if (side>0 and s.l[j]<=stop) or (side<0 and s.h[j]>=stop):
                i_out,px=j,stop-side*spread/2.0; tag="stop"; break
            if basket:
                fav_money = side*(fav-entry)*gbp_pt
                if fav_money>bkpeak: bkpeak=fav_money
                if bkpeak>=bk_arm:
                    floor=bkpeak*(1.0-bk_give)
                    chk = (adv if intrabar else s.c[j])
                    chk_money = side*(chk-entry)*gbp_pt
                    if chk_money<=floor:
                        i_out=j; px=entry+side*(floor/gbp_pt); tag="basket"; break
            peak=max(peak,s.h[j]) if side>0 else min(peak,s.l[j])
            mfe=max(mfe,side*(peak-entry)/risk)
            t=peak-side*trail*a
            stop=max(stop,t) if side>0 else min(stop,t)
            if mfe>=arm:
                allow=0.20
                if mfe>=1.5: allow=0.16
                if mfe>=3.0: allow=0.12
                gb=entry+side*(peak-entry)*(1.0-allow)
                stop=max(stop,gb) if side>0 else min(stop,gb)
        if i_out is None:
            i_out=min(i+maxbars,n-1); px=s.c[i_out]-side*spread/2.0; tag="timecap"
        r=side*(px-entry)/risk
        R.append((r, risk))
        tags[tag]=tags.get(tag,0)+1
        busy=i_out
    return R,tags,bk_arm,day_lim

def report(label,**kw):
    R,tags,bk_arm,day_lim=run(**kw)
    rs=[x[0] for x in R]
    money=[x[0]*x[1]*GBP_PT for x in R]
    n=len(rs)
    print(f"\n  {label}")
    print(f"    basket arms at GBP{bk_arm:.2f}   daily guard at GBP{day_lim:.2f}")
    print(f"    n={n}  meanR={statistics.mean(rs):+.4f}  win%={100*sum(1 for x in rs if x>0)/n:.1f}"
          f"  total GBP={sum(money):+.2f}  avg win GBP={statistics.mean([m for m in money if m>0] or [0]):+.3f}"
          f"  avg loss GBP={statistics.mean([m for m in money if m<=0] or [0]):+.3f}")
    print(f"    exits: {tags}")

print("="*104)
print("  WHAT THE SHIPPED DEFAULTS ACTUALLY DO ON A 60 POUND ACCOUNT AT 0.01 LOTS")
print("  (GOLD 15m real bars - the ONLY data in this repo. M1 has no data at all.)")
print("="*104)
report("A. no basket rule, no daily guard  (this is what EXPERIMENTS.md measured)", basket=False, daily=False)
report("B. + InpUseBasket=true as shipped (arm 0.40% of equity / GBP1 floor, 20% give-back)", basket=True, daily=False)
report("C. + InpDailyLossPct=3.0 as shipped (guard flattens at GBP1.80 floating)", basket=True, daily=True)
report("D. daily guard only, basket OFF", basket=False, daily=True)
print("\n  Same at the account size E-096 says is the minimum:")
report("E. GBP100 account, basket + daily guard as shipped", basket=True, daily=True, eq=100.0)
report("F. GBP500 account, basket + daily guard as shipped", basket=True, daily=True, eq=500.0)
