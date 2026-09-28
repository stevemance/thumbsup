"""Courtyard boxes of every footprint (board-local) and the part-keepout rule areas: /usr/bin/python3 cydump.py board out.json"""
import json
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
t = pcbnew.ToMM
bb = b.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
out = {}
for f in b.GetFootprints():
    side = "B" if f.IsFlipped() else "F"
    c = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
    if c.OutlineCount() == 0:
        r = f.GetBoundingBox(False, False)
    else:
        r = c.BBox()
    out[f.GetReference()] = dict(side=side, box=[t(r.GetLeft()) - OX, t(r.GetTop()) - OY, t(r.GetRight()) - OX, t(r.GetBottom()) - OY],
                                 pos=[t(f.GetPosition().x) - OX, t(f.GetPosition().y) - OY], rot=f.GetOrientationDegrees(),
                                 pads={p.GetNumber(): dict(net=p.GetNetname(), c=[t(p.GetPosition().x) - OX, t(p.GetPosition().y) - OY])
                                       for p in f.Pads()})
json.dump(out, open(sys.argv[2], "w"))
print(len(out), "footprints")
