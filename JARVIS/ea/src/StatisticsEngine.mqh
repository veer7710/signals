//+------------------------------------------------------------------+
//|  StatisticsEngine.mqh — measurement, and nothing else             |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                   |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §1.14
//
//  RESPONSIBILITY. Port of v19.18's QSP_TrackLive / QSP_TagRecord /
//  QSP_Recompute — the one genuinely valuable artefact in that 20,695-line
//  file. It measures MFE/MAE per ticket in R, keeps a per-exit-tag ledger
//  of R TAKEN versus R OFFERED AT THE PEAK, and — the key part — records
//  SUPPRESSED attempts so the cost of every veto is visible. That is real
//  quant work and 05_ea_deep_audit.md says to port it wholesale.
//
//  MUST NOT: influence any decision. It is read-only with respect to
//  trading. IF THIS CLASS WERE DELETED THE EA'S BEHAVIOUR WOULD BE
//  IDENTICAL. That property is the test of whether a change belongs here.
//
//  SLOT MANAGEMENT — fixes v19.18 bug S2. The old TrackProgress used
//  `if(g_pCount >= 200) g_pCount = 0;` — a blind wrap that overwrote slot 0
//  while its position was still open, so a live position could inherit
//  another ticket's progress record and be cut, or become un-cuttable.
//  (UpdatePeakR and TradePeakCash were fixed in seven other registries;
//  this one was missed.) Here: STATS_SLOTS fixed slots each with an in_use
//  flag; a slot is reclaimed ONLY when its ticket no longer appears in
//  PositionsTotal(); if all slots are in use the engine logs STATS_FULL and
//  STOPS RECORDING rather than corrupting a slot.
//
//  NOT COMPILED. Declarations only.
//+------------------------------------------------------------------+
#ifndef LS_STATISTICSENGINE_MQH
#define LS_STATISTICSENGINE_MQH

#include "Types.mqh"

class CLogger;

//+------------------------------------------------------------------+
//| StatSlot — per-ticket excursion record.                           |
//+------------------------------------------------------------------+
struct StatSlot
  {
   bool              in_use;
   ulong             ticket;
   double            r_distance;
   double            peak_r;        // MFE in R
   double            trough_r;      // MAE in R
   datetime          opened;
  };

//+------------------------------------------------------------------+
//| TagLedgerRow — one exit route's lifetime record.                  |
//| `suppressed` is the column that matters: it is what made the old  |
//| EA's instrumentation honest, because it showed that 21 of 32 exit |
//| tags fired ZERO times across 279 trades while the machinery to    |
//| support them still cost CPU, parameters and reasoning.            |
//+------------------------------------------------------------------+
struct TagLedgerRow
  {
   string            tag;            // "STOP" | "TARGET" | "TIME" | "FLATTEN:*"
   int               fired;
   int               suppressed;     // v19.18's "~TAG" counter
   double            sum_r_taken;
   double            sum_r_at_peak;  // what was on the table when it fired
   double            worst_r;
   double            best_r;
  };

//+------------------------------------------------------------------+
//| CStatisticsEngine                                                 |
//| STATE OWNED: STATS_SLOTS excursion slots, the tag ledger, and the |
//|   reject / lock histograms. All persisted.                        |
//+------------------------------------------------------------------+
class CStatisticsEngine
  {
private:
   CLogger          *m_log;          // borrowed
   ulong             m_magic;
   StatSlot          m_slot[];
   TagLedgerRow      m_ledger[];
   int               m_reject_count[];  // indexed by ENUM_REJECT_STAGE
   int               m_lock_count[];    // indexed by ENUM_LOCK
   bool              m_slots_full_logged;

   int               FindSlot(const ulong ticket) const;
   int               ClaimSlot(const ulong ticket);
   //--- Reclaims ONLY slots whose ticket is absent from PositionsTotal().
   //--- Never wraps, never overwrites a live slot.
   void              ReleaseClosedSlots(void);

public:
                     CStatisticsEngine(void);
                    ~CStatisticsEngine(void);

   bool              Init(CLogger *log, const ulong magic);

   //--- Per tick: update peak_r / trough_r for every open ticket.
   void              TrackOpenPositions(void);

   void              RecordReject(const ENUM_REJECT_STAGE stage);
   void              RecordFill(const ulong ticket, const double r_distance);
   void              RecordExit(const ulong ticket, const string tag,
                                const double r_realized, const double r_peak);
   //--- A route that WANTED to fire and was vetoed. With only three exits
   //--- this should be near zero; a non-zero count here is the earliest
   //--- warning that exit machinery is creeping back in.
   void              RecordSuppressed(const ulong ticket, const string tag,
                                      const double r_now, const double r_peak);
   void              RecordLock(const ENUM_LOCK lock);

   //--- Printed on OnDeinit and on demand. Includes the reject histogram,
   //--- the lock histogram, the tag ledger with R-taken vs R-offered, and
   //--- the fraction of trades that never reached 0.3R.
   //--- That last number is the one to watch: E-008 measured 23% across the
   //--- research entries and 81% for v19.18's own trades — "153 of 188
   //--- losers NEVER went GBP0.30 green". A high value there is an ENTRY
   //--- problem and no exit change will fix it.
   string            Report(void) const;

   bool              Persist(void);
   bool              Restore(void);
  };

#endif // LS_STATISTICSENGINE_MQH
//+------------------------------------------------------------------+
