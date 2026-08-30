//+------------------------------------------------------------------+
//|  RegimeEngine.mqh — the expansion gate                            |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                   |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §1.6, §5.4
//
//  RESPONSIBILITY. Answer ONE question, on closed bars only:
//  is volatility compressed enough that a large move is likely to follow?
//
//  THE EVIDENCE, AND ITS LIMIT — read both halves.
//
//  E-019 (direct measurement, replicated GOLD 15m and 1h independently
//  over different periods) — P(3+ ATR move within 40 bars):
//      ADX 0-15              91% (15m)  90% (1h)
//      ADX >= 40             68%        66%
//      ATR >= 2x its median   —         25%
//      ATR 0.8-1.0x median   93%        83%
//  Volatility CONTRACTION precedes expansion. This predicts SIZE, never
//  DIRECTION. It stands: it was a measurement, not a fitted strategy.
//
//  E-021 (the correction, and it is the reason this gate is not trusted):
//  under a proper chronological 70/30 split, sweep-continuation configs
//  WITH this gate collapsed from 4/4 markets +0.166R in-sample to
//  1/4 markets -0.109R out-of-sample, and the two best out-of-sample
//  configs both had gate = none. E-020's apparent +0.108R for gating was
//  substantially in-sample fitting.
//
//  CONSEQUENCE FOR THIS MODULE: it must be cheap to turn OFF, and the
//  gate settings must be walk-forwarded before either is believed.
//  Set InpMaxAtrRatio >= 3.00 and InpMaxAdx = 60 to disable in practice.
//
//  THE GATE IS A BOOLEAN VETO AND NOTHING ELSE. It never touches the
//  target. E-020 tested adaptive targeting explicitly: gate-only +0.108R,
//  adaptive +0.001R, worse than a plain fixed 3R (+0.029R). TargetEngine
//  holds no reference to this class and cannot acquire one.
//
//  MUST NOT KNOW ABOUT: levels, sweeps, positions, money, targets.
//
//  HARD CONSTRAINT: every read is shift >= 1. There is NO shift-0 read in
//  this module. Buffers are copied with CopyBuffer(handle, 0, 1, n, buf).
//
//  NOT COMPILED. Declarations only.
//+------------------------------------------------------------------+
#ifndef LS_REGIMEENGINE_MQH
#define LS_REGIMEENGINE_MQH

#include "Types.mqh"

//+------------------------------------------------------------------+
//| CRegimeEngine                                                     |
//|                                                                   |
//| STATE OWNED: the ATR handle, the hand-rolled Wilder DMI/ADX state,|
//|   a rolling ATR ring buffer for the median, and the cached         |
//|   closed-bar values for the current bar.                           |
//+------------------------------------------------------------------+
class CRegimeEngine
  {
private:
   string            m_symbol;
   ENUM_TIMEFRAMES   m_tf;
   int               m_atr_period;
   int               m_atr_median_len;
   int               m_adx_period;

   int               m_h_atr;            // iATR handle; read at shift 1 only
   double            m_atr_ring[];       // last m_atr_median_len CLOSED-bar ATR values
   int               m_ring_fill;

   //--- Hand-rolled Wilder state. See the note on Adx() below for why the
   //--- built-in iADX is deliberately not used.
   double            m_rma_tr;
   double            m_rma_plus_dm;
   double            m_rma_minus_dm;
   double            m_rma_dx;
   bool              m_wilder_seeded;

   double            m_atr;
   double            m_atr_median;
   double            m_adx;
   datetime          m_last_bar;

   //--- Pine ta.rma(x,n): alpha = 1/n exponential smoothing SEEDED WITH AN
   //--- SMA of the first n values. Match that seed exactly or the first
   //--- few hundred bars diverge. Pine ta.tr(true) treats the first bar as
   //--- high - low; match that too.
   double            Rma(const double prev, const double value, const int n) const;

   //--- Pine ta.median(atr, 50). 50 IS EVEN, so Pine returns the AVERAGE OF
   //--- THE TWO MIDDLE VALUES after sorting. An implementation returning
   //--- "the 25th element" is off by half a gap and silently drifts the
   //--- gate boundary. Implement as: copy 50 values, ArraySort,
   //--- return (v[24] + v[25]) / 2.0.
   double            MedianOfRing(void) const;

public:
                     CRegimeEngine(void);
                    ~CRegimeEngine(void);

   bool              Init(const string symbol, const ENUM_TIMEFRAMES tf,
                          const int atr_period,       // ATR_PERIOD      = 14
                          const int atr_median_len,   // ATR_MEDIAN_LEN  = 50
                          const int adx_period);      // ADX_PERIOD      = 14

   //--- Recompute the cached closed-bar values. Reads shift 1 ONLY.
   //--- Idempotent per bar. Returns false on any CopyBuffer failure — and
   //--- the caller MUST treat false as "do not trade this bar", never as
   //--- "use the last value". v19.18's Buf() returned 0.0 on a failed
   //--- CopyBuffer, which silently skipped management for that tick (S1).
   bool              Update(const datetime bar_time);

   double            Atr(void)       const;   // ATR(14) at shift 1
   double            AtrMedian(void) const;   // even-n median, see MedianOfRing
   double            AtrRatio(void)  const;   // Atr()/AtrMedian(), 1.0 if median <= 0
   //--- Wilder ADX(14) at shift 1, HAND-ROLLED, NOT iADX.
   //--- MT5's built-in ADX has historically differed from Wilder's original
   //--- in how it handles bars where +DM and -DM are equal or both
   //--- non-positive, and in whether DI is smoothed before or after
   //--- normalisation. That is the highest-risk numeric divergence in the
   //--- system and it moves the gate. Follow Pine ta.dmi step for step:
   //---   up = high-high[1];  dn = low[1]-low
   //---   +DM = (up > dn && up > 0) ? up : 0
   //---   -DM = (dn > up && dn > 0) ? dn : 0
   //---   +DI = 100*rma(+DM,14)/rma(TR,14);  -DI likewise
   //---   DX  = 100*|+DI - -DI|/(+DI + -DI);  ADX = rma(DX,14)
   //--- Log iADX alongside it for one run so the built-in's error is on record.
   double            Adx(void)       const;

   //--- Wraps midnight correctly: from > to means (h >= from || h < to).
   //--- Interval is [from, to) — hour `to` is OUTSIDE. Parity test P-16.
   bool              InSession(const datetime t, const int from_hour_utc,
                               const int to_hour_utc) const;

   //--- Boundary is INCLUSIVE on both gates: atr_ratio <= max_atr_ratio and
   //--- adx <= max_adx both PASS at exact equality. A `<` on one side is a
   //--- silent, rare and extremely annoying divergence. Parity test P-17.
   //--- Fills `out` with the numbers that produced the verdict, and sets
   //--- out.reject to RJ_REGIME_ATR / RJ_REGIME_ADX / RJ_SESSION on failure.
   bool              ExpansionOk(const double max_atr_ratio, const double max_adx,
                                 const int from_hour_utc, const int to_hour_utc,
                                 RegimeState &out) const;
  };

#endif // LS_REGIMEENGINE_MQH
//+------------------------------------------------------------------+
