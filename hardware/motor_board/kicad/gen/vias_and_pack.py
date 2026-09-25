"""Layout step 2 prep: the "obvious" vias and the pack-path pours (no signal routing).
  - weapon gate escape vias (+ the stub from each gate pin), Q8's PSW_G via
  - pack-path pours on L1: BAT_IN (JBAT1 + Q7 drain), PSW_S (the two source columns), VBAT_SW (Q8 drain + RS4 pad 1),
    VBAT strip (RS4 pad 2, D1 cathode, C1 VBAT) with a via field into the L3 VBAT feed; GND via fields at C1 / D1
  - a GND via (+ stub) at every SMD GND pad that is not already on a GND pour, to the L2 plane
Idempotent-ish: re-running adds nothing where a via of the net is already next to the pad.  /usr/bin/python3; KiCad closed."""
import math
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent / "motor_board"
PCB, PRO = PROJ / "motor_board.kicad_pcb", PROJ / "motor_board.kicad_pro"
pro_before = PRO.read_text()
board = pcbnew.LoadBoard(str(PCB))
t, F = pcbnew.ToMM, pcbnew.FromMM
bb = board.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
BW, BH = t(bb.GetWidth()) - 0.1, t(bb.GetHeight()) - 0.1
net = {str(k).split("/")[-1]: v for k, v in board.GetNetsByName().items() if str(k)}
fps = {f.GetReference(): f for f in board.GetFootprints()}
names = {z.GetZoneName() for z in board.Zones()}
CELLS = {"A": 60.5, "B": 48.0, "C": 35.5}


def L(v):
    return t(v) - OX


def box(p):
    r = p.GetBoundingBox()
    return t(r.GetLeft()) - OX, t(r.GetTop()) - OY, t(r.GetRight()) - OX, t(r.GetBottom()) - OY


PADS = [(box(p), p.GetNetname().split("/")[-1], f.GetReference(), p) for f in board.GetFootprints() for p in f.Pads()]
VIAS = [(t(v.GetPosition().x) - OX, t(v.GetPosition().y) - OY, t(v.GetWidth(pcbnew.F_Cu)) / 2, v.GetNetname().split("/")[-1])
        for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
NO_VIA = []          # rule areas that forbid vias
LANES = []           # bottom lanes kept for the gate/sense routing and the IC escapes: no stitching vias there
OUTER_ZONES = []     # other-net copper pours on L1/L4
for z in board.Zones():
    ol = z.Outline()
    pts = [(t(ol.CVertex(i).x) - OX, t(ol.CVertex(i).y) - OY) for i in range(ol.FullPointCount())]
    if z.GetIsRuleArea():
        if z.GetDoNotAllowVias():
            NO_VIA.append(pts)
        elif any(k in z.GetZoneName() for k in ("corridor", "fan-out", "escape")):
            LANES.append(pts)
    elif z.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
        OUTER_ZONES.append((pts, z.GetNetname().split("/")[-1]))


def inside(poly, x, y):
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def legal(x, y, r, netname, lanes_ok=False, zones_ok=()):
    if x < r + 0.5 or y < r + 0.5 or x > BW - r - 0.5 or y > BH - r - 0.5:
        return False
    for (a, b, c, d), pn, ref, _p in PADS:
        g = 0.05 if pn in (netname, "") else 0.25
        if a - r - g < x < c + r + g and b - r - g < y < d + r + g:
            return False
    for vx, vy, vr, vn in VIAS:
        if math.hypot(x - vx, y - vy) < r + vr + 0.2 - 1e-6:
            return False
    if any(inside(p, x, y) for p in NO_VIA):
        return False
    if not lanes_ok and any(inside(p, x, y) for p in LANES):
        return False
    for poly, zn in OUTER_ZONES:
        if zn != netname and zn not in zones_ok and inside(poly, x, y):
            return False
    return True


def seg_clear(p0, p1, w, netname, layer, own=None, clr=0.18):
    """True if a track p0-p1 of width w on `layer` stays clr away from every other-net pad on that layer."""
    n = max(2, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 0.04))
    for (a, b, c, d), pn, ref, pad in PADS:
        if pad is own or pn == netname:
            continue
        on = pad.IsOnLayer(layer)
        if not on:
            continue
        for i in range(n + 1):
            x = p0[0] + (p1[0] - p0[0]) * i / n
            y = p0[1] + (p1[1] - p0[1]) * i / n
            dx = max(a - x, 0, x - c); dy = max(b - y, 0, y - d)
            if math.hypot(dx, dy) < w / 2 + clr:
                return False
    return True


def add_via(x, y, netname, d=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I_MM(OX + x, OY + y)); v.SetDrill(F(drill)); v.SetWidth(F(d))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net[netname])
    board.Add(v)
    VIAS.append((x, y, d / 2, netname))


