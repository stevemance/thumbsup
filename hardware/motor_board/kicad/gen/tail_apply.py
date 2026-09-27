"""Apply tail_edits.EDITS to a board (the board-editing half of tail.py).
/usr/bin/python3 tail_apply.py <in.kicad_pcb> <out.kicad_pcb> <requests.json>"""
import json
import math
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tail_edits  # noqa: E402

src, dst, reqf = sys.argv[1:4]
b = pcbnew.LoadBoard(src)
t, F = pcbnew.ToMM, pcbnew.FromMM
bb = b.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
LAY = {"F.Cu": pcbnew.F_Cu, "In2.Cu": pcbnew.In2_Cu, "In3.Cu": pcbnew.In3_Cu, "B.Cu": pcbnew.B_Cu}
nets = {str(k): v for k, v in b.GetNetsByName().items()}
fps = {f.GetReference(): f for f in b.GetFootprints()}


def loc(p):
    return (t(p.x) - OX, t(p.y) - OY)


def inbox(p, box):
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def remove(items):
    for x in items:                  # collect first, then remove (removing while iterating crashes pcbnew)
        b.Remove(x)


reqs, n_rip = [], 0
# pass 1: every rip, against the frozen board (after one Remove the board's track list can no longer be walked)
kill_all, soft_via, hard_via = {}, set(), set()
for e in tail_edits.EDITS:
    if e["op"] not in ("rip", "rip_ref"):
        continue
    if e["op"] == "rip_ref":
        e = dict(e, nets=e.get("nets") or [q.GetNetname() for q in fps[e["ref"]].Pads()])   # only the part's own nets
        boxes = []
        for p in fps[e["ref"]].Pads():
            r = p.GetBoundingBox()
            boxes.append((t(r.GetLeft()) - OX - 0.05, t(r.GetTop()) - OY - 0.05, t(r.GetRight()) - OX + 0.05,
                          t(r.GetBottom()) - OY + 0.05))
    else:
        boxes = [e["box"]]
    for x in b.GetTracks():
        if e.get("nets") and x.GetNetname() not in e["nets"]:
            continue
        if x.GetClass() == "PCB_VIA":
            if not e.get("keep_vias") and any(inbox(loc(x.GetPosition()), bx) for bx in boxes):
                kill_all[id(x)] = x
                (soft_via if e.get("layers") else hard_via).add(id(x))
        elif x.GetClass() == "PCB_TRACK":
            if e.get("layers") and pcbnew.BOARD.GetStandardLayerName(x.GetLayer()) not in e["layers"]:
                continue
            if any(inbox(loc(x.GetStart()), bx) or inbox(loc(x.GetEnd()), bx) for bx in boxes):
                kill_all[id(x)] = x
# a via caught only by layer-limited rips stays if a surviving track still lands on it
for v in [x for x in kill_all.values() if id(x) in soft_via and id(x) not in hard_via]:
    vp = v.GetPosition()
    if any(x.GetClass() == "PCB_TRACK" and id(x) not in kill_all and x.GetNetCode() == v.GetNetCode()
           and vp in (x.GetStart(), x.GetEnd()) for x in b.GetTracks()):
        del kill_all[id(v)]
