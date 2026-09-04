"""
E-099 — MULTIPLE ENTRIES INSIDE ONE TREND. Veer's central idea, tested.

Him, verbatim: "within a trend there's also multiple opportunities for more
trades eg pullbacks a small opposite direction then we using analysis close or
wait for continuation or breakout... catch every possible opportunity".

Both EAs take ONE trade per trend. `busy_until` blocks anything while a position
is open, and `InpReentryCool` blocks the bars after it closes. So a 60-point run
that the SuperTrend caught at its birth pays exactly once, and every pullback
inside it is discarded.

E-097 already found the hint that he is right: when concurrency was allowed, the
trades it ADDED scored +0.68R against the base's +0.36R on GOLD 1h, and +0.96R
against +0.39R on 15m. Trades arriving mid-move are BETTER than average. That is
his claim, arrived at from the other direction.

But E-097 also found those adds did not pay RISK-ADJUSTED, because they were the
same trade twice - opened together, they lose together. The question here is
different and sharper: does a SECOND ENTRY AT A PULLBACK, taken at a better
price than the first, beat holding one position through the same move?

FOUR ENTRY TYPES, all from closed bars, no look-ahead:
  BIRTH        the SuperTrend flip itself. What ships today.
  PULLBACK     price retraces >= pb_atr against the trend, then makes a higher
               low (long) / lower high (short), with the trend direction
               UNCHANGED. This is his "small opposite direction then continuation".
  BREAKOUT     price makes a new extreme in the trend direction after >= n bars
               of consolidation. His "breakout".
  BOTH         pullback and breakout together.

Judged on POINTS (E-074), one vote per trade (E-073), and on return per unit of
drawdown, because more entries in the same direction is more risk unless the
size is split.

Run:  python3 JARVIS/research/trend_reentry.py
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import atr as watr
from pine_ea_parity import ea_supertrend_at, ea_dema_at

ATRL, MULT, DEMAL, WARM, SPREAD = 7, 1.2, 200, 400, 0.46
STOP_ATR, TRAIL, MAXBARS = 2.0, 3.0, 50


def trend_map(s, warm=WARM):
    """SuperTrend direction on every bar, computed once. -1 bullish, +1 bearish."""
    A = watr(s, ATRL)
    n = len(s)
    d = [0] * n
    dp = [0] * n
    start = max(warm + 10, DEMAL * 4 + 20)
    for i in range(start, n):
        d[i], dp[i] = ea_supertrend_at(s, i, ATRL, MULT, warm)
    return d, dp, A, start


def resolve(s, i, side, a, stop_atr=STOP_ATR, trail=TRAIL, maxbars=MAXBARS):
    """One trade. 2.0 ATR stop, 3 ATR trail, give-back stop from 1.0R, 50-bar
    cap - the EA's shipped stack. Ties lose."""
    n = len(s)
    if i + 1 >= n or not a or a <= 0:
        return None
    entry = s.o[i + 1] + side * SPREAD / 2.0
    risk = stop_atr * a
    stop = entry - side * risk
    peak, mfe = entry, 0.0
    for j in range(i + 1, min(i + 1 + maxbars, n)):
        if (side > 0 and s.l[j] <= stop) or (side < 0 and s.h[j] >= stop):
            px = stop - side * SPREAD / 2.0
            return {"in": i + 1, "out": j, "side": side,
                    "pts": side * (px - entry), "r": side * (px - entry) / risk}
        peak = max(peak, s.h[j]) if side > 0 else min(peak, s.l[j])
        mfe = max(mfe, side * (peak - entry) / risk)
        t = peak - side * trail * a
        stop = max(stop, t) if side > 0 else min(stop, t)
        if mfe >= 1.0:
            allow = 0.20
            if mfe >= 1.5: allow = 0.16
            if mfe >= 3.0: allow = 0.12
            gb = entry + side * side * (peak - entry) * (1.0 - allow)
            stop = max(stop, gb) if side > 0 else min(stop, gb)
    j = min(i + maxbars, n - 1)
    px = s.c[j] - side * SPREAD / 2.0
    return {"in": i + 1, "out": j, "side": side,
            "pts": side * (px - entry), "r": side * (px - entry) / risk}


