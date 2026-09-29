"""Split the global router's overflow into pad-escape tiles (within 1 mm of a pad) and channel tiles, per region.
    python3 gstats.py out/groute.json out/geom_place.json"""
import collections
import json
import sys

r = json.load(open(sys.argv[1]))
g = json.load(open(sys.argv[2]))
near = set()
for p in g["pads"]:
    x0, y0, x1, y1 = p["box"]
    for i in range(int((x0 - 1) / 0.5), int((x1 + 1) / 0.5) + 1):
        for j in range(int((y0 - 1) / 0.5), int((y1 + 1) / 0.5) + 1):
            near.add((i, j))
esc, chan = 0, 0
reg = collections.Counter()
for l, x, y, o in r["overflow_tiles"]:
    if (int(round(x / 0.5)), int(round(y / 0.5))) in near:
        esc += 1
    else:
        chan += 1
        reg[(l, int(x // 10) * 10, int(y // 10) * 10)] += 1
print(f"overflow tiles {len(r['overflow_tiles'])}: pad escape {esc}, channel {chan}")
print("channel overflow by 10 mm region:", ", ".join(f"{l}@{x},{y}:{n}" for (l, x, y), n in reg.most_common(12)))
