//+------------------------------------------------------------------+
//|  ZoneSniper.mq5  —  SYSTEM A                                     |
//|                                                                  |
//|  M15 liquidity zone  ->  M1 limit inside the zone  ->            |
//|  M1 SuperTrend band as the trailing stop.                        |
//|                                                                  |
//|  THE EVIDENCE (JARVIS/lab/FINAL_ARCHITECTURE.md, E-119..E-126):  |
//|    real zones     +39.6 points over 109 trading days             |
//|    the SAME zones, time-shifted   -584.2 points                  |
//|    EDGE +623.8 points = 21.0 control standard errors             |
//|    out-of-sample (24.1 pts) EXCEEDS in-sample (15.5)             |
//|    356 trades, 3.3/day, on 157,051 real M1 bars built from       |
//|    18.8M bid/ask ticks with the real per-bar spread charged.     |
//|                                                                  |
//|  WHAT IS DELIBERATELY ABSENT, and why - every one of these was   |
//|  tested on the same data and REMOVED because it did not pay:     |
//|    SuperTrend flip as an entry   +0.0021R over control AT ZERO   |
//|                                  COST. There is no edge in it.   |
//|    the DEMA gate                 -3.1 control se: worse than     |
//|                                  random.                          |
//|    a directional / chop filter   filtering only removed trades   |
//|                                  (all 11.0 pts, filtered 2.0-9.0)|
//|    a fixed 2R or 3R target       -29.3 and -43.6 points          |
//|    a 25% give-back trail         in-sample 11.1 -> OOS -0.1      |
//|    the rejection-wick filter     added nothing on top of the     |
//|                                  trail                            |
//|  Every component that remains carries information nothing else   |
//|  in the system provides. That is the whole design rule.          |
//|                                                                  |
//|  NOT FORWARD TESTED. 2018 H1 only. DEMO FIRST.                   |
//+------------------------------------------------------------------+
#property copyright "JARVIS"
#property version   "2.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

#define ZS_BUILD "2.00"

input group "=== SAFETY ==="
input bool   InpDemoOnly     = true;    // refuse to start on a live account
input long   InpMagic        = 880041;  // magic number

//==================== BUILD 2.00 — VEER'S ARCHITECTURE ==============
// He said, and he was right: "supertrend is meant for m1, the point is we catch
// every single m1 trend... m5 or m15 is caught late by supertrend but top ticked
// by smc and ict thru liquidity strats".
//
// Build 1.00 used M15 zones and ignored SuperTrend's DIRECTION entirely, using
// it only as the trail. Testing his combination - M1 SuperTrend supplies the
// direction, an M1 liquidity pivot supplies the timing - measured far better,
// and the trend filter helps ONLY at M1, which is exactly his claim:
//
//   zone TF        no filter    + ST direction    trades/day
//   M15 pivot 3      39.2 pts        24.4 pts        3.2
//   M5  pivot 5      58.6            55.4           6.1
//   M1  pivot 5      48.4            97.1           9.0   <- SHIPPED
//
// The M1 filter DOUBLES the result (48.4 -> 97.1) while M15 and M5 are flat or
// worse. E-127.
//
// VALIDATION (E-128), on 157,051 real M1 bars from 18.8M bid/ask ticks:
//   train 46.7 pts -> TEST 50.3 pts        out of sample EXCEEDS in sample
//   walk-forward   15.8 / 18.7 / 21.1 / 20.3 / 21.2   five of five positive
//   long +56.3, short +40.8                both directions
//   cost      0.11 -> 97.1 | 0.17 -> 82.6 | 0.25 -> 63.1 | 0.40 -> 26.7
//             survives a standard retail spread
//   parameters      a PLATEAU, not a peak: all nine neighbouring cells positive
//   time-shifted control  -1099.3 pts -> EDGE +1196.5 = 79.2 control se
//
// THE KNOWN FAILURE MODE (E-129), stated because it is the thing that will
// break this: the exit is a STOP, so it fills at or below its level.
//   slippage 0.00 -> 97.1 pts | 0.02 -> 77.5 | 0.05 -> 48.1 | 0.10 -> -1.0
// BREAKEVEN AT 0.10 POINTS OF EXIT SLIPPAGE. Normal M1 gold stop fills slip
// 0.01-0.05, so it survives with roughly half the edge. It does not survive a
// broker that slips a full tenth of a point, and that is measurable on demo
// before any money is at risk.
input group "=== THE ZONE ==="
input ENUM_TIMEFRAMES InpZoneTF = PERIOD_M1;  // M1 measured best; M5/M15 also work
input int    InpPivotBars    = 5;       // swing needs this many bars EITHER side
input int    InpZoneLifeM15  = 200;     // a zone expires after this many zone-TF bars
input int    InpMaxZones     = 60;      // zones tracked per side
input bool   InpUseStDirection = true;  // E-127: only take sweeps the M1 SuperTrend agrees with

