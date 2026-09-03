# RUN THIS — live package, 2026-09-03

Four files. Two EAs for MT5, two indicators for TradingView.

| file | put it | what it is |
|---|---|---|
| `JARVIS/ea/build/SuperTrendSniper.mq5` | MQL5/Experts | build **2.21** |
| `JARVIS/ea/build/LiquiditySniper.mq5` | MQL5/Experts | build **3.05** |
| `JARVIS/pine/XAUUSD_CLEAN_3_7.pine` | TradingView | SuperTrend, by eye |
| `JARVIS/pine/LIQUIDITY_CLEAN_1_6.pine` | TradingView | Liquidity, by eye |

**Recompile both EAs (F7).** The chart prints its build stamp on the first line.
If it does not read 2.21 / 3.05, MetaEditor has not rebuilt and none of this is
running.

## The stop is wide on purpose, and this is what makes that safe

`InpMinStopCostX = 7` forces the stop wide enough that the spread is at most a
seventh of the risk — without that the edge is gone (E-089). A wide stop with
nothing faster behind it is just a bigger bet, so there is now a **disaster
brake**, checked on every tick, ahead of everything else:

- **1.8 ATR against an open loser inside 2 bars → closed at market.**
- **Spread blows out past 3x its own average → closed at market.** That is what
  news looks like from inside an EA, and a stop is not dependable while it lasts.

Every TIGHTER brake was measured and every one LOSES money — the trades they cut
recover. Cutting at 0.40 of the stop costs 779 points on 1h. This one fires on
about 6% of trades and its cost is inside the noise. It is insurance priced at
zero, and tightening it is measurably paying to feel safer.

---

## Set these three, then leave it alone

**1. `InpDemoOnly = true` → run it on demo first.** Set it false only when you
have decided to go live. It refuses to start on a live account otherwise, on
purpose.

**2. Lots.** `InpUseFixedLots = true`, `InpFixedLots = 0.01` until £100, then
0.02, then 0.03. Nothing else changes when you move up.

**3. Nothing else.** Every other default is a measured number and the tooltip on
each one carries its measurement. If you change a default you are changing a
result.

---

## What the chart tells you, and what to watch

Line 1 is the build stamp and a **live clock**. If the clock is frozen the EA is
not running — that is the whole reason it is there.

Line 3 is the one that matters:

```
>>> TOTAL NOW £x      PEAK £y      GIVEN BACK £z <<<
```

`GIVEN BACK` is your "up 4-5 pound and somehow closed in loss", as a number, live.
It should stay small now: the profit stop sits **at the broker** from 1.0R of
peak onwards, so a spike cannot take back what a market close was too slow to hold.

The `SAME-DIR / ALTERNATING` line is a live experiment. You said back-to-back
same-direction signals lose; on my data they carry 86% of the profit. **Your
account will settle it in a few sessions.** If SAME-DIR goes negative on real
fills, that is a real finding and the fix is one input.

---

## What the liquidity Pine draws now

The DEMA, the LuxAlgo levels, BUY/SELL, and the position box. Nothing else is
on by default.

Two things were added for the manual trade:
- **M5 and M15 swing levels feed the M1 chart.** An M5 swing high is a real
  level on an M1 chart — it is where M5 traders' stops sit — and without it an
  M1 chart only ever sees M1 structure. They feed both the entry search and the
  take-profit. (`Trade M1 INSIDE M5/M15 levels`, on.)
- **A dot prints at every level the LIVE trade reaches**, in its favour. That is
  the bank-some-here moment on a manual trade. It is a mark, not a signal — the
  EA does not act on it and neither should you unless the trade has already paid
  for itself.

## The one number to send me back

`spread now / avg / worst` on the readout, after a session.

Everything downstream turns on it. `InpMinStopCostX = 7.0` makes the EA widen
its stop until the spread is at most a seventh of the risk — so on M1:

| your spread | stop becomes | risk at 0.01 |
|---|---|---|
| 0.46 | 3.92 points | £3.09 |
| 0.30 | 2.80 points | £2.20 |
| **0.20** | **2.10 points** | **£1.65** |

A tighter spread buys a tighter stop automatically, on every timeframe, with no
setting to change. You have said your spread is not large — this is the input
that turns that into money instead of into an argument.

---

## What is honest about this package

**Measured and shipped:**
- No ceiling on winners. The cap was costing 13-76% of expectancy (E-090); the
  top 5% of trades carry 68% of the profit and a 3R cap was deleting them.
- Profit stop held at the broker, not a tick-reactive market close (E-086).
- Mid-range flips sized to a quarter — they carry 53% of all losses, and it
  holds out of sample in all four splits (E-085).
- The liquidity EA targets the **next level**, not a flat 2R. Same money,
  31% win rate, average win **+3.21R** (E-087).
- Every threshold is in R or ATR, never money — money thresholds do not survive
  a change of timeframe or lot size, and that bug had the EA holding trades for
  0.9 bars (E-083).

**Not measured, and I will not pretend otherwise:**
- **There is no M1 data in this repository.** Every number above is 15m/1h.
  M1 frequency — the thing your whole £50-100/day rests on — is the one term I
  cannot compute. `JARVIS/ea/tools/ExportHistory.mq5`, dragged onto an M1
  chart, ends that permanently.
- FX is rejected on both strategies. This is XAUUSD only.
- The strongest word any of it has earned is PROMISING.
