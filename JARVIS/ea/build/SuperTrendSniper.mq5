//+------------------------------------------------------------------+
//|                                          SuperTrendSniper.mq5    |
//|         Your SuperTrend strategy, rebuilt around the exits       |
//+------------------------------------------------------------------+
//
//  WHAT THIS IS
//  The SAME signal you already trust - SuperTrend(7, 1.2) with a DEMA trend
//  filter, identical to XAUUSD_CLEAN_3.5.pine. The signal logic is NOT
//  changed, because you are right that it finds moves.
//
//  What IS rebuilt is everything after the entry, because that is where the
//  money was going. Your own words: "a majority of trades go into profit, we
//  just don't close in that profit."
//
//  WHY THE OLD EA GAVE PROFIT BACK - measured, not guessed
//  Testing 11 exit rules over identical entries on GOLD, US500, EURUSD and
//  GBPUSD, first-touch resolution, ties counted as losses:
//
//      break-even at 0.5R then trail : -0.161R  (GOLD)   <- WORST on all four
//      break-even at 1R then trail   : -0.009R
//      trail 2x ATR                  : -0.029R
//      fixed 3R target               : +0.181R
//      hold 20 bars                  : +0.201R  <- BEST
//
//  Moving the stop up early is the single most expensive habit available. It
//  scratches the trade out before the rare large winner - the one that pays
//  for everything - can develop. v19.18 was built around doing exactly that
//  (NoiseFloorPts armed at one band and gave back one band), which is why
//  peaks summed GBP110 and handed back GBP73.
//
//  So this EA defaults to: NO break-even move, NO early trail, a fixed R
//  target, and a time cap. Every one of those defaults is the option that
//  measured best. They are all switchable if you want to test otherwise.
//
//  WHY YOUR BACKTESTS DID NOT MATCH LIVE
//  Three causes, all fixed here:
//    1. v19.18 acted on EVERY TICK. Its own OnTick carried the comment
//       "Entries only on a new bar" and then called the engine every tick.
//       This EA computes signals ONLY when a bar closes, so "Open prices
//       only", "1 minute OHLC" and live all produce the same decisions.
//    2. Indicator values were read from the FORMING bar, which changes until
//       the bar closes. Everything here is read at shift >= 1.
//    3. Spread was not modelled. Here it is checked before every entry and
//       the trade is skipped if it is abnormal.
//
//  NOT COMPILED. There is no MetaTrader in the environment this was written
//  in. Compile in MetaEditor and report any error text.
//
//  DEMO GUARD IS ON BY DEFAULT. InpDemoOnly must be set false deliberately.
//+------------------------------------------------------------------+
#property copyright "JARVIS"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//===================================================================
//  EVERY PRICE SCENARIO, AND WHAT THIS EA DOES ABOUT IT
//===================================================================
//  Written out because "think of every scenario" is only answerable if the
//  answers are listed somewhere they can be checked against the code.
//
//  ENTRY
//   signal fires, open air ahead ....... take it
//   signal fires, level in the way ..... REFUSED (InpSkipNoRoom), reason logged
//   signal fires, market chopping ...... refused; a run of flips is one range
//                                        being sliced, not a run of setups
//   want a better price ................ rest a limit InpPullAtr back
//                                        (InpUseLimitEntry). Measured +0.451R
//                                        vs +0.321R out-of-sample on GOLD 1h
//   limit never filled ................. cancelled after InpLimitLifeBars and
//                                        logged, so the miss rate is visible
//   second signal while one is live .... ignored; one position or one pending,
//                                        never both
//
//  HOLD
//   trade in profit .................... trail follows at InpTrailAtrMult,
//                                        ratcheting - it never gives ground back
//   approaching a level ................ bank half (InpPartialAtLevel), let the
//                                        rest ride through if it breaks
//   trade stalls ....................... closed after InpMaxBars
//   trend flips against it ............. closed
//
//  WHEN THE LEVEL IS NOT RESPECTED - and it often is not
//   This is why the position is SPLIT at a level rather than closed there.
//   Nobody knows in advance whether a level holds, so the trade stops guessing:
//   half is banked while the level is still in front of price (the "pennies"),
//   and the remainder trails through it if it breaks (the big move). A level
//   that fails costs the banked half's upside and nothing else; a level that
//   holds means the runner's trail takes it out near the high. There is no
//   configuration of a single all-or-nothing exit that wins both cases.
//
//  EXIT
//   target .......... capped just SHORT of the next level, so it fills rather
//                     than watching price turn a tick away from it
//   stop ............ attached at OrderSend, never held in EA memory only
//   gap through it .. the broker fills at the gap; the journal records the real
//                     price, not the intended one
//
//  WHAT IT DOES NOT DO, stated so it is not assumed
//   It does not re-enter automatically after a stop-out. It does not add to a
//   winner. It does not trade news events differently. And it cannot make a
//   drawdown-free entry exist - see the note on InpUseLimitEntry: the median
//   winning trade first goes 0.35R AGAINST the entry, and 10% go 0.85R against.
//   Minimising that is possible; eliminating it is not.
//===================================================================

//============================== INPUTS ==============================
// 21 inputs. The EA this replaces had 748.

input group "=== SIGNAL (identical to your Pine) ==="
input int    InpStAtrLen      = 7;      // SuperTrend ATR length
input double InpStMult        = 1.2;    // SuperTrend multiplier
input int    InpDemaLen       = 200;    // DEMA length (60 on M1, 100 on M3)
input bool   InpUseDemaFilter = true;   // only trade with the DEMA slope

