//+------------------------------------------------------------------+
//|  LIQUIDITY SNIPER                                                |
//|  The liquidity sweep strategy, as MEASURED - not as imagined.    |
//+------------------------------------------------------------------+
//
//  WHAT THIS TRADES, AND WHY EVERY NUMBER IN IT IS THE NUMBER IT IS
//
//  Veer trades this by hand and reports an 80% win rate. The first research
//  build of these rules measured 31.6% and it was WRONG - it fired twelve
//  times in 4501 bars, so nothing it reported was a measurement of anything.
//  E-068 found three errors, each with a price tag, and this EA is what is
//  left after they are corrected:
//
//   1. A ZONE IS ONE CONFIRMED PIVOT, not three clustered.
//      Requiring three inside a +/-ATR/6.9 band fires 2.7 times per 1000 bars.
//      One pivot fires 39.3 times. Veer sent two LuxAlgo scripts - "Liquidity
//      Sweeps" (a single swing point IS liquidity) and "Buyside & Sellside
//      Liquidity" (clustered) - and the research build ANDed them, keeping the
//      strictest reading of each.
//
//   2. THE ORDER RESTS INSIDE THE ZONE AND THE SWEEP FILLS IT.
//      Veer: "we need to have top tick entrys meaning we do a small stop loss
//      which is reasonable and catch a massiveeee entry from the tick".
//
//      Both entries I had measured before this enter AFTER the sweep is over -
//      at the sweep bar's close, or back at the zone edge later. Neither is
//      that trade. A professional does not wait: the zone is WHERE THE STOPS
//      ARE, the sweep is the market reaching in to take them, so the limit
//      rests inside the zone BEFORE the sweep and is filled BY it. The stop
//      then sits just past the poke - small - and the whole reversal is the
//      target.
//
//      It also fills on every BREAK, not only every sweep, and that is the
//      honest cost. A break is a full-size loss. The measurement below is
//      whether a small stop and a 2R target pay for those.
//
//   3. SMALL STOP, BIG TARGET. Risk 1 to make 2.
//      0.60 ATR of risk, 2R of target. NOT the 1.5-ATR-stop / 0.5-ATR-target
//      shape this EA shipped with yesterday, which wins 87% of the time and
//      makes a third of the money.
//
//  E-077, the geometry attacked. XAUUSD:
//    GOLD 1h   n=491  47.5% win  +0.378R  PF 1.69  t=+5.58   +2172 points
//              OOS +0.470 / +0.286   walk-forward 6 of 6 blocks
//              +4.7 sd clear of 30 random-entry control seeds    PROMISING
//    GOLD 15m  n=158  48.1% win  +0.382R  PF 1.69  t=+3.20    +301 points
//              OOS +0.498 / +0.265   walk-forward 4 of 6       PROMISING
//
//  And it is a PLATEAU, not a cell. Every combination from a 0.45-0.90 ATR
//  stop and a 1.5R-2.5R target is positive on GOLD 1h. The best of them is
//  0.75 ATR / 1.5R at +3183 points; the shipped default sits in the interior
//  because an edge-of-grid optimum is usually a fit.
//
//  PROMISING is the strongest word the directive allows for something that has
//  survived. It does not mean profitable and this EA does not claim to be.
//
//  WHAT YOU MUST KNOW BEFORE RUNNING IT
//   * XAUUSD. FX is rejected outright on these rules.
//   * HALF THE TRADES LOSE. 47.5% win rate. The money is in 2R being twice
//     as big as 1R, not in being right often. A run of five losses is normal
//     and the Monte Carlo says the drawdown to expect is about 12R, with 18R
//     at the 95th percentile. If that would make you turn it off, turn it off
//     now instead.
//   * THIS SHAPE CARES ABOUT THE SPREAD, unlike the one it replaces. Measured
//     on GOLD 1h: +0.492R at zero spread, +0.378R at the 0.46 off Veer's
//     terminal, +0.279R at 1.00. A small stop cannot absorb a wide spread, so
//     news-time spreads are a real cost, not a rounding error.
//   * IT WAS MEASURED ON 15m AND 1h BARS. There is no M1 or M5 data in the
//     repository. Running it on M1 is an extrapolation, and the honest way to
//     end that is to run ExportHistory.mq5 and re-measure.
//
#property copyright "JARVIS"
#property version   "3.00"
#property strict