input group "=== THE ENTRY (M1) ==="
input double InpEntryPastAtr = 0.50;    // limit sits this far PAST the level, in M1 ATR
input int    InpArmWaitM1    = 60;      // cancel an unfilled limit after this many M1 bars
input int    InpCooldownM1   = 120;     // bars after a close before a new entry

input group "=== RISK ==="
input double InpStopAtr      = 4.0;     // initial stop, in M1 ATR
input int    InpMaxBars      = 240;     // absolute time exit, M1 bars
input bool   InpUseFixedLots = true;    // fixed size (recommended while proving it)
input double InpFixedLots    = 0.01;    // E-081: 0.01 is GBP 0.787/point and is the floor
input double InpRiskPct      = 0.50;    // used only when InpUseFixedLots = false
input double InpMaxSpreadPts = 0.60;    // refuse to arm when the spread is wider than this

input group "=== THE TRAIL (this is the SuperTrend's only job) ==="
// E-125 measured SuperTrend as an entry, a filter, a chop detector, an exit and
// a trail. It FAILED as all of them except the trail, where it produced 39.6
// points against 11.0 for a fixed give-back. The band widens in a trend and
// tightens in chop by construction, which is exactly what a give-back rule has
// to do and what a fixed percentage cannot.
input bool   InpUseStTrail   = true;
input int    InpStAtrLen     = 7;
input double InpStMult       = 1.2;

input group "=== GUARDS ==="
input double InpMaxDayLossPct = 3.0;
input double InpMaxDDPct      = 6.0;
input int    InpMaxTradesDay  = 20;
input bool   InpVerbose       = true;

//==================== STATE ========================================
struct Zone { double px; int dir; datetime born; datetime dead; bool used; };
Zone     g_zones[];
int      g_atrM1 = INVALID_HANDLE;
datetime g_lastM1  = 0;
datetime g_lastM15 = 0;
ulong    g_pendBuy = 0;
ulong    g_pendSell = 0;
int      g_armBarBuy = 0;
int      g_armBarSell = 0;
double   g_dayStartEq = 0.0;
double   g_peakEq     = 0.0;
double   g_floor      = 0.0;
int      g_dayStamp   = 0;
int      g_tradesToday = 0;
bool     g_lockDay    = false;
bool     g_lockPerm   = false;
datetime g_lastClose = 0;
// SuperTrend state, recomputed from history every closed bar (never carried)
double   g_stUpper = 0.0;
double   g_stLower = 0.0;
int      g_stDir   = 0;
bool     g_stReady = false;

void Log(string s) { if(InpVerbose) Print("[ZS] ", s); }

double ATR1()
{
   double b[];
   if(CopyBuffer(g_atrM1, 0, 1, 1, b) != 1) return 0.0;
   return b[0];
}

