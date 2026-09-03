# The two charts — everything on them, in plain words

## Install

TradingView → **Pine Editor** → paste the whole file → **Save** → **Add to chart**.
Separate charts for the two scripts. They are different systems.

## Set these three first, or every money figure is wrong

**LIVE TRADING (manual)** group:

| Setting | Set it to |
|---|---|
| Your lot size | `0.01` |
| Money per 1.0 of price, at 0.01 lots | `1.00` for XAUUSD on most brokers — check your contract size |
| How many bars until I actually click | `1` (minimum — 0 would be look-ahead and is blocked) |

---

# LIQUIDITY SNIPER — what everything on the chart means

## The levels

| On the chart | Meaning |
|---|---|
| **SSL** label | Sell-side liquidity — resting stops **above** price. A rally runs into these |
| **BSL** label | Buy-side liquidity — resting stops **below** price. A selloff runs into these |
| Next to the label: `3 held / 1 broke ~14.2pt` | What price did the last times it was here, and how far it moved after |
| Green label | This zone tends to **hold** |
| Red label | This zone tends to **break** |
| Line thickness | How many times it has been retested |
| Faded grey line | Already taken out — still useful as a flip zone |
| **SWEEP** mark | A level was just taken. This is the event the whole strategy is built on |

Levels come from: swing pivots at three sizes, previous day high/low, previous
**week** high/low, session highs/lows, and pivots from three higher timeframes.
The structural ones are **sticky** — micro-levels can never push them off the chart.

## The order book — top left

Four orders you can place right now, off the nearest live level each side:

| order | what it bets |
|---|---|
| **BUY LIMIT** at support | the level holds |
| **SELL LIMIT** at resistance | the level holds |
| **BUY STOP** above resistance | the level breaks |
| **SELL STOP** below support | the level breaks |

Each row gives entry, stop, target, **R:R**, and that zone's record. R:R shows
red under 1. Stops sit slightly beyond the level so the wick that tests it does
not trigger them. The four prices are drawn as dotted lines on the chart.

The limits and stops are deliberately opposite bets on the same two prices —
whichever way it resolves, your order is already worked out.

## The eight setup types

Every signal is labelled with which one fired:

| setup | what it is |
|---|---|
| **BREAK** | a level is taken out and price continues |
| **BOUNCE** | price tests a level and it holds |
| **RETEST** | a broken level is revisited and holds from the other side |
| **PULLBACK** | in a trend, price returns to the moving average and goes again |
| **BREAKOUT** | a quiet range ends |
| **GAP FILL** | price returns into an unfilled 3-bar imbalance |
| **INVERSE GAP** | a gap **failed** — price closed through it, so it now works from the other side |
| **ORDER BLOCK** | the last opposite candle before a move that broke structure |

## The panel — top right

1. **TODAY** — your money, realised + open, at your lot size
2. **Structure** — bullish / bearish, and CHoCH when it turns
3. **Price is** — cheap (discount) or expensive (premium), with % of range
4. …then the filters, open trades, missed entries, and signals per day

## The scoreboard — bottom left

**This is the one that answers "which setups should I take".**

Every finished trade is filed under the setup that produced it: how many taken,
win rate, total R, total money. **Green = keep taking it. Red = switch it off.**

History cannot rank these setups — a confluence score built from every measured
factor separated winners in only 5 of 8 markets and ran backwards on gold 15m.
So the ranking comes from your results, in your money.

## The record — bottom right

Last trades with **got / peak / money / exit**, then two summary rows. The one
to watch is **EXECUTION**: what % you kept of what the trades were worth at
their best. Low "kept" with lots of green = your exits are the problem, not
your entries.

---

# SUPERTREND SNIPER

Same signal as the MT5 EA — SuperTrend(7, 1.2) flip with DEMA(200) agreement.

**CHOP GUARD is on by default.** SuperTrend is tight, which is why it catches
moves early and also why it whipsaws when price goes nowhere. It counts flips
and sits out when they stack up. Panel says `CHOPPY - 5 flips, sitting out`.

**Measured, on GOLD 1h:**
- **71.7% of signals close back through the entry within 3 bars.** That is the fakeout rate.
- Of signals that reached +1R, the median first went **0.35R against you**; 10% went 0.85R against. A stop tighter than ~0.9R removes one winner in ten.
- Waiting 0.30 ATR for a better price: **+0.451R** out-of-sample vs **+0.321R** for a market entry — but 23% never fill. Off by default because you want signal count.

---

## Honest status

Nothing here has cleared the significance bar. ~780 configurations tested; the
luck threshold is around t = 3.65 and the best out-of-sample result is +2.47.

More importantly: **at 15m and 1h these markets test as random walks** — 40
variance-ratio tests, not one significant. No entry pattern can extract a
directional edge from that. It does **not** cover M1, which is genuinely
different and untested, and it does not cover discretionary reading of context.

Trade small, use the scoreboard to find what *you* convert, and treat every
number here as a measurement rather than a promise.

## If it does not compile

These are written without access to a Pine compiler. `check_pine.py` catches
undeclared names, use-before-declaration, arity, table bounds, drawings in
ternaries, illegal line wrapping and nested function declarations — but passing
it means those specific faults are absent, **not** that the file compiles.
Paste the exact error text back and it gets fixed immediately.
