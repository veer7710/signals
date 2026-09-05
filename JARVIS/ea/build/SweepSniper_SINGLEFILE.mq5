//+------------------------------------------------------------------+
//|  SweepSniper.mq5  —  the liquidity sweep Veer trades, automated   |
//|                                                                  |
//|  "i literally run liquidity sweep strat myself and i have 80%     |
//|   winrate. i wanted u using ict smc perfect and automate so i     |
//|   dont have to do analysis"                                       |
//|                                                                  |
//|  THE RULES. Every one was measured before it was allowed in, on   |
//|  157,051 real M1 bars built from 18,816,940 bid/ask ticks with    |
//|  each bar charged its OWN measured spread.                        |
//|                                                                  |
//|   1 LEVEL       a confirmed swing pivot, 5 bars either side.      |
//|                 Resting liquidity - the stops above a high or     |
//|                 below a low.                                       |
//|   2 SWEEP       price runs THROUGH it by 0.10 ATR. The stop run.  |
//|   3 THE WICK    the sweep bar's body must be at most 64.6% of its |
//|                 range. THIS IS THE FAKEOUT FILTER. A sweep that   |
//|                 CLOSES with a big body is a real breakout and     |
//|                 fading it is how you lose; a sweep that is mostly |
//|                 WICK is a rejection. The DIRECTION of this rule   |
//|                 comes from ICT, not from the data - the data only |
//|                 supplied the cut, from the first half of the      |
//|                 sample, tested once on the second (E-135d).       |
//|   4 DISPLACEMENT  MEASURED, AND THEN SWITCHED OFF. It was the     |
//|                 second half of the tested filter and it is worth   |
//|                 real money - but it is evaluated at the FILL bar,  |
//|                 and an EA holding a resting limit cannot know      |
//|                 which bar will fill it. E-139 tested all four ways |
//|                 of getting round that and every one was worse than |
//|                 simply dropping it:                                 |
//|                   A wick+disp, limit at level  349.7 NOT EA-ABLE   |
//|                   B wick only, limit at level  310.7 <- SHIPPED    |
//|                   C wick+disp, market next bar  81.4 (dead at      |
//|                                                 0.05 slippage)     |
//|                   D limit, then bail out       228.4               |
//|                 A rule an EA can execute beats a better rule it    |
//|                 cannot. This is the P92 lesson - a 52% signal gap  |
//|                 between a Pine and an EA sat unnoticed for 180     |
//|                 commits because nobody checked.                     |
//|   5 ENTRY       a limit resting AT the level. NOT the sweep's     |
//|                 close - E-130 measured that and it cost 97 of     |
//|                 97.1 points on System A.                           |
//|   6 STOP        beyond the SWEEP EXTREME + 0.30 ATR. Where the    |
//|                 setup is genuinely wrong, not a fixed distance.    |
//|   7 RISK CAP    REFUSE the setup if that stop is wider than 2.0   |
//|                 ATR. Read the audit below before touching this.    |
//|   8 EXIT        give back 25%: the stop ratchets to entry + 75%   |
//|                 of the best excursion. No fixed target - every    |
//|                 fixed target banked less (E-137).                  |
//|                                                                  |
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
//|  NOT PROVEN. One instrument, 2018 H1, NEVER FORWARD TESTED, and   |
//|  the money figure depends on scaling 2018 volatility to today.    |
//|  SUPPORTED, in the vocabulary of EXPERIMENTS.md. DEMO FIRST.      |
//+------------------------------------------------------------------+
#property copyright "JARVIS"
#property version   "1.00"
#property strict

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
#define SS_BUILD "1.00"

input group "=== SAFETY ==="
input bool   InpDemoOnly     = true;    // refuse to start on a live account
input long   InpMagic        = 990077;  // magic number
input ENUM_TIMEFRAMES InpMaxTF = PERIOD_M30;  // highest chart this will start on

