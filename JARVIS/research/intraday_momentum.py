"""
Intraday momentum — does the FIRST bar of the session predict the LAST?

Gao, Han, Li & Zhou (JFE 2018) found the first half-hour return of the US
equity session predicts the last half-hour return. Li, Sakkas & Urquhart (JFM
2022) report it across 16 markets. It is a genuinely different animal from the
opening-range breakout already tested and rejected here: different trigger,
different direction source, different hold.

PRE-REGISTERED, so this is a test and not a fishing trip:
  * PREDICTION: the relationship is POSITIVE (momentum, not reversal).
  * VALIDATION FIRST: US500 is where the published effect lives. If it does not
    appear there, the implementation is wrong and no gold result can be trusted.
  * Only then look at GOLD and FX.
  * Terciles and thresholds are never fitted; this is a plain correlation plus a
    sign test on held-out data.

Run:  python3 JARVIS/research/intraday_momentum.py
"""
from __future__ import annotations
import datetime as dt, math, os, statistics as stat, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study

IS_FRAC = 0.70


def sessions(s: engine.Series, open_h, close_h):
    """Group bars into sessions by UTC hour window. Returns (first, last) bar
    index per day that has both."""
    out, cur, day = [], [], None
    for i in range(len(s)):
        d = dt.datetime.fromtimestamp(s.ts[i], dt.timezone.utc)
        if not (open_h <= d.hour < close_h):
            continue
        key = d.date()
        if key != day:
            if len(cur) >= 4:
                out.append((cur[0], cur[-1]))
            cur, day = [], key
        cur.append(i)
    if len(cur) >= 4:
        out.append((cur[0], cur[-1]))
    return out


def pearson(xs, ys):
    n = len(xs)
    if n < 10:
        return 0.0, 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return 0.0, 0.0
    r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)
    t = r * math.sqrt((n - 2) / max(1e-12, 1 - r * r))
    return r, t


def analyse(sym, tf, open_h, close_h, label):
    s = engine.load(sym, tf)
    k = int(len(s) * IS_FRAC)
    rows = []
    for a, b in sessions(s, open_h, close_h):
        if b <= a:
            continue
        r_first = (s.c[a] - s.o[a]) / s.o[a]
        r_last = (s.c[b] - s.o[b]) / s.o[b]
        rows.append((a, r_first, r_last))
    if len(rows) < 40:
        print(f"  {label:<22}{'too few sessions':>20} (n={len(rows)})")
        return None
    is_rows = [r for r in rows if r[0] < k]
    oos_rows = [r for r in rows if r[0] >= k]

    def block(rs):
        if len(rs) < 20:
            return None
        x = [r[1] for r in rs]
        y = [r[2] for r in rs]
        r, t = pearson(x, y)
        # sign agreement: does the last bar go the same way as the first?
        agree = sum(1 for a_, b_ in zip(x, y) if a_ * b_ > 0) / len(rs)
        return len(rs), r, t, agree

    bi, bo = block(is_rows), block(oos_rows)
    if not bi or not bo:
        print(f"  {label:<22}{'insufficient split':>20}")
        return None
    print(f"  {label:<22}"
          f"{bi[0]:>6}{bi[1]:>+8.3f}{bi[2]:>+7.2f}{100*bi[3]:>7.0f}%"
          f"{bo[0]:>7}{bo[1]:>+8.3f}{bo[2]:>+7.2f}{100*bo[3]:>7.0f}%")
    return {"sym": sym, "is": bi, "oos": bo}


def run():
    print("=" * 92)
    print("  INTRADAY MOMENTUM — does the first session bar predict the last?")
    print("  PRE-REGISTERED prediction: POSITIVE correlation (momentum).")
    print("  US500 is the validation case: the published effect lives there.")
    print("=" * 92)
    print(f"\n  {'market / session':<22}{'IS n':>6}{'corr':>8}{'t':>7}{'agree':>8}"
          f"{'OOS n':>7}{'corr':>8}{'t':>7}{'agree':>8}")
    print("  " + "-" * 88)

    res = []
    # validation first
    for sym, oh, ch, lab in [
        ("US500", 14, 21, "US500 NY 14-21"),
        ("US500", 8, 16, "US500 EU 08-16"),
        ("GOLD", 8, 17, "GOLD London 08-17"),
        ("GOLD", 13, 21, "GOLD NY 13-21"),
        ("GOLD", 0, 24, "GOLD full day"),
        ("EURUSD", 7, 16, "EURUSD EU 07-16"),
        ("GBPUSD", 7, 16, "GBPUSD EU 07-16"),
    ]:
        r = analyse(sym, "1h", oh, ch, lab)
        if r:
            res.append((lab, r))
    print("  " + "-" * 88)

    print("\n  VERDICT")
    us = [r for lab, r in res if r["sym"] == "US500"]
    if not us:
        print("  validation case produced no result — cannot trust anything below it.")
        return
    val_ok = any(u["is"][1] > 0.05 and u["oos"][1] > 0 for u in us)
    if not val_ok:
        print("  VALIDATION FAILED. The published effect does not appear on US500,")
        print("  which is where it is documented. That means either the")
        print("  implementation is wrong or 1h bars are too coarse to capture a")
        print("  half-hour effect — the latter is likely, since the paper uses")
        print("  30-minute bars and the first hour is not the first half hour.")
        print("  NOTHING below the validation line should be acted on.")
        print("  To settle it properly: re-run on M15 or M5 data once the MT5")
        print("  export provides it.")
    else:
        survivors = [(lab, r) for lab, r in res
                     if r["is"][1] > 0.05 and r["oos"][1] > 0.05]
        print(f"  Validation passed on US500. {len(survivors)} market/session")
        print("  combination(s) showed a positive relationship in BOTH halves:")
        for lab, r in survivors:
            print(f"    {lab}: IS corr {r['is'][1]:+.3f} (t {r['is'][2]:+.2f}), "
                  f"OOS corr {r['oos'][1]:+.3f} (t {r['oos'][2]:+.2f})")


if __name__ == "__main__":
    run()
