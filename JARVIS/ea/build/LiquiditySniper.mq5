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
//   2. THE ENTRY IS THE RETEST, NOT THE SWEEP.
//      Buying the sweep bar's close scores MINUS 0.003R WITH ZERO COSTS. Not a
//      weak edge eaten by the spread - no edge at all. The entire edge is in
//      waiting for price to come BACK to the level that was swept. So a sweep
//      places a LIMIT ORDER and the fill is the trade.
//
//   3. THE TARGET IS NEAR AND THE STOP IS WIDE.
//      Aiming at the opposite zone, 3-6 ATR away, is a 33% win rate however
//      good the trigger is. 0.5 ATR behind a 1.5 ATR stop is 80.5% pooled -
//      which is Veer's reported number, to within a point.
//
//  E-069, that geometry attacked:
//    GOLD 1h   n=401  87.8% win  +0.106R  PF 1.85  t=+5.05
//              OOS +0.098 / +0.114   walk-forward 6/6 blocks
//              7.8 control-sd clear of twelve random-entry seeds   PROMISING
//    US500 1h  n=345  84.1%  +0.053R  PF 1.33  t=+2.12  6/6         PROMISING
//    EURUSD and GBPUSD, both timeframes                             REJECTED
//
//  PROMISING is the strongest word the directive allows for something that has
//  survived. It does not mean profitable and this EA does not claim to be.
//
//  WHAT YOU MUST KNOW BEFORE RUNNING IT
//   * GOLD AND INDICES. FX is rejected outright on these same rules.
//   * It risks 1.5 to make 0.5, so it needs about 75% just to break even.
//     Every point of win rate lost to live slippage costs roughly 0.03R. There
//     is no margin for sloppiness in this shape - that is the trade-off that
//     buys the high win rate, and it is not free.
//   * IT WAS MEASURED ON 15m AND 1h BARS. There is no M1 or M5 data in the
//     repository. Running it on M1 is an extrapolation, and the honest way to
//     end that is to run ExportHistory.mq5 and re-measure.
//   * The spread barely matters here: +0.111R at zero spread, +0.090R at the
//     0.46 measured off Veer's own terminal. The 1.5 ATR stop makes R large
//     enough that the spread is a rounding error. That is unusual and it is
//     the strategy's best structural property.
//
#property copyright "JARVIS"
#property version   "1.00"
#property strict

#define LQS_BUILD "2026-09-02 / 1.00 / retest entry, E-069 geometry"

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

input group "=== SWEEP  (LuxAlgo: the wick rule) ==="
input double InpWickShare     = 0.30;   // wick must be this share of the bar

input group "=== THE TRADE  (E-069 - do not tune without re-measuring) ==="
input int    InpRetestWait    = 20;     // bars the limit order stays live
input double InpStopAtr       = 1.5;    // stop, ATR beyond the SWEEP WICK
input double InpTargetAtr     = 0.50;   // target, ATR from the fill
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

// the armed setup: a resting order that has not filled yet
int      g_aDir  = 0;
double   g_aLvl  = 0.0;    // the limit price
double   g_aWick = 0.0;    // the sweep bar's own extreme
double   g_aAtr  = 0.0;
datetime g_aBar  = 0;
int      g_aAge  = 0;
ulong    g_aTicket = 0;    // the REAL pending order at the broker

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
void   ScanSweep();
void   ManageArmed();
void   PlacePending();
void   KillPending(string why);
bool   HavePosition();
void   AddZone(Zone &Z[], double &piv[], double at, int dir, double mar, int bar);
void   ExpireZones(Zone &Z[], int bar);
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

   ExpireZones(g_zB, bar);
   ExpireZones(g_zS, bar);
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