input group "=== THE SETUP ==="
input int    InpPivotBars    = 5;       // swing needs this many bars either side
input double InpSweepAtr     = 0.10;    // sweep must clear the level by this x ATR
input double InpWickCut      = 0.646;   // sweep body/range must be under this
input bool   InpUseDisp      = false;   // OFF. E-139: an EA cannot execute this - see below
input double InpDispCutNote  = 0.0;     // (unused; kept so the group reads in order)
input double InpDispCut      = -1.4909; // only used if InpUseDisp is switched on
input int    InpSetupLife    = 120;     // give up on a setup after N bars

input group "=== RISK — read E-138 before changing anything here ==="
input double InpStopBufAtr   = 0.30;    // stop this far beyond the sweep extreme
input double InpMaxRiskAtr   = 1.2;     // REFUSE the setup if the stop is wider
input double InpGiveBack     = 0.25;    // give back this much of the best excursion
input int    InpMaxBars      = 240;     // time exit, M1 bars
input bool   InpUseFixedLots = true;
input double InpFixedLots    = 0.01;    // E-081: 0.01 is GBP0.787/point and is the floor
input double InpRiskPct      = 0.50;    // used only when InpUseFixedLots = false
input double InpMaxSpreadPts = 0.60;    // refuse to arm when the spread is wider

input group "=== GUARDS ==="
input double InpMaxDayLossPct = 3.0;
input double InpMaxDDPct      = 6.0;
input int    InpMaxTradesDay  = 60;     // it runs ~19/day; this is a circuit breaker
input bool   InpVerbose       = true;

input group "=== THE PROFIT BOX ==="
input bool   InpShowProfitBox = true;
input int    InpBoxCorner     = 3;      // 0 TL, 1 TR, 2 BL, 3 BR
input int    InpBoxX          = 12;
input int    InpBoxY          = 12;
input long   InpTrackMagic2   = 880041; // ZoneSniper, if you run it too
input string InpTrackLabel2   = "ZONE  st+liq";
input long   InpTrackMagic3   = 770001; // SuperTrendSniper
input string InpTrackLabel3   = "SUPERTREND";

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

int      g_atr = INVALID_HANDLE;
datetime g_lastBar = 0;
ulong    g_pend = 0;        // the resting limit
int      g_pendBar = 0;
int      g_pendDir = 0;
double   g_pendStop = 0.0;

double   g_peakPrice = 0.0; // best excursion of the open position
int      g_posBar = 0;
double   g_posEntry = 0.0;
int      g_posDir = 0;

double   g_dayStartEq = 0.0, g_peakEq = 0.0, g_floor = 0.0;
int      g_dayStamp = 0, g_tradesToday = 0, g_refusedToday = 0;
bool     g_lockDay = false, g_lockPerm = false;

void Log(string s) { if(InpVerbose) Print("[SS] ", s); }

double ATR()
{
   double b[];
   if(CopyBuffer(g_atr, 0, 1, 1, b) != 1) return 0.0;
   return b[0];
}

int BarNo() { return Bars(_Symbol, PERIOD_M1); }

