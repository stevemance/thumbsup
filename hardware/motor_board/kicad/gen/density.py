"""Board density map: copper coverage per layer, via density, part (courtyard) coverage, and a combined 'routing
pressure' map, with the open connections drawn on top.

uv run --no-project --with numpy --with scipy --with matplotlib python density.py geom.json drc.json cy.json out.png [cell_mm]

Rasterised at 0.1 mm, averaged over cell_mm squares (default 2 mm).  Copper counts track width + clearance halo
(0.13 mm) so 'full' means no room for another track; vias count their pad + halo on every copper layer."""
import json
import re
import sys

import matplotlib
import numpy as np
from scipy import ndimage

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

geom, drc, cyf, out = sys.argv[1:5]
CELL = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
g = json.load(open(geom))
d = json.load(open(drc))
cy = json.load(open(cyf))
W, H = g["board"]
RES = 0.1
NX, NY = int(W / RES) + 1, int(H / RES) + 1
HALO = 0.13
LAYERS = ["F.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"]
NAMES = {"F.Cu": "F (top)", "In2.Cu": "L3 (VBAT feed + bus)", "In3.Cu": "L4 (signals, 3V3 fill)",
         "In4.Cu": "L5 (GND plane)", "B.Cu": "B (bottom)"}
ys, xs = np.mgrid[0:NY, 0:NX] * RES


def seg_mask(a, b, r):
    x0, x1 = min(a[0], b[0]) - r, max(a[0], b[0]) + r
    y0, y1 = min(a[1], b[1]) - r, max(a[1], b[1]) + r
    i0, i1 = max(0, int(y0 / RES)), min(NY, int(y1 / RES) + 2)
    j0, j1 = max(0, int(x0 / RES)), min(NX, int(x1 / RES) + 2)
    X, Y = xs[i0:i1, j0:j1], ys[i0:i1, j0:j1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 == 0:
        dd = np.hypot(X - a[0], Y - a[1])
    else:
        u = np.clip(((X - a[0]) * dx + (Y - a[1]) * dy) / L2, 0, 1)
        dd = np.hypot(X - a[0] - u * dx, Y - a[1] - u * dy)
    return (slice(i0, i1), slice(j0, j1)), dd <= r


def box_mask(bx, pad=0.0):
    i0, i1 = max(0, int((bx[1] - pad) / RES)), min(NY, int((bx[3] + pad) / RES) + 1)
    j0, j1 = max(0, int((bx[0] - pad) / RES)), min(NX, int((bx[2] + pad) / RES) + 1)
    return slice(i0, i1), slice(j0, j1)


occ = {l: np.zeros((NY, NX), bool) for l in LAYERS}
for t in g["tracks"]:
    if t["layer"] in occ:
        sl, m = seg_mask(t["a"], t["b"], t["w"] / 2 + HALO)
        occ[t["layer"]][sl] |= m
viam = np.zeros((NY, NX), bool)
for v in g["vias"]:
    sl, m = seg_mask(v["c"], v["c"], v["d"] / 2 + HALO)
    viam[sl] |= m
    for l in LAYERS:
        occ[l][sl] |= m
for p in g["pads"]:
    ls = LAYERS if p["tht"] else [l for l in p["layers"] if l in occ]
    for l in ls:
        occ[l][box_mask(p["box"], HALO)] = True
from matplotlib.path import Path as MPath  # noqa: E402
pts = np.c_[xs.ravel(), ys.ravel()]
for z in g["zones"]:                     # power pours are copper too (the GND / 3V3 fills and planes are not obstacles)
    if z["layer"] not in occ or z["name"].endswith("fill") or "plane" in z["name"]:
        continue
    poly = np.array(z["poly"])
    x0, y0 = poly.min(0); x1, y1 = poly.max(0)
    sl = box_mask((x0, y0, x1, y1))
    sub = np.c_[xs[sl].ravel(), ys[sl].ravel()]
    occ[z["layer"]][sl] |= MPath(poly).contains_points(sub).reshape(xs[sl].shape)
cyd = {"F": np.zeros((NY, NX), bool), "B": np.zeros((NY, NX), bool)}
for r, c in cy.items():
    cyd[c["side"]][box_mask(c["box"])] = True
# power pours (named copper zones other than the plane / fill pours) count as full on their layer
k = int(CELL / RES)


def cellavg(m):
    return ndimage.uniform_filter(m.astype(float), size=k, mode="constant")


fig, axs = plt.subplots(3, 3, figsize=(36, 14))
panels = [(NAMES[l], cellavg(occ[l])) for l in LAYERS]
panels.append(("via density (share of area in via + halo)", cellavg(viam) * 3))
panels.append(("parts, top (courtyards)", cellavg(cyd["F"])))
panels.append(("parts, bottom (courtyards)", cellavg(cyd["B"])))
# routing pressure: mean of the four signal-usable layers' occupancy + parts on both sides
press = (cellavg(occ["F.Cu"]) + cellavg(occ["B.Cu"]) + cellavg(occ["In3.Cu"]) + cellavg(occ["In4.Cu"]) + cellavg(occ["In2.Cu"])) / 5
panels.append(("combined routing pressure (all 5 layers)", press))
opens = []
for u in d["unconnected_items"]:
    net = re.search(r"\[([^\]]*)\]", u["items"][0]["description"]).group(1)
    ps = [(i["pos"]["x"] - 100, i["pos"]["y"] - 70) for i in u["items"]]
    if net != "GND" and len(ps) == 2:
        opens.append((net.split("/")[-1], ps))
for ax, (title, im) in zip(axs.flat, panels):
    h = ax.imshow(im, extent=(0, W, H, 0), cmap="inferno", vmin=0, vmax=1, interpolation="bilinear")
    ax.set_title(title)
    ax.set_xticks(range(0, int(W) + 1, 5)); ax.set_yticks(range(0, int(H) + 1, 5)); ax.grid(lw=0.3, alpha=0.3)
    for net, (a, b) in opens:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="cyan", lw=1.2)
        ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, net, color="cyan", fontsize=6)
    for r, c in cy.items():
        if len(c["pads"]) >= 8:
            bx = c["box"]
            ax.add_patch(plt.Rectangle((bx[0], bx[1]), bx[2] - bx[0], bx[3] - bx[1], fill=False, ec="lime" if c["side"] == "F" else "deepskyblue", lw=0.6))
            ax.text(bx[0], bx[1], r, color="lime" if c["side"] == "F" else "deepskyblue", fontsize=6)