#define LQS_BUILD "2026-09-02 / 3.00 / top-tick + FVG + order blocks"

#include <Trade/Trade.mqh>
CTrade trade;

//==================== INPUTS =======================================
input group "=== SAFETY ==="
input bool   InpDemoOnly      = true;   // refuse to start on a live account
input long   InpMagic         = 770069; // magic number

input group "=== ZONES  (LuxAlgo: Liquidity Sweeps) ==="
input int    InpPivLen        = 7;      // pivot length
input double InpMarDiv        = 6.9;    // zone half-width = ATR / this
input int    InpMinPivots     = 1;      // pivots needed to make a zone
input int    InpZoneLife      = 600;    // forget a zone after N bars
input int    InpMaxZones      = 40;     // zones tracked each side

input group "=== THE TRADE  (E-077 - do not tune without re-measuring) ==="
input double InpEntryPast     = 0.25;   // limit sits this many ATR PAST the zone's far edge
input double InpStopAtr       = 0.60;   // stop, ATR beyond the FILL. Small, on purpose.
input double InpTargetR       = 2.0;    // target, multiples of that risk
input int    InpArmLife       = 60;     // a zone stops being armable this many bars after birth
input double InpEntryLots     = 0.02;   // size for one entry
input int    InpMaxPositions  = 1;      // one at a time, as measured

input group "=== RISK ==="
input double InpMaxDayLossPct = 3.0;    // stop for the day after this drawdown
input double InpMaxDDPct      = 10.0;   // stop permanently after this drawdown
input int    InpMaxTradesDay  = 60;     // hard cap on entries per day

input group "=== READOUT ==="
input bool   InpComment       = true;   // the chart readout
input bool   InpVerboseLog    = true;   // log every decision

//==================== STATE ========================================
struct Zone
{
   double px;        // centre
   double top;
   double bot;
   int    born;      // bar index when it was confirmed
   int    dir;       // +1 buyside (above), -1 sellside (below)
   bool   broken;    // a CLOSE went through it - the zone is dead
};

Zone   g_zB[];       // buyside zones
Zone   g_zS[];       // sellside zones


int      g_atrHandle = INVALID_HANDLE;
datetime g_lastBar   = 0;
double   g_pivH[];         // recent confirmed pivot highs
double   g_pivL[];

// accounting
double   g_dayStartEq = 0.0;
double   g_peakEq     = 0.0;
int      g_dayStamp   = 0;
int      g_tradesToday = 0;
bool     g_lockedDay  = false;
bool     g_lockedPerm = false;
int      g_nTrades    = 0;
int      g_nWins      = 0;
double   g_realized   = 0.0;
double   g_dayRealized = 0.0;
long     g_readN      = 0;
double   g_spSum     = 0.0;
int      g_spN       = 0;
double   g_spMax     = 0.0;

//==================== FORWARD ======================================
void   Log(string m);
string Money(double v);
double ATRv(int shift);
int    DayStamp();
void   Readout();
void   BuildZones();
double EntryLevel(const Zone &z, double a);
void   PushGap(Gap &G[], double top, double bot, int dir, int bar);
void   AgeGaps(Gap &G[], int bar, double c);
void   BuildSmc();
double BestLevel(int dir, double px, double a, string &src);
int    NearestZone(const Zone &Z[], int bar, double px, bool above);
void   ArmSide(int dir);
void   KillSide(int dir, string why);
void   KillAll(string why);
void   ManageOrders();
bool   HavePosition();
void   AddZone(Zone &Z[], double &piv[], double at, int dir, double mar, int bar);
void   ExpireZones(Zone &Z[], int bar);
void   MarkBroken(Zone &Z[], double c);
void   CheckGuards();
double MinStopDist();
int    PosCount();

//==================== HELPERS ======================================
void Log(string m)
{
   if(InpVerboseLog) Print(m);
}

string Money(double v)
{
   return StringFormat("%s%.2f", (v < 0 ? "-" : ""),
                       MathAbs(NormalizeDouble(v, 2)));
}

double ATRv(int shift)
{
   double b[];
   if(CopyBuffer(g_atrHandle, 0, shift, 1, b) != 1) return 0.0;
   return b[0];
}

int DayStamp()
{
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   return t.year * 10000 + t.mon * 100 + t.day;
}

// The broker will not accept a stop closer than this to the market. Ignoring
// it is how an EA ends up sending orders that are silently rejected all day.
double MinStopDist()
{
   long   lvl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double pt  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(lvl <= 0 || pt <= 0.0) return 0.0;
   return (double)lvl * pt;
}

