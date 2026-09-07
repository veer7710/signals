//+------------------------------------------------------------------+
//|  SweepSniper.mq5  —  the liquidity sweep Veer trades, automated   |
//|                                                                  |
//|  "i literally run liquidity sweep strat myself and i have 80%     |
//|   winrate. i wanted u using ict smc perfect and automate so i     |
//|   dont have to do analysis"                                       |
//|                                                                  |
//|  FOUR SIGNALS, and this file now matches LIQUIDITY_SNIPER_2_0.pine        |
//|  one for one. Until build 2.00 the chart had four and the EA had ONE -    |
//|  which is the P92 defect exactly: a 52% signal gap between a chart and    |
//|  its EA that sat unnoticed for 180 commits.                               |
//|                                                                          |
//|  1 SWEEP        a confirmed swing level is taken by a WICK (the sweep     |
//|                 bar's body <= 64.6% of its range - THE FAKEOUT FILTER),   |
//|                 then price comes BACK to it. A STOP order at the level.   |
//|                 2579 trades, 65.1% win, 107.3 control se, OOS +0.0991.    |
//|                 Positive on all six instrument/clock cells it was pointed |
//|                 at with NO re-fitting - gold, US500, EURUSD, GBPUSD, on   |
//|                 current data (E-146). The strongest thing here.           |
//|                                                                          |
//|  2 BREAK+RETEST the level is DISRESPECTED by a CLOSE, price returns,      |
//|                 holds, and resumes. A STOP order at the retest bar's      |
//|                 extreme. The OPPOSITE of the sweep - and both are true    |
//|                 because the wick filter separates a rejection from a real |
//|                 break. 2013 trades, 64.3% win, 73.8 control se, and its   |
//|                 out-of-sample BEAT its in-sample (E-144).                 |
//|                                                                          |
//|  3 OB DETECTION a down candle followed by InpObLen up candles is a        |
//|                 bullish block (wugamlo, MPL-2.0). MARKET on the           |
//|                 confirming bar. E-148: nearly DOUBLE the return entry     |
//|                 per trade on M1, 2.4x on M5, OOS better than IS.          |
//|                 The marker every chart draws sits four bars back on the   |
//|                 block candle and THAT PRICE WAS NOT KNOWABLE THEN - this  |
//|                 is the honest version of catching the birth of the move.  |
//|                                                                          |
//|  4 OB RETURN    a LIMIT at the block's near edge when price comes back.   |
//|                 Weakest of the four and still clearly real (56.8 se), and |
//|                 it fires four times as often as detection.                |
//|                                                                          |
//|  ONE POSITION AT A TIME, strongest first. E-149 simulated exactly that    |
//|  and found NO cannibalisation - the sweep's per-trade inside the combined |
//|  book is the same as its standalone figure, so the others fill idle time. |
//|  But it DOES dilute: see the note above InpUseSweep before running all    |
//|  four on M1.                                                              |
//|                                                                          |
//|  RISK, identical for all four: the stop sits beyond the setup's own       |
//|  invalidation + 0.30 ATR, and a setup whose stop is wider than 1.2 ATR is |
//|  REFUSED, not resized - 0.01 lots is the floor (E-081) so it cannot be    |
//|  sized down. Uncapped, one trade took 57% of a GBP60 account (E-138).     |
//|  Exit: give back 25% of the best excursion. No take profit - every fixed  |
//|  target measured worse (E-137) and every PARTIAL measured worse still,    |
//|  without reducing the drawdown or the worst trade (E-147).                |
//|                                                                          |
//|  MEASURED — these are VARIANT B's numbers, the one that ships,     |
//|  not variant A's. Quoting A's validation for B would be quoting    |
//|  numbers for a system that is not the one running (E-139b).        |
//|    2579 trades, 23.6/day, 65.1% win, +309.5 points, GBP1797 @0.01  |
//|    control  real +0.1119/trade vs -0.0142  =  107.3 control se     |
//|    in-sample +0.1241  ->  OUT OF SAMPLE +0.0991                    |
//|    walk-forward +0.1056/+0.1477/+0.1155/+0.0927/+0.0968   5 of 5   |
//|    cost   310.7 at a 0.20 spread -> 241.8 at a 0.40 spread         |
//|    slippage 309.5 -> 257.9 at 0.02 -> 180.5 at 0.05 -> 51.6 at     |
//|             0.10, charged on EVERY trade                            |
//|    max drawdown GBP12.68, worst single trade -GBP4.63              |
//|                                                                    |
//|  THE AUDIT THAT CHANGED THE DESIGN (E-138)                        |
//|    WITHOUT the risk cap the worst single trade was -GBP34.27 and  |
//|    the max drawdown GBP37.99 - 57% and 63% of a GBP60 account.    |
//|    The edge was never the problem. The ACCOUNT would have died    |
//|    before the edge paid. The stop sits beyond the SWEEP EXTREME   |
//|    and nothing bounds how far a sweep runs; 0.01 lots is the      |
//|    floor (E-081) so a stop too wide to afford cannot be sized     |
//|    down - only REFUSED.                                            |
//|         risk cap    points   max DD    worst trade                 |
//|         none         316.6   GBP37.99   -GBP34.27                  |
//|         2.0 ATR      310.7   GBP14.93   -GBP5.90                   |
//|         1.2 ATR      309.5   GBP12.68   -GBP4.63   <- SHIPPED      |
//|    It costs almost nothing and removes two thirds of the          |
//|    drawdown. It is not an optimisation.                            |
//|                                                                    |
//|  ON THE GIVE-BACK: tighter measured better all the way down -      |
//|  5% gives 374.1 points against 25%'s 309.5, and it survives cost   |
//|  and slippage. It is NOT the default, because an optimum sitting   |
//|  at the edge of the tested range is the classic shape of a fitted  |
//|  result, and 25% is the value the full harness was run on. Move    |
//|  it if a demo run supports it, not because the backtest liked it.  |
//|                                                                    |
//|  WHICH CLOCK TO RUN IT ON (E-140). It is no longer hardcoded to   |
//|  M1 - it runs on whatever chart it is attached to, up to InpMaxTF. |
//|      TF    trades/day   per trade today   GBP/day   slip 0.20     |
//|      M1        23.6        0.89 pts        16.48      -206.3      |
//|      M5         5.2        2.11 pts         8.67       +49.1      |
//|      M15        1.9        2.98 pts         4.38       +41.5      |
//|  M1 banks the most in the backtest AND IS THE ONLY ONE THAT DIES  |
//|  UNDER SLIPPAGE. M5 makes half as much and survives four times    |
//|  the slippage, because a 0.40 spread is 0.220 of ATR on M1 and    |
//|  0.088 on M5 (E-132) - the same cost against a bigger move.       |
//|  Run M1 on DEMO to measure your real stop fills. Run M5 live      |
//|  until that measurement says M1 is safe.                           |
//|                                                                    |
//|  NOT PROVEN. One instrument, 2018 H1, NEVER FORWARD TESTED, and   |
//|  the money figure depends on scaling 2018 volatility to today.    |
//|  SUPPORTED, in the vocabulary of EXPERIMENTS.md. DEMO FIRST.      |
//+------------------------------------------------------------------+
#property copyright "JARVIS"
#property version   "2.00"
#property strict

//==================== FORWARD DECLARATIONS =========================
// MQL5 needs a function DECLARED before it is called. Each of these is
// defined further down the file than its first call, which is a compile
// error, not a style point - check_mq5.py now catches the whole class.
double ATR();
bool   InOverlap();


#include <Trade/Trade.mqh>
CTrade trade;
//==============================================================
// BEGIN ProfitBox.mqh  (spliced by JARVIS/tools/build_ea.py - edit the .mqh, not this)
//==============================================================
//+------------------------------------------------------------------+
//|  ProfitBox.mqh  —  the on-chart profit box, shared by every EA    |
//|                                                                  |
//|  WHAT IT IS FOR                                                  |
//|  Veer asked for a box that "should show profit from supertrend    |
//|  strat and liquidity, so it should know how to measure and treat  |
//|  each different".                                                 |
//|                                                                  |
//|  HOW IT DOES THAT: one row per STRATEGY, keyed by magic number.   |
//|  Register every magic you run with PB_AddStrategy() and the box   |
//|  reports each one separately - points, money, trades, win rate -  |
//|  plus a total. Run ZoneSniper, SuperTrendSniper and               |
//|  LiquiditySniper on one account and all three read off one box.   |
//|                                                                  |
//|  WHAT THIS DELIBERATELY DOES *NOT* DO, and the number that        |
//|  settled it (E-131)                                               |
//|  ---------------------------------------------------------------- |
//|  The first version of this file split each trade along the price  |
//|  axis at the arm price:                                           |
//|      LEVEL = dir*(armPx - entry),  TREND = dir*(exit - armPx)     |
//|  That identity holds exactly - it was checked to 0.00e+00 over    |
//|  981 real trades - and it is USELESS. On the shipped System A:    |
//|      TOTAL   +97.1 points                                         |
//|      LEVEL  +691.9  (712% of the result, positive on 100.0% of    |
//|                      trades)                                      |
//|      TREND  -594.8  (-612%, positive on 6.2%)                     |
//|  LEVEL is positive on every single trade because it is MECHANICAL:|
//|  the limit rests 0.50 ATR past the level, so the fill beats the   |
//|  arm price by that offset by construction. It measures the offset,|
//|  not the level. Two rows reading +692 and -595 against a +97      |
//|  result would have looked broken and meant nothing.               |
//|                                                                   |
//|  An exact decomposition is not automatically an honest            |
//|  attribution. What a component is WORTH is an ablation - run the  |
//|  system with and without it - and that is a backtest question,    |
//|  not something a live panel can answer. So the box reports what   |
//|  it can actually measure and says so.                             |
//|                                                                   |
//|  FILL VS SIGNAL is kept, correctly labelled, as an ENTRY-QUALITY  |
//|  diagnostic in points per trade: how much better the resting      |
//|  limit filled than the market at the moment the EA armed. On the  |
//|  backtest that is +0.705/trade against a 0.50 ATR design offset.  |
//|  If your broker's live number comes in far below that, the limits |
//|  are being filled late and the edge is going with it. That is a   |
//|  real thing to watch. It is not a share of the profit.            |
//|                                                                   |
//|  POINTS COME FIRST. E-074: the best per-trade gate set in this    |
//|  project banked the LEAST money. Points are the unit that         |
//|  matters, money second.                                           |
//|                                                                   |
//|  Money is the BROKER'S number: DEAL_PROFIT + swap + commission,   |
//|  in the account currency. It is never modelled here.              |
//+------------------------------------------------------------------+
#property strict

#ifndef PROFITBOX_MQH
#define PROFITBOX_MQH

//==================== configuration ================================
struct PBConfig
{
   string  prefix;        // object-name prefix, must be unique per EA
   string  title;         // shown top-left
   long    magic;         // this EA's own magic (the first strategy row)
   int     corner;        // CORNER_LEFT_UPPER etc.
   int     x;             // margin from that corner, pixels
   int     y;
   int     fontSize;
   string  font;
   color   cBg;
   color   cFrame;
   color   cHead;
   color   cVal;
   color   cPos;
   color   cNeg;
   color   cDim;
   bool    show;
   bool    compact;       // TODAY-first, six rows. See PB_Draw.
};

//==================== per-position ledger ==========================
struct PBTrade
{
   ulong    pid;
   long     magic;        // which strategy opened it
   int      dir;          // +1 long, -1 short
   double   inVol,  inPxVol;
   double   outVol, outPxVol;
   double   money;        // profit + swap + commission, account currency
   double   armPx;        // market price when the EA decided to trade
   datetime tOpen, tClose;
   bool     closed;
};

//==================== the strategy table ===========================
// One row per magic number. Register the EA's own magic first, then any other
// EA you run on the same account, and this box speaks for all of them.
struct PBStrat
{
   long   magic;
   string label;
   int    n, wins;
   int    nDay;                 // today only - the compact box leads with it
   double pts, money, ptsDay;
};
PBStrat g_pbS[];

int PB_StratIdx(long magic)
{
   for(int i = 0; i < ArraySize(g_pbS); i++)
      if(g_pbS[i].magic == magic) return i;
   return -1;
}

void PB_AddStrategy(long magic, string label)
{
   if(PB_StratIdx(magic) >= 0) return;
   int n = ArraySize(g_pbS);
   ArrayResize(g_pbS, n + 1);
   g_pbS[n].magic = magic;
   g_pbS[n].label = label;
   g_pbS[n].n = 0; g_pbS[n].wins = 0; g_pbS[n].nDay = 0;
   g_pbS[n].pts = 0; g_pbS[n].money = 0; g_pbS[n].ptsDay = 0;
}

//==================== state ========================================
PBConfig  g_pb;
PBTrade   g_pbT[];
datetime  g_pbLastScan  = 0;
bool      g_pbDirty     = true;
int       g_pbMaxRows   = 16;

// box geometry, in one place so the background and the rows can never disagree
#define PB_BOX_W 262
int PB_BoxH() { return 20 + g_pbMaxRows * (g_pb.fontSize + 7); }

