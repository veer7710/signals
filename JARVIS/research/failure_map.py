"""
E-084 — WHERE DOES EACH STRATEGY LOSE? A price-action failure map.

Veer: "see where super trend could make loss in terms of price actions same w
liquidity strat ... there's areas where signals themselves make loss and areas
where we don't capture enough profit nor have a sniper entry or enter based of
false move which is ok as profits will and should heavily outweigh loss".

That last clause is the important one and it changes what this file is for. He
is NOT asking for a filter that removes losing trades - E-074 already measured
that road and found the highest-expectancy gate set banked the LEAST money. He
is asking WHICH PRICE ACTION produces the losses, so the losses can be made
SMALLER while the trade count stays high.

So every descriptor below is computed from bars that have already CLOSED before
the entry, and the output is expectancy AND points by bucket. Three different
things can then be done with a losing bucket, in descending order of how much
of the edge they preserve:

    1. SIZE DOWN in it        - keeps the trade, shrinks the loss
    2. WIDEN OR TIGHTEN there - the loss may be a stop-placement problem
    3. SKIP it                - last resort, because skipping costs trades

THE DESCRIPTORS, all backward-looking
  bar_size    the signal bar's own range in ATR. Big = we are chasing.
  run_bars    how many bars the current directional run has already lasted.
  run_atr     how far that run has already travelled, in ATR.
  from_swing  distance from the last confirmed swing, in ATR. Are we AT an
              extreme, which is where reversals start?
  atr_ratio   ATR(5) / ATR(20). Above 1 = expanding, below = contracting.
  range_pos   where entry sits in the last 20-bar range. 0 = low, 1 = high.
  eff         Kaufman efficiency over 20 bars: net distance / path walked.
  body        the signal bar's body as a share of its range. Small = indecision.
  htf         does the 4x-resampled trend agree with the trade?

Run:  python3 JARVIS/research/failure_map.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, strategies
from engine import Series
from liquidity import stat
from toptick import zone_stream, entry_level
from smc import smc_state, resolve, STOP_ATR as LQ_STOP, TGT_R as LQ_TGT, FRAC
from ea_parity import ea_best_level

GBP_PER_POINT = 1.00 / 1.27


def descriptors(s: Series, i: int, side: int, A, A5, A20, D):
    """Everything is computed from bars <= i, which have closed."""
    a = A[i]
    if not a or a <= 0:
        return None
    out = {}
    out["bar_size"] = (s.h[i] - s.l[i]) / a
    rng = max(s.h[i] - s.l[i], 1e-9)
    out["body"] = abs(s.c[i] - s.o[i]) / rng

    # how long has the current directional run gone on
    run = 0
    d0 = 1 if s.c[i] > s.c[i - 1] else -1
    for k in range(i, max(i - 60, 1), -1):
        d = 1 if s.c[k] > s.c[k - 1] else -1
        if d != d0:
            break
        run += 1
    out["run_bars"] = run
    out["run_atr"] = abs(s.c[i] - s.c[max(i - run, 0)]) / a

    # distance from the last confirmed swing on the side we are trading into
    sw = None
    for k in range(i - 3, max(i - 60, 3), -1):
        if side == 1:
            if all(s.h[k] >= s.h[k - j] for j in range(1, 4)) and \
               all(s.h[k] >= s.h[k + j] for j in range(1, 4)):
                sw = s.h[k]; break
        else:
            if all(s.l[k] <= s.l[k - j] for j in range(1, 4)) and \
               all(s.l[k] <= s.l[k + j] for j in range(1, 4)):
                sw = s.l[k]; break
    out["from_swing"] = (abs(s.c[i] - sw) / a) if sw is not None else None

    a5, a20 = A5[i], A20[i]
    out["atr_ratio"] = (a5 / a20) if (a5 and a20 and a20 > 0) else None

    lo = min(s.l[max(i - 19, 0):i + 1])
    hi = max(s.h[max(i - 19, 0):i + 1])
    out["range_pos"] = ((s.c[i] - lo) / (hi - lo)) if hi > lo else 0.5

    net = abs(s.c[i] - s.c[max(i - 20, 0)])
    path = sum(abs(s.c[k] - s.c[k - 1]) for k in range(max(i - 19, 1), i + 1))
    out["eff"] = (net / path) if path > 0 else None

    dn, dp = D[i], D[i - 4] if i >= 4 else (None, None)
    if dn is not None and dp is not None:
        out["htf"] = 1.0 if ((dn > dp) == (side > 0)) else 0.0
    else:
        out["htf"] = None
    return out


def supertrend_trades(s: Series, costs, warmup=300, max_bars=200):
    """The EA's entries and the R-denominated exit stack it now ships with."""
    d, fu, fl = strategies.supertrend_dir(s, 7, 1.2)
    A = engine.atr(s, 7); A5 = engine.atr(s, 5); A20 = engine.atr(s, 20)
    D = strategies.dema(s.c, 200)
    half = costs.spread / 2.0
    comm = costs.commission_per_lot / costs.value_per_point_per_lot
    out, busy = [], -1
    for i in range(warmup, len(s) - 2):
        if i <= busy or d[i] == 0 or d[i - 1] == 0:
            continue
        up = d[i] == -1 and d[i - 1] == 1
        dn_ = d[i] == 1 and d[i - 1] == -1
        if not (up or dn_):
            continue
        a = A[i]
        if not a or a <= 0:
            continue
        dnow, dprev = D[i], D[i - 2]
        if dnow is None or dprev is None:
            continue
        side = 1 if up else -1
        if (side == 1 and dnow < dprev) or (side == -1 and dnow > dprev):
            continue
        desc = descriptors(s, i, side, A, A5, A20, D)
        if desc is None:
            continue
        j = i + 1
        entry = s.o[j] + side * (half + costs.slippage)
        stop = s.c[i] - side * 2.0 * a
        risk = (entry - stop) * side
        if risk <= 0:
            continue
        tgt = entry + side * 3.0 * risk
        peak, peak_bar, locked, cur = 0.0, j, False, stop
        done = None
        for k in range(j, min(j + 50, len(s))):
            fav = (s.h[k] - entry) if side == 1 else (entry - s.l[k])
            if fav > peak: peak, peak_bar = fav, k
            pr = peak / risk
            hs = (s.l[k] <= cur) if side == 1 else (s.h[k] >= cur)
            ht = (s.h[k] >= tgt) if side == 1 else (s.l[k] <= tgt)
            if hs: done = (cur, k); break
            if ht: done = (tgt, k); break
            c = s.c[k]
            if not locked and pr >= 1.0:            # lock 1.0R
                be = entry + side * (2 * (half + costs.slippage) + comm)
                if (be - cur) * side > 0: cur, locked = be, True
            t = c - side * 3.0 * a                  # trail 3 ATR
            if (t - cur) * side > 0: cur = t
            if pr >= 3.0 and peak > 0:              # give-back armed at 3R
                if (c - entry) * side <= peak * 0.88:
                    done = (c, k); break
            if k - peak_bar >= 25: done = (c, k); break
        if done is None:
            k = min(j + 50, len(s)) - 1
            done = (s.c[k], k)
        px, k = done
        fill = px - side * (half + costs.slippage)
        r = ((fill - entry) * side - comm) / risk
        out.append({"r": r, "pts": (fill - entry) * side - comm,
                    "side": side, "i_in": j, "i_out": k, **desc})
        busy = k
    return out


