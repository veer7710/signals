//+------------------------------------------------------------------+
//|                                        SuperTrendSniper2.mq5     |
//|  XAUUSD mini-trend scalper. Rebuild of the v1 Sniper.            |
//|                                                                  |
//|  WHAT CHANGED AND WHY (all measured, see docs/FINDINGS.md):      |
//|                                                                  |
//|  1. THE TRAIL NOW ARMS AT 1R, NOT AT ZERO.                       |
//|     v1 trailed at 40% of run-up from the first tick in profit,   |
//|     so it exited on the first pullback of EVERY trade. Measured  |
//|     average winner: $5.06. That is the "went to GBP15, closed    |
//|     at GBP4" complaint, and it was arithmetic, not bad luck.     |
//|     Paired test on 498 identical entries (GOLD 15m, de-trended): |
//|       ATR-trail 3.0            +$4.54/trade  t=3.44  CI[1.9,7.1] |
//|       giveback .55 armed at 1R +$2.70/trade  t=2.48  CI[0.6,4.9] |
//|     Same direction on 1h (+1.46, +0.85), not significant there.  |
//|                                                                  |
//|  2. STOP DISTANCE IS CAPPED.                                     |
//|     v1's complaint "it signals on big candles" is NOT an entry-  |
//|     quality problem -- measured, big-candle flips scored the     |
//|     SAME or better than quiet ones. The real damage is that a    |
//|     big candle produces a wide structural stop, and at a fixed   |
//|     0.01 lot a wide stop is a big loss. So we cap the STOP, not  |
//|     the signal. Trades needing more than InpMaxStopATR are       |
//|     skipped and counted, so you can see what refusing them cost. |
//|                                                                  |
//|  3. IT NEVER OVERSIZES.                                          |
//|     If risk-% sizing asks for less than the broker minimum lot,  |
//|     the trade is SKIPPED, never rounded up. Rounding up is how   |
//|     a GBP50 account gets margin-called.                          |
//|                                                                  |
//|  4. IT REPORTS ITS OWN CAPTURE RATIO (exit-R / peak-R).          |
//|     You cannot fix "it does not close near the peak" without a   |
//|     number for how near it closes. It is on the chart panel.     |
//|                                                                  |
//|  NOT CLAIMED: that this is profitable. Measured edge on entries  |
//|  is not distinguishable from zero (t<2 on every entry family I   |
//|  tested). What IS established is that this exit beats v1's exit  |
//|  on the same trades. Run it small.                               |
//+------------------------------------------------------------------+
#property copyright "Signals research build"
#property version   "2.00"
#property strict

#include <Trade\Trade.mqh>
CTrade Trade;

//--- Entry ---------------------------------------------------------
input group             "=== ENTRY ==="
input int    InpStPeriod      = 10;      // SuperTrend ATR period
input double InpStMult        = 3.0;     // SuperTrend multiplier
input bool   InpWaitPullback  = false;   // enter on pullback to ST line (else market on flip)
input int    InpPullbackBars  = 5;       // max bars to wait for that pullback

//--- Stop ----------------------------------------------------------
input group             "=== STOP ==="
input int    InpSwingLook     = 3;       // bars back for the structural stop
input double InpStopBufATR    = 0.25;    // buffer beyond the swing, in ATR
input double InpMaxStopATR    = 3.0;     // SKIP trade if stop wider than this (risk cap)

//--- Exit (the fix) ------------------------------------------------
input group             "=== EXIT ==="
enum ExitMode { EXIT_ATR_TRAIL, EXIT_GIVEBACK };
input ExitMode InpExitMode    = EXIT_ATR_TRAIL; // measured best: ATR trail
input double InpTrailAtr      = 3.0;     // ATR trail multiple
input double InpGiveBack      = 0.55;    // giveback fraction (giveback mode)
input double InpArmAtR        = 1.0;     // >>> ARM THE TRAIL ONLY AT THIS R <<<
input double InpHardTpR       = 0.0;     // 0 = no fixed TP (let the trail work)
input int    InpMaxBars       = 120;     // hard time stop
input int    InpStallBars     = 0;       // 0 = OFF. v1 used 25 and it killed runners.

