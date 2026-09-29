"""Coarse global router: the v2 routability gate (lessons memo 4, P2).
    uv run --no-project --with numpy --with matplotlib python groute.py [--pins out/pinsolve_180.json] [--iters N]
Input: out/geom_place.json (render.py dump).  Output: out/groute.json, out/groute.png, a report on stdout.

Model (memo 3.1):
  tiles 0.5 mm; routing layers L1 (top), L3 (In2), L4 (bottom); L2 is solid GND (never used).
  capacity: each tile carries 0.5 mm of (track width + clearance) per layer; nets use their net-class width.
  pads block their tiles for other nets (THT pads on every layer); board edge 0.3 mm; mounting holes 2.6 mm.
  front power band (y < BAND_Y, and the VM feed strip): L3 = VBAT pour and L4 = solid GND under it, so no signal
      on L3/L4 there and no vias; signals in the band run on L1 only.
  L3 elsewhere is the GND pour with budgeted lanes: an L3 track also consumes the L4 capacity of its tile (the L4
      GND fill that must sit over it).
  exposed-pad thermal fields (U2/U3/U4): no vias, no L3 and no L4 in them (memo: L3 GND island under U3/U4).
  vias: through (L1-L3-L4), at most one per 1 mm cell (plane-integrity proxy), each uses its tile on every layer.
  not routed: GND (planes) and the pour nets (VBAT, pack path, weapon phase / shunt nodes, drive outputs) - their
      pads still block.  Multi-pin nets grow a tree from the first pad.  Negotiated congestion (PathFinder)."""
import heapq
import os
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
PRO = HERE.parent / "motor_board" / "motor_board.kicad_pro"
T = 0.5
W, H = 85.0, 35.0
NX, NY = int(W / T), int(H / T)
V1 = "--v1" in sys.argv      # calibration on attempt 1's 6-layer board: routing on L1, L3, L4, L6 (L2/L5 GND)
LAYERS = ["L1", "L3", "L4", "L6"] if V1 else ["L1", "L3", "L4"]
NL = len(LAYERS)
ALL = tuple(range(NL))
BAND_Y = 18.5
VIA_COST = 6.0
POUR = {"GND", "VBAT", "BAT_IN", "PSW_S", "VBAT_SW", "W_A", "W_B", "W_C", "W_SLA", "W_SLB", "W_SLC",
        "L_A", "L_B", "L_C", "R_A", "R_B", "R_C", ""}
EP_REFS = ("U2", "U3", "U4")

args = sys.argv[1:]
geom = json.load(open(args[args.index("--geom") + 1] if "--geom" in args else OUT / "geom_place.json"))
pinmap = None
if "--pins" in args:
    pinmap = {d["pin"]: n for n, d in json.load(open(args[args.index("--pins") + 1]))["pins"].items()}
iters = int(args[args.index("--iters") + 1]) if "--iters" in args else 40

# ---------------------------------------------------------------- net classes
pro = json.load(open(PRO))
cls = {c["name"]: (c["track_width"], c["clearance"]) for c in pro["net_settings"]["classes"]}
pat = {p["pattern"]: p["netclass"] for p in pro["net_settings"]["netclass_patterns"]}


def short(n):
    return n.split("/")[-1]


def need(full):
    w, c = cls[pat.get(full, "Default")]
    return w + c


# ---------------------------------------------------------------- pads, nets
pads = []
for p in geom["pads"]:
    net = p["net"]
    if p["ref"] == "U1" and pinmap is not None and p["num"] in pinmap:
        net = pinmap[p["num"]]
    elif p["ref"] == "U1" and pinmap is not None and short(net) in pinmap.values():
        net = ""                               # this pin gave its net away in the new pin map
    pads.append(dict(p, net=net))
nets = {}
for p in pads:
    nets.setdefault(p["net"], []).append(p)
route_nets = sorted(n for n in nets if short(n) not in POUR and not short(n).startswith("unconnected") and len(nets[n]) > 1)
nid = {n: i for i, n in enumerate(route_nets)}


def tiles_of(box, pad_margin=0.0):
    """tiles whose centre lies inside the box grown by pad_margin"""
    x0, y0, x1, y1 = box[0] - pad_margin, box[1] - pad_margin, box[2] + pad_margin, box[3] + pad_margin
    i0, i1 = int(math.ceil(x0 / T - 0.5)), int(math.floor(x1 / T - 0.5))
    j0, j1 = int(math.ceil(y0 / T - 0.5)), int(math.floor(y1 / T - 0.5))
    return [(i, j) for i in range(max(i0, 0), min(i1, NX - 1) + 1) for j in range(max(j0, 0), min(j1, NY - 1) + 1)]


