# NEXT SESSION — start here

Read `CLAUDE.md`, then `JARVIS/state/SESSION_STATE.md` (2026-09-06), then this.

## Where things stand

E-151 found that every give-back trail in the repo was filling at prices no
order could rest at. Corrected, **only the liquidity SWEEP makes money**; the
break+retest and both order-block entries are negative and are now OFF by
default in both the Pine and the EA. The sweep survived hard: +0.0713/trade on
M1 (n=4045, t=14.3), 65 se above a control that itself loses, positive in 6 of 6
cells off XAUUSD. The 25% give-back exit was re-tested four ways and stays.
23 live-safety defects in the two EAs are fixed (`FAILURE_LOG.md`).

## Do these, in order

1. **Read any agent findings not yet actioned.** An adversarial review of the
   sweep and a code review of the Pine + research diff were running when the
   session ended. Their conclusions may not be in `EXPERIMENTS.md` yet — check
   `git log` against what the files say.

2. **The blocking item, and it cannot be done from here: a demo forward test.**
   Everything in this repo is 2018 gold, backtested. E-155 measured that the M1
   sweep is positive at 0.05 points of slippage and NEGATIVE at 0.10. Nothing
   available in this environment can say which one is real. Until Veer runs
   `SweepSniper.mq5` on a demo account and the log reports actual stop-fill
   slippage, no live or funded claim can be upgraded past SUPPORTED.
   The EA prints what is needed; it refuses to start on a live account
   (`InpDemoOnly = true`) and that default must not be changed for him.

3. **Read PU Prime's actual symbol properties off the terminal.** The EAs now
   read `SYMBOL_TRADE_FREEZE_LEVEL`, `SYMBOL_TRADE_STOPS_LEVEL`,
   `SYMBOL_VOLUME_MIN/STEP`, `SYMBOL_TRADE_TICK_SIZE` and `OrderCalcMargin`
   instead of assuming them, but which of them bite is only visible on a live
   chart. Have Veer paste the OnInit block from the Experts log.

4. **Neither EA has been compiled.** `check_mq5.py` says so itself on every run.
   MetaEditor F7 is the only thing that can confirm the ~23 patches build.

5. **The prop-firm day boundary is unverified** (F16). `TimeCurrent()` is broker
   server time, not UTC, and a mismatch can put two of the EA's 2.5% days inside
   one of the firm's 5% days. This needs the firm's rule book, not a guess.

## Standing rules that were nearly broken this session

- **A parameter monotone to the edge of the range you tested is a leak until
  proven otherwise.** Extend the range. If it keeps running, look at the fill,
  not the parameter. This is how E-151 was found.
- **A trade call whose return value is discarded is a bug, without exception.**
- **An out-of-sample test whose winner was chosen using the out-of-sample half
  is not an out-of-sample test.** E-150 made exactly that error.
- **A rule that wins on 25 unseen trades has not won anything.** Minimum 100.

## What NOT to do

- Do not re-enable break+retest or the order block as ENTRIES without new
  evidence. Eight exit variants were tested on them; all eight failed.
- Do not change the 25% give-back. It has 56 firm/risk/clock cells behind it.
- Do not remove the order block DRAWING. Veer asked for it, and it is real
  structure — it just does not pay on its own.
- Do not tell Veer the system is ready for funded money. It has never been
  forward tested and he must hear that plainly every time he asks.
