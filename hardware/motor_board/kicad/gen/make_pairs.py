"""Freeze a block's connection list from a DRC report of the board routed through the previous blocks.
python3 make_pairs.py out/route/drc.json pairs/<block>.json x0 y0 x1 y1 [--skip NET,NET] [--only NET,NET]

Takes every unconnected pair with both ends inside the box (board-local mm), skips the listed nets (GND by default:
GND pads get their own vias to the L2 plane at close-out), and writes endpoints the router understands:
pads by ref/number, vias by position, tracks/zones as a point on their layer."""
import json
import re
import sys
from pathlib import Path

drc, out = sys.argv[1], Path(sys.argv[2])
x0, y0, x1, y1 = map(float, sys.argv[3:7])
opts = dict(zip(sys.argv[7::2], sys.argv[8::2]))
skip = set(opts.get("--skip", "GND").split(","))
only = set(opts["--only"].split(",")) if "--only" in opts else None
LAYER = re.compile(r" on (\S+\.Cu)")


def endpoint(it):
    d = it["description"]
    x, y = it["pos"]["x"] - 100.0, it["pos"]["y"] - 70.0
    m = re.match(r"(?:PTH )?[Pp]ad (\S+) \[.*?\] of (\S+) on", d)
    if m:
        return ["pad", m.group(2), m.group(1)]
    if d.startswith("Via"):
        return ["via", round(x, 4), round(y, 4)]
    lm = LAYER.search(d)
    return ["pt", round(x, 4), round(y, 4), lm.group(1) if lm else "F.Cu"]


pairs = []
for u in json.load(open(drc))["unconnected_items"]:
    its = u["items"]
    net = re.search(r"\[([^\]]*)\]", its[0]["description"]).group(1)
    if net in skip or (only and net not in only):
        continue
    pts = [(i["pos"]["x"] - 100.0, i["pos"]["y"] - 70.0) for i in its]
    if not all(x0 <= x <= x1 and y0 <= y <= y1 for x, y in pts):
        continue
    d = abs(pts[0][0] - pts[1][0]) + abs(pts[0][1] - pts[1][1])
    pairs.append(dict(net=net, a=endpoint(its[0]), b=endpoint(its[1]), dist=round(d, 2)))
out.parent.mkdir(exist_ok=True)
json.dump(pairs, open(out, "w"), indent=0)
print(f"{len(pairs)} pairs -> {out}")
