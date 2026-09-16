//+------------------------------------------------------------------+
//|                                                      SNIPER.mq5  |
//|            was XAUUSD_QUAD through v19.18 -- that name is retired |
//|                                                                  |
//|  M1 XAUUSD. Balance-adaptive, symbol-agnostic, funded or live.   |
//|                                                                  |
//|  ================= THE ONE FACT THIS IS BUILT ON =================|
//|  The system FINDS moves. It does not KEEP them.                  |
//|                                                                  |
//|  Reference day, 279 closed trades, -147.04 GBP:                  |
//|    best moment of every trade added up   +293.26 GBP             |
//|    handed back                           +440.30 GBP             |
//|    SL-HIT   109 trades  peak 173.4 pts -> net  -54.7 pts         |
//|    BASKET-LOCK 15 trades peak  26.0 pts -> net  +25.4 pts  (98%) |
//|  Near-identical average peak per trade (1.62 vs 1.64 GBP). One   |
//|  kept 98%, the other kept nothing. The ONLY difference was which |
//|  mechanism owned the exit. So every exit here locks like         |
//|  BASKET-LOCK.                                                    |
//|                                                                  |
//|  ================= MECHANISM #1: THE 60-SECOND CUT ===============|
//|  Finding 2, own-exit prices excluded so outcome cannot leak in:  |
//|    went 0.60+ adverse in first 60s : 48 trades, -86.49, hit  6.2%|
//|    did NOT                         : 23 trades, +49.92, hit 82.6%|
//|  Cutting the adverse cohort at -0.60 costs 0.60 + 0.30 spread    |
//|  = GBP 0.66 each, turning -86.49 into -31.67. The 71-trade block |
//|  goes -36.57 -> +18.25.                                          |
//|                                                                  |
//|  Checked against a bigger independent slice (Finding 4): 153     |
//|  losers never got even 0.30 up and lost 252.27 between them,     |
//|  average 1.65 each. Cutting at 0.66 saves 0.99 each = GBP 151    |
//|  on a day that lost 147.04.                                      |
//|                                                                  |
//|  Two independent slices of the same day agree. This is the       |
//|  highest-value rule available and it is mechanism #1.            |
//|                                                                  |
//|  The 82.6% hit rate on the surviving cohort is not a projection. |
//|  It is what the tickets say.                                     |
//|                                                                  |
//|  ================= BUGS FROM THE AUDIT, FIXED ====================|
//|  B1  The grace window was INVERTED: T_MinHoldSecs=180 against a  |
//|      240s average hold stood down every discretionary exit for   |
//|      75% of a trade's life. 21 of 32 exit mechanisms fired ZERO  |
//|      times in 279 trades. Here the grace window is 0 by default  |
//|      and is HARD-CAPPED below the fast-fail window, so the cut   |
//|      can always act. A grace window that outlives the exit it    |
//|      gates is the bug, not the setting.                          |
//|  B2  Session weighting ran nowhere -- stranded behind an early   |
//|      return in the sizing function. Here SizeFor() applies every |
//|      multiplier and RETURNS ONCE, at the bottom.                 |
//|  B3  DuplicateFill() read deal history, which is empty when two  |
//|      clocks fire in one OnTick, so one signal became 2-3         |
//|      positions at one price sharing a stop and paying three      |
//|      spreads. Here the guard is IN MEMORY at send time, and the  |
//|      first leg carries the full size.                            |
//|  B4  Orphaned inputs. Every input in this file is read; run      |
//|      tools/mql5_check.py to prove it.                            |
//|  B6  One definition of a thin session, not two.                  |
//|                                                                  |
//|  ================= WRONG ATR COST A WHOLE SESSION ===============|
//|  M1 ATR is 1.47 (1487 pts travel / 1012 M1 bars), NOT 0.35.      |
//|  A prior session calibrated on 0.35 and broke three mechanisms.  |
//|  Nothing here is denominated in gold dollars -- every threshold  |
//|  is ATR, spread or tick value, so it also runs on EURUSD.        |
//+------------------------------------------------------------------+
#property copyright "SNIPER"
#property link      "https://github.com/veer7710/signals"
#property version   "20.00"
#property strict

#include <Trade\Trade.mqh>
CTrade Trade;

#define SNIPER_BUILD "SNIPER v20.00"

//====================================================================
input group "=== MECHANISM 1: FAST-FAIL (the 60-second cut) ==="
input bool   InpFastFail      = true;   // Finding 2. Worth ~GBP 151 on the reference day.
input int    InpFastFailSecs  = 60;     // window measured from fill
input double InpFastFailATR   = 0.41;   // 0.60 pts / 1.47 ATR = 0.41. Symbol-agnostic.
input int    InpGraceSecs     = 0;      // B1: hard-capped below InpFastFailSecs below

input group "=== FAST-FAIL SAFETY: measure before it acts ==="
input bool   InpFFShadow      = true;   // TRUE = log what it WOULD cut, do not cut.
                                        // Your live example went -GBP5, then +5, then +3.
                                        // Finding 2 says cutting is right ON AVERAGE, but
                                        // that trade is a possible counterexample and it is
                                        // YOUR account. Run a session in shadow, read the
                                        // CSV column ff_shadow, then set this false.

input group "=== MECHANISM 2: PEAK LOCK (the BASKET-LOCK model) ==="
input bool   InpPeakLock      = true;
input double InpLockArmATR    = 0.50;   // arm once peak reaches this many ATR
input bool   InpBandArm       = true;   // ...or derive it from the noise band, like QUAD's
input double InpNoiseFloorATR = 0.60;   // BASKET-LOCK does. band = spread + this x ATR;
input double InpArmBands      = 2.0;    // arm at ArmBands x band, give back 1 band. Two bands
                                        // is arithmetic, not taste: to guarantee one band of
                                        // profit after handing one back, the peak must first
                                        // reach two. QUAD's own note has this right -- what
                                        // broke it there was a GBP5 cash floor overriding it.
input double InpLockKeepMin   = 0.65;   // was 0.50. "up GBP4, closes at GBP2" is a 50% giveback.
input double InpLockKeepMax   = 0.90;   // Policy test on his own peak distribution: keep-85%
input double InpLockScaleATR  = 2.00;   // netted -90.8 per 275 vs -188.1 for keep-50%, and a
                                        // hard bank at GBP5 netted -371.7. Harder lock wins on
                                        // BOTH his complaint and the arithmetic. Reaching the
                                        // max at 2 ATR (not 3) means a GBP4 peak at 0.02 lots
                                        // = 1.86 ATR now keeps ~88%: GBP3.51, not GBP2.
input double InpBEAtR         = 1.00;   // once peak reaches this R, the stop NEVER goes below
input double InpBELockR       = 0.05;   // entry + this. SL-HIT held 173.4 pts of peak and
                                        // closed -54.7: winners turning into losers.
input double InpTrailATR      = 2.00;   // runner trail once locked

input group "=== HOLD TIME (Finding 6: moves last 42 min, holds were 4) ==="
input int    InpMaxHoldMins   = 60;     // was effectively 4 minutes
input int    InpRunnerMins    = 90;     // a trade past the lock may live this long