//==================== THE SWEEP ====================================
// Runs on the CLOSED bar (shift 1). A wick through a zone that closes back
// inside is a sweep and arms the opposite side. A CLOSE through it is a break
// and kills the zone - those are different events and conflating them is how
// this strategy loses money.
void ScanSweep()
{
   if(g_aDir != 0) return;              // one armed setup at a time
   if(HavePosition()) return;           // and none while a trade is live

   double o = iOpen(_Symbol, _Period, 1);
   double h = iHigh(_Symbol, _Period, 1);
   double l = iLow(_Symbol, _Period, 1);
   double c = iClose(_Symbol, _Period, 1);
   double rng = MathMax(h - l, SymbolInfoDouble(_Symbol, SYMBOL_POINT));
   double upW = h - MathMax(o, c);
   double dnW = MathMin(o, c) - l;
   double a = ATRv(1);
   if(a <= 0.0) return;

   // buyside zones: a wick above that closes back below -> SELL the retest
   for(int i = 0; i < ArraySize(g_zB); i++)
   {
      if(g_zB[i].broken) continue;
      if(c > g_zB[i].top) { g_zB[i].broken = true; continue; }
      if(h > g_zB[i].top && c < g_zB[i].top && (upW / rng) >= InpWickShare)
      {
         g_aDir = -1;  g_aLvl = g_zB[i].top;  g_aWick = h;
         g_aAtr = a;   g_aBar = iTime(_Symbol, _Period, 1);  g_aAge = 0;
         Log(StringFormat("SWEEP buyside %.*f -> SELL limit at %.*f, "
                          "invalidated by a close above %.*f",
                          _Digits, g_zB[i].px, _Digits, g_aLvl, _Digits, g_aWick));
         PlacePending();
         return;
      }
   }
   // sellside zones: a wick below that closes back above -> BUY the retest
   for(int i = 0; i < ArraySize(g_zS); i++)
   {
      if(g_zS[i].broken) continue;
      if(c < g_zS[i].bot) { g_zS[i].broken = true; continue; }
      if(l < g_zS[i].bot && c > g_zS[i].bot && (dnW / rng) >= InpWickShare)
      {
         g_aDir = 1;   g_aLvl = g_zS[i].bot;  g_aWick = l;
         g_aAtr = a;   g_aBar = iTime(_Symbol, _Period, 1);  g_aAge = 0;
         Log(StringFormat("SWEEP sellside %.*f -> BUY limit at %.*f, "
                          "invalidated by a close below %.*f",
                          _Digits, g_zS[i].px, _Digits, g_aLvl, _Digits, g_aWick));
         PlacePending();
         return;
      }
   }
}

// A setup dies if price CLOSES beyond the sweep's own extreme - the sweep was
// not a rejection after all - or if the retest simply never arrives.
void ManageArmed()
{
   if(g_aDir == 0) return;
   g_aAge++;
   double c = iClose(_Symbol, _Period, 1);
   bool dead = (g_aDir == 1 && c < g_aWick) || (g_aDir == -1 && c > g_aWick);
   if(dead)
   {
      KillPending("price closed beyond the sweep wick, so it was not a rejection");
      g_aDir = 0;
      return;
   }
   if(g_aAge > InpRetestWait)
   {
      KillPending(StringFormat("no retest in %d bars", InpRetestWait));
      g_aDir = 0;
      return;
   }
   // the broker filled it, or expired it, while we were not looking
   if(g_aTicket != 0 && !OrderSelect(g_aTicket))
   {
      g_aTicket = 0;
      g_aDir    = 0;
   }
}