def add_track(a, b, w, layer, netname):
    tr = pcbnew.PCB_TRACK(board)
    tr.SetStart(pcbnew.VECTOR2I_MM(OX + a[0], OY + a[1])); tr.SetEnd(pcbnew.VECTOR2I_MM(OX + b[0], OY + b[1]))
    tr.SetWidth(F(w)); tr.SetLayer(layer); tr.SetNet(net[netname])
    board.Add(tr)


def pad_of(ref, num):
    return [p for p in fps[ref].Pads() if p.GetNumber() == num][0]


def centre(p):
    c = p.GetPosition()
    return t(c.x) - OX, t(c.y) - OY


def layer_of(ref):
    return pcbnew.B_Cu if fps[ref].IsFlipped() else pcbnew.F_Cu


log = {}
# ---------------------------------------------------------------- 1. weapon gate escapes
for ph, x0 in CELLS.items():
    hs, ls = {"A": ("Q1", "Q2"), "B": ("Q3", "Q4"), "C": ("Q5", "Q6")}[ph]
    for ref, site, netn in ((hs, (x0 + 6.54, 6.42), f"W_GH{ph}"), (ls, (x0 + 5.95, 11.9), f"W_GL{ph}")):
        pc = centre(pad_of(ref, "4"))
        if any(math.hypot(site[0] - vx, site[1] - vy) < 0.1 for vx, vy, _r, _n in VIAS):
            continue
        VIAS[:] = [v for v in VIAS if math.hypot(site[0] - v[0], site[1] - v[1]) > 0.05]
        assert legal(site[0], site[1], 0.3, netn, lanes_ok=True, zones_ok=("W_A", "W_B", "W_C", "VBAT")), (ref, site)
        add_via(site[0], site[1], netn)
        add_track(pc, site, 0.3, pcbnew.F_Cu, netn)
        log.setdefault("gate escape vias", []).append(ref)


def via_near_pad(ref, num, netname, d=0.45, drill=0.25, outward_only=False, lanes_ok=False, zones_ok=(), stub_w=0.25):
    """nearest legal via next to a pad (outside it), with a stub from the pad centre; None if nothing fits."""
    p = pad_of(ref, num)
    (a, b, c, e) = box(p)
    cx, cy = centre(p)
    fx, fy = centre_fp = (t(fps[ref].GetPosition().x) - OX, t(fps[ref].GetPosition().y) - OY)
    r = d / 2
    w, h = (c - a) / 2, (e - b) / 2
    cands = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for extra in (0.0, 0.4, 0.8):
            reach = (w if dx else h) + r + 0.12 + extra
            for k in (0.0, 0.35, -0.35, 0.7, -0.7, 1.0, -1.0):
                px = cx + dx * reach + (k if dy else 0)
                py = cy + dy * reach + (k if dx else 0)
                outward = (px - cx) * (cx - fx) + (py - cy) * (cy - fy)
                cands.append((0 if outward > 0 else 1, extra + abs(k), dx, dy, px, py, outward))
    cands.sort()
    for rank, _k, dx, dy, px, py, outward in cands:
        if outward_only and outward <= 0:
            continue
        sw = min(stub_w, 2 * min(w, h))
        if legal(px, py, r, netname, lanes_ok=lanes_ok, zones_ok=zones_ok) and seg_clear((cx, cy), (px, py), sw, netname, layer_of(ref), own=p):
            add_via(px, py, netname, d, drill)
            add_track((cx, cy), (px, py), sw, layer_of(ref), netname)
            return px, py
    return None


def via_grid(ref, num, netname, d=0.6, drill=0.3, stub_w=0.3, radius=2.5):
    """fallback: nearest legal via within `radius` of the pad centre with a clean stub."""
    p = pad_of(ref, num)
    cx, cy = centre(p)
    cands = sorted(((i * 0.1, j * 0.1) for i in range(-25, 26) for j in range(-25, 26)), key=lambda q: math.hypot(*q))
    for dx, dy in cands:
        if math.hypot(dx, dy) > radius:
            break
        x, y = cx + dx, cy + dy
        if legal(x, y, d / 2, netname) and seg_clear((cx, cy), (x, y), stub_w, netname, layer_of(ref), own=p):
            add_via(x, y, netname, d, drill)
            add_track((cx, cy), (x, y), stub_w, layer_of(ref), netname)
            return x, y
    return None


# Q8's gate (its pin is at the far corner from U13's GATE pin; the trace leaves on another layer)
if via_near_pad("Q8", "4", "PSW_G", d=0.6, drill=0.3, stub_w=0.3) or via_grid("Q8", "4", "PSW_G"):
    log.setdefault("gate escape vias", []).append("Q8")

# ---------------------------------------------------------------- 2. pack-path pours (L1)


