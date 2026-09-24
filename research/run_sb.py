"""
run_sb.py -- attack the one row that survived.

PDH/PDL sweep -> displacement MSS, inside the 10-11am New York hour, showed a
+9.8% residual over geometry and was positive on 4/4 sets. Everything else in
run_ict_all.py was noise around zero.

Before that is believed it has to survive three attacks, because it was found
among ~36 tested combinations and one row at p~0.1 is EXPECTED from 36 tests:

  1. WHICH HOUR. Scan all 24. ICT specified 10-11am NY in advance, so this is a
     pre-registered hypothesis and not a fitted one -- but if 10-11 is a lone
     spike in an otherwise flat scan, that is noise wearing a theory's name. If
     there is a broad elevated region around the NY open that happens to peak
     there, the claim is far more plausible.
  2. SHUFFLED BARS. Same trade count, same directions, random bars in the same
     hour. Does the STRUCTURE do work, or only the clock?
  3. OUT OF SAMPLE. First half vs second half, per set.
"""
import sys, numpy as np
sys.path.insert(0, "research")
import core, sessions as S, ict
from run_ict import run_model, summarise
from run_partials import COSTS

SETS = [("GOLD","1h"), ("GOLD","15m"), ("EURUSD","1h"), ("EURUSD","15m"),
        ("GBPUSD","1h"), ("GBPUSD","15m"), ("US500","1h"), ("US500","15m")]

def prep(sym, tf):
    d = core.load(sym, tf); f = S.ny_fields(d)
    PDH, PDL = S.prior_day_levels(d, f)
    return d, f, PDH, PDL

def hour_mask(f, h):
    return f["h"] == h

def model_at_hour(d, f, PDH, PDL, h, cost, **kw):
    """The same composition as ict.sweep_mss_entries but with an arbitrary
    single-hour filter, so all 24 hours are treated identically."""
    n = d["n"]
    m = ict.displacement_mss(d)
    sw_hi = ict.sweep_of(d, PDH, +1); sw_lo = ict.sweep_of(d, PDL, -1)
    ok = hour_mask(f, h)
    sig = []; ph = -1; pl = -1
    for i in range(n):
        if sw_hi[i]: ph = i
        if sw_lo[i]: pl = i
        if ph >= 0 and i - ph <= 8 and m[i] == -1 and ok[i]:
            sig.append((i, -1)); ph = pl = -1
        elif pl >= 0 and i - pl <= 8 and m[i] == 1 and ok[i]:
            sig.append((i, 1)); ph = pl = -1
    if len(sig) < 8: return None, sig
    return summarise("x", run_model(d, f, sig, PDH, PDL, cost=cost)), sig

if __name__ == "__main__":
    data = {}
    for sym, tf in SETS:
        try: data[(sym,tf)] = prep(sym, tf)
        except Exception: pass

    # ---------------- ATTACK 1: all 24 New York hours ----------------
    print(f"\n{'='*104}")
    print("ATTACK 1 -- the same model in every New York hour. 10:00 is the one ICT")
    print("named in advance. If it is a lone spike, it is noise with a theory's name.")
    print(f"{'='*104}")
    print(f"  {'NY hour':<9}{'sets':>5}{'trades':>8}{'wResid':>9}{'+ve':>7}{'mean $/trd':>12}")
    scan = {}
    for h in range(24):
        rs = []
        for (sym,tf),(d,f,PDH,PDL) in data.items():
            s, _ = model_at_hour(d, f, PDH, PDL, h, COSTS[sym])
            if s and not np.isnan(s["resid"]): rs.append((s["resid"], s["n"], s["pts"]))
        if len(rs) < 3: continue
        r = np.array([x[0] for x in rs]); nn = np.array([x[1] for x in rs])
        scan[h] = float((r*nn).sum()/nn.sum())
        bar = "#" * max(0, int(round(scan[h]*100/2)))
        print(f"  {h:02d}:00{'':<4}{len(rs):>5}{int(nn.sum()):>8}{100*scan[h]:>+9.1f}"
              f"{int((r>0).sum()):>4}/{len(rs):<2}"
              f"{np.mean([x[2] for x in rs]):>12.2f}  {bar}")
    if scan:
        order = sorted(scan, key=lambda k: -scan[k])
        print(f"\n  ranked: " + "  ".join(f"{h:02d}h({100*scan[h]:+.0f})" for h in order[:6]))
        print(f"  10:00 NY ranks {order.index(10)+1} of {len(order)} hours tested.")

    # ---------------- ATTACK 2 + 3 ----------------
    print(f"\n{'='*104}")
    print("ATTACK 2/3 -- per set at 10:00 NY: shuffled-bar null, and first half vs second")
    print(f"{'='*104}")
    print(f"  {'set':<14}{'n':>5}{'resid':>8}{'per trade':>11}{'t':>6}"
          f"{'null':>8}{'null p95':>10}{'1st half':>10}{'2nd half':>10}   (ATR units)")
    for (sym,tf),(d,f,PDH,PDL) in data.items():
        s, sig = model_at_hour(d, f, PDH, PDL, 10, COSTS[sym])
        if not s: continue
        unit = float(np.nanmedian(core.atr(d, 14)))
        rng = np.random.default_rng(7)
        hrs = np.nonzero(hour_mask(f, 10) & (np.arange(d["n"]) > 25)
                         & (np.arange(d["n"]) < d["n"]-70))[0]
        nulls = []
        for _ in range(60):
            if len(hrs) < len(sig): break
            fake = sorted(zip(rng.choice(hrs, len(sig), replace=False),
                              [x for _, x in sig]))
            t2 = run_model(d, f, fake, PDH, PDL, cost=COSTS[sym])
            s2 = summarise("n", t2)
            if s2: nulls.append(s2["pts"])
        nm = np.mean(nulls) if nulls else float("nan")
        n95 = np.quantile(nulls, 0.95) if nulls else float("nan")
        mid = d["n"] // 2
        h1 = [x for x in sig if x[0] < mid]; h2 = [x for x in sig if x[0] >= mid]
        a = summarise("a", run_model(d, f, h1, PDH, PDL, cost=COSTS[sym])) if len(h1) >= 8 else None
        b = summarise("b", run_model(d, f, h2, PDH, PDL, cost=COSTS[sym])) if len(h2) >= 8 else None
        ha = f"{a['pts']/unit:>10.3f}" if a else "       n/a"
        hb = f"{b['pts']/unit:>10.3f}" if b else "       n/a"
        print(f"  {sym+' '+tf:<14}{s['n']:>5}{100*s['resid']:>+8.1f}"
              f"{s['pts']/unit:>11.3f}{s['t']:>6.2f}{nm/unit:>8.3f}"
              f"{n95/unit:>10.3f}{ha}{hb}")
