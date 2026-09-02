# Start here

Read CLAUDE.md, then SESSION_STATE.md, then this.

## Do these in order

1. **Ask Veer for two files** and do not build anything cost-related until you
   have them: `STS_journal_XAUUSD_PERIOD_M1.csv` (the EA now logs spread, stop
   and cost/stop on every entry) and the `GOLD_M1.json` output of
   `JARVIS/ea/tools/ExportHistory.mq5`. The spread question has been argued
   from charts twice and been wrong twice. Measure it.

2. **Re-test E-056 with ONE observation per trade.** `JARVIS/research/stall.py`
   currently emits one row per BAR, so rows inside a trade are correlated and
   the 8-of-8 unanimity may be an artifact of that. This is the project's
   strongest claim and it has not survived its own strongest attack. If it
   fails, the stall exit in the EA must be reconsidered.

3. **Relaunch the three agents that died on the session limit** (briefs are in
   this conversation's history and in JARVIS/titan/): move-size prediction
   (can a 0.1-point flip be told from a 20-point one AT the flip — this is the
   highest-value open question), EA chart vision (clusters, real
   break-of-structure reversals, session state, level quality), and the red
   team on E-063 / half-banking / stall.

4. **Only then** touch the Pines or the EA again.

## What Veer has said repeatedly and I have repeatedly got wrong
- Signal COUNT is not the problem. Do not add entry filters. E-053 measured
  that they only shrink the system, and F-010 is what happened when I ignored
  that.
- He trades M1 gold only. H1 is context, never acted on (D-010).
- His charts must stay clean: his own XAUUSD_CLEAN_3.5 header is the spec —
  DEMA, BUY/SELL, live crosses, numbers in the status line, nothing else.
- Short replies. He has said so explicitly.
