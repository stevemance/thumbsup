"""Dump nets' tracks / vias (board-local mm) to json, for tail op copy_nets:
/usr/bin/python3 netcopper.py <board> <out.json> net [net ...]"""
import json
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
t = pcbnew.ToMM
bb = b.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
ns = set(sys.argv[3:])
out = []
for x in b.GetTracks():
    if x.GetNetname() not in ns:
        continue
    if x.GetClass() == "PCB_VIA":
        out.append(dict(kind="via", net=x.GetNetname(), c=[t(x.GetPosition().x) - OX, t(x.GetPosition().y) - OY],
                        d=t(x.GetWidth(pcbnew.F_Cu)), drill=t(x.GetDrill())))
    else:
        out.append(dict(kind="track", net=x.GetNetname(), layer=b.GetLayerName(x.GetLayer()), w=t(x.GetWidth()),
                        a=[t(x.GetStart().x) - OX, t(x.GetStart().y) - OY], b=[t(x.GetEnd().x) - OX, t(x.GetEnd().y) - OY]))
json.dump(out, open(sys.argv[2], "w"))
print(len(out), "items")
