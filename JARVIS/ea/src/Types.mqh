//+------------------------------------------------------------------+
//|  Types.mqh — shared enums and plain data structs                 |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                  |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §1.3
//
//  STATUS. Phase-1 declarations only. NOT COMPILED, NOT TICK-TESTED —
//  there is no MetaTrader and no MetaEditor in the container this was
//  authored in. Every other .mqh in this directory declares methods
//  without bodies; MQL5 requires a body for every declared method, so
//  the tree will not compile until Phase 2 supplies them. That is
//  intentional: the interfaces are being reviewed before they are built.
//
//  GATE. Phase 2 is BLOCKED until sweep-continuation clears the four
//  missing tests in EA_ARCHITECTURE.md §0 (t-stat vs the ~3.0 multiple-
//  testing bar, walk-forward, cost sensitivity, out-of-sample). See
//  JARVIS/state/EXPERIMENTS.md E-018 (PROMISING) and E-021 (in-sample
//  winners failed out-of-sample).
//
//  This file has ZERO dependencies. Nothing here allocates, reads the
//  account, or touches the terminal.
//+------------------------------------------------------------------+
#ifndef LS_TYPES_MQH
#define LS_TYPES_MQH

#define LS_DIR_LONG    (+1)
#define LS_DIR_SHORT   (-1)
#define LS_DIR_NONE      0     // sentinel ONLY. Never a tradable direction.

//--- How TargetEngine picks the take profit. Pine `tpMode`.
enum ENUM_TARGET_MODE
  {
   TARGET_NEXT_LIQUIDITY = 0,  // nearest LIVE level beyond entry; falls back to fixed R
   TARGET_FIXED_R        = 1   // entry + dir * InpFixedTargetR * risk_price
  };

//--- Prop-firm daily reset clock. §3.2.
//    CLOCK_WORST_OF_ALL keeps four anchors (21/22/23/00 UTC) and uses the
//    most restrictive floor. The single-clock values exist ONLY for the case
//    where a human has page-verified one firm's rule (PROP_FIRMS.md §0).
enum ENUM_RESET_CLOCK
  {
   CLOCK_WORST_OF_ALL = 0,     // default
   CLOCK_UTC          = 1,     // 00:00 UTC        (Maven)
   CLOCK_CET          = 2,     // 00:00 CE(S)T     (FTMO) — DST aware, 23:00/22:00 UTC
   CLOCK_GMT2         = 3,     // 00:00 GMT+2      -> 22:00 UTC
   CLOCK_GMT3         = 4      // 00:00 GMT+3      -> 21:00 UTC
  };

enum ENUM_LOG_LEVEL
  {
   LOG_SILENT  = 0,
   LOG_ERROR   = 1,
   LOG_TRADE   = 2,
   LOG_SIGNAL  = 3,
   LOG_VERBOSE = 4             // writes the 30-column parity CSV row every bar
  };

//--- Where a liquidity level came from. Pine: pivots, prev-day, session, round.
enum ENUM_LEVEL_SOURCE
  {
   SRC_PIVOT    = 0,
   SRC_PREV_DAY = 1,
   SRC_SESSION  = 2,
   SRC_ROUND    = 3
  };

//--- Every reason the EA can refuse to trade. §3.5 for the semantics of each.
enum ENUM_LOCK
  {
   LOCK_NONE = 0,
   LOCK_DAILY_SOFT,   // block new entries
   LOCK_DAILY_HARD,   // block + FLATTEN ALL
   LOCK_DD_SOFT,      // block, 0.5% hysteresis on clear
   LOCK_DD_HARD,      // block + FLATTEN ALL, latched, cleared only by a human
   LOCK_STREAK,       // block until next anchor roll
   LOCK_SPREAD,       // block THIS signal only
   LOCK_NEWS,         // block + FLATTEN ALL
   LOCK_FRIDAY,       // block + FLATTEN ALL at 20:00 UTC Friday
   LOCK_ROLLOVER,     // block new entries 21:55-22:10 UTC
   LOCK_MARGIN,       // block
   LOCK_CONNECT,      // block (terminal/account/EA trading disabled)
   LOCK_SPECS,        // block (symbol specs unusable)
   LOCK_DEMO          // OnInit returns INIT_FAILED
  };

//--- Every point at which a bar can stop being a trade. Logged and counted
//    by StatisticsEngine so the cost of each veto is visible, which is the
//    one habit worth keeping from v19.18 (its `~TAG` suppressed-attempt log).
enum ENUM_REJECT_STAGE
  {
   RJ_NONE = 0,
   RJ_NO_SWEEP,        // no level broken, or BOTH sides broken (outside bar)
   RJ_REGIME_ATR,      // atr_ratio > InpMaxAtrRatio
   RJ_REGIME_ADX,      // adx > InpMaxAdx
   RJ_SESSION,         // outside InpSessionUtc
   RJ_DISPLACEMENT,    // |close-open| < InpDisplacementAtr * atr
   RJ_LEVEL_AGE,       // level younger than InpMinLevelAgeBars
   RJ_STOP_TOO_WIDE,   // risk_price > InpMaxStopAtr * atr
   RJ_STOP_TOO_TIGHT,  // risk_price < SYMBOL_TRADE_STOPS_LEVEL * SYMBOL_POINT
   RJ_RR_TOO_LOW,      // reward_risk < InpMinRewardRisk
   RJ_SPREAD,          // spread > InpMaxSpreadPctOfStop % of risk_price
   RJ_LOTS_BELOW_MIN,  // sized lots < SYMBOL_VOLUME_MIN -> SKIP, never round up
   RJ_MAX_POSITIONS,   // InpMaxConcurrentPositions reached
   RJ_OPPOSING,        // a position in the other direction is open; no hedging
   RJ_PROPFIRM_LOCK,   // any ENUM_LOCK active
   RJ_SEND_FAILED      // OrderSend bucket B, or retries exhausted
  };

