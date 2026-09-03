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

   // MT5 ONLY HANDS OUT BARS IT HAS ALREADY DOWNLOADED, AND THE DOWNLOAD IS
   // ASYNCHRONOUS. The first call to CopyRates for a timeframe the terminal has
   // not cached returns a few hundred bars (or -1) and STARTS the fetch in the
   // background. A script that takes that first answer as the truth writes a
   // useless file and looks like it worked - which is the most likely reason
   // this has never produced a usable M1 export.
   //
   // So: ask, wait, ask again, until the count stops growing. Requesting the
   // bars is itself what triggers the download; there is no other way to make
   // the terminal fetch deep M1 history from a script.
   int want = InpMaxBars;
   int got = 0, prev = -1, still = 0;
   for(int attempt = 0; attempt < 120; attempt++)   // up to ~60 seconds
   {
      got = CopyRates(_Symbol, tf, 0, want, r);
      if(got >= want) break;                        // got everything asked for
      if(got == prev)
      {
         still++;
         // three identical answers in a row means the server has no more
         if(still >= 6 && got > 0) break;
      }
      else
      {
         still = 0;
         if(got > 0)
            PrintFormat("%s: downloading... %d bars so far", tag, got);
      }
      prev = got;
      Sleep(500);
   }

   if(got <= 10)
   {
      PrintFormat("%s: only %d bars after waiting. Open a chart on %s, press "
                  "Home and hold it until the bar count stops rising, then run "
                  "this again. Some brokers also cap how far back M1 goes.",
                  tag, got, EnumToString(tf));
      return 0;
   }
   if(got < want)
      PrintFormat("%s: got %d of the %d requested - that is everything the "
                  "server has.", tag, got, want);

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
   Print("This can take up to a minute per timeframe: M1 history is downloaded "
         "on demand and the script waits for it. Do not close the terminal.");
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
