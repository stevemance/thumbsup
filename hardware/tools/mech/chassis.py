#!/usr/bin/env python3
"""Chassis geometry from the Bambu 3MF files in ../../../models.

Loads the meshes (with the 3MF build transforms, so the parts are in print
coordinates: Z up, plate at Z = 0), slices them at chosen heights, and renders
the slices so the PCB bay, mounting bosses and height limits can be read off.

    python3 chassis.py slices          # PNGs of Z slices of the main chassis
    python3 chassis.py floor           # height map of upward-facing floor area
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
MODELS = ROOT / "models"
OUT = ROOT / "hardware" / "mech"


def _mat(t: str) -> np.ndarray:
    v = [float(x) for x in t.split()]
    m = np.eye(4)
    m[:3, :3] = np.array(v[:9]).reshape(3, 3).T  # 3MF stores row vectors: m00 m01 m02 m10 ...
    m[:3, 3] = v[9:12]
    return m


def load(part: str) -> tuple[np.ndarray, np.ndarray]:
    """Vertices (N,3) in print coordinates and triangles (M,3) of one chassis part."""
    z = zipfile.ZipFile(MODELS / f"Chassis - {part}.3mf")
    root = z.read("3D/3dmodel.model").decode()
    verts, tris = [], []
    # component -> object file transforms, then build item transform
    item = re.search(r'<item objectid="(\d+)"[^>]*transform="([^"]+)"', root)
    build_m = _mat(item.group(2))
    for comp in re.finditer(r'<component p:path="([^"]+)" objectid="(\d+)"[^>]*transform="([^"]+)"', root):
        path, oid, tr = comp.groups()
        text = z.read(path.lstrip("/")).decode()
        obj = re.search(rf'<object id="{oid}".*?</object>', text, re.S)
        if not obj:
            continue
        v = np.array(re.findall(r'<vertex x="([-\d.e+]+)" y="([-\d.e+]+)" z="([-\d.e+]+)"', obj.group(0)), dtype=float)
        t = np.array(re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"', obj.group(0)), dtype=int)
        m = build_m @ _mat(tr)
        vh = np.c_[v, np.ones(len(v))] @ m.T
        tris.append(t + sum(len(x) for x in verts))
        verts.append(vh[:, :3])
    return np.vstack(verts), np.vstack(tris)


def slice_z(V: np.ndarray, T: np.ndarray, z: float) -> np.ndarray:
    """Line segments (K,2,2) of the mesh cut by the plane Z=z."""
    p = V[T]  # (M,3,3)
    segs = []
    for tri in p:
        d = tri[:, 2] - z
        if (d > 0).all() or (d < 0).all():
            continue
        pts = []
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            da, db = a[2] - z, b[2] - z
            if da * db < 0:
                t = da / (da - db)
                pts.append(a[:2] + t * (b[:2] - a[:2]))
        if len(pts) == 2:
            segs.append(pts)
    return np.array(segs)


def render_slices(part: str, heights, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    V, T = load(part)
    zmin, zmax = V[:, 2].min(), V[:, 2].max()
    print(f"{part}: x[{V[:,0].min():.1f},{V[:,0].max():.1f}] y[{V[:,1].min():.1f},{V[:,1].max():.1f}] z[{zmin:.1f},{zmax:.1f}]")
    n = len(heights)
    fig, axes = plt.subplots(1, n, figsize=(6 * n, 6))
    for ax, z in zip(np.atleast_1d(axes), heights):
        segs = slice_z(V, T, z)
        for s in segs:
            ax.plot(s[:, 0], s[:, 1], "k-", lw=0.5)
        ax.set_aspect("equal")
        ax.set_title(f"{part} Z={z:.1f} mm")
        ax.grid(True, lw=0.2)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90)
    print("wrote", out)


def floor_map(part: str, out: Path, cell: float = 1.0) -> None:
    """Height of the highest upward-facing surface per XY cell (where can a board sit)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    V, T = load(part)
    p = V[T]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    up = n[:, 2] > 0.5 * np.linalg.norm(n, axis=1)  # faces pointing up
    xs = np.arange(V[:, 0].min(), V[:, 0].max(), cell)
    ys = np.arange(V[:, 1].min(), V[:, 1].max(), cell)
    H = np.full((len(ys), len(xs)), np.nan)
    for tri in p[up]:
        c = tri.mean(axis=0)
        i = int((c[1] - ys[0]) / cell)
        j = int((c[0] - xs[0]) / cell)
        if 0 <= i < len(ys) and 0 <= j < len(xs):
            H[i, j] = np.nanmax([H[i, j], c[2]])
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(H, origin="lower", extent=[xs[0], xs[-1], ys[0], ys[-1]], cmap="viridis")
    fig.colorbar(im, label="Z of up-facing surface [mm]")
    ax.set_title(f"{part}: upward-facing surface height")
    fig.savefig(out, dpi=90)
    print("wrote", out)