input group "=== SIZING: drift alignment (Finding 3) ==="
input bool   InpDriftSize     = true;   // never REFUSE a signal -- only size it
input int    InpDriftMins     = 30;     // prior-drift window
input double InpWithDriftMult = 1.00;   // 137 trades, -0.15/trade
input double InpAgainstMult   = 0.35;   // 97 trades, -1.13/trade. Size down, do not block.

input group "=== REGIME (reference day: efficiency 0.038, traded as trend) ==="
input bool   InpRegimeGate    = true;
input int    InpRegimeBars    = 30;
input double InpRangeER       = 0.15;   // below this = range: rotate, do not chase
input double InpTrendER       = 0.30;   // above this = trend
input double InpRangeMult     = 0.60;   // size in a range

input group "=== LIQUIDITY: absorption vs expansion (Part 5D) ==="
input bool   InpLiquidity     = true;
input int    InpLevelLookback = 240;
input int    InpSwingN        = 3;
input double InpEqualTolATR   = 0.15;   // equal highs cluster tolerance
input double InpPierceATR     = 0.05;
input double InpExpandCloseATR= 0.35;   // close beyond by this = EXPANSION, never fade

input group "=== ROOM TO LIQUIDITY (the equal-high fault, on camera) ==="
input bool   InpRoomGate      = true;   // do not buy INTO a shelf of resting sell orders
input double InpMinRoomATR    = 1.20;   // need at least this much clear air to the next
                                        // untested equal level, or the trade has nowhere to go
input double InpEqualShelfATR = 0.20;   // levels within this of each other ARE a shelf

input group "=== DISPLACEMENT (the 18:53 bar: 4.42 pts = 3.0 ATR in one minute) ==="
input bool   InpTravelGate    = true;
input double InpMaxTravelATR  = 1.50;   // refuse to enter this far into a bar's own range --
                                        // buying 3 ATR up a vertical bar buys the last of it

input group "=== ANTI-WHIPSAW (20 signals in 72 min = 51% of the move in spread) ==="
input bool   InpFlipGate      = true;
input int    InpFlipCooldown  = 180;    // seconds before the OPPOSITE direction is allowed
input double InpFlipMinMoveATR= 0.80;   // unless price has moved this far since the last exit

input group "=== SPREAD (48% of the loss, and it is not constant) ==="
input bool   InpSpreadGate    = true;
input double InpMaxSpreadMult = 1.60;   // refuse while live spread is this x its own median
input int    InpSpreadWindow  = 200;    // ticks of median

input group "=== RE-ENTRY (paying twice for one wrong read) ==="
input bool   InpReentryGate   = true;
input int    InpReentryBars   = 10;     // after a LOSS, refuse the same direction for this long
input double InpReentryDistATR= 1.00;   // unless price has moved this far from the failed entry

input group "=== DEAD MARKET (reference day ER was 0.038) ==="
input double InpMinRangeATR   = 3.00;   // a range is only worth rotating if it is this wide
input double InpMinAtrPts     = 0.0;    // 0 = off; absolute floor if you want one

input group "=== PULLBACK BAND (the one cohort that tested POSITIVE) ==="
input bool   InpPullbackGate  = false;  // OFF by default -- it REFUSES signals, and your
                                        // standing rule is that the lever is size, not refusal.
input double InpPullMin       = 0.60;   // Part 5E: entries at 60-80% of the prior 30-min range
input double InpPullMax       = 0.80;   // in the trend direction were the only clearly
input int    InpPullMins      = 30;     // positive cohort in the book.

input group "=== NEWS ('volume was being put into market') ==="
input bool   InpNewsGate      = true;
input int    InpNewsBeforeMin = 5;      // stand down this long BEFORE a high-impact event
input int    InpNewsAfterMin  = 3;      // and this long after
input double InpVolSurgeMult  = 3.0;    // or when tick volume hits this x the 50-bar median

input group "=== RISK -- derived from the broker, nothing hardcoded ==="
input double InpRiskPct       = 0.35;   // % of balance per trade
input double InpMaxStopATR    = 3.00;
input double InpStopBufATR    = 0.30;
input int    InpMaxPositions  = 0;      // 0 = derive from margin headroom
input double InpMarginHeadroom= 0.50;   // never commit more than this share of free margin

input group "=== ACCOUNT RULES ==="
enum SniperRules { SR_LIVE, SR_PROP_8_4_6, SR_PROP_10_5_10, SR_CUSTOM };
input SniperRules InpRules    = SR_LIVE;
input double InpTargetPct     = 8.0;
input double InpDailyLossPct  = 4.0;
input double InpMaxDDPct      = 6.0;
input bool   InpTrailingDD    = true;
input bool   InpStopAtTarget  = true;

input group "=== INSTRUMENTATION (Part 5H) ==="
input bool   InpWriteCSV      = true;   // one row per trade, every gate recorded
input string InpCSVName       = "SNIPER_trades.csv";
input bool   InpJournal       = true;
input bool   InpShowPanel     = true;

input group "=== GENERAL ==="
input long   InpMagic         = 2000001;
input int    InpSlippage      = 30;

//====================================================================
//  state
//====================================================================
struct Live
{
   ulong    ticket;
   int      dir;
   double   entry, stopDist, peak, lockPx;
   datetime opened;
   bool     locked, fastFailed;
   double   worstFirstWindow;
   double   travelATR;
   string   regime, why;
   double   driftMult, regimeMult;
};
Live L[];                       // open positions this EA owns

int      hAtr = INVALID_HANDLE;
datetime lastBar = 0;
double   gAtr = 0.0;
// broker facts
double   bMinLot=0.01, bMaxLot=100.0, bLotStep=0.01, bTickVal=0, bTickSize=0;
double   bMoneyPerPt=0, bStopLvl=0, bMarginPerMinLot=0;
int      bDigits=2;
// guards
double   gStart=0, gDayStart=0, gPeak=0;
datetime gDayStamp=0;
bool     gHalted=false;
string   gHaltWhy="";
// duplicate guard (B3) -- in memory, at send time
datetime gLastSendBar=0;
int      gLastSendDir=0;
double   gLastSendPx=0;
// re-entry guard
datetime gLastLossTime=0;
int      gLastLossDir=0;
double   gLastLossPx=0;
int      gLastLossBar=0;
int      nSpreadBlock=0, nReentryBlock=0, nDeadBlock=0, nPullBlock=0;
// anti-whipsaw
datetime gLastExitTime=0;
int      gLastExitDir=0;
double   gLastExitPx=0;
// instrumentation
int      nShadowCut=0, nRoomBlock=0, nTravelBlock=0, nFlipBlock=0, nNewsBlock=0;
// levels
double   lvlHi[], lvlLo[];
bool     lvlHiDead[], lvlLoDead[];
// stats
int      nT=0, nWin=0, nFastFail=0, nLocked=0, nSkipWide=0, nSkipSize=0;
double   sumPts=0, sumPeakPts=0, sumKept=0;
int      nKept=0;
int      csvHandle=INVALID_HANDLE;




