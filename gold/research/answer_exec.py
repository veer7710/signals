"""
Answers four specific questions:
 1. How much of the swing is ALREADY GONE when the signal prints?
 2. What is the ceiling if you could exit at the exact peak of every trade (perfect
    hindsight) -- and what does that same perfect exit make on COIN-FLIP entries?
 3. What does a pure trailing stop actually achieve, swept finely?
 4. Can you "close before the reversal"? i.e. is the noise band smaller than the move?
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))
import pandas as pd, numpy as np

df = pd.read_parquet("data/xauusd_m1.parquet")
df = df[df.dt >= "2024-01-01"].reset_index(drop=True)
legs = pd.read_parquet("research/legs_2024plus.parquet")
o, h, l, spr = df.open.values, df.high.values, df.low.values, df.spread.values
n = len(df); days = len(set(df.dt.dt.date))
GBP = 0.733
print(f"legs {len(legs):,}  trading days {days}\n")

# ---------- 1. how much of the swing is gone before the signal prints
L = legs.dropna(subset=["lag"]).copy()
L["swing"] = L.lag + L.avail.clip(lower=0)
L = L[L.swing > 0.5]                     # ignore non-moves
frac = (L.lag / L.swing) * 100
print("=" * 72)
print("1. HOW LATE IS THE SIGNAL? (share of the whole swing already gone at the arrow)")
print("=" * 72)
for p in (10, 25, 50, 75, 90):
    print(f"   p{p:<3} {np.percentile(frac,p):5.1f}%")
print(f"   mean {frac.mean():.1f}%   n={len(L):,}")
print(f"   median lag {L.lag.median():.2f} pt   median still available after it "
      f"{L.avail.median():.2f} pt")

# ---------- 2. perfect-hindsight ceiling, signal vs coin flip
print("\n" + "=" * 72)
print("2. THE CEILING: exit at the EXACT peak of every trade (impossible, but it bounds")
print("   the best case any exit rule could ever reach)")
print("=" * 72)
perfect = legs.mfe.clip(lower=0).sum()
print(f"   Supertrend entries, perfect exit : {perfect/len(legs):+.3f} pt/trade "
      f"({perfect*GBP/days:+.2f} GBP/day @0.01)")
rng = np.random.default_rng(5)
res = []
hold = legs.bars.values
for _ in range(3):
    ent = rng.integers(1, n-2, size=len(legs)); dirs = rng.choice([1,-1], size=len(legs))
    mfe = np.zeros(len(legs))
    for i in range(len(legs)):
        e, d, k = ent[i], dirs[i], max(int(hold[i]),1)
        x = min(e+k, n-1)
        if x <= e: continue
        entry = o[e] + spr[e] if d > 0 else o[e]
        adj = 0.0 if d > 0 else spr[e]
        best = h[e:x].max() if d > 0 else l[e:x].min()+adj
        mfe[i] = max((best-entry)*d, 0.0)
    res.append(mfe.sum())
coin = np.mean(res)
print(f"   COIN FLIP entries, perfect exit  : {coin/len(legs):+.3f} pt/trade "
      f"({coin*GBP/days:+.2f} GBP/day @0.01)")
print(f"   => the signal's peak-potential is only {perfect/coin:.2f}x a coin flip's.")
print("   A perfect exit makes money on ANYTHING, which is why 'it could have captured")
print("   more' is not evidence that the entry is any good.")

# ---------- 3. a pure trailing stop, swept finely
def pure_trail(dist_pts=None, atr_mult=None):
    tot = 0.0; stopped = 0
    for r in legs.itertuples(index=False):
        d, e = r.dir, r.entry_i
        if e >= n-1: continue
        D = dist_pts if dist_pts is not None else atr_mult*(r.atr if r.atr==r.atr else 1.0)
        s_in = r.spread
        entry = o[e] + s_in if d > 0 else o[e]
        adj = 0.0 if d > 0 else s_in
        stop = entry - d*D
        ext = entry; out = None
        last = r.exit_i - 1
        bi = e
        while bi <= min(last, n-1):
            hi_x = h[bi]+adj; lo_x = l[bi]+adj
            if (lo_x <= stop) if d > 0 else (hi_x >= stop):
                out = stop; stopped += 1; break
            fav = hi_x if d > 0 else lo_x
            if (fav - ext)*d > 0:
                ext = fav
                lvl = ext - d*D
                stop = max(stop, lvl) if d > 0 else min(stop, lvl)
            bi += 1
        if out is None:
            xi = min(r.exit_i, n-1); out = o[xi] + adj
        tot += (out - entry)*d
    return tot, stopped

print("\n" + "=" * 72)
print("3. A PURE TRAILING STOP — 'trail the SL and let it run'. Swept finely.")
print("=" * 72)
print(f"   {'trail':>12} {'net pt':>10} {'per trade':>10} {'GBP/day':>9} {'stopped out':>12}")
base = legs.net.sum()
print(f"   {'(hold to flip)':>12} {base:>10.0f} {base/len(legs):>10.3f} "
      f"{base*GBP/days:>9.2f} {'-':>12}")
best = None
for D in (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0):
    t, st = pure_trail(dist_pts=D)
    print(f"   {D:>9.2f} pt {t:>10.0f} {t/len(legs):>10.3f} {t*GBP/days:>9.2f} "
          f"{100*st/len(legs):>11.1f}%")
    if best is None or t > best[1]: best = (f"{D} pt", t)
for k in (0.5, 1.0, 2.0, 3.0):
    t, st = pure_trail(atr_mult=k)
    print(f"   {k:>8.2f} ATR {t:>10.0f} {t/len(legs):>10.3f} {t*GBP/days:>9.2f} "
          f"{100*st/len(legs):>11.1f}%")
    if t > best[1]: best = (f"{k} ATR", t)
print(f"   BEST trail tested: {best[0]} at {best[1]/len(legs):+.3f} pt/trade "
      f"({best[1]*GBP/days:+.2f} GBP/day) — still {'negative' if best[1]<0 else 'POSITIVE'}")

# ---------- 4. the noise band vs the move
print("\n" + "=" * 72)
print("4. CAN YOU 'CLOSE BEFORE THE REVERSAL'? The arithmetic that decides it.")
print("=" * 72)
atr = legs.atr.median(); sp = legs.spread.median()
noise = sp + 0.60*atr
print(f"   median ATR {atr:.2f} pt | median spread {sp:.2f} pt")
print(f"   noise band (spread + 0.60 x ATR) = {noise:.2f} pt")
print(f"   median points the trade ever offers = {legs.avail.median():.2f} pt")
print(f"   => a stop closer than {noise:.2f} pt is taken by ordinary wiggle, but the")
print(f"      typical trade only ever offers {legs.avail.median():.2f} pt. On the median")
print(f"      trade there is NO room for a trail to work at all.")
for thr in (2, 5, 10):
    sub = legs[legs.avail >= thr]
    print(f"   legs offering >={thr:2d} pt: {100*len(sub)/len(legs):5.1f}% of trades, "
          f"and they hold {100*sub.avail.sum()/legs.avail.sum():.0f}% of all available points")