//--- Risk ----------------------------------------------------------
input group             "=== RISK ==="
input bool   InpUseRiskPct    = true;    // size by % risk (else fixed lot)
input double InpRiskPct       = 0.50;    // % of balance risked per trade
input double InpFixedLot      = 0.01;    // used when InpUseRiskPct = false
input int    InpMaxOpen       = 1;       // concurrent positions

//--- Funded-account guards (checked BEFORE every order) ------------
input group             "=== FUNDED GUARDS ==="
input bool   InpUseGuards     = true;
input double InpDailyLossPct  = 3.0;     // stop trading for the day at this loss
input double InpMaxDDPct      = 6.0;     // stop trading entirely at this drawdown
input bool   InpCloseOnGuard  = true;    // flatten when a guard trips

//--- Housekeeping --------------------------------------------------
input group             "=== GENERAL ==="
input long   InpMagic         = 770021;
input int    InpSlippage      = 20;
input bool   InpShowPanel     = true;
input bool   InpJournal       = true;

//--- state ---------------------------------------------------------
int      hAtr = INVALID_HANDLE;
datetime lastBar = 0;
double   stLine[], stDirArr[];
int      pendingDir = 0, pendingAge = 0;
double   gPeakFav = 0.0, gEntry = 0.0, gStopDist = 0.0, gArmed = 0.0;
int      gDir = 0;
ulong    gTicket = 0;
// guards
double   gDayStart = 0.0, gPeakEquity = 0.0;
datetime gDayStamp = 0;
bool     gHalted = false;
string   gHaltWhy = "";
// stats
int      nTrades = 0, nSkipWide = 0, nSkipSize = 0, nWins = 0;
double   sumR = 0.0, sumCapture = 0.0, sumPts = 0.0;
int      nCapture = 0;

string GuardFile() { return "STS2_" + _Symbol + "_" + (string)InpMagic + ".guard"; }

//+------------------------------------------------------------------+
int OnInit()
{
   hAtr = iATR(_Symbol, _Period, InpStPeriod);
   if(hAtr == INVALID_HANDLE) { Print("ATR handle failed"); return INIT_FAILED; }
   ArraySetAsSeries(stLine, true);
   ArraySetAsSeries(stDirArr, true);
   Trade.SetExpertMagicNumber(InpMagic);
   Trade.SetDeviationInPoints(InpSlippage);
   Trade.SetTypeFillingBySymbol(_Symbol);
   LoadGuards();                       // persisted, so a restart cannot reset the day
   EventSetTimer(5);
   Print("SuperTrendSniper2 init. Guards halted=", gHalted, " ", gHaltWhy);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   SaveGuards();
   ObjectsDeleteAll(0, "STS2_");
   if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr);
}

void OnTimer() { SaveGuards(); if(InpShowPanel) DrawPanel(); }

//+------------------------------------------------------------------+
//| Guard persistence -- v1 reset the daily limit on every restart.   |
//+------------------------------------------------------------------+
void LoadGuards()
{
   gPeakEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   gDayStart   = gPeakEquity;
   gDayStamp   = Today();
   int h = FileOpen(GuardFile(), FILE_READ|FILE_TXT|FILE_COMMON);
   if(h != INVALID_HANDLE)
   {
      gDayStamp   = (datetime)StringToInteger(FileReadString(h));
      gDayStart   = StringToDouble(FileReadString(h));
      gPeakEquity = StringToDouble(FileReadString(h));
      gHalted     = (StringToInteger(FileReadString(h)) == 1);
      gHaltWhy    = FileReadString(h);
      FileClose(h);
   }
   if(gDayStamp != Today()) NewDay();
   if(gPeakEquity <= 0) gPeakEquity = AccountInfoDouble(ACCOUNT_EQUITY);
}

