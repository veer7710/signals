//+------------------------------------------------------------------+
//|                                              chart_vision.mqh    |
//|   "IT CAN'T SEE THE CHART." This is the part that looks at it.   |
//+------------------------------------------------------------------+
//
//  WHY THIS EXISTS - Veer, 2026-09-01, verbatim:
//    "this ea goes of trend and hence why it catches sideways movements and
//     doesnt close as early in loss as it can point being it CAN'T SEE THE
//     CHART it can't see a cluster is forming it also needs to understand
//     levels and reversals and like how trends flip as m1 is super sensitive
//     yk anything can happen like session opens can dump or sky rocket"
//
//  He is describing four blind spots, and they are four different questions.
//  This module answers each one SEPARATELY, because a bundle cannot be
//  measured and cannot be switched off one piece at a time:
//
//    1. CvClusterState()   - is price coiling into a range right now
//    2. CvReversal()       - has structure actually turned, as opposed to
//                            the SuperTrend printing its 40th flip of the day
//    3. CvSession()        - Tokyo / London / New York, in BROKER time, with
//                            the first-15-minutes window called out
//    4. CvLevelAbove/Below - not just "there is a line there" but how many
//                            times price touched it and how many times it
//                            actually REACTED to it
//
//    plus CvRead(CvView&)  - all four in one struct for the entry/exit code.
//
//  ------------------------------------------------------------------
//  WHAT THIS MODULE IS NOT
//  ------------------------------------------------------------------
//  It is NOT a filter, and nothing in it is wired into the entry logic. It
//  computes and reports. Whether any of it should ever refuse a trade is a
//  measurement question, and the measurement does not exist yet.
//
//  That sentence is here because of FAILURE_LOG F-010. Four gates were
//  stacked onto this EA in one afternoon and they refused essentially every
//  M1 gold entry, AFTER Veer had said repeatedly that the signal count is
//  fine and the problem is what happens after entry, and AFTER E-053 had
//  measured that filters improve total R in 5 of 8 markets - a coin flip -
//  and hurt precisely the markets that were winning.
//
//  So: every threshold below is a STARTING POINT, not a measured value.
//  None of them has been through study.py. The intended first use of this
//  module is to write its readings into the journal next to every signal, so
//  the thresholds are settled by Veer's own fills instead of by my taste.
//  Read README_chart_vision.md before wiring anything to a refusal.
//
//  ------------------------------------------------------------------
//  CLOSED BARS ONLY - and here is where I checked
//  ------------------------------------------------------------------
//  Every price this module reads comes through CvHigh/CvLow/CvOpen/CvClose/
//  CvBarTime, which are the ONLY four places bars are touched, and each one
//  returns 0 for shift < 1. There is no path from the forming bar to any
//  number here. The bar cache is filled by CopyRates(..., start_pos = 1,
//  ...), so the forming bar is not even in memory.
//
//  Two deliberate exceptions, both non-price and both stated so they are not
//  mistaken for oversights:
//    * the session block reads TimeCurrent(), a clock, not a price. A clock
//      does not repaint.
//    * CvRoomAtr(px, dir) takes whatever price the CALLER hands it, so entry
//      code can measure room from the live ask. That is the caller's choice
//      and the caller owns it; nothing cached here depends on it.
//
//  A subtler look-ahead trap, handled: a swing high at shift S is not KNOWN
//  until InpCvSwingBars bars later. The reversal test therefore refuses to
//  count a break-of-structure that happened before the swing it references
//  was confirmable. See CvComputeReversal(). Getting this wrong is how a
//  backtest invents a signal that live trading can never take.
//
//  ------------------------------------------------------------------
//  PERFORMANCE
//  ------------------------------------------------------------------
//  On M1 this can be called on every tick. Everything is computed ONCE per
//  closed bar into module globals and served from there, in the style of the
//  existing g_boxBar cache - CvRefresh() returns immediately unless
//  iTime(_Symbol,_Period,1) has changed. One CopyRates and one CopyBuffer per
//  bar; the level scan then runs entirely in memory instead of making tens of
//  thousands of iHigh/iLow calls. (The existing AddLevel() calls ATR() - a
//  CopyBuffer - up to 200 times per bar; this module does not repeat that.)
//  The only work done per TICK is the session arithmetic, which is a handful
//  of integer operations.
//
//  ------------------------------------------------------------------
//  HOW TO USE IT
//  ------------------------------------------------------------------
//    #include "modules/chart_vision.mqh"   (or paste this whole block in)
//    OnInit()   -> if(!CvInit()) return INIT_FAILED;
//    OnDeinit() -> CvDeinit();
//    anywhere   -> CvView v; if(CvRead(v) && v.consolidating) ...
//  CvRead() refreshes itself, so call order cannot break it.
//
//  NOT COMPILED. There is no MetaTrader in the environment this was written
//  in. It passes JARVIS/tools/check_mq5.py, which is evidence that the things
//  that checker models are absent - not evidence that it builds (L-009).
//+------------------------------------------------------------------+
#ifndef CHART_VISION_MQH
#define CHART_VISION_MQH

//============================ INPUTS ================================
input group "=== VISION: general ==="
input bool   InpCvEnabled       = true;   // master switch for the whole module
input int    InpCvAtrLen        = 14;     // ATR used for every distance below
input int    InpCvLookback      = 500;    // bars held in the module's own cache