//==================== SUPERTREND ===================================
// Recomputed from a fixed warm-up on every closed bar, never carried in memory.
// A recursive value held between calls desynchronises PERMANENTLY and silently
// after one missed bar - a disconnect, a weekend, a restart, a parameter change.
// This is the same fix E-092 verified as bit-exact against ta.supertrend.
#define ST_WARM 400
void UpdateSuperTrend()
{
   g_stReady = false;
   int avail = Bars(_Symbol, PERIOD_M1);
   int warm  = MathMin(ST_WARM, avail - 2);
   if(warm < InpStAtrLen + 3) return;

   double atrBuf[];
   int h = iATR(_Symbol, PERIOD_M1, InpStAtrLen);
   if(h == INVALID_HANDLE) return;
   if(CopyBuffer(h, 0, 1, warm, atrBuf) != warm) { IndicatorRelease(h); return; }
   MqlRates r[];
   if(CopyRates(_Symbol, PERIOD_M1, 1, warm + 1, r) != warm + 1)
     { IndicatorRelease(h); return; }
   IndicatorRelease(h);
   ArraySetAsSeries(atrBuf, true);
   ArraySetAsSeries(r, true);

   double fu = 0, fl = 0; int dir = 0; bool seeded = false;
   for(int s = warm - 1; s >= 0; s--)
   {
      double a = atrBuf[s];
      if(!MathIsValidNumber(a) || a <= 0.0) continue;
      double mid = (r[s].high + r[s].low) / 2.0;
      double bu = mid + InpStMult * a, bl = mid - InpStMult * a;
      if(!seeded) { fu = bu; fl = bl; dir = (r[s].close > bu) ? -1 : 1; seeded = true; continue; }
      double pu = fu, pl = fl, pc = r[s + 1].close;
      fu = (bu < pu || pc > pu) ? bu : pu;
      fl = (bl > pl || pc < pl) ? bl : pl;
      if(dir == 1 && r[s].close > fu)       dir = -1;
      else if(dir == -1 && r[s].close < fl) dir = 1;
   }
   if(!seeded) return;
   g_stUpper = fu; g_stLower = fl; g_stDir = dir; g_stReady = true;
}

//==================== ZONES ========================================
// A pivot needs InpPivotBars closed bars on BOTH sides, so it is only KNOWABLE
// InpPivotBars bars after it forms. Scanning from shift InpPivotBars+1 is what
// makes that true - reading it any earlier is look-ahead, and it is the single
// easiest way to build a backtest that cannot be traded.
void BuildZones()
{
   int k = InpPivotBars;
   int need = k * 2 + 2;
   MqlRates r[];
   int want = MathMin(InpZoneLifeM15 + need + 10, Bars(_Symbol, InpZoneTF) - 1);
   if(want < need + 2) return;
   if(CopyRates(_Symbol, InpZoneTF, 1, want, r) != want) return;
   ArraySetAsSeries(r, true);

   // shift k+1 is the newest bar that has k confirmed bars on its right
   int c = k + 1;
   if(c + k >= want) return;
   bool isHigh = true, isLow = true;
   for(int t = c - k; t <= c + k; t++)
   {
      if(t == c) continue;
      if(r[t].high >= r[c].high) isHigh = false;
      if(r[t].low  <= r[c].low)  isLow  = false;
   }
   datetime born = r[c].time;
   datetime dead = born + (datetime)(InpZoneLifeM15 * PeriodSeconds(InpZoneTF));
   if(isHigh) AddZone(r[c].high,  1, born, dead);
   if(isLow)  AddZone(r[c].low,  -1, born, dead);

   // prune expired
   datetime now = TimeCurrent();
   for(int i = ArraySize(g_zones) - 1; i >= 0; i--)
      if(g_zones[i].dead < now || g_zones[i].used) RemoveZone(i);
}

void AddZone(double px, int dir, datetime born, datetime dead)
{
   for(int i = 0; i < ArraySize(g_zones); i++)
      if(g_zones[i].born == born && g_zones[i].dir == dir) return;   // already have it
   int n = ArraySize(g_zones);
   if(n >= InpMaxZones * 2) RemoveZone(0);
   n = ArraySize(g_zones);
   ArrayResize(g_zones, n + 1);
   g_zones[n].px = px; g_zones[n].dir = dir;
   g_zones[n].born = born; g_zones[n].dead = dead; g_zones[n].used = false;
   Log(StringFormat("zone %s at %.*f, born %s", dir > 0 ? "HIGH" : "LOW",
                    _Digits, px, TimeToString(born, TIME_MINUTES)));
}

void RemoveZone(int i)
{
   int last = ArraySize(g_zones) - 1;
   if(i < 0 || i > last) return;
   g_zones[i] = g_zones[last];
   ArrayResize(g_zones, last);
}

