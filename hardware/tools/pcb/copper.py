"""Hand copper for the ThumbsUp v1 board: power pours, via fields, gate stubs, Kelvin
stubs.  Everything else (logic, gate drive from the vias on, sense lines) is left to
Freerouting (route.py).

Layer plan (4 layers, 2 oz outer / 1 oz inner):
  F.Cu   VBAT pour (W + L blocks, both cans), VBAT pour (R block + R can), VBAT_PACK
         under J1, nine phase pours, three I_x+ pours to the shunts, GND patches with
         via fields at every shunt / can GND pad.
  In1    GND plane with an 8 mm VBAT corridor (cans -> L block left edge -> front -> R can).
  In2    signals only (Freerouting).
  B.Cu   VBAT_PACK / VBAT pours under J1 (pack shunt R2) and under the W high row;
         GND pour everywhere else (thermal reliefs).

FET geometry (PQFN-8-EP 5x6, rot 90 / 270): leads 1-3 = source, 4 = gate on the
column's outer side, pad 5 = drain tab (custom polygon -2.35..2.35 x -1.1..3.5 in the
footprint frame).  Every gate gets a via 1.045 mm outboard of its pad and 1.0 mm into
the neighbouring pour, with the pour notched around it (see ``gate_notches``).
"""

from __future__ import annotations

import pcbnew

from board import Board

F, IN1, IN2, B = pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu

VIA_D, VIA_DRILL = 0.6, 0.3
GATE_VIA_OUT, GATE_VIA_IN = 1.045, 1.0     # gate via: outboard of pad 4, into the pour
NOTCH_IN = GATE_VIA_IN + VIA_D / 2 + 0.35   # pour notch depth past the leads row
PWR_CLR = 0.35                              # power copper clearance (also in thumbsup.kicad_dru)


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def pad(b: Board, ref: str, num: str):
    for p in b.fps[ref].Pads():
        if p.GetNumber() == num:
            return p
    raise KeyError((ref, num))


def pad_xy(b: Board, ref: str, num: str):
    p = pad(b, ref, num).GetPosition()
    return pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)


def net_of(b: Board, ref: str, num: str) -> str:
    return pad(b, ref, num).GetNetname()


# ---------------------------------------------------------------- gates
def gate_info(b: Board, ref: str):
    """(gx, gy, sx, sy): gate pad centre, outboard direction, pour-interior direction."""
    fp = b.fps[ref]
    gx, gy = pad_xy(b, ref, "4")
    cx, cy = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
    sx = 1.0 if gx > cx else -1.0
    sy = 1.0 if gy > cy else -1.0          # leads point away from the body centre
    return gx, gy, sx, sy


def gate_via_xy(b: Board, ref: str):
    gx, gy, sx, sy = gate_info(b, ref)
    return gx + sx * GATE_VIA_OUT, gy + sy * GATE_VIA_IN


def notched_edge(x0, x1, y_edge, notches, sy):
    """Points along a horizontal zone edge from x0 to x1 at y_edge, with rectangular
    notches (xa, xb, depth) cut into the zone (interior is +sy)."""
    pts = [(x0, y_edge)]
    for xa, xb, depth in sorted(n for n in notches if n[1] > x0 and n[0] < x1):
        xa, xb = max(xa, x0), min(xb, x1)
        pts += [(xa, y_edge), (xa, y_edge + sy * depth), (xb, y_edge + sy * depth), (xb, y_edge)]
    pts.append((x1, y_edge))
    return pts


def zone_with_top_notches(b, net, layer, x0, y0, x1, y1, notches, priority, name):
    """Rectangle zone whose top edge (y0) carries notches; interior is +y."""
    pts = notched_edge(x0, x1, y0, notches, +1.0) + [(x1, y1), (x0, y1)]
    return b.zone(net, layer, pts, priority=priority, clearance=PWR_CLR, min_width=0.25, name=name)


def zone_with_bottom_notches(b, net, layer, x0, y0, x1, y1, notches, priority, name):
    """Rectangle zone whose bottom edge (y1) carries notches; interior is -y."""
    edge = notched_edge(x0, x1, y1, notches, -1.0)
    pts = [(x0, y0), (x1, y0)] + list(reversed(edge))
    return b.zone(net, layer, pts, priority=priority, clearance=PWR_CLR, min_width=0.25, name=name)


