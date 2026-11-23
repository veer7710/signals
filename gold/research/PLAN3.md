# PLAN3 — pre-registered, written BEFORE running (2026-11-23)

## Why this test exists
Corrected break-even + tight trail is the first exit rule to land near zero
(-0.012 pt/trade, his spread). But it is UNSTABLE across walk-forward halves:

| config | half A (2024-01..2025-05) | half B (2025-05..2026-11) | all |
|---|---|---|---|
| nothing | -0.322 | -0.302 | -0.312 |
| BE 0.10 + trail 0.25 from +0.5 | -0.172 | **+0.152** | -0.012 |

Spread is held at 0.320 in both halves, so the sign flip is NOT a cost artifact.
The obvious candidate mechanism: **half B has far higher ATR.** Owner's live ATR
right now is 2.824 against a 2024-2026 median of 1.18. If the rule's profitability
is a function of ATR/spread, then half B is not "a lucky half", it is "the regime
he is actually trading in".

## HYPOTHESIS (stated before seeing the answer)
Net points per trade for BE+trail is monotonically increasing in ATR, and crosses
zero somewhere in the range ATR 1.5 - 2.5 at a 0.320 spread.

## PRE-REGISTERED MEASURES
1. Legs bucketed by entry ATR into fixed edges [0,0.75,1.0,1.25,1.5,2.0,2.5,3.5,99].
   Report N, net pt/trade, t, and GBP/day for `nothing` and for BE+trail in each.
2. Same table computed on half A and half B SEPARATELY. The ATR explanation only
   survives if the per-bucket numbers AGREE across halves. If bucket "ATR>2.5"
   is positive in B but negative in A, it is time, not volatility, and the
   hypothesis is REJECTED.
3. Regression of per-trade net on ATR/spread ratio; report slope, t, and the
   implied zero-crossing.

## ACCEPTANCE (fixed now, not after)
- ATR explanation ACCEPTED only if: slope t > 4, AND the sign of every bucket
  agrees between half A and half B, AND the top ATR bucket is positive in BOTH
  halves with t > 2 in each.
- If accepted, the actionable consequence is a VOLATILITY CONDITION. That is a
  signal filter, which the standing rules say I must STOP AND ASK about. I will
  bring the number, not apply it.
- If rejected, BE+trail is a 2025-26 artifact and gets reported as such.

## KNOWN WEAKNESS, declared now
BE 0.10 + trail 0.25-from-+0.5 was chosen AFTER looking at ~50 configurations in
this session. It is a candidate, not a validated edge. The ATR test below is the
first thing about it that is pre-registered. Treat the -0.012 headline as
in-sample-selected until it survives this.
