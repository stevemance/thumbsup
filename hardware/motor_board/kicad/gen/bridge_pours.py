"""Layout step 1: the weapon bridge's power pours (L1, per phase cell) + the L3 VBAT feed + GND/VBAT via fields.
Outlines only (the user adjusts them); no tracks.  Idempotent (skips zones by name, vias by position).
Run with /usr/bin/python3; close KiCad first."""
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
nets = board.GetNetsByName()
net = {str(k).split("/")[-1]: v for k, v in nets.items() if str(k)}
names = {z.GetZoneName() for z in board.Zones()}

CELLS = {"A": 60.5, "B": 48.0, "C": 35.5}      # cell origins (placement_spec.CELL)


def zone(name, netname, layer, pts, priority=1, clearance=0.2, tht_thermal=True):
    if name in names:
        return None
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net[netname])
    z.SetZoneName(name)
    z.SetAssignedPriority(priority)
    z.SetLocalClearance(F(clearance))
    z.SetMinThickness(F(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL if tht_thermal else pcbnew.ZONE_CONNECTION_FULL)
    z.SetThermalReliefGap(F(0.5))
    z.SetThermalReliefSpokeWidth(F(1.0))                 # wire holes: 4 x 1 mm spokes (DESIGN 6.9)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(F(OX + x), F(OY + y))
    board.Add(z)
    return pts


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


made = {}
for ph, x0 in CELLS.items():
    X = lambda d: x0 + d
    # 1. phase node: front strip + wire-hole pad + LS drain tab + HS source pins (stops before the HS drain tab)
    made[f"cell {ph}: phase W_{ph}"] = zone(f"cell {ph}: phase W_{ph}", f"W_{ph}", pcbnew.F_Cu, [
        (X(0.1), 0.45), (X(12.2), 0.45), (X(12.2), 7.6), (X(5.5), 7.6), (X(5.5), 10.8), (X(0.5), 10.8), (X(0.5), 7.6),
        (X(0.1), 7.6)])
    # 2. LS source pins -> shunt pad 1 (clear of the LS gate pin at the rear-right corner)
    made[f"cell {ph}: LS source to shunt W_SL{ph}"] = zone(f"cell {ph}: LS source to shunt W_SL{ph}", f"W_SL{ph}", pcbnew.F_Cu, [
        (X(0.55), 10.95), (X(4.25), 10.95), (X(4.25), 13.15), (X(2.75), 13.15), (X(2.75), 17.55), (X(-0.65), 17.55),
        (X(-0.65), 13.15), (X(0.55), 13.15)])
    # 3. HS drain tab + the local 10 uF's VBAT pad (VBAT; fed from L3 through the via field)
    xr = 10.0 if ph == "B" else 11.6              # cell B: stop short of TH1
    xg = 12.35                                     # into the gap before the next cell's LS tab (or the board edge side)
    made[f"cell {ph}: HS drain VBAT"] = zone(f"cell {ph}: HS drain VBAT", "VBAT", pcbnew.F_Cu, [
        (X(5.75), 7.75), (X(xg), 7.75), (X(xg), 13.1), (X(xr), 13.1), (X(xr), 15.3), (X(7.2), 15.3), (X(7.2), 13.1),
        (X(5.75), 13.1)])
    # 4. shunt GND pad + cap GND pad + Kelvin tie GND end (GND; via field to L2).  Cell B stops at y 17.6 so the
    #    strip in front of U2's pins stays free for the phase-C gate/sense traces.
    yb = 17.6 if ph == "B" else 18.75
    made[f"cell {ph}: shunt/cap GND"] = zone(f"cell {ph}: shunt/cap GND", "GND", pcbnew.F_Cu, [
        (X(3.7), 13.2), (X(7.05), 13.2), (X(7.05), 15.45), (X(11.6), 15.45), (X(11.6), yb), (X(3.7), yb)])

# 5. L3 VBAT feed: from RS4 / D1 / C1's VBAT pad under all three cells (the high sides are fed from below)
made["L3 VBAT feed"] = zone("L3 VBAT feed", "VBAT", pcbnew.In2_Cu, [
    (21.0, 1.5), (34.6, 1.5), (34.6, 5.3), (72.8, 5.3), (72.8, 18.5), (34.6, 18.5), (34.6, 20.8), (21.0, 20.8)], priority=1)

# ---------------------------------------------------------------- via fields (GND -> L2, VBAT -> L3), only on free copper
pads = []
for f in board.GetFootprints():
    for p in f.Pads():
        r = p.GetBoundingBox()
        pads.append((t(r.GetLeft()) - OX, t(r.GetTop()) - OY, t(r.GetRight()) - OX, t(r.GetBottom()) - OY,
                     p.GetNetname().split("/")[-1]))
vias = [(t(v.GetPosition().x) - OX, t(v.GetPosition().y) - OY) for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
# reserved: the weapon gate escape vias (placed by vias_and_pack.py); the via fields keep clear of them
for x0 in CELLS.values():
    vias += [(x0 + 6.54, 6.42), (x0 + 5.95, 11.9)]
keep = []
for z in board.Zones():
    if z.GetIsRuleArea() and z.GetDoNotAllowVias():
        b_ = z.GetBoundingBox()
        keep.append((t(b_.GetLeft()) - OX, t(b_.GetTop()) - OY, t(b_.GetRight()) - OX, t(b_.GetBottom()) - OY))


def inside(poly, x, y):
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def edge_dist(poly, x, y):
    d = 1e9
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        dx, dy = x2 - x1, y2 - y1
        u = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        d = min(d, math.hypot(x - x1 - u * dx, y - y1 - u * dy))
    return d


def add_vias(poly, netname, pitch=0.2, r=0.3, pad_gap=0.25, limit=40):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    n = 0
    y = min(ys) + 0.5
    while y < max(ys) - 0.3:
        x = min(xs) + 0.5
        while x < max(xs) - 0.3:
            ok = inside(poly, x, y) and edge_dist(poly, x, y) >= r + 0.05 - 1e-6
            # never in a pad; next to a same-net pad is the point; 0.25 mm from any other net's pad
            ok = ok and all(not (a - r - g < x < c + r + g and b - r - g < y < d + r + g)
                            for a, b, c, d, pn in pads for g in [(0.05 if pn in (netname, "") else pad_gap)])
            ok = ok and all(math.hypot(x - vx, y - vy) >= 2 * r + 0.2 - 1e-6 for vx, vy in vias)
            ok = ok and all(not (a < x < c and b < y < d) for a, b, c, d in keep)
            if ok and n < limit:
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I_MM(OX + x, OY + y)); v.SetDrill(F(0.3)); v.SetWidth(F(0.6))
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net[netname])
                board.Add(v)
                vias.append((x, y))
                n += 1
            x += pitch
        y += pitch
    return n