// The nearest zone on the side we want, that price has NOT already passed.
bool BestZone(int dir, double px, double a, double &lvl, int &zi)
{
   // dir = +1 means we want to BUY, so we want a swing LOW (zone dir -1)
   double best = 0; zi = -1;
   for(int i = 0; i < ArraySize(g_zones); i++)
   {
      if(g_zones[i].used) continue;
      int want = (dir > 0) ? -1 : 1;
      if(g_zones[i].dir != want) continue;
      double l = g_zones[i].px - dir * InpEntryPastAtr * a;
      // the limit must still be BEYOND price, or the sweep has already happened
      if(dir > 0 && l >= px) continue;
      if(dir < 0 && l <= px) continue;
      if(zi < 0 || MathAbs(l - px) < MathAbs(best - px)) { best = l; zi = i; }
   }
   if(zi < 0) return false;
   lvl = best;
   return true;
}

//==================== POSITION / ORDER HELPERS =====================
int PosCount()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) == InpMagic &&
         PositionGetString(POSITION_SYMBOL) == _Symbol) n++;
   }
   return n;
}

bool OrderAlive(ulong tk)
{
   if(tk == 0) return false;
   return OrderSelect(tk);
}

void KillSide(int dir, string why)
{
   ulong tk = (dir > 0) ? g_pendBuy : g_pendSell;
   if(tk == 0) return;
   if(OrderAlive(tk))
   {
      if(!trade.OrderDelete(tk))
         Log(StringFormat("could not delete %I64u: %d %s", tk,
                          trade.ResultRetcode(), trade.ResultRetcodeDescription()));
      else if(why != "") Log(StringFormat("cancelled %s limit: %s",
                                          dir > 0 ? "BUY" : "SELL", why));
   }
   if(dir > 0) g_pendBuy = 0; else g_pendSell = 0;
}

void KillAll(string why) { KillSide(1, why); KillSide(-1, why); }

double LotFor(double stopPts)
{
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(InpUseFixedLots)
   {
      double lf = InpFixedLots;
      if(st > 0) lf = MathFloor(lf / st) * st;
      return NormalizeDouble(MathMax(mn, MathMin(mx, lf)), 2);
   }
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0 || ts <= 0 || stopPts <= 0) return 0.0;
   double lossPerLot = (stopPts / ts) * tv;
   if(lossPerLot <= 0) return 0.0;
   double want = (eq * InpRiskPct / 100.0) / lossPerLot;
   if(st > 0) want = MathFloor(want / st) * st;
   // THE LOT FLOOR IS A SILENT RISK MULTIPLIER. E-102 found this in the other
   // EA: MathMax rounds UP to the broker minimum whenever the account is too
   // small and says nothing, so the trade carries several times the configured
   // risk, on every trade, for ever. It is reported here instead of hidden.
   if(mn > 0 && want < mn)
   {
      static bool warned = false;
      if(!warned)
      {
         warned = true;
         PrintFormat("[ZS] RISK WARNING: %.2f%% of %.2f needs %.5f lots but the "
                     "broker minimum is %.2f. Every trade will risk %.2f "
                     "(%.1f%% of equity) - %.1fx what you asked for. E-081: "
                     "0.01 cannot be made smaller, the ACCOUNT must be bigger.",
                     InpRiskPct, eq, want, mn, mn * lossPerLot,
                     100.0 * mn * lossPerLot / eq, mn / MathMax(want, 1e-9));
      }
      want = mn;
   }
   return NormalizeDouble(MathMax(mn, MathMin(mx, want)), 2);
}

double MinStopDist()
{
   long lvl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(lvl <= 0 || pt <= 0) return 0.0;
   return (double)lvl * pt;
}