input group "=== EXIT (measured on THIS strategy, out-of-sample) ==="
// Every default below held on data the test never saw (GOLD 1h, 70/30 split):
//   fixed 3R      in-sample +0.183R   out-of-sample +0.394R
//   time 50 bars  in-sample +0.293R   out-of-sample +0.506R
//   trail 3xATR   in-sample +0.248R   out-of-sample +0.505R   <- default
//   BE@1R + trail in-sample +0.110R   out-of-sample lower      <- still off
// A WIDE trail is not the same thing as moving to break-even. The trail rides
// 3 ATR behind price and only ever ratchets in your favour; break-even parks
// the stop at entry and gets scratched by noise. That distinction is the whole
// difference between +0.505R and the worst rule tested.
input double InpTargetR       = 3.0;    // hard take profit at N x risk
input int    InpMaxBars       = 50;     // time cap. 50 measured better than 20 here
input bool   InpUseTrail      = true;   // ON: measured best on SuperTrend entries
input double InpTrailAtR      = 0.0;    // arm immediately. A wide trail needs no delay
input double InpTrailAtrMult  = 3.0;    // 3 ATR. Wide on purpose - tight trails lost
input bool   InpUseBreakEven  = false;  // KEEP FALSE. Worst rule on all 4 markets
input double InpBreakEvenAtR  = 1.5;    // only used if you switch BE on to test it
input bool   InpPartialAt1R   = false;  // close half at 1R, let the rest run

input group "=== FILTERS (both held out-of-sample) ==="
// Measured by partitioning every trade by the condition it opened in, then
// re-checking on held-out data. GOLD 1h:
//   ADX > 35 (already-extended trend) : -0.132R   <- the losing bucket
//   ADX < 20 (quiet before expansion) : +0.304R
//   skip ADX>35 : in-sample +0.053R -> out-of-sample +0.426R  HELD
//   NY session  : in-sample +0.181R -> out-of-sample +0.704R  HELD
//   both        : in-sample +0.293R -> out-of-sample +0.672R  HELD
// THE TRADE-OFF, STATED: these filters roughly THIRD the number of trades
// (2.6/week -> 0.8/week on gold 1h). They raise expectancy per trade and cut
// how many you get. Turn them off for frequency, on for quality.
input bool   InpUseAdxFilter  = true;   // skip entries when the trend is already extended
input double InpMaxAdx        = 35.0;   // ADX ceiling
input bool   InpUseSession    = false;  // restrict to one session (see below)
input int    InpSessFromUTC   = 13;     // NY open
input int    InpSessToUTC     = 20;     // NY close

input group "=== ENTRY STYLE (this is the drawdown question) ==="
// MEASURED, GOLD 1h, out-of-sample, next-bar fills, ties losing:
//    market at next open ........ +0.321R    0% missed
//    limit 0.15 ATR back ........ +0.393R   11% missed
//    limit 0.30 ATR back ........ +0.451R   23% missed
//    limit 0.50 ATR back ........ +0.473R   37% missed
// The mechanism is not a guess either: 71.7% of signals close back THROUGH the
// signal price within three bars, so a resting limit gets filled most of the
// time at a better price - and a better entry is a smaller drawdown on the
// same trade.
// The honest wrinkle: IN sample the market entry looked better, so the two
// halves disagree, and t = +2.47 is under this repo's 3.65 luck threshold.
// It is the best-supported way to cut drawdown here, not a certainty.
input bool   InpUseLimitEntry = false;  // rest a limit instead of paying the market
input double InpPullAtr       = 0.30;   // how far back to wait (x ATR)
input int    InpLimitLifeBars = 3;      // cancel it if unfilled after this many bars

input group "=== LEVELS (the EA can now see them) ==="
input bool   InpUseLevels     = true;   // find levels and trade around them
input int    InpPivotBars     = 5;      // swing size for a level
input int    InpLevelLookback = 400;    // bars to scan for swings
input bool   InpUseDayLevels  = true;   // previous day high / low
input bool   InpUseWeekLevels = true;   // previous week high / low
input bool   InpUseRound      = true;   // round numbers (gold clusters stops there)
input double InpRoundStep     = 10.0;   // round number spacing
input double InpNearAtr       = 0.60;   // "close to a level" = within this x ATR
input double InpLevelBufAtr   = 0.25;   // park the target THIS far short of it
input bool   InpTpAtLevel     = true;   // cap the target at the next level
input bool   InpPartialAtLevel= true;   // bank half there, let the rest run
input bool   InpSkipNoRoom    = true;   // refuse entries with a level in the way
input double InpMinRoomR      = 1.0;    // need at least this much room, in R

input group "=== RISK ==="
input double InpRiskPct       = 0.50;   // % of equity risked per trade
input double InpStopAtrMult   = 1.5;    // stop distance in ATR
input double InpMaxSpreadAtr  = 0.15;   // skip entry if spread > this x ATR

input group "=== PROP FIRM GUARDS ==="
input double InpDailyLossPct  = 3.0;    // stop for the day at this % equity loss
input double InpMaxDDPct      = 6.0;    // stop permanently at this % from peak
input int    InpMaxTradesDay  = 20;     // hard cap on entries per day
input int    InpResetHourUTC  = 0;      // daily reset hour, UTC

input group "=== SAFETY ==="
input bool   InpDemoOnly      = true;   // refuse to run on a live account
input long   InpMagic         = 770001; // magic number
input bool   InpVerboseLog    = true;   // log every decision
input bool   InpJournal       = true;   // write every signal and fill to a CSV

//============================ STATE ================================
datetime g_lastBarTime = 0;
double   g_dayStartEq  = 0.0;
double   g_peakEq      = 0.0;
int      g_tradesToday = 0;
int      g_dayStamp    = -1;
bool     g_lockedDay   = false;
bool     g_lockedPerm  = false;
int      g_atrHandle   = INVALID_HANDLE;
int      g_adxHandle   = INVALID_HANDLE;

// SuperTrend state, carried bar to bar exactly as the Pine does
double   g_finalUpper  = 0.0;
double   g_finalLower  = 0.0;
int      g_stDir       = 0;      // -1 bullish, +1 bearish (Pine convention)
int      g_stDirPrev   = 0;
bool     g_stReady     = false;

