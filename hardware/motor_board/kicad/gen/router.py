"""Grid router for scripted "interactive-style" routing: one connection at a time, in the order and on the layers the
block specs ask for, clear of every other net by the net classes' width + clearance.

    uv run --no-project --with numpy --with scipy --with matplotlib python router.py geom.json blocks.json routes.json

Model: 0.05 mm grid on the routing layers F.Cu, In2.Cu, In3.Cu, B.Cu (In1 and In4 are GND planes: vias pass, no tracks).  Each cell
records the net whose copper covers it (pours as their outlines, then pads, tracks, vias on top).  A request routes one
connection with A* (45-degree moves, per-layer costs, a via cost); the result becomes an obstacle for the next request.
Pads are treated as their bounding boxes, so the router is slightly conservative next to round and rounded pads."""
import heapq
import json
import os
import math
import sys

import numpy as np
from matplotlib.path import Path as MPath
from scipy import ndimage

RES = 0.05
MARGIN = 0.045              # rasterisation error allowance on every clearance
EDGE_CLR = 0.3              # copper to board edge
RL = ["F.Cu", "In2.Cu", "In3.Cu", "B.Cu"]

G = json.load(open(sys.argv[1]))
REQ = json.load(open(sys.argv[2]))
W, H = G["board"]
NX, NY = int(round(W / RES)) + 1, int(round(H / RES)) + 1
NETS = sorted(G["nets"])
NID = {n: i for i, n in enumerate(NETS)}
CLR = np.array([G["nets"][n]["clr"] for n in NETS] + [0.15], float)     # last entry: keep-outs / no net

owner = {l: np.full((NY, NX), -1, np.int32) for l in RL}
zown = {l: np.full((NY, NX), -1, np.int32) for l in RL}          # pours: block other nets' tracks; vias only by request
notrack = {l: np.zeros((NY, NX), bool) for l in RL}
novia = np.zeros((NY, NX), bool)
smd = {l: np.full((NY, NX), -1, np.int32) for l in RL}           # SMD pad copper (no via-in-pad, any net)
XS = (np.arange(NX) * RES)
YS = (np.arange(NY) * RES)


def cidx(x, y):
    return int(round(y / RES)), int(round(x / RES))


def win(x0, y0, x1, y1):
    i0, j0 = max(0, int(math.floor(y0 / RES))), max(0, int(math.floor(x0 / RES)))
    i1, j1 = min(NY, int(math.ceil(y1 / RES)) + 1), min(NX, int(math.ceil(x1 / RES)) + 1)
    return i0, i1, j0, j1


def draw_rect(arr, box, val):
    i0, i1, j0, j1 = win(*box)
    ys, xs = YS[i0:i1, None], XS[None, j0:j1]
    m = (xs >= box[0]) & (xs <= box[2]) & (ys >= box[1]) & (ys <= box[3])
    arr[i0:i1, j0:j1][m] = val


def draw_disc(arr, c, r, val):
    i0, i1, j0, j1 = win(c[0] - r, c[1] - r, c[0] + r, c[1] + r)
    ys, xs = YS[i0:i1, None], XS[None, j0:j1]
    m = (xs - c[0]) ** 2 + (ys - c[1]) ** 2 <= r * r
    arr[i0:i1, j0:j1][m] = val