//==================== PIVOTS =======================================
// A pivot is only KNOWN InpPivotBars bars after it forms. This checks the bar
// at that offset, so the level is real at the moment it is acted on. Reading it
// any earlier is look-ahead and it is the single easiest way to fake this
// strategy into working.
bool ConfirmedPivot(int k, bool wantHigh, double &px)
{
   int c = k + 1;                      // the candidate, k bars back from bar 1
   double v = wantHigh ? iHigh(_Symbol, PERIOD_M1, c) : iLow(_Symbol, PERIOD_M1, c);
   for(int i = 1; i <= k; i++)
   {
      if(wantHigh)
      {
         if(iHigh(_Symbol, PERIOD_M1, c - i) > v) return false;
         if(iHigh(_Symbol, PERIOD_M1, c + i) > v) return false;
      }
      else
      {
         if(iLow(_Symbol, PERIOD_M1, c - i) < v) return false;
         if(iLow(_Symbol, PERIOD_M1, c + i) < v) return false;
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

bool OrderAlive(ulong tk)
{
   if(tk == 0) return false;
   return OrderSelect(tk);
}

void KillPending(string why)
{
   if(!OrderAlive(g_pend)) { g_pend = 0; return; }
   if(trade.OrderDelete(g_pend))
      Log("cancelled resting limit: " + why);
   g_pend = 0;
   g_pendDir = 0;
}

double MinStopDist()
{
   long lv = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   return (double)lv * _Point;
}

double LotFor(double stopPts)
{
   if(InpUseFixedLots) return InpFixedLots;
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

   double h1 = iHigh(_Symbol, PERIOD_M1, 1);
   double l1 = iLow(_Symbol, PERIOD_M1, 1);
   double o1 = iOpen(_Symbol, PERIOD_M1, 1);
   double c1 = iClose(_Symbol, PERIOD_M1, 1);
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
      ? iLow(_Symbol, PERIOD_M1, 1) - iHigh(_Symbol, PERIOD_M1, 3)
      : iLow(_Symbol, PERIOD_M1, 3) - iHigh(_Symbol, PERIOD_M1, 1);
   return (gap / a) >= InpDispCut;
}

void TryArm()
{
   if(g_lockDay || g_lockPerm) return;
   if(PosCount() > 0 || OrderAlive(g_pend)) return;
   if(g_tradesToday >= InpMaxTradesDay) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(ask - bid > InpMaxSpreadPts) return;

   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   int bar = BarNo();

   for(int pass = 0; pass < 2; pass++)
   {
      bool sellSide = (pass == 0);
      Setup s = sellSide ? g_sell : g_buy;
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

      double lots = LotFor(risk);
      if(lots <= 0.0) continue;

      // NO TAKE PROFIT. E-137 measured every fixed target and all of them
      // banked less than the give-back trail.
      bool ok = sellSide
         ? trade.SellLimit(lots, lvl, _Symbol, stop, 0.0, ORDER_TIME_GTC, 0, "SS sweep")
         : trade.BuyLimit(lots, lvl, _Symbol, stop, 0.0, ORDER_TIME_GTC, 0, "SS sweep");
      if(ok)
      {
         g_pend = trade.ResultOrder();
         g_pendBar = bar;
         g_pendDir = dir;
         g_pendStop = stop;
         PB_NoteOrder(g_pend, (bid + ask) / 2.0);
         Log(StringFormat("armed %s limit at %.*f, stop %.*f (%.2f ATR), %.2f lots",
                          sellSide ? "SELL" : "BUY", dg, lvl, dg, stop,
                          risk / s.atr, lots));
         if(sellSide) ResetSetup(g_sell); else ResetSetup(g_buy);
         return;
      }
      Log(StringFormat("arm failed: %d %s", trade.ResultRetcode(),
                       trade.ResultRetcodeDescription()));
   }
}

void AgePending()
{
   if(!OrderAlive(g_pend)) { g_pend = 0; return; }
   if(BarNo() - g_pendBar > InpSetupLife) KillPending("unfilled and stale");
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
         g_posBar = BarNo();
      }
      g_peakPrice = (dir > 0) ? MathMax(g_peakPrice, px) : MathMin(g_peakPrice, px);

      double runUp = dir * (g_peakPrice - entry);
      if(runUp > 0.0)
      {
         int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
         double cand = NormalizeDouble(entry + dir * runUp * (1.0 - InpGiveBack), dg);
         bool better = (dir > 0) ? (cand > sl) : (cand < sl);
         double md = MinStopDist();
         bool room = (md <= 0.0) || (MathAbs(px - cand) >= md);
         if(better && room)
            trade.PositionModify(tk, cand, 0.0);
      }

      if(BarNo() - g_posBar >= InpMaxBars)
      {
         trade.PositionClose(tk);
         Log("time exit");
      }
   }
}

//==================== GUARDS =======================================
int DayStamp()
{
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   return t.year * 10000 + t.mon * 100 + t.day;
}

void CheckGuards()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_peakEq) g_peakEq = eq;
   if(!g_lockDay && g_dayStartEq > 0.0
      && eq <= g_dayStartEq * (1.0 - InpMaxDayLossPct / 100.0))
   {
      g_lockDay = true;
      KillPending("daily loss limit");
      Log("DAILY LOSS LIMIT - no new trades today");
   }
   if(!g_lockPerm && g_floor > 0.0 && eq <= g_floor)
   {
      g_lockPerm = true;
      KillPending("max drawdown");
      Log("MAX DRAWDOWN - stopped");
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
   g_atr = iATR(_Symbol, PERIOD_M1, 14);
   if(g_atr == INVALID_HANDLE) { Print("[SS] ATR handle failed"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(20);

   ResetSetup(g_sell);
   ResetSetup(g_buy);

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayStartEq = eq; g_peakEq = eq;
   g_floor = eq * (1.0 - InpMaxDDPct / 100.0);
   g_dayStamp = DayStamp();

   int corner = InpBoxCorner == 0 ? CORNER_LEFT_UPPER  :
                InpBoxCorner == 1 ? CORNER_RIGHT_UPPER :
                InpBoxCorner == 2 ? CORNER_LEFT_LOWER  : CORNER_RIGHT_LOWER;
   PB_Init("SS.", "SWEEP SNIPER " + SS_BUILD, InpMagic, InpShowProfitBox,
           corner, InpBoxX, InpBoxY, "SWEEP  liq");
   if(InpTrackMagic2 != 0) PB_AddStrategy(InpTrackMagic2, InpTrackLabel2);
   if(InpTrackMagic3 != 0) PB_AddStrategy(InpTrackMagic3, InpTrackLabel3);

   PrintFormat("[SS] === SWEEP SNIPER %s === pivot %d, sweep %.2f ATR, wick <= %.3f, "
               "stop %.2f ATR past the extreme, RISK CAP %.2f ATR, give back %.0f%%",
               SS_BUILD, InpPivotBars, InpSweepAtr, InpWickCut, InpStopBufAtr,
               InpMaxRiskAtr, InpGiveBack * 100.0);
   Print("[SS] Measured (variant B, the one that runs): 2579 trades, 23.6/day, "
         "65.1% win, +309.5 points, 107.3 control se, OOS +0.0991 vs IS +0.1241, "
         "walk-forward 5 of 5, max drawdown GBP12.68, worst trade -GBP4.63.");
   Print("[SS] THE RISK CAP IS NOT AN OPTIMISATION. Uncapped, the worst single "
         "trade was 57% of a GBP60 account and the max drawdown 63%. Read E-138 "
         "before raising InpMaxRiskAtr.");
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
   int ds = DayStamp();
   if(ds != g_dayStamp)
   {
      g_dayStamp = ds;
      g_dayStartEq = AccountInfoDouble(ACCOUNT_EQUITY);
      g_tradesToday = 0;
      g_refusedToday = 0;
      g_lockDay = false;
      Log("new trading day");
   }

   CheckGuards();

   datetime b = iTime(_Symbol, PERIOD_M1, 0);
   if(b != g_lastBar)
   {
      g_lastBar = b;
      UpdateSetups();
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

   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry == DEAL_ENTRY_IN)
   {
      g_tradesToday++;
      g_pend = 0;
      g_posDir = 0;                       // TrailStop re-seeds from the position
      PB_PromoteOrder((ulong)HistoryDealGetInteger(trans.deal, DEAL_ORDER),
                      (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID),
                      HistoryDealGetDouble(trans.deal, DEAL_PRICE));
      Log("FILLED");
      return;
   }
   if(entry == DEAL_ENTRY_OUT)
   {
      g_posDir = 0;
      g_peakPrice = 0.0;
      g_pbDirty = true;
      Log(StringFormat("closed, profit %.2f",
                       HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));
   }
}
