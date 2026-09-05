#!/usr/bin/env python3
"""Splice local #include "x.mqh" files into a single drop-in .mq5.

Veer copies these files into MQL5/Experts by hand. Every extra file is another
chance for a compile error that has nothing to do with the strategy, so the
shipped EA is one file. The .mqh under JARVIS/ea/include stays the single
source of truth and this splices it in.

    python3 JARVIS/tools/build_ea.py JARVIS/ea/build/ZoneSniper.mq5
"""
import re
import sys
from pathlib import Path

INC = Path(__file__).resolve().parents[1] / "ea" / "include"
PAT = re.compile(r'^\s*#include\s+"([^"]+)"\s*$', re.M)


def splice(src: Path, seen=None) -> str:
    seen = seen if seen is not None else set()
    text = src.read_text()

    def sub(m):
        name = m.group(1)
        if name in seen:
            return f"// (already spliced: {name})"
        seen.add(name)
        target = INC / name
        if not target.exists():
            raise SystemExit(f"{src}: cannot find include {name} under {INC}")
        body = splice(target, seen)
        bar = "=" * 62
        return (f"//{bar}\n// BEGIN {name}  (spliced by JARVIS/tools/build_ea.py "
                f"- edit the .mqh, not this)\n//{bar}\n{body}\n"
                f"//{bar}\n// END {name}\n//{bar}")

    return PAT.sub(sub, text)


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for arg in sys.argv[1:]:
        src = Path(arg)
        out = src.with_name(src.stem + "_SINGLEFILE.mq5")
        text = splice(src)
        if "#include \"" in text:
            raise SystemExit(f"{src}: an include survived the splice")
        out.write_text(text)
        print(f"{src.name}  ->  {out.name}  ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
