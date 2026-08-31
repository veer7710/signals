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