// aggregates, recomputed by PB_Scan()
double g_pbPts, g_pbPtsDay, g_pbFill, g_pbMoney, g_pbMoneyDay;
int    g_pbNFill;   // trades that carried an arm-price note
double g_pbBest, g_pbWorst, g_pbMaxDD, g_pbLong, g_pbShort;
int    g_pbN, g_pbNDay, g_pbWins, g_pbWinsDay, g_pbNLong, g_pbNShort;
datetime g_pbFirst;

//+------------------------------------------------------------------+
//| the arm price is remembered in an MT5 global variable so that an  |
//| EA restart, a terminal restart or a recompile does not silently   |
//| move a trade's points from LEVEL to TREND. A missing note is not  |
//| an error - it just means that trade reads as entered at market.   |
//+------------------------------------------------------------------+
string PB_Key(string kind, ulong id)
{
   return g_pb.prefix + kind + "." + IntegerToString((long)id);
}

void PB_NoteOrder(ulong orderTicket, double px)
{
   if(orderTicket == 0 || px <= 0.0) return;
   GlobalVariableSet(PB_Key("o", orderTicket), px);
}

// call from OnTradeTransaction on DEAL_ENTRY_IN: moves the note from the
// order ticket it was filed under to the position it became.
void PB_PromoteOrder(ulong orderTicket, ulong positionId, double fallbackPx)
{
   string ko = PB_Key("o", orderTicket);
   double px = GlobalVariableCheck(ko) ? GlobalVariableGet(ko) : fallbackPx;
   if(GlobalVariableCheck(ko)) GlobalVariableDel(ko);
   if(positionId != 0 && px > 0.0)
      GlobalVariableSet(PB_Key("p", positionId), px);
   g_pbDirty = true;
}

// returns 0.0 when there is no note - the caller must not invent one
double PB_ArmPx(ulong positionId, double fallbackPx)
{
   string kp = PB_Key("p", positionId);
   if(GlobalVariableCheck(kp))
   {
      double v = GlobalVariableGet(kp);
      if(v > 0.0) return v;
   }
   return fallbackPx;
}

// notes older than this many days are dead weight in the terminal
void PB_Prune(int days = 30)
{
   datetime cut = TimeCurrent() - (datetime)days * 86400;
   for(int i = GlobalVariablesTotal() - 1; i >= 0; i--)
   {
      string nm = GlobalVariableName(i);
      if(StringFind(nm, g_pb.prefix) != 0) continue;
      if(GlobalVariableTime(nm) < cut) GlobalVariableDel(nm);
   }
}

//==================== the ledger ===================================
int PB_Find(ulong pid)
{
   for(int i = ArraySize(g_pbT) - 1; i >= 0; i--)
      if(g_pbT[i].pid == pid) return i;
   return -1;
}

int PB_Add(ulong pid)
{
   int n = ArraySize(g_pbT);
   ArrayResize(g_pbT, n + 1);
   g_pbT[n].pid = pid;
   g_pbT[n].magic = 0;
   g_pbT[n].dir = 0;
   g_pbT[n].inVol = 0.0;  g_pbT[n].inPxVol = 0.0;
   g_pbT[n].outVol = 0.0; g_pbT[n].outPxVol = 0.0;
   g_pbT[n].money = 0.0;  g_pbT[n].armPx = 0.0;
   g_pbT[n].tOpen = 0;    g_pbT[n].tClose = 0;
   g_pbT[n].closed = false;
   return n;
}

//+------------------------------------------------------------------+
//| Rebuild everything from the terminal's own deal history. Doing it |
//| this way rather than incrementing counters means a restart, a     |
//| manual close or a stop-out filled by the broker all show up - the |
//| box can never drift away from the account.                        |
//|                                                                   |
//| Partial closes are handled by volume-weighting both sides, so a   |
//| position closed in three pieces still reports one honest average  |
//| entry and one honest average exit.                                 |
//+------------------------------------------------------------------+
void PB_Scan()
{
   ArrayFree(g_pbT);
   g_pbPts = 0; g_pbPtsDay = 0; g_pbFill = 0; g_pbNFill = 0;
   g_pbMoney = 0; g_pbMoneyDay = 0;
   g_pbBest = 0; g_pbWorst = 0; g_pbMaxDD = 0; g_pbLong = 0; g_pbShort = 0;
   g_pbN = 0; g_pbNDay = 0; g_pbWins = 0; g_pbWinsDay = 0;
   g_pbNLong = 0; g_pbNShort = 0;
   g_pbFirst = 0;
   for(int i = 0; i < ArraySize(g_pbS); i++)
   {
      g_pbS[i].n = 0; g_pbS[i].wins = 0;
      g_pbS[i].pts = 0; g_pbS[i].money = 0; g_pbS[i].ptsDay = 0;
      g_pbS[i].nDay = 0;
   }

   if(!HistorySelect(0, TimeCurrent() + 86400)) return;

   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0) continue;
      long mg = HistoryDealGetInteger(tk, DEAL_MAGIC);
      if(PB_StratIdx(mg) < 0) continue;          // not a strategy we track
      if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol) continue;

      long entry = HistoryDealGetInteger(tk, DEAL_ENTRY);
      long dtype = HistoryDealGetInteger(tk, DEAL_TYPE);
      if(dtype != DEAL_TYPE_BUY && dtype != DEAL_TYPE_SELL) continue;

      ulong  pid = (ulong)HistoryDealGetInteger(tk, DEAL_POSITION_ID);
      double px  = HistoryDealGetDouble(tk, DEAL_PRICE);
      double vol = HistoryDealGetDouble(tk, DEAL_VOLUME);
      if(pid == 0 || vol <= 0.0) continue;

      int j = PB_Find(pid);
      if(j < 0) j = PB_Add(pid);
      g_pbT[j].magic = mg;

      if(entry == DEAL_ENTRY_IN)
      {
         // a BUY deal opening a position means the position is long
         g_pbT[j].dir     = (dtype == DEAL_TYPE_BUY) ? 1 : -1;
         g_pbT[j].inVol  += vol;
         g_pbT[j].inPxVol += px * vol;
         if(g_pbT[j].tOpen == 0)
            g_pbT[j].tOpen = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
      }
      else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
      {
         g_pbT[j].outVol   += vol;
         g_pbT[j].outPxVol += px * vol;
         g_pbT[j].tClose    = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
      }
      // commission and swap are booked on whichever deal carries them
      g_pbT[j].money += HistoryDealGetDouble(tk, DEAL_PROFIT)
                      + HistoryDealGetDouble(tk, DEAL_SWAP)
                      + HistoryDealGetDouble(tk, DEAL_COMMISSION);
   }

   // ---- turn the ledger into the numbers on the box -----------------
   MqlDateTime nowS; TimeToStruct(TimeCurrent(), nowS);
   double eq = 0.0, peak = 0.0;

   for(int i = 0; i < ArraySize(g_pbT); i++)
   {
      if(g_pbT[i].inVol <= 0.0 || g_pbT[i].outVol <= 0.0) continue;  // still open
      g_pbT[i].closed = true;

      double inPx  = g_pbT[i].inPxVol  / g_pbT[i].inVol;
      double outPx = g_pbT[i].outPxVol / g_pbT[i].outVol;
      int    d     = g_pbT[i].dir;
      double pts   = d * (outPx - inPx);

      // FILL VS SIGNAL, and this is an entry-quality diagnostic, NOT a share
      // of the profit - see the E-131 note in the header. A trade with no
      // arm-price note (market entry, or the note was lost) is left out of the
      // average rather than counted as zero, which would drag it toward 0 and
      // say something false about the fills we can actually measure.
      double arm = PB_ArmPx(g_pbT[i].pid, 0.0);
      if(arm > 0.0)
      {
         g_pbFill += d * (arm - inPx);
         g_pbNFill++;
      }

      g_pbN++;
      if(pts > 0) g_pbWins++;
      g_pbPts   += pts;
      g_pbMoney += g_pbT[i].money;
      if(pts > g_pbBest)  g_pbBest  = pts;
      if(pts < g_pbWorst) g_pbWorst = pts;
      if(d > 0) { g_pbNLong++;  g_pbLong  += pts; }
      else      { g_pbNShort++; g_pbShort += pts; }
      if(g_pbFirst == 0 || g_pbT[i].tOpen < g_pbFirst) g_pbFirst = g_pbT[i].tOpen;

      eq += pts;
      if(eq > peak) peak = eq;
      if(peak - eq > g_pbMaxDD) g_pbMaxDD = peak - eq;

      MqlDateTime cs; TimeToStruct(g_pbT[i].tClose, cs);
      bool today = (cs.year == nowS.year && cs.mon == nowS.mon && cs.day == nowS.day);
      if(today)
      {
         g_pbNDay++;
         if(pts > 0) g_pbWinsDay++;
         g_pbPtsDay   += pts;
         g_pbMoneyDay += g_pbT[i].money;
      }

      int si = PB_StratIdx(g_pbT[i].magic);
      if(si >= 0)
      {
         g_pbS[si].n++;
         if(pts > 0) g_pbS[si].wins++;
         g_pbS[si].pts   += pts;
         g_pbS[si].money += g_pbT[i].money;
         if(today) { g_pbS[si].ptsDay += pts; g_pbS[si].nDay++; }
      }
   }
   g_pbLastScan = TimeCurrent();
   g_pbDirty    = false;
}

//==================== drawing ======================================
string PB_Num(double v, int d)
{
   return (v >= 0 ? "+" : "") + DoubleToString(v, d);
}

void PB_Obj(string name, int sub, string text, color c, int row, int col)
{
   string nm = g_pb.prefix + name;
   if(ObjectFind(0, nm) < 0)
   {
      ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN,     true);
      ObjectSetInteger(0, nm, OBJPROP_BACK,       false);
      ObjectSetString (0, nm, OBJPROP_FONT,       g_pb.font);
   }
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, sub > 0 ? g_pb.fontSize - 1 : g_pb.fontSize);
   ObjectSetInteger(0, nm, OBJPROP_CORNER,   g_pb.corner);

   // Everything below is laid out in BOX-LOCAL pixels - lx from the box's left
   // edge, ly from its top - and only the last step converts to the chart's
   // corner. MT5 measures XDISTANCE leftward from a right corner and YDISTANCE
   // upward from a lower one, so without this the box renders mirrored or
   // upside down depending on which corner it is pinned to. The first draft of
   // this file did exactly that.
   int lineH = g_pb.fontSize + 7;
   int lx = (col == 0) ? 10 : (col == 1) ? 152 : PB_BOX_W - 10;
   int ly = 10 + row * lineH;

   bool right = (g_pb.corner == CORNER_RIGHT_UPPER || g_pb.corner == CORNER_RIGHT_LOWER);
   bool lower = (g_pb.corner == CORNER_LEFT_LOWER  || g_pb.corner == CORNER_RIGHT_LOWER);

   int xd = right ? g_pb.x + (PB_BOX_W - lx) : g_pb.x + lx;
   int yd = lower ? g_pb.y + (PB_BoxH()  - ly) : g_pb.y + ly;

   // the anchor describes the TEXT, not the corner: column 0 starts at its
   // point, the two number columns end at theirs.
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR,
                    col == 0 ? ANCHOR_LEFT_UPPER : ANCHOR_RIGHT_UPPER);
   ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, xd);
   ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, yd);
   ObjectSetString (0, nm, OBJPROP_TEXT,  text);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, c);
}

void PB_Row(int row, string a, string b, color cb, string c)
{
   PB_Obj("r" + IntegerToString(row) + "a", 0, a, g_pb.cHead, row, 0);
   PB_Obj("r" + IntegerToString(row) + "b", 0, b, cb,         row, 1);
   PB_Obj("r" + IntegerToString(row) + "c", 1, c, g_pb.cDim,  row, 2);
}

void PB_Sep(int row, string caption)
{
   PB_Obj("r" + IntegerToString(row) + "a", 1, caption, g_pb.cDim, row, 0);
   PB_Obj("r" + IntegerToString(row) + "b", 1, "",      g_pb.cDim, row, 1);
   PB_Obj("r" + IntegerToString(row) + "c", 1, "",      g_pb.cDim, row, 2);
}

void PB_Destroy()
{
   ObjectsDeleteAll(0, g_pb.prefix);
}