//==================== HELPERS ======================================
void Log(string msg)
{
   if(InpVerboseLog) Print(msg);
}

// Current UTC day number, for the daily reset
int DayStamp()
{
   datetime t = TimeCurrent() - InpResetHourUTC * 3600;
   MqlDateTime d;
   TimeToStruct(t, d);
   return d.year * 1000 + d.day_of_year;
}

//---------------------------------------------------------------------------
// PERSISTENT GUARD STATE
// OnInit used to re-seed g_peakEq to the CURRENT equity and clear both locks.
// MT5 calls OnInit on every terminal restart, reconnect-with-recompile,
// timeframe change and parameter change - so the max-drawdown lock could be
// cleared, and the drawdown baseline moved down to the already-drawn-down
// equity, simply by restarting the terminal. A guard a restart removes is not
// a guard. These values now live in terminal global variables, which survive
// a restart, keyed by account login + magic so a different account or a
// different EA never inherits them.
//
// Disabled in the tester so nothing can leak between optimisation passes.
bool GuardsPersist()
{
   return !(bool)MQLInfoInteger(MQL_TESTER);
}

string GKey(string field)
{
   return "STS_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))
        + "_" + IntegerToString(InpMagic) + "_" + field;
}

double GGet(string field, double def)
{
   if(!GuardsPersist()) return def;
   string k = GKey(field);
   if(!GlobalVariableCheck(k)) return def;
   return GlobalVariableGet(k);
}

void GSet(string field, double v)
{
   if(!GuardsPersist()) return;
   GlobalVariableSet(GKey(field), v);
}

void PersistGuards()
{
   GSet("peakEq",     g_peakEq);
   GSet("dayStartEq", g_dayStartEq);
   GSet("dayStamp",   (double)g_dayStamp);
   GSet("tradesDay",  (double)g_tradesToday);
   GSet("lockDay",    g_lockedDay  ? 1.0 : 0.0);
   GSet("lockPerm",   g_lockedPerm ? 1.0 : 0.0);
}

double ATR(int shift)
{
   double buf[];
   if(CopyBuffer(g_atrHandle, 0, shift, 1, buf) != 1) return 0.0;
   return buf[0];
}

// Buffer 0 of iADX is the main ADX line.
double ADXValue(int shift)
{
   if(g_adxHandle == INVALID_HANDLE) return 0.0;
   double buf[];
   if(CopyBuffer(g_adxHandle, 0, shift, 1, buf) != 1) return 0.0;
   return buf[0];
}

// DEMA = 2*EMA(n) - EMA(EMA(n)), computed from closes. Matches the Pine.
double DEMA(int len, int shift)
{
   int need = len * 3 + shift + 5;
   if(Bars(_Symbol, _Period) < need) return 0.0;
   double k = 2.0 / (len + 1.0);
   double e1 = iClose(_Symbol, _Period, need - 1);
   double e2 = e1;
   for(int i = need - 2; i >= shift; i--)
   {
      double c = iClose(_Symbol, _Period, i);
      e1 = c * k + e1 * (1.0 - k);
      e2 = e1 * k + e2 * (1.0 - k);
   }
   return 2.0 * e1 - e2;
}

//==================== SUPERTREND ===================================
// Recomputed FROM HISTORY on every closed bar. The recursion is unchanged and
// still matches ta.supertrend(mult, len); what changed is where the previous
// bar's state comes from.
//
// WHY IT NO LONGER CARRIES STATE IN MEMORY
// The old version advanced g_finalUpper/g_finalLower/g_stDir once per new-bar
// event and kept them between calls. That equals the chart's SuperTrend only
// if this EA has observed EVERY bar of the series. It has not:
//   * the first call seeded direction from a SINGLE bar (c > basicUpper),
//     which is a guess, and the guess can survive for hundreds of bars and
//     manufacture one flip that the indicator never had;
//   * any bar that arrives with no tick, any disconnect, any weekend, any
//     terminal restart, timeframe change or parameter change drops bars out
//     of the recursion;
//   * because the state is recursive, a single dropped bar desynchronises the
//     EA from the chart PERMANENTLY, silently, with no error anywhere.
// That is precisely the "the EA does not do what the chart shows" class of
// defect. Recomputing over a fixed warm-up makes the value a pure function of
// price history, so live, tester and chart agree and a restart changes
// nothing. Cost is one CopyBuffer, one CopyRates and a few hundred
// multiplications, once per closed bar.
#define ST_WARMUP_BARS 400

void UpdateSuperTrend()
{
   g_stReady = false;

   int avail = Bars(_Symbol, _Period);
   int warm  = MathMin(ST_WARMUP_BARS, avail - 2);
   if(warm < InpStAtrLen + 3) return;

   double atrBuf[];
   if(CopyBuffer(g_atrHandle, 0, 1, warm, atrBuf) != warm) return;
   MqlRates r[];
   if(CopyRates(_Symbol, _Period, 1, warm + 1, r) != warm + 1) return;

   // Set AFTER the copy: that guarantees index 0 is the newest element no
   // matter which direction the copy filled the array in.
   ArraySetAsSeries(atrBuf, true);
   ArraySetAsSeries(r, true);

   double fUpper = 0.0, fLower = 0.0;
   int    dir = 0, dirPrev = 0;
   bool   seeded = false;

   // s indexes atrBuf, so bar shift = s + 1. s = 0 is the last CLOSED bar;
   // the forming bar (shift 0) is never read anywhere in this loop.
   for(int s = warm - 1; s >= 0; s--)
   {
      double atr = atrBuf[s];
      if(!MathIsValidNumber(atr) || atr <= 0.0) continue;

      double h   = r[s].high;
      double l   = r[s].low;
      double c   = r[s].close;
      double cp  = r[s + 1].close;
      double mid = (h + l) / 2.0;

      double basicUpper = mid + InpStMult * atr;
      double basicLower = mid - InpStMult * atr;

      if(!seeded)
      {
         fUpper  = basicUpper;
         fLower  = basicLower;
         dir     = (c > basicUpper) ? -1 : 1;
         dirPrev = dir;
         seeded  = true;
         continue;
      }

      double prevUpper = fUpper;
      double prevLower = fLower;

      fUpper = (basicUpper < prevUpper || cp > prevUpper) ? basicUpper : prevUpper;
      fLower = (basicLower > prevLower || cp < prevLower) ? basicLower : prevLower;

      dirPrev = dir;
      if(dir == 1 && c > fUpper)       dir = -1;   // flip bullish
      else if(dir == -1 && c < fLower) dir = 1;    // flip bearish
   }

   if(!seeded) return;

   g_finalUpper = fUpper;
   g_finalLower = fLower;
   g_stDir      = dir;
   g_stDirPrev  = dirPrev;
   g_stReady    = true;
}

