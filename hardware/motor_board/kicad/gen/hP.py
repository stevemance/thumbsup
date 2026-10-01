"""hP: copper pours, power via fields, exposed-pad thermal vias and GND stitching (final layout phase), on hD.

Zones (board-local mm; the op "py" below builds them, tail.py fills them):
- L2 (In1.Cu): one solid GND plane over the whole board (no tracks on L2, DRC rule).
- L1 (F.Cu): one pour per power net in its own region (DESIGN 6.1-6.9): BAT_IN (JBAT1 -> Q7 tab), PSW_S (Q7 / Q8
  sources), VBAT_SW (Q8 tab -> RS4.1), VBAT (RS4.2 -> D1 / TP10 / C1.1, and each weapon cell's high-side tab + its 10 uF
  cap), W_x (JWx hole <- low-side tab + high-side sources), W_SLx (low-side sources -> shunt pad 1), L_x / R_x (drive
  outputs -> JL / JR holes), L_VM / R_VM (R302 / R402 -> the VM caps and pins).  Solid pad connections for SMD pads,
  1.5 mm thermal spokes for the battery / weapon wire holes (JBAT1 4 spokes; JW1-3 3 spokes, the front-edge side has no
  copper; JBAT2 on every GND layer), DESIGN 6.9.  The drive holes JL / JR are solid-connected: L_x / R_x copper is a
  small L1-only pour (nothing to sink the iron's heat) and JL1-3 at 3.6 mm pitch beside the board edge leave no room for
  4 spokes.  GND fill (lowest priority) everywhere else.  The INA239 Kelvin taps (RS4 inner edges -> R2.1 /
  R3.1 / U7.8) and the shunt Kelvin pairs (SPx from the shunt pad-1 inner edge, SNx from the net ties NT1-NT3) are
  outside every same-net polygon (plus fill keep-outs where the taps leave RS4), so they stay the only connection.
- L3 (In2.Cu): the VBAT band (y < 16.0, x 4-84.7) fed from L1 by via fields (RS4 / C1 and each high-side cell),
  an L_VM patch (R302.2's corridor -> the existing L3 VM strip), GND fill in every other free area.
- L4 (B.Cu): GND fill (solid under the L3 VBAT band but for the gate lanes).
Vias: VBAT / L_VM fields (0.6 / 0.3 power vias, rows at >= 1.3 mm pitch), R402.1 VBAT vias in pad (as R302.1),
U2 / U3 / U4 exposed-pad thermal arrays and U6 / U8 EP vias (all via in pad: POFV, filled + capped), and GND stitching
placed by `stitch()`: every GND pad gets a GND via within ~1 mm on its own fill (or a short stub / via in pad), every
GND fill piece is stitched, a ~3 mm grid over the fills and a fence along the power pours.  Every via is checked against
all other-net copper on all layers (0.2 mm), holes (0.3 mm), the board edge (0.3 mm) and, for non-GND vias, the 0.9 mm
pitch; illegal candidates are skipped and counted."""
import json
import math
from pathlib import Path

import v2_pre
from v2_pre import EDITS

v2_pre.VIA_PITCH = 0.9
n_ = v2_pre.n_
HERE = Path(__file__).resolve().parent
W, H = 85.0, 35.0

# ------------------------------------------------------------------------------------------------ zones
# (name, net, layer, priority, polygon, opts)
ZONES = []


def Z(name, net, layer, prio, poly, **o):
    ZONES.append((name, net, layer, prio, poly, o))


FULLB = [(0, 0), (W, 0), (W, H), (0, H)]
Z("L2 GND plane", "GND", "In1.Cu", 0, FULLB, spoke=1.5)
Z("L1 GND fill", "GND", "F.Cu", 1, FULLB, spoke=1.5)
Z("L3 GND fill", "GND", "In2.Cu", 1, FULLB, spoke=1.5)
Z("L4 GND fill", "GND", "B.Cu", 1, FULLB, spoke=1.5)

# --- power entry
Z("L1 BAT_IN", "BAT_IN", "F.Cu", 30, [(5.6, 0.3), (17.25, 0.3), (17.25, 6.35), (13.9, 6.35), (13.9, 8.75),
                                      (11.0, 8.75), (11.0, 6.35), (5.6, 6.35)], spoke=1.5)   # lobe west of C18 -> R13.1
Z("L1 PSW_S", "PSW_S", "F.Cu", 31, [(17.95, 1.15), (21.85, 1.15), (21.85, 6.2), (17.95, 6.2)])
Z("L1 VBAT_SW", "VBAT_SW", "F.Cu", 32, [(22.3, 0.3), (30.95, 0.3), (30.95, 5.35), (30.15, 5.35), (30.15, 6.3),
                                        (22.3, 6.3)])
# VBAT: RS4.2 -> south of D1 (D1.2 GND carved out) -> C1.1, D1.1, TP10; west edge clear of the U7 Kelvin tap
Z("L1 VBAT entry", "VBAT", "F.Cu", 33, [(34.7, 0.3), (37.25, 0.3), (37.25, 4.8), (40.45, 4.8), (40.45, 0.3),
                                        (46.85, 0.3), (46.85, 5.3), (45.7, 5.3), (45.7, 10.6), (44.45, 10.6),
                                        (44.45, 13.6), (39.55, 13.6), (39.55, 10.5), (35.7, 10.5), (35.7, 5.5),
                                        (35.25, 5.5), (35.25, 4.5), (34.7, 4.5)])   # clear of the tap at RS4.2's corner
# --- weapon cells (C x 46-57, B x 58-70, A x 70.5-84.7)
Z("L1 W_C", "W_C", "F.Cu", 40, [(47.15, 0.3), (57.75, 0.3), (57.75, 7.35), (51.25, 7.35), (51.25, 10.45),
                                (45.95, 10.45), (45.95, 5.45), (47.15, 5.45)], spoke=1.5)
Z("L1 VBAT C", "VBAT", "F.Cu", 41, [(51.5, 7.8), (57.45, 7.8), (57.45, 12.75), (56.3, 12.75), (56.3, 14.85),
                                    (52.6, 14.85), (52.6, 12.75), (51.5, 12.75)])