def gate_notch_own(gx, sx):
    """Notch in the gate's own pour: from 0.4 inboard of pad 4 to the pour's outer edge."""
    a, c = gx - sx * 0.75, gx + sx * 3.0
    return (min(a, c), max(a, c), NOTCH_IN)


def gate_notch_neighbour(gx, sx):
    """Notch in the next column's pour (same edge) up to its pad 1: 1.74 outboard of pad 4."""
    a, c = gx + sx * 1.0, gx + sx * 1.74
    return (min(a, c), max(a, c), NOTCH_IN)


def gate_notch_shared(gx, sx):
    """Notch in a pour shared by several columns (I_x+): pad-4 clearance up to the next pad 1."""
    a, c = gx - sx * 0.75, gx + sx * 1.74
    return (min(a, c), max(a, c), NOTCH_IN)


# ---------------------------------------------------------------- pour pickup vias
def pickup_via_spots(b: Board, blocks: dict):
    """(net, x, y) for vias that give Freerouting a target inside every F.Cu pour it cannot
    connect to on its own: two per phase column (beside the high FET's leads and beside the
    low FET's tab, away from the gate side), two per I_x+ band, two in the R VBAT pour."""
    spots = []
    for base, blk in blocks.items():
        u = base // 10
        cols, y_hi, y_lo, flip = blk["cols"], blk["y_hi"], blk["y_lo"], blk["flip"]
        for i, col in enumerate(cols):
            gx, gy, sx, sy = gate_info(b, f"Q{u + 2 * i}")     # high FET: leads face the pour
            net = net_of(b, f"Q{u + 2 * i}", "1")
            x = col - sx * 2.0
            spots.append((net, x, y_hi + sy * 4.1))              # just past the high FET's lead pads
            spots.append((net, x, y_lo - sy * 4.3))              # just before the low FET's tab
        # I_x+ band: beside the low FETs' leads, the band side away from the notches
        lo_net = net_of(b, f"Q{u + 1}", "1")
        gx, gy, sx, sy = gate_info(b, f"Q{u + 1}")
        for col in ((cols[0], cols[1]) if flip else (cols[0], cols[2])):   # flip: cols[2] + 2 is on the chamfer
            spots.append((lo_net, col - sx * 2.0, gy + sy * 2.2))
    spots.append(("VBAT", 80.3, 21.6))
    spots.append(("VBAT", 96.6, 21.6))
    return spots


# ---------------------------------------------------------------- reservations (bottom side)
def reserved_rects(b: Board, blocks: dict) -> list[tuple[float, float, float, float]]:
    """Bottom-side rectangles the packer must keep free: via fields, GND patches and the
    gate vias (computed from the placed FETs)."""
    r = [
        (31.4, 1.0, 35.4, 12.6),      # left VBAT via field (F <-> In2 <-> B)
        (80.0, 29.8, 87.2, 33.8),     # R can VBAT via field (F <-> In1 corridor)
        (12.6, 15.9, 31.2, 18.2),     # bottom VBAT band under the W high tabs
        (53.5, 15.6, 56.2, 19.6),     # C223/C224 VBAT patch + via
        (13.2, 17.4, 14.8, 20.3),     # C423 VBAT via patch
        (25.0, 17.4, 26.6, 20.3),     # C424 VBAT via patch
        (79.8, 24.3, 82.3, 26.1),     # C323 VBAT via patch
        (94.8, 24.3, 97.4, 26.1),     # C324 VBAT via patch
    ]
    for ref, num in (("R235", "2"), ("R335", "2"), ("R435", "2"), ("C225", "2"), ("C425", "2"), ("C325", "2")):
        bb = pad(b, ref, num).GetBoundingBox()
        r.append((pcbnew.ToMM(bb.GetLeft()) - 0.75, pcbnew.ToMM(bb.GetTop()) - 0.75, pcbnew.ToMM(bb.GetRight()) + 0.75, pcbnew.ToMM(bb.GetBottom()) + 0.75))
    for base in blocks:
        u = base // 10
        for i in range(6):
            vx, vy = gate_via_xy(b, f"Q{u + i}")
            r.append((vx - 0.55, vy - 0.55, vx + 0.55, vy + 0.55))
    for net, x, y in pickup_via_spots(b, blocks):
        r.append((x - 0.5, y - 0.5, x + 0.5, y + 0.5))
    for x, y in pico_gnd_via_spots(b):
        r.append((x - 0.5, y - 0.5, x + 0.5, y + 0.5))
    return r


