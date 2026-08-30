//+------------------------------------------------------------------+
//|  PropFirmEngine.mqh — the part that saves the account             |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                   |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §3 (all of it)
//  SOURCE OF THE NUMBERS: JARVIS/research/PROP_FIRMS.md §4 and §7
//
//  THE UNIVERSAL MECHANIC. Every firm researched measures the daily limit
//  against EQUITY, not balance. Floating loss on an open position counts
//  IMMEDIATELY. YOU CAN FAIL AN ACCOUNT WITHOUT CLOSING A SINGLE TRADE AND
//  WITHOUT ANY STOP-LOSS BEING HIT. An EA that holds through a spike is
//  the single most common cause of funded-account death.
//
//  PROP_FIRMS.md §7: "the floating-loss monitor is the whole product.
//  Balance-based checks are useless — every worked example breaches on
//  unrealised P/L. If the engine only evaluates on trade close, it will
//  watch accounts die."
//
//  WHAT THIS REPLACES. v19.18 had InpMaxDailyLossPct = 40.0 (a 40% daily
//  stop is not a stop), its halt only set g_halt and cancelled pendings
//  WITHOUT FLATTENING OPEN POSITIONS, it had NO max-drawdown guard of any
//  kind anywhere in 20,695 lines, and g_dayStart was re-seeded on every
//  OnInit so a mid-day restart reset the daily baseline it was supposed to
//  be counting.
//
//  THE DESIGN TARGET, STATED AS AN ASSERTION OnInit ENFORCES:
//     InpRiskPctPerTrade * InpMaxConcurrentPositions   (0.70%)
//       <  DAILY_SOFT_FRACTION * InpDailyLossLimitPct  (1.00%)
//       <  DAILY_HARD_FRACTION * InpDailyLossLimitPct  (1.50%)
//       <  InpDailyLossLimitPct                        (3.00%)
//  OnInit returns INIT_FAILED if the chain is violated. These locks exist
//  for what the sizing model CANNOT see — a weekend gap through the stop,
//  a broker rejecting a close, a feed stall, a server-stripped stop, a
//  manual position on the same magic. THE PRIMARY DEFENCE IS THAT THE
//  POSITION IS SMALL ENOUGH THAT THE LIMIT IS UNREACHABLE.
//
//  UNVERIFIED, AND IT MATTERS. PROP_FIRMS.md §0: every firm rule came from
//  search-engine summaries of official pages, NOT from pages opened and
//  read. A human must confirm the four numbers that actually kill accounts
//  — daily-loss %, daily-loss BASIS, daily-loss RESET TIME, and whether
//  max drawdown TRAILS — on each firm's own help centre before any real
//  money is committed. Everything here is coded to the HARSHEST reading
//  precisely because the readings are unverified.
//
//  MUST NOT KNOW ABOUT: levels, sweeps, regime, entries, targets. It knows
//  equity, balance, the clock, and how to say no.
//
//  NOT COMPILED. Declarations only.
//+------------------------------------------------------------------+
#ifndef LS_PROPFIRMENGINE_MQH
#define LS_PROPFIRMENGINE_MQH

#include "Types.mqh"

class CLogger;

#define LS_ANCHOR_COUNT 4      // 21:00, 22:00, 23:00, 00:00 UTC

//+------------------------------------------------------------------+
//| DailyAnchor — one firm's idea of when "today" started.            |
//|                                                                   |
//| Four are maintained simultaneously under CLOCK_WORST_OF_ALL        |
//| because the offsets MOVE. PROP_FIRMS.md §4.2: "the server rolls    |
//| GMT+3 <-> GMT+2 seasonally. An engine hard-coded to one offset     |
//| will compute the wrong daily anchor twice a year, on the exact     |
//| days volatility is unusual." §7: the four reset clocks are "the    |
//| most likely source of a silent bug that fails an account at        |
//| 23:30 UTC on a Sunday in October."                                 |
//+------------------------------------------------------------------+
struct DailyAnchor
  {
   int               hour_utc;         // 21, 22, 23 or 0
   double            value;            // max(balance, equity) sampled AT the roll
   datetime          rolled_at;
   double            limit_cash;       // pct/100 * min(initial_balance, value)
   double            floor_equity;     // value - limit_cash
   bool              reconstructed;    // true -> limit_cash was halved, see below
  };