def draw_capsule(arr, a, b, r, val):
    i0, i1, j0, j1 = win(min(a[0], b[0]) - r, min(a[1], b[1]) - r, max(a[0], b[0]) + r, max(a[1], b[1]) + r)
    ys, xs = YS[i0:i1, None], XS[None, j0:j1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy or 1e-12
    u = np.clip(((xs - a[0]) * dx + (ys - a[1]) * dy) / L2, 0, 1)
    m = (xs - a[0] - u * dx) ** 2 + (ys - a[1] - u * dy) ** 2 <= r * r
    arr[i0:i1, j0:j1][m] = val


def draw_poly(arr, pts, val):
    xs_, ys_ = [p[0] for p in pts], [p[1] for p in pts]
    i0, i1, j0, j1 = win(min(xs_), min(ys_), max(xs_), max(ys_))
    gx, gy = np.meshgrid(XS[j0:j1], YS[i0:i1])
    m = MPath(pts).contains_points(np.c_[gx.ravel(), gy.ravel()]).reshape(gx.shape)
    arr[i0:i1, j0:j1][m] = val


# ---------------------------------------------------------------- build the model
for z in G["zones"]:
    if z["layer"] in RL and z["net"] and not z["name"].endswith("GND fill"):   # the outer GND fills pour last, around everything
        draw_poly(zown[z["layer"]], z["poly"], NID[z["net"]])
for r in G["rules"]:
    for l in r["layers"]:
        if l in RL and (r["no_tracks"] or r["no_copper"]):
            draw_poly(notrack[l], r["poly"], True)
    if r["no_vias"] or r["no_copper"]:
        draw_poly(novia, r["poly"], True)
for p in G["pads"]:
    nid = NID.get(p["net"], len(NETS))            # net-less pads (NPTH, paste) still block
    for l in p["layers"]:
        if l not in RL:
            continue
        if p["shape"] == "circle":
            draw_disc(owner[l], p["c"], (p["box"][2] - p["box"][0]) / 2, nid)
        else:
            draw_rect(owner[l], p["box"], nid)
        if not p["tht"]:
            draw_rect(smd[l], p["box"], nid)
    if p["tht"] and p["drill"]:
        draw_disc(novia, p["c"], p["drill"] / 2 + 0.25, True)            # hole-to-hole
for t_ in G["tracks"]:
    if t_["layer"] in RL:
        draw_capsule(owner[t_["layer"]], t_["a"], t_["b"], t_["w"] / 2, NID[t_["net"]])
VIAS_OF = {}                     # net id -> [(x, y)]: existing vias are free layer changes for their own net


def note_via(n, c):
    VIAS_OF.setdefault(n, []).append((c[0], c[1]))


for v in G["vias"]:
    note_via(NID[v["net"]], v["c"])
    for l in RL:
        draw_disc(owner[l], v["c"], v["d"] / 2, NID[v["net"]])
    draw_disc(novia, v["c"], 0.3 / 2 + 0.25, True)                       # hole-to-hole (drill <= 0.3)
edge_dist = np.minimum.reduce([YS[:, None] + 0 * XS[None, :], (H - YS)[:, None] + 0 * XS[None, :],
                               XS[None, :] + 0 * YS[:, None], (W - XS)[None, :] + 0 * YS[:, None]])
R_CORNER = 1.5
for cx, cy in ((R_CORNER, R_CORNER), (W - R_CORNER, R_CORNER), (R_CORNER, H - R_CORNER), (W - R_CORNER, H - R_CORNER)):
    gx, gy = np.meshgrid(XS, YS)
    corner = ((gx - cx) * (1 if cx > W / 2 else -1) > 0) & ((gy - cy) * (1 if cy > H / 2 else -1) > 0)
    d = R_CORNER - np.hypot(gx - cx, gy - cy)
    edge_dist = np.where(corner, np.minimum(edge_dist, d), edge_dist)
# distance to the nearest no-track keep-out cell: a track's EDGE must stay out, not just its centreline
nt_dist = {l: ndimage.distance_transform_edt(~notrack[l], sampling=RES) for l in RL}


def pad_of(ref, num):
    for p in G["pads"]:
        if p["ref"] == ref and p["num"] == num:
            return p
    raise KeyError((ref, num))


def endpoint(e):
    """-> list of (layer, i, j) start/goal cells, and a representative point."""
    k = e[0]
    if k == "pad":
        p = pad_of(e[1], e[2])
        i, j = cidx(*p["c"])
        return [(l, i, j) for l in p["layers"] if l in RL], tuple(p["c"])
    if k == "via":
        i, j = cidx(e[1], e[2])
        return [(l, i, j) for l in RL], (e[1], e[2])
    if k == "pt":
        i, j = cidx(e[1], e[2])
        return [(e[3], i, j)], (e[1], e[2])
    raise ValueError(e)


def route(req):
    net = req["net"]
    n = NID[net]
    cls = G["nets"][net]
    w = req.get("w", cls["w"])
    clr = max(req.get("clr", cls["clr"]), 0.127)
    vd, vdr = req.get("via", cls["via"]), req.get("drill", cls["drill"])
    layers = req.get("layers", RL)
    lcost = req.get("layer_cost", {})
    via_cost = req.get("via_cost", 1.5)
    tol = req.get("tol", MARGIN)          # extra clearance over the rules (rasterisation allowance); lower next to
                                          # hand-placed lanes that sit at exactly the minimum pitch
    starts, pa = endpoint(req["a"])
    drop = req["b"][0] == "drop"             # ("drop",): end at the nearest legal via spot (e.g. a GND pad to the plane)
    goals, pb = ([], pa) if drop else endpoint(req["b"])
    starts = [s for s in starts if s[0] in layers]
    goals = [g for g in goals if g[0] in layers]
    m = req.get("margin", 5.0)
    x0, y0 = max(0, min(pa[0], pb[0]) - m), max(0, min(pa[1], pb[1]) - m)
    x1, y1 = min(W, max(pa[0], pb[0]) + m), min(H, max(pa[1], pb[1]) + m)
    i0, i1, j0, j1 = win(x0, y0, x1, y1)
    pad = 12                                                           # EDT guard band (cells)
    gi0, gi1, gj0, gj1 = max(0, i0 - pad), min(NY, i1 + pad), max(0, j0 - pad), min(NX, j1 + pad)
    free_t, free_v = {}, np.ones((i1 - i0, j1 - j0), bool)
    for l in RL:
        o0 = owner[l][gi0:gi1, gj0:gj1]
        zo = zown[l][gi0:gi1, gj0:gj1]
        o = np.where(o0 != -1, o0, zo)                      # copper incl. pours
        other = (o != -1) & (o != n)
        dist, idx = ndimage.distance_transform_edt(~other, sampling=RES, return_indices=True)
        near = o[idx[0], idx[1]]
        if req.get("via_through_pours"):                    # a via of another net in a pour just gets a clearance hole
            other_v = (o0 != -1) & (o0 != n)
            dist_v, idx_v = ndimage.distance_transform_edt(~other_v, sampling=RES, return_indices=True)
            near_v = o0[idx_v[0], idx_v[1]]
        else:
            dist_v, near_v = dist, near
        cn = np.where(near >= 0, CLR[np.clip(near, 0, len(CLR) - 1)], 0.15)
        need_t = w / 2 + np.maximum(clr, cn) + tol
        cn_v = np.where(near_v >= 0, CLR[np.clip(near_v, 0, len(CLR) - 1)], 0.15)
        need_v = vd / 2 + np.maximum(clr, cn_v) + tol
        sl = (slice(i0 - gi0, i1 - gi0), slice(j0 - gj0, j1 - gj0))
        ok_t = (dist[sl] >= need_t[sl]) & (nt_dist[l][i0:i1, j0:j1] >= w / 2 + tol) & (edge_dist[i0:i1, j0:j1] >= w / 2 + EDGE_CLR)
        free_t[l] = ok_t if l in layers else np.zeros_like(ok_t)
        s = smd[l][i0:i1, j0:j1]
        sd = ndimage.distance_transform_edt(s < 0, sampling=RES)
        free_v &= (dist_v[sl] >= need_v[sl]) & (sd >= vd / 2 + 0.05)
    free_v &= ~novia[i0:i1, j0:j1] & (edge_dist[i0:i1, j0:j1] >= vd / 2 + EDGE_CLR)
    # reserved corridors: [layer or "*", x0, y0, x1, y1] boxes this request may not use (a via anywhere in a box on
    # any of its layers is refused too, since the barrel crosses every layer)
    for bl, bx0, by0, bx1, by1 in req.get("avoid", []):
        bi0, bj0 = cidx(bx0, by0)
        bi1, bj1 = cidx(bx1, by1)
        bi0, bi1 = max(bi0, i0) - i0, min(bi1 + 1, i1) - i0
        bj0, bj1 = max(bj0, j0) - j0, min(bj1 + 1, j1) - j0
        if bi0 >= bi1 or bj0 >= bj1:
            continue
        for l in RL:
            if bl in ("*", l) and l in free_t:
                free_t[l][bi0:bi1, bj0:bj1] = False
        free_v[bi0:bi1, bj0:bj1] = False
    # endpoints are always enterable (they sit in the net's own copper)
    for l, i, j in starts + goals:
        if l in free_t and i0 <= i < i1 and j0 <= j < j1:
            free_t[l][i - i0, j - j0] = True
    goalset = {(l, i - i0, j - j0) for l, i, j in goals}
    own_vias = set()
    for vx, vy in VIAS_OF.get(n, []):
        vi_, vj_ = cidx(vx, vy)
        if i0 <= vi_ < i1 and j0 <= vj_ < j1:
            own_vias.add((vi_ - i0, vj_ - j0))
            for l in RL:                                        # its barrel is the net's own copper on every layer
                if l in layers:
                    free_t[l][vi_ - i0, vj_ - j0] = True
    if drop:
        own = {l for l, _, _ in starts}
        ii, jj = np.nonzero(free_v)
        goalset = {(l, i, j) for l in own for i, j in zip(ii, jj) if free_t[l][i, j]}
    hi, hj = (pb[1] / RES - i0), (pb[0] / RES - j0)
    minc = 0.0 if drop else min([lcost.get(l, 1.0) for l in layers] or [1.0])     # drop: plain Dijkstra
    lidx = {l: k for k, l in enumerate(RL)}
    Hh, Ww = i1 - i0, j1 - j0
    best = {}
    heap = []
    for l, i, j in starts:
        s = (l, i - i0, j - j0)
        if 0 <= s[1] < Hh and 0 <= s[2] < Ww:
            best[s] = 0.0
            heapq.heappush(heap, (0.0, 0.0, s, None))
    parent = {}
    steps = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)]
    found = None
    while heap:
        f, g, s, par = heapq.heappop(heap)
        if s in parent:
            continue
        parent[s] = par
        if s in goalset:
            found = s
            break
        l, i, j = s
        c = lcost.get(l, 1.0)
        for di, dj, k in steps:
            ni, nj = i + di, j + dj
            if not (0 <= ni < Hh and 0 <= nj < Ww) or not free_t[l][ni, nj]:
                continue
            if di and dj and not (free_t[l][i + di, j] and free_t[l][i, j + dj]):
                continue
            t2 = (l, ni, nj)
            ng = g + RES * k * c
            if ng < best.get(t2, 1e18):
                best[t2] = ng
                h = RES * minc * (max(abs(ni - hi), abs(nj - hj)) + 0.4142 * min(abs(ni - hi), abs(nj - hj)))
                heapq.heappush(heap, (ng + h, ng, t2, s))
        if free_v[i, j] or (i, j) in own_vias:
            for l2 in layers:
                if l2 == l or not free_t[l2][i, j]:
                    continue
                t2 = (l2, i, j)
                ng = g + (0.0 if (i, j) in own_vias else via_cost)
                if ng < best.get(t2, 1e18):
                    best[t2] = ng
                    h = RES * minc * (max(abs(i - hi), abs(j - hj)) + 0.4142 * min(abs(i - hi), abs(j - hj)))
                    heapq.heappush(heap, (ng + h, ng, t2, s))
    if not found:
        return None
    path = []
    s = found
    while s is not None:
        path.append(s)
        s = parent[s]
    path.reverse()
    pts = [(l, (j + j0) * RES, (i + i0) * RES) for l, i, j in path]
    pts[0] = (pts[0][0], pa[0], pa[1])
    if drop:
        pb = (pts[-1][1], pts[-1][2])
    pts[-1] = (pts[-1][0], pb[0], pb[1])
    # split into per-layer runs, simplify collinear points
    tracks, vias = [], []
    run = [pts[0]]
    for p in pts[1:]:
        if p[0] != run[-1][0]:
            tracks.append(run)
            if not any(abs(p[1] - vx) < 0.06 and abs(p[2] - vy) < 0.06 for vx, vy in VIAS_OF.get(n, [])):
                vias.append((p[1], p[2]))                       # (an existing own via needs no new one)
            run = [p]
        else:
            run.append(p)
    tracks.append(run)
    out_t = []
    for r_ in tracks:
        if len(r_) < 2:
            continue
        simp = [r_[0]]
        for k in range(1, len(r_) - 1):
            a, b_, c_ = simp[-1], r_[k], r_[k + 1]
            cross = (b_[1] - a[1]) * (c_[2] - a[2]) - (b_[2] - a[2]) * (c_[1] - a[1])
            if abs(cross) > 1e-9:
                simp.append(b_)
        simp.append(r_[-1])
        out_t.append(dict(net=net, layer=r_[0][0], pts=[[round(p[1], 4), round(p[2], 4)] for p in simp], w=w))
    if drop:
        vias.append(pb)
    out_v = [dict(net=net, c=[round(x, 4), round(y, 4)], d=vd, drill=vdr) for x, y in vias]
    # the new copper is an obstacle for the next requests
    for tt in out_t:
        for a, b_ in zip(tt["pts"], tt["pts"][1:]):
            draw_capsule(owner[tt["layer"]], a, b_, w / 2, n)
    for v in out_v:
        note_via(n, v["c"])
        for l in RL:
            draw_disc(owner[l], v["c"], vd / 2, n)
        draw_disc(novia, v["c"], vdr / 2 + 0.25, True)
    length = sum(math.dist(a, b_) for tt in out_t for a, b_ in zip(tt["pts"], tt["pts"][1:]))
    return dict(tracks=out_t, vias=out_v, length=round(length, 2))


