"""Connected pieces of one net (default GND) the way DRC sees them: filled zone islands, tracks, vias and pads.
/usr/bin/python3 netcc.py <board> [net] [--fill]   -> every piece except the largest: bbox, layers, pads, a point
(Unconnected zone-to-zone items in the DRC report carry no position; this says where they are.)"""
import sys

import pcbnew

args = [a for a in sys.argv[1:] if not a.startswith("--")]
b = pcbnew.LoadBoard(args[0])
NET = args[1] if len(args) > 1 else "GND"
t = pcbnew.ToMM
bb = b.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
if "--fill" in sys.argv:
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
nc = b.GetNetcodeFromNetname(NET)
CU = [l for l in b.GetEnabledLayers().CuStack()]

par = {}


def find(k):
    par.setdefault(k, k)
    while par[k] != k:
        par[k] = par[par[k]]
        k = par[k]
    return k


def join(a, c):
    par[find(a)] = find(c)


isl = {l: [] for l in CU}        # layer -> [(key, SHAPE_POLY_SET, idx)]
for z in b.Zones():
    if z.GetNetCode() != nc or z.GetIsRuleArea():
        continue
    for l in CU:
        if not z.IsOnLayer(l):
            continue
        fp = z.GetFilledPolysList(l)
        for i in range(fp.OutlineCount()):
            k = ("z", z.GetZoneName(), l, i)
            find(k)
            isl[l].append((k, fp, i))


def at(p, l):
    return [k for k, fp, i in isl[l] if fp.Contains(p, i)]


info = {}
segs = [x for x in b.GetTracks() if x.GetNetCode() == nc]      # one proxy per item (keys by uuid)
U = lambda x: ("t", x.m_Uuid.AsString())
for x in segs:
    k = U(x)
    find(k)
    if x.GetClass() == "PCB_VIA":
        for l in CU:
            if x.IsOnLayer(l):
                for zk in at(x.GetPosition(), l):
                    join(k, zk)
        info[k] = ("via", x.GetPosition())
    else:
        for p in (x.GetStart(), x.GetEnd()):
            for zk in at(p, x.GetLayer()):
                join(k, zk)
        info[k] = ("trk", x.GetStart())
pads = []
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetNetCode() != nc:
            continue
        k = ("p", f.GetReference() + "." + p.GetNumber(), id(p))
        find(k)
        pads.append((k, p))
        for l in CU:
            if p.IsOnLayer(l):
                for zk, fp, i in isl[l]:
                    if fp.Contains(p.GetPosition(), i):
                        join(k, zk)
# tracks / vias to each other and to pads
ends = {}
for x in segs:
    pts = [x.GetPosition()] if x.GetClass() == "PCB_VIA" else [x.GetStart(), x.GetEnd()]
    for p in pts:
        ends.setdefault((p.x, p.y), []).append(x)
for (px, py), xs in ends.items():
    for y in xs[1:]:
        join(U(xs[0]), U(y))
for x in segs:
    if x.GetClass() == "PCB_VIA":
        continue
    for k, p in pads:
        if p.IsOnLayer(x.GetLayer()) and (p.HitTest(x.GetStart()) or p.HitTest(x.GetEnd())):
            join(U(x), k)
for v in [x for x in segs if x.GetClass() == "PCB_VIA"]:     # a track passing over a via's centre
    for x in segs:
        if x.GetClass() != "PCB_VIA" and x.HitTest(v.GetPosition()):
            join(U(v), U(x))
comp = {}
for k in list(par):
    comp.setdefault(find(k), []).append(k)
big = max(comp.values(), key=len)
for ks in sorted(comp.values(), key=len, reverse=True):
    if ks is big:
        continue
    pd = [k[1] for k in ks if k[0] == "p"]
    zs = [k for k in ks if k[0] == "z"]
    lays = sorted({b.GetLayerName(k[2]) for k in zs})
    pt = None
    for k in ks:
        if k[0] == "z":
            fp = [q for q in isl[k[2]] if q[0] == k][0]
            r = fp[1].Outline(fp[2]).BBox()
            pt = f"zone bbox ({t(r.GetLeft())-OX:.2f},{t(r.GetTop())-OY:.2f})-({t(r.GetRight())-OX:.2f},{t(r.GetBottom())-OY:.2f})"
            break
    if pt is None and ks:
        for k in ks:
            if k in info:
                p = info[k][1]
                pt = f"{info[k][0]} at ({t(p.x)-OX:.2f},{t(p.y)-OY:.2f})"
                break
    print(f"piece: {len(ks)} items, zones on {lays}, pads {pd[:8]}, {pt}")
print("pieces:", len(comp), "(1 = fully connected)")
