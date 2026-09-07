# START HERE — install, run, read, report

One page. Replaces every other setup note.

---

## 0. THE ACCOUNT SIZE, BEFORE ANYTHING ELSE

**Start at £250. £172 is the bare minimum. £60 cannot trade M1 gold.**

This is arithmetic, not caution (E-081, E-181): 0.01 lots is the smallest trade
that exists and it is £0.787 per point. A 2-ATR M1 stop is ~4.4 points, so
**one trade risks £3.43 whatever you set the risk percentage to.**

| balance | one M1 trade is | verdict |
|---|---|---|
| £60 | 5.7% | **not viable** |
| £100 | 3.4% | tight |
| £150 | 2.3% | tight |
| £250 | 1.4% | survivable |

The worst losing run measured on the real signal is **12 in a row** — ordinary
at a 38% win rate, not unlucky. Twelve M1 losses is **£41: 68% of a £60 account,
16% of £250.** That run is what took the £140 account out.

**Margin, the other half of it:** 0.01 lots of gold is ~£3,400 of notional. At
1:100 that needs £34 of margin — **57% of a £60 account for one position.**
Check your leverage before you fund anything.

---

## 1. INSTALL

### MT5 — the EAs
Copy the three `_SINGLEFILE.mq5` files into `MQL5/Experts`, compile, attach one
per chart. **Enable AutoTrading.** Leave `InpJournal = true`.

| EA | chart | magic | why it is on the list |
|---|---|---|---|
| `SuperTrendSniper` | **M1** | 770001 | the only strategy here with a positive out-of-sample result (E-176: +0.374 ATR/trade, t +2.91) |
| `LiquiditySniper` | M15 | 770069 | levels + limit fills. Weak evidence — small size |
| `SweepSniper` | M5 | 990077 | the sweep book, second opinion on the same idea |

**`ZoneSniper` is not on the list.** Its headline numbers were computed before
the two fill-bug fixes (E-151, E-165) and have never been re-run. Don't run it.

### TradingView — the indicators
Open the Pine editor, **Ctrl+A, then paste**. Pasting on top of the old text is
what produced the "already defined" errors.

| file | chart | for |
|---|---|---|
| `LIQUIDITY_SNIPER_2_0.pine` | M5 | levels, sweeps, order blocks, sessions, live position box |
| `SUPERTREND_SNIPER_5_0.pine` | M1 | the trend signal the EA trades |

---

## 2. FIRST THING TO CHECK WHEN IT STARTS

Open the **Experts** tab. SuperTrendSniper prints which gate preset it chose:

```
[STS] AutoTune: M30-and-below preset. DEMA on, chop guard ON,
      ADX ceiling ON, mid-range skip OFF.
```

On M1 it also prints a warning that the preset is **inherited from M15**, not
measured there. That warning is accurate and it is the honest state of this
project — see section 5.

If you see `REFUSING TO START`, read the next line: it says exactly why.

---

## 3. READING THE RESULT — one screenshot

Every EA registers all four magic numbers, so **whichever chart you look at, the
box shows all of them.** Top right, six rows, today first:

```
 SUPERTREND                    LONG
 TODAY          +12.4 pts    9.76 GBP
 trades         7      4W 3L   57%
 open LONG      +3.2 pts    2.51 GBP  0.01 lots
 -- today, by strategy --
 SUPERTREND     +14.1        5 tr
 LIQUIDITY       -1.7        2 tr
 SWEEP  liq       0.0        0 tr
 -- since 12 Sep --
 points         +48.1    22 tr  55%W  37.84
 max DD          -14.2    spread 0.18
```

**TODAY is the top row and it resets at broker midnight.** Screenshot that.

---

## 4. TRADING IT BY HAND

The Pine files draw the same setups the EAs take, and nothing suppresses a
signal — a mark once printed never disappears, which was a real bug and is
fixed. On the chart:

- **BUY / SELL labels** — the signal fired on that closed bar
- **level lines** — the price the setup is built on; they stay drawn while a
  trade is open (they used to vanish)
- **the live position box** — entry, stop and target of the simulated trade
- **the panel's "missed while busy" row** — signals shown but not booked,
  because the simulation holds one position and you don't have to

---

## 5. WHAT IS STILL UNKNOWN, STATED PLAINLY

**There is no recent M1 gold data in this repo.** Every M1 number is either
from Jan–Jun 2018 (a rangebound market, wrong regime) or inherited from M15.
You trade M1. That means the single most important clock in this project has
never actually been measured.

**Export it** — `JARVIS/tools/GET_M1_DATA.md` — and the entry gates, the stop,
the trail and the account size all get settled on the clock you use instead of
assumed from a slower one.

**Nothing here has been forward tested.** No strategy in this project may be
called profitable. The best measured result is one clock, one sample, out of
sample: SuperTrend + DEMA on 1h gold, +0.374 ATR/trade at t +2.91.

---

## 6. WHAT TO SEND BACK

1. **`MQL5/Files/JARVIS_exec_*.csv`** — one row per fill: the price asked, the
   price got, the spread. Copy into `JARVIS/data/exec/`. This measures the two
   numbers the whole project assumes and nobody has ever observed.
2. **A screenshot of the profit box** at the end of a session.
3. **Any bar where you expected a signal and got none** — chart, timeframe, time.
4. **Anything the EA refused** — the Experts log says why, and a refusal that
   looks wrong to you is worth more than ten that look right.
