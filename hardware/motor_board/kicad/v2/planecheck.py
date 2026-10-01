"""Plane-integrity check for the v2 board (L2 = In1.Cu solid GND plane, L3 = In2.Cu GND/VBAT pour with signal lanes).

    /usr/bin/python3 planecheck.py dump [board.kicad_pcb] [--fill]     # pcbnew -> out/planecheck.json
    uv run --no-project --with numpy --with scipy --with matplotlib python planecheck.py check   # report + PNG

dump: every via and PTH/NPTH pad (centre, drill, copper diameter, net), every L3 track, the board outline.  With
--fill a copy of the board gets a GND zone on In1 plus the L3 pours (GND behind the band, VBAT in the band) and is
filled by KiCad; the filled polygons are dumped too, so check can compare its own raster with KiCad's fill.

check, L2 (no tracks on L2):
  - copper = board outline pulled in by 0.3 mm (edge clearance) minus an antipad round every non-GND via / PTH:
    antipad radius = drill / 2 + 0.2 mm (the "hole + 0.2 mm each side" rule; NPTH holes get the same), GND vias and
    GND PTH pads are part of the plane;
  - web between two neighbouring antipads = centre distance - r1 - r2 (minimum and the worst spots);
  - slots: antipads chained by webs < 0.25 mm; a chain whose extent is > 3 mm is a slot in the return path;
  - connectivity: the raster (0.025 mm) labelled into connected copper regions; every region but the main one is
    reported (area, bounding box), and with --fill the number of KiCad fill outlines on In1.
check, L3: the GND pour (rear band) and the VBAT pour (front band: y < 16.0 for x 14-27 and x >= 44.5, else y < 18.5)
  with every other net's L3 track (w / 2 + 0.2 mm), via and PTH (antipad as on L2, or the copper ring + 0.2 mm for a
  track-connected via of the pour's own net is skipped) cut out; reports the pieces each pour falls into (islands) and
  the narrowest necks (distance-transform ridge < 0.25 mm wide)."""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
DUMP = OUT / "planecheck.json"
OX, OY = 100.0, 70.0
CLR_HOLE = 0.2           # antipad: hole + 0.2 mm each side
EDGE = 0.3               # plane pulled back from the board edge
SLOT_WEB, SLOT_LEN = 0.25, 3.0
TRK_CLR = 0.2            # L3 pour clearance to other nets' tracks
BAND = [(0, 0, 14.0, 18.5), (14.0, 0, 27.0, 16.0), (27.0, 0, 44.5, 18.5), (44.5, 0, 85.0, 16.0)]


