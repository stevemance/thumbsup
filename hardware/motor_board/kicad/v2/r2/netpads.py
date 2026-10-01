"""netpads.py <dump.json> x0 y0 x1 y1 : every net with a pad in the box, and all of that net's pads (ref.num side x y)"""
import json
import sys
from collections import defaultdict

D = json.load(open(sys.argv[1]))
x0, y0, x1, y1 = map(float, sys.argv[2:6])
by = defaultdict(list)
for p in D["pads"]:
    by[p["net"]].append(p)
skip = {"GND"}
nets = sorted({p["net"] for p in D["pads"] if x0 <= p["c"][0] <= x1 and y0 <= p["c"][1] <= y1} - skip)
for n in nets:
    if n.startswith("unconnected"):
        continue
    s = " ".join(f"{p['ref']}.{p['num']}{p['side']}({p['c'][0]:.2f},{p['c'][1]:.2f})" for p in by[n])
    print(f"{n.split('/')[-1]:12s} {s}")
