"""Apply the placement spec (placement_spec.py) to motor_board.kicad_pcb: new outline, every part moved,
checks, renders and a placement table.  Footprints (and their schematic links) are kept; only position, side
and rotation change.  Run with /usr/bin/python3 (KiCad's pcbnew).  Close KiCad first.

    /usr/bin/python3 place_v2.py          # place, check, save, render
    /usr/bin/python3 place_v2.py --dry    # place and check only
"""
import csv
import os
import importlib
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent / "motor_board"
PCB = PROJ / "motor_board.kicad_pcb"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(HERE))
S = importlib.import_module("placement_spec")

BW, BH, OX, OY = S.BW, S.BH, 100.0, 70.0
T, B = "T", "B"
t = pcbnew.ToMM
board = pcbnew.LoadBoard(str(PCB))
fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
RAILS = {"GND", "+3V3", "+5V", "+3V3A", "VBAT"}


def P(x, y):
    return pcbnew.VECTOR2I_MM(OX + x, OY + y)


# ---------------------------------------------------------------- outline
# board.Remove() on drawings breaks pcbnew's SWIG type table (KiCad 10.0.6), so the existing Edge.Cuts
# shapes are reused with new geometry (extras are parked on User.9).
old_edges = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]


def outline(r):
    geo = []
    for a, b in (((r, 0), (BW - r, 0)), ((BW, r), (BW, BH - r)), ((BW - r, BH), (r, BH)), ((0, BH - r), (0, r))):
        geo.append(("seg", a, b))
    for cx, cy, a0 in ((BW - r, r, 270), (BW - r, BH - r, 0), (r, BH - r, 90), (r, r, 180)):
        geo.append(("arc",) + tuple((cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in (a0, a0 + 45, a0 + 90)))
    for i, g in enumerate(geo):
        if i < len(old_edges):
            s = old_edges[i]
        else:
            s = pcbnew.PCB_SHAPE(board); board.Add(s)
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.1))
        if g[0] == "seg":
            s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(P(*g[1])); s.SetEnd(P(*g[2]))
        else:
            s.SetShape(pcbnew.SHAPE_T_ARC); s.SetArcGeometry(P(*g[1]), P(*g[2]), P(*g[3]))
    for s in old_edges[len(geo):]:
        s.SetLayer(pcbnew.User_9)


outline(S.CORNER_R)


# ---------------------------------------------------------------- geometry
def set_pose(fp, x, y, rot, side):
    if fp.IsFlipped() != (side == B):
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(P(x, y))


def court(fp):
    """courtyard bbox from the footprint's courtyard shapes (falls back to the pads' bbox + 0.25)."""
    layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    xs, ys = [], []
    for g in fp.GraphicalItems():
        if g.GetLayer() == layer:
            b = g.GetBoundingBox(); xs += [t(b.GetLeft()), t(b.GetRight())]; ys += [t(b.GetTop()), t(b.GetBottom())]
    if xs:
        w = 0.025          # the courtyard line half-width is included in the shape bbox; remove it
        return min(xs) - OX + w, min(ys) - OY + w, max(xs) - OX - w, max(ys) - OY - w
    for p in fp.Pads():
        b = p.GetBoundingBox(); xs += [t(b.GetLeft()), t(b.GetRight())]; ys += [t(b.GetTop()), t(b.GetBottom())]
    return min(xs) - OX - 0.25, min(ys) - OY - 0.25, max(xs) - OX + 0.25, max(ys) - OY + 0.25


def tht_clear(ref):
    for pre, mm in S.THT_CLEAR.items():
        if ref.startswith(pre):
            return mm
    return 0.3


def through_rect(fp, side=B):
    """what a through-hole part blocks: its drilled pads' bbox + the soldering clearance.  Wires and J4's pins
    come in from the top and are soldered on the BOTTOM (the side facing the compute board, before stacking), so
    the full S.THT_CLEAR (iron tip + fillet) applies there and a 1.0 mm mask-protected margin on the top.
    Mounting holes block their whole courtyard (washer / standoff) on both sides."""
    ref = fp.GetReference()
    if ref.startswith("MH"):
        c = court(fp)
        return c[0] - 0.2, c[1] - 0.2, c[2] + 0.2, c[3] + 0.2
    xs, ys = [], []
    for p in fp.Pads():
        if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
            b = p.GetBoundingBox(); xs += [t(b.GetLeft()), t(b.GetRight())]; ys += [t(b.GetTop()), t(b.GetBottom())]
    if not xs:
        return None
    m = tht_clear(ref) if side == B else min(1.0, tht_clear(ref))
    return min(xs) - OX - m, min(ys) - OY - m, max(xs) - OX + m, max(ys) - OY + m