//==================== THE RESTING ORDER =============================
// A REAL pending order at the broker, not a price check inside OnTick.
//
// This matters more here than anywhere else in either EA. The whole measured
// edge of this strategy IS the fill: E-068 found that taking the same signals
// at the sweep bar's close instead scores -0.003R with zero costs. A simulated
// limit only fills when a tick happens to arrive while price is through the
// level, and on a fast retest wick that tick may never come - so the EA would
// miss exactly the fills the backtest counted, and keep the ones it did not.
// A broker-side limit fills on the touch whether or not this EA is looking.
//
// The stop and target go ON the order, so a disconnect cannot leave a naked
// position: the broker holds both sides of the trade from the moment it fills.
void PlacePending()
{
   KillPending("");                    // never two at once
   if(g_aDir == 0) return;
   if(g_lockedDay || g_lockedPerm) return;
   if(PosCount() >= InpMaxPositions) return;
   if(g_tradesToday >= InpMaxTradesDay) return;

   double a = (g_aAtr > 0.0) ? g_aAtr : ATRv(1);
   if(a <= 0.0) return;

   int    dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double lvl  = NormalizeDouble(g_aLvl, dg);
   double stop = NormalizeDouble(g_aWick - g_aDir * InpStopAtr * a, dg);
   double tgt  = NormalizeDouble(lvl + g_aDir * InpTargetAtr * a, dg);

   // the broker's own floor, applied to the ORDER price - a limit inside the
   // stops level is rejected, and a rejected order is a trade silently missed
   double md = MinStopDist();
   if(md > 0.0)
   {
      if(MathAbs(lvl - stop) < md) stop = NormalizeDouble(lvl - g_aDir * md, dg);
      if(MathAbs(tgt - lvl)  < md) tgt  = NormalizeDouble(lvl + g_aDir * md, dg);
   }
   if((lvl - stop) * g_aDir <= 0.0)
   {
      Log("refusing to arm: the stop is on the wrong side of the limit");
      g_aDir = 0;
      return;
   }

   // A limit must rest on the far side of the market. If price has already
   // gone through the level by the time the bar closed, the retest happened
   // inside the sweep bar and the setup is gone - it is not an excuse to
   // chase it with a market order.
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if((g_aDir == 1 && ask <= lvl) || (g_aDir == -1 && bid >= lvl))
   {
      Log("not arming: price is already through the level, the retest is gone");
      g_aDir = 0;
      return;
   }

   datetime exp = iTime(_Symbol, _Period, 0)
                + (datetime)(PeriodSeconds(_Period) * (InpRetestWait + 1));

   bool ok = (g_aDir == 1)
      ? trade.BuyLimit(InpEntryLots, lvl, _Symbol, stop, tgt,
                       ORDER_TIME_SPECIFIED, exp, "LQS retest")
      : trade.SellLimit(InpEntryLots, lvl, _Symbol, stop, tgt,
                        ORDER_TIME_SPECIFIED, exp, "LQS retest");
   if(ok)
   {
      g_aTicket = trade.ResultOrder();
      Log(StringFormat("ARMED %s LIMIT %.2f lots at %.*f   stop %.*f   "
                       "target %.*f   ticket %I64u",
                       g_aDir > 0 ? "BUY" : "SELL", InpEntryLots,
                       dg, lvl, dg, stop, dg, tgt, g_aTicket));
   }
   else
   {
      Log(StringFormat("ARM REJECTED: %d %s", trade.ResultRetcode(),
                       trade.ResultRetcodeDescription()));
      g_aDir = 0;
   }
}

void KillPending(string why)
{
   if(g_aTicket == 0) return;
   if(OrderSelect(g_aTicket))
   {
      trade.OrderDelete(g_aTicket);
      if(why != "") Log("cancelled the resting order: " + why);
   }
   g_aTicket = 0;
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

   string armed = (g_aDir == 0)
      ? "none"
      : StringFormat("%s limit at %.*f   %d/%d bars   dies on a close %s %.*f",
                     g_aDir > 0 ? "BUY" : "SELL", _Digits, g_aLvl,
                     g_aAge, InpRetestWait, g_aDir > 0 ? "below" : "above",
                     _Digits, g_aWick);

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
      "ZONES      %d buyside   %d sellside\n"
      "WIN RATE   %s   (%d of %d closed)\n"
      "SPREAD     now %.*f   avg %.*f   worst %.*f\n"
      "STATE      %s\n"
      "\n"
      "E-069: GOLD 1h 87.8%% on 401, PF 1.85, walk-forward 6/6 - PROMISING.\n"
      "Measured on 15m/1h bars, NOT on M1. FX is rejected on these rules.",
      LQS_BUILD,
      _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period), Money(eq), live, (int)g_readN,
      pos,
      Money(pl), Money(g_dayRealized), g_tradesToday,
      armed,
      ArraySize(g_zB), ArraySize(g_zS),
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
   Print("Geometry is E-069 and is NOT a tuning surface: retest entry, stop "
         "1.5 ATR beyond the sweep wick, target 0.50 ATR. Changing any of the "
         "three invalidates every number quoted for it.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   // Leave no order behind that nothing is managing.
   KillPending("the EA is shutting down");
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
   ManageArmed();
   ScanSweep();
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
      g_aTicket = 0;
      g_aDir    = 0;
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