n_rip = len(kill_all)
# a ripped GND via: its pad (the nearest GND SMD pad within 2 mm) gets a fresh drop to the planes after the routes
redrop = []
gpads = [(f.GetReference(), p.GetNumber(), loc(p.GetPosition())) for f in b.GetFootprints() for p in f.Pads()
         if p.GetNetname() == "GND" and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
for x in kill_all.values():
    if x.GetClass() == "PCB_VIA" and x.GetNetname() == "GND":
        c = loc(x.GetPosition())
        near = min(gpads, key=lambda q: math.dist(q[2], c))
        if math.dist(near[2], c) < 2.0:
            redrop.append((near[0], near[1]))
remove(list(kill_all.values()))
# pass 2: everything else, in order
for e in tail_edits.EDITS:
    op = e["op"]
    if op == "move":
        f = fps[e["ref"]]
        want_b = e.get("side", "B" if f.IsFlipped() else "F") == "B"
        if want_b != f.IsFlipped():
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        if "rot" in e:
            f.SetOrientationDegrees(e["rot"])
        f.SetPosition(pcbnew.VECTOR2I(F(e["x"] + OX), F(e["y"] + OY)))
    elif op in ("rip", "rip_ref"):
        pass                             # (done in pass 1)
    elif op == "track":
        for a, c in zip(e["pts"], e["pts"][1:]):
            x = pcbnew.PCB_TRACK(b)
            x.SetStart(pcbnew.VECTOR2I_MM(OX + a[0], OY + a[1])); x.SetEnd(pcbnew.VECTOR2I_MM(OX + c[0], OY + c[1]))
            x.SetWidth(F(e.get("w", 0.15))); x.SetLayer(LAY[e["layer"]]); x.SetNet(nets[e["net"]])
            b.Add(x)
    elif op == "via":
        x = pcbnew.PCB_VIA(b)
        x.SetPosition(pcbnew.VECTOR2I_MM(OX + e["c"][0], OY + e["c"][1]))
        x.SetWidth(F(e.get("d", 0.4))); x.SetDrill(F(e.get("drill", 0.2)))
        x.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); x.SetNet(nets[e["net"]])
        b.Add(x)
    elif op == "route":
        r = {k: v for k, v in e.items() if k != "op"}
        r.setdefault("tag", f"{e['net']} {e['a'][1]}-{e['b'][1]}")
        r.setdefault("layers", ["F.Cu", "B.Cu", "In3.Cu", "In2.Cu"])
        r.setdefault("via_through_pours", True)
        reqs.append(r)
    elif op == "why":                   # probe: route ignoring existing tracks, report what it runs into
        r = {k: v for k, v in e.items() if k != "op"}
        r["tag"] = f"why {e['net']} {e['a'][1]}-{e['b'][1]}"
        r["ignore_tracks"] = True
        r.setdefault("layers", ["F.Cu", "B.Cu", "In3.Cu", "In2.Cu"])
        r.setdefault("via_through_pours", True)
        reqs.append(r)
    elif op == "zone":                  # a pour (lowest priority, fills around everything; the router ignores "* fill")
        src = [z for z in b.Zones() if z.GetZoneName() == "L2 GND plane"][0]
        z = pcbnew.ZONE(b)
        z.SetLayer(LAY[e["layer"]]); z.SetNetCode(nets[e["net"]].GetNetCode()); z.SetZoneName(e["name"])
        z.SetAssignedPriority(e.get("priority", 0)); z.SetLocalClearance(F(e.get("clr", 0.2)))
        z.SetMinThickness(F(e.get("min_w", 0.25))); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        ol = z.Outline(); ol.NewOutline()
        if e.get("poly"):
            for x_, y_ in e["poly"]:
                ol.Append(F(x_ + OX), F(y_ + OY))
        else:
            so = src.Outline()
            for i in range(so.Outline(0).PointCount()):
                q = so.Outline(0).CPoint(i); ol.Append(q.x, q.y)
        b.Add(z)
    elif op == "vip":                   # via in pad (filled + capped, FAB.md): a boxed-in passive pad straight to a plane/pour
        pd = [q for q in fps[e["pad"][0]].Pads() if q.GetNumber() == e["pad"][1]][0]
        x = pcbnew.PCB_VIA(b)
        x.SetPosition(pd.GetPosition() + pcbnew.VECTOR2I_MM(*e.get("off", (0, 0))))
        x.SetWidth(F(e.get("d", 0.4))); x.SetDrill(F(e.get("drill", 0.2)))
        x.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); x.SetNet(pd.GetNet())
        b.Add(x)
    elif op == "drop":
        reqs.append(dict(tag=f"drop {e['pad'][0]}.{e['pad'][1]}", net=e["net"], a=("pad",) + tuple(e["pad"]),
                         b=("drop",), layers=e.get("layers", ["F.Cu", "B.Cu"]), w=e.get("w", 0.3),
                         via=e.get("via", 0.45), drill=e.get("drill", 0.25), margin=e.get("margin", 2.0),
                         via_through_pours=True))
    else:
        raise SystemExit(f"unknown op {op}")
for ref_, num_ in dict.fromkeys(redrop):
    reqs.append(dict(tag=f"redrop {ref_}.{num_}", net="GND", a=("pad", ref_, num_), b=("drop",), layers=["F.Cu", "B.Cu"],
                     w=0.3, via=0.45, drill=0.25, margin=2.5, via_through_pours=True))
pcbnew.SaveBoard(dst, b)
json.dump(reqs, open(reqf, "w"), indent=0)
print(f"tail edits: {len(tail_edits.EDITS)} ops, {n_rip} items ripped, {len(reqs)} router requests")
