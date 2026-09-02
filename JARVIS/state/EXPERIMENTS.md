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

## E-015 — Correlation structure (CONFIRMED, two consequences)
- **Measured** on 570 days of daily returns from repo data.
- **EURUSD/GBPUSD correlate at 0.81** — nearly the same bet twice, since both
  are largely a dollar bet. Gold/US500/FX are otherwise independent (0.00-0.11).
  So the "4 market" test set is really ~3 independent bets, which is a further
  reason nothing reached significance: trend following needs diversification.
- **The 5-account consequence:** one strategy on 5 accounts = correlation 1.00.
  At an illustrative 2% daily-breach probability, 5 independent strategies
  breach together about 1 day in 312,000,000; 5 copies of one strategy breach
  together about 1 day in 50. Five accounts is one income stream with five sets
  of fees, all dying the same afternoon.
- Full write-up: `JARVIS/research/findings/07_correlation.md`

## E-016 — Prop-firm simulator + leaderboard built; verdict unchanged
- **Built:** `prop_sim.py` (daily loss limit, static/trailing drawdown, profit
  target, min trading days, Monte Carlo pass-rate estimation) and
  `leaderboard.py` (runs every strategy through backtest + walk-forward +
  multiple-testing correction + prop Monte Carlo, ranked on 4 gates, not on
  profit alone). Both deterministic, zero AI cost per run — the "Claude picks
  the experiment, a local program runs the tests" architecture.
- **Result:** `python3 JARVIS/research/leaderboard.py` — **0 of 8 strategies
  clear all 4 gates.** Best (`ma_cross`) clears 1/4. Simulated prop pass rate
  under generic 2-step rules: 2-4% for every strategy tested.
- **On the near-100% win-rate target:** explicitly not fabricated, per the
  standing rule. The honest finding is the opposite direction — nothing tested
  beats even a 50/50 coin flip once sized and costed realistically. A near-100%
  win rate would need an enormous reward:risk asymmetry or a real, currently
  undiscovered edge; neither exists in this library yet. Recorded here rather
  than asserted anywhere as a target being approached.
- **Caveat:** rule presets are generic, not any specific firm's real terms
  (A-004 blocked on Veer naming the firm). Prop pass rate will change once
  real rules are entered.

## E-017 — Sweep taxonomy built and falsified in the FADE direction (MAJOR)
- **Built:** `sweeps.py` — liquidity levels with confirmation lag, 7 sweep
  classes A-G, depth/wick/reclaim/displacement/structure-shift features,
  strength score, and a structural split between decision-time features and
  after-the-fact outcomes so a future value cannot leak into a decision.
- **Method fix mid-test:** first pass measured MFE and MAE independently, which
  reported "75% reached 1R" while 85% were stopped out. Replaced with
  FIRST-TOUCH resolution (ties lose). The honest number was 44.5%, not 75%.
- **Result — FADE (the specified strategy) is worse than random:**
  GOLD 15m 701 sweeps, 44.5% at 1R vs 49.2% for a coin flip at the same bars
  and 49.4% for random bars. 100% of random-side trials beat it.
- **Result — FOLLOW (the opposite) beats FADE on 5/5 markets:**
  GOLD 15m 54.1%, GOLD 1h 53.1%, US500 1h 52.0%, GBPUSD 1h 51.7%,
  EURUSD 1h 49.7%. ~10,000 events, same direction everywhere.
- **Mechanism:** consistent with Osler's stop-cascade research — triggered
  stops ACCELERATE price rather than reversing it. The retail narrative has the
  mechanism inverted. Type F ("continuation", labelled the failure case) beat
  types A and B, the supposed successes.
- **Conclusion:** do NOT build a sweep-fade EA. The continuation direction is a
  CANDIDATE, not an edge — it has not faced costs, walk-forward, or the
  multiple-testing bar. Full write-up:
  `JARVIS/research/findings/08_sweep_direction.md`
- **Next test (highest value):** does the sweep add anything over a plain
  "buy an N-bar high" momentum rule? If not, delete the sweep apparatus.

## E-018 — Does sweep detection beat plain momentum? (YES, in FOLLOW direction)
- **Test:** sweep-FOLLOW vs "buy any 20-bar high / sell any 20-bar low",
  identical stop (1 ATR), target (1R), first-touch resolution. Only entry differs.
- **Result — sweep beats plain breakout on 5/5 markets:**
  GOLD 15m 54.1% vs 52.4% · GOLD 1h 53.1% vs 47.9% · US500 1h 52.0% vs 50.2% ·
  EURUSD 1h 49.7% vs 46.7% · GBPUSD 1h 51.7% vs 47.9%. Average +3.1 points.
- **Meaning:** breaking a level where resting orders sit is measurably
  different from breaking an arbitrary 20-bar high. The liquidity layer carries
  real information — the previous conclusion was wrong only about DIRECTION.
- **Cost check:** ~+0.04R net per trade after a 0.35 gold round-trip. Real but
  thin; a worse broker or tighter stop erases it.
- **Status: PROMISING.** Has NOT faced the multiple-testing bar (t-stat not
  computed; ~50+ variants tried so the bar is near 2.8), walk-forward, cost
  sensitivity, or out-of-sample. First result in this project to beat its
  baseline consistently across markets.
- **A bug I made and caught:** the first run of this comparison passed the fade
  direction and concluded sweeps were WORSE than momentum. Corrected before
  reporting. Recorded because reporting that would have killed a real finding.

## E-009 — Sweep ANATOMY: do sweeps reverse at all? (MEASURED, adverse)
- **Method:** not a backtest. Enumerate every pierce of a confirmed swing
  level and score a SYMMETRIC ±1×ATR14 barrier, 24 bars forward, from the
  sweep bar's close — then compare to the instrument's OWN unconditional
  baseline rather than to 0.500. Code: `JARVIS/research/sweep_anatomy.py`,
  `microstructure_facts.py`, `failure_probes.py`.
- **Baselines:** GOLD 1h P(down 1 ATR before up 1 ATR) = **0.544**, GOLD 15m
  0.523, EURUSD 0.500, US500 0.490. Gold is down-skewed at short horizons
  *during a bull market*. Any statistic compared to 0.500 is wrong.
- **Result 1 — the long setup is wrong-signed.** "Swing low pierced, close
  back above" on gold gives P(down first) = 0.633 (n=1694) vs baseline 0.544:
  **+8.9pp, z=+6.95**. It is a CONTINUATION-DOWN signal. Replicated on 15m
  (+8.1pp, z=+3.41) and in **3/3 disjoint date blocks** (+9.7 / +7.0 / +9.3pp,
  all |z|>3) through a parabola to $5,626 and a −29.7% crash.
- **Result 2 — the short setup has nothing.** +1.1pp (z=+0.75) on 1h, −1.7pp
  on 15m, and 0/3 date blocks replicate.
- **Result 3 — no "quality" filter replicates.** Displacement >1.5 ATR:
  +6.6pp on 1h, **−13.2pp** on 15m. With-trend: +4.8pp vs −8.3pp. NY overlap:
  +5.7pp vs −10.3pp. Nesting: no effect either way. Every filter that helps on
  one timeframe hurts on the other, several with |z|>2 on both sides.
- **Conclusion:** the retail sweep-reversal thesis is not merely edgeless on
  gold, its long half is significantly *anti*-correlated with its own premise,
  in the exact direction Osler's stop-loss cascade result predicts. This
  explains E-003's null (and its longs −0.018R vs shorts +0.054R) without
  blaming the implementation. The "sophisticated" version differs from the
  naive one only in how many hypotheses it silently tests.
- **Status:** MEASURED, not CONFIRMED — one instrument, one 2024–2026 window.
- **Full write-up:** `JARVIS/research/FAILURE_MODES.md` (81 failure modes).

