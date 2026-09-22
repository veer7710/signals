# WINRATE_RESEARCH — where high intraday hit rates actually come from

Companion to `SNIPER_AUDIT.md`. That doc established the priors this one builds on:
win rate is bought with geometry (85% banked at 0.25R → 82.5% OOS, worst PF of four
shapes); for a driftless series `P(target before stop) ≈ S/(S+T)`; sweeps, FVG, OB,
BOS and CHoCH all scored at or below a random-entry baseline as standalone triggers.

**Sourcing convention.** WebFetch and curl are blocked in this environment. Only
WebSearch works and it returns result *summaries*, not page text. So:
`[search summary]` = read off a search-result summary, page never opened, **not
independently verified**. `[own knowledge]` = my own knowledge, no source consulted.
`[measured here]` = computed in this repo. No number below is a verified primary-source
figure. Every win-rate claim marked `[search summary]` should be treated as an
advertisement until someone opens the page.

---

## 0. The reference ceiling

Two anchors worth keeping in view before reading any 80% claim.

| anchor | number | source |
|---|---|---|
| Gao/Han/Li/Zhou, *Market Intraday Momentum*, JFE 2018 — first half-hour return predicts last half-hour, SPY 1993–2013 | predictive **R² = 1.6%** | [search summary] |
| that R² converted to a directional hit rate: ρ=√0.016=0.126, P(sign agrees)=0.5+arcsin(ρ)/π | **54.0%** | [own knowledge] |
| Mesfin, *Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures* (arXiv 2605.04004), 14 signal families, 947 days, 5-min, 2021–2025, pre-registered criteria (t≥2.0, n≥30, positive after 2-pt friction) | **none of 14 passed**; max gross 0.07–1.50 pts/trade vs 2.0-pt friction | [search summary] |

The best peer-reviewed intraday directional effect in the literature is worth about
**four percentage points of hit rate**. Anything claiming forty is claiming to be ten
times the size of a JFE paper. That is the frame for section 1.

---

## 1. Scalping claims — the geometry arithmetic, done explicitly

`P_geom = S/(S+T)` for a driftless series. "Residual" = claimed win% − P_geom, and is
the only part that could be a directional edge.

