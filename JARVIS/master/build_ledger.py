"""
Generate PHASE_LEDGER.md from MASTER_PROMPT.md.

The ledger is generated, never hand-edited into existence, so the phase list
and the status list cannot drift apart. Status is PRESERVED across regenerations
by reading the existing ledger first - editing a status by hand is the intended
way to use it; editing the phase TEXT by hand is not.

Run:  python3 JARVIS/master/build_ledger.py
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "MASTER_PROMPT.md")
OUT = os.path.normpath(os.path.join(HERE, "..", "state", "PHASE_LEDGER.md"))
VALID = ("TODO", "DOING", "DONE", "BLOCKED", "DROPPED")


def parse_master():
    block, phases = None, []
    for line in open(SRC):
        b = re.match(r'^### BLOCK ([A-H]) — (.+?)\.?\s*\(P\d+', line)
        if b:
            block = (b.group(1), b.group(2).strip())
        m = re.match(r'^- \*\*P(\d+)\*\* (.+)$', line)
        if m and block:
            txt = re.sub(r'[`*]', '', m.group(2)).strip()
            phases.append((int(m.group(1)), block[0], block[1], txt))
    return phases


def parse_existing():
    """Keep whatever status a human or an earlier session already set."""
    st = {}
    if not os.path.exists(OUT):
        return st
    for line in open(OUT):
        m = re.match(r'^\| P(\d+) \| \w \| (\w+) \|(.*)$', line)
        if m:
            note = m.group(3).rsplit("|", 1)[0].strip() if "|" in m.group(3) else ""
            st[int(m.group(1))] = (m.group(2), note)
    return st


def main():
    phases = parse_master()
    old = parse_existing()
    done = sum(1 for p in phases if old.get(p[0], ("TODO", ""))[0] == "DONE")
    lines = [
        "# PHASE LEDGER",
        "",
        "**GENERATED FILE.** Edit the STATUS and NOTE columns; never the phase text.",
        "Regenerate with `python3 JARVIS/master/build_ledger.py` after changing",
        "`JARVIS/master/MASTER_PROMPT.md`. Status is preserved across regenerations.",
        "",
        f"Status vocabulary: {' / '.join(VALID)}",
        "",
        f"**{done} of {len(phases)} phases DONE.**",
        "",
        "A session takes the LOWEST-NUMBERED phase that is not DONE or DROPPED.",
        "A phase is DONE only when its block's gate passes. BLOCKED requires a note",
        "saying the single action that would clear it.",
        "",
        "| # | B | STATUS | phase | note |",
        "|---|---|---|---|---|",
    ]
    lastb = None
    for num, bl, bname, txt in phases:
        if bl != lastb:
            lines.append(f"| | | | **BLOCK {bl} — {bname}** | |")
            lastb = bl
        stat, note = old.get(num, ("TODO", ""))
        if stat not in VALID:
            stat = "TODO"
        if len(txt) > 96:
            txt = txt[:93] + "..."
        lines.append(f"| P{num} | {bl} | {stat} | {txt} | {note} |")
    open(OUT, "w").write("\n".join(lines) + "\n")
    print(f"wrote {OUT}: {len(phases)} phases, {done} DONE")


if __name__ == "__main__":
    main()