def box_hit(pad, r):
    b = pad.GetBoundingBox()
    x0, y0, x1, y1 = t(b.GetLeft()) - OX, t(b.GetTop()) - OY, t(b.GetRight()) - OX, t(b.GetBottom()) - OY
    return x0 < r[2] and r[0] < x1 and y0 < r[3] and r[1] < y1


def is_tht(fp):
    return any(p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) for p in fp.Pads())


def pad_xy(ref, num=None):
    return [(t(p.GetPosition().x) - OX, t(p.GetPosition().y) - OY) for p in fps[ref].Pads() if num is None or p.GetNumber() == num]


def centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


occ = {T: [], B: []}
placed, why, rule_of, anchor_dist = {}, {}, {}, {}


def occupy(ref):
    fp = fps[ref]
    side = B if fp.IsFlipped() else T
    occ[side].append((court(fp), ref))
    if through_rect(fp):
        occ[T].append((through_rect(fp, T), ref + " solder zone"))
        occ[B].append((through_rect(fp, B), ref + " solder zone"))


def ep_rect(ref, margin):
    """the exposed (largest) pad of an IC + margin: the thermal-via field that the other side must leave free."""
    p = max(fps[ref].Pads(), key=lambda p: t(p.GetBoundingBox().GetWidth()) * t(p.GetBoundingBox().GetHeight()))
    b = p.GetBoundingBox()
    return t(b.GetLeft()) - OX - margin, t(b.GetTop()) - OY - margin, t(b.GetRight()) - OX + margin, t(b.GetBottom()) - OY + margin


def overlaps(r, side, gap):
    x0, y0, x1, y1 = r
    for (a0, b0, a1, b1), who in occ[side]:
        if x0 < a1 + gap and a0 < x1 + gap and y0 < b1 + gap and b0 < y1 + gap:
            return who
    return None


def inside(r, edge):
    return r[0] >= edge and r[1] >= edge and r[2] <= BW - edge and r[3] <= BH - edge


# ---------------------------------------------------------------- explicit parts
problems = []
EXPLICIT_REFS = set(S.EXPLICIT)
for ref, (x, y, rot, side, text) in S.EXPLICIT.items():
    fp = fps[ref]
    set_pose(fp, x, y, rot, side)
    cx0, cy0, cx1, cy1 = court(fp)                   # (x, y) is the courtyard centre
    dx, dy = x - (cx0 + cx1) / 2, y - (cy0 + cy1) / 2
    pos = fp.GetPosition()
    fp.SetPosition(pcbnew.VECTOR2I(pos.x + pcbnew.FromMM(dx), pos.y + pcbnew.FromMM(dy)))
    r = court(fp)
    who = None
    for (a0, b0, a1, b1), w in occ[B if side == B else T]:
        if not (r[0] < a1 and a0 < r[2] and r[1] < b1 and b0 < r[3]):
            continue
        if w.endswith("solder zone"):
            hole = fps[w.split()[0]]
            if is_tht(fp):
                continue                  # hole next to hole: soldered one at a time
            hole_nets = {p.GetNetname() for p in hole.Pads()}
            if not any(p.GetNetname() and p.GetNetname() not in hole_nets and box_hit(p, (a0, b0, a1, b1)) for p in fp.Pads()):
                continue                  # only same-net copper (e.g. Q7's drain tab at JBAT1) inside the zone
        who = w
        break
    if not who and through_rect(fp):
        for sd in (T, B):
            tr = through_rect(fp, sd)
            for (a0, b0, a1, b1), w in occ[sd]:
                if w.split()[0] not in fps:
                    continue
                if tr[0] < a1 and a0 < tr[2] and tr[1] < b1 and b0 < tr[3] and not is_tht(fps[w.split()[0]]):
                    tn = {p.GetNetname() for p in fp.Pads()}
                    if any(q.GetNetname() and q.GetNetname() not in tn and box_hit(q, tr) for q in fps[w.split()[0]].Pads()):
                        who = w + f" ({sd})"
    if who:
        problems.append(f"{ref}: courtyard overlaps {who}")
    if not inside(r, 0.0) and ref not in S.EDGE_OK:
        problems.append(f"{ref}: courtyard outside the board {tuple(round(v, 2) for v in r)}")
    placed[ref] = True
    why[ref] = text
    rule_of[ref] = "explicit"
    occupy(ref)