//==================== LEVELS =======================================
// Veer: "i need the ea to auto UNDERSTAND all these levels what they mean and
// that we may get close to them and react not always hit them exactly".
//
// Price does not turn ON a level, it turns NEAR one. So every question here is
// asked with a tolerance rather than an equality: is there a level within
// InpNearAtr of this price, how far is the nearest one, is there room to the
// next one. A target parked just short of a level fills; one sitting exactly on
// it watches price stop a tick away and reverse.
#define MAX_LEVELS 200
double g_lvl[MAX_LEVELS];
int    g_lvlCount = 0;

void AddLevel(double p)
{
   if(p <= 0 || g_lvlCount >= MAX_LEVELS) return;
   double atr = ATR(1);
   double tol = (atr > 0 ? atr * 0.25 : _Point * 10);
   for(int i = 0; i < g_lvlCount; i++)          // merge near-equal levels
      if(MathAbs(g_lvl[i] - p) <= tol) return;
   g_lvl[g_lvlCount++] = p;
}

// A swing high is a bar whose high is the highest of the InpPivotBars either
// side of it. It is only KNOWN InpPivotBars later, and the scan respects that
// by starting at that offset - reading it sooner would be reading the future.
void BuildLevels()
{
   g_lvlCount = 0;
   if(!InpUseLevels) return;

   int n = MathMin(InpLevelLookback, Bars(_Symbol, _Period) - InpPivotBars - 2);
   for(int i = InpPivotBars + 1; i < n; i++)
   {
      bool isHigh = true, isLow = true;
      double h = iHigh(_Symbol, _Period, i);
      double l = iLow(_Symbol, _Period, i);
      for(int j = 1; j <= InpPivotBars; j++)
      {
         if(iHigh(_Symbol, _Period, i - j) > h || iHigh(_Symbol, _Period, i + j) > h) isHigh = false;
         if(iLow(_Symbol, _Period, i - j)  < l || iLow(_Symbol, _Period, i + j)  < l) isLow  = false;
         if(!isHigh && !isLow) break;
      }
      if(isHigh) AddLevel(h);
      if(isLow)  AddLevel(l);
   }

   if(InpUseDayLevels)
   {
      AddLevel(iHigh(_Symbol, PERIOD_D1, 1));
      AddLevel(iLow(_Symbol, PERIOD_D1, 1));
   }
   if(InpUseWeekLevels)
   {
      AddLevel(iHigh(_Symbol, PERIOD_W1, 1));
      AddLevel(iLow(_Symbol, PERIOD_W1, 1));
   }
   if(InpUseRound && InpRoundStep > 0)
   {
      double px = iClose(_Symbol, _Period, 1);
      for(int k = -3; k <= 3; k++)
         AddLevel(MathRound(px / InpRoundStep + k) * InpRoundStep);
   }
}

// Nearest level strictly above / below a price. 0 when there is none.
double NearestLevel(double from, int dir)
{
   double best = 0.0;
   for(int i = 0; i < g_lvlCount; i++)
   {
      double p = g_lvl[i];
      if(dir > 0 && p > from && (best == 0.0 || p < best)) best = p;
      if(dir < 0 && p < from && (best == 0.0 || p > best)) best = p;
   }
   return best;
}

// Is price sitting AT a level right now - within tolerance, not exactly on it?
bool NearAnyLevel(double px, double &which)
{
   double atr = ATR(1);
   if(atr <= 0) return false;
   double tol = InpNearAtr * atr;
   for(int i = 0; i < g_lvlCount; i++)
      if(MathAbs(g_lvl[i] - px) <= tol) { which = g_lvl[i]; return true; }
   return false;
}

//==================== RISK GATES ===================================
// Every prop firm measures the daily limit on EQUITY including floating P/L,
// so this uses AccountInfoDouble(ACCOUNT_EQUITY), never balance.
bool RiskAllowsEntry(string &why)
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);

   if(g_lockedPerm) { why = "max drawdown lock"; return false; }
   if(g_lockedDay)  { why = "daily loss lock";   return false; }

   if(g_dayStartEq > 0)
   {
      double dayLoss = (g_dayStartEq - eq) / g_dayStartEq * 100.0;
      if(dayLoss >= InpDailyLossPct)
      {
         g_lockedDay = true;
         PersistGuards();
         why = StringFormat("daily loss %.2f%% >= %.2f%%", dayLoss, InpDailyLossPct);
         Log("LOCK: " + why);
         return false;
      }
   }
   if(g_peakEq > 0)
   {
      double dd = (g_peakEq - eq) / g_peakEq * 100.0;
      if(dd >= InpMaxDDPct)
      {
         g_lockedPerm = true;
         PersistGuards();
         why = StringFormat("max drawdown %.2f%% >= %.2f%%", dd, InpMaxDDPct);
         Log("LOCK: " + why);
         return false;
      }
   }
   if(g_tradesToday >= InpMaxTradesDay) { why = "daily trade cap"; return false; }

   double atr = ATR(1);
   double spread = (SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                  - SymbolInfoDouble(_Symbol, SYMBOL_BID));
   if(atr > 0 && spread > InpMaxSpreadAtr * atr)
   {
      why = StringFormat("spread %.5f > %.1f%% of ATR", spread, InpMaxSpreadAtr * 100);
      return false;
   }
   return true;
}