def tile(x, y):
    return min(max(int(x / T), 0), NX - 1), min(max(int(y / T), 0), NY - 1)


def pad_tiles(p):
    """a fine-pitch pad (narrow side < 0.6 mm) is one tile row/column through its centre along its long axis, so
    neighbouring pads on a 0.5 mm pitch never share a tile; wider pads block their box + 0.1 mm"""
    x0, y0, x1, y1 = p["box"]
    ci, cj = tile(*p["c"])
    if min(x1 - x0, y1 - y0) < 0.6:
        if x1 - x0 >= y1 - y0:
            i0, i1 = int(math.ceil(x0 / T - 0.5)), int(math.floor(x1 / T - 0.5))
            return sorted({(i, cj) for i in range(max(i0, 0), min(i1, NX - 1) + 1)} | {(ci, cj)})
        j0, j1 = int(math.ceil(y0 / T - 0.5)), int(math.floor(y1 / T - 0.5))
        return sorted({(ci, j) for j in range(max(j0, 0), min(j1, NY - 1) + 1)} | {(ci, cj)})
    return tiles_of(p["box"], 0.0)


# owner: -1 free, -2 blocked, k = only net k may use it
owner = np.full((NL, NX, NY), -1, dtype=np.int32)
CAP = 0.56   # mm of (width + clearance) per 0.5 mm tile: two default tracks (0.127/0.127 at 0.254 pitch) or one gate-class track
cap = np.full((NL, NX, NY), CAP, dtype=np.float64)
via_ok = np.ones((NX, NY), dtype=bool)
L1, L3, L4 = 0, 1, 2
BOT = NL - 1
for p in pads:
    lays = list(ALL) if p["side"] == "TB" else ([L1] if p["side"] == "T" else [BOT])
    k = nid.get(p["net"], -2)
    for (i, j) in pad_tiles(p):
        for l in lays:
            o = owner[l, i, j]
            owner[l, i, j] = k if o == -1 else (o if o == k else -2)
        via_ok[i, j] = False
    ci, cj = tile(*p["c"])
    for l in lays:
        if k >= 0:
            owner[l, ci, cj] = k               # the pad centre is always its own net's entry
    # tiles that only brush the pad's clearance zone keep half their capacity (a trace still fits beside the pad)
    for (i, j) in tiles_of(p["box"], 0.2):
        for l in lays:
            if owner[l, i, j] == -1:
                cap[l, i, j] = min(cap[l, i, j], CAP / 2)
# edge and mounting holes
for i in range(NX):
    for j in range(NY):
        x, y = (i + 0.5) * T, (j + 0.5) * T
        if x < 0.3 or y < 0.3 or x > W - 0.3 or y > H - 0.3:
            owner[:, i, j] = -2; via_ok[i, j] = False
        for mx, my in ((3, 3), (82, 3), (3, 32), (82, 32)):
            if math.hypot(x - mx, y - my) < 2.6:
                owner[:, i, j] = -2; via_ok[i, j] = False
        if y < BAND_Y and not V1:
            owner[L3, i, j] = -2; owner[L4, i, j] = -2; via_ok[i, j] = False
# L1 power pours (pads of the pour net on these parts, convex hull, blocked on L1): pour copper is not signal space
POUR_GROUPS = [
    ("W_A", ("Q1", "Q2", "JW1")), ("W_B", ("Q3", "Q4", "JW2")), ("W_C", ("Q5", "Q6", "JW3")),
    ("W_SLA", ("Q2", "RS1")), ("W_SLB", ("Q4", "RS2")), ("W_SLC", ("Q6", "RS3")),
    ("VBAT", ("Q1", "C25")), ("VBAT", ("Q3", "C26")), ("VBAT", ("Q5", "C31")),
    ("GND", ("RS1", "C25")), ("GND", ("RS2", "C26")), ("GND", ("RS3", "C31")),
    ("BAT_IN", ("JBAT1", "Q7")), ("PSW_S", ("Q7", "Q8")), ("VBAT_SW", ("Q8", "RS4")), ("VBAT", ("RS4", "C1", "D1")),
    ("L_A", ("U3", "JL1")), ("L_B", ("U3", "JL2")), ("L_C", ("U3", "JL3")),
    ("R_A", ("U4", "JR1")), ("R_B", ("U4", "JR2")), ("R_C", ("U4", "JR3")),
    ("L_VM", ("R302", "C302", "C308")), ("R_VM", ("R402", "C402", "C408")),
]


def hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for q in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], q) <= 0:
            lo.pop()
        lo.append(q)
    for q in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], q) <= 0:
            up.pop()
        up.append(q)
    return lo[:-1] + up[:-1]


def inside_poly(x, y, poly):
    if len(poly) < 3:
        return False
    s = None
    for a, b in zip(poly, poly[1:] + poly[:1]):
        c = (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])
        if c != 0:
            if s is None:
                s = c > 0
            elif (c > 0) != s:
                return False
    return True


pour_tiles = 0
# a pour keeps 0.6 mm from other nets' pads: that gap is where e.g. a high-side gate trace leaves the phase strip
near_other = {}
for p in pads:
    for (i, j) in tiles_of(p["box"], 0.6):
        near_other.setdefault((i, j), set()).add(short(p["net"]))
for net, refs in POUR_GROUPS:
    pts = []
    for p in pads:
        if p["ref"] in refs and short(p["net"]) == net and p["side"] in ("T", "TB"):
            x0, y0, x1, y1 = p["box"]
            pts += [(x0, y0), (x0, y1), (x1, y0), (x1, y1)]
    poly = hull(pts)
    if len(poly) < 3:
        continue
    xs, ys = [q[0] for q in poly], [q[1] for q in poly]
    for (i, j) in tiles_of((min(xs), min(ys), max(xs), max(ys))):
        if inside_poly((i + 0.5) * T, (j + 0.5) * T, poly) and owner[L1, i, j] == -1:
            if near_other.get((i, j), set()) - {net}:
                continue
            k = [nid[n] for n in route_nets if short(n) == net]
            owner[L1, i, j] = k[0] if k else -2    # a routed pour net (L_VM/R_VM) keeps its own copper
            pour_tiles += 1

# exposed-pad thermal fields
for ref in EP_REFS:
    ps = [p for p in pads if p["ref"] == ref]
    ep = max(ps, key=lambda p: (p["box"][2] - p["box"][0]) * (p["box"][3] - p["box"][1]))
    for (i, j) in tiles_of(ep["box"], 0.5):
        via_ok[i, j] = False
        owner[BOT, i, j] = -2
    if ref in ("U3", "U4") and not V1:                    # L3 GND island under each DRV8316: EP + 1.5 mm (L2 is the main spreader)
        cx, cy = ep["c"]
        for (i, j) in tiles_of(ep["box"], 1.5):
            owner[L3, i, j] = -2

# ---------------------------------------------------------------- router
N = 3 * NX * NY
def idx(l, i, j):
    return (l * NX + i) * NY + j