//--- forward declarations (auto-generated; see tools/add_fwd_decls.py)
bool ResolveBroker();
int MaxStack();
bool Viable();
int GraceSecs();
double AtrNow();
datetime Today();
string GuardFile();
void LoadGuards();
void SaveGuards();
void NewDay();
void RuleSet(double &target, double &daily, double &maxdd, bool &trailing);
bool GuardsBlock();
double EfficiencyRatio(int bars);
string Regime();
int Drift();
void RebuildLevels();
void PushLevel(double &arr[], bool &dead[], double v, double tol);
int Touches(double level, double tol);
double RunOrigin(int dir, int fromBar);
int LiquiditySignal(double &levelOut, string &whyOut);
int RangeSignal(string &whyOut);
double RoomToLevel(int dir);
bool IsShelf(int dir, double level);
bool RoomOK(int dir);
bool TravelOK(int dir);
bool FlipOK(int dir);
bool NewsClear();
double SpreadPts();
bool SpreadOK();
bool ReentryOK(int dir);
bool AliveOK();
bool PullbackOK(int dir);
void Enter(int dir, double px, string why);
double SizeFor(double stopDist, double mult);
void ManageAll();
void ManageOne(int i);
void SetStop(int i, double want, double cur, int dir);
void Settle(int i);
void Drop(int i);
void CloseAll(string why);
void OpenCSV();
void WriteCSV(int i, double pts);
string SessionNow();
void DrawPanel();
//--- end forward declarations

//====================================================================
int OnInit()
{
   hAtr = iATR(_Symbol, _Period, 14);
   if(hAtr == INVALID_HANDLE) { Print(SNIPER_BUILD, ": ATR handle failed"); return INIT_FAILED; }
   if(!ResolveBroker()) { Print(SNIPER_BUILD, ": symbol specs unavailable"); return INIT_FAILED; }

   Trade.SetExpertMagicNumber(InpMagic);
   Trade.SetDeviationInPoints(InpSlippage);
   Trade.SetTypeFillingBySymbol(_Symbol);
   ArrayResize(L, 0);
   ArrayResize(lvlHi, 0); ArrayResize(lvlLo, 0);
   ArrayResize(lvlHiDead, 0); ArrayResize(lvlLoDead, 0);
   LoadGuards();
   OpenCSV();
   EventSetTimer(1);            // 1s: the fast-fail needs sub-bar resolution

   if(!Viable())
   {
      PrintFormat("%s: balance %.2f %s cannot carry one %.2f lot at %.0f%% risk"
                  " -- refusing to trade rather than oversizing",
                  SNIPER_BUILD, AccountInfoDouble(ACCOUNT_BALANCE),
                  AccountInfoString(ACCOUNT_CURRENCY), bMinLot, InpRiskPct);
      return INIT_FAILED;
   }
   PrintFormat("%s init %s %s | minLot %.2f step %.2f | %.2f %s per point"
               " | margin/minlot %.2f | max stack %d | grace %ds (capped)",
               SNIPER_BUILD, _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
               bMinLot, bLotStep, bMoneyPerPt*bMinLot,
               AccountInfoString(ACCOUNT_CURRENCY), bMarginPerMinLot,
               MaxStack(), GraceSecs());
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   SaveGuards();
   if(csvHandle != INVALID_HANDLE) { FileClose(csvHandle); csvHandle = INVALID_HANDLE; }
   ObjectsDeleteAll(0, "SNIPER_");
   if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr);
}

//--- 1-second timer. The fast-fail is a SECONDS rule; a bar-close EA
//--- cannot enforce it, which is part of why it was never enforced.
void OnTimer()
{
   ManageAll();
   SaveGuards();
   if(InpShowPanel) DrawPanel();
}

//====================================================================
//  BROKER ADAPTATION -- Part 5B/5C. Nothing below is a gold constant.
//====================================================================
bool ResolveBroker()
{
   bMinLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   bMaxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   bLotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   bTickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   bTickSize= SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   bDigits  = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   bStopLvl = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL)
              * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(bLotStep <= 0) bLotStep = 0.01;
   if(bMinLot  <= 0) bMinLot  = 0.01;
   if(bTickSize <= 0) return false;
   bMoneyPerPt = bTickVal / bTickSize;      // account currency per 1.0 of price, per lot
   // margin is live and moves with price -- never hardcode it (brief: 0.01 = GBP 16)
   double m = 0.0;
   if(OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, bMinLot,
                      SymbolInfoDouble(_Symbol, SYMBOL_ASK), m))
      bMarginPerMinLot = m;
   else
      bMarginPerMinLot = 0.0;
   return (bMoneyPerPt > 0);
}

//--- Concurrency is a MARGIN question, decided before the fill, never by
//--- free margin at send time (Part 5B).
int MaxStack()
{
   if(InpMaxPositions > 0) return InpMaxPositions;
   if(bMarginPerMinLot <= 0) return 1;
   double usable = AccountInfoDouble(ACCOUNT_MARGIN_FREE) * InpMarginHeadroom;
   int n = (int)MathFloor(usable / bMarginPerMinLot);
   return MathMax(1, MathMin(n, 20));
}

bool Viable()
{
   if(bMarginPerMinLot > 0 &&
      AccountInfoDouble(ACCOUNT_MARGIN_FREE) < bMarginPerMinLot) return false;
   return true;
}

//--- B1: a grace window that outlives the exit it gates IS the bug.
int GraceSecs()
{
   int g = InpGraceSecs;
   if(InpFastFail && g >= InpFastFailSecs) g = InpFastFailSecs - 1;
   return MathMax(0, g);
}

double AtrNow()
{
   double a[]; ArraySetAsSeries(a, true);
   if(CopyBuffer(hAtr, 0, 1, 2, a) < 2) return 0.0;
   return a[0];
}

//====================================================================
//  GUARDS
//====================================================================
datetime Today()
{
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   t.hour = 0; t.min = 0; t.sec = 0;
   return StructToTime(t);
}

string GuardFile() { return "SNIPER_" + _Symbol + "_" + (string)InpMagic + ".guard"; }

void LoadGuards()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   gStart = eq; gPeak = eq; gDayStart = eq; gDayStamp = Today();
   int h = FileOpen(GuardFile(), FILE_READ|FILE_TXT|FILE_COMMON);
   if(h != INVALID_HANDLE)
   {
      gDayStamp = (datetime)StringToInteger(FileReadString(h));
      gStart    = StringToDouble(FileReadString(h));
      gDayStart = StringToDouble(FileReadString(h));
      gPeak     = StringToDouble(FileReadString(h));
      gHalted   = (StringToInteger(FileReadString(h)) == 1);
      gHaltWhy  = FileReadString(h);
      FileClose(h);
   }
   if(gDayStamp != Today()) NewDay();
   if(gStart <= 0) gStart = eq;
   if(gPeak  <= 0) gPeak  = eq;
}

