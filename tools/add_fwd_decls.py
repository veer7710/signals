#!/usr/bin/env python3
"""
Insert a forward-declaration block for every user function, right after the
last input/global declaration. The brief records six declaration-order traps
in one session; forward declarations cost nothing and remove the entire class.
Idempotent: re-running replaces the existing block.
"""
import re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from mql5_check import strip_noise, FUNC_DEF

MARK_A = "//--- forward declarations (auto-generated; see tools/add_fwd_decls.py)"
MARK_B = "//--- end forward declarations"

def process(path):
    raw = open(path).read()
    # drop any previous block so this is idempotent
    raw = re.sub(re.escape(MARK_A)+r".*?"+re.escape(MARK_B)+r"\n", "", raw, flags=re.S)
    src = strip_noise(raw)
    sigs, seen, all_def_lines = [], set(), []
    for m in FUNC_DEF.finditer(src):
        ret, nm, params = m.group(1), m.group(2), m.group(3).strip()
        ln = src[:m.start()].count("\n")+1
        all_def_lines.append(ln)          # includes OnInit/OnTick/OnDeinit
        if nm.startswith("On") or nm in seen: continue
        seen.add(nm)
        sigs.append((ln, f"{ret} {nm}({params});"))
    if not sigs: return False
    # the block must sit above the FIRST function of any kind -- the On*
    # handlers call these helpers, so landing after OnInit defeats the point
    first_def = min(all_def_lines)
    lines = raw.split("\n")
    # insert just above the first function definition
    ins = first_def - 1
    while ins > 0 and lines[ins-1].strip().startswith("//"):
        ins -= 1
    block = [MARK_A] + [s for _, s in sigs] + [MARK_B, ""]
    lines[ins:ins] = block
    open(path, "w").write("\n".join(lines))
    return True

if __name__ == "__main__":
    targets = sys.argv[1:] or ["mq5/"+f for f in sorted(os.listdir("mq5")) if f.endswith(".mq5")]
    for t in targets:
        print(("added " if process(t) else "skipped "), t)
