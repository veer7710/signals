import os,sys,random,statistics
sys.path.insert(0,'/home/user/signals/JARVIS/research')
import engine
from engine import atr as watr
from pine_ea_parity import ea_supertrend_at, ea_dema_at
ATRL,MULT,DEMAL,WARM=7,1.2,200,400

def r_dist_mae(sym="GOLD",tf="15m",spread=0.46,stop_atr=2.0,trail=3.0,maxbars=50,arm=1.0):
    s=engine.load(sym,tf); A=watr(s,ATRL); n=len(s)
    start=max(WARM+10,DEMAL*4+20); out=[];busy=-1
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
        mae=0.0
        for j in range(i+1,min(i+1+maxbars,n)):
            adv=side*((s.l[j] if side>0 else s.h[j])-entry)/risk
            mae=min(mae,adv)
            if (side>0 and s.l[j]<=stop) or (side<0 and s.h[j]>=stop):
                i_out,px=j,stop-side*spread/2.0; break
            peak=max(peak,s.h[j]) if side>0 else min(peak,s.l[j])
            mfe=max(mfe,side*(peak-entry)/risk)
            t=peak-side*trail*a
            stop=max(stop,t) if side>0 else min(stop,t)
            if mfe>=arm:
                allow=0.20
                if mfe>=1.5: allow=0.16
                if mfe>=3.0: allow=0.12
                gb=entry+side*side*(peak-entry)*(1.0-allow)
                stop=max(stop,gb) if side>0 else min(stop,gb)
        if i_out is None:
            i_out=min(i+maxbars,n-1); px=s.c[i_out]-side*spread/2.0
        out.append((side*(px-entry)/risk, mae))
        busy=i_out
    return out
if __name__=="__main__":
    import json
    d=r_dist_mae()
    json.dump(d,open('/home/user/signals/JARVIS/research/findings/RM.json','w'))
    Rs=[x[0] for x in d]; M=[x[1] for x in d]
    print("n",len(d),"meanR",round(statistics.mean(Rs),4))
    for thr in (-0.30,-0.40,-0.52,-0.60,-0.80):
        c=sum(1 for m in M if m<=thr)
        print(f"  MAE reaches {thr:+.2f}R on {c:3d}/{len(M)} = {100*c/len(M):.1f}% of trades")
