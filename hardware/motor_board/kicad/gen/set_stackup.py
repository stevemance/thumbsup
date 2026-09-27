"""Replace the stack-up block of a .kicad_pcb with base_edits.STACKUP6 (the ordered JLC stack-up).
/usr/bin/python3 set_stackup.py board.kicad_pcb [...]"""
import re
import sys
from pathlib import Path

src = (Path(__file__).resolve().parent / "base_edits.py").read_text()
a = src.index("STACKUP6 = '''") + len("STACKUP6 = '''")
STACKUP6 = src[a:src.index("'''", a)]
for f in sys.argv[1:]:
    txt = Path(f).read_text()
    k = txt.index("(stackup")
    i = txt.rfind("\n", 0, k) + 1
    depth = 0
    while True:
        c = txt[k]
        depth += c == "("
        depth -= c == ")"
        k += 1
        if depth == 0:
            break
    k = txt.index("\n", k) + 1
    Path(f).write_text(txt[:i] + STACKUP6 + txt[k:])
    print("stack-up set:", f)