input group "=== VISION: cluster / consolidation ==="
// COMPRESSION = (highest high - lowest low) over N bars, divided by the SUM
// of the N individual bar ranges. One-way movement puts every bar's range end
// to end, so the ratio approaches 1. Price coiling re-uses the same ground
// over and over, so the ratio falls toward 1/N. It is scale-free, which is
// why it is used instead of a points threshold.
//
// OVERLAP is the second, independent reading: the fraction of the last N bars
// that overlap the PREVIOUS bar's range by more than half of the smaller of
// the two. A three-bar spike with a long tail can look compressed; it cannot
// also look overlapped.
//
// RANGE-IN-ATR is the sanity check. A compressed, overlapped 40-point box on
// gold is not a cluster, it is a range you could trade inside of.
//
// THESE THREE NUMBERS ARE NOT MEASURED. They are starting points chosen so
// that on a chart they mark what a person would point at. Log them, then set
// them from the journal.
input bool   InpCvUseCluster    = true;
input int    InpCvClusterBars   = 20;     // N. On M1 that is 20 minutes
input double InpCvCompressMax   = 0.38;   // below this = compressed
input double InpCvOverlapMin    = 0.60;   // at least this fraction overlapping
input double InpCvRangeAtrMax   = 3.0;    // and the whole box under this x ATR
input double InpCvTightMult     = 0.72;   // TIGHT = these thresholds x this
input int    InpCvClusterScan   = 40;     // bars to look back for "how long"

input group "=== VISION: reversal (NOT a SuperTrend flip) ==="
// A FLIP is one indicator changing its mind; on M1 gold that happens dozens
// of times a day and E-053 counted 16 in 24 minutes inside a $4.50 range.
// A REVERSAL is a two-part event and needs both parts:
//    (a) FAILURE - the market tried to extend and could not. The newest
//        confirmed swing high is not above the previous one (or the newest
//        swing low is not below the previous one).
//    (b) BREAK OF STRUCTURE - a bar then CLOSED through the swing on the
//        other side of that failed leg, by a real margin.
// One opposite candle satisfies neither. It cannot: (a) needs two confirmed
// swings, which take at least 2*InpCvSwingBars+2 bars to exist, and (b) needs
// a close beyond a level those swings defined. Veer has said explicitly and
// repeatedly that a single opposite candle must not count, and the structure
// of the test - not a threshold in it - is what enforces that.
input bool   InpCvUseReversal   = true;
input int    InpCvSwingBars     = 3;      // bars either side of a swing point
input double InpCvEqTolAtr      = 0.10;   // "did not make a new extreme" slack
input double InpCvMinLegAtr     = 0.75;   // ignore legs smaller than this
input double InpCvBosBufAtr     = 0.10;   // the break must clear by this much
input int    InpCvMinStructBars = 5;      // the failed leg must span this many
input int    InpCvRevLifeBars   = 20;     // a reversal is news for this long

input group "=== VISION: sessions (broker time, derived at runtime) ==="
// BROKER TIME IS NOT UTC and the offset is not knowable in advance: most
// MT5 servers run GMT+2/GMT+3 and switch with European DST, so a hardcoded
// hour is wrong for part of the year on the same server. The offset is
// derived at runtime from TimeCurrent() - TimeGMT() and re-derived every bar,
// so a DST change fixes itself.
//
// Opens are given in GMT MINUTES FROM MIDNIGHT, standard (winter) time:
//   Tokyo   00:00 GMT = 09:00 JST. Japan has no DST.
//   London  08:00 GMT = 08:00 local winter; EU DST moves it to 07:00 GMT.
//   New York 13:30 GMT = 08:30 ET, which is the US data drop and the COMEX
//            open, i.e. the one that moves gold. US DST moves it to 12:30
//            GMT. The 14:30 GMT equity open is inside the burst window of it.
input bool   InpCvUseSession    = true;
input bool   InpCvAutoDst       = true;   // shift London/NY in summer
input int    InpCvGmtOffsetMin  = 9999;   // 9999 = derive it; else force it
input int    InpCvTokyoOpenGmt  = 0;      // 00:00 GMT
input int    InpCvTokyoLenMin   = 480;    // 8h
input int    InpCvLondonOpenGmt = 480;    // 08:00 GMT
input int    InpCvLondonLenMin  = 510;    // to 16:30 GMT
input int    InpCvNyOpenGmt     = 810;    // 13:30 GMT
input int    InpCvNyLenMin      = 450;    // to 21:00 GMT
input int    InpCvOpenBurstMin  = 15;     // "can dump or sky rocket"
input int    InpCvOpenHourMin   = 60;     // the hour around an open

input group "=== VISION: level quality ==="
// The existing BuildLevels/NearAnyLevel answers "is there a line near here".
// That is not the question. A line price has never touched, a line it has
// touched and sliced straight through, and a line it has bounced off three
// times are three different objects, and only the third one is worth pricing
// a trade around.
//
// TOUCH   = price came within InpCvTouchAtr x ATR of the level. Consecutive
//           bars in the zone count ONCE; a new touch needs price to have left
//           by InpCvLeaveAtr x ATR first, otherwise twenty bars parked on a
//           level would score as twenty touches.
// REACTION= a touch that was followed, within InpCvReactBars bars, by a move
//           of InpCvReactAtr x ATR back the way price came, with NO close
//           through the level in between. That last clause is what separates
//           a rejection from a breakout that happened to pause.
input bool   InpCvUseLevels     = true;
input int    InpCvLevelSwings   = 20;     // newest N swing highs and N lows
input bool   InpCvUseDayLevels  = true;   // previous day high / low
input bool   InpCvUseWeekLevels = true;   // previous week high / low
input double InpCvRoundStep     = 5.0;    // round-number grid, 0 = off
input int    InpCvRoundCount    = 3;      // how many either side of price
input double InpCvMergeAtr      = 0.20;   // levels closer than this are one
input double InpCvTouchAtr      = 0.25;   // "at" the level
input double InpCvLeaveAtr      = 0.60;   // must clear this to re-touch
input double InpCvReactAtr      = 1.00;   // a reaction is this big a move away
input int    InpCvReactBars     = 12;     // and happens within this many bars