| # | strategy as described | T/S | **P_geom** | claimed | residual | verdict |
|---|---|---|---|---|---|---|
| 1 | 5-pip target / 20-pip stop scalp `[search summary]` | 0.25 | **80.0%** | "80%+" | **0** | **pure artefact.** The source itself says this needs 80%+ just to break even |
| 2 | "5–8 pip target, 3–6 pip stop" `[search summary]` | 1.44 | **40.8%** | 55–70% | +14 to +29 | see cost note ↓ |
| 2b | same, cost-adjusted: spread+comm eats ~30% of gross, effective RR 1.25→0.64 `[search summary]` | 0.64 | **61.0%** | 55–70% | **−6 to +9** | **mostly artefact.** Costs move the geometry line *up*, through the claim |
| 3 | viral "9:30 candle" scalp, self-reported 1,000-trade backtest: 773W/533L `[search summary]` | not stated | **unknown** | 59.2% (=773/1306, not /1000 — the numbers don't even sum) | **uncomputable** | claim is internally inconsistent; cannot be attributed |
| 4 | ORB 15-min, 10y S&P `[search summary]` | 1.80 | **35.7%** | 56% | **+20.3** | the one claim with a large unexplained residual — see §2 |
| 5 | ORB + volume filter, 1.5× target `[search summary]` | 1.50 | **40.0%** | 64% | +24.0 | needs volume (unavailable here); extra filter = extra selection |
| 6 | Connors RSI(2) on SPY, 181 trades / 26 yrs `[search summary]` | **no stop** | **→100% as T→0** | 75–82% | n/a | open-ended hold. "Win" = any positive exit. Not intraday, 7 trades/yr |
| 7 | Bollinger 80-period 3σ, whole bar outside `[search summary]` | n/a | n/a | 4/4 = 100% | n/a | **n=4.** Not a result |
| 8 | VWAP 2σ reversion `[search summary]` | **no stop** | n/a | 63% "reversion rate" | n/a | first-passage statistic, not a P&L. Same summary: ~45% unfiltered, "fails badly on trend days" |
| 9 | Market Profile "80% rule" `[search summary]` | no stop | n/a | 80% | n/a | the same summary states the 80% is **a rule-of-thumb label, not an audited statistic**, and measured rates are "often below 80%" |

**Reading.** Of nine documented high-win-rate claims, **six are arithmetic or definitional
artefacts** (1, 2/2b, 6, 7, 8, 9), **one is uncomputable** (3), and **two (4, 5) carry a
real residual** — both ORB, both from marketing blogs, both unverified, and both in the
family the MNQ falsification study tested and failed.

A win rate quoted without its T/S ratio, or with an open-ended exit, is not a claim about
prediction. It is a claim about geometry with the geometry omitted.

---

## 2. Mean reversion at intraday horizons

| mechanism | documented hit rate | horizon | status |
|---|---|---|---|
| VWAP 2σ reversion | 63% filtered / ~45% unfiltered `[search summary]` | intraday, open-ended | **VWAP is not computable here** — no volume. TWAP proxy only |
| ORB fade (wide opening range) | source says explicitly **do not fade** a wide 30-min OR; data favours the first break `[search summary]` | same session | fade is the *wrong sign* per the one source found |
| Opening range structure | 30-min OR ≈ 30–35% of session range; day's high/low usually in first or last hour `[search summary]` | session | testable on OHLC |
| Gap fill, 1–2% gap (QQQ) | **45%** same day `[search summary]` | session | testable on OHLC |
| Gap fill, ≥2% gap | **30–33%** `[search summary]` | session | testable |
| Gap fill, "common" small gaps | 70–75% `[search summary]` | session | testable; note this is a *smaller target*, i.e. geometry again |
| Gap fill day-of-week | Thu 82% vs Mon 65% `[search summary]` | session | testable — and a textbook multiple-testing trap (5 days tested, best reported) |
| Bollinger 3σ touch | 4 trades / 6,050 bars `[search summary]` | n/a | no sample |

Note the pattern across the gap rows: fill rate falls monotonically with gap size. That
is `S/(S+T)` again — a bigger gap is a more distant target. It is consistent with zero
directional edge.

---

## 3. Order flow / microstructure — what is flatly impossible here

This repo has **OHLC and nothing else**: bars are `[ts, open, high, low, close]`, no
volume field at all (verified in `data/*.json`).

| concept | needs | possible on this data? |
|---|---|---|
| Footprint / bid-ask volume at price | trade-side classification per price level | **NO** |
| Delta, Cumulative Volume Delta | signed trade volume | **NO** — and `[search summary]` notes most platforms already *approximate* delta with a tick rule; we have no ticks either |
| Absorption (high delta, price stalls) | the "effort" half is delta | **NO.** Only "result" (range) is observable |
| Stacked imbalances, exhaustion | volume at price | **NO** |
| DOM / iceberg / spoofing | L2 book | **NO** |
| Volume profile, VPOC, volume value area | volume at price | **NO** |
| **TPO profile, TPO value area, 80% rule** | *time* at price | **YES** — TPO is time-based by construction; distribute each bar's H–L across price bins. This is the one profile object that survives on OHLC |
| VWAP | volume | **NO**. TWAP / anchored mean of (H+L+C)/3 is a proxy, not the same object |
| ATR, ER, range statistics | OHLC | YES |

**Consequence:** every "absorption" or "delta divergence" entry in this project's specs is,
on this data, a range-and-close statistic wearing an order-flow name. `SNIPER_AUDIT.md` §10
already measured that object and it failed its own stop rule. That is not a coincidence —
the order-flow half was never in the data to begin with.

---

## 4. How published win rates are manufactured

| mechanism | effect on reported win% | detectable from the writeup? |
|---|---|---|
| No stop / exit-on-opposite-signal | →100% as target→0 | yes — check if a stop is quoted at all |
| Target quoted, stop omitted | hides the whole geometry | yes |
| Costs excluded | on a 5-pip target, spread+comm ≈ 30% of gross `[search summary]` | rarely |
| Open trades at backtest end counted as wins | inflates | almost never |
| Parameter selection over many trials | Deflated Sharpe: P(selecting an overfit strategy) rises rapidly with trial count, Bailey & López de Prado `[search summary]` | almost never |
| Best symbol / best year / best session reported | inflates | no |
| Tiny n presented as a rate | 4/4 = "100%" `[search summary]` | yes — check n |

On this project the multiple-testing correction is already quantified: `SMC_SPEC.md`'s
best-of-N line puts the null at **57.5%** for six variants `[measured here]`. A "60% win
rate" found after trying six things is not significant.

### "Leg to leg, wick to wick" is a description, not a rule

A leg is only a leg once it has ended. To mark one you need a swing rule with lookback *k*,
and a swing at bar *i* is confirmed only at bar *i+k*. Any chart annotated after the fact
has *k* bars of lookahead in every marking. The reason leg-to-leg looks 80%-reliable is
that **every marked leg, by construction, went somewhere** — the moves that failed to
become legs were never drawn. It is a hindsight-selected sample of successful moves, and
the selection *is* the win rate.

The causal version is testable and partly already measured: `SNIPER_AUDIT.md` §23 found
that on 15m, expectancy dies past 2 ATR of leg travel **while win rate rises to 35.6%** —
more winners, less money. That is the same trap as the geometry exits.

---

## 5. Mechanisms with a genuine structural reason

| mechanism | why it could be real | usable here? |
|---|---|---|
| Intraday momentum (first ½hr → last ½hr) | overnight inventory + close-auction positioning; peer-reviewed | **yes**, OHLC only. Ceiling ~54% |
| Session-open effects | ~35% of daily volume in first 30 min, 50% in first hour `[search summary]`; genuine information release | **yes**, OHLC only |
| Gap as unauctioned region | no trade occurred there, so no inventory is defended there | **yes** |
| Auction rotation in balance | in balance the marginal participant sits at the edges; TPO value area is OHLC-computable | **yes** — and **never tested on this project** |
| Index rebalance / MOC imbalance | passive funds must trade at a known time; documented predictable dislocation `[search summary]` | **no** — equities/close-auction, and only ~10 quarterly events in this dataset |
| Macro news windows | scheduled, mechanical repricing | partly — no calendar in this repo |

---

## 6. Sample the repo actually has

| file | bars | calendar days | once-per-day events |
|---|---|---|---|
| GOLD_15m / US500_15m | 4,534 / 4,532 | **60** | 60 |
| EURUSD_15m / GBPUSD_15m | 5,643 | **73** | 73 |
| GOLD_1h / US500_1h | 13,737 / 13,700 | **734** (~524 trading) | ~524 |
| EURUSD_1h / GBPUSD_1h | 17,229 / 17,231 | **813** (~580 trading) | ~580 |

Detection thresholds, binomial, one-sided `[own knowledge]`:

| true hit rate | n for t=2 vs 50% | n for 80% power |
|---|---|---|
| 54% | 600 | 1,225 |
| 55% | 384 | 784 |
| 57.5% (the best-of-6 null) | 178 | 348 |
| 60% | 96 | 196 |

**The binding constraint.** A once-per-day event has n≈60–73 on 15m and n≈524–580 per
symbol on 1h. Pooling four symbols gives ~2,200 nominal, but US500/EURUSD/GBPUSD/GOLD are
correlated, so effective n is nearer 1,000–1,400. That means: **a 54% effect is at the
very edge of what this dataset can resolve; a 60% effect is comfortably resolvable; an 80%
directional effect would be unmissable.** Its absence in every test run here so far is
itself evidence.

---

## 7. Ranked: plausibly real, OHLC-testable, not yet falsified here

Ranked by (prior plausibility × testability × sample adequacy). All tests use **close-to-close
returns on confirmed bars only**, costs charged at the measured spread, and report
hit rate *with the T/S ratio alongside it* so geometry can never be mistaken for edge.

| # | mechanism | event definition | forward horizon | null it must beat | n needed | n available |
|---|---|---|---|---|---|---|
| **1** | **Intraday momentum** | sign of return over first *m* bars of the session (m=2 on 1h, m=2 on 15m), measured on the day's first confirmed bars | last 2 bars of the same session | **54.0%** (the published R²=1.6% implies this; beating 50% is not enough — it must beat the literature, and must clear the best-of-6 line at 57.5% if you test >1 value of m) | 600–1,225 | ~2,200 pooled 1h ✅ |
| **2** | **Gap / unauctioned region fill** | session open more than *g* ATR from prior session close, g ∈ {0.5, 1.0, 2.0} | same session | fill rate must be **above `S/(S+T)`** for that gap size, not above 50%. This is the key control — the published monotone decline with gap size is exactly what zero edge looks like | 384 (55%) | ~524–580/symbol ✅ marginal |
| **3** | **TPO value-area rotation (80% rule)** | build TPO profile from prior session OHLC bars (range split into bins, one count per bar touching a bin); 70% VA; event = open outside VA then **two consecutive bars closing inside** | touch of opposite VA edge before touch of the entry-side extreme | 57.5% best-of-6 (VA%, bin width, acceptance count are all free parameters — declare them before running) | 348 | ~524–580/symbol ✅ **untested on this project** |
| **4** | **Opening-range structure** | OR = first 30 min; event = close beyond OR edge | rest of session, target 1.8× OR width vs stop at OR mid | the ORB blog claim of 56% at RR 1.8 implies residual +20 pts. Null: **35.7%** (geometry) — but the honest bar is the MNQ study's, i.e. positive **after** 2-pt-equivalent friction | 196 (at 60%) | 60–73 on 15m ❌, ~524 on 1h ✅ (coarse OR) |
| **5** | **Session-boundary / first-hour high-low** | whether session extreme is set in hour 1 | session | 50% baseline on a random-hour null | 384 | ✅ |
| **6** | **Causal leg-to-leg** | swing with lookback k, **confirmed at i+k only**; entry on reclaim after counter-side sweep | next opposing swing | random-entry baseline (this repo's existing control) **and** the §23 result that expectancy dies past 2 ATR — so restrict to legs <2 ATR travel | 384 | ✅ 15m and 1h |

**Do not re-run** (falsified here already): standalone FVG, order block, BOS, CHoCH,
liquidity sweep as entry triggers; absorption-vs-expansion separation on 15m/1h gold;
fading distance-from-mean; fading range extremes; any exit shape that banks most of the
position at a fraction of R.

**Cannot run at all** (data does not exist): delta, CVD, footprint, absorption in its real
definition, volume profile, VWAP, stacked imbalance, index-rebalance flow.

### The blunt summary

Six of nine documented "70–90% win rate" claims are explained to within a few points by
`S/(S+T)` alone, or have no stop, or have n<10. The two with a real residual are both
opening-range variants from unverified marketing sources, and the only pre-registered
falsification study found covering that family reports **zero of fourteen** signal families
surviving realistic friction. Meanwhile the best peer-reviewed intraday directional effect
is worth about **54%**. If a mechanism on this list returns 60%+, the first hypothesis
should be a bug, the second should be lookahead, and only the third should be edge.