def pico_gnd_via_spots(b: Board):
    """GND vias for the Pico's castellation pads sit 2.3 mm inboard of each pad (the bottom
    under the pad columns is packed with parts, so the spot is reserved before packing)."""
    fp = b.fps["A1"]
    cx = pcbnew.ToMM(fp.GetPosition().x)
    out = []
    for pad in fp.Pads():
        if pad.GetNetname() == "GND" and pad.GetDrillSize().x == 0:
            px, py = pcbnew.ToMM(pad.GetPosition().x), pcbnew.ToMM(pad.GetPosition().y)
            out.append((px + 2.3 if px < cx else px - 2.0, py))   # right column: 2.0 keeps clear of the antenna keep-out
    return out


# ---------------------------------------------------------------- pours
def gnd_patch(b: Board, ref: str, num: str, sides="tblr", priority=4):
    """F.Cu GND patch around a top-side GND pad with vias just outside the pad on the
    given sides (t/b/l/r: corners + mid) into the plane."""
    bb = pad(b, ref, num).GetBoundingBox()
    x0, y0, x1, y1 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
    b.zone("GND", F, rect(x0 - 0.65, y0 - 0.65, x1 + 0.65, y1 + 0.65), priority=priority, clearance=PWR_CLR, min_width=0.25, name=f"GND {ref}")
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    d = 0.33                                  # via centre just outside the pad, fully inside the patch
    spots = []
    if "t" in sides:
        spots += [(x0 - d, y0 - d), (cx, y0 - d), (x1 + d, y0 - d)]
    if "b" in sides:
        spots += [(x0 - d, y1 + d), (cx, y1 + d), (x1 + d, y1 + d)]
    if "l" in sides:
        spots += [(x0 - d, cy)]
    if "r" in sides:
        spots += [(x1 + d, cy)]
    for x, y in spots:
        if y > 0.8:                      # C425's GND pad sits at the wall edge
            b.via("GND", x, y, VIA_DRILL, VIA_D)


def via_grid(b: Board, net: str, xs, ys):
    for x in xs:
        for y in ys:
            b.via(net, x, y, VIA_DRILL, VIA_D)


def frange(a, b_, step):
    out, x = [], a
    while x <= b_ + 1e-6:
        out.append(round(x, 3))
        x += step
    return out


def mlcc_via(b: Board, ref: str, num: str, vx, vy, patch):
    """Bottom-side MLCC VBAT pad: B.Cu patch zone + via up into the top pour."""
    net = net_of(b, ref, num)
    b.zone(net, B, rect(*patch), priority=2, clearance=0.2, min_width=0.25, name=f"{net} {ref}")
    b.via(net, vx, vy, VIA_DRILL, VIA_D)


def phase_pours(b: Board, base: int, blk: dict):
    u = base // 10
    cols, y_hi, y_lo, flip = blk["cols"], blk["y_hi"], blk["y_lo"], blk["flip"]
    # per-column pour extents (rot 90: high leads row +2.0 .. low tab end +1.3; rot 270 mirrored)
    if not flip:
        y0, y1 = y_hi + 2.0, y_lo + 1.3          # high leads row .. low tab end
    else:
        y0, y1 = y_lo - 1.3, y_hi - 2.0          # low tab end .. high leads row
    gates = []   # (gx, sx) of the high FETs, one per column
    for i, x in enumerate(cols):
        gx, gy, sx, sy = gate_info(b, f"Q{u + 2 * i}")
        gates.append((gx, sx))
    for i, x in enumerate(cols):
        net = net_of(b, f"Q{u + 2 * i}", "1")
        notches = [gate_notch_own(*gates[i])]
        # rot 90 gates face +x, so column i also carries the notch of column i-1's gate (it sits just
        # before this column's pad 1); mirrored for rot 270
        j = i - 1 if not flip else i + 1
        if 0 <= j < 3:
            notches.append(gate_notch_neighbour(*gates[j]))
        if not flip:
            zone_with_top_notches(b, net, F, x - 2.75, y0, x + 2.75, y1, notches, 3, f"{net} pour")
        else:
            zone_with_bottom_notches(b, net, F, x - 2.75, y0, x + 2.75, y1, notches, 3, f"{net} pour")