void SaveGuards()
{
   int h = FileOpen(GuardFile(), FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   FileWrite(h, (string)(long)gDayStamp);
   FileWrite(h, DoubleToString(gStart, 2));
   FileWrite(h, DoubleToString(gDayStart, 2));
   FileWrite(h, DoubleToString(gPeak, 2));
   FileWrite(h, gHalted ? "1" : "0");
   FileWrite(h, gHaltWhy);
   FileClose(h);
}

void NewDay()
{
   gDayStamp = Today();
   gDayStart = AccountInfoDouble(ACCOUNT_EQUITY);
   if(gHaltWhy == "daily") { gHalted = false; gHaltWhy = ""; }
   SaveGuards();
}

void RuleSet(double &target, double &daily, double &maxdd, bool &trailing)
{
   switch(InpRules)
   {
      case SR_PROP_8_4_6:   target=8.0;  daily=4.0; maxdd=6.0;  trailing=true;  break;
      case SR_PROP_10_5_10: target=10.0; daily=5.0; maxdd=10.0; trailing=false; break;
      case SR_LIVE:         target=1e9;  daily=InpDailyLossPct; maxdd=25.0; trailing=true; break;
      default:              target=InpTargetPct; daily=InpDailyLossPct;
                            maxdd=InpMaxDDPct;   trailing=InpTrailingDD;        break;
   }
}

bool GuardsBlock()
{
   if(gDayStamp != Today()) NewDay();
   double target, daily, maxdd; bool trailing;
   RuleSet(target, daily, maxdd, trailing);
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > gPeak) gPeak = eq;
   double base = trailing ? gPeak : gStart;
   if(gDayStart > 0 && (gDayStart-eq)/gDayStart*100.0 >= daily)
   { gHalted = true; gHaltWhy = "daily"; }
   if(base > 0 && (base-eq)/base*100.0 >= maxdd)
   { gHalted = true; gHaltWhy = "maxdd"; }
   if(InpStopAtTarget && gStart > 0 && (eq-gStart)/gStart*100.0 >= target)
   { gHalted = true; gHaltWhy = "TARGET"; }
   if(gHalted) CloseAll("guard:" + gHaltWhy);
   return gHalted;
}

//====================================================================
//  REGIME  --  on the reference day efficiency was 0.038 and the EA
//  traded it as if it were trending. That is a classification failure,
//  not an entry failure.
//====================================================================
double EfficiencyRatio(int bars)
{
   int n = MathMin(bars, Bars(_Symbol,_Period)-2);
   if(n < 5) return 0.0;
   double net = MathAbs(iClose(_Symbol,_Period,1) - iClose(_Symbol,_Period,n));
   double path = 0.0;
   for(int i=1; i<n; i++)
      path += MathAbs(iClose(_Symbol,_Period,i) - iClose(_Symbol,_Period,i+1));
   return (path > 0) ? net/path : 0.0;
}

string Regime()
{
   double er = EfficiencyRatio(InpRegimeBars);
   if(er < InpRangeER) return "RANGE";
   if(er > InpTrendER) return "TREND";
   return "MIXED";
}

//--- Finding 3: prior 30m drift. WITH -0.15/trade, AGAINST -1.13/trade.
//--- 68% of the day's loss came from 35% of the trades, identifiable
//--- before entry from price alone.
int Drift()
{
   int bars = (int)MathMax(2, InpDriftMins * 60 / PeriodSeconds());
   if(Bars(_Symbol,_Period) < bars+2) return 0;
   double a = iClose(_Symbol,_Period,1), b = iClose(_Symbol,_Period,bars);
   if(a > b) return 1;
   if(a < b) return -1;
   return 0;
}

//====================================================================
//  LIQUIDITY  --  Part 5D.
//  Piercing a level is NOT a signal. What matters is what happens next:
//    EXPANSION  decisive close beyond  -> stops won, level dead, never fade
//    ABSORPTION pierce, no expansion, close back inside -> tradeable
//  Entry only after a reclaim PLUS confirmation: a body close through the
//  open of the last unbroken run of same-direction closes into the extreme.
//  That is parameter-free and earlier than waiting for a swing break.
//====================================================================
void RebuildLevels()
{
   ArrayResize(lvlHi,0); ArrayResize(lvlLo,0);
   ArrayResize(lvlHiDead,0); ArrayResize(lvlLoDead,0);
   int look = MathMin(InpLevelLookback, Bars(_Symbol,_Period)-InpSwingN-2);
   double tol = InpEqualTolATR * gAtr;
   for(int i = InpSwingN+1; i < look; i++)
   {
      bool ph = true, pl = true;
      double hv = iHigh(_Symbol,_Period,i), lv = iLow(_Symbol,_Period,i);
      for(int k=1; k<=InpSwingN; k++)
      {
         if(iHigh(_Symbol,_Period,i+k) >= hv || iHigh(_Symbol,_Period,i-k) >= hv) ph=false;
         if(iLow (_Symbol,_Period,i+k) <= lv || iLow (_Symbol,_Period,i-k) <= lv) pl=false;
      }
      if(ph) PushLevel(lvlHi, lvlHiDead, hv, tol);
      if(pl) PushLevel(lvlLo, lvlLoDead, lv, tol);
   }
}

//--- equal highs/lows within tol are ONE pool, not several
void PushLevel(double &arr[], bool &dead[], double v, double tol)
{
   for(int i=0; i<ArraySize(arr); i++)
      if(MathAbs(arr[i]-v) <= tol) return;
   int n = ArraySize(arr);
   ArrayResize(arr, n+1); ArrayResize(dead, n+1);
   arr[n] = v; dead[n] = false;
}

//--- how many bars traded back into this level: significance is MEASURED,
//--- not guessed from age (Part 5D).
int Touches(double level, double tol)
{
   int n=0, look = MathMin(InpLevelLookback, Bars(_Symbol,_Period)-2);
   for(int i=1; i<look; i++)
      if(iHigh(_Symbol,_Period,i) >= level-tol && iLow(_Symbol,_Period,i) <= level+tol) n++;
   return n;
}

//--- the confirmation: open of the last unbroken run of same-direction
//--- closes into the extreme. A body close through it is the trigger.
double RunOrigin(int dir, int fromBar)
{
   int i = fromBar;
   int guard = 0;
   while(i < Bars(_Symbol,_Period)-2 && guard < 50)
   {
      bool sameDir = (dir > 0)
         ? (iClose(_Symbol,_Period,i) < iOpen(_Symbol,_Period,i))   // down-closes into a low
         : (iClose(_Symbol,_Period,i) > iOpen(_Symbol,_Period,i));
      if(!sameDir) break;
      i++; guard++;
   }
   return iOpen(_Symbol,_Period,MathMax(1, i-1));
}

//--- returns +1 long / -1 short / 0 none, and writes the level used
int LiquiditySignal(double &levelOut, string &whyOut)
{
   if(!InpLiquidity) return 0;
   if(gAtr <= 0) return 0;
   double tol    = InpEqualTolATR * gAtr;
   double pierce = InpPierceATR * gAtr;
   double expand = InpExpandCloseATR * gAtr;
   double h1 = iHigh(_Symbol,_Period,1), l1 = iLow(_Symbol,_Period,1);
   double c1 = iClose(_Symbol,_Period,1);

   for(int i=0; i<ArraySize(lvlLo); i++)
   {
      if(lvlLoDead[i]) continue;
      double lv = lvlLo[i];
      if(l1 > lv - pierce) continue;                  // not pierced
      if(c1 < lv - expand) { lvlLoDead[i] = true; continue; }  // EXPANSION: dead
      if(c1 <= lv) continue;                          // pierced, not reclaimed yet
      if(c1 <= RunOrigin(1, 1)) continue;             // reclaim without confirmation
      if(Touches(lv, tol) < 2) continue;              // insignificant level
      lvlLoDead[i] = true;                            // one event per level
      levelOut = lv; whyOut = "absorb-low";
      return 1;
   }
   for(int i=0; i<ArraySize(lvlHi); i++)
   {
      if(lvlHiDead[i]) continue;
      double lv = lvlHi[i];
      if(h1 < lv + pierce) continue;
      if(c1 > lv + expand) { lvlHiDead[i] = true; continue; }
      if(c1 >= lv) continue;
      if(c1 >= RunOrigin(-1, 1)) continue;
      if(Touches(lv, tol) < 2) continue;
      lvlHiDead[i] = true;
      levelOut = lv; whyOut = "absorb-high";
      return -1;
   }
   return 0;
}

