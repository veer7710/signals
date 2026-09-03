"""
BLOCK F / P79-P86 — FUNDED-ACCOUNT SIMULATOR.

`prop_sim.py` cannot answer the question this block asks, for four reasons that
are all the same reason: it scores an account on CLOSED TRADES.

  1. It checks the daily loss limit only at a day rollover, against the closed
     balance. Every firm in PROP_FIRMS.md measures the daily limit against
     EQUITY, floating loss included. Section 4 of that document is a worked
     example of an account failing while UP $1,500 on the day, with no stop hit
     and nothing closed. The old simulator can never see that event - which is
     the single most common way a funded account dies.
  2. It has no consistency rule at all. P84 says that rule kills most strategies
     that pass, and four of the eight firms researched enforce one.
  3. `max_eval_days` is compared against the count of TRADING days, so a 30-day
     window became ten calendar weeks for a strategy that trades three days a
     week.
  4. Its trailing drawdown follows the peak forever. E8 and Alpha Capital both
     LOCK the trail at the initial balance once the account is up, which is a
     materially different - and much more survivable - rule.

This file simulates the account BAR BY BAR instead. While a position is open,
each bar's worst excursion is marked to market and charged against the daily
limit and the drawdown floor immediately, exactly as a firm's risk system does.

Everything is in account currency and points. R is reported but never relied on
(E-074: expectancy is not money).

Run:  python3 JARVIS/research/funded.py
"""
from __future__ import annotations
import os, sys, datetime, random
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import Series, atr as watr


# ----------------------------------------------------------------- the rules
@dataclass
class Firm:
    """
    One firm's rule set. Every field is sourced from JARVIS/research/PROP_FIRMS.md
    and is tagged OFFICIAL-SUMMARY there, meaning: from the firm's own help
    centre via search summary, NOT from a page opened and read line by line.
    That document's own instruction stands - a human must confirm the four
    numbers that actually kill accounts before any money is committed.
    """
    name: str
    balance: float = 100_000.0
    profit_target_pct: float = 0.10
    daily_loss_pct: float = 0.05
    max_dd_pct: float = 0.10
    trailing: bool = False           # does the drawdown floor follow the peak
    trail_locks_at_start: bool = True  # ...and does it stop once back at initial
    dd_on_closed_only: bool = False  # E8: the floor rises on CLOSED profit only
    reset_hour_utc: int = 0          # the daily baseline clock
    min_trading_days: int = 4
    min_profitable_days: int = 0     # days each >= profitable_day_pct
    profitable_day_pct: float = 0.005
    consistency_day_pct: float = 0.0   # best DAY / total profit ceiling. 0 = none
    consistency_trade_pct: float = 0.0 # best TRADE / total profit ceiling (Maven)
    max_calendar_days: int = 0       # 0 = unlimited


# Presets. Numbers from PROP_FIRMS.md section 3.
FIRMS = {
    "FTMO_2STEP_P1": Firm("FTMO 2-step phase 1", profit_target_pct=0.10,
                          daily_loss_pct=0.05, max_dd_pct=0.10, trailing=False,
                          reset_hour_utc=23, min_trading_days=4),
    "FUNDEDNEXT_2STEP_P1": Firm("FundedNext Stellar 2-step phase 1",
                                profit_target_pct=0.08, daily_loss_pct=0.05,
                                max_dd_pct=0.10, trailing=True,
                                trail_locks_at_start=True, reset_hour_utc=21,
                                min_trading_days=5),
    "FUNDINGPIPS_2STEP_PRO": Firm("FundingPips 2 Step Pro", profit_target_pct=0.08,
                                  daily_loss_pct=0.03, max_dd_pct=0.06,
                                  trailing=False, min_trading_days=2,
                                  min_profitable_days=7, profitable_day_pct=0.005,
                                  consistency_day_pct=0.35),
    "E8_CLASSIC_P1": Firm("E8 Classic phase 1", profit_target_pct=0.08,
                          daily_loss_pct=0.04, max_dd_pct=0.08, trailing=True,
                          trail_locks_at_start=True, dd_on_closed_only=True,
                          min_trading_days=0),
    "E8_PERFORMANCE": Firm("E8 performance (funded)", profit_target_pct=0.06,
                           daily_loss_pct=0.04, max_dd_pct=0.08, trailing=True,
                           trail_locks_at_start=True, dd_on_closed_only=True,
                           min_trading_days=0, consistency_day_pct=0.40),
    "ALPHA_ONE": Firm("Alpha Capital Alpha One", profit_target_pct=0.10,
                      daily_loss_pct=0.04, max_dd_pct=0.06, trailing=True,
                      trail_locks_at_start=True, reset_hour_utc=21,
                      consistency_day_pct=0.40),
    "THE5ERS_HIGHSTAKES": Firm("The5ers High Stakes", profit_target_pct=0.10,
                               daily_loss_pct=0.05, max_dd_pct=0.10,
                               trailing=False, min_trading_days=0,
                               min_profitable_days=3, profitable_day_pct=0.005),
}


