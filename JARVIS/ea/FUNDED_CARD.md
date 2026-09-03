# P90 — WHICH PRESET, FOR WHICH FIRM, AND WHY

One page. Set two inputs on `LiquiditySniper.mq5` build 3.10 and everything
else derives.

```
InpFirm         = the firm you bought
InpAccountSize  = 0   (reads the account balance) or the challenge size
```

---

## THE ONE DECISION THAT MATTERS MORE THAN ANY SETTING

**Buy from a firm with no consistency rule.**

E-093 held the strategy, the sizing and every other rule fixed and switched only
the best-day rule on, over 2000 simulated attempts per cell:

| firm | pass rate without it | with it | what the rule costs |
|---|---|---|---|
| FTMO 2-step | 98.2% | 98.2% | **no such rule** |
| FundedNext Stellar | 96.0% | 96.0% | **no such rule** |
| E8 Classic (challenge) | 90.8% | 90.8% | **no such rule** |
| The5ers High Stakes | 98.2% | 98.2% | **no such rule** |
| Alpha Capital Alpha One | 78.7% | 60.2% | −18.4 points |
| FundingPips 2 Step Pro | 92.1% | 29.7% | **−62.4 points** |
| E8 performance (funded) | 92.7% | 23.1% | **−69.7 points** |

**The consistency rule is a bigger obstacle than the daily loss limit and the
max drawdown put together.** No EA setting recovers 60 points of pass rate.
Choosing the firm does, and it is free.

**The E8 trap:** E8 Classic has no consistency rule and passes 90.8%. E8
performance — the funded stage, where the money is — enforces 40% and passes
23.1%. **You pass the challenge and then cannot get paid.** Read the payout
stage's rules, not the challenge's.

---

## WHAT DOES NOT WORK, MEASURED

**Sizing down.** best-day ÷ total-profit is a ratio, so it is scale-free. On one
path at E8 performance: 0.25% risk gave a 52.0% ratio, 0.50% gave 78.4%, 1.00%
gave 90.8%. Cutting risk made it **worse**, because a smaller account takes
longer and banks its profit in fewer, relatively larger days.

**A daily profit lock alone.** Sweeping it from 2.0% down to 0.5% moved the
ratio 78.4% → 50-58%, still over the 40% cap. A lock can only refuse new
**entries**; a trade already open still runs, and E-090 says that tail is where
the profit is. This is a real conflict, not an oversight: **the fat tail that
makes the strategy work is the thing that fails the consistency rule.**

---

## WHAT DOES WORK: FREQUENCY

Daily risk budget held constant, only the trade count changed:

| trades/day | risk/trade | FundingPips 35% | E8 perf 40% |
|---|---|---|---|
| 2 | 0.560% | 24.0% | 19.9% |
| 5 | 0.224% | 89.2% | 80.3% |
| 10 | 0.112% | 99.9% | 99.5% |
| 20 | 0.056% | 100.0% | 100.0% |

**Veer's demand for frequency has been right all along, and this is the hardest
number attached to it yet.** More days, and each day is a smaller share.

**But frequency is bought by dropping timeframe, and E-089 says that costs R.**
At the cost/stop of 0.14 this EA holds (`InpMinStopCostX = 7`):

| trades/day | 5 | 10 | 20 | 50 | **100** |
|---|---|---|---|---|---|
| pass rate | 57.6% | 86.2% | 95.0% | 98.8% | **16.5%** |

100/day collapses — 662 of 800 attempts simply **ran out of days**, because the
size per trade gets too small to reach the target in the window. **Aim for 10 to
50 trades a day, not as many as possible.** And at a cost/stop of 0.20 every row
collapses, so holding `InpMinStopCostX` is not optional.

---

## RECOMMENDED PRESETS

| situation | preset | why |
|---|---|---|
| **first account, prove a payout** | `FIRM_FTMO_2STEP` | highest measured pass rate, no consistency rule, best-documented rules |
| cheap second attempt | `FIRM_5ERS` | same 98.2%, no consistency rule |
| want a lower target | `FIRM_FUNDEDNEXT` | 8% not 10%, no consistency rule, 96.0% |
| **only if you must** | `FIRM_FUNDINGPIPS` | 29.7%. Needs 10+ trades/day to be viable |
| **read this before buying** | `FIRM_E8_PERF` | the challenge is easy and the payout stage is 23.1% |

Leave `InpSafetyBuffer = 0.80`. Every limit is then enforced at 80% of its true
value, because acting **at** a 3% daily limit means acting after the breach.

---

## WHAT THIS CARD DOES NOT PROVE

- The pass rates are bootstrapped from **this EA's own historical trades**, so
  they assume the edge is real and stationary. They measure sequence risk, not
  whether the edge exists. E-092 has just shown the SuperTrend EA's main filter
  is not established.
- Every number is measured on **GOLD 15m and 1h**. The EA is for M1, and there
  is still no M1 data in the repository. The frequency row that matters most —
  how many trades M1 actually gives — is the one row that cannot be filled in.
- Firm rules are `OFFICIAL-SUMMARY` from `JARVIS/research/PROP_FIRMS.md`: from
  the firms' own help centres via search summary, not pages read line by line.
  **Before committing money, confirm four numbers on the firm's own site — the
  daily-loss %, its basis, its reset time, and whether the drawdown trails.**
