"""Move a block of the board (both sides, parts + copper + rule-area vertices) by DX along x, inside the board: the
generalisation of grow.py for spreading a packed area into a sparse one.

/usr/bin/python3 blockmove.py <in.kicad_pcb> <out.kicad_pcb> <reroute.json> [spec.json]

The block is a set of rows (y0, y1, x_west, x_east); a part belongs to it by its origin (IN / OUT override).
Track segments crossing the block edge:
  - the west edge (vertical): a horizontal bridge of length DX (as grow.py);
  - an east edge (vertical) with the outside end far enough east: the inside end moves (the run gets shorter);
  - anything else (north / step edges, short east runs): removed and listed for re-routing.
The strip the block moves into must be clear of parts outside the block (checked, listed)."""
import json
import sys

import pcbnew

src, dst, rer = sys.argv[1:4]
spec = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else {}
DX = spec.get("dx", 5.0)
ROWS = spec.get("rows", [(13.5, 18.9, 28.4, 39.7), (18.9, 28.5, 28.4, 49.4), (28.5, 36.0, 28.4, 45.45)])
IN, OUT = set(spec.get("in", [])), set(spec.get("out", []))

b = pcbnew.LoadBoard(src)
t, F = pcbnew.ToMM, pcbnew.FromMM
bb = b.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
SH = pcbnew.VECTOR2I(F(DX), 0)


def loc(p):
    return (t(p.x) - OX, t(p.y) - OY)


def row_of(y):
    for r in ROWS:
        if r[0] <= y < r[1]:
            return r
    return None


def inside(pt):
    x, y = pt
    r = row_of(y)
    return r is not None and r[2] < x < r[3]


fin = {}
for f in b.GetFootprints():
    r = f.GetReference()
    fin[r] = r in IN or (r not in OUT and inside(loc(f.GetPosition())))
pad_in = [(p, fin[f.GetReference()]) for f in b.GetFootprints() for p in f.Pads()]
vias = [x for x in b.GetTracks() if x.GetClass() == "PCB_VIA"]
via_in = {id(v): inside(loc(v.GetPosition())) for v in vias}


def ep_in(p, layer):
    for v in vias:
        if (v.GetPosition() - p).EuclideanNorm() < F(0.02):
            return via_in[id(v)]
    for pad, e in pad_in:
        if pad.IsOnLayer(layer) and pad.HitTest(p):
            return e
    return inside(loc(p))


# landing strip check: parts outside the block whose courtyard lies in the strip the block moves into
blockers = []
for f in b.GetFootprints():
    if fin[f.GetReference()]:
        continue
    c = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
    r_ = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False, False)
    x0, y0, x1, y1 = t(r_.GetLeft()) - OX, t(r_.GetTop()) - OY, t(r_.GetRight()) - OX, t(r_.GetBottom()) - OY
    for ry0, ry1, xw, xe in ROWS:
        if y0 < ry1 and y1 > ry0 and x0 < xe + DX and x1 > xe:
            blockers.append(f.GetReference())
            break

segs = [x for x in b.GetTracks() if x.GetClass() == "PCB_TRACK"]
plan = [(s, ep_in(s.GetStart(), s.GetLayer()), ep_in(s.GetEnd(), s.GetLayer())) for s in segs]
for f in b.GetFootprints():
    if fin[f.GetReference()]:
        f.Move(SH)
for v in vias:
    if via_in[id(v)]:
        v.Move(SH)

removed, bridged, shrunk = [], 0, 0
for s, ea, ec in plan:
    if ea and ec:
        s.Move(SH)
        continue
    if not ea and not ec:
        continue
    a, c = s.GetStart(), s.GetEnd()
    pin, pout = (loc(a), loc(c)) if ea else (loc(c), loc(a))
    done = False
    # west edge: the outside end is west of the block, the crossing is on a row's west x
    if pout[0] < pin[0]:
        for ry0, ry1, xw, xe in ROWS:
            if pout[0] <= xw <= pin[0]:
                u = (xw - pout[0]) / (pin[0] - pout[0])
                yc = pout[1] + u * (pin[1] - pout[1])
                if ry0 + 0.05 < yc < ry1 - 0.05:
                    P = pcbnew.VECTOR2I(F(xw + OX), F(yc + OY))
                    Pin = pcbnew.VECTOR2I(F(pin[0] + DX + OX), F(pin[1] + OY))
                    Pout = pcbnew.VECTOR2I(F(pout[0] + OX), F(pout[1] + OY))
                    s.SetStart(Pout); s.SetEnd(P)
                    for q0, q1 in ((P, P + SH), (P + SH, Pin)):
                        n = pcbnew.PCB_TRACK(b)
                        n.SetStart(q0); n.SetEnd(q1); n.SetWidth(s.GetWidth()); n.SetLayer(s.GetLayer()); n.SetNet(s.GetNet())
                        b.Add(n)
                    bridged += 1
                    done = True
                    break
    # east edge: the outside end lies east of the moved inside end -> shorten
    elif pout[0] > pin[0] + DX + 0.3:
        for ry0, ry1, xw, xe in ROWS:
            if pin[0] <= xe <= pout[0]:
                u = (xe - pin[0]) / (pout[0] - pin[0])
                yc = pin[1] + u * (pout[1] - pin[1])
                if ry0 + 0.05 < yc < ry1 - 0.05:
                    Pin = pcbnew.VECTOR2I(F(pin[0] + DX + OX), F(pin[1] + OY))
                    if ea:
                        s.SetStart(Pin)
                    else:
                        s.SetEnd(Pin)
                    shrunk += 1
                    done = True
                    break
    if not done:
        removed.append(dict(net=s.GetNetname(), layer=b.GetLayerName(s.GetLayer()),
                            a=[round(x, 4) for x in (loc(a)[0] + (DX if ea else 0), loc(a)[1])],
                            b=[round(x, 4) for x in (loc(c)[0] + (DX if ec else 0), loc(c)[1])], w=round(t(s.GetWidth()), 3)))
        b.Remove(s)

# rule areas / zones: vertices inside the block move (board-wide pours have their vertices at the edges)
for z in b.Zones():
    ol = z.Outline()
    for i in range(ol.OutlineCount()):
        o = ol.Outline(i)
        for k in range(o.PointCount()):
            p = o.CPoint(k)
            if inside(loc(p)):
                o.SetPoint(k, p + SH)
for d in b.GetDrawings():
    if d.GetLayer() != pcbnew.Edge_Cuts and inside(loc(d.GetPosition())):
        d.Move(SH)

pcbnew.SaveBoard(dst, b)
json.dump(removed, open(rer, "w"), indent=0)
print(f"moved {sum(fin.values())} parts; bridged {bridged}, shortened {shrunk}, removed {len(removed)} segments "
      f"({len({r['net'] for r in removed})} nets); landing-strip blockers: {sorted(blockers)}")
