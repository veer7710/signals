"""
POINT-SCALE STUDY — testing Veer's own observation with numbers.

Veer, watching the SuperTrend Pine live:
    "insane consistent signals which get 1-5 points on the lower end and
     catch straight bangers on some days"

That is a claim about the SHAPE of the outcome distribution, and it is exactly
the claim that decides whether this strategy can pay. If nearly every signal
gives a few points and a few give a hundred, then the money question is not
"is the entry good" - it is "is the STOP the right size for the move the entry
actually produces".

The suspicion this file exists to test:
    the stop is 1.5 x ATR. If the typical favourable move is 1-5 points and
    the stop is 8 points, the trade risks 8 to make 3 and the entry can be
    excellent while the system still bleeds. That would explain the complaint
    that has run through this whole project - "a majority of trades go into
    profit, we just don't close in that profit".

METHOD (the same rules as everything else here)
  * signal from CLOSED bars only, entry at the NEXT bar's open
  * FIRST TOUCH: a target counts only if it is reached BEFORE the stop
  * ties lose: if one bar contains both, it is recorded as a loss
  * costs applied to every fill

WHAT IT CANNOT ANSWER
  The committed data is 15m and 1h. Veer scalps lower. Nothing here measures
  M1 or M5 behaviour and no number in this output should be read as if it did.

Run:  python3 JARVIS/research/pointscale.py
"""
from __future__ import annotations
import os, sys, statistics as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import Costs
import strategies as S


def scan(s, dir_fn, stop_atr=1.5, max_bars=50, warmup=250):
    """
    For every SuperTrend flip, walk forward bar by bar and record, in POINTS:
      - the stop distance the strategy would have used
      - the best favourable excursion reached BEFORE the stop was hit
      - which fixed point-targets were reached before the stop
    Returns one dict per signal.
    """
    atr = engine.atr(s, 14)
    d = dir_fn(s)
    out = []

    for i in range(warmup, len(s) - 2):
        if d[i] is None or d[i - 1] is None:
            continue
        flip_up = d[i] == -1 and d[i - 1] == 1
        flip_dn = d[i] == 1 and d[i - 1] == -1
        if not (flip_up or flip_dn):
            continue
        if atr[i] is None or atr[i] <= 0:
            continue

        side = 1 if flip_up else -1
        entry = s.o[i + 1]                      # next-bar open, never the close
        stop_d = stop_atr * atr[i]
        stop = entry - side * stop_d

        mfe = 0.0
        bars = 0
        stopped = False
        for j in range(i + 1, min(i + 1 + max_bars, len(s))):
            bars = j - i
            # the stop is checked FIRST, so a bar holding both resolves as a loss
            if (s.l[j] <= stop) if side == 1 else (s.h[j] >= stop):
                stopped = True
                break
            fav = (s.h[j] - entry) if side == 1 else (entry - s.l[j])
            if fav > mfe:
                mfe = fav
        out.append({"side": side, "entry": entry, "stop_d": stop_d,
                    "mfe": mfe, "bars": bars, "stopped": stopped})
    return out


def pct(xs, p):
    if not xs: return float("nan")
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, int(round(p / 100.0 * (len(xs) - 1)))))
    return xs[k]


def report(sym, tf, stop_atr=1.5):
    s = engine.load(sym, tf)
    # supertrend_dir returns (direction, final_upper, final_lower)
    sig = scan(s, lambda x: S.supertrend_dir(x, atr_len=7, mult=1.2)[0],
               stop_atr=stop_atr)
    if not sig:
        print(f"  {sym} {tf}: no signals"); return

    n = len(sig)
    days = (s.ts[-1] - s.ts[0]) / 86400.0
    stops = [x["stop_d"] for x in sig]
    mfes = [x["mfe"] for x in sig]

    print(f"\n{'='*74}\n  {sym} {tf}   {n} signals over {days:.0f} days "
          f"= {n/max(days,1):.2f}/day\n{'='*74}")
    print(f"  STOP DISTANCE (1.5 x ATR), points: "
          f"median {st.median(stops):.2f}   p10 {pct(stops,10):.2f}   p90 {pct(stops,90):.2f}")
    print(f"  BEST MOVE IN FAVOUR before the stop, points: "
          f"median {st.median(mfes):.2f}   p25 {pct(mfes,25):.2f}   p75 {pct(mfes,75):.2f}   max {max(mfes):.2f}")

    med_stop, med_mfe = st.median(stops), st.median(mfes)
    print(f"\n  THE RATIO THAT MATTERS: the median signal risks "
          f"{med_stop:.2f} to capture {med_mfe:.2f} points.")
    if med_mfe < med_stop:
        print(f"  -> The typical move in favour is SMALLER than the stop. "
              f"An excellent entry still loses money at this stop size.")
    else:
        print(f"  -> The typical move in favour exceeds the stop.")

    # how far do signals actually run, as a fraction of all signals
    print(f"\n  REACHED N POINTS BEFORE THE STOP (first touch, ties lose):")
    for tgt in (1, 2, 3, 5, 10, 20, 50, 100):
        hit = sum(1 for x in sig if x["mfe"] >= tgt)
        print(f"     {tgt:>4} pts : {hit:>5}/{n}  {100.0*hit/n:>5.1f}%")

    # Does a small fixed target actually pay once the spread is charged?
    # Every trade that does not reach the target is assumed to lose the stop.
    c = Costs()
    cost = c.spread + 2 * c.slippage
    print(f"\n  FIXED POINT TARGET, net of {cost:.2f} pts round-trip cost:")
    print(f"     {'target':>7} {'win%':>7} {'exp/trade':>11} {'per day':>9}")
    for tgt in (1, 2, 3, 5, 10, 20, 50):
        wins = sum(1 for x in sig if x["mfe"] >= tgt)
        losses = n - wins
        exp = (wins * (tgt - cost) - losses * (med_stop + cost)) / n
        print(f"     {tgt:>7} {100.0*wins/n:>6.1f}% {exp:>11.3f} {exp*n/max(days,1):>9.3f}")
    print(f"\n  (expectancy is in POINTS per trade. At 0.01 lots on gold, "
          f"1 point = about 1.00 of account currency.)")