count = {}
POLYS = dict(made)
for name, poly in POLYS.items():
    if poly is None:
        poly = next(([(t(z.Outline().CVertex(i).x) - OX, t(z.Outline().CVertex(i).y) - OY) for i in range(z.Outline().FullPointCount())]
                     for z in board.Zones() if z.GetZoneName() == name), None)
        if poly is None:
            continue
    if name.endswith("GND"):
        count[name] = add_vias(poly, "GND")
    elif name.endswith("HS drain VBAT"):
        count[name] = add_vias(poly, "VBAT")
rs2 = [p for f in board.GetFootprints() if f.GetReference() == "RS2" for p in f.Pads() if p.GetNumber() == "2"][0]
b2 = rs2.GetBoundingBox()
n_ip = 0
for vx in (t(b2.GetRight()) - OX - 1.15, t(b2.GetRight()) - OX - 0.45):
    for vy in (13.9, 14.8, 15.7, 16.6):
        if all(math.hypot(vx - a, vy - c) > 0.5 for a, c in vias):
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I_MM(OX + vx, OY + vy)); v.SetDrill(F(0.3)); v.SetWidth(F(0.6))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net["GND"])
            board.Add(v); vias.append((vx, vy)); n_ip += 1
count["cell B: RS2 GND pad (via-in-pad)"] = n_ip
print("zones added:", [k for k, v in made.items() if v], "\nvias:", count)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(PCB), board)
PRO.write_text(pro_before)