//+------------------------------------------------------------------+
//| A liquidity level in the registry. Mirrors Pine's parallel arrays |
//| (hiPx/hiBar/hiHits/hiDead), one struct instead of four arrays.    |
//+------------------------------------------------------------------+
struct LiquidityLevel
  {
   double            price;         // merged: max for highs, min for lows
   datetime          formed_time;   // ORIGINAL formation time; a merge does not refresh it
   int               formed_bar;    // ORIGINAL bar index; a merge does not refresh it
   int               touch_count;   // Pine `hits`. Equal highs hold MORE resting orders.
   bool              swept;         // Pine `dead`
   datetime          swept_time;
   bool              is_high;
   ENUM_LEVEL_SOURCE source;
  };

//+------------------------------------------------------------------+
//| One side's worth of "a level was taken out on this closed bar".   |
//| Describes WHAT HAPPENED. Says nothing about what to do about it.  |
//+------------------------------------------------------------------+
struct SweepEvent
  {
   bool              valid;
   int               direction;       // +1 a HIGH was broken, -1 a LOW was broken
   double            level_price;     // the MOST EXTREME level broken this bar
   int               level_touches;
   datetime          level_formed;
   double            break_open;
   double            break_high;
   double            break_low;
   double            break_close;
   double            displacement_atr;// |close-open| / atr  (BODY, not range)
   int               levels_killed;   // how many levels this bar marked swept
   datetime          bar_time;
  };

//+------------------------------------------------------------------+
//| The expansion gate's inputs and verdict, kept together so the     |
//| rejection can be logged with the numbers that caused it.          |
//+------------------------------------------------------------------+
struct RegimeState
  {
   double            atr;             // ATR(14) at shift 1
   double            atr_median;      // median of last 50 CLOSED-bar ATRs, even-n average
   double            atr_ratio;       // atr/atr_median, 1.0 if median <= 0
   double            adx;             // hand-rolled Wilder ADX(14) at shift 1, NOT iADX
   bool              in_session;
   bool              expansion_ok;
   ENUM_REJECT_STAGE reject;
  };

//+------------------------------------------------------------------+
//| A fully-specified intent to trade, in PRICE. `lots` is filled by  |
//| RiskEngine and by nothing else — no signal module writes it.      |
//+------------------------------------------------------------------+
struct TradePlan
  {
   bool              valid;
   int               direction;       // LS_DIR_LONG / LS_DIR_SHORT, never 0
   double            entry;           // signal_bar.close (the honestly-obtainable price)
   double            stop;
   double            target;
   double            risk_price;      // |entry - stop|, the R unit
   double            reward_risk;     // |target - entry| / risk_price
   double            lots;            // written by RiskEngine ONLY
   double            atr_at_signal;
   ENUM_REJECT_STAGE reject;
   datetime          signal_bar;
   string            source_name;     // ISignalProvider::Name(), for the log
  };

//+------------------------------------------------------------------+
//| Cache of an open position. NEVER the source of truth — the broker |
//| is. Rebuilt by TradeManagement::Adopt() on every OnInit.          |
//+------------------------------------------------------------------+
struct PositionState
  {
   ulong             ticket;
   int               direction;
   double            entry;
   double            stop_initial;
   double            target;
   double            r_distance;      // |entry - stop_initial|; 3-tier recovery, §4.4
   bool              r_approx;        // true if recovered from tier 3 with a moved stop
   datetime          open_time;
   int               bars_held;
   double            peak_r;          // MFE in R  (StatisticsEngine mirror)
   double            trough_r;        // MAE in R
   bool              stop_verified;   // POSITION_SL != 0 confirmed after fill
  };

//+------------------------------------------------------------------+
//| Symbol specification, read at RUNTIME. Nothing in this struct may |
//| ever appear as a literal anywhere else in the codebase. §4.2.     |
//+------------------------------------------------------------------+
struct SymbolSpecs
  {
   bool              valid;
   string            why_invalid;
   double            point;              // SYMBOL_POINT — used in EXACTLY two places
   int               digits;             // SYMBOL_DIGITS
   double            tick_size;          // SYMBOL_TRADE_TICK_SIZE — guard > 0 before dividing
   double            tick_value;         // SYMBOL_TRADE_TICK_VALUE
   double            contract_size;      // SYMBOL_TRADE_CONTRACT_SIZE — cross-check only
   double            volume_min;         // below this -> SKIP the trade
   double            volume_max;
   double            volume_step;        // floor to this, never round, never ceil
   int               stops_level_pts;    // SYMBOL_TRADE_STOPS_LEVEL
   int               freeze_level_pts;   // SYMBOL_TRADE_FREEZE_LEVEL
   bool              spread_float;       // SYMBOL_SPREAD_FLOAT
   long              filling_modes;      // SYMBOL_FILLING_MODE bitmask
   long              trade_mode;         // must be SYMBOL_TRADE_MODE_FULL
   double            money_per_lot_per_price; // tick_value / tick_size — the whole conversion
  };

#endif // LS_TYPES_MQH
//+------------------------------------------------------------------+