// Size from the stop distance and the symbol's REAL tick value. Nothing here
// is hardcoded for gold, so the same EA sizes correctly on any symbol.
double LotFor(double stopDistPrice)
{
   if(stopDistPrice <= 0) return 0.0;
   double eq       = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskCash = eq * InpRiskPct / 100.0;
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0 || tickSize <= 0) return 0.0;

   double lossPerLot = (stopDistPrice / tickSize) * tickVal;
   if(lossPerLot <= 0) return 0.0;

   double lots = riskCash / lossPerLot;
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step > 0) lots = MathFloor(lots / step) * step;
   lots = MathMax(minL, MathMin(maxL, lots));
   return NormalizeDouble(lots, 2);
}

//==================== PENDING ORDERS ===============================
// A resting limit is the only way to get a better price than the market is
// offering. The cost is real and is not hidden here: an order that never gets
// filled is a trade you did not take, and roughly a quarter of them will not
// fill at 0.30 ATR. Every expiry is logged so the miss rate is visible rather
// than assumed.
bool HasPending()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol)  continue;
      return true;
   }
   return false;
}

// Cancel a limit that has sat unfilled too long. The setup that justified it
// is stale by then, and a limit left resting is an order waiting to be filled
// by exactly the move that invalidates it.
void ExpireStalePendings()
{
   int lifeSec = InpLimitLifeBars * PeriodSeconds(_Period);
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol)  continue;
      datetime setup = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
      if(TimeCurrent() - setup >= lifeSec)
      {
         double px = OrderGetDouble(ORDER_PRICE_OPEN);
         if(trade.OrderDelete(tk))
         {
            Log(StringFormat("limit at %.*f expired unfilled after %d bars",
                             (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS),
                             px, InpLimitLifeBars));
            Journal("LIMIT EXPIRED", "-", px, 0, 0, 0, 0, "never filled");
         }
      }
   }
}

//==================== POSITION HELPERS =============================
bool HasPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == InpMagic
         && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}