//+------------------------------------------------------------------+
//| PB_Draw - call from OnTick. Rescans at most once every 3 seconds  |
//| unless a deal has just landed, so it costs nothing on a tick.     |
//+------------------------------------------------------------------+
void PB_Draw()
{
   if(!g_pb.show) return;
   if(g_pbDirty || TimeCurrent() - g_pbLastScan >= 3) PB_Scan();

   // ---- the open position, live -------------------------------------
   int    oDir = 0;
   double oPts = 0.0, oMoney = 0.0, oLots = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != g_pb.magic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)    continue;
      int d = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      oDir   = d;
      oLots += PositionGetDouble(POSITION_VOLUME);
      oPts  += d * (PositionGetDouble(POSITION_PRICE_CURRENT)
                  - PositionGetDouble(POSITION_PRICE_OPEN));
      oMoney += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   }

   string cur   = AccountInfoString(ACCOUNT_CURRENCY);
   double winPc = g_pbN > 0 ? 100.0 * g_pbWins / g_pbN : 0.0;
   double avg   = g_pbN > 0 ? g_pbPts / g_pbN : 0.0;
   double days  = 1.0;
   if(g_pbFirst > 0)
      days = MathMax(1.0, (double)(TimeCurrent() - g_pbFirst) / 86400.0);

   // THE BACKDROP IS DRAWN BELOW FROM g_pbMaxRows, so the compact layout has
   // to set it HERE - it used to set it 55 lines further down, after the
   // rectangle had already been sized for the full 15-row panel. With four
   // magics registered that made the backdrop 324px tall while the rows were
   // laid out for 212px, and because the box anchors from a corner the rows
   // sat about 112px inside their own frame.
   if(g_pb.compact)
   {
      int extraNow = ArraySize(g_pbS) > 1 ? ArraySize(g_pbS) + 1 : 0;
      g_pbMaxRows = 8 + extraNow;
   }
   else
      g_pbMaxRows = 15 + ArraySize(g_pbS);   // 15 fixed plus one per strategy

   // ---- background ---------------------------------------------------
   string bg = g_pb.prefix + "bg";
   if(ObjectFind(0, bg) < 0)
   {
      ObjectCreate(0, bg, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, bg, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, bg, OBJPROP_HIDDEN,     true);
      ObjectSetInteger(0, bg, OBJPROP_BACK,       false);
      ObjectSetInteger(0, bg, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, bg, OBJPROP_STYLE,      STYLE_SOLID);
      ObjectSetInteger(0, bg, OBJPROP_WIDTH,      1);
   }
   ObjectSetInteger(0, bg, OBJPROP_CORNER,    g_pb.corner);
   ObjectSetInteger(0, bg, OBJPROP_XDISTANCE, g_pb.x);
   ObjectSetInteger(0, bg, OBJPROP_YDISTANCE, g_pb.y);
   ObjectSetInteger(0, bg, OBJPROP_XSIZE,     PB_BOX_W);
   ObjectSetInteger(0, bg, OBJPROP_YSIZE,     PB_BoxH());
   ObjectSetInteger(0, bg, OBJPROP_BGCOLOR,   g_pb.cBg);
   ObjectSetInteger(0, bg, OBJPROP_COLOR,     g_pb.cFrame);

   // ---- the rows -----------------------------------------------------
   // The row count is dynamic because the strategy section grows with however
   // many magics are registered, so every row index is taken from one counter
   // rather than hard-coded. Hard-coded indices are how a panel ends up with
   // two rows drawn on top of each other.
   int r = 0;
   PB_Obj("title",  0, g_pb.title, g_pb.cVal, r, 0);
   PB_Obj("titleb", 0, "",         g_pb.cVal, r, 1);
   PB_Obj("state",  1, oDir == 0 ? "flat" : (oDir > 0 ? "LONG" : "SHORT"),
          oDir == 0 ? g_pb.cDim : (oDir > 0 ? g_pb.cPos : g_pb.cNeg), r, 2);
   r++;

   // ================== COMPACT: TODAY FIRST ==============================
   // Veer: "make sure itss for the day only so from 12 am till live", and
   // "nothing overboard". The full box below is fifteen rows and leads with an
   // all-time total, so the first number his eye lands on is the wrong one -
   // that is why a four-day panel read as one session in his screenshot.
   //
   // This layout puts TODAY at the top in the largest type the box has, keeps
   // the open position visible, and files everything cumulative under one
   // "since" line. Six rows. The per-strategy split only appears when more than
   // one magic is actually registered, because a "by strategy" header over a
   // single row is furniture.
   //
   // The day boundary is the broker's calendar day on the deal's CLOSE time
   // (PB_Scan), which is the midnight his account rolls over on.
   if(g_pb.compact)
   {
      // Veer: "make one massive profit box's and show pnl per ea so i can just
      // screenshot that". Every EA now registers all four magics, so this block
      // is the screenshot: one row per EA, today's points and trade count, on
      // whichever chart he happens to be looking at.
      // g_pbMaxRows is already set above, BEFORE the backdrop was drawn.
      // +1 over the rows written so the frame has bottom padding.
      int extra = ArraySize(g_pbS) > 1 ? ArraySize(g_pbS) + 1 : 0;

      PB_Row(r++, "TODAY", PB_Num(g_pbPtsDay, 1) + " pts",
             g_pbPtsDay >= 0 ? g_pb.cPos : g_pb.cNeg,
             PB_Num(g_pbMoneyDay, 2) + " " + cur);
      PB_Row(r++, "trades", IntegerToString(g_pbNDay), g_pb.cVal,
             g_pbNDay > 0 ? IntegerToString(g_pbWinsDay) + "W "
                            + IntegerToString(g_pbNDay - g_pbWinsDay) + "L  "
                            + DoubleToString(100.0 * g_pbWinsDay
                                             / MathMax(g_pbNDay, 1), 0) + "%"
                          : "none yet today");
      PB_Row(r++, oDir == 0 ? "open" : "open " + (oDir > 0 ? "LONG" : "SHORT"),
             oDir == 0 ? "-" : PB_Num(oPts, 1) + " pts",
             oDir == 0 ? g_pb.cDim : (oPts >= 0 ? g_pb.cPos : g_pb.cNeg),
             oDir == 0 ? "flat" : PB_Num(oMoney, 2) + " " + cur
                                  + "  " + DoubleToString(oLots, 2) + " lots");

      if(extra > 0)
      {
         PB_Sep(r++, "-- today, by strategy --");
         for(int i = 0; i < ArraySize(g_pbS); i++)
            PB_Row(r++, g_pbS[i].label, PB_Num(g_pbS[i].ptsDay, 1),
                   g_pbS[i].nDay == 0 ? g_pb.cDim
                       : (g_pbS[i].ptsDay >= 0 ? g_pb.cPos : g_pb.cNeg),
                   g_pbS[i].nDay == 0 ? "-"
                       : IntegerToString(g_pbS[i].nDay) + " tr");
      }

      PB_Sep(r++, "-- since " + (g_pbFirst > 0
             ? TimeToString(g_pbFirst, TIME_DATE) : "start") + " --");
      PB_Row(r++, "points", PB_Num(g_pbPts, 1),
             g_pbPts >= 0 ? g_pb.cPos : g_pb.cNeg,
             IntegerToString(g_pbN) + " tr  "
             + DoubleToString(winPc, 0) + "%W  " + PB_Num(g_pbMoney, 2));
      PB_Row(r++, "max DD", DoubleToString(-g_pbMaxDD, 1), g_pb.cNeg,
             "spread " + DoubleToString(SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                      - SymbolInfoDouble(_Symbol, SYMBOL_BID), 2));

      for(int i = r; i < r + 14; i++)
      {
         ObjectDelete(0, g_pb.prefix + "r" + IntegerToString(i) + "a");
         ObjectDelete(0, g_pb.prefix + "r" + IntegerToString(i) + "b");
         ObjectDelete(0, g_pb.prefix + "r" + IntegerToString(i) + "c");
      }
      ChartRedraw(0);
      return;
   }

   // POINTS FIRST. E-074.
   PB_Row(r++, "points", PB_Num(g_pbPts, 1),
          g_pbPts >= 0 ? g_pb.cPos : g_pb.cNeg,
          PB_Num(g_pbMoney, 2) + " " + cur);
   PB_Row(r++, "today",  PB_Num(g_pbPtsDay, 1),
          g_pbPtsDay >= 0 ? g_pb.cPos : g_pb.cNeg,
          PB_Num(g_pbMoneyDay, 2) + " " + cur);
   PB_Row(r++, "trades", IntegerToString(g_pbN), g_pb.cVal,
          DoubleToString(g_pbN / days, 1) + "/day");
   PB_Row(r++, "win rate", DoubleToString(winPc, 1) + "%", g_pb.cVal,
          IntegerToString(g_pbWins) + "W " + IntegerToString(g_pbN - g_pbWins) + "L");
   PB_Row(r++, "avg trade", PB_Num(avg, 3),
          avg >= 0 ? g_pb.cPos : g_pb.cNeg, "points");

   // ---- one row per strategy. This is the split Veer asked for, and it is
   // the one that means something: separate magics, separate books.
   PB_Sep(r++, "-- by strategy --");
   for(int i = 0; i < ArraySize(g_pbS); i++)
   {
      string note = g_pbS[i].n == 0
                  ? "no trades yet"
                  : IntegerToString(g_pbS[i].n) + " tr  "
                    + DoubleToString(100.0 * g_pbS[i].wins / g_pbS[i].n, 0) + "%W  "
                    + PB_Num(g_pbS[i].money, 2);
      PB_Row(r++, g_pbS[i].label, PB_Num(g_pbS[i].pts, 1),
             g_pbS[i].n == 0 ? g_pb.cDim
                             : (g_pbS[i].pts >= 0 ? g_pb.cPos : g_pb.cNeg), note);
   }

   // ---- entry quality. NOT a share of the profit - see the E-131 note at the
   // top of this file. It is how much better the resting limit filled than the
   // market at the moment the EA armed, and it is here so a broker that fills
   // limits late shows up as a falling number instead of as a mystery.
   PB_Sep(r++, "-- entry quality --");
   PB_Row(r++, "fill vs signal",
          g_pbNFill > 0 ? PB_Num(g_pbFill / g_pbNFill, 3) : "-",
          g_pbNFill > 0 && g_pbFill >= 0 ? g_pb.cPos : g_pb.cDim,
          g_pbNFill > 0 ? "pts/trade, " + IntegerToString(g_pbNFill) + " limits"
                        : "market entries");

   PB_Sep(r++, "-- risk --");
   PB_Row(r++, "best / worst",
          PB_Num(g_pbBest, 1) + " / " + DoubleToString(g_pbWorst, 1),
          g_pb.cVal, "points");
   PB_Row(r++, "max drawdown", DoubleToString(-g_pbMaxDD, 1), g_pb.cNeg, "points");
   PB_Row(r++, "long / short",
          PB_Num(g_pbLong, 1) + " / " + PB_Num(g_pbShort, 1), g_pb.cVal,
          IntegerToString(g_pbNLong) + " / " + IntegerToString(g_pbNShort));

   PB_Sep(r++, "-- open --");
   PB_Row(r++, oDir == 0 ? "no position" : "unrealised",
          oDir == 0 ? "-" : PB_Num(oPts, 1),
          oDir == 0 ? g_pb.cDim : (oPts >= 0 ? g_pb.cPos : g_pb.cNeg),
          oDir == 0 ? "" : PB_Num(oMoney, 2) + " " + cur);
   PB_Row(r++, "lots", oDir == 0 ? "-" : DoubleToString(oLots, 2), g_pb.cVal,
          "spread " + DoubleToString(SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                   - SymbolInfoDouble(_Symbol, SYMBOL_BID), 2));

   // any row left over from a previous, taller draw
   for(int i = r; i < r + 4; i++)
   {
      ObjectDelete(0, g_pb.prefix + "r" + IntegerToString(i) + "a");
      ObjectDelete(0, g_pb.prefix + "r" + IntegerToString(i) + "b");
      ObjectDelete(0, g_pb.prefix + "r" + IntegerToString(i) + "c");
   }

   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| PB_Init - call from OnInit, after the magic number is known.      |
//+------------------------------------------------------------------+
void PB_Init(string prefix, string title, long magic, bool show,
             int corner = CORNER_RIGHT_LOWER, int x = 12, int y = 12,
             string label = "")
{
   ArrayFree(g_pbS);
   PB_AddStrategy(magic, label == "" ? title : label);

   g_pb.prefix   = prefix;
   g_pb.title    = title;
   g_pb.magic    = magic;
   g_pb.show     = show;
   g_pb.corner   = corner;
   g_pb.x        = x;
   g_pb.y        = y;
   g_pb.compact  = true;      // six rows, today first. false = the full box.
   g_pb.fontSize = 9;
   g_pb.font     = "Consolas";
   g_pb.cBg      = C'14,22,33';
   g_pb.cFrame   = C'42,58,77';
   g_pb.cHead    = C'143,163,184';
   g_pb.cVal     = C'230,237,245';
   g_pb.cPos     = C'0,176,255';
   g_pb.cNeg     = C'255,59,92';
   g_pb.cDim     = C'92,112,137';

   PB_Destroy();
   PB_Prune();
   g_pbDirty = true;
}

#endif  // PROFITBOX_MQH

