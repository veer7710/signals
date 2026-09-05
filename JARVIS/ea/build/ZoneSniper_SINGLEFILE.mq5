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
#property version   "2.10"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

// The on-chart profit box. It reports POINTS first and money second (E-074),
// and it splits the result between the two things this EA actually combines:
//   LEVEL  what resting a limit inside the zone bought over chasing the signal
//   TREND  what the SuperTrend direction filter and the band trail made of it
// The split is exact - LEVEL + TREND = total, with no residual and no model.
// Ship as ZoneSniper_SINGLEFILE.mq5 (JARVIS/tools/build_ea.py) if you would
// rather not put a second file in MQL5/Include.
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
   g_pbS[n].n = 0; g_pbS[n].wins = 0;
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
int    g_pbN, g_pbNDay, g_pbWins, g_pbNLong, g_pbNShort;
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
   g_pbN = 0; g_pbNDay = 0; g_pbWins = 0; g_pbNLong = 0; g_pbNShort = 0;
   g_pbFirst = 0;
   for(int i = 0; i < ArraySize(g_pbS); i++)
   {
      g_pbS[i].n = 0; g_pbS[i].wins = 0;
      g_pbS[i].pts = 0; g_pbS[i].money = 0; g_pbS[i].ptsDay = 0;
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
         if(today) g_pbS[si].ptsDay += pts;
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

   // 15 fixed rows plus one per registered strategy
   g_pbMaxRows = 15 + ArraySize(g_pbS);

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
// M1-M30 only. Higher timeframes are context, not instruments (E-133).
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

bool TfAllowed(ENUM_TIMEFRAMES tf)
{
   return tf == PERIOD_M1  || tf == PERIOD_M2  || tf == PERIOD_M3
       || tf == PERIOD_M4  || tf == PERIOD_M5  || tf == PERIOD_M6
       || tf == PERIOD_M10 || tf == PERIOD_M12 || tf == PERIOD_M15
       || tf == PERIOD_M20 || tf == PERIOD_M30;
}

// Returns false and prints why. Call it first in OnInit and return
// INIT_FAILED on false.
bool TfGuard(string ea)
{
   if(TfAllowed((ENUM_TIMEFRAMES)_Period)) return true;
   PrintFormat("[%s] REFUSING TO START on %s.", ea,
               EnumToString((ENUM_TIMEFRAMES)_Period));
   Print("This is an M1-M30 system. Every number it is quoted at was measured "
         "on M1 and none of it transfers upward: the spread is a far smaller "
         "fraction of the move up there, the stop and trail are sized in an "
         "ATR that means something different, and the trade count collapses.");
   Print("Higher timeframes are for CONTEXT. Reading H4 is not trading H4. "
         "E-133 measured H1 and H4 as direction sources against M1 across nine "
         "variants and not one of them beat M1.");
   Print("Attach this to M1, M3, M5, M15 or M30.");
   return false;
}

#endif  // TIMEFRAME_GUARD_MQH

//==============================================================
// END TimeframeGuard.mqh
//==============================================================
#define ZS_BUILD "2.10"

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

input group "=== THE PROFIT BOX ==="
input bool   InpShowProfitBox = true;   // the on-chart panel
input int    InpBoxCorner     = 3;      // 0 top-left, 1 top-right, 2 bottom-left, 3 bottom-right
input int    InpBoxX          = 12;     // pixels in from that corner
input int    InpBoxY          = 12;
// Run more than one of these EAs on the same account and the box speaks for
// all of them - one row per magic, separate books. Set a magic to 0 to drop
// its row. These defaults are the magics the other two EAs ship with.
input long   InpTrackMagic2  = 770001;  // SuperTrendSniper
input string InpTrackLabel2  = "SUPERTREND";
input long   InpTrackMagic3  = 770069;  // LiquiditySniper
input string InpTrackLabel3  = "LIQUIDITY";

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
      ulong tk = trade.ResultOrder();
      if(dir > 0) { g_pendBuy = tk; g_armBarBuy = Bars(_Symbol, PERIOD_M1); }
      else        { g_pendSell = tk; g_armBarSell = Bars(_Symbol, PERIOD_M1); }
      // the market price at the moment we decided to trade. Everything the
      // limit earns over this is the LEVEL's contribution; everything after
      // it is the TREND's. Filed against the ORDER ticket and promoted to the
      // position id on the fill, because the position does not exist yet.
      PB_NoteOrder(tk, (bid + ask) / 2.0);
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
   if(!TfGuard("ZS")) return INIT_FAILED;
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

   int corner = InpBoxCorner == 0 ? CORNER_LEFT_UPPER  :
                InpBoxCorner == 1 ? CORNER_RIGHT_UPPER :
                InpBoxCorner == 2 ? CORNER_LEFT_LOWER  : CORNER_RIGHT_LOWER;
   PB_Init("ZS.", "ZONE SNIPER " + ZS_BUILD, InpMagic, InpShowProfitBox,
           corner, InpBoxX, InpBoxY, "ZONE  st+liq");
   if(InpTrackMagic2 != 0) PB_AddStrategy(InpTrackMagic2, InpTrackLabel2);
   if(InpTrackMagic3 != 0) PB_AddStrategy(InpTrackMagic3, InpTrackLabel3);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_atrM1 != INVALID_HANDLE) IndicatorRelease(g_atrM1);
   PB_Destroy();
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
   PB_Draw();   // rescans the deal history at most once every 3 seconds
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
         // move the arm-price note from the order ticket onto the position it
         // became. If the note is missing the trade simply reads as entered at
         // market, which is the honest answer rather than a guess.
         PB_PromoteOrder((ulong)HistoryDealGetInteger(trans.deal, DEAL_ORDER),
                         (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID),
                         HistoryDealGetDouble(trans.deal, DEAL_PRICE));
         Log("FILLED");
      }
      else if(entry == DEAL_ENTRY_OUT)
      {
         g_lastClose = TimeCurrent();
         g_pbDirty   = true;   // redraw the box off the broker's own numbers
         Log(StringFormat("closed, profit %.2f",
                          HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));
      }
   }
}