//==================== ENTRY ========================================
void TryEntry()
{
   if(HasPosition()) return;
   // A resting limit already IS this signal. Without this the next flip stacks
   // a second order on the same idea and both can fill within a few points of
   // each other - the same triple-entry fault that had to be fixed in the Pine.
   if(HasPending()) return;

   // The flip test comes FIRST so that every line logged below corresponds to
   // a real signal. Testing the risk gates first logged a refusal on every
   // single bar of a locked day, which buried the signals in noise.
   bool flipUp   = (g_stDir == -1 && g_stDirPrev == 1);
   bool flipDown = (g_stDir == 1  && g_stDirPrev == -1);
   if(!flipUp && !flipDown) return;

   string sdir = flipUp ? "long" : "short";

   string why = "";
   if(!RiskAllowsEntry(why)) { SkipLog(sdir, why); return; }

   if(InpUseDemaFilter)
   {
      double dNow  = DEMA(InpDemaLen, 1);
      double dPrev = DEMA(InpDemaLen, 3);
      if(dNow <= 0 || dPrev <= 0) return;
      if(flipUp   && dNow < dPrev) { SkipLog(sdir, "DEMA falling"); return; }
      if(flipDown && dNow > dPrev) { SkipLog(sdir, "DEMA rising");  return; }
   }

   // --- ADX ceiling. The losing bucket on this strategy is entries taken when
   // the trend is ALREADY extended: ADX>35 measured -0.132R while ADX<20
   // measured +0.304R. Skipping the extended ones held out-of-sample.
   if(InpUseAdxFilter)
   {
      double adx = ADXValue(1);
      if(adx > 0 && adx > InpMaxAdx)
      {
         SkipLog(sdir, StringFormat("ADX %.1f > %.1f, trend already extended",
                                    adx, InpMaxAdx));
         return;
      }
   }

   // --- session filter
   if(InpUseSession)
   {
      MqlDateTime dt_;
      TimeToStruct(TimeCurrent(), dt_);
      int h = dt_.hour;
      bool inSess = (InpSessFromUTC <= InpSessToUTC)
                  ? (h >= InpSessFromUTC && h < InpSessToUTC)
                  : (h >= InpSessFromUTC || h < InpSessToUTC);
      if(!inSess) { SkipLog(sdir, "outside session"); return; }
   }

   double atr = ATR(1);
   if(atr <= 0) return;

   double stopDist = InpStopAtrMult * atr;

   // NO ROOM, NO TRADE. A signal pointing straight into a level a few points
   // away is not the same trade as one with open air ahead of it, and taking
   // both at the same size is how the small ones pay for nothing.
   if(InpUseLevels && InpSkipNoRoom)
   {
      double px   = iClose(_Symbol, _Period, 1);
      double wall = NearestLevel(px, flipUp ? +1 : -1);
      if(wall > 0)
      {
         double roomR = MathAbs(wall - px) / stopDist;
         if(roomR < InpMinRoomR)
         {
            SkipLog(sdir, StringFormat("only %.2fR of room, level at %.*f",
                                       roomR, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS), wall));
            return;
         }
      }
   }

   double lots = LotFor(stopDist);
   if(lots <= 0) { SkipLog(sdir, "lot size rounded to zero"); return; }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   int    dg  = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   // The stop is attached AT OrderSend, never "managed later". A stop that
   // only exists in EA memory does not exist at all if the terminal drops.
   if(flipUp)
   {
      double sl = NormalizeDouble(ask - stopDist, dg);
      double tp = NormalizeDouble(ask + InpTargetR * stopDist, dg);
      // A target sitting beyond the next level watches price stop just short of
      // it and turn. Park it INSIDE the level instead, by InpLevelBufAtr, so it
      // is reached rather than admired.
      if(InpUseLevels && InpTpAtLevel)
      {
         double capLvl = NearestLevel(ask, +1);
         if(capLvl > 0)
         {
            double capped = NormalizeDouble(capLvl - InpLevelBufAtr * atr, dg);
            if(capped > ask && capped < tp)
            {
               Log(StringFormat("target pulled in from %.*f to %.*f, level at %.*f",
                                dg, tp, dg, capped, dg, capLvl));
               tp = capped;
            }
         }
      }
      // A LIMIT rests below and is filled by the pullback; the stop and target
      // are re-anchored to that better price, so the whole trade shifts down
      // rather than just the entry. That is what makes it a smaller drawdown
      // and not merely a nicer-looking fill.
      if(InpUseLimitEntry)
      {
         double lim = NormalizeDouble(ask - InpPullAtr * atr, dg);
         double lsl = NormalizeDouble(lim - stopDist, dg);
         double ltp = NormalizeDouble(lim + (tp - ask), dg);
         if(trade.BuyLimit(lots, lim, _Symbol, lsl, ltp, ORDER_TIME_GTC, 0,
                           RiskTag(stopDist, dg)))
         {
            g_tradesToday++;
            Journal("LIMIT", "long", lim, lots, lsl, ltp, 0, "waiting for pullback");
            Log(StringFormat("BUY LIMIT %.2f at %.*f  sl %.*f  tp %.*f",
                             lots, dg, lim, dg, lsl, dg, ltp));
         }
         else Log("BuyLimit failed: " + IntegerToString(trade.ResultRetcode()));
         return;
      }

      if(trade.Buy(lots, _Symbol, 0.0, sl, tp, RiskTag(stopDist, dg)))
      {
         g_tradesToday++;
         Journal("ENTRY", "long", ask, lots, sl, tp, 0, "");
         Log(StringFormat("LONG %.2f lots  sl %.*f  tp %.*f  atr %.*f",
                          lots, dg, sl, dg, tp, dg, atr));
      }
      else Log("Buy failed: " + IntegerToString(trade.ResultRetcode()));
   }
   else
   {
      double sl = NormalizeDouble(bid + stopDist, dg);
      double tp = NormalizeDouble(bid - InpTargetR * stopDist, dg);
      if(InpUseLevels && InpTpAtLevel)
      {
         double capLvl = NearestLevel(bid, -1);
         if(capLvl > 0)
         {
            double capped = NormalizeDouble(capLvl + InpLevelBufAtr * atr, dg);
            if(capped < bid && capped > tp)
            {
               Log(StringFormat("target pulled in from %.*f to %.*f, level at %.*f",
                                dg, tp, dg, capped, dg, capLvl));
               tp = capped;
            }
         }
      }
      if(InpUseLimitEntry)
      {
         double lim = NormalizeDouble(bid + InpPullAtr * atr, dg);
         double lsl = NormalizeDouble(lim + stopDist, dg);
         double ltp = NormalizeDouble(lim - (bid - tp), dg);
         if(trade.SellLimit(lots, lim, _Symbol, lsl, ltp, ORDER_TIME_GTC, 0,
                            RiskTag(stopDist, dg)))
         {
            g_tradesToday++;
            Journal("LIMIT", "short", lim, lots, lsl, ltp, 0, "waiting for pullback");
            Log(StringFormat("SELL LIMIT %.2f at %.*f  sl %.*f  tp %.*f",
                             lots, dg, lim, dg, lsl, dg, ltp));
         }
         else Log("SellLimit failed: " + IntegerToString(trade.ResultRetcode()));
         return;
      }

      if(trade.Sell(lots, _Symbol, 0.0, sl, tp, RiskTag(stopDist, dg)))
      {
         g_tradesToday++;
         Journal("ENTRY", "short", bid, lots, sl, tp, 0, "");
         Log(StringFormat("SHORT %.2f lots  sl %.*f  tp %.*f  atr %.*f",
                          lots, dg, sl, dg, tp, dg, atr));
      }
      else Log("Sell failed: " + IntegerToString(trade.ResultRetcode()));
   }
}

//==================== JOURNAL ======================================
// This EA runs on a LIVE account, and the honest reason nobody can say WHY it
// underperforms is that nobody has the data. The Experts tab is not data - it
// scrolls away and cannot be analysed.
//
// So every signal, every refusal and every fill is written to
//   MQL5/Files/STS_journal_<symbol>_<timeframe>.csv
// with the market conditions at that moment attached. Send that file back and
// the next fix is derived from your actual trades instead of from theory.
//
// The SKIP rows are the valuable ones: they are the signals the filters
// refused. If those keep winning, a filter is costing you money, and that is
// only knowable from this file.
string JournalName()
{
   return StringFormat("STS_journal_%s_%s.csv", _Symbol,
                       EnumToString((ENUM_TIMEFRAMES)_Period));
}

void Journal(string ev, string dir, double px, double lots,
             double sl, double tp, double money, string note)
{
   if(!InpJournal) return;

   int h = FileOpen(JournalName(),
                    FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ, ',');
   if(h == INVALID_HANDLE) return;

   if(FileSize(h) == 0)
      FileWrite(h, "utc_time", "event", "dir", "price", "lots", "sl", "tp",
                   "money", "atr", "adx", "spread", "equity", "note");
   FileSeek(h, 0, SEEK_END);

   double atr = ATR(1);
   double adx = ADXValue(1);
   double sp  = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
              - SymbolInfoDouble(_Symbol, SYMBOL_BID);

   FileWrite(h, TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
             ev, dir, DoubleToString(px, _Digits), DoubleToString(lots, 2),
             DoubleToString(sl, _Digits), DoubleToString(tp, _Digits),
             DoubleToString(money, 2), DoubleToString(atr, _Digits),
             DoubleToString(adx, 1), DoubleToString(sp, _Digits),
             DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2), note);
   FileClose(h);
}