void SaveGuards()
{
   int h = FileOpen(GuardFile(), FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   FileWrite(h, (string)(long)gDayStamp);
   FileWrite(h, DoubleToString(gDayStart, 2));
   FileWrite(h, DoubleToString(gPeakEquity, 2));
   FileWrite(h, gHalted ? "1" : "0");
   FileWrite(h, gHaltWhy);
   FileClose(h);
}

datetime Today()
{
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   t.hour = 0; t.min = 0; t.sec = 0;
   return StructToTime(t);
}

void NewDay()
{
   gDayStamp = Today();
   gDayStart = AccountInfoDouble(ACCOUNT_EQUITY);
   if(gHaltWhy == "daily") { gHalted = false; gHaltWhy = ""; }  // DD halt persists
   SaveGuards();
}

bool GuardsBlock()
{
   if(!InpUseGuards) return false;
   if(gDayStamp != Today()) NewDay();
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > gPeakEquity) gPeakEquity = eq;
   if(gDayStart > 0 && (gDayStart - eq) / gDayStart * 100.0 >= InpDailyLossPct)
   { gHalted = true; gHaltWhy = "daily"; }
   if(gPeakEquity > 0 && (gPeakEquity - eq) / gPeakEquity * 100.0 >= InpMaxDDPct)
   { gHalted = true; gHaltWhy = "maxdd"; }
   if(gHalted && InpCloseOnGuard) CloseAll("guard:" + gHaltWhy);
   return gHalted;
}

//+------------------------------------------------------------------+
//| SuperTrend -- identical formula to the Pine, so both flip on the |
//| same bar. Computed on CLOSED bars only.                          |
//+------------------------------------------------------------------+
bool CalcSuperTrend(int need, double &dirOut, double &lineOut)
{
   int bars = need + InpStPeriod + 60;
   double atr[]; ArraySetAsSeries(atr, true);
   if(CopyBuffer(hAtr, 0, 0, bars, atr) < bars) return false;
   MqlRates r[]; ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, _Period, 0, bars, r) < bars) return false;

   int last = bars - 2;                       // oldest usable index
   double fu = 0, fd = 0, prevFu = 0, prevFd = 0;
   int dir = 1, prevDir = 1;
   bool init = false;
   for(int i = last; i >= 1; i--)             // i=1 is the newest CLOSED bar
   {
      if(atr[i] <= 0) continue;
      double hl2 = (r[i].high + r[i].low) / 2.0;
      double up  = hl2 - InpStMult * atr[i];
      double dn  = hl2 + InpStMult * atr[i];
      if(!init) { fu = up; fd = dn; dir = 1; init = true; prevFu = fu; prevFd = fd; prevDir = dir; continue; }
      fu = (r[i+1].close > prevFu) ? MathMax(up, prevFu) : up;
      fd = (r[i+1].close < prevFd) ? MathMin(dn, prevFd) : dn;
      if(prevDir == 1) dir = (r[i].close < fu) ? -1 : 1;
      else             dir = (r[i].close > fd) ? 1 : -1;
      prevFu = fu; prevFd = fd; prevDir = dir;
   }
   dirOut  = (double)dir;
   lineOut = (dir == 1) ? fu : fd;
   return true;
}

double AtrNow()
{
   double a[]; ArraySetAsSeries(a, true);
   if(CopyBuffer(hAtr, 0, 1, 2, a) < 2) return 0.0;
   return a[0];
}

//+------------------------------------------------------------------+
void OnTick()
{
   ManageOpen();

   datetime bt = iTime(_Symbol, _Period, 0);
   if(bt == lastBar) return;
   lastBar = bt;                               // one decision per CLOSED bar

   if(GuardsBlock()) return;
   if(CountOpen() >= InpMaxOpen) return;

   double dirNow, lineNow, dirPrev, linePrev;
   if(!CalcSuperTrend(3, dirNow, lineNow)) return;
   // direction on the previous closed bar, to detect the flip
   static double lastDir = 0;
   int flip = 0;
   if(lastDir != 0 && dirNow != lastDir) flip = (int)dirNow;
   lastDir = dirNow;

   if(flip != 0)
   {
      if(InpWaitPullback) { pendingDir = flip; pendingAge = 0; }
      else                TryEnter(flip, lineNow);
   }
   else if(pendingDir != 0)
   {
      pendingAge++;
      if(pendingAge > InpPullbackBars) { pendingDir = 0; return; }
      double c = iClose(_Symbol, _Period, 1);
      double a = AtrNow();
      if(a <= 0) return;
      // pullback = price comes back within 0.5 ATR of the ST line
      if(MathAbs(c - lineNow) <= 0.5 * a) { TryEnter(pendingDir, lineNow); pendingDir = 0; }
   }
}

