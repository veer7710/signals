# JARVIS

A persistent personal AI operating system. Built to survive across Claude
Code sessions: state lives in files, not in a chat window.

## Start here

```bash
./JARVIS/bin/resume                        # where things stand
python3 JARVIS/research/test_engine.py     # is the engine trustworthy?
python3 JARVIS/research/study.py GOLD 1h   # test the strategies
```

Starting a new Claude Code session? `CLAUDE.md` loads automatically and tells
it to read the state files. To be explicit, paste
`JARVIS/state/NEXT_SESSION_PROMPT.md`.

## Layout

```
CLAUDE.md                     session-start protocol (auto-loaded)
JARVIS/
  research/
    engine.py                 backtest core — no look-ahead, real costs
    strategies.py             strategy library
    study.py                  walk-forward + Monte Carlo + cost sensitivity
    test_engine.py            16 regression tests — run before trusting numbers
  state/                      persistent memory (see below)
  ea/inbox/                   ← put your .mq5 and Pine scripts here
  bin/resume                  one-command checkpoint
  reports/                    generated study output
.claude/agents/               6 specialists
data/                         2.4y hourly candles: GOLD, US500, EURUSD, GBPUSD
```

## The research engine

Pure Python, no dependencies, fully deterministic — the same inputs give the
same numbers on any machine, forever.

Four rules are enforced structurally, not by convention:

- **No look-ahead.** Signals see only closed bars; fills happen at the next
  bar's open.
- **Ties lose.** If one bar contains both the stop and the target, it is
  recorded as a loss, because tick order is unknowable from candles.
- **Costs are always charged.** Half-spread plus slippage on every fill,
  plus commission.
- **Nothing is judged on total profit.** Every strategy faces walk-forward
  across six periods, 20,000 Monte Carlo reshuffles, cost sensitivity up to
  3x spread, and a long/short split to expose bull-market bias.

`test_engine.py` proves these hold, including a null test confirming the
engine finds **no** edge in random data. If those tests fail, no backtest
number in this repo means anything.

## Memory

| File | Holds |
|---|---|
| `SESSION_STATE.md` | where the last session stopped |
| `PROJECT_STATUS.md` | what exists and works |
| `NEXT_ACTIONS.md` | what to do next, and what is blocked |
| `NEXT_SESSION_PROMPT.md` | paste-ready continuation prompt |
| `EXPERIMENTS.md` | every hypothesis and its verdict |
| `DECISIONS.md` | settled decisions — not relitigated |
| `FAILURE_LOG.md` | bugs made, root causes, and their regression tests |
| `LESSONS_LEARNED.md` | generalised rules extracted from failures |
| `CAPABILITY_MAP.md` | what JARVIS can and cannot do |
| `KNOWN_LIMITATIONS.md` | honest boundaries |
| `RESEARCH_QUEUE.md` | open research questions |
| `USER_GOALS.md` | goals and constraints |
| `AGENT_STATUS.md` | the agent roster |

## Honesty rules

JARVIS uses a fixed vocabulary and never blurs it: **CONFIRMED · SUPPORTED ·
PROMISING · UNPROVEN · REJECTED · DISPROVEN**.

A backtest is evidence, never proof. No strategy in this repo is claimed to
be profitable, and none ever will be — past results do not establish future
returns, and any system that says otherwise is selling something.
