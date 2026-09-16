"""
"I'd rather have GBP 5 than hope for GBP 20."

Tests that against the measured peak distribution in HIS OWN tickets, because
the answer depends entirely on how often a GBP 5 peak actually happens -- and
that is a number he already has, not an opinion either of us needs to hold.
"""
import numpy as np

GBP001 = 0.733           # per point at 0.01 lots
ATR    = 1.47            # M1
AVG_LOSS = 1.73          # measured
N      = 275

# Finding 4 cohorts + the winners, from the brief. Peak = best moment reached.
COHORTS = [
    # (count, mean peak GBP, label)
    (153, 2.02/153,  "never got GBP0.30 up"),
    ( 17, 13.56/17,  "GBP0.30-1.50"),
    ( 18, 79.56/18,  "GBP1.50+ then reversed"),
    ( 87, 198.12/87, "winners"),
]

def sample_peaks(n=200000, seed=3):
    """Rebuild the peak distribution: pick a cohort by its share, then draw an
    exponential inside it with that cohort's measured mean. Exponential is the
    right shape for excursions and it reproduces the measured pool exactly."""
    rng = np.random.default_rng(seed)
    counts = np.array([c for c,_,_ in COHORTS], float)
    means  = np.array([m for _,m,_ in COHORTS], float)
    p = counts/counts.sum()
    idx = rng.choice(len(COHORTS), size=n, p=p)
    return rng.exponential(means[idx])

peaks = sample_peaks()
print("="*78)
print("THE PEAK DISTRIBUTION IN YOUR OWN TICKETS")
print("="*78)
print(f"  mean peak per trade   GBP {peaks.mean():.2f}"
      f"   (brief: 293.26/279 = GBP {293.26/279:.2f})")
print(f"  {'peak reaches':>14}{'% of trades':>13}{'times per 275':>15}")
for t in (1,2,3,4,5,8,10,15,20):
    pr = (peaks>=t).mean()
    print(f"  {'GBP '+str(t):>14}{100*pr:>12.1f}%{pr*N:>15.0f}")
print(f"\n  at 0.02 lots GBP 5 = {5/(GBP001*2):.2f} pts = {5/(GBP001*2)/ATR:.2f} ATR")
print(f"  at 0.03 lots GBP 5 = {5/(GBP001*3):.2f} pts = {5/(GBP001*3)/ATR:.2f} ATR")
print("  -> 'GBP 5' is a different trade at every lot size. That is why the")
print("     lock has to be in ATR and the bank has to be in R, not pounds.")

print("\n"+"="*78)
print("WHAT EACH EXIT POLICY IS WORTH, ON THOSE SAME TRADES")
print("="*78)
print("  Assumption stated plainly: a trade that never reaches the bank level")
print("  ends at the average measured loss, -GBP1.73. Winners are not assumed;")
print("  they come out of the measured peak distribution.")
print(f"\n  {'policy':<34}{'wins':>7}{'win%':>7}{'avg win':>9}{'net / 275':>11}")

def evaluate(label, f):
    pnl = np.array([f(p) for p in peaks[:40000]])
    w = pnl>0
    print(f"  {label:<34}{w.sum():>7}{100*w.mean():>6.1f}%"
          f"{(pnl[w].mean() if w.any() else 0):>9.2f}{pnl.mean()*N:>11.1f}")
    return pnl.mean()

res = {}
# A. hard bank at a fixed pound target
for T in (2,3,4,5,8):
    res[f"bank all at GBP{T}"] = evaluate(f"bank ALL at GBP {T}",
        lambda p,T=T: T if p>=T else -AVG_LOSS)
# B. trail keeping a fraction of the peak
for K in (0.50,0.70,0.85):
    res[f"trail keep {K}"] = evaluate(f"trail, keep {int(K*100)}% of peak",
        lambda p,K=K: K*p if p>=0.74 else -AVG_LOSS)     # 0.74 = 0.5 ATR at 0.01
# C. the hybrid: bank most of it, run the rest
for T,frac in ((3,0.70),(4,0.70),(5,0.70),(4,0.50)):
    res[f"bank {int(frac*100)}% at GBP{T} + trail"] = evaluate(
        f"bank {int(frac*100)}% at GBP{T}, trail rest",
        lambda p,T=T,f=frac: (f*T + (1-f)*0.85*p) if p>=T else
                             (0.85*p if p>=0.74 else -AVG_LOSS))

best = max(res, key=res.get)
print(f"\n  best of these: {best}  ({res[best]*N:+.1f} per 275 trades)")

print("\n"+"="*78)
print("YOUR SPECIFIC ARITHMETIC, CHECKED")
print("="*78)
n4 = (peaks>=4).mean()*N
print(f'  "up GBP4 ten times = GBP40, close each at 2 = GBP20, so GBP20 gone"')
print(f"  How often does a GBP4 peak actually happen? {n4:.0f} times per 275 trades.")
print(f"  So your 'ten times' is close to right -- it is about {n4:.0f}.")
print(f"  Giving back half of {n4:.0f} x GBP4 = GBP {n4*2:.0f}. You are right that")
print(f"  it is real money and right that it is worth fixing.")
print()
print("  BUT the give-back is not 50% under a scaling lock. Keeping 85% of a")
print(f"  GBP4 peak is GBP3.40, not GBP2. That recovers GBP {n4*(3.40-2.00):.0f} of the"
      f" GBP {n4*2:.0f}")
print("  WITHOUT capping anything.")

print("\n"+"="*78)
print("WHERE YOU ARE RIGHT, AND WHERE THE DATA DISAGREES")
print("="*78)
pr20 = (peaks>=20).mean()
print(f'  RIGHT: "hoping for GBP20" is not a plan. A GBP20 peak happens'
      f" {100*pr20:.2f}% of the time")
print(f"         = {pr20*N:.1f} times per 275 trades. Essentially never.")
print(f"  RIGHT: the give-back on GBP4 peaks is real money and worth fixing.")
print()
pr5 = (peaks>=5).mean()
print(f'  WRONG: "GBP5 is likely." It is reached {100*pr5:.1f}% of the time'
      f" = {pr5*N:.0f} per 275.")
print(f"         A hard bank at GBP5 only pays on those {pr5*N:.0f}; the other"
      f" {N-pr5*N:.0f} still lose.")
print(f"  The level that IS likely is around GBP{np.percentile(peaks,75):.2f}"
      f" (75th percentile of peaks).")
