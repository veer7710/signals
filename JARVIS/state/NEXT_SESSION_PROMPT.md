# NEXT SESSION — start here

Read `CLAUDE.md`, then `JARVIS/state/SESSION_STATE.md`, then E-165 in
`EXPERIMENTS.md`, then the last two entries in `FAILURE_LOG.md`.

## The situation, stated plainly

**There is no validated strategy in this repository.** Two fill bugs, found on
the same day, removed all four signals:

- **E-151** — the exit trail filled at prices no order could rest at. Killed
  break+retest and both order-block entries.
- **E-165** — the ENTRY booked the level on bars that had already opened past
  it, on 75% of setups. Killed the sweep, which was the only one left.
  Corrected: −0.0103 a trade on M1 (t −1.85); on the subset the EA can actually
  execute, −0.0030 (t −0.37).

The null is the thing to hold onto: **the old code made +0.0226 a trade at t = 5
on a driftless random walk.** Every impressive number this repo produced came
from that.

## Do these, in order

1. **RUN THE NULL FIRST, ALWAYS.** `engine.entry_fill` and `engine.trail_level`
   are now the only fill models and both have regression tests. Before any new
   idea gets a control, a walk-forward or a parameter sweep, put it on a
   driftless random walk. If it makes money there, stop.

2. **Re-measure what is left, honestly.** Every result from E-134 to E-164 used
   the broken entry and is withdrawn. `combined.candidates()` is fixed at the
   source, so re-running is now the honest thing rather than a rebuild. Expect
   most of it to come back flat. That is fine — flat and known beats positive
   and false.

3. **Do not restart from the sweep.** It has now failed twice under correction.
   If liquidity sweeps are to be revisited, it needs a different entry
   mechanism, because the wick that defines the setup is precisely what makes
   the level unfillable.

4. **SuperTrend (E-158) is unaffected** — it does not use this entry. It is
   still not funded-account material (it fails 3 of 7 firms on consistency, best
   day 42.8–78.4% of profit), but it is the only thing here that has not been
   disproven. That is where to look next.

5. **Nothing goes on a live or funded account.** `InpDemoOnly = true` in
   `SweepSniper.mq5` and it must stay true. The EA now prints the disproof on
   startup.

## The one measurement that could change any of this

A demo run logging **requested entry price against actual fill price, per
trade**. If real fills come back at the level on setups where price has already
left it, the correction is wrong. Nothing short of measured fills should put
money on this.

## Standing rules earned today

- **Run the null before anything else.** A t-statistic of 14 on a simple rule is
  a symptom, not a triumph.
- **A fill correction is a signal to re-audit the whole trade** — entry, stop,
  exit, cost — not a repair to one line.
- **When the EA and the backtest disagree, the disagreement IS the finding.**
  They disagreed about 75% of all trades for months and nothing compared them.
- **An out-of-sample test whose winner was chosen on the out-of-sample half is
  not one.** A rule that wins on 25 unseen trades has won nothing; minimum 100.
- **A parameter monotone to the edge of its tested range is a leak.**
