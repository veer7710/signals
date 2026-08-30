//+------------------------------------------------------------------+
//|  TradeManagement.mqh — what happens after the fill                |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                   |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §1.9, §4.4
//
//  RESPONSIBILITY. Everything that happens to a position AFTER it is
//  filled: bar counting, the time exit, the optional (default-OFF) trail,
//  restart adoption, and the stop-integrity check.
//
//  THERE ARE EXACTLY THREE EXITS:
//     1. broker-side TAKE PROFIT at plan.target, attached at OrderSend
//     2. broker-side STOP LOSS   at plan.stop,   attached at OrderSend
//     3. TIME EXIT at InpMaxHoldBars closed bars held (default 40)
//  Plus one optional and off by default: a Chandelier trail that arms at
//  InpTrailArmR R and is disabled entirely at InpTrailArmR == 0.0, which
//  is the shipped default.
//
//  ============ THE PROHIBITIONS, AND WHY THEY ARE ABSOLUTE ============
//
//  NO BREAK-EVEN. There is no break-even code path anywhere in this class:
//  no T_MicroLock, no T_EarlyBE, no T_BeArmPts. E-008 / 06_exit_experiment.md
//  measured "break-even at 0.5R then trail" as the WORST exit rule on ALL
//  FOUR markets tested: GOLD -0.161R, US500 -0.188R, EURUSD -0.308R,
//  GBPUSD -0.293R, with the win rate collapsing to 15-20%. Early profit
//  protection scratches trades at break-even and removes the tail that pays
//  for everything. v19.18 armed its equivalent at ~0.24R — EARLIER than the
//  0.5R that was tested. This is the single mechanism most responsible for
//  the give-back that killed the old account. It is REMOVED, not reduced.
//
//  NO PEAK-ANCHORED ANYTHING. No giveback guard, no basket lock, no trade
//  lock, no exhaustion, no chop-stall, no momentum fade, no spike-peak, no
//  peak-bank. v19.18 ran EIGHT peak-anchored guards and THREE break-even
//  mechanisms simultaneously with no arbitration; whichever tripped first
//  ended the trade, so the realised exit was the minimum of ten. Every one
//  armed at >= one "noise band" and gave back >= one band, which means a
//  trade had to peak above ~2 bands before anything could bank it, and
//  anything above that surrendered 40-60% of itself BY CONSTRUCTION. That
//  is arithmetic, not a tuning miss.
//
//  E-008 also measured the ceiling: an oracle exiting at each trade's exact
//  best price returns +3.019R/trade on gold; the best REAL exit returns
//  +0.201R. The ~2.8R gap is the cost of not knowing the future, not a
//  defect to be engineered away. Every guard added to close that gap has
//  measured negative.
//
//  MONOTONE STOPS. ModifyStop is monotone by construction: for a long,
//  new_sl > current_sl or the call is refused INSIDE THIS MODULE. There is
//  no path that moves a stop toward entry.
//
//  MUST NOT KNOW ABOUT: levels, sweeps, regime, or the next signal.
//
//  NOT COMPILED. Declarations only.
//+------------------------------------------------------------------+
#ifndef LS_TRADEMANAGEMENT_MQH
#define LS_TRADEMANAGEMENT_MQH

#include "Types.mqh"
#include "ExecutionEngine.mqh"

class CLogger;
class CStatisticsEngine;