def gate_stubs(b: Board, blocks: dict):
    for base in blocks:
        u = base // 10
        for i in range(6):
            ref = f"Q{u + i}"
            gx, gy = pad_xy(b, ref, "4")
            vx, vy = gate_via_xy(b, ref)
            net = net_of(b, ref, "4")
            b.track(net, (gx, gy), (vx, vy), 0.25, F)
            b.via(net, vx, vy, VIA_DRILL, VIA_D)


def kelvin_stubs(b: Board, shunts):
    """Tie pad 1 -> 0.9 mm into the shunt pad of the same net."""
    for ref, nt_a, nt_b in shunts:
        fp = b.fps[ref]
        layer = B if fp.IsFlipped() else F
        p1, p2 = pad_xy(b, ref, "1"), pad_xy(b, ref, "2")
        ux, uy = (p2[0] - p1[0]) / 4.4, (p2[1] - p1[1]) / 4.4
        for nt in (nt_a, nt_b):
            net = net_of(b, nt, "1")
            pos = pad_xy(b, nt, "1")
            sgn = 1.0 if net == net_of(b, ref, "2") else -1.0
            b.track(net, pos, (pos[0] + sgn * 0.9 * ux, pos[1] + sgn * 0.9 * uy), 0.2, layer)


def copper(b: Board, mech: dict, blocks: dict, shunts):
    outline = mech["outline"]

    # ---- planes -----------------------------------------------------------------
    b.zone("GND", IN1, outline, priority=0, clearance=PWR_CLR, min_width=0.25, name="GND plane")
    b.zone("GND", B, outline, priority=0, clearance=PWR_CLR, min_width=0.25, thermal=False, name="GND bottom")  # solid: thermal spokes starve in the dense bottom

    # ---- pack entry: J1 pad 2 -> R2 (bottom) -> VBAT --------------------------------
    b.zone("VBAT_PACK", F, rect(17.2, 6.0, 24.0, 16.0), priority=1, clearance=PWR_CLR, name="VBAT_PACK top")
    b.zone("VBAT_PACK", B, rect(17.2, 6.0, 24.0, 16.0), priority=1, clearance=PWR_CLR, name="VBAT_PACK bottom")
    vbat_bottom = [(25.5, 0.6), (36.0, 0.6), (36.0, 13.0), (31.2, 13.0), (31.2, 18.2), (12.6, 18.2), (12.6, 15.9),
                   (28.5, 15.9), (28.5, 11.3), (25.5, 11.3)]
    b.zone("VBAT", B, vbat_bottom, priority=1, clearance=PWR_CLR, name="VBAT bottom (R2 -> W high row, via field)")

    # ---- VBAT top: W block top row + bridge + cans + L block top row -------------------
    vbat_top = [(12.6, 15.9), (31.2, 15.9), (31.2, 0.3), (56.0, 0.3), (56.0, 18.6), (35.8, 18.6), (35.8, 27.0),
                (30.3, 27.0), (30.3, 22.5), (12.6, 22.5)]
    b.zone("VBAT", F, vbat_top, priority=1, clearance=PWR_CLR, name="VBAT top W+L")
    vbat_r = [(79.6, 20.9), (97.3, 20.9), (97.3, 26.6), (94.3, 26.6), (94.3, 37.2), (79.6, 37.2)]
    b.zone("VBAT", F, vbat_r, priority=1, clearance=PWR_CLR, name="VBAT top R")
    # VBAT bus as an 8 mm corridor in the In1 GND plane (1 oz, ~7 A continuous: the drive motors
    # are low-KV geared BLDCs, the weapon is fed on F.Cu): cans -> down the left edge of the L
    # block -> along the front under the Pico -> R can.  This keeps In2 entirely free for signals
    # (Freerouting routes the dense Pico / cell undersides there); the plane stays connected around
    # the corridor.  Two overlapping zones with distinct priorities (KiCad zones_intersect rule).
    b.zone("VBAT", IN1, [(31.5, 0.6), (56.0, 0.6), (56.0, 13.0), (44.0, 13.0), (44.0, 37.2), (36.0, 37.2), (36.0, 13.0), (31.5, 13.0)],
           priority=1, clearance=PWR_CLR, name="VBAT bus In1 (cans -> L block left)")
    b.zone("VBAT", IN1, rect(43.0, 29.0, 93.0, 35.0), priority=2, clearance=PWR_CLR, name="VBAT bus In1 (front -> R can)")  # y <= 35 keeps a plane strip along the front edge so the plane is not split
    # A track on In1 stops Freerouting from declaring In1 a power plane: with a plane layer it
    # flags GND *and* VBAT as "plane nets" and never routes their pads (DsnFile.java).  GND pads
    # get their own vias below; VBAT pads are routed to the via fields like any other net.
    b.track("VBAT", (40.0, 6.0), (42.0, 6.0), 1.0, IN1)
    via_grid(b, "VBAT", (31.9, 33.4, 34.9), frange(1.6, 12.1, 1.5))          # left field: F / In2 / B
    via_grid(b, "VBAT", frange(80.6, 86.6, 1.0), (30.4, 31.8, 33.2))         # R can field: F / In1 corridor
    via_grid(b, "VBAT", frange(13.5, 29.5, 1.6), (17.0,))                    # W high row: F / B band
    # bottom drain MLCCs -> VBAT pours above them
    mlcc_via(b, "C423", "1", 13.9, 17.6, (13.3, 17.4, 14.8, 20.3))
    mlcc_via(b, "C424", "1", 25.6, 17.6, (25.0, 17.4, 26.6, 20.3))
    mlcc_via(b, "C223", "1", 53.95, 17.6, (53.6, 15.7, 56.1, 19.5))
    mlcc_via(b, "C323", "1", 80.4, 25.2, (80.0, 24.4, 82.2, 26.0))
    mlcc_via(b, "C324", "1", 96.9, 25.2, (95.0, 24.4, 97.3, 26.0))

    # ---- phase pours and I_x+ pours ---------------------------------------------------
    for base, blk in blocks.items():
        phase_pours(b, base, blk)
    lo_gates = {base: [gate_info(b, f"Q{base // 10 + 2 * i + 1}") for i in range(3)] for base in blocks}
    # L: leads row at y_lo + 2.73, pour down to 33.0, extension to R235 pad 1 (x 46.65..49.75, y 31.5..35.5)
    # straight under column 3's leads; right of it the band stays above R235's GND patch
    yl = blocks[200]["y_lo"]
    n = [gate_notch_shared(g[0], g[2]) for g in lo_gates[200]]
    pts = notched_edge(35.8, 53.5, yl + 2.0, n, +1.0) + [(53.5, 30.4), (50.0, 30.4), (50.0, 35.7), (46.4, 35.7), (46.4, 33.0), (35.8, 33.0)]
    b.zone(net_of(b, "R235", "1"), F, pts, priority=2, clearance=PWR_CLR, name="I_L+ pour")
    # W: leads row at y_lo + 2.73, pour to 37.2, over R435 pad 1 (x 30.9..34.9, y 32.15..35.25)
    yw = blocks[400]["y_lo"]
    n = [gate_notch_shared(g[0], g[2]) for g in lo_gates[400]]
    pts = notched_edge(12.6, 35.0, yw + 2.0, n, +1.0) + [(35.0, 37.2), (12.6, 37.2)]
    b.zone(net_of(b, "R435", "1"), F, pts, priority=2, clearance=PWR_CLR, name="I_W+ pour")
    # R (flipped): leads row at y_lo - 2.73, pour upward to R335 pad 1 (x 80.75..83.85, y 2.4..6.4)
    yr = blocks[300]["y_lo"]
    n = [gate_notch_shared(g[0], g[2]) for g in lo_gates[300]]
    edge = notched_edge(79.6, 97.0, yr - 2.0, n, -1.0)
    pts = [(79.6, 2.2), (84.0, 2.2), (84.0, 6.9), (88.6, 6.9), (88.6, 1.1), (97.0, 9.5)] + list(reversed(edge))
    b.zone(net_of(b, "R335", "1"), F, pts, priority=2, clearance=PWR_CLR, name="I_R+ pour")

    # ---- GND returns: shunt and can GND pads into the plane -----------------------------
    gnd_patch(b, "R235", "2", "br", priority=5)   # top side faces the L low FET leads, left side the I_L+ extension
    gnd_patch(b, "R335", "2", "tlr")       # bottom side faces the I_R+ band
    gnd_patch(b, "R435", "2", "tblr")
    gnd_patch(b, "C225", "2", "tb")        # side vias at the pad's mid-height get re-netted by KiCad
    gnd_patch(b, "C425", "2", "bl")
    gnd_patch(b, "C325", "2", "tblr")

    gate_stubs(b, blocks)
    kelvin_stubs(b, shunts)
    for net, x, y in pickup_via_spots(b, blocks):
        b.via(net, x, y, VIA_DRILL, VIA_D)
    for z in b.b.Zones():
        if not z.GetIsRuleArea() and z.GetLayer() != B:
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)   # no floating slivers on F / In1


