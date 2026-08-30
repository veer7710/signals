# Strategy hunt — where the published DIRECTION edges actually are

**Purpose:** find short-horizon *direction* signals with genuine published
evidence that a retail MT5 trader can implement on XAUUSD or major FX, and
that are **not already tested in this repo**.

**Status of everything below: UNPROVEN.** Nothing here has been run against
`study.py`. These are literature-sourced hypotheses with codeable rules, not
results. Evidence quality is graded per idea.

Already excluded because the repo tested them: donchian breakout, MA
crossover, time-series momentum, ATR-stretch mean reversion, opening range
breakout, EMA pullback, liquidity sweep fade, liquidity sweep follow.

---

## BOTTOM LINE — the three most promising untested ideas, ranked

| # | Idea | Why it ranks here | Evidence grade |
|---|---|---|---|
| **1** | **Condition the trend signals you already have on the compression state (the LeBaron effect)** | It is the only idea that *uses* the repo's own strongest replicated finding as an input rather than starting over. The published claim is precisely that trend-following PnL concentrates in low-volatility regimes, and that this is the one slice that survived the post-2008 decay of short-horizon trend. Near-zero cost to test: it is a re-slice of results already computed. | **B+** — LeBaron (1992) plus a 2026 Bouchaud-group futures study that partitions explicitly by volatility |
| **2** | **Open-anchored intraday momentum (Gao/Han/Li/Zhou "market intraday momentum", Zarattini noise-area implementation)** | The single best-documented *intraday direction* effect in the literature: JFE 2018 original, Journal of Financial Markets 2022 replication across 16 international markets, plus Chinese metals-futures extension. It is **not** the ORB the repo already tested — different trigger, different holding window, different exit. And it can be validated on US500 first, where the evidence actually lives, before transferring to gold. | **A-** for equity indices, **C** for gold/FX transfer |
| **3** | **Intraday periodicity — same-clock-slot return continuation and local-hours drift** | Cheapest test in the whole document: pure OHLCV, no extra data, one pass over the bar series. Two independent literatures (Heston-Korajczyk-Sadka half-hour periodicity; Ranaldo/Breedon time-of-day FX drift) say a bar's *clock position* carries directional information. Also the natural "which direction" partner to a "when" filter. | **B** in equities and FX; **untested** in gold |