# ---------------------------------------------------------------- keep-outs for the anchored parts
for ref, side, margin, why_k in S.EP_KEEPOUT:
    r = ep_rect(ref, margin)
    occ[side].append((r, f"{ref} thermal-via field"))
    for (a0, b0, a1, b1), who in list(occ[side]):
        if who in EXPLICIT_REFS and side == (B if fps[who].IsFlipped() else T) and a0 < r[2] and r[0] < a1 and b0 < r[3] and r[1] < b1:
            problems.append(f"{who}: explicit part inside {ref}'s thermal-via field")
for (x0, y0, x1, y1), side, name in S.KEEPOUT:
    occ[side].append(((x0, y0, x1, y1), name))
    for (a0, b0, a1, b1), who in list(occ[side]):
        if who in EXPLICIT_REFS and a0 < x1 and x0 < a1 and b0 < y1 and y0 < b1 and fps[who].IsFlipped() == (side == B):
            problems.append(f"{who}: explicit part inside keep-out '{name}'")

# ---------------------------------------------------------------- anchored parts
GRID = 0.25
OFFS = sorted(((i * GRID, j * GRID) for i in range(-100, 101) for j in range(-100, 101)), key=lambda d: d[0] ** 2 + d[1] ** 2)


def anchor_point(a):
    if isinstance(a, tuple) and isinstance(a[0], (int, float)):
        return a
    if isinstance(a, tuple):
        return centroid(pad_xy(*a))
    return centroid(pad_xy(a))


def orient_cost(ref):
    """sum over this part's signal pads of the distance to the nearest placed pad on the same net."""
    cost = 0.0
    for p in fps[ref].Pads():
        n = p.GetNetname().split("/")[-1]
        if not n or n in RAILS or n.startswith("unconnected"):
            continue
        px, py = t(p.GetPosition().x) - OX, t(p.GetPosition().y) - OY
        best = None
        for r2 in placed:
            for q in fps[r2].Pads():
                if q.GetNetname() == p.GetNetname():
                    d = math.hypot(px - t(q.GetPosition().x) + OX, py - t(q.GetPosition().y) + OY)
                    best = d if best is None or d < best else best
        cost += best or 0.0
    return cost


def served_pad_dist(ref, anchor):
    """distance from this part's pad on the anchor pad's net to the anchor pad (None if the anchor is not a pad)."""
    if not (isinstance(anchor, tuple) and isinstance(anchor[0], str)):
        return None
    aref, anum = anchor
    ap = [p for p in fps[aref].Pads() if p.GetNumber() == anum][0]
    mine = [p for p in fps[ref].Pads() if p.GetNetname() == ap.GetNetname()]
    if not mine:
        return None
    ax, ay = t(ap.GetPosition().x), t(ap.GetPosition().y)
    return min(math.hypot(t(p.GetPosition().x) - ax, t(p.GetPosition().y) - ay) for p in mine)


CANDIDATES = 60          # free spots examined per rotation (nearest first)
FLEX = ("0805", "1206", "2512")   # DESIGN 6.10: parallel to the nearest board edge, >= 3 mm from the mounting holes
HOLES = [court(fps[r]) for r in fps if r.startswith("MH")]


def flex_ok(fp, rot, r):
    if not any(k in fp.GetFPIDAsString() for k in FLEX):
        return True
    cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
    nearest = min((cy, "x"), (BH - cy, "x"), (cx, "y"), (BW - cx, "y"))[1]   # front/rear edge -> run along x
    along = "x" if round(rot) % 180 == 0 else "y"
    if along != nearest:
        return False
    for h in HOLES:                       # MH courtyard is the 5 mm circle's box: hole edge = courtyard - 1.4 mm
        hole = (h[0] + 1.4, h[1] + 1.4, h[2] - 1.4, h[3] - 1.4)
        if r[0] < hole[2] + 3.0 and hole[0] < r[2] + 3.0 and r[1] < hole[3] + 3.0 and hole[1] < r[3] + 3.0:
            return False
    return True