int PosCount()
{
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      c++;
   }
   return c;
}

bool HavePosition() { return PosCount() > 0; }

//==================== ZONES ========================================
// A pivot at bar i is only KNOWN at bar i+InpPivLen. Every use below respects
// that; the whole strategy is worthless if it does not.
void BuildZones()
{
   int n = Bars(_Symbol, _Period);
   int p = InpPivLen;
   if(n < p * 2 + 8) return;

   // The candidate pivot sits at shift p+1, confirmed by the p bars closed on
   // either side of it. NOT shift p: that window reaches shift 0, which is the
   // bar still forming. Reading it would let a pivot be confirmed or denied by
   // a high that has not happened yet, and the whole strategy is worthless if
   // any part of it can see the current bar.
   int b = p + 1;
   double h = iHigh(_Symbol, _Period, b);
   double l = iLow(_Symbol, _Period, b);
   bool isH = true, isL = true;
   for(int k = 1; k <= p; k++)
   {
      if(iHigh(_Symbol, _Period, b - k) > h || iHigh(_Symbol, _Period, b + k) > h) isH = false;
      if(iLow(_Symbol, _Period, b - k)  < l || iLow(_Symbol, _Period, b + k)  < l) isL = false;
   }

   double a = ATRv(1);
   if(a <= 0.0) return;
   double mar = a / InpMarDiv;
   int bar = Bars(_Symbol, _Period) - 1;

   if(isH) AddZone(g_zB, g_pivH, h, 1, mar, bar);
   if(isL) AddZone(g_zS, g_pivL, l, -1, mar, bar);

   // A zone price has CLOSED beyond is DEAD - that is a break, not a sweep,
   // and there is no trade left at it. The old sweep scanner used to set this
   // flag; it was removed with the sweep logic, so for one build nothing did,
   // and orders would have gone on resting at levels the market had left
   // behind. Zones are now killed here, on every bar close, unconditionally.
   MarkBroken(g_zB, iClose(_Symbol, _Period, 1));
   MarkBroken(g_zS, iClose(_Symbol, _Period, 1));

   ExpireZones(g_zB, bar);
   ExpireZones(g_zS, bar);
}

void MarkBroken(Zone &Z[], double c)
{
   for(int i = 0; i < ArraySize(Z); i++)
   {
      if(Z[i].broken) continue;
      if((Z[i].dir == 1 && c > Z[i].top) || (Z[i].dir == -1 && c < Z[i].bot))
         Z[i].broken = true;
   }
}

void AddZone(Zone &Z[], double &piv[], double at, int dir, double mar, int bar)
{
   // remember the pivot, and count how many recent ones cluster with it
   int np = ArraySize(piv);
   ArrayResize(piv, np + 1);
   piv[np] = at;
   if(ArraySize(piv) > 50)
   {
      for(int i = 0; i < ArraySize(piv) - 1; i++) piv[i] = piv[i + 1];
      ArrayResize(piv, 50);
   }
   int cnt = 0;
   for(int i = 0; i < ArraySize(piv); i++)
      if(MathAbs(piv[i] - at) <= mar) cnt++;
   if(cnt < InpMinPivots) return;

   // merge into an existing live zone rather than stacking duplicates
   for(int i = 0; i < ArraySize(Z); i++)
      if(!Z[i].broken && MathAbs(Z[i].px - at) <= mar)
      {
         Z[i].top = MathMax(Z[i].top, at + mar);
         Z[i].bot = MathMin(Z[i].bot, at - mar);
         return;
      }

   int nz = ArraySize(Z);
   ArrayResize(Z, nz + 1);
   Z[nz].px = at;  Z[nz].top = at + mar;  Z[nz].bot = at - mar;
   Z[nz].born = bar;  Z[nz].dir = dir;  Z[nz].broken = false;

   if(ArraySize(Z) > InpMaxZones)
   {
      for(int i = 0; i < ArraySize(Z) - 1; i++) Z[i] = Z[i + 1];
      ArrayResize(Z, InpMaxZones);
   }
}

void ExpireZones(Zone &Z[], int bar)
{
   int w = 0;
   for(int i = 0; i < ArraySize(Z); i++)
   {
      if(bar - Z[i].born > InpZoneLife) continue;
      if(Z[i].broken) continue;
      if(w != i) Z[w] = Z[i];
      w++;
   }
   ArrayResize(Z, w);
}

