# SESSION STATE — 2026-09-03

Branch: `claude/trading-ea-pine-scripts-xv4m8q` (the JARVIS history was merged
onto it from `claude/jarvis-ai-operating-system-2xaclm`; that branch is now
behind and should not be worked on).

## What this session settled

Five things, all measured, four of them negative or narrowing — which is what
progress looks like here.

### E-092 / P92 — the Pine and the EA were not the same strategy
The assumption the whole project rests on, unchecked in 180 commits.

- **SuperTrend indicator parity is EXACT.** 0 of 3944 bars disagree on GOLD 15m,
  0 of 13115 on 1h. The EA's 400-bar recompute really does equal
  `ta.supertrend`. A whole suspected defect class is closed.
- **The Pine printed 346 BUY/SELL labels where the EA took 165** (1010 vs 466 on
  1h). Every EA entry was on the chart, so the Pine is a strict superset, and
  **52-54% of the chart's labels are trades the EA refuses.** All of it the DEMA
  gate, which the Pine never had. Veer hand-trades this chart.
- **The live-account defect:** the Pine auto-switched the DEMA to 60 on M1 while
  the EA was hard-wired to 200. On the one timeframe the EA is *for*, the two ran
  different filters. DEMA(60) and DEMA(200) pick the same trade only 74% of the
  time.
- The EA seeded its EMA from a single close; Pine seeds from an SMA. 2.0% of
  bars disagreed on the slope SIGN. Fixed → 0.1%.
- **I nearly overclaimed.** Under the shipped exit the refused flips looked
  clearly bad. Across six exit stacks they are negative 6/6 on 15m but
  **positive 4/6 on 1h**, and no t clears 2.2. E-074's "only the DEMA gate has
  ever paid for itself" was measured under one exit and is downgraded. So the
  Pine SHOWS the gate rather than adopting it.

Shipped: **EA 2.22**, **Pine 3.8** (refused flips dimmed, reusing the existing
mid-range dim and the same two plotshapes — no new chart objects). Residual
disagreement 3 of 1332 flips.

### E-093 / Block F — the consistency rule is the funded problem
`prop_sim.py` could not answer this: it scores closed trades, so it never sees
the floating loss every firm measures the daily limit against — the way funded
accounts actually die. `funded.py` simulates bar by bar.

Isolating the rule over 2000 attempts per firm: **FundingPips 92.1% → 29.7%,
E8 performance 92.7% → 23.1%.** Bigger than daily loss and max drawdown
combined. FTMO, FundedNext, E8 Classic and The5ers have no such rule.
**The E8 trap: challenge 90.8%, funded stage 23.1% — you pass and then cannot
get paid.**

- **Sizing cannot fix it** (it is a ratio; cutting risk made it worse).
- **A daily profit lock alone cannot** (50-58% against a 40% cap).
- **Frequency dissolves it.** 2/day 24.0%, 10/day 99.9%. **Veer has been right
  to demand frequency, and this is the hardest number yet attached to it.**
- But frequency costs R, and at cost/stop 0.14 **100/day COLLAPSES to 16.5%** —
  the size per trade gets too small to reach target in time. **Target 10-50/day.**

Shipped: **LiquiditySniper 3.10** — seven firm presets, one input block, and
three real fixes: the floor is the FIRM's floor not the equity peak (3.05 was
harsher than any real rule), state persists across restarts (a restart used to
hand the EA a fresh daily allowance the firm had not given it), and every limit
is enforced at 80% of its value. Card: `JARVIS/ea/FUNDED_CARD.md`.

### E-094 — sideways detection: six detectors, none earns its place
In-sample, refusing each one's worst quintile "worked" 5 of 6 on 15m. That is
cherry-picking. **The tell: the detectors do not agree with themselves across
markets** — `contain`'s worst quintile is Q1 on 15m (POSITIVE, +30 points) and
Q5 on 1h. Walk-forward, nothing survives on both timeframes. `alternate` —
Veer's own "up down candles" taken literally — threw away 1201 points on 1h.

Same answer E-053 gave: the regime is real, the filter is not. Nothing gains the
power to refuse a signal; containment joins the spacing ratio in the status line
as a reading that gates nothing.

### E-095 — peak capture: there is nothing to capture on small moves
**I corrected my own measurement mid-experiment.** The first run modelled only
the 3.0 ATR trail and said the 1-2R bucket keeps 2-4%. With a 2.0 ATR risk a
3.0 ATR trail cannot protect anything under 1.5R. The EA also has a give-back
stop from 1.0R; with the full stack the bucket keeps **80%**. I nearly reported
a defect that does not exist.

The sub-1R trades are **not underprotected winners** — they are losses that
briefly showed a small profit (53 of them banked −829.5 points, mean MFE
0.10-0.74R). There is no peak there to take.

But the full stack exposed the real cost: **arming at 0.6R, 1.0R, 1.5R or 2.0R
eliminates every trade that reaches 4R, on both timeframes.** E-090 in a
different hat. 4.0R is the only value that beats OFF on both. **The default is
NOT changed** — 1.0 is Veer's written instruction and a preference is not a
defect — but the price is now documented beside the input.

### E-096 — the £40 squeeze, resolved: the account must be larger
I threw away my own first answer. Bootstrapping the strategy's own trades said
£40 at 5.3% risk had a 0.7% ruin chance and a **median 11× outcome**. Nonsense:
the bootstrap is fed the backtest's +0.181R mean, so it can only confirm it.

The measured edge is **+0.181R ± 0.101 (n=112); the 95% interval [−0.017,
+0.380] does not exclude zero.** So: what edge does a given account NEED?

**At E-089's M1 edge (+0.041R), £40 has a 33.2% chance of halving. £100 has
1.0%.** This is not about the strategy — £0.787/point at 0.01 lots is a broker
floor and 2.7 points of stop is a spread floor, so £2.12 of risk is fixed.
**Only the denominator can move. £100 is the threshold, and the £40 → £100 leg
is the only phase of the plan with meaningful ruin risk.**

## The blocker, re-verified this session, not taken on trust
**There is still no M1 or M5 data in `data/`.** I probed stooq, dukascopy,
binance and yahoo: the gateway answers **403 to CONNECT** on all four
(`curl "$HTTPS_PROXY/__agentproxy/status"` shows the rejections). It genuinely
cannot be fetched from inside a session. `JARVIS/ea/tools/ExportHistory.mq5`
fixes it in one drag-and-drop from Veer's terminal.

**Four of this session's five findings name M1 as the thing that would settle
them.** If `GOLD_M1.json` arrives, re-run E-069, E-077, E-080, E-083, E-089,
E-091 and then E-093's frequency row and E-096's edge row.