def zone(name, netname, pts, priority=1):
    if name in names:
        return
    z = pcbnew.ZONE(board)
    z.SetLayer(pcbnew.F_Cu); z.SetNet(net[netname]); z.SetZoneName(name); z.SetAssignedPriority(priority)
    z.SetLocalClearance(F(0.2)); z.SetMinThickness(F(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
    z.SetThermalReliefGap(F(0.5)); z.SetThermalReliefSpokeWidth(F(1.0))
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts:
        ol.Append(F(OX + x), F(OY + y))
    board.Add(z)
    OUTER_ZONES.append((pts, netname))
    log.setdefault("pack pours", []).append(name)


zone("pack: BAT_IN (JBAT1 + Q7 drain)", "BAT_IN", [(1.0, 6.4), (11.5, 6.4), (11.5, 11.6), (1.0, 11.6)])
zone("pack: PSW_S (Q7/Q8 sources)", "PSW_S", [(12.1, 7.85), (14.35, 7.85), (14.35, 6.6), (15.8, 6.6), (15.8, 10.2),
                                             (13.55, 10.2), (13.55, 11.4), (12.1, 11.4)])
zone("pack: VBAT_SW (Q8 drain + RS4 pad 1)", "VBAT_SW", [(16.55, 6.5), (24.2, 6.5), (24.2, 11.5), (16.55, 11.5)])
vstrip = [(27.7, 1.5), (31.6, 1.5), (31.6, 19.45), (26.1, 19.45), (26.1, 16.5), (27.7, 16.5)]
zone("pack: VBAT (RS4 pad 2, D1, C1)", "VBAT", vstrip)


def field(poly, netname, n_max, d=0.6, drill=0.3, pitch=0.2):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    n = 0
    y = min(ys) + 0.5
    while y < max(ys) - 0.3 and n < n_max:
        x = min(xs) + 0.5
        while x < max(xs) - 0.3 and n < n_max:
            if inside(poly, x, y) and legal(x, y, d / 2, netname, zones_ok=()):
                add_via(x, y, netname, d, drill); n += 1
            x += pitch
        y += pitch
    return n


log["VBAT vias RS4/C1 strip -> L3"] = field(vstrip, "VBAT", 18)
for ref, num in (("C1", "2"), ("D1", "2"), ("C14", "2")):
    (a, b, c, e) = box(pad_of(ref, num))
    zone(f"pack: GND at {ref}", "GND", [(a - 1.2, b - 1.2), (c + 1.2, b - 1.2), (c + 1.2, e + 1.2), (a - 1.2, e + 1.2)], priority=0)
# GND fields round C1's and D1's GND pads (return of the bulk cap and the TVS)
for ref, num, n_max in (("C1", "2", 8), ("D1", "2", 4), ("C14", "2", 2)):
    (a, b, c, e) = box(pad_of(ref, num))
    ring = [(a - 1.2, b - 1.2), (c + 1.2, b - 1.2), (c + 1.2, e + 1.2), (a - 1.2, e + 1.2)]
    log[f"GND vias at {ref}"] = field(ring, "GND", n_max, d=0.6, drill=0.3)

# ---------------------------------------------------------------- 3. a GND via at every SMD GND pad not on a GND pour
EP = {("U2", "49"), ("U3", "41"), ("U4", "41"), ("U8", "21")}
tied = 0
for ic, epn in EP:
    ep = pad_of(ic, epn)
    ea, eb, ec, ee = box(ep)
    for q in fps[ic].Pads():
        if q.GetNetname().split("/")[-1] != "GND" or q.GetNumber() == epn or not q.GetNumber():
            continue
        qx, qy = centre(q)
        tx, ty = min(max(qx, ea + 0.2), ec - 0.2), min(max(qy, eb + 0.2), ee - 0.2)   # nearest point just inside the EP
        if math.hypot(tx - qx, ty - qy) < 1.6 and (abs(tx - qx) < 0.01 or abs(ty - qy) < 0.01) \
                and seg_clear((qx, qy), (tx, ty), 0.25, "GND", layer_of(ic), own=q):   # straight in, clear of the neighbours
            add_track((qx, qy), (tx, ty), 0.25, layer_of(ic), "GND")
            tied += 1
            PADS[:] = [row for row in PADS if row[3] is not q]      # counted as done
log["IC GND pins tied into their exposed pad"] = tied
gnd_zones = [poly for poly, zn in OUTER_ZONES if zn == "GND"]
done = placed = failed = 0
fails = []
for (a, b, c, e), pn, ref, p in list(PADS):
    if pn != "GND" or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or (ref, p.GetNumber()) in EP or ref.startswith("NT"):
        continue
    cx, cy = centre(p)
    if any(inside(poly, cx, cy) for poly in gnd_zones):
        continue
    near = any(vn == "GND" and (a - 0.7 < vx < c + 0.7) and (b - 0.7 < vy < e + 0.7) for vx, vy, _r, vn in VIAS)
    if near:
        done += 1
        continue
    ic = ref[0] == "U" or ref.startswith("J")
    if via_near_pad(ref, p.GetNumber(), "GND", outward_only=ic):
        placed += 1
    else:
        failed += 1
        fails.append(f"{ref}.{p.GetNumber()}")
log["GND pad vias"] = f"placed {placed}, already had one {done}, no room {failed}: {' '.join(fails)}"

for k, v in log.items():
    print(f"{k}: {v}")
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(PCB), board)
PRO.write_text(pro_before)
