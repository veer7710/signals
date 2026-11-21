import csv,statistics as st
from datetime import datetime,timedelta
hd={}
with open('raw/Craig-Pang_QuantXAU/DAT_ASCII_XAUUSD_M1_2024.csv') as f:
    for line in f:
        a=line.strip().split(';')
        if len(a)<5: continue
        hd[datetime.strptime(a[0],'%Y%m%d %H%M%S')]=float(a[4])
bs={}
with open('raw/Best6626840_xauusd-m1-data/XAUUSDm_M1_2024.csv') as f:
    r=csv.reader(f); next(r)
    for a in r:
        if len(a)<5: continue
        bs[datetime.fromisoformat(a[0])]=float(a[4])
def corr(x,y):
    mx=st.mean(x);my=st.mean(y)
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/((sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y))**.5)
print("2024 only. Testing hour shifts applied to HistData timestamps:")
for sh in [4,5,6,7]:
    h2={t+timedelta(hours=sh):v for t,v in hd.items()}
    com=sorted(set(h2)&set(bs))
    rb=[];rh=[]
    for i in range(1,len(com)):
        if (com[i]-com[i-1]).total_seconds()!=60: continue
        rb.append(bs[com[i]]-bs[com[i-1]]); rh.append(h2[com[i]]-h2[com[i-1]])
    d=sorted(bs[t]-h2[t] for t in com)
    print(f"  +{sh}h: overlap={len(com):>8}  med_diff={st.median(d):+7.3f}  r_1min={corr(rb,rh):.4f}")
# best shift = 5; now aggregate returns over N minutes
h2={t+timedelta(hours=5):v for t,v in hd.items()}
com=sorted(set(h2)&set(bs))
for N in [1,5,15,60]:
    rb=[];rh=[]
    for i in range(N,len(com)):
        if (com[i]-com[i-N]).total_seconds()!=60*N: continue
        rb.append(bs[com[i]]-bs[com[i-N]]); rh.append(h2[com[i]]-h2[com[i-N]])
    print(f"  {N:>2}-min return correlation = {corr(rb,rh):.4f}  (n={len(rb)})")
# how often does histdata close repeat (staleness)?
hv=[h2[t] for t in com]; bv=[bs[t] for t in com]
print("repeated consecutive close: histdata %.2f%%  best %.2f%%" % (
  100*sum(1 for i in range(1,len(hv)) if hv[i]==hv[i-1])/len(hv),
  100*sum(1 for i in range(1,len(bv)) if bv[i]==bv[i-1])/len(bv)))
