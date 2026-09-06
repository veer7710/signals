# Research queue

## R-001 — Legitimate ways to increase AI throughput  [RESEARCHED 2026-08-27]
- **OmniRoute — RECOMMENDATION RETRACTED 2026-08-28. DO NOT INSTALL.**
  My first pass recommended it after a shallow search. Deeper verification
  found two disqualifying problems:
  (a) it ships **TLS/JA3-JA4 fingerprint stealth and a MITM proxy** as
      features. Fingerprint stealth exists to defeat provider anti-abuse
      detection. That is evasion, and it violates D-005 directly — the very
      thing this project refused to do.
  (b) a disclosed auth-bypass class issue (default `JWT_SECRET` of
      `omniroute-default-secret-change-me`).
  Also: the URL originally cited (`pitbaden/omniroute`) is NOT the canonical
  repo and is best treated as a mirror of unknown provenance. Do not
  `docker run` or `npm i -g` from it.
  **Lesson:** a single web search is not research. Recorded in
  LESSONS_LEARNED as L-006.
- **Graphify** — still plausible, but **the domain I originally cited
  (`graphifyai.net`) could not be verified as the project's real domain.**
  Treat install instructions from it as untrusted until confirmed from the
  project's own GitHub README. In any case it only pays off on large
  codebases and this repo is small, so it is not needed yet.
- **Local models via Ollama** on Veer's PC for bulk/background work.
- Not viable: evading limits, multiple accounts, ToS circumvention (D-005).

## R-002 — Prop firm multi-account rules  [RESEARCHED 2026-08-27 — CRITICAL]
- FTMO caps total allocation at **$400,000 per trader OR PER STRATEGY**
  before scaling. Identical strategies across accounts exceeding that cap
  → accounts suspended.
- Multiple registrations to dodge the cap → prohibited.
- Across DIFFERENT firms is generally allowed, BUT firms detect copy-trading
  via near-identical fill timestamps and shared IP addresses; matched fills
  can get payouts denied at BOTH firms simultaneously.
- **Consequence for the 40-account plan:** it cannot be 40 identical
  accounts. Needs different firms, deliberately varied execution
  (entry offsets, sizing, symbols), and separate network paths. This is a
  hard constraint on the whole scaling thesis — see NEXT_ACTIONS A-004.

## R-003 — Liquidity concepts still untested (E-003 covered only one)
Prior-day/prior-week high-low, session highs/lows (Asia/London/NY), equal
highs/lows clustering, displacement + FVG confirmation, sweep-then-reclaim
on 15m. Each is a separate testable hypothesis.

## R-004 — Not yet started
Open-source JARVIS projects worth borrowing from; MT5 Python bridge for
automated tick-level testing; news/calendar feed for event filtering;
broker symbol specs (contract size, swap, commission) for GOLD.

---

## 2026-09-06 — THE TWO STRUCTURAL GAPS, AND WHY THEY ARE THE BEST SHOTS LEFT

Veer: *"you don't have to be stuck on exactly what we have, you can remove and
add, millions of people use liquidity ICT SMC, take advantage of the thousands
of public indicators."* He is right, and reading the public material against our
own code exposes two gaps that are structural rather than parametric.

### GAP 1 — the levels are on the wrong timeframe
Every public ICT/SMC source agrees on the architecture: **the liquidity that
matters forms on a HIGHER timeframe, and the entry is taken on a lower one.**
`combined.candidates()` calls `pivots(s, 5)` on the same series it trades, so on
M1 it is defending five-bar M1 pivots.

This repo wrote down why that is wrong and then did not act on it.
`liq_m1.py`'s own docstring, months old:
> *"An M1 pivot is noise - seven one-minute bars is not a level anyone is
> defending. An M15 pivot is. So: find the zones on M15, rest the order, and let
> M1 do the execution."*

**The architecture was described, and the code does something else.** Nobody
compared the two.

### GAP 2 — every test ran on the clock where cost is worst
E-132/E-140: spread as a share of ATR is **0.220 on M1, 0.088 on M5, 0.047 on
M15.** Every micro-effect this project has found covers 38-40% of the M1 spread
(E-151's order block, E-168's one-bar top-tick retest). **The same gross edge is
about 4.7x more affordable on M15.** We have repeatedly found real structure and
then killed it on cost, on the one timeframe where cost is highest.

### What `htf_levels.py` is testing
Levels from {M15, H1, Daily} x execution on {M5, M15, M30, H1}, and five
published entries at each: the sweep-and-return we ship, **sweep then FVG entry**
(the most-cited ICT entry, never tested here), sweep then OTE (62-79%
retracement), sweep into an opposing HTF order block, and break-then-retest.
Every table carries **cost as a share of gross**, because that column is the
whole point.

### On the public "80% win rate" claims
Searched for the evidence behind them. What comes back is vendor blogs and
TradingView write-ups quoting 65-75% standalone and 80%+ with confluence, with
**no reproducible backtest attached to any of them.** They are not evidence and
are not treated as such here. What IS worth taking from the public material is
the STRUCTURE - HTF liquidity, LTF entry - which is consistent across every
source and which we demonstrably did not build.