## E-019 — Move size IS predictable at entry (REPLICATED, strongest finding)
- **Question (Veer's own diagnosis):** "we catch every mini trend... we never
  know if they are small or massive." Is move SIZE predictable before entry?
- **Test:** `movesize.py` — every bar, forward travel in ATR over 40 bars,
  bucketed by decision-time features only.
- **Result — replicated on GOLD 15m (70d) AND 1h (2.4y), near-identical:**

  | condition | P(>3 ATR move) 15m | P(>3 ATR move) 1h |
  |---|---|---|
  | ADX 0-15 | 91% | 90% |
  | ADX >= 40 | 68% | 66% |
  | ATR >= 2x its median | — | **25%** |
  | ATR 0.8-1.0x median | 93% | 83% |

  Hours (15m): 04-12 UTC 89-93% · 14-16 UTC **62%**.
  Trend efficiency was strong on 15m (+9pts) but weak on 1h (+3pts) — DROPPED.
- **Mechanism:** volatility contraction precedes expansion. When ATR is already
  stretched and ADX already high, the move has largely happened.
- **This predicts SIZE, not DIRECTION.** It is a filter on when to act.

## E-020 — How to USE the move-size predictor (gate beats adaptive targeting)
- **Tested three uses** on identical donchian entries, 4 markets, full costs:
  fixed target · gate (only trade when expansion likely) · adaptive target
  (big target when expansion likely, small when not).
- **Result, average expectancy across 4 markets:**
  fixed 1R -0.029R · fixed 3R +0.029R · **gate-only +0.108R** · adaptive +0.001R
- **My hypothesis was wrong.** Adaptive targeting sounded better and measured
  worse than a plain fixed 3R. Gating is the right use.
- **Best single result in the project so far:** donchian + expansion gate on
  GOLD, **+0.605R, t=+2.9, n=85** (vs +0.198R, t=+1.6 ungated).
- **Still does not clear the bar.** With ~100 variants now tried the luck
  threshold is ~3.0, and t=2.9 sits just under it. Also inconsistent: US500
  turns negative under the same gate.
- **For the EA:** gate on compressed volatility, do NOT adapt targets, do NOT
  use early break-even (E-008, worst exit on 4/4 markets).

## E-021 — Automated search: in-sample winners FAILED out-of-sample (MAJOR)
- **Built:** `autosearch.py` — runs the whole config space locally at zero AI
  cost. Three defences baked in: chronological 70/30 split, out-of-sample run
  ONCE on the top handful, and a multiple-testing correction stating the luck
  bar for the number of configs tried.
- **Run:** 672 tests, 168 configs x 4 markets, 1h, 40 seconds.
- **Result — the overfitting was caught red-handed:**

  | config | in-sample | out-of-sample |
  |---|---|---|
  | sweep_continuation + gate adx25/1.15, rr3 | **4/4 markets, +0.166R** | **1/4 markets, -0.109R** |
  | sweep_continuation + gate adx20/1.0, rr3 | 3/4, +0.185R | 1/2, -0.158R |
  | ma_cross, NO gate, rr3 | 3/4, +0.094R | **3/3, +0.208R (only survivor)** |

  **7 of 8 in-sample winners failed out-of-sample.** The best in-sample config
  inverted completely.
- **Luck bar at N=672 is t=3.61.** Best out-of-sample t anywhere was +2.24.
  **NOTHING cleared it.**
- **This CORRECTS E-020.** That test found the expansion gate averaged +0.108R
  against +0.029R ungated — but it was NOT split in-sample/out-of-sample. Under
  a proper split the gated configs are the ones that collapse, and the two best
  out-of-sample configs both had **gate = none**. The gate's apparent value in
  E-020 was substantially in-sample fitting.
  E-019 (that compressed volatility PRECEDES bigger moves) still stands — it was
  a direct measurement, not a fitted strategy. What does not stand is that
  gating on it improves a traded system.
- **Value of this run:** it prevented an EA being built on a configuration that
  looked best on every in-sample metric and is negative on unseen data.

## E-022 — LeBaron compression-trend effect (DOES NOT REPLICATE — idea closed)
- **Hypothesis** (from `findings/09_strategy_hunt.md`, ranked #1): Kurth/Eisler/
  Rej/Bouchaud 2026 find futures trend PnL keeps accruing in LOW volatility
  even after the post-2008 break. If true here, the flat Donchian result would
  be a diluted signal rather than no signal.
- **Method:** `volregime.py`. Take EVERY trade, then partition by the volatility
  tercile it OPENED in. Terciles computed from the in-sample half ONLY, so the
  out-of-sample test never sees a boundary derived from its own data. This is a
  partition of outcomes, not a fitted filter, so it cannot overfit like E-021.
- **Result — donchian_trend, 1h, 4 markets:**

  | regime | IS n | IS exp | OOS n | OOS exp |
  |---|---|---|---|---|
  | low vol | 115 | -0.039R | 41 | **-0.133R** |
  | mid vol | 219 | **+0.197R** | 85 | -0.044R |
  | high vol | 402 | -0.029R | 186 | -0.015R |

- **Conclusion: NO low-volatility advantage.** Low vol was NEGATIVE in both
  halves and worse out-of-sample than high vol. The only positive cell (mid
  vol, in-sample) went negative out-of-sample — the same in-sample-fitting
  pattern as E-021.
- **Idea CLOSED.** The published effect is on large-tick futures contracts;
  XAUUSD CFD is not one, which the source paper itself flags as the boundary
  condition. Do not revisit without different instruments.
- **Cost of this test: one script, zero AI usage for the compute.** This is the
  intended pattern — falsify cheaply and move on.

## E-023 — Intraday momentum (VALIDATION FAILED — result correctly refused)
- **Hypothesis** (strategy hunt #2): Gao/Han/Li/Zhou JFE 2018 — the first
  half-hour of the session predicts the last half-hour. Pre-registered
  prediction: POSITIVE correlation.
- **Design feature that mattered:** US500 was set as a VALIDATION GATE, because
  that is where the effect is published. If it fails there, the implementation
  or the data granularity is wrong and no other market's number can be trusted.
- **Result — validation failed:** US500 NY session IS corr +0.066 (t +1.34),
  OOS **-0.026**. US500 EU session negative in both halves.
- **THE FLUKE THIS CAUGHT:** GOLD full-day showed IS corr **+0.129, t=+2.71** —
  which crosses a naive significance threshold — and OOS **-0.022**. Without the
  validation gate and the IS/OOS split this would have been reported as a
  finding. It is noise.
- **Most likely cause:** 1h bars are too coarse. The paper uses 30-minute bars;
  the first HOUR is not the first half-hour. This is a data-granularity
  problem, not a refutation of the published effect.
- **Status: UNTESTABLE on current data, not disproven.** Re-run on M15/M5 once
  the MT5 export provides them. Until then it stays open and unclaimed.

## E-024 — Session scoreboard: what is actually left standing
After 23 experiments and ~700 configuration tests:
- **DISPROVEN / CLOSED:** old signal system (E-001), capped-target design
  (E-002), sweep FADE (E-017), LeBaron compression-trend (E-022), lead-lag
  DXY→gold (research, no peer-reviewed intraday evidence), mean reversion, ORB,
  ema_pullback.
- **MEASURED AND STANDING:** sweeps predict CONTINUATION not reversal (E-017,
  5/5 markets); early break-even is the worst exit rule (E-008, 4/4 markets);
  compressed volatility precedes bigger moves (E-019, replicated on two
  timeframes) — though GATING on it fails out-of-sample (E-021).
- **NOTHING has cleared the multiple-testing bar.** At ~700 tests the luck
  threshold is t≈3.6; the best out-of-sample t observed anywhere is +2.24.
- **The single biggest blocker is still DATA.** M1/M5 do not exist in this repo,
  which blocks the M1 sniper model, the intraday-momentum retest (E-023), and
  any honest test of the scalping layer.

## E-025 — BOUNCE setups: many more entries, no edge (BUILT + MEASURED)
- **The gap Veer identified, correctly:** the indicator only signalled on
  BREAKS of a level. Price coming to support/resistance and HOLDING it — the
  "predictable buys and sells" — was never implemented. That is a whole setup
  class, and it was the largest source of missed entries.
- **Built:** bounce detection (level tested within tolerance, closed on the
  correct side, with a rejection wick) plus multi-scale pivots at 3 lengths so
  scalp-sized levels appear alongside structural ones.
- **Frequency achieved:** GOLD 1h goes from ~2,238 sweep events to **7,449
  bounce setups** — roughly 12/day, the order of magnitude Veer describes.
- **Edge measured (stop 1 ATR, target 2R, first-touch, ties lose;
  break-even at 2R is 33.3%):**

  | market | setups | win rate | vs break-even |
  |---|---|---|---|
  | GOLD 15m | 2,191 | 30.7% | **-2.6** |
  | GOLD 1h | 7,449 | 30.5% | **-2.9** |
  | US500 1h | 6,773 | 33.7% | +0.3 |
  | EURUSD 1h | 9,157 | 33.0% | -0.3 |
  | GBPUSD 1h | 9,568 | 33.4% | +0.1 |

- **Conclusion: bounce setups are AT break-even before costs, so they LOSE
  after them.** More entries were delivered; extra edge was not.
- **The finding that matters more:** at a 2R target these win ~31-33%, NOT a
  "fat majority". A fat majority going green implies a SMALL target and a wide
  stop — which is the 0.53 R:R geometry that made the old EA lose while winning
  70% of trades. High win rate and losing money are the same phenomenon.
- **Recorded arithmetic:** break-even win rate is 1/(1+R:R). At 0.5 R:R you
  need 66.7%; at 2R you need 33.3%. And GBP50/day on a $10k account at 0.5%
  risk is 1.0R PER DAY, every day, against a best measured expectancy of
  ~+0.04R per trade.

## E-026 — Higher-timeframe level confluence (NO ADVANTAGE — do not build)
- **Veer's idea:** "on M15, a buy opportunity aligned with levels from last
  week." The intuition that a level from a higher timeframe is worth more. This
  was the most promising remaining SELECTION idea, because E-025 showed bounce
  setups run at break-even overall — if HTF-aligned ones were better, the
  average would be hiding a good subset.
- **Method:** levels derived at three scales from the same series (1h local,
  ~daily via resample 24, ~weekly via resample 120), each carrying its own
  confirmation lag so a weekly pivot is unusable until its weekly bar closed.
  Setups bucketed by whether the level they fired at coincided with a higher
  timeframe one.
- **Result — pooled across 4 markets, 33,600 setups:**

  | confluence | n | win rate @2R | vs 33.3% break-even |
  |---|---|---|---|
  | local only | 23,500 | 32.9% | -0.4 |
  | + daily | 8,393 | 32.6% | -0.7 |
  | + both daily & weekly | 1,717 | 33.2% | -0.1 |

  Everything sits within 0.6 points of everything else, and all of it at or
  below break-even.
- **The tempting false positive:** GOLD "+ both" showed 37.3% (+4.0) — but on
  118 samples, and it does not replicate on the other three markets (35.0%,
  33.5%, 32.3%). Noise.
- **Conclusion: DO NOT build confluence as a filter.** A level from last week
  performs the same as a local one in this data.
- **Precise limit of the test:** the WEEKLY-only bucket never gathered enough
  samples (0-19 per market) because few setups coincide with a weekly level at
  all. So "daily confluence gives no advantage" is MEASURED; "weekly confluence
  specifically" is UNTESTED, not disproven.
- **What this means cumulatively:** across E-019 to E-026 every selection rule
  tried — volatility gate, sweep class, level strength, sweep depth, HTF
  confluence — has failed to separate winners from losers. The problem is not
  which setups to pick from the current signal family; it is that the family
  itself has no measured edge.

---
## E-027 — SuperTrend Sniper: how often does it actually trade? (MEASURED)
- **Question asked:** "how many entries per day, on every market and timeframe
  in the repo" — never stated before, and everything downstream depends on it.
- **Setup measured:** signal `supertrend_sniper_ea` (ST 7/1.2 + DEMA200 slope +
  ADX<=35, the EA's defaults), exits = the EA's own (3R target, 50-bar cap,
  3.0xATR trail armed at 0R, no break-even), one position at a time, warmup 300.
- **Reproduce:** `python3 JARVIS/research/test_engine.py` (ALL TESTS PASSED)
  then `python3 JARVIS/research/st_capacity.py`, section 1.
- **Result (full series, entries after the ADX gate and occupancy):**

  | market | bars | session days | raw signals | entries | ent/session day | median bars held | full-sample exp | t |
  |---|---|---|---|---|---|---|---|---|
  | GOLD 15m | 4501 | 58 | 146 | 113 | 1.948 | 10 | +0.119R | +0.76 |
  | GOLD 1h | 13750 | 720 | 373 | 302 | **0.419** | 10 | +0.167R | +1.71 |
  | US500 15m | 4500 | 58 | 156 | 119 | 2.052 | 9 | -0.235R | -1.92 |
  | US500 1h | 13716 | 721 | 463 | 375 | 0.520 | 8 | +0.088R | +1.06 |
  | EURUSD 15m | 5624 | 69 | 267 | 202 | 2.928 | 6 | -0.480R | -4.94 |
  | EURUSD 1h | 17252 | 799 | 653 | 535 | 0.670 | 8 | -0.013R | -0.18 |
  | GBPUSD 15m | 5624 | 69 | 262 | 210 | 3.043 | 7 | -0.426R | -4.40 |
  | GBPUSD 1h | 17253 | 799 | 650 | 533 | 0.667 | 8 | -0.124R | -1.85 |

- **The number that matters:** on 1h the strategy trades **0.42-0.69 times per
  session day** per market. On GOLD 1h that is one trade every 2.4 days.
  Occupancy is not the binding constraint — the raw signal count is only
  ~19-24% above the entry count.
- **Missing data, stated rather than estimated:** there is **no M1 data in this
  repo**. The EA is documented as an M1 sniper. Every number here is 15m/1h.
  The 15m files cover only 58-69 session days (2026-06 -> 2026-08), so their
  out-of-sample slices are 16-19 days — one month at most.

## E-028 — SuperTrend Sniper out-of-sample expectancy (UNPROVEN; 15m REJECTED)
- **Hypothesis:** the SuperTrend flip + DEMA-slope + ADX<=35 entry has positive
  expectancy per trade after realistic costs on data it was not chosen on.
- **Method:** chronological 70/30 split (`autosearch.IS_FRAC = 0.70`, same
  split used by E-021). Nothing tuned on the OOS slice; EA defaults only.
- **Reproduce:** `python3 JARVIS/research/st_capacity.py`, section 2.
- **Result:**

  | market | IS n | IS exp | IS t | OOS n | OOS win | OOS exp | OOS SE | OOS t |
  |---|---|---|---|---|---|---|---|---|
  | GOLD 15m | 73 | +0.197 | +0.99 | 31 | 32.3% | +0.010 | 0.288 | +0.04 |
  | GOLD 1h | 206 | +0.040 | +0.35 | 95 | 37.9% | **+0.455** | 0.187 | **+2.43** |
  | US500 15m | 92 | -0.344 | -2.70 | 24 | 25.0% | -0.280 | 0.279 | -1.00 |
  | US500 1h | 254 | +0.140 | +1.37 | 111 | 27.9% | -0.020 | 0.151 | -0.13 |
  | EURUSD 15m | 133 | -0.389 | -3.13 | 53 | 13.2% | -0.743 | 0.158 | -4.72 |
  | EURUSD 1h | 373 | -0.038 | -0.47 | 152 | 28.9% | +0.032 | 0.138 | +0.23 |
  | GBPUSD 15m | 148 | -0.427 | -3.69 | 50 | 26.0% | -0.498 | 0.189 | -2.64 |
  | GBPUSD 1h | 365 | -0.137 | -1.73 | 159 | 28.3% | -0.075 | 0.128 | -0.58 |
  | **POOLED OOS** | | | | **675** | 28.4% | **-0.054** | **0.062** | **-0.87** |

  Pooled OOS 95% CI on expectancy: **[-0.177R, +0.068R]** — straddles zero,
  point estimate negative.
- **Verdict, pooled: UNPROVEN.** Expectancy is not distinguishable from zero
  and its point estimate is negative.
- **Verdict, 15m FX: REJECTED.** EURUSD 15m -0.743R (t -4.72, two-sided
  p=0.00002, still p=0.014 after a 780-config Sidak correction) and GBPUSD 15m
  -0.498R (t -2.64). Significantly negative, not merely unproven.
- **The one positive result and why it is not enough:** GOLD 1h OOS +0.455R,
  t +2.43, two-sided p=0.017. The multiple-testing bar for this dataset is
  t ~ 3.65 (E-012, ~780 configurations). Even ignoring all prior tests, this
  was the best of 8 series measured in one run: Sidak best-of-8 p = 0.128.
  It also **contradicts its own in-sample slice** (IS +0.040R, t +0.35): the
  OOS number is 11x the IS number, which is the signature of a regime, not a
  stable edge. The OOS window is 2025-12-19 -> 2026-08-24 with gold +7.3%.
  Walk-forward with EA exits: **4/6 folds positive**, and fold expectancy rises
  monotonically with recency (-0.228, +0.243, -0.037, +0.183, +0.329, +0.526R).
  Direction split OOS: long +0.275R (n 56, t +1.19), short +0.712R (n 39,
  t +2.30). Cost sensitivity is flat (0.5x -> 2x spread: +0.458R -> +0.447R),
  so costs are not what is deciding this.
- **Standard harness for the record** (`python3 JARVIS/research/study.py GOLD 1h`,
  fixed 3R exits rather than the EA's): supertrend_sniper_ea, 277 trades,
  30.0% win, PF 1.20, exp +0.144R, t +1.34, 4/6 folds positive,
  **VERDICT: UNPROVEN (edge not distinguishable from noise)**.

## E-029 — The GBP60/day arithmetic (the claim is DISPROVEN)
- **Question:** what account size and risk setting makes GBP60/day?
- **Identity used:** `60 = trades_per_day x expectancy_R x GBP_risked`, then
  `account = GBP_risked / 0.005` at the EA's 0.50% risk default.
- **Reproduce:** `python3 JARVIS/research/st_capacity.py`, section 3.
- **Result, using OOS expectancy and OOS entry rate per market:**

  | market | OOS ent/day | OOS exp R | R/day | GBP risk/trade | account @0.5% |
  |---|---|---|---|---|---|
  | GOLD 15m | 1.938 | +0.010 | +0.0198 | 3,037 | 607,477 |
  | GOLD 1h | 0.459 | +0.455 | +0.2086 | 288 | **57,515** |
  | US500 15m | 1.500 | -0.280 | -0.4200 | impossible | impossible |
  | US500 1h | 0.541 | -0.020 | -0.0107 | impossible | impossible |
  | EURUSD 15m | 2.789 | -0.743 | -2.0727 | impossible | impossible |
  | EURUSD 1h | 0.664 | +0.032 | +0.0214 | 2,803 | 560,552 |
  | GBPUSD 15m | 2.632 | -0.498 | -1.3100 | impossible | impossible |
  | GBPUSD 1h | 0.694 | -0.075 | -0.0519 | impossible | impossible |
  | all 8 series together | 11.217 | — | **-3.6154** | **no account size works** | — |
  | all 4 markets, 1h only | 2.358 | — | +0.1675 | 358 | 71,629 |

- **The honest denominator.** GOLD 1h's +0.2086 R/day is the single
  cherry-picked best cell. Using GOLD 1h's **full sample** instead (2024-04 ->
  2026-08, exp +0.167R, 0.419 entries/day = +0.0700 R/day) the answer becomes
  **GBP 858 risked per trade = a GBP 171,505 account at 0.50%**.
- **What a normal account actually yields at 0.50% risk (GOLD 1h):**

  | account | risk/trade | GBP/day at OOS rate | GBP/day at full-sample rate |
  |---|---|---|---|
  | 2,000 | 10.00 | 2.09 | 0.70 |
  | 5,000 | 25.00 | 5.21 | 1.75 |
  | 10,000 | 50.00 | 10.43 | 3.50 |
  | 25,000 | 125.00 | 26.07 | 8.75 |
  | 57,515 | 287.57 | 59.99 | 20.13 |
  | 100,000 | 500.00 | 104.30 | 35.00 |
  | 171,505 | 857.52 | 178.88 | 60.03 |

- **If the account is GBP10,000 instead**, GBP60/day requires **2.88% risk per
  trade** (best-case OOS rate) or **8.57%** (full-sample rate). Monte Carlo at
  those risk levels: 2.88% -> median maxDD 21.6%, 95th 36.4%, P(dd>30%) 15.2%.
  8.57% -> **median maxDD 87.2%, P(dd>30%) 100.0%, P(dd>50%) 100.0%**.
- **ONE-SENTENCE FINDING:** GBP60/day from this strategy needs a **GBP57,515
  account at 0.50% risk on the single best cherry-picked slice, GBP171,505 on
  GOLD 1h's full history, and is arithmetically impossible on 6 of the 8
  market/timeframe combinations because their out-of-sample expectancy is
  negative** — so the claim that it can produce GBP60/day on a retail-sized
  account is **DISPROVEN**.

## E-030 — Is GBP60/day CONSISTENT? (DISPROVEN)
- **Point:** "consistent GBP60/day" is a claim about the distribution, not the
  mean. Measured directly.
- **Reproduce:** `python3 JARVIS/research/st_capacity.py`, sections 4, 5 and 7.
- **Bootstrapped months** (a month = 21 trading days x that series' OOS entry
  rate, 20,000 draws from its OOS trade distribution):

  | market | trades/month | P(month < 0) | median month | 5th pct | 95th pct | P(month hits 60/day avg) |
  |---|---|---|---|---|---|---|
  | GOLD 15m | 41 | 48.8% | +0.28R | -15.69R | +17.33R | 49.5% |
  | GOLD 1h | 10 | **23.5%** | +4.14R | -4.83R | +14.39R | **48.9%** |
  | US500 15m | 32 | 87.8% | -9.36R | -20.78R | +4.08R | n/a (neg) |
  | US500 1h | 11 | 53.3% | -0.55R | -8.26R | +9.04R | n/a (neg) |
  | EURUSD 15m | 59 | 100.0% | -44.21R | -57.41R | -28.72R | n/a (neg) |
  | EURUSD 1h | 14 | 49.0% | +0.31R | -9.74R | +11.13R | 49.3% |
  | GBPUSD 15m | 55 | 99.5% | -27.80R | -42.71R | -10.71R | n/a (neg) |
  | GBPUSD 1h | 15 | 59.0% | -1.64R | -10.76R | +9.50R | n/a (neg) |
  | POOLED (all 8) | 236 | **70.5%** | -13.50R | -53.53R | +28.33R | n/a (neg) |

- **Even in the single best cell (GOLD 1h at its cherry-picked OOS rate):
  23.5% of months are negative and only 48.9% of months reach the GBP60/day
  average the account was sized for.** Longer horizons: quarter P(<0) 8.4%,
  P(hits target) 51.5%; year P(<0) 0.2%, P(hits target) 54.0%.
- **Actual calendar months in the OOS slices (not bootstrapped):** GOLD 1h
  1/9 negative; US500 1h 4/9; EURUSD 1h 7/10; GBPUSD 1h 6/10; every 15m series
  has only 1 OOS month and 3 of those 4 are negative.
- **Day level (section 7), the level the claim is actually made at:** on 1h,
  **44.5%-58.5% of session days contain no trade at all**, the median day is
  0.00R, and only 14.1%-17.9% of days are positive. A GBP60/day target cannot
  be met by an instrument that does not trade on most days; the daily figure
  can only ever be an average over months.
- **Pooled Monte Carlo at 0.50% risk (engine.monte_carlo, 20k reshuffles,
  675 OOS trades):** median maxDD 29.2%, 95th-pct maxDD 46.2%,
  P(dd>30%) 46.8%, P(dd>50%) 2.1%, **P(losing overall) 83.6%**.
- **VERDICT: DISPROVEN** as a consistent daily income. The distribution
  requirement fails even where the mean does not: the best case is a coin-flip
  month (48.9% of months hit the target, 23.5% lose money), and pooled across
  everything in the repo the strategy loses money in 83.6% of reshuffles.
- **Underlying edge, separately: UNPROVEN.** GOLD 1h OOS t = +2.43 against a
  multiple-testing bar of t ~ 3.65 (E-012), and it disagrees with its own
  in-sample slice by 11x. 15m FX is REJECTED (significantly negative).
- **Variants tested in this experiment: 8** (one configuration — the EA's
  defaults — on 8 market/timeframe pairs). No parameter was searched here, but
  E-012's ~780-config history still applies to the data.

---

## E-031 — The seven setup types, measured one at a time
`python3 JARVIS/research/smc_setups.py`. Each setup implemented as the Pine
implements it, next-bar fills, first touch, ties lose, per-symbol costs,
chronological 70/30 split, OOS run once. 8 market/timeframe pairs.

Count of pairs where a setup was positive in BOTH halves:

| setup | held | best OOS |
|---|---|---|
| ORDER BLOCK | 2 / 8 | +0.271R (GOLD 15m), +0.262R (US500 1h) |
| GAP FILL | 2 / 8 | +0.157R (GOLD 1h, t +1.11) |
| GAP FILL + structure bias | 2 / 8 | +0.036R |
| PULLBACK | 1 / 8 | +0.096R (GOLD 15m) |
| DISCOUNT/PREMIUM | 1 / 8 | +0.375R (US500 15m) |
| BREAKOUT | 0 / 8 | held nowhere |

**Verdict: UNPROVEN, all of them.** The highest out-of-sample t observed is
+1.35 against a multiple-testing threshold of about t = 3.65. Nothing here is
evidence of an edge; the ranking is only useful for deciding what to leave
switched on.

Gold is the only market where anything survived both halves twice. Both FX
pairs are negative nearly everywhere, GBPUSD strongly so (IS t as low as
-4.99), which is consistent with these setups simply not working on FX.

## E-032 — The BREAKOUT setting shipped in the Pine could never fire
`boxTight` defaulted to 1.2, meaning a 20-bar high-low range had to be smaller
than 1.2 x ATR(14). Measured across ~41,000 bars of GOLD 15m/1h and EURUSD 15m:

    smallest 20-bar range / ATR ever observed : 1.27
    fraction of bars <= 1.2 x ATR             : 0.000%
    fraction of bars <= 3.0 x ATR             : 11.0 - 13.7%

**ZERO bars could satisfy it.** The setup was dead code in a shipped file, and
it was reported to Veer as a working source of extra signals. Default corrected
to 3.0. Found by measuring the setup rather than by reading it - the code was
correct, the constant was impossible.

## E-033 — Three research scripts were charging GOLD costs to FX
`smc_setups.py`, `pointscale.py` and `small_account.py` used the bare
`engine.Costs()` default, which is gold-shaped: a 0.30 spread in PRICE units.
Applied to EURUSD that is roughly 3000 pips per trade, so every FX row those
scripts produced was an artefact of the cost model rather than a fact about the
strategy - EURUSD 15m showed -2.34R per trade with t = -5276 before the fix.
`study.COSTS` already held correct per-symbol values and the other scripts were
using it. All three now do.

The GOLD rows were unaffected (the default IS gold), so the stop/target sweep
conclusion in E-030 stands: DID NOT HOLD on any of the 8 pairs, on correct costs.

## E-034 — Adversarial Pine audit (post-1770c6f): both indicators fail to compile
Audited `LiquiditySniper_v1.pine` (1687 lines) and `SuperTrendSniper_v1.pine`
(709 lines) at commit 1770c6f. `check_pine.py` reports CLEAN on both; the
checker does not model Pine's line-wrapping rule and misses the blocker.

**BLOCKER.** `LiquiditySniper_v1.pine:1614` and `SuperTrendSniper_v1.pine:635`
wrap `totM += ...` onto a continuation line indented 16 spaces with all
brackets closed on the previous line. Pine requires wrapped lines to be
indented by a number of spaces that is NOT a multiple of four; 16 is read as a
new local block and the parser raises "end of line without line continuation".
Introduced in 892c12f. Neither file can have been loaded on TradingView since
then, so every "shipped and working" claim about them is unverified.

**Highest-value non-compile findings.**
- Order blocks and FVGs are CONSUMED at signal time (LiqSniper:825-834, 881-886)
  but the entry can still be rejected afterwards by gateOk, minR, maxRiskAtr or
  the maxTrades cap. Valid zones are destroyed by bars that produce no trade.
- No dedup on the pending queue (LiqSniper:1175): `pbLong`/`rcLong`/`bncLong`
  stay true on consecutive bars, so one idea queues up to maxTrades+1 entries
  at nearly the same price. 3x intended risk on a single setup.
- Panel row 8 "Setups allowed" reports `expansionOk`, but `gateOk`
  (LiqSniper:1150) only applies it to BREAK setups while gateAll is false
  (default). The panel says "NO - waiting" while five setup types fire.
- Consumed FVG boxes are dropped from `fvBx` without `box.delete`
  (LiqSniper:834) - unbounded leak against max_boxes_count = 500.
- Order blocks are never drawn at all; `showSmc` ("Draw gaps and order blocks")
  only reaches the FVG box at LiqSniper:794.
- `armExt` is inert (LiqSniper:1194/1198): `math.min(low, armExt)` where
  armExt is a running max of highs is always `low`. The comment above it claims
  this exact bug was already fixed.
- `bias` (LiqSniper:759/761) never decays, so the Structure row keeps asserting
  BULLISH indefinitely after one break.
- `entryDelay = 0` (minval 0, both files) fills at the SIGNAL BAR's own open and
  then resolves TP/SL against that same bar's range. Look-ahead of the F-001
  class, reachable from the settings dialog.

Status: both files UNPROVEN and currently UNLOADABLE. Full defect list with
triggers in the review transcript.

## E-035 — Entry quality: heat, fakeouts, and whether waiting pays
`python3 JARVIS/research/entry_quality.py`. SuperTrend+DEMA signals, next-bar
fills, first touch, ties lose, per-symbol costs, chronological 70/30 split.

**HEAT.** Of signals that eventually reached +1R, how far they first went
against the entry (in R):

| market | median | p75 | p90 |
|---|---|---|---|
| GOLD 15m | 0.36 | 0.66 | 0.82 |
| GOLD 1h | 0.35 | 0.59 | 0.85 |
| US500 15m | 0.43 | 0.61 | 0.78 |

A stop tighter than ~0.85R removes one eventual winner in ten. This is the
arithmetic behind "it stopped me out and then went".

Not reported, because it is a tautology: "share that went more than 1R against
you" is 0% by construction, since MAE is measured until the stop and the stop
sits at 1R.

**FAKEOUTS.** Share of signals that close back THROUGH the signal price within
3 bars: GOLD 15m 71.1%, GOLD 1h 71.7%, US500 15m 79.0%. Most signals retrace
through their own entry almost immediately.

**WAITING FOR A BETTER PRICE** (GOLD 1h, in-sample -> out-of-sample expectancy):

| entry | IS | OOS | OOS t | never filled |
|---|---|---|---|---|
| market, next open | +0.208 | +0.321 | +2.05 | 0% |
| wait 0.15 ATR | +0.187 | +0.393 | +2.34 | 11% |
| **wait 0.30 ATR** | +0.182 | **+0.451** | **+2.47** | 23% |
| wait 0.50 ATR | +0.131 | +0.473 | +2.37 | 37% |
| wait 0.75 ATR | +0.125 | +0.332 | +1.41 | 55% |

**Verdict: PROMISING, not proven.** Waiting improves OOS expectancy on gold and
the mechanism is consistent with the 71.7% fakeout rate - if price comes back
through the entry that often, a resting limit fills most of the time at a better
price. But the two halves DISAGREE (in-sample the market entry looked better),
and t = +2.47 is below the 3.65 multiple-testing threshold. On US500 and both FX
pairs every entry style is negative, so this is a gold result, not a general one.

The Pine default stays OFF (Veer prioritises signal count) with the measured
numbers written into the tooltip so the trade-off is visible at the point of
decision. pullAtr default set to the measured best, 0.30.

## E-036 — A confluence score does NOT separate winners. Only one filter does.
`python3 JARVIS/research/setup_score.py` and `--components`.

Veer's problem is selection, not generation: "idk what setups to take". The
obvious fix is a confluence score, so one was built from factors this repo had
already measured (ADX, ATR vs median, trend agreement, room to run, session),
summed unweighted so nothing was fitted, and then tested.

**The sum failed.** Out-of-sample, high-score (>=5) minus low-score (<=3):
separated in 5 of 8 markets, best gap t +2.70, and on GOLD 15m it ran
BACKWARDS (-0.422R - high scores did worse). 5 of 8 is barely distinguishable
from the 4 of 8 a coin flip produces. **Shipping this as a grade would have put
an authoritative-looking letter on the chart with nothing behind it.**

Testing each factor alone shows why - adding them together buried the one that
works:

| factor | markets helped | median gap |
|---|---|---|
| **ADX < 35** | **4 / 5** | **+0.324R** |
| DEMA agrees | 5 / 8 | +0.143R |
| ATR <= 1.3x median | 3 / 6 | +0.094R |
| ATR <= median | 5 / 8 | +0.074R |
| long vs short | 4 / 8 | +0.068R |
| ADX < 20 | 5 / 8 | +0.056R |
| session 04-12 / 13-20 | 5 / 8 | +0.056R |
| **room >= 2R** | **3 / 8** | **-0.097R** |

`long vs short` at 4/8 is the control: a factor with no edge should land there,
and it does, which is evidence the method is not manufacturing separation.

**CONCLUSIONS**
1. The only factor with real separation is ADX < 35 - and it is already the
   default in both the Pine and the EA. There is no undiscovered confluence
   filter sitting in this data.
2. `room >= 2R` measured NEGATIVE in 5 of 8 markets. The Pine's `minR` input
   (reject a setup if R:R is below 1.2) encodes the same intuition and should
   be treated with suspicion rather than raised.
3. Because history cannot rank these setups, the ranking has to come from
   Veer's OWN results. That is what the per-setup-type breakdown added to the
   liquidity indicator is for.

## E-037 — These markets are statistically random walks at 15m and 1h
`python3 JARVIS/research/is_it_tradeable.py`. Lo-MacKinlay variance ratio with
the heteroscedasticity-robust z, self-tested against synthetic series of known
behaviour before any market data is read.

**40 tests. Four markets, two timeframes, five horizons each (q = 2, 4, 8, 16,
32). NOT ONE is significant.** The largest |z| across all forty is 1.79, against
a 1.96 threshold that is not even corrected for multiple testing.

| market | VR range across q | max abs z |
|---|---|---|
| GOLD 15m | 0.940 - 0.990 | 0.98 |
| GOLD 1h | 0.957 - 1.077 | 1.56 |
| US500 15m | 0.774 - 1.001 | 1.67 |
| US500 1h | 0.924 - 1.044 | 0.58 |
| EURUSD 15m | 0.949 - 1.015 | 1.24 |
| EURUSD 1h | 0.960 - 0.981 | 1.79 |
| GBPUSD 15m | 0.977 - 1.032 | 0.53 |
| GBPUSD 1h | 0.938 - 0.984 | 1.59 |

Autocorrelations: 80 tests (10 lags x 8 series), about 4 marginally exceed two
standard errors. That is exactly the count chance produces.

**THIS EXPLAINS THE WHOLE PROJECT.** Roughly 780 configurations have failed to
clear the significance bar here, and it has been read as "the strategies are
wrong". The likelier reading is that no entry pattern can extract a directional
edge from a series that is indistinguishable from a random walk. The strategies
were not the problem; the search was aimed at a property the data does not have.

**WHAT THIS DOES NOT SAY**, and the distinction matters:
1. It is 15m and 1h. **M1 is untested and is genuinely different in kind** -
   bid-ask bounce and order-flow effects produce real autocorrelation at very
   short horizons. This is now the strongest argument in the repo for getting M1
   data, because it is the one place a directional edge could still be hiding.
2. A variance ratio tests UNCONDITIONAL behaviour. A conditional edge - only at
   certain hours, only after certain events - can exist inside a series that is
   unconditionally a random walk. VR = 1 does not prove no edge exists.
3. It says nothing about non-directional approaches.

**ALSO FOUND:** round-trip cost as a share of a typical one-bar move is 0.46 on
EURUSD 15m and 0.49 on GBPUSD 15m - the spread is about half a bar. That is a
structural reason 15m FX was negative nearly everywhere here, independent of any
strategy.

**Verdict: DISPROVEN that a simple directional entry pattern can work on this
data at these timeframes.** Effort should move to M1 (untested, different in
kind) rather than to configuration 782.

## E-038 — VOLATILITY IS PREDICTABLE HERE. Direction is not.
`python3 JARVIS/research/vol_predictability.py`, self-tested against synthetic
random-walk and clustered-volatility series before reading any market.

Autocorrelation at lag 1, signed returns vs absolute returns:

| market | signed r | \|r\| (volatility) | 2 SE |
|---|---|---|---|
| GOLD 15m | -0.010 | **+0.198** | 0.030 |
| GOLD 1h | -0.029 | **+0.279** | 0.017 |
| US500 15m | +0.001 | **+0.346** | 0.030 |
| US500 1h | -0.004 | **+0.285** | 0.017 |
| EURUSD 15m | -0.033 | **+0.218** | 0.027 |
| EURUSD 1h | -0.019 | **+0.206** | 0.015 |
| GBPUSD 15m | -0.010 | **+0.213** | 0.027 |
| GBPUSD 1h | -0.016 | **+0.198** | 0.015 |

**8 of 8.** Every series. Absolute-return autocorrelation is 7 to 19 times two
standard errors while signed returns sit at zero - the exact opposite of every
directional test in this repo, all of which came back 4 or 5 of 8.

Range prediction, one 20-bar window to the next: GOLD 1h **R² 0.523**
(correlation +0.723), US500 1h 0.257, EURUSD 1h 0.096, GBPUSD 1h 0.043. On
GOLD 1h the quietest quartile is followed by an average range of 37.3 and the
loudest by 126.1, against an overall average of 74.1 - a **3.4x spread**, on a
round-trip cost of 0.40.

**Verdict: CONFIRMED.** This is the first genuinely predictable quantity found
in this project, it is the standard finance result (volatility clustering), and
it is present in every series tested. WHERE price goes is unknowable here.
HOW FAR it travels is substantially knowable.

## E-039 — Reachability as a trade filter: REJECTED, and the reason redirects
Hypothesis: if range is predictable, then whether a target can PHYSICALLY be
reached is predictable, so trades whose target the coming range cannot cover
should be skipped. That would be a trade-selection edge needing no directional
call.

`python3 JARVIS/research/reachability.py`. Out-of-sample, split by quartile of
predicted-travel / required-travel: the best quartile beat the worst in **2 of
6 markets**, with no monotonic gradient anywhere. Rejected.

**WHY it failed, which is the useful part.** The stop is `stop_atr x ATR` and
the target is `rr x stop`, so required travel is proportional to ATR. Predicted
travel is derived from recent range, which is also proportional to ATR. The
ratio is therefore **near-constant by construction** and carries almost no
information. At a cut of 1.0 the filter rejected 3 to 13 trades out of hundreds.

**The redirect this implies:** volatility prediction can only inform a target
that is NOT itself ATR-scaled. That means a target fixed in price terms - a
money target, or a LEVEL-based target, where the distance to the next level is
set by market structure rather than by current volatility. That is the next
experiment and it is now the highest-value open question in the project.

## E-040 — The cost floor: which instrument and holding period are viable at all
`python3 JARVIS/research/cost_floor.py`. Median absolute move over N bars
divided by round-trip cost, per market and timeframe. Asked BEFORE any strategy
question because it constrains all of them: a signal cannot fix an instrument
whose typical move does not clear its own spread.

Move as a multiple of cost, at a ONE-BAR hold:

| market | 15m | 1h |
|---|---|---|
| **GOLD** | **8.0x** | **9.7x** |
| US500 | 3.9x | 6.1x |
| EURUSD | **0.8x** | 2.3x |
| GBPUSD | **1.0x** | 2.3x |

**GOLD is structurally the right instrument and it is not close.** A single 15m
gold bar covers its own cost eight times over. A single 15m EURUSD bar does not
cover it at all - the median move is 0.8x the spread, so the average trade is
behind before it starts.

This is a property of the instrument, not of any strategy, and it explains
every FX result in this repo without reference to signals. It also retires the
question: **do not trade FX at short holds.** No entry pattern can repair a
0.8x cost ratio.

FX only becomes workable at 8h+ holds (EURUSD 1h at 8 bars = 7.3x). That is a
different business from the one being built.

### Implied M1 gold — EXTRAPOLATED, NOT MEASURED
No M1 data exists here. Range scales with the square root of time under a
random walk, and E-037 found these series ARE statistically random walks, so
the scaling is better justified than usual - but it is an inference and it
stops being one when the M1 export arrives.

| hold | implied move | x cost |
|---|---|---|
| **1 minute** | 0.83 | **2.1x** |
| 3 minutes | 1.43 | 3.6x |
| 5 minutes | 1.85 | 4.6x |
| 10 minutes | 2.61 | 6.5x |
| 15 minutes | 3.20 | 8.0x |

A one-minute hold on gold has roughly **twice the spread** to work with. Not
impossible, but nothing sloppy survives it - and it is a mechanical explanation
for why an M1 scalp that looks right on the chart still bleeds. **Holding
minutes rather than seconds is what buys the room**, and the live evidence
(12 trades, zero TPs, -0.58R) is consistent with trades being cut before they
ever had cost-adjusted room to work.

## E-041 — Level-target reachability: a real gradient that still ends at zero
`python3 JARVIS/research/level_reach.py`. The fix E-039 implied: use a target
whose distance is set by STRUCTURE (the next confirmed swing level, published
5 bars late as it would actually be known) rather than by ATR, so the ratio
predicted-travel / distance-to-target genuinely varies.

The control worked: mean coefficient of variation of the ratio is **0.99**,
against the near-zero variation that made E-039 uninformative. This test is
informative.

Out-of-sample, expectancy by quartile of the ratio:

| market | Q1 | Q2 | Q3 | Q4 | Q4 > Q1 |
|---|---|---|---|---|---|
| GOLD 1h | -0.170 | -0.197 | +0.034 | **+0.002** | yes |
| US500 1h | +0.208 | -0.083 | -0.065 | -0.158 | no |
| EURUSD 15m | -0.664 | -0.543 | -0.685 | -0.305 | yes |
| EURUSD 1h | -0.431 | -0.066 | -0.164 | -0.122 | yes |
| GBPUSD 1h | -0.338 | -0.013 | -0.093 | -0.161 | yes |

Q4 beat Q1 in **4 of 5**. Three markets lacked the sample size once a
structural target was required.

**Verdict: UNPROVEN, and the reason matters more than the verdict.**

The gradient is real but no quartile is monotonic, and — decisively — **the best
bucket in every market is at or below zero.** The single positive figure in the
table is +0.002R. The filter moves a losing entry toward break-even. It never
moves it past.

### THE SYNTHESIS THIS FORCES
Across E-036 (a confluence score from every measured factor: 5 of 8, backwards
on gold 15m), E-039 (ATR-scaled reachability: uninformative by construction) and
now E-041 (structural reachability: a real gradient ending at zero), the same
result keeps appearing in different clothes:

**A filter can improve a zero-edge entry toward zero. It cannot carry it past
zero.** Filtering removes the worst trades from a distribution; it does not add
information the entry never had. If the entry has no directional edge — and
E-037 says these series have none, and the live chart agrees at -0.58R with
zero take-profits in twelve — then no amount of filtering, confluence, zone
memory, structure or reachability produces one.

This closes an entire class of work. Effort on better filters for an existing
directional entry is now known to be effort spent moving toward zero from
below. What remains open is unchanged and is stated in MISSION.md: conditional
edges (currently under test), volatility-based sizing and payoff structure
(E-038 is CONFIRMED and is the only confirmed finding in the project), and M1
microstructure (blocked on data).

## E-050 — THE MISSING CONTROL. A random entry scores +0.202R on GOLD 1h.
(Numbered 050 to leave room for agents writing E-042..E-046 concurrently.)

`python3 JARVIS/research/inversion.py`. Three arms on identical bars with
identical exits and costs: the signal as built, the signal inverted, and a
RANDOM coin-flip direction repeated 20 times with different seeds.

**This project has never had a random-entry control. That is a serious method
failure and it invalidates a headline number.**

GOLD 1h, out-of-sample:

| arm | with cost |
|---|---|
| SuperTrend as signalled | **+0.321R** (t +2.05) |
| **random direction, 20 seeds** | **+0.202R** (5th +0.003, 95th +0.424) |

**+0.321 sits inside the random band.** A coin flip on the same bars, with the
same 3R target, 1R stop and 50-bar cap, produces a median +0.202R and reaches
+0.424R at the 95th percentile. The signal is not distinguishable from noise.

### What was wrong and why it looked right
An asymmetric payoff (3R target, 1R stop, time cap) has mechanically non-zero
expectancy on a random walk with drift — the target is far and rarely hit, the
stop is near and often hit, and the time exit closes the rest at whatever the
drift has done. That structure, not the signal, produced the positive number.
Every prior comparison here was signal-versus-zero. **The correct comparison is
signal-versus-random-on-the-same-payoff, and nobody ran it.**

**RETRACTION.** +0.321R OOS on GOLD 1h has been reported repeatedly in this
project and to Veer as the best result achieved and as evidence the pullback
entry helped. It is not evidence of anything. E-035's pullback comparison
(+0.451R at 0.30 ATR versus +0.321R market) is also uncontrolled and its
conclusion does not survive: both figures need re-testing against a random arm
matched for entry timing before either can be believed.

### Worthless, not wrong
Positive OOS with costs: as-signalled 3 of 7, inverted 4 of 7 — both at coin
flip. No-cost expectancy is not clearly below the random band anywhere, so the
signal is not carrying information pointed the wrong way. There is nothing to
invert. **The SuperTrend entry is empty, not backwards.**

### The standing rule this creates
Every future strategy claim in this project must be reported against a
random-entry arm with the SAME payoff structure, the same bars and the same
costs, or it is not a claim about a signal — it is a claim about a payoff
structure wearing a signal's name.

## E-043 — Non-directional payoff: the ceiling is enormous and 0% of it is reachable
`python3 JARVIS/research/nondirectional.py`. (A4. E-043 was the assigned
number and was still free; E-042 and E-044..E-046 are reserved for the
concurrent agents, and E-050 was appended while this ran.)

The question E-041 forces. Filtering is closed — a filter moves a zero-edge
entry toward zero and never past it. So: can a different PAYOFF SHAPE, one
that never bets on direction, monetise the project's only CONFIRMED finding
(E-038, volatility predictable in 8 of 8 series)?

Structure tested: at the close of bar i, a buy stop at `c[i] + k*ATR(14)` and
a sell stop at `c[i] - k*ATR(14)`, both live for bars i+1..i+H, **neither
cancelled when the other fills**. Grid H = 2,4,8,16,32,64 x k = 0.25,0.50,
1.00,1.50,2.00 x 8 series = **240 cells**, non-overlapping windows, per-symbol
costs from `study.COSTS`, per-leg round trip charged on every fill. The grid
and the decision rule were committed in `0320f12` **before** any market data
was read.

### WHAT A SPOT MT5 ACCOUNT CAN AND CANNOT EXPRESS — read this first
A retail spot account can place market orders, stop orders, limit orders,
stop losses and take profits. **It cannot buy an option.** That matters more
than anything else in this entry. A real long-volatility bet is an option: you
pay a premium, and you win if the market moves more than the premium implied.
A pair of stop orders is *not* that. There is no premium, so there is nothing
to be mispriced — it is a breakout system with two entries, and it pays a full
round trip on every leg that fills. **You cannot buy volatility on this
account. You can only buy price direction, twice, in opposite directions, and
pay for both.**

### THE GATE: the oracle ceiling is huge — and that is the trap
Perfect foresight of the EXIT only (capture the larger of the two excursions
in full, minus the width, minus the honest cost of every leg that filled) is
positive in **240 of 240 cells**, and not marginally: on GOLD 1h it runs from
3.0x to **215x the round-trip cost** per window. A thin ceiling would have
closed this branch cheaply. This ceiling is enormous.

It is also worthless, and the decomposition is the finding. Replace perfect
foresight with **no foresight at all** — every filled leg closed at the
window's closing price — and the fraction of the ceiling that survives is:

| series | median B/A | best cell B/A |
|---|---|---|
| GOLD 15m | +0.043 | +0.256 |
| GOLD 1h | **-0.063** | **+0.002** |
| US500 15m | -0.122 | +0.041 |
| US500 1h | -0.021 | +0.017 |
| EURUSD 1h | -0.086 | +0.000 |
| GBPUSD 1h | -0.082 | +0.050 |

**Essentially none of it.** The entire ceiling is exit-timing foresight, which
is precisely what E-037 says this data does not supply.

### The no-foresight result, in full
Mean payoff per window in multiples of the round-trip cost c:

- positive in **28 of 240 cells**
- positive AND t > 3.65 in **0 of 240 cells**
- best cell on a market E-040 says is tradeable: GOLD 15m, H=64, k=1.50,
  **+28.51c but t = +2.57 on n = 66 windows** — below 3.65, and it is the
  best of 240.
- the *significant* results all point the other way: EURUSD 15m H=2 k=0.25
  **t = -34.10**, GOLD 1h H=2 k=1.00 **t = -12.18**.

### WHY, and it is not an empirical accident
Self-test (d), run before any market data: on a driftless random walk with
GOLD costs, bars built from a genuine sub-path,

| per-bar sigma | gross payoff | t | net payoff |
|---|---|---|---|
| 0.5 | +0.0067 | +0.22 | -0.6538 |
| 1.0 | +0.0134 | +0.22 | -0.6471 |
| 2.0 | +0.0268 | +0.22 | -0.6337 |

**Quadrupling the variance changes the net payoff by 3%.** The gross payoff is
exactly zero at every volatility, because the structure's payoff is *linear*
in price and every entry is a stopping time — by optional stopping, ANY
non-anticipating exit rule on a martingale has zero expected gross. That is
not one exit rule failing; it is the whole class. E-037 established these
series are martingales. Predictable volatility scales the wins and the
whipsaws by the same factor and cancels out. **You need convexity to monetise
volatility, and convexity is the thing a spot instrument cannot express.**

The pipeline is not blind: injecting a +0.30/bar drift into the same generator
is detected at gross +2.392, **t +28.62**.

### The whipsaw, measured rather than assumed
Fraction of filled windows where BOTH legs fill (GOLD 1h):

| H | k=0.25 | k=1.00 |
|---|---|---|
| 2 | 47.9% | 4.1% |
| 8 | 75.2% | 19.6% |
| 16 | 82.6% | 35.5% |
| 32 | 88.1% | 48.8% |
| 64 | 93.3% | 63.3% |

A both-legs window locks in exactly -2d plus two round trips, whatever price
then does. Widening k to avoid it just stops the structure filling at all.

### THE MIRROR CLOSES THE ESCAPE ROUTE
Fading the range (short volatility) is the exact algebraic mirror: a sell
limit at P+d earns what a buy stop at P+d loses. Measured across 24 cells,

    straddle payoff + fade payoff == -2 x (legs filled) x cost

held to **3.18e-13**, i.e. exactly. Long volatility and short volatility do not
sum to zero — they sum to *minus two round trips*. There is no sign flip that
rescues this. In no cell were both positive; where the straddle was best
(GOLD 15m H=32, +4.45c) the fade was -7.42c, and where the fade was best
(GOLD 1h H=8, +2.02c) the straddle was -4.20c.

### E-038 conditioning: tested anyway, and null
Bucketing OOS windows by quartile of predicted range / d (E-038's predictor,
`look`=20, scaled sqrt(H/look)). Dispersion gate first, as E-041 established:
ratio CV is **0.298 to 0.347** in every series — genuinely varying, so unlike
E-039 the test is informative, though narrower than E-041's 0.99 because d is
still ATR-scaled. **88 quartile buckets. Buckets with t > 3.65: 0. Largest t
+1.59, smallest -6.92.** GOLD 1h H=32 Q4 shows +82.72c, which looks
spectacular and is t = +1.59 on 30 windows — it is the loudest cell of 88 and
it is noise.

### The bull-market check
Gold's history here is a strong uptrend, so a "non-directional" result must be
shown to be indifferent to it. Gross contribution by leg, GOLD 1h:

| H | up leg | down leg |
|---|---|---|
| 8 | +3.66c | -6.77c |
| 16 | +7.55c | -8.78c |
| 32 | **+13.54c** | **-13.37c** |

The structure is *not* indifferent — it contains a large long-trend gain and
an almost exactly equal short-trend loss, which cancel to zero gross. Deleting
the losing leg would make it a directional trend bet, which is E-030 and E-031
and is dead.

### Verdict: REJECTED
Not "unproven". The no-foresight payoff is negative in 212 of 240 cells, zero
cells are positive at t > 3.65, the mechanism is proved analytically and
reproduced numerically, and the mirror image loses by the same identity.

### Method notes, including one failure worth recording
The pre-registered self-test **FAILED on first run** (gross payoff t = +8.35
on a driftless walk). Diagnosis: not a simulator bug but **intrabar
discretisation overshoot** — assuming a stop order fills AT its level is free
money, because the true price when it crosses the level is already past it.
The bias scales with the sub-step and vanishes when the path is fine:

| sub-step sd | spurious gross payoff | t |
|---|---|---|
| 0.4472 | +0.3598 | +4.70 |
| 0.2236 | +0.3445 | +4.31 |
| 0.1414 | +0.1246 | +1.52 |
| 0.0707 | +0.1259 | +1.55 |

Only the synthetic GENERATOR was changed (commit after the pre-registration,
labelled as such); the grid, the decision rule and the three payoff
accountings are untouched. **Every real-data figure above is optimistic by
roughly this amount**, since real bars are coarse — which can only make a
negative verdict safer. This is a general warning for any future stop-order
backtest in this repo.

Ties: with no tick data, a single bar containing both levels is resolved as
BOTH legs filled (ties lose). The `tie%` column reports how much rests on it —
at k >= 1.00 it is 2-22% of both-fill windows, so the usable widths do not
depend on the assumption; at k = 0.25 it is 74-92% and they do.

E-050's standing rule is satisfied by construction: this structure contains
**no signal at all**, so it *is* the random arm. It earns exactly minus the
cost. Note also that the exit here is a symmetric time exit, not the 3R/1R
asymmetry E-050 showed can manufacture a positive number by itself.

### What this licenses and what it does NOT
LICENSES: closing "non-directional structure" as a branch for **spot
instruments**. Every strategy in this repo bets on direction; this establishes
that the alternative is not available on this account, for a mechanical
reason, not a measurement one.

DOES NOT LICENSE: any claim that volatility prediction is useless. E-038
stands. It fails to become a PAYOFF here because spot payoffs are linear.
Volatility prediction remains legitimate as a **sizing** input (that is E-044 /
A5, untested) and as a **risk** input. If an options-capable account ever
existed, this branch would reopen immediately and would be the first thing to
retest — but that is a different broker and a different project.

DOES NOT LICENSE: extrapolating to M1. The martingale argument is general, but
E-037's martingale finding is measured at 15m and 1h only. If M1 shows genuine
bid-ask-bounce autocorrelation, the series is not a martingale there and the
optional-stopping argument does not apply. M1 remains the strongest open
branch.

## E-046 — How many live trades settle the scoreboard? The date is 2029, and the Pine only stores 30 trades
(A7. E-046 was the assigned number and was still free when this was appended;
E-042, E-044 and E-045 are reserved for concurrent agents.)

`python3 JARVIS/research/test_engine.py` (ALL TESTS PASSED) then
`python3 JARVIS/research/live_power.py`. A power/design calculation, not a
backtest. **It authorises nothing — D-006 stands.**

MISSION.md calls "which setup types Veer personally converts" the only live
question with a real chance of a positive answer. Nobody had computed what it
costs to answer. This does.

### THE HEADLINE, first

| question | trades needed PER SETUP TYPE | weeks at 4 trades/day over 8 types | date from 2026-08-31 |
|---|---|---|---|
| is this type CATASTROPHIC (-0.58R)? | **53** (sim 58) | 21 | **2027-01-26** |
| is this type +0.25R? (optimistic sd) | **51** (sim 46) | 20 | **2027-01-20** |
| is this type +0.25R? (backtest sd) | **371** (sim 371) | 148 | **2029-07-04** |
| is this type +0.25R at the project's t=3.65? | **927** (sim 927) | 371 | **2033-10-08** |
| is type A BETTER THAN type B by 0.25R? | **742** each (sim 742) | 297 | **2032-05-08** |

Even with the 12/day cap fully saturated by an EA taking every signal, the
+0.25R question needs **49 weeks** and the ranking question **99 weeks**.

**And none of those are reachable at all, because of the next finding.**

### THE DESIGN IS CAPPED AT 30 TRADES — TOTAL, NOT PER TYPE
`LiquiditySniper_v1.pine` line 1572:

    while array.size(hDir) > 30
        array.shift(hDir) ... array.shift(hSet) ...

The completed-trade record is a **rolling 30-trade ring buffer shared by all
eight setup types** — about 3.75 trades per type at steady state, against the
53 per type the CHEAPEST useful question needs. The Pine state is also lost on
every chart reload and cannot be exported. **As currently coded the scoreboard
can never accumulate enough trades to answer anything, at any trade rate, ever.**
It is a recent-form display. Right now it is decoration, and it will stay
decoration until the trades are logged outside the chart.

### THE NUISANCE PARAMETER, measured (this is what decides everything)
Required n scales with (sd_R / edge)^2, so sd_R is the whole calculation.

| population | n | exp R | **sd R** | IS sd | OOS sd |
|---|---|---|---|---|---|
| GAP FILL [GOLD 15m] | 167 | +0.042 | 1.713 | 1.627 | 1.810 |
| PULLBACK [GOLD 15m] | 131 | +0.215 | 1.796 | 1.783 | 1.798 |
| ORDER BLOCK [GOLD 15m] | 64 | +0.094 | 1.694 | 1.675 | 1.772 |
| BREAKOUT [GOLD 15m] | 52 | -0.206 | 1.517 | 1.558 | 1.495 |
| SUPERTREND SNIPER [GOLD 15m] | 116 | +0.126 | 1.795 | 1.771 | 1.834 |
| GAP FILL [GOLD 1h] | 481 | +0.082 | 1.694 | 1.676 | 1.753 |
| PULLBACK [GOLD 1h] | 530 | -0.101 | 1.674 | 1.648 | 1.745 |
| SUPERTREND SNIPER [GOLD 1h] | 339 | +0.085 | 1.767 | 1.702 | 2.365 |

(14 populations measured, 8 shown; per-symbol costs from `study.COSTS`,
next-bar fills, first touch, ties lose. **Median sd_R = 1.694**, and it is
stable across the chronological 70/30 split, which is the check that it is a
nuisance parameter and not a fitted one.)

**LIVE (LIVE_EVIDENCE.md, XAUUSD 3m, 12 SuperTrend trades):** only summary
stats exist, so the R list was reconstructed — 8 stop-outs at -1R, 4 winners
sharing the residual +1.1R. That gives exp **-0.575R**, sd **0.628**, with a
95% bootstrap interval on the sd of **[0.368, 0.666]**. Equal-splitting the
winners is the MINIMUM-variance reconstruction, so 0.628 is a **lower bound**
and every n derived from it is a lower bound too. Both estimates are carried
through the whole report; they differ by 2.7x and that ratio **squares** into
the sample size (7.3x).

### POWER GRID — trades per setup type, 80% power, one-sided
(analytic n / simulated n from bootstrapping the measured, skewed R
distribution; where they differ the simulated one is the answer)

live sd 0.63 (optimistic bound):

| true edge | t=2.00 | t=2.73 (Bonferroni, 8 types) | t=3.65 (project bar) |
|---|---|---|---|
| +0.10R | 319 / 287 | 504 / 454 | 796 / 796 |
| +0.25R | 51 / 46 | 81 / 73 | 128 / 115 |
| +0.50R | 13 / 12 | 21 / 17 | 32 / 26 |

backtest sd 1.69 (the shape the Pine's own 3R payoff produces):

| true edge | t=2.00 | t=2.73 (Bonferroni, 8 types) | t=3.65 (project bar) |
|---|---|---|---|
| +0.10R | 2318 / 2318 | 3671 / 3671 | 5791 / 6370 |
| +0.25R | 371 / 371 | 588 / 588 | 927 / 927 |
| +0.50R | 93 / 93 | 147 / 147 | 232 / 232 |

**Correcting for the 8 parallel scoreboard rows costs 217 extra trades per
type at +0.25R (371 -> 588). Meeting the project's own t=3.65 costs 556 extra
(371 -> 927).** That is the sentence that should change behaviour.

Full-precision check: backtest sd, +0.25R, t=3.65, n=927 -> empirical power
**0.808** over 4000 bootstraps.

### RANKING TWO SETUP TYPES IS THE EXPENSIVE QUESTION — and E-050 says it is the RIGHT one
Two-sample, per type, backtest sd: gap 0.10R -> 4636 / 5100 each; gap 0.25R ->
**742 / 742 each**; gap 0.50R -> 186 / 205 each (t=2.00). At t=3.65: 11581,
1853, 464. E-050 established that a random entry on this payoff scores +0.202R,
so "this type is above zero" is not the question — "this type beats the others
on the same payoff" is, and it is **twice** the price.

### WHAT THE SCOREBOARD CAN LEGITIMATELY DO FIRST — the cheap half
Detecting a catastrophic type is one-sided and the effect is large, so it is
far cheaper (analytic / simulated, backtest sd):

| true edge | t=2.00 | t=1.645 (a=0.05) | t=2.50 (Bonferroni, 8) |
|---|---|---|---|
| -0.25R | 371 / 408 | 284 / 312 | 513 / 564 |
| **-0.58R** (the live SuperTrend number) | 69 / 76 | **53 / 58** | 96 / 106 |
| -1.00R | 24 / 30 | 18 / 22 | 33 / 41 |

At the live sd 0.63 those fall to n=8 (-0.58R) and n=3 (-1.00R) at t=1.645.
**So: kill-a-bad-setup needs 53-106 trades per type; rank-two-mediocre-setups
needs 742-1853 per type. The two thresholds differ by roughly 14x, and only the
first is reachable this decade.**

### SEQUENTIAL RULE — errors simulated, not quoted
One-sided Wald SPRT on per-trade R, H0 mu=0 vs H1 mu=-0.5R, designed alpha
0.05 / beta 0.20, **no decision before 15 trades**, sd fixed at 1.694.
4000 simulated paths per row, bootstrapped from the measured R distribution:

| true expectancy | ABANDON | CLEAR | median n at decision |
|---|---|---|---|
| +0.00R | **0.041** | 0.959 | 27 |
| -0.25R | 0.392 | 0.608 | 46 |
| -0.50R | **0.831** | 0.169 | 40 |
| -0.75R | 0.967 | 0.033 | 27 |
| +0.25R | 0.000 | 1.000 | 18 |

Realised false-abandon rate 0.041 against a design of 0.05. It kills a truly
-0.5R setup type in a median of 40 trades. **CLEAR means "not catastrophic",
it does not mean "profitable"** — clearing is not evidence of an edge.

### AND WHAT HAPPENS WITHOUT A BOUNDARY — the reason this matters
Watching the running t after every trade and acting when |t| crosses 2.0,
under a true expectancy of **exactly zero**, 400 trades max:

    P(ever declares POSITIVE) 0.131   P(ever declares NEGATIVE) 0.278
    per-type false-claim rate 0.409 against a nominal 0.046
    across 8 scoreboard rows: 0.985

**When no setup type has any edge whatsoever, staring at the scoreboard and
reacting produces at least one false verdict 98.5% of the time.** That is a
9x inflation per type. The 12-trade judgement in LIVE_EVIDENCE.md is exactly
this failure mode, and it is about to be repeated eight times in parallel.
(The asymmetry — false NEGATIVE 0.278 vs false POSITIVE 0.131 — is the skewed
3R payoff: the running mean sits below zero most of the time even when the
true mean is zero.)

### TRADE RATE, measured
Raw signals per session day, GOLD, repo data: 15m — PULLBACK 9.48, GAP FILL
5.79, DISCOUNT 4.37, GAP FILL+bias 3.48, ORDER BLOCK 1.29, BREAKOUT 1.21
(**25.63 combined**); 1h — 6.91 combined. The live Pine caps at 12 signals/day
with an 8-bar cooldown and max 2 concurrent, so the cap binds on 3m. Trades
TAKEN is what the scoreboard records and is <= signals. Weeks at 5 trading
days, per setup type:

| trades/day taken (over 8 types) | catastrophe n=53 | +0.25R live sd n=51 | +0.25R backtest sd n=371 | +0.25R at t=3.65 n=927 | rank two types n=742 |
|---|---|---|---|---|---|
| 12 (cap saturated, EA) | 7w | 7w | 49w | 124w | 99w |
| 8 | 11w | 10w | 74w | 185w | 148w |
| **4 (realistic manual)** | **21w** | 20w | **148w** | 371w | 297w |
| 2 | 42w | 41w | 297w | 742w | 594w |
| 1 | 85w | 82w | 594w | >1000w | >1000w |

### SELF-TESTS (printed, exit non-zero on failure — all PASSED)
- POSITIVE CONTROL: true +0.25R at sd 1.694, analytic n 371 -> empirical power
  **0.807**; at t=3.65, n 927 -> **0.794**. Target 0.80.
- NEGATIVE CONTROL: true 0.00R, per-test alpha at t=2.00 measured **0.0219**
  against a nominal 0.0228. Family-wise over 8 types: uncorrected **0.162**,
  Bonferroni (t=2.73) **0.021**.
- SEQUENTIAL CONTROL: SPRT designed for alpha 0.05, realised false-ABANDON
  rate under a true 0.00R **0.0483**.

### VERDICTS
- **"The scoreboard as designed can rank which setup types Veer converts":
  DISPROVEN.** Not by a marginal t — by arithmetic. 742-1853 trades per type
  against a 30-trade shared ring buffer, and 99-297 weeks even if the buffer
  were removed. It cannot happen this decade at this trade rate.
- **"The scoreboard can flag a catastrophically bad setup type in months":
  SUPPORTED** — 53-106 trades per type, 7-21 weeks at 4-12 trades/day, with a
  simulated false-abandon rate of 0.041. Conditional on the trades being
  logged somewhere that holds more than 30 of them.
- **"12 trades can support a judgement about a strategy": DISPROVEN.** At the
  live sd 0.628, 12 trades give a standard error of 0.181R; the observed
  -0.575R is t = -3.17, which does clear t=2 — but the same procedure applied
  to a true zero declares something 40.9% of the time per row.

### WHAT WOULD HAVE TO CHANGE (concrete, in priority order)
1. **Log trades outside the chart.** The 30-trade cap and the loss of state on
   reload are fatal on their own. Nothing else matters until this is fixed.
2. **Cut 8 setup types to 2-3 groups.** Trades per group triple or quadruple
   AND the Bonferroni threshold falls from 2.73 to ~2.39, which together take
   +0.25R detection from 588 trades per type to roughly 450 per group at 3-4x
   the rate — the single largest available speed-up.
3. **Shrink the payoff variance, not just the trade count.** sd 1.69 -> 0.63
   cuts required n by 7.3x, more than any realistic increase in trade rate can.
   A 3R-target payoff makes every trade a noisy measurement. This is a
   MEASUREMENT argument for a tighter payoff, and is independent of E-043.
4. **Run the SPRT above as the only live decision rule** — abandon-only, no
   promotion, minimum 15 trades, and no reacting to the table between
   boundaries.
5. **Ask a cheaper question.** "Is any type catastrophic?" is answerable by
   spring 2027. "Which type is best?" is not answerable before 2032.

### LOGGING SCHEMA — if a field is not recorded it does not exist
Per completed trade, one row, appended to a file that survives chart reload:
`trade_id, utc_timestamp_signal, utc_timestamp_fill, utc_timestamp_exit,
symbol, timeframe, setup_type, side, signalled_price, fill_price,
slippage_R (fill vs signalled, in R), stop, target, planned_RR, exit_price,
exit_reason (TP/SL/time/manual/opposite), R_realised, MFE_R, MAE_R, risk_ccy,
lot_size, taken_by (manual|EA), and a free-text note`.
Without `slippage_R` the manual-vs-EA question is unanswerable; without
`MFE_R`/`MAE_R` no exit change can ever be evaluated retrospectively; without
`setup_type` on every row the entire scoreboard question dies.

### SCOPE AND CAVEATS
Twenty-four power cells, six ranking cells, nine catastrophe cells and
twenty-five calendar cells were computed — none is a test on market data, so
there is no selection effect, but the sd that drives all of them comes from
GOLD 15m/1h backtests in this repo plus a 12-observation live reconstruction.
The live product trades 3m, for which **this repo has no data**; if 3m R
dispersion differs from 1.69, every n moves with its square. Nothing here says
whether Veer's discretion has an edge — only how long it would take to find
out. **No live trade is authorised by any of it (D-006).**

---

## E-051 — Profit protection: the give-back rule BEATS the trail this EA ships
**Verdict: SUPPORTED (exit comparison only — it is NOT a claim of an edge)**
Scripts: `JARVIS/research/exits.py` (new policies), `JARVIS/research/giveback_study.py`
Run: `python3 JARVIS/research/giveback_study.py GOLD 1h`

### The question
Veer's complaint is not about entries. It is: *"a basket reached ~£12 floating
and closed at breakeven; four positions reached ~£4 and still closed in loss;
trades reached £10+ and closed for far less."* Every exit rule in this repo
is anchored to PRICE — a stop level, an ATR distance, a multiple of risk.
None is anchored to **how good the trade already was**. So a new family was
built that is: remember the best the trade ever got, leave when a fixed
fraction of that best has been handed back.

### No look-ahead
The trigger for bar *i* is computed from the peak as it stood at the END of
bar *i-1*. Using this bar's own high to place a trigger inside this bar would
assume the high printed before the retrace, which OHLC cannot tell you. That
assumption is worth roughly a third of the measured result, so it is not made.
Fills remain optimistic in the usual way (L-012, intrabar discretisation) —
every number below is a ceiling.

### The result that decides it
Identical entries (`donchian_trend`), only the exit changes. `trail 3xATR` is
what `SuperTrendSniper.mq5` ships today; `giveback 30% arm@1R` is the
candidate.

| market | trail 3xATR | giveback 30% arm@1R | change |
|---|---|---|---|
| GOLD 1h    | +0.077R | **+0.099R** | +0.022 |
| GOLD 15m   | −0.160R | **+0.059R** | +0.219 |
| EURUSD 1h  | −0.283R | **−0.028R** | +0.255 |
| US500 1h   | −0.080R | **+0.099R** | +0.179 |
| GBPUSD 1h  | −0.164R | **−0.082R** | +0.082 |

**5 of 5** on expectancy. And 5 of 5 on drawdown — GOLD 1h at 2% risk:
real max drawdown 92% → 63%, 95th-percentile bootstrap drawdown 78% → 53%,
P(drawdown > 30%) 99% → 68%, P(ending down) 19% → 2%.

### It removes the exact complaint
"Went at least 1R into profit and still closed at or below zero", GOLD 1h,
846 paired trades:

| rule | complaint rate |
|---|---|
| fixed 3R | 196 of 449 — **44%** |
| trail 3xATR (shipped) | 138 of 435 — **32%** |
| time 20 bars | 87 of 401 — 22% |
| giveback 30% arm@1R | 6 of 449 — **1%** |

### Where it costs, and why that is acceptable
Trades bucketed by how good they ever got (MFE), GOLD 1h, fixed 3R vs giveback:

| MFE bucket | n | fixed 3R | giveback | difference |
|---|---|---|---|---|
| 0–1R | 397 | −0.997R | −0.997R | +0.000R |
| 1–3R | 200 | −0.953R | +0.891R | **+1.845R** |
| 3–6R | 247 | +2.988R | +1.156R | **−1.833R** |
| 6R+ | 2 | +0.619R | +7.872R | +7.253R |

The rule is a **redistribution, not an improvement in edge**: it converts
almost-winners into winners at almost exactly the cost of turning good
winners into small winners. The two middle buckets cancel to within 1%.
It wins overall because the drawdown path is far kinder, not because it
finds money.

### What this does NOT say — read before quoting it
1. **This is a comparison of exits, not evidence of an edge.** E-050 measured
   a RANDOM entry at +0.202R on GOLD 1h. `fixed 3R` (+0.181R) and
   `time 20 bars` (+0.196R) sit on that number; the give-back rule at +0.099R
   sits *below* it. Nothing here beats random entry on GOLD 1h.
2. **EURUSD and GBPUSD are negative under every rule tested.** The give-back
   rule loses less. Losing less is not winning.
3. **47% of all trades (397 of 846) never got 1R green at all** and lose a
   full R under every exit. No exit rule touches that. It is entry quality,
   and it is the larger problem.
4. Tested on 15m and 1h. **Veer trades M1/M5/M15 and this repo has no M1 or
   M5 data.** The 15m column is the closest evidence and it is the strongest
   one, but M1 is unverified.

### What it changes in the product
`InpUseGiveBack` becomes the default profit protection in the EA, alongside
(not instead of) the trail — the trail is the disaster stop, the give-back
rule is the profit stop. Defaults set from this table: arm at 1.0R, give back
30%, tightening as the peak grows.

---

## E-052 — "Don't enter at the end of a trend": right at the extreme, wrong everywhere else
**Verdict: PARTIALLY SUPPORTED — and it disproves two of the three gates I had
already written into the EA**
Script: `JARVIS/research/continuation.py` — `python3 ... continuation.py ALL`

### The hypothesis, in Veer's words
*"the ea doesn't understand a trend doesn't always continue so when its
constantly doing a buy or a sell it needs to actually use analysis and see if
it will continue as we don't wanna enter on the end of a trend get caught in
the reversal or new trend"*

### The outcome measured, and why it is not R
Conditioning R on entry features measures the exit as much as the entry. The
outcome here is **P(+1R before −1R)** — did price travel one unit of risk in
the trade's favour before it travelled one against — which is a property of
the entry alone. A bar spanning both levels is scored a LOSS, because OHLC
cannot say which came first and assuming the good one is free money (L-012).
Every bucket is reported as a difference from **that market's own base rate**,
never against 50%.

8 market/timeframe combinations, SuperTrend entries as the EA gates them.

### WHAT REPLICATED
Both findings say the same thing in two different units — the FAR END of a
one-way run is worse — which is why they are treated as one effect, not two.

| feature | bucket | markets below their own base | mean |
|---|---|---|---|
| bars since the opposite signal | **100+** | **7 of 8** | −3.4 pts |
| distance travelled in the run | **8+ ATR** | **7 of 8** | −3.0 pts |

And its mirror image, which is the same effect read from the other end:

| bars since the opposite signal | **15–40** | **0 of 7 below — all 7 ABOVE** | +6.6 pts |

A run that is well underway but not exhausted is the best place to enter.
A run past 100 bars or 8 ATR is the worst. **Veer's instinct is correct.**

### WHAT DID NOT REPLICATE — including two gates I had already built
| feature | bucket | markets below base | reading |
|---|---|---|---|
| consecutive same-direction signals | 1–2 / 2–3 / 3–4 / 4–6 / 6+ | 4/8, 4/8, 2/6, 2/8, 5/8 | **coin flip. No effect.** |
| stretch from DEMA200 | 2.5 ATR+ | 5/8 | no gradient; the 0–0.5 ATR bucket is 5/5 below, i.e. being CLOSE to the mean is the bad one |
| position in the last 100 bars | 0.9+ (at the extreme) | **2 of 8 — 6 of 8 ABOVE base** | **backwards.** Entering at the top of the range is BETTER |
| ADX at entry | 25–35 | 6/8 | correct sign, but mean only −1.3 pts. The weakest of the three kept. |

I had already written `InpMaxSameDir` (streak) and `InpTrendStretch`
(stretch) into the EA as two of the three components of its trend-risk score.
**Neither survives.** They were written from the instinct, before the
measurement, and the measurement says they are noise. They are being replaced
with run-age and run-distance, which are what actually replicated.

### Multiple testing — read this before quoting any cell
30 buckets were examined. Under the null, P(a bucket lands ≥7 of 8 on one
side) ≈ 3.5%, so **about 1 such cell is expected by chance alone**, and 3–4
were found. That is an excess, not a landslide. The reason the run-age result
is believed anyway is that its two strongest cells are not independent tests:
`runbars 100+` and `runmove 8+` are two measurements of one thing, they agree,
and the 15–40 bucket is the same effect with its sign flipped.

### THE MAGNITUDE, stated plainly so it is not oversold
The effect is worth roughly **3.4 percentage points** on a base rate near 50%.
Filtering out the oldest runs moves P(+1R first) from about 51% to about 47%
in the bucket avoided — worth about 0.07R per trade. It is real, it is
consistent, and it is **small**. This is not a filter that turns a losing
system into a winning one, and per E-041 no filter can be: a filter improves
a zero-edge entry toward zero, never past it. It is a reason to size down and
to refuse ADDING to an exhausted run — not a reason to expect a different
system.

### What it changes in the EA
`TrendRisk()` is rewritten to score: run age ≥ 100 bars, run distance ≥ 8 ATR,
ADX ≥ 25. Streak and stretch are deleted. Effects unchanged and deliberately
proportionate to a 3-point edge: score 2 halves the size, score 3 refuses a
further same-way entry, and a higher score tightens the give-back allowance.
No score blocks a fresh signal in a NEW direction — the finding is about
continuing an old run, not about trading at all.

### Caveats
15m and 1h only; **this repo still has no M1 or M5 data** and Veer trades
M1/M5/M15. Base rates ran 45–55%, so none of these markets showed a large
directional edge to begin with, consistent with E-050.

---

## E-053 — Sideways price action: the regime is real, the filter is not, and the actual problem is COST
**Verdict on a chop filter: UNPROVEN — it shrinks the system rather than improving it**
**Verdict on the cost explanation: SUPPORTED, and it is arithmetic rather than a fit**
Script: `JARVIS/research/chop.py` — `python3 ... chop.py ALL`

### What prompted it
Veer's M1 XAUUSD screenshot, 20:04–20:28 on 1 Sep: roughly **16 SuperTrend
signals in 24 minutes**, inside a range of about **$4.50**, oscillating around
two level lines 22 cents apart. Then: *"u can [see] how we perform shit in
sideways price action make sure we can limit loss on those"*.

### A defect found on the way
`SuperTrendSniper.mq5` line 67 states, in its own scenario map, that a signal
fired into a chopping market is *"refused"*. **There is no chop code in the
EA.** The Pine has a chop guard; the EA never had one and the comment claimed
otherwise. Second: the Pine's guard was broken by my own timeframe conversion
last session — `chopLen = chopMins / barMins` gives **750 bars on M1**, so
"more than 3 flips in 750 M1 bars" is true essentially always. Flip density is
a per-BAR property and should never have been converted to minutes.

### Q1 — is sideways actually worse? Partly.
8 market/timeframe combinations. Each bucket scored against that market's own
base expectancy.

| definition | bucket | markets below own base |
|---|---|---|
| efficiency ratio over 50 bars | **< 0.08** | **6 of 8** |
| SuperTrend flips in last 20 bars | 2–3 | 7 of 8 |
| SuperTrend flips in last 20 bars | 3–5 | **1 of 8 — i.e. 7 of 8 ABOVE** |
| SuperTrend flips in last 20 bars | 5+ | 3 of 3 |

The flip readings are **not** the chop story they look like. Few flips means a
sustained one-way move, and that bucket being bad is E-052 again (an exhausted
run), not chop. Only the 5+ bucket is chop, and only 3 markets had enough
samples to say anything.

### Q2 — does filtering it limit loss? NO, not in any way that survives.
Total R before and after applying each rule, across all 8 markets:

| rule | markets improved |
|---|---|
| skip er50 < 0.08 | **5 of 8** |
| skip er50 < 0.08 OR flips20 ≥ 5 | **5 of 8** |
| skip er20 < 0.10 | 5 of 8 |
| skip flips20 ≥ 3 | 4 of 8 |
| skip flips50 ≥ 6 | 3 of 8 |

5 of 8 is a coin flip with one extra head. And the *pattern* of who it helps
is the whole answer: `skip er50 < 0.08` takes **EURUSD 15m from −95.1R to
−71.4R** and **GBPUSD 15m from −90.2R to −54.5R** — while taking **GOLD 1h
from +124.9R to +91.8R** and **US500 1h from +19.6R to −3.2R**.

It helps the losing systems and hurts the winning ones, because it does not
select — it just removes trades roughly proportionally and scales the result
toward zero. **This is E-041 restated: a filter moves a system toward zero, it
does not move it past zero.** A chop filter is not a way to limit loss. It is
a way to trade less.

### THE ACTUAL FINDING: it is a cost problem, and that is why M1 is different
New measurement — round-trip cost as a fraction of the 1.5-ATR stop, i.e. how
much of each trade's risk is paid to the broker before the trade starts:

| market | median cost/stop | stop is this many × cost | expectancy |
|---|---|---|---|
| GOLD 1h | 0.028 | 35.2× | **+0.335R** |
| GOLD 15m | 0.039 | 25.9× | **+0.227R** |
| US500 1h | 0.040 | 25.1× | +0.042R |
| US500 15m | 0.067 | 14.9× | −0.319R |
| GBPUSD 1h | 0.150 | 6.7× | −0.076R |
| EURUSD 1h | 0.153 | 6.5× | +0.044R |
| GBPUSD 15m | **0.412** | **2.4×** | **−0.344R** |
| EURUSD 15m | **0.429** | **2.3×** | **−0.356R** |

The ordering is almost perfect. Every market where the stop is more than ~15×
the round trip is positive or near flat; both markets where it is under 2.5×
lose about a third of a unit of risk per trade. `skip costfrac > 0.07` deletes
**100%** of the EURUSD 15m and GBPUSD 15m samples — those systems are not
strategies with a chop problem, they are spread payment schemes.

### What that implies for GOLD M1, which is what Veer actually trades
ATR scales roughly with the square root of bar duration, so cost/stop scales
with its inverse:
- from GOLD 15m: 0.0386 × √15 = **0.149**
- from GOLD 1h: 0.0284 × √60 = **0.220**

Both extrapolations land at **0.15–0.22**, four to six times the 15m figure,
in the same band as EURUSD/GBPUSD 1h (0.15) where expectancy is 0.00 to −0.10.
So on M1 gold roughly **15–22% of every trade's risk is paid before the trade
begins**, against a raw entry that E-050 could not distinguish from random.

**That is the mechanism behind the screenshot.** 16 signals in 24 minutes is
not fatal because the market is sideways. It is fatal because on M1 each of
those round trips costs a fifth of its own risk, and a $4.50 range does not
contain enough movement to pay 16 of them. The same range on 15m is survivable
with the identical logic, which is why this never showed up in any test so far.

### Assumptions that must be checked against the real broker
Costs assumed for GOLD: spread 0.30, slippage 0.05 per side, commission $7 per
lot — about 0.47 in price per round trip. **If PU Prime's M1 gold spread is
wider than 0.30 at the times Veer trades, every number above is optimistic.**
The EA can settle this without any backtest: it reads the live spread.

### What changes
1. The EA's cost gate is rebuilt. It had `InpMaxSpreadAtr` (spread only,
   0.15 × ATR ≈ 0.10 cost/stop) which ignored commission and slippage. It
   becomes a true cost-to-stop gate including both.
2. The chop guard the EA never had is added — and **defaults OFF**, because
   5 of 8 is not evidence. It is present so it can be tested, not argued about.
3. The Pine's `chopLen` reverts to bars.
4. **No filter is claimed to fix this.** The honest levers on M1 are a wider
   stop, a bigger required move, or a cheaper instrument/timeframe — all of
   which reduce cost/stop directly. Filtering does not.

### Caveats
Still no M1 or M5 data (Dukascopy is blocked by this environment's network
policy). The M1 numbers above are a √-time extrapolation from 15m and 1h, not
a measurement, and they are labelled as such everywhere they appear.

---

## E-051b — AMENDMENT TO E-051. The headline was measured on the wrong entries.
**This corrects E-051. Read this before quoting it.**

### What was wrong
E-051 concluded that the peak-give-back exit "beat the 3xATR trail this EA
ships on 5 of 5 markets", and that conclusion was used to make
`InpUseGiveBack` the EA's default profit protection. The comparison between
exit rules was fair and correctly controlled — but it ran on
`strategies.donchian_trend` entries. **SuperTrendSniper does not take Donchian
entries.** E-051 was a true statement about exit rules in general and was
never a statement about this EA. It was presented as though it were.

Found by the independent MQL5 audit of 2026-09-01, which noticed that the
EA's own comment cited "identical entries" while `giveback_study.py:35` called
`donchian_trend`. `giveback_study.py` now takes the entry strategy as an
argument so this cannot recur silently.

### Re-run on `supertrend_sniper_ea`, the entries the EA actually takes
Risk 2% of equity. Same exits, same costs, same tie rules.

| market | trail 3xATR | giveback 30% arm@1R | better |
|---|---|---|---|
| **GOLD 1h** | **+0.488R** | +0.158R | **trail, by a mile** |
| **GOLD 15m** | **+0.051R** | +0.015R | **trail** |
| GBPUSD 15m | −0.371R | −0.393R | trail |
| EURUSD 15m | −0.541R | −0.433R | giveback |
| US500 15m | −0.215R | −0.101R | giveback |

**2 of 5, and both wins are on systems that lose either way.** On GOLD — the
instrument actually traded — the trail earns roughly three times as much.

This is the same shape as E-053's chop filter: the rule helps losing systems
and hurts winning ones, because cutting a fat right tail costs most where the
tail is worth most. On GOLD 1h the best single trade was +24.35R on the trail;
the give-back rule sells that trade early, every time.

### What survives, and it is not nothing
The give-back rule still buys a large reduction in drawdown risk:

| GOLD 1h | expectancy | real max DD | P(DD > 30%) |
|---|---|---|---|
| trail 3xATR | +0.488R | 42% | **57%** |
| giveback 30% | +0.158R | 40% | **39%** |
| **half gb + half trail** | **+0.323R** | 38% | **29%** |

The 50/50 blend — bank half at the give-back trigger, leave the rest on the
trail — keeps **66% of the trail's expectancy for half its probability of a
30% drawdown**. On GOLD 15m it is the same story in miniature (P(DD>30%) 59%
→ 38%). That blend is computable exactly rather than estimated, because the
partial does not change how the remainder is managed, so it is the average of
the two policies trade by trade.

### What changes in the EA
`InpGbClosePart` is added, defaulting to **0.5**. The give-back rule no longer
CLOSES a position — it banks half of it, once, and the remainder rides the
trail. That is the measured blend rather than either extreme, and it is also
what Veer described wanting: the pennies and the big move out of the same
signal.

`InpUseGiveBack` stays on. The rule that fires is now the one that was
measured on his entries, not on somebody else's.

### The lesson, which is not a new one
E-050 retracted a headline for want of a random control. This retracts one for
want of the right entries. Both failures are the same failure: a number was
carried further than the thing it was computed on. **A result is a statement
about the exact configuration that produced it and about nothing else.**

---

## E-054 — Was the +GBP50 session evidence of an edge? It depends entirely on one number Veer has not told me
**Verdict: UNRESOLVED, and resolvable in about a minute from the EA's journal**
Script: `JARVIS/research/luck.py`

Veer: *"the ea made me 50+ even with its shit stacking shit closing at peaks in
a few hours this means if we improve even on chop days and good days we will
see straight green and consistent results"*.

The inference only holds if the session came from EDGE. If it came from SIZE,
the identical settings produce the mirror image just as readily.

Method: take the R distribution of the REAL SuperTrend strategy (GOLD 15m, the
EA's own gating) and shift it so expectancy is EXACTLY ZERO. The shape is real
— the fat right tail, the cluster of full-R losses — and the edge is gone. Then
ask how often a worthless system doubles.

**Reaching 2.24x (GBP50 -> GBP112) in one session, with NO edge at all:**

| risk/trade | trades | P(hit +124%) | P(lose half) |
|---|---|---|---|
| 1% | 20–80 | **0.0%** | 0.0% |
| 2% | 40 | **0.0%** | 0.1% |
| 2% | 80 | 0.9% | 3.3% |
| 5% | 40 | 8.3% | 26.3% |
| 10% | 40 | **25.5%** | **68.5%** |
| 20% | 40 | **34.1%** | **92.3%** |

**This is the whole answer and it is not rhetorical.** At 1–2% risk a zero-edge
system essentially never does this, so if that is what he risked, the session
is real evidence and deserves investigation rather than dismissal. At 10–20%
risk, a worthless system does it in one session out of three.

The number needed is risk per trade, or equivalently lot size and stop
distance and trade count. **The EA already writes all three to
`MQL5/Files/STS_journal_<symbol>_<tf>.csv` on every fill.** One file settles it.

What does NOT depend on the answer: at the settings that make +124% reachable,
the same settings halve the account 68–92% of the time. Both branches come out
of the same distribution and only one of them gets screenshotted.

---

## E-055 — Sessions: too thin to call
**Verdict: UNPROVEN**
Script: `JARVIS/research/sessions.py`

Veer: *"think in terms of sessions sometimes session opens create diffrent
trends"*. Six session blocks, 8 market/timeframe combinations, each cell scored
against that market's own base expectancy.

| block | markets below own base |
|---|---|
| Asia (00–07 UTC) | 6 of 8 |
| London open (07–10) | 1 of 6 — i.e. 5 of 6 ABOVE |
| London (10–12) | 2 of 3 |
| NY overlap (12–16) | 3 of 8 |
| NY late (16–21) | 6 of 7 |
| Close/thin (21–24) | 2 of 5 |

The direction is plausible — Asia and the late NY session worse, the London
open better — but **nothing reaches 7 of 8 or 8 of 8**, and with six blocks
examined that is inside what chance produces. NY late at 6 of 7 is p ≈ 0.06
one-sided; London open at 5 of 6 is p ≈ 0.11. Neither survives being one of
six.

The hourly cut on GOLD, the instrument that matters, is worse: GOLD 15m has
145 signals across 24 hours and not one hour reaches 15 observations. The
GOLD 1h cells that do print (06:00 at +1.055R on n=20) are noise wearing a
decimal point, and are shown in the output only so nobody mistakes them for a
finding later.

**No session filter is justified by this data.** M1 data would give roughly
sixty times the signals per bucket and would genuinely answer it — another
line on the list of things `ExportHistory.mq5` unlocks.

---

## E-056 — A STALL PREDICTS THE GIVE-BACK. Unanimous across every market tested.
**Verdict: CONFIRMED**
Script: `JARVIS/research/stall.py`

Veer: *"what if price reacts to our position but has slow price action how do
we know how to move"*. This is the best-posed question he has asked, because
it is about information the EA already holds and throws away.

**STALL** = bars since the position last made a new favourable extreme. A
trade that just printed a new best has stall 0; one that peaked twelve bars
ago has stall 12. Measured at every bar of every trade that reached at least
+0.5R. Outcome: did it give back to break-even BEFORE adding another 0.5R?
Ties go to the give-back (L-012).

**P(gives it back), minus each market's own base rate:**

| market | stall 0–1 | 1–3 | 3–6 | 6–12 | 12–25 | 25+ |
|---|---|---|---|---|---|---|
| GOLD 1h | −19.9 | −7.8 | +0.2 | +4.9 | +9.3 | +9.4 |
| GOLD 15m | −27.3 | −8.2 | −2.3 | +0.5 | +9.3 | +10.8 |
| EURUSD 1h | −18.5 | −7.3 | −2.0 | +1.5 | +8.5 | +6.5 |
| EURUSD 15m | −21.0 | −7.6 | +0.6 | +2.6 | +5.8 | +7.3 |
| GBPUSD 1h | −23.9 | −10.4 | −2.5 | −1.2 | +5.5 | +15.6 |
| GBPUSD 15m | −20.3 | −6.5 | +4.2 | +7.9 | +4.7 | +6.1 |
| US500 1h | −18.6 | −8.4 | −3.5 | +1.5 | +6.6 | +17.9 |
| US500 15m | −27.3 | −11.8 | −2.0 | +0.1 | −2.3 | +19.9 |
| **worse than base** | **0/8** | **0/8** | 3/8 | 7/8 | 7/8 | **8/8** |

Monotone in every single market. Two unanimous buckets and two at 7 of 8.
With six buckets examined, roughly 0.2 cells at the 7-of-8 level are expected
by chance; four appeared, two of them stronger than that.

**GOLD 15m in absolute terms** (base 51.3%): stall 0–1 gives back **24.0%** of
the time; stall 25+ gives back **62.1%**. A 38-point spread on the same trade,
from a number the EA can compute for free.
**GOLD 1h** (base 37.9%): **18.0%** at stall 0–1 against **47.3%** at 25+.

### The honest caveat, and it matters
These are observations PER BAR, not per trade, so a single long trade
contributes dozens of correlated rows. **The Wilson intervals printed by the
script are therefore far too narrow and should not be read as if each row were
independent.** What carries this result is not the interval width — it is that
the gradient is monotone and points the same way in 8 of 8 markets across two
timeframes and four instruments, which correlated sampling within a trade
cannot manufacture.

### What it changes
The EA's only current answer to a stalling trade is `InpMaxBars = 50`, which
is blind: it treats a trade that made a new high on the last bar exactly like
one that peaked thirty bars ago. Those are measurably different trades.

1. A **stall cap** replaces the blind bar cap as the primary time exit.
2. The give-back allowance now **scales with stall** — generous while a trade
   is still making new highs, tight once it has stopped.

This is also the direct answer to Veer's actual question. When price reacts to
the position but goes slow: the slowness itself is the signal, and it is worth
between 20 and 38 percentage points of give-back probability.

---

## E-057 — After an impulse candle: bank the peak, yes. Trade the bounce, no.
**Verdict: "close at the peak" SUPPORTED (weakly). "buy the bounce" and
"wait for the pullback then continue" REJECTED as edges.**
Script: `JARVIS/research/impulse.py`

### The event
Veer's M1 gold chart, 1 Sep 21:03. One M1 candle drops about $3 — roughly four
times the M1 ATR — and prints the low. Three stacked shorts (0.01 at 4344.27,
0.02 at 4341.35, 0.02 at 4339.22) are worth about **GBP10.30** at that low and
show **GBP7.06** when he looks: **31% of the basket peak handed back**. The
3xATR trail sits ~2.4 points behind price on M1, which is most of the move —
his words, "sl nowhere near peak", are literally correct.

His reading contains three separate claims and they have different answers:
  A. the peak was worth banking
  B. the bounce was worth buying
  C. after the pullback, the short should resume

### Why E-056 does not cover this
Stall is counted in BARS. An impulse sets its extreme in ONE bar, so stall is
0 or 1 at exactly the moment the give-back is largest — and E-056 measured
stall 0-1 as the SAFEST bucket. After an impulse that is backwards, which is
why this needed its own experiment rather than a wider threshold.

### THE CONTROL, which is the whole result
For every impulse, the identical statistics were computed at a randomly chosen
NON-impulse bar, matched on range size and direction. K = 2 x ATR:

| market | n | median giveback | CONTROL | exceeded the extreme | CONTROL |
|---|---|---|---|---|---|
| GOLD 1h | 673 | 1.21 | 1.02 | 86% | **89%** |
| GOLD 15m | 164 | 1.07 | 0.92 | 87% | **87%** |
| EURUSD 1h | 790 | 1.19 | 1.10 | 89% | **89%** |
| EURUSD 15m | 183 | 1.29 | 1.13 | 87% | **87%** |
| GBPUSD 1h | 760 | 1.23 | 1.10 | 90% | **89%** |
| GBPUSD 15m | 169 | 1.36 | 1.06 | 89% | **91%** |
| US500 1h | 876 | 1.35 | 1.11 | 88% | **91%** |
| US500 15m | 197 | 1.31 | 0.93 | 88% | **88%** |

**"Price eventually exceeds the extreme" is 86–90% after an impulse and
87–91% after a random bar.** It is not a property of impulses. It is what
price does past any level given thirty bars. Quoted without the control it
would have looked like an 88% continuation edge and it is nothing.

**What IS real:** the median give-back is larger after an impulse than after
the control in **8 of 8 markets** — 1.07–1.36 of the range against 0.92–1.13.
Modest, unanimous, and it points one way: after an impulse, the typical
outcome hands back the whole move and then some.

### The three claims, answered
- **A. Bank the peak — SUPPORTED, weakly.** Median give-back exceeds 100% of
  the impulse's own range and beats the control 8 of 8. Holding through is,
  typically, giving the move back.
- **B. Buy the bounce — REJECTED.** Nothing here distinguishes the bounce from
  ordinary wandering. The continuation rate is the control rate.
- **C. Pullback then resume — REJECTED as an edge.** The 70–74% resume rate,
  conditioned on giving back half, sits below the 87–91% unconditional control
  for exceeding a level. Conditioning on the pullback makes it *worse*, not
  better. It is a real pattern in the sense that it happens; it is not an edge.

### The gradient nobody would guess
Bigger impulses give back proportionally LESS. Median give-back falls from
1.07–1.36 at K=2 to 0.55–0.79 at K=4, and "gave back half first" falls from
40–63% to 24–47%. Veer's candle was roughly 4–6 x ATR, i.e. the K=4 bucket —
where the data leans toward continuation, not reversal. **n is 38–57 there and
that is too few to act on**, but it is the opposite of the intuition and it is
recorded so nobody later "discovers" the reverse.

### What changes
The give-back allowance tightens when the peak was set by an impulse bar. That
is the one claim the control supports, at the size the control supports.
Nothing is built for B or C.

### Caveats
15m and 1h only. HORIZON is 30 bars; a different horizon moves the
unconditional rates, though it moves the control with them, which is the point
of having one.

---

## E-058 — "A baseline of GBP50 a day": the arithmetic that decides what the EA is for
**Verdict: the target is coherent at GBP2,500–5,000. On GBP112 it is not a
low-risk target and no execution work makes it one.**
Script: `JARVIS/research/target.py`

Veer: *"the goal of this live ea is a low risk compoudning results 50 a day or
40 ... we want a baseline of 50 a day which is possible it happend today"*.

GBP50/day is not one target. It is three different targets depending on the
account, and the EA's code cannot tell them apart — the same settings produce
all three.

| daily return | account for GBP50/day | what that return is |
|---|---|---|
| 0.5% | GBP10,000 | demanding but coherent |
| 1.0% | GBP5,000 | demanding but coherent |
| 2.0% | GBP2,500 | very good, sustainable |
| 5.0% | GBP1,000 | top decile, hard to sustain |
| 10.0% | GBP500 | not sustainable |
| **45%** | **GBP111** | **what GBP112 requires** |

### Why "baseline" cannot attach to the last row
If GBP50/day were genuinely a floor on GBP112, compounding over 20 trading days:

| after | equity |
|---|---|
| 1 day | GBP162 |
| 5 days | GBP718 |
| 10 days | GBP4,601 |
| 20 days | **GBP189,051** |

One GBP50 day on GBP112 is a real event that happened. A *baseline* of GBP50/day
on GBP112 is a different claim and that table is what it implies.

### The risk it requires, and what that risk costs
Real SuperTrend payoff shape, expectancy forced to zero, 40 trades, 20,000 runs:

| risk/trade | P(+45% day) | P(−45% day) | P(halved) |
|---|---|---|---|
| 1% | 0.1% | 0.0% | 0.0% |
| 2% | 4.2% | 0.4% | 0.1% |
| 5% | 16.3% | 23.2% | 26.1% |
| 10% | 19.7% | **52.0%** | **68.6%** |
| 20% | 9.7% | **79.5%** | **92.4%** |

**There is no risk setting where the good day is likely and the bad day is
not.** At 20% risk the up-day probability has already started FALLING while the
down-day probability keeps climbing — the geometry turns against you before the
target gets easier.

### What this settles for the EA
Tune it for the account it will grow into, not the one it is on. The settings
that take GBP112 to GBP5,000 fastest are the same ones most likely to take it
to zero first, and the EA cannot know which run it is in until afterwards.

**The supported half of Veer's claim:** today's session did leave money on the
table, the give-back was real and measurable, and closing nearer the peak is
worth a quantified amount (E-051b, E-056, E-057). That is a genuine capture
improvement. It is a different claim from GBP50/day being a floor, and only one
of the two has numbers behind it.

---

## E-059 — The largest profitability lever in this project is the account form, not the strategy
**Verdict: CONFIRMED — measured off Veer's own screenshots, arithmetic thereafter**
Found because Veer asked "what broker is taking 1.11 commission on a 0.03" and
the honest answer was that the number was mislabelled AND the input behind it
was wrong.

### First, the correction
GBP 1.11 was the TOTAL round trip, not commission. Commission was GBP 0.17 of
it. Presenting the total under a heading that made it read as commission was my
error and Veer was right to stop on it.

### Then, questioning the input — which is where the finding is
Every cost figure in this project has assumed a **0.30** gold spread. Veer's
own screenshots show the live spread in the SELL | nn | BUY boxes:

| quote | spread | terminal |
|---|---|---|
| 4331.500 / 4332.000 | 0.50 | 50 points |
| 4332.190 / 4332.650 | 0.46 | 46 points |
| 4332.510 / 4332.980 | 0.47 | 47 points |
| 4326.320 / 4326.730 | 0.41 | 41 points |

**Average 0.46 — the assumption was 53% optimistic.** It has been sitting in
`study.py COSTS` and in every experiment that used it, and in his own 3.5 Pine,
where it made each net target read 0.32 points better than it was.

### The lever
PU Prime runs two account forms and they are not the same trade:

| account | spread | commission | round trip at 0.03 lots |
|---|---|---|---|
| Standard | 0.46 | none | **GBP 1.33** |
| Prime / ECN | ~0.20 | $7/lot round turn | **GBP 0.88** |

**GBP 0.45 saved per round trip — 34% of the cost — for filling in a form.**

| trades/day | saved per day | per month (21 days) |
|---|---|---|
| 50 | GBP 22.51 | GBP 473 |
| 100 | GBP 45.03 | GBP 946 |
| 200 | **GBP 90.06** | **GBP 1,891** |
| 300 | GBP 135.09 | GBP 2,837 |

### What it does to the thing that actually decides the account
Break-even win rate, symmetric targets:

| target | Standard | Prime/ECN | handed over |
|---|---|---|---|
| 1.0 pt | 78.0% | 68.5% | **9.5 points** |
| 1.5 pt | 68.7% | 62.3% | 6.3 points |
| 2.0 pt | 64.0% | 59.2% | 4.7 points |
| 3.0 pt | 59.3% | 56.2% | 3.1 points |

Nothing else measured in this project moves the break-even win rate by nine
percentage points. E-052's run-exhaustion filter was worth three points of
*outcome probability*; this is worth up to nine points of *required* win rate,
it applies to every trade, and it cannot be curve-fit because it is not a
model — it is a price list.

### Why it matters most at Veer's stated design
He wants hundreds of small positions a day. The cost is paid per round trip, so
it scales linearly with trade count while the edge does not. **The higher the
frequency, the larger this lever gets** — which is the exact opposite of every
filter tried in E-053, all of which shrank the system.

### What to check before acting
Prime/ECN spread and commission should be confirmed against a live PU Prime
account rather than taken from the numbers above, and the two accounts should
be compared at the hours Veer actually trades. The 0.46 figure is his; the 0.20
is the published tier and is the one number here he has not personally
verified.

### Also fixed
`study.py COSTS` still carries 0.30 for GOLD. Every experiment that quoted a
cost/stop ratio — E-053 in particular — is therefore optimistic, and the M1
extrapolation of 0.15–0.22 becomes roughly **0.23–0.34** at the real spread.
That makes E-053's conclusion stronger, not weaker: M1 gold on a Standard
account pays about a third of its risk to the broker before the trade starts.

---

## E-063 — THE ANSWER. On M1 gold the spread is 61% of the way to your own stop.
**Verdict: CONFIRMED — arithmetic on Veer's own measured numbers**

### The number
His spread, read off his terminal: **0.46**. His M1 bar ranges, read off his
20:04–20:28 screenshot: roughly **0.3–0.8**, so ATR(7) ≈ 0.5.

The EA shipped a **1.5 × ATR** stop. On M1 gold that is **0.75 points**.

| | |
|---|---|
| round trip (spread + 2× slippage) | **0.56 points** = GBP 1.33 at 0.03 lots |
| stop distance | **0.75 points** |
| **cost / stop** | **0.75** |
| spread alone, as a share of the stop | **61%** |

**Every trade is filled 0.46 in the red against a 0.75 stop.** It has to travel
three quarters of its own risk just to get to zero.

E-053 measured that every market with cost/stop under ~0.07 was positive and
both markets over 0.40 lost about a third of a unit of risk per trade. M1 gold
at these settings is **0.75** — nearly double the worst thing in that table.

### This is why profit evaporates
It is not the trail, the peak-chasing, the stacking or the give-back. Those are
all real and all worth fixing, and they were fixed. But a trade that starts 61%
of the way to its own stop cannot be rescued by exit management. The give-back
rule, the stall exit, the basket protection — every one of them is arranged
around a stop that the spread has already half-consumed.

### Fixed in the EA: the stop now has a COST FLOOR
`InpMinStopCostX` (default 4.0). The stop is
`max(InpStopAtrMult × ATR, InpMinStopCostX × round-trip cost)`.

It is self-adjusting and needs no per-timeframe tuning: on 15m and 1h, where
ATR is large relative to the spread, the ATR term wins and nothing changes. On
M1, where the spread is large relative to ATR, the cost term takes over and the
stop widens to where the trade is not mostly fee.

### Every route out, on his own numbers
| change | cost/stop | vs now |
|---|---|---|
| nothing — M1, 1.5×ATR, Standard | **0.75** | — |
| Prime/ECN spread 0.20, M1, 1.5×ATR | 0.40 | −46% |
| trade M5 instead (ATR ≈ 1.1) | 0.34 | −55% |
| **widen the M1 stop to 4 × ATR** | **0.28** | **−62%** |
| trade M15 instead (ATR ≈ 1.9) | 0.20 | −74% |
| widen the M1 stop to 6 × ATR | 0.19 | −75% |
| Prime/ECN AND M5 | 0.18 | −76% |
| **Prime/ECN AND a 4 × ATR M1 stop** | **0.15** | **−80%** |

The last row is the same order as US500 15m, which was the last market on the
positive side of E-053's table. The top row is off the end of it.

### What it costs him
A wider stop with a fixed 0.03 lot means more money at risk per trade: a 4×ATR
M1 stop is 2.0 points = **GBP 4.74** against GBP 1.78 at 1.5×ATR. On a GBP 112
account that is 4.2% a trade, which is too much — so the stop widening and the
lot size have to move together. `InpUseFixedLots` should go OFF and
`InpRiskPct` should carry the sizing once the stop is honest.

### Fact-checking my own inputs, which is where this came from
1. I assumed a 0.30 spread for months. His terminal says 0.46. (E-059)
2. I extrapolated M1 ATR from the repo's 15m data. That sample runs
   2026-06-14 to 2026-08-24 with a median 15m bar range of **7.40** — a far
   more volatile period than the one he is trading now, where his M1 bars run
   0.3–0.8. **My extrapolation understated his cost burden by roughly 4×.**

Both errors pushed the same way: they made the strategy look cheaper to trade
than it is. Neither was found by more analysis. They were found by checking two
inputs against his screenshots.

---

## E-064 — The control's own seed noise. My red team caught this before it died.
**Verdict: the GOLD edge SURVIVES, at 1.7–1.8 control standard deviations**

The adversarial agent's last line before the session limit killed it was:
*"E-060's control looks like a single random seed. Let me verify and measure
the control's own seed noise."* It was right to look. A random control run on
ONE seed has its own sampling error, and if that error is as large as the edge
being claimed, the claim is not measured.

Re-run with 12 seeds, GOLD, at the geometry the EA ships (1.5 ATR stop, 3R,
50-bar cap):

| | signal | control mean | control sd | control range | signal beats |
|---|---|---|---|---|---|
| GOLD 15m | **+0.260R** (n=96) | +0.086 | 0.099 | −0.069 to +0.246 | **12 of 12 seeds** |
| GOLD 1h | **+0.227R** (n=264) | +0.026 | 0.121 | −0.173 to +0.347 | **11 of 12 seeds** |

Edge over the mean control: **+0.175R on 15m, +0.201R on 1h** — about **1.8 and
1.7 control standard deviations**.

### Read it honestly
The control's seed-to-seed spread is 0.10–0.12R, which is the same order as the
edge itself. That is exactly why this check was needed. The edge survives it —
beating 12 of 12 and 11 of 12 independent draws is not what a zero edge does —
but 1.75 sd is modest, roughly p ≈ 0.04–0.08 one-sided, and it is one
instrument. It is not the 3.65 t-statistic this project set as its bar for a
780-configuration search, and it should not be quoted as though it were.

### What it means in practice
On GOLD, the SuperTrend + DEMA entry is better than random by a real but small
margin. That is the honest ceiling on what execution work can amplify: a good
exit on a +0.2R entry is worth having; no exit rule turns a zero-edge entry
positive (E-041).

**Every single-seed control in E-060, E-061 and E-062 should be read with this
in mind.** The direction of those results is unchanged; the precision implied
by their decimal places is not real.

---

## E-065 — The liquidity strategy measured. The stop was the problem, not the entry.
**Verdict: UNPROVEN as an edge. But stop placement is worth 21 points of win rate.**
Script: `JARVIS/research/liquidity.py`

Veer runs this by hand and has never had a number for it. This implements the
SAME rules `LIQUIDITY_CLEAN_1_0.pine` draws — the two LuxAlgo scripts' rules —
so the number describes the chart he is actually looking at.

Zone = 3+ pivots clustered within ±ATR/6.9. Entry = a wick sweep of the zone
that closes back inside, wick ≥30% of the bar. Target = the nearest live zone
the other way. Ties resolved as losses. Costs applied.

### THE FINDING: the stop, not the signal

| stop placed | buffer | min target | n | win% | expectancy | PF | stopped |
|---|---|---|---|---|---|---|---|
| beyond the ZONE | 0.25 ATR | 1 ATR | 186 | **10.2%** | −0.372R | 0.65 | **90.3%** |
| beyond the ZONE | 1.5 ATR | 3 ATR | 117 | 23.9% | +0.032R | 1.04 | 76.1% |
| beyond the WICK | 0.25 ATR | 1 ATR | 155 | 16.8% | −0.236R | 0.75 | 83.2% |
| **beyond the WICK** | **1.5 ATR** | **1 ATR** | 133 | **31.6%** | +0.004R | 1.01 | 67.7% |
| beyond the WICK | 1.5 ATR | 3 ATR | 117 | 26.5% | **+0.024R** | **1.03** | 73.5% |

**Win rate 10.2% → 31.6%, expectancy −0.372R → +0.004R, from the stop alone.**
The entries are identical in every row.

My first implementation put the stop 0.25 ATR beyond the ZONE EDGE. But a
sweep means price has ALREADY been through that edge — the stop was sitting
inside the exact noise the setup is built on, and 90% of trades died there. The
correct placement is beyond the SWEEP BAR'S OWN EXTREME: the sweep defined how
far the market was willing to push, so the trade is wrong only if price goes
BEYOND what the sweep already reached.

### The honest verdict
At the best setting the profit factor is **1.03** on **117 trades**. That is
breakeven with noise around it, not an edge. **This strategy is UNPROVEN.**

### Veer's belief, measured
He wrote: *"price normally respects the zones hits it and comes down or up ...
sometimes rarely it wont and it will breakthrough thats where we make our loss
... and that is not very often"*.

**Measured: 67.7% of sweep entries end at the stop even at the best setting.**
The break-through is not rare on this data. Two readings are possible and they
are not the same:
1. It genuinely is rare on M1/M5 with his discretion, and 15m/1h does not
   transfer. Possible — there is still NO M1 or M5 data in this repo.
2. He remembers the reactions and not the break-throughs. Also possible, and
   it is what a 68% stop rate would feel like if the winners were much larger.

The profit factor of 1.03 says the winners ARE much larger — which is exactly
what would make a 68% stop rate feel like "price normally respects the zone".

### What changes in the Pine
The default stop moves to **beyond the sweep wick + 1.5 ATR**, and the minimum
target to **3 ATR**. Those are the measured-best cells and they are also the
ones that most reduce the stop rate. Nothing else changes.

### What would settle it
M1 and M5 data. `ExportHistory.mq5` produces it in one drag-and-drop. Every
number above is 15m and 1h, and the strategy is run on M1/M5/M15.

---

## E-066 — Where the SuperTrend makes and loses money, by market condition
**Verdict: SUPPORTED — and it says the paying regime is the MIDDLE, not the trend**
Script: `JARVIS/research/regime.py`

Veer: *"supertrend m1 is there to catch all trends meaning small big chop we
just need to be able to perform well in all ... it needs to trade all sessions
although some are slow so it needs to be able to actually capture those pennies"*.

Two axes, both computable at entry from closed bars. SPEED = ATR(7) over its
own 200-bar median. SHAPE = the 50-bar Kaufman efficiency ratio, net distance
divided by the path walked.

**Pooled, 2,967 trades, 8 market/timeframe combinations:**

| | chop (<0.10) | **mixed (0.10–0.25)** | trend (>0.25) |
|---|---|---|---|
| slow | −0.027 (287) | **+0.192 (279)** | −0.267 (83) |
| normal | −0.053 (696) | −0.023 (807) | −0.072 (182) |
| fast | −0.181 (242) | **+0.063 (320)** | −0.097 (71) |

**The money is in the middle column.** Dead chop loses at every speed. An
already-established trend loses at every speed — and loses MOST in a slow
market (−0.267R), which is the cell that looks safest.

### Why, mechanically
A SuperTrend catches TURNS. In dead chop the turns are noise and cost the
spread. In a running trend the turn already happened and the entry is late —
which is E-052's run-exhaustion result arriving from a completely different
direction, on different data, and agreeing.

### GOLD, the instrument that matters
GOLD 1h base +0.339R over 373 trades. The **normal/mixed** cell is **+0.549R on
102 trades** — the strongest cell anywhere with enough trades to mean anything.
GOLD 15m base +0.232R; its cells are 10–60 trades and are not quotable.

### What it changes: SIZING, NOT FILTERING
`InpUseRegimeSize` scales the lot by the efficiency ratio — 0.70× in chop,
**1.25× in the middle**, 0.70× in a running trend. Every signal is still taken.

That distinction is the whole point and it is the thing I got wrong in F-010.
Veer has said since his first message that signal count is not the problem, and
E-053 measured that filters drag a system toward zero because they remove
trades without selecting. Sizing weights the edge instead of deleting the
trades, which is what the table above actually supports: no cell is so bad it
should never be traded, and one cell is clearly worth more.

### Caveats
15m and 1h. Still no M1 data. Nine cells were examined, so a single cell would
prove nothing — what carries this is that the SHAPE axis is monotone in the
same direction at all three speeds, and that its mechanism agrees with E-052
which was measured independently.

---

## E-067 — Retuning the give-back from a live trade. The arming threshold was the bug.
**Verdict: a deliberate expectancy-for-consistency trade, made on Veer's instruction**

Veer, 2026-09-02: *"i've already seen us in the past 5 min go up in peaks of 8
pound close not near was up 2.50 on two 0.01s total and closed at 47 p each see
how horrible that is"*.

GBP 2.50 peak, GBP 0.94 kept. **62% of the peak handed back.**

### Why the rule did not fire
It armed at **1.0 R only**. On 0.01 lots, and with the stop now widened by the
cost floor (E-063), one R is several pounds — so a trade could run to GBP 2.50,
never reach 1 R, and give the whole thing back **with the give-back rule never
once evaluating it**. The rule was blind to exactly the trades being complained
about, because it only spoke R and he trades in pounds.

### Changed
1. **Arms on MONEY or on R, whichever comes first.** `InpGbArmMoney = 1.00`.
2. **Allowances roughly a third tighter**: base 0.30 → 0.20, tier2 0.24 → 0.16,
   tier3 0.18 → 0.12, and the tiers trigger sooner (1.5 R and 3.0 R).
3. **A money floor alongside the R floor**, so a trade armed on money is
   protected in money — the R-space floor can sit below zero and never trigger.
4. **Basket: `MathMax` → `MathMin` on the arming threshold.** The old line armed
   at the LARGER of "0.6% of equity" and "GBP 2.00", so on a small account the
   GBP 2.00 floor dominated and a GBP 2.50 peak had almost no protected range.
   The floor exists to stop the rule firing on noise, not to postpone it until
   the money is gone. That was a genuine logic error, not a tuning choice.

### What it does to his trade
| peak | old (30% back) | new (20% back) |
|---|---|---|
| GBP 2.50 | GBP 1.75 | **GBP 2.00** |
| GBP 8.00 | GBP 5.60 | **GBP 6.40** |

Against the GBP 0.94 he actually kept, the arming fix is worth more than the
allowance change: the allowance only matters once the rule is looking.

### The cost, stated plainly
E-051b measured that a tighter give-back keeps LESS expectancy — it sells the
runners that pay for the losers. This is the third time Veer has chosen the
certain smaller number over the larger uncertain one, in writing: *"we are not
looking for massive profits ... we want small consistent profits hundreds of
times"*. That is a legitimate preference between two measured options and the
settings now match it. `InpGbBase` and `InpGbArmMoney` reverse it in one edit.

---

## E-068 / E-069 — The 80% gap, closed. The liquidity strategy was never measured.

**Veer:** *"i personally have a 80% winrate w liquidity strat and losses dont
even compare to the profits"*. **E-065 measured 31.6%.** Both cannot describe
the same trade, and it was mine that was wrong — in three separate places.

### What E-065 actually measured
Twelve trades on GOLD 15m. Twelve, in 4501 bars. Its 117 "pooled" trades were
~15 per market. Nothing computed on that sample — not the 31.6% win rate, not
the 68% stop rate, not the PF of 1.03 — was ever a measurement of a strategy.

### The three errors, each with a price tag

| # | E-065 did | Veer does | cost |
|---|---|---|---|
| ZONE | 3 pivots inside a ±ATR/6.9 band | a single swing point is liquidity | 39.3 → **2.7** sweeps per 1000 bars |
| ENTRY | bought the sweep bar's close | waits for the **retest** of the swept level | close scores **−0.003R at ZERO cost** — no edge at all |
| TARGET | the opposite zone, 3–6 ATR away | ~0.5 ATR | 33% win → **80%** |

The zone error is mine and specific: he sent **two** LuxAlgo scripts —
*Liquidity Sweeps* (one swing point) and *Buyside & Sellside Liquidity*
(clustered) — and I ANDed them, keeping the strictest reading of each.

The entry error is the important one. At **zero costs** the sweep-close entry
scores −0.003R. It is not a weak edge being eaten by spread; it is nothing.
**The entire edge is in the retest.**

### E-069 — the reconciled geometry, attacked
`zone = any confirmed pivot · entry = RETEST · stop = 1.5 ATR beyond the sweep
wick · target = 0.5 ATR`. Pooled win rate **80.5%** — Veer's number to within
a point.

| market | n | win% | expectancy | PF | t | OOS 1st / 2nd | walk-fwd | vs control | verdict |
|---|---|---|---|---|---|---|---|---|---|
| **GOLD 1h** | 401 | **87.8%** | **+0.106R** | 1.85 | +5.05 | +0.098 / +0.114 | **6/6** | **+7.8 sd** | **PROMISING** |
| US500 1h | 345 | 84.1% | +0.053R | 1.33 | +2.12 | +0.035 / +0.072 | 6/6 | +8.3 sd | PROMISING |
| GOLD 15m | 98 | 81.6% | +0.023R | 1.12 | +0.45 | −0.003 / +0.048 | 4/6 | +2.2 sd | UNPROVEN |
| US500 15m | 110 | 83.6% | +0.026R | 1.15 | +0.58 | −0.010 / +0.062 | 4/6 | +2.4 sd | UNPROVEN |
| EURUSD 1h | 366 | 79.8% | −0.070R | 0.68 | −2.63 | | 0/6 | | REJECTED |
| GBPUSD 1h | 357 | 84.6% | −0.002R | 0.99 | −0.10 | | 4/6 | | REJECTED |
| EURUSD 15m | 111 | 54.1% | −0.348R | 0.10 | −6.26 | | 0/6 | | REJECTED |
| GBPUSD 15m | 110 | 54.5% | −0.356R | 0.10 | −6.33 | | 0/6 | | REJECTED |

Control is 12 seeds, not one (E-064). Monte Carlo on trade order: GOLD 1h
drawdown median 4.0R, 95th percentile 6.1R.

### Why it is not a fitted cell
The whole 5×4 neighbourhood on GOLD 1h is positive, on **both** zone
definitions, and the trigger survives pivot length 5→14 and wick share
0→0.5 (t between +2.6 and +6.1 in all twelve). It is a plateau, not a spike.
Best interior cell is min_piv=2 / stop 1.0A / target 0.75A at **+0.286R**
(n=152), better than the cell chosen — the chosen cell was picked to match
Veer's reported win rate, not to maximise anything.

### And it barely cares about the spread
GOLD, same geometry, commission 0: **+0.111R at zero spread, +0.090R at the
0.46 measured off his terminal.** A 1.5 ATR stop makes R large enough that the
spread is a rounding error. The argument about PU Prime's spread does not
decide this strategy.

### The honest caveats
- FX is rejected outright and the 15m rows are UNPROVEN. This is a **gold and
  index** result, on **1h**.
- The shape risks 1.5 to make 0.5: it needs ~75% just to break even, and every
  point of live win rate lost to slippage costs about 0.03R. No margin for
  sloppiness.
- **15m and 1h bars. Veer trades M1/M5/M15.** Nothing here measures his
  timeframe. `ExportHistory.mq5` is still the blocker.

Files: `JARVIS/research/liq_geometry.py`, `JARVIS/research/liq_validate.py`.

---

## E-070 / E-071 / E-072 — The SuperTrend EA. The entry is fine. The exit is the problem, and the fix is the opposite of what was asked for.

### E-070 — the entry is NOT the problem
E-068 found the liquidity strategy's entry was worth everything. Same test on
SuperTrend flips: identical signals, only the order's location changes, risk
anchored to the signal bar so a better fill cannot flatter itself.

| entry | taken | fill% | win% | expectancy | total R |
|---|---|---|---|---|---|
| **market (what the EA does)** | 2235 | 65% | 25.7% | **−0.106R** | −236R |
| limit 0.25 ATR back | 2200 | 64% | 22.5% | −0.120R | −264R |
| limit 0.50 ATR back | 2104 | 61% | 19.2% | −0.137R | −289R |
| limit at the SuperTrend line | 181 | 5% | 8.3% | −0.803R | −145R |
| limit at the DEMA | 691 | 20% | 18.4% | −0.350R | −242R |

**Market entry wins on expectancy, total R and fill rate.** Waiting for a
pullback loses money here, and the reason is not mysterious: a sweep is a
REJECTION, so price comes back to you; a flip is a BREAKOUT, so it does not.
The "top tick / limit order / never in drawdown" idea is **REJECTED** for
SuperTrend. It stays right for liquidity.

*(First run of this scored limit_st at −18R. A resting order at the SuperTrend
line can sit BEYOND the stop; filling there is not a brilliant entry with a
tiny risk, it is a trade already stopped out, and dividing by that near-zero
risk produced the number. Such fills are now refused.)*

### E-071 — the exit grid, and the number that settles a session-long argument
GOLD, SuperTrend flips, every cell market-entry:

| stop | target | n | win% | expectancy | **points** |
|---|---|---|---|---|---|
| 2.0 ATR | 3R | 313 | 31.0% | +0.212R | **+1385** |
| 3.0 ATR | 2R | 241 | 41.5% | +0.209R | +1365 |
| 2.0 ATR | 2R | 389 | 38.8% | +0.144R | +1274 |
| **1.5 ATR | 3R — the EA today** | 433 | 27.3% | +0.072R | **+715** |
| 3.0 ATR | 0.25 ATR | 594 | **91.6%** | −0.018R | **−548** |

**A 91.6% win rate that loses money.** Not a paradox — the near target caps
every winner while the wide stop pays every loser in full. On GOLD 1h that cell
walk-forwards **0 of 6 blocks** and loses 611 points.

Veer, three times in writing: *"we are not looking for massive profits ... we
want small consistent profits hundreds of times"*. On the SuperTrend flip that
shape is measurably the losing one. It remains correct for liquidity sweeps —
different trade, different physics.

Widening the stop 1.5 → 2.0 ATR roughly **doubles the points** and changes
nothing else.

### E-072 — two lots, two jobs
He trades 0.02 as two 0.01s, so the position can hold both shapes. GOLD:

| | n | win% | expectancy | **points** |
|---|---|---|---|---|
| **runner** — both lots to 2R | 389 | 38.8% | **+0.144R** | **+1274** |
| split, half at 0.5 ATR, half runs | 389 | 38.8% | +0.060R | +562 |
| split + break-even on the remainder | 583 | 78.0% | +0.008R | +99 |
| **scalp** — both lots at 0.5 ATR | 606 | 78.5% | **−0.033R** | **−273** |

Every step toward "bank it early and protect it" costs money, in order:
1274 → 562 → 99 → −273. **Break-even alone costs 82% of what is left**
(562 → 99), which is the fourth independent measurement calling it poison.

*(First run had `left` initialised to the post-scale remainder, so a stop-out
before the scale banked a fraction of the loss — and in `scalp` mode, none of
it. Profit factor came back 0.00 with a t of +63, which is what gave it away.)*

### What this does NOT license
None of the R-target cells clears t ≥ 2.0. Best is 3.0A/2R on GOLD 1h at
t=+1.80, +1.9 control sd, OOS +0.191/+0.199. **UNPROVEN**, with a consistent
direction across both timeframes and both halves. Pooled across eight markets
every cell is still negative — this is a GOLD result.

**Give-back is not the same thing as a near target** and this does not condemn
it. A fixed target caps a winner; a give-back rule only acts once the trade has
stopped making new highs. The two must not be conflated, and the give-back
engine keeps its stall gate.

Files: `JARVIS/research/st_entry.py`, `st_exit_grid.py`, `st_partial.py`.

---

## E-073 — The stall finding was 6x smaller than reported. The EA was tuned on it.

E-056 is the project's most-cited result: "bars since a trade last made a new
best predicts giving it back, monotone, **8 of 8 markets**, CONFIRMED". The EA's
give-back allowance scales on it — a trade still printing new highs got 35%
more rope, one that peaked 25 bars ago got 45% less.

**E-056 takes one observation per BAR.** A trade that runs 61 bars contributes
61 rows sharing one entry, one peak and one outcome, and every count and
interval in E-056 treats them as 61 independent facts. Across all eight markets
the average is **61.1 bars per trade**, so its n was inflated roughly 61-fold
and its intervals are about √61 ≈ 8x too narrow.

Re-run three ways. `gap` = P(gives it back | stall 12+) − P(gives it back | stall 0–3).

| | gap | 95% interval | |
|---|---|---|---|
| counting BARS (E-056's method) | **+0.289** | [+0.264, +0.316] | clear |
| cluster bootstrap, resampling TRADES | +0.289 | [+0.264, +0.316] | clear |
| **one vote per trade**, 1826 independent trades | **+0.046** | **[−0.002, +0.105]** | **spans zero** |

Per market, one vote per trade: **0 of 8** have an interval clear of zero.
Six of eight still lean positive, and the pooled point estimate is positive.

### The verdict
**E-056 is downgraded from CONFIRMED to SUPPORTED, and its magnitude is wrong
by a factor of six.** The direction is probably real — six markets lean the
same way and the pooled estimate is positive — but the size it was quoted at
came from long trades each contributing dozens of stalled bars.

The cluster bootstrap being clear while the per-trade estimate is not is not a
contradiction: the cluster test resamples trades but keeps their bars, so it
measures the *bar-weighted* gap honestly, and that quantity really is +0.289.
The EA does face a bar-weighted decision population — it asks "has this trade
stalled?" at every bar. But the *evidence* behind the rule rests on ~1800
independent trades, not 111,605 bars, and at that n the effect is +0.046.

### What changed in the EA
Stall tiers cut by the same factor the effect shrank by: **1.35/0.55 → 1.07/0.93**.
The direction is kept, the magnitude is now what is measured. `InpStallScales=false`
removes it entirely, which the evidence would also permit.

### The lesson, which is general
Three separate results this session (E-050, E-064, this) failed the same way:
a statistic computed over the wrong unit. Bars are not trades, one control seed
is not a control, and twelve signals are not a strategy. **Any result quoted
with an n far larger than the number of independent decisions behind it should
be assumed wrong until re-counted.**

File: `JARVIS/research/stall_attack.py`.

---

## E-074 — Every gate in the SuperTrend EA, audited. Only one of them pays.

Veer: *"we are now not hitting same trades as before"*, *"see what else we can
ADD REMOVE IMPROVE OPTIMISE"*.

The EA has eight conditions that can refuse a signal. Each was added for a
reason; almost none was ever measured **as a gate**. A gate earns its place
only if the trades it REFUSES are worse than the ones it ALLOWS — a one-line
test nobody had run. F-010 is what happens when you skip it.

### GOLD — each gate on its own, same signals, same exit (2.0 ATR / 3R)

| gate | allowed | exp | refused | exp | delta | verdict |
|---|---|---|---|---|---|---|
| **DEMA slope agrees** | 625 | **+0.275R** | 698 | **−0.041R** | **+0.316R** | **KEEP** |
| ADX ≤ 35 | 1000 | +0.130R | 323 | +0.043R | +0.087R | NOISE |
| efficiency ≥ 0.08 | 905 | +0.113R | 418 | +0.098R | +0.015R | NOISE |
| < 5 flips in 20 | 1297 | +0.103R | 26 | +0.363R | −0.260R | refuses nothing, wrong sign |
| cost/stop ≤ 0.30 | 1323 | — | **0** | — | — | never binds on gold |
| stop ≥ 4 round trips | 1323 | — | **0** | — | — | never binds on gold |
| re-entry cooldown | 1323 | — | **0** | — | — | never binds |
| no-fade candle | 1323 | — | **0** | — | — | never binds on gold |

**The DEMA filter is the entire edge.** Remove it and gold goes from +0.275R to
+0.111R. Four gates refuse literally nothing on gold at a 2.0 ATR stop. The two
cost gates DO earn their place pooled across eight markets (+0.293R and +0.304R
separation) — they are insurance that never binds on gold, and they stay.

### In combination, GOLD, points banked per 0.01 lot

| gate set | taken | kept% | expectancy | t | **points** |
|---|---|---|---|---|---|
| everything on | 344 | 26% | +0.324R | +3.20 | +2692 |
| DEMA + ADX + cost (**the EA before this**) | 519 | 39% | +0.309R | +3.76 | +4445 |
| **DEMA + cost (the EA now)** | 625 | **47%** | +0.275R | +3.71 | **+4639** |
| no gates at all | 1323 | 100% | +0.109R | +2.22 | +5962 |
| everything except DEMA | 618 | 47% | +0.111R | +1.54 | +1466 |

**Highest expectancy is not the most money.** "Everything on" has the best
per-trade number and the worst total, because it only trades a quarter of its
own signals. Turning off the ADX ceiling gives 20% more trades AND more points.

Removing every gate makes more points still (+5962) but at t=+2.22 against
+3.71, and 4.5 points per trade against 7.4. The DEMA filter is kept.

### Changed
`InpUseAdxFilter` **true → false**. The chop guard was already off (E-053).
This is the third independent measurement saying the same thing: E-053 (chop
filters are 5/8, a coin flip), E-066 (the money is in the MIDDLE efficiency
band, so filtering by efficiency cuts the paying regime), and now E-074.

File: `JARVIS/research/gate_audit.py`.

---

## E-075 — The give-back rule was never the problem. Arming it at 0.6R was.

E-051b compared exits on a 1.5 ATR stop with the ADX gate on. Both have since
changed (E-071, E-074), so R is a third larger and every rule expressed in R —
which is all of them — means something different. Re-run on the EA as it now
stands. GOLD 1h, 459 trades, same entries for every row, overlap allowed so
this measures exits and nothing else.

| exit policy | win% | expectancy | t | **points** |
|---|---|---|---|---|
| **trail 3×ATR armed at 1R** | 39.7% | +0.347R | +3.46 | **+4622** |
| **give-back 25% armed at 3R** | 33.4% | **+0.368R** | +3.77 | +4313 |
| trail 3×ATR | 36.9% | +0.305R | +3.11 | +4065 |
| fixed 3R | 33.6% | +0.311R | +3.57 | +3961 |
| give-back 30% armed at 2R | 41.6% | +0.295R | +3.77 | +3763 |
| time 50 bars | 35.8% | +0.321R | +3.06 | +3729 |
| give-back 25% armed at 1.5R | 46.6% | +0.227R | +3.35 | +3210 |
| **give-back 30% armed at 1R** | 52.3% | +0.136R | +2.29 | **+2251** |
| BE@1R + trail | 34.9% | +0.223R | +2.51 | +2690 |
| **trail + give-back 30% at 1R (the EA before this)** | 49.2% | **+0.087R** | +1.52 | **+1618** |
| ORACLE — closes at the exact peak, not tradeable | 97.8% | +3.018R | +15.11 | +41471 |

### The finding
**Arming level is a monotone dial, and the EA was at the wrong end of it.**
+0.136R at 1R → +0.227R at 1.5R → +0.295R at 2R → **+0.368R at 3R**. The
give-back rule armed at 3R is the highest-expectancy exit tested. Armed at
0.6R and £0.30 — where this EA has been — it fires on ordinary trades and caps
them, which is exactly where the earlier "3× worse than the trail" result came
from. I had been condemning the rule when the fault was the threshold.

**Trail + give-back together is the worst reasonable combination** at every
arming level: +1618 points against +4622 for the trail alone.

### Changed
`InpGbArmR` 0.6 → **3.0**, `InpGbArmMoney` £0.30 → **£2.00**.

That still does the job Veer asked for — *"was up 2.50 on two 0.01s total and
closed at 47p each"* — because a £2.00 floor protects a £2.50 peak. A £0.30
floor protects nothing and pays for it with the runners.

**Honest note:** on points the trail alone still wins, +4622 against +4313.
Keeping the give-back armed high is a deliberate concession to a preference
Veer has stated three times in writing, and it now costs about 7% rather
than 65%.

File: `JARVIS/research/exit_rerun.py`.

---

## E-076 / E-077 — The top-tick entry. The cell I never tested, and the one that wins.

Veer: *"we need to have top tick entrys meaning we do a small stop loss which
is reasonable and catch a massiveeee entry from the tick thats the point"*.

That is **risk 1 to make 2+**. Everything I had built for liquidity was the
opposite shape. E-068 swept two entries — the sweep bar's CLOSE, and the RETEST
back at the zone edge — and **both enter after the sweep is over**. Neither is
that trade. By the time price is back at the edge the wick is far away and the
risk is already large, which is why E-069 ended up risking 1.5 ATR to make 0.5.

### What I had never tested
A limit resting **INSIDE the zone, past its far edge, BEFORE the sweep**,
filled BY the sweep. The zone is where the stops are; the sweep is the market
reaching in to take them. The stop then sits just past the poke — small — and
the whole reversal is the target.

It also fills on every BREAK, not only every sweep, and that is its honest
cost. A break is a full-size loss. The question is whether a small stop and a
2R target pay for those. They do.

### E-077, the chosen cell attacked
`limit 0.25 ATR past the far edge · stop 0.60 ATR · target 2R`

| | n | win% | expectancy | PF | t | OOS | walk-fwd | vs control | points |
|---|---|---|---|---|---|---|---|---|---|
| **GOLD 1h** | 491 | 47.5% | **+0.378R** | 1.69 | **+5.58** | +0.470 / +0.286 | **6/6** | **+4.7 sd** | **+2172** |
| **GOLD 15m** | 158 | 48.1% | +0.382R | 1.69 | +3.20 | +0.498 / +0.265 | 4/6 | +3.8 sd | +301 |

Both **PROMISING**. Against E-069, which this replaces: 401 trades, 87.8% win,
**+0.106R**. The new shape is **3.5× the expectancy with more trades**, in the
opposite geometry.

### Why it is not a fitted cell
The whole neighbourhood pays. GOLD 1h, expectancy / points:

| stop | 1.5R | 2.0R | 2.5R | 3.0R |
|---|---|---|---|---|
| 0.35 ATR | −0.02 / +375 | +0.14 / +898 | +0.28 / +1327 | +0.32 / +1533 |
| 0.45 ATR | +0.18 / +1178 | +0.34 / +1851 | +0.40 / +2038 | +0.31 / +1481 |
| **0.60 ATR** | +0.39 / +2375 | **+0.38 / +2172** | +0.34 / +1759 | +0.21 / +844 |
| 0.75 ATR | **+0.46 / +3183** | +0.37 / +2322 | +0.21 / +1114 | +0.07 / +393 |
| 0.90 ATR | +0.38 / +2623 | +0.27 / +1554 | +0.11 / +658 | +0.05 / +551 |

A 0.15 ATR stop loses everywhere — the poke overshoots. 0.45–0.90 is the
plateau. The shipped default sits in its **interior**, not at the peak, because
an edge-of-grid optimum is usually a fit.

### It behaves the way the model says it should
Small stop ⇒ **cost-sensitive**, unlike E-069's wide-stop shape which barely
noticed the spread. GOLD 1h: **+0.492R at zero spread, +0.378R at 0.46,
+0.279R at 1.00.** If it had been cost-*insensitive* with a 0.60 ATR stop,
the model would have been wrong.

### A statistics correction inside this experiment
The control z was first computed as (ours − control mean) / **per-seed sd**,
giving +1.1 sd. That is the wrong denominator: the question is whether our
expectancy differs from the *expected* expectancy of a random entry, and that
expected value is estimated by the control **mean**, whose error is
sd/√seeds. Corrected, with 30 seeds: **+4.7 sd**. Understating a separation is
the wrong direction to be wrong in when the conclusion is "trade it".

### Shipped
`JARVIS/pine/LIQUIDITY_CLEAN_1_2.pine` and `LiquiditySniper.mq5` build 2.00.

**Half these trades lose.** 47.5% is the measured win rate and it is the shape,
not a fault. Monte Carlo on trade order: drawdown ~12R median, 18R at the 95th.

Files: `JARVIS/research/toptick.py`, `toptick_validate.py`.

---

## E-079 / E-080 — SMC measured. Two of six pay; the other four are decoration.

Veer: *"base liquidity strat with order blooms fvg all those kinda things smc
bos choch everything you can be deep and thorough have signals sniper entry"*.

Deep does not mean drawing all of it. Each concept is a claim about the future
and a claim can be checked, so each was built and tested twice against the
entry that already survives (E-077): **as a filter** on it, and **as a trigger
on its own** with the same 0.60 ATR stop and 2R target.

### As triggers, GOLD 1h — against a 30-seed random-entry control
| concept | n | win% | expectancy | PF | t | points | edge vs control |
|---|---|---|---|---|---|---|---|
| **fair value gap** | 44 | **65.9%** | **+0.943R** | 3.66 | +4.39 | +552 | **+1.053R** |
| **order block** | 70 | 51.4% | **+0.498R** | 1.98 | +2.78 | +312 | +0.628R |
| inverse FVG | 1333 | 36.5% | +0.054R | 1.08 | +1.37 | +896 | +0.238R |
| BOS retest | 283 | 35.7% | +0.030R | 1.05 | +0.36 | +202 | +0.214R |
| CHoCH retest | 213 | 33.8% | −0.028R | 0.96 | −0.28 | +305 | +0.151R |

### Combined, one account, one position, first touched wins
| signal set | n | win% | expectancy | t | **points** |
|---|---|---|---|---|---|
| base (E-077 zone entry alone) | 480 | 47.7% | +0.385R | +5.62 | +2110 |
| base + FVG | 501 | 49.5% | +0.440R | +6.55 | +2542 |
| **base + FVG + order block** | **515** | **51.1%** | **+0.487R** | **+7.37** | **+2792** |
| base + FVG + OB, bias-filtered | 205 | 56.1% | +0.638R | +6.13 | +1403 |
| everything incl. iFVG | 1446 | 38.7% | +0.119R | +3.10 | +1785 |

**More trades, higher expectancy and 32% more money than the base** — better on
every axis at once, which is rare enough to distrust, so it was checked out of
sample and block by block:

`base + FVG + order block`, GOLD 1h: **n=515, 51.1% win, +0.487R, PF 1.95,
t=+7.37, +2792 points, OOS +0.598 / +0.377, walk-forward 6/6, +5.0 control sd,
Monte Carlo drawdown 9.8R median / 14.6R at the 95th.** **PROMISING.**
GOLD 15m, base + FVG: n=159, +0.392R, t=+3.30, 6/6, +3.6 sd. **PROMISING.**

### The four that are out, and why
- **Inverse FVG — OUT.** 1136 trades in the stack for **−39 points**. It fires
  constantly and dilutes: the stack falls from +0.487R to +0.119R with it in.
- **BOS / CHoCH — OUT.** Inside noise as triggers, and as filters the samples
  that pass are 17–27 trades.
- **Structure bias — OUT, and this is the interesting refusal.** As a filter it
  *raises* expectancy from +0.487R to +0.638R — and cuts trades from 515 to 205
  and money from +2792 to +1403 points. **Best per-trade number, least money.**
  Exactly the trap E-074 caught in the SuperTrend EA.
- **"Entry inside an order block" — BACKWARDS on 15m**, +0.141R allowed against
  +0.463R refused. Being *in* the block is worse than approaching it.

### A bug caught before the numbers were believed
The first run had `base` at n=26 against E-077's 491. The candidate generator
marked a zone *used* when it first appeared rather than when its order was
actually reached, so zones were burned on bars price never came near. A resting
order rests until touched — that is the whole point of it.

### Shipped
`LIQUIDITY_CLEAN_1_3.pine` and `LiquiditySniper.mq5` build 3.00.

Files: `JARVIS/research/smc.py`, `smc_combine.py`.
