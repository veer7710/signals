import csv,sys
from datetime import datetime,timedelta
import statistics as st
# HistData EST (UTC-5 fixed) -> UTC
hd={}
for y in ['2021','2022','2023','2024','2025']:
    with open(f'raw/Craig-Pang_QuantXAU/DAT_ASCII_XAUUSD_M1_{y}.csv') as f:
        for line in f:
            a=line.strip().split(';')
            if len(a)<5: continue
            t=datetime.strptime(a[0],'%Y%m%d %H%M%S')+timedelta(hours=5)
            hd[t]=float(a[4])
for m in ['202601','202602','202603','202604','202605']:
    with open(f'raw/Paaktingc_forex_bot/DAT_ASCII_XAUUSD_M1_{m}.csv') as f:
        for line in f:
            a=line.strip().split(';')
            if len(a)<5: continue
            t=datetime.strptime(a[0],'%Y%m%d %H%M%S')+timedelta(hours=5)
            hd[t]=float(a[4])
print("histdata bars(UTC-shifted):",len(hd))
bs={}
for y in range(2021,2027):
    with open(f'raw/Best6626840_xauusd-m1-data/XAUUSDm_M1_{y}.csv') as f:
        r=csv.reader(f); next(r)
        for a in r:
            if len(a)<5: continue
            bs[datetime.fromisoformat(a[0])]=float(a[4])
print("best bars 2021-2026:",len(bs))
common=sorted(set(hd)&set(bs))
print("overlapping minutes:",len(common))
d=[bs[t]-hd[t] for t in common]
d.sort()
print(f"close diff (best - histdata): median={st.median(d):+.3f}  mean={st.mean(d):+.3f}  p1={d[len(d)//100]:+.3f} p99={d[99*len(d)//100]:+.3f}")
print(f"abs diff > $1 : {sum(1 for x in d if abs(x)>1)} ({100*sum(1 for x in d if abs(x)>1)/len(d):.3f}%)")
print(f"abs diff > $5 : {sum(1 for x in d if abs(x)>5)}")
# correlation of 1-min returns
rb=[];rh=[]
for i in range(1,len(common)):
    if (common[i]-common[i-1]).total_seconds()!=60: continue
    rb.append(bs[common[i]]-bs[common[i-1]]); rh.append(hd[common[i]]-hd[common[i-1]])
mb=st.mean(rb);mh=st.mean(rh)
cov=sum((a-mb)*(b-mh) for a,b in zip(rb,rh))
print(f"1-min return correlation over {len(rb)} pairs = {cov/((sum((a-mb)**2 for a in rb)*sum((b-mh)**2 for b in rh))**.5):.6f}")