occ = np.zeros((NL, NX, NY))
vocc = np.zeros((NX // 2 + 1, NY // 2 + 1))
hist = np.zeros((NL, NX, NY))
hist_v = np.zeros((NX // 2 + 1, NY // 2 + 1))
paths = {}


# L3 lanes (rear band): slow digital nets only.  L3 couples to L4 (0.069 mm), so a lane takes half the L4 tile
# over it: an L4 track may cross it but not run stacked along it.  Analog/sense/gate/charge-pump nets never use L3.
L3_SHARE = 0.0 if V1 else 0.5
# analog nets may use L3 only as a proper stripline: L4 GND fill over the whole lane (full L4 share)
ANALOG = ("SO", "_F", "MTEMP", "TEMPJ", "W_V", "VBAT_SNS", "NTC", "CELL", "BAL")
# never on L3: noisy or loop-critical copper
NO_L3 = ("INA_IN", "W_SN", "W_SP", "W_SL", "BMS_BAT", "AVDD", "VREF", "DVDD", "_CP", "CPH", "CPL", "BUCK", "_GH",
         "_GL", "FBBK", "SWBK", "PSW", "3V3A")


def l3_ok(n):
    if V1:
        return True
    s = short(n)
    return not any(a in s for a in NO_L3)


def l3_share(n):
    if V1:
        return 0.0
    return 1.0 if any(a in short(n) for a in ANALOG) else L3_SHARE


def node_cost(l, i, j, w, pf, sh=0.5):
    over = occ[l, i, j] + w - cap[l, i, j]
    c = (1.0 + hist[l, i, j]) * (1.0 + pf * max(0.0, over) / T)
    if l == L3:
        over4 = occ[L4, i, j] + sh * w - cap[L4, i, j]
        c += (1.0 + hist[L4, i, j]) * pf * max(0.0, over4) / T + 0.3
    return c


def via_cost(i, j, pf, w):
    """a through via takes its tile on every layer: pay that congestion too"""
    o = vocc[i // 2, j // 2]
    c = VIA_COST * (1.0 + hist_v[i // 2, j // 2]) * (1.0 + pf * max(0, o) * 4)
    for l in ALL:
        c += (1.0 + hist[l, i, j]) * pf * max(0.0, occ[l, i, j] + w - cap[l, i, j]) / T
    return c


def usable(l, i, j, k):
    o = owner[l, i, j]
    return o == -1 or o == k


def route_net(n, pf):
    k = nid[n]
    w = need(n)
    l3 = l3_ok(n)
    sh = l3_share(n)
    ps = nets[n]
    targets = []
    for p in ps:
        lays = list(ALL) if p["side"] == "TB" else ([L1] if p["side"] == "T" else [BOT])
        ci, cj = tile(*p["c"])
        targets.append([(l, ci, cj) for l in lays])
    tree = set(targets[0])
    path_nodes, vias = [], []
    remaining = targets[1:]
    # connect the nearest remaining pad each time
    while remaining:
        tx = [(sum(t[0][1] for t in [r]) , r) for r in remaining]
        best_r = min(remaining, key=lambda r: min(abs(r[0][1] - a[1]) + abs(r[0][2] - a[2]) for a in tree))
        remaining.remove(best_r)
        goal = set(best_r)
        gi, gj = best_r[0][1], best_r[0][2]
        dist = {}
        prev = {}
        pq = []
        for s in tree:
            dist[s] = 0.0
            heapq.heappush(pq, (abs(s[1] - gi) + abs(s[2] - gj), 0.0, s))
        found = None
        while pq:
            f, g, u = heapq.heappop(pq)
            if g > dist.get(u, 1e18):
                continue
            if u in goal:
                found = u
                break
            l, i, j = u
            for (di, dj) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ni, nj = i + di, j + dj
                if not (0 <= ni < NX and 0 <= nj < NY):
                    continue
                v = (l, ni, nj)
                if not usable(l, ni, nj, k) and v not in goal:
                    continue
                if l == L3 and owner[L4, ni, nj] == -2:
                    continue
                ng = g + node_cost(l, ni, nj, w, pf, sh)
                if ng < dist.get(v, 1e18):
                    dist[v] = ng; prev[v] = u
                    heapq.heappush(pq, (ng + abs(ni - gi) + abs(nj - gj), ng, v))
            if via_ok[i, j]:
                for nl in ALL:
                    if nl == l or not usable(nl, i, j, k):
                        continue
                    if nl == L3 and (owner[L4, i, j] == -2 or not l3):
                        continue
                    v = (nl, i, j)
                    ng = g + via_cost(i, j, pf, w)
                    if ng < dist.get(v, 1e18):
                        dist[v] = ng; prev[v] = u
                        heapq.heappush(pq, (ng + abs(i - gi) + abs(j - gj), ng, v))
        if found is None:
            if n == os.environ.get("GR_DEBUG"):
                for t, p in zip(targets, ps):
                    seen, stack = set(t), list(t)
                    while stack and len(seen) < 400:
                        l, i, j = stack.pop()
                        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            v = (l, i + di, j + dj)
                            if 0 <= v[1] < NX and 0 <= v[2] < NY and v not in seen and usable(l, v[1], v[2], k):
                                seen.add(v); stack.append(v)
                        if via_ok[i, j]:
                            for nl in ALL:
                                v = (nl, i, j)
                                if v not in seen and usable(nl, i, j, k):
                                    seen.add(v); stack.append(v)
                    print("  debug", n, p["ref"], p["num"], p["side"], "reach", len(seen), "tile", t[0])
            return None
        u = found
        seg = [u]
        while u in prev:
            u = prev[u]
            seg.append(u)
        for a, b in zip(seg, seg[1:]):
            if a[0] != b[0]:
                vias.append((a[1], a[2]))
        path_nodes += seg
        tree |= set(seg) | goal
    return dict(nodes=sorted(set(path_nodes)), vias=sorted(set(vias)), w=w, sh=sh)


def add(r, sign):
    for (l, i, j) in r["nodes"]:
        occ[l, i, j] += sign * r["w"]
        if l == L3:
            occ[L4, i, j] += sign * r.get("sh", L3_SHARE) * r["w"]
    for (i, j) in r["vias"]:
        vocc[i // 2, j // 2] += sign
        for l in ALL:
            occ[l, i, j] += sign * r["w"]


order = sorted(route_nets, key=lambda n: -len(nets[n]))
failed = set()
pf = 0.5
best = None
for it in range(iters):
    for n in order:
        if n in paths:
            add(paths[n], -1)
        r = route_net(n, pf)
        if r is None:
            failed.add(n)
            paths.pop(n, None)
            continue
        failed.discard(n)
        paths[n] = r
        add(r, +1)
    over = np.maximum(occ - cap - 1e-9, 0)
    vover = np.maximum(vocc - 1, 0)
    n_over = int((over > 0).sum()) + int((vover > 0).sum())
    print(f"iter {it:2d}: pf {pf:5.1f}  overflow tiles {int((over > 0).sum()):4d}  via cells {int((vover > 0).sum()):3d}  "
          f"failed {len(failed)}  vias {sum(len(r['vias']) for r in paths.values())}", flush=True)
    score = n_over + 50 * len(failed)
    if best is None or score < best[0]:
        best = (score, it, {n: dict(r) for n, r in paths.items()}, set(failed))
    if n_over == 0 and not failed:
        break
    hist += 0.3 * (over > 0) + over / T
    hist_v += 0.5 * (vover > 0)
    pf *= 1.4

# keep the best iteration
_, best_it, paths, failed = best
occ[:] = 0
vocc[:] = 0
for r in paths.values():
    add(r, +1)
print("best iteration", best_it)

# ---------------------------------------------------------------- report
over = np.maximum(occ - cap - 1e-9, 0)
res = dict(overflow_tiles=[[LAYERS[l], i * T, j * T, round(float(over[l, i, j]), 3)] for l, i, j in zip(*np.nonzero(over))],
           via_cells_over=[[i * 1.0, j * 1.0] for i, j in zip(*np.nonzero(vocc > 1))],
           failed=sorted(failed), vias=sum(len(r["vias"]) for r in paths.values()),
           length_mm={LAYERS[l]: round(float(sum(1 for r in paths.values() for n in r["nodes"] if n[0] == l)) * T, 1) for l in range(NL)},
           paths={n: dict(nodes=r["nodes"], vias=r["vias"]) for n, r in paths.items()})
TAG = "_v1" if V1 else ""
json.dump(res, open(OUT / f"groute{TAG}.json", "w"))
conn = sum(len(nets[n]) - 1 for n in route_nets)
print(f"nets {len(route_nets)}, connections {conn}, vias {res['vias']} ({res['vias'] / conn:.2f}/connection), "
      f"length {res['length_mm']}, overflow tiles {len(res['overflow_tiles'])}, via cells over {len(res['via_cells_over'])}, "
      f"failed {res['failed']}")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig, axs = plt.subplots(NL, 1, figsize=(20, 8.3 * NL), dpi=60)
for l, ax in enumerate(axs):
    u = occ[l] / cap[l]
    blocked = owner[l] == -2
    img = np.where(blocked, np.nan, u).T
    ax.imshow(img, origin="upper", extent=(0, W, H, 0), cmap="viridis", vmin=0, vmax=1.5)
    oy = np.nonzero(over[l] > 0)
    ax.scatter((oy[0] + 0.5) * T, (oy[1] + 0.5) * T, s=12, c="red", marker="s")
    if l == 0:
        for i, j in zip(*np.nonzero(vocc > 0)):
            ax.add_patch(plt.Rectangle((i * 1.0, j * 1.0), 1, 1, fill=False, ec="white" if vocc[i, j] <= 1 else "red", lw=0.6))
    ax.set_title(f"{LAYERS[l]} usage (red = over capacity; white boxes on L1 = via cells)", fontsize=16)
fig.tight_layout()
fig.savefig(OUT / f"groute{TAG}.png")