def liquidity_trades(s: Series, costs, warmup=250):
    """The liquidity EA's entries, build 3.02 semantics."""
    A = engine.atr(s, 14); A5 = engine.atr(s, 5); A20 = engine.atr(s, 20)
    D = strategies.dema(s.c, 200)
    per_bar, _ = zone_stream(s)
    st = smc_state(s, A)
    half = costs.spread / 2.0
    out, busy, used = [], -1, set()
    arm = {1: None, -1: None}
    for i in range(warmup, len(s) - 2):
        a = A[i]
        if not a or a <= 0:
            continue
        if i > busy:
            for dirn in (1, -1):
                if arm[dirn] is None:
                    continue
                lvl, src, aa, ab = arm[dirn]
                hit = (s.l[i] <= lvl) if dirn > 0 else (s.h[i] >= lvl)
                if not hit:
                    continue
                entry = lvl + dirn * (half + costs.slippage)
                stop = entry - dirn * LQ_STOP * aa
                if (entry - stop) * dirn <= 0:
                    arm[dirn] = None; continue
                tgt = entry + dirn * LQ_TGT * (entry - stop) * dirn
                t = resolve(s, costs, i, dirn, entry, stop, tgt)
                desc = descriptors(s, ab, dirn, A, A5, A20, D)
                if desc:
                    out.append({"r": t["r"], "pts": t["pts"], **desc})
                busy = t["exit_bar"]
                used.add(round(lvl, 4))
                arm = {1: None, -1: None}
                break
        if i <= busy:
            arm = {1: None, -1: None}; continue
        zb = [z for z in per_bar[i] if z["dir"] == 1 and i - z["born"] <= 60]
        zs = [z for z in per_bar[i] if z["dir"] == -1 and i - z["born"] <= 60]
        gaps = [g for g in st["fvg"][i] if not g["inverted"]]
        obs = st["ob"][i]
        for dirn in (1, -1):
            if arm[dirn] is not None and i - arm[dirn][3] <= 60:
                continue
            lvl, src = ea_best_level(dirn, s.c[i], zs if dirn > 0 else zb,
                                     gaps, obs, a)
            if lvl is None or round(lvl, 4) in used:
                arm[dirn] = None; continue
            arm[dirn] = (lvl, src, a, i)
    return out