//============================ TYPES =================================
enum ENUM_CV_CLUSTER
{
   CV_CLUSTER_OFF     = 0,   // the module is off or has no data - NO OPINION
   CV_CLUSTER_NO      = 1,   // price is going somewhere
   CV_CLUSTER_FORMING = 2,   // coiling
   CV_CLUSTER_TIGHT   = 3    // coiling hard
};

enum ENUM_CV_SESSION
{
   CV_SESS_UNKNOWN   = 0,    // module off, or no clock - NO OPINION
   CV_SESS_CLOSED    = 1,    // weekend, or the 21:00-00:00 GMT dead zone
   CV_SESS_TOKYO     = 2,
   CV_SESS_LONDON    = 3,
   CV_SESS_NEWYORK   = 4,
   CV_SESS_LON_NY    = 5     // the overlap, where gold does most of its work
};

// Level kinds, so the journal can say WHICH kind of level held.
#define CV_KIND_SWINGHI 1
#define CV_KIND_SWINGLO 2
#define CV_KIND_DAY     3
#define CV_KIND_WEEK    4
#define CV_KIND_ROUND   5

// Returned by CvRoomAtr()/CvView when there is no level on that side at all.
// It is NOT zero, deliberately: a caller that reads 0 as "no room" and
// refuses the trade would have the meaning exactly backwards.
#define CV_OPEN_AIR 99.0

struct CvView
{
   bool            ready;            // false = NO OPINION. Do not gate on it.
   double          atr;              // the ATR every other figure is in
   double          price;            // close of the last CLOSED bar

   // --- 1. cluster
   bool            consolidating;    // FORMING or TIGHT
   ENUM_CV_CLUSTER cluster;
   double          compression;      // total range / sum of bar ranges
   double          overlapFrac;      // fraction of bars overlapping the prior
   double          rangeAtr;         // the box height in ATR
   int             clusterBars;      // how many bars it has held for
   double          clusterHigh;
   double          clusterLow;
   int             clusterBreak;     // +1 broke up, -1 broke down, 0 no

   // --- 2. reversal
   int             reversal;         // -1 bearish, 0 none, +1 bullish
   int             reversalAge;      // bars since the break bar closed
   double          swingHigh;        // newest CONFIRMED swing high
   double          swingLow;         // newest CONFIRMED swing low
   int             swingHighAge;
   int             swingLowAge;

   // --- 3. session
   ENUM_CV_SESSION session;
   int             minsIntoSession;  // -1 when no session is open
   bool            openBurst;        // first InpCvOpenBurstMin after an open
   bool            openHour;         // first InpCvOpenHourMin after an open
   int             gmtOffsetMin;     // broker minus GMT, derived at runtime

   // --- 4. levels
   double          levelAbove;       // 0 = none found
   double          levelBelow;
   double          roomAboveAtr;     // CV_OPEN_AIR when there is no level
   double          roomBelowAtr;
   int             touchAbove;
   int             touchBelow;
   int             reactAbove;
   int             reactBelow;
   int             qualAbove;        // 0 untested .. 3 repeatedly respected
   int             qualBelow;
   int             kindAbove;        // CV_KIND_*
   int             kindBelow;
};

//============================ STATE =================================
// Everything here is recomputed once per CLOSED bar by CvRefresh() and read
// from cache for the rest of that bar. Same pattern as g_boxBar in the EA.
datetime g_cvBar        = 0;         // the closed bar this cache describes
bool     g_cvReady      = false;
int      g_cvAtrHandle  = INVALID_HANDLE;
double   g_cvAtr        = 0.0;
int      g_cvBarsN      = 0;         // bars actually in the cache
MqlRates g_cvBars[];                 // index 0 = shift 1 = last CLOSED bar

#define MAX_CV_SWINGS 64
double   g_cvShPrice[MAX_CV_SWINGS]; // swing HIGHS, newest first
int      g_cvShShift[MAX_CV_SWINGS];
int      g_cvShN       = 0;
double   g_cvSlPrice[MAX_CV_SWINGS]; // swing LOWS, newest first
int      g_cvSlShift[MAX_CV_SWINGS];
int      g_cvSlN       = 0;

// cluster cache
int      g_cvClState   = 0;
double   g_cvClComp    = 0.0;
double   g_cvClOvl     = 0.0;
double   g_cvClRange   = 0.0;
int      g_cvClBars    = 0;
double   g_cvClHigh    = 0.0;
double   g_cvClLow     = 0.0;
int      g_cvClBreak   = 0;

// reversal cache
int      g_cvRev       = 0;
int      g_cvRevAge    = 0;

// level cache
#define MAX_CV_LEVELS 96
double   g_cvLvPrice[MAX_CV_LEVELS];
int      g_cvLvTouch[MAX_CV_LEVELS];
int      g_cvLvReact[MAX_CV_LEVELS];
int      g_cvLvLast[MAX_CV_LEVELS];  // shift of the most recent touch
int      g_cvLvKind[MAX_CV_LEVELS];
int      g_cvLvN       = 0;

