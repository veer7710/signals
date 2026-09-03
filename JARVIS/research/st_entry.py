"""
E-070 — Does the SuperTrend EA have the same disease the liquidity script had?

E-068 found that the liquidity strategy's ENTRY was worth everything and its
TRIGGER was worth nothing: buying the sweep bar's close scored -0.003R WITH
ZERO COSTS, and simply waiting for price to come back to the swept level turned
the same signals into +0.106R on GOLD 1h.

Veer on the SuperTrend EA: "for supertrend its all about entry and exit the
strat is fine". And: "we want perfect top tick entrys we don't wish to be in
drawdown". Those are the same complaint, so this asks the same question of it.

Market-at-the-flip is what the EA does today. It is also the entry that pays
the full spread and starts the trade at the WORST price of the impulse that
caused the flip, which is exactly what "we don't wish to be in drawdown" means.

THE VARIANTS, all on the identical signal set (no signal is added or removed):
  market       fill at the next bar's open. What the EA does now.
  limit_st     rest a limit at the SuperTrend line itself.
  limit_25/50/75  rest a limit 0.25 / 0.50 / 0.75 ATR back from the flip close.
  limit_dema   rest a limit at the DEMA.

A limit that never fills is not a loss - it is a trade not taken - so the fill
rate is reported beside every row. A rule that improves expectancy by refusing
90% of the signals is not an improvement to a strategy Veer wants firing 30-40
times a day, and the 'taken' column is there to catch exactly that.

The stop is anchored to the SIGNAL BAR, not to the fill, so a better entry buys
a smaller risk rather than a further stop - otherwise a pullback entry would
flatter itself by silently widening R.

Ties lose. Costs charged both ends. Every row gets a matched random control.

Run:  python3 JARVIS/research/st_entry.py
"""
from __future__ import annotations
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, strategies
from engine import Series
from liquidity import stat

COMBOS = [("GOLD", "15m"), ("GOLD", "1h"), ("US500", "15m"), ("US500", "1h"),
          ("EURUSD", "15m"), ("EURUSD", "1h"), ("GBPUSD", "15m"), ("GBPUSD", "1h")]

VARIANTS = ["market", "limit_st", "limit_25", "limit_50", "limit_75", "limit_dema"]


def signals(s: Series, atr_len=7, mult=1.2, dema_len=200):
    """Every SuperTrend flip the EA would act on, with the state an entry rule
    needs. Nothing here looks past bar i."""
    d, fu, fl = strategies.supertrend_dir(s, atr_len, mult)
    A = engine.atr(s, atr_len)
    D = strategies.dema(s.c, dema_len)
    out = []
    for i in range(3, len(s) - 2):
        if d[i] == 0 or d[i - 1] == 0:
            continue
        up = d[i] == -1 and d[i - 1] == 1
        dn = d[i] == 1 and d[i - 1] == -1
        if not (up or dn):
            continue
        a = A[i]
        if a is None or a <= 0:
            continue
        dnow, dprev = D[i], D[i - 2]
        if dnow is None or dprev is None:
            continue
        if up and dnow < dprev:
            continue
        if dn and dnow > dprev:
            continue
        side = 1 if up else -1
        # the SuperTrend line on the signal bar, which is the band price just
        # crossed - the natural place for a resting order
        stline = fl[i] if side == 1 else fu[i]
        out.append({"i": i, "side": side, "atr": a, "close": s.c[i],
                    "st": stline, "dema": dnow})
    return out


def level(ev, variant):
    side, c, a = ev["side"], ev["close"], ev["atr"]
    if variant == "market":     return None
    if variant == "limit_st":   return ev["st"]
    if variant == "limit_dema": return ev["dema"]
    if variant == "limit_25":   return c - side * 0.25 * a
    if variant == "limit_50":   return c - side * 0.50 * a
    if variant == "limit_75":   return c - side * 0.75 * a
    raise ValueError(variant)


