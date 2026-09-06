# Live chart evidence — 2026-08-31, XAUUSD 3m (Veer's screenshots)

The first real out-of-repo measurement of either system. It outranks every
backtest here, because it is the actual product on the actual instrument at the
actual timeframe traded.

## SuperTrend Sniper — LAST 12 trades

| metric | value |
|---|---|
| win rate | **33%** |
| total | **-6.9R** |
| at 0.01 lots | **-40.27** |
| average | **-0.58R per trade** |
| how they ended | **TP 0 · early 0 · SL 8** |
| hit 1R at any point | 25% |
| kept | **-89%** |
| left behind | 14.7R (-85.17) |

**Zero take-profits in twelve trades.** Eight stop-outs. The strategy did not
give back profit — it never reached profit. Only 25% of trades ever touched 1R.

This is consistent with E-037 (these markets test as random walks at the
timeframes measured) and with E-035 (71.7% of signals close back through the
entry within three bars). It is NOT consistent with the premise this project
has run on for weeks — "a majority of trades go into profit, we just don't
close in that profit". On this evidence, at 3m, they do not go into profit.

## Liquidity Sniper — signal flood

    Signals: 121 today   119.6/day avg

The chart in the screenshot is a solid wall of overlapping BUY and SELL labels
with no readable price action underneath. **This is my error, not a market
observation.** Over the last several sessions I loosened, in order: entry
cooldown 3 -> 1 bar, concurrent setups 3 -> 4, R:R floor 1.2 -> 1.0, level age
5 -> 3 bars, setup types 2 -> 8, and scoped the expansion gate to BREAK setups
only so the other six bypassed it entirely.

Each change was defensible alone. Together they produced ~120 signals a day,
which is not a signal generator, it is a noise generator - and it made the
chart unusable, which was the exact opposite of the instruction given
repeatedly ("dumb simple to read and follow").

**Lesson L-011:** loosening several independent gates in sequence, each for a
locally good reason, compounds multiplicatively. Signal count must be measured
after every change, not assumed. The Signals row on the panel existed and I
never once looked at what it would read.

---

## 2026-09-06 — THE FIRST HONEST LIVE MEASUREMENT IN THIS PROJECT

Veer ran SUPERTREND SNIPER 5.1 on XAUUSD M1 and photographed the panel. This is
the first number this project has ever produced from **live current bars with a
corrected fill model** rather than from 2018 backtest data.

```
  measured over   31 Aug -> 04 Sep 2026
  trades                304        62.8 a day
  win rate            32.6%        99W 205L
  if traded         -117.1pt       -£92.12
  avg trade          -0.385pt
  SYSTEM            -117.1pt       stop / trail / stall, 304 trades
  FLIP & HOLD        -85.0pt       flip to flip, 304 trades
  exit adds          -32.1pt
  cost paid         -103.4pt       -£81.34
```

### What it says, and it is not what it looks like
**88% of the entire loss is transaction cost.** Gross, the system is about
−13.7 points over 304 trades. **It is not losing because its direction is wrong.
It is losing because it trades 63 times a day on M1 and pays 63 round trips.**

And the exit stack is **actively harmful**: holding flip-to-flip loses 85 points
where the stop/trail/stall version loses 117. The exits designed to protect the
trade cost 32 points.

### Why this matters more than any backtest here
It is 4 days and 304 trades, which is a small sample and cannot settle
anything on its own. But it is **live, current, real-spread data**, and it
agrees with what Veer says when he looks at the chart: *"entries are just shit,
we catch every trend not every volume candle"*. The panel and his eye are saying
the same thing, which is the first time in this project that has happened.

### The direction it points
Not "find a better filter". **Trade less.** SuperTrend(7, 1.2) on M1 is a very
tight band on a fast clock and it flips on noise. The open questions are in
`st_churn.py`: does widening the multiplier cut churn without losing the trend;
does the exit stack help at all; does a higher-timeframe direction gate cut
trades a day - which is exactly what Veer asked for at the start of this project
and which has never been tested on this system.