def fixed(req):
    out_t, out_v = [], []
    for tt in req["fixed"].get("tracks", []):
        n = NID[tt["net"]]
        for a, b_ in zip(tt["pts"], tt["pts"][1:]):
            draw_capsule(owner[tt["layer"]], a, b_, tt["w"] / 2, n)
        out_t.append(tt)
    for v in req["fixed"].get("vias", []):
        note_via(NID[v["net"]], v["c"])
        n = NID[v["net"]]
        for l in RL:
            draw_disc(owner[l], v["c"], v["d"] / 2, n)
        draw_disc(novia, v["c"], v["drill"] / 2 + 0.25, True)
        out_v.append(v)
    return dict(tracks=out_t, vias=out_v, length=0)


BASE_OWNER = {l: owner[l].copy() for l in RL}
BASE_NOVIA = novia.copy()
BASE_VIAS = {k: list(v) for k, v in VIAS_OF.items()}


def paint(res):
    for tt in res["tracks"]:
        n = NID[tt["net"]]
        for a, b_ in zip(tt["pts"], tt["pts"][1:]):
            draw_capsule(owner[tt["layer"]], a, b_, tt["w"] / 2, n)
    for v in res["vias"]:
        n = NID[v["net"]]
        note_via(n, v["c"])
        for l in RL:
            draw_disc(owner[l], v["c"], v["d"] / 2, n)
        draw_disc(novia, v["c"], v.get("drill", 0.2) / 2 + 0.25, True)