//+------------------------------------------------------------------+
double StopDistance(int dir)
{
   double a = AtrNow();
   if(a <= 0) return 0.0;
   double ext = (dir > 0) ? iLow(_Symbol, _Period, 1) : iHigh(_Symbol, _Period, 1);
   for(int k = 2; k <= InpSwingLook; k++)
   {
      if(dir > 0) ext = MathMin(ext, iLow(_Symbol, _Period, k));
      else        ext = MathMax(ext, iHigh(_Symbol, _Period, k));
   }
   double px = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                         : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   return MathAbs(px - ext) + InpStopBufATR * a;
}

double MoneyPerPricePerLot()
{
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0) return 0.0;
   return tv / ts;                       // account currency per 1.0 of price, per 1 lot
}

double SizeFor(double stopDist)
{
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stp  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(!InpUseRiskPct) return MathMax(minL, MathMin(maxL, InpFixedLot));
   double mpp = MoneyPerPricePerLot();
   if(mpp <= 0 || stopDist <= 0) return 0.0;
   double riskMoney = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPct / 100.0;
   double lots = riskMoney / (stopDist * mpp);
   lots = MathFloor(lots / stp) * stp;            // ALWAYS round DOWN
   if(lots < minL) return 0.0;                    // too small -> skip, never round up
   return MathMin(lots, maxL);
}

void TryEnter(int dir, double stLineVal)
{
   double a = AtrNow();
   if(a <= 0) return;
   double sd = StopDistance(dir);
   if(sd <= 0) return;
   if(sd > InpMaxStopATR * a) { nSkipWide++; return; }   // risk cap, counted

   double lots = SizeFor(sd);
   if(lots <= 0) { nSkipSize++; return; }

   double px = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                         : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = (dir > 0) ? px - sd : px + sd;
   double tp = 0.0;
   if(InpHardTpR > 0) tp = (dir > 0) ? px + InpHardTpR * sd : px - InpHardTpR * sd;

   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   sl = NormalizeDouble(sl, dg);
   if(tp > 0) tp = NormalizeDouble(tp, dg);

   bool ok = (dir > 0) ? Trade.Buy(lots, _Symbol, 0.0, sl, tp, "STS2")
                       : Trade.Sell(lots, _Symbol, 0.0, sl, tp, "STS2");
   if(!ok) { Print("order failed ", Trade.ResultRetcode(), " ", Trade.ResultRetcodeDescription()); return; }

   gTicket   = Trade.ResultOrder();
   gDir      = dir;
   gEntry    = Trade.ResultPrice() > 0 ? Trade.ResultPrice() : px;
   gStopDist = sd;
   gPeakFav  = 0.0;
   gArmed    = 0.0;
   nTrades++;
   if(InpJournal)
      PrintFormat("ENTRY %s lots=%.2f entry=%.2f stop=%.2f stopDist=%.2f (%.2f ATR)",
                  dir > 0 ? "BUY" : "SELL", lots, gEntry, sl, sd, sd / a);
}