//==================== SMC: FVG AND ORDER BLOCKS ====================
// E-079 built six SMC concepts and measured every one of them against the
// entry that already works. Three pay and three do not, and the three that do
// not are in this comment rather than in the code:
//
//   FAIR VALUE GAP     IN.  As a trigger on its own, GOLD 1h: 34 trades,
//                      67.6% win, +0.998R, +466 points. The strongest single
//                      signal in the project.
//   ORDER BLOCK        IN.  58 trades, 53.4% win, +0.559R, +338 points.
//   INVERSE FVG        OUT. 1136 trades and MINUS 39 points. It fires
//                      constantly and dilutes everything it is added to:
//                      the full stack drops from +0.487R to +0.119R with it.
//   BOS / CHoCH        OUT. As triggers, -0.028R to +0.030R - inside noise.
//   STRUCTURE BIAS     OUT, and this one is the interesting refusal. As a
//                      filter it RAISES expectancy from +0.487R to +0.638R -
//                      and cuts the trade count from 515 to 205 and the money
//                      from +2792 points to +1403. That is exactly the trap
//                      E-074 caught in the SuperTrend EA: the best per-trade
//                      number and the least money. Veer is paid in points.
//
// Together with the zone entry: n=515, 51.1% win, +0.487R, PF 1.95, t=+7.37,
// +2792 points, walk-forward 6 of 6, +5.0 sd clear of 30 control seeds, and a
// Monte Carlo drawdown of 9.8R median. Against the zone entry alone (480
// trades, +0.385R, +2110 points) it is MORE trades, higher expectancy and 32%
// more money - better on every axis, which is rare enough to be suspicious of,
// so it was checked out of sample (+0.598 / +0.377) and block by block.

struct Gap
{
   double top;
   double bot;
   int    born;
   int    dir;        // +1 bullish (support), -1 bearish (resistance)
   bool   dead;
};

Gap g_fvg[];
Gap g_ob[];

input group "=== SMC  (E-079: these two pay, iFVG/BOS/CHoCH do not) ==="
input bool   InpUseFvg        = true;   // rest orders at fair value gaps
input bool   InpUseOB         = true;   // rest orders at order blocks
input double InpDispAtr       = 1.0;    // a displacement bar's BODY, in ATR
input double InpMinGapAtr     = 0.10;   // ignore gaps smaller than this
input int    InpSmcLife       = 200;    // bars an FVG or block stays live

void PushGap(Gap &G[], double top, double bot, int dir, int bar)
{
   int n = ArraySize(G);
   ArrayResize(G, n + 1);
   G[n].top = top;  G[n].bot = bot;  G[n].dir = dir;
   G[n].born = bar; G[n].dead = false;
   if(ArraySize(G) > 60)
   {
      for(int i = 0; i < ArraySize(G) - 1; i++) G[i] = G[i + 1];
      ArrayResize(G, 60);
   }
}

void AgeGaps(Gap &G[], int bar, double c)
{
   int w = 0;
   for(int i = 0; i < ArraySize(G); i++)
   {
      if(bar - G[i].born > InpSmcLife) continue;
      // a close through it the wrong way kills it. For an FVG that is the
      // INVERSION, which E-079 measured as worth nothing - so it is killed
      // here rather than traded the other way.
      if((G[i].dir == 1 && c < G[i].bot) || (G[i].dir == -1 && c > G[i].top))
         continue;
      if(w != i) G[w] = G[i];
      w++;
   }
   ArrayResize(G, w);
}

