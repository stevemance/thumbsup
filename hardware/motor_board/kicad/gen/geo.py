"""Clearance checks for hand-planned geometry (before DRC): pads as rectangles, tracks as capsules, vias as discs.
Used by route_blocks.py generators to pick legal spots; DRC stays the final word."""
import math

CU = ("F.Cu", "In2.Cu", "In3.Cu", "B.Cu")


def seg_pt(a, b, p):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L2 = dx * dx + dy * dy
    u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - ax - u * dx, p[1] - ay - u * dy)


def seg_seg(a, b, c, d):
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    if (cross(a, b, c) * cross(a, b, d) < 0) and (cross(c, d, a) * cross(c, d, b) < 0):
        return 0.0
    return min(seg_pt(a, b, c), seg_pt(a, b, d), seg_pt(c, d, a), seg_pt(c, d, b))


def rect_seg(box, a, b):
    x0, y0, x1, y1 = box
    if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
        return 0.0
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    return min(seg_seg(a, b, e0, e1) for e0, e1 in edges)


class Space:
    """Copper already on the board, per layer.  Items: ('rect', box, net) | ('cap', a, b, r, net)."""

    def __init__(self, geom, clr=0.15):
        self.clr = clr
        self.items = {l: [] for l in CU}
        self.holes = []                                             # (x, y, drill/2)
        for p in geom["pads"]:
            for l in p["layers"]:
                if l in CU:
                    self.items[l].append(("rect", tuple(p["box"]), p["net"]))
            if p.get("drill"):
                self.holes.append((p["c"][0], p["c"][1], p["drill"] / 2))
        for t in geom["tracks"]:
            if t["layer"] in CU:
                self.items[t["layer"]].append(("cap", tuple(t["a"]), tuple(t["b"]), t["w"] / 2, t["net"]))
        for v in geom["vias"]:
            self.add_via(v["c"], v["d"], v.get("drill", 0.3), v["net"])

    def add_via(self, c, d, drill, net):
        for l in CU:
            self.items[l].append(("cap", tuple(c), tuple(c), d / 2, net))
        self.holes.append((c[0], c[1], drill / 2))

    def add_track(self, pts, w, layer, net):
        for a, b in zip(pts, pts[1:]):
            self.items[layer].append(("cap", tuple(a), tuple(b), w / 2, net))

    def seg_ok(self, a, b, r, layer, net, clr=None):
        clr = self.clr if clr is None else clr
        for it in self.items[layer]:
            if it[-1] == net:
                continue
            if it[0] == "rect":
                if rect_seg(it[1], a, b) < r + clr:
                    return False
            elif seg_seg(a, b, it[1], it[2]) < r + it[3] + clr:
                return False
        return True

    def via_ok(self, c, d, drill, net, hole_clr=0.25):
        if any(math.hypot(c[0] - x, c[1] - y) < drill / 2 + h + hole_clr for x, y, h in self.holes):
            return False
        return all(self.seg_ok(c, c, d / 2, l, net) for l in CU)

    def track_ok(self, pts, w, layer, net):
        return all(self.seg_ok(a, b, w / 2, layer, net) for a, b in zip(pts, pts[1:]))
