"""Nearest legal via spots to a point on the routed board.   python3 geo_near.py x y net [d] [n] [geom.json]"""
import json
import math
import sys

from geo import Space

x, y, net = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
d = float(sys.argv[4]) if len(sys.argv) > 4 else 0.4
n = int(sys.argv[5]) if len(sys.argv) > 5 else 5
g = json.load(open(sys.argv[6] if len(sys.argv) > 6 else "out/route/geom_routed.json"))
sp = Space(g)
found = []
step = 0.05
for r in range(0, 60):
    for i in range(-r, r + 1):
        for j in range(-r, r + 1):
            if max(abs(i), abs(j)) != r:
                continue
            c = (round(x + i * step, 3), round(y + j * step, 3))
            if sp.via_ok(c, d, d / 2, net):
                found.append((math.hypot(c[0] - x, c[1] - y), c))
    if len(found) >= n:
        break
for dist, c in sorted(found)[:n]:
    print(c, round(dist, 2))
