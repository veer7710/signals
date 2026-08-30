"""
SuperTrend Sniper — capacity study.

One question, answered with measured numbers only:
  what account size and risk setting would this strategy need to make a
  CONSISTENT GBP60/day, and does the evidence support that it can at all?

Sections, in the order the arithmetic needs them:
  1. FREQUENCY   entries per trading day, every market and timeframe in /data
  2. EXPECTANCY  out-of-sample only (last 30% of each series, chronological),
                 in R, with standard error and t-statistic
  3. ARITHMETIC  GBP60/day = trades_per_day x expectancy_R x GBP_risked,
                 solved for GBP_risked and converted to an account size at
                 the EA's 0.50% risk default
  4. VARIANCE    bootstrap of MONTHS: what fraction come out negative
  5. no verdict is printed here. Verdicts are written by a human into
     EXPERIMENTS.md using the fixed vocabulary.

Signal: strategies.supertrend_sniper_ea (SuperTrend 7/1.2 + DEMA200 slope +
ADX<=35), the EA's defaults. Exits: the EA's own — 3R target, 50-bar cap,
3.0xATR trail armed at 0R, no break-even. The trail is set from the CLOSE of
bar i and can only be hit from bar i+1 onward, so nothing anticipates.

Run:  python3 JARVIS/research/st_capacity.py
"""
from __future__ import annotations
import datetime as dt, math, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, exits, strategies as S, study

MARKETS = [(m, tf) for m in ("GOLD", "US500", "EURUSD", "GBPUSD")
           for tf in ("15m", "1h")]
IS_FRAC = 0.70
WARMUP = 300
RISK_PCT = 0.005          # the EA's default
TARGET_GBP_DAY = 60.0


# --------------------------------------------------------- the EA's exits
def ea_exit(rr=3.0, trail_mult=3.0, arm_at_r=0.0, cap=50):
    """3R target, 50-bar time cap, 3.0xATR trail armed at 0R, no break-even.

    Order inside a bar: stop first (ties lose), then target, then the time
    cap, and only THEN is the trail moved using this bar's close — so the new
    trail level cannot be hit by the same bar that created it.
    """
    def f(p, b):
        side, risk = p["side"], p["risk"]
        hit_stop = b["l"] <= p["stop"] if side == 1 else b["h"] >= p["stop"]
        if hit_stop:
            return (p["stop"], "stop" if p["stop"] == p["init_stop"] else "trail")
        tgt = p["entry"] + side * rr * risk
        hit_tgt = b["h"] >= tgt if side == 1 else b["l"] <= tgt
        if hit_tgt:
            return (tgt, "target")
        if p["bars"] >= cap:
            return (b["c"], "time")
        a = b["atr"] or 0.0
        prof_r = ((b["c"] - p["entry"]) * side) / risk
        if a > 0 and prof_r >= arm_at_r:
            new = b["c"] - side * trail_mult * a
            p["stop"] = max(p["stop"], new) if side == 1 else min(p["stop"], new)
        return None
    return f


def make(sub):
    return S.supertrend_sniper_ea(sub)


def sub(s, lo, hi):
    return engine.Series(s.ts[lo:hi], s.o[lo:hi], s.h[lo:hi], s.l[lo:hi], s.c[lo:hi])


def day_count(ts_list):
    return len(set(dt.datetime.fromtimestamp(t, dt.timezone.utc).date()
                   for t in ts_list))


def describe(rs):
    n = len(rs)
    if n == 0:
        return dict(n=0)
    m = sum(rs) / n
    sd = statistics.stdev(rs) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else float("nan")
    return dict(n=n, exp=m, sd=sd, se=se,
                t=(m / se if se and se > 0 else 0.0),
                win=sum(1 for r in rs if r > 0) / n, total=sum(rs))


def run_slice(s, costs, warmup=WARMUP):
    """Entries + EA exits, one position at a time (as the EA trades)."""
    tr = exits.simulate(s, make(s), ea_exit(), costs,
                        warmup=warmup, max_bars=50, allow_overlap=False)
    return tr


def raw_signal_count(s, warmup=WARMUP):
    """How many times the signal fires at all, ignoring position occupancy."""
    ctx = engine.build_context(s)
    sig = make(s)
    n = 0
    for i in range(warmup, len(s) - 1):
        if sig(ctx, i):
            n += 1
    return n