def _items_near(board, x, y, r):
    """Pads (any layer), vias and tracks within r mm of (x, y), as (item, distance_to_copper_edge)."""
    pt = pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
    out = []
    for fp in board.Footprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            if bb.Inflate(pcbnew.FromMM(r)).Contains(pt):
                out.append(pad)
    for t in board.Tracks():
        bb = t.GetBoundingBox()
        if bb.Inflate(pcbnew.FromMM(r)).Contains(pt):
            out.append(t)
    return out


def free_spot(board, x, y, via_d=0.5, clearance=0.2, net=None, outline=None):
    """True if a via of ``via_d`` at (x, y) keeps ``clearance`` from every pad / track / via of a
    different net on any layer and is inside the outline (0.5 mm in)."""
    if outline is not None:
        from placement import point_in_poly
        for dx, dy in ((0.5, 0.5), (-0.5, 0.5), (0.5, -0.5), (-0.5, -0.5)):
            if not point_in_poly(x + dx, y + dy, outline):
                return False
    pt = pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
    need = pcbnew.FromMM(via_d / 2 + clearance - 0.005)
    zones = list(board.Zones())
    for fp in board.Footprints():
        zones += list(fp.Zones())
    r_ = pcbnew.FromMM(via_d / 2 + 0.05)
    d_ = int(r_ * 0.7071)
    probe = [pt, pcbnew.VECTOR2I(pt.x + r_, pt.y), pcbnew.VECTOR2I(pt.x - r_, pt.y), pcbnew.VECTOR2I(pt.x, pt.y + r_), pcbnew.VECTOR2I(pt.x, pt.y - r_),
             pcbnew.VECTOR2I(pt.x + d_, pt.y + d_), pcbnew.VECTOR2I(pt.x - d_, pt.y + d_), pcbnew.VECTOR2I(pt.x + d_, pt.y - d_), pcbnew.VECTOR2I(pt.x - d_, pt.y - d_)]
    for z in zones:                               # keep-outs that forbid vias (Pico antenna / RF / pad keep-outs)
        if z.GetIsRuleArea() and z.GetDoNotAllowVias() and any(z.Outline().Contains(q) for q in probe):
            return False
    for it in _items_near(board, x, y, via_d / 2 + clearance + 0.05):
        if net is not None and it.GetNetname() == net:
            continue
        if it.GetClass() == "PAD" and not (it.IsOnLayer(pcbnew.F_Cu) or it.IsOnLayer(pcbnew.B_Cu)):
            continue                              # paste-only pads (Pico castellation extensions)
        if it.GetClass() == "PCB_VIA":
            d = (it.GetPosition() - pt).EuclideanNorm() - it.GetWidth(pcbnew.F_Cu) // 2
        elif it.GetClass() == "PCB_TRACK":
            d = pcbnew.SEG(it.GetStart(), it.GetEnd()).Distance(pt) - it.GetWidth() // 2
        else:                                    # pad: conservative distance to its bounding box
            bb = it.GetBoundingBox()
            dx = max(bb.GetLeft() - pt.x, 0, pt.x - bb.GetRight())
            dy = max(bb.GetTop() - pt.y, 0, pt.y - bb.GetBottom())
            d = int((dx * dx + dy * dy) ** 0.5)
        if d < need:
            return False
    return True


