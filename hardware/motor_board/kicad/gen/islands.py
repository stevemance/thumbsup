"""Filled GND islands on F/B that reach no GND via or through-hole pad (i.e. not tied to the L2/L5 planes).
/usr/bin/python3 islands.py [board]   -> per island: layer, area, a point inside, the GND SMD pads it touches"""
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
SPOTS = "--spots" in sys.argv
TIES = "--ties" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]
PCB = args[0] if args else str(HERE.parent / "motor_board" / "motor_board.kicad_pcb")
b = pcbnew.LoadBoard(PCB)
t = pcbnew.ToMM
bb = b.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
gnd = b.GetNetcodeFromNetname("GND")
anchors = [x.GetPosition() for x in b.GetTracks() if x.GetClass() == "PCB_VIA" and x.GetNetCode() == gnd]
anchors += [p.GetPosition() for f in b.GetFootprints() for p in f.Pads()
            if p.GetNetCode() == gnd and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
smd = [(f.GetReference() + "." + p.GetNumber(), p) for f in b.GetFootprints() for p in f.Pads()
       if p.GetNetCode() == gnd and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
for z in b.Zones():
    if z.GetNetCode() != gnd or z.GetIsRuleArea():
        continue
    for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
        if not z.IsOnLayer(lay):
            continue
        fp = z.GetFilledPolysList(lay)
        for i in range(fp.OutlineCount()):
            if any(fp.Contains(a, i) for a in anchors):
                continue
            ol = fp.Outline(i)
            bx = ol.BBox()
            touch = [n for n, p in smd if p.IsOnLayer(lay) and fp.Contains(p.GetPosition(), i)]
            c = bx.Centre()
            print(f"{z.GetZoneName():14s} {b.GetLayerName(lay)} island {i}: bbox ({t(bx.GetLeft())-OX:.2f},{t(bx.GetTop())-OY:.2f})"
                  f"-({t(bx.GetRight())-OX:.2f},{t(bx.GetBottom())-OY:.2f}) pads {touch}")

if SPOTS:          # a legal GND via spot inside each padded island (via 0.4 fully inside the fill)
    import math
    L = lambda v: (t(v.x) - OX, t(v.y) - OY)

    def sd(a, c, p):
        dx, dy = c[0] - a[0], c[1] - a[1]; Ln = dx * dx + dy * dy
        u = 0 if Ln == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / Ln))
        return math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dy)
    segs = [(L(x.GetStart()), L(x.GetEnd()), t(x.GetWidth()) / 2) for x in b.GetTracks()
            if x.GetClass() == "PCB_TRACK" and x.GetNetCode() != gnd]
    circ = [(L(x.GetPosition()), t(x.GetWidth(pcbnew.F_Cu)) / 2) for x in b.GetTracks()
            if x.GetClass() == "PCB_VIA" and x.GetNetCode() != gnd]
    holes = [L(x.GetPosition()) for x in b.GetTracks() if x.GetClass() == "PCB_VIA"]
    rects = []
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetCode() != gnd:
                r = p.GetBoundingBox()
                rects.append((t(r.GetLeft()) - OX, t(r.GetTop()) - OY, t(r.GetRight()) - OX, t(r.GetBottom()) - OY))
    keep = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    out = []
    for z in b.Zones():
        if z.GetNetCode() != gnd or z.GetIsRuleArea() or not z.GetZoneName().endswith("GND fill"):
            continue
        lay = z.GetLayer()
        fp = z.GetFilledPolysList(lay)
        for i in range(fp.OutlineCount()):
            if any(fp.Contains(a, i) for a in anchors):
                continue
            if not [n for n, p in smd if p.IsOnLayer(lay) and fp.Contains(p.GetPosition(), i)]:
                continue
            bx = fp.Outline(i).BBox()
            best = None
            x = t(bx.GetLeft()) - OX
            while x <= t(bx.GetRight()) - OX:
                y = t(bx.GetTop()) - OY
                while y <= t(bx.GetBottom()) - OY:
                    P = pcbnew.VECTOR2I(pcbnew.FromMM(x + OX), pcbnew.FromMM(y + OY))
                    if fp.Contains(P, i) and all(fp.Contains(pcbnew.VECTOR2I(P.x + int(pcbnew.FromMM(0.22 * math.cos(k * math.pi / 4))),
                                                                              P.y + int(pcbnew.FromMM(0.22 * math.sin(k * math.pi / 4)))), i)
                                                 for k in range(8)) \
                            and not any(k_.Outline().Contains(P) for k_ in keep):
                        p = (x, y)
                        d = min([sd(a, c, p) - w for a, c, w in segs] + [math.dist(q, p) - r for q, r in circ] +
                                [math.hypot(max(r[0] - x, 0, x - r[2]), max(r[1] - y, 0, y - r[3])) for r in rects] + [9])
                        dh = min([math.dist(q, p) for q in holes] + [9]) - 0.2
                        if d - 0.2 >= 0.15 and dh >= 0.25 and (best is None or d > best[0]):
                            best = (d, round(x, 3), round(y, 3))
                    y += 0.05
                x += 0.05
            print(f"{b.GetLayerName(lay)} island {i}: spot {best}")
            if best:
                out.append((best[1], best[2]))
    print("SPOTS", out)

if TIES:           # route requests: each stranded pad -> its 3 nearest plane-tied GND vias, own layer only
    import json, math, os
    reqs = []
    for z in b.Zones():
        if z.GetNetCode() != gnd or z.GetIsRuleArea() or not z.GetZoneName().endswith("GND fill"):
            continue
        lay = z.GetLayer(); fp = z.GetFilledPolysList(lay)
        for i in range(fp.OutlineCount()):
            if any(fp.Contains(a, i) for a in anchors):
                continue
            for n, p in smd:
                if p.IsOnLayer(lay) and fp.Contains(p.GetPosition(), i):
                    pp = p.GetPosition()
                    vs = sorted(anchors, key=lambda a: (a - pp).EuclideanNorm())[:3]
                    for v in vs[:int(os.environ.get("TIES_K", "1"))]:
                        reqs.append(dict(op="route", net="GND", a=("pad",) + tuple(n.split(".")),
                                         b=("via", round(t(v.x) - OX, 4), round(t(v.y) - OY, 4)),
                                         layers=[b.GetLayerName(lay).replace("F.Cu", "F.Cu")], w=0.2, margin=1.5))
    json.dump(reqs, open(HERE / "out" / "tail" / "ties.json", "w"))
    print(len(reqs), "tie requests")
