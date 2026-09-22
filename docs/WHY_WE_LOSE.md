# Why are we losing? — entry, exit, setup, strategy, or conditions

Not a win-rate backtest. `research/attribution.py` decomposes every trade into
an **exact identity**, so the loss is assigned rather than guessed at:

```
actual = setup_max − entry_cost − exit_cost − spread
```

| term | meaning |
|---|---|
| `setup_max` | the peak, measured from the best fill that actually traded in the entry window. The ceiling on the idea. |
| `entry_cost` | how much worse the real fill was than that. **This is "not hitting top tick", in money.** |
| `exit_cost` | how much of the peak was handed back. |
| `spread` | the fee. Certain. |

---

## The answer

GOLD 1h, de-trended, ATR-3 trail — the *good* exit:

| | sweep continuation | pullback continuation | momentum |
|---|---|---|---|
| setup offered | +42.45/trade | +40.33 | +42.52 |
| **lost to EXIT** | **−29.64 (69.8%)** | **−28.58 (70.8%)** | **−29.57 (69.5%)** |
| lost to ENTRY | −9.49 (22.4%) | −10.34 (25.6%) | −10.56 (24.8%) |
| lost to SPREAD | −0.30 (0.7%) | −0.30 (0.7%) | −0.30 (0.7%) |
| **kept** | +3.17 | +1.27 | +2.23 |

**The exit is roughly 70% of the leak. The entry is about 24%. All three
families give the same answer, so it is not family-specific.**

### Bounded to what is actually reachable

"Perfect entry" and "perfect exit" are hindsight and flatter everything. Bounded
instead by what the two shipped mechanisms can really deliver — the retail limit
getting one noise band better at a 60% fill rate, and a trail keeping 85% of
peak rather than 100%:

| GOLD 1h | now | + entry fix | + exit fix | both |
|---|---|---|---|---|
| sweep continuation | 1102 | 2358 | **9745** | 11001 |
| pullback continuation | 409 | 1641 | **8342** | 9573 |
| momentum | 608 | 1631 | **7371** | 8395 |

**The exit fix is worth about seven times the entry fix.**

### And that ordering is not an artefact of the 85% assumption

| trail keeps | entry gain | exit gain | ratio |
|---|---|---|---|
| 50% | 1256 | 5395 | **4.3×** |
| 70% | 1256 | 7068 | 5.6× |
| 85% | 1256 | 8643 | 6.9× |
| 95% | 1256 | 9749 | 7.8× |

Even at a trail keeping **half** the peak — worse than the give-back the EA runs
today — the exit is still the bigger number.

---

## Answering each of your questions separately

**Is it the entry?** Partly. 22–26% of the leak, worth about £1 of every £5 the
exit is worth. The retail-limit fix is correctly aimed but it is the smaller
lever.

**Is it the exit?** **Yes. ~70%.** This is the answer.

**Is it the trade / the setup?** No. **0% of setups offered less than the
spread** — every one of them had something in it. Setup selection is not where
the money goes.

**Is it the strategy?** No. Three unrelated entry families produce the same
~70/24/1 split. A different strategy would inherit the same problem.

**Is it market conditions?** Partly, and not the way you would expect. Trades
per regime, points per regime:

| GOLD 1h | RANGE | MIXED | TREND |
|---|---|---|---|
| pullback continuation | 206 / **+252** | 107 / **+395** | 16 / **−237** |
| sweep continuation | 197 / **+734** | 103 / +290 | 48 / +78 |
| momentum | 86 / −2 | 122 / **+680** | 64 / −70 |

**TREND is the losing regime on two of three families.** The money is made in
RANGE and MIXED. That is consistent with gold's own statistics — variance ratio
below 1 at every horizon — and it is the opposite of how the EA has been aimed.

**Are we in drawdown too much?** That is the exit question again, and the
breakeven ladder addresses it directly: ~9% of trades reach breakeven and then
fail, and those become scratches instead of full stops.

---

## What this means for what to build next

1. **Stop adding entry gates.** They chase 24% of the problem. Eight now exist
   and seven ship OFF.
2. **The exit is the whole game.** The ladder and the chandelier are the right
   work. Anything else that touches the exit gets priority.
3. **Stop aiming at TREND.** It loses on two of three families.
4. Spread is 0.7% of the gross offered — though it is still 48% of the *net*
   loss, because the net is small. Both numbers are true; they have different
   denominators, and the brief's 48% figure uses the net one.