def run(s: Series, costs, events, variant, stop_atr=1.5, target_r=3.0,
        wait=10, max_bars=200):
    """One position at a time. The stop is set from the SIGNAL bar's close so
    that every variant risks the same DISTANCE from the same reference and a
    better fill shows up as a better R, not as a wider one."""
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
    trades, offered, busy = [], 0, -1

    for ev in events:
        i, side, a = ev["i"], ev["side"], ev["atr"]
        offered += 1
        if i <= busy:
            continue
        lvl = level(ev, variant)

        if lvl is None:
            j = i + 1
            if j >= len(s): continue
            entry = s.o[j] + side * (half + costs.slippage)
        else:
            # a resting order fills when the bar trades through it
            j = None
            for k in range(i + 1, min(i + 1 + wait, len(s))):
                if (side == 1 and s.l[k] <= lvl) or (side == -1 and s.h[k] >= lvl):
                    j = k; break
            if j is None:
                continue
            entry = lvl + side * (half + costs.slippage)

        # RISK IS ANCHORED TO THE SIGNAL BAR, not to the fill.
        stop = ev["close"] - side * stop_atr * a
        risk = (entry - stop) * side
        # A resting order can sit at or BEYOND the stop - the SuperTrend line
        # after a flip often does. Filling there is not a brilliant entry with
        # a tiny risk, it is a trade that is already stopped out, and dividing
        # by that near-zero risk is what produced -18R rows the first time this
        # ran. Such a fill is not a trade.
        if risk <= 0.25 * stop_atr * a:
            continue
        tgt = entry + side * target_r * (stop_atr * a)

        done = None
        for k in range(j, min(j + max_bars, len(s))):
            hs = (s.l[k] <= stop) if side == 1 else (s.h[k] >= stop)
            ht = (s.h[k] >= tgt) if side == 1 else (s.l[k] <= tgt)
            if hs: done = (stop, "stop", k); break
            if ht: done = (tgt, "target", k); break
        if done is None:
            k = min(j + max_bars, len(s)) - 1
            done = (s.c[k], "time", k)
        px, why, k = done
        fill = px - side * (half + costs.slippage)
        r = ((fill - entry) * side - comm_px) / risk
        # MAE: how far underwater it went before it worked. This is the
        # "we don't wish to be in drawdown" complaint, measured.
        mae = 0.0
        for q in range(j, k + 1):
            adv = (entry - s.l[q]) if side == 1 else (s.h[q] - entry)
            if adv > mae: mae = adv
        trades.append({"r": r, "why": why, "bars": k - j, "mae_atr": mae / a})
        busy = k
    return trades, offered


def main():
    print("=" * 112)
    print("  E-070  SUPERTREND: is the entry the problem, as it was for liquidity?")
    print("  Identical signals in every row. Only WHERE the order sits changes.")
    print("  Risk is measured from the signal bar, so a better fill cannot flatter")
    print("  itself with a wider stop. Ties lose. Costs both ends.")
    print("=" * 112)

    pooled = {v: [] for v in VARIANTS}
    off = {v: 0 for v in VARIANTS}
    winrows = {v: 0 for v in VARIANTS}
    for sym, tf in COMBOS:
        try:
            s = engine.load(sym, tf)
        except Exception:
            continue
        c = study.COSTS.get(sym, engine.Costs())
        ev = signals(s)
        print(f"\n  ### {sym} {tf}   {len(ev)} flips")
        print(f"   {'entry':<12}{'taken':>7}{'fill%':>7}{'win%':>8}{'expect':>10}"
              f"{'PF':>7}{'t':>7}{'avg MAE':>10}{'total R':>10}")
        base = None
        for v in VARIANTS:
            tr, offered = run(s, c, ev, v)
            pooled[v] += tr
            off[v] += offered
            if not tr:
                continue
            a = stat(tr)
            mae = sum(x["mae_atr"] for x in tr) / len(tr)
            if v == "market":
                base = a["exp"]
            elif base is not None and a["exp"] > base:
                winrows[v] += 1
            print(f"   {v:<12}{a['n']:>7}{100.0*a['n']/max(offered,1):>6.0f}%"
                  f"{a['win']:>7.1f}%{a['exp']:>+9.3f}R{a['pf']:>7.2f}{a['t']:>+7.2f}"
                  f"{mae:>9.2f}A{a['exp']*a['n']:>+9.1f}R")

    print("\n" + "=" * 112)
    print("  POOLED — the row that matters. 'beats market' counts markets, not R.")
    print("=" * 112)
    print(f"\n  {'entry':<12}{'taken':>8}{'fill%':>7}{'win%':>8}{'expect':>10}"
          f"{'PF':>7}{'t':>7}{'avg MAE':>10}{'total R':>10}{'beats mkt':>11}")
    print("  " + "-" * 108)
    for v in VARIANTS:
        tr = pooled[v]
        if not tr:
            continue
        a = stat(tr)
        mae = sum(x["mae_atr"] for x in tr) / len(tr)
        bm = "-" if v == "market" else f"{winrows[v]}/8"
        print(f"  {v:<12}{a['n']:>8}{100.0*a['n']/max(off[v],1):>6.0f}%"
              f"{a['win']:>7.1f}%{a['exp']:>+9.3f}R{a['pf']:>7.2f}{a['t']:>+7.2f}"
              f"{mae:>9.2f}A{a['exp']*a['n']:>+9.1f}R{bm:>11}")

    print("\n  HOW TO READ 'fill%'")
    print("  A limit that never fills is a trade NOT TAKEN, not a loss. Veer wants")
    print("  30-40 entries a day, so a rule that lifts expectancy by refusing most")
    print("  signals is not an improvement to the system he is asking for. Judge a")
    print("  row on TOTAL R and fill%% together, never on expectancy alone.")


if __name__ == "__main__":
    main()