def rebuild(keep):
    for l in RL:
        owner[l][:] = BASE_OWNER[l]
    novia[:] = BASE_NOVIA
    VIAS_OF.clear()
    VIAS_OF.update({k: list(v) for k, v in BASE_VIAS.items()})
    for res in keep:
        paint(res)


results = []
done = set()
for req in REQ:
    tag = req.get("tag") or req["net"]
    if req.get("retry"):                      # second pass: only for requests that failed the first time
        if tag in done:
            continue
    r = fixed(req) if "fixed" in req else route(req)
    if r is not None:
        done.add(tag)
    if r is None:
        if req.get("retry") or not any(q.get("retry") and (q.get("tag") or q["net"]) == tag for q in REQ):
            print(f"FAIL  {tag}")             # final: no retry left for it
        results.append(dict(tag=tag, ok=False))
    else:
        print(f"{'ok2 ' if req.get('retry') else 'ok  '}  {tag}: {r['length']} mm, {len(r['vias'])} vias, layers {sorted({t['layer'] for t in r['tracks']})}")
        results.append(dict(tag=tag, ok=True, **r))
    results[-1]["_req"] = req


# ---------------------------------------------------------------- rip-up and reroute (post-pass)
# A request that finally failed is routed once with every *soft* route lifted (requests marked soft: router-made
# local routes; hand-placed geometry and planned buses never are); the soft routes its path runs into are ripped up,
# the failed request routed, then the ripped ones re-routed in their original order.  Kept only if all of them route.
def seg_d(a, b, c, d):
    def pt(p, q, r_):
        dx, dy = q[0] - p[0], q[1] - p[1]
        L2 = dx * dx + dy * dy
        u = 0 if L2 == 0 else max(0, min(1, ((r_[0] - p[0]) * dx + (r_[1] - p[1]) * dy) / L2))
        return math.hypot(r_[0] - p[0] - u * dx, r_[1] - p[1] - u * dy)
    return min(pt(a, b, c), pt(a, b, d), pt(c, d, a), pt(c, d, b))