def raster_floor(V: np.ndarray, T: np.ndarray, cell: float = 0.5):
    """Rasterised height of the highest upward-facing surface per XY cell (proper
    triangle fill, not centroids)."""
    p = V[T]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    nn = np.linalg.norm(n, axis=1)
    up = n[:, 2] > 0.7 * np.where(nn == 0, 1, nn)
    x0, y0 = V[:, 0].min(), V[:, 1].min()
    xs = np.arange(x0, V[:, 0].max() + cell, cell)
    ys = np.arange(y0, V[:, 1].max() + cell, cell)
    H = np.full((len(ys), len(xs)), np.nan)
    for tri in p[up]:
        xmin, xmax = tri[:, 0].min(), tri[:, 0].max()
        ymin, ymax = tri[:, 1].min(), tri[:, 1].max()
        i0, i1 = int((ymin - y0) / cell), int((ymax - y0) / cell) + 1
        j0, j1 = int((xmin - x0) / cell), int((xmax - x0) / cell) + 1
        gx, gy = np.meshgrid(xs[j0:j1], ys[i0:i1])
        # barycentric test
        a, b, c = tri[:, :2]
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(det) < 1e-9:
            continue
        l1 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / det
        l2 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / det
        l3 = 1 - l1 - l2
        inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        z = l1 * tri[0, 2] + l2 * tri[1, 2] + l3 * tri[2, 2]
        sub = H[i0:i1, j0:j1]
        sub[inside] = np.fmax(sub[inside], z[inside])
    return xs, ys, H