// session cache - only the DST/offset part is per-bar, the arithmetic is
// per-call because minutes-into-session has to keep moving between bars.
int      g_cvGmtOff    = 0;          // broker minus GMT, in MINUTES
bool     g_cvOffKnown  = false;

//====================== FORWARD DECLARATIONS ========================
// The EA this module is written for was shipped three times in a state that
// would not compile because of an ordering rule I had assumed rather than
// checked (F-006/F-007/F-008). Prototypes make the question moot.
bool            CvInit();
void            CvDeinit();
bool            CvRefresh();
bool            CvRead(CvView &v);
double          CvHigh(int shift);
double          CvLow(int shift);
double          CvClose(int shift);
double          CvOpen(int shift);
datetime        CvBarTime(int shift);
double          CvAtr();
void            CvLoadBars();
void            CvComputeSwings();
void            CvComputeCluster();
bool            CvClusterAt(int endShift, double &comp, double &ovl, double &rngAtr, double &hi, double &lo);
void            CvComputeReversal();
void            CvComputeLevels();
void            CvAddLevel(double p, int kind);
void            CvScoreLevel(int idx);
ENUM_CV_CLUSTER CvClusterState();
int             CvReversal();
ENUM_CV_SESSION CvSession();
bool            CvSessionAt(datetime brokerTime, ENUM_CV_SESSION &sess, int &minsIn, bool &burst, bool &hour);
int             CvGmtOffsetMin();
bool            CvIsEuDst(datetime gmt);
bool            CvIsUsDst(datetime gmt);
datetime        CvMakeUtc(int year, int mon, int day, int hour);
int             CvDowUtc(datetime t);
datetime        CvNthSundayUtc(int year, int mon, int nth, int hour);
datetime        CvLastSundayUtc(int year, int mon, int lastDay, int hour);
int             CvNearestLevel(double from, int dir);
double          CvRoomAtr(double from, int dir);
int             CvLevelQuality(int idx);
string          CvStatus();

//====================== BAR ACCESS ==================================
// THESE FOUR FUNCTIONS ARE THE ONLY PLACE THIS MODULE TOUCHES A BAR.
// Every one of them returns 0 for shift < 1, so there is no route from the
// forming bar into any number this module produces. That is the invariant the
// whole file rests on, and keeping it in four small functions is what makes
// it auditable in one screen instead of scattered over eight hundred lines.
//
// They read from a per-bar CopyRates cache rather than calling iHigh/iLow
// each time. Same values, one system call instead of tens of thousands: the
// level scan alone asks for ~25,000 highs and lows per bar, and on M1 with a
// per-tick caller that arithmetic decides whether the EA keeps up.
double CvHigh(int shift)
{
   if(shift < 1) return 0.0;
   int i = shift - 1;
   if(i >= 0 && i < g_cvBarsN) return g_cvBars[i].high;
   return iHigh(_Symbol, _Period, shift);
}

double CvLow(int shift)
{
   if(shift < 1) return 0.0;
   int i = shift - 1;
   if(i >= 0 && i < g_cvBarsN) return g_cvBars[i].low;
   return iLow(_Symbol, _Period, shift);
}

double CvClose(int shift)
{
   if(shift < 1) return 0.0;
   int i = shift - 1;
   if(i >= 0 && i < g_cvBarsN) return g_cvBars[i].close;
   return iClose(_Symbol, _Period, shift);
}

double CvOpen(int shift)
{
   if(shift < 1) return 0.0;
   int i = shift - 1;
   if(i >= 0 && i < g_cvBarsN) return g_cvBars[i].open;
   return iOpen(_Symbol, _Period, shift);
}

datetime CvBarTime(int shift)
{
   if(shift < 1) return 0;
   int i = shift - 1;
   if(i >= 0 && i < g_cvBarsN) return g_cvBars[i].time;
   return iTime(_Symbol, _Period, shift);
}

double CvAtr()
{
   return g_cvAtr;
}

// Fill the cache from the last CLOSED bar backwards. start_pos = 1 is the
// reason the forming bar is not in memory at all.
void CvLoadBars()
{
   g_cvBarsN = 0;
   int avail = Bars(_Symbol, _Period);
   int want  = MathMin(InpCvLookback, avail - 2);
   if(want < 60) return;

   int got = CopyRates(_Symbol, _Period, 1, want, g_cvBars);
   if(got <= 0) return;

   // Set AFTER the copy, so index 0 is the newest element regardless of the
   // order CopyRates filled the array in. (The reasoning quoted in the EA for
   // this line is wrong - CopyRates fills deterministically - but the call is
   // still required, because ArraySetAsSeries is what makes [0] mean "newest"
   // for the READS below. Audit item M14.)
   ArraySetAsSeries(g_cvBars, true);
   g_cvBarsN = got;
}

