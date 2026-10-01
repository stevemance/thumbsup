"""probe.py <dump.json> <spec> ... : clearance check of proposed copper against the dump.
spec:  via:NET:x,y            (0.4 via, all layers)
       F:NET:x,y;x,y;...[:w]  track on F / L3 / B (default w 0.15)
Reports every other-net item closer than the clearance (0.127 + margin), via pitch < 0.9 to other non-GND vias,
and board-edge distance < 0.3.  Pads: side T -> F, B -> B, TB (THT) -> all layers; a THT pad's hole also blocks L2/L3."""
import json
import math
import sys

D = json.load(open(sys.argv[1]))
CLR = 0.127 + 0.01
W, H = 85.0, 35.0


def nm(n):
    return n.split("/")[-1]


def seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def seg_seg(a, b, c, d):
    # min distance between two segments (sampled ends + crossing test)
    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0])
    if (ccw(a, c, d) > 0) != (ccw(b, c, d) > 0) and (ccw(a, b, c) > 0) != (ccw(a, b, d) > 0):
        return 0.0
    return min(seg_dist(a, c, d), seg_dist(b, c, d), seg_dist(c, a, b), seg_dist(d, a, b))


def box_seg(bx, a, b):
    x0, y0, x1, y1 = bx
    # distance from segment to rectangle
    if any(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in (a, b)):
        return 0.0
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return min(seg_seg(a, b, corners[i], corners[(i + 1) % 4]) for i in range(4))


CROP = None
_cache = {}


def items(layer):
    if CROP is not None:
        if layer not in _cache:
            x0, y0, x1, y1 = CROP

            def near(g):
                if g[0] == "box":
                    b = g[1]
                    return b[2] >= x0 and b[0] <= x1 and b[3] >= y0 and b[1] <= y1
                return max(g[1][0], g[2][0]) >= x0 and min(g[1][0], g[2][0]) <= x1 and \
                    max(g[1][1], g[2][1]) >= y0 and min(g[1][1], g[2][1]) <= y1
            _cache[layer] = [it for it in _items(layer) if near(it[3])]
        return _cache[layer]
    return _items(layer)


def _items(layer):
    for p in D["pads"]:
        on = {"T": ["F"], "B": ["B"]}.get(p["side"], ["F", "L3", "B"])
        if layer in on:
            yield ("pad", f"{p['ref']}.{p['num']}", nm(p["net"]), ("box", p["box"]))
    for t in D["tracks"]:
        if t["layer"] == layer:
            yield ("trk", "", nm(t["net"]), ("seg", t["a"], t["b"], t["w"] / 2))
    for v in D["vias"]:
        yield ("via", "", nm(v["net"]), ("seg", v["c"], v["c"], v["d"] / 2))


def check(layer, net, a, b, r):
    out = []
    for kind, ref, n, g in items(layer):
        if n == net:
            continue
        if g[0] == "box":
            d = box_seg(g[1], a, b) - r
            where = f"{ref}"
        else:
            d = seg_seg(a, b, g[1], g[2]) - r - g[3]
            where = f"{kind}({g[1][0]:.2f},{g[1][1]:.2f})" + (f"-({g[2][0]:.2f},{g[2][1]:.2f})" if kind == "trk" else "")
        if d < CLR:
            out.append(f"  {layer} {n} {where} gap {d:.3f}")
    return out


def via_probs(net, c):
    probs = []
    for ly in ("F", "L3", "B"):
        probs += check(ly, net, c, c, 0.2)
    for v in D["vias"]:
        n = nm(v["net"])
        if n != net and n != "GND" and net != "GND" and math.dist(v["c"], c) < 0.9:
            probs.append(f"  pitch {n} via({v['c'][0]:.2f},{v['c'][1]:.2f}) {math.dist(v['c'], c):.2f}")
    e = min(c[0], c[1], W - c[0], H - c[1]) - 0.2
    if e < 0.3:
        probs.append(f"  edge {e:.2f}")
    return probs


for spec in sys.argv[2:]:
    parts = spec.split(":")
    kind, net = parts[0], parts[1]
    probs = []
    if kind == "scan":                       # scan:NET:x0,y0,x1,y1[:step] -> legal via spots
        bx = list(map(float, parts[2].split(",")))
        st = float(parts[3]) if len(parts) > 3 else 0.05
        CROP = (bx[0] - 1.5, bx[1] - 1.5, bx[2] + 1.5, bx[3] + 1.5)
        _cache.clear()
        ok = []
        y = bx[1]
        while y <= bx[3] + 1e-9:
            x = bx[0]
            while x <= bx[2] + 1e-9:
                if not via_probs(net, (x, y)):
                    ok.append((round(x, 2), round(y, 2)))
                x += st
            y += st
        print(spec, len(ok), "spots")
        # coarse map: one character per step, '+' legal
        ys = sorted({p[1] for p in ok})
        okset = set(ok)
        y = bx[1]
        while y <= bx[3] + 1e-9:
            row, x = "", bx[0]
            while x <= bx[2] + 1e-9:
                row += "+" if (round(x, 2), round(y, 2)) in okset else "."
                x += st
            print(f"  {y:6.2f} {row}")
            y += st
        print(f"  x from {bx[0]} step {st}")
        CROP = None
        _cache.clear()
        continue
    if kind == "via":
        c = tuple(map(float, parts[2].split(",")))
        for ly in ("F", "L3", "B"):
            probs += check(ly, net, c, c, 0.2)
        for v in D["vias"]:
            n = nm(v["net"])
            if n != net and n != "GND" and net != "GND" and math.dist(v["c"], c) < 0.9:
                probs.append(f"  pitch {n} via({v['c'][0]:.2f},{v['c'][1]:.2f}) {math.dist(v['c'], c):.2f}")
        e = min(c[0], c[1], W - c[0], H - c[1]) - 0.2
        if e < 0.3:
            probs.append(f"  edge {e:.2f}")
    else:
        pts = [tuple(map(float, q.split(","))) for q in parts[2].split(";")]
        w = float(parts[3]) if len(parts) > 3 else 0.15
        for a, b in zip(pts, pts[1:]):
            probs += check(kind, net, a, b, w / 2)
    print(spec, "OK" if not probs else "")
    for p in dict.fromkeys(probs):
        print(p)