def signals(s, d, dp, A, start, use_pullback=False, use_breakout=False,
            pb_atr=0.8, bo_bars=6, use_dema=True, max_per_trend=99):
    """Every entry the configuration would take, in time order."""
    n = len(s)
    out = []
    run_side = 0          # +1 long trend, -1 short trend
    run_from = 0
    taken = 0
    ext = None            # running extreme since the trend began
    pb_low = None         # the retracement extreme, once a pullback starts
    for i in range(start, n - 1):
        a = A[i]
        if not a or a <= 0:
            continue
        up = d[i] == -1 and dp[i] == 1
        dn = d[i] == 1 and dp[i] == -1
        if up or dn:
            run_side = 1 if up else -1
            run_from = i
            taken = 0
            ext = s.c[i]
            pb_low = None
            if use_dema:
                en, ep = ea_dema_at(s, i, DEMAL, 1), ea_dema_at(s, i, DEMAL, 3)
                if en is None or ep is None:
                    run_side = 0; continue
                if (run_side > 0 and en < ep) or (run_side < 0 and en > ep):
                    run_side = 0; continue
            out.append((i, run_side, a, "birth"))
            taken += 1
            continue
        if run_side == 0 or taken >= max_per_trend:
            continue
        # the trend's running extreme
        ext = (max(ext, s.h[i]) if run_side > 0 else min(ext, s.l[i]))

        # ---- PULLBACK: retrace pb_atr against the trend, then turn back.
        # "a small opposite direction then we wait for continuation."
        if use_pullback:
            back = (ext - s.l[i]) if run_side > 0 else (s.h[i] - ext)
            if back >= pb_atr * a:
                if pb_low is None:
                    pb_low = s.l[i] if run_side > 0 else s.h[i]
                else:
                    pb_low = (min(pb_low, s.l[i]) if run_side > 0
                              else max(pb_low, s.h[i]))
                # the turn: this bar closes back through the previous bar's
                # extreme, in the trend's direction. Closed bars only.
                turned = (s.c[i] > s.h[i - 1]) if run_side > 0 else (s.c[i] < s.l[i - 1])
                if turned:
                    out.append((i, run_side, a, "pullback"))
                    taken += 1
                    pb_low = None
                    continue

        # ---- BREAKOUT: a new trend extreme after a quiet stretch.
        if use_breakout and i - run_from >= bo_bars:
            win_hi = max(s.h[i - bo_bars:i])
            win_lo = min(s.l[i - bo_bars:i])
            broke = (s.c[i] > win_hi) if run_side > 0 else (s.c[i] < win_lo)
            tight = (win_hi - win_lo) <= 2.0 * a
            if broke and tight:
                out.append((i, run_side, a, "breakout"))
                taken += 1
    return out


def book(s, sigs, slots=1, split=True):
    """Walk the signals. `slots` positions may be open at once; when split, each
    is sized 1/slots so total exposure matches the single-position baseline."""
    trades, busy = [], []
    for (i, side, a, kind) in sigs:
        busy = [b for b in busy if b >= i]
        if len(busy) >= slots:
            continue
        t = resolve(s, i, side, a)
        if t is None:
            continue
        t["kind"] = kind
        t["w"] = (1.0 / slots) if split else 1.0
        trades.append(t)
        busy.append(t["out"])
    return trades


def report(trades):
    if not trades:
        return 0, 0.0, 0.0, 0.0, 0.0
    ts = sorted(trades, key=lambda t: t["out"])
    eq = peak = dd = 0.0
    for t in ts:
        eq += t["r"] * t["w"]
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    pts = sum(t["pts"] * t["w"] for t in trades)
    return len(trades), pts, eq, dd, (eq / dd if dd > 0 else 0.0)


def main():
    for sym, tf in (("GOLD", "15m"), ("GOLD", "1h")):
        s = engine.load(sym, tf)
        d, dp, A, start = trend_map(s)
        print(f"\n{'='*100}\n  {sym} {tf} — entries inside one trend. "
              f"Size split across slots so total risk is matched.\n{'='*100}")
        print(f"  {'configuration':<34} {'slots':>6} {'n':>6} {'birth':>6} "
              f"{'pull':>6} {'brk':>6} {'points':>10} {'total R':>9} "
              f"{'maxDD':>8} {'R/DD':>7}")
        print("  " + "-" * 96)
        CFG = [
            ("BIRTH only (ships today)",  False, False, 1),
            ("+ pullback",                True,  False, 2),
            ("+ breakout",                False, True,  2),
            ("+ pullback + breakout",     True,  True,  3),
            ("+ both, 4 slots",           True,  True,  4),
        ]
        for name, pb, bo, slots in CFG:
            sg = signals(s, d, dp, A, start, use_pullback=pb, use_breakout=bo)
            tr = book(s, sg, slots=slots)
            n, pts, eq, dd, rdd = report(tr)
            kinds = {}
            for t in tr:
                kinds[t["kind"]] = kinds.get(t["kind"], 0) + 1
            print(f"  {name:<34} {slots:>6} {n:>6} {kinds.get('birth',0):>6} "
                  f"{kinds.get('pullback',0):>6} {kinds.get('breakout',0):>6} "
                  f"{pts:>10.1f} {eq:>+9.2f} {dd:>8.2f} {rdd:>7.2f}")

        # per-kind quality, which is the question underneath
        sg = signals(s, d, dp, A, start, use_pullback=True, use_breakout=True)
        tr = book(s, sg, slots=3)
        print(f"\n  QUALITY BY ENTRY TYPE (are the extra entries actually good?)")
        print(f"  {'kind':<12} {'n':>6} {'mean R':>9} {'points':>10} {'win%':>7}")
        print("  " + "-" * 48)
        for k in ("birth", "pullback", "breakout"):
            b = [t for t in tr if t["kind"] == k]
            if not b:
                continue
            m = sum(t["r"] for t in b) / len(b)
            w = 100.0 * sum(1 for t in b if t["pts"] > 0) / len(b)
            print(f"  {k:<12} {len(b):>6} {m:>+9.3f} "
                  f"{sum(t['pts'] for t in b):>10.1f} {w:>6.1f}%")


if __name__ == "__main__":
    main()
