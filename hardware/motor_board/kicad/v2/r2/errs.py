"""DRC errors of a stage, one line each with positions (board-local mm), and the open items of the listed nets.
    python3 r2/errs.py <exp | drc.json> [net,net,...]"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
arg = sys.argv[1]
p = Path(arg) if arg.endswith(".json") else HERE.parents[1] / "gen" / "out" / "exp" / arg / "drc.json"
d = json.load(open(p))
OX, OY = 100.0, 70.0        # KiCad page offset of the board origin (board-local = KiCad - offset)


def loc(i):
    return f"({i['pos']['x'] - OX:.2f},{i['pos']['y'] - OY:.2f})"


def short(s):
    s = re.sub(r"/[a-z_]+/", "", s)
    return s.replace(" on L1.TOP", "@F").replace(" on L4.BOT", "@B").replace(" on L3.SIG", "@L3")[:60]


for v in d["violations"]:
    if v["severity"] != "error":
        continue
    print(v["type"], " | ".join(f"{short(i['description'])} {loc(i)}" for i in v["items"]))
if len(sys.argv) > 2:
    want = set(sys.argv[2].split(","))
    for u in d["unconnected_items"]:
        m = re.search(r"\[([^\]]+)\]", u["items"][0]["description"])
        n = m.group(1).split("/")[-1] if m else "?"
        if n in want:
            print("open", n, " <-> ".join(f"{short(i['description'])} {loc(i)}" for i in u["items"]))
