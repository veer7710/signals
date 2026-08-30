# Liquidity Sniper v1 — how to use it

1. TradingView → Pine Editor → paste `LiquiditySniper_v1.pine` → Save → Add to chart.
2. Works on any timeframe. Start on M5 or M15 to judge it; M1 has the worst
   signal-to-spread ratio on gold.

## What is drawn

| Element | Meaning |
|---|---|
| Red dotted lines / zones above | Sell-side liquidity (stops of shorts) |
| Green dotted lines / zones below | Buy-side liquidity (stops of longs) |
| Line thickness | How many times that level was retested — thicker = more resting orders |
| Faded grey line | Level already taken out |
| BUY / SELL label | Setup fired, all filters passed |
| Green box | Entry → take profit |
| Red box | Entry → stop loss |
| ✓ / ✕ | Trade closed at target / stop |
| Top-right panel | Why it is or is not trading right now |

Only the live trade box plus the last 2 completed ones stay on screen.

## The setting that matters most

**Trade direction** defaults to `Continuation (tested)`.

This is the opposite of what most liquidity indicators do, and it is the
central research finding. Measured over 10,000+ sweeps on GOLD, US500, EURUSD
and GBPUSD, first-touch resolution, ties counted as losses:

| | GOLD 15m |
|---|---|
| Fade the sweep (the usual assumption) | 44.5% |
| Coin flip at the same bars | 49.2% |
| **Follow the sweep** | **54.1%** |

Follow beat fade on 5 of 5 markets. Fading was worse than random.

`Reversal (classic)` is included ONLY so you can flip it and see the difference
on your own charts. It is the weaker mode.

## The expansion filter

The panel will often say **"NO — waiting"**. That is the point.

Measured on GOLD 15m and 1h independently:

| Condition | Chance of a 3+ ATR move in the next 40 bars |
|---|---|
| ADX 0-15 | **90-91%** |
| ADX ≥ 40 | 66-68% |
| ATR ≥ 2× its own median | **25%** |

Volatility contraction precedes expansion. When ATR is already stretched and
ADX is already high, the move has mostly happened. The filter refuses those.

If you want more signals, raise `max ATR / median ATR` and `max ADX` — but you
are then taking the setups that measured worse.

## Honest status

The continuation direction is **measured**, not proven. Once realistic spread
and next-bar fills are applied it has **not** cleared a multiple-testing
significance bar. Forward-test it on demo before it touches a funded account.

## If it does not compile

It was written without access to a Pine compiler. Paste the exact error text
back and it gets fixed immediately.