if __name__ == "__main__":
    print(__doc__)
    for sym in ("GOLD", "US500", "EURUSD", "GBPUSD"):
        for tf in ("15m", "1h"):
            try:
                report(sym, tf)
            except FileNotFoundError:
                pass
    print("\n" + "=" * 74)
    print("  REMINDER: this is 15m and 1h data. It says NOTHING about M1/M5,")
    print("  which is where the scalping happens. That data does not exist in")
    print("  this repo and no claim here should be transferred to it.")
    print("=" * 74)


# ============================================================================
#  STOP/TARGET SWEEP, with the split that stops this being curve-fitting
# ============================================================================
# The scan above says the entry is fine and the STOP SIZE is wrong. That is a
# hypothesis, and the honest way to test it is to search stop and target
# together on the first 70% of the data ONLY, then run the single best pair
# once on the last 30%. If the winner does not survive that, it was noise.

def split(s, frac=0.70):
    k = int(len(s) * frac)
    return (engine.Series(s.ts[:k], s.o[:k], s.h[:k], s.l[:k], s.c[:k]),
            engine.Series(s.ts[k:], s.o[k:], s.h[k:], s.l[k:], s.c[k:]))


def expectancy(sig, tgt_atr, cost):
    """Points per trade for a target of tgt_atr x ATR. Non-winners lose the
    stop in full: pessimistic, but it never flatters the result."""
    if not sig: return float("nan"), 0, 0
    wins = tot = 0
    pnl = 0.0
    for x in sig:
        # stop_d = stop_mult x ATR, so this recovers ATR and scales the target
        # in ATR units - NOT in multiples of the stop.
        tgt = tgt_atr * (x["stop_d"] / x["stop_mult"])
        tot += 1
        if x["mfe"] >= tgt:
            wins += 1; pnl += tgt - cost
        else:
            pnl += -(x["stop_d"] + cost)
    return pnl / tot, wins, tot


def sweep(sym, tf):
    s = engine.load(sym, tf)
    ins, oos = split(s)
    c = Costs(); cost = c.spread + 2 * c.slippage

    stops = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
    tgts  = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0]

    def sigs_for(series, sm):
        out = scan(series, lambda x: S.supertrend_dir(x, atr_len=7, mult=1.2)[0],
                   stop_atr=sm, max_bars=50)
        for o in out: o["stop_mult"] = sm
        return out

    print(f"\n{'='*74}\n  STOP/TARGET SWEEP — {sym} {tf}"
          f"\n  chosen on the first 70% only, then run ONCE on the last 30%\n{'='*74}")

    best = None
    for sm in stops:
        sg = sigs_for(ins, sm)
        for tg in tgts:
            e, w, n = expectancy(sg, tg, cost)
            if n < 30:      # too few trades to mean anything
                continue
            if best is None or e > best[0]:
                best = (e, sm, tg, w, n)
    if best is None:
        print("  not enough in-sample trades"); return

    e, sm, tg, w, n = best
    print(f"  BEST IN-SAMPLE : stop {sm} ATR, target {tg} ATR ({tg/sm:.2f}R)")
    print(f"                   {e:+.3f} pts/trade, {100.0*w/n:.1f}% win, {n} trades")

    sg_o = sigs_for(oos, sm)
    eo, wo, no = expectancy(sg_o, tg, cost)
    print(f"  SAME PAIR, OUT OF SAMPLE (never used to choose it):")
    print(f"                   {eo:+.3f} pts/trade, "
          f"{100.0*wo/max(no,1):.1f}% win, {no} trades")
    if no:
        days = (oos.ts[-1] - oos.ts[0]) / 86400.0
        print(f"                   {eo*no/max(days,1):+.3f} pts/day at 1 unit risk")
    verdict = "HELD" if (eo > 0 and e > 0) else "DID NOT HOLD"
    print(f"  ---> {verdict}")


if __name__ == "__main__" and "--sweep" in sys.argv:
    for sym in ("GOLD", "US500", "EURUSD", "GBPUSD"):
        for tf in ("15m", "1h"):
            try: sweep(sym, tf)
            except FileNotFoundError: pass
