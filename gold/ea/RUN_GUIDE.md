# Running XAUUSD_LEAN.mq5

## Install
1. MT5 → File → Open Data Folder → `MQL5/Experts/` → drop `XAUUSD_LEAN.mq5` in.
2. MT5 → Navigator → right-click Expert Advisors → Refresh.
3. Open it (F4 → MetaEditor) and press **F7** to compile.
   **It has never been compiled** — there is no MetaEditor on the machine it was written
   on. If F7 reports errors, send me the exact text and I will fix them.
4. Attach to a **XAUUSD M1** chart. Tick "Allow Algo Trading". Make sure the
   AutoTrading button in the toolbar is green.

## Scroll the chart back a day before attaching
It needs ~1000 M1 bars of history to converge the Supertrend chain the way TradingView
does. If the log says "only N bars available", scroll back or let history load, or drop
`InpWarmupBars` to 400.

## Read the Experts log first
On attach it prints a preflight block: symbol, settings, money per point read from YOUR
symbol, cost of a full stop, and how many losses the daily halt allows. If anything there
looks wrong, stop and tell me before letting it trade.

It will also print a loud TIMEFRAME WARNING on M1. That is expected and correct — see below.

## The panel — what to actually look at
```
---- TODAY: did gold move, and did we get any of it? ----
  gold range          42.3 pt   (4012.80 - 4055.10)
  gold total path    318.6 pt   (all the back-and-forth)
  trades                  37 closed, 1 open
  OFFERED (peaks)    +54.2 pt   <- what our trades put on the table
  CAPTURED            -7.9 pt   <- what we actually kept
  CAPTURE            -14.6 %    <- the execution read
  money              -5.79 GBP
  signals seen 38 | entries refused 1  last: spread 1.14 > cap 1.00
```
- **gold range / total path** — how much gold moved at all. Context.
- **OFFERED** — the sum of each closed trade's best moment. What the signal actually
  handed us.
- **CAPTURED** — what we realised, spread included.
- **CAPTURE %** — captured ÷ offered. **This is the number you asked for.**

### How to read it
- **OFFERED small** → the signal gave nothing. No execution change can help, and the
  problem is the entry, not the exit.
- **OFFERED large but CAPTURE % low** → execution is the problem, and it is worth fixing.
- **entries refused > 0** → something is blocking trades. The reason is on the panel.
  QUAD's worst habit was refusing silently; this one always tells you.

Every closed trade also prints `took +X pt of a +Y pt peak (Z%)` in the log, and lands in
`MQL5/Files/lean_journal_<SYMBOL>.csv` with a `capture_pct` column, so you can sort it later.

## What I expect to happen, stated in advance
It should **lose money**, and fastest on M1. Measured on 3.83M real bars, this signal is
anti-predictive on M1 (gross −0.030 pt/trade, t = −5.44, before any cost) and a median
**64.6%** of each swing is already gone when the arrow prints.

So this run is not a profitability test. It is three checks:
1. does it fill, hold and exit correctly on PU Prime
2. do the fills and the journal match my simulator (if they do, the research apparatus is
   trustworthy and we can test new signals fast)
3. is CAPTURE % anywhere near what I predict (about −7% on M1)

If CAPTURE % comes out much *better* than that, my model is wrong somewhere and I want to
know immediately.

## Safety defaults
- `InpLots` 0.01, `InpMaxOpenPositions` 1
- `InpMaxDailyLoss` 10.0 — halts NEW entries for the day; open trades keep their stop
- Stop = 1.5 × ATR, floored at 1.00 pt and 3 × spread, capped at 8.00 pt, broker minimum
  respected. The stop is a real broker-side stop, so it works even if the EA or terminal dies.
- Every optional exit (trailing, profit lock, fixed target, time stop) defaults **OFF**
  because 38 variants were tested and none beat simply holding to the opposite signal.
- Spread cap 1.00 — raise it if the panel shows entries being refused on spread.

## If you want to try the one thing that measured better
A trailing stop at 0.5 × ATR roughly halved the bleed in testing (−0.213 → −0.117 pt/trade).
It is still a loss, and it stops you out of nearly every trade, but if you want to see it:
set `InpTrailAtrMult = 0.5` and `InpTrailArmUSD = 0.0`.
