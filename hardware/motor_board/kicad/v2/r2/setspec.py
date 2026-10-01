"""Replace (or add) EXPLICIT entries in spec.py's r2 block:  python3 r2/setspec.py r2/edits.txt
edits.txt lines:  REF|x|y|rot|side|description"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE.parent / "spec.py"
L = p.read_text().split("\n")
for line in open(sys.argv[1]):
    line = line.rstrip("\n")
    if not line.strip() or line.startswith("#"):
        continue
    ref, x, y, rot, side, desc = line.split("|", 5)
    entry = f'    "{ref}": ({x}, {y}, {rot}, {side}, "{desc}"),'
    hits = [i for i, l in enumerate(L) if l.strip().startswith(f'"{ref}": (') and l.strip().endswith("),")
            and ("T, \"" in l or "B, \"" in l)]
    if hits:
        L[hits[-1]] = entry
        for i in hits[:-1]:
            L[i] = None
    else:
        k = max(i for i, l in enumerate(L) if l is not None and l.strip().startswith('"TH1": (69'))
        L.insert(k, entry)
    L = [l for l in L if l is not None]
    print("set", ref)
p.write_text("\n".join(L))