Honourable mention (#4): **pre-announcement drift around scheduled US macro
releases** — real, published, and directional, but it is partly a
leakage effect that release-policy changes have since attenuated. Details in
its own section.

---

## 1. Compression-conditioned trend continuation (the LeBaron effect)

### Why this is the highest-value idea in the document

The repo's strongest finding is that **volatility contraction predicts
expansion** (ADX 0-15 → a 3+ ATR move ~90% of the time; ATR at 2x median →
25%), replicated on GOLD 15m and 1h. The stated problem is that this predicts
size, not direction.

The literature says the size filter is *also* a direction filter — not
because compression picks a side, but because **trend-continuation signals
work far better inside low-volatility regimes**. This is the LeBaron effect,
named for LeBaron (1992), and it was re-confirmed in 2026 by Kurth, Eisler,
Rej and Bouchaud on futures: when they partition trend PnL by volatility,
low-volatility periods on small-tick contracts *continue to accrue positive
PnL even after the overall post-2008 PnL break*. Their stated mechanism: in
low-vol environments prices do not react violently to information arrival,
which raises the probability of **underreaction** to news, and underreaction
is exactly what a trend signal monetises.

Read against the repo's own results this reframes the earlier negatives.
Donchian on GOLD 1h gave +0.198R with t=+1.63 — directionally right,
statistically short. If the effect is concentrated in the low-vol slice, the
unconditional test is diluting a real signal with a regime where it does not
work. That is a testable claim, not a rescue narrative, and it has a hard
falsification: if the low-vol slice is not better than the high-vol slice,
the idea is dead and the earlier verdicts stand.

### Exact codeable rules

```
Regime variable (choose one; test both):
  compression = ADX(14) < 15                       # repo's own definition
  compression = ATR(14) < percentile_40(ATR(14), lookback=500 bars)

Signal (reuse the repo's EXISTING strategy functions unchanged):
  s = donchian_trend(...)      # or ma_crossover, or tsmom
Entry:
  take s's entry ONLY on bars where compression was TRUE at the
  decision bar (strictly: computed from bars <= decision bar)
Everything else — stop, target, sizing, fills — unchanged from the
existing implementation, so the comparison is apples-to-apples.

Required comparison table, per market:
  all bars | compression==True | compression==False
  and the DIFFERENCE with its own t-statistic
```

The number that matters is not the compression-slice expectancy on its own
(that is a subset and will be noisy) — it is the **difference between slices**
and whether the sign of that difference is stable across GOLD 15m, GOLD 1h,
US500, EURUSD, GBPUSD. Five markets, one directional prediction, is the same
design that made the sweep-follow result credible.

### Data required
None beyond what is in `data/` already. `GOLD_1h` is 13,750 bars
(2024-04-02 → 2026-08-24), `EURUSD_1h`/`GBPUSD_1h` 17,252/17,253 bars
(2023-11-07 → 2026-08-24), `US500_1h` 13,716 bars. Verified by direct read.

### Expected effect size
The Bouchaud paper reports the low-vol/high-vol split qualitatively
(low-vol slice keeps accruing, high-vol slice breaks) rather than as a
per-trade number, so **do not pre-commit to a magnitude**. The honest
prior: if this is real, the compression slice should show an expectancy
gap over the non-compression slice with a consistent sign in ≥4 of 5
markets. If the gap's t-stat cannot clear 2.0 pooled, treat as UNPROVEN.

### Evidence grade: B+
Strong mechanism, two independent sources decades apart, direct futures
evidence. Downgraded from A because neither source tests gold specifically
and because "condition an existing signal on a regime" is exactly the kind
of manoeuvre that manufactures false positives — the multiple-testing bar
must be applied to the *whole family* of (signal × regime definition)
combinations, not to the winner.

### The trap to avoid
The Bouchaud paper's headline finding is that short-term trend-following
**died around 2010** on small-tick contracts, and the survivor is *large-tick*
contracts. XAUUSD as a CFD is not a large-tick instrument. So the correct
reading is: the low-vol conditioning is the plausible survivor, and the
overall prior on short-horizon trend in gold should be *lowered*, not raised.

---

## 2. Open-anchored intraday momentum (market intraday momentum / noise area)

### The published claim

Gao, Han, Li and Zhou, *Market Intraday Momentum*, Journal of Financial
Economics 129(2) 2018 (SSRN 2440866; earlier draft 2552752). SPY 1993-2013:
**the first half-hour return predicts the last half-hour return.** Reported
numbers: scaled slope 6.94, significant at 1%, R² = 1.6%; adding the twelfth
half-hour return raises R² to 2.6%. The timing strategy on the sign of the
first half-hour return returned **6.67% p.a. with 6.19% volatility → Sharpe
1.08**. Predictability is *stronger on high-volatility days, high-volume days,
recession days and major macro release days* — note that this interacts with
the repo's volatility work in the opposite direction to the LeBaron effect,
which is itself informative and worth measuring.

Li, Sakkas and Urquhart, *Intraday time series momentum: global evidence and
links to market characteristics*, Journal of Financial Markets, Jan 2022:
16 developed markets, "economically sizable and statistically significant
both in- and out-of-sample in most countries". Pooled first-half-hour
coefficient reported as 2.86 with t = 7.53. ITSM is **stronger when liquidity
is low, volatility is high, and information is discrete**.

Extension into metals: the "night effect" paper on Chinese gold and silver
futures (Global Finance Journal 64, 2025) finds the predictive half-hour
*moved* when SHFE introduced night trading — before night trading the first
half-hour of the day session predicted; after, the first half-hour of the
**night session** predicted. That is the closest thing in the literature to
direct evidence for this family in gold, and its lesson is that **the anchor
is the session open that absorbs the overnight information flow**, which for
XAUUSD means testing several candidate anchors rather than assuming one.

### Why this is NOT the opening range breakout already tested

| | ORB (already tested) | Market intraday momentum |
|---|---|---|
| Trigger | price exceeds the high/low of the first N minutes | price exceeds a boundary derived from the *typical cumulative move from the open at that clock time over the last 14 days* |
| Check frequency | continuous / on breach | only at fixed clock times (HH:00 / HH:30) |
| Direction source | which side of the range breaks | the sign of the first interval's return, or the side of the boundary crossed |
| Hold | usually to target/stop | to a *specific later window* (last interval) or session close |
| Exit | fixed R | opposite boundary, or VWAP, or session close — never a fixed R multiple |

They share "the session open matters" and nothing else.

### Exact codeable rules — Version A (Gao et al., the cleanest test)

```
Define a session for XAUUSD. Candidate anchors, test all three, report all:
  A1: 00:00 UTC        (calendar/broker day open)
  A2: 08:00 UTC        (London)
  A3: 13:30 UTC        (COMEX open / US data window)

Let the session be split into K equal intervals (K=13 mirrors the paper's
13 half-hours; on 1h bars K=24 with 1h intervals is the practical version).

  r_first = return of interval 1  (from prior session close to end of
                                   interval 1 — the paper measures the first
                                   half-hour FROM THE PREVIOUS CLOSE, not
                                   from the session open; this matters)
  r_last  = return of interval K

Predictive regression (do this BEFORE any trading rule):
  r_last = a + b * r_first + e
  report b, Newey-West t, R^2, and the same for r_{K-1} added.

Trading rule (only if b is significant):
  at the START of interval K:
      if r_first > 0: go long  for exactly interval K
      if r_first < 0: go short for exactly interval K
      flat otherwise
  exit at the session close. No stop, no target — the paper's rule is
  a fixed-horizon hold, and adding a stop changes the estimand.
```

### Exact codeable rules — Version B (Zarattini/Aziz/Barbon noise area)

Zarattini, Aziz, Barbon, *Beat the Market: An Effective Intraday Momentum
Strategy for S&P500 ETF (SPY)*, SSRN 4824172 / SFI Research Paper 24-97.
2007 → early 2024, SPY: total return 1,985% net of costs, **19.6% annualised,
Sharpe 1.33**.

```
For each minute (or bar) t of the session:
  sigma_t = mean over the last 14 trading days of
            | close(same clock time, day d) / open(day d) - 1 |
            i.e. the average absolute move-from-open observed at THIS
            clock time over the last 14 sessions
  upper_t = open_today * (1 + N * sigma_t)
  lower_t = open_today * (1 - N * sigma_t)
  gap adjustment: if the prior overnight gapped DOWN, raise upper_t by
                  the gap size; if it gapped UP, lower lower_t by the gap.
  N is the boundary multiplier (paper's baseline effectively N=1;
  larger N = fewer, higher-conviction trades). Test N in {1.0, 1.5, 2.0}
  and report ALL of them, not the best.

Entry: checked ONLY at clock hour and half-hour marks (HH:00, HH:30).
  price > upper_t  -> long
  price < lower_t  -> short
Exit, whichever comes first:
  (a) stop-and-reverse at the opposite boundary
      (long stops at lower_t and flips short), OR
  (b) trailing exit at max(upper_t, session VWAP) for longs and
      min(lower_t, session VWAP) for shorts, OR
  (c) session close — always flatten, never hold overnight.
```

Note (b) requires VWAP, which requires volume. **The repo's JSON bars carry
no volume field** — verified: every row is `[timestamp, O, H, L, C]`, five
fields. So exit (b) is not runnable on current data; either use exit (a)
only, substitute a typical-price moving average for VWAP and label it as a
deviation, or re-export from MT5 with tick volume.

A follow-up by Maróy (SSRN 5095349, Jan 2025) optimises the parameters and
exits and reports Sharpe over 3.0 with >50% annualised returns on SPY.
**Treat that number as a red flag, not a target** — it is a parameter search
over the same 17 years of the same single instrument, which is the textbook
recipe for an inflated in-sample Sharpe. Cite it as a warning about how far
this family can be overfit.

### Data required
- Intraday bars with a clean, stable session definition. GOLD_15m in the repo
  covers only 2026-06-14 → 2026-08-24 (4,501 bars) — **too short**; roughly
  50 sessions gives ~50 observations of "interval K", nowhere near enough.
- GOLD_1h has 13,750 bars over ~2.4 years ≈ 600 sessions. Usable for the
  1-hour-interval version.
- **Recommended: export XAUUSD M5 or M15 from MT5 for 5+ years, with tick
  volume**, before spending much on this.
- US500_1h (13,716 bars, identical timestamps to GOLD_1h) should be tested
  FIRST as a code-validation replication — the published effect lives in
  equity indices, so if the implementation cannot find it on US500 the bug is
  in the code, not in gold.

### Expected effect size
Equity indices: Sharpe ~1.08 (Gao et al. timing rule), ~1.33 (Zarattini,
net of costs, with the trailing exit and hourly re-checks). R² of the
underlying predictive regression is 1.6-2.6% — **that is what a real
short-horizon direction edge looks like**, and it is a useful calibration
for the whole document. For gold, no published number exists; the honest
prior is "smaller, if present at all".

### Evidence grade: A- (equity indices) / C (gold and FX transfer)
JFE + JFM + a metals-futures extension is about as good as it gets for a
retail-implementable intraday effect. The transfer to XAUUSD is a genuine
open question, which is exactly why it is worth testing rather than assuming.

---

## 3. Intraday periodicity — clock-slot continuation and local-hours drift

### The published claims

**Heston, Korajczyk and Sadka**, *Intraday Patterns in the Cross-Section of
Stock Returns*, Journal of Finance 65(4) 2010: a striking pattern of **return
continuation at half-hour intervals that are exact multiples of a trading
day**, persisting for at least 40 trading days. With 13 half-hours per day the
significant lags are 13, 26, 39, ... — i.e. *the same clock slot on
subsequent days*. Volume, order imbalance, volatility and spreads show
similar periodicity but **do not explain the return pattern**. The effect is
more pronounced at, but not restricted to, the first and last half-hours.

**Ranaldo**, *Segmentation and time-of-day patterns in foreign exchange
markets*, Journal of Banking & Finance 33(12) 2009, and **Breedon & Ranaldo**,
*Intraday patterns in FX returns and order flow* (SNB WP 2011-04): currencies
systematically **depreciate during their own local trading hours and
appreciate during foreign trading hours**. The pattern shows up in order flow
— participants are net buyers of *foreign* exchange in their own hours — and
is described as "statistically and economically highly significant" and
persistent across many years and currencies, after controlling for calendar
effects. Applied to EURUSD this predicts EURUSD *down* in European hours and
*up* in US hours.

For gold there is a folk version of the same claim (the "London bias" —
daytime erodes, overnight accrues) which circulates mostly in gold-advocacy
sources and is entangled with manipulation narratives. **Do not cite it as
evidence.** The defensible academic anchor for gold is Iwatsubo, Watkins and
Xu, *Intraday seasonality in efficiency, liquidity, volatility and volume:
platinum and gold futures in Tokyo and New York* (Journal of Commodity Markets
2018): liquidity trading dominates the Tokyo day session while **informed
trading dominates the New York day session**. That is a microstructure fact
about *who* is trading when, and it makes a session-dependent drift plausible
without asserting one.

### Exact codeable rules

```
TEST 1 — clock-slot periodicity (Heston-Korajczyk-Sadka, adapted to one
         instrument as a time-series rather than a cross-section)

  Let S = number of bars per session (e.g. 24 for 1h bars on a 24h market).
  For every bar t, let slot(t) = t mod S.
  Estimate the autocorrelation of returns at lags 1..(5*S) and plot it.
  The published prediction is POSITIVE, significant spikes at lags
  S, 2S, 3S, ... and nowhere in between.
  This is a pure statistical test with NO trading rule. Run it first.
  Null: shuffle returns within each slot across days, 1000 times, and
  compare the lag-S autocorrelation against that distribution.

  Only if the spikes exist, build:
  signal(t) = sign( mean of returns in slot(t) over the previous K days )
              with K in {10, 20, 40}
  Enter at the open of bar t in that direction, exit at the close of bar t.
  Fixed one-bar hold. No stop — a stop changes the estimand.

TEST 2 — local-hours drift (Ranaldo)

  For each instrument, bucket every bar by UTC hour 0..23.
  Report mean return, t-stat, and n per bucket, plus a Bonferroni-corrected
  threshold for 24 buckets (t ~ 3.0 at alpha=0.05, which is conveniently
  the repo's existing multiple-testing bar).
  Split the sample in half by date and require the SAME buckets to survive
  in both halves. Anything that only appears in one half is noise.

  For EURUSD the pre-registered directional prediction is:
      negative mean return in ~07:00-15:00 UTC (European hours)
      positive mean return in ~14:00-21:00 UTC (US hours)
  Stating the prediction BEFORE running it is what makes this a test rather
  than a fishing expedition.

  For GOLD there is no pre-registered direction. Run it as exploratory and
  hold it to the corrected threshold plus the split-half requirement.
```

### Data required
None beyond `data/`. `GOLD_1h`, `EURUSD_1h`, `GBPUSD_1h`, `US500_1h` all
carry UTC timestamps aligned to the hour (verified: 1712030400 is exactly
divisible by 3600). Caveat: broker-server time may differ from UTC and DST
shifts will smear the buckets — check the timestamp convention of the export
before drawing conclusions about a specific hour.

### Expected effect size
Ranaldo's effect is measured in basis points per session, not per bar. The
crucial arithmetic (**computed from the repo's own data**): median ATR(14) on
GOLD 1h is 13.79 price units, so a 0.20 USD round-trip cost is 1.45% of one
ATR; on GOLD 15m median ATR(14) is 8.21, so the same 0.20 is 2.43% of one
ATR. Costs are therefore *not* the binding constraint for a one-bar hold on
gold — the binding constraint is that the mean per-bar drift is tiny relative
to the per-bar standard deviation, so **this family needs thousands of
observations to reach significance**, which is exactly why the statistical
test must come before the trading rule.

### Evidence grade: B
Top-tier journals, but the equity result is cross-sectional (long the high-
past-slot-return stocks, short the low) and does not automatically become a
single-instrument timing rule. The FX result is a direct single-instrument
prediction and is the stronger part. Gold is exploratory.

---

## LEAD-LAG — the highest-value angle, and the most disappointing evidence

This was the brief's priority. The honest finding after searching the
microstructure and commodity literature: **the intraday gold ↔ dollar ↔
yields relationship is overwhelmingly contemporaneous, and the published
lead-lag results that do exist are between instruments a retail MT5 trader
cannot separately trade.**

### What the literature actually establishes

**1. The gold-dollar relationship is real but simultaneous, and the causality
tests are at DAILY-or-slower frequency.** VAR/Granger work finds DXY Granger-
causes gold *and* gold Granger-causes DXY (bidirectional), with gold and the
dollar negatively correlated 73% of the time over 3-month windows and 95%
over 10-year windows. Bidirectional causality at daily frequency is the
signature of a common driver (US real rates / risk appetite) hitting both
instruments at once — not of a tradeable lead. Search across the intraday
literature turned up **no peer-reviewed 5-minute-frequency study establishing
that DXY leads gold**.

**2. The real-yield link is an elasticity, not a lead.** A 100bp rise in
10-year real yields has historically been associated with an ~18% decline in
the inflation-adjusted gold price. That is a level relationship measured at
daily-or-lower frequency and it is contemporaneous. There is no published
intraday drift of gold *after* a real-yield move.

**3. Where lead-lag IS documented, it is futures→spot and it is 0-5 minutes.**
The precious-metals high-frequency literature finds one-minute futures returns
leading cash returns by 0-5 minutes. A retail MT5 trader typically has
XAUUSD spot CFD only; the leading leg (COMEX GC) is on a different venue with
different data. And 0-5 minutes at retail latency and retail spread is not an
exploitable window.

**4. The commodity-currency result is real but at the WRONG horizon.** Chen,
Rogoff and Rossi, *Can Exchange Rates Forecast Commodity Prices?*, QJE 125(3)
2010: commodity-exporter exchange rates have "surprisingly robust" power to
predict global commodity prices, in- and out-of-sample. That is a
**quarterly** result on aggregate commodity indices. Notably they also report
that the reverse — commodity prices Granger-causing exchange rates — holds
in-sample but **is not robust out-of-sample**, which is precisely the failure
mode to expect from a naive "AUD leads gold" intraday test.

**5. Cross-asset FX predictability exists but self-destructs.** Hasselgren,
Peltomäki and Graham, *Speculator activity and the cross-asset predictability
of FX returns* (International Review of Financial Analysis 72, 2020): equity-
market and commodity-market predictability of FX returns **dissipates when
speculators are active in the FX market**, via gradual information diffusion.
Read straight, this says: cross-asset lead-lag survives only where the lagging
market is under-monitored. XAUUSD and EURUSD are the two most heavily
monitored instruments a retail trader has access to. That is a structural
argument against finding a lead there, and it should lower the prior a lot.

**6. Gold miners do not lead gold.** GDX carries equity beta, leverage and
idiosyncratic corporate risk, underperformed GLD by roughly 6.5% annualised
over 2006-2025, and decouples from gold during crises by tracking equities.
No credible lead-lag claim, and not on MT5 anyway.

**7. Gold-silver ratio mean reversion is genuinely contested.** Cointegration
between gold and silver is documented but described as unstable across
regimes and weakening over long horizons. The positive backtests are recent,
ML-augmented preprints on 2015-2025 (Mittal & Mittal, SSRN 5710242) —
in-sample-flavoured and not independently replicated. Against them, at least
one systematic review reports failing to find any robust profitable strategy
from the ratio, either for equities or for gold and silver themselves. Verdict:
**do not build on this without doing the cointegration test yourself first.**

### What is nevertheless worth ONE careful test

The repo already holds **timestamp-aligned multi-symbol data** — verified:
GOLD_1h and US500_1h share 13,700 common bar timestamps; GOLD_1h and
EURUSD_1h share 13,595; GOLD_15m and US500_15m share 4,500. That makes the
test nearly free, and a clean negative is worth having in writing.

```
LEAD-LAG PROTOCOL (run it as a statistical test; do NOT jump to a strategy)

Let g_t = log return of GOLD at bar t
    x_t = log return of the candidate leader at bar t
          candidates available now: US500, EURUSD, GBPUSD
          (EURUSD/GBPUSD serve as an inverse dollar proxy; a synthetic
           dollar index = -0.5*ret(EURUSD) - 0.5*ret(GBPUSD) is the closest
           DXY substitute the repo can build today)

STEP 1 — establish the contemporaneous relationship:
    g_t = a + b0 * x_t + e_t          report b0 and R^2
    Expect this to be significant. It is NOT an edge.

STEP 2 — the actual lead-lag test:
    g_t = a + b0*x_t + b1*x_{t-1} + b2*x_{t-2} + b3*x_{t-3} + e_t
    The ONLY coefficients that matter are b1..b3.
    Report Newey-West t-stats.
    PRE-COMMIT: b1 must clear |t| > 3.0 and hold the same sign in a
    split-half test, or this is dead.

STEP 3 — the reverse direction (mandatory):
    x_t = a + c0*g_t + c1*g_{t-1} + ...
    If gold leads US500 as much as US500 leads gold, you have found
    autocorrelated noise plus non-synchronous bar closes, not information
    flow. This step is what kills most naive lead-lag findings.

STEP 4 — residual reversion (the only version with a plausible mechanism):
    resid_t = g_t - b0 * x_t     (b0 estimated on a rolling window that
                                  ENDS at t-1, never including t)
    z_t = zscore(cumulative resid over the last k bars, lookback 200)
    Test: does z_t predict g_{t+1}? Fade high |z|.
    Mechanism: gold has temporarily decoupled from the dollar factor and
    snaps back. This is the pairs-trade version and it is the only one the
    cointegration literature gives any support to.
    Same bar: |t| > 3.0, split-half stable, or dead.

STEP 5 — the null that must be beaten:
    Shuffle the leader series by whole days (preserving intraday shape,
    destroying the cross-asset alignment), re-run 1000 times, and place
    the real b1 in that distribution. Report the percentile.
```

### What is missing from the repo's data that would matter

- **XAGUSD** (silver) — the gold-silver pair is the one cross-asset
  relationship with a cointegration literature behind it, and MT5 brokers
  carry it. Worth exporting.
- **A real DXY or USDJPY/USDCHF** — the two-currency synthetic above is a
  poor dollar proxy because EURUSD and GBPUSD correlate at 0.81 in this
  repo's own measurement (`findings/07_correlation.md`), so the synthetic is
  close to "EURUSD twice".
- **Tick volume** — every idea involving order flow requires it and the
  current export has none.

### Lead-lag verdict

**Do not build the next strategy on lead-lag.** Run the protocol above once,
write down the answer, and move on. The prior from the literature is that
you will find a large contemporaneous b0 and a b1 indistinguishable from
zero. If b1 *is* significant on a liquid pair like GOLD/US500 at 1h, the
first hypothesis should be a data artefact (bar-close misalignment, broker
feed timestamping, weekend/holiday handling), not alpha.

---

## The size filter without direction — can you trade it symmetrically?

Given a reliable "a big move is coming" signal and no direction, the obvious
move is a two-sided breakout with OCO. Here is the honest arithmetic before
any backtest.

A symmetric straddle-like breakout on a spot instrument is **not** an options
straddle. An options straddle has a bounded, pre-paid cost and unlimited
upside on either side. A two-sided stop-entry OCO has:
- entry cost paid on whichever side triggers (one spread), plus
- the very real possibility of triggering on *both* sides in sequence
  (whipsaw), paying two spreads and two stops, and
- no premium received for the volatility view — you are long gamma
  synthetically and paying for it in whipsaws instead of in premium.

Break-even condition for a one-sided-triggering OCO with breakout distance
d from the compression range, stop back through the range (width w) and
target T:
```
    p_win * T  >  (1 - p_win) * (d + w) + cost
```
and for the double-whipsaw case you must add the cost and loss of the
first, failed trigger. **This is why symmetric breakout systems live or die
on the whipsaw rate, not on the size prediction.** The repo's finding that
compression predicts a 3+ ATR move within some window is necessary but
nowhere near sufficient: the move has to happen *before* the price
round-trips through the range.

### Documented evidence on volatility-contraction breakouts

Weak. The canonical source is Toby Crabel, *Day Trading with Short Term Price
Patterns and Opening Range Breakout* (1990) — NR7, inside days, and the
contraction/expansion cycle, developed on liquid futures. It is a trading
book, not peer-reviewed work, it predates the modern cost and multiple-
testing standards, and the patterns have been public for 35 years. There is
no journal-quality test of NR7 breakout profitability that survives realistic
costs that I could locate. Retail replications exist and report positive
results; none of them are trustworthy at the repo's evidentiary bar.

Pushing hard against the family: Mesfin, *Structural Limits of OHLCV-Based
Intraday Signals in MNQ Futures: A Systematic Falsification Study* (arXiv
2605.04004 / SSRN 6709401, 2026) tested **fourteen signal families** on 947
trading days of 5-minute MNQ data (2021-2025), with walk-forward validation,
t > 2.0, ≥30 trades, positive net returns after a fixed 2-point round-trip
friction, and consistency across years. **None satisfied all criteria.** Gross
returns per trade ranged ~0.07 to 1.50 points against a 2-point friction —
i.e. the signals were not merely unprofitable, they were an order of
magnitude short. The single exception, gap-continuation-short, had t = 3.23
and +14.52 points mean net return on **only 22 trades in three years**. The
paper's own conclusion is that single-bar directional signals from public
OHLCV features do not generate economically significant edge at 5-minute
resolution, and that anything above that ceiling requires **regime
classification and multi-bar hold structures** — which is, notably, an
endorsement of the approach in idea #1, not of naive breakouts.

### The recommendation

Do **not** build a symmetric OCO breakout. Instead:
1. Use the compression filter as a **regime gate on a directional signal**
   (idea #1) — this is what the falsification study points at.
2. Use the compression filter as a **position-sizing input**, which has real
   published support of its own. Moreira and Muir, *Volatility-Managed
   Portfolios* (JF 2017): scaling exposure by the inverse of recent realised
   variance raises factor Sharpe ratios by 50-100%, because volatility spikes
   and recedes quickly while expected returns are more persistent. **Critical
   caveat for this repo:** Harvey, Hoyle, Korgaonkar, Rattray, Sargaison and
   Van Hemert, *The Impact of Volatility Targeting* (SSRN 3175538, 2018)
   found the Sharpe benefit holds for *risk assets* (equities, credit) via the
   leverage effect, and that **for bonds, currencies and commodities the
   Sharpe impact is negligible**. Gold is a commodity. So expect vol-targeting
   on XAUUSD to improve *tail behaviour* (which it does across all asset
   classes in that paper) and **not** Sharpe. That is still worth having for
   a prop-firm drawdown limit — but do not sell it as an edge.

---

## STOP PURSUING — with reasons

| Approach | Why stop |
|---|---|
| **Candlestick patterns** | Marshall, Young & Rose, *Candlestick technical trading strategies: can they create value for investors?*, Journal of Banking & Finance 30(8) 2006. DJIA components 1992-2002, bootstrapped random OHLC series as the null. No statistically significant excess returns vs random trading. This is a properly-nulled test and it is negative. |
| **Generic technical trading rules on price alone** | Park & Irwin's review of 95 studies plus their own data-snooping-free test of 12 US futures markets: substantial technical trading profits in 1978-1984 were **no longer available in 1985-2003**. The effect decayed as it became known. |
| **Any single-bar OHLCV directional signal at 5-minute resolution** | Mesfin (2026): 14 families, none cleared the bar; gross edge ~0.07-1.50 points against 2-point friction. If a signal fits in one bar and uses only OHLCV, assume it is already arbitraged. |
| **VPIN / order-flow-toxicity as a return or volatility predictor** | Andersen & Bondarenko's critique: the ELO Bulk Volume Classification scheme is *inferior to a plain tick rule* against accurate benchmarks on E-mini S&P futures, and VPIN predicted volatility largely because rising volatility induces systematic classification errors in BVC. VPIN's predictive content is substantially a mechanical relation with trading intensity. Combined with the fact that MT5 gives **tick count, not signed volume**, this whole family is not retail-computable in a trustworthy way. Drop it. |
| **Order flow imbalance / Lee-Ready tick-rule classification** | The genuine result (Cont, Kukanov & Stoikov: price changes over short intervals are driven near-linearly by best-bid/ask order flow imbalance) requires **limit order book data**. MT5 gives no book depth and no signed trades. Bar-level reconstructions (candle body position, BVC-normal, "volume imbalance") are estimates of the tape, not the tape, and there is no published validation that they retain predictive power. Do not build on candle-body "order flow" indicators. |
| **Gold-silver ratio timing as a standalone signal** | Cointegration is unstable across regimes and weakening; the supportive backtests are recent unreplicated preprints; at least one systematic review reports finding no robust profitable strategy. Test the cointegration yourself before believing any of it. |
| **Gold mining equities as a gold lead** | Structurally different asset (equity beta, leverage, depletion), underperformed bullion by ~6.5%/yr 2006-2025, decouples in crises. No lead-lag claim worth testing, and not on MT5. |
| **Short-horizon trend on small-tick instruments, unconditionally** | Kurth, Eisler, Rej & Bouchaud (2026): post-2008 trend PnL collapsed on small-tick contracts at **all signal horizons**, with a microstructural mechanism (HFT market makers withdrawing liquidity ahead of predictable directional flow). It survives on large-tick contracts and in low-volatility regimes. XAUUSD CFD is not large-tick. |
| **Pre-FOMC drift specifically** | Lucca & Moench's pre-FOMC drift is large (it accounted for >80% of the equity premium over 17 years) but the same literature reports it is found in **global equity indices and not in other asset classes**, and subsequent work documents it *disappearing*. Not a gold or FX trade. |
| **"5 funded accounts running one EA"** | Already settled in `findings/07_correlation.md`: correlation is exactly 1.00 and all five die on the same afternoon. Nothing in this document changes that. |

---

## Honourable mention #4 — pre-announcement drift around scheduled US macro releases

Kurov, Sancetta, Strasser & Wolfe, *Price Drift Before U.S. Macroeconomic
News: Private Information about Public Announcements?* (JFQA 2019; ECB WP
1901). Findings: prices begin moving in the **eventual correct direction
about 30 minutes before the scheduled release**, and this pre-announcement
drift accounts on average for about **half of the total price adjustment**.
Nine of the twenty market-moving US announcements show the drift; all nine
show it in the bond market, four in equities.

Why it is interesting here: it is a directional signal that (a) is anchored
to a *known schedule*, (b) does not require you to forecast the surprise —
the drift itself is the signal — and (c) applies to FX futures, which is the
closest published market to XAUUSD/EURUSD.

Codeable rule:
```
Requires: a calendar of scheduled release TIMESTAMPS (no forecasts needed).
For each scheduled release at time R:
    drift = return over [R - 30min, R - 1min]
    trade in the direction of sign(drift), entering at R - 1min
    exit at R + 15min (test R+5, R+15, R+60)
Report by announcement type. Do NOT pool — the paper's result is that only
9 of 20 announcements show it.
```

**The reason this is #4 and not #1:** the mechanism the authors propose is
information leakage and early proprietary access, and a follow-up literature
(*"Drift Begone! Release policies and preannouncement informed trading"*,
Journal of International Money and Finance 2022) documents the drift changing
after release-policy reforms restricted early access. The effect may be
substantially dead. It is also the only idea here that needs an external data
feed. Test it late, and test whether it survives in the post-reform subsample
specifically.

---

## Realistic expectations for a retail systematic trader on gold

### What the professionals achieve

- **Diversified trend following, 67 markets, 1880-2016**: Sharpe **0.76 net
  of fees and costs**, positive in every decade (Hurst, Ooi & Pedersen, AQR,
  *A Century of Evidence on Trend-Following Investing*). That is the ceiling
  for a well-diversified, institutionally-executed, four-asset-class program
  over 136 years.
- **The live CTA industry does worse than the backtest.** SG CTA Trend Index
  over a recent five-year window: **Sharpe 0.38**, return/max-drawdown 0.35.
  2022 was an exceptional year (SG Trend +27.3%, Sharpe > 1) and is not the
  base rate.
- **Best-in-class published single-instrument intraday strategies**: Sharpe
  1.08 (Gao et al. SPY timing rule, gross), Sharpe 1.33 (Zarattini et al.
  SPY noise-area, net of costs, 2007-2024). Both on the single most liquid,
  most studied instrument in the world, both with 17-21 year samples.
- **Anything claiming Sharpe > 2 on one instrument** should be read as
  parameter-search output until proven otherwise. The Maróy follow-up
  reporting Sharpe > 3.0 on SPY is the illustration, not the counterexample.

### What that implies for this project

A realistic target for a *single-instrument* retail system on XAUUSD is
**Sharpe 0.4-0.8 out-of-sample**, not 2+. At Sharpe 0.6, with the standard
approximation that a Sharpe-S strategy needs about 1/S² years to produce a
t-stat of 1, you need roughly **3 years of live trading to distinguish it
from zero** — which is why the backtest bar has to be so much higher than
the live bar.

Drawdown: for a strategy at Sharpe 0.6 running at 10% annualised volatility,
a peak-to-trough drawdown of 15-20% is an ordinary event, not a failure. The
SG Trend Index's max drawdown running at "about double its volatility" is the
professional benchmark, and that is a *diversified* program; a single
instrument should be expected to be worse.

### Win rate — the number that must stop being a target

**Computed from the arithmetic, not cited:** for symmetric 1R-win / 1R-loss
trades, the win rate needed to reach a given t-statistic is

| trades | win rate for t=2.0 | win rate for t=3.0 | expectancy at t=3.0 |
|---|---|---|---|
| 200 | 57.00% | 60.38% | 0.2075 R |
| 500 | 54.45% | 56.65% | 0.1330 R |
| 1,000 | 53.16% | 54.72% | 0.0944 R |
| 2,000 | 52.23% | 53.35% | 0.0669 R |
| 5,000 | 51.41% | 52.12% | 0.0424 R |

Read this next to the repo's own sweep-follow result (54.1% on 701 GOLD 15m
sweeps): a 54.1% win rate on ~700 trades sits **below** the 56.65%/500-trade
line and roughly at the t=2 line — consistent with the parent finding that it
does not clear a multiple-testing bar of ~3.0. The table is the standing
benchmark: **any new idea should be checked against it before being coded**,
because it tells you immediately whether the available sample size can ever
support the claim.

### Costs on gold are not the binding constraint

**Computed from `data/GOLD_*.json`:** median ATR(14) is 13.79 price units on
GOLD 1h and 8.21 on GOLD 15m.

| round-trip cost | % of 1 ATR (GOLD 1h) | % of 1 ATR (GOLD 15m) |
|---|---|---|
| $0.15 | 1.09% | 1.83% |
| $0.20 | 1.45% | 2.43% |
| $0.30 | 2.18% | 3.65% |
| $0.50 | 3.63% | 6.09% |

At a 1-ATR stop, a $0.30 round trip costs 2-4% of R. That is real but it is
**not** what is killing these strategies — a 2-4% drag turns a +0.15R
expectancy into +0.11R, not into a loss. What kills them is that the
underlying expectancy is at or near zero. Stop blaming spreads; the cost
sensitivity test in `study.py` is still mandatory, but it is a robustness
check, not the explanation.

### The retail base rate

ESMA-mandated broker disclosures put **74-89% of retail CFD accounts losing
money**; the UK FCA figure is around 63%. These are not a statement about
whether an edge exists — they are a statement about what the unconditional
outcome of retail trading is, and therefore about how strong the prior
against any given retail strategy should be.

---

## Suggested test order

1. **Compression-conditioned trend** (idea #1) — hours of work, reuses
   existing code and data, and can only sharpen or kill results you already
   have. Do this first.
2. **Clock-slot periodicity + hour-of-day buckets** (idea #3, TEST 1 and
   TEST 2) — pure statistics, no strategy, one pass over existing data.
   Cheap, and the answer is informative either way.
3. **Lead-lag protocol** — one run, write down the answer, close the topic.
4. **Market intraday momentum on US500_1h first** (idea #2, Version A
   regression only) — this is a *code validation*: the effect is published
   for equity indices, so failing to find it means the implementation is
   wrong.
5. Only if step 4 reproduces: **transfer to GOLD**, after exporting 5+ years
   of XAUUSD M15 with tick volume from MT5.
6. Pre-announcement drift — last, and only if an economic calendar with
   reliable release timestamps is available.

Before any of it: `python3 JARVIS/research/test_engine.py`.

---

## Sources

**Intraday momentum**
- Gao, Han, Li & Zhou, *Market Intraday Momentum*, JFE 129(2) 2018 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866 · https://www.sciencedirect.com/science/article/abs/pii/S0304405X18301351
- Gao, Han, Li & Zhou, *Intraday Momentum: The First Half-Hour Return Predicts the Last Half-Hour Return* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2552752
- Li, Sakkas & Urquhart, *Intraday time series momentum: global evidence and links to market characteristics*, Journal of Financial Markets, 2022 — https://www.sciencedirect.com/science/article/abs/pii/S138641812100001X · preprint https://centaur.reading.ac.uk/95566/1/Accepted-Version.pdf
- Zarattini, Aziz & Barbon, *Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)*, SFI RP 24-97 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172 · https://alexandria.unisg.ch/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/download
- Maróy, *Improvements to Intraday Momentum Strategies Using Parameter Optimization and Different Exit Strategies*, 2025 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5095349
- *The "night effect" of intraday trading: Evidence from Chinese gold and silver futures markets*, Global Finance Journal 64, 2025 — https://www.sciencedirect.com/science/article/abs/pii/S1044028325000110
- Quantitativo, *Intraday Momentum for ES and NQ* — https://www.quantitativo.com/p/intraday-momentum-for-es-and-nq

**Intraday periodicity and time-of-day**
- Heston, Korajczyk & Sadka, *Intraday Patterns in the Cross-Section of Stock Returns*, Journal of Finance 65(4) 2010 — https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2010.01573.x · https://www.bauer.uh.edu/departments/finance/documents/Heston-Korajczyk-Sadka-jf-2010-01-07.pdf
- Ranaldo, *Segmentation and time-of-day patterns in foreign exchange markets*, JBF 33(12) 2009 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=960209 · https://www.sciencedirect.com/science/article/abs/pii/S0378426609001265
- Breedon & Ranaldo, *Intraday Patterns in FX Returns and Order Flow*, SNB WP 2011-04 — https://www.snb.ch/public/asset/en/www-snb-ch/publications/research/working-papers/2011/working_paper_2011_04/publications0_en/working_paper_2011_04.n.pdf
- Iwatsubo, Watkins & Xu, *Intraday seasonality in efficiency, liquidity, volatility and volume: platinum and gold futures in Tokyo and New York* — https://www.sciencedirect.com/science/article/abs/pii/S2405851318300102
- Lou, Polk & Skouras, *A Tug of War: Overnight Versus Intraday Expected Returns*, JFE 2019 — https://www.sciencedirect.com/science/article/abs/pii/S0304405X19300650

**Volatility regime and trend**
- Kurth, Eisler, Rej & Bouchaud, *Is Trend Still Your Friend? A Microstructural Account of the Demise of Short-Term Trend-Following*, 2026 — https://arxiv.org/abs/2607.01550 · summary https://quantpedia.com/is-trend-still-your-friend-a-microstructural-account-of-the-demise-of-short-term-trend-following/
- Lempérière, Deremble, Seager, Potters & Bouchaud, *Two Centuries of Trend Following*, 2014 — https://arxiv.org/pdf/1404.3274
- *Intraday LeBaron effects*, PNAS — https://www.pnas.org/doi/10.1073/pnas.0901165106
- Moreira & Muir, *Volatility-Managed Portfolios*, Journal of Finance 2017 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431 · https://www.nber.org/system/files/working_papers/w22208/w22208.pdf
- Harvey, Hoyle, Korgaonkar, Rattray, Sargaison & Van Hemert, *The Impact of Volatility Targeting*, 2018 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3175538

**Lead-lag and cross-asset**
- Chen, Rogoff & Rossi, *Can Exchange Rates Forecast Commodity Prices?*, QJE 125(3) 2010 — https://academic.oup.com/qje/article-abstract/125/3/1145/1903653 · https://www.nber.org/system/files/working_papers/w13901/w13901.pdf
- Hasselgren, Peltomäki & Graham, *Speculator activity and the cross-asset predictability of FX returns*, IRFA 72, 2020 — https://www.sciencedirect.com/science/article/abs/pii/S1057521920302052
- Cartea, Cucuringu & Jin, *Detecting Lead-Lag Relationships in Stock Returns and Portfolio Strategies* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4599565
- *Stylized facts of intraday precious metals* (15 years of 5-minute data) — https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5407636/
- Mittal & Mittal, *Gold Silver Pair Trading — Mean Reversion Strategy Using Machine Learning* (preprint, treat with caution) — https://papers.ssrn.com/sol3/Delivery.cfm/5710242.pdf?abstractid=5710242
- Melvin & Prins, *Equity hedging and exchange rates at the London 4 p.m. fix*, JIFMIM 2015 — https://www.sciencedirect.com/science/article/abs/pii/S1386418114000779

**Order flow and microstructure (why it is not retail-computable)**
- Cont, Kukanov & Stoikov, *The Price Impact of Order Book Events* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1712822 · https://arxiv.org/pdf/1011.6402
- Easley, López de Prado & O'Hara, *Discerning Information from Trade Data* (Bulk Volume Classification) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1989555
- Andersen & Bondarenko, *Reflecting on the VPIN Dispute* — https://repec.econ.au.dk/repec/creates/rp/13/rp13_42.pdf
- *VPIN and the flash crash*, Journal of Financial Markets — https://www.sciencedirect.com/science/article/abs/pii/S1386418113000189

**Negative results and honest tests**
- Mesfin, *Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures: A Systematic Falsification Study*, 2026 — https://arxiv.org/abs/2605.04004 · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6709401
- Marshall, Young & Rose, *Candlestick technical trading strategies: can they create value for investors?*, JBF 30(8) 2006 — https://www.sciencedirect.com/science/article/abs/pii/S0378426605002116
- Park & Irwin, *The Profitability of Technical Analysis: A Review* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=603481 · *A data-snooping-free test in US futures markets* https://farmdoc.illinois.edu/assets/marketing/agmas/AgMAS05_04.pdf
- Park & Irwin, *What do we know about the profitability of technical analysis?*, Journal of Economic Surveys 2007 — https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-6419.2007.00519.x

**Macro announcements**
- Kurov, Sancetta, Strasser & Wolfe, *Price Drift Before U.S. Macroeconomic News*, JFQA 2019 — https://www.ecb.europa.eu/pub/pdf/scpwps/ecbwp1901.en.pdf · https://www.skidmore.edu/economics/documents/KurovSancettaStrasserWolfe-2017PriceDriftBeforeUSMacro.pdf
- *Drift Begone! Release policies and preannouncement informed trading*, JIMF 2022 — https://www.sciencedirect.com/science/article/abs/pii/S0261560622001218
- Lucca & Moench, *The Pre-FOMC Announcement Drift*, FRBNY SR 512 — https://www.newyorkfed.org/research/staff_reports/sr512.html
- *The disappearing pre-FOMC announcement drift* — https://pmc.ncbi.nlm.nih.gov/articles/PMC7525326/

**Realistic expectations**
- Hurst, Ooi & Pedersen, *A Century of Evidence on Trend-Following Investing*, AQR 2017 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026 · https://www.chesler.us/resources/academia/A_Century_of_Evidence_on_Trend_Following.pdf
- SG CTA / Trend Index performance commentary — https://content.sgmarkets.com/CTA_UPDATE_KEEPING_UP_WITH_THE_TRENDFOLLOWERS_2025 · https://www.alpha-week.com/2022-cta-index-performance-review
- ESMA / FCA retail CFD loss disclosures (summarised) — https://www.traderslog.com/what-percentage-of-traders-lose-money

**Reference works cited but not peer-reviewed**
- Crabel, *Day Trading with Short Term Price Patterns and Opening Range Breakout* (1990) — origin of NR7 / contraction-expansion. Not a validated source; listed for provenance only.

---

*Written 2026-08-30. Every number here is either (a) quoted from the cited
source, or (b) computed directly from this repo's data and marked
"computed". No strategy in this document has been backtested. Everything is
UNPROVEN until it survives `JARVIS/research/study.py`.*
