# Experiment ledger

Vocabulary (never blur these):
- **CONFIRMED** — replicated out-of-sample, survived adversarial review
- **SUPPORTED** — positive across walk-forward, costs, and Monte Carlo
- **PROMISING** — positive but not yet adversarially attacked
- **UNPROVEN** — result not distinguishable from noise
- **REJECTED** — negative expectancy after realistic costs
- **DISPROVEN** — a specific claim shown false

Command to reproduce all of these: `python3 JARVIS/research/study.py GOLD 1h`
Engine must pass `python3 JARVIS/research/test_engine.py` first.

---
## E-001 — Does the old signal system have an edge? (DISPROVEN)
- **Hypothesis:** the deleted scanner's intraday engine had a real edge
  ("~$150/day potential").
- **Data:** its own live-tracked log, 30 intraday trades, 2026-07-16 → 08-25.
- **Result:** 70% win rate, but average R:R 0.53 → break-even needs 65.4%.
  Wilson 95% CI on the win rate: 52.1%–83.3%, straddling break-even.
  Monte Carlo against a skill-free null with identical stop/target geometry:
  a random system beat its +$34.40 **32.2% of the time**.
  29 of 30 trades were LONG during a +17% gold bull run.
- **Conclusion:** DISPROVEN as an edge. Realised P&L was +$8.19/day, and
  96% of that came from a single swing trade that risked 100% of the account.
- **Do not repeat:** do not resurrect this logic without fixing R:R first.

## E-002 — Does the capped-target design cause the failure? (CONFIRMED)
- **Hypothesis:** capped TP + ATR-scaled SL is the structural fault.
- **Test:** `capped_target_trap` on GOLD 1h, 13,750 bars, 2024-04 → 2026-08.
- **Result:** 666 trades, **69.5% win rate** — and **-0.066R expectancy**,
  PF 0.79, -43.9R total, 0/6 walk-forward folds positive, P(losing) 99.6%.
- **Conclusion:** CONFIRMED. The design loses money *while winning 70% of
  trades*, exactly reproducing the live result. Root cause established.

## E-003 — Liquidity sweep / stop-run on gold (UNPROVEN, leaning REJECTED)
- **Hypothesis:** price spikes past swing highs/lows to trigger resting
  stops, then reverses; fading the sweep has an edge.
- **Test:** `liquidity_sweep`, GOLD 1h, 603 trades, 2 years.
- **Result:** +0.001R expectancy, t=+0.02, PF 1.00. Walk-forward 3/6.
  **Dies as costs rise:** 2x spread → -0.031R, 3x spread → -0.061R.
  Shorts (+0.054R) marginally better than longs (-0.018R).
- **Conclusion:** UNPROVEN. The raw concept has no edge on gold 1h at retail
  cost. NOT yet a verdict on liquidity as a family — only on this
  implementation and timeframe. Next: test on 15m, test session-scoped
  levels (prior day/week high-low), require displacement confirmation.

## E-004 — Donchian breakout trend-following (DOWNGRADED -> UNPROVEN, see E-008)
- **Hypothesis:** classic 55-bar breakout + EMA20/100 filter + fixed 3R.
- **Test:** `donchian_trend`, GOLD 1h, 224 trades, 2 years.
- **Result:** 31.7% win rate, **+0.198R expectancy**, PF 1.28, +44.2R,
  max drawdown 9.7%. **Walk-forward 5/6 folds positive.** Survives 3x
  spread (+0.157R). Monte Carlo: P(drawdown>30%) = 0.0%,
  P(losing overall) = 5.6%.
- **Caveats:** t-statistic +1.63, below the t>2 bar, so the engine
  classifies it UNPROVEN by the strict rule. Longs (+0.292R) far outperform
  shorts (+0.007R) — likely gold's bull run. Worst losing streak 16 trades.
- **Conclusion:** PROMISING and the strongest candidate found. The boring
  classic beat the sophisticated liquidity concept. Must now face the
  adversarial reviewer and out-of-sample data on other symbols.

## E-005 — EMA pullback continuation with fixed R:R (REJECTED)
- **Result:** 102 trades, -0.142R expectancy, PF 0.80, 0/6 folds positive.
- **Conclusion:** REJECTED. Fixing the R:R alone does not rescue the old
  entry logic — the entries themselves carry no edge.

## E-006 — Is XAUUSD_QUAD v19.18 viable? (REJECTED)
- **Files:** received 2026-08-27, stored in `JARVIS/ea/inbox/`.
- **Measured:** 20,695 lines, 9,596 code lines, **748 input parameters**,
  274 functions, ~20 versions of patching (v12 -> v19.18).
- **Evidence from the EA's own header (its own live results):**
  spread bill GBP76.53 = **48% of the loss**; 153 of 188 losers never went
  GBP0.30 green; a -GBP159.79 day; efficiency ratio 0.038 (26:1 churn);
  hold time 4 min against a median 42-min move; 21 of 32 live exit routes
  fired ZERO times across 279 trades.
