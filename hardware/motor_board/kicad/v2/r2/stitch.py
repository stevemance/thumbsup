"""L3 GND stitching: every piece of the L3 GND pour (out/planecheck.json, made by planecheck.py dump <board> --fill)
larger than MIN_AREA gets GND vias until it holds >= NEED of them (existing GND vias / GND PTH inside count).  A via
goes where it clears every other-net pad / track / via on all layers (stage geometry geom_r2.json) and sits >= 0.45 mm
inside the piece.  Writes out/r2_stitch.json: [[x, y], ...] for the r2_gnd stage.
    uv run --no-project --with numpy --with matplotlib python r2/stitch.py <exp> [MIN_AREA] [NEED]"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from matplotlib.path import Path as MPath

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
exp = sys.argv[1]
MIN_AREA = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
NEED = int(sys.argv[3]) if len(sys.argv) > 3 else 2
D = json.load(open(V2 / "out" / "planecheck.json"))
G = json.load(open(V2.parent / "gen" / "out" / "exp" / exp / "geom_r2.json"))
VD, CLR = 0.45, 0.2
BAND = [(0, 0, 14.0, 18.5), (14.0, 0, 27.0, 16.0), (27.0, 0, 44.5, 18.5), (44.5, 0, 85.0, 16.0)]


def area(pts):
    a = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        a += x0 * y1 - x1 * y0
    return abs(a) / 2


def seg_d(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    u = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dy)


pads = [(p["box"], p["net"]) for p in G["pads"]]
tracks = [(t["a"], t["b"], t["w"], t["net"]) for t in G["tracks"]]
vias = [(v["c"], v["d"], v["net"]) for v in G["vias"]]
added = []


def free(x, y):
    r = VD / 2
    if not (0.6 < x < 84.4 and 0.6 < y < 34.4):
        return False
    for b, net in pads:
        c = CLR if net != "GND" else 0.15
        if b[0] - r - c < x < b[2] + r + c and b[1] - r - c < y < b[3] + r + c:
            return False
    for a, b, w, net in tracks:
        if net != "GND" and seg_d((x, y), a, b) < r + w / 2 + CLR:
            return False
    for c, d, net in vias + [((ax, ay), VD, "GND") for ax, ay in added]:
        if math.hypot(c[0] - x, c[1] - y) < r + d / 2 + (0.25 if net == "GND" else CLR + 0.1):
            return False
    return True


gnd_pts = [v[0] for v in vias if v[2] == "GND"] + [h["c"] for h in D["holes"] if h["net"] == "GND"]
report = []
for k, poly in enumerate(D["fill"]["pc L3 GND"]):
    outl = poly["outline"]
    a = area(outl) - sum(area(h) for h in poly["holes"])
    path = MPath(outl)
    holes = [MPath(h) for h in poly["holes"]]

    def inside(p):
        return path.contains_point(p) and not any(h.contains_point(p) for h in holes)
    have = sum(1 for p in gnd_pts if inside(p))
    if a < MIN_AREA or have >= NEED:
        report.append((round(a, 2), have, 0))
        continue
    xs, ys = [p[0] for p in outl], [p[1] for p in outl]
    cand = []
    for x in np.arange(min(xs), max(xs), 0.1):
        for y in np.arange(min(ys), max(ys), 0.1):
            if not inside((x, y)):
                continue
            if not all(inside((x + 0.45 * math.cos(t), y + 0.45 * math.sin(t))) for t in np.linspace(0, 2 * math.pi, 9)[:-1]):
                continue
            cand.append((round(float(x), 2), round(float(y), 2)))
    got = 0
    for c in cand:
        if have + got >= NEED:
            break
        if any(math.dist(c, q) < 1.5 for q in added[len(added) - got:]):
            continue
        if free(*c):
            added.append(c)
            got += 1
    report.append((round(a, 2), have, got))
json.dump(added, open(V2 / "out" / "r2_stitch.json", "w"))
short = [r for r in report if r[0] >= MIN_AREA and r[1] + r[2] < NEED]
print(f"L3 GND pieces {len(report)}; >= {MIN_AREA} mm2: {sum(1 for r in report if r[0] >= MIN_AREA)}; "
      f"stitch vias added {len(added)}; pieces still short of {NEED}: {len(short)} {short[:12]}")
