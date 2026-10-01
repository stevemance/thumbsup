"""Apply router output (routes.json) to a board.  /usr/bin/python3 apply_routes.py <in.kicad_pcb> <routes.json> <out.kicad_pcb>"""
import json
import sys

import pcbnew

src, routes, dst = sys.argv[1:4]
b = pcbnew.LoadBoard(src)
t, F = pcbnew.ToMM, pcbnew.FromMM
bb = b.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
LAY = {"F.Cu": pcbnew.F_Cu, "In2.Cu": pcbnew.In2_Cu, "In3.Cu": pcbnew.In3_Cu, "In4.Cu": pcbnew.In4_Cu, "B.Cu": pcbnew.B_Cu}
nets = {str(k): v for k, v in b.GetNetsByName().items()}
nt = nv = 0
seen_v = {(str(x.GetNetname()), round(t(x.GetPosition().x) - OX, 3), round(t(x.GetPosition().y) - OY, 3))
          for x in b.GetTracks() if x.GetClass() == "PCB_VIA"}
for r in json.load(open(routes)):
    if not r.get("ok"):
        continue
    for tr in r["tracks"]:
        for a, c in zip(tr["pts"], tr["pts"][1:]):
            x = pcbnew.PCB_TRACK(b)
            x.SetStart(pcbnew.VECTOR2I_MM(OX + a[0], OY + a[1])); x.SetEnd(pcbnew.VECTOR2I_MM(OX + c[0], OY + c[1]))
            x.SetWidth(F(tr["w"])); x.SetLayer(LAY[tr["layer"]]); x.SetNet(nets[tr["net"]])
            b.Add(x); nt += 1
    for v in r["vias"]:
        key = (v["net"], round(v["c"][0], 3), round(v["c"][1], 3))
        if key in seen_v:            # two routes ending on the same via spot (e.g. GND drops): one via
            continue
        seen_v.add(key)
        x = pcbnew.PCB_VIA(b)
        x.SetPosition(pcbnew.VECTOR2I_MM(OX + v["c"][0], OY + v["c"][1])); x.SetWidth(F(v["d"])); x.SetDrill(F(v["drill"]))
        x.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); x.SetNet(nets[v["net"]])
        b.Add(x); nv += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
print(f"applied {nt} track segments, {nv} vias")
