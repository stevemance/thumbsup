"""Fab facts from a board for FAB.md: vias inside pads (via-in-pad = POFV order option) grouped by part, and the board-edge
spans with no copper / courtyard within 1.5 mm (where JLC may put mouse-bite tabs).
    /usr/bin/python3 fabfacts.py <board.kicad_pcb>"""
import collections
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
t = pcbnew.ToMM
bb = b.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
W, H = t(bb.GetWidth()) - 0.1, t(bb.GetHeight()) - 0.1

pads = [(f.GetReference(), p) for f in b.GetFootprints() for p in f.Pads()]
vip = collections.defaultdict(list)
sizes = collections.Counter()
for v in b.GetTracks():
    if v.GetClass() != "PCB_VIA":
        continue
    pos = v.GetPosition()
    for ref, p in pads:
        if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
            continue
        lay = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        if p.HitTest(pos) or p.GetEffectivePolygon(lay).Contains(pos):
            vip[ref].append((round(t(pos.x) - OX, 3), round(t(pos.y) - OY, 3), round(t(v.GetWidth()), 2), round(t(v.GetDrillValue()), 2)))
            sizes[(round(t(v.GetWidth()), 2), round(t(v.GetDrillValue()), 2))] += 1
            break
n = sum(len(x) for x in vip.values())
print(f"VIA-IN-PAD: {n} vias in {len(vip)} parts; sizes {dict(sizes)}")
for ref in sorted(vip, key=lambda r: (r.rstrip('0123456789'), int(''.join(c for c in r if c.isdigit()) or 0))):
    print(f"  {ref}: {len(vip[ref])}")

# edge spans: sample each edge every 0.1 mm, blocked if any copper item / courtyard comes within 1.5 mm
boxes = []
for x in b.GetTracks():
    if x.GetNetname() == "GND":
        continue
    r = x.GetBoundingBox(); boxes.append((t(r.GetLeft()) - OX, t(r.GetTop()) - OY, t(r.GetRight()) - OX, t(r.GetBottom()) - OY))
for z in b.Zones():
    for li in z.GetLayerSet().Seq():
        fp = z.GetFilledPolysList(li)
        for i in range(fp.OutlineCount()):
            r = fp.Outline(i).BBox()
            # zones: keep their outline pieces, sampled below as points
for ref, p in pads:
    r = p.GetBoundingBox(); boxes.append((t(r.GetLeft()) - OX, t(r.GetTop()) - OY, t(r.GetRight()) - OX, t(r.GetBottom()) - OY))
for f in b.GetFootprints():
    for lay in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        c = f.GetCourtyard(lay)
        if c.OutlineCount():
            r = c.BBox(); boxes.append((t(r.GetLeft()) - OX, t(r.GetTop()) - OY, t(r.GetRight()) - OX, t(r.GetBottom()) - OY))
fills = []                                 # non-GND fills block a tab; GND fill at a tab is harmless
for z in b.Zones():
    if z.GetNetname() == "GND":
        continue
    for li in z.GetLayerSet().Seq():
        fills.append(z.GetFilledPolysList(li))
for x in list(boxes):
    pass


def blocked(x, y, m=float(sys.argv[2]) if len(sys.argv) > 2 else 1.5):
    if any(bx[0] - m <= x <= bx[2] + m and bx[1] - m <= y <= bx[3] + m for bx in boxes):
        return True
    q = pcbnew.VECTOR2I(pcbnew.FromMM(x + OX), pcbnew.FromMM(y + OY))
    for f in fills:
        if f.OutlineCount() and (f.Contains(q) or f.SquaredDistance(q) < pcbnew.FromMM(m) ** 2):
            return True
    return False


def spans(pts):
    out, cur = [], None
    for s, (x, y) in pts:
        if not blocked(x, y):
            cur = [s, s] if cur is None else [cur[0], s]
        else:
            if cur and cur[1] - cur[0] >= 3.0:
                out.append(cur)
            cur = None
    if cur and cur[1] - cur[0] >= 3.0:
        out.append(cur)
    return [(round(a, 1), round(c, 1)) for a, c in out]


N = lambda L: [i * 0.1 for i in range(int(L * 10) + 1)]
print("EDGE spans clear of non-GND copper / pads / courtyards by 1.5 mm (>= 3 mm long; GND fill / stitching allowed):")
print("  front y=0  :", spans([(s, (s, 0.0)) for s in N(W)]))
print("  rear  y=%.0f:" % H, spans([(s, (s, H)) for s in N(W)]))
print("  left  x=0  :", spans([(s, (0.0, s)) for s in N(H)]))
print("  right x=%.0f:" % W, spans([(s, (W, s)) for s in N(H)]))
