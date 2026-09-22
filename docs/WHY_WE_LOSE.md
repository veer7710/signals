# Why are we losing? — entry, exit, setup, strategy, or conditions

Not a win-rate backtest. `research/attribution.py` decomposes every trade into
an **exact identity**, so the loss is assigned rather than guessed at:

```
actual = setup_max − entry_cost − exit_cost − spread
```

| term | meaning |
|---|---|
| `setup_max` | the peak, measured from the best fill that actually traded in the entry window. The ceiling on the idea. |
| `entry_cost` | how much worse the real fill was than that. **This is "not hitting top tick", in money.** |
| `exit_cost` | how much of the peak was handed back. |
| `spread` | the fee. Certain. |

---

## The answer

GOLD 1h, de-trended, ATR-3 trail — the *good* exit:

| | sweep continuation | pullback continuation | momentum |
|---|---|---|---|
| setup offered | +42.45/trade | +40.33 | +42.52 |
| **lost to EXIT** | **−29.64 (69.8%)** | **−28.58 (70.8%)** | **−29.57 (69.5%)** |
| lost to ENTRY | −9.49 (22.4%) | −10.34 (25.6%) | −10.56 (24.8%) |
| lost to SPREAD | −0.30 (0.7%) | −0.30 (0.7%) | −0.30 (0.7%) |
| **kept** | +3.17 | +1.27 | +2.23 |

**The exit is roughly 70% of the leak. The entry is about 24%. All three
families give the same answer, so it is not family-specific.**

### Bounded to what is actually reachable

"Perfect entry" and "perfect exit" are hindsight and flatter everything. Bounded
instead by what the two shipped mechanisms can really deliver — the retail limit
getting one noise band better at a 60% fill rate, and a trail keeping 85% of
peak rather than 100%:

| GOLD 1h | now | + entry fix | + exit fix | both |
|---|---|---|---|---|
| sweep continuation | 1102 | 2358 | **9745** | 11001 |
| pullback continuation | 409 | 1641 | **8342** | 9573 |
| momentum | 608 | 1631 | **7371** | 8395 |

**The exit fix is worth about seven times the entry fix.**

### And that ordering is not an artefact of the 85% assumption

| trail keeps | entry gain | exit gain | ratio |
|---|---|---|---|
| 50% | 1256 | 5395 | **4.3×** |
| 70% | 1256 | 7068 | 5.6× |
| 85% | 1256 | 8643 | 6.9× |
| 95% | 1256 | 9749 | 7.8× |

Even at a trail keeping **half** the peak — worse than the give-back the EA runs
today — the exit is still the bigger number.

---

## Answering each of your questions separately

**Is it the entry?** Partly. 22–26% of the leak, worth about £1 of every £5 the
exit is worth. The retail-limit fix is correctly aimed but it is the smaller
lever.

**Is it the exit?** **Yes. ~70%.** This is the answer.

**Is it the trade / the setup?** No. **0% of setups offered less than the
spread** — every one of them had something in it. Setup selection is not where
the money goes.

**Is it the strategy?** No. Three unrelated entry families produce the same
~70/24/1 split. A different strategy would inherit the same problem.

**Is it market conditions?** Partly, and not the way you would expect. Trades
per regime, points per regime:

| GOLD 1h | RANGE | MIXED | TREND |
|---|---|---|---|
| pullback continuation | 206 / **+252** | 107 / **+395** | 16 / **−237** |
| sweep continuation | 197 / **+734** | 103 / +290 | 48 / +78 |
| momentum | 86 / −2 | 122 / **+680** | 64 / −70 |

**TREND is the losing regime on two of three families.** The money is made in
RANGE and MIXED. That is consistent with gold's own statistics — variance ratio
below 1 at every horizon — and it is the opposite of how the EA has been aimed.

**Are we in drawdown too much?** That is the exit question again, and the
breakeven ladder addresses it directly: ~9% of trades reach breakeven and then
fail, and those become scratches instead of full stops.

---

## What this means for what to build next

1. **Stop adding entry gates.** They chase 24% of the problem. Eight now exist
   and seven ship OFF.
2. **The exit is the whole game.** The ladder and the chandelier are the right
   work. Anything else that touches the exit gets priority.
3. **Stop aiming at TREND.** It loses on two of three families.
4. Spread is 0.7% of the gross offered — though it is still 48% of the *net*
   loss, because the net is small. Both numbers are true; they have different
   denominators, and the brief's 48% figure uses the net one.