//==============================================================
// END ProfitBox.mqh
//==============================================================
//==============================================================
// BEGIN TimeframeGuard.mqh  (spliced by JARVIS/tools/build_ea.py - edit the .mqh, not this)
//==============================================================
//+------------------------------------------------------------------+
//|  TimeframeGuard.mqh                                              |
//|                                                                  |
//|  Veer, and this is a hard rule, not a preference:                 |
//|    "we trade m1 m5 m15 and m3 maybe... we simply LOOK AT higher   |
//|     timeframes we don't trade them"                               |
//|                                                                  |
//|  Two of these EAs read _Period and will trade whatever chart they |
//|  are dropped on. Nothing stopped an H1 or H4 chart from becoming  |
//|  an H1 or H4 strategy - a defect, because every number any of     |
//|  them is quoted at was measured on M1, and the cost picture is    |
//|  completely different up there (E-132: the same 0.40 spread is    |
//|  0.220 of ATR on M1 and 0.047 on M15).                            |
//|                                                                  |
//|  This refuses to start above M30. It is deliberately a REFUSAL    |
//|  and not a warning: a warning in the Experts log is something you |
//|  find out about after the trades.                                 |
//|                                                                  |
//|  Higher timeframes are still read for CONTEXT wherever an EA does |
//|  that. Reading H4 is not trading H4.                              |
//|                                                                  |
//|  WHAT THE CONTEXT IS ACTUALLY WORTH, so nobody re-adds it on a    |
//|  hunch (E-133, 157,051 real M1 bars, nine variants):              |
//|    M1 direction only        981 trades   97.1 pts   +0.0990 each  |
//|    M1 + H1 must agree       850          80.2       +0.0943       |
//|    M1 + H4 must agree       851          93.1       +0.1094       |
//|    M1 + H1 + H4             582          53.9       +0.0926       |
//|    H1 alone                 942          94.3       +0.1001       |
//|    H4 alone                 937          82.6       +0.0882       |
//|  NOT ONE of them beats reading direction off M1. A trend filter   |
//|  is worth a great deal - without any, the same entries make 48.4  |
//|  points instead of 97.1 (E-127) - but the best clock to read it   |
//|  from is the one being traded.                                    |
//+------------------------------------------------------------------+
#property strict

#ifndef TIMEFRAME_GUARD_MQH
#define TIMEFRAME_GUARD_MQH

// The ceiling is a SETTING, not a constant. Veer: "i'm putting all ea on m1
// it can trade based of whatever it wants... i wanted to trade m1 to m30
// possibly h1 possibly if good setup". The first version of this file hard
// refused above M30, which was me turning a default into a rule. The default
// is still M30 because that is where every measurement lives, but raising it
// is his call to make, and the log says what he is giving up when he does.
bool TfAllowed(ENUM_TIMEFRAMES tf, ENUM_TIMEFRAMES ceiling)
{
   if(tf == PERIOD_MN1) return false;
   int mins = PeriodSeconds(tf) / 60;
   int cap  = PeriodSeconds(ceiling) / 60;
   return mins > 0 && cap > 0 && mins <= cap;
}

// Returns false and prints why. Call it first in OnInit and return
// INIT_FAILED on false.
bool TfGuard(string ea, ENUM_TIMEFRAMES ceiling = PERIOD_M30)
{
   if(TfAllowed((ENUM_TIMEFRAMES)_Period, ceiling)) return true;
   PrintFormat("[%s] REFUSING TO START on %s - above the configured ceiling %s.",
               ea, EnumToString((ENUM_TIMEFRAMES)_Period),
               EnumToString(ceiling));
   Print("Raise InpMaxTF if you mean to do this. It is your call, but read "
         "the next two lines first.");
   Print("This is an M1-M30 system. Every number it is quoted at was measured "
         "on M1 and none of it transfers upward: the spread is a far smaller "
         "fraction of the move up there, the stop and trail are sized in an "
         "ATR that means something different, and the trade count collapses.");
   Print("Higher timeframes are for CONTEXT. Reading H4 is not trading H4. "
         "E-133 measured H1 and H4 as direction sources against M1 across nine "
         "variants and not one of them beat M1.");
   Print("Attach this to M1, M3, M5, M15 or M30, or raise InpMaxTF deliberately.");
   return false;
}

#endif  // TIMEFRAME_GUARD_MQH

//==============================================================
// END TimeframeGuard.mqh
//==============================================================
#define SS_BUILD "2.00"

input group "=== SAFETY ==="
input bool   InpDemoOnly     = true;    // refuse to start on a live account
input long   InpMagic        = 990077;  // magic number
input ENUM_TIMEFRAMES InpMaxTF = PERIOD_M30;  // highest chart this will start on

input group "=== THE SETUP ==="
input int    InpPivotBars    = 3;       // swing needs this many bars either side.
                                        // E-179: a smaller pivot is better the
                                        // faster the clock (2R target, ATR/trade:
                                        // 15m +0.208 at 3 vs +0.126 at 5; 1h
                                        // +0.050 at 3 vs -0.005 at 5), and a
                                        // 12-bar pivot is negative on every
                                        // clock. Raise it to 8 on H4+.
input double InpSweepAtr     = 0.10;    // sweep must clear the level by this x ATR
input double InpWickCut      = 0.646;   // sweep body/range must be under this
input bool   InpUseDisp      = false;   // OFF. E-139: an EA cannot execute this - see below
input double InpDispCutNote  = 0.0;     // (unused; kept so the group reads in order)
input double InpDispCut      = -1.4909; // only used if InpUseDisp is switched on
input int    InpSetupLife    = 120;     // give up on a setup after N bars

input group "=== WHICH SIGNALS (E-149: read this before turning them all on) ==="
// The Pine had four signals and this EA had one. That is the P92 defect exactly
// - a 52% signal gap between a chart and its EA that sat unnoticed for 180
// commits - so all four are here now and the chart and this file agree.
//
// E-149 simulated all four sharing ONE position, which is what actually runs.
// More signals = more total points and a THINNER per-trade edge, and every
// extra trade pays the round trip again. Total points by exit slippage:
//                       0.00     0.02     0.05     0.10
//   M1 sweep alone     449.3    369.2    249.0     48.7
//   M1 all four        556.1    370.0     91.0   -374.0   <- crosses at 0.02
//   M5 sweep alone     258.1    240.1    213.2    168.3
//   M5 all four        322.6    282.9    223.3    123.9   <- crosses at ~0.07
// ON M5 RUN ALL FOUR. ON M1, IF YOUR FILLS SLIP MORE THAN ~0.02 POINTS, TURN
// THE EXTRAS OFF. 85 trades a day pays 85 round trips a day. The profit box's
// "fill vs signal" row is how you measure which world you are in.
input bool   InpUseSweep     = true;    // the only one positive under E-151 fills
input bool   InpUseBR        = false;   // E-151: -0.0095/trade under achievable fills
input bool   InpUseObDetect  = false;   // E-151: -0.0089/trade under achievable fills
input bool   InpUseObReturn  = false;   // E-151: -0.0319/trade under achievable fills

input group "=== BREAK + RETEST ==="
input double InpBrAtr        = 0.10;    // a CLOSE this far through the level is a break
input double InpBrTol        = 0.20;    // the retest must come this close (ATR)
input int    InpBrWait       = 60;      // bars allowed for break, retest, resume

input group "=== ORDER BLOCKS (wugamlo rule, MPL-2.0) ==="
input int    InpObLen        = 3;       // candles after the OB candle. 3 beat 5 everywhere
input double InpObThrPct     = 0.0;     // minimum % move to qualify

input group "=== RISK — read E-138 before changing anything here ==="
input double InpStopBufAtr   = 0.30;    // stop this far beyond the sweep extreme
input double InpMaxRiskAtr   = 1.2;     // REFUSE the setup if the stop is wider
input double InpGiveBack     = 0.25;    // give back this much of the best excursion
input double InpHiWinR       = 0.0;     // HIGH WIN RATE: fixed target at this R (0 = off)
                                        // At 0.5R you need 67% to break even, at 0.25R you need 80%.
                                        // E-136: the spread caps the win rate near 81% on this setup,
                                        // so 80% at 0.25R is break-even, not profit. Watch both numbers.
input double InpBeAtR        = 1.0;     // move the stop to TRUE breakeven at this R (0 = never)
input double InpTrailAtR     = 1.0;     // arm the give-back trail at this R (0 = from the first tick)
input int    InpMaxBars      = 240;     // time exit, in chart bars
input bool   InpUseFixedLots = true;
input double InpFixedLots    = 0.01;    // E-081: 0.01 is GBP0.787/point and is the floor
input double InpRiskPct      = 0.50;    // used only when InpUseFixedLots = false
input double InpMaxSpreadPts = 0.60;    // refuse to arm when the spread is wider

input group "=== SESSION (E-161/E-162) ==="
// OFF by default. The London/New York overlap is the best session PER TRADE on
// both clocks and it holds out of sample - but at the slippage you probably
// have (0.02-0.05) taking every session banks MORE TOTAL money, and only past
// about 0.10 does the overlap alone win. Measured, total points:
//   M1 session      0.00    0.02    0.05    0.10   |  M5      0.00    0.05    0.10
//     Asia          54.5    33.6     2.3   -49.9   |         22.0     9.2    -3.5
//     OVERLAP       79.5    64.1    40.9    +2.4   |         77.1    67.7    58.3
//     all          288.6   207.7    86.3  -115.9   |        171.3   125.9    80.6
// This is a DIAL for after the demo run measures your fills, not a default.
input bool   InpOverlapOnly  = false;   // trade the London/NY overlap only
input int    InpOverlapFrom  = 12;      // server-time hour, inclusive
input int    InpOverlapTo    = 16;      // server-time hour, exclusive

input group "=== GUARDS ==="
input double InpMaxDayLossPct = 3.0;
input double InpMaxDDPct      = 6.0;
input int    InpMaxTradesDay  = 60;     // it runs ~19/day; this is a circuit breaker
input bool   InpFlattenOnBreach = true; // close open trades when a limit breaks
input bool   InpVerbose       = true;
input bool   InpJournal       = true;    // CSV of every fill: asked vs got

input group "=== THE PROFIT BOX ==="
input bool   InpShowProfitBox = true;
input int    InpBoxCorner     = 1;      // 0 top-left, 1 TOP RIGHT, 2 bottom-left, 3 bottom-right
input int    InpBoxX          = 12;
input int    InpBoxY          = 12;
input long   InpTrackMagic2   = 880041; // ZoneSniper, if you run it too
input string InpTrackLabel2   = "ZONE  st+liq";
input long   InpTrackMagic3   = 770001; // SuperTrendSniper
input string InpTrackLabel3   = "SUPERTREND";
input long   InpTrackMagic4  = 770069;  // LIQUIDITY, so ONE box shows every EA
input string InpTrackLabel4  = "LIQUIDITY";

//==================== STATE ========================================
// One live setup per side. A swing HIGH is sell-side liquidity: the sweep runs
// UP through it and the trade is SHORT back through the level.
struct Setup
{
   bool     live;
   double   lvl;        // the level price
   double   atr;        // ATR at the level's confirmation - frozen, not live
   int      born;       // bar the level was confirmed
   int      swept;      // bar the sweep happened, -1 until then
   double   ext;        // the sweep's running extreme
   double   disp;       // the sweep bar's body / range
};
Setup g_sell, g_buy;

// ---- BREAK + RETEST. Its own level tracking, kept separate from the sweep's
// so the two can never disturb each other: the sweep consumes its level on a
// fill and this must not inherit that.
struct BrSetup
{
   bool     live;
   double   lvl;
   double   atr;
   int      state;      // 0 watching, 1 broken, 2 retested and armed
   int      bar;
   double   trig;
   double   stop;
};
BrSetup g_brUp, g_brDn;   // brUp: a swing HIGH broken upward -> BUY the retest

// ---- ORDER BLOCKS. The last opposing candle before a run.
struct ObZone
{
   bool     live;
   double   top;
   double   bot;
   double   atr;
   int      born;
};
ObZone g_obB, g_obS;
int    g_armSrc = 0;      // 1 sweep, 2 break+retest, 3 OB detect, 4 OB return
int    g_armSide = 0;     // E-164: -1 sell setup armed, +1 buy, 0 none

int      g_atr = INVALID_HANDLE;
datetime g_lastBar = 0;
ulong    g_pend = 0;        // the resting limit
int      g_pendDir = 0;
double   g_pendPx = 0.0;    // the price we ASKED for, for the slippage column

double   g_peakPrice = 0.0; // best excursion of the open position
datetime g_posBarTime = 0;  // F10: a TIME, because Bars() plateaus and jumps
double   g_lastSl = 0.0;    // F7: the last stop we successfully asked for
datetime g_lastTry = 0;     // F7: throttle on exit retries
double   g_posInit = 0.0;   // the ORIGINAL stop, so R can be measured
double   g_posEntry = 0.0;
int      g_posDir = 0;

double   g_dayStartEq = 0.0, g_peakEq = 0.0, g_floor = 0.0;
int      g_dayStamp = 0, g_tradesToday = 0, g_refusedToday = 0;
ulong    g_lastPosId = 0;   // F20: count trades, not fills
bool     g_lockDay = false, g_lockPerm = false;

void Log(string s) { if(InpVerbose) Print("[SS] ", s); }

//==================== EXECUTION JOURNAL ============================
// THE MEASUREMENT THIS PROJECT HAS NEVER HAD.
//
// Every backtest in this repo charges cost through one assumed number -
// spread/ATR = 0.11 (E-132, E-173) - and assumes slippage is exactly zero.
// Neither has ever been measured on Veer's broker, and both are load-bearing:
// E-149's whole M5 book is +24.2 points and dies at 0.02 points of slippage,
// so the difference between an edge and a fantasy is a quantity nobody in this
// project has ever observed.
//
// One row per fill and per close, with the price we ASKED for, the price we
// GOT, and the spread at that instant. A week on demo turns the biggest
// assumption in the research into a fact. Read it with
// JARVIS/research/read_exec.py.
//
// FILE_SHARE_READ|FILE_SHARE_WRITE so it can be opened in Excel while running.
// Which signal armed the trade, so the journal can be split by source later -
// E-149 showed the four sources behave very differently from each other.
string SrcName(int src)
{
   if(src == 1) return "sweep";
   if(src == 2) return "break+retest";
   if(src == 3) return "ob-detect";
   if(src == 4) return "ob-return";
   return "unknown";
}