// Runs on the CLOSED bar. An FVG needs bars 1, 2 and 3 back, all closed.
void BuildSmc()
{
   int bar = Bars(_Symbol, _Period) - 1;
   double a = ATRv(1);
   if(a <= 0.0) return;
   double c1 = iClose(_Symbol, _Period, 1);

   AgeGaps(g_fvg, bar, c1);
   AgeGaps(g_ob,  bar, c1);

   if(InpUseFvg)
   {
      double h3 = iHigh(_Symbol, _Period, 3), l3 = iLow(_Symbol, _Period, 3);
      double h1 = iHigh(_Symbol, _Period, 1), l1 = iLow(_Symbol, _Period, 1);
      if(h3 < l1 && (l1 - h3) >= InpMinGapAtr * a) PushGap(g_fvg, l1, h3,  1, bar);
      if(l3 > h1 && (l3 - h1) >= InpMinGapAtr * a) PushGap(g_fvg, l3, h1, -1, bar);
   }

   if(InpUseOB)
   {
      double o1 = iOpen(_Symbol, _Period, 1);
      double body = c1 - o1;
      if(MathAbs(body) >= InpDispAtr * a)
      {
         int d = (body > 0) ? 1 : -1;
         // the last OPPOSITE-colour candle before the displacement leg
         for(int k = 2; k < 9; k++)
         {
            double ok = iOpen(_Symbol, _Period, k), ck = iClose(_Symbol, _Period, k);
            bool opp = (d > 0) ? (ck < ok) : (ck > ok);
            if(opp)
            {
               PushGap(g_ob, MathMax(ok, ck), MathMin(ok, ck), d, bar);
               break;
            }
         }
      }
   }
}

// The nearest tradeable level on one side, from ANY source. dir +1 wants a
// level BELOW price to buy at, dir -1 a level above to sell at.
double BestLevel(int dir, double px, double a, string &src)
{
   double best = 0.0;
   bool   have = false;
   src = "";

   int bar = Bars(_Symbol, _Period) - 1;
   int idx = (dir > 0) ? NearestZone(g_zS, bar, px, false)
                       : NearestZone(g_zB, bar, px, true);
   if(idx >= 0)
   {
      Zone z = (dir > 0) ? g_zS[idx] : g_zB[idx];
      double lvl = EntryLevel(z, a);
      if((dir > 0 && lvl < px) || (dir < 0 && lvl > px))
      { best = lvl; have = true; src = "zone"; }
   }

   for(int pass = 0; pass < 2; pass++)
   {
      if(pass == 0 && !InpUseFvg) continue;
      if(pass == 1 && !InpUseOB)  continue;
      int cnt = (pass == 0) ? ArraySize(g_fvg) : ArraySize(g_ob);
      for(int i = 0; i < cnt; i++)
      {
         Gap g = (pass == 0) ? g_fvg[i] : g_ob[i];
         if(g.dir != dir) continue;
         double mid = (g.top + g.bot) / 2.0;
         if(dir > 0 && mid >= px) continue;
         if(dir < 0 && mid <= px) continue;
         if(!have || MathAbs(mid - px) < MathAbs(best - px))
         {
            best = mid; have = true;
            src = (pass == 0) ? "fvg" : "ob";
         }
      }
   }
   return have ? best : 0.0;
}

//==================== THE RESTING ORDERS ===========================
// The whole strategy, in one idea: a limit sits INSIDE the nearest live zone
// on each side, and the sweep fills it. Nothing waits for confirmation, because
// E-076 measured what waiting costs - by the time the sweep bar has closed, the
// wick is far away and the risk is no longer small.
//
// Two orders can rest at once, one each side, which is what a desk actually
// does. The first to fill cancels the other: InpMaxPositions is 1 and the
// measurement counted one trade at a time.
//
// These are REAL broker-side pending orders. That matters more here than
// anywhere else: the fill IS the edge, and a limit simulated inside OnTick only
// fills if a tick happens to arrive while price is through the level. On a fast
// sweep wick - which is precisely the bar this strategy exists to catch - that
// tick may never come, so the EA would miss the fills the backtest counted and
// keep the slow ones it did not.

ulong    g_tkBuy  = 0;      // resting BUY limit  (at a sellside zone, below)
ulong    g_tkSell = 0;      // resting SELL limit (at a buyside zone, above)
double   g_lvlBuy = 0.0;
double   g_lvlSell = 0.0;

// Where the order sits: past the far edge of the zone, into the liquidity.
double EntryLevel(const Zone &z, double a)
{
   // buyside zone (above): we SELL, so the far edge is its top
   if(z.dir == 1) return z.top + InpEntryPast * a;
   return z.bot - InpEntryPast * a;
}

// The nearest live zone on one side that is still young enough to trade.
int NearestZone(const Zone &Z[], int bar, double px, bool above)
{
   int best = -1;
   double bd = 0.0;
   for(int i = 0; i < ArraySize(Z); i++)
   {
      if(Z[i].broken) continue;
      if(bar - Z[i].born > InpArmLife) continue;
      double lvl = (Z[i].dir == 1) ? Z[i].top : Z[i].bot;
      if(above && lvl <= px) continue;
      if(!above && lvl >= px) continue;
      double d = MathAbs(lvl - px);
      if(best < 0 || d < bd) { best = i; bd = d; }
   }
   return best;
}

