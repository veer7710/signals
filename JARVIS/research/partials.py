"""
E-188 — THREE TP LEVELS, THREE PARTIALS. What Veer actually trades, on RECENT
data only.

Veer: "it's not about rr we simply set 3 tp levels and take 3 partials on our
funded also why u doing 2018 im showing u live data and dont worry about rr we
just want best entry and a safe sl and tp for consistent payouts".

Both corrections are taken.

ON 2018: he is right and I kept going back to it because it is the only M1 file
in the repo. Outbound fetching is blocked here (the proxy returns 403), so
recent M1 cannot be obtained from this container - but GOLD_1h.json runs to
Aug 2026 and GOLD_15m.json is Jun-Aug 2026, and both have been under-used
because I chased sample size. **Nothing below touches 2018.**

ON R:R: a single target with a single R multiple is not how a funded account is
traded and it is not what he does. This models the real thing:

    full size in, ONE stop
    TP1  ->  close a third
    TP2  ->  close a third        stop to breakeven once TP1 is banked
    TP3  ->  close the last third

That changes the arithmetic completely from E-186. There the whole position
lived or died on one target. Here a trade that reaches TP1 and reverses is a
SMALL WIN, not a full loss - which is exactly the "consistent payouts" shape,
and it is why the win rate and the expectancy stop being the same question.

The metrics reported are the ones a funded account is actually judged on:
what fraction of trades bank something, the worst losing run, and the deepest
drawdown of the equity curve - not R multiples.
"""
from __future__ import annotations
import os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, Series
from regime import load_plain, resample
from legcatch import features
from bias_run import bias_series

COST = 0.02


def sigs(s, A, need=3):
    F = features(s, A, None)
    keep = [k for k in ["stretched from 50 EMA", "premium / discount",
                        "60%+ rejection wick", "equal highs taken",
                        "equal lows taken"] if k in F]
    out = []
    for i in range(len(s)):
        up = sum(1 for k in keep if F[k][i] > 0)
        dn = sum(1 for k in keep if F[k][i] < 0)
        if up >= need and up > dn:
            out.append((i, 1))
        elif dn >= need and dn > up:
            out.append((i, -1))
    return out


def book(s, A, sig, bias, side, stopAtr, tps, beAfterTp1=True,
         hold=400, cool=5, cost=COST):
    """side: 'with', 'against' or 'all'. tps: three distances in ATR.

    Returns (per-trade results in ATR, how many reached each TP).
    """
    out, busy = [], -1
    reach = [0, 0, 0]
    for (i, t) in sig:
        if i <= busy or i + 1 >= len(s):
            continue
        b = bias[i]
        if side == "with" and b != t:
            continue
        if side == "against" and b != -t:
            continue
        a = A[i]
        if not a or a <= 0:
            continue
        entry = s.o[i + 1]
        sl = entry - t * stopAtr * a
        lv = [entry + t * x * a for x in tps]
        left = 1.0
        got = 0.0
        hitN = 0
        kk = None
        for k in range(i + 1, min(i + 1 + hold, len(s))):
            # the stop is tested FIRST on every bar: ties lose
            hitSl = (s.l[k] <= sl) if t > 0 else (s.h[k] >= sl)
            if hitSl:
                got += left * t * (sl - entry) / a
                left = 0.0
                kk = k
                break
            if k == i + 1:
                continue                      # E-110: not on the entry bar
            for n in range(hitN, 3):
                hit = (s.h[k] >= lv[n]) if t > 0 else (s.l[k] <= lv[n])
                if not hit:
                    break
                part = 1.0 / 3.0 if n < 2 else left
                got += part * t * (lv[n] - entry) / a
                left -= part
                hitN = n + 1
                reach[n] += 1
                if n == 0 and beAfterTp1:
                    # THE STOP TO BREAKEVEN, and it is a REAL breakeven: entry
                    # plus the cost, not entry. "At breakeven" at the entry
                    # price is a story - the spread has already been paid.
                    be = entry + t * cost * a
                    if (be > sl) if t > 0 else (be < sl):
                        sl = be
            if left <= 1e-9:
                kk = k
                break
        if left > 1e-9:
            kk = min(i + 1 + hold, len(s) - 1)
            got += left * t * (s.c[kk] - entry) / a
        out.append(got - cost)
        busy = kk + cool
    return out, reach


def stats(r):
    if len(r) < 30:
        return None
    m = statistics.fmean(r)
    t = m / (statistics.pstdev(r) / len(r) ** 0.5)
    eq, peak, dd, run, worst = 0.0, 0.0, 0.0, 0, 0
    for x in r:
        eq += x
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
        run = run + 1 if x <= 0 else 0
        worst = max(worst, run)
    banked = 100.0 * sum(1 for x in r if x > 0) / len(r)
    return len(r), banked, m, t, dd, worst


