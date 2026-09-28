"""Dump the filled islands of the L4 3V3 fill (board-local) and the +3V3 vias: /usr/bin/python3 l4dump.py <board> <out.json>"""
import pcbnew, sys, json
b = pcbnew.LoadBoard(sys.argv[1]); t = pcbnew.ToMM
bb = b.GetBoardEdgesBoundingBox(); OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
z = [z for z in b.Zones() if z.GetZoneName() == "L4 3V3 fill"][0]
fp = z.GetFilledPolysList(pcbnew.In3_Cu)
isl = []
for i in range(fp.OutlineCount()):
    o = fp.Outline(i)
    isl.append([(t(o.CPoint(k).x) - OX, t(o.CPoint(k).y) - OY) for k in range(o.PointCount())])
net = b.GetNetcodeFromNetname("+3V3")
vias = [(t(x.GetPosition().x) - OX, t(x.GetPosition().y) - OY) for x in b.GetTracks() if x.GetClass() == "PCB_VIA" and x.GetNetCode() == net]
json.dump(dict(isl=isl, vias=vias), open(sys.argv[2], "w"))
