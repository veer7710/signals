# signals

Gold/index strategy research, three MT5 EAs, and their TradingView twins.

- **`docs/FINDINGS.md`** — what was measured, with the nulls attached. Read
  this before running anything.
- **`docs/INSTALL.md`** — how to install and what the settings mean.
- `mq5/` — three Expert Advisors.
- `pine/` — the matching Pine scripts, one per EA.
- `research/` — the backtest engine and every script that produced the
  numbers in FINDINGS.md. All re-runnable.

Headline results, in one paragraph: no entry marker tested (SuperTrend
flips, liquidity sweeps, FVGs, order blocks, opening-range breaks,
mean-reversion fades) produced a directional edge distinguishable from
noise once sample drift and spread were accounted for — every 95% CI
straddles zero. One result *is* significant: replacing the old give-back
exit, which armed at zero profit and pinned the average winner at $5.06,
is worth **+$4.54/trade (t=3.44)** on 498 paired entries. The old scanner
and web backtester are still here (`scanner.py`, `backtest.py`,
`index.html`) and untouched.