//+------------------------------------------------------------------+
//| Manage the open position: track peak, arm at InpArmAtR, trail.   |
//+------------------------------------------------------------------+
void ManageOpen()
{
   if(!PositionSelect(_Symbol)) { if(gDir != 0) FinishTrade(); return; }
   if(PositionGetInteger(POSITION_MAGIC) != InpMagic) return;

   int    dir  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
   double ent  = PositionGetDouble(POSITION_PRICE_OPEN);
   double cur  = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                           : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl   = PositionGetDouble(POSITION_SL);
   if(gStopDist <= 0) gStopDist = MathAbs(ent - sl);
   if(gStopDist <= 0) return;
   gDir = dir; gEntry = ent;

   double fav = (cur - ent) * dir;
   if(fav > gPeakFav) gPeakFav = fav;

   // ---- THE FIX: nothing trails until the trade is InpArmAtR in profit ----
   if(gPeakFav < InpArmAtR * gStopDist) return;
   gArmed = 1.0;

   double a = AtrNow();
   double cand;
   if(InpExitMode == EXIT_ATR_TRAIL)
      cand = (dir > 0) ? cur - InpTrailAtr * a : cur + InpTrailAtr * a;
   else
      cand = ent + dir * gPeakFav * (1.0 - InpGiveBack);

   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   cand = NormalizeDouble(cand, dg);
   bool better = (dir > 0) ? (cand > sl) : (cand < sl);
   double stopLvl = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL)
                    * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   bool legal = (dir > 0) ? (cur - cand > stopLvl) : (cand - cur > stopLvl);
   if(better && legal)
      Trade.PositionModify(_Symbol, cand, PositionGetDouble(POSITION_TP));
}

void FinishTrade()
{
   // read the closed deal to record capture ratio
   if(!HistorySelect(TimeCurrent() - 86400, TimeCurrent() + 60)) { gDir = 0; return; }
   double pts = 0.0; bool found = false;
   for(int i = HistoryDealsTotal() - 1; i >= 0 && !found; i--)
   {
      ulong t = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(t, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetInteger(t, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      double px = HistoryDealGetDouble(t, DEAL_PRICE);
      pts = (px - gEntry) * gDir;
      found = true;
   }
   if(found && gStopDist > 0)
   {
      double exitR = pts / gStopDist;
      double peakR = gPeakFav / gStopDist;
      sumR += exitR; sumPts += pts;
      if(pts > 0) nWins++;
      if(peakR >= 0.5) { sumCapture += exitR / peakR; nCapture++; }
      if(InpJournal)
         PrintFormat("EXIT  peakR=%.2f exitR=%.2f capture=%.2f pts=%.2f armed=%s",
                     peakR, exitR, peakR > 0 ? exitR / peakR : 0.0, pts,
                     gArmed > 0 ? "yes" : "no");
   }
   gDir = 0; gPeakFav = 0; gStopDist = 0; gArmed = 0;
}

int CountOpen()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == InpMagic
         && PositionGetString(POSITION_SYMBOL) == _Symbol) n++;
   }
   return n;
}

void CloseAll(string why)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == InpMagic
         && PositionGetString(POSITION_SYMBOL) == _Symbol)
      { Trade.PositionClose(t); Print("closed by ", why); }
   }
}

//+------------------------------------------------------------------+
string SessionNow()
{
   MqlDateTime t; TimeToStruct(TimeGMT(), t);
   int h = t.hour;
   if(h >= 23 || h < 7)  return "Asia";
   if(h >= 7  && h < 12) return "London";
   if(h >= 12 && h < 16) return "London/NY overlap";
   if(h >= 16 && h < 21) return "New York";
   return "Off-session";
}

void DrawPanel()
{
   string n = "STS2_panel";
   double cap = (nCapture > 0) ? sumCapture / nCapture : 0.0;
   double wr  = (nTrades > 0) ? 100.0 * nWins / nTrades : 0.0;
   string s = StringFormat(
      "SuperTrend Sniper v2   %s %s\n"
      "session: %s (GMT %s)\n"
      "trades %d   win %.0f%%   sumR %+.2f   pts %+.1f\n"
      "CAPTURE RATIO %.2f  (exit-R / peak-R, n=%d)\n"
      "skipped: stop too wide %d | size too small %d\n"
      "guards: %s   day %+.2f%%   dd %+.2f%%",
      _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
      SessionNow(), TimeToString(TimeGMT(), TIME_MINUTES),
      nTrades, wr, sumR, sumPts, cap, nCapture,
      nSkipWide, nSkipSize,
      gHalted ? ("HALTED " + gHaltWhy) : "ok",
      gDayStart > 0 ? (AccountInfoDouble(ACCOUNT_EQUITY) - gDayStart) / gDayStart * 100.0 : 0.0,
      gPeakEquity > 0 ? (AccountInfoDouble(ACCOUNT_EQUITY) - gPeakEquity) / gPeakEquity * 100.0 : 0.0);

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