---

# The 80% win-rate claims, decomposed

`docs/WINRATE_RESEARCH.md` took nine published claims and did the arithmetic on
each. For a driftless series `P(target before stop) = S/(S+T)`, so the only part
of a claimed win rate that could be a real edge is what is left over after the
geometry is subtracted.

| claim | target/stop | geometry alone gives | claimed | **residual** |
|---|---|---|---|---|
| 5-pip target / 20-pip stop scalp | 0.25 | **80.0%** | "80%+" | **0** |
| "5–8 pip target, 3–6 pip stop", cost-adjusted | 0.64 | **61.0%** | 55–70% | −6 to +9 |
| Connors RSI(2), 75–82% | **no stop** | **→100% as T→0** | 75–82% | n/a |
| Bollinger 3σ "100%" | — | — | 100% | **n = 4** |
| viral "9:30 candle", 773W/533L from a "1,000-trade" test | — | — | 59.2% | **773+533 = 1,306. Does not sum.** |
| ORB 15-min, 10y S&P | 1.80 | 35.7% | 56% | **+20.3** |
| ORB + volume filter | 1.50 | 40.0% | 64% | **+24.0** |

**Six of nine are arithmetic artefacts.** The 5-pip/20-pip scalp needs 80% *just
to break even* — its own source says so. Connors has no stop at all, so its win
rate tends to 100% as the target tends to zero, and it trades 7 times a year.

Only two carry a real unexplained residual — both ORB variants, both from
unverified marketing pages, and both in the family that the one pre-registered
study tested and failed.

### The reference ceiling

| anchor | number |
|---|---|
| Gao/Han/Li/Zhou (JFE 2018), intraday momentum, SPY 1993–2013 | predictive R² = **1.6%** |
| that R² as a directional hit rate | **54.0%** |
| Mesfin (arXiv 2605.04004), 14 OHLCV signal families, 947 days, 5-min, pre-registered | **0 of 14 passed** |

**A peer-reviewed intraday effect is worth about four percentage points, not
forty.** And an independent pre-registered study of fourteen OHLCV families
found none that cleared friction — converging with this repo's own results from
a completely different direction.

## Two corrections to my own work

**1. What I called "absorption" was never absorption.** Real absorption is an
order-flow object: volume hitting a level without price moving. `data/*.json`
carries `[timestamp, O, H, L, C]` — **five fields, no volume.** So delta, CVD,
footprint, stacked imbalance, volume profile and VWAP are all flatly impossible
here, and what I built and tested was a range-and-close statistic wearing an
order-flow name. That is very likely why it failed its own stop rule in §10.

**2. TPO value-area rotation — tested, and the "80% rule" is the same artefact.**
A TPO profile is built from *time*, not volume, so it genuinely is computable
from OHLC. It is the one profile object testable here, and it had never been
tested. Prior session's value area only, so no lookahead:

| GOLD 1h | n | win% | $/trade | t | CI95 |
|---|---|---|---|---|---|
| VA 70%, accept 2 periods | 451 | 37.0% | +0.90 | 1.16 | [−0.56, +2.48] |
| VA 80%, accept 1 period | 602 | 31.4% | +1.14 | 1.50 | [−0.29, +2.60] |

**The "80%" is a first-passage probability with no stop.** Add a 1 ATR stop and
it is 31–37%. On 15m it is negative. The $/trade is mildly positive on 1h and
comparable to the best families here — so it is a lead, not a result.

## On "leg to leg, wick to wick"

A swing at bar *i* is only confirmed at bar *i+k*. Any leg drawn after the fact
carries *k* bars of lookahead, and — more importantly — **every leg that gets
drawn is one that went somewhere.** Failed moves were never drawn. The
reliability is the selection, not the rule.

The causal version is already measured here (§23): past 2 ATR of leg travel the
win rate *rises* to 35.6% while expectancy goes negative.

## Sample-size reality check

| data | effective n |
|---|---|
| 15m files (60–73 calendar days) | **n ≈ 60–73** for any once-per-day event — fatally small |
| 1h files (734–813 days) | ~1,000–1,400 after cross-symbol correlation |

Detection needs n≈600 for a 54% effect, 196 for 60%. **So a 60% effect would be
comfortably visible here, and an 80% one would be unmissable. Its absence across
every test run in this repo is itself evidence.**
