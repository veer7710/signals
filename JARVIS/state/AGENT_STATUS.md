# Agent status

Agents live in `.claude/agents/*.md` and are invoked with the Task tool.

**How the "office" is structured** (see `research/findings/02_jarvis_architecture.md`):
one main loop carries all state, and sub-agents are stateless workers with
narrow scope and their own context window. That is the shape the published
engineering evidence converges on — Cognition's "Don't Build Multi-Agents" and
the MAST failure taxonomy both find that dispersed decision-making is the main
cause of multi-agent failure, and that failures are design failures rather than
model failures.

The sharpest rule from that research: **READ actions parallelise, WRITE actions
do not.** Fan out research, backtest sweeps and log analysis; never run two
agents editing strategy code. Anthropic's own multi-agent research system is
reported to use roughly 15x the tokens of a chat interaction, so an agent is
worth spawning when work is genuinely separable and read-heavy — not to look
busy. This session is a live example: 5 research agents were killed mid-run by
a usage limit (see FAILURE_LOG F-003).

| Agent | Purpose | Status |
|---|---|---|
| `quant-researcher` | Form and test strategy hypotheses via the engine | DEFINED |
| `adversarial-reviewer` | Try to DESTROY promising strategies | DEFINED |
| `mql5-engineer` | Write/audit MQL5 EAs and MT5 execution logic | DEFINED |
| `code-reviewer` | Catch bugs, look-ahead, and false claims in new code | DEFINED |
| `opportunity-scout` | Research income/business opportunities with evidence | DEFINED |
| `memory-keeper` | Keep state files true and write the session handoff | DEFINED |
| `orchestrator` | **Prompt master.** Writes the prompts that drive the other agents | DEFINED |

DEFINED = written and available; none has been run in anger yet. First real
use should be `adversarial-reviewer` against `donchian_trend` (A-001).

Deliberately NOT created: the 40+ agent roster from the master directive.
Most would duplicate these six with different labels, and each unused agent
is context cost and maintenance burden for zero capability. More will be
added when a real bottleneck demands one — the directive's own rule:
"use the smallest effective team."


---
## How to use the office

Say it in plain English and Claude spawns the right one:

    Use the orchestrator agent to plan research on <topic>.
    Use the adversarial-reviewer agent to attack <strategy>.
    Use the quant-researcher agent to test <idea>.
    Use the mql5-engineer agent to audit <file>.
    Use the code-reviewer agent on the last change.
    Use the opportunity-scout agent to research <business idea>.
    Use the memory-keeper agent to checkpoint before I stop.

**Start with the orchestrator when a job needs several specialists.** It reads
the experiment log so it never briefs an agent to redo settled work, and it
writes prompts with a disproof criterion — which is the difference between an
agent that finds an answer and one that finds agreement.

## What the office is NOT

It is not autonomous. Agents run when asked, report back, and stop. Nothing
here trades, spends money, or acts outside the repo. That is deliberate: an
agent that can both read untrusted web content and move money is the single
worst security shape available.
