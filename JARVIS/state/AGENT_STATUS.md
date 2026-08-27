# Agent status

Agents live in `.claude/agents/*.md` and are invoked with the Task tool.

**How the "office" actually works.** The main session is the orchestrator;
it spawns specialists, each with its own fresh context window. That is the
real mechanism behind "agents controlling agents" — genuine parallelism and
context isolation, not roleplay. Each spawned agent starts cold, so
orchestration cost is real: use one when the work is genuinely separable,
not to look busy.

| Agent | Purpose | Status |
|---|---|---|
| `quant-researcher` | Form and test strategy hypotheses via the engine | DEFINED |
| `adversarial-reviewer` | Try to DESTROY promising strategies | DEFINED |
| `mql5-engineer` | Write/audit MQL5 EAs and MT5 execution logic | DEFINED |
| `code-reviewer` | Catch bugs, look-ahead, and false claims in new code | DEFINED |
| `opportunity-scout` | Research income/business opportunities with evidence | DEFINED |
| `memory-keeper` | Keep state files true and write the session handoff | DEFINED |

DEFINED = written and available; none has been run in anger yet. First real
use should be `adversarial-reviewer` against `donchian_trend` (A-001).

Deliberately NOT created: the 40+ agent roster from the master directive.
Most would duplicate these six with different labels, and each unused agent
is context cost and maintenance burden for zero capability. More will be
added when a real bottleneck demands one — the directive's own rule:
"use the smallest effective team."