//+------------------------------------------------------------------+
//| CTradeManagement                                                  |
//|                                                                   |
//| STATE OWNED: PositionState m_pos[], rebuilt from the broker by     |
//|   Adopt(). IT IS A CACHE AND NEVER THE SOURCE OF TRUTH — the       |
//|   broker is. Any disagreement is resolved in the broker's favour.  |
//+------------------------------------------------------------------+
class CTradeManagement
  {
private:
   ulong             m_magic;
   string            m_symbol;
   ENUM_TIMEFRAMES   m_tf;
   int               m_max_hold_bars;
   double            m_trail_arm_r;      // 0.0 = trailing entirely disabled
   double            m_trail_atr_mult;
   CExecutionEngine *m_exec;             // borrowed
   CLogger          *m_log;              // borrowed
   CStatisticsEngine*m_stats;            // borrowed
   PositionState     m_pos[];

   //--- THREE-TIER r_distance RECOVERY (§4.4). r_distance cannot be read
   //--- directly from a position, and it is needed for R logging and the
   //--- trail arm.
   //---   1. GlobalVariable  LS_<magic>_R_<ticket>, written at fill, deleted
   //---      on close. Survives restart, flushed to disk by the terminal.
   //---   2. POSITION_COMMENT token "LS<dir><r_x100>" (e.g. LS+920 for a
   //---      long with r_distance 9.20), kept under 31 characters. Brokers
   //---      can and do REWRITE comments, so this is the fallback.
   //---   3. |POSITION_PRICE_OPEN - POSITION_SL| — exact whenever the stop
   //---      has not moved, which with InpTrailArmR = 0.0 (the default) is
   //---      ALWAYS. If the trail is ever enabled this tier becomes an
   //---      UNDERESTIMATE of R and the engine logs R_RECOVERED_APPROX and
   //---      sets PositionState.r_approx.
   bool              RecoverRDistance(const ulong ticket, double &r_dist, bool &approx);

   //--- Refuses any move toward entry. Refuses inside the freeze level.
   //--- Refuses entirely when m_trail_arm_r <= 0.0.
   bool              TryTrail(const int idx, const double atr);

public:
                     CTradeManagement(void);
                    ~CTradeManagement(void);

   bool              Init(const ulong magic, const string symbol,
                          const ENUM_TIMEFRAMES tf, const int max_hold_bars,
                          const double trail_arm_r, const double trail_atr_mult,
                          CExecutionEngine *exec, CLogger *log,
                          CStatisticsEngine *stats);

   //--- Rebuild m_pos from PositionsTotal() filtered by
   //--- POSITION_MAGIC == magic AND POSITION_SYMBOL == symbol. BOTH.
   //--- A position failing either test is INVISIBLE to this EA: never
   //--- modified, never closed, never counted.
   //--- Runs in OnInit. Returns the number adopted.
   //---
   //--- v19.18 persisted only its hour-of-day learning. On restart
   //--- QSP_TrackLive re-seeded each position's peak to the CURRENT P/L, so
   //--- a trade that had peaked at +5R and was sitting at +1R was recorded
   //--- as having peaked at +1R, and every peak-anchored guard then behaved
   //--- as though the move had never happened.
   int               Adopt(void);

   //--- The ONLY place management logic acts. NEVER called from a mid-bar
   //--- tick. Increments bars_held, applies the time exit, and applies the
   //--- trail if and only if it is enabled.
   //--- MIN_TRADE_DURATION_SEC (120 s) suppresses the time exit and the
   //--- trail inside the first two minutes, which is what keeps the EA
   //--- outside every firm's HFT / tick-scalping prohibition. The
   //--- broker-side stop and target still apply throughout — the position
   //--- is never unprotected in order to satisfy a conduct rule.
   void              OnNewBar(const datetime bar_time, const double atr);

   //--- The ONLY per-tick work this module does: verify that every open
   //--- position still carries a broker-side stop. A broker or a bridge can
   //--- strip a stop at ANY time, not only at fill. A position found with
   //--- POSITION_SL == 0 is re-stopped, and closed if that fails.
   void              VerifyStopsOnTick(void);

   int               CountOpen(void) const;
   int               CountOpen(const int direction) const;  // for the no-hedging rule
   //--- sum over open positions of |entry - stop| * money_per_price * lots.
   //--- Used by the orchestrator to refuse a signal that would push total
   //--- open risk past InpRiskPctPerTrade * InpMaxConcurrentPositions.
   double            TotalOpenRiskCash(void) const;
   bool              GetState(const ulong ticket, PositionState &out) const;

   //--- Called by the ORCHESTRATOR ONLY, on PropFirmEngine::MustFlatten().
   //--- Idempotent and retried: loops PositionsTotal() filtered by
   //--- magic+symbol, calls ClosePosition with unlimited_retries on each,
   //--- and re-runs on the next tick until the count is zero.
   void              FlattenAll(const string reason);
  };

#endif // LS_TRADEMANAGEMENT_MQH
//+------------------------------------------------------------------+
