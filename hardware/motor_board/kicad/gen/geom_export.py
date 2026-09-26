"""Export the board's copper, keep-outs and net rules to JSON for the router (board-local mm, y down).
/usr/bin/python3 geom_export.py <board.kicad_pcb> <out.json>"""
import json
import sys

import pcbnew

pcb, out = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(pcb)
t = pcbnew.ToMM
bb = b.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
LAYERS = {pcbnew.F_Cu: "F.Cu", pcbnew.In1_Cu: "In1.Cu", pcbnew.In2_Cu: "In2.Cu", pcbnew.In3_Cu: "In3.Cu",
          pcbnew.In4_Cu: "In4.Cu", pcbnew.B_Cu: "B.Cu"}


def xy(p):
    return [round(t(p.x) - OX, 4), round(t(p.y) - OY, 4)]


def outline(z):
    ol = z.Outline()
    return [xy(ol.CVertex(i)) for i in range(ol.FullPointCount())]


G = dict(board=[t(bb.GetWidth()) - 0.1, t(bb.GetHeight()) - 0.1], pads=[], tracks=[], vias=[], zones=[], rules=[], classes={}, nets={})
for f in b.GetFootprints():
    for p in f.Pads():
        r = p.GetBoundingBox()
        lays = [LAYERS[l] for l in LAYERS if p.IsOnLayer(l)]
        tht = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        shape = "circle" if p.GetShape(pcbnew.F_Cu) == pcbnew.PAD_SHAPE_CIRCLE else "rect"
        G["pads"].append(dict(ref=f.GetReference(), num=p.GetNumber(), net=p.GetNetname(), layers=lays, tht=tht, shape=shape,
                              box=[round(t(r.GetLeft()) - OX, 4), round(t(r.GetTop()) - OY, 4), round(t(r.GetRight()) - OX, 4), round(t(r.GetBottom()) - OY, 4)],
                              c=xy(p.GetPosition()), drill=round(t(p.GetDrillSize().x), 3) if tht else 0))
for x in b.GetTracks():
    if x.GetClass() == "PCB_VIA":
        G["vias"].append(dict(net=x.GetNetname(), c=xy(x.GetPosition()), d=round(t(x.GetWidth(pcbnew.F_Cu)), 3)))
    elif x.GetClass() == "PCB_TRACK":
        G["tracks"].append(dict(net=x.GetNetname(), layer=LAYERS.get(x.GetLayer(), "?"), a=xy(x.GetStart()), b=xy(x.GetEnd()), w=round(t(x.GetWidth()), 3)))
for z in b.Zones():
    if z.GetIsRuleArea():
        G["rules"].append(dict(name=z.GetZoneName(), layers=[LAYERS[l] for l in LAYERS if z.IsOnLayer(l)], poly=outline(z),
                               no_tracks=z.GetDoNotAllowTracks(), no_vias=z.GetDoNotAllowVias(), no_copper=z.GetDoNotAllowZoneFills()))
    else:
        G["zones"].append(dict(name=z.GetZoneName(), net=z.GetNetname(), layer=LAYERS.get(z.GetLayer(), "?"), poly=outline(z)))
from pathlib import Path
pro = json.loads((Path(__file__).resolve().parent.parent / "motor_board" / "motor_board.kicad_pro").read_text())
CL = {c["name"]: c for c in pro["net_settings"]["classes"]}
for n, ni in b.GetNetsByName().items():
    n = str(n)
    if not n:
        continue
    cn = next((q["netclass"] for q in pro["net_settings"]["netclass_patterns"] if q["pattern"] == n), "Default")
    c = CL.get(cn, CL["Default"])
    G["nets"][n] = dict(cls=cn, w=c["track_width"], clr=c["clearance"], via=c["via_diameter"], drill=c["via_drill"])
json.dump(G, open(out, "w"))
print(f"exported {len(G['pads'])} pads, {len(G['tracks'])} tracks, {len(G['vias'])} vias, {len(G['zones'])} zones, {len(G['rules'])} rule areas")