//--- RANGE regime: rotate inside the boundaries. This is the OPPOSITE of
//--- the trend logic and is exactly what the reference day needed.
int RangeSignal(string &whyOut)
{
   if(Regime() != "RANGE") return 0;
   int look = MathMin(InpRegimeBars*2, Bars(_Symbol,_Period)-2);
   double hi=-DBL_MAX, lo=DBL_MAX;
   for(int i=1;i<look;i++)
   { hi=MathMax(hi,iHigh(_Symbol,_Period,i)); lo=MathMin(lo,iLow(_Symbol,_Period,i)); }
   double w = hi-lo;
   if(w < gAtr*2.0) return 0;
   double c1 = iClose(_Symbol,_Period,1);
   double pos = (c1-lo)/w;
   if(pos <= 0.20) { whyOut="range-low";  return  1; }
   if(pos >= 0.80) { whyOut="range-high"; return -1; }
   return 0;
}

//====================================================================
//  GATES LEARNED FROM THE LIVE CHARTS (15 Sep, M1)
//====================================================================

//--- ROOM TO LIQUIDITY.
//    His words: "bullish trend hit an equality high, we had entered a buy
//    before, it just started dumping, we hit stop loss."
//    An equal high is not resistance -- it is a shelf of resting sell orders
//    plus the stops of everyone long underneath. Price is ATTRACTED to it,
//    trades through it to fill them, then reverses. Buying into an untested
//    shelf is buying the liquidity the move exists to collect.
//    So: require clear air between here and the nearest untested shelf.
double RoomToLevel(int dir)
{
   double px = iClose(_Symbol,_Period,1);
   double best = -1.0;
   if(dir > 0)
   {
      for(int i=0; i<ArraySize(lvlHi); i++)
      {
         if(lvlHiDead[i]) continue;
         double d = lvlHi[i] - px;
         if(d <= 0) continue;
         if(best < 0 || d < best) best = d;
      }
   }
   else
   {
      for(int i=0; i<ArraySize(lvlLo); i++)
      {
         if(lvlLoDead[i]) continue;
         double d = px - lvlLo[i];
         if(d <= 0) continue;
         if(best < 0 || d < best) best = d;
      }
   }
   return best;                       // negative = no level in the way
}

//--- is that nearest level actually a SHELF (two or more equal levels)?
//    A single swing is weak. Equal highs are where the orders pile up.
bool IsShelf(int dir, double level)
{
   double tol = InpEqualShelfATR * gAtr;
   int n = 0;
   if(dir > 0)
   { for(int i=0;i<ArraySize(lvlHi);i++) if(MathAbs(lvlHi[i]-level)<=tol) n++; }
   else
   { for(int i=0;i<ArraySize(lvlLo);i++) if(MathAbs(lvlLo[i]-level)<=tol) n++; }
   return (n >= 2) || (Touches(level, tol) >= 3);
}

bool RoomOK(int dir)
{
   if(!InpRoomGate) return true;
   double room = RoomToLevel(dir);
   if(room < 0) return true;                       // clear air
   if(room >= InpMinRoomATR * gAtr) return true;   // enough room
   // close to a level: only block if it is a real shelf
   double px = iClose(_Symbol,_Period,1);
   double lv = (dir > 0) ? px + room : px - room;
   if(!IsShelf(dir, lv)) return true;
   nRoomBlock++;
   return false;
}

//--- DISPLACEMENT. The 18:53 bar ran 4.42 pts = 3.0 ATR in one minute and a
//    BUY arrow sat inside it. Entering that far up a bar leaves no room and
//    a wide stop. Gate on how far price already travelled within the bar,
//    not on bar size alone -- a big bar you enter at the START of is fine.
bool TravelOK(int dir)
{
   if(!InpTravelGate) return true;
   double o = iOpen(_Symbol,_Period,1);
   double c = iClose(_Symbol,_Period,1);
   double travelled = (c - o) * dir;               // in the trade's own direction
   if(travelled < InpMaxTravelATR * gAtr) return true;
   nTravelBlock++;
   return false;
}

//--- ANTI-WHIPSAW. Image 4: 20 arrows in 72 minutes, alternating, each pair a
//    round trip. At 0.02 lots that is GBP 8.80 of spread across an 11.7-point
//    window -- 51% of the whole move, paid before anything is right or wrong.
bool FlipOK(int dir)
{
   if(!InpFlipGate) return true;
   if(gLastExitDir == 0 || gLastExitDir == dir) return true;
   int since = (int)(TimeCurrent() - gLastExitTime);
   if(since >= InpFlipCooldown) return true;
   double moved = MathAbs(iClose(_Symbol,_Period,1) - gLastExitPx);
   if(moved >= InpFlipMinMoveATR * gAtr) return true;
   nFlipBlock++;
   return false;
}

//--- NEWS. His note: "may have been cuz news was in few minutes, volume was
//    being put into market." Two independent detectors: the terminal calendar,
//    and a raw tick-volume surge for anything the calendar does not list.
bool NewsClear()
{
   if(!InpNewsGate) return true;
   // 1. tick-volume surge -- works on every terminal, no calendar needed
   long v[]; ArraySetAsSeries(v, true);
   if(CopyTickVolume(_Symbol, _Period, 1, 51, v) == 51)
   {
      long tmp[]; ArrayResize(tmp, 50);
      for(int i=0;i<50;i++) tmp[i] = v[i+1];
      ArraySort(tmp);
      double med = (double)tmp[25];
      if(med > 0 && (double)v[0] >= InpVolSurgeMult * med)
      { nNewsBlock++; return false; }
   }
   // 2. terminal economic calendar, where the build provides it
   MqlCalendarValue cv[];
   datetime from = TimeTradeServer() - InpNewsAfterMin*60;
   datetime to   = TimeTradeServer() + InpNewsBeforeMin*60;
   string ccy = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_PROFIT);
   if(ccy == "") ccy = "USD";
   int n = CalendarValueHistory(cv, from, to, NULL, ccy);
   for(int i=0; i<n; i++)
   {
      MqlCalendarEvent ev;
      if(!CalendarEventById(cv[i].event_id, ev)) continue;
      if(ev.importance == CALENDAR_IMPORTANCE_HIGH)
      { nNewsBlock++; return false; }
   }
   return true;
}

//--- SPREAD. Finding 5: GBP76.53 of a GBP159.79 loss. Unlike every other
//    line in the book this one is CERTAIN -- it is not a bet, it is a fee, and
//    it is the only cost you can cut without giving up a trade you wanted.
//    It is also not constant: it widens at rollover, in thin Asia hours and
//    around news. Entering then pays the worst price of the day for the same
//    signal. Measured against its OWN median, so it works on any symbol.
double SpreadPts()
{
   return SymbolInfoDouble(_Symbol,SYMBOL_ASK) - SymbolInfoDouble(_Symbol,SYMBOL_BID);
}

