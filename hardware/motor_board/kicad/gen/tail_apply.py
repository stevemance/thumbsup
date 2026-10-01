"""Apply tail_edits.EDITS to a board (the board-editing half of tail.py).
/usr/bin/python3 tail_apply.py <in.kicad_pcb> <out.kicad_pcb> <requests.json>"""
import json
import math
import re
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
src, dst, reqf = sys.argv[1:4]
tail_edits = __import__(sys.argv[4] if len(sys.argv) > 4 else "tail_edits")
b = pcbnew.LoadBoard(src)
t, F = pcbnew.ToMM, pcbnew.FromMM
bb = b.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
LAY = {"F.Cu": pcbnew.F_Cu, "In2.Cu": pcbnew.In2_Cu, "In3.Cu": pcbnew.In3_Cu, "In4.Cu": pcbnew.In4_Cu, "B.Cu": pcbnew.B_Cu}
nets = {str(k): v for k, v in b.GetNetsByName().items()}
fps = {f.GetReference(): f for f in b.GetFootprints()}


def loc(p):
    return (t(p.x) - OX, t(p.y) - OY)


def inbox(p, box):
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def anchor(v):
    """A lone new via overlapping a pour's fill is re-netted to the pour's net on SaveBoard (pcbnew connectivity);
    a 0.02 mm stub of its own net on L5 inside the barrel keeps its net until the router joins it."""
    if not b.IsLayerEnabled(pcbnew.In4_Cu):      # 4-layer v2 board: no L5 (and no pours yet to re-net the via)
        return
    x = pcbnew.PCB_TRACK(b)
    x.SetStart(v.GetPosition()); x.SetEnd(v.GetPosition() + pcbnew.VECTOR2I_MM(0.02, 0))
    x.SetWidth(F(0.15)); x.SetLayer(pcbnew.In4_Cu); x.SetNet(v.GetNet())
    b.Add(x)


def remove(items):
    for x in items:                  # collect first, then remove (removing while iterating crashes pcbnew)
        b.Remove(x)


reqs, n_rip = [], 0
# pass 1: every rip, against the frozen board (after one Remove the board's track list can no longer be walked)
kill_all, soft_via, hard_via = {}, set(), set()
rr_kill, rr_opt = {}, {}           # rips with reroute=True: their items, and the route options per net
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
        if x.GetNetname() in e.get("except_nets", ()):     # region rips: everything but the listed (power) nets
            continue
        if x.GetClass() == "PCB_VIA":
            if not e.get("keep_vias") and any(inbox(loc(x.GetPosition()), bx) for bx in boxes):
                kill_all[id(x)] = x
                (soft_via if e.get("layers") else hard_via).add(id(x))
        elif x.GetClass() == "PCB_TRACK":
            if e.get("layers") and pcbnew.BOARD.GetStandardLayerName(x.GetLayer()) not in e["layers"]:
                continue
            p0, p1 = loc(x.GetStart()), loc(x.GetEnd())
            hit = any(inbox(p0, bx) or inbox(p1, bx) for bx in boxes)
            if not hit and e.get("cross"):                    # also segments that only pass through the box
                hit = any(inbox((p0[0] + (p1[0] - p0[0]) * k / 40, p0[1] + (p1[1] - p0[1]) * k / 40), bx) for bx in boxes for k in range(41))
            if hit:
                kill_all[id(x)] = x
                if e.get("reroute"):
                    rr_kill[id(x)] = x
                    rr_opt[x.GetNetname()] = e["reroute"] if isinstance(e["reroute"], dict) else {}
# exact rips: dict(op="rip_segs", tracks=[(net, layer, a, b)], vias=[(net, c)]) - the listed segments / vias only
# (matched to 0.005 mm, either direction), e.g. one stage's router-made copper replaced by a later global re-route
_segs = {}
for e in tail_edits.EDITS:
    if e["op"] == "rip_segs":
        for n, l, a, c in e.get("tracks", []):
            for k in ((round(a[0], 2), round(a[1], 2), round(c[0], 2), round(c[1], 2)),
                      (round(c[0], 2), round(c[1], 2), round(a[0], 2), round(a[1], 2))):
                _segs[(n, l) + k] = True
        for n, c in e.get("vias", []):
            _segs[(n, "via", round(c[0], 2), round(c[1], 2))] = True
