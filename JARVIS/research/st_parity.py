"""
P91b / E-083 — Does SuperTrendSniper.mq5 trade what E-075 measured?

E-082 asked this of the liquidity EA and found a 2.4x expectancy gap and a 2.2x
drawdown gap. This EA is the one on Veer's LIVE account, and the same question
has never been asked of it.

E-075 compared clean, single exit policies: "trail 3xATR armed at 1R",
"giveback 25% arm@3R", and so on. The EA runs NONE of those. It runs all of
them at once, layered:

    hard target 3R
    trail 3 ATR, armed immediately
    give-back, armed at max(3R, GBP2.00), allowance 0.20 -> 0.16 -> 0.12 by tier,
        scaled 1.07..0.93 by stall, floored so it never fires inside its own cost
    per-position lock to breakeven+cost once the position is GBP0.50 green
    stall exit at 25 bars
    hard bar cap at 50
    structural reversal exit

Six rules that can each close the trade, and whichever fires FIRST wins. That
is not any of the policies that were measured, and the interaction is not
guessable - a lock at GBP0.50 can pre-empt the trail, a stall exit can pre-empt
the give-back, and the hard 50-bar cap can pre-empt everything.

This implements the stack as the EA runs it and puts it beside the single
policies. Every rule is then removed one at a time, so the cost or benefit of
each layer is a number rather than an intention.

Ties lose. Costs both ends. GOLD, 2.0 ATR stop, DEMA gate on, ADX gate off -
the EA as it now stands.

Run:  python3 JARVIS/research/st_parity.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, strategies, exits
from engine import Series
from liquidity import stat

GBP_PER_POINT = 1.00 / 1.27          # 0.01 lot XAUUSD
LOTS = 0.03                          # what Veer actually enters with
GBP_PER_POINT_POS = GBP_PER_POINT * (LOTS / 0.01)

STOP_ATR      = 2.0
TARGET_R      = 3.0
TRAIL_ATR     = 3.0
TRAIL_ARM_R   = 0.0    # the EA arms the trail immediately (InpTrailAtR = 0.0)
GB_ARM_R      = 3.0
GB_ARM_MONEY  = 2.00
GB_BASE       = 0.20
GB_T2R, GB_T2 = 1.5, 0.16
GB_T3R, GB_T3 = 3.0, 0.12
GB_MIN_MONEY  = 0.10
LOCK_POS_MONEY = 0.50
LOCK_MONEY = 0.50      # swept below
LOCK_R = 0.0           # 0 = money only
STOP_SLIP = 0.0        # EXTRA points of adverse slippage on STOP-type exits only
MAX_STALL     = 25
MAX_BARS      = 50


def gb_allowance(peak_r, stall):
    gb = GB_BASE
    if peak_r >= GB_T2R: gb = GB_T2
    if peak_r >= GB_T3R: gb = GB_T3
    if stall <= 1:    gb *= 1.07
    elif stall <= 3:  gb *= 1.04
    elif stall <= 6:  gb *= 1.00
    elif stall <= 12: gb *= 0.98
    elif stall <= 25: gb *= 0.95
    else:             gb *= 0.93
    return max(gb, 0.08)


def run_stack(s: Series, costs, use, warmup=300):
    """The EA's layered exit. `use` switches individual rules off so each can
    be priced. Every rule is evaluated on the CLOSED bar except the stop and
    the target, which are intrabar because they sit at the broker."""
    d, fu, fl = strategies.supertrend_dir(s, 7, 1.2)
    A = engine.atr(s, 7)
    D = strategies.dema(s.c, 200)
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
    out, busy = [], -1

    for i in range(warmup, len(s) - 2):
        if i <= busy or d[i] == 0 or d[i - 1] == 0:
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
        side = 1 if up else -1
        if (side == 1 and dnow < dprev) or (side == -1 and dnow > dprev):
            continue

        j = i + 1
        entry = s.o[j] + side * (half + costs.slippage)
        stop = s.c[i] - side * STOP_ATR * a
        risk = (entry - stop) * side
        if risk <= 0:
            continue
        tgt = entry + side * TARGET_R * risk

        peak_px = 0.0        # best favourable excursion in price
        peak_bar = j
        locked = False
        cur_stop = stop
        done = None

        for k in range(j, min(j + MAX_BARS, len(s))):
            fav = (s.h[k] - entry) if side == 1 else (entry - s.l[k])
            if fav > peak_px:
                peak_px, peak_bar = fav, k
            stall = k - peak_bar
            peak_r = peak_px / risk
            peak_money = peak_px * GBP_PER_POINT_POS

            # ---- intrabar, at the broker: stop then target. TIES LOSE.
            hs = (s.l[k] <= cur_stop) if side == 1 else (s.h[k] >= cur_stop)
            ht = (s.h[k] >= tgt) if side == 1 else (s.l[k] <= tgt)
            if hs:
                done = (cur_stop, "stop" if not locked else "locked", k); break
            if "target" in use and ht:
                done = (tgt, "target", k); break

            # ---- everything below is decided on the CLOSED bar
            c = s.c[k]
            now_px = (c - entry) * side
            now_money = now_px * GBP_PER_POINT_POS

            lock_hit = (peak_money >= LOCK_MONEY) or (LOCK_R > 0 and peak_r >= LOCK_R)
            if "lock" in use and not locked and lock_hit:
                be = entry + side * (2 * (half + costs.slippage) + comm_px)
                if (be - cur_stop) * side > 0:
                    cur_stop = be
                    locked = True

            if "trail" in use and peak_r >= TRAIL_ARM_R:
                t = c - side * TRAIL_ATR * a
                if (t - cur_stop) * side > 0:
                    cur_stop = t

            if "giveback" in use and peak_px > 0:
                armed = (peak_r >= GB_ARM_R) or (GB_ARM_MONEY > 0
                                                 and peak_money >= GB_ARM_MONEY)
                if armed and now_money >= GB_MIN_MONEY:
                    allow = gb_allowance(peak_r, stall)
                    if now_px <= peak_px * (1.0 - allow):
                        done = (c, "giveback", k); break

            if "stall" in use and stall >= MAX_STALL:
                done = (c, "stall", k); break

        if done is None:
            k = min(j + MAX_BARS, len(s)) - 1
            done = (s.c[k], "cap", k)
        px, why, k = done
        # Stops slip; limits do not. A stop is a market order the moment it is
        # touched, and the lock's stop sits 0.21 points from entry - inside the
        # spread's own width - so it is the most slippage-exposed thing in this
        # EA. Targets fill at their price or better.
        extra = STOP_SLIP if why in ("stop", "locked", "giveback", "stall", "cap") else 0.0
        fill = px - side * (half + costs.slippage + extra)
        out.append({"r": ((fill - entry) * side - comm_px) / risk, "why": why,
                    "pts": (fill - entry) * side - comm_px, "bars": k - j})
        busy = k
    return out


FULL = {"target", "trail", "giveback", "lock", "stall"}
VARIANTS = [
    ("THE EA, as it ships",      FULL),
    ("without the give-back",    FULL - {"giveback"}),
    ("without the lock",         FULL - {"lock"}),
    ("without the stall exit",   FULL - {"stall"}),
    ("without the trail",        FULL - {"trail"}),
    ("without the hard target",  FULL - {"target"}),
    ("trail + target only",      {"trail", "target"}),
    ("target only (stop and 3R)", {"target"}),
]


def sweep_lock():
    """The lock is the rule that actually runs this EA - it closes 53% of the
    trades - and it is set in ABSOLUTE MONEY, which does not survive a change of
    lot size. At 0.03 lots GBP0.50 is 0.21 points of gold. The round trip is
    about 0.56 points. So it arms BEFORE THE TRADE HAS COVERED ITS OWN COST and
    flattens it at a scratch. This prices the alternatives."""
    global LOCK_MONEY, LOCK_R
    print("\n" + "=" * 104)
    print("  WHERE SHOULD THE LOCK ARM? It closes 53% of trades, so this is the")
    print(f"  most consequential number in the file. At {LOTS} lots, GBP1 is"
          f" {1.0/GBP_PER_POINT_POS:.2f} points.")
    print("=" * 104)
    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        rt = c.spread + 2 * c.slippage
        print(f"\n  ### {sym} {tf}   round trip {rt:.2f} points"
              f" = GBP{rt*GBP_PER_POINT_POS:.2f} at {LOTS} lots")
        print(f"   {'lock arms at':<22}{'n':>6}{'win%':>8}{'expect':>10}{'PF':>7}"
              f"{'t':>8}{'points':>10}{'GBP':>9}{'bars':>7}")
        print("   " + "-" * 88)
        for label, money, r in (("GBP0.50 (shipped)", 0.50, 0.0),
                                ("GBP1.00", 1.00, 0.0),
                                ("GBP2.00", 2.00, 0.0),
                                ("GBP4.00", 4.00, 0.0),
                                ("GBP8.00", 8.00, 0.0),
                                ("0.5R", 1e9, 0.5),
                                ("1.0R", 1e9, 1.0),
                                ("1.5R", 1e9, 1.5),
                                ("off", 1e9, 0.0)):
            LOCK_MONEY, LOCK_R = money, r
            tr = run_stack(s, c, FULL)
            if len(tr) < 25:
                continue
            a_ = stat(tr)
            pts = sum(x["pts"] for x in tr)
            print(f"   {label:<22}{a_['n']:>6}{a_['win']:>7.1f}%{a_['exp']:>+9.3f}R"
                  f"{a_['pf']:>7.2f}{a_['t']:>+8.2f}{pts:>+10.0f}"
                  f"{pts*GBP_PER_POINT_POS:>+9.0f}"
                  f"{sum(x['bars'] for x in tr)/len(tr):>7.1f}")
    LOCK_MONEY, LOCK_R = 0.50, 0.0


def main():
    print("=" * 104)
    print("  P91b / E-083  DOES THE SUPERTREND EA TRADE WHAT WAS MEASURED?")
    print("  E-075 compared single exit policies. The EA runs SIX at once and")
    print("  whichever fires first wins. Each is removed here so its cost is a")
    print("  number. GOLD, 2.0 ATR stop, DEMA on, ADX off. Ties lose.")
    print(f"  Money is at {LOTS} lots, which is what Veer enters with.")
    print("=" * 104)

    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        print(f"\n  ### {sym} {tf}")
        print(f"   {'variant':<28}{'n':>6}{'win%':>8}{'expect':>10}{'PF':>7}"
              f"{'t':>8}{'points':>10}{'GBP':>10}{'bars':>7}")
        print("   " + "-" * 92)
        base = None
        for name, use in VARIANTS:
            tr = run_stack(s, c, use)
            if len(tr) < 25:
                continue
            a_ = stat(tr)
            pts = sum(x["pts"] for x in tr)
            if base is None:
                base = pts
            print(f"   {name:<28}{a_['n']:>6}{a_['win']:>7.1f}%{a_['exp']:>+9.3f}R"
                  f"{a_['pf']:>7.2f}{a_['t']:>+8.2f}{pts:>+10.0f}"
                  f"{pts*GBP_PER_POINT_POS:>+10.0f}"
                  f"{sum(x['bars'] for x in tr)/len(tr):>7.1f}")

        # what actually closes the trades
        tr = run_stack(s, c, FULL)
        if tr:
            print(f"\n   what closes an EA trade, and what each exit is worth:")
            print(f"   {'reason':<12}{'count':>7}{'share':>8}{'expect':>10}{'points':>10}")
            for w in ("target", "trail", "locked", "stop", "giveback", "stall", "cap"):
                sub = [x for x in tr if x["why"] == w]
                if not sub:
                    continue
                a_ = stat(sub)
                print(f"   {w:<12}{len(sub):>7}{100.0*len(sub)/len(tr):>7.0f}%"
                      f"{a_['exp']:>+9.3f}R{sum(x['pts'] for x in sub):>+10.0f}")


def sweep_slip():
    """The lock closes 53% of trades at a stop 0.21 points from entry. If those
    exits slip even slightly, a scratch becomes a loss 53% of the time. This is
    the single largest live-vs-backtest risk in this EA, so it gets priced."""
    global STOP_SLIP
    print("\n" + "=" * 104)
    print("  SLIPPAGE ON STOP-TYPE EXITS. The lock's stop is 0.21 points from")
    print("  entry, so this is where backtest and live diverge if they do.")
    print("=" * 104)
    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        print(f"\n  ### {sym} {tf}")
        print(f"   {'extra slip':>12}{'n':>6}{'win%':>8}{'expect':>10}{'PF':>7}"
              f"{'t':>8}{'points':>10}{'GBP':>9}")
        print("   " + "-" * 70)
        for sl in (0.00, 0.05, 0.10, 0.20, 0.30, 0.50):
            STOP_SLIP = sl
            tr = run_stack(s, c, FULL)
            if len(tr) < 25:
                continue
            a_ = stat(tr)
            pts = sum(x["pts"] for x in tr)
            print(f"   {sl:>11.2f}p{a_['n']:>6}{a_['win']:>7.1f}%{a_['exp']:>+9.3f}R"
                  f"{a_['pf']:>7.2f}{a_['t']:>+8.2f}{pts:>+10.0f}"
                  f"{pts*GBP_PER_POINT_POS:>+9.0f}")
    STOP_SLIP = 0.0
    print("\n  A stop 0.21 points from entry that slips 0.20 points is not a stop,")
    print("  it is a coin flip. Read the row that matches your broker, not the top one.")


def sweep_trail():
    """E-075 measured a plain 3-ATR trail ARMED AT 1R at +4622 points on GOLD
    1h. This EA's layered stack makes +1263 on the same bars. The EA arms its
    trail IMMEDIATELY (InpTrailAtR = 0.0), which is the one difference between
    them that is a single number, so it gets swept - with and without the lock,
    because the lock and the trail fight each other for the same trades."""
    global TRAIL_ARM_R, LOCK_MONEY
    print("\n" + "=" * 104)
    print("  WHEN SHOULD THE TRAIL ARM? E-075 says 1R on a clean trail. This EA")
    print("  arms it at 0R and layers a lock on top. Both are swept together.")
    print("=" * 104)
    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        print(f"\n  ### {sym} {tf}")
        print(f"   {'trail arms':>11}{'lock':>10}{'n':>6}{'win%':>8}{'expect':>10}"
              f"{'PF':>7}{'t':>8}{'points':>10}{'GBP':>9}{'bars':>7}")
        print("   " + "-" * 86)
        for lock_lbl, lock_v in (("GBP0.50", 0.50), ("off", 1e9)):
            for arm in (0.0, 0.5, 1.0, 1.5, 2.0):
                TRAIL_ARM_R, LOCK_MONEY = arm, lock_v
                tr = run_stack(s, c, FULL)
                if len(tr) < 25:
                    continue
                a_ = stat(tr)
                pts = sum(x["pts"] for x in tr)
                print(f"   {arm:>10.1f}R{lock_lbl:>10}{a_['n']:>6}{a_['win']:>7.1f}%"
                      f"{a_['exp']:>+9.3f}R{a_['pf']:>7.2f}{a_['t']:>+8.2f}"
                      f"{pts:>+10.0f}{pts*GBP_PER_POINT_POS:>+9.0f}"
                      f"{sum(x['bars'] for x in tr)/len(tr):>7.1f}")
    TRAIL_ARM_R, LOCK_MONEY = 0.0, 0.50


def sweep_scalefree():
    """THE THRESHOLDS ARE DENOMINATED IN MONEY AND THAT DOES NOT SURVIVE A
    CHANGE OF TIMEFRAME.

    InpLockPosMoney = GBP0.50 and InpGbArmMoney = GBP2.00 were set for an M1
    account where one R is about 1.3 points. On GOLD 1h one R is 28 points, so
    GBP2.00 is 0.03R and the give-back arms essentially at once; the trail never
    fires at all, which is why sweeping its arming level changed nothing.

    So the EA measured on 1h is not the EA that will run on M1, and neither
    number is informative about the other. The fix is to express both in R,
    which is scale-free: the same setting then means the same thing on every
    timeframe and at every lot size. This finds it.
    """
    global LOCK_MONEY, LOCK_R, GB_ARM_R, GB_ARM_MONEY
    GB_ARM_MONEY = 0.0          # money floors OFF: R only
    LOCK_MONEY = 1e9
    print("\n" + "=" * 104)
    print("  SCALE-FREE: lock and give-back both armed in R, money floors off.")
    print("  cell = expectancy / points. The same setting now means the same")
    print("  thing on M1 as on 1h, which is the only way to tune one from the other.")
    print("=" * 104)
    GBS = [0.5, 1.0, 2.0, 3.0]
    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        print(f"\n  ### {sym} {tf}")
        print(f"   {'lock arms':>10} |" + "".join(
            f"{('give-back at %.1fR' % g):>22}" for g in GBS))
        for lk in (0.0, 0.15, 0.25, 0.50, 1.00):
            cells = []
            for g in GBS:
                LOCK_R, GB_ARM_R = lk, g
                tr = run_stack(s, c, FULL if lk > 0 else FULL - {"lock"})
                if len(tr) < 25:
                    cells.append(" " * 21); continue
                a_ = stat(tr)
                pts = sum(x["pts"] for x in tr)
                cells.append(f"{a_['n']:>4} {a_['exp']:>+6.3f}R {pts:>+7.0f}")
            lbl = "off" if lk == 0.0 else f"{lk:.2f}R"
            print(f"   {lbl:>10} |" + "".join(f"{x:>22}" for x in cells))
    LOCK_MONEY, LOCK_R, GB_ARM_R, GB_ARM_MONEY = 0.50, 0.0, 3.0, 2.00


if __name__ == "__main__":
    main()
    sweep_lock()
    sweep_slip()
    sweep_trail()
    sweep_scalefree()
