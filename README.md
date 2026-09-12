# signals

Gold/index strategy research, three MT5 EAs, and their TradingView twins.

- **`docs/FINDINGS.md`** — what was measured, with the nulls attached. Read
  this before running anything.
- **`docs/INSTALL.md`** — how to install and what the settings mean.
- `mq5/` — four Expert Advisors. Start with **ApexEngine**.
- `pine/` — the matching Pine scripts, one per EA.
- `research/` — the backtest engine and every script that produced the
  numbers in FINDINGS.md. All re-runnable.

Headline results, in one paragraph: no entry marker tested (SuperTrend
flips, liquidity sweeps, FVGs, order blocks, opening-range breaks,
mean-reversion fades) produced a directional edge distinguishable from
noise once sample drift and spread were accounted for — every 95% CI
straddles zero. One result *is* significant: replacing the old give-back
exit, which armed at zero profit and pinned the average winner at $5.06,
is worth **+$4.54/trade (t=3.44)** on 498 paired entries. A second pass then tested combinations rather than isolated markers and
found two that work: **HTF bias + LTF pullback** and **Asian-range break**.
Combined as `ApexEngine`, walk-forward tuned on the first half of the data
and reported on the second, they return **+$4.90/trade PF 1.37 (1h)** and
**+$6.97/trade PF 2.00 (15m)** out-of-sample — positive on both timeframes
and both halves, at t=1.38-1.73, so consistent but not yet significant.
Sizing is Monte-Carlo optimised: **0.20% risk per trade gives an 80% pass
rate** on a standard +8%/6% challenge, and P(pass) falls monotonically as
risk rises. The old scanner and web backtester are still here
(`scanner.py`, `backtest.py`, `index.html`) and untouched.
