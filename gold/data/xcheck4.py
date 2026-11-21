import csv,glob,statistics as st
from datetime import datetime,timedelta
def corr(x,y):
    mx=st.mean(x);my=st.mean(y)
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/((sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y))**.5)
pa={}
for p in glob.glob('raw/parshant65-lang_Gold-XAUUSD-1m-2020-2025/XAUUSD/1m/202[4-6]/*/*.csv'):
    with open(p) as f:
        r=csv.reader(f); next(r)
        for a in r:
            if len(a)<6: continue
            pa[datetime.fromisoformat(a[1])]=float(a[5])
bs={}
for y in [2024,2025,2026]:
    with open(f'raw/Best6626840_xauusd-m1-data/XAUUSDm_M1_{y}.csv') as f:
        r=csv.reader(f); next(r)
        for a in r:
            if len(a)<5: continue
            bs[datetime.fromisoformat(a[0])]=float(a[4])
print(f"parshant 2024-2026 bars={len(pa):,}  best 2024-2026 bars={len(bs):,}")
print("shift applied to parshant timestamps -> UTC:")
for sh in [0,-1,-2,-3]:
    p2={t+timedelta(hours=sh):v for t,v in pa.items()}
    com=sorted(set(p2)&set(bs))
    if len(com)<1000: print(f"  {sh:+}h overlap={len(com)}"); continue
    rb=[];rp=[]
    for i in range(1,len(com)):
        if (com[i]-com[i-1]).total_seconds()!=60: continue
        rb.append(bs[com[i]]-bs[com[i-1]]); rp.append(p2[com[i]]-p2[com[i-1]])
    d=sorted(bs[t]-p2[t] for t in com)
    print(f"  {sh:+}h overlap={len(com):>8,} med_diff={st.median(d):+8.3f} p1={d[len(d)//100]:+8.3f} p99={d[99*len(d)//100]:+8.3f} r_1min={corr(rb,rp):.5f}")
