# Correlation — why 5 accounts is one bet, and why 4 markets is not a basket

Measured on 570 days of daily returns from the repo's own data.

## The correlation matrix

|  | GOLD | US500 | EURUSD | GBPUSD |
|---|---|---|---|---|
| **GOLD** | 1.00 | 0.11 | 0.03 | 0.00 |
| **US500** | 0.11 | 1.00 | -0.07 | -0.08 |
| **EURUSD** | 0.03 | -0.07 | 1.00 | **0.81** |
| **GBPUSD** | 0.00 | -0.08 | **0.81** | 1.00 |

Gold, US500 and the FX bloc are genuinely independent — good. But **EURUSD and
GBPUSD correlate at 0.81**: they are close to the same bet twice, because both
are mostly a bet on the US dollar.

So the "four market" test set is really about **three** independent bets. That
is one more reason nothing reached significance: trend following needs
diversification to work, and published research uses 50+ markets across
equities, bonds, FX, energy, metals and agriculture.

## The number that kills the 5-account plan

Running ONE strategy across 5 funded accounts gives correlation **1.00**
between those accounts. Not 0.8, not 0.6 — exactly 1.00, because they are
literally the same trades.

Worked example. Suppose a strategy has a 2% chance on any given day of a loss
large enough to breach a daily loss limit:

| Setup | P(all 5 breach same day) | In plain terms |
|---|---|---|
| 5 genuinely independent strategies | 0.000000003 | about 1 in 312,000,000 days |
| **5 copies of one strategy** | **0.0200** | **about 1 in 50 days** |

Five accounts running the same EA is **not five income streams.** It is one
income stream with five sets of challenge fees, and every account dies on the
same afternoon.

The 2% is illustrative. The real figure comes from the strategy's own daily
loss distribution, which requires the MT5 export.

## What follows from this

1. **Scaling accounts does not reduce risk.** It multiplies fees while leaving
   risk unchanged. The only real protection is genuinely different strategies,
   different markets, or different timing — and "different parameters on the
   same logic" does not count, because the trades still coincide.
2. **This compounds the copy-trade detection problem.** Identical fills across
   firms are exactly what triggers payout denial, so the naive implementation
   is both the riskiest financially AND the most likely to be flagged.
3. **Before any multi-account plan**, the single-account strategy has to have a
   measured edge. Right now none does.
