"""Where the detailed router left opens: signal/rail unconnected items from out/fr/drc.json (pour nets left out),
clustered by 5 mm region and by the parts at their ends, drawn over the placement.
    uv run --no-project --with matplotlib python fr_opens.py"""
import collections
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OX, OY = 100.0, 70.0
POUR = {"VBAT", "BAT_IN", "PSW_S", "VBAT_SW", "W_A", "W_B", "W_C", "W_SLA", "W_SLB", "W_SLC", "L_A", "L_B", "L_C",
        "R_A", "R_B", "R_C", "L_VM", "R_VM"}
d = json.load(open(HERE / "out" / "fr" / "drc.json"))
opens = []
for u in d.get("unconnected_items", []):
    its = u["items"]
    m = re.search(r"\[(.*?)\]", its[0]["description"])
    net = m.group(1).split("/")[-1] if m else "?"
    if net in POUR:
        continue
    ends = []
    for it in its:
        r = re.search(r"of (\w+)", it["description"])
        ends.append((r.group(1) if r else it["description"][:18], it["pos"]["x"] - OX, it["pos"]["y"] - OY))
    opens.append((net, ends))
print(f"{len(opens)} signal/rail opens")
reg = collections.Counter()
parts = collections.Counter()
for net, ends in opens:
    for ref, x, y in ends:
        reg[(int(x // 5) * 5, int(y // 5) * 5)] += 1
        parts[ref] += 1
print("by 5 mm region (end points):", ", ".join(f"{x},{y}:{n}" for (x, y), n in reg.most_common(15)))
print("by part:", ", ".join(f"{r}:{n}" for r, n in parts.most_common(25)))
for net, ends in sorted(opens):
    print(f"  {net:12s} " + "  ->  ".join(f"{r}({x:.1f},{y:.1f})" for r, x, y in ends))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
g = json.load(open(HERE / "out" / "geom_place.json"))
fig, ax = plt.subplots(figsize=(26, 11), dpi=70)
ax.set_xlim(-1, 86); ax.set_ylim(36, -1); ax.set_aspect("equal")
ax.add_patch(Rectangle((0, 0), 85, 35, fill=False, lw=2))
for p in g["parts"]:
    x0, y0, x1, y1 = p["box"]
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, lw=0.5, ec="#888" if p["side"] == "B" else "#333",
                           ls="--" if p["side"] == "B" else "-"))
    ax.text((x0 + x1) / 2, (y0 + y1) / 2, p["ref"], fontsize=6, ha="center", va="center", color="#666")
for net, ends in opens:
    xs, ys = [e[1] for e in ends], [e[2] for e in ends]
    ax.plot(xs, ys, "-o", color="red", lw=1.2, ms=3)
    ax.text(xs[0], ys[0], net, fontsize=6, color="red")
ax.set_title(f"{len(opens)} signal/rail opens after Freerouting (red); parts: solid top, dashed bottom")
fig.tight_layout()
fig.savefig(HERE / "out" / "fr_opens.png")
