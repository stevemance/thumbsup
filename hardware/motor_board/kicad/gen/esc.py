"""Escape finder: for a pad, the nearest legal via spots reachable by a straight stub (or one bend) on the pad's
own layer, on the fully built board (geom.json + every routed track/via in routes.json).

    python3 esc.py REF PIN [rmax] [n]

Prints candidates as  via (x, y)  stub [...]  (distance): ready to paste into a fixed block.  Checks copper on
all four signal layers and hole spacing (geo.Space); pours are ignored (they clear around a via), DRC stays final."""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo import Space  # noqa: E402

HERE = Path(__file__).resolve().parent
# REF PIN [rmax] [n], or REF.PIN,REF.PIN,... [rmax] [n] for several pads in one run (the model loads once)
if "." in sys.argv[1]:
    PADS = [tuple(x.split(".")) for x in sys.argv[1].split(",")]
    rest = sys.argv[2:]
else:
    PADS = [(sys.argv[1], sys.argv[2])]
    rest = sys.argv[3:]
rmax = float(rest[0]) if rest else 2.0
nshow = int(rest[1]) if len(rest) > 1 else 6
g = json.load(open(HERE / "out" / "route" / "geom.json"))
sp = Space(g)
for r in json.load(open(HERE / "out" / "route" / "routes.json")):
    if r.get("ok"):
        for t in r["tracks"]:
            sp.add_track(t["pts"], t["w"], t["layer"], t["net"])
        for v in r["vias"]:
            sp.add_via(v["c"], v["d"], v.get("drill", 0.2), v["net"])
SMD = [q for q in g["pads"] if not q["tht"]]
for ref, pin in PADS:
    pad = [p for p in g["pads"] if p["ref"] == ref and p["num"] == pin][0]
    net, lay = pad["net"], pad["layers"][0]
    cx, cy = pad["c"]
    x0, y0, x1, y1 = pad["box"]
    w = 0.15
    # stub starts: the pad centre and the middles of its four edges
    starts = [(cx, cy), ((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1), (x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2)]
    found = []
    step = 0.05
    n = int(rmax / step)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            vx, vy = round(cx + i * step, 3), round(cy + j * step, 3)
            d = math.hypot(vx - cx, vy - cy)
            if d > rmax or d < 0.3:
                continue
            if not sp.via_ok((vx, vy), 0.4, 0.2, net):
                continue
            if any(not q["tht"] and q["box"][0] - 0.2 < vx < q["box"][2] + 0.2 and q["box"][1] - 0.2 < vy < q["box"][3] + 0.2
                   for q in SMD):                              # no via in (or touching) any SMD pad, own net included
                continue
            best = None
            for s in starts:
                for path in ([s, (vx, vy)], [s, (s[0], vy), (vx, vy)], [s, (vx, s[1]), (vx, vy)]):
                    pts = [p for k, p in enumerate(path) if k == 0 or p != path[k - 1]]
                    if sp.track_ok(pts, w, lay, net):
                        L = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
                        if best is None or L < best[0]:
                            best = (L, pts)
            if best:
                found.append((best[0], (vx, vy), best[1]))
    found.sort()
    seen = []
    for L, v, pts in found:
        if any(math.dist(v, s) < 0.3 for s in seen):
            continue
        seen.append(v)
        print(f"via ({v[0]}, {v[1]})  stub {[tuple(round(c, 3) for c in p) for p in pts]}  ({L:.2f} mm) on {lay} [{net}]")
        if len(seen) >= nshow:
            break
    if not found:
        print(f"no escape within {rmax} mm for {ref}.{pin} [{net}] on {lay}")