// One file PER EA. Four EAs on four charts sharing one handle is a corrupt
// CSV the first time two of them fill in the same second.
string JournalName() { return "JARVIS_exec_SweepSniper_" + _Symbol + ".csv"; }

// The price we ASKED for, read off the order rather than off a global: a
// global is wrong for an order adopted after a restart and wrong again after
// a requote. g_pendPx is kept only as the fallback when the lookup fails.
double AskedPrice(ulong dealTicket)
{
   ulong ord = (ulong)HistoryDealGetInteger(dealTicket, DEAL_ORDER);
   if(ord == 0 || !HistoryOrderSelect(ord)) return g_pendPx;
   double p = HistoryOrderGetDouble(ord, ORDER_PRICE_OPEN);
   return p > 0.0 ? p : g_pendPx;
}

void JRow(string event, int dir, double reqPx, double fillPx, double lots,
          double sl, double tp, double profit, ulong posId, string note)
{
   if(!InpJournal) return;
   int h = FileOpen(JournalName(), FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI
                    |FILE_SHARE_READ|FILE_SHARE_WRITE, ',');
   if(h == INVALID_HANDLE) return;
   if(FileSize(h) == 0)
      FileWrite(h, "utc", "ea", "symbol", "tf", "event", "dir", "req_px",
                   "fill_px", "slip_pts", "spread_pts", "atr", "lots",
                   "sl", "tp", "profit", "pos_id", "note");
   FileSeek(h, 0, SEEK_END);
   int    dg  = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   // Signed so that POSITIVE always means WORSE than asked, for both
   // directions: a buy filled above its level and a sell filled below it both
   // read positive. Averaging a column that mixes the two signs would report
   // roughly zero slippage on a broker that slips every fill.
   double slip = (reqPx > 0.0 && fillPx > 0.0) ? dir * (fillPx - reqPx) : 0.0;
   FileWrite(h, TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
             "SweepSniper", _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
             event, (string)dir, DoubleToString(reqPx, dg),
             DoubleToString(fillPx, dg), DoubleToString(slip, dg),
             DoubleToString(ask - bid, dg), DoubleToString(ATR(), dg),
             DoubleToString(lots, 2), DoubleToString(sl, dg),
             DoubleToString(tp, dg), DoubleToString(profit, 2),
             (string)posId, note);
   FileClose(h);
}

double ATR()
{
   double b[];
   if(CopyBuffer(g_atr, 0, 1, 1, b) != 1) return 0.0;
   return b[0];
}

int BarNo() { return Bars(_Symbol, _Period); }

//==================== PIVOTS =======================================
// A pivot is only KNOWN InpPivotBars bars after it forms. This checks the bar
// at that offset, so the level is real at the moment it is acted on. Reading it
// any earlier is look-ahead and it is the single easiest way to fake this
// strategy into working.
bool ConfirmedPivot(int k, bool wantHigh, double &px)
{
   int c = k + 1;                      // the candidate, k bars back from bar 1
   double v = wantHigh ? iHigh(_Symbol, _Period, c) : iLow(_Symbol, _Period, c);
   for(int i = 1; i <= k; i++)
   {
      if(wantHigh)
      {
         if(iHigh(_Symbol, _Period, c - i) > v) return false;
         if(iHigh(_Symbol, _Period, c + i) > v) return false;
      }
      else
      {
         if(iLow(_Symbol, _Period, c - i) < v) return false;
         if(iLow(_Symbol, _Period, c + i) < v) return false;
      }
   }
   px = v;
   return true;
}

void ResetSetup(Setup &s)
{
   s.live = false; s.lvl = 0.0; s.atr = 0.0; s.born = 0;
   s.swept = -1; s.ext = 0.0; s.disp = 1.0;
}

//==================== POSITION / ORDER HELPERS =====================
int PosCount()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == InpMagic
         && PositionGetString(POSITION_SYMBOL) == _Symbol) n++;
   }
   return n;
}

// F1. A ulong holding "the" pending ticket is not a record of what is resting
// at the broker, and three ordinary events make the two disagree: a failed
// OrderDelete (which used to zero the ticket anyway), an OnInit from a restart
// or a parameter change, and a ResultOrder() of 0 on an async placement. Each
// one ends with TryArm believing it is flat and arming a SECOND order on top of
// a live one. Both can fill. That doubles the position and doubles the risk cap
// the whole of E-138 exists to enforce. So: count the orders at the broker.
int PendingCount()
{
   int n = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol)  continue;
      n++;
   }
   return n;
}

bool OrderAlive(ulong tk) { return PendingCount() > 0; }

// Deletes EVERY order of ours, and says so when it cannot. A cancel that was
// rejected is not a cancel: the old code forgot it, and the guards call this,
// so a locked-out day could still open a trade an hour later.
void KillPending(string why)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol)  continue;
      if(trade.OrderDelete(tk))
         Log(StringFormat("cancelled resting order %I64u: %s", tk, why));
      else
         Log(StringFormat("COULD NOT CANCEL order %I64u (%s): %d %s "
                          "- IT IS STILL LIVE AND CAN STILL FILL",
                          tk, why, trade.ResultRetcode(),
                          trade.ResultRetcodeDescription()));
   }
   g_pend = 0;
   g_pendDir = 0;
}

// F11. Neither EA ever called OrderCalcMargin. On a small account the order
// simply comes back NO_MONEY, the setup stays live, and the identical order is
// re-sent every bar until it expires - 120 bars of the same rejection on M1,
// with nothing in the log saying the account is the problem.
bool CanAfford(int dir, double lots, double price)
{
   double need = 0.0;
   ENUM_ORDER_TYPE t = (dir > 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!OrderCalcMargin(t, _Symbol, lots, price, need)) return true;  // unknown: try
   double free = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   if(need <= free * 0.90) return true;
   static datetime told = 0;
   if(TimeCurrent() - told > 3600)
   {
      told = TimeCurrent();
      PrintFormat("[SS] REFUSED: %.2f lots needs %.2f margin and only %.2f is "
                  "free. E-081 - 0.01 lots cannot be made smaller, so it is the "
                  "ACCOUNT that has to be bigger. Not retrying this every bar.",
                  lots, need, free);
   }
   return false;
}

double MinStopDist()
{
   long lv = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   return (double)lv * _Point;
}

// F6. FREEZE LEVEL. Inside this band the broker refuses BOTH a stop
// modification and an EA close. It was read nowhere in this project, and the
// give-back trail places its stop close to price by construction - which is
// exactly where the band is. When it bites, the trail silently stops moving
// and the market exit silently does not happen, while the log says both worked.
double FreezeDist()
{
   long lv = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   return (double)lv * _Point;
}

// F18. Round to the symbol's TICK SIZE, not just its digit count. On XAUUSD
// they are the same; on an instrument with a 0.05 tick they are not, and the
// server rejects a correctly-rounded-to-digits price it cannot quote.
double NormPx(double p)
{
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   int    dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   if(ts > 0.0) p = MathRound(p / ts) * ts;
   return NormalizeDouble(p, dg);
}

double LotFor(double stopPts)
{
   double vmn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vst = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   // F12. The fixed-lot path returned the input untouched. If this broker's
   // minimum or step on gold is not 0.01, every order comes back 10014
   // INVALID_VOLUME and the EA never trades while the log fills with retcodes.
   if(InpUseFixedLots)
   {
      double lf = InpFixedLots;
      if(vst > 0.0) lf = MathFloor(lf / vst + 1e-9) * vst;
      if(lf < vmn) lf = vmn;
      if(lf > vmx) lf = vmx;
      return NormalizeDouble(lf, 2);
   }
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0.0 || ts <= 0.0 || stopPts <= 0.0) return InpFixedLots;
   double risk = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0;
   double perLot = stopPts / ts * tv;
   if(perLot <= 0.0) return InpFixedLots;
   double lots = risk / perLot;
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(st > 0.0) lots = MathFloor(lots / st) * st;
   if(lots < mn) lots = mn;
   if(lots > mx) lots = mx;
   return lots;
}

//==================== THE SETUP MACHINE ============================
void UpdateSetups()
{
   // F17. iHigh/iLow return 0.0 for a bar that is not in the series yet - the
   // first ticks after attach, or after a history purge - and 0.0 satisfies
   // every comparison in ConfirmedPivot, so a "confirmed pivot" is accepted at
   // price ZERO. It is then instantly "swept", and ResetSetup destroys that
   // side's real level. NewObBlock already guards this; this did not.
   if(Bars(_Symbol, _Period) < 2 * InpPivotBars + 5) return;
   double a = ATR();
   if(a <= 0.0) return;
   int bar = BarNo();

   // ---- a new confirmed pivot replaces any unfilled setup on that side ----
   double px;
   if(ConfirmedPivot(InpPivotBars, true, px))
   {
      if(!g_sell.live || MathAbs(px - g_sell.lvl) > _Point)
      {
         ResetSetup(g_sell);
         g_sell.live = true; g_sell.lvl = px; g_sell.atr = a; g_sell.born = bar;
      }
   }
   if(ConfirmedPivot(InpPivotBars, false, px))
   {
      if(!g_buy.live || MathAbs(px - g_buy.lvl) > _Point)
      {
         ResetSetup(g_buy);
         g_buy.live = true; g_buy.lvl = px; g_buy.atr = a; g_buy.born = bar;
      }
   }

   double h1 = iHigh(_Symbol, _Period, 1);
   double l1 = iLow(_Symbol, _Period, 1);
   double o1 = iOpen(_Symbol, _Period, 1);
   double c1 = iClose(_Symbol, _Period, 1);
   double r1 = h1 - l1;

   // ---- the sweep ---------------------------------------------------------
   if(g_sell.live && g_sell.swept < 0 && h1 >= g_sell.lvl + InpSweepAtr * g_sell.atr)
   {
      g_sell.swept = bar;
      g_sell.ext = h1;
      g_sell.disp = (r1 > 0.0) ? MathAbs(c1 - o1) / r1 : 1.0;
   }
   if(g_buy.live && g_buy.swept < 0 && l1 <= g_buy.lvl - InpSweepAtr * g_buy.atr)
   {
      g_buy.swept = bar;
      g_buy.ext = l1;
      g_buy.disp = (r1 > 0.0) ? MathAbs(c1 - o1) / r1 : 1.0;
   }

   // ---- after a sweep the run can keep extending, and the stop goes with it
   if(g_sell.live && g_sell.swept >= 0 && bar > g_sell.swept)
      g_sell.ext = MathMax(g_sell.ext, h1);
   if(g_buy.live && g_buy.swept >= 0 && bar > g_buy.swept)
      g_buy.ext = MathMin(g_buy.ext, l1);

   // ---- a setup that never came back is not a signal ----------------------
   if(g_sell.live && bar - g_sell.born > InpSetupLife) ResetSetup(g_sell);
   if(g_buy.live  && bar - g_buy.born  > InpSetupLife) ResetSetup(g_buy);
}

// the return leg's displacement, bar 1 against bar 3 - the same pair the
// measurement used (j against j-2)
bool DispOk(int dir, double a)
{
   if(!InpUseDisp) return true;
   double gap = (dir > 0)
      ? iLow(_Symbol, _Period, 1) - iHigh(_Symbol, _Period, 3)
      : iLow(_Symbol, _Period, 3) - iHigh(_Symbol, _Period, 1);
   return (gap / a) >= InpDispCut;
}

//==================== BREAK + RETEST ===============================
// The level is DISRESPECTED by a CLOSE, price comes back, holds, then resumes.
// The opposite of the sweep, which fades a level taken by a WICK - and the wick
// filter is exactly what separates the two cases.
void ResetBr(BrSetup &b)
{
   b.live = false; b.lvl = 0.0; b.atr = 0.0; b.state = 0;
   b.bar = 0; b.trig = 0.0; b.stop = 0.0;
}