void ArmSide(int dir)
{
   if(g_lockedDay || g_lockedPerm) return;
   if(PosCount() >= InpMaxPositions) return;
   if(g_tradesToday >= InpMaxTradesDay) return;

   ulong  tk   = (dir > 0) ? g_tkBuy : g_tkSell;
   double a    = ATRv(1);
   if(a <= 0.0) return;
   int    bar  = Bars(_Symbol, _Period) - 1;
   double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(bid <= 0.0 || ask <= 0.0) return;

   // The nearest level on this side from ANY source - liquidity zone, fair
   // value gap or order block. Nearest, because that is the one price reaches
   // first, and the backtest resolved overlapping signals the same way: first
   // touched wins, one position at a time.
   string src = "";
   double raw = BestLevel(dir, (dir > 0) ? bid : ask, a, src);
   if(raw == 0.0) { KillSide(dir, "no live level on this side"); return; }

   int dg   = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double lvl = NormalizeDouble(raw, dg);

   // already resting at this exact level for this exact zone: leave it alone.
   // Re-sending it every bar would churn the order book and reset its age.
   double have = (dir > 0) ? g_lvlBuy : g_lvlSell;
   if(tk != 0 && OrderSelect(tk) && MathAbs(have - lvl) < _Point)
      return;

   KillSide(dir, "");

   double stop = NormalizeDouble(lvl - dir * InpStopAtr * a, dg);
   double risk = (lvl - stop) * dir;
   if(risk <= 0.0) return;
   double tgt  = NormalizeDouble(lvl + dir * InpTargetR * risk, dg);

   // the broker's floor. A limit inside the stops level is REJECTED, and a
   // rejected order is a trade silently not taken.
   double md = MinStopDist();
   if(md > 0.0)
   {
      if(MathAbs(lvl - stop) < md) stop = NormalizeDouble(lvl - dir * md, dg);
      if(MathAbs(tgt - lvl)  < md) tgt  = NormalizeDouble(lvl + dir * md, dg);
   }

   // A limit must rest on the far side of the market. If price is already
   // through the level the sweep has happened without us, and chasing it with
   // a market order is the entry E-076 measured at -0.003R.
   if((dir > 0 && ask <= lvl) || (dir < 0 && bid >= lvl))
   {
      Log("not arming: price is already through the level");
      return;
   }

   bool ok = (dir > 0)
      ? trade.BuyLimit(InpEntryLots, lvl, _Symbol, stop, tgt,
                       ORDER_TIME_GTC, 0, "LQS toptick")
      : trade.SellLimit(InpEntryLots, lvl, _Symbol, stop, tgt,
                        ORDER_TIME_GTC, 0, "LQS toptick");
   if(ok)
   {
      if(dir > 0) { g_tkBuy = trade.ResultOrder();  g_lvlBuy = lvl; }
      else        { g_tkSell = trade.ResultOrder(); g_lvlSell = lvl; }
      Log(StringFormat("ARMED %s LIMIT %.2f at %.*f   stop %.*f (%.*f risk)   "
                       "target %.*f   source %s",
                       dir > 0 ? "BUY" : "SELL", InpEntryLots, dg, lvl,
                       dg, stop, dg, risk, dg, tgt, src));
   }
   else
      Log(StringFormat("ARM REJECTED (%s): %d %s", dir > 0 ? "buy" : "sell",
                       trade.ResultRetcode(), trade.ResultRetcodeDescription()));
}

void KillSide(int dir, string why)
{
   ulong tk = (dir > 0) ? g_tkBuy : g_tkSell;
   if(tk == 0) return;
   if(OrderSelect(tk))
   {
      trade.OrderDelete(tk);
      if(why != "") Log(StringFormat("cancelled the %s limit: %s",
                                     dir > 0 ? "buy" : "sell", why));
   }
   if(dir > 0) { g_tkBuy = 0;  g_lvlBuy = 0.0; }
   else        { g_tkSell = 0; g_lvlSell = 0.0; }
}

void KillAll(string why)
{
   KillSide(1, why);
   KillSide(-1, why);
}