//==================== ARMING =======================================
void ArmSide(int dir)
{
   if(g_lockDay || g_lockPerm) return;
   if(PosCount() > 0) return;
   if(g_tradesToday >= InpMaxTradesDay) return;
   if(TimeCurrent() - g_lastClose < InpCooldownM1 * 60) return;
   if(OrderAlive(dir > 0 ? g_pendBuy : g_pendSell)) return;

   double a = ATR1();
   if(a <= 0.0) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sp  = ask - bid;
   if(sp > InpMaxSpreadPts)
   {
      Log(StringFormat("not arming: spread %.3f > %.3f", sp, InpMaxSpreadPts));
      return;
   }

   // E-127: SuperTrend supplies the DIRECTION, the zone supplies the TIMING.
   // Only at M1 does this filter pay - it doubled the result there and was flat
   // or negative on M5 and M15, which is why it is a switch and not a constant.
   if(InpUseStDirection)
   {
      if(!g_stReady) return;
      bool agrees = (g_stDir == -1 && dir > 0) || (g_stDir == 1 && dir < 0);
      if(!agrees) return;
   }

   double px = (dir > 0) ? ask : bid;
   double lvl; int zi;
   if(!BestZone(dir, px, a, lvl, zi)) return;

   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   lvl = NormalizeDouble(lvl, dg);
   double stop = NormalizeDouble(lvl - dir * InpStopAtr * a, dg);
   double md = MinStopDist();
   if(md > 0.0 && MathAbs(lvl - stop) < md)
      stop = NormalizeDouble(lvl - dir * md, dg);

   double lots = LotFor(MathAbs(lvl - stop));
   if(lots <= 0.0) return;

   // NO TAKE PROFIT. E-122 measured a fixed 2R at -29.3 points and 3R at -43.6
   // on these same entries. The trail is the exit.
   bool ok = (dir > 0)
      ? trade.BuyLimit(lots, lvl, _Symbol, stop, 0.0, ORDER_TIME_GTC, 0, "ZS zone")
      : trade.SellLimit(lots, lvl, _Symbol, stop, 0.0, ORDER_TIME_GTC, 0, "ZS zone");
   if(ok)
   {
      if(dir > 0) { g_pendBuy = trade.ResultOrder(); g_armBarBuy = Bars(_Symbol, PERIOD_M1); }
      else        { g_pendSell = trade.ResultOrder(); g_armBarSell = Bars(_Symbol, PERIOD_M1); }
      Log(StringFormat("armed %s limit %.*f, stop %.*f, %.2f lots (zone %.*f)",
                       dir > 0 ? "BUY" : "SELL", dg, lvl, dg, stop, lots,
                       dg, g_zones[zi].px));
   }
   else
      Log(StringFormat("arm failed: %d %s", trade.ResultRetcode(),
                       trade.ResultRetcodeDescription()));
}

void AgeOrders()
{
   int now = Bars(_Symbol, PERIOD_M1);
   if(g_pendBuy != 0 && now - g_armBarBuy > InpArmWaitM1)
      KillSide(1, "unfilled past the wait window");
   if(g_pendSell != 0 && now - g_armBarSell > InpArmWaitM1)
      KillSide(-1, "unfilled past the wait window");
}

//==================== THE TRAIL ====================================
// THE SUPERTREND'S ONLY JOB, and the one it measured well at (E-125: 39.6
// points against 11.0 for a fixed 25% give-back; out-of-sample 24.1 against
// in-sample 15.5). The band widens in a trend and tightens in chop by
// construction, which is what a give-back rule must do and a fixed percentage
// cannot. It lives AT THE BROKER, so a spike cannot beat it and it does not
// need this EA awake (E-086).
void TrailStop()
{
   if(!InpUseStTrail || !g_stReady) return;
   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double md = MinStopDist();

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      int    dir = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      double sl  = PositionGetDouble(POSITION_SL);
      double band = (dir > 0) ? g_stLower : g_stUpper;
      if(band <= 0.0) continue;
      double want = NormalizeDouble(band, dg);

      double px = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                            : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      // never inside the broker's own stop level, or the modify is rejected
      if(md > 0.0 && MathAbs(px - want) < md) continue;
      // RATCHET: profitable direction only. A stop that can move backwards is
      // not a stop.
      if(sl != 0.0 && ((dir > 0 && want <= sl) || (dir < 0 && want >= sl))) continue;

      if(!trade.PositionModify(tk, want, PositionGetDouble(POSITION_TP)))
         Log(StringFormat("trail modify failed: %d %s", trade.ResultRetcode(),
                          trade.ResultRetcodeDescription()));
      else
         Log(StringFormat("trail -> %.*f", dg, want));
   }
}

void AgePositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if(TimeCurrent() - opened >= InpMaxBars * 60)
      {
         if(trade.PositionClose(tk)) Log("time exit at the bar cap");
         else Log(StringFormat("time-exit close failed: %d %s",
                               trade.ResultRetcode(), trade.ResultRetcodeDescription()));
      }
   }
}

//==================== GUARDS =======================================
void CheckGuards()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_peakEq) g_peakEq = eq;
   if(g_floor <= 0.0) g_floor = g_dayStartEq * (1.0 - InpMaxDDPct / 100.0);

   if(!g_lockPerm && eq <= g_floor)
   {
      g_lockPerm = true;
      KillAll("max drawdown");
      PrintFormat("[ZS] PERMANENT LOCK: equity %.2f at the %.1f%% floor %.2f",
                  eq, InpMaxDDPct, g_floor);
   }
   if(!g_lockDay && g_dayStartEq > 0.0)
   {
      double lost = (g_dayStartEq - eq) / g_dayStartEq * 100.0;
      if(lost >= InpMaxDayLossPct)
      {
         g_lockDay = true;
         KillAll("daily loss");
         PrintFormat("[ZS] LOCKED FOR TODAY: down %.2f%% of %.2f%%",
                     lost, InpMaxDayLossPct);
      }
   }
}

int DayStamp()
{
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   return t.year * 10000 + t.mon * 100 + t.day;
}

//==================== LIFECYCLE ====================================
int OnInit()
{
   if(InpDemoOnly && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Print("[ZS] REFUSING TO START: InpDemoOnly is true and this is not a demo "
            "account. This system has NEVER been forward tested. Set "
            "InpDemoOnly=false deliberately, and only after a demo run.");
      return INIT_FAILED;
   }
   g_atrM1 = iATR(_Symbol, PERIOD_M1, 14);
   if(g_atrM1 == INVALID_HANDLE) { Print("[ZS] ATR handle failed"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(20);

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayStartEq = eq; g_peakEq = eq;
   g_floor = eq * (1.0 - InpMaxDDPct / 100.0);
   g_dayStamp = DayStamp();
   ArrayResize(g_zones, 0);

   PrintFormat("[ZS] === ZONE SNIPER %s ===  M15 zones -> M1 limit -> SuperTrend trail",
               ZS_BUILD);
   Print("[ZS] Evidence: +1196.5 points over a time-shifted control = 79.2 se; "
         "OOS 50.3 vs IS 46.7; walk-forward 5 of 5. 2018 H1 only. NOT forward tested.");
   Print("[ZS] KNOWN LIMIT: the exit is a stop, and the edge breaks even at 0.10 "
         "points of exit slippage. Measure your broker's on demo first.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_atrM1 != INVALID_HANDLE) IndicatorRelease(g_atrM1);
}

void OnTick()
{
   int ds = DayStamp();
   if(ds != g_dayStamp)
   {
      g_dayStamp = ds;
      g_dayStartEq = AccountInfoDouble(ACCOUNT_EQUITY);
      g_tradesToday = 0;
      g_lockDay = false;
      Log("new trading day");
   }

   CheckGuards();

   datetime m1 = iTime(_Symbol, PERIOD_M1, 0);
   if(m1 != g_lastM1)
   {
      g_lastM1 = m1;
      UpdateSuperTrend();
      AgeOrders();
      AgePositions();
      datetime m15 = iTime(_Symbol, InpZoneTF, 0);
      if(m15 != g_lastM15) { g_lastM15 = m15; BuildZones(); }
      if(PosCount() == 0) { ArmSide(1); ArmSide(-1); }
   }

   TrailStop();
}

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &req, const MqlTradeResult &res)
{
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      if(!HistoryDealSelect(trans.deal)) return;
      if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic) return;
      long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
      if(entry == DEAL_ENTRY_IN)
      {
         g_tradesToday++;
         // one side filled: the other is now a trade we do not want
         KillAll("filled on the other side");
         // mark the zone consumed so it is not re-armed
         for(int i = 0; i < ArraySize(g_zones); i++) g_zones[i].used = true;
         Log("FILLED");
      }
      else if(entry == DEAL_ENTRY_OUT)
      {
         g_lastClose = TimeCurrent();
         Log(StringFormat("closed, profit %.2f",
                          HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));
      }
   }
}