//+------------------------------------------------------------------+
//| CPropFirmEngine                                                   |
//|                                                                   |
//| STATE OWNED: the four anchors, the high-water mark, the            |
//|   consecutive-loss count, the DD_HARD latch, the active lock, and  |
//|   the last equity poll. ALL OF IT IS PERSISTED (§3.3, §4.4).       |
//+------------------------------------------------------------------+
class CPropFirmEngine
  {
private:
   double            m_daily_loss_pct;
   double            m_max_dd_pct;
   int               m_max_consec_losses;
   ENUM_RESET_CLOCK  m_clock;
   int               m_news_blackout_min;
   ulong             m_magic;
   CLogger          *m_log;            // borrowed

   double            m_initial_balance;
   DailyAnchor       m_anchor[LS_ANCHOR_COUNT];
   double            m_hwm;            // max(hwm, balance, equity), continuous
   int               m_consec_losses;
   bool              m_dd_hard_latched;
   ENUM_LOCK         m_lock;
   string            m_lock_reason;
   double            m_equity;
   double            m_balance;
   ulong             m_last_poll_ms;
   datetime          m_last_deal_seen; // for RegisterClosedTrade de-duplication

   //--- Roll any anchor whose hour has been crossed. Anchor value is
   //--- max(balance, equity) sampled at the instant of the crossing.
   //--- Taking the MAX automatically implements Alpha Capital's carry-over
   //--- rule: a position held across the boundary with a floating loss
   //--- gives equity < balance, the anchor is balance, and the day starts
   //--- with a reduced budget it never asked for. The rule falls out of the
   //--- formula rather than needing its own branch.
   void              RollAnchorsIfDue(void);

   //--- limit_cash = pct/100 * MIN(initial_balance, anchor.value).
   //--- Some firms compute the limit on the INITIAL balance (FundedNext:
   //--- "fixed $ = 5% of initial"), some on the day-start value. Whichever
   //--- gives the SMALLER allowance wins.
   void              RecomputeFloors(void);

   //--- Balance at an anchor is EXACTLY reconstructible from deal history:
   //---   balance_at_anchor = balance_now
   //---                     - SUM(profit+swap+commission) over HistoryDeals
   //---                       with DEAL_ENTRY_OUT and DEAL_TIME >= anchor_time
   //--- Equity at the anchor is NOT reconstructible, so the anchor becomes
   //---   MAX(balance_at_anchor, equity_now, balance_now)
   //--- which can only be too restrictive, never too permissive.
   //--- AND THEN limit_cash IS HALVED (ANCHOR_RECONSTRUCT_HAIRCUT) and
   //--- ANCHOR_RECONSTRUCTED is logged: a reconstructed anchor is an
   //--- estimate, and the engine pays for the uncertainty out of its own
   //--- allowance rather than out of the account.
   bool              ReconstructAnchor(const int idx);

   //--- Wilder-free, DST-aware conversion of a firm's local midnight into
   //--- UTC. NEVER hard-code an offset; recompute from the tz rules.
   int               AnchorHourFor(const ENUM_RESET_CLOCK clock) const;

public:
                     CPropFirmEngine(void);
                    ~CPropFirmEngine(void);

   bool              Init(const double daily_loss_pct, const double max_dd_pct,
                          const int max_consecutive_losses,
                          const ENUM_RESET_CLOCK clock,
                          const int news_blackout_min,
                          const ulong magic, CLogger *log);

   //--- Equity poll + anchor roll + full lock evaluation. Called on EVERY
   //--- TICK. ACCOUNT_EQUITY is the only acceptable source; it includes
   //--- floating P/L.
   void              OnTick(void);

   //--- Identical work on an EventSetMillisecondTimer(EQUITY_POLL_MS = 250)
   //--- timer. Both are required and neither alone is sufficient: OnTick
   //--- catches every price move while quotes flow; OnTimer catches the
   //--- case where ticks STOP arriving (thin book, weekend gap, feed stall)
   //--- while equity is still moving on the broker's side, and guarantees a
   //--- 250 ms staleness bound regardless of tick rate.
   void              OnTimer(void);

   //--- False if ANY lock is active. `lock` and `reason` are always set.
   bool              CanOpenNewPosition(ENUM_LOCK &lock, string &reason) const;

   //--- True ONLY for the four flatten locks: LOCK_DAILY_HARD, LOCK_DD_HARD,
   //--- LOCK_NEWS, LOCK_FRIDAY.
   //---
   //--- WHY SOFT AND HARD ARE SEPARATE. A soft lock stops the bleeding from
   //--- NEW decisions while letting existing positions reach their
   //--- broker-side stops, which are already inside the budget. A hard
   //--- flatten is an admission that the model of the account is no longer
   //--- trustworthy, and it fires at HALF the firm's actual limit precisely
   //--- so that the flatten itself — including slippage on the exit fills —
   //--- still lands inside the firm's number. Flattening AT the limit is
   //--- flattening PAST it.
   bool              MustFlatten(ENUM_LOCK &lock, string &reason) const;

   //--- Counted from HistoryDealGetInteger(DEAL_ENTRY) == DEAL_ENTRY_OUT
   //--- with our magic, ordered by DEAL_TIME, loss test on
   //--- DEAL_PROFIT + DEAL_SWAP + DEAL_COMMISSION < 0.
   //--- Reset to zero on any winning close AND at each anchor roll.
   //--- This is a CIRCUIT BREAKER for a regime or feed failure, not a
   //--- strategy input: 06_exit_experiment.md establishes that a low win
   //--- rate is correct for this style (30% wins at 3R beats 53% at 1R),
   //--- so a 4-loss streak is entirely normal.
   void              RegisterClosedTrade(const double profit_cash, const datetime close_time);

   double            Equity(void)              const;
   double            Balance(void)             const;
   //--- The anchor whose floor is the HIGHEST, i.e. the most restrictive.
   double            EffectiveAnchor(void)     const;
   double            DailyFloorEquity(void)    const;   // MAX over the four floors
   double            DailyLossCash(void)       const;   // effective_anchor - equity_now
   double            DailyHeadroomPct(void)    const;

   //--- hwm = MAX(hwm, balance_now, equity_now), updated every tick and
   //--- persisted. ASSUME TRAILING, ALWAYS — PROP_FIRMS.md §7 says "never
   //--- assume static", and §8 records that FTMO's 2-step static-vs-
   //--- ratcheting wording could not be separated from an official page.
   //--- Three harshness choices, all from §7:
   //---   trailing_basis = MAX(highest closed balance, highest equity)
   //---     — harsher than either alone; an intraday equity spike that was
   //---       never closed still raises the mark
   //---   trailing_updates = CONTINUOUS — harsher than EOD-only, and safe
   //---       under an EOD firm
   //---   trailing_locks_at_initial_balance = false — do not rely on a lock
   //---       existing even at firms that have one
   //--- The E8 One trap is the reason (PROP_FIRMS.md §4.4): "a strategy
   //--- that grinds up 3% then gives back 4% survives a static 8% drawdown
   //--- and dies instantly on a 4% dynamic one." If the real model is
   //--- static this engine is merely conservative; if it is dynamic and the
   //--- engine assumed static, the account is gone.
   double            HighWaterMark(void)       const;
   double            DrawdownFloorEquity(void) const;
   int               ConsecutiveLosses(void)   const;
   bool              DdHardLatched(void)       const;

   //--- All state to GlobalVariables prefixed GV_PREFIX + magic, so two
   //--- instances on different magics on the same terminal cannot collide.
   //--- MT5 global variables survive terminal restart and are flushed to
   //--- disk on shutdown. Called on every anchor roll, every lock change,
   //--- and in OnDeinit for EVERY deinit reason including REASON_RECOMPILE.
   bool              Persist(void);

   //--- Read back on OnInit. An anchor is accepted ONLY if its timestamp
   //--- falls inside the current anchor period; otherwise ReconstructAnchor
   //--- runs and the period's budget is halved.
   //--- LOCK_DD_HARD is LATCHED: the flag is re-read here and the engine
   //--- stays locked. It NEVER clears automatically. Only a human deleting
   //--- the LS_<magic>_DD_HARD global variable restarts trading.
   bool              Restore(void);

   //--- One line for the journal: effective anchor, floor, headroom %, hwm,
   //--- dd floor, streak, active lock. Printed on every lock transition.
   string            StatusLine(void) const;
  };

#endif // LS_PROPFIRMENGINE_MQH
//+------------------------------------------------------------------+
