# SESSION STATE — 2026-09-06

Branch: `claude/trading-ea-pine-scripts-xv4m8q`.

## What this session found, in one line

**A measurement bug was making three of the four shipped signals look
profitable. They are not. The sweep is the strategy, and it survived the
correction intact.**

## E-151 — the bug

Every give-back trail in this repo computed its stop level from a bar's own
high, then let the next bar fill at it — **even when that level was on the far
side of the bar's close.** For a long that is a sell-stop above the market: an
order that cannot exist. The backtest was paying itself the bar's own
favourable extreme.

The same three lines were copy-pasted into **twelve** files. The tell was that
"best give-back" ran to the tightest value in every range tested, on every
signal, on both clocks — *a parameter monotone to the edge of what you tried is
a leak, not an optimum.*

Fixed: one function, `trail_level()` / `trail_apply()` in `engine.py`, used by
every call site, with a regression test including a grid property check that no
returned stop is ever on the wrong side of the close.

## What the correction cost, and what survived

| | before | corrected |
|---|---|---|
| M1 sweep | +0.1200/trade | **+0.0713** (n=4045, t=14.3) |
| M1 break+retest | +0.0483 | **−0.0095** |
| M1 order block detection | +0.0280 | **−0.0089** |
| M1 order block return | +0.0163 | **−0.0319** |

The sweep is 65 standard errors above a time-shifted control **which itself
loses 193 points** — so the money is in the level, not in the trail. It is
positive in 6 of 6 instrument/timeframe cells off XAUUSD; the order block is
negative in 6 of 6.

**The three extras are OFF by default in both the Pine and the EA.** They are
not noise — they beat a random entry — they just do not clear the spread. The
order blocks still DRAW, because that is what Veer asked for and the structure
is real.

## The exit: asked four ways, unchanged

E-153/154/155/156/157. No exit rescues the three dead signals (8 cells, 8
rejects). The sweep looked like it wanted a 3-ATR trail (+27% points on M1
unseen, +47% on M5) — until it was priced: **max drawdown £18 → £60 at 0.01
lots, which is the whole live account,** and E-081 says the lot size cannot go
lower. Then the prop rules decided it: **the 25% give-back wins 28 of 28 cells
against ATR trails and 28 more against wider give-backs.** Its R distribution
has half the standard deviation, and every prop rule is a variance test.

**Nothing about the exit changed. It was already right.**

## The funded-account answer

Simulated at 0.25% risk a trade, sweep only:
- FTMO, FundedNext, E8 Classic, The5ers — **~100%**
- FundingPips — **86%**
- Alpha Capital — 48% on M1, **96.5% on M5**
- E8 performance — 5.8% on M1, **72.2% on M5**

**M5 is the funded clock.** M1 makes more money and fails the consistency-rule
firms. 0.50% risk is worse at every single firm.

**SuperTrend is not funded material** (E-158): it fails 3 of 7 firms on
consistency because its best day is 42.8%–78.4% of its profit. It belongs on
Veer's own live account, where nobody enforces that.

## The EAs: 23 live-safety defects, none of them syntax

Both files passed the static checker and always did. The pattern was one thing
twenty-three times: **a trade call whose result is discarded, followed by a log
line announcing success.** The worst four: a pending-order ticket that three
ordinary events silently zeroed, after which the EA armed a second order on top
of a live one; guards that declined new trades but never closed the position
that breached them; a max drawdown measured from attach equity instead of peak;
and the give-back close — the EA's *only* exit — sent unchecked. All fixed, all
in `FAILURE_LOG.md`.

## THE ONE THING THAT HAS NOT CHANGED

**Nothing here has ever been forward tested.** Not one trade. Every number in
this file is a backtest on 2018 gold that has never met a real spread, a real
requote, a real fill or a real Sunday gap. The funded pass rates are the best
available answer to Veer's question and they are not a promise.

**The single blocking item for live or funded money is a demo run that measures
real stop-fill slippage.** E-155 shows M1 dies at 0.10 points of slippage and
survives 0.05. Which world we are in is not knowable from here.