Z("L1 W_SLC", "W_SLC", "F.Cu", 42, [(44.75, 11.1), (49.8, 11.1), (49.8, 12.6), (48.05, 12.6), (48.05, 16.9),
                                    (44.75, 16.9)])
Z("L1 W_B", "W_B", "F.Cu", 43, [(58.2, 0.3), (70.45, 0.3), (70.45, 7.4), (64.95, 7.4), (64.95, 10.45), (59.1, 10.45),
                                (59.1, 5.4), (58.2, 5.4)], spoke=1.5)
Z("L1 VBAT B", "VBAT", "F.Cu", 44, [(65.25, 7.8), (71.1, 7.8), (71.1, 12.2), (70.3, 12.8), (69.4, 12.8), (69.4, 14.85),
                                    (65.9, 14.85), (65.9, 12.8), (65.25, 12.8)])
Z("L1 W_SLB", "W_SLB", "F.Cu", 45, [(59.15, 11.1), (62.85, 11.1), (62.85, 12.6), (61.15, 12.6), (61.15, 16.5),
                                    (57.9, 16.5), (57.9, 13.3), (59.15, 12.4)])
Z("L1 W_A", "W_A", "F.Cu", 46, [(70.75, 0.3), (84.7, 0.3), (84.7, 7.4), (77.55, 7.4), (77.55, 10.45), (71.55, 10.45),
                                (71.55, 7.4), (70.75, 7.4)], spoke=1.5)
Z("L1 VBAT A", "VBAT", "F.Cu", 47, [(77.85, 7.75), (84.7, 7.75), (84.7, 13.25), (81.7, 13.25), (81.7, 14.85),
                                    (78.4, 14.85), (78.4, 12.8), (77.85, 12.8)])
Z("L1 W_SLA", "W_SLA", "F.Cu", 48, [(71.6, 11.1), (75.35, 11.1), (75.35, 12.6), (73.65, 12.6), (73.65, 17.0),
                                    (70.5, 17.0), (70.5, 13.2), (71.6, 12.6)])
# --- left drive (U3 west pins -> JL1-3) and its VM
Z("L1 L_A", "L_A", "F.Cu", 50, [(0.8, 19.15), (5.7, 19.15), (5.7, 22.3), (6.5, 22.3), (6.5, 23.3), (4.1, 23.3),
                                (4.1, 22.6), (0.8, 22.6)], conn="full")
Z("L1 L_B", "L_B", "F.Cu", 51, [(0.8, 22.85), (3.85, 22.85), (3.85, 23.6), (5.4, 23.6), (5.6, 23.75), (6.5, 23.75), (6.5, 24.8),
                                (5.6, 24.8), (5.4, 25.05), (4.1, 25.05), (4.1, 25.4), (0.8, 25.4)], conn="full")
Z("L1 L_C", "L_C", "F.Cu", 52, [(0.8, 25.65), (4.1, 25.65), (4.1, 25.3), (6.5, 25.3), (6.5, 26.35), (6.2, 26.45), (5.0, 27.65),
                                (5.0, 29.0), (0.8, 29.0)], conn="full")
Z("L1 L_VM R302", "L_VM", "F.Cu", 53, [(5.3, 12.0), (7.45, 12.0), (7.45, 16.3), (7.0, 16.75), (7.0, 18.25),
                                       (5.6, 18.25), (5.3, 18.6), (2.2, 18.6), (2.2, 15.65), (5.3, 15.65)])
Z("L1 L_VM caps", "L_VM", "F.Cu", 54, [(5.9, 19.75), (13.75, 19.75), (13.75, 21.1), (8.5, 21.1), (8.5, 22.25),
                                       (7.0, 22.25), (7.0, 21.1), (5.9, 21.1)])
Z("L3 L_VM", "L_VM", "In2.Cu", 30, [(4.95, 16.3), (8.5, 16.3), (8.5, 19.55), (14.0, 19.55), (14.0, 21.0),
                                    (4.95, 21.0)])
# --- right drive (U4 south pins -> JR1-3) and its VM
# (north-west corner off the pins -> JR1 diagonal left to the GND fill: it joins C401.2 to U4.12 / the EP island, final review)
Z("L1 R_A", "R_A", "F.Cu", 55, [(20.45, 27.3), (21.55, 27.3), (21.55, 27.9), (20.6, 29.3), (20.25, 30.0), (20.25, 32.45),
                                (17.15, 32.45), (17.15, 30.0), (18.4, 29.0), (20.1, 28.2), (20.45, 27.75)], conn="full")
Z("L1 R_B", "R_B", "F.Cu", 56, [(22.0, 27.3), (23.0, 27.3), (23.0, 27.45), (23.35, 27.45), (23.35, 28.2), (23.95, 29.6),
                                (24.0, 32.45), (21.0, 32.45), (21.0, 30.0), (21.65, 28.5), (21.65, 27.45), (22.0, 27.45)], conn="full")
Z("L1 R_C", "R_C", "F.Cu", 57, [(23.5, 27.3), (24.5, 27.3), (25.2, 28.0), (26.6, 29.3), (27.8, 29.6), (27.8, 32.45),
                                (24.4, 32.45), (24.4, 29.7), (23.5, 28.0)], conn="full")
Z("L1 R_VM R402", "R_VM", "F.Cu", 58, [(17.7, 12.0), (19.4, 12.0), (19.4, 17.1), (19.2, 17.1), (19.2, 22.3), (16.4, 22.3),
                                       (16.4, 18.75), (14.3, 18.75), (14.3, 15.85), (17.7, 15.85)])
Z("L1 R_VM caps", "R_VM", "F.Cu", 59, [(17.45, 24.35), (19.6, 24.35), (19.6, 24.45), (20.45, 24.45), (20.45, 25.95),
                                       (19.6, 25.95), (19.6, 27.0), (17.45, 27.0), (17.45, 26.4), (16.25, 26.4),
                                       (16.25, 25.2), (17.45, 25.2)])
# --- L3 VBAT band (DESIGN 6.2: y < 16.0)
Z("L3 VBAT band", "VBAT", "In2.Cu", 40, [(4.0, 0.3), (84.7, 0.3), (84.7, 16.0), (4.0, 16.0)])