fig.colorbar(h, ax=axs, shrink=0.6)
fig.savefig(out, dpi=70)
fig2, ax = plt.subplots(figsize=(26, 11))
ax.imshow(press, extent=(0, W, H, 0), cmap="inferno", vmin=0, vmax=0.8, interpolation="bilinear")
ax.set_title("combined routing pressure (mean copper occupancy over 5 layers, incl. power pours) + open connections")
ax.set_xticks(range(0, int(W) + 1, 5)); ax.set_yticks(range(0, int(H) + 1, 5)); ax.grid(lw=0.3, alpha=0.4)
for net, (a, b) in opens:
    ax.plot([a[0], b[0]], [a[1], b[1]], color="cyan", lw=2)
    ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, net, color="cyan", fontsize=10)
for r, c in cy.items():
    bx = c["box"]
    col = "lime" if c["side"] == "F" else "deepskyblue"
    big = len(c["pads"]) >= 8 or (bx[2] - bx[0]) * (bx[3] - bx[1]) > 12
    ax.add_patch(plt.Rectangle((bx[0], bx[1]), bx[2] - bx[0], bx[3] - bx[1], fill=False, ec=col, lw=0.8 if big else 0.3, alpha=0.9 if big else 0.5))
    if big:
        ax.text(bx[0] + 0.2, bx[1] + 0.8, r, color=col, fontsize=8)
fig2.savefig(out.replace(".png", "_combined.png"), dpi=70)
# coarse numbers: per 5 x 5 mm block, mean pressure, printed as a table
B = int(5 / RES)
print("pressure per 5 mm block (rows y, cols x), 0-100:")
print("     " + " ".join(f"{x:>3d}" for x in range(0, int(W), 5)))
for i in range(0, NY - 1, B):
    row = [int(100 * press[i:i + B, j:j + B].mean()) for j in range(0, NX - 1, B)]
    print(f"{i * RES:4.0f} " + " ".join(f"{v:3d}" for v in row))