void UpdateBr()
{
   if(!InpUseBR) return;
   double a = ATR();
   if(a <= 0.0) return;
   int bar = BarNo();
   double c1 = iClose(_Symbol, _Period, 1);
   double h1 = iHigh(_Symbol, _Period, 1);
   double l1 = iLow(_Symbol, _Period, 1);
   double px;

   // a fresh pivot only replaces a setup that is not mid-sequence
   if(ConfirmedPivot(InpPivotBars, true, px) && g_brUp.state == 0)
   {
      g_brUp.live = true; g_brUp.lvl = px; g_brUp.atr = a;
   }
   if(ConfirmedPivot(InpPivotBars, false, px) && g_brDn.state == 0)
   {
      g_brDn.live = true; g_brDn.lvl = px; g_brDn.atr = a;
   }

   // ---- upside
   if(g_brUp.live)
   {
      if(g_brUp.state == 0 && c1 > g_brUp.lvl + InpBrAtr * g_brUp.atr)
      {
         g_brUp.state = 1; g_brUp.bar = bar;
      }
      else if(g_brUp.state == 1)
      {
         if(bar - g_brUp.bar > InpBrWait || c1 < g_brUp.lvl - InpBrTol * g_brUp.atr)
            ResetBr(g_brUp);
         else if(l1 <= g_brUp.lvl + InpBrTol * g_brUp.atr && c1 > g_brUp.lvl)
         {
            g_brUp.state = 2;
            g_brUp.trig  = h1;
            g_brUp.stop  = l1 - InpStopBufAtr * g_brUp.atr;
            g_brUp.bar   = bar;
         }
      }
      else if(g_brUp.state == 2)
      {
         if(bar - g_brUp.bar > InpBrWait || c1 < g_brUp.lvl - InpBrTol * g_brUp.atr)
            ResetBr(g_brUp);
      }
   }
   // ---- downside
   if(g_brDn.live)
   {
      if(g_brDn.state == 0 && c1 < g_brDn.lvl - InpBrAtr * g_brDn.atr)
      {
         g_brDn.state = 1; g_brDn.bar = bar;
      }
      else if(g_brDn.state == 1)
      {
         if(bar - g_brDn.bar > InpBrWait || c1 > g_brDn.lvl + InpBrTol * g_brDn.atr)
            ResetBr(g_brDn);
         else if(h1 >= g_brDn.lvl - InpBrTol * g_brDn.atr && c1 < g_brDn.lvl)
         {
            g_brDn.state = 2;
            g_brDn.trig  = l1;
            g_brDn.stop  = h1 + InpStopBufAtr * g_brDn.atr;
            g_brDn.bar   = bar;
         }
      }
      else if(g_brDn.state == 2)
      {
         if(bar - g_brDn.bar > InpBrWait || c1 > g_brDn.lvl + InpBrTol * g_brDn.atr)
            ResetBr(g_brDn);
      }
   }
}

//==================== ORDER BLOCKS =================================
// wugamlo's rule, MPL-2.0 (notice in the header). A DOWN candle followed by
// InpObLen consecutive UP candles clearing InpObThrPct is a bullish block; the
// zone is that candle's high..low. Mirror for bearish.
//
// E-148: the marker every chart draws sits on the block candle, obp bars BACK,
// and that price was not knowable when the block formed. Entering AT DETECTION
// - market, on the confirming bar - measured nearly double the return entry per
// trade on M1 and 2.4x on M5, with out-of-sample better than in-sample. Both
// are offered because the return fires far more often.
bool NewObBlock(int dir, double &top, double &bot)
{
   int obp = InpObLen + 1;
   if(Bars(_Symbol, _Period) < obp + 5) return false;
   double c0 = iClose(_Symbol, _Period, obp);
   double o0 = iOpen(_Symbol, _Period, obp);
   if(c0 == 0.0) return false;
   double move = MathAbs(c0 - iClose(_Symbol, _Period, 1)) / c0 * 100.0;
   if(move < InpObThrPct) return false;
   int run = 0;
   for(int k = 1; k <= InpObLen; k++)
   {
      double ck = iClose(_Symbol, _Period, k);
      double ok = iOpen(_Symbol, _Period, k);
      if(dir > 0 ? (ck > ok) : (ck < ok)) run++;
   }
   if(run != InpObLen) return false;
   if(dir > 0 ? !(c0 < o0) : !(c0 > o0)) return false;
   top = iHigh(_Symbol, _Period, obp);
   bot = iLow(_Symbol, _Period, obp);
   return true;
}

void UpdateOb()
{
   if(!InpUseObDetect && !InpUseObReturn) return;
   double a = ATR();
   if(a <= 0.0) return;
   int bar = BarNo();
   double top, bot;
   if(NewObBlock(1, top, bot))
   {
      g_obB.live = true; g_obB.top = top; g_obB.bot = bot;
      g_obB.atr = a; g_obB.born = bar;
   }
   if(NewObBlock(-1, top, bot))
   {
      g_obS.live = true; g_obS.top = top; g_obS.bot = bot;
      g_obS.atr = a; g_obS.born = bar;
   }
   // a zone price has traded through is no longer a zone
   double l1 = iLow(_Symbol, _Period, 1);
   double h1 = iHigh(_Symbol, _Period, 1);
   if(g_obB.live && (l1 < g_obB.bot || bar - g_obB.born > InpSetupLife))
      g_obB.live = false;
   if(g_obS.live && (h1 > g_obS.top || bar - g_obS.born > InpSetupLife))
      g_obS.live = false;
}

//==================== ONE PLACER FOR EVERY SIGNAL ==================
// Every source goes through here so the risk cap, the lot rule, the minimum
// stop distance and the arm-price note can never be applied to one signal and
// forgotten on another. The OB risk cap was missed exactly that way in the Pine
// and it had to be caught in an audit.
bool Place(int dir, int otype, double price, double stop, double atrRef,
           string tag, int src)
{
   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   price = NormalizeDouble(price, dg);
   stop  = NormalizeDouble(stop, dg);
   double risk = MathAbs(price - stop);
   if(risk <= 0.0) return false;

   if(risk > InpMaxRiskAtr * atrRef)
   {
      g_refusedToday++;
      Log(StringFormat("REFUSED %s: stop is %.2f ATR, cap %.2f",
                       tag, risk / atrRef, InpMaxRiskAtr));
      return false;
   }
   double md = MinStopDist();
   if(md > 0.0 && risk < md) return false;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double now = (dir > 0) ? ask : bid;

   // a pending order must sit the broker's minimum distance from the market,
   // and on the correct SIDE of it for its type, or it is rejected - or worse,
   // silently converted into something that is not the trade that was measured.
   if(otype != 0)
   {
      double away = (otype == 1) ? dir * (price - now)    // stop: beyond price
                                 : dir * (now - price);   // limit: behind price
      if(away <= 0.0 || (md > 0.0 && away < md)) return false;
   }

   double lots = LotFor(risk);
   if(lots <= 0.0) return false;
   if(!CanAfford(dir, lots, price)) return false;

   bool ok = false;
   if(otype == 0)
      ok = (dir > 0) ? trade.Buy(lots, _Symbol, 0.0, stop, 0.0, tag)
                     : trade.Sell(lots, _Symbol, 0.0, stop, 0.0, tag);
   else if(otype == 1)
      ok = (dir > 0) ? trade.BuyStop(lots, price, _Symbol, stop, 0.0,
                                     ORDER_TIME_GTC, 0, tag)
                     : trade.SellStop(lots, price, _Symbol, stop, 0.0,
                                      ORDER_TIME_GTC, 0, tag);
   else
      ok = (dir > 0) ? trade.BuyLimit(lots, price, _Symbol, stop, 0.0,
                                      ORDER_TIME_GTC, 0, tag)
                     : trade.SellLimit(lots, price, _Symbol, stop, 0.0,
                                       ORDER_TIME_GTC, 0, tag);
   if(!ok)
   {
      Log(StringFormat("%s failed: %d %s", tag, trade.ResultRetcode(),
                       trade.ResultRetcodeDescription()));
      return false;
   }
   g_armSrc = src;
   if(otype != 0)
   {
      g_pend    = trade.ResultOrder();
      g_pendDir = dir;
      g_pendPx  = price;          // what we ASKED for, for the slippage column
      PB_NoteOrder(g_pend, (bid + ask) / 2.0);
   }
   else
      g_pendPx = price;           // a market order: the price we saw when we sent
   Log(StringFormat("%s %s at %.*f, stop %.*f (%.2f ATR), %.2f lots",
                    tag, dir > 0 ? "BUY" : "SELL", dg, price, dg, stop,
                    risk / atrRef, lots));
   return true;
}

void TryArm()
{
   if(g_lockDay || g_lockPerm) return;
   if(PosCount() > 0 || OrderAlive(g_pend)) return;
   if(g_tradesToday >= InpMaxTradesDay) return;
   if(!InOverlap()) return;                     // E-161, off by default

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(ask - bid > InpMaxSpreadPts) return;

   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   int bar = BarNo();

   // PRIORITY IS THE MEASURED RANKING, not a preference: sweep (107.3 control
   // se) > break+retest (73.8) > order block (56.8). E-149 confirmed it holds
   // under competition - the sweep's per-trade INSIDE the combined book is the
   // same as its standalone figure, so the others fill idle time rather than
   // stealing good trades.
   for(int pass = 0; pass < 2 && InpUseSweep; pass++)
   {
      bool sellSide = (pass == 0);
      Setup s; if(sellSide) s = g_sell; else s = g_buy;   // no struct ternary in MQL5
      if(!s.live || s.swept < 0 || bar <= s.swept) continue;
      if(s.disp > InpWickCut) continue;              // THE FAKEOUT FILTER

      int dir = sellSide ? -1 : 1;
      if(!DispOk(dir, s.atr)) continue;

      double lvl  = NormalizeDouble(s.lvl, dg);
      double stop = NormalizeDouble(s.ext - dir * InpStopBufAtr * s.atr, dg);
      double risk = MathAbs(lvl - stop);

      // ---- THE RISK CAP, and it is a REFUSAL, not a resize -------------
      // 0.01 lots is the floor (E-081), so a stop too wide to afford cannot
      // be sized down. E-138: uncapped, one trade took 57% of a GBP60
      // account. This is the line between an edge that compounds and an
      // account that does not survive to see it.
      if(risk > InpMaxRiskAtr * s.atr)
      {
         g_refusedToday++;
         Log(StringFormat("REFUSED %s: stop %.*f is %.2f ATR, cap is %.2f",
                          sellSide ? "SELL" : "BUY", dg, risk,
                          risk / s.atr, InpMaxRiskAtr));
         if(sellSide) ResetSetup(g_sell); else ResetSetup(g_buy);
         continue;
      }

      double md = MinStopDist();
      if(md > 0.0 && risk < md) continue;
      // a STOP order's trigger must also sit at least that far from the market,
      // or the broker rejects it. If price is already back at the level the
      // trade is gone - taking it at market here would be a different entry
      // from the one that was measured.
      double now = sellSide ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                            : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double away = sellSide ? (now - lvl) : (lvl - now);
      if(away <= 0.0 || (md > 0.0 && away < md))
      {
         if(sellSide) ResetSetup(g_sell); else ResetSetup(g_buy);
         continue;
      }

      double lots = LotFor(risk);
      if(lots <= 0.0) continue;

      // NO TAKE PROFIT. E-137 measured every fixed target and all of them
      // banked less than the give-back trail.
      // ---- STOP ORDERS, NOT LIMITS, AND THIS IS NOT A PREFERENCE --------
      // After the sweep, price is on the FAR SIDE of the level: below it on a
      // swept low, above it on a swept high. A BUY LIMIT sitting at a level
      // that price is already UNDER fills IMMEDIATELY, at the bottom of the
      // sweep - the exact opposite of the trade. The entry the backtest
      // measures is "price comes BACK to the level", which is a STOP order.
      //
      // The first build of this file used BuyLimit/SellLimit and would have
      // filled every trade at the worst possible moment while the log said it
      // was doing the right thing. Veer's question about the size of the
      // per-trade number is what sent me back to check the units, and this
      // was underneath it.
      if(!CanAfford(dir, lots, lvl))
      { if(sellSide) ResetSetup(g_sell); else ResetSetup(g_buy); return; }
      bool ok = sellSide
         ? trade.SellStop(lots, lvl, _Symbol, stop, 0.0, ORDER_TIME_GTC, 0, "SS sweep")
         : trade.BuyStop(lots, lvl, _Symbol, stop, 0.0, ORDER_TIME_GTC, 0, "SS sweep");
      if(ok)
      {
         g_pend = trade.ResultOrder();
         g_pendDir = dir;
         g_pendPx  = lvl;         // what we ASKED for, for the slippage column
         PB_NoteOrder(g_pend, (bid + ask) / 2.0);
         // E-164. The setup used to be RESET here, which froze its extreme at
         // the moment of arming. The research keeps extending the extreme
         // right up to the bar before the fill - all closed bars, nothing
         // unknowable - and that is worth +0.0873 a trade against +0.0774
         // frozen, 255.7 points against 233.8. So the setup stays live and
         // ReviseArmed() below moves the resting order's stop with it.
         g_armSide = sellSide ? -1 : 1;
         Log(StringFormat("armed %s stop at %.*f, stop %.*f (%.2f ATR), %.2f lots",
                          sellSide ? "SELL" : "BUY", dg, lvl, dg, stop,
                          risk / s.atr, lots));
         return;
      }
      Log(StringFormat("arm failed: %d %s", trade.ResultRetcode(),
                       trade.ResultRetcodeDescription()));
   }
   if(OrderAlive(g_pend) || PosCount() > 0) return;

   // ---- 2. BREAK + RETEST, a stop order at the retest bar's extreme --------
   if(InpUseBR)
   {
      if(g_brUp.state == 2 && bar > g_brUp.bar)
         if(Place(1, 1, g_brUp.trig, g_brUp.stop, g_brUp.atr, "SS b+r", 2))
         {
            ResetBr(g_brUp);
            return;
         }
      if(g_brDn.state == 2 && bar > g_brDn.bar)
         if(Place(-1, 1, g_brDn.trig, g_brDn.stop, g_brDn.atr, "SS b+r", 2))
         {
            ResetBr(g_brDn);
            return;
         }
   }

   // ---- 3. ORDER BLOCK AT DETECTION, market on the confirming bar ---------
   // E-148: nearly double the return entry per trade on M1, and its
   // out-of-sample beat its in-sample. This is the honest version of "catch
   // the birth of the move" - the marker the eye loves is drawn four bars back
   // at a price that was not knowable then.
   if(InpUseObDetect)
   {
      if(g_obB.live && g_obB.born == bar)
         if(Place(1, 0, ask, g_obB.bot - InpStopBufAtr * g_obB.atr,
                  g_obB.atr, "SS ob-new", 3))
            return;
      if(g_obS.live && g_obS.born == bar)
         if(Place(-1, 0, bid, g_obS.top + InpStopBufAtr * g_obS.atr,
                  g_obS.atr, "SS ob-new", 3))
            return;
   }

   // ---- 4. ORDER BLOCK ON THE RETURN, a LIMIT at the near edge -------------
   // A limit is correct HERE and a stop was correct above: after the run the
   // block sits BEHIND price, so price falls back to a bullish block and rises
   // back to a bearish one. Getting this backwards is the bug that was found in
   // the sweep entry, and it is worth stating once per order type.
   if(InpUseObReturn)
   {
      if(g_obB.live && bar > g_obB.born)
         if(Place(1, 2, g_obB.top, g_obB.bot - InpStopBufAtr * g_obB.atr,
                  g_obB.atr, "SS ob-ret", 4))
            return;
      if(g_obS.live && bar > g_obS.born)
         if(Place(-1, 2, g_obS.bot, g_obS.top + InpStopBufAtr * g_obS.atr,
                  g_obS.atr, "SS ob-ret", 4))
            return;
   }
}

