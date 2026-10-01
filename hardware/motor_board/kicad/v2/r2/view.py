"""Zoomed view of a board region: courtyards (top solid, bottom dashed), pads with net names, tracks per layer, vias,
spec keep-outs, and the opens of a DRC report.
    /usr/bin/python3 r2/view.py dump <board.kicad_pcb> <out.json>
    uv run --no-project --with matplotlib python r2/view.py plot <dump.json> x0 y0 x1 y1 <out.png> [F,L3,B] [drc.json] [nets]
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

if sys.argv[1] == "dump":
    import pcbnew
    b = pcbnew.LoadBoard(sys.argv[2])
    t = pcbnew.ToMM
    bb = b.GetBoardEdgesBoundingBox()
    OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
    LN = {pcbnew.F_Cu: "F", pcbnew.In1_Cu: "L2", pcbnew.In2_Cu: "L3", pcbnew.B_Cu: "B"}

    def xy(p):
        return [round(t(p.x) - OX, 4), round(t(p.y) - OY, 4)]
    D = dict(parts=[], pads=[], tracks=[], vias=[])
    for f in b.GetFootprints():
        side = "B" if f.IsFlipped() else "T"
        cy = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
        r = cy.BBox() if cy.OutlineCount() else f.GetBoundingBox(False)
        D["parts"].append(dict(ref=f.GetReference(), side=side, box=[t(r.GetLeft()) - OX, t(r.GetTop()) - OY,
                                                                      t(r.GetRight()) - OX, t(r.GetBottom()) - OY]))
        for p in f.Pads():
            r = p.GetBoundingBox()
            tht = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            D["pads"].append(dict(ref=f.GetReference(), num=p.GetNumber(), net=p.GetNetname(), side="TB" if tht else side,
                                  c=xy(p.GetPosition()), box=[t(r.GetLeft()) - OX, t(r.GetTop()) - OY, t(r.GetRight()) - OX,
                                                              t(r.GetBottom()) - OY]))
    for x in b.GetTracks():
        if x.GetClass() == "PCB_VIA":
            D["vias"].append(dict(net=x.GetNetname(), c=xy(x.GetPosition()), d=round(t(x.GetWidth(pcbnew.F_Cu)), 3),
                                  drill=round(t(x.GetDrillValue()), 3)))
        elif x.GetClass() == "PCB_TRACK":
            D["tracks"].append(dict(net=x.GetNetname(), layer=LN.get(x.GetLayer(), "?"), a=xy(x.GetStart()), b=xy(x.GetEnd()),
                                    w=round(t(x.GetWidth()), 3)))
    json.dump(D, open(sys.argv[3], "w"))
    print(len(D["parts"]), "parts", len(D["tracks"]), "tracks", len(D["vias"]), "vias")
    sys.exit(0)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

D = json.load(open(sys.argv[2]))
x0, y0, x1, y1 = map(float, sys.argv[3:7])
out = sys.argv[7]
show = sys.argv[8].split(",") if len(sys.argv) > 8 and sys.argv[8] else ["F", "L3", "B"]
drc = json.load(open(sys.argv[9])) if len(sys.argv) > 9 and sys.argv[9] else None
hl = set(sys.argv[10].split(",")) if len(sys.argv) > 10 else set()
COL = {"F": "#d62728", "L3": "#e08a00", "B": "#1f5fbf"}
sc = 1.0 if (x1 - x0) > 25 else 1.6
fig, ax = plt.subplots(figsize=((x1 - x0) * 0.75 * sc, (y1 - y0) * 0.75 * sc), dpi=80)
ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect("equal")
ax.set_xticks([x / 2 for x in range(int(2 * x0), int(2 * x1) + 1)])
ax.set_yticks([y / 2 for y in range(int(2 * y0), int(2 * y1) + 1)])
ax.tick_params(labelsize=6)
ax.grid(lw=0.3, alpha=0.4)


def inb(p, m=1.0):
    return x0 - m <= p[0] <= x1 + m and y0 - m <= p[1] <= y1 + m


def short(n):
    return n.split("/")[-1] if n else ""


try:
    sys.path.insert(0, str(HERE.parent))
    import spec as S
    for (a, b_, c, d), side, name in S.KEEPOUT:
        ax.add_patch(Rectangle((a, b_), c - a, d - b_, fill=False, ec="#2ca02c" if side == "T" else "#9467bd",
                               lw=0.8, ls=":", alpha=0.8))
except Exception as e:  # noqa: BLE001
    print("no keep-outs:", e)
for p in D["parts"]:
    b = p["box"]
    if not (inb(b[:2], 6) or inb(b[2:], 6)):
        continue
    if ("T" if "F" in show else "") + ("B" if "B" in show else "") and p["side"] not in (("T" if "F" in show else "") + ("B" if "B" in show else "")):
        continue
    ax.add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1], fill=False, ec="k" if p["side"] == "T" else "#1f5fbf",
                           lw=0.8, ls="-" if p["side"] == "T" else "--"))
    ax.text(b[0] + 0.05, b[1] + 0.05, p["ref"], fontsize=6 * sc, va="top", ha="left",
            color="k" if p["side"] == "T" else "#1f5fbf", clip_on=True, weight="bold")
for p in D["pads"]:
    if not inb(p["c"]):
        continue
    if p["side"] == "T" and "F" not in show or p["side"] == "B" and "B" not in show:
        continue
    b = p["box"]
    fc = {"T": "#f4a582", "B": "#92c5de", "TB": "#999999"}[p["side"]]
    ax.add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1], fc=fc, alpha=0.75, ec="k", lw=0.3))
    ax.text(p["c"][0], p["c"][1], f"{p['num']}\n{short(p['net'])[:9]}", fontsize=3.2 * sc, ha="center", va="center", clip_on=True)
for l in ("B", "L3", "F"):
    if l not in show:
        continue
    for t_ in D["tracks"]:
        if t_["layer"] == l and (inb(t_["a"]) or inb(t_["b"])):
            a = 0.85 if (not hl or short(t_["net"]) in hl) else 0.25
            ax.plot([t_["a"][0], t_["b"][0]], [t_["a"][1], t_["b"][1]], color=COL[l], lw=t_["w"] * 40 * sc, alpha=a,
                    solid_capstyle="round")
for v in D["vias"]:
    if inb(v["c"]):
        ax.add_patch(Circle(v["c"], v["d"] / 2, fc="#bbb", ec="k", lw=0.4))
        ax.text(v["c"][0], v["c"][1] - v["d"] / 2 - 0.05, short(v["net"])[:8], fontsize=2.8 * sc, ha="center", va="bottom", clip_on=True)
if drc:
    for u in drc["unconnected_items"]:
        ps = [(i["pos"]["x"] - 100, i["pos"]["y"] - 70) for i in u["items"]]
        if any(inb(p, 0) for p in ps):
            m = re.search(r"\[([^\]]+)\]", u["items"][0]["description"])
            ax.plot([ps[0][0], ps[1][0]], [ps[0][1], ps[1][1]], "m--", lw=0.8)
            ax.text((ps[0][0] + ps[1][0]) / 2, (ps[0][1] + ps[1][1]) / 2, short(m.group(1)) if m else "?", color="m",
                    fontsize=5 * sc, clip_on=True)
fig.savefig(out, bbox_inches="tight")
print("wrote", out)
