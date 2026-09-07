# RUN THIS ON DEMO TODAY — what to load, what to ignore, what to send back

One page. Everything below is set up and pushed.

---

## THE HONEST FRAME, IN THREE LINES

Nothing in this project has a proven edge. Today's run is **not** a test of
whether the strategies make money — the backtests already say they sit on zero,
and one week of demo cannot overturn that either way.

**What today's run IS for: measuring your broker's execution.** Every backtest
here charges cost through one assumed number — spread as 0.11 of M1 ATR — and
assumes slippage is *exactly zero*. Neither has ever been observed on your
account. Both decide everything: the best book in the repo (E-149, M5) is
+24.2 points and turns negative at **0.012 points** of slippage.

So the EAs now write down, for every single fill, **the price we asked for and
the price we got**. That is the deliverable. P&L over a week is noise; the
slippage distribution over 100 fills is a fact that changes the research.

---

## WHAT TO LOAD

### Indicators (TradingView — you can run 2 at once)

| file | put it on | what it is for |
|---|---|---|
| `JARVIS/pine/LIQUIDITY_SNIPER_2_0.pine` | **M5** | the one you said you'd use. Sweeps, levels, order blocks, sessions, live position box, today-only panel |
| `JARVIS/pine/ZONE_SNIPER_3_2.pine` | M15 | level-return entries, now with the levels actually drawn while a trade is open |

Paste method, every time: open the Pine editor, **Ctrl+A**, then paste. Pasting
on top of the existing text is what produced the ten "already defined" errors.

`SUPERTREND_SNIPER_5_0.pine` is fixed and day-scoped, but see the next section
before you put money behind anything it says.

### EAs (MT5 demo — one chart each, all four if you want the data faster)

Use the `_SINGLEFILE.mq5` builds in `JARVIS/ea/build/`. Drop into
`MQL5/Experts`, compile, attach. Leave `InpJournal = true` — that is the whole
point of the exercise.

| EA | timeframe | why it is on the list |
|---|---|---|
| `SweepSniper_SINGLEFILE.mq5` | M5 | the sweep book. Fills at levels, so it measures **stop-order slippage**, the number that matters most |
| `LiquiditySniper_SINGLEFILE.mq5` | M15 | limit fills. Measures the opposite fill type |
| `ZoneSniper_SINGLEFILE.mq5` | M15 | second limit source |
| `SuperTrendSniper_SINGLEFILE.mq5` | M5 | **execution probe only — see below** |

---

## READ THIS BEFORE YOU JUDGE SUPERTREND BY ITS P&L

E-175, run today. The SuperTrend signal was stripped to nothing — enter on the
flip, exit on the opposite flip, no stop, no trail, no stall, no filter, and
**no cost at all**:

```
      M1  n 16134  gross  -126.3 pts  -0.0078/trade   t -1.42
      M5  n  2976  gross  -161.5 pts  -0.0543/trade   t -1.76
     M15  n   886  gross   +72.1 pts  +0.0814/trade   t +0.80
```

**On M1 and M5 it loses before a single penny of cost.** Your live panel's
"88% of the loss is transaction cost" and "exit adds −32.1pt" now have an
explanation: the exit stack was trying to rescue a signal with nothing in it.
No cooldown, no ATR length, no multiplier fixes a negative gross. At the shipped
(7, 1.2) the raw signal flips **147.9 times a day** on M1.

M15 is the only non-negative cell and its t-stat is 0.80, which is zero.

It stays on the list because it fills often, and something that fills often
measures slippage fast. Run it for the journal, not for the money.

---

## WHAT CHANGED IN THE INDICATORS TODAY

**The missing-signal bug you kept reporting was still live.** The fix I shipped
before split "the signal" from "the simulated trade" — but the gate was also
sitting one layer further upstream, in `readyS`/`readyB`. While a trade was
open, the sweep condition was false, so the sweep marks were still being
deleted off your chart. Sweeps are the only signal ON by default, so that was
almost all of them.

The proof it was real, not a guess: the panel's own **"missed while busy"** row
counts signals that fired while a trade was open. For sweeps that could never
be true, so the row built to measure this could only ever read zero.

Also fixed:
- the sweep's extreme stopped tracking mid-trade, so a later fill got its stop
  from a stale extreme — and disagreed with the research
- the **level lines themselves** disappeared while a trade was open (Zone
  Sniper too). You asked for levels marked out like an SMC tool; they now stay
- panels on SuperTrend and Zone are now **today only, midnight to live**, in
  the session timezone. Only Liquidity had that before, which is why your
  screenshot showed four days stacked as one session

---

## WHAT TO SEND BACK

**Do not send me a P&L number. It will not mean anything after a week.**

Send these:

1. **The CSV files.** `MQL5/Files/JARVIS_exec_*.csv` — one per EA. That is the
   whole point. Copy them into `JARVIS/data/exec/` and I run
   `python3 JARVIS/research/read_exec.py`, which prints your measured
   spread/ATR and your measured slippage against the assumed values and says
   what they do to the research.
2. **Screenshots of any bar where you expected a signal and did not get one.**
   Chart, timeframe and time, so I can reproduce it. This is the only way the
   signal-quality question gets answered.
3. **Anything the EA refused.** The Experts log line says why. A refusal that
   looks wrong to you is worth more than ten that look right.
4. **Whether the panel numbers match your account's actual closed P&L for the
   day.** If they diverge, the panel is lying and I need to know.

---

## WHAT WOULD MAKE THE DATA WORTHLESS

- **Fewer than about 30 fills.** The slippage median is noise below that.
- **A demo feed that fills every stop order at exactly the requested level.**
  Some do, as a courtesy, and live will not honour it. `read_exec.py` prints the
  share of exactly-zero-slip fills so this is visible rather than assumed.
- Running it on a symbol other than XAUUSD. Every number in this repo is gold.
