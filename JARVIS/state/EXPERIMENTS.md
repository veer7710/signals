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
