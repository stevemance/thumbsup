"""GND stitching (memo 3.4 / P3): a via next to every SMD GND pad that is not on an L1 GND pour, with a short stub to
the pad, so the pad reaches the L2 plane.  The via goes on the pad's outward side (away from the part centre) where it
clears every other-net pad, existing vias and tracks by the rules, and the thermal-via fields.
    /usr/bin/python3 gndvias.py <board.kicad_pcb> [out.kicad_pcb]"""
import math
import sys

import pcbnew

src = sys.argv[1]
dst = sys.argv[2] if len(sys.argv) > 2 else src
b = pcbnew.LoadBoard(src)
MM = pcbnew.FromMM
t = pcbnew.ToMM
VIA_D, VIA_DRILL = 0.45, 0.25
CLR = 0.2                   # via copper to other copper (hole-to-copper 0.2 + margin via the pad clearance)
HOLE_HOLE = 0.45            # via hole to via hole (centre spacing ~ drill + 0.2 rule, with margin)
# pads on the L1 GND pours of the bridge cells: they join GND through the pour (placed when the pours are drawn)
POUR_GND = {"RS1", "RS2", "RS3", "C25", "C26", "C31", "NT1", "NT2", "NT3"}
gnd = b.FindNet("GND")
obst = []                   # (x, y, halfw, halfh, layerset-string, net)
for f in b.GetFootprints():
    for p in f.Pads():
        bb = p.GetBoundingBox()
        obst.append((t(bb.GetLeft()), t(bb.GetTop()), t(bb.GetRight()), t(bb.GetBottom()), p.GetNetname(),
                     p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH, f.IsFlipped()))
vias = [(t(tr.GetPosition().x), t(tr.GetPosition().y)) for tr in b.GetTracks() if tr.GetClass() == "PCB_VIA"]
eps = []
for ref in ("U2", "U3", "U4"):
    f = b.FindFootprintByReference(ref)
    ep = max(f.Pads(), key=lambda p: p.GetBoundingBox().GetWidth() * p.GetBoundingBox().GetHeight())
    bb = ep.GetBoundingBox()
    eps.append((t(bb.GetLeft()), t(bb.GetTop()), t(bb.GetRight()), t(bb.GetBottom())))
edge = b.GetBoardEdgesBoundingBox()
EX0, EY0, EX1, EY1 = t(edge.GetLeft()), t(edge.GetTop()), t(edge.GetRight()), t(edge.GetBottom())


def free(x, y):
    r = VIA_D / 2
    if not (EX0 + 0.5 < x < EX1 - 0.5 and EY0 + 0.5 < y < EY1 - 0.5):
        return False
    for (x0, y0, x1, y1, net, tht, flip) in obst:
        c = CLR if net != "GND" else 0.1
        if net == "GND" and not tht:
            c = -1.0            # a GND pad may touch the via (via-at-pad)... but not a THT hole
        if x0 - r - c < x < x1 + r + c and y0 - r - c < y < y1 + r + c:
            return False
    for (vx, vy) in vias:
        if math.hypot(vx - x, vy - y) < VIA_D + HOLE_HOLE - 0.1:
            return False
    for (x0, y0, x1, y1) in eps:
        if x0 - 0.8 < x < x1 + 0.8 and y0 - 0.8 < y < y1 + 0.8:
            return False
    return True


def seg_free(p0, p1, own, flip):
    """the 0.25 mm stub keeps 0.127 mm from every other-net pad on its layer (outside its own pad)"""
    n = max(2, int(math.dist(p0, p1) / 0.05))
    m = 0.125 + 0.127
    for k in range(n + 1):
        x = p0[0] + (p1[0] - p0[0]) * k / n
        y = p0[1] + (p1[1] - p0[1]) * k / n
        if own[0] <= x <= own[2] and own[1] <= y <= own[3]:
            continue
        for (x0, y0, x1, y1, net, tht, fl) in obst:
            if net == "GND" or (fl != flip and not tht):
                continue
            if x0 - m < x < x1 + m and y0 - m < y < y1 + m:
                return False
    return True


placed, missed = 0, []
for f in b.GetFootprints():
    if f.GetReference() in POUR_GND or f.GetReference().startswith(("MH", "JBAT")):
        continue
    fc = f.GetPosition()
    for p in f.Pads():
        if p.GetNetname() != "GND" or p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
            continue
        bb = p.GetBoundingBox()
        if t(bb.GetWidth()) > 2.0 and t(bb.GetHeight()) > 2.0:
            continue            # exposed pads / big GND pads get their own via arrays later
        px, py = t(p.GetPosition().x), t(p.GetPosition().y)
        ux, uy = px - t(fc.x), py - t(fc.y)
        n = math.hypot(ux, uy) or 1.0
        ux, uy = ux / n, uy / n
        hw, hh = t(bb.GetWidth()) / 2, t(bb.GetHeight()) / 2
        best = None
        for dist in (0.0, 0.35, 0.6, 0.9, 1.2, 1.5):
            for ang in (0, 30, -30, 60, -60, 90, -90, 120, -120, 150, -150, 180):
                a = math.radians(ang)
                dx, dy = ux * math.cos(a) - uy * math.sin(a), ux * math.sin(a) + uy * math.cos(a)
                # start just outside the pad edge in that direction
                ex = abs(dx) * hw + abs(dy) * hh
                x, y = px + dx * (ex + VIA_D / 2 + dist), py + dy * (ex + VIA_D / 2 + dist)
                own = (t(bb.GetLeft()), t(bb.GetTop()), t(bb.GetRight()), t(bb.GetBottom()))
                if free(x, y) and seg_free((px, py), (x, y), own, f.IsFlipped()):
                    best = (x, y)
                    break
            if best:
                break
        if not best:
            missed.append(f"{f.GetReference()}.{p.GetNumber()}")
            continue
        x, y = best
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DRILL)); v.SetNet(gnd)
        b.Add(v)
        tr = pcbnew.PCB_TRACK(b)
        tr.SetStart(p.GetPosition()); tr.SetEnd(pcbnew.VECTOR2I(MM(x), MM(y)))
        tr.SetWidth(MM(0.25)); tr.SetLayer(pcbnew.B_Cu if f.IsFlipped() else pcbnew.F_Cu); tr.SetNet(gnd)
        b.Add(tr)
        vias.append((x, y))
        obst.append((x - VIA_D / 2, y - VIA_D / 2, x + VIA_D / 2, y + VIA_D / 2, "GND", False, False))
        placed += 1
pcbnew.SaveBoard(dst, b)
print(f"GND stitch vias: {placed} placed, {len(missed)} without a spot: {missed}")