//====================== SWINGS ======================================
// A swing high at shift S is a bar whose high is the highest of the
// InpCvSwingBars bars on EITHER side. The right-hand side of that test lives
// in the FUTURE relative to bar S, which is why a swing is only KNOWN
// InpCvSwingBars bars after it prints. The scan therefore starts at
// shift = InpCvSwingBars + 1: at shift InpCvSwingBars the right-hand
// neighbours would include the forming bar, and reading them would be reading
// the future.
//
// Swings are stored NEWEST FIRST. Index 0 is the most recent confirmed one.
void CvComputeSwings()
{
   g_cvShN = 0;
   g_cvSlN = 0;

   int p = InpCvSwingBars;
   if(p < 1) p = 1;
   int last = g_cvBarsN - p - 1;
   if(last < p + 1) return;

   for(int i = p + 1; i <= last; i++)
   {
      if(g_cvShN >= MAX_CV_SWINGS && g_cvSlN >= MAX_CV_SWINGS) break;

      double h = CvHigh(i);
      double l = CvLow(i);
      bool isHigh = true;
      bool isLow  = true;

      for(int j = 1; j <= p; j++)
      {
         // i - j is a NEWER bar, i + j an older one. i - j >= 1 always, so
         // the forming bar is never one of the neighbours.
         if(CvHigh(i - j) > h || CvHigh(i + j) > h) isHigh = false;
         if(CvLow(i - j)  < l || CvLow(i + j)  < l) isLow  = false;
         if(!isHigh && !isLow) break;
      }

      if(isHigh && g_cvShN < MAX_CV_SWINGS)
      {
         g_cvShPrice[g_cvShN] = h;
         g_cvShShift[g_cvShN] = i;
         g_cvShN++;
      }
      if(isLow && g_cvSlN < MAX_CV_SWINGS)
      {
         g_cvSlPrice[g_cvSlN] = l;
         g_cvSlShift[g_cvSlN] = i;
         g_cvSlN++;
      }
   }
}

//====================== 1. CLUSTER / CONSOLIDATION ==================
// Veer: "it can't see a cluster is forming".
//
// Two independent readings, both required, plus a size sanity check:
//
//   COMPRESSION = (highest high - lowest low) / SUM of the bar ranges.
//     Trending: each bar's range extends the last, so the numerator is close
//     to the denominator and the ratio approaches 1.
//     Coiling: the same ground is covered repeatedly, so the denominator
//     grows while the numerator does not, and the ratio falls toward 1/N.
//     Scale-free, so it needs no per-symbol tuning.
//
//   OVERLAP = fraction of bars overlapping the PREVIOUS bar's range by more
//     than half the smaller of the two ranges. Compression alone can be
//     produced by one huge bar and nineteen tiny ones; that arrangement
//     cannot also be highly overlapped. Requiring both kills that case.
//
//   RANGE-IN-ATR caps the absolute size. A tight, overlapped box that is
//     eight ATR tall is not a cluster to be avoided, it is a range with
//     tradeable edges.
//
// WHY IT IS COMPUTED AT AN ARBITRARY END BAR
// CvClusterAt(endShift, ...) evaluates the window ENDING at endShift rather
// than always at shift 1. That is what lets CvComputeCluster count how many
// consecutive bars the condition has held (a cluster twenty bars old is a
// different object from one that appeared on this bar), and it is what makes
// the breakout test possible: the breakout bar itself must be excluded from
// the box it is breaking out of, or it widens the box and hides itself.
bool CvClusterAt(int endShift, double &comp, double &ovl, double &rngAtr, double &hi, double &lo)
{
   comp   = 1.0;
   ovl    = 0.0;
   rngAtr = 0.0;
   hi     = 0.0;
   lo     = 0.0;

   int n = InpCvClusterBars;
   if(n < 4) n = 4;
   if(endShift < 1) return false;
   if(endShift + n > g_cvBarsN) return false;      // need one spare for overlap
   if(g_cvAtr <= 0.0) return false;

   double top = CvHigh(endShift);
   double bot = CvLow(endShift);
   double sum = 0.0;

   for(int i = endShift; i < endShift + n; i++)
   {
      double h = CvHigh(i);
      double l = CvLow(i);
      if(h > top) top = h;
      if(l < bot) bot = l;
      sum += (h - l);
   }
   if(sum <= 0.0) return false;

   double total = top - bot;
   comp   = total / sum;
   rngAtr = total / g_cvAtr;
   hi     = top;
   lo     = bot;

   // Overlap against the previous bar. i + 1 is the older neighbour, and the
   // loop reaches endShift + n, which is why the bounds test above needs one
   // bar of headroom.
   int hits = 0;
   for(int i = endShift; i < endShift + n; i++)
   {
      double h1 = CvHigh(i),     l1 = CvLow(i);
      double h2 = CvHigh(i + 1), l2 = CvLow(i + 1);
      double over  = MathMin(h1, h2) - MathMax(l1, l2);
      double small = MathMin(h1 - l1, h2 - l2);
      if(small > 0.0 && over > 0.5 * small) hits++;
   }
   ovl = (double)hits / (double)n;

   return true;
}

