"""Courtyard map of a region (both sides): python3 cymap.py board x0 y0 x1 y1 out.png  (board-local mm)"""
import json
import subprocess
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
t = pcbnew.ToMM
bb = b.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
x0, y0, x1, y1 = map(float, sys.argv[2:6])
rows = []
for f in b.GetFootprints():
    for side, lay in (("F", pcbnew.F_CrtYd), ("B", pcbnew.B_CrtYd)):
        c = f.GetCourtyard(lay)
        if c.OutlineCount() == 0:
            continue
        r = c.BBox()
        box = (t(r.GetLeft()) - OX, t(r.GetTop()) - OY, t(r.GetRight()) - OX, t(r.GetBottom()) - OY)
        if box[2] > x0 and box[0] < x1 and box[3] > y0 and box[1] < y1:
            rows.append((f.GetReference(), side, [round(v, 2) for v in box]))
json.dump(dict(region=[x0, y0, x1, y1], parts=rows), open(sys.argv[6] + ".json", "w"))
subprocess.run(["uv", "run", "--no-project", "--with", "matplotlib", "python", "-c", f"""
import json, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
d = json.load(open({sys.argv[6] + '.json'!r}))
x0, y0, x1, y1 = d['region']
fig, axs = plt.subplots(1, 2, figsize=((x1 - x0) * 1.2, (y1 - y0) * 0.6), dpi=80)
for ax, side in zip(axs, 'FB'):
    ax.set_title(side); ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect('equal'); ax.grid(lw=0.3)
    for ref, s, (a, b_, c, e) in d['parts']:
        if s == side:
            ax.add_patch(Rectangle((a, b_), c - a, e - b_, fc='#9cf' if s == 'B' else '#f99', ec='k', lw=0.5, alpha=0.6))
            ax.text((a + c) / 2, (b_ + e) / 2, ref, fontsize=6, ha='center', va='center')
fig.savefig({sys.argv[6]!r}, bbox_inches='tight')
"""])