// E-164. While our order rests at the level, the sweep can keep running. The
// invalidation moves with it, so the stop must too - and if it moves so far
// that the setup breaches the risk cap, the trade is no longer the one that was
// measured and the order is cancelled rather than taken at a size we refused.
// Everything here is read off CLOSED bars; nothing about the filling bar is
// used, which is the look-ahead this same fix removed from the Pine.
void ReviseArmed()
{
   if(g_armSide == 0 || PendingCount() == 0) return;
   // No struct ternary in MQL5, and the fields are lvl/ext/atr - read them out
   // explicitly rather than copying a Setup around.
   bool   sellSide = (g_armSide < 0);
   bool   live     = sellSide ? g_sell.live  : g_buy.live;
   int    swept    = sellSide ? g_sell.swept : g_buy.swept;
   double lvl      = sellSide ? g_sell.lvl   : g_buy.lvl;
   double ext      = sellSide ? g_sell.ext   : g_buy.ext;
   double atr      = sellSide ? g_sell.atr   : g_buy.atr;
   if(!live || swept < 0) { g_armSide = 0; return; }
   int    dir  = sellSide ? -1 : 1;
   double want = NormPx(ext - dir * InpStopBufAtr * atr);
   double risk = MathAbs(lvl - want);
   if(atr > 0.0 && risk > InpMaxRiskAtr * atr)
   {
      Log(StringFormat("cancelling armed order: the sweep kept running and the "
                       "stop is now %.2f ATR, over the %.2f cap",
                       risk / atr, InpMaxRiskAtr));
      KillPending("risk cap breached after arming");
      if(sellSide) ResetSetup(g_sell); else ResetSetup(g_buy);
      g_armSide = 0;
      return;
   }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol)  continue;
      double have = OrderGetDouble(ORDER_SL);
      if(MathAbs(have - want) < _Point) continue;
      double px = OrderGetDouble(ORDER_PRICE_OPEN);
      if(!trade.OrderModify(tk, px, want, 0.0, ORDER_TIME_GTC, 0))
         Log(StringFormat("could not move the armed stop to %.*f: %d %s",
                          (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS), want,
                          trade.ResultRetcode(), trade.ResultRetcodeDescription()));
   }
}

void AgePending()
{
   if(PendingCount() == 0) { g_pend = 0; return; }
   // F10. Age the order off its OWN setup time, not off a Bars() count that
   // plateaus and jumps.
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol)  continue;
      datetime setup = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
      int age = iBarShift(_Symbol, _Period, setup, false);
      if(age > InpSetupLife)
      {
         if(trade.OrderDelete(tk)) Log("cancelled: unfilled and stale");
         else Log(StringFormat("COULD NOT CANCEL stale order %I64u: %d %s",
                               tk, trade.ResultRetcode(),
                               trade.ResultRetcodeDescription()));
      }
   }
   if(PendingCount() == 0)
   {
      g_pend = 0;
      g_pendDir = 0;
      // E-164: the setup now survives arming, so when its order is cancelled
      // the setup has to go with it - otherwise the next bar simply re-arms a
      // setup that has already been declared stale.
      if(g_armSide != 0)
      {
         if(g_armSide < 0) ResetSetup(g_sell); else ResetSetup(g_buy);
         g_armSide = 0;
      }
   }
}

//==================== THE GIVE-BACK TRAIL ==========================
// The stop ratchets to entry + (1 - giveBack) x the best excursion. It only
// ever moves toward profit - a stop that can move backwards is not a stop.
void TrailStop()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      int    dir   = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl    = PositionGetDouble(POSITION_SL);
      double px    = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                               : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      if(g_posDir == 0 || MathAbs(entry - g_posEntry) > _Point)
      {
         g_posDir = dir; g_posEntry = entry; g_peakPrice = entry;
         g_posBarTime = (datetime)PositionGetInteger(POSITION_TIME);
         g_lastSl = 0.0;
         g_posInit = sl;          // the stop as it was placed = 1R
      }
      g_peakPrice = (dir > 0) ? MathMax(g_peakPrice, px) : MathMin(g_peakPrice, px);

      int    dg0   = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      double risk0 = (g_posInit > 0.0) ? MathAbs(entry - g_posInit) : 0.0;

      // HIGH WIN RATE MODE - a real take profit, placed at the broker so it
      // fills without this EA having to be awake for the tick.
      if(InpHiWinR > 0.0 && risk0 > 0.0)
      {
         double tgt  = NormPx(entry + dir * InpHiWinR * risk0);
         double have = PositionGetDouble(POSITION_TP);
         double gd2  = MathMax(MinStopDist(), FreezeDist());
         bool   room2 = (gd2 <= 0.0) || (dir * (tgt - px) >= gd2);
         if(MathAbs(have - tgt) >= _Point && room2)
            if(!trade.PositionModify(tk, sl, tgt))
               Log(StringFormat("TAKE PROFIT MODIFY REJECTED %d %s - no target is set",
                                trade.ResultRetcode(),
                                trade.ResultRetcodeDescription()));
      }
      double runUp = dir * (g_peakPrice - entry);
      double runR  = (risk0 > 0.0) ? runUp / risk0 : 0.0;

      // STAGE 1 - TRUE BREAKEVEN. Not the entry price: entry plus the spread
      // and the slippage both ways, because a stop AT entry still loses the
      // round trip. Veer: "sl closer to be as it grows".
      if(InpBeAtR > 0.0 && runR >= InpBeAtR && risk0 > 0.0)
      {
         double sp   = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                     - SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double beLv = NormPx(entry + dir * sp);
         bool   bett = (dir > 0) ? (beLv > sl) : (beLv < sl);
         bool   safe = (dir > 0) ? (beLv < px) : (beLv > px);
         double gd   = MathMax(MinStopDist(), FreezeDist());
         if(bett && safe && (gd <= 0.0 || dir * (px - beLv) >= gd))
         {
            // PASS THE CURRENT TP, NOT 0.0. CTrade::PositionModify sets BOTH,
            // so 0.0 ERASES the take profit. With InpHiWinR > 0 the sequence
            // was: TP placed at arm time, then the first tick this trade
            // reached InpBeAtR deleted it, and the position ran with no target
            // at all - the exact opposite of what "high win rate mode" says it
            // does. Dormant at InpHiWinR = 0, live the moment it is switched on.
            if(trade.PositionModify(tk, beLv, PositionGetDouble(POSITION_TP)))
               { sl = beLv; g_lastSl = beLv; Log("stop to breakeven"); }
            else
               Log(StringFormat("BREAKEVEN MODIFY REJECTED %d %s - stop still %.*f",
                                trade.ResultRetcode(),
                                trade.ResultRetcodeDescription(), dg0, sl));
         }
      }

      // STAGE 2 - the give-back trail, and only once the trade has earned it.
      // Veer: "trail sl not too aggressively for liquidity sweeps".
      if(runUp > 0.0 && runR >= InpTrailAtR)
      {
         int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
         double cand = NormPx(entry + dir * runUp * (1.0 - InpGiveBack));
         bool better = (dir > 0) ? (cand > sl) : (cand < sl);
         double md = MinStopDist();

         // E-151. A ratcheted level price has ALREADY passed cannot be sent as
         // a stop: for a long, a stop above the bid is rejected, and a rejected
         // modify leaves the OLD, looser stop sitting there - the trail simply
         // stops working and nothing says so. On a fast move against us that is
         // exactly when it matters. If the level is gone, exit at market.
         bool passed = (dir > 0) ? (px <= cand) : (px >= cand);
         if(better && passed)
         {
            // F7. THIS IS THE ONLY EXIT THIS EA HAS - there is no take profit
            // anywhere in it, by design (E-137). The close used to be sent with
            // its result discarded and "market exit" logged either way, so a
            // requote, a price-off, a freeze-band rejection or AutoTrading
            // being switched off all produced a log line saying the trade was
            // closed while it was still running. Throttled so a persistent
            // rejection does not become a tick-rate retry storm.
            if(TimeCurrent() - g_lastTry >= 2)
            {
               g_lastTry = TimeCurrent();
               if(trade.PositionClose(tk))
                  Log("trail level already passed - market exit DONE");
               else
                  Log(StringFormat("EXIT REJECTED %d %s - THE POSITION IS "
                                   "STILL OPEN, stop still %.*f. Retrying.",
                                   trade.ResultRetcode(),
                                   trade.ResultRetcodeDescription(), dg, sl));
            }
            continue;
         }

         // F6 freeze band, and F7 do not re-send the same price every tick.
         double guardD = MathMax(md, FreezeDist());
         bool room  = (guardD <= 0.0) || (dir * (px - cand) >= guardD);
         bool moved = (MathAbs(cand - g_lastSl) >= _Point);
         if(better && room && moved)
         {
            if(trade.PositionModify(tk, cand, PositionGetDouble(POSITION_TP)))
               g_lastSl = cand;
            else
               Log(StringFormat("TRAIL MODIFY REJECTED %d %s - the stop is "
                                "STILL %.*f, not %.*f. The trail is NOT running.",
                                trade.ResultRetcode(),
                                trade.ResultRetcodeDescription(),
                                dg, sl, dg, cand));
         }
      }

      // F10. Bars() is not a clock. It plateaus at the terminal's "max bars in
      // chart" setting, after which this subtraction freezes and the time exit
      // NEVER fires again; and it jumps by thousands when history back-fills,
      // firing the time exit instantly on a position seconds old. iBarShift
      // does neither, and it is what SuperTrendSniper already uses.
      int held = (g_posBarTime > 0)
               ? iBarShift(_Symbol, _Period, g_posBarTime, false) : 0;
      if(held >= InpMaxBars)
      {
         if(trade.PositionClose(tk)) Log("time exit DONE");
         else Log(StringFormat("TIME EXIT REJECTED %d %s - still open",
                               trade.ResultRetcode(),
                               trade.ResultRetcodeDescription()));
      }
   }
}

//==================== GUARDS =======================================
int DayStamp()
{
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   return t.year * 10000 + t.mon * 100 + t.day;
}

// F5. MT5 calls OnInit on a restart, a recompile, a timeframe change and EVERY
// parameter change, and OnInit used to reset the day baseline, the drawdown
// floor and both locks to whatever the (already drawn down) equity was. Lose
// 3%, nudge an input, lose another 3%. SuperTrendSniper fixed this and called
// it BLOCKER 1; this EA never got the fix. Keyed by login and magic so no other
// account or EA inherits a lock, and disabled in the tester so nothing leaks
// between passes.
bool   GuardsPersist() { return !(bool)MQLInfoInteger(MQL_TESTER); }
string GKey(string f)
{
   return "SS_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))
        + "_" + IntegerToString(InpMagic) + "_" + f;
}
double GGet(string f, double d)
{
   if(!GuardsPersist()) return d;
   return GlobalVariableCheck(GKey(f)) ? GlobalVariableGet(GKey(f)) : d;
}
void GSet(string f, double v) { if(GuardsPersist()) GlobalVariableSet(GKey(f), v); }

void PersistGuards()
{
   GSet("peakEq", g_peakEq);
   GSet("dayStartEq", g_dayStartEq);
   GSet("dayStamp", (double)g_dayStamp);
   GSet("tradesDay", (double)g_tradesToday);
   GSet("lockDay",  g_lockDay  ? 1.0 : 0.0);
   GSet("lockPerm", g_lockPerm ? 1.0 : 0.0);
}