bool SpreadOK()
{
   if(!InpSpreadGate) return true;
   static double hist[]; static int hn = 0;
   double sp = SpreadPts();
   if(sp <= 0) return true;
   int cap = MathMax(20, InpSpreadWindow);
   if(ArraySize(hist) != cap) { ArrayResize(hist, cap); ArrayInitialize(hist, 0.0); hn = 0; }
   hist[hn % cap] = sp; hn++;
   int have = MathMin(hn, cap);
   if(have < 20) return true;                       // not enough history yet
   double tmp[]; ArrayResize(tmp, have);
   for(int i=0;i<have;i++) tmp[i] = hist[i];
   ArraySort(tmp);
   double med = tmp[have/2];
   if(med <= 0) return true;
   if(sp <= InpMaxSpreadMult * med) return true;
   nSpreadBlock++;
   return false;
}

//--- RE-ENTRY. "we hit stop loss then we did reenter but it was a lucky move."
//    Re-entering the same direction near the same price after being stopped is
//    paying twice for one wrong read. Allowed again once price has genuinely
//    moved away, or enough bars have passed.
bool ReentryOK(int dir)
{
   if(!InpReentryGate) return true;
   if(gLastLossDir == 0 || gLastLossDir != dir) return true;
   int barsSince = Bars(_Symbol,_Period) - gLastLossBar;
   int secsSince = (int)(TimeCurrent() - gLastLossTime);
   // bars stall when the market is dead; seconds do not. Need BOTH to expire.
   if(barsSince >= InpReentryBars && secsSince >= InpReentryBars*PeriodSeconds())
      return true;
   double moved = MathAbs(iClose(_Symbol,_Period,1) - gLastLossPx);
   if(moved >= InpReentryDistATR * gAtr) return true;
   nReentryBlock++;
   return false;
}

//--- DEAD MARKET. SNIPER rotates ranges, which is right -- but only when the
//    range is wide enough to pay the spread twice and leave something over.
//    On the reference day efficiency was 0.038: that is not a range, it is noise.
bool AliveOK()
{
   if(InpMinAtrPts > 0 && gAtr < InpMinAtrPts) { nDeadBlock++; return false; }
   if(Regime() != "RANGE") return true;
   int look = MathMin(InpRegimeBars*2, Bars(_Symbol,_Period)-2);
   double hi=-DBL_MAX, lo=DBL_MAX;
   for(int i=1;i<look;i++)
   { hi=MathMax(hi,iHigh(_Symbol,_Period,i)); lo=MathMin(lo,iLow(_Symbol,_Period,i)); }
   if((hi-lo) >= InpMinRangeATR*gAtr) return true;
   nDeadBlock++;
   return false;
}

//--- PULLBACK BAND. Part 5E records this as the only clearly positive cohort:
//    entries at 60-80% of the prior 30-min range, in the trend direction.
//    Default OFF because it REFUSES signals and the standing rule is that the
//    lever is size, never refusal. Turn it on only after the CSV shows it earns
//    its place on your own account.
bool PullbackOK(int dir)
{
   if(!InpPullbackGate) return true;
   int bars = (int)MathMax(4, InpPullMins*60/PeriodSeconds());
   bars = MathMin(bars, Bars(_Symbol,_Period)-2);
   double hi=-DBL_MAX, lo=DBL_MAX;
   for(int i=1;i<bars;i++)
   { hi=MathMax(hi,iHigh(_Symbol,_Period,i)); lo=MathMin(lo,iLow(_Symbol,_Period,i)); }
   double w = hi-lo;
   if(w <= 0) return true;
   double pos = (iClose(_Symbol,_Period,1)-lo)/w;
   if(dir < 0) pos = 1.0 - pos;
   if(pos >= InpPullMin && pos <= InpPullMax) return true;
   nPullBlock++;
   return false;
}

//====================================================================
//  ENTRY
//====================================================================
void OnTick()
{
   ManageAll();
   datetime bt = iTime(_Symbol,_Period,0);
   if(bt == lastBar) return;
   lastBar = bt;

   gAtr = AtrNow();
   if(gAtr <= 0) return;
   if(GuardsBlock()) return;
   if(ArraySize(L) >= MaxStack()) return;

   RebuildLevels();

   double lvl = 0.0; string why = "";
   int sig = LiquiditySignal(lvl, why);
   if(sig == 0) sig = RangeSignal(why);
   if(sig == 0) return;

   // gates learned from the live charts -- each one counts what it refuses,
   // so you can check on your own account whether it earned its place
   if(!SpreadOK())      return;
   if(!AliveOK())       return;
   if(!NewsClear())     return;
   if(!ReentryOK(sig))  return;
   if(!FlipOK(sig))     return;
   if(!TravelOK(sig))   return;
   if(!RoomOK(sig))     return;
   if(!PullbackOK(sig)) return;

   // B3: in-memory duplicate guard AT SEND TIME. Deal history is empty when
   // two clocks fire in the same OnTick, which is how one signal became three
   // positions sharing a stop and paying three spreads.
   double px = (sig>0) ? SymbolInfoDouble(_Symbol,SYMBOL_ASK)
                       : SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(bt == gLastSendBar && sig == gLastSendDir && MathAbs(px-gLastSendPx) < gAtr*0.05)
      return;

   Enter(sig, px, why);
}

void Enter(int dir, double px, string why)
{
   double ext = (dir>0) ? iLow(_Symbol,_Period,1) : iHigh(_Symbol,_Period,1);
   for(int k=2; k<=InpSwingN; k++)
      ext = (dir>0) ? MathMin(ext, iLow(_Symbol,_Period,k))
                    : MathMax(ext, iHigh(_Symbol,_Period,k));
   double sd = MathAbs(px-ext) + InpStopBufATR*gAtr;
   if(sd <= 0) return;
   if(sd > InpMaxStopATR*gAtr) { nSkipWide++; return; }

   string reg = Regime();
   double dMult = 1.0, rMult = 1.0;
   if(InpDriftSize)
   {
      int d = Drift();
      dMult = (d == 0) ? 1.0 : ((d == dir) ? InpWithDriftMult : InpAgainstMult);
   }
   if(InpRegimeGate && reg == "RANGE") rMult = InpRangeMult;

   double lots = SizeFor(sd, dMult*rMult);
   if(lots <= 0) { nSkipSize++; return; }

   double sl = NormalizeDouble((dir>0) ? px-sd : px+sd, bDigits);
   bool ok = (dir>0) ? Trade.Buy(lots,_Symbol,0.0,sl,0.0,"SNIPER-"+why)
                     : Trade.Sell(lots,_Symbol,0.0,sl,0.0,"SNIPER-"+why);
   if(!ok)
   {
      PrintFormat("%s order rejected %d %s", SNIPER_BUILD,
                  Trade.ResultRetcode(), Trade.ResultRetcodeDescription());
      return;
   }
   gLastSendBar = iTime(_Symbol,_Period,0);
   gLastSendDir = dir;
   gLastSendPx  = px;

   int n = ArraySize(L);
   ArrayResize(L, n+1);
   L[n].ticket   = Trade.ResultOrder();
   L[n].dir      = dir;
   L[n].entry    = (Trade.ResultPrice() > 0 ? Trade.ResultPrice() : px);
   L[n].stopDist = sd;
   L[n].peak     = 0.0;
   L[n].lockPx   = 0.0;
   L[n].opened   = TimeCurrent();
   L[n].locked   = false;
   L[n].fastFailed = false;
   L[n].worstFirstWindow = 0.0;
   L[n].travelATR = (gAtr > 0)
      ? (iClose(_Symbol,_Period,1)-iOpen(_Symbol,_Period,1))*dir/gAtr : 0.0;
   L[n].regime   = reg;
   L[n].why      = why;
   L[n].driftMult= dMult;
   L[n].regimeMult = rMult;
   nT++;

   if(InpJournal)
      PrintFormat("%s %s %s lots=%.2f entry=%.2f sl=%.2f (%.2f ATR) regime=%s driftx%.2f",
                  SNIPER_BUILD, (dir>0?"BUY":"SELL"), why, lots,
                  L[n].entry, sl, sd/gAtr, reg, dMult);
}