void CvComputeCluster()
{
   g_cvClState = (int)CV_CLUSTER_OFF;
   g_cvClComp  = 0.0;
   g_cvClOvl   = 0.0;
   g_cvClRange = 0.0;
   g_cvClBars  = 0;
   g_cvClHigh  = 0.0;
   g_cvClLow   = 0.0;
   g_cvClBreak = 0;
   if(!InpCvUseCluster) return;

   double comp = 0.0, ovl = 0.0, rng = 0.0, hi = 0.0, lo = 0.0;
   if(!CvClusterAt(1, comp, ovl, rng, hi, lo)) return;

   g_cvClComp  = comp;
   g_cvClOvl   = ovl;
   g_cvClRange = rng;
   g_cvClHigh  = hi;
   g_cvClLow   = lo;

   bool forming = (comp <= InpCvCompressMax
                && ovl  >= InpCvOverlapMin
                && rng  <= InpCvRangeAtrMax);
   bool tight   = (comp <= InpCvCompressMax * InpCvTightMult
                && ovl  >= InpCvOverlapMin
                && rng  <= InpCvRangeAtrMax * InpCvTightMult);

   if(tight)        g_cvClState = (int)CV_CLUSTER_TIGHT;
   else if(forming) g_cvClState = (int)CV_CLUSTER_FORMING;
   else             g_cvClState = (int)CV_CLUSTER_NO;

   // HOW LONG HAS IT HELD. Walk the same window back one bar at a time and
   // count the consecutive bars on which it was already true. A cluster that
   // has held for fifteen bars is coiled; one that is true for the first time
   // on this bar is usually just two quiet candles.
   if(forming)
   {
      int held = 1;
      for(int e = 2; e <= InpCvClusterScan; e++)
      {
         double c2 = 0.0, o2 = 0.0, r2 = 0.0, h2 = 0.0, l2 = 0.0;
         if(!CvClusterAt(e, c2, o2, r2, h2, l2)) break;
         if(c2 <= InpCvCompressMax && o2 >= InpCvOverlapMin && r2 <= InpCvRangeAtrMax)
            held++;
         else
            break;
      }
      g_cvClBars = held;
   }

   // BREAKOUT. Measured against the box formed by the bars BEFORE the last
   // closed bar, so the breakout candle is not part of its own box. The
   // buffer stops a one-tick poke counting as a break, the same way the
   // reversal test does.
   double bc = 0.0, bo = 0.0, br = 0.0, bh = 0.0, bl = 0.0;
   if(CvClusterAt(2, bc, bo, br, bh, bl))
   {
      bool wasBox = (bc <= InpCvCompressMax && bo >= InpCvOverlapMin
                  && br <= InpCvRangeAtrMax);
      if(wasBox)
      {
         double buf = InpCvBosBufAtr * g_cvAtr;
         double c1  = CvClose(1);
         if(c1 > bh + buf)      g_cvClBreak = 1;
         else if(c1 < bl - buf) g_cvClBreak = -1;
      }
   }
}

// PUBLIC. CV_CLUSTER_OFF means NO OPINION - the module is off or has no
// data. It does not mean "not consolidating", and a caller that treats the
// two the same has a bug.
ENUM_CV_CLUSTER CvClusterState()
{
   if(!CvRefresh()) return CV_CLUSTER_OFF;
   return (ENUM_CV_CLUSTER)g_cvClState;
}

//====================== 2. REVERSAL, NOT A FLIP =====================
// Veer: "it also needs to understand levels and reversals and like how trends
// flip as m1 is super sensitive".
//
// The SuperTrend flip is not the thing he is describing. A flip is one
// indicator changing its mind, and on M1 gold it does that dozens of times a
// day - E-053 counted 16 signals in 24 minutes inside a $4.50 range. Every
// one of those was a "trend change" as far as this EA could tell.
//
// A REVERSAL here requires TWO events in order, and a single opposite candle
// can produce neither:
//
//   (a) FAILURE TO EXTEND. The newest confirmed swing high is not above the
//       previous one, within InpCvEqTolAtr (so a double top counts, and a
//       new high by one tick does not count as a failure). The market tried
//       and could not. This alone takes at least 2*InpCvSwingBars+2 bars of
//       structure to exist.
//
//   (b) BREAK OF STRUCTURE. A bar then CLOSED below the swing low of that
//       failed leg, by InpCvBosBufAtr x ATR. A wick through is not a break;
//       a close is. This is the part that separates "price dipped" from
//       "the people who were long have been proven wrong".
//
// PLUS three qualifiers, each of which kills a different false positive:
//   * the failed leg must span InpCvMinStructBars bars - two swings four bars
//     apart are noise, not structure;
//   * the leg must be at least InpCvMinLegAtr ATR tall - a 0.2 ATR "reversal"
//     on M1 gold is one spread's worth of movement;
//   * the break must have happened within InpCvRevLifeBars bars - a reversal
//     that completed forty bars ago is history, not news.
//
// THE LOOK-AHEAD TRAP, and this is the part that is easy to get wrong.
// The swing high at shift S is not KNOWN until InpCvSwingBars bars after it
// prints. A break that happened DURING those bars could not have been acted
// on in real time, because at that moment nobody knew there was a swing high
// to have failed. So the break scan starts at shift (S - InpCvSwingBars),
// never at S. Without that line the backtest would report reversals that the
// live EA can never take, and the difference would look like slippage.
void CvComputeReversal()
{
   g_cvRev    = 0;
   g_cvRevAge = 0;
   if(!InpCvUseReversal) return;
   if(g_cvAtr <= 0.0) return;

   int p      = MathMax(InpCvSwingBars, 1);
   double eq  = InpCvEqTolAtr  * g_cvAtr;
   double buf = InpCvBosBufAtr * g_cvAtr;
   double leg = InpCvMinLegAtr * g_cvAtr;

   int    bearAge = 0;
   double bearLeg = 0.0;
   int    bullAge = 0;
   double bullLeg = 0.0;

   //---------------------------------------------------------------- bearish
   if(g_cvShN >= 2 && g_cvSlN >= 1)
   {
      double h0 = g_cvShPrice[0];
      int    s0 = g_cvShShift[0];
      double h1 = g_cvShPrice[1];
      int    s1 = g_cvShShift[1];

      bool failed = (h0 <= h1 + eq);                  // did NOT make a new high
      bool spans  = ((s1 - s0) >= InpCvMinStructBars);

      if(failed && spans)
      {
         // The structural low is the LOWEST confirmed swing low inside the
         // failed leg. Lowest rather than newest, because that is the level
         // whose break the market itself treats as the turn.
         double lp = 0.0;
         bool   haveLow = false;
         for(int k = 0; k < g_cvSlN; k++)
         {
            int sk = g_cvSlShift[k];
            if(sk <= s0 || sk >= s1) continue;
            if(!haveLow || g_cvSlPrice[k] < lp) { lp = g_cvSlPrice[k]; haveLow = true; }
         }
         // Fall back to the newest low older than the failed high, for the
         // case where the leg contains no confirmed low of its own.
         if(!haveLow)
         {
            for(int k = 0; k < g_cvSlN; k++)
            {
               if(g_cvSlShift[k] > s0) { lp = g_cvSlPrice[k]; haveLow = true; break; }
            }
         }

         if(haveLow && (h1 - lp) >= leg)
         {
            int first = s0 - p;                       // see the look-ahead note
            for(int b = first; b >= 1; b--)
            {
               if(CvClose(b) < lp - buf)
               {
                  bearAge = b;
                  bearLeg = h1 - lp;
                  break;
               }
            }
         }
      }
   }

   //---------------------------------------------------------------- bullish
   if(g_cvSlN >= 2 && g_cvShN >= 1)
   {
      double l0 = g_cvSlPrice[0];
      int    s0 = g_cvSlShift[0];
      double l1 = g_cvSlPrice[1];
      int    s1 = g_cvSlShift[1];

      bool failed = (l0 >= l1 - eq);                  // did NOT make a new low
      bool spans  = ((s1 - s0) >= InpCvMinStructBars);

      if(failed && spans)
      {
         double hp = 0.0;
         bool   haveHigh = false;
         for(int k = 0; k < g_cvShN; k++)
         {
            int sk = g_cvShShift[k];
            if(sk <= s0 || sk >= s1) continue;
            if(!haveHigh || g_cvShPrice[k] > hp) { hp = g_cvShPrice[k]; haveHigh = true; }
         }
         if(!haveHigh)
         {
            for(int k = 0; k < g_cvShN; k++)
            {
               if(g_cvShShift[k] > s0) { hp = g_cvShPrice[k]; haveHigh = true; break; }
            }
         }

         if(haveHigh && (hp - l1) >= leg)
         {
            int first = s0 - p;
            for(int b = first; b >= 1; b--)
            {
               if(CvClose(b) > hp + buf)
               {
                  bullAge = b;
                  bullLeg = hp - l1;
                  break;
               }
            }
         }
      }
   }

   // Both sides can qualify after a wide swing. Take the more RECENT break;
   // if they broke on the same bar the structure is genuinely ambiguous and
   // the honest answer is no reversal rather than a coin toss.
   int rev = 0;
   int age = 0;
   if(bearAge > 0 && bullAge > 0)
   {
      if(bearAge < bullAge)      { rev = -1; age = bearAge; }
      else if(bullAge < bearAge) { rev =  1; age = bullAge; }
      else                       { rev =  0; age = 0; }
   }
   else if(bearAge > 0) { rev = -1; age = bearAge; }
   else if(bullAge > 0) { rev =  1; age = bullAge; }

   if(rev != 0 && age > InpCvRevLifeBars) { rev = 0; age = 0; }

   g_cvRev    = rev;
   g_cvRevAge = age;
}

