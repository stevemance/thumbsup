"""Stitch requests for the islands of the "L4 3V3 fill": a spanning tree over the islands (nearest points first),
each edge a route between points just inside the two islands (the router may hop layers across the signal
tracks that split the fill).  Input: a dump of the filled islands (l4dump in tail_log); returns route edits."""
import json
import math
from pathlib import Path


def inside(poly, p):
    x, y = p; c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def area(p):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(p, p[1:] + p[:1]))) / 2


def stitch(dump, min_area=0.5, max_gap=4.0, inset=0.9, w=0.2, per_pair=1, spread=2.0, tree=True, **kw):
    dump = Path(__file__).resolve().parent / "tail_log" / dump
    isl = [p for p in json.load(open(dump))["isl"] if area(p) >= min_area]
    pairs = []
    for i in range(len(isl)):
        for j in range(i + 1, len(isl)):
            cand = sorted((math.dist(a, c), a, c) for a in isl[i][::2] for c in isl[j][::2])
            got = []
            for q in cand:
                if q[0] > max_gap or len(got) >= per_pair:
                    break
                if all(math.dist(q[1], g[1]) > spread for g in got):
                    got.append(q)
            pairs += [(q[0], i, j, q[1], q[2]) for q in got]
    par = list(range(len(isl)))

    def root(k):
        while par[k] != k:
            k = par[k]
        return k
    out = []
    for d, i, j, a, c in sorted(pairs):
        if tree and root(i) == root(j):
            continue
        ux, uy = (c[0] - a[0]) / max(d, 1e-6), (c[1] - a[1]) / max(d, 1e-6)
        pa, pc = (a[0] - ux * inset, a[1] - uy * inset), (c[0] + ux * inset, c[1] + uy * inset)
        if not (inside(isl[i], pa) and inside(isl[j], pc)):
            continue
        par[root(i)] = root(j)
        out.append(dict(dict(op="route", net="+3V3", a=("pt", round(pa[0], 3), round(pa[1], 3), "In3.Cu"),
                             b=("pt", round(pc[0], 3), round(pc[1], 3), "In3.Cu"), w=w, margin=3.0,
                             tag=f"stitch L4 {i}-{j} ({d:.1f} mm)"), **kw))
    return out