def main():
    print("=" * 96)
    print("  SUPERTREND SNIPER — CAPACITY STUDY   (signal: supertrend_sniper_ea,"
          " exits: EA 3R/50bar/3ATR-trail)")
    print("=" * 96)

    rows = []
    print("\n1. FREQUENCY  (full series, warmup %d bars, one position at a time)" % WARMUP)
    print(f"  {'market':<12}{'bars':>7}{'sess.days':>10}{'raw sigs':>10}"
          f"{'entries':>9}{'ent/sess.day':>14}{'ent/cal.day':>13}{'med bars held':>15}")
    for m, tf in MARKETS:
        s = engine.load(m, tf)
        costs = study.COSTS.get(m, engine.Costs())
        traded_ts = s.ts[WARMUP:]
        sd_ = day_count(traded_ts)
        cd = (dt.datetime.fromtimestamp(traded_ts[-1], dt.timezone.utc)
              - dt.datetime.fromtimestamp(traded_ts[0], dt.timezone.utc)).days
        raw = raw_signal_count(s)
        tr = run_slice(s, costs)
        held = statistics.median([t["bars"] for t in tr]) if tr else 0
        rows.append((m, tf, s, costs, tr, sd_, cd, raw))
        print(f"  {m+' '+tf:<12}{len(s):>7}{sd_:>10}{raw:>10}{len(tr):>9}"
              f"{len(tr)/sd_:>14.3f}{len(tr)/max(cd,1):>13.3f}{held:>15.0f}")

    print("\n2. EXPECTANCY  chronological split, in-sample = first %d%%, "
          "OOS = last %d%%" % (IS_FRAC * 100, (1 - IS_FRAC) * 100))
    print(f"  {'market':<12}{'IS n':>6}{'IS exp':>9}{'IS t':>7}   "
          f"{'OOS n':>6}{'OOS win':>9}{'OOS exp':>10}{'OOS SE':>9}{'OOS t':>8}"
          f"{'OOS ent/day':>13}")
    oos_all, oos_by = [], {}
    for (m, tf, s, costs, _tr, _sd, _cd, _raw) in rows:
        k = int(len(s) * IS_FRAC)
        a, b = sub(s, 0, k), sub(s, k, len(s))
        ta, tb = run_slice(a, costs), run_slice(b, costs)
        da, db = describe([t["r"] for t in ta]), describe([t["r"] for t in tb])
        odays = day_count(b.ts[WARMUP:])
        oos_by[(m, tf)] = (db, odays, [t["r"] for t in tb], tb, b)
        oos_all += [t["r"] for t in tb]
        f = lambda d, k_: ("--" if d["n"] == 0 else d[k_])
        if da["n"] == 0 or db["n"] == 0:
            print(f"  {m+' '+tf:<12}{da['n']:>6}{'':>9}{'':>7}   {db['n']:>6}")
            continue
        print(f"  {m+' '+tf:<12}{da['n']:>6}{da['exp']:>+9.3f}{da['t']:>+7.2f}   "
              f"{db['n']:>6}{100*db['win']:>8.1f}%{db['exp']:>+10.3f}"
              f"{db['se']:>9.3f}{db['t']:>+8.2f}{db['n']/max(odays,1):>13.3f}")
    pooled = describe(oos_all)
    print(f"  {'POOLED OOS':<12}{'':>6}{'':>9}{'':>7}   {pooled['n']:>6}"
          f"{100*pooled['win']:>8.1f}%{pooled['exp']:>+10.3f}{pooled['se']:>9.3f}"
          f"{pooled['t']:>+8.2f}")
    print(f"  pooled OOS 95%% CI on expectancy: "
          f"[{pooled['exp']-1.96*pooled['se']:+.4f}R, {pooled['exp']+1.96*pooled['se']:+.4f}R]")

    print("\n3. ARITHMETIC   GBP%.0f/day = trades_per_day x expectancy_R x GBP_risked"
          % TARGET_GBP_DAY)
    print(f"  {'market':<12}{'OOS ent/day':>13}{'OOS exp R':>11}{'R/day':>9}"
          f"{'GBP risk/trade':>16}{'account @0.5%':>16}")
    for (m, tf) in [k for k in oos_by]:
        db, odays, rs, _tb, _b = oos_by[(m, tf)]
        if db["n"] == 0:
            continue
        tpd = db["n"] / max(odays, 1)
        rpd = tpd * db["exp"]
        if rpd <= 0:
            print(f"  {m+' '+tf:<12}{tpd:>13.3f}{db['exp']:>+11.3f}{rpd:>+9.4f}"
                  f"{'IMPOSSIBLE':>16}{'IMPOSSIBLE':>16}")
            continue
        risk = TARGET_GBP_DAY / rpd
        print(f"  {m+' '+tf:<12}{tpd:>13.3f}{db['exp']:>+11.3f}{rpd:>+9.4f}"
              f"{risk:>16,.0f}{risk/RISK_PCT:>16,.0f}")
    # all markets traded together
    tot_tpd = sum(db["n"] / max(od, 1) for db, od, _r, _t, _b in oos_by.values()
                  if db["n"])
    tot_rpd = sum((db["n"] / max(od, 1)) * db["exp"]
                  for db, od, _r, _t, _b in oos_by.values() if db["n"])
    print(f"  {'ALL 8 (1h+15m together)':<12}  entries/day {tot_tpd:.3f}   "
          f"R/day {tot_rpd:+.4f}", end="")
    if tot_rpd > 0:
        print(f"   GBP risk/trade {TARGET_GBP_DAY/tot_rpd:,.0f}   "
              f"account @0.5% {TARGET_GBP_DAY/tot_rpd/RISK_PCT:,.0f}")
    else:
        print("   -> no account size achieves it: R/day is negative")
    # 1h only, the only series with multi-year history
    h_tpd = sum(db["n"] / max(od, 1) for (m, tf), (db, od, _r, _t, _b)
                in oos_by.items() if tf == "1h" and db["n"])
    h_rpd = sum((db["n"] / max(od, 1)) * db["exp"] for (m, tf), (db, od, _r, _t, _b)
                in oos_by.items() if tf == "1h" and db["n"])
    print(f"  {'ALL 4 markets, 1h only':<12}   entries/day {h_tpd:.3f}   "
          f"R/day {h_rpd:+.4f}", end="")
    if h_rpd > 0:
        print(f"   GBP risk/trade {TARGET_GBP_DAY/h_rpd:,.0f}   "
              f"account @0.5% {TARGET_GBP_DAY/h_rpd/RISK_PCT:,.0f}")
    else:
        print("   -> no account size achieves it: R/day is negative")

    print("\n4. VARIANCE   bootstrap of MONTHS from the OOS trade distribution")
    print("   a month = 21 trading days x that market's OOS entries/day, "
          "20,000 draws")
    print(f"  {'market':<12}{'trades/mo':>11}{'P(month<0)':>12}"
          f"{'median mo R':>13}{'5th pct R':>11}{'95th pct R':>12}"
          f"{'P(mo >= 60/day)':>17}")
    for (m, tf), (db, odays, rs, _tb, _b) in oos_by.items():
        if db["n"] < 10:
            print(f"  {m+' '+tf:<12}{'(too few OOS trades: %d)' % db['n']:>60}")
            continue
        tpm = max(1, int(round(db["n"] / max(odays, 1) * 21)))
        rng = random.Random(7)
        sims = []
        for _ in range(20000):
            sims.append(sum(rs[rng.randrange(len(rs))] for _ in range(tpm)))
        sims.sort()
        neg = sum(1 for x in sims if x < 0) / len(sims)
        q = lambda p: sims[int(p * (len(sims) - 1))]
        # target in R terms: 60/day for 21 days at the risk size solved above
        rpd = (db["n"] / max(odays, 1)) * db["exp"]
        need_R = (TARGET_GBP_DAY * 21) / (TARGET_GBP_DAY / rpd) if rpd > 0 else None
        hit = ("n/a" if need_R is None
               else f"{100*sum(1 for x in sims if x >= need_R)/len(sims):.1f}%")
        print(f"  {m+' '+tf:<12}{tpm:>11}{100*neg:>11.1f}%{q(.5):>+13.2f}"
              f"{q(.05):>+11.2f}{q(.95):>+12.2f}{hit:>17}")

    # pooled: all 8 series traded together
    if pooled["n"] >= 30:
        tpm = max(1, int(round(tot_tpd * 21)))
        rng = random.Random(7)
        sims = sorted(sum(oos_all[rng.randrange(len(oos_all))] for _ in range(tpm))
                      for _ in range(20000))
        neg = sum(1 for x in sims if x < 0) / len(sims)
        q = lambda p: sims[int(p * (len(sims) - 1))]
        print(f"  {'POOLED (all 8)':<12}{tpm:>11}{100*neg:>11.1f}%{q(.5):>+13.2f}"
              f"{q(.05):>+11.2f}{q(.95):>+12.2f}")

    print("\n   ACTUAL calendar months in the OOS slices (not bootstrapped):")
    for (m, tf), (db, odays, rs, tb, b) in oos_by.items():
        if db["n"] < 10:
            continue
        by = {}
        for t in tb:
            key = dt.datetime.fromtimestamp(b.ts[t["i_in"]], dt.timezone.utc).strftime("%Y-%m")
            by.setdefault(key, []).append(t["r"])
        months = sorted(by)
        neg = sum(1 for k in months if sum(by[k]) < 0)
        detail = "  ".join(f"{k}:{sum(by[k]):+.1f}R(n{len(by[k])})" for k in months)
        print(f"  {m+' '+tf:<12} {neg}/{len(months)} months negative   {detail}")

    print("\n5. MONTE CARLO on the pooled OOS R sequence at 0.50% risk "
          "(engine.monte_carlo)")
    class T:  # engine.monte_carlo only reads .r
        def __init__(self, r): self.r = r
    mc = engine.monte_carlo([T(r) for r in oos_all], trials=20000,
                            risk_pct=RISK_PCT)
    for k in ("median_dd", "dd_95", "median_end", "end_05", "end_95",
              "p_dd_over_30pct", "p_dd_over_50pct", "p_losing_overall"):
        print(f"   {k:<18}{mc[k]:+.4f}")


if __name__ == "__main__":
    main()
