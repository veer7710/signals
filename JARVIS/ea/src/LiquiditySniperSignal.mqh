//+------------------------------------------------------------------+
//|  LiquiditySniperSignal.mqh — the ONE concrete ISignalProvider     |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                   |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §1.15
//  MIRRORS: JARVIS/pine/LiquiditySniper_v1.pine
//
//  RESPONSIBILITY. Compose LiquidityEngine -> SweepEngine -> RegimeEngine
//  -> EntryEngine -> TargetEngine into one per-closed-bar call, and hand
//  the orchestrator a TradePlan in price. It owns the ORDER of those calls
//  and nothing else; it contains no strategy arithmetic of its own.
//
//  This is the only place where the sweep-continuation strategy is
//  assembled. Everything below it in the include graph is generic; the
//  strategy is swapped by writing a second ISignalProvider and changing
//  one `new` in LiquiditySniper.mq5.
//
//  STATUS OF THE STRATEGY IT IMPLEMENTS: PROMISING, NOT CONFIRMED.
//  E-018 measured ~+0.04R net per trade after gold's ~0.35 round trip and
//  a win against plain 20-bar breakout on 5/5 markets. It has NOT faced
//  a t-statistic against the ~3.0 multiple-testing bar (E-012), walk-
//  forward, cost sensitivity, or out-of-sample. E-003 — the sibling fade
//  variant — went +0.001R, then -0.031R at 2x spread, then -0.061R at 3x.
//  A +0.04R edge sits inside that same failure band. Phase 2 is BLOCKED
//  until those four tests pass (spec §0).
//
//  NOT COMPILED. Declarations only.
//+------------------------------------------------------------------+
#ifndef LS_LIQUIDITYSNIPERSIGNAL_MQH
#define LS_LIQUIDITYSNIPERSIGNAL_MQH

#include "Types.mqh"
#include "ISignalProvider.mqh"
#include "LiquidityEngine.mqh"
#include "SweepEngine.mqh"
#include "RegimeEngine.mqh"
#include "EntryEngine.mqh"
#include "TargetEngine.mqh"
#include "Logger.mqh"

//+------------------------------------------------------------------+
//| CLiquiditySniperSignal                                            |
//|                                                                   |
//| STATE OWNED: the five sub-engines BY VALUE (constructed here,     |
//|   destroyed here), the cached last RegimeState / SweepEvents for  |
//|   the parity row, and m_last_bar.                                 |
//|                                                                   |
//| MUST NOT KNOW ABOUT: equity, lots, spread, locks, tickets, CTrade.|
//|   None of those types are included from this file, so the         |
//|   restriction is enforced by the include graph, not by discipline.|
//+------------------------------------------------------------------+
class CLiquiditySniperSignal : public ISignalProvider
  {
private:
   CLiquidityEngine  m_levels;
   CSweepEngine      m_sweeps;
   CRegimeEngine     m_regime;
   CEntryEngine      m_entry;
   CTargetEngine     m_target;
   CLogger          *m_log;          // borrowed

   string            m_symbol;
   ENUM_TIMEFRAMES   m_tf;
   datetime          m_last_bar;
   int               m_session_from;  // parsed from InpSessionUtc, -1 = all hours
   int               m_session_to;

   RegimeState       m_last_regime;   // cached for ParityRow / Diagnostics
   SweepEvent        m_last_hi;
   SweepEvent        m_last_lo;
   ENUM_REJECT_STAGE m_last_reject;

   //--- Parses InpSessionUtc "HH-HH". "" -> from = to = -1 meaning all hours.
   //--- Returns false on a malformed string, which OnInit turns into
   //--- INIT_FAILED rather than silently trading 24h.
   bool              ParseSession(const string s, int &from_h, int &to_h) const;

public:
                     CLiquiditySniperSignal(void);
                    ~CLiquiditySniperSignal(void);

   virtual string    Name(void)    const override;   // "LiquiditySniper"
   virtual string    Version(void) const override;   // tracks the Pine version it mirrors

   virtual bool      Init(const string symbol, const ENUM_TIMEFRAMES tf,
                          CLogger *log, string &why) override;

   //--- max(ATR_MEDIAN_LEN + ATR_PERIOD, MAX_LEVEL_AGE_BARS) + 200.
   //--- The +200 is the parity warm-up: everything before bar 200 is
   //--- smoothing-seed noise, not a logic difference, and compare.py
   //--- excludes it (spec §5.1).
   virtual int       WarmupBars(void) const override;

   //--- THE CALL ORDER, and it is fixed:
   //---   1. m_regime.Update(bar_time)                 shift-1 reads only
   //---   2. m_levels.OnNewBar(bar_time, atr)          register new levels
   //---   3. m_sweeps.DetectOnClosedBar(...)           MARK ALL BROKEN SWEPT
   //---   4. m_regime.ExpansionOk(...)                 the boolean veto
   //---   5. m_sweeps.DisplacementOk(...)
   //---   6. m_entry.Evaluate(...)                     direction, entry, stop
   //---   7. m_target.Resolve(plan)                    target, R:R   <- AFTER 3
   //--- Steps 3 and 7 must not be reordered; see SweepEngine's ordering
   //--- contract. Steps 4 and 5 are cheap and run before 6 so the reject
   //--- code recorded is the FIRST reason, which is what the ledger counts.
   virtual bool      Evaluate(const datetime bar_time, TradePlan &plan) override;

   //--- Steps 1-3 only. Called on every closed bar even when the
   //--- orchestrator cannot trade (locked, at the position limit, spread
   //--- too wide), so the level registry never develops a hole and the
   //--- parity CSV has a row for every bar. Evaluate() may then be skipped.
   virtual bool      OnNewBarObserve(const datetime bar_time) override;

   virtual string    ParityRow(const datetime bar_time) const override;
   virtual string    Diagnostics(void) const override;
   virtual void      Reset(void) override;

   //--- Read-only access for the parity harness and the logger.
   //--- No caller may mutate registry state through these.
   int               LiveLevels(const bool is_high) const;
   bool              LastRegime(RegimeState &out) const;
  };

#endif // LS_LIQUIDITYSNIPERSIGNAL_MQH
//+------------------------------------------------------------------+
