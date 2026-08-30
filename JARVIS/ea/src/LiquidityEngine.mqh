//+------------------------------------------------------------------+
//|  LiquidityEngine.mqh — the liquidity level registry               |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                   |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §1.4
//  MIRRORS: JARVIS/pine/LiquiditySniper_v1.pine lines 197-262
//
//  RESPONSIBILITY. Maintain the registry of live liquidity levels from
//  four sources (swing pivots, previous-day H/L, session H/L, round
//  numbers) with merge-on-equal, FIFO eviction and age expiry.
//
//  This is a PURE PRICE-STRUCTURE CONTAINER. It does not decide whether a
//  break is tradable — only SweepEngine does — and it does not know a
//  trade exists.
//
//  MUST NOT KNOW ABOUT: open positions, lots, equity, spread, orders,
//  prop-firm state, the trade direction convention, or _Point.
//
//  NOT COMPILED. Declarations only.
//+------------------------------------------------------------------+
#ifndef LS_LIQUIDITYENGINE_MQH
#define LS_LIQUIDITYENGINE_MQH

#include "Types.mqh"

//+------------------------------------------------------------------+
//| CLiquidityEngine                                                  |
//|                                                                   |
//| STATE OWNED:                                                      |
//|   m_hi[], m_lo[]     insertion-ordered level arrays                |
//|   m_last_bar         idempotence guard                             |
//|   m_last_pdh/pdl     last registered previous-day extremes         |
//|   m_last_round       last registered round number                  |
//|   m_sess_id/hi/lo    rolling 8-hour session block extremes         |
//+------------------------------------------------------------------+
class CLiquidityEngine
  {
private:
   string            m_symbol;
   ENUM_TIMEFRAMES   m_tf;
   int               m_pivot_len;
   double            m_eq_tol_atr;
   int               m_max_age_bars;
   int               m_max_levels;
   bool              m_use_prev_day;
   bool              m_use_session;
   bool              m_use_round;
   double            m_round_step;

   LiquidityLevel    m_hi[];
   LiquidityLevel    m_lo[];
   datetime          m_last_bar;
   double            m_last_pdh;
   double            m_last_pdl;
   double            m_last_round;
   int               m_last_sess_id;
   double            m_sess_hi;
   double            m_sess_lo;
   int               m_bar_index;      // monotonic count of bars observed

   //--- PARITY-CRITICAL. Pine merges into an existing near-equal level
   //--- because equal highs/lows hold MORE resting orders than a lone
   //--- extreme. On merge: price becomes max (highs) / min (lows),
   //--- touch_count++, and formed_bar/formed_time KEEP THE ORIGINAL VALUE.
   //--- Tolerance boundary is INCLUSIVE: |stored - p| <= eq_tol * atr.
   //--- Parity tests P-02 (merge) and P-03 (boundary exclusivity).
   bool              AddLevel(const bool is_high, const double price,
                              const int formed_bar, const datetime formed_time,
                              const ENUM_LEVEL_SOURCE src, const double atr);

   //--- Pine's `array.shift` semantics: remove INDEX 0 — the oldest by
   //--- INSERTION ORDER, not the oldest by price age and not the
   //--- least-recently-touched. Parity test P-04 depends on this exactly.
   void              EvictOldest(const bool is_high);

   //--- Drop levels older than m_max_age_bars. Housekeeping only.
   void              ExpireAged(const int bar_index_now);

   //--- Candidate is at shift (m_pivot_len + PIVOT_CANDIDATE_SHIFT_ADD)
   //--- from the just-closed bar. Using +1 instead of +2 is ONE BAR OF
   //--- LOOK-AHEAD versus Pine and is the single most likely parity break
   //--- in the whole system. Derivation in spec §5.3; parity test P-01.
   bool              PivotHighCandidate(double &px, int &bar, datetime &t) const;
   bool              PivotLowCandidate (double &px, int &bar, datetime &t) const;

public:
                     CLiquidityEngine(void);
                    ~CLiquidityEngine(void);

   bool              Init(const string symbol, const ENUM_TIMEFRAMES tf,
                          const int pivot_len, const double eq_tol_atr,
                          const int max_age_bars, const int max_levels,
                          const bool use_prev_day, const bool use_session,
                          const bool use_round, const double round_step);

   //--- Called ONCE per closed bar. `atr` is the closed-bar ATR(14) at
   //--- shift 1. Registers new pivots, previous-day H/L, session H/L and
   //--- round levels; expires aged levels; evicts FIFO past max_levels.
   //--- Idempotent: a second call with the same bar_time is a no-op.
   //---
   //--- NOTE, deliberate Pine parity: previous-day, session and round
   //--- levels are registered with formed_bar = THE CURRENT BAR, not the
   //--- bar the extreme actually occurred on (Pine lines 243/251/259).
   //--- So InpMinLevelAgeBars counts from REGISTRATION for those three
   //--- sources. Parity test P-18.
   bool              OnNewBar(const datetime bar_time, const double atr);

   int               Count(const bool is_high) const;      // incl. swept
   int               CountLive(const bool is_high) const;  // unswept only
   bool              Get(const bool is_high, const int idx, LiquidityLevel &out) const;
   bool              MarkSwept(const bool is_high, const int idx, const datetime when);

   //--- Nearest UNSWEPT level strictly above / below a price.
   //--- Returns 0.0 when none exists — the caller must treat 0.0 as
   //--- "no level", never as a price. Pine's `na(lvlTp)` fallback.
   double            NearestLiveAbove(const double price) const;
   double            NearestLiveBelow(const double price) const;

   int               Snapshot(LiquidityLevel &dst[]) const; // parity dump / logging
   void              Reset(void);
  };

#endif // LS_LIQUIDITYENGINE_MQH
//+------------------------------------------------------------------+