def via_for_pad(board, pad, outline, via_d=0.5, drill=0.25, track_w=0.25, clearance=0.15):
    """Place a via next to ``pad`` (8 candidate directions, then in-pad as a last resort) and a
    stub joining them on the pad's layer.  Returns the via or None."""
    net = pad.GetNetname()
    c = pad.GetPosition()
    cx, cy = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
    sz = pad.GetSize()
    hx, hy = pcbnew.ToMM(sz.x) / 2, pcbnew.ToMM(sz.y) / 2
    if pad.GetOrientationDegrees() % 180 == 90:
        hx, hy = hy, hx
    layer = pcbnew.B_Cu if pad.IsFlipped() else pcbnew.F_Cu
    cands = []
    for step in (0.0, 0.3, 0.6, 0.75, 1.05, 1.5, 2.0):
        d = via_d / 2 + 0.2 + step
        cands += [(cx + hx + d, cy), (cx - hx - d, cy), (cx, cy + hy + d), (cx, cy - hy - d),
                  (cx + hx + d * 0.8, cy + hy + d * 0.8), (cx - hx - d * 0.8, cy + hy + d * 0.8),
                  (cx + hx + d * 0.8, cy - hy - d * 0.8), (cx - hx - d * 0.8, cy - hy - d * 0.8)]
    for x, y in cands + [(cx, cy)]:
        if free_spot(board, x, y, via_d, clearance, net=net, outline=outline) and _stub_clear(board, (cx, cy), (x, y), track_w, net):
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
            v.SetDrill(pcbnew.FromMM(drill)); v.SetWidth(pcbnew.FromMM(via_d)); v.SetNet(pad.GetNet())
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            board.Add(v)
            if (x, y) != (cx, cy):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(c); t.SetEnd(v.GetPosition()); t.SetWidth(pcbnew.FromMM(track_w)); t.SetLayer(layer); t.SetNet(pad.GetNet())
                board.Add(t)
            return v
    return None