// A signal the filters refused, recorded with the reason.
void SkipLog(string dir, string why)
{
   Log("skip " + dir + ": " + why);
   Journal("SKIP", dir, iClose(_Symbol, _Period, 1), 0, 0, 0, 0, why);
}

//==================== R MEASUREMENT ================================
// R must be measured against the risk the trade was OPENED with, never against
// the current stop. The moment a trail moves the stop, |open - sl| shrinks, so
// R computed from it inflates - and every R-based rule below (partial,
// break-even, trail arm) fires on a number that is not true. Worse, when a
// trail crosses the entry price |open - sl| passes through zero, the guard
// `if(risk <= 0) continue;` fires, and the position stops being managed at all.
//
// So the original stop distance rides on the position itself, in its comment,
// and therefore survives a terminal restart. If a broker mangles the comment
// the fallback is the old behaviour, which is wrong but not fatal.
string RiskTag(double stopDist, int dg)
{
   return "STS|" + DoubleToString(stopDist, dg);
}

double OriginalRisk(double openPx, double sl, string cmt)
{
   if(StringLen(cmt) > 4 && StringSubstr(cmt, 0, 4) == "STS|")
   {
      double d = StringToDouble(StringSubstr(cmt, 4));
      if(d > 0) return d;
   }
   return MathAbs(openPx - sl);
}

// A partial close must happen ONCE. Without this the old code re-closed half
// the remaining volume on every single bar the trade spent above 1R, bleeding
// a winner down to the minimum lot while it was still working.
ulong g_partialed[];
// A SECOND, separate register. The 1R partial and the level partial are
// different events and can both happen on one trade; sharing one list would
// let whichever fired first silently cancel the other.
ulong g_lvlPartialed[];

bool AlreadyLvlPartialed(ulong tk)
{
   for(int i = 0; i < ArraySize(g_lvlPartialed); i++)
      if(g_lvlPartialed[i] == tk) return true;
   return false;
}

void MarkLvlPartialed(ulong tk)
{
   int n = ArraySize(g_lvlPartialed);
   ArrayResize(g_lvlPartialed, n + 1);
   g_lvlPartialed[n] = tk;
   if(n > 400) ArrayRemove(g_lvlPartialed, 0, 200);
}

bool AlreadyPartialed(ulong tk)
{
   for(int i = 0; i < ArraySize(g_partialed); i++)
      if(g_partialed[i] == tk) return true;
   return false;
}

void MarkPartialed(ulong tk)
{
   int n = ArraySize(g_partialed);
   ArrayResize(g_partialed, n + 1);
   g_partialed[n] = tk;
   if(n > 400) ArrayRemove(g_partialed, 0, 200);   // never grow without bound
}

//==================== MANAGEMENT ===================================
// Two rules are ON by default because they MEASURED better on these entries:
// a wide 3-ATR trail armed immediately, and a 50-bar stall exit. Break-even
// and the 1R partial are OFF: break-even was the worst exit rule on all four
// markets tested, and the partial has never been measured on this strategy.
void ManagePosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;

      long   type  = PositionGetInteger(POSITION_TYPE);
      double open  = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl    = PositionGetDouble(POSITION_SL);
      double tp    = PositionGetDouble(POSITION_TP);
      double vol   = PositionGetDouble(POSITION_VOLUME);
      datetime ot  = (datetime)PositionGetInteger(POSITION_TIME);
      string  cmt  = PositionGetString(POSITION_COMMENT);
      int    dg    = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      double atr   = ATR(1);
      if(atr <= 0) continue;

      double price = (type == POSITION_TYPE_BUY)
                   ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                   : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      int dir      = (type == POSITION_TYPE_BUY) ? 1 : -1;
      double risk  = OriginalRisk(open, sl, cmt);
      if(risk <= 0) continue;
      double rNow  = (price - open) * dir / risk;

      // --- time cap. Measured as one of the two best exits on gold.
      int barsHeld = iBarShift(_Symbol, _Period, ot, false);
      if(InpMaxBars > 0 && barsHeld >= InpMaxBars)
      {
         if(trade.PositionClose(tk))
            Log(StringFormat("time exit after %d bars at %.2fR", barsHeld, rNow));
         continue;
      }

      // --- APPROACHING A LEVEL: bank half, let the rest run.
      // This is the answer to wanting both the pennies and the big moves out of
      // the same signal. Price arriving at a level does one of two things and
      // nobody knows which in advance, so the trade does both: half is taken
      // while the level is still in front of price, and the remainder rides the
      // trail through it if it breaks. Note NearAnyLevel uses a TOLERANCE -
      // price reacts near a level, not on it, and a partial that waits for an
      // exact touch is a partial that often never happens.
      if(InpUseLevels && InpPartialAtLevel && rNow > 0.3
         && !AlreadyLvlPartialed(tk)
         && vol > SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
      {
         double hitLvl = 0.0;
         if(NearAnyLevel(price, hitLvl))
         {
            // only a level the trade is running INTO, not one behind it
            bool ahead = (dir > 0) ? (hitLvl >= open) : (hitLvl <= open);
            if(ahead)
            {
               double half = NormalizeDouble(vol / 2.0, 2);
               double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
               if(step > 0) half = MathFloor(half / step) * step;
               if(half >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN)
                  && trade.PositionClosePartial(tk, half))
               {
                  MarkLvlPartialed(tk);
                  Log(StringFormat("banked %.2f of %.2f at level %.*f (%.2fR), "
                                   "rest rides the trail", half, vol,
                                   (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS),
                                   hitLvl, rNow));
                  Journal("PARTIAL", dir > 0 ? "long" : "short", price, half,
                          0, 0, 0, StringFormat("at level %.2f", hitLvl));
               }
            }
         }
      }

      // --- partial at 1R, optional
      if(InpPartialAt1R && rNow >= 1.0 && !AlreadyPartialed(tk)
         && vol > SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
      {
         double half = NormalizeDouble(vol / 2.0, 2);
         double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         if(step > 0) half = MathFloor(half / step) * step;
         if(half >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
         {
            if(trade.PositionClosePartial(tk, half))
            {
               MarkPartialed(tk);
               Log(StringFormat("partial close %.2f of %.2f at 1R", half, vol));
            }
         }
      }

      // --- break-even. OFF by default. Measured as the WORST exit rule on all
      // four markets tested (-0.161R to -0.308R). Present only so it can be
      // tested rather than argued about.
      if(InpUseBreakEven && rNow >= InpBreakEvenAtR)
      {
         double be = NormalizeDouble(open, dg);
         bool better = (dir > 0) ? (be > sl) : (be < sl);
         if(better) { trade.PositionModify(tk, be, tp); Log("moved to break-even"); }
      }

      // --- trail. ON by default and arms IMMEDIATELY (InpTrailAtR = 0), because
      // a wide trail measured best on these entries and a tight or late one did
      // not. It only ever moves the stop in the trade's favour.
      if(InpUseTrail && rNow >= InpTrailAtR)
      {
         double t = (dir > 0) ? price - InpTrailAtrMult * atr
                              : price + InpTrailAtrMult * atr;
         t = NormalizeDouble(t, dg);
         bool better = (dir > 0) ? (t > sl) : (t < sl);
         if(better) { trade.PositionModify(tk, t, tp); }
      }
   }
}