- **Cost arithmetic:** M1 gold, 1.40 x ATR stop = 1.40 price, against a
  0.30 round trip = **21.4% of risk lost to cost** before any edge.
- **Conclusion:** REJECTED as a live candidate. Root causes are structural:
  (a) 748 parameters cannot be validated on 279 trades, (b) M1 cost/risk is
  fatal, (c) exits fire before the move happens. Full audit in
  `JARVIS/ea/AUDIT_v19_18.md`.
- **Do not:** patch it to v19.19. Twenty rounds of patching is the failure
  mode, not the fix.

## E-007 — Timeframe effect on the same strategy (INCONCLUSIVE)
- **Test:** donchian_trend on GOLD 15m resampled to 30m/1h/2h, same costs.
- **Result:** 15m +0.130R (74 trades), 30m -0.022R (32), 1h -0.072R (17),
  2h +0.982R (4 trades).
- **Conclusion:** INCONCLUSIVE — only 70 days of 15m data exists, so the
  higher timeframes have far too few trades to read. Recorded so no future
  session mistakes this for evidence. The cost/risk arithmetic in E-006
  stands on its own and does not depend on this test.
- **To settle it:** need 15m history going back 2+ years.

## E-008 — Exit rules: can you capture the peak? (CONFIRMED finding)
- **Hypothesis:** Veer's "never closes at the peak" is an exit problem that
  better exit logic can fix.
- **Test:** `exit_study.py`, identical entries (overlap allowed so the exit
  cannot change which trades are taken), 11 exit policies, 4 markets.
- **Result 1 — CONFIRMED:** "break-even at 0.5R then trail" is the WORST exit
  on all four markets (GOLD -0.161R, US500 -0.188R, EURUSD -0.308R,
  GBPUSD -0.293R). Early profit protection scratches trades at break-even and
  removes the tail that pays for everything. Win rate falls to 15-20%.
- **Result 2 — the peak is not capturable:** an oracle exiting at each trade's
  exact best price returns +3.019R/trade on gold; the best real exit returns
  +0.201R. The ~2.8R gap is the cost of not knowing the future, not a defect.
- **Result 3:** 23% of trades never reach 0.3R. Entry quality, not exits.
  Veer's own EA: 81%. His entries are the bigger problem.
- **Conclusion:** his instinct ("focus on indubitable profits") is the cause,
  not the cure. Full write-up: `JARVIS/research/findings/06_exit_experiment.md`

## E-009 — Does donchian_trend survive other markets? (NO — E-004 downgraded)
- **Test:** same entry, all exit policies, on US500/EURUSD/GBPUSD.
- **Result:** negative expectancy on essentially every exit rule on all three
  non-gold markets, while positive on gold.
- **Conclusion:** the gold result is most likely an artifact of the 2024-2026
  gold bull run, not a structural edge. E-004 downgraded PROMISING -> UNPROVEN.
  Do not build an EA on it without a much stronger case.

## E-010 — Cross-market scan of 8 strategies (NOTHING PASSES)
- **Test:** `robustness.py` — every strategy on GOLD/US500/EURUSD/GBPUSD, 1h,
  2+ years, full retail costs. Then the full study gauntlet on the survivor.
- **Result — markets with positive expectancy:**

  | strategy | GOLD | US500 | EURUSD | GBPUSD | +ve |
  |---|---|---|---|---|---|
  | ma_cross | +0.200 | +0.046 | +0.008 | -0.052 | 3/4 |
  | donchian_trend | +0.198 | +0.130 | -0.146 | -0.067 | 2/4 |
  | tsmom | +0.076 | +0.044 | -0.151 | -0.290 | 2/4 |
  | liquidity_sweep | +0.001 | -0.033 | -0.170 | -0.238 | **1/4** |
  | ema_pullback | -0.142 | -0.004 | -0.247 | -0.080 | 0/4 |
  | mean_revert | -0.062 | -0.034 | -0.096 | -0.084 | 0/4 |
  | orb | -0.140 | -0.089 | -0.291 | -0.299 | 0/4 |

- **The survivor failed too.** `ma_cross` on gold: t-stat 1.22 (needs >2),
  only 3/6 walk-forward folds positive and all three are the last three
  (the 2025-26 gold rally), longs +0.704R vs shorts **-0.199R**. On US500 its
  edge vanishes entirely at 3x spread.
- **Conclusion:** after 8 strategies x 4 markets with costs, walk-forward,
  Monte Carlo and direction splits, **NOTHING reaches PROMISING.** The
  apparent winners are long-biased and concentrated in gold's bull run.
- **Liquidity sweep specifically: 1/4 markets = likely artifact.** This is
  the second independent test to find no edge in the concept as implemented.
- **What this means:** finding a real edge is not a weekend task. The
  infrastructure to TEST honestly now exists, which is the precondition for
  everything else. That is the actual achievement so far.

