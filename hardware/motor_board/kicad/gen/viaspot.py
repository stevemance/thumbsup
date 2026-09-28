"""Legal via spots near a pad (via-in-pad first, then around it): python3 viaspot.py geom.json REF NUM [r] [d] [drill]
Clear of every other net's track / via / pad on all routed copper layers by the Default clearance + 0.05,
drill-to-drill 0.25 (hole-to-copper 0.2), outside no-via rule areas.  Prints the best few (distance from the pad)."""
import json
import math
import sys

g = json.load(open(sys.argv[1]))
ref, num = sys.argv[2], sys.argv[3]
R = float(sys.argv[4]) if len(sys.argv) > 4 else 1.5
D = float(sys.argv[5]) if len(sys.argv) > 5 else 0.4
DR = float(sys.argv[6]) if len(sys.argv) > 6 else 0.2
CLR = 0.127 + 0.05
if ref == "pt":                      # viaspot.py geom.json pt x,y,net [r]: around a point, for that net
    _x, _y, _n = num.split(",", 2)
    pad = dict(c=[float(_x), float(_y)], box=[float(_x)] * 2 + [float(_y)] * 2, net=_n, layers=[])
    pad["box"] = [float(_x), float(_y), float(_x), float(_y)]
else:
    pad = [p for p in g["pads"] if p["ref"] == ref and p["num"] == num][0]
net = pad["net"]
LAY = ("F.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu")


def sd(a, b, p):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    u = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dy)


def box_d(bx, p):
    dx = max(bx[0] - p[0], 0, p[0] - bx[2])
    dy = max(bx[1] - p[1], 0, p[1] - bx[3])
    return math.hypot(dx, dy)


def inpoly(poly, p):
    x, y = p
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


tracks = [t for t in g["tracks"] if t["net"] != net and t["layer"] in LAY]
vias = [v for v in g["vias"] if v["net"] != net]
pads = [p for p in g["pads"] if p["net"] != net and (p["tht"] or any(l in LAY for l in p["layers"]))]
rules = [r for r in g["rules"] if r.get("no_vias")]


def ok(p):
    if any(inpoly(r["poly"], p) for r in rules):
        return False
    for t in tracks:
        if sd(t["a"], t["b"], p) < D / 2 + t["w"] / 2 + CLR:
            return False
    for v in vias:
        if math.dist(v["c"], p) < D / 2 + v["d"] / 2 + CLR:
            return False
    for q in pads:
        if box_d(q["box"], p) < D / 2 + CLR:
            return False
    return 0.35 <= p[0] <= g["board"][0] - 0.35 and 0.35 <= p[1] <= g["board"][1] - 0.35


BLK1 = __import__("os").environ.get("VS_BLK1")        # also list spots blocked by exactly one track (to lift)


def blockers(p):
    if any(inpoly(r["poly"], p) for r in rules):
        return None
    if any(math.dist(v["c"], p) < D / 2 + v["d"] / 2 + CLR for v in vias):
        return None
    if any(box_d(q["box"], p) < D / 2 + CLR for q in pads):
        return None
    if not (0.35 <= p[0] <= g["board"][0] - 0.35 and 0.35 <= p[1] <= g["board"][1] - 0.35):
        return None
    return {(t["net"], t["layer"]) for t in tracks if sd(t["a"], t["b"], p) < D / 2 + t["w"] / 2 + CLR}


cx, cy = pad["c"]
if BLK1:
    POWER = {"GND", "VBAT", "/drive_left/L_VM", "/drive_right/R_VM", "+5V"}
    seen = {}
    n = int(R / 0.05)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            p = (round(cx + i * 0.05, 3), round(cy + j * 0.05, 3))
            bl = blockers(p)
            if bl is not None and len(bl) == 1 and not (bl & {(x, l) for x in POWER for l in LAY}):
                k = next(iter(bl))
                d = box_d(pad["box"], p)
                if k not in seen or d < seen[k][0]:
                    seen[k] = (d, p)
    for k, (d, p) in sorted(seen.items(), key=lambda kv: kv[1][0]):
        print(f"   lift {k[0]} on {k[1]}: via at {p}, {d:.2f} mm off the pad")
    sys.exit(0)
out = []
n = int(R / 0.05)
for i in range(-n, n + 1):
    for j in range(-n, n + 1):
        p = (round(cx + i * 0.05, 3), round(cy + j * 0.05, 3))
        d = math.dist(p, (cx, cy))
        if d <= R and ok(p):
            out.append((box_d(pad["box"], p), d, p))
out.sort()
print(ref, num, net, "pad", pad["c"], pad["box"], pad["layers"])
for bd, d, p in out[:int(__import__("os").environ.get("VS_N", "6"))]:
    print(f"   {'in pad' if bd == 0 else f'{bd:.2f} mm off the pad'}  at {p}  (off {round(p[0]-cx,3)},{round(p[1]-cy,3)})")
if not out:
    print("   none within", R)