# fill keep-outs (all nets, F.Cu): where the INA239 Kelvin taps leave RS4's inner edges
KEEPOUT = [("K RS4 taps", "F.Cu", [(30.1, 5.5), (35.65, 5.5), (35.65, 6.45), (30.1, 6.45)])]

# ------------------------------------------------------------------------------------------------ fixed vias
PWR_VIA = (0.6, 0.3)
GND_VIA = (0.45, 0.25)
POFV = (0.4, 0.2)
EPV = (0.45, 0.25)
FIXED = []          # (net, (x, y), (d, drill), tag)


def grid(x0, x1, nx, y0, y1, ny):
    return [(round(x0 + (x1 - x0) * i / max(nx - 1, 1), 3), round(y0 + (y1 - y0) * j / max(ny - 1, 1), 3))
            for i in range(nx) for j in range(ny)]


# VBAT: RS4 -> C1 field (L1 -> L3 band), 1.3 mm pitch
for c in grid(36.6, 44.4, 7, 5.9, 9.8, 4):
    FIXED.append(("VBAT", c, PWR_VIA, "vbat field RS4/C1"))
# each high-side cell: the strip between the tab and the 10 uF cap's VBAT pad, and beside it
for c in [(52.9, 13.05), (54.2, 13.05), (55.5, 13.05), (57.35, 12.2), (57.35, 10.9), (57.35, 9.6),
          (66.2, 13.05), (67.5, 13.05), (68.8, 13.05), (70.55, 11.6), (70.55, 10.3), (70.55, 9.0),
          (78.9, 13.05), (80.2, 13.05), (81.5, 13.05), (83.6, 8.4), (83.6, 9.7), (83.6, 11.0), (83.6, 12.3),
          (82.9, 14.2), (83.9, 13.5)]:
    FIXED.append(("VBAT", c, PWR_VIA, "vbat field cell"))
# R402.1 (VBAT, fed from the L3 band) as R302.1: three vias in pad
for y in (12.9, 13.9, 14.9):
    FIXED.append(("VBAT", (24.46, y), POFV, "pofv R402.1"))
# L_VM: R302.2's corridor -> L3 patch -> the existing L3 VM strip
for c in [(5.8, 16.6), (6.65, 17.25), (5.8, 17.9)]:
    FIXED.append(("L_VM", c, (0.45, 0.25), "lvm field"))
# GND return fields (L1 -> L2) at each cell's shunt pad 2 / 10 uF cap pad 2 (the weapon commutation loop's return) and
# at the bulk cap C1 / TVS D1 (legal ones only)
for dx in (0.0, 13.1, 25.6):          # cell C, B, A (shunt / cap pitch 13.1 / 12.5)
    for c in [(52.75, 15.3), (52.75, 16.25), (53.55, 15.45), (54.4, 15.45), (55.25, 15.45), (56.1, 15.6), (56.1, 16.55)]:
        FIXED.append(("GND", (round(c[0] + dx, 2), c[1]), GND_VIA, "gnd field cell"))
for c in [(32.0, 14.0), (33.2, 14.0), (34.4, 14.0), (35.5, 14.0), (32.2, 9.8), (33.4, 9.8), (34.6, 9.8), (38.2, 1.2),
          (39.4, 1.2)]:
    FIXED.append(("GND", c, GND_VIA, "gnd field C1/D1"))
# exposed pads (DESIGN 6.5): thermal via arrays, via in pad (POFV); the lattice phase with the most legal vias wins
EP = {"U2": ((60.93, 21.42, 66.07, 26.58), 1.0), "U3": ((6.65, 22.45, 12.35, 26.15), 1.0),
      "U4": ((20.65, 20.65, 24.35, 26.35), 1.0), "U6": ((61.0, 29.75, 62.5, 30.75), 0.75),
      "U8": ((70.1, 21.5, 72.1, 23.5), 0.75)}

LOG = {}


