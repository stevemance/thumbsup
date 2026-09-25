"""What blocks a via spot?  python3 geo_why.py x y [d] [net] [geom.json]"""
import json
import sys

from geo import Space, rect_seg, seg_seg

x, y = float(sys.argv[1]), float(sys.argv[2])
d = float(sys.argv[3]) if len(sys.argv) > 3 else 0.4
net = sys.argv[4] if len(sys.argv) > 4 else "?"
g = json.load(open(sys.argv[5] if len(sys.argv) > 5 else "out/route/geom.json"))
sp = Space(g)
c = (x, y)
for l, items in sp.items.items():
    for it in items:
        if it[-1] == net:
            continue
        dd = rect_seg(it[1], c, c) if it[0] == "rect" else seg_seg(c, c, it[1], it[2]) - it[3]
        if dd < d / 2 + sp.clr:
            print(l, it[0], it[-1], [round(v, 2) for v in (it[1] if it[0] == "rect" else it[1])], "gap", round(dd - d / 2, 3))
for hx, hy, r in sp.holes:
    import math
    if math.hypot(hx - x, hy - y) < 0.15 + r + 0.25:
        print("hole", hx, hy, r)