@dataclass
class Outcome:
    passed: bool
    reason: str
    calendar_days: int
    trading_days: int
    end_balance: float
    peak_balance: float
    worst_equity: float
    best_day: float
    best_trade: float
    total_profit: float
    consistency_day: float
    consistency_trade: float
    n_trades: int
    day_pnl: dict = field(default_factory=dict)


# ------------------------------------------------------- the account itself
def simulate(bars, positions, firm: Firm, risk_pct: float,
             value_per_point_per_lot=100.0, min_lot=0.01, lot_step=0.01,
             fx=1.0):
    """
    bars      : Series
    positions : list of dicts from build_positions() - one per trade, with the
                bar range it was open over so floating P&L can be marked.
    risk_pct  : fraction of CURRENT balance risked per trade.
    fx        : account-currency per USD. 1.0 keeps everything in USD.

    Walks the bars in order. On every bar the position's WORST excursion is
    marked to market, so the daily limit and the drawdown floor see floating
    loss the moment it happens, not when the trade closes.
    """
    by_entry = {}
    for p in positions:
        by_entry.setdefault(p["i_in"], []).append(p)

    bal = firm.balance
    peak = bal
    floor = bal * (1 - firm.max_dd_pct)
    worst_equity = bal
    open_pos = None
    day_key = None
    day_base = bal          # equity baseline for the daily limit
    day_pnl = {}
    trading_days = set()
    best_trade = 0.0
    n_trades = 0
    first_ts = bars.ts[positions[0]["i_in"]] if positions else bars.ts[0]

    def dkey(ts):
        d = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
        d -= datetime.timedelta(hours=firm.reset_hour_utc)
        return d.date()

    def done(passed, reason, i):
        cal = max(1, (bars.ts[i] - first_ts) // 86400)
        tot = bal - firm.balance
        bd = max(day_pnl.values()) if day_pnl else 0.0
        cd = (bd / tot) if tot > 0 else 0.0
        ct = (best_trade / tot) if tot > 0 else 0.0
        return Outcome(passed, reason, int(cal), len(trading_days), bal, peak,
                       worst_equity, bd, best_trade, tot, cd, ct, n_trades,
                       dict(day_pnl))

    for i in range(len(bars)):
        ts = bars.ts[i]
        k = dkey(ts)
        if k != day_key:
            day_key = k
            day_base = bal + _floating(open_pos, bars.o[i], value_per_point_per_lot, fx)
            day_pnl.setdefault(k, 0.0)

        # ---- mark the open position at this bar's WORST point
        if open_pos is not None:
            worst = bars.l[i] if open_pos["side"] > 0 else bars.h[i]
            eq_low = bal + _floating(open_pos, worst, value_per_point_per_lot, fx)
            worst_equity = min(worst_equity, eq_low)
            if eq_low <= day_base * (1 - firm.daily_loss_pct):
                return done(False, "DAILY LOSS breached on floating equity", i)
            if eq_low <= floor:
                return done(False, "MAX DRAWDOWN breached on floating equity", i)

            # ---- does it close on this bar?
            if i >= open_pos["i_out"]:
                pnl = _floating(open_pos, open_pos["exit"],
                                value_per_point_per_lot, fx)
                bal += pnl
                n_trades += 1
                best_trade = max(best_trade, pnl)
                day_pnl[k] = day_pnl.get(k, 0.0) + pnl
                trading_days.add(k)
                open_pos = None
                peak = max(peak, bal)
                if firm.trailing:
                    nf = peak * (1 - firm.max_dd_pct)
                    if firm.trail_locks_at_start:
                        nf = min(nf, firm.balance)
                    floor = max(floor, nf)
                if bal <= floor:
                    return done(False, "MAX DRAWDOWN breached on close", i)
                if bal <= day_base * (1 - firm.daily_loss_pct):
                    return done(False, "DAILY LOSS breached on close", i)
                # ---- pass test
                if bal >= firm.balance * (1 + firm.profit_target_pct):
                    prof_days = sum(1 for v in day_pnl.values()
                                    if v >= firm.balance * firm.profitable_day_pct)
                    if (len(trading_days) >= firm.min_trading_days
                            and prof_days >= firm.min_profitable_days):
                        r = done(True, "target reached", i)
                        # consistency is checked AT PAYOUT, not during
                        if firm.consistency_day_pct and r.consistency_day > firm.consistency_day_pct:
                            return Outcome(False, "CONSISTENCY: best day too large",
                                           *(_astuple_rest(r)))
                        if firm.consistency_trade_pct and r.consistency_trade > firm.consistency_trade_pct:
                            return Outcome(False, "CONSISTENCY: best trade too large",
                                           *(_astuple_rest(r)))
                        return r

        # ---- open a new one
        if open_pos is None and i in by_entry:
            p = by_entry[i][0]
            risk_ccy = bal * risk_pct
            pts = abs(p["entry"] - p["stop"])
            if pts > 0:
                lots = risk_ccy / (pts * value_per_point_per_lot * fx)
                lots = max(min_lot, round(lots / lot_step) * lot_step)
                open_pos = dict(p)
                open_pos["lots"] = lots

        if firm.max_calendar_days:
            if (ts - first_ts) // 86400 > firm.max_calendar_days:
                return done(False, "evaluation window expired", i)

    return done(False, "ran out of data before target", len(bars) - 1)


def _floating(pos, px, vpp, fx):
    if pos is None:
        return 0.0
    return pos["side"] * (px - pos["entry"]) * vpp * pos["lots"] * fx


def _astuple_rest(r: Outcome):
    return (r.calendar_days, r.trading_days, r.end_balance, r.peak_balance,
            r.worst_equity, r.best_day, r.best_trade, r.total_profit,
            r.consistency_day, r.consistency_trade, r.n_trades, r.day_pnl)


# ------------------------------------------------- turning signals into trades
def build_positions(s: Series, atr_len=7, mult=1.2, dema_len=200, warm=400,
                    stop_atr=2.0, trail_atr=3.0, max_bars=50, spread=0.46,
                    use_dema=True):
    """
    SuperTrendSniper 2.22's own trade, resolved to bar indices so the account
    simulator can mark it to market while it is open.

    The exit stack is the EA's shipped one: 2.0 ATR stop, a 3.0 ATR trail armed
    immediately (InpTrailAtR = 0), a 50-bar cap, and NO fixed target
    (InpTargetR = 0, per E-090 - a fixed target was destroying the tail).
    Ties lose: the stop is checked before anything else on every bar.
    """
    from pine_ea_parity import ea_supertrend_at, ea_dema_at
    A = watr(s, atr_len)
    n = len(s)
    start = max(warm + 10, dema_len * 4 + 20)
    out = []
    busy_until = -1
    for i in range(start, n - 1):
        if i <= busy_until:
            continue
        d, dp = ea_supertrend_at(s, i, atr_len, mult, warm)
        up, dn = d == -1 and dp == 1, d == 1 and dp == -1
        if not (up or dn):
            continue
        side = 1 if up else -1
        if use_dema:
            en, ep = ea_dema_at(s, i, dema_len, 1), ea_dema_at(s, i, dema_len, 3)
            if en is None or ep is None:
                continue
            if side > 0 and en < ep:
                continue
            if side < 0 and en > ep:
                continue
        a = A[i]
        if not a or a <= 0:
            continue
        entry = s.o[i + 1] + side * spread / 2.0
        stop = entry - side * stop_atr * a
        peak = entry
        i_out, exit_px = None, None
        for j in range(i + 1, min(i + 1 + max_bars, n)):
            if (side > 0 and s.l[j] <= stop) or (side < 0 and s.h[j] >= stop):
                i_out, exit_px = j, stop - side * spread / 2.0
                break
            peak = max(peak, s.h[j]) if side > 0 else min(peak, s.l[j])
            t = peak - side * trail_atr * a
            stop = max(stop, t) if side > 0 else min(stop, t)
        if i_out is None:
            i_out = min(i + max_bars, n - 1)
            exit_px = s.c[i_out] - side * spread / 2.0
        out.append({"i_in": i + 1, "i_out": i_out, "side": side, "entry": entry,
                    "stop": entry - side * stop_atr * a, "exit": exit_px,
                    "atr": a})
        busy_until = i_out
    return out


# ------------------------------------------------------------------- driver
def report(sym="GOLD", tf="15m", risk_pct=0.005, firms=None):
    s = engine.load(sym, tf)
    pos = build_positions(s)
    print(f"\n{sym} {tf}: {len(s)} bars, {len(pos)} trades from the EA's own signal")
    print(f"risk {risk_pct*100:.2f}% of balance per trade, "
          f"$100k account, gold at $100/point/lot\n")
    print(f"  {'firm':<34} {'result':<44} {'days':>5} {'end $':>10} "
          f"{'worst eq':>10} {'best day':>9}")
    print("  " + "-" * 116)
    for key in (firms or FIRMS):
        f = FIRMS[key]
        r = simulate(s, pos, f, risk_pct)
        tag = ("PASS  " if r.passed else "FAIL  ") + r.reason
        print(f"  {f.name:<34} {tag:<44} {r.calendar_days:>5} "
              f"{r.end_balance:>10,.0f} {r.worst_equity:>10,.0f} "
              f"{r.consistency_day*100:>8.1f}%")
    return s, pos


if __name__ == "__main__":
    print("=" * 118)
    print("  BLOCK F — one pass of the SuperTrend EA through seven real rule sets")
    print("=" * 118)
    for tf in ("15m", "1h"):
        report("GOLD", tf)


# ------------------------------------------------- P87: the funded-mode lever
# The consistency rule is a RATIO - best day divided by total profit - so it is
# scale-free. Halving the risk halves both halves and changes nothing. This is
# worth stating plainly because "size down to be safe" is the reflex answer and
# it is useless here.
#
# What DOES bound the ratio is refusing to keep trading on a day that has
# already gone well: a DAILY PROFIT LOCK. Stop for the day at +X% of the
# account and the best day cannot exceed X% of balance, so the ratio falls as
# the run lengthens. It costs the right-hand tail of every good day, which is
# exactly the tail E-090 said carries the profit - so this is a real trade, not
# a free win, and it has to be measured rather than assumed.
def simulate_locked(bars, positions, firm: Firm, risk_pct: float,
                    day_profit_lock: float = 0.0, day_loss_lock: float = 0.0,
                    value_per_point_per_lot=100.0, min_lot=0.01, lot_step=0.01,
                    fx=1.0):
    """`simulate` plus two per-day circuit breakers, both as a fraction of the
    STARTING balance: stop taking new trades once the day is up day_profit_lock
    or down day_loss_lock. Open trades are never cut - the lock gates entries
    only, which is what an EA can actually enforce without fighting its own
    exit logic."""
    by_entry = {}
    for p in positions:
        by_entry.setdefault(p["i_in"], []).append(p)
    bal, peak = firm.balance, firm.balance
    floor = bal * (1 - firm.max_dd_pct)
    worst_equity = bal
    open_pos, day_key, day_base = None, None, bal
    day_pnl, trading_days = {}, set()
    best_trade, n_trades, locked = 0.0, 0, False
    first_ts = bars.ts[positions[0]["i_in"]] if positions else bars.ts[0]

    def dkey(ts):
        d = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
        d -= datetime.timedelta(hours=firm.reset_hour_utc)
        return d.date()

    def done(passed, reason, i):
        cal = max(1, (bars.ts[i] - first_ts) // 86400)
        tot = bal - firm.balance
        bd = max(day_pnl.values()) if day_pnl else 0.0
        return Outcome(passed, reason, int(cal), len(trading_days), bal, peak,
                       worst_equity, bd, best_trade, tot,
                       (bd / tot) if tot > 0 else 0.0,
                       (best_trade / tot) if tot > 0 else 0.0, n_trades,
                       dict(day_pnl))

    for i in range(len(bars)):
        ts = bars.ts[i]
        k = dkey(ts)
        if k != day_key:
            day_key = k
            day_base = bal + _floating(open_pos, bars.o[i], value_per_point_per_lot, fx)
            day_pnl.setdefault(k, 0.0)
            locked = False
        if open_pos is not None:
            worst = bars.l[i] if open_pos["side"] > 0 else bars.h[i]
            eq_low = bal + _floating(open_pos, worst, value_per_point_per_lot, fx)
            worst_equity = min(worst_equity, eq_low)
            if eq_low <= day_base * (1 - firm.daily_loss_pct):
                return done(False, "DAILY LOSS breached on floating equity", i)
            if eq_low <= floor:
                return done(False, "MAX DRAWDOWN breached on floating equity", i)
            if i >= open_pos["i_out"]:
                pnl = _floating(open_pos, open_pos["exit"], value_per_point_per_lot, fx)
                bal += pnl
                n_trades += 1
                best_trade = max(best_trade, pnl)
                day_pnl[k] = day_pnl.get(k, 0.0) + pnl
                trading_days.add(k)
                open_pos = None
                peak = max(peak, bal)
                if firm.trailing:
                    nf = peak * (1 - firm.max_dd_pct)
                    if firm.trail_locks_at_start:
                        nf = min(nf, firm.balance)
                    floor = max(floor, nf)
                if bal <= floor:
                    return done(False, "MAX DRAWDOWN breached on close", i)
                if bal >= firm.balance * (1 + firm.profit_target_pct):
                    prof_days = sum(1 for v in day_pnl.values()
                                    if v >= firm.balance * firm.profitable_day_pct)
                    if (len(trading_days) >= firm.min_trading_days
                            and prof_days >= firm.min_profitable_days):
                        r = done(True, "target reached", i)
                        if firm.consistency_day_pct and r.consistency_day > firm.consistency_day_pct:
                            return Outcome(False, "CONSISTENCY: best day too large",
                                           *(_astuple_rest(r)))
                        if firm.consistency_trade_pct and r.consistency_trade > firm.consistency_trade_pct:
                            return Outcome(False, "CONSISTENCY: best trade too large",
                                           *(_astuple_rest(r)))
                        return r
        # ---- the day's circuit breakers, checked on CLOSED profit for the day
        if not locked:
            dp = day_pnl.get(k, 0.0)
            if day_profit_lock and dp >= firm.balance * day_profit_lock:
                locked = True
            if day_loss_lock and dp <= -firm.balance * day_loss_lock:
                locked = True
        if open_pos is None and not locked and i in by_entry:
            p = by_entry[i][0]
            pts = abs(p["entry"] - p["stop"])
            if pts > 0:
                lots = (bal * risk_pct) / (pts * value_per_point_per_lot * fx)
                lots = max(min_lot, round(lots / lot_step) * lot_step)
                open_pos = dict(p)
                open_pos["lots"] = lots
        if firm.max_calendar_days and (ts - first_ts) // 86400 > firm.max_calendar_days:
            return done(False, "evaluation window expired", i)
    return done(False, "ran out of data before target", len(bars) - 1)


# --------------------------------------------------- P82 / P86: pass rates
# One historical path is n=1. A pass/fail on it says almost nothing: the
# question a challenge fee actually asks is "what FRACTION of attempts pass",
# and that needs a distribution. Two resamplers, because they disagree about
# what matters and the disagreement is informative:
#
#   iid    trades drawn independently. Destroys every bit of serial structure,
#          so it answers "is the EDGE enough" with clustering removed.
#   block  contiguous runs of `blk` trades. Keeps losing streaks and winning
#          streaks intact, which is what actually breaches a daily limit.
#
# Trades are laid out on days using the REAL trades-per-day distribution from
# the historical run, so the consistency ratio is computed over a realistic
# number of days rather than an invented one.
def pass_rate(day_pnls_per_trade, trades_per_day, firm: Firm, risk_pct,
              trials=1000, mode="block", blk=5, seed=11,
              apply_consistency=True, day_profit_lock=0.0, max_days=400):
    """
    day_pnls_per_trade : per-trade R multiples from the historical run.
    trades_per_day     : the observed counts of trades per trading day.
    Returns (pass_rate, mean_days_to_outcome, fail_reason_counts).
    """
    rng = random.Random(seed)
    R = list(day_pnls_per_trade)
    TPD = list(trades_per_day) or [1]
    if not R:
        return 0.0, 0, {}
    npass, days_acc, reasons = 0, [], {}
    for _ in range(trials):
        bal, peak = firm.balance, firm.balance
        floor = bal * (1 - firm.max_dd_pct)
        day_pnl, reason, dcount = [], None, 0
        while dcount < max_days:
            dcount += 1
            base = bal
            today = 0.0
            for _t in range(rng.choice(TPD)):
                if day_profit_lock and today >= firm.balance * day_profit_lock:
                    break
                if mode == "iid":
                    r = rng.choice(R)
                else:
                    st = rng.randrange(len(R))
                    r = R[(st + (_t % blk)) % len(R)]
                pnl = bal * risk_pct * r
                bal += pnl
                today += pnl
                peak = max(peak, bal)
                if firm.trailing:
                    nf = peak * (1 - firm.max_dd_pct)
                    if firm.trail_locks_at_start:
                        nf = min(nf, firm.balance)
                    floor = max(floor, nf)
                if bal <= floor:
                    reason = "max drawdown"
                    break
            day_pnl.append(today)
            if reason:
                break
            if base > 0 and (base - bal) / base >= firm.daily_loss_pct:
                reason = "daily loss"
                break
            if bal >= firm.balance * (1 + firm.profit_target_pct):
                prof = sum(1 for v in day_pnl if v >= firm.balance * firm.profitable_day_pct)
                if dcount >= firm.min_trading_days and prof >= firm.min_profitable_days:
                    tot = bal - firm.balance
                    bd = max(day_pnl) if day_pnl else 0.0
                    if (apply_consistency and firm.consistency_day_pct
                            and tot > 0 and bd / tot > firm.consistency_day_pct):
                        reason = "consistency"
                    else:
                        reason = "PASS"
                    break
        if reason is None:
            reason = "ran out of days"
        reasons[reason] = reasons.get(reason, 0) + 1
        if reason == "PASS":
            npass += 1
            days_acc.append(dcount)
    return (npass / trials,
            (sum(days_acc) / len(days_acc)) if days_acc else 0,
            reasons)