// PUBLIC. -1 bearish, 0 none, +1 bullish. Zero means "no reversal", which is
// the normal state; it is not an error and not "no opinion" - that is what
// CvRead().ready is for.
int CvReversal()
{
   if(!CvRefresh()) return 0;
   return g_cvRev;
}

//====================== 3. SESSION STATE ============================
// Veer: "anything can happen like session opens can dump or sky rocket".
//
// BROKER TIME IS NOT UTC. This matters more than it sounds: most MT5 servers
// run GMT+2 in winter and GMT+3 in summer, so a session hour hardcoded in
// server time is wrong for seven months of the year ON THE SAME SERVER, and
// wrong by a different amount on the next broker. The EA's existing session
// filter reads TimeCurrent() and compares it to InpSessFromUTC - that is
// broker time being tested against a number labelled UTC, and it is off by
// two or three hours in practice.
//
// So the offset is DERIVED AT RUNTIME:  TimeCurrent() - TimeGMT(), rounded to
// the nearest 15 minutes because tick timestamps jitter and no server sits on
// a 7-minute offset. It is re-derived every bar, so a DST change on either
// side fixes itself without a restart and without a parameter.
//
// WHAT I COULD NOT VERIFY WITHOUT MT5: TimeGMT() in the STRATEGY TESTER
// returns a modelled GMT derived from the terminal's own settings, not from
// the historical server clock. It is normally right, but if a backtest shows
// sessions an hour out, set InpCvGmtOffsetMin explicitly rather than trusting
// it. There is no way to check that from this container.
int CvGmtOffsetMin()
{
   if(InpCvGmtOffsetMin != 9999) return InpCvGmtOffsetMin;
   if(g_cvOffKnown) return g_cvGmtOff;
   return 0;                      // no clock yet: behave as if broker == GMT
}

// Recomputed once per bar by CvRefresh().
void CvUpdateOffset()
{
   datetime srv = TimeCurrent();
   datetime utc = TimeGMT();
   if(srv <= 0 || utc <= 0) return;
   double mins = ((double)((long)srv - (long)utc)) / 60.0;
   int    q    = (int)MathRound(mins / 15.0) * 15;    // nearest quarter hour
   if(q < -900 || q > 900) return;                    // nonsense, keep the old
   g_cvGmtOff   = q;
   g_cvOffKnown = true;
}

