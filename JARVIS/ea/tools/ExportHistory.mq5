//+------------------------------------------------------------------+
//|  ExportHistory.mq5 — get JARVIS the data it has never had         |
//|                                                                   |
//|  WHY THIS EXISTS                                                  |
//|  Every experiment in this project has run on 15m and 1h data,     |
//|  because that is the only data in the repository. Veer trades M1  |
//|  for the SuperTrend EA and M15/M5/M1 for liquidity entries, and   |
//|  does not act on H1 at all. So every conclusion so far has been   |
//|  drawn on timeframes he does not trade, and said so in its own    |
//|  caveats — over and over.                                         |
//|                                                                   |
//|  The data exists. It is sitting in his MT5 terminal. This script  |
//|  writes it out in the exact format JARVIS/research/engine.py      |
//|  loads, so it drops straight into the data/ folder and every      |
//|  study in the repo can be re-run on the real timeframes.          |
//|                                                                   |
//|  HOW TO USE IT                                                    |
//|  1. Put this file in  MQL5/Scripts/  and compile it (F7).         |
//|  2. Open a XAUUSD chart. Press Home a few times and wait — MT5    |
//|     only exports bars it has actually downloaded. The script      |
//|     tells you how many it found; if the number looks small, let   |
//|     the chart load further back and run it again.                 |
//|  3. Drag the script onto the chart. Tick "Allow" if asked.        |
//|  4. Files land in  MQL5/Files/  named like  GOLD_M1.json .        |
//|     Send those files back.                                        |
//|                                                                   |
//|  The output name uses GOLD rather than XAUUSD because that is     |
//|  what the repository's loader already expects.                    |
//+------------------------------------------------------------------+
#property copyright "JARVIS"
#property version   "1.00"
#property strict
#property script_show_inputs

input string InpOutName   = "GOLD";  // name for the output files
input bool   InpDoM1      = true;    // export M1
input bool   InpDoM5      = true;    // export M5
input bool   InpDoM15     = true;    // export M15
input bool   InpDoH1      = false;   // H1 is context only, not traded
input int    InpMaxBars   = 200000;  // cap per timeframe (200k M1 ~ 140 days)

//+------------------------------------------------------------------+
int WriteOne(ENUM_TIMEFRAMES tf, string tag)
{
   MqlRates r[];
   ArraySetAsSeries(r, false);          // oldest first, which is what we write

   int avail = Bars(_Symbol, tf);
   if(avail <= 10)
   {
      PrintFormat("%s: only %d bars available. Open a chart on this timeframe "
                  "and press Home until it stops loading, then run again.",
                  tag, avail);
      return 0;
   }

   int want = MathMin(avail, InpMaxBars);
   int got  = CopyRates(_Symbol, tf, 0, want, r);
   if(got <= 0)
   {
      PrintFormat("%s: CopyRates failed (%d). Error %d.", tag, got, GetLastError());
      return 0;
   }

   string fn = InpOutName + "_" + tag + ".json";
   int h = FileOpen(fn, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      PrintFormat("%s: cannot open %s for writing. Error %d.", tag, fn, GetLastError());
      return 0;
   }

   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   FileWriteString(h, "[");

   // The last element of r is the bar still FORMING. It is written by nobody:
   // an unfinished bar in a research file is a look-ahead bug waiting to be
   // discovered six experiments later.
   int last = got - 1;
   bool first = true;
   for(int i = 0; i < last; i++)
   {
      if(!first) FileWriteString(h, ",");
      first = false;
      FileWriteString(h, StringFormat("[%d,%s,%s,%s,%s]",
                       (long)r[i].time,
                       DoubleToString(r[i].open,  dg),
                       DoubleToString(r[i].high,  dg),
                       DoubleToString(r[i].low,   dg),
                       DoubleToString(r[i].close, dg)));
   }
   FileWriteString(h, "]");
   FileClose(h);

   PrintFormat("%s: wrote %d bars to MQL5/Files/%s  (%s to %s)",
               tag, last, fn,
               TimeToString(r[0].time, TIME_DATE | TIME_MINUTES),
               TimeToString(r[last - 1].time, TIME_DATE | TIME_MINUTES));
   return last;
}

//+------------------------------------------------------------------+
void OnStart()
{
   PrintFormat("ExportHistory on %s. Files go to MQL5/Files/ — open that "
               "folder with File > Open Data Folder.", _Symbol);

   int total = 0;
   if(InpDoM1)  total += WriteOne(PERIOD_M1,  "M1");
   if(InpDoM5)  total += WriteOne(PERIOD_M5,  "M5");
   if(InpDoM15) total += WriteOne(PERIOD_M15, "M15");
   if(InpDoH1)  total += WriteOne(PERIOD_H1,  "H1");

   if(total == 0)
      Print("Nothing was exported. MT5 only gives out bars it has already "
            "downloaded, so load the charts further back and try again.");
   else
      PrintFormat("Done. %d bars written in total.", total);
}
//+------------------------------------------------------------------+
