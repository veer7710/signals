# EA inbox — drop files here

JARVIS has never seen your EA. The repo contained no `.mq5` and no Pine
scripts. Put them in this folder and a new session will find them.

## What to upload

| File | Why it is needed |
|---|---|
| `YourEA.mq5` (source, not `.ex5`) | `.ex5` is compiled binary and unreadable |
| any `.mqh` include files | the EA will not make sense without them |
| liquidity Pine script (`.pine`/`.txt`) | to reverse-engineer and repaint-check |
| the second Pine script | same |
| MT5 backtest report (HTML) | shows how it behaved and on what settings |
| a screenshot of your broker's gold symbol spec | contract size, spread, swap, commission |

## Also write down (a file here is fine)
- Which prop firm(s), and account size(s)
- Their daily loss limit, max drawdown, profit target, min trading days
- Which symbol and timeframe the EA is meant to run on

## Why this matters
Costs and rules change every verdict. A strategy that looks profitable at
0.30 spread can be a loser at 0.60. A 16-trade losing streak that is
survivable on a personal account breaches a prop firm's daily loss limit
and ends the account. Nothing can be judged without these numbers.