if _segs:
    for x in b.GetTracks():
        n = x.GetNetname()
        if x.GetClass() == "PCB_VIA":
            p = loc(x.GetPosition())
            if (n, "via", round(p[0], 2), round(p[1], 2)) in _segs:
                kill_all[id(x)] = x
                hard_via.add(id(x))
        elif x.GetClass() == "PCB_TRACK":
            p0, p1 = loc(x.GetStart()), loc(x.GetEnd())
            if (n, pcbnew.BOARD.GetStandardLayerName(x.GetLayer()), round(p0[0], 2), round(p0[1], 2), round(p1[0], 2),
                    round(p1[1], 2)) in _segs:
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
# reroute: the cut ends a ripped run leaves (surviving track ends, vias, pads) get re-joined after every other route
rr_reqs = []
if rr_kill:
    alive = [x for x in b.GetTracks() if id(x) not in kill_all]
    ends = {}
    for x in rr_kill.values():
        if x.GetClass() != "PCB_TRACK":
            continue
        n = x.GetNetname()
        for p in (x.GetStart(), x.GetEnd()):
            if any(id(y) in rr_kill and y.GetClass() == "PCB_TRACK" and y is not x and p in (y.GetStart(), y.GetEnd())
                   and y.GetLayer() == x.GetLayer() for y in rr_kill.values()):
                continue                                   # interior joint of the ripped run
            q = loc(p); en = None
            for y in alive:
                if y.GetNetname() != n:
                    continue
                if y.GetClass() == "PCB_VIA" and y.GetPosition() == p:
                    en = ("via", round(q[0], 4), round(q[1], 4)); break
                if y.GetClass() == "PCB_TRACK" and y.GetLayer() == x.GetLayer() and p in (y.GetStart(), y.GetEnd()):
                    en = ("pt", round(q[0], 4), round(q[1], 4), pcbnew.BOARD.GetStandardLayerName(x.GetLayer())); break
            if en is None:
                for f in b.GetFootprints():
                    for pd in f.Pads():
                        if pd.GetNetname() == n and pd.IsOnLayer(x.GetLayer()) and pd.HitTest(p):
                            en = ("pad", f.GetReference(), pd.GetNumber())
            if en is not None:
                ends.setdefault(n, [])
                if en not in ends[n]:
                    ends[n].append(en)

    def xy(en):
        if en[0] == "pad":
            pd = [q for q in fps[en[1]].Pads() if q.GetNumber() == en[2]][0]
            return loc(pd.GetPosition())
        return en[1], en[2]
    ORDER = getattr(tail_edits, "RR_ORDER", None)          # optional net order for the re-joins (ordering searches)
    items = sorted(ends.items(), key=lambda kv: ORDER.index(kv[0]) if ORDER and kv[0] in ORDER else 999)
    for n, es in items:
        done = [es[0]]; rest = es[1:]
        while rest:                                        # nearest-neighbour tree over the cut ends
            a_, b_ = min(((a, c) for a in done for c in rest), key=lambda ac: math.dist(xy(ac[0]), xy(ac[1])))
            o = rr_opt[n]
            rr_reqs.append(dict(dict(net=n, a=a_, b=b_, tag=f"rr {n} {a_[1]}-{b_[1]}",
                                     w=max(t(x.GetWidth()) for x in rr_kill.values() if x.GetClass() == "PCB_TRACK" and x.GetNetname() == n), margin=4.0,
                                     layers=["F.Cu", "B.Cu", "In3.Cu", "In2.Cu"], via_through_pours=True), **o))
            done.append(b_); rest.remove(b_)
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
    elif op == "shift":                 # move a block (parts + its nets' copper + its pours) by dx, dy; the undo of grow.py
        V = pcbnew.VECTOR2I(F(e["dx"]), F(e.get("dy", 0)))
        ns = set(e["nets"])
        bxs = e["box"] if isinstance(e["box"][0], (list, tuple)) else [e["box"]]
        gps = (e["bridges"] if isinstance(e["bridges"][0], (list, tuple)) else [e["bridges"]]) if e.get("bridges") else []

        def inb(p):
            return any(inbox(p, q) for q in bxs)

        def ing(p0, p1):
            return any(inbox(p0, q) and inbox(p1, q) for q in gps)
        zs = [z for z in b.Zones() if any(z.GetZoneName().startswith(p) for p in e.get("zones", []))]
        zpoly = [z.Outline() for z in zs if not z.GetIsRuleArea()]

        def in_pour(p):                  # inside one of the block's own copper pours (before the move)
            return any(o.Contains(p) for o in zpoly)
        kill, mv = [], []                # bridges: boxes holding the cell nets' grow bridges (removed)
        for x in b.GetTracks():
            n = x.GetNetname()
            if x.GetClass() == "PCB_VIA":
                p = x.GetPosition()
                if (n in ns and inb(loc(p))) or (n in e.get("stitch", ()) and in_pour(p)):
                    mv.append(x)
                continue
            p0, p1 = loc(x.GetStart()), loc(x.GetEnd())
            if n in ns and inb(p0) and inb(p1):
                mv.append(x)
            elif n in ns and ing(p0, p1) and not (inb(p0) and inb(p1)):
                kill.append(x)
            elif n in e.get("stitch", ()) and in_pour(x.GetStart()) and in_pour(x.GetEnd()):
                mv.append(x)
        remove(kill)
        for x in mv:
            x.Move(V)
        for r in e["refs"]:
            fps[r].Move(V)
        for z in zs:
            z.Move(V)
        print(f"shift: {len(e['refs'])} parts, {len(mv)} copper items, {len(zs)} zones moved; {len(kill)} bridge segments removed")
    elif op == "copy_nets":             # replace nets' tracks / vias with a netcopper.py dump, translated (pre-grow copper)
        src = json.load(open(Path(__file__).resolve().parent / e["src"]))
        ns = set(e["nets"])
        remove([x for x in b.GetTracks() if x.GetNetname() in ns])
        dx, dy = e["dx"], e.get("dy", 0)
        for q in src:
            if q["net"] not in ns:
                continue
            if q["kind"] == "via":
                y = pcbnew.PCB_VIA(b)
                y.SetPosition(pcbnew.VECTOR2I_MM(q["c"][0] + dx + OX, q["c"][1] + dy + OY))
                y.SetWidth(F(q["d"])); y.SetDrill(F(q["drill"])); y.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            else:
                y = pcbnew.PCB_TRACK(b)
                y.SetStart(pcbnew.VECTOR2I_MM(q["a"][0] + dx + OX, q["a"][1] + dy + OY))
                y.SetEnd(pcbnew.VECTOR2I_MM(q["b"][0] + dx + OX, q["b"][1] + dy + OY))
                y.SetWidth(F(q["w"])); y.SetLayer(b.GetLayerID(q["layer"]))
            y.SetNet(nets[q["net"]])
            b.Add(y)
        print(f"copy_nets: {len([q for q in src if q['net'] in ns])} items from {e['src']}")
    elif op in ("rip", "rip_ref", "rip_segs"):
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
        anchor(x)
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
    elif op == "outline":               # replace a zone's outline (board-local polygon)
        z = [b.GetArea(i) for i in range(b.GetAreaCount()) if b.GetArea(i).GetZoneName() == e["name"]][0]
        ol = z.Outline(); ol.RemoveAllContours(); ol.NewOutline()
        for x_, y_ in e["poly"]:
            ol.Append(F(x_ + OX), F(y_ + OY))
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
    elif op == "swap_pin":              # MCU pin swap: the pad and its own fan-out (copper of its old net chained to it,
        # both ends inside `box`) take the new net; copper beyond the box must be ripped by the caller
        pd = [q for q in fps[e["ref"]].Pads() if q.GetNumber() == e["pad"]][0]
        old = pd.GetNetname()
        items = [x for x in b.GetTracks() if x.GetNetname() == old and
                 all(inbox(loc(p), e["box"]) for p in ([x.GetPosition()] if x.GetClass() == "PCB_VIA" else [x.GetStart(), x.GetEnd()]))]
        pts = {(pd.GetPosition().x, pd.GetPosition().y)}
        chain, took, grew = [], set(), True
        while grew:
            grew = False
            for k_, x in enumerate(items):
                if k_ in took:
                    continue
                ends = [x.GetPosition()] if x.GetClass() == "PCB_VIA" else [x.GetStart(), x.GetEnd()]
                if any((p.x, p.y) in pts for p in ends) or (x.GetClass() == "PCB_TRACK" and any(pd.HitTest(p) for p in ends)):
                    chain.append(x); took.add(k_); grew = True
                    pts |= {(p.x, p.y) for p in ends}
        if e["net"] not in nets:                          # e.g. KiCad's "unconnected-(U1-PC6-Pad38)" for a freed pin
            ni = pcbnew.NETINFO_ITEM(b, e["net"]); b.Add(ni)
            nets[e["net"]] = b.FindNet(e["net"])
        pd.SetNet(nets[e["net"]])
        for x in chain:
            x.SetNet(nets[e["net"]])
        print(f"swap {e['ref']}.{e['pad']}: {old} -> {e['net']} ({len(chain)} fan-out items)")
    elif op == "del_fp":                # a part removed from the design (its pads' stubs: rip_ref first)
        b.Remove(fps[e["ref"]])
    elif op == "vip":                   # via in pad (filled + capped, FAB.md): a boxed-in passive pad straight to a plane/pour
        pd = [q for q in fps[e["pad"][0]].Pads() if q.GetNumber() == e["pad"][1]][0]
        x = pcbnew.PCB_VIA(b)
        x.SetPosition(pd.GetPosition() + pcbnew.VECTOR2I_MM(*e.get("off", (0, 0))))
        x.SetWidth(F(e.get("d", 0.4))); x.SetDrill(F(e.get("drill", 0.2)))
        x.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); x.SetNet(pd.GetNet())
        b.Add(x)
        anchor(x)
    elif op == "silk":                  # silk only on parts someone handles + pin-1 dots + function labels (silk.py)
        import silk
        silk.apply(b, e)
    elif op == "sync":                  # re-link to the regenerated schematic, add new parts (schsync.py)
        import schsync
        schsync.apply(b, e, OX, OY)
    elif op == "py":                    # a stage's own board edit: e["fn"](board, ctx) (e.g. hP's pours / keep-outs / via fields)
        e["fn"](b, dict(OX=OX, OY=OY, nets=nets, fps=fps, LAY=LAY, loc=loc))
    elif op == "drop":
        reqs.append(dict(tag=f"drop {e['pad'][0]}.{e['pad'][1]}", net=e["net"], a=("pad",) + tuple(e["pad"]),
                         b=("drop",), layers=e.get("layers", ["F.Cu", "B.Cu"]), w=e.get("w", 0.3),
                         via=e.get("via", 0.45), drill=e.get("drill", 0.25), margin=e.get("margin", 2.0),
                         via_through_pours=True, **({"avoid": e["avoid"]} if "avoid" in e else {})))
    else:
        raise SystemExit(f"unknown op {op}")
reqs += rr_reqs
if getattr(tail_edits, "RR_ORDER", None):                   # ordering searches: every request of a listed net in list order
    reqs.sort(key=lambda r: tail_edits.RR_ORDER.index(r["net"]) if r["net"] in tail_edits.RR_ORDER else -1)
for ref_, num_ in dict.fromkeys(redrop):
    reqs.append(dict(tag=f"redrop {ref_}.{num_}", net="GND", a=("pad", ref_, num_), b=("drop",), layers=["F.Cu", "B.Cu"],
                     w=0.3, via=0.45, drill=0.25, margin=2.5, via_through_pours=True))
pcbnew.SaveBoard(dst, b)
json.dump(reqs, open(reqf, "w"), indent=0)
print(f"tail edits: {len(tail_edits.EDITS)} ops, {n_rip} items ripped, {len(reqs)} router requests")