def dump():
    import pcbnew
    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    src = args[0] if args else str(HERE.parent / "motor_board" / "motor_board.kicad_pcb")
    b = pcbnew.LoadBoard(src)
    t = pcbnew.ToMM
    bb = b.GetBoardEdgesBoundingBox()
    ox, oy = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05

    def xy(p):
        return [round(t(p.x) - ox, 4), round(t(p.y) - oy, 4)]
    D = dict(board=[round(t(bb.GetWidth()) - 0.1, 3), round(t(bb.GetHeight()) - 0.1, 3)], holes=[], l3=[], fill={})
    for x in b.GetTracks():
        if x.GetClass() == "PCB_VIA":
            D["holes"].append(dict(kind="via", c=xy(x.GetPosition()), drill=round(t(x.GetDrillValue()), 3),
                                   d=round(t(x.GetWidth(pcbnew.F_Cu)), 3), net=x.GetNetname()))
        elif x.GetClass() == "PCB_TRACK" and x.GetLayer() == pcbnew.In2_Cu:
            D["l3"].append(dict(a=xy(x.GetStart()), b=xy(x.GetEnd()), w=round(t(x.GetWidth()), 3), net=x.GetNetname()))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetAttribute() not in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                continue
            ds = p.GetDrillSize()
            D["holes"].append(dict(kind="npth" if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else "pth",
                                   c=xy(p.GetPosition()), drill=round(t(max(ds.x, ds.y)), 3),
                                   d=round(t(max(p.GetSize(pcbnew.F_Cu).x, p.GetSize(pcbnew.F_Cu).y)), 3),
                                   net=p.GetNetname(), ref=f"{f.GetReference()}.{p.GetNumber()}"))
    if "--fill" in sys.argv:
        gnd, vb = b.FindNet("GND"), b.FindNet("VBAT")

        def zone(layer, net, poly, prio, name):
            z = pcbnew.ZONE(b)
            z.SetLayer(layer); z.SetNet(net); z.SetZoneName(name); z.SetAssignedPriority(prio)
            z.SetLocalClearance(pcbnew.FromMM(0.2)); z.SetMinThickness(pcbnew.FromMM(0.2))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)
            ch = pcbnew.SHAPE_LINE_CHAIN()
            for px, py in poly:
                ch.Append(pcbnew.VECTOR2I_MM(ox + px, oy + py))
            ch.SetClosed(True)
            z.Outline().AddOutline(ch)
            b.Add(z)
            return z
        W, H = D["board"]
        zs = [zone(pcbnew.In1_Cu, gnd, [(0, 0), (W, 0), (W, H), (0, H)], 0, "pc L2 GND")]
        band = [(0, 0), (W, 0), (W, 16.0), (44.5, 16.0), (44.5, 18.5), (27.0, 18.5), (27.0, 16.0), (14.0, 16.0),
                (14.0, 18.5), (0, 18.5)]
        zs.append(zone(pcbnew.In2_Cu, vb, band, 2, "pc L3 VBAT"))
        zs.append(zone(pcbnew.In2_Cu, gnd, [(0, 0), (W, 0), (W, H), (0, H)], 1, "pc L3 GND"))
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        for z in zs:
            fp = z.GetFilledPolysList(z.GetLayer())
            polys = []
            for i in range(fp.OutlineCount()):
                o = fp.Outline(i)
                polys.append(dict(outline=[xy(o.CPoint(k)) for k in range(o.PointCount())],
                                  holes=[[xy(fp.Hole(i, h).CPoint(k)) for k in range(fp.Hole(i, h).PointCount())]
                                         for h in range(fp.HoleCount(i))]))
            D["fill"][z.GetZoneName()] = polys
        pcbnew.SaveBoard(str(OUT / "planecheck_filled.kicad_pcb"), b)
    json.dump(D, open(DUMP, "w"))
    print(f"dumped {len(D['holes'])} holes, {len(D['l3'])} L3 tracks" + (f", fills {[(k, len(v)) for k, v in D['fill'].items()]}" if D["fill"] else ""))


