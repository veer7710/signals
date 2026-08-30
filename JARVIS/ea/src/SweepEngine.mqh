//+------------------------------------------------------------------+
//|  SweepEngine.mqh — which levels were taken out on this bar        |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                   |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §1.5
//  MIRRORS: JARVIS/pine/LiquiditySniper_v1.pine lines 300-335
//
//  RESPONSIBILITY. On a CLOSED bar, determine which live levels were taken
//  out, mark them swept, and emit at most one SweepEvent per side
//  describing the MOST EXTREME level broken.
//
//  It reports WHAT HAPPENED TO THE LEVELS. It does not know whether the
//  system trades continuation or reversal — that mapping lives in
//  EntryEngine, and it is the single most consequential finding in the
//  repository (E-017: FADE 44.5% at 1R vs a 49.2% coin flip; FOLLOW 54.1%,
//  better on 5/5 markets; mechanism is Osler's stop cascade — a stop-loss
//  to sell IS a market sell order, so a stop cluster is FUEL, not a spring).
//
//  MUST NOT KNOW ABOUT: direction preference, risk, lots, the account,
//  orders, or the regime.
//
//  NOT COMPILED. Declarations only.
//+------------------------------------------------------------------+
#ifndef LS_SWEEPENGINE_MQH
#define LS_SWEEPENGINE_MQH

#include "Types.mqh"
#include "LiquidityEngine.mqh"

//+------------------------------------------------------------------+
//| CSweepEngine                                                      |
//|                                                                   |
//| STATE OWNED: a BORROWED (not owned, not deleted) pointer to the   |
//|   level registry, plus m_last_bar for idempotence.                |
//+------------------------------------------------------------------+
class CSweepEngine
  {
private:
   CLiquidityEngine *m_levels;        // borrowed; this class never deletes it
   int               m_min_level_age_bars;
   double            m_displacement_atr;
   bool              m_require_close;
   datetime          m_last_bar;

public:
                     CSweepEngine(void);
                    ~CSweepEngine(void);

   bool              Init(CLiquidityEngine *levels, const int min_level_age_bars,
                          const double displacement_atr, const bool require_close);

   //--- Evaluates the just-closed bar.
   //---
   //--- ORDERING CONTRACT (load-bearing, and it is the subtlest rule in
   //--- the system). This function must run to completion, marking EVERY
   //--- broken level swept — not just the extreme one — BEFORE
   //--- TargetEngine queries NearestLiveAbove/Below. Pine's script order
   //--- does the sweep loops first and defines nextLiq afterwards.
   //--- Getting it backwards produces a target sitting on a level the
   //--- entry bar just destroyed, i.e. a target BEHIND the entry.
   //--- Parity tests P-09 (all die, highest wins) and P-10 (target reads
   //--- the registry after).
   //---
   //--- Break test: require_close ? (close > p) : (high > p) for highs.
   //--- A wick through is NOT a break — parity test P-05.
   //---
   //--- Returns true if at least one side produced a valid event.
   bool              DetectOnClosedBar(const datetime bar_time, const MqlRates &bar,
                                       const double atr, const int bar_index_now,
                                       SweepEvent &hi_event, SweepEvent &lo_event);

   //--- |close - open| >= displacement_atr * atr.
   //--- BODY, NOT RANGE. A bar with a 3.20 range and a 0.05 body fails.
   //--- Parity test P-07 exists specifically to catch a range implementation.
   //--- displacement_atr <= 0.0 disables the test (returns true).
   bool              DisplacementOk(const MqlRates &bar, const double atr) const;
  };

#endif // LS_SWEEPENGINE_MQH
//+------------------------------------------------------------------+