void LoadGuards()
{
   if(!GuardsPersist()) return;
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double pk = GGet("peakEq", 0.0);
   if(pk > 0.0) g_peakEq = MathMax(pk, eq);
   g_lockPerm = (GGet("lockPerm", 0.0) > 0.5);
   if((int)GGet("dayStamp", -1.0) == DayStamp())
   {
      double ds = GGet("dayStartEq", 0.0);
      if(ds > 0.0) g_dayStartEq = ds;
      g_tradesToday = (int)GGet("tradesDay", 0.0);
      g_lockDay     = (GGet("lockDay", 0.0) > 0.5);
   }
   g_floor = g_peakEq * (1.0 - InpMaxDDPct / 100.0);
   if(g_lockPerm)
      Print("[SS] RESTORED: the permanent max-drawdown lock is SET. This EA "
            "will not trade. Clear it by deleting the global variable "
            + GKey("lockPerm"));
   if(g_lockDay) Print("[SS] RESTORED: locked out for the rest of today.");
}

// E-161. Server time, like every other clock in this EA - see F16, TimeCurrent()
// is NOT UTC. Check the offset against your broker before switching this on.
bool InOverlap()
{
   if(!InpOverlapOnly) return true;
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   return (t.hour >= InpOverlapFrom && t.hour < InpOverlapTo);
}

void CheckGuards()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_peakEq) { g_peakEq = eq; PersistGuards(); }

   // F4. The floor used to be set ONCE, in OnInit, from whatever the equity
   // was when the EA was attached. Attach at GBP60 and the floor is GBP56.40 -
   // grow to GBP100 and it is STILL GBP56.40, which is a 44% drawdown from
   // peak before a "6% max drawdown" guard says a word. Every prop firm
   // measures from the peak. g_peakEq was already being computed and was never
   // read by anything.
   if(g_peakEq > 0.0) g_floor = g_peakEq * (1.0 - InpMaxDDPct / 100.0);

   if(!g_lockDay && g_dayStartEq > 0.0
      && eq <= g_dayStartEq * (1.0 - InpMaxDayLossPct / 100.0))
   {
      g_lockDay = true;
      Log("DAILY LOSS LIMIT - no new trades today");
      PersistGuards();
   }
   if(!g_lockPerm && g_floor > 0.0 && eq <= g_floor)
   {
      g_lockPerm = true;
      Log("MAX DRAWDOWN - stopped");
      PersistGuards();
   }

   // F2/F3. A limit that only refuses NEW trades is not a limit. The position
   // whose floating loss BREACHED the limit was left running, and a prop firm
   // measures the daily limit on equity - so the guard fired at exactly the
   // moment it needed to act, and did nothing but stop arming.
   //
   // Flattening is a STATE, not an event: while a lock is set there must be
   // nothing resting and nothing open, rechecked every couple of seconds. The
   // breach tick is a fast, wide-spread, requote-prone tick, which makes it the
   // likeliest tick in the session for a close to be rejected - and the old
   // one-shot version would have given up there, silently.
   if(!g_lockDay && !g_lockPerm) return;
   static datetime lastFlat = 0;
   if(TimeCurrent() - lastFlat < 2) return;
   lastFlat = TimeCurrent();

   if(PendingCount() > 0)
      KillPending(g_lockPerm ? "max drawdown" : "daily loss limit");
   if(!InpFlattenOnBreach) return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;
      if(trade.PositionClose(tk))
         Log("closed on guard breach");
      else
         Log(StringFormat("GUARD CLOSE REJECTED %I64u: %d %s - STILL OPEN, "
                          "retrying", tk, trade.ResultRetcode(),
                          trade.ResultRetcodeDescription()));
   }
}

//==================== LIFECYCLE ====================================
int OnInit()
{
   if(!TfGuard("SS", InpMaxTF)) return INIT_FAILED;
   if(InpDemoOnly && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Print("[SS] REFUSING TO START: InpDemoOnly is true and this is not a demo "
            "account. This has NEVER been forward tested. Set InpDemoOnly=false "
            "deliberately, and only after a demo run that measured your real "
            "stop-fill slippage.");
      return INIT_FAILED;
   }
   g_atr = iATR(_Symbol, _Period, 14);
   if(g_atr == INVALID_HANDLE) { Print("[SS] ATR handle failed"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(20);

   ResetSetup(g_sell);
   ResetSetup(g_buy);
   ResetBr(g_brUp);
   ResetBr(g_brDn);
   g_obB.live = false;
   g_obS.live = false;
   g_armSrc = 0;

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayStartEq = eq; g_peakEq = eq;
   g_floor = eq * (1.0 - InpMaxDDPct / 100.0);
   g_dayStamp = DayStamp();
   LoadGuards();          // F5: after the defaults, never before

   // F1. Adopt what is already at the broker instead of arming on top of it.
   g_pend = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol)  continue;
      g_pend    = tk;
      g_pendDir = (OrderGetInteger(ORDER_TYPE) == ORDER_TYPE_BUY_STOP
                || OrderGetInteger(ORDER_TYPE) == ORDER_TYPE_BUY_LIMIT) ? 1 : -1;
      g_pendPx  = OrderGetDouble(ORDER_PRICE_OPEN);
      Log(StringFormat("adopted resting order %I64u on start", tk));
   }
   if(PosCount() > 0)
      Log("adopted an open position on start - the peak and the bar clock "
          "restart from here. The broker's stop is untouched.");

   int corner = InpBoxCorner == 0 ? CORNER_LEFT_UPPER  :
                InpBoxCorner == 1 ? CORNER_RIGHT_UPPER :
                InpBoxCorner == 2 ? CORNER_LEFT_LOWER  : CORNER_RIGHT_LOWER;
   PB_Init("SS.", "SWEEP SNIPER " + SS_BUILD, InpMagic, InpShowProfitBox,
           corner, InpBoxX, InpBoxY, "SWEEP  liq");
   if(InpTrackMagic2 != 0) PB_AddStrategy(InpTrackMagic2, InpTrackLabel2);
   if(InpTrackMagic3 != 0) PB_AddStrategy(InpTrackMagic3, InpTrackLabel3);
   if(InpTrackMagic4 != 0) PB_AddStrategy(InpTrackMagic4, InpTrackLabel4);

   PrintFormat("[SS] === SWEEP SNIPER %s === pivot %d, sweep %.2f ATR, wick <= %.3f, "
               "stop %.2f ATR past the extreme, RISK CAP %.2f ATR, give back %.0f%%",
               SS_BUILD, InpPivotBars, InpSweepAtr, InpWickCut, InpStopBufAtr,
               InpMaxRiskAtr, InpGiveBack * 100.0);
   Print("[SS] ================= READ THIS BEFORE RUNNING =================");
   Print("[SS] E-165: THE SWEEP IS DISPROVEN. The backtest that justified this "
         "EA was booking entries AT the level on bars that had already OPENED "
         "past it - 75% of them. No order could have been resting there.");
   Print("[SS] Corrected, on the subset THIS EA can actually execute: "
         "-0.0030 points a trade on M1 (t -0.37, indistinguishable from zero) "
         "and -0.0885 on M5 (t -2.39, negative). The old +201.1 points figure "
         "was an accounting artefact.");
   Print("[SS] The proof: the same backtest code extracted +0.0226 a trade at "
         "t = 5 from a DRIFTLESS RANDOM WALK, on every seed. Nothing real does "
         "that. With honest fills the random walk pays -0.039, the spread, "
         "which is what a null should pay.");
   Print("[SS] This EA REFUSES to arm when price has already passed the level, "
         "which is correct and always was - it is why its executable subset is "
         "only 25% of the backtest's trades. That refusal is the reason it was "
         "never going to make the money the backtest promised.");
   Print("[SS] DO NOT PUT THIS ON A LIVE OR FUNDED ACCOUNT. There is no "
         "measured edge to trade. It is left runnable ON DEMO ONLY so it can "
         "log requested price against actual fill, which is the one "
         "measurement that could still change this verdict.");
   Print("[SS] ============================================================");
   if(InpUseDisp)
      Print("[SS] WARNING: InpUseDisp is ON. That filter is evaluated at the FILL "
            "bar and this EA rests a LIMIT, so it will be applied at the ARM bar "
            "instead - a different signal from the one measured. E-139.");
   Print("[SS] 2018 H1 only. NEVER FORWARD TESTED. Demo first, and watch the "
         "'fill vs signal' row - it is how you see your limits filling late.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_atr != INVALID_HANDLE) IndicatorRelease(g_atr);
   PB_Destroy();
}

void OnTick()
{
   // F15. Nothing in this project ever asked whether trading was possible. With
   // AutoTrading off, or after a disconnect, every trade call returns
   // TRADE_RETCODE_TRADE_DISABLED - and the exit path used to log "market exit"
   // regardless. An EA that cannot act must say so, not pretend.
   if(!TerminalInfoInteger(TERMINAL_CONNECTED)
      || !TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)
      || !MQLInfoInteger(MQL_TRADE_ALLOWED)
      || !AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)
      || !AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
   {
      static datetime shout = 0;
      if(TimeCurrent() - shout > 60)
      {
         shout = TimeCurrent();
         Print("[SS] TRADING IS DISABLED (AutoTrading off, disconnected, or "
               "this account forbids EAs). OPEN POSITIONS ARE NOT BEING "
               "MANAGED - the trail and the time exit are both dead.");
      }
      return;
   }

   int ds = DayStamp();
   if(ds != g_dayStamp)
   {
      g_dayStamp = ds;
      g_dayStartEq = AccountInfoDouble(ACCOUNT_EQUITY);
      g_tradesToday = 0;
      g_refusedToday = 0;
      g_lockDay = false;
      Log("new trading day");
      PersistGuards();
   }

   CheckGuards();

   datetime b = iTime(_Symbol, _Period, 0);
   if(b != g_lastBar)
   {
      g_lastBar = b;
      UpdateSetups();
      UpdateBr();
      UpdateOb();
      ReviseArmed();          // E-164, before ageing so a cancel is not missed
      AgePending();
      if(PosCount() == 0) TryArm();
   }

   TrailStop();
   PB_Draw();
}

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &req, const MqlTradeResult &res)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;

   long  entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   ulong pid   = (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);

   // F14. DEAL_ENTRY_INOUT is what a NETTING account produces on a reversal,
   // and several prop firms run netting. It was dropped on the floor: the trade
   // was never counted, the pending was never cleared and the trail kept
   // measuring against the previous position's entry.
   if(entry == DEAL_ENTRY_IN || entry == DEAL_ENTRY_INOUT)
   {
      // F20. Count TRADES, not deals. One pending order that fills in three
      // parts is three DEAL_ENTRY_IN events and one trade, and the old counter
      // tripped the daily circuit breaker on trades that never happened.
      if(pid != g_lastPosId) { g_tradesToday++; g_lastPosId = pid; }
      g_pend = 0;
      g_armSide = 0;
      ResetSetup(g_sell);
      ResetSetup(g_buy);
      g_posDir = 0;                       // TrailStop re-seeds from the position
      PB_PromoteOrder((ulong)HistoryDealGetInteger(trans.deal, DEAL_ORDER),
                      pid, HistoryDealGetDouble(trans.deal, DEAL_PRICE));
      PersistGuards();
      // The slippage row. g_pendPx is what we asked for; DEAL_PRICE is what
      // the broker gave us. Written BEFORE g_pendPx is cleared.
      // The stop as the BROKER now holds it, not g_lastSl - that global is
      // the last stop we ASKED for and is stale or zero at the moment of fill.
      double fillSl = PositionSelectByTicket(pid)
                    ? PositionGetDouble(POSITION_SL) : 0.0;
      JRow("FILL", (int)(HistoryDealGetInteger(trans.deal, DEAL_TYPE)
                         == DEAL_TYPE_BUY ? 1 : -1),
           AskedPrice(trans.deal), HistoryDealGetDouble(trans.deal, DEAL_PRICE),
           HistoryDealGetDouble(trans.deal, DEAL_VOLUME),
           fillSl, 0.0, 0.0, pid, SrcName(g_armSrc));
      g_pendPx = 0.0;
      Log("FILLED");
      return;
   }
   if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
   {
      // F14. A PARTIAL close also raises DEAL_ENTRY_OUT. Zeroing the peak on a
      // position that is still open restarts the give-back from entry, so the
      // ratchet stalls until price makes a new extreme. Only a close that
      // actually left us flat ends the trade.
      if(!PositionSelectByTicket(pid))
      {
         g_posDir = 0;
         g_peakPrice = 0.0;
         g_lastSl = 0.0;
         g_posInit = 0.0;
      }
      g_pbDirty = true;
      // An exit has no "asked" price - a stop or a trail is filled wherever
      // the market was - so req_px is left empty and slip_pts reads 0. The
      // spread column is still the point of the row.
      JRow("EXIT", (int)(HistoryDealGetInteger(trans.deal, DEAL_TYPE)
                         == DEAL_TYPE_BUY ? -1 : 1),
           0.0, HistoryDealGetDouble(trans.deal, DEAL_PRICE),
           HistoryDealGetDouble(trans.deal, DEAL_VOLUME), 0.0, 0.0,
           HistoryDealGetDouble(trans.deal, DEAL_PROFIT), pid,
           PositionSelectByTicket(pid) ? "partial" : "flat");
      Log(StringFormat("closed, profit %.2f",
                       HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));
   }
}