//--- B2: every multiplier applies, and there is exactly ONE return, at the
//--- bottom. The old file returned early on fixed lots and stranded the
//--- session, confidence and coordination multipliers behind it.
double SizeFor(double stopDist, double mult)
{
   double lots = 0.0;
   if(bMoneyPerPt > 0 && stopDist > 0)
   {
      double riskMoney = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPct/100.0 * mult;
      lots = riskMoney / (stopDist * bMoneyPerPt);
   }
   lots = MathFloor(lots/bLotStep) * bLotStep;
   if(lots < bMinLot) lots = 0.0;              // refuse, never round up
   if(lots > bMaxLot) lots = bMaxLot;
   // affordability, checked before the order rather than by free margin at fill
   if(lots > 0 && bMarginPerMinLot > 0)
   {
      double need = bMarginPerMinLot * (lots/bMinLot);
      double have = AccountInfoDouble(ACCOUNT_MARGIN_FREE) * InpMarginHeadroom;
      if(need > have) lots = 0.0;
   }
   return lots;
}

//====================================================================
//  EXIT STACK
//====================================================================
void ManageAll()
{
   for(int i = ArraySize(L)-1; i >= 0; i--)
   {
      if(!PositionSelectByTicket(L[i].ticket)) { Settle(i); continue; }
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) { Drop(i); continue; }
      ManageOne(i);
   }
}

void ManageOne(int i)
{
   double a = AtrNow();
   if(a <= 0) a = gAtr;
   if(a <= 0) return;
   int dir = L[i].dir;
   double cur = (dir>0) ? SymbolInfoDouble(_Symbol,SYMBOL_BID)
                        : SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double fav = (cur - L[i].entry) * dir;
   double adv = -fav;
   int age = (int)(TimeCurrent() - L[i].opened);
   if(fav > L[i].peak) L[i].peak = fav;
   if(age <= InpFastFailSecs && adv > L[i].worstFirstWindow)
      L[i].worstFirstWindow = adv;

   if(age < GraceSecs()) return;               // B1: capped below the cut window

   // ---- MECHANISM 1: the 60-second cut ----
   if(InpFastFail && !L[i].fastFailed && age <= InpFastFailSecs)
   {
      if(adv >= InpFastFailATR * a)
      {
         L[i].fastFailed = true;
         if(InpFFShadow)
         {
            // SHADOW: record that it WOULD have cut, and let the trade run so
            // the CSV can answer whether cutting was right on THIS account.
            nShadowCut++;
            if(InpJournal)
               PrintFormat("%s FAST-FAIL (shadow) at %ds, %.2f ATR against"
                           " -- would have cut here, holding to measure",
                           SNIPER_BUILD, age, adv/a);
         }
         else
         {
            nFastFail++;
            Trade.PositionClose(L[i].ticket);
            if(InpJournal)
               PrintFormat("%s FAST-FAIL at %ds, %.2f ATR against -- Finding 2 cohort",
                           SNIPER_BUILD, age, adv/a);
            return;
         }
      }
   }

   // ---- a winner must never become a loser. SL-HIT held 173.4 pts of peak
   //      and closed -54.7. Once peak reaches InpBEAtR the stop never goes
   //      back below entry.
   if(InpBEAtR > 0 && L[i].peak >= InpBEAtR * L[i].stopDist)
      SetStop(i, L[i].entry + dir * InpBELockR * L[i].stopDist, cur, dir);

   // ---- MECHANISM 2: the peak lock (BASKET-LOCK kept 98%) ----
   // Arm level in PRICE, derived from the noise band so it scales with both
   // volatility and position size. No cash floor: a fixed pound figure is what
   // stopped QUAD's best exit from ever firing.
   double band = SpreadPts() + InpNoiseFloorATR * a;
   double armPx = InpBandArm ? (InpArmBands * band) : (InpLockArmATR * a);
   if(InpPeakLock && L[i].peak >= armPx)
   {
      // keep-fraction rises with the peak: protects a small winner without
      // capping a runner. A flat GBP1 is unreachable on a dead night and a
      // joke on a spike -- so it is in ATR and it scales.
      double armATR = armPx / a;
      double span = MathMax(0.0001, InpLockScaleATR - armATR);
      double t = (L[i].peak/a - armATR) / span;
      t = MathMax(0.0, MathMin(1.0, t));
      double keep = InpLockKeepMin + t*(InpLockKeepMax - InpLockKeepMin);
      // never lock closer than ONE band: no trail can hold inside the noise
      double lockLevel = L[i].entry + dir * MathMin(L[i].peak*keep, L[i].peak - band);
      if((L[i].peak - band) <= 0) lockLevel = L[i].entry + dir * L[i].peak * keep;
      double trailLevel = cur - dir * InpTrailATR * a;
      double want = (dir>0) ? MathMax(lockLevel, trailLevel)
                            : MathMin(lockLevel, trailLevel);
      if(!L[i].locked) { L[i].locked = true; nLocked++; }
      SetStop(i, want, cur, dir);
   }

   // ---- time stop. Finding 6: the move lasts 42 min, the hold was 4. ----
   int limit = L[i].locked ? InpRunnerMins : InpMaxHoldMins;
   if(age >= limit*60)
   {
      Trade.PositionClose(L[i].ticket);
      if(InpJournal) PrintFormat("%s time stop at %d min", SNIPER_BUILD, age/60);
   }
}

void SetStop(int i, double want, double cur, int dir)
{
   double sl = PositionGetDouble(POSITION_SL);
   want = NormalizeDouble(want, bDigits);
   bool better = (dir>0) ? (want > sl) : (want < sl);
   bool legal  = (dir>0) ? (cur - want > bStopLvl) : (want - cur > bStopLvl);
   if(better && legal)
   {
      Trade.PositionModify(L[i].ticket, want, PositionGetDouble(POSITION_TP));
      L[i].lockPx = want;
   }
}

