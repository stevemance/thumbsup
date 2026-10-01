"""Unconnected items of a stage's DRC report, by class and net.
    python3 r2/opens.py <exp | path/to/drc.json> [-v]      (exp = kicad/gen/out/exp/<exp>/drc.json)"""
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
POUR = {"VBAT", "BAT_IN", "PSW_S", "VBAT_SW", "W_A", "W_B", "W_C", "W_SLA", "W_SLB", "W_SLC", "L_A", "L_B", "L_C",
        "R_A", "R_B", "R_C", "L_VM", "R_VM"}
arg = sys.argv[1]
p = Path(arg) if arg.endswith(".json") else HERE.parents[1] / "gen" / "out" / "exp" / arg / "drc.json"
d = json.load(open(p))
by = collections.defaultdict(list)
for u in d["unconnected_items"]:
    m = re.search(r"\[([^\]]+)\]", u["items"][0]["description"])
    n = m.group(1).split("/")[-1] if m else "?"
    by[n].append(" <-> ".join(re.sub(r" on .*", "", i["description"])[:40] for i in u["items"]))
cls = {"GND": [], "pour": [], "sig": []}
for n, v in by.items():
    cls["GND" if n == "GND" else "pour" if n in POUR else "sig"].append((n, v))
err = collections.Counter(v["type"] for v in d["violations"] if v["severity"] == "error")
print(f"DRC errors {dict(err) or 0}; unconnected {len(d['unconnected_items'])}: GND {sum(len(v) for _, v in cls['GND'])}, "
      f"pour {sum(len(v) for _, v in cls['pour'])}, signal/rail {sum(len(v) for _, v in cls['sig'])}")
print("signal/rail:", " ".join(f"{n}:{len(v)}" for n, v in sorted(cls["sig"])))
if "-v" in sys.argv:
    for n, v in sorted(cls["sig"]):
        for x in v:
            print(f"   {n:12s} {x}")