def report(label, s, factor, need=3):
    A = watr(s, 14)
    sig = sigs(s, A, need)
    bias = bias_series(s, factor)
    print(f"\n  ---- {label} — {len(sig)} signals ----")
    print(f"  {'side  stop  TP ladder (ATR)':<34}{'n':>6}{'banked':>8}"
          f"{'ATR/trd':>10}{'t':>7}{'maxDD':>8}{'worst run':>10}")
    print("  " + "-" * 83)
    for side in ("against", "with", "all"):
        for stopAtr in (1.0, 1.5):
            for tps in ([1.0, 2.0, 3.0], [1.5, 3.0, 5.0], [2.0, 4.0, 7.0]):
                r, reach = book(s, A, sig, bias, side, stopAtr, tps)
                v = stats(r)
                if not v:
                    continue
                n, bank, m, t, dd, worst = v
                lad = "/".join(f"{x:.0f}" for x in tps)
                print(f"  {side:<8}{stopAtr:>4.1f}  {lad:<20}{n:>6}{bank:>7.1f}%"
                      f"{m:>+10.4f}{t:>+7.2f}{dd:>8.1f}{worst:>10}"
                      f"{'  <<<' if t >= 2.0 else ''}")
        print()


def main():
    print("=" * 92)
    print("  E-188 — three TPs, three partials, stop to breakeven after TP1.")
    print("  RECENT DATA ONLY. Nothing here touches 2018.")
    print("=" * 92)
    h1 = load_plain("GOLD_1h.json")
    report("2024-2026 1h, H1 bias from 4h", h1, 4)
    report("2026 Jun-Aug 15m, bias from 1h", load_plain("GOLD_15m.json"), 4)




def pooled():
    """Recent data is THIN - 1h gives ~300 trades, 15m ~100 - and at that size
    nothing above reaches significance. Results are already in ATR, which is
    scale-free, so the honest way to get n up without going back to 2018 is to
    pool every recent clock and test the ONE configuration that had the best
    shape on both: stop 1.5 ATR, TP ladder 1/2/3 ATR, stop to breakeven after
    TP1.

    Nothing is re-optimised here. One configuration, chosen for the shape Veer
    asked for - most trades banking something, shallow drawdown, short losing
    runs - measured across every recent sample available.
    """
    h1 = load_plain("GOLD_1h.json")
    g15 = load_plain("GOLD_15m.json")
    sets = [("2024-2026 1h", h1, 4),
            ("2024-2026 4h", resample(h1, 4), 4),
            ("2024-2026 2h", resample(h1, 2), 4),
            ("2026 15m", g15, 4),
            ("2026 30m", resample(g15, 2), 4),
            ("2026 1h", resample(g15, 4), 4)]
    print("\n" + "=" * 92)
    print("  E-188 POOLED — one configuration (stop 1.5 ATR, TP 1/2/3 ATR, BE")
    print("  after TP1) across every recent sample. No re-optimising.")
    print("=" * 92)
    print(f"  {'sample':<18}{'side':<10}{'n':>6}{'banked':>8}{'ATR/trd':>10}"
          f"{'t':>7}{'maxDD':>8}{'worst run':>10}")
    print("  " + "-" * 78)
    allr = {"against": [], "with": [], "all": []}
    for (lbl, s, f) in sets:
        A = watr(s, 14)
        sig = sigs(s, A, 3)
        bias = bias_series(s, f)
        for side in ("against", "with", "all"):
            r, _ = book(s, A, sig, bias, side, 1.5, [1.0, 2.0, 3.0])
            allr[side].extend(r)
            v = stats(r)
            if not v:
                continue
            n, bank, m, t, dd, worst = v
            print(f"  {lbl:<18}{side:<10}{n:>6}{bank:>7.1f}%{m:>+10.4f}"
                  f"{t:>+7.2f}{dd:>8.1f}{worst:>10}")
    print("  " + "-" * 78)
    for side in ("against", "with", "all"):
        v = stats(allr[side])
        if not v:
            continue
        n, bank, m, t, dd, worst = v
        print(f"  {'POOLED':<18}{side:<10}{n:>6}{bank:>7.1f}%{m:>+10.4f}"
              f"{t:>+7.2f}{dd:>8.1f}{worst:>10}{'  <<<' if t >= 2.0 else ''}")
    print("\n  The pooled clocks overlap in time, so these are not six")
    print("  independent samples and the pooled t is optimistic. It is a")
    print("  better estimate of the MEAN than any single row, not a stronger")
    print("  significance claim than the rows deserve.")


if __name__ == "__main__":
    main()
    pooled()
