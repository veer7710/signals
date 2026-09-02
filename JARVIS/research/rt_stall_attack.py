"""
RED TEAM attack on E-056 (stall.py).

Three attacks, all run on the same collector so they are comparable:
  A. PER-TRADE. E-056 pooled one row per BAR. A single long trade can supply
     dozens of near-identical rows, so 'n' is fiction and so is the 8/8. Take
     ONE observation per trade instead and see if unanimity survives.
  B. CENSORING. stall.py resolves the outcome inside the window
     [j+1, entry+max_hold). A high-stall observation sits LATER in the trade
     and therefore has FEWER bars left to resolve in. Unresolved rows are
     DROPPED. Give-back (close back through entry) resolves much faster than
     +0.5R of new peak, so short windows keep give-backs and drop the others.
     Fix: give every observation the SAME forward horizon measured from j.
  C. DOES IT MAKE MONEY. E-056 measures P(gives it back), never R. Simulate
     a stall exit against no stall exit on the same trades and report R.
"""
from __future__ import annotations
import os, sys, math, random, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, study, chop

STALL_BUCKETS = [(0, 1), (1, 3), (3, 6), (6, 12), (12, 25), (25, 10 ** 9)]
LABS = [f"{a}-{b}" if b < 10**9 else f"{a}+" for a, b in STALL_BUCKETS]


def collect(s, costs, warmup=300, max_hold=200, stop_atr=1.5,
            min_r=0.5, step_r=0.5, horizon=None):
    """Same as stall.collect but records trade id and, if horizon is set,
    resolves every observation inside a FIXED window of `horizon` bars from j
    (so the available window no longer shrinks with stall)."""
    ctx = engine.build_context(s)
    sig = strategies.supertrend_sniper_ea(s)
    half = costs.spread / 2.0
    obs = []
    tid = 0
    for i in range(warmup, len(s) - 2):
        sg = sig(ctx, i)
        if not sg:
            continue
        side = sg["side"]
        a = ctx["atr"][i]
        if a is None or a <= 0:
            continue
        entry = s.o[i + 1] + side * (half + costs.slippage)
        risk = stop_atr * a
        if risk <= 0:
            continue
        tid += 1
        peak = 0.0
        peak_bar = i + 1
        for j in range(i + 1, min(i + 1 + max_hold, len(s))):
            fav = (s.h[j] - entry) if side == 1 else (entry - s.l[j])
            adv = (entry - s.l[j]) if side == 1 else (s.h[j] - entry)
            if adv >= risk:
                break
            if fav > peak:
                peak = fav
                peak_bar = j
            peak_r = peak / risk
            if peak_r < min_r:
                continue
            stall = j - peak_bar
            need = peak + step_r * risk
            if horizon is None:
                end = min(i + 1 + max_hold, len(s))
            else:
                end = min(j + 1 + horizon, len(s))
            avail = end - (j + 1)
            gone = None
            for k in range(j + 1, end):
                f2 = (s.h[k] - entry) if side == 1 else (entry - s.l[k])
                back = (s.c[k] - entry) * side
                if back <= 0:
                    gone = True
                    break
                if f2 >= need:
                    gone = False
                    break
            obs.append({"tid": tid, "stall": stall, "peak_r": peak_r,
                        "gaveback": gone, "bars_held": j - i, "avail": avail})
    return obs


def grid(store, pick, title):
    """pick(obs_list_for_market) -> list of rows to score."""
    print(f"\n  {title}")
    print(f"  {'market':<14}{'n':>8}" + "".join(f"{l:>10}" for l in LABS))
    above = [0] * len(LABS); seen = [0] * len(LABS)
    for name, obs in store.items():
        rows = pick(obs)
        rows = [o for o in rows if o["gaveback"] is not None]
        if not rows:
            continue
        base = sum(1 for o in rows if o["gaveback"]) / len(rows)
        cells = []
        for bi, (a, b) in enumerate(STALL_BUCKETS):
            sel = [o for o in rows if a <= o["stall"] < b]
            if len(sel) < 30:
                cells.append(f"{'-':>10}"); continue
            p = sum(1 for o in sel if o["gaveback"]) / len(sel)
            cells.append(f"{100*(p-base):>+10.1f}")
            seen[bi] += 1
            if p > base:
                above[bi] += 1
        print(f"  {name:<14}{len(rows):>8}" + "".join(cells))
    print(f"  {'WORSE than base':<14}{'':>8}"
          + "".join(f"{f'{above[i]}/{seen[i]}':>10}" for i in range(len(LABS))))
    return above, seen