//--- the position is gone: record what happened, including how much of the
//--- peak was kept. "How many trades went above GBP 1" was unanswerable from
//--- the old logs (Part 5H); it is answerable from this CSV.
void Settle(int i)
{
   double pts = 0.0, vol = 0.0;
   if(HistorySelect(L[i].opened-60, TimeCurrent()+60))
   {
      for(int k = HistoryDealsTotal()-1; k >= 0; k--)
      {
         ulong t = HistoryDealGetTicket(k);
         if(HistoryDealGetInteger(t, DEAL_MAGIC) != InpMagic) continue;
         if(HistoryDealGetInteger(t, DEAL_POSITION_ID) != (long)L[i].ticket) continue;
         if(HistoryDealGetInteger(t, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
         double v = HistoryDealGetDouble(t, DEAL_VOLUME);
         pts += v * (HistoryDealGetDouble(t, DEAL_PRICE) - L[i].entry) * L[i].dir;
         vol += v;
      }
   }
   if(vol > 0) pts /= vol;
   gLastExitTime = TimeCurrent();
   gLastExitDir  = L[i].dir;
   gLastExitPx   = iClose(_Symbol,_Period,1);
   if(pts <= 0)
   {
      gLastLossTime = TimeCurrent();
      gLastLossDir  = L[i].dir;
      gLastLossPx   = L[i].entry;
      gLastLossBar  = Bars(_Symbol,_Period);
   }
   sumPts += pts;
   sumPeakPts += L[i].peak;
   if(pts > 0) nWin++;
   if(L[i].peak > 0.0001) { sumKept += pts/L[i].peak; nKept++; }
   WriteCSV(i, pts);
   if(InpJournal)
      PrintFormat("%s closed %s peak=%.2f exit=%.2f kept=%.0f%% age=%dm %s",
                  SNIPER_BUILD, L[i].why, L[i].peak, pts,
                  (L[i].peak>0 ? 100.0*pts/L[i].peak : 0.0),
                  (int)((TimeCurrent()-L[i].opened)/60), L[i].regime);
   Drop(i);
}

void Drop(int i)
{
   int n = ArraySize(L);
   for(int k=i; k<n-1; k++) L[k] = L[k+1];
   ArrayResize(L, n-1);
}

void CloseAll(string why)
{
   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == InpMagic
         && PositionGetString(POSITION_SYMBOL) == _Symbol)
      { Trade.PositionClose(t); Print(SNIPER_BUILD, " closed by ", why); }
   }
}

//====================================================================
//  CSV -- Part 5H. Every gate that was evaluated, with its result.
//====================================================================
void OpenCSV()
{
   if(!InpWriteCSV) return;
   bool fresh = !FileIsExist(InpCSVName, FILE_COMMON);
   csvHandle = FileOpen(InpCSVName, FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON, ',');
   if(csvHandle == INVALID_HANDLE) { Print(SNIPER_BUILD, ": CSV open failed"); return; }
   FileSeek(csvHandle, 0, SEEK_END);
   if(fresh)
      FileWrite(csvHandle, "open_time","close_time","symbol","tf","dir","why",
                "entry","exit_pts","peak_pts","kept_frac","stop_atr","atr",
                "hold_secs","regime","drift_mult","regime_mult",
                "fast_failed","ff_shadow","locked","worst_first_window_atr",
                "room_atr","travel_atr");
}

void WriteCSV(int i, double pts)
{
   if(!InpWriteCSV || csvHandle == INVALID_HANDLE) return;
   double a = (gAtr > 0 ? gAtr : 1.0);
   FileWrite(csvHandle,
      TimeToString(L[i].opened, TIME_DATE|TIME_SECONDS),
      TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
      _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
      (L[i].dir>0 ? "BUY" : "SELL"), L[i].why,
      DoubleToString(L[i].entry, bDigits),
      DoubleToString(pts, 2),
      DoubleToString(L[i].peak, 2),
      DoubleToString((L[i].peak>0 ? pts/L[i].peak : 0.0), 3),
      DoubleToString(L[i].stopDist/a, 2),
      DoubleToString(a, 3),
      (string)(int)(TimeCurrent()-L[i].opened),
      L[i].regime,
      DoubleToString(L[i].driftMult, 2),
      DoubleToString(L[i].regimeMult, 2),
      (L[i].fastFailed ? "1" : "0"),
      (InpFFShadow ? "1" : "0"),
      (L[i].locked ? "1" : "0"),
      DoubleToString(L[i].worstFirstWindow/a, 2),
      DoubleToString(RoomToLevel(L[i].dir)/a, 2),
      DoubleToString(L[i].travelATR, 2));
   FileFlush(csvHandle);
}

//====================================================================
//  PANEL
//====================================================================
string SessionNow()
{
   MqlDateTime t; TimeToStruct(TimeGMT(), t);
   int h = t.hour;
   if(h >= 23 || h < 7)  return "Asia";
   if(h < 12)            return "London";
   if(h < 16)            return "London/NY";
   if(h < 21)            return "New York";
   return "Off";
}

void DrawPanel()
{
   double target, daily, maxdd; bool trailing;
   RuleSet(target, daily, maxdd, trailing);
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double base = trailing ? gPeak : gStart;
   double kept = (nKept > 0) ? 100.0*sumKept/nKept : 0.0;
   double gave = sumPeakPts - sumPts;

   string s = StringFormat(
     "%s   %s %s   %s   regime %s\n"
     "session %s (GMT %s)   ER(%d) %.3f   drift %s\n"
     "-----------------------------------------------\n"
     "open %d / %d max    balance %.2f %s   minLot %.2f\n"
     "risk %.2f%%   ATR %.2f   grace %ds   cut %.2f ATR @ %ds\n"
     "-----------------------------------------------\n"
     "trades %d   win %.0f%%   net %.1f pts\n"
     "PEAK POOL %.1f pts   KEPT %.0f%%   GAVE BACK %.1f pts\n"
     "fast-fails %d (shadow %d)   locked %d   wide %d / size %d\n"
     "refused: room %d travel %d flip %d news %d\n"
     "         spread %d reentry %d dead %d pullback %d\n"
     "%s",
     SNIPER_BUILD, _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
     EnumToString(InpRules), Regime(),
     SessionNow(), TimeToString(TimeGMT(), TIME_MINUTES),
     InpRegimeBars, EfficiencyRatio(InpRegimeBars),
     (Drift()>0 ? "up" : (Drift()<0 ? "down" : "flat")),
     ArraySize(L), MaxStack(), AccountInfoDouble(ACCOUNT_BALANCE),
     AccountInfoString(ACCOUNT_CURRENCY), bMinLot,
     InpRiskPct, gAtr, GraceSecs(), InpFastFailATR, InpFastFailSecs,
     nT, (nT>0 ? 100.0*nWin/nT : 0.0), sumPts,
     sumPeakPts, kept, gave,
     nFastFail, nShadowCut, nLocked, nSkipWide, nSkipSize,
     nRoomBlock, nTravelBlock, nFlipBlock, nNewsBlock,
     nSpreadBlock, nReentryBlock, nDeadBlock, nPullBlock,
     (gHalted ? "HALTED: "+gHaltWhy : "trading"));

   string n = "SNIPER_panel";
   if(ObjectFind(0, n) < 0)
   {
      ObjectCreate(0, n, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, n, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, n, OBJPROP_XDISTANCE, 12);
      ObjectSetInteger(0, n, OBJPROP_YDISTANCE, 20);
      ObjectSetInteger(0, n, OBJPROP_FONTSIZE, 9);
      ObjectSetString(0, n, OBJPROP_FONT, "Consolas");
      ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
   }
   ObjectSetInteger(0, n, OBJPROP_COLOR, gHalted ? clrTomato : clrGainsboro);
   ObjectSetString(0, n, OBJPROP_TEXT, s);
   ChartRedraw(0);
}
//+------------------------------------------------------------------+