def _stub_clear(board, a, b_, w, net):
    """The straight stub a->b (width w) touches nothing of another net (sampled every 0.1 mm)."""
    dx, dy = b_[0] - a[0], b_[1] - a[1]
    n = max(1, int((dx * dx + dy * dy) ** 0.5 / 0.1))
    for i in range(1, n):
        x, y = a[0] + dx * i / n, a[1] + dy * i / n
        if not free_spot(board, x, y, w, 0.1, net=net):
            return False
    return True


def stranded_gnd_pads(board, net_name="GND", layer=None):
    """Bottom GND pads whose centre lies in a non-main island of the bottom GND pour."""
    layer = B if layer is None else layer
    out = []
    for z in board.Zones():
        if not hasattr(z, "GetIsRuleArea") or z.GetIsRuleArea() or z.GetNetname() != net_name or z.GetLayer() != layer:
            continue                                   # (bare SwigPyObject after board.Remove(): skip)
        isl = islands(board, z, layer)
        main = isl[0][1] if isl else None
        for fp in board.Footprints():
            for pad in fp.Pads():
                if pad.GetNetname() != net_name or not pad.IsFlipped() or pad.GetDrillSize().x > 0:
                    continue
                if main is not None and main.PointInside(pad.GetPosition()):
                    continue
                out.append(pad)
    return out