# ------------------------------------------------------------------------------------------------ board op
def apply(b, ctx):
    import pcbnew
    F, T = pcbnew.FromMM, pcbnew.ToMM
    OX, OY = ctx["OX"], ctx["OY"]
    LAYER = {"F.Cu": pcbnew.F_Cu, "In1.Cu": pcbnew.In1_Cu, "In2.Cu": pcbnew.In2_Cu, "B.Cu": pcbnew.B_Cu}
    CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]

    def V(x, y):
        return pcbnew.VECTOR2I(F(x + OX), F(y + OY))

    def L(p):
        return (T(p.x) - OX, T(p.y) - OY)

    def fullnet(n):
        return "GND" if n == "GND" else n_(n)

    netobj = {str(k): v for k, v in b.GetNetsByName().items()}
    gnd = netobj["GND"].GetNetCode()
    for name, net, layer, prio, poly, o in ZONES:
        z = pcbnew.ZONE(b)
        z.SetLayer(LAYER[layer]); z.SetNetCode(netobj[fullnet(net)].GetNetCode()); z.SetZoneName(name)
        z.SetAssignedPriority(prio); z.SetLocalClearance(F(o.get("clr", 0.2)))
        z.SetMinThickness(F(o.get("min_w", 0.25 if net == "GND" else 0.3)))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if o.get("conn") == "full" else pcbnew.ZONE_CONNECTION_THT_THERMAL)
        z.SetThermalReliefGap(F(o.get("gap", 0.5))); z.SetThermalReliefSpokeWidth(F(o.get("spoke", 1.0)))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        ol = z.Outline(); ol.NewOutline()
        for x, y in poly:
            ol.Append(F(x + OX), F(y + OY))
        b.Add(z)
    for name, layer, poly in KEEPOUT:
        z = pcbnew.ZONE(b)
        z.SetIsRuleArea(True); z.SetLayer(LAYER[layer]); z.SetZoneName(name)
        z.SetDoNotAllowZoneFills(True); z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        ol = z.Outline(); ol.NewOutline()
        for x, y in poly:
            ol.Append(F(x + OX), F(y + OY))
        b.Add(z)
    # outlines of the power polygons a GND stitching via must not punch (L1 pours, L3 L_VM; the L3 VBAT band is
    # allowed where the via stitches L1 GND, e.g. at the shunt / cap GND pads)
    PWR_OL = [(LAYER[layer], poly) for name, net, layer, prio, poly, o in ZONES if net != "GND" and layer == "F.Cu"]

    def pip(poly, x, y):
        c = False
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                c = not c
        return c

    def in_power(x, y, m, layers=(pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)):
        pts = [(x, y)] + [(x + m * math.cos(a), y + m * math.sin(a)) for a in [k * math.pi / 4 for k in range(8)]]
        return any(l in layers and any(pip(poly, *q) for q in pts) for l, poly in PWR_OL)

    # ---- spatial index of copper for via legality (board-local mm)
    BK = 2.0
    idx = {}

    def put(item, box):
        for i in range(int(box[0] // BK), int(box[2] // BK) + 1):
            for j in range(int(box[1] // BK), int(box[3] // BK) + 1):
                idx.setdefault((i, j), []).append(item)

    pads = []
    for f in b.GetFootprints():
        for p in f.Pads():
            r = p.GetBoundingBox()
            box = (T(r.GetLeft()) - OX, T(r.GetTop()) - OY, T(r.GetRight()) - OX, T(r.GetBottom()) - OY)
            tht = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            lays = CU if tht else [l for l in CU if p.IsOnLayer(l)]
            it = dict(k="pad", net=p.GetNetCode(), lays=lays, shp={l: p.GetEffectiveShape(l) for l in lays}, box=box,
                      c=L(p.GetPosition()), drill=T(p.GetDrillSize().x) if tht else 0, ref=f.GetReference(),
                      num=p.GetNumber(), smd=not tht)
            pads.append(it)
            put(it, box)
    for x in b.GetTracks():
        if x.GetClass() == "PCB_VIA":
            it = dict(k="via", net=x.GetNetCode(), c=L(x.GetPosition()), d=T(x.GetWidth(pcbnew.F_Cu)),
                      drill=T(x.GetDrillValue()))
            put(it, (it["c"][0] - 0.5, it["c"][1] - 0.5, it["c"][0] + 0.5, it["c"][1] + 0.5))
        elif x.GetClass() == "PCB_TRACK":
            a, c = L(x.GetStart()), L(x.GetEnd())
            w = T(x.GetWidth())
            it = dict(k="trk", net=x.GetNetCode(), lay=x.GetLayer(), shp=x.GetEffectiveShape(x.GetLayer()), a=a, b=c, w=w)
            put(it, (min(a[0], c[0]) - w, min(a[1], c[1]) - w, max(a[0], c[0]) + w, max(a[1], c[1]) + w))
    CLR0, HOLE = 0.2, 0.3
    CLR = CLR0

    def near(x, y, rad=1.6):
        seen = set()
        for i in range(int((x - rad) // BK), int((x + rad) // BK) + 1):
            for j in range(int((y - rad) // BK), int((y + rad) // BK) + 1):
                for it in idx.get((i, j), ()):
                    if id(it) not in seen:
                        seen.add(id(it))
                        yield it

    def pad_dist(p, c):
        bx = p["box"]
        dx = max(bx[0] - c[0], 0, c[0] - bx[2]); dy = max(bx[1] - c[1], 0, c[1] - bx[3])
        return math.hypot(dx, dy)

    WHY = []

    def legal(x, y, d, drill, net, in_pad_ok=False, gnd_gap=0.7, tht_keep=1.0, clr=None):
        r = d / 2
        CLR = clr if clr is not None else CLR0

        def no(what):
            if WHY:
                WHY.append(what)
            return False
        if not (0.3 + r <= x <= W - 0.3 - r and 0.3 + r <= y <= H - 0.3 - r):
            return no("edge")
        circ = pcbnew.SHAPE_CIRCLE(V(x, y), F(r))
        for it in near(x, y):
            if it["k"] == "via":
                dd = math.dist(it["c"], (x, y))
                if dd - it["drill"] / 2 - drill / 2 < HOLE:
                    return no(f"hole via {it['c']}")
                if it["net"] != net and dd < r + it["d"] / 2 + CLR:
                    return no(f"via {it['c']}")
                if it["net"] == net and dd < (gnd_gap if net == gnd else 0.9):
                    return no(f"same-net via {it['c']}")
                if net != gnd and it["net"] != gnd and dd < 0.9:
                    return no(f"pitch via {it['c']}")
            elif it["k"] == "pad":
                if it["drill"]:
                    if math.dist(it["c"], (x, y)) - it["drill"] / 2 - drill / 2 < HOLE:
                        return no(f"hole {it['ref']}.{it['num']}")
                    if it["net"] != net and it["drill"] >= 1.1 and pad_dist(it, (x, y)) < tht_keep + r:
                        return no(f"wire hole {it['ref']}.{it['num']}")      # keep wire-hole spokes / pours free
                if it["net"] != net or it["net"] == 0:
                    for s in it["shp"].values():
                        if s.Collide(circ, F(CLR)):
                            return no(f"pad {it['ref']}.{it['num']}")
                elif not in_pad_ok and it["smd"]:
                    for s in it["shp"].values():
                        if s.Collide(circ, 0):
                            return no(f"own pad {it['ref']}.{it['num']}")
            else:
                if it["net"] != net and it["shp"].Collide(circ, F(CLR)):
                    return no(f"track {it['lay']} {it['a']}-{it['b']}")
        return True

    def probe(pts):
        from collections import Counter
        for q in pts:
            if len(q) == 2:
                WHY[:] = ["?"]
                ok = legal(q[0], q[1], 0.4, 0.2, gnd, in_pad_ok=True, clr=0.15)
                print("probe", q, ok, WHY[1:])
            else:                 # x, y, radius: reasons over a 0.1 grid
                cnt, oks = Counter(), []
                x = q[0] - q[2]
                while x <= q[0] + q[2]:
                    y = q[1] - q[2]
                    while y <= q[1] + q[2]:
                        WHY[:] = ["?"]
                        if legal(x, y, 0.4, 0.2, gnd, in_pad_ok=True, clr=0.15, gnd_gap=0.0):
                            oks.append((round(x, 2), round(y, 2)))
                        else:
                            cnt[WHY[1] if len(WHY) > 1 else "?"] += 1
                        y += 0.1
                    x += 0.1
                print("probe", q, "legal:", oks[:60], "| blockers:", cnt.most_common(8))
        WHY[:] = []
    if __import__("os").environ.get("HP_SEG"):          # x0,y0,x1,y1,layer(F|B): what blocks a 0.2 mm GND stub
        x0, y0, x1, y1, ly = __import__("os").environ["HP_SEG"].split(",")
        l = pcbnew.F_Cu if ly == "F" else pcbnew.B_Cu
        a, q = (float(x0), float(y0)), (float(x1), float(y1))
        seg = pcbnew.SHAPE_SEGMENT(V(*a), V(*q), F(0.2))
        for it in near((a[0] + q[0]) / 2, (a[1] + q[1]) / 2, rad=math.dist(a, q) / 2 + 1.5):
            if it["net"] == gnd:
                continue
            hit = (it["k"] == "pad" and l in it["shp"] and it["shp"][l].Collide(seg, F(0.15))) or \
                (it["k"] == "trk" and it["lay"] == l and it["shp"].Collide(seg, F(0.15))) or \
                (it["k"] == "via" and seg.Collide(pcbnew.SHAPE_CIRCLE(V(*it["c"]), F(it["d"] / 2)), F(0.15)))
            if hit:
                print("probe seg blocked by", it["k"], it.get("ref", ""), it.get("num", ""), it.get("c", ""), it.get("a", ""), it.get("b", ""))
        print("probe seg done")
        return
    if __import__("os").environ.get("HP_PROBE"):
        probe([tuple(map(float, t.split(","))) for t in __import__("os").environ["HP_PROBE"].split(";")])
        return

    added = []

    def add_via(net, c, dv, tag):
        x = pcbnew.PCB_VIA(b)
        x.SetPosition(V(*c)); x.SetWidth(F(dv[0])); x.SetDrill(F(dv[1]))
        x.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); x.SetNetCode(net)
        b.Add(x)
        it = dict(k="via", net=net, c=tuple(c), d=dv[0], drill=dv[1])
        put(it, (c[0] - 0.5, c[1] - 0.5, c[0] + 0.5, c[1] + 0.5))
        inpad = [f'{p["ref"]}.{p["num"]}' for p in near(*c, rad=0.1) if p["k"] == "pad" and p["smd"] and p["net"] == net
                 and any(s.Collide(pcbnew.SHAPE_CIRCLE(V(*c), F(dv[0] / 2)), 0) for s in p["shp"].values())]
        added.append(dict(net=x.GetNetname(), c=[round(c[0], 3), round(c[1], 3)], d=dv[0], drill=dv[1], tag=tag,
                          pad=inpad[0] if inpad else ""))
        return x

    def add_track(net, a, c, w, layer):
        x = pcbnew.PCB_TRACK(b)
        x.SetStart(V(*a)); x.SetEnd(V(*c)); x.SetWidth(F(w)); x.SetLayer(layer); x.SetNetCode(net)
        b.Add(x)
        it = dict(k="trk", net=net, lay=layer, shp=x.GetEffectiveShape(layer), a=a, b=c, w=w)
        put(it, (min(a[0], c[0]) - w, min(a[1], c[1]) - w, max(a[0], c[0]) + w, max(a[1], c[1]) + w))

    stats = {"rejected": []}
    for net, c, dv, tag in FIXED:
        nc = netobj[fullnet(net)].GetNetCode()
        if legal(c[0], c[1], dv[0], dv[1], nc, in_pad_ok=True, gnd_gap=0.6):
            add_via(nc, c, dv, tag)
        else:
            stats["rejected"].append((net, c, tag))
    for u, (bx, pitch) in EP.items():
        m = EPV[0] / 2 + 0.12
        best = []
        for fx in (0, 0.25, 0.5, 0.75):
            for fy in (0, 0.25, 0.5, 0.75):
                pts, x = [], bx[0] + m + fx * pitch
                while x <= bx[2] - m + 1e-9:
                    y = bx[1] + m + fy * pitch
                    while y <= bx[3] - m + 1e-9:
                        if legal(x, y, EPV[0], EPV[1], gnd, in_pad_ok=True, gnd_gap=0.6):
                            pts.append((round(x, 3), round(y, 3)))
                        y += pitch
                    x += pitch
                if len(pts) > len(best):
                    best = pts
        for c in best:
            add_via(gnd, c, EPV, f"ep {u}")

    # ---- GND stitching on the filled board
    filler = pcbnew.ZONE_FILLER(b)
    gz = {l: [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetCode() == gnd and z.GetLayer() == l][0]
          for l in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)}

    def fill():
        filler.Fill(b.Zones())

    def inside(ps, x, y, m, i=-1):
        if not ps.Contains(V(x, y), i):
            return False
        return all(ps.Contains(V(x + m * math.cos(a), y + m * math.sin(a)), i) for a in [k * math.pi / 4 for k in range(8)])

    def gnd_at(l, x, y, m=0.0):
        return inside(gz[l].GetFilledPolysList(l), x, y, m)

    def gvias_near(x, y, rad):
        return [it for it in near(x, y, rad) if it["net"] == gnd and (it["k"] == "via" or (it["k"] == "pad" and it["drill"]))
                and math.dist(it["c"], (x, y)) <= rad]

    gpads = [p for p in pads if p["net"] == gnd and p["smd"] and (p["ref"], p["num"]) not in DROP + HAND]
    rep = {}

    def bump(k):
        rep[k] = rep.get(k, 0) + 1

    def ring(cx, cy, r0, r1, step=0.15):
        out, r = [], r0
        while r <= r1 + 1e-9:
            n = max(8, int(2 * math.pi * r / step))
            out += [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
            r += step
        return out

    def pad_ok(p, l, rad):
        ps = gz[l].GetFilledPolysList(l)
        cs = [v for v in gvias_near(p["c"][0], p["c"][1], rad + 3.0) if pad_dist(p, v["c"]) <= rad]
        if not cs:
            return False
        pieces = [i for i in range(ps.OutlineCount()) if ps.Contains(V(*p["c"]), i)]
        for v in cs:
            if pad_dist(p, v["c"]) <= 0.05:        # via in pad
                return True
            if any(ps.Contains(V(*v["c"]), i) for i in pieces):
                return True
        for it in near(*p["c"], rad=1.6):         # stub: a GND track from the pad to one of the vias
            if it["k"] == "trk" and it["net"] == gnd and it["lay"] == l:
                ends = [it["a"], it["b"]]
                if any(pad_dist(p, e) <= 0.01 for e in ends) and any(math.dist(e, v["c"]) < 0.05 for e in ends for v in cs):
                    return True
        return False

    other_outer = {pcbnew.F_Cu: (pcbnew.B_Cu, pcbnew.In2_Cu), pcbnew.B_Cu: (pcbnew.F_Cu, pcbnew.In2_Cu)}

    def vip_spot(p, l):
        """a POFV spot inside the pad (whole via on the pad), legal on every layer, nearest the pad centre"""
        bx = p["box"]
        cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        s = p["shp"][l]
        r = POFV[0] / 2
        cands = []
        x = bx[0] + r
        while x <= bx[2] - r + 1e-9:
            y = bx[1] + r
            while y <= bx[3] - r + 1e-9:
                if all(s.Collide(pcbnew.SHAPE_CIRCLE(V(x + r * math.cos(a), y + r * math.sin(a)), 1), 0)
                       for a in [k * math.pi / 4 for k in range(8)]):
                    cands.append((x, y))
                y += 0.05
            x += 0.05
        for q in sorted(cands, key=lambda q: math.dist(q, (cx, cy))):
            if not in_power(q[0], q[1], 0.4, other_outer[l]) and \
                    legal(q[0], q[1], POFV[0], POFV[1], gnd, in_pad_ok=True, gnd_gap=0.5):
                return (round(q[0], 3), round(q[1], 3))
        return None

    def seg_ok(a, q, w, l, clr):
        seg = pcbnew.SHAPE_SEGMENT(V(*a), V(*q), F(w))
        for it in near((a[0] + q[0]) / 2, (a[1] + q[1]) / 2, rad=math.dist(a, q) / 2 + 1.5):
            if it["net"] == gnd:
                continue
            if it["k"] == "pad" and l in it["shp"] and it["shp"][l].Collide(seg, F(clr)):
                return False
            if it["k"] == "trk" and it["lay"] == l and it["shp"].Collide(seg, F(clr)):
                return False
            if it["k"] == "via" and seg.Collide(pcbnew.SHAPE_CIRCLE(V(*it["c"]), F(it["d"] / 2)), F(clr)):
                return False
        return True

    def rescue(p, l):
        """last resort for a GND pad: 0.4 / 0.2 via at 0.15 mm clearance (the netclass minimum), on a 0.2 mm straight or
        L-shaped stub from the pad centre or either end of its long axis (within 1.6 mm; the via may land on another GND
        pad: POFV), or a stub to an existing GND via, else a via in pad that may overhang the pad"""
        dv, c2 = (0.4, 0.2), 0.15
        bx = p["box"]
        cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        if bx[2] - bx[0] >= bx[3] - bx[1]:
            starts = [(cx, cy), (bx[0] + 0.12, cy), (bx[2] - 0.12, cy)]
        else:
            starts = [(cx, cy), (cx, bx[1] + 0.12), (cx, bx[3] - 0.12)]

        def path(st, q):
            best_ = None
            for pts in ([st, q], [st, (q[0], st[1]), q], [st, (st[0], q[1]), q]):
                ln = sum(math.dist(u, w) for u, w in zip(pts, pts[1:]))
                if (best_ is None or ln < best_[0]) and all(seg_ok(u, w, 0.2, l, c2) for u, w in zip(pts, pts[1:]) if u != w):
                    best_ = (ln, pts)
            return best_
        best = None
        for st in starts:                  # a stub to an existing GND via
            for v in gvias_near(st[0], st[1], 1.6):
                if v["k"] != "via":
                    continue
                pp = path(st, v["c"])
                if pp and (not best or pp[0] < best[0]):
                    best = pp
        if best:
            for u, w in zip(best[1], best[1][1:]):
                if u != w:
                    add_track(gnd, u, w, 0.2, l)
            added.append(dict(net="GND", c=list(best[1][-1]), d=0, drill=0, tag=f"rescue-link {p['ref']}.{p['num']}", pad=""))
            return "rescue-link"
        for st in starts:
            for q in ring(st[0], st[1], 0.3, 1.6, step=0.1):
                if best and math.dist(st, q) >= best[0]:
                    continue
                if pad_dist(p, q) < dv[0] / 2 + 0.02 or in_power(q[0], q[1], 0.4):
                    continue
                if legal(q[0], q[1], dv[0], dv[1], gnd, gnd_gap=0.5, clr=c2, in_pad_ok=True):
                    pp = path(st, q)
                    if pp and (not best or pp[0] < best[0]):
                        best = pp
        if best:
            add_via(gnd, best[1][-1], dv, f"rescue-stub {p['ref']}.{p['num']}")
            for u, w in zip(best[1], best[1][1:]):
                if u != w:
                    add_track(gnd, u, w, 0.2, l)
            return "rescue-stub"
        s_ = p["shp"][l]
        cands = []
        x = bx[0]
        while x <= bx[2] + 1e-9:
            y = bx[1]
            while y <= bx[3] + 1e-9:
                if s_.Collide(pcbnew.SHAPE_CIRCLE(V(x, y), 1), 0):
                    cands.append((x, y))
                y += 0.05
            x += 0.05
        for q in sorted(cands, key=lambda q: math.dist(q, (cx, cy))):
            if not in_power(q[0], q[1], 0.4, other_outer[l]) and \
                    legal(q[0], q[1], dv[0], dv[1], gnd, in_pad_ok=True, gnd_gap=0.5, clr=c2):
                add_via(gnd, (round(q[0], 3), round(q[1], 3)), dv, f"rescue-vip {p['ref']}.{p['num']}")
                return "rescue-vip"
        return None

    def stitch_pads(final=False):
        fails = []
        for p in gpads:
            l = pcbnew.F_Cu if pcbnew.F_Cu in p["lays"] else pcbnew.B_Cu
            if pad_ok(p, l, 1.0):
                continue
            ps = gz[l].GetFilledPolysList(l)
            bx = p["box"]
            cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
            hw = max(bx[2] - bx[0], bx[3] - bx[1]) / 2
            pieces = [i for i in range(ps.OutlineCount()) if ps.Contains(V(cx, cy), i)]
            cands = sorted(ring(cx, cy, 0.3, hw + 1.6), key=lambda q: pad_dist(p, q))
            done = None
            if pieces:
                k = pieces[0]
                for q in cands:
                    dq = pad_dist(p, q)
                    if dq < GND_VIA[0] / 2 + 0.05 or dq > 1.0:
                        continue
                    if inside(ps, q[0], q[1], GND_VIA[0] / 2 + 0.02, k) and not in_power(q[0], q[1], 0.45, other_outer[l]) \
                            and legal(q[0], q[1], GND_VIA[0], GND_VIA[1], gnd):
                        add_via(gnd, q, GND_VIA, f"pad {p['ref']}.{p['num']}"); done = "pad"
                        break
                if not done and pad_ok(p, l, 3.0):
                    done = "near"
            if not done:      # stub: via within 1.5 mm + a 0.25 mm track from the pad centre
                for q in cands:
                    dq = pad_dist(p, q)
                    if dq < GND_VIA[0] / 2 + 0.05 or dq > 1.5:
                        continue
                    if in_power(q[0], q[1], 0.45) or not legal(q[0], q[1], GND_VIA[0], GND_VIA[1], gnd):
                        continue
                    seg = pcbnew.SHAPE_SEGMENT(V(*p["c"]), V(*q), F(0.25))
                    ok = True
                    for it in near((cx + q[0]) / 2, (cy + q[1]) / 2, rad=2.5):
                        if it["net"] == gnd:
                            continue
                        if it["k"] == "pad" and l in it["shp"] and it["shp"][l].Collide(seg, F(CLR)):
                            ok = False; break
                        if it["k"] == "trk" and it["lay"] == l and it["shp"].Collide(seg, F(CLR)):
                            ok = False; break
                        if it["k"] == "via" and seg.Collide(pcbnew.SHAPE_CIRCLE(V(*it["c"]), F(it["d"] / 2)), F(CLR)):
                            ok = False; break
                    if ok:
                        add_via(gnd, q, GND_VIA, f"stub {p['ref']}.{p['num']}")
                        add_track(gnd, p["c"], q, 0.25, l); done = "stub"
                        break
            if not done:
                q = vip_spot(p, l)
                if q:
                    add_via(gnd, q, POFV, f"vip {p['ref']}.{p['num']}"); done = "vip"
            if not done and pieces:     # any spot of the pad's own fill piece within 3 mm
                for q in sorted(ring(cx, cy, 0.3, hw + 3.0, step=0.2), key=lambda q: pad_dist(p, q)):
                    if pad_dist(p, q) < GND_VIA[0] / 2 + 0.05:
                        continue
                    if inside(ps, q[0], q[1], GND_VIA[0] / 2 + 0.02, pieces[0]) and \
                            legal(q[0], q[1], GND_VIA[0], GND_VIA[1], gnd):
                        add_via(gnd, q, GND_VIA, f"pad3 {p['ref']}.{p['num']}"); done = "pad3"
                        break
            if not done and (final or not pieces):
                done = rescue(p, l)
            if done:
                bump(done)
            else:
                fails.append(f"{p['ref']}.{p['num']}")
        return fails

    fill()
    stitch_pads()
    fill()
    stitch_pads()           # second pass on the refilled board (new vias change the fill)

    def piece_pass():
        fails = []
        for l in gz:
            ps = gz[l].GetFilledPolysList(l)
            for i in range(ps.OutlineCount()):
                ol = ps.Outline(i)
                pts = [L(ol.CPoint(k)) for k in range(ol.PointCount())]
                xs, ys = [q[0] for q in pts], [q[1] for q in pts]
                area = abs(sum(pts[k][0] * pts[k - 1][1] - pts[k - 1][0] * pts[k][1] for k in range(len(pts)))) / 2
                if any(ps.Contains(V(*v["c"]), i) for v in gvias_near((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                                                                       max(max(xs) - min(xs), max(ys) - min(ys)) + 1)):
                    continue
                ok = False
                x = min(xs)
                while x <= max(xs) and not ok:
                    y = min(ys)
                    while y <= max(ys):
                        if inside(ps, x, y, GND_VIA[0] / 2 + 0.02, i) and not in_power(x, y, 0.45) and \
                                legal(x, y, GND_VIA[0], GND_VIA[1], gnd):
                            add_via(gnd, (x, y), GND_VIA, "piece"); ok = True
                            break
                        y += 0.1
                    x += 0.1
                if not ok:          # a POFV in one of the piece's own GND pads
                    for p in gpads:
                        if l in p["lays"] and min(xs) <= p["c"][0] <= max(xs) and min(ys) <= p["c"][1] <= max(ys) \
                                and ps.Contains(V(*p["c"]), i):
                            q = vip_spot(p, l)
                            if q:
                                add_via(gnd, q, POFV, f"vip-piece {p['ref']}.{p['num']}"); ok = True
                                break
                            if rescue(p, l):
                                ok = True
                                break
                if not ok:
                    fails.append((pcbnew.BOARD.GetStandardLayerName(l), round(min(xs), 2), round(min(ys), 2),
                                  round(max(xs), 2), round(max(ys), 2), round(area, 2)))
        return fails

    piece_pass()

    # grid stitching (3 mm) over the fills, preferring spots inside GND fill on all three routable layers
    gx = 1.0
    while gx < W:
        gy = 1.0
        while gy < H:
            if not gvias_near(gx, gy, 1.5):
                best = None
                for q in [(gx, gy)] + ring(gx, gy, 0.15, 0.9, step=0.2):
                    sc = sum(1 for l in gz if gnd_at(l, q[0], q[1], GND_VIA[0] / 2 + 0.02))
                    if sc == 0 or (best and sc <= best[0]) or gvias_near(q[0], q[1], 1.2):
                        continue
                    if not in_power(q[0], q[1], 0.45) and legal(q[0], q[1], GND_VIA[0], GND_VIA[1], gnd, gnd_gap=1.2):
                        best = (sc, q)
                        if sc == 3:
                            break
                if best:
                    add_via(gnd, best[1], GND_VIA, "grid")
            gy += 3.0
        gx += 3.0

    # fence: GND vias along the power pours' L1 edges, ~2 mm apart, on the GND fill beside them
    for z in [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetCode() != gnd and z.GetLayer() == pcbnew.F_Cu]:
        ps = z.GetFilledPolysList(pcbnew.F_Cu)
        for i in range(ps.OutlineCount()):
            ol = ps.Outline(i)
            pts = [L(ol.CPoint(k)) for k in range(ol.PointCount())]
            acc, samples = 0.0, []
            for a, c in zip(pts, pts[1:] + pts[:1]):
                seg = math.dist(a, c)
                while acc <= seg:
                    t = acc / seg if seg else 0
                    samples.append((a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t))
                    acc += 2.0
                acc -= seg
            for s in samples:
                if gvias_near(s[0], s[1], 1.6):
                    continue
                for q in sorted(ring(s[0], s[1], 0.5, 1.2, step=0.2), key=lambda q: math.dist(q, s)):
                    if gnd_at(pcbnew.F_Cu, q[0], q[1], GND_VIA[0] / 2 + 0.02) and not in_power(q[0], q[1], 0.45) and \
                            legal(q[0], q[1], GND_VIA[0], GND_VIA[1], gnd, gnd_gap=1.2):
                        add_via(gnd, q, GND_VIA, "fence")
                        break
    fill()
    pad_fail = stitch_pads(final=True)
    fill()
    piece_fail = piece_pass()
    LOG.update(rep=rep, rejected=stats["rejected"], vias=added, pad_fail=pad_fail, piece_fail=piece_fail)
    out = HERE / "out" / "exp" / (__import__("os").environ.get("TAIL_EXP") or "hP") / "hP_vias.json"
    json.dump(LOG, open(out, "w"), indent=0, default=str)
    kinds = {}
    for v in added:
        kinds[v["tag"].split()[0]] = kinds.get(v["tag"].split()[0], 0) + 1
    print("hP vias:", kinds, "| in pad:", sum(1 for v in added if v["pad"]), "| pad results:", rep)
    print("hP fixed vias rejected:", stats["rejected"])
    print("hP GND pads without a via <= 1 mm on their fill (or 3 mm when none fits):", pad_fail)
    print("hP GND fill pieces without a via:", piece_fail)


# ---- hand fixes for GND pads walled in by signal copper (before the op, so its via checks see them)
F1_, L3_, L4_ = "F.Cu", "In2.Cu", "B.Cu"
HAND = [("C22", "2"), ("C23", "2"), ("C400", "2"), ("C46", "2")]
# C22.2 (U2 DVDD 1 uF, walled in by the +3V3 / +5V vias, W_EN and the DVDD lane; L3 / L4 full under it): the +5V
# L3 -> L4 drop (58.65, 25.9) is a redundant loop (the hub (67.7, 20.4) also feeds L4 through (59.2, 22.1) -> (59.8,
# 27.45) -> (58.75, 27.5)), so it goes; C22.2 then runs on L1 to U2's AGND pin 35 (DESIGN 6.4: the DVDD cap returns there)
EDITS.append(dict(op="rip", box=(57.9, 25.8, 58.75, 26.5), nets=["+5V"], reroute=False))
EDITS.append(dict(op="rip_segs", tracks=[("+5V", L3_, (62.9, 21.65), (66.15, 21.65))]))   # its stub (doubles the y 21.65 run)
EDITS.append(dict(op="track", net="GND", layer=F1_, pts=[(58.0, 26.5), (58.3, 26.1), (59.3, 26.1), (59.8, 26.25)], w=0.2))
# C23.2: the +3V3 via (57.75, 20.75) moves 0.25 mm east (opens a lane), GND stub south to the stitched fill
EDITS.append(dict(op="rip_segs", tracks=[("+3V3", F1_, (57.75, 20.75), (57.9, 20.6)),
                                         ("+3V3", L4_, (58.01, 21.4), (57.75, 20.75)),
                                         ("+3V3", L4_, (57.7, 20.8), (57.75, 20.75))], vias=[("+3V3", (57.75, 20.75))]))
EDITS.append(dict(op="via", net="+3V3", c=(58.0, 20.82), d=0.45, drill=0.25))
EDITS.append(dict(op="track", net="+3V3", layer=F1_, pts=[(58.0, 20.82), (58.05, 20.6)], w=0.2))
EDITS.append(dict(op="track", net="+3V3", layer=L4_, pts=[(57.7, 20.8), (58.0, 20.82)], w=0.2))
EDITS.append(dict(op="track", net="+3V3", layer=L4_, pts=[(58.0, 20.82), (58.01, 21.4)], w=0.15))
EDITS.append(dict(op="track", net="GND", layer=F1_, pts=[(57.5, 20.3), (57.45, 21.95)], w=0.2))
# C400.2 (U4 VM 100 nF, walled in by the charge-pump lanes): via in pad; U4's 1.0 mm L3 VM strip jogs west around it
EDITS.append(dict(op="rip", box=(18.3, 20.6, 18.6, 26.6), nets=[n_("R_VM")], layers=[L3_], keep_vias=True, reroute=False))
EDITS.append(dict(op="track", net=n_("R_VM"), layer=L3_, pts=[(18.45, 20.75), (18.45, 22.0), (17.45, 22.6), (17.45, 23.8),
                                                                (18.45, 24.4), (18.45, 26.48)], w=1.0))
EDITS.append(dict(op="via", net="GND", c=(18.6, 23.22), d=0.4, drill=0.2))
# C46.2 (bottom, under J2's pad row): a GND via north-east of the row, L4 stub between R54.1 and L_H2's via
EDITS.append(dict(op="via", net="GND", c=(11.55, 31.6), d=0.4, drill=0.2))
EDITS.append(dict(op="track", net="GND", layer=L4_, pts=[(9.88, 33.75), (10.7, 33.75), (10.6, 32.6), (11.12, 31.95),
                                                         (11.55, 31.6)], w=0.2))
EDITS.append(dict(op="py", fn=apply))
# GND pads with no via spot within reach of a straight / L stub (dense corners): the router's drop (pad -> track ->
# nearest legal via spot, L1 / L4, after the pours exist; the power pours block it, the GND fills do not)
DROP = [("U1", "47"), ("C80", "2"), ("U10", "4")]
for pad in DROP:
    EDITS.append(dict(op="drop", pad=pad, net="GND", layers=["F.Cu", "B.Cu"], w=0.2, via=0.4, drill=0.2, margin=4.0))
