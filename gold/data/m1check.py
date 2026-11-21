import sys
from datetime import datetime
from collections import Counter
fmt,name=sys.argv[1],sys.argv[2]
rows=[]
for p in sys.argv[3:]:
    with open(p) as f:
        for line in f:
            a=line.strip().split(';')
            if len(a)<5: continue
            rows.append((datetime.strptime(a[0],'%Y%m%d %H%M%S'),float(a[1]),float(a[2]),float(a[3]),float(a[4])))
rows.sort(key=lambda x:x[0]); n=len(rows)
print(f"### {name}\nbars={n:,}  first={rows[0][0]}  last={rows[-1][0]}")
cl=[r[4] for r in rows]; print(f"close min={min(cl)} max={max(cl)}")
bad=sum(1 for r in rows if not(r[3]<=r[1]<=r[2] and r[3]<=r[4]<=r[2]))
print(f"duplicate timestamps={n-len({r[0] for r in rows})}  OHLC-inconsistent={bad}")
gaps=Counter(); big=[]; miss=0
for i in range(1,n):
    prev,cur=rows[i-1][0],rows[i][0]; d=int((cur-prev).total_seconds())
    gaps[d]+=1
    if d>3600: big.append((d,prev,cur))
    if d>60 and not(prev.weekday()==4 and d>3600*20) and prev.weekday()<5 and cur.weekday()<5: miss+=d//60-1
tot=sum(gaps.values()); mc=gaps.most_common(1)[0]
print(f"modal gap={mc[0]}s ({100*mc[1]/tot:.2f}% of intervals)")
print("gap hist top5:",gaps.most_common(5))
print(f"missing minutes Mon-Fri (excl weekend)={miss:,}")
big.sort(reverse=True); print("largest 3 gaps(h):",[(round(g/3600,1),str(a),str(b)) for g,a,b in big[:3]])
fr=Counter(); su=Counter()
for i in range(1,n):
    prev,cur=rows[i-1][0],rows[i][0]
    if (cur-prev).total_seconds()>3600*20: fr[(prev.weekday(),prev.hour)]+=1; su[(cur.weekday(),cur.hour)]+=1
print("weekend gap START(wd,hr):",fr.most_common(3)); print("weekend gap END(wd,hr):",su.most_common(3))
rep=sum(1 for i in range(1,n) if cl[i]==cl[i-1]); print(f"repeated consecutive close={100*rep/n:.2f}%")
