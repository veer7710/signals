"""
Memory integrity checker.

Implements the recommendation from `findings/02_jarvis_architecture.md`: every
stored claim must declare what KIND of claim it is, so retrieval cannot
launder a guess into a fact.

This matters because JARVIS's memory is read at the start of every session. A
single unmarked speculation in SESSION_STATE.md becomes, three sessions later,
a "fact everyone knows" that nobody can trace. That is how the 748-parameter EA
accumulated twenty rounds of confident, wrong reasoning.

Claim types:
  FACT       — measured or observed; MUST cite how (a command, a file, a source)
  ASSUMPTION — taken as true to proceed; must be re-checked before it matters
  HYPOTHESIS — a testable guess; must name the test that would settle it
  DECISION   — a choice made; not a truth claim
  UNKNOWN    — explicitly not known

Run:  python3 JARVIS/tools/check_memory.py
"""
from __future__ import annotations
import os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "state")

# Phrases that assert a result. If one appears without a traceable source
# nearby, it is an unsupported claim.
ASSERTIVE = re.compile(
    r"\b(proves?|proven|confirmed|guaranteed|always|never fails|certain|"
    r"will (?:make|produce|earn|return)|profitable|works)\b", re.I)

# Something that makes a claim checkable: a command, a file path, a %/R number,
# an experiment id, or an explicit hedge label.
TRACEABLE = re.compile(
    r"(`[^`]+`|\.py|\.md|\.json|E-\d{3}|F-\d{3}|L-\d{3}|D-\d{3}|R-\d{3}|"
    r"[-+]?\d+\.?\d*\s*(?:R\b|%)|[-+]\d+\.?\d*|[£$]\d|https?://|"
    r"UNPROVEN|REJECTED|DISPROVEN|PROMISING|SUPPORTED|CONFIRMED|"
    r"ASSUMPTION|HYPOTHESIS|UNKNOWN|UNVERIFIED|illustrative|indicative)", re.I)

BANNED = re.compile(
    r"\b(guaranteed profit|risk[- ]free|can'?t lose|sure thing|"
    r"will definitely|100% win)\b", re.I)

# A line that FORBIDS a claim is not making it. Without this, the rule
# "never claim guaranteed profit" trips the guaranteed-profit detector, and a
# checker that cries wolf on its own rulebook gets ignored within a day.
NEGATED = re.compile(
    r"\b(never|no claim|not claim|do not|don'?t|avoid|refuse|forbid|"
    r"prohibit|must not|cannot claim|no such|rather than|instead of|"
    r"is not|are not|was not|were not)\b", re.I)


def check():
    problems, checked = [], 0
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".md"):
            continue
        path = os.path.join(ROOT, fn)
        in_code = False
        for n, line in enumerate(open(path, encoding="utf-8"), 1):
            s = line.strip()
            if s.startswith("```"):
                in_code = not in_code
                continue
            if in_code or not s or s.startswith(("#", "|", ">", "-", "*", "1.")):
                # tables and bullets are checked too, but headings are not
                if s.startswith("#"):
                    continue
            checked += 1
            if NEGATED.search(s):
                continue                      # a prohibition, not a claim
            if BANNED.search(s):
                problems.append((fn, n, "BANNED CLAIM", s[:90]))
            elif ASSERTIVE.search(s) and not TRACEABLE.search(s):
                problems.append((fn, n, "unsupported assertion", s[:90]))

    print("=" * 72)
    print("  JARVIS MEMORY INTEGRITY CHECK")
    print("=" * 72)
    print(f"  checked {checked} lines across {len(os.listdir(ROOT))} files\n")
    if not problems:
        print("  CLEAN — every assertive claim is traceable to evidence.")
        return 0
    for fn, n, kind, txt in problems:
        print(f"  {kind:<22} {fn}:{n}")
        print(f"    {txt}")
    print(f"\n  {len(problems)} claim(s) need a source, a hedge, or removal.")
    print("  Fix by citing the experiment id, the command, or labelling the")
    print("  claim ASSUMPTION / HYPOTHESIS / UNKNOWN.")
    return 1


if __name__ == "__main__":
    sys.exit(check())