for ref, side, anchor, rots, text in S.ANCHORED:
    fp = fps[ref]
    tx, ty = anchor_point(anchor)
    best = None
    for rot in rots:
        set_pose(fp, 0, 0, rot, side)
        cx0, cy0, cx1, cy1 = court(fp)
        w, h = cx1 - cx0, cy1 - cy0
        ox, oy = (cx0 + cx1) / 2, (cy0 + cy1) / 2
        seen = 0
        for dx, dy in OFFS:
            x, y = tx + dx, ty + dy
            r = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
            if not inside(r, S.EDGE):
                continue
            if overlaps(r, side, S.GAP):
                continue
            if is_tht(fp) and overlaps(r, B if side == T else T, S.GAP):
                continue
            if not flex_ok(fp, rot, r):
                continue
            set_pose(fp, x - ox, y - oy, rot, side)
            sp = served_pad_dist(ref, anchor)
            # the pad that serves the anchor pin as close as possible; then compactness and the other nets
            cost = (sp if sp is not None else math.hypot(dx, dy)) + 0.2 * math.hypot(dx, dy) + 0.1 * orient_cost(ref)
            if best is None or cost < best[0]:
                best = (cost, rot, x - ox, y - oy)
            seen += 1
            if seen >= CANDIDATES:
                break
    if best is None:
        if os.environ.get("DEBUG_REF") == ref:
            import collections
            why_not = collections.Counter()
            for rot in rots:
                set_pose(fp, 0, 0, rot, side); c0 = court(fp); w, h = c0[2] - c0[0], c0[3] - c0[1]
                for dx, dy in OFFS[:4000]:
                    r = (tx + dx - w / 2, ty + dy - h / 2, tx + dx + w / 2, ty + dy + h / 2)
                    why_not["edge" if not inside(r, S.EDGE) else (overlaps(r, side, S.GAP) or ("flex" if not flex_ok(fp, rot, r) else "ok"))] += 1
            print(ref, "blocked by", why_not.most_common(8))
        problems.append(f"{ref}: no free spot near its anchor")
        continue
    _, rot, x, y = best
    set_pose(fp, round(x / 0.05) * 0.05, round(y / 0.05) * 0.05, rot, side)
    placed[ref] = True
    why[ref] = text
    rule_of[ref] = "near " + (anchor if isinstance(anchor, str) else ".".join(map(str, anchor)))
    anchor_dist[ref] = min(math.hypot(px - tx, py - ty) for px, py in pad_xy(ref))
    occupy(ref)

missing = sorted(set(fps) - set(placed), key=lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r) or 0)))
if missing:
    problems.append(f"not placed ({len(missing)}): {missing}")

# ---------------------------------------------------------------- report
area = {T: 0.0, B: 0.0}
for fp in fps.values():          # part courtyards only (keep-outs and solder zones are not parts)
    c = court(fp)
    a = (c[2] - c[0]) * (c[3] - c[1])
    area[B if fp.IsFlipped() else T] += a
    if is_tht(fp):
        area[T if fp.IsFlipped() else B] += a if fp.GetReference().startswith("MH") else 0.0
print(f"board {BW} x {BH} = {BW * BH:.0f} mm2; courtyard use top {area[T]:.0f} ({100 * area[T] / (BW * BH):.0f} %), "
      f"bottom {area[B]:.0f} ({100 * area[B] / (BW * BH):.0f} %)")
for p in problems:
    print("PROBLEM:", p)
rows = []
for ref, fp in fps.items():
    pos = fp.GetPosition()
    rows.append(dict(ref=ref, side="bottom" if fp.IsFlipped() else "top", x=round(t(pos.x) - OX, 2), y=round(t(pos.y) - OY, 2),
                     rot=round(fp.GetOrientationDegrees()), value=fp.GetValue(), rule=rule_of.get(ref, ""),
                     anchor_mm=round(anchor_dist[ref], 2) if ref in anchor_dist else "", why=why.get(ref, "")))
rows.sort(key=lambda r: (re.sub(r"\d", "", r["ref"]), int(re.sub(r"\D", "", r["ref"]) or 0)))
with open(OUT / "placement_v2.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
if "--dry" in sys.argv:
    sys.exit(0)
bak = OUT / "motor_board.kicad_pcb.before_v2"
if not bak.exists():
    shutil.copy(PCB, bak)
pro = (PROJ / "motor_board.kicad_pro").read_text()
pcbnew.SaveBoard(str(PCB), board)
(PROJ / "motor_board.kicad_pro").write_text(pro)          # SaveBoard rewrites the project file; keep ours
for side, layers in (("top", "F.Cu,F.SilkS,F.CrtYd,Edge.Cuts"), ("bottom", "B.Cu,B.SilkS,B.CrtYd,Edge.Cuts")):
    subprocess.run(["kicad-cli", "pcb", "export", "svg", "--layers", layers, "--mode-single", "--fit-page-to-board",
                    "--exclude-drawing-sheet", "-o", str(OUT / f"v2_{side}.svg"), str(PCB)], capture_output=True)
print("saved; renders in", OUT)