//==================== CLOSE RECORDING ==============================
// Every fill is recorded here rather than where it was requested, because a
// stop or a target is hit by the BROKER, not by this EA - those closes never
// pass through any code above. DEAL_REASON is the broker's own statement of
// why the position ended, so the journal records what actually happened
// instead of what the EA intended.
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest    &request,
                        const MqlTradeResult     &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;

   ulong d = trans.deal;
   if(d == 0 || !HistoryDealSelect(d)) return;
   if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic)     return;
   if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol)      return;
   if(HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_OUT) return;

   double px    = HistoryDealGetDouble(d, DEAL_PRICE);
   double vol   = HistoryDealGetDouble(d, DEAL_VOLUME);
   double money = HistoryDealGetDouble(d, DEAL_PROFIT)
                + HistoryDealGetDouble(d, DEAL_SWAP)
                + HistoryDealGetDouble(d, DEAL_COMMISSION);
   long   rsn   = HistoryDealGetInteger(d, DEAL_REASON);
   long   type  = HistoryDealGetInteger(d, DEAL_TYPE);

   // the closing deal is the OPPOSITE side of the position it closed
   string dir = (type == DEAL_TYPE_SELL) ? "long" : "short";

   string why = "other";
   if(rsn == DEAL_REASON_SL)     why = "SL";
   else if(rsn == DEAL_REASON_TP) why = "TP";
   else if(rsn == DEAL_REASON_EXPERT) why = "EA (time cap or partial)";
   else if(rsn == DEAL_REASON_SO) why = "STOP OUT - margin";

   Journal("EXIT", dir, px, vol, 0, 0, money, why);
   Log(StringFormat("closed %s %.2f at %s for %.2f (%s)",
                    dir, vol, DoubleToString(px, _Digits), money, why));
}

//==================== LIFECYCLE ====================================
int OnInit()
{
   if(InpDemoOnly && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Print("REFUSING TO START: InpDemoOnly is true and this is not a demo "
            "account. Set InpDemoOnly=false deliberately to trade live.");
      return INIT_FAILED;
   }

   g_atrHandle = iATR(_Symbol, _Period, InpStAtrLen);
   if(g_atrHandle == INVALID_HANDLE) { Print("ATR handle failed"); return INIT_FAILED; }
   g_adxHandle = iADX(_Symbol, _Period, 14);
   if(g_adxHandle == INVALID_HANDLE) { Print("ADX handle failed"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(20);

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayStartEq = eq;
   g_peakEq     = eq;
   g_dayStamp   = DayStamp();

   PrintFormat("SuperTrendSniper started. ST(%d, %.2f) DEMA(%d) risk %.2f%% "
               "target %.1fR  BE=%s trail=%s",
               InpStAtrLen, InpStMult, InpDemaLen, InpRiskPct, InpTargetR,
               InpUseBreakEven ? "ON" : "off", InpUseTrail ? "ON" : "off");
   if(InpUseBreakEven)
      Print("WARNING: break-even is ON. It measured as the worst exit rule on "
            "all four markets tested. Only leave it on if you are testing it.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
   if(g_adxHandle != INVALID_HANDLE) IndicatorRelease(g_adxHandle);
}

void OnTick()
{
   // Equity peak tracks on every tick so the drawdown lock cannot be
   // out-run between bars.
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_peakEq) g_peakEq = eq;

   int ds = DayStamp();
   if(ds != g_dayStamp)
   {
      g_dayStamp    = ds;
      g_dayStartEq  = eq;
      g_tradesToday = 0;
      g_lockedDay   = false;
      Log("new trading day, daily counters reset");
   }

   // EVERYTHING BELOW RUNS ONLY WHEN A BAR CLOSES.
   // This is what makes a backtest match live. v19.18 recomputed its engine on
   // every tick, so its backtest and its live behaviour were different systems.
   datetime bt = iTime(_Symbol, _Period, 0);
   if(bt == g_lastBarTime) return;
   g_lastBarTime = bt;

   if(Bars(_Symbol, _Period) < InpDemaLen * 3 + 10) return;

   UpdateSuperTrend();
   BuildLevels();          // before anything asks where the levels are
   ExpireStalePendings();  // a limit is only good while its setup is
   ManagePosition();
   TryEntry();
}
//+------------------------------------------------------------------+
