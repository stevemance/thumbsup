"""Free spots for re-placing a small part on the routed board (last build: geom.json + routes.json).
python3 spot.py REF SIDE x y [rmax] [rot]     SIDE F/B; rot 0 (pads along x) or 90; default: both rotations

A spot is free when the part's courtyard box (its current size, rotated) overlaps no other courtyard on that side and
no copper on that side's layer (pads, tracks, vias) other than its own pads' nets, with 0.15 mm clearance.  Reports
the nearest few by distance from (x, y)."""
import json
import math
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo import Space  # noqa: E402

HERE = Path(__file__).resolve().parent
OX, OY = 100.0, 70.0
ref, side = sys.argv[1], sys.argv[2]
tx, ty = float(sys.argv[3]), float(sys.argv[4])
rmax = float(sys.argv[5]) if len(sys.argv) > 5 else 6.0
rots = [int(sys.argv[6])] if len(sys.argv) > 6 else [0, 90]
layer = "F.Cu" if side == "F" else "B.Cu"

b = pcbnew.LoadBoard(str(HERE / "base" / "motor_board_base.kicad_pcb"))
boxes, me = [], None
for f in b.GetFootprints():
    fside = "B" if f.IsFlipped() else "F"
    try:
        bb = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd).BBox()
        box = [pcbnew.ToMM(bb.GetLeft()) - OX, pcbnew.ToMM(bb.GetTop()) - OY, pcbnew.ToMM(bb.GetRight()) - OX,
               pcbnew.ToMM(bb.GetBottom()) - OY]
        if box[2] - box[0] <= 0:
            raise ValueError
    except Exception:
        bb = f.GetBoundingBox(False, False)
        box = [pcbnew.ToMM(bb.GetLeft()) - OX, pcbnew.ToMM(bb.GetTop()) - OY, pcbnew.ToMM(bb.GetRight()) - OX,
               pcbnew.ToMM(bb.GetBottom()) - OY]
    if f.GetReference() == ref:
        me = (box, {p.GetNetname() for p in f.Pads()})
    elif fside == side:
        boxes.append(box)
assert me, ref
(bx0, by0, bx1, by1), mynets = me
w0, h0 = bx1 - bx0, by1 - by0

g = json.load(open(HERE / "out" / "route" / "geom.json"))
sp = Space(g)
for r in json.load(open(HERE / "out" / "route" / "routes.json")):
    if r.get("ok"):
        for t in r["tracks"]:
            sp.add_track(t["pts"], t["w"], t["layer"], t["net"])
        for v in r["vias"]:
            sp.add_via(v["c"], v["d"], v.get("drill", 0.2), v["net"])
mypads = [p for p in g["pads"] if p["ref"] == ref]


def free(cx, cy, w, h):
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    if x0 < 0.5 or y0 < 0.5 or x1 > 74.5 or y1 > 34.5:
        return False
    for q in boxes:
        if x0 < q[2] and q[0] < x1 and y0 < q[3] and q[1] < y1:
            return False
    # copper: probe the box with a fat "track" through its middle along the long axis, then its edges
    inset = 0.15
    pts = [(x0 + inset, y0 + inset), (x1 - inset, y0 + inset), (x1 - inset, y1 - inset), (x0 + inset, y1 - inset),
           (x0 + inset, y0 + inset)]
    for net in [n for n in mynets if n] or ["?"]:
        pass
    for a, c in zip(pts, pts[1:]):
        if not sp.track_ok([a, c], 0.3, layer, "__probe__"):
            return False
    mid = [(x0 + inset, (y0 + y1) / 2), (x1 - inset, (y0 + y1) / 2)] if w >= h else [((x0 + x1) / 2, y0 + inset), ((x0 + x1) / 2, y1 - inset)]
    return sp.track_ok(mid, min(w, h) - 0.3, layer, "__probe__")


found = []
step = 0.05
n = int(rmax / step)
cands = sorted(((i * step, j * step) for i in range(-n, n + 1) for j in range(-n, n + 1)), key=lambda o: o[0] ** 2 + o[1] ** 2)
for rot in rots:
    w, h = (w0, h0) if rot == 0 else (h0, w0)
    if abs(w0 - h0) < 0.01 and rot == 90:
        continue
    k = 0
    for dx, dy in cands:
        cx, cy = round(tx + dx, 2), round(ty + dy, 2)
        if free(cx, cy, w, h):
            found.append((math.hypot(dx, dy), rot, cx, cy))
            k += 1
            if k >= 4:
                break
for d, rot, cx, cy in sorted(found)[:8]:
    print(f"{ref} {side} rot{rot} centre ({cx:.2f},{cy:.2f})  {d:.2f} mm from target  (courtyard {w0:.2f}x{h0:.2f})")
if not found:
    print("no spot within", rmax)
