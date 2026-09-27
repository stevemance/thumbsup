"""Grow the board along x: everything east of a stepped cut line moves +DX; tracks crossing a vertical part of the cut
get a horizontal bridge, the rest that cross (at a step, or tied to a part on the other side) are removed and listed
for re-routing.  Pours, rule areas, the outline and board graphics stretch (vertices east of the cut move).

/usr/bin/python3 grow.py <in.kicad_pcb> <out.kicad_pcb> <reroute.json>

The cut and the side overrides below are the design; see ROUTING_PLAN.md (board growth, 2026-09-28)."""
import json
import sys

import pcbnew

DX = 10.0
# cut x as a function of y (board-local mm): (y_from, y_to, x) pieces, top to bottom
CUT = [(-1.0, 13.12, 47.95),     # between weapon cells C and B (their pours: C <= 47.85, B >= 48.1)
       (13.12, 18.8, 47.13),     # C shunt / cap GND <= 47.1, B LS source + RS2 >= 47.16
       (18.8, 27.2, 49.3),       # U2 (>= 49.32) east; C23 / R44 / R45 / C22 / JP2 / C48 west
       (27.2, 36.0, 45.13)]      # buck (L1, C28-C30, D2) east with U2; U1's cluster west
EAST = {"L1", "C28", "C29", "C30", "D2", "U12", "C49", "C410", "R57", "R58", "R43", "R24", "R25", "Q4", "RS2"}
WEST = {"R53", "C73", "TP11", "C48", "JP2", "Q5", "C31", "TP7"}

src, dst, rer = sys.argv[1:4]
b = pcbnew.LoadBoard(src)
t, F = pcbnew.ToMM, pcbnew.FromMM
bb = b.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
SH = pcbnew.VECTOR2I(F(DX), 0)


def cut(y):
    for y0, y1, x in CUT:
        if y0 <= y < y1:
            return x
    return CUT[-1][2]


def loc(p):
    return (t(p.x) - OX, t(p.y) - OY)


def east_pt(p):
    x, y = loc(p)
    return x > cut(y)


# 1. footprints
fside = {}
for f in b.GetFootprints():
    r = f.GetReference()
    e = r in EAST or (r not in WEST and east_pt(f.GetPosition()))
    fside[r] = e
pad_side = []                    # (pad, east?) for endpoint classification, before moving anything
for f in b.GetFootprints():
    for p in f.Pads():
        pad_side.append((p, fside[f.GetReference()]))

# 2. classify track endpoints and vias against the ORIGINAL geometry
vias = [x for x in b.GetTracks() if x.GetClass() == "PCB_VIA"]
via_e = {id(v): east_pt(v.GetPosition()) for v in vias}


def ep_side(p, layer):
    for v in vias:
        if (v.GetPosition() - p).EuclideanNorm() < F(0.02):
            return via_e[id(v)]
    for pad, e in pad_side:
        if pad.IsOnLayer(layer) and pad.HitTest(p):
            return e
    return east_pt(p)


segs = [x for x in b.GetTracks() if x.GetClass() == "PCB_TRACK"]
plan = []
for s in segs:
    a, c = s.GetStart(), s.GetEnd()
    ea, ec = ep_side(a, s.GetLayer()), ep_side(c, s.GetLayer())
    plan.append((s, ea, ec))

# 3. move footprints
for f in b.GetFootprints():
    if fside[f.GetReference()]:
        f.Move(SH)
for v in vias:
    if via_e[id(v)]:
        v.Move(SH)

# 4. tracks
removed, bridged = [], 0
for s, ea, ec in plan:
    a, c = s.GetStart(), s.GetEnd()
    if ea and ec:
        s.Move(SH)
        continue
    if not ea and not ec:
        continue
    # mixed: bridge if the segment crosses a vertical piece of the cut with the west end west of it
    (ax, ay), (cx, cy) = loc(a), loc(c)
    w_pt, e_pt = ((ax, ay), (cx, cy)) if not ea else ((cx, cy), (ax, ay))
    ok = False
    for y0, y1, xc in CUT:
        if w_pt[0] <= xc <= e_pt[0] and e_pt[0] > w_pt[0]:
            u = (xc - w_pt[0]) / (e_pt[0] - w_pt[0])
            yc = w_pt[1] + u * (e_pt[1] - w_pt[1])
            if y0 + 0.05 < yc < y1 - 0.05:
                ok = True
                break
    if not ok:
        removed.append(dict(net=s.GetNetname(), layer=b.GetLayerName(s.GetLayer()),
                            a=[round(ax + (DX if ea else 0), 4), round(ay, 4)],
                            b=[round(cx + (DX if ec else 0), 4), round(cy, 4)], w=round(t(s.GetWidth()), 3)))
        b.Remove(s)
        continue
    P = pcbnew.VECTOR2I(F(xc + OX), F(yc + OY))
    Pe = P + SH
    wpt = pcbnew.VECTOR2I(F(w_pt[0] + OX), F(w_pt[1] + OY))
    ept = pcbnew.VECTOR2I(F(e_pt[0] + OX + DX), F(e_pt[1] + OY))
    s.SetStart(wpt); s.SetEnd(P)
    for q0, q1 in ((P, Pe), (Pe, ept)):
        n = pcbnew.PCB_TRACK(b)
        n.SetStart(q0); n.SetEnd(q1); n.SetWidth(s.GetWidth()); n.SetLayer(s.GetLayer()); n.SetNet(s.GetNet())
        b.Add(n)
    bridged += 1

# 5. zones (incl. rule areas): stretch outline vertices east of the cut
for z in b.Zones():
    ol = z.Outline()
    for i in range(ol.OutlineCount()):
        o = ol.Outline(i)
        for k in range(o.PointCount()):
            p = o.CPoint(k)
            if east_pt(p):
                o.SetPoint(k, p + SH)
    z.UnFill() if hasattr(z, "UnFill") else None

# 6. board graphics (outline, silk on the board): stretch / move
for d in b.GetDrawings():
    if d.GetClass() in ("PCB_SHAPE",):
        if d.GetLayer() == pcbnew.Edge_Cuts:
            if d.GetShape() == pcbnew.SHAPE_T_ARC:           # corner arcs move whole
                if east_pt(d.GetStart()):
                    d.Move(SH)
            else:                                          # lines: each end on its side (the long edges stretch)
                p0, p1 = d.GetStart(), d.GetEnd()
                if east_pt(p0):
                    d.SetStart(p0 + SH)
                if east_pt(p1):
                    d.SetEnd(p1 + SH)
        elif east_pt(d.GetPosition()):
            d.Move(SH)
    elif east_pt(d.GetPosition()):
        d.Move(SH)

pcbnew.SaveBoard(dst, b)
json.dump(removed, open(rer, "w"), indent=0)
print(f"moved {sum(fside.values())} parts east, bridged {bridged} tracks, removed {len(removed)} segments "
      f"({len({r['net'] for r in removed})} nets) for re-routing")