def render_floor2(part: str, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    V, T = load(part)
    xs, ys, H = raster_floor(V, T)
    fig, ax = plt.subplots(figsize=(12, 9))
    im = ax.imshow(H, origin="lower", extent=[xs[0], xs[-1], ys[0], ys[-1]], cmap="turbo", vmin=0, vmax=np.nanmax(H))
    fig.colorbar(im, label="Z of highest up-facing surface [mm]")
    ax.set_xticks(np.arange(int(xs[0]) // 10 * 10, xs[-1], 10))
    ax.set_yticks(np.arange(int(ys[0]) // 10 * 10, ys[-1], 10))
    ax.grid(True, lw=0.3, color="w", alpha=0.5)
    ax.set_title(f"{part}: up-facing surface height (0.5 mm cells)")
    fig.savefig(out, dpi=90)
    print("wrote", out)
    np.save(out.with_suffix(".npy"), np.stack([np.broadcast_to(xs, H.shape), np.broadcast_to(ys[:, None], H.shape), H]))


def render_xsections(part: str, out: Path, ycuts=(150.0, 165.0, 128.0), xcuts=(128.0, 100.0)) -> None:
    """Vertical cross sections: X–Z at given Y, Y–Z at given X."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    V, T = load(part)
    cuts = [("y", y) for y in ycuts] + [("x", x) for x in xcuts]
    fig, axes = plt.subplots(len(cuts), 1, figsize=(14, 3.2 * len(cuts)))
    for ax, (axis, c) in zip(axes, cuts):
        # reuse slice_z by swapping axes
        W = V.copy()
        if axis == "y":
            W = W[:, [0, 2, 1]]  # x, z, y  -> slice on 'y' as the third coord
        else:
            W = W[:, [1, 2, 0]]
        segs = slice_z(W, T, c)
        for s in segs:
            ax.plot(s[:, 0], s[:, 1], "k-", lw=0.6)
        ax.set_aspect("equal")
        ax.grid(True, lw=0.3)
        ax.set_title(f"{part}: section at {axis}={c} (horizontal = {'x' if axis == 'y' else 'y'}, vertical = z)")
    fig.tight_layout()
    fig.savefig(out, dpi=90)
    print("wrote", out)



# ---------------------------------------------------------------- board outline
# Measured from the Main Chassis mesh (print coordinates, mm): floor top at Z=2.0,
# bay inner walls x=74.5 / 182.0, back wall y=175.5, corner blocks x<84 & x>172 for
# y<145, neck walls x=99.5 / 156.5 for y<136, drum cradle from y=118, lid-screw
# bosses (Ø7, 14 mm tall) at (79,171) and (176,171), floor through-hole at (105,125).
CLEAR = 1.0          # wall clearance
FLOOR_Z = 2.0
# chassis-frame polygon (counter-clockwise as seen from above)
BAY_POLY = [
    (76.0, 158.0), (76.0, 147.5), (85.5, 147.5), (85.5, 137.0),
    (109.0, 137.0), (109.0, 123.5), (155.5, 123.5), (155.5, 137.0),
    (170.5, 137.0), (170.5, 147.5), (180.5, 147.5), (180.5, 158.0),
    (164.0, 174.5), (92.5, 174.5),
]
HOLES = [(79.7, 155.7), (177.5, 154.0), (128.8, 127.2)]  # M2.5 bosses to add to the print (board (3.7,18.8) (101.5,20.5) (52.8,47.3))
STANDOFF = 3.0       # board underside above the floor
ORIGIN = (76.0, 174.5)  # chassis point that becomes board (0, 0); board Y grows toward the drum


def to_board(p):
    return (round(p[0] - ORIGIN[0], 3), round(ORIGIN[1] - p[1], 3))


def fit_check(V, T, poly, holes, clear=CLEAR):
    """Every point of the (dilated) board must sit over floor at Z<=FLOOR_Z+0.5 with no
    wall/boss above it; returns a list of offending chassis points."""
    xs, ys, H = raster_floor(V, T, 0.5)
    import matplotlib.path as mpath

    path = mpath.Path(poly)
    bad = []
    for i, y in enumerate(ys):
        for j, x in enumerate(xs):
            if path.contains_point((x, y), radius=-1e-9) or path.contains_point((x, y), radius=clear):
                h = H[i, j]
                if np.isnan(h):
                    if not any((x - hx) ** 2 + (y - hy) ** 2 < 2.0 ** 2 for hx, hy in holes):
                        bad.append((x, y, "hole in floor"))
                elif h > FLOOR_Z + 0.5:
                    bad.append((x, y, f"obstacle z={h:.1f}"))
    return bad, (xs, ys, H)


def board_outline(scratch: Path | None = None) -> dict:
    V, T = load("Main Chassis")
    bad, (xs, ys, H) = fit_check(V, T, BAY_POLY, HOLES)
    print(f"fit check: {len(bad)} offending cells")
    for b in bad[:10]:
        print("  ", b)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 9))
    ax.imshow(H, origin="lower", extent=[xs[0], xs[-1], ys[0], ys[-1]], cmap="turbo", vmin=0, vmax=np.nanmax(H))
    px = [p[0] for p in BAY_POLY] + [BAY_POLY[0][0]]
    py = [p[1] for p in BAY_POLY] + [BAY_POLY[0][1]]
    ax.plot(px, py, "w-", lw=2)
    for hx, hy in HOLES:
        ax.add_patch(plt.Circle((hx, hy), 1.6, color="w", fill=False, lw=2))
    for x, y, _ in bad:
        ax.plot(x, y, "rx", ms=4)
    ax.set_title("board outline (white) over chassis floor map; red = fit violations")
    out = (scratch or OUT) / "board_fit.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90)
    print("wrote", out)
    data = {
        "units": "mm",
        "frame": "board: origin = chassis (76.0, 174.5), x right, y toward the drum (KiCad convention)",
        "chassis_floor_z": FLOOR_Z,
        "standoff": STANDOFF,
        "clearance_to_walls": CLEAR,
        "outline": [to_board(p) for p in BAY_POLY],
        "holes_m25": [to_board(h) for h in HOLES],
        "notes": [
            "lid-screw bosses at chassis (79,171) and (176,171) are cleared by the 16.5 mm corner chamfers",
            "neck (board y 37.5..51, x 33..79.5) lies under the drum: parts there <= 8 mm tall",
            "back wall (board y=0) is the vent grille; side walls (x=0 / x=104.5) are plastic wheel pods: Pico antenna end at the x=104.5 edge",
            "floor through-hole at chassis (105,125) is outside the neck (neck starts at x=109)",
        ],
        "fit_violations": len(bad),
    }
    import json

    (OUT).mkdir(parents=True, exist_ok=True)
    (OUT / "board_outline.json").write_text(json.dumps(data, indent=1))
    print("wrote", OUT / "board_outline.json")
    return data


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "slices"
    scratch = Path(sys.argv[2]) if len(sys.argv) > 2 else OUT
    if cmd == "slices":
        render_slices("Main Chassis", [1.5, 3.0, 5.0, 8.0, 14.0, 24.0], scratch / "chassis_slices.png")
    elif cmd == "floor":
        floor_map("Main Chassis", scratch / "chassis_floor.png")
    elif cmd == "top":
        render_slices("Top", [1.0, 3.0, 6.0, 10.0, 14.0], scratch / "top_slices.png")
    elif cmd == "floor2":
        render_floor2("Main Chassis", scratch / "chassis_floor2.png")
    elif cmd == "outline":
        board_outline(scratch)
    elif cmd == "xsec":
        render_xsections("Main Chassis", scratch / "chassis_xsec.png")
