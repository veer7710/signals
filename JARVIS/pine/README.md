# The two charts — how to actually take a trade

You have a live account. Read this part first, then the detail below.

## Install (2 minutes each)

TradingView → **Pine Editor** → paste the whole file → **Save** → **Add to chart**.

- `SuperTrendSniper_v1.pine` — the same strategy the MT5 EA trades.
- `LiquiditySniper_v1.pine` — the liquidity/sweep strategy, manual only.

Run them on separate charts. They are different systems and blending their
signals gives you a third system nobody has tested.

## Set these three before anything else

Both scripts, **LIVE TRADING (manual)** group. If these are wrong, every money
figure on the chart is wrong.

| Setting | Set it to | Why |
|---|---|---|
| Your lot size | `0.01` | What you are actually clicking |
| Account currency per 1.0 price move, per 0.01 lot | `1.00` for XAUUSD on most brokers | 0.01 lot of a 100 oz contract = 1 oz, so $1 of price = $1. **Check your broker's contract size.** |
| Bars between signal and your actual entry | `1` | See below. Do not set it to 0. |

### Why "bars between signal and your actual entry" exists

A signal is only real when the bar closes. Then you have to see it, and then
you have to click. That is not free, and the price has moved by the time you
are filled.

Every other indicator hides this by pretending you were filled at the signal
price. These do not. Set the delay to how long you realistically take, and
the entry line, stop, target, P/L and the whole record are all computed from
the price you would actually have got. The panel tells you what the delay
cost, in price, on the last fill.

**At 0 the numbers flatter you and the chart stops being a record of trades
you could have taken.**

## Reading a live trade

| On the chart | Meaning |
|---|---|
| **BUY** / **SELL** label | Signal fired at that bar's close |
| Solid coloured line | **Your actual fill price.** It extends as the trade runs |
| Green box | Fill → take profit |
| Red box | Fill → stop loss |
| Dashed line | Where the trail stop currently sits |
| Faded grey boxes | The last 10 completed trades, so you can see how they went |
| ✓ | Closed at target |
| ✕ | Closed at stop |
| TRL / TIME / FLIP / BE | **Closed early** — trail hit, stalled out, opposite signal, break-even |
| Label at the right edge | Live R and live money at your lot size |
| Grey ✕ (SuperTrend chart) | A flip a filter refused. Watch these — if the ones it skips keep running, the filter is costing you |

### The panel, top right

Tells you why it is or is not trading right now. `ENTER NOW` means a signal has
fired and its fill bar has arrived.

On the SuperTrend chart, set **"Size positions for this much risk"** to what you
are willing to lose on one trade and the panel gives you the lot size for the
current stop distance — so you are not on a calculator while the entry runs away.

### The record table, bottom right

The last trades in R and in money at your lot size, then two summary rows:

- **TOTAL** — count, win %, total R, total money, average R
- **how they ended** — TP / early / SL

That last row is the one to watch. If **early** dominates, your target is too
far away for this market. If **SL** dominates, your stop is too close to it.

---

# SuperTrend Sniper

Every default matches `JARVIS/ea/build/SuperTrendSniper.mq5`. The chart and the
EA are one strategy. Change a setting in one and change it in the other, or you
are running two systems and will not know which is working.

**Signal:** SuperTrend(ATR 7, mult 1.2) flips, DEMA(200) sloping the same way.
That entry was left alone deliberately — it was not the problem.

**What was actually wrong was the exits.** Measured on GOLD, US500, EURUSD and
GBPUSD with next-bar fills, first-touch resolution and ties counted as losses:

| Exit rule | Result |
|---|---|
| Early break-even | **Worst rule on all four markets** (−0.161R to −0.308R) |
| Tight trail | Second worst |
| Wide 3-ATR trail, armed immediately | Best on these entries |
| 50-bar time cap | Beat a 20-bar cap |

Break-even is in the settings so you can switch it on and watch it lose, rather
than wonder. Leave it off.

**The one filter that survived a hold-out:** ADX ≥ 35 at entry measured −0.132R.
ADX < 20 measured +0.304R. Entering when the trend is already extended is the
losing bucket, and refusing those held up on data it was not chosen on.

The session filter (NY 13–20 UTC) measured best on gold but is **off by default** —
it was measured on one instrument and it cuts your trade count hard.

---

# Liquidity Sniper

**The setting that matters most: Trade direction — `Continuation (tested)`.**

This is the opposite of what most liquidity indicators do, and it is the central
research finding. Over 10,000+ sweeps, first-touch resolution, ties lose:

| | GOLD 15m |
|---|---|
| Fade the sweep (the usual assumption) | 44.5% |
| Coin flip at the same bars | 49.2% |
| **Follow the sweep** | **54.1%** |

Follow beat fade on 5 of 5 markets. Fading was worse than random. The mechanism
is Osler's stop-cascade research: a stop-loss to sell **is** a market sell order,
so a cluster of stops beyond a level is fuel in the direction of the break, not
a spring that reverses it.

`Reversal (classic)` is kept only so you can flip it and see the difference on
your own charts. It is the weaker mode.

**The expansion filter** will often say "NO — waiting". That is the point:

| Condition | Chance of a 3+ ATR move in the next 40 bars |
|---|---|
| ADX 0–15 | **90–91%** |
| ADX ≥ 40 | 66–68% |
| ATR ≥ 2× its own median | **25%** |

Volatility contraction precedes expansion. Want more signals? Raise the ATR and
ADX ceilings — but you are then taking the setups that measured worse.

**Timeframe:** M5 or M15 to judge it. M1 on gold has the worst signal-to-spread
ratio of anything tested.

---

## Honest status — read this before it sees money

Roughly 780 configurations have now been tested against this data. At that
count, the best of a set of **worthless** strategies would be expected to score
about **t = 3.65** on luck alone. The best out-of-sample result measured here is
**t = +2.09**.

That is encouraging. It is **not** proof, and nothing in this repo has cleared
that bar. Both scripts are research instruments to forward-test, not money
machines. Forward-test on demo before either touches a funded account.

## If it does not compile

These were written without access to a Pine compiler. Paste the exact error
text back and it gets fixed immediately.