def check():
    import numpy as np
    from scipy import ndimage
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    D = json.load(open(DUMP))
    W, H = D["board"]
    RES = 0.025
    NX, NY = int(W / RES) + 1, int(H / RES) + 1
    XS, YS = np.arange(NX) * RES, np.arange(NY) * RES
    gx, gy = np.meshgrid(XS, YS)
    R_CORNER = 1.5

    def outline_mask(edge):
        m = (gx >= edge) & (gx <= W - edge) & (gy >= edge) & (gy <= H - edge)
        for cx, cy in ((R_CORNER, R_CORNER), (W - R_CORNER, R_CORNER), (R_CORNER, H - R_CORNER), (W - R_CORNER, H - R_CORNER)):
            corner = ((gx - cx) * (1 if cx > W / 2 else -1) > 0) & ((gy - cy) * (1 if cy > H / 2 else -1) > 0)
            m &= ~(corner & (np.hypot(gx - cx, gy - cy) > R_CORNER - edge))
        return m

    def disc(m, c, r, val=False):
        i0, i1 = max(0, int((c[1] - r) / RES) - 1), min(NY, int((c[1] + r) / RES) + 2)
        j0, j1 = max(0, int((c[0] - r) / RES) - 1), min(NX, int((c[0] + r) / RES) + 2)
        sub = (gx[i0:i1, j0:j1] - c[0]) ** 2 + (gy[i0:i1, j0:j1] - c[1]) ** 2 <= r * r
        m[i0:i1, j0:j1][sub] = val

    def capsule(m, a, b, r, val=False):
        i0, i1 = max(0, int((min(a[1], b[1]) - r) / RES) - 1), min(NY, int((max(a[1], b[1]) + r) / RES) + 2)
        j0, j1 = max(0, int((min(a[0], b[0]) - r) / RES) - 1), min(NX, int((max(a[0], b[0]) + r) / RES) + 2)
        xs, ys = gx[i0:i1, j0:j1], gy[i0:i1, j0:j1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy or 1e-12
        u = np.clip(((xs - a[0]) * dx + (ys - a[1]) * dy) / L2, 0, 1)
        m[i0:i1, j0:j1][(xs - a[0] - u * dx) ** 2 + (ys - a[1] - u * dy) ** 2 <= r * r] = val

    rep = []
    P = rep.append
    # ------------------------------------------------------------------ L2
    holes = D["holes"]
    anti = [h for h in holes if h["net"] != "GND"]
    for h in anti:
        h["r"] = h["drill"] / 2 + CLR_HOLE
    P(f"L2 (In1.Cu GND plane): {len(holes)} holes, {len(anti)} with an antipad (non-GND vias / PTH / NPTH), "
      f"antipad = drill/2 + {CLR_HOLE} mm")
    pairs = []
    for i, a in enumerate(anti):
        for j in range(i + 1, len(anti)):
            b_ = anti[j]
            dd = math.dist(a["c"], b_["c"])
            if dd < a["r"] + b_["r"] + 1.0:
                pairs.append((dd - a["r"] - b_["r"], i, j))
    pairs.sort()
    P(f"  minimum web between neighbouring antipads: {pairs[0][0]:.3f} mm" if pairs else "  no neighbouring antipads")
    P("  worst webs (web mm | hole A | hole B):")
    for w, i, j in pairs[:15]:
        a, b_ = anti[i], anti[j]
        P(f"    {w:6.3f} | {a['kind']} {a['net'].split('/')[-1]} ({a['c'][0]:.2f}, {a['c'][1]:.2f}) dr {a['drill']} | "
          f"{b_['kind']} {b_['net'].split('/')[-1]} ({b_['c'][0]:.2f}, {b_['c'][1]:.2f}) dr {b_['drill']}")
    # slots: union-find over webs < SLOT_WEB
    par = list(range(len(anti)))

    def find(k):
        while par[k] != k:
            par[k] = par[par[k]]
            k = par[k]
        return k
    for w, i, j in pairs:
        if w < SLOT_WEB:
            par[find(i)] = find(j)
    groups = {}
    for k in range(len(anti)):
        groups.setdefault(find(k), []).append(k)
    slots = []
    for g in groups.values():
        if len(g) < 2:
            continue
        ext = max(math.dist(anti[p]["c"], anti[q]["c"]) + anti[p]["r"] + anti[q]["r"] for p in g for q in g)
        slots.append((ext, g))
    slots.sort(reverse=True)
    long_ = [s for s in slots if s[0] > SLOT_LEN]
    P(f"  antipad chains with webs < {SLOT_WEB} mm: {len(slots)}; longer than {SLOT_LEN} mm: {len(long_)}")
    for ext, g in slots[:10]:
        xs_ = [anti[k]["c"][0] for k in g]; ys_ = [anti[k]["c"][1] for k in g]
        nets = sorted({anti[k]["net"].split("/")[-1] for k in g})
        P(f"    {'SLOT ' if ext > SLOT_LEN else 'chain'} {ext:5.2f} mm, {len(g)} holes, x {min(xs_):.2f}-{max(xs_):.2f} "
          f"y {min(ys_):.2f}-{max(ys_):.2f}: {', '.join(nets[:8])}")
    l2 = outline_mask(EDGE)
    for h in anti:
        disc(l2, h["c"], h["r"])
    lab, n = ndimage.label(l2)
    sizes = ndimage.sum(l2, lab, range(1, n + 1)) * RES * RES
    main = int(np.argmax(sizes)) + 1 if n else 0
    P(f"  connectivity (raster {RES} mm): {n} copper region(s); main {sizes[main - 1]:.1f} mm2" if n else "  no copper")
    for k in range(1, n + 1):
        if k == main:
            continue
        ii, jj = np.nonzero(lab == k)
        P(f"    ISLAND {sizes[k - 1]:.3f} mm2 at x {jj.min() * RES:.2f}-{jj.max() * RES:.2f} y {ii.min() * RES:.2f}-{ii.max() * RES:.2f}")
    # narrowest necks: the distance transform of the copper; ridge cells (local maxima across the neck) with
    # width < SLOT_WEB on the main region
    dist = ndimage.distance_transform_edt(l2, sampling=RES)
    ridge = (dist == ndimage.maximum_filter(dist, size=5)) & l2
    neck = ridge & (2 * dist < SLOT_WEB) & (dist > 0)
    nl, nn = ndimage.label(ndimage.binary_dilation(neck, iterations=4))
    necks = []
    for k in range(1, nn + 1):
        ii, jj = np.nonzero((nl == k) & neck)
        if len(ii):
            w_ = 2 * dist[ii, jj].min()
            necks.append((w_, jj.mean() * RES, ii.mean() * RES, (jj.max() - jj.min() + ii.max() - ii.min()) * RES))
    necks.sort()
    P(f"  copper necks narrower than {SLOT_WEB} mm (raster ridge): {len(necks)}")
    for w_, x_, y_, ln in necks[:10]:
        P(f"    {w_:.3f} mm wide at ({x_:.2f}, {y_:.2f}), ridge extent {ln:.2f} mm")
    fills = D.get("fill", {})
    if fills:
        P(f"  KiCad fill of a GND zone on In1 (copy): {len(fills.get('pc L2 GND', []))} filled outline(s), "
          f"{sum(len(p['holes']) for p in fills.get('pc L2 GND', []))} holes")
        for p in fills.get("pc L2 GND", [])[1:]:
            xs_ = [q[0] for q in p["outline"]]; ys_ = [q[1] for q in p["outline"]]
            P(f"    extra fill piece x {min(xs_):.2f}-{max(xs_):.2f} y {min(ys_):.2f}-{max(ys_):.2f}")
    # ------------------------------------------------------------------ L3
    P("L3 (In2.Cu): VBAT pour in the front band, GND pour behind it, lanes / vias / PTH of other nets cut out")
    band = np.zeros((NY, NX), bool)
    for x0, y0, x1, y1 in BAND:
        band |= (gx >= x0) & (gx < x1) & (gy >= y0) & (gy < y1)
    l3 = {}
    for name, region, net in (("VBAT", band, "VBAT"), ("GND", ~band, "GND")):
        m = outline_mask(EDGE) & region
        # the GND/VBAT boundary: 0.2 mm each side
        m &= ~ndimage.binary_dilation(region & ~ndimage.binary_erosion(region, iterations=1), iterations=int(0.2 / RES))
        for tr in D["l3"]:
            if tr["net"] != net:
                capsule(m, tr["a"], tr["b"], tr["w"] / 2 + TRK_CLR)
        for h in holes:
            if h["net"] != net:
                disc(m, h["c"], max(h["drill"] / 2 + CLR_HOLE, h["d"] / 2 + TRK_CLR if h["kind"] == "via" else 0))
        lab3, n3 = ndimage.label(m)
        s3 = ndimage.sum(m, lab3, range(1, n3 + 1)) * RES * RES
        order = np.argsort(-s3)
        P(f"  {name} pour: {n3} piece(s); largest {s3[order[0]]:.1f} mm2" if n3 else f"  {name}: none")
        for k in order[1:12]:
            ii, jj = np.nonzero(lab3 == k + 1)
            P(f"    piece {s3[k]:.2f} mm2 at x {jj.min() * RES:.2f}-{jj.max() * RES:.2f} y {ii.min() * RES:.2f}-{ii.max() * RES:.2f}")
        if n3 > 12:
            P(f"    ... {n3 - 12} more pieces, {s3[order[12:]].sum():.2f} mm2 together")
        l3[name] = (m, lab3, order[0] + 1 if n3 else 0)
    # ------------------------------------------------------------------ picture
    fig, axs = plt.subplots(2, 1, figsize=(W / 4, H / 2))
    img = np.ones((NY, NX, 3))
    img[l2] = (0.55, 0.7, 0.55)
    if n:
        img[l2 & (lab != main)] = (1, 0, 0)
    img[neck] = (1, 0, 1)
    axs[0].imshow(img, extent=(0, W, H, 0), interpolation="nearest")
    for ext, g in long_:
        for k in g:
            axs[0].add_patch(plt.Circle(anti[k]["c"], anti[k]["r"], fill=False, ec="red", lw=0.8))
    axs[0].set_title("L2 GND plane (green), islands red, necks < 0.25 mm magenta, slot chains > 3 mm circled", fontsize=8)
    img3 = np.ones((NY, NX, 3))
    for name, col in (("VBAT", (0.9, 0.6, 0.5)), ("GND", (0.55, 0.7, 0.55))):
        m, lab3, mainp = l3[name]
        img3[m] = col
        img3[m & (lab3 != mainp)] = (1, 0, 0)
    axs[1].imshow(img3, extent=(0, W, H, 0), interpolation="nearest")
    axs[1].set_title("L3: VBAT (band) / GND pours with lanes cut out; pieces cut off from the main pour red", fontsize=8)
    for ax in axs:
        ax.set_xticks(range(0, int(W) + 1, 5)); ax.set_yticks(range(0, int(H) + 1, 5)); ax.tick_params(labelsize=6)
    fig.savefig(OUT / "planecheck.png", dpi=150, bbox_inches="tight")
    (OUT / "planecheck.txt").write_text("\n".join(rep) + "\n")
    print("\n".join(rep))
    print("picture:", OUT / "planecheck.png")


if __name__ == "__main__":
    {"dump": dump, "check": check}[sys.argv[1]]()
