"""Composite plot of a board region from a geometry export, with the open connections of a DRC report drawn in.
uv run --no-project --with matplotlib python plot.py geom.json drc.json x0 y0 x1 y1 out.png [layers] [nets]
layers: comma list of F,B,L3,L4 (default all); nets: comma list to highlight (others drawn faint)."""
import json
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

g = json.load(open(sys.argv[1]))
drc = json.load(open(sys.argv[2]))
x0, y0, x1, y1 = map(float, sys.argv[3:7])
out = sys.argv[7]
LY = {"F": "F.Cu", "B": "B.Cu", "L3": "In2.Cu", "L4": "In3.Cu"}
show = [LY[k] for k in (sys.argv[8].split(",") if len(sys.argv) > 8 and sys.argv[8] else LY)]
hl = set(sys.argv[9].split(",")) if len(sys.argv) > 9 else set()
COL = {"F.Cu": "#d62728", "B.Cu": "#1f5fbf", "In2.Cu": "#e08a00", "In3.Cu": "#17a2b8"}
fig, ax = plt.subplots(figsize=((x1 - x0) * 0.9, (y1 - y0) * 0.9), dpi=90)
ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect("equal")
ax.set_xticks(range(int(x0), int(x1) + 1)); ax.set_yticks(range(int(y0), int(y1) + 1)); ax.grid(lw=0.3, alpha=0.4)
inb = lambda p, m=1: x0 - m <= p[0] <= x1 + m and y0 - m <= p[1] <= y1 + m
for l in ("B.Cu", "In2.Cu", "In3.Cu", "F.Cu"):
    if l not in show:
        continue
    for p in g["pads"]:
        if (l in p["layers"]) and inb(p["c"]):
            b = p["box"]
            a = 0.9 if (not hl or p["net"] in hl) else 0.25
            ax.add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1], fc=COL[l], alpha=a * 0.6, ec="k", lw=0.3))
            if l in ("F.Cu", "B.Cu"):
                ax.text(p["c"][0], p["c"][1], f"{p['ref']}.{p['num']}", fontsize=4, ha="center", va="center")
    for t in g["tracks"]:
        if t["layer"] == l and (inb(t["a"]) or inb(t["b"])):
            a = 0.9 if (not hl or t["net"] in hl) else 0.3
            ax.plot([t["a"][0], t["b"][0]], [t["a"][1], t["b"][1]], color=COL[l], lw=t["w"] * 50, alpha=a,
                    solid_capstyle="round")
for v in g["vias"]:
    if inb(v["c"]):
        ax.add_patch(Circle(v["c"], v["d"] / 2, fc="#999", ec="k", lw=0.4, alpha=0.9 if (not hl or v["net"] in hl) else 0.4))
for u in drc["unconnected_items"]:
    ps = [(i["pos"]["x"] - 100, i["pos"]["y"] - 70) for i in u["items"]]
    if any(inb(p, 0) for p in ps):
        net = re.search(r"\[([^\]]+)\]", u["items"][0]["description"]).group(1)
        ax.plot([ps[0][0], ps[1][0]], [ps[0][1], ps[1][1]], "m--", lw=1)
        ax.text((ps[0][0] + ps[1][0]) / 2, (ps[0][1] + ps[1][1]) / 2, net.split("/")[-1], color="m", fontsize=6)
fig.savefig(out, bbox_inches="tight")
