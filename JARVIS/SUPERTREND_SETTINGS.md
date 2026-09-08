# SuperTrendSniper — every setting, and the measurement behind it

Only settings with a measured basis are listed. Anything not here is left at its
shipped default because there is no evidence to move it, and moving a default
without evidence is how the 89.8% win rate got into ZoneSniper.

---

## READ THIS BEFORE THE TABLE

You told me you took a live loss and want to make it back. The honest sequence
that produced the last one is on record and it is worth saying once: the account
went £50 → £140 on riskier stacked setups, then gave it all back to a margin
call. Size chosen to recover a loss is the mechanism, not bad luck. The margin
guard below now refuses that size — please don't route around it.

**And the state of the evidence, plainly: E-188 found no positive expectancy on
recent data for any entry, stop, target or partial structure I have tested,
including this one.** What IS established is that the entry marks leg starts
1.4–2.2× better than chance (E-184) and that the execution defects that were
losing money on top of that are now fixed. Those are different claims and I am
not going to blur them for you.

---

## THE SETTINGS

| input | set to | why, and what measured it |
|---|---|---|
| `InpDemoOnly` | **true** until it compiles and runs a session cleanly | it has never been compiled. Flip it only after a clean demo day |
| `InpMaxTF` | `PERIOD_M30` | M1–M30 allowed. AutoTune picks the gate preset from the chart |
| `InpAutoTune` | **true** | E-178. Sets the gates from the chart's timeframe. On M1 it prints a warning that the preset is inherited from M15 — that warning is accurate |
| `InpGiveBack` | **0.60** | E-177. Trail measured from the PEAK, not from price. MAE 1.824 → 0.803 ATR and win rate 44.6% → 50.7%, same return per unit of drawdown. This is the fix for "it didn't close at peaks" |
| `InpStopAtrMult` | **2.0** | E-177: best on the unseen half. 1.0 has a better t (2.63 vs 2.49) and a 26% win rate, which is unusable on a consistency rule |
| `InpUseTwoPole` | **false** | E-180. All three reads look excellent in-sample (VETO +0.490, t 2.84) and every one refuses the BETTER trades in the second half. It is a fit. The code is there if you want to watch it |
| `InpMaxMarginPct` | **35.0** | E-181. This is the margin-call fix. At 1:100 leverage one 0.01 lot is 57% of a £60 account's free margin |
| `InpMaxTotalLots` | **set it** — 0.01 per £250 of balance | a hard ceiling in lots that no sizing rule can argue around. 0 = off, and off is what got you margin called |
| `InpRiskPct` | 0.50 | mostly decorative below ~£350: E-081 says 0.01 lots is the floor, so a 2-ATR M1 stop risks £3.43 whatever you type here |
| `InpMaxDDPct` | **6.0** | below any prop firm's limit, so the EA stops before the firm does |
| `InpMaxTradesDay` | **20** | E-175: the raw signal flips 147.9×/day on M1. The gates refuse most of it; this is the backstop |
| `InpFlattenOnBreach` | **true** | a guard that refuses entries but leaves the losing position open is not a guard |
| `InpJournal` | **true** | writes asked-price vs filled-price per trade. This is the only way the cost assumption behind every number here gets replaced by a fact |

---

## ACCOUNT SIZE — E-181, and it is arithmetic

**£250 minimum. £172 is the floor. £60 cannot trade M1 gold.**

0.01 lots is £0.787/point and cannot go smaller, so a 2-ATR M1 stop risks
**£3.43 whatever the risk percentage says**:

| balance | one M1 trade | worst measured losing run (12) |
|---|---|---|
| £60 | 5.7% | £41 = **68% of the account** |
| £150 | 2.3% | 27% |
| £250 | 1.4% | **16%** |

A 12-loss run at a 38% win rate is ordinary, not unlucky.

---

## WHAT TO WATCH ON DAY ONE

1. **The Experts tab, first line.** AutoTune prints which preset it chose. If it
   says `REFUSING TO START`, the next line says exactly why.
2. **The profit box, top right.** Today's points and money, today's trades, the
   open position, then one "since" line. Every EA registers all four magics, so
   one screenshot shows everything running.
3. **`MQL5/Files/JARVIS_exec_SuperTrendSniper_XAUUSD.csv`** — asked vs got, per
   fill. Send it to me. `read_exec.py` turns it into your real spread and
   slippage, which replaces the biggest assumption in all of this.
