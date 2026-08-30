# How to run JARVIS — free, on your own PC

Everything below is free. No API keys, no subscriptions beyond the Claude
account you already have.

---

## What JARVIS actually is

Not a chatbot. It is a set of files in this repo that make Claude Code carry
knowledge between sessions, plus local Python tools that do the heavy work
without costing you any Claude usage.

Three parts:

| Part | What it does | Cost |
|---|---|---|
| **Memory** (`JARVIS/state/`) | Every decision, failure and experiment. Claude reads it at the start of every session so you never re-explain anything. | free |
| **Research engine** (`JARVIS/research/`) | Backtests, searches thousands of strategy configs, catches overfitting. Pure Python. | **free — no AI usage at all** |
| **Agents** (`.claude/agents/`) | Six specialists Claude can spawn for deep work. | uses your Claude plan |

---

## Setup (10 minutes, once)

### 1. Install Python
https://python.org — tick **"Add Python to PATH"** during install.

### 2. Get the repo onto your PC
```
git clone https://github.com/veer7710/signals
cd signals
git checkout claude/jarvis-ai-operating-system-2xaclm
```

### 3. Check it works
```
python JARVIS/research/test_engine.py
```
You should see **ALL TESTS PASSED**. If not, stop and tell me.

---

## Daily use

### See where everything stands
```
python JARVIS/research/leaderboard.py
```
Every strategy, ranked, with the four gates each must pass.

### Run thousands of tests — costs zero AI usage
```
python JARVIS/research/autosearch.py --fast
```
672 configurations in about 40 seconds. Splits data 70/30, tests the winners on
data it never saw, and tells you the luck threshold. **This is the one that
saves you money** — run it as often as you like.

### Check a specific idea
```
python JARVIS/research/study.py GOLD 1h          # full gauntlet on one market
python JARVIS/research/exit_study.py GOLD 1h     # which exit rule is best
python JARVIS/research/movesize.py GOLD 15m      # when are big moves coming
python JARVIS/research/sweep_study.py GOLD 15m   # liquidity sweep stats
```

### Verify a Pine script before pasting it
```
python JARVIS/tools/check_pine.py JARVIS/pine/LiquiditySniper_v1.pine
```
Catches undeclared variables — the exact bug that made one version fail to
compile.

---

## Starting a Claude session

Just open Claude Code in the repo folder. `CLAUDE.md` loads automatically and
tells it to read the state files first.

To be explicit, paste this:

> Read JARVIS/state/SESSION_STATE.md, NEXT_ACTIONS.md and EXPERIMENTS.md, then
> continue from the checkpoint.

You never need to explain the project again.

### Making Claude use an agent
```
Use the adversarial-reviewer agent to attack <strategy>.
Use the quant-researcher agent to test <idea>.
Use the mql5-engineer agent to audit <file>.
```

---

## The one thing only you can do

Every market data site is blocked from Claude's container. **I cannot get M1
or M5 data.** Your MT5 can.

On your PC, with MT5 open and logged in:
```
pip install MetaTrader5
python JARVIS/tools/export_mt5_data.py
```

That creates `mt5_export/`. Send me that folder.

It gets us two things nothing else can:
1. **M1 and M5 history** — every negative result so far is on 1h and 15m. Your
   actual strategy is M1 scalping, and it has never been tested.
2. **Your broker's real spreads** — every cost figure so far is my estimate.

---

## Free ways to get more out of your plan

| Do this | Why |
|---|---|
| Run the Python tools yourself | They cost zero AI usage. Do the grinding locally, bring Claude the summary. |
| Start a new session per topic | Smaller context = less usage per message. |
| Point Claude at `JARVIS/state/` | Faster than re-reading whole files. |
| Install [Ollama](https://ollama.com) | Free local models for background work. |

**Do not install OmniRoute.** I recommended it early on and was wrong — it
ships tools designed to evade provider limits and has a disclosed
default-secret vulnerability.