FIELDS = [("bar_size", "signal bar range, in ATR"),
          ("run_bars", "bars the run has already lasted"),
          ("run_atr", "ATR the run has already travelled"),
          ("from_swing", "ATR from the last swing we trade into"),
          ("atr_ratio", "ATR(5)/ATR(20): expanding vs contracting"),
          ("range_pos", "position in the last 20-bar range"),
          ("eff", "efficiency over 20 bars"),
          ("body", "signal bar body as a share of its range"),
          ("htf", "does the higher-timeframe slope agree")]


def buckets(tr, field, n=5):
    vals = sorted(x[field] for x in tr if x.get(field) is not None)
    if len(vals) < n * 12:
        return []
    cuts = [vals[int(len(vals) * (k + 1) / n) - 1] for k in range(n)]
    out = []
    lo = float("-inf")
    for c in cuts:
        sel = [x for x in tr if x.get(field) is not None and lo < x[field] <= c]
        if sel:
            out.append((lo, c, sel))
        lo = c
    return out


def report(name, tr):
    a0 = stat(tr)
    tot = sum(x["pts"] for x in tr)
    print(f"\n{'='*100}\n  {name}   n={a0['n']}  {a0['exp']:+.3f}R  "
          f"{tot:+.0f} points  (GBP{tot*GBP_PER_POINT:+.0f} per 0.01 lot)\n{'='*100}")
    for f, desc in FIELDS:
        bs = buckets(tr, f)
        if not bs:
            continue
        print(f"\n  {desc}")
        print(f"   {'bucket':>18}{'n':>6}{'win%':>8}{'expect':>10}{'points':>10}"
              f"{'GBP':>9}   {'share of all losses':>20}")
        allloss = -sum(x["pts"] for x in tr if x["pts"] < 0) or 1.0
        for lo, hi, sel in bs:
            a = stat(sel)
            p = sum(x["pts"] for x in sel)
            lossshare = -sum(x["pts"] for x in sel if x["pts"] < 0) / allloss
            lbl = f"{'' if lo==float('-inf') else f'{lo:.2f}'}..{hi:.2f}"
            flag = "  <-- LOSES" if a["exp"] < 0 else ""
            print(f"   {lbl:>18}{a['n']:>6}{a['win']:>7.1f}%{a['exp']:>+9.3f}R"
                  f"{p:>+10.0f}{p*GBP_PER_POINT:>+9.0f}{100*lossshare:>19.0f}%{flag}")


def main():
    print("=" * 100)
    print("  E-084  WHERE EACH STRATEGY LOSES, BY PRICE ACTION")
    print("  Every descriptor is computed from bars that CLOSED before entry.")
    print("  A losing bucket is not automatically a bucket to skip - E-074 showed")
    print("  that removing trades usually removes more money than it saves. Size")
    print("  down first, re-place the stop second, skip last.")
    print("=" * 100)
    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        report(f"SUPERTREND — {sym} {tf}", supertrend_trades(s, c))
        lq = liquidity_trades(s, c)
        if len(lq) >= 60:
            report(f"LIQUIDITY — {sym} {tf}", lq)


if __name__ == "__main__":
    main()