def clash(p, q):
    for t1 in p["tracks"]:
        for t2 in q["tracks"]:
            if t1["layer"] != t2["layer"] or t1["net"] == t2["net"]:
                continue
            for a, b_ in zip(t1["pts"], t1["pts"][1:]):
                for c, d in zip(t2["pts"], t2["pts"][1:]):
                    if seg_d(a, b_, c, d) < (t1["w"] + t2["w"]) / 2 + 0.2:
                        return True
    for v in p["vias"] + q["vias"]:
        other = q if v in p["vias"] else p
        for t2 in other["tracks"]:
            if t2["net"] == v["net"]:
                continue
            for c, d in zip(t2["pts"], t2["pts"][1:]):
                if seg_d(c, d, v["c"], v["c"]) < v["d"] / 2 + t2["w"] / 2 + 0.2:
                    return True
    return False


if os.environ.get("RRR", "1") == "1":
    final_fail = {}
    for k, res in enumerate(results):
        if not res["ok"] and res["tag"] not in done:
            final_fail[res["tag"]] = k
    won = 0
    for tag, kf in final_fail.items():
        freq = results[kf]["_req"]
        if "fixed" in freq:
            continue
        soft = [k for k, r_ in enumerate(results) if r_["ok"] and r_["_req"].get("soft")]
        rebuild([r_ for k, r_ in enumerate(results) if r_["ok"] and k not in soft])
        probe = route(dict(freq, retry=False))
        if probe is None:
            continue
        blockers = [k for k in soft if clash(probe, results[k])]
        if not blockers or len(blockers) > 4:
            continue
        keep = [r_ for k, r_ in enumerate(results) if r_["ok"] and k not in blockers]
        rebuild(keep)
        rf = route(freq)
        new = {}
        if rf is not None:
            for k in blockers:
                rr = route(results[k]["_req"])
                if rr is None:
                    break
                new[k] = rr
        if rf is not None and len(new) == len(blockers):
            for k, rr in new.items():
                results[k] = dict(results[k], **rr)
            results[kf] = dict(tag=tag, ok=True, _req=freq, **rf)
            done.add(tag)
            won += 1
            print(f"rrr   {tag}: rerouted, ripped {len(blockers)}")
    rebuild([r_ for r_ in results if r_["ok"]])
    print(f"rip-up and reroute: {won} of {len(final_fail)} failures recovered")
for r_ in results:
    r_.pop("_req", None)
json.dump(results, open(sys.argv[3], "w"), indent=0)