def relocate_keepout_vias(board, outline):
    """Vias that ended up inside a via keep-out (older builds probed only the via centre): drop
    the via and its stub, then place a fresh via for the pad the stub came from."""
    zones = [z for z in board.Zones() if hasattr(z, "GetIsRuleArea") and z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    for fp in board.Footprints():
        zones += [z for z in fp.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    moved = 0
    for v in [t for t in board.Tracks() if t.GetClass() == "PCB_VIA"]:
        pt = v.GetPosition()
        r_ = v.GetWidth(pcbnew.F_Cu) // 2
        probe = [pt, pcbnew.VECTOR2I(pt.x + r_, pt.y), pcbnew.VECTOR2I(pt.x - r_, pt.y), pcbnew.VECTOR2I(pt.x, pt.y + r_), pcbnew.VECTOR2I(pt.x, pt.y - r_)]
        if not any(z.Outline().Contains(q) for z in zones for q in probe):
            continue
        stubs = [t for t in board.Tracks() if t.GetClass() == "PCB_TRACK" and (t.GetStart() == pt or t.GetEnd() == pt)]
        pad = None
        for t in stubs:
            far = t.GetEnd() if t.GetStart() == pt else t.GetStart()
            for fp in board.Footprints():
                for p in fp.Pads():
                    if p.GetPosition() == far and p.GetNetname() == v.GetNetname():
                        pad = p
        for t in stubs:
            board.Remove(t)
        board.Remove(v)
        if pad is not None and via_for_pad(board, pad, outline) is not None:
            moved += 1
    return moved


def stitch_stranded_pads(board, outline):
    """Post-route: every bottom GND pad the router's tracks cut off from the main pour gets a
    via beside it (anywhere free, not only inside its sliver) into the In1 plane."""
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pads = stranded_gnd_pads(board)
    n, miss = 0, []
    for pad in pads:
        v = via_for_pad(board, pad, outline, via_d=0.4, drill=0.2, track_w=0.2)
        if v is None:
            miss.append(f"{pad.GetParentFootprint().GetReference()}.{pad.GetNumber()}")
        else:
            n += 1
    filler.Fill(board.Zones())
    return n, miss


def gnd_pad_vias(board, outline, net_name="GND"):
    """Every SMD GND pad gets its own via into the In1 plane before routing: top pads because
    Freerouting never connects to pours, bottom pads because the router's tracks later carve
    the bottom pour into slivers (a pad in a sliver would be stranded).  Top pads already on an
    F.Cu GND patch are skipped."""
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    fills = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() == net_name and z.GetLayer() == pcbnew.F_Cu]
    n, inpad = 0, 0
    for fp in board.Footprints():
        for pad in fp.Pads():
            if pad.GetNetname() != net_name or pad.GetDrillSize().x > 0:
                continue
            if not pad.IsFlipped() and any(z.GetFilledPolysList(pcbnew.F_Cu).Contains(pad.GetPosition()) for z in fills):
                continue
            if pad.IsFlipped():
                v = via_for_pad(board, pad, outline, via_d=0.4, drill=0.2, track_w=0.2, clearance=0.1)
            else:
                v = via_for_pad(board, pad, outline)
            if v is None:
                print(f"  no via spot for {fp.GetReference()} pad {pad.GetNumber()}")
            else:
                n += 1
                if v.GetPosition() == pad.GetPosition():
                    inpad += 1
    filler.Fill(board.Zones())
    return n, inpad


def islands(board, zone, layer):
    """Filled outlines of ``zone`` on ``layer`` sorted by area, largest first."""
    polys = zone.GetFilledPolysList(layer)
    out = []
    for i in range(polys.OutlineCount()):
        o = polys.Outline(i)
        out.append((o.Area() / 1e12, o))
    out.sort(key=lambda t: -t[0])
    return out


def stitch_gnd_islands(board, outline_pts=None, net_name="GND", layer=None, via_d=0.4, drill=0.2):
    """After a fill, give every island of the bottom GND pour (except the main one) a via into
    the In1 plane so the pads it holds are connected.  Candidate points are sampled on a grid
    inside the island and must clear every pad / track / via on every layer.  Returns
    (vias added, islands left without a via)."""
    layer = B if layer is None else layer
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    net = board.GetNetsByName()[net_name]
    added, missed = 0, 0
    for z in board.Zones():
        if not hasattr(z, "GetIsRuleArea") or z.GetIsRuleArea() or z.GetNetname() != net_name or z.GetLayer() != layer:
            continue
        isl = islands(board, z, layer)
        for area, outline in isl[1:]:
            if area < 0.3:
                continue
            bb = outline.BBox()
            x0, y0, x1, y1 = (pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
            best = None
            y = y0 + 0.3
            while y < y1 and best is None:
                x = x0 + 0.3
                while x < x1:
                    pt = pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
                    if outline.PointInside(pt) and outline.Distance(pt) >= pcbnew.FromMM(via_d / 2 + 0.05) \
                            and free_spot(board, x, y, via_d, 0.1, net=net_name, outline=outline_pts):
                        best = (x, y)
                        break
                    x += 0.15
                y += 0.15
            if best is None:
                missed += 1
                continue
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(best[0]), pcbnew.FromMM(best[1])))
            v.SetDrill(pcbnew.FromMM(drill)); v.SetWidth(pcbnew.FromMM(via_d)); v.SetNet(net)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            board.Add(v)
            added += 1
    if added:
        filler.Fill(board.Zones())
    return added, missed
