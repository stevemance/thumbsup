"""Placement render: both sides, courtyards coloured by block, pads, reference labels, and the ratsnest (a minimum
spanning tree per signal net; rails left out).  Two steps:
    /usr/bin/python3 render.py dump            # pcbnew -> out/geom_place.json
    uv run --no-project --with matplotlib python render.py plot [out.png]"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OX, OY = 100.0, 70.0
RAILS = {"GND", "+3V3", "+3V3A", "+5V", "VBAT", ""}

if sys.argv[1] == "dump":
    import pcbnew
    sys.path.insert(0, str(HERE))
    from blocknets import blk
    b = pcbnew.LoadBoard(sys.argv[2] if len(sys.argv) > 2 else str(HERE.parent / "motor_board" / "motor_board.kicad_pcb"))
    t = pcbnew.ToMM
    parts, pads = [], []
    for f in b.GetFootprints():
        side = "B" if f.IsFlipped() else "T"
        cy = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
        bb = cy.BBox() if cy.OutlineCount() else f.GetBoundingBox(False)
        parts.append(dict(ref=f.GetReference(), side=side, block=blk.get(f.GetReference(), "?"),
                          box=[t(bb.GetLeft()) - OX, t(bb.GetTop()) - OY, t(bb.GetRight()) - OX, t(bb.GetBottom()) - OY]))
        for p in f.Pads():
            pb = p.GetBoundingBox()
            tht = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            pads.append(dict(ref=f.GetReference(), num=p.GetNumber(), net=p.GetNetname(), side="TB" if tht else side,
                             c=[t(p.GetPosition().x) - OX, t(p.GetPosition().y) - OY],
                             box=[t(pb.GetLeft()) - OX, t(pb.GetTop()) - OY, t(pb.GetRight()) - OX, t(pb.GetBottom()) - OY]))
    json.dump(dict(parts=parts, pads=pads), open(sys.argv[3] if len(sys.argv) > 3 else OUT / "geom_place.json", "w"))
    print(len(parts), "parts", len(pads), "pads")
    sys.exit(0)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

g = json.load(open(OUT / "geom_place.json"))
out = sys.argv[2] if len(sys.argv) > 2 else str(OUT / "place.png")
blocks = sorted({p["block"] for p in g["parts"]})
cmap = plt.get_cmap("tab20")
col = {b: cmap(i % 20) for i, b in enumerate(blocks)}
nets = {}
for p in g["pads"]:
    if p["net"] not in RAILS and not p["net"].startswith("unconnected"):
        nets.setdefault(p["net"], []).append(p)


def mst(pts):
    if len(pts) < 2:
        return []
    inT, edges = {0}, []
    d = {i: (math.dist(pts[0], pts[i]), 0) for i in range(1, len(pts))}
    while d:
        j = min(d, key=lambda k: d[k][0])
        edges.append((pts[d[j][1]], pts[j]))
        inT.add(j)
        del d[j]
        for k in d:
            dk = math.dist(pts[j], pts[k])
            if dk < d[k][0]:
                d[k] = (dk, j)
    return edges


fig, axs = plt.subplots(2, 1, figsize=(26, 22), dpi=70)
for ax, side, title in ((axs[0], "T", "TOP (L1)"), (axs[1], "B", "BOTTOM (L4), seen from the top")):
    ax.set_xlim(-1, 86); ax.set_ylim(36, -1); ax.set_aspect("equal"); ax.set_title(title, fontsize=16)
    ax.add_patch(Rectangle((0, 0), 85, 35, fill=False, lw=2))
    ax.set_xticks(range(0, 86, 5)); ax.set_yticks(range(0, 36, 5)); ax.grid(lw=0.3, alpha=0.4)
    for p in g["parts"]:
        if p["side"] != side:
            continue
        x0, y0, x1, y1 = p["box"]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, color=col[p["block"]], alpha=0.35))
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, lw=0.6))
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, p["ref"], ha="center", va="center", fontsize=6 if (x1 - x0) < 3 else 8)
    for p in g["pads"]:
        if side in p["side"]:
            x0, y0, x1, y1 = p["box"]
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, color="#c87533" if p["side"] != "TB" else "#555", alpha=0.8))
    for n, ps in nets.items():
        for a, b in mst([tuple(p["c"]) for p in ps]):
            ax.plot([a[0], b[0]], [a[1], b[1]], lw=0.35, color="#0044cc", alpha=0.5)
fig.tight_layout()
fig.savefig(out)
print("wrote", out)