datetime CvMakeUtc(int year, int mon, int day, int hour)
{
   MqlDateTime d;
   d.year        = year;
   d.mon         = mon;
   d.day         = day;
   d.hour        = hour;
   d.min         = 0;
   d.sec         = 0;
   d.day_of_week = 0;
   d.day_of_year = 0;
   return StructToTime(d);
}

int CvDowUtc(datetime t)
{
   MqlDateTime d;
   TimeToStruct(t, d);
   return d.day_of_week;              // 0 = Sunday
}

datetime CvNthSundayUtc(int year, int mon, int nth, int hour)
{
   datetime first = CvMakeUtc(year, mon, 1, hour);
   int dow = CvDowUtc(first);
   int day = 1 + ((7 - dow) % 7) + (nth - 1) * 7;
   return CvMakeUtc(year, mon, day, hour);
}

datetime CvLastSundayUtc(int year, int mon, int lastDay, int hour)
{
   datetime last = CvMakeUtc(year, mon, lastDay, hour);
   int dow = CvDowUtc(last);
   return (datetime)((long)last - (long)dow * 86400);
}

// EU summer time: last Sunday in March 01:00 UTC to last Sunday in October
// 01:00 UTC. This is what moves the LONDON open from 08:00 to 07:00 GMT.
bool CvIsEuDst(datetime gmt)
{
   MqlDateTime d;
   TimeToStruct(gmt, d);
   datetime a = CvLastSundayUtc(d.year, 3,  31, 1);
   datetime b = CvLastSundayUtc(d.year, 10, 31, 1);
   return (gmt >= a && gmt < b);
}

// US summer time: second Sunday in March 07:00 UTC to first Sunday in
// November 06:00 UTC. This is what moves the NEW YORK open from 13:30 to
// 12:30 GMT - and for three weeks in March and one in autumn the two DST
// regimes disagree, which is exactly when a hardcoded hour is wrong.
bool CvIsUsDst(datetime gmt)
{
   MqlDateTime d;
   TimeToStruct(gmt, d);
   datetime a = CvNthSundayUtc(d.year, 3,  2, 7);
   datetime b = CvNthSundayUtc(d.year, 11, 1, 6);
   return (gmt >= a && gmt < b);
}

// The whole session read, for any broker timestamp. Public so the caller can
// ask about the last closed bar's time instead of "now" when it wants an
// answer that is reproducible in a backtest.
//
// minsIn is minutes since the session that is currently running OPENED, or -1
// when none is. When two sessions overlap it is measured from the one that
// opened most recently, which is the one that just moved the price.
bool CvSessionAt(datetime brokerTime, ENUM_CV_SESSION &sess, int &minsIn, bool &burst, bool &hour)
{
   sess   = CV_SESS_UNKNOWN;
   minsIn = -1;
   burst  = false;
   hour   = false;
   if(!InpCvUseSession) return false;
   if(brokerTime <= 0)  return false;

   datetime gmt = (datetime)((long)brokerTime - (long)CvGmtOffsetMin() * 60);
   MqlDateTime g;
   TimeToStruct(gmt, g);
   int mod = g.hour * 60 + g.min;         // minutes into the GMT day
   int dow = g.day_of_week;

   // WEEKEND. Approximate on purpose and stated as such: FX/metals open
   // around 22:00 GMT Sunday and close around 21:00 GMT Friday, and every
   // broker shades that differently. It is here so the module does not
   // report "Tokyo" over a weekend, not as a trading gate.
   bool closed = (dow == 6)
              || (dow == 0 && mod < 1320)
              || (dow == 5 && mod >= 1260);
   if(closed)
   {
      sess = CV_SESS_CLOSED;
      return true;
   }

   int tOpen = InpCvTokyoOpenGmt;
   int lOpen = InpCvLondonOpenGmt - ((InpCvAutoDst && CvIsEuDst(gmt)) ? 60 : 0);
   int nOpen = InpCvNyOpenGmt     - ((InpCvAutoDst && CvIsUsDst(gmt)) ? 60 : 0);

   int tSince = mod - tOpen; if(tSince < 0) tSince += 1440;
   int lSince = mod - lOpen; if(lSince < 0) lSince += 1440;
   int nSince = mod - nOpen; if(nSince < 0) nSince += 1440;

   bool inT = (tSince < InpCvTokyoLenMin);
   bool inL = (lSince < InpCvLondonLenMin);
   bool inN = (nSince < InpCvNyLenMin);

   if(inL && inN)      sess = CV_SESS_LON_NY;
   else if(inN)        sess = CV_SESS_NEWYORK;
   else if(inL)        sess = CV_SESS_LONDON;
   else if(inT)        sess = CV_SESS_TOKYO;
   else                sess = CV_SESS_CLOSED;   // the 21:00-00:00 GMT dead zone

   // Minutes into the MOST RECENTLY OPENED session that is still running.
   int best = -1;
   if(inT && (best < 0 || tSince < best)) best = tSince;
   if(inL && (best < 0 || lSince < best)) best = lSince;
   if(inN && (best < 0 || nSince < best)) best = nSince;
   minsIn = best;

   if(best >= 0)
   {
      burst = (best < InpCvOpenBurstMin);
      hour  = (best < InpCvOpenHourMin);
   }
   return true;
}

// PUBLIC. Uses the wall clock, which is the honest source for "how long has
// this session been running" - a clock is not a price and cannot repaint.
ENUM_CV_SESSION CvSession()
{
   ENUM_CV_SESSION s = CV_SESS_UNKNOWN;
   int  m = -1;
   bool b = false;
   bool h = false;
   CvSessionAt(TimeCurrent(), s, m, b, h);
   return s;
}