// Called on every bar close: re-point the orders at the zones that are still
// alive, and clear any ticket the broker has already disposed of.
void ManageOrders()
{
   if(g_tkBuy  != 0 && !OrderSelect(g_tkBuy))  { g_tkBuy = 0;  g_lvlBuy = 0.0; }
   if(g_tkSell != 0 && !OrderSelect(g_tkSell)) { g_tkSell = 0; g_lvlSell = 0.0; }

   if(PosCount() >= InpMaxPositions || g_lockedDay || g_lockedPerm)
   {
      KillAll("a position is open, or trading is locked");
      return;
   }
   ArmSide(1);
   ArmSide(-1);
}

//==================== RISK =========================================
void CheckGuards()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_peakEq) g_peakEq = eq;

   if(!g_lockedPerm && g_peakEq > 0.0
      && (g_peakEq - eq) / g_peakEq * 100.0 >= InpMaxDDPct)
   {
      g_lockedPerm = true;
      Log("PERMANENT LOCK: max drawdown breached. No further entries.");
   }
   if(!g_lockedDay && g_dayStartEq > 0.0
      && (g_dayStartEq - eq) / g_dayStartEq * 100.0 >= InpMaxDayLossPct)
   {
      g_lockedDay = true;
      Log("LOCKED FOR TODAY: daily loss limit breached.");
   }
}

//==================== READOUT ======================================
// On a 250ms TIMER, not on the tick. OnTick does not run when the market is
// quiet, does not run when it is shut, and does not run between the EA being
// attached and the first quote - which is how the SuperTrend EA's box came to
// look frozen three separate times. The heartbeat clock is there so that "it
// is not updating" is answerable from the chart instead of from a guess.
void Readout()
{
   if(!InpComment) return;

   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sp  = ask - bid;
   if(sp > 0.0) { g_spSum += sp; g_spN++; if(sp > g_spMax) g_spMax = sp; }
   double spAvg = (g_spN > 0) ? g_spSum / (double)g_spN : 0.0;

   double pl = 0.0, lots = 0.0, ent = 0.0, slp = 0.0, tpp = 0.0;
   int    dir = 0, np = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      np++;
      lots += PositionGetDouble(POSITION_VOLUME);
      pl   += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      ent   = PositionGetDouble(POSITION_PRICE_OPEN);
      slp   = PositionGetDouble(POSITION_SL);
      tpp   = PositionGetDouble(POSITION_TP);
      dir   = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
   }

   g_readN++;
   string live = TimeToString(TimeCurrent(), TIME_MINUTES | TIME_SECONDS);

   // both sides, because both can be resting at once
   string armed = "";
   if(g_tkBuy != 0)
      armed += StringFormat("BUY limit %.*f", _Digits, g_lvlBuy);
   if(g_tkSell != 0)
      armed += StringFormat("%sSELL limit %.*f", armed == "" ? "" : "   ",
                            _Digits, g_lvlSell);
   if(armed == "") armed = "none resting";

   string pos = (np == 0)
      ? "flat"
      : StringFormat("%s %.2f lots from %.*f   stop %.*f   target %.*f",
                     dir > 0 ? "LONG" : "SHORT", lots, _Digits, ent,
                     _Digits, slp, _Digits, tpp);

   Comment(StringFormat(
      "LIQUIDITY SNIPER  build %s\n"
      "%s %s   equity %s   live %s  (%d)\n"
      "\n"
      "POSITION   %s\n"
      "P/L        %s        today %s over %d trades\n"
      "ARMED      %s\n"
      "\n"
      "LEVELS     %d buyside  %d sellside  %d FVG  %d order blocks\n"
      "WIN RATE   %s   (%d of %d closed)\n"
      "SPREAD     now %.*f   avg %.*f   worst %.*f\n"
      "STATE      %s\n"
      "\n"
      "E-080: GOLD 1h 51.1%% on 515, +0.487R, PF 1.95, t=+7.4, 6/6 - PROMISING.\n"
      "HALF THESE TRADES LOSE. The money is in 2R, not in being right often.\n"
      "Measured on 15m/1h bars, NOT on M1. XAUUSD only.",
      LQS_BUILD,
      _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period), Money(eq), live, (int)g_readN,
      pos,
      Money(pl), Money(g_dayRealized), g_tradesToday,
      armed,
      ArraySize(g_zB), ArraySize(g_zS), ArraySize(g_fvg), ArraySize(g_ob),
      (g_nTrades > 0 ? StringFormat("%.1f%%", 100.0 * g_nWins / g_nTrades) : "-"),
      g_nWins, g_nTrades,
      _Digits, sp, _Digits, spAvg, _Digits, g_spMax,
      g_lockedPerm ? "LOCKED - max drawdown"
                   : (g_lockedDay ? "locked for today" : "trading")));
}