## E-011 — Where the published evidence actually lives (RESEARCH DIRECTION)
Trend following's strong published record (Moskowitz/Ooi/Pedersen; AQR's
"A Century of Evidence") is on **daily-and-slower** timeframes across a
**diversified basket of 50+ instruments** — not intraday on one symbol.
Every test here has been 1h on 4 correlated instruments, which is close to the
hardest possible version of the game: highest cost drag, lowest signal, no
diversification.
**Next test to run:** daily data across 20-40 uncorrelated futures/FX/indices,
simple trend rules. If an edge exists anywhere reachable, it is most likely
there. Requires daily history the repo does not yet hold.

## E-012 — Multiple-testing correction (THE DECISIVE TEST)
- **Method:** if you test N strategies with NO real edge, the best of them has
  an expected t-statistic of about sqrt(2 ln N) — the expected maximum of N
  normals. This is the bar any result must clear. (Bailey & Lopez de Prado,
  deflated Sharpe / probability of backtest overfitting.)
- **Luck thresholds:** N=10 -> 2.15 · N=32 -> 2.63 · N=52 -> 2.80 · N=100 -> 3.03
- **This project has run ~32 strategy/market combinations**, plus 20 parameter
  variants in E-013 below, so N is at least ~52 and the bar is **2.80**.
- **Best t-statistics observed:** donchian_trend on GOLD +1.63,
  ma_cross on GOLD +1.22, best swept variant +2.52.
- **CONCLUSION: nothing this project has tested beats chance.** Every result is
  below the level that luck alone produces given how many things were tried.
  This is the single cleanest statement of where the research stands.
- **Rule going forward:** count every variant tested, and hold results to
  sqrt(2 ln N). Reporting a t-stat above 2 after 50 experiments is meaningless.

## E-013 — Parameter sensitivity: plateau or lucky spike? (MIXED)
- **Test:** `sensitivity.py` sweeps one parameter at a time and prints the
  whole surface. A real edge degrades smoothly; a curve-fit one is a lone spike.
- **Result — the surfaces are PLATEAUS, which is mildly encouraging:**
  - donchian `rr` 1.5..5.0 : 7/7 settings positive (+0.065R to +0.327R)
  - donchian `stop_atr` 1.0..3.5 : 6/6 positive (+0.015R to +0.352R)
  - ma_cross `rr` 1.5..5.0 : 7/7 positive (+0.022R to +0.366R)
  Wider stops and larger targets are consistently better, which is the same
  direction as E-008: give trades room, do not protect profit early.
- **THE TRAP I WALKED INTO:** running these 20 sweeps RAISED the trial count
  from 32 to ~52, which lifts the luck threshold from 2.63 to 2.80. The best
  swept variant reached t=2.52 — still below the bar it just helped raise.
  **Searching for a better parameter makes the evidence bar higher, not lower.**
  Recorded because it is the exact mechanism that produced a 748-parameter EA.
- **Conclusion:** plateau structure is a point in favour of the trend family
  being real, but significance is still not established, and donchian remains
  negative on 3 of 4 markets (E-009). Verdict stays UNPROVEN.

## E-014 — Minimal 5-parameter trend, pre-registered (FAILS — important)
- **Design fixed BEFORE running**, from prior lessons: EMA50/200 trend filter,
  Donchian-55 entry, 2.5xATR stop, 4R target, NO break-even, NO trailing.
  5 parameters against the old EA's 748. Tested once, no searching.
- **Result:**

  | market | trades | win% | expectancy | t | maxDD |
  |---|---|---|---|---|---|
  | GOLD | 136 | 29% | +0.207R | +1.18 | 7.1% |
  | US500 | 145 | 19% | -0.161R | -1.07 | 23.1% |
  | EURUSD | 199 | 17% | -0.259R | -2.03 | 29.6% |
  | GBPUSD | 180 | 21% | -0.133R | -0.97 | 15.4% |

  Positive on 1/4 markets. Gold walk-forward 4/6 folds. Best t +1.18 against a
  luck threshold of 2.84 at N=56.
- **Conclusion: INDISTINGUISHABLE FROM LUCK.**
- **Why this matters more than the other failures.** This was the clean
  rebuild — every lesson applied, complexity stripped to 5 parameters, no
  curve-fitting, pre-registered. It still finds nothing. So the 748-parameter
  problem was real but was NOT the only problem.
- **The implication:** the search space itself is probably barren. 1-hour bars,
  four correlated instruments, retail spreads — that combination may simply not
  contain a reachable edge, however cleanly it is attacked. This is strong
  support for E-011: the published evidence lives on DAILY bars across MANY
  uncorrelated markets, and that test has not been possible offline.
- **Do not conclude "trend following does not work."** Conclude "trend
  following was not measurable in the only data this repo holds." The
  difference matters, and A-008 (real daily data via MT5 export) settles it.
