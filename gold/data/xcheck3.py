import csv,statistics as st
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
NY=ZoneInfo("America/New_York")
def corr(x,y):
    mx=st.mean(x);my=st.mean(y)
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/((sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y))**.5)
hd={}
for y in ['2021','2022','2023','2024','2025']:
    with open(f'raw/Craig-Pang_QuantXAU/DAT_ASCII_XAUUSD_M1_{y}.csv') as f:
        for line in f:
            a=line.strip().split(';')
            if len(a)<5: continue
            t=datetime.strptime(a[0],'%Y%m%d %H%M%S').replace(tzinfo=NY).astimezone(timezone.utc).replace(tzinfo=None)
            hd[t]=float(a[4])
for m in ['202601','202602','202603','202604','202605']:
    with open(f'raw/Paaktingc_forex_bot/DAT_ASCII_XAUUSD_M1_{m}.csv') as f:
        for line in f:
            a=line.strip().split(';')
            if len(a)<5: continue
            t=datetime.strptime(a[0],'%Y%m%d %H%M%S').replace(tzinfo=NY).astimezone(timezone.utc).replace(tzinfo=None)
            hd[t]=float(a[4])
bs={}
for y in range(2021,2027):
    with open(f'raw/Best6626840_xauusd-m1-data/XAUUSDm_M1_{y}.csv') as f:
        r=csv.reader(f); next(r)
        for a in r:
            if len(a)<5: continue
            bs[datetime.fromisoformat(a[0])]=float(a[4])
com=sorted(set(hd)&set(bs))
print(f"overlap minutes = {len(com):,}")
d=sorted(bs[t]-hd[t] for t in com)
print(f"close diff (best-histdata): median={st.median(d):+.3f} mean={st.mean(d):+.3f} p1={d[len(d)//100]:+.3f} p99={d[99*len(d)//100]:+.3f}")
print(f"abs diff >$1: {100*sum(1 for x in d if abs(x)>1)/len(d):.3f}%   >$5: {sum(1 for x in d if abs(x)>5)}")
for N in [1,5,60]:
    rb=[];rh=[]
    for i in range(N,len(com)):
        if (com[i]-com[i-N]).total_seconds()!=60*N: continue
        rb.append(bs[com[i]]-bs[com[i-N]]); rh.append(hd[com[i]]-hd[com[i-N]])
    print(f"{N:>2}-min return correlation = {corr(rb,rh):.5f} (n={len(rb):,})")