//==================== EVENTS =======================================
int OnInit()
{
   if(InpDemoOnly && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Print("REFUSING TO START: InpDemoOnly is true and this is not a demo "
            "account. Set InpDemoOnly=false deliberately to trade live.");
      return INIT_FAILED;
   }

   g_atrHandle = iATR(_Symbol, _Period, 14);
   if(g_atrHandle == INVALID_HANDLE) { Print("ATR handle failed"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(20);

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayStartEq = eq;
   g_peakEq     = eq;
   g_dayStamp   = DayStamp();

   ArrayResize(g_zB, 0);  ArrayResize(g_zS, 0);
   ArrayResize(g_pivH, 0); ArrayResize(g_pivL, 0);

   EventSetMillisecondTimer(250);
   Readout();

   Print("=== LIQUIDITY SNIPER BUILD " + LQS_BUILD + " ===");
   Print("If that build stamp is not the one you were sent, MetaEditor has not "
         "rebuilt it. Open the .mq5 and press F7.");
   Print("Geometry is E-077 and is NOT a tuning surface: the limit rests 0.25 "
         "ATR PAST the zone's far edge, the stop is 0.60 ATR beyond the fill, "
         "the target is 2R. Changing any of the three invalidates every number "
         "quoted for it.");
   Print("EXPECT TO LOSE ABOUT HALF THESE TRADES. 47.5% win rate is the "
         "measured figure and it is not a fault. Monte Carlo on trade order "
         "puts the drawdown to expect near 12R, and 18R at the 95th "
         "percentile. Decide now whether you can sit through that.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   // Leave no order behind that nothing is managing.
   KillAll("the EA is shutting down");
   Comment("");
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
}

void OnTimer()
{
   Readout();
}

void OnTick()
{
   int ds = DayStamp();
   if(ds != g_dayStamp)
   {
      g_dayStamp     = ds;
      g_dayStartEq   = AccountInfoDouble(ACCOUNT_EQUITY);
      g_tradesToday  = 0;
      g_lockedDay    = false;
      g_dayRealized  = 0.0;
      Log("new trading day, daily counters reset");
   }

   CheckGuards();

   // There is nothing for OnTick to do about the entry: the limit order is at
   // the BROKER, so it fills on the touch whether or not a tick reaches this
   // EA. That is the point of using a real pending order.

   // EVERYTHING BELOW RUNS ONLY WHEN A BAR CLOSES, so that the backtest and
   // the live account remain the same system.
   datetime bt = iTime(_Symbol, _Period, 0);
   if(bt == g_lastBar) return;
   g_lastBar = bt;

   if(Bars(_Symbol, _Period) < InpPivLen * 4 + 30) return;

   BuildZones();
   BuildSmc();
   ManageOrders();
}

// The stop and the target are on the order, so the broker closes the trade.
// This only counts the result, which is what the readout reports.
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &req,
                        const MqlTradeResult &res)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);

   // THE FILL. g_tradesToday used to be incremented where the EA sent the
   // order; now the broker owns the order, so the only honest place to count a
   // trade is where one actually opened.
   if(entry == DEAL_ENTRY_IN)
   {
      g_tradesToday++;
      // one side filled, so the other must go: the measurement counted one
      // position at a time and two open would be a different strategy.
      KillAll("the other side filled");
      Log(StringFormat("FILLED at %.*f   %d trades today",
                       _Digits, HistoryDealGetDouble(trans.deal, DEAL_PRICE),
                       g_tradesToday));
      return;
   }
   if(entry != DEAL_ENTRY_OUT) return;

   double p = HistoryDealGetDouble(trans.deal, DEAL_PROFIT)
            + HistoryDealGetDouble(trans.deal, DEAL_SWAP)
            + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
   g_nTrades++;
   if(p > 0.0) g_nWins++;
   g_realized    += p;
   g_dayRealized += p;
   Log(StringFormat("CLOSED %s   running %s over %d trades, %.1f%% won",
                    Money(p), Money(g_realized), g_nTrades,
                    100.0 * g_nWins / MathMax(g_nTrades, 1)));
}