def main():
    store, store_h = {}, {}
    for sym, tf in chop.COMBOS:
        try:
            s = engine.load(sym, tf)
        except Exception:
            continue
        c = study.COSTS.get(sym, engine.Costs())
        o = collect(s, c)
        if len(o) < 200:
            continue
        store[f"{sym} {tf}"] = o
        store_h[f"{sym} {tf}"] = collect(s, c, horizon=40)

    print("=" * 100)
    print("  RED TEAM / E-056")
    print("=" * 100)

    # ---------- reproduce the published table (unresolved dropped)
    grid(store, lambda o: o, "A0. AS PUBLISHED — one row per BAR, unresolved dropped")

    # ---------- how much of that n is independent?
    print("\n  INDEPENDENCE OF THE SAMPLE")
    print(f"  {'market':<14}{'rows':>8}{'trades':>9}{'rows/trade':>12}{'max rows in 1 trade':>22}")
    for name, obs in store.items():
        per = {}
        for o in obs:
            per[o["tid"]] = per.get(o["tid"], 0) + 1
        print(f"  {name:<14}{len(obs):>8}{len(per):>9}{len(obs)/len(per):>12.1f}"
              f"{max(per.values()):>22}")

    # ---------- ATTACK B evidence: is the window shrinking with stall?
    print("\n  B. CENSORING DIAGNOSTIC — as published, per stall bucket")
    print(f"  {'market':<14}" + "".join(f"{l:>10}" for l in LABS) + "   (unresolved %)")
    for name, obs in store.items():
        cells = []
        for a, b in STALL_BUCKETS:
            sel = [o for o in obs if a <= o["stall"] < b]
            if len(sel) < 30:
                cells.append(f"{'-':>10}"); continue
            un = sum(1 for o in sel if o["gaveback"] is None) / len(sel)
            cells.append(f"{100*un:>10.1f}")
        print(f"  {name:<14}" + "".join(cells))

    # ---------- ATTACK A: one observation per trade
    for seedset in (0,):
        rng = random.Random(1234 + seedset)
        grid(store, lambda o: [random.Random(o[0]["tid"] * 0 + 7).choice(v)
                               for v in _by_trade(o)],
             "A1. ONE OBSERVATION PER TRADE — random bar within each trade (seed 7)")

    grid(store, lambda o: [v[0] for v in _by_trade(o)],
         "A2. ONE OBSERVATION PER TRADE — the FIRST qualifying bar of each trade")
    grid(store, lambda o: [v[-1] for v in _by_trade(o)],
         "A3. ONE OBSERVATION PER TRADE — the LAST qualifying bar of each trade")

    # ---------- ATTACK B: fixed forward horizon, still per bar and per trade
    grid(store_h, lambda o: o,
         "B1. FIXED 40-BAR FORWARD HORIZON from the observation — per BAR")
    grid(store_h, lambda o: [random.Random(7).choice(v) for v in _by_trade(o)],
         "B2. FIXED 40-BAR FORWARD HORIZON — one observation per trade")

    # ---------- multiple-seed stability of the per-trade result
    print("\n  A4. PER-TRADE UNANIMITY ACROSS 25 SEEDS  (how often does each")
    print("      bucket land 8/8 or 0/8 when only one row per trade is used?)")
    counts = {l: [] for l in LABS}
    for seed in range(25):
        rng = random.Random(seed)
        above = [0] * len(LABS); seen = [0] * len(LABS)
        for name, obs in store.items():
            rows = [rng.choice(v) for v in _by_trade(obs)]
            rows = [o for o in rows if o["gaveback"] is not None]
            base = sum(1 for o in rows if o["gaveback"]) / len(rows)
            for bi, (a, b) in enumerate(STALL_BUCKETS):
                sel = [o for o in rows if a <= o["stall"] < b]
                if len(sel) < 30:
                    continue
                p = sum(1 for o in sel if o["gaveback"]) / len(sel)
                seen[bi] += 1
                if p > base:
                    above[bi] += 1
        for bi, l in enumerate(LABS):
            counts[l].append((above[bi], seen[bi]))
    for l in LABS:
        arr = counts[l]
        unan = sum(1 for a, s_ in arr if s_ > 0 and (a == s_ or a == 0))
        mean_above = statistics.mean(a for a, _ in arr)
        mean_seen = statistics.mean(s_ for _, s_ in arr)
        print(f"    stall {l:<6} mean {mean_above:.1f}/{mean_seen:.1f} worse-than-base,"
              f"  unanimous in {unan}/25 seeds")


def _by_trade(obs):
    d = {}
    for o in obs:
        if o["gaveback"] is None:
            continue
        d.setdefault(o["tid"], []).append(o)
    return list(d.values())


if __name__ == "__main__":
    main()
