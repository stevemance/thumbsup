"""Placement and hand copper for the ThumbsUp v1 board.

Board frame (mech/board_outline.json): origin at the chassis back-left corner,
x to the right, y toward the drum (KiCad convention).  Outline: bay
104.5 x 37.5 with 16.5 mm chamfers at the back corners and 9.5 mm notches at
the front corners, plus the 46.5 x 13.5 neck (x 33..79.5, y 37.5..51/52).

Floorplan (top side)
  * Pico W vertical at x 59.5..80.5, y 0..51: micro-USB at the back-wall edge
    (mates through a slot in the printed wall), antenna toward the drum so its
    10 mm RF keep-out is off-board.
  * J1 XT30 at the back-wall edge (x 19..34) - the SPARC disconnect, also
    through a wall slot.
  * L cell FETs mid-left, R cell FETs right, W cell FETs in the neck; bulk cans
    next to each block; motor holes in the bottom band.
Bottom side (<= 2.5 mm under the 3 mm standoffs): every AT32/driver/INA180
group under its FET block, INA226s at their shunts, IMUs, flash, LDOs, buck
(inductor is 2 mm), passives.  ``check()`` enforces outline, courtyard overlap
and the Pico keep-outs; DRC does the rest.
"""

from __future__ import annotations

import pcbnew

from board import Board

TOP, BOT = False, True


# ---------------------------------------------------------------- helpers
def bbox(fp):
    bb = fp.GetBoundingBox(False, False)
    return (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))


def courtyard(fp):
    """Axis-aligned bbox of the footprint's courtyard polygon (GetLayerBoundingBox does not
    follow rotation for asymmetric footprints)."""
    layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    fp.BuildCourtyardCaches()
    poly = fp.GetCourtyard(layer)
    if poly.OutlineCount() == 0:
        return bbox(fp)
    bb = poly.BBox()
    return (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))


def overlaps(a, b, gap=0.0):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xi:
                inside = not inside
    return inside


def pack_row(b: Board, refs, x0, y, rot=0, back=False, gap=0.3):
    """Place parts left-to-right from x0 (top-left of the row at (x0, y)) using their
    real courtyard sizes."""
    x = x0
    for ref in refs:
        if ref not in b.fps:
            continue
        fp = b.place(ref, 0, 0, rot, back)
        cb = courtyard(fp)
        b.place(ref, x - cb[0], y - cb[1], rot, back)
        x += (cb[2] - cb[0]) + gap
    return x


def pack_grid(b: Board, refs, x0, y0, width, rot=0, back=False, gap=0.3):
    """Fill rows of at most ``width`` mm starting at the top-left (x0, y0); returns the
    bottom y."""
    x, y, rh = x0, y0, 0.0
    for ref in refs:
        if ref not in b.fps:
            continue
        fp = b.place(ref, 0, 0, rot, back)
        cb = courtyard(fp)
        w, h = cb[2] - cb[0], cb[3] - cb[1]
        if x + w > x0 + width and x > x0:
            x, y, rh = x0, y + rh + gap, 0.0
        b.place(ref, x - cb[0], y - cb[1], rot, back)
        x += w + gap
        rh = max(rh, h)
    return y + rh


class Packer:
    """Row packer over named regions (x, y, w, h) on one side of the board.  The fill
    cursor persists across calls so several groups can share a region; through-hole
    pads of every footprint and the courtyards of already-placed same-side parts are
    obstacles the packer steps around."""

    def __init__(self, b: Board, regions: dict, back=True, gap=0.3, row_gap=None, fixed=(), extra=()):
        self.b, self.regions, self.back, self.gap = b, regions, back, gap
        self.row_gap = gap if row_gap is None else row_gap   # >= 0.4 leaves a via channel between rows
        self.state = {k: [r[0], r[1], 0.0] for k, r in regions.items()}  # x, y, row height
        self.obstacles = []
        for ref, fp in b.fps.items():
            for pad in fp.Pads():
                if pad.GetDrillSize().x > 0:
                    bb = pad.GetBoundingBox()
                    self.obstacles.append((pcbnew.ToMM(bb.GetLeft()) - 0.35, pcbnew.ToMM(bb.GetTop()) - 0.35, pcbnew.ToMM(bb.GetRight()) + 0.35, pcbnew.ToMM(bb.GetBottom()) + 0.35))
        for ref in fixed:
            self.obstacles.append(courtyard(b.fps[ref]))
        self.obstacles += list(extra)

    def _blocked(self, rect):
        for ob in self.obstacles:
            if overlaps(rect, ob, 0.0):
                return ob
        return None

    def add(self, refs, keys):
        todo = [r for r in refs if r.split("@")[0] in self.b.fps]
        for key in keys:
            x0, y0, w, h = self.regions[key]
            st = self.state[key]
            rest = []
            for item in todo:
                ref, _, rot = item.partition("@")
                rot = float(rot or 0)
                fp = self.b.place(ref, 0, 0, rot, self.back)
                cb = courtyard(fp)
                pw, ph = cb[2] - cb[0], cb[3] - cb[1]
                if pw > w or ph > h:
                    rest.append(item)
                    continue
                placed = False
                while not placed:
                    if st[0] + pw > x0 + w:
                        if st[0] == x0:
                            break
                        st[0], st[1], st[2] = x0, st[1] + st[2] + self.row_gap, 0.0
                    if st[1] + ph > y0 + h:
                        break
                    ob = self._blocked((st[0], st[1], st[0] + pw, st[1] + ph))
                    if ob is None:
                        placed = True
                    else:
                        st[0] = ob[2] + self.gap
                        if st[0] + pw > x0 + w:
                            if st[2] == 0.0:  # empty row blocked to its end: step the row down
                                st[0], st[1] = x0, st[1] + 0.5
                            else:
                                st[0], st[1], st[2] = x0, st[1] + st[2] + self.row_gap, 0.0
                if not placed:
                    rest.append(item)
                    continue
                self.b.place(ref, st[0] - cb[0], st[1] - cb[1], rot, self.back)
                self.obstacles.append(courtyard(self.b.fps[ref]))
                st[0] += pw + self.gap
                st[2] = max(st[2], ph)
            todo = rest
            if not todo:
                break
        return todo


# ---------------------------------------------------------------- blocks
def fet_block(b: Board, base: int, cols, y_top, flip=False):
    """Three half-bridge columns on 5.9 mm pitch (courtyards touching) with the motor
    holes between the rows.  Normal (rot 90): tab (drain) toward -y.  Top row = high
    FETs (tab = VBAT at the top edge, leads = phase), holes row (phase), bottom row = low
    FETs (tab = phase, leads = I_x+ at the bottom edge).  ``flip`` mirrors it (rot 270):
    I_x+ at the top edge, VBAT at the bottom edge.  ``y_top`` is the block's top
    courtyard edge.  Rows are 9.6 apart: the 3.0 mm hole pads sit 0.3 mm from both FET
    bodies (all three are the phase net).  Block = 17.7 x 17.0.  Returns (y_hi, y_hole, y_lo)."""
    u = base // 10
    rot = 270 if flip else 90
    y_a = y_top + (3.6 if flip else 3.8)     # first row centre (tab side is 3.8, lead side 3.6)
    y_b = y_a + 9.6
    y_hole = y_a + 4.8
    hi_row, lo_row = (y_b, y_a) if flip else (y_a, y_b)
    for i, x in enumerate(cols):
        b.place(f"Q{u + i * 2}", x, hi_row, rot)
        b.place(f"Q{u + i * 2 + 1}", x, lo_row, rot)
    b.place(f"J{u + 1}", cols[1], y_hole, 0)
    return hi_row, y_hole, lo_row


SHUNTS = []   # (shunt, tie_a, tie_b) for copper()


def shunt_with_ties(b: Board, ref: str, nt_a: str, nt_b: str, x, y, rot, back=False):
    """Shunt plus its two Kelvin net-ties in the 1.3 mm pad gap: tie A on one side of
    the gap's centre line, tie B on the other, pads across the gap.  Tie pad 1 (force
    net) sits 0.8 mm from the centre line so copper() can stub it into the shunt pad;
    tie pad 2 (sense) faces outward and its trace leaves sideways."""
    b.place(ref, x, y, rot, back)
    p1 = b.pad_pos(ref, "1")
    p2 = b.pad_pos(ref, "2")
    m = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    ux, uy = (p2[0] - p1[0]) / 4.4, (p2[1] - p1[1]) / 4.4   # unit vector along the shunt
    wx, wy = -uy, ux                                        # across it
    for nt, sgn in ((nt_a, -1.0), (nt_b, 1.0)):
        cx, cy = m[0] + sgn * 1.2 * wx, m[1] + sgn * 1.2 * wy
        best = None
        for r in (0, 90, 180, 270):
            b.place(nt, cx, cy, r, back)
            q = b.pad_pos(nt, "1")
            d = (q[0] - m[0]) ** 2 + (q[1] - m[1]) ** 2
            if best is None or d < best[0]:
                best = (d, r)
        b.place(nt, cx, cy, best[1], back)
    SHUNTS.append((ref, nt_a, nt_b))


def cell_ics(b: Board, base: int, x, y):
    """Bottom: AT32, driver, INA180 in a row starting at (x, y) (top-left)."""
    u = base // 10
    return pack_row(b, [f"U{u}", f"U{u + 1}", f"U{u + 2}"], x, y, 0, BOT, gap=0.8)


def cell_passives(b: Board, base: int, x, y, width):
    """Bottom: the cell's passives, packed into rows of ``width`` from (x, y)."""
    u = base // 10
    refs = ([f"C{base + n}" for n in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)] + [f"R{base}", f"R{base + 1}", f"R{base + 2}", f"R{base + 3}", f"R{base + 4}"]
            + [f"D{u}", f"D{u + 1}", f"D{u + 2}", f"R{base + 32}", f"R{base + 33}", f"R{base + 34}", f"C{base + 20}", f"C{base + 21}", f"C{base + 22}"]
            + [f"R{base + 20 + i}" for i in range(12)] + [f"R{base + 5 + i}" for i in range(9)])
    return pack_grid(b, refs, x, y, width, 0, BOT)


# ---------------------------------------------------------------- floorplan
BLOCKS = {}   # cell base -> dict(cols, y_hi, y_hole, y_lo, flip) for copper()


def place_all(b: Board, mech: dict):
    # ---- Pico W: vertical, USB (footprint -y) at the back wall, antenna (+y) toward the drum
    b.place("A1", 67.7, 25.4, 0)   # courtyard x 56.11..79.28, module y -0.1..50.9, RF keep-out y >= 50.4 off-board
    for z in b.fps["A1"].Zones():
        if "USB" in z.GetZoneName() or "Suggestion" in z.GetZoneName():
            z.SetDoNotAllowFootprints(False); z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False)
            z.SetDoNotAllowPads(False); z.SetDoNotAllowZoneFills(False)
            z.SetZoneName(z.GetZoneName() + " (disabled)")
        elif "RF" in z.GetZoneName():
            z.SetDoNotAllowPads(False)   # the footprint's own paste-only pads sit inside it

    # ---- top side: power ------------------------------------------------------
    b.place("J1", 26.3, 13.6, 0)                          # XT30 x 16.6..31, y 0..15.9 (courtyard is -9.7/+4.7), mates at y=0 through the wall slot
    shunt_with_ties(b, "R2", "NT1", "NT2", 23.8, 8.5, 0, BOT)           # pack shunt under J1 between its pegs and pins
    W_COLS, L_COLS, R_COLS = [15.55, 21.45, 27.35], [38.75, 44.65, 50.55], [82.55, 88.45, 94.35]
    hi, ho, lo = fet_block(b, 400, W_COLS, 17.5)                        # W: x 12.6..30.3, y 17.5..34.5, VBAT at the top (fed from under J1)
    BLOCKS[400] = dict(cols=W_COLS, y_hi=hi, y_hole=ho, y_lo=lo, flip=False)
    shunt_with_ties(b, "R435", "NT40", "NT41", 32.9, 31.5, 90)          # x 30.45..35.35, y 27.35..35.65: I_W+ from the W low leads
    b.place("C225", 37.9, 5.6)                            # L can x 31.2..44.6, y 0.1..11.1 (VBAT)
    b.place("C425", 50.5, 6.8, 90)                        # W can x 45..56, y 0.1..13.5 (VBAT, same pour)
    hi, ho, lo = fet_block(b, 200, L_COLS, 13.6)                        # L: x 35.8..53.5, y 13.6..30.6, VBAT at the top next to the cans
    BLOCKS[200] = dict(cols=L_COLS, y_hi=hi, y_hole=ho, y_lo=lo, flip=False)
    b.place("C223", 54.9, 15.2, 90, BOT)                  # L drain MLCCs under the strip between the L block and the Pico
    b.place("C224", 54.9, 20.0, 270, BOT)                 # VBAT pads of C223/C224 face each other (shared via)
    shunt_with_ties(b, "R235", "NT20", "NT21", 50.4, 33.5, 0)           # x 46.3..54.5, y 31.1..35.9: I_L+ pad (46.65..49.75) under column 3's leads, GND pad at the right
    hi, ho, lo = fet_block(b, 300, R_COLS, 9.3, flip=True)              # R: x 79.6..97.3, y 9.3..26.3 (chamfer x <= 88 + y), I_R+ at the top, VBAT at the bottom
    BLOCKS[300] = dict(cols=R_COLS, y_hi=hi, y_hole=ho, y_lo=lo, flip=True)
    shunt_with_ties(b, "R335", "NT30", "NT31", 84.5, 4.4, 0)            # x 80.4..88.6, y 2..6.8: I_R+ from the R low leads
    b.place("C325", 86.3, 31.9)                           # R can x 79.6..93, y 26.4..37.45 (VBAT, next to the R high tabs)
    b.place("C323", 83.1, 25.2, 0, BOT)                   # R drain MLCCs under the high (bottom) row
    b.place("C324", 94.2, 25.2, 180, BOT)                 # VBAT pad outboard (via at x 96.9)
    b.place("C423", 15.6, 19.3, 0, BOT)                   # W drain MLCCs under the high (top) row
    b.place("C424", 27.3, 19.3, 0, BOT)

    # ---- top side: connectors, small stuff ---------------------------------------
    b.place("SW1", 12.6, 13.0)                            # reset, x 8.8..16.4, y 10.15..15.85
    b.place("J2", 4.9, 24.8, 270)                         # ARM link x 0.6..6.7, y 23..26.6
    b.place("D5", 9.6, 17.9)                              # status LEDs at the left edge (x 6.75..12.45), visible past the W block
    b.place("D6", 9.6, 22.9)
    b.place("D4", 10.6, 26.15)
    for ref, (x, y) in zip(("TP1", "TP2", "TP3"), ((13.6, 5.6), (10.8, 8.4), (5.2, 14.0))):
        b.place(ref, x, y)                                # rail test points along the chamfer (x + y >= 19.1 clears it)
    pack_row(b, ["TP200", "TP201", "TP202", "TP203"], 35.4, 32.9, 0, TOP, 0.15)  # x 35.4..46.3, y 32.9..35.5 (I_L+ pour ends at 33.0)
    b.place("J3", 35.2, 42.0, 90)                         # expansion 2x6 in the neck x 33.4..49.7, y 37.6..43.8 (<= 8 mm tall parts there)
    b.place("J20", 36.8, 46.2)                            # SWD pads
    b.place("J30", 44.1, 46.2)
    b.place("TP4", 54.7, 38.9)                            # between J3 and the Pico
    b.place("TP5", 54.7, 41.6)
    for ref, y in zip(("R24", "R25", "R26", "C24", "C82"), (38.4, 39.7, 41.0, 42.3, 43.6)):
        b.place(ref, 51.9, y)                             # DShot series R, NTC ADC cap, 5 V cap: top side beside the Pico
    b.place("C83", 101.5, 16.6)                           # top right notch, above H2 (5 V decoupling)
    for ref, y in zip(("C23", "C25", "R20", "R21", "R22", "R23"), (27.9, 29.15, 30.4, 31.65, 32.9, 34.15)):
        b.place(ref, 11.0, y)                             # Pico-side RC / I2C pull-ups: top strip left of the W block
    b.place("J40", 36.8, 49.0)
    b.place("TP6", 41.7, 49.0)
    b.place("TP40", 44.5, 49.0)
    b.place("TP10", 102.5, 25.4)

    # ---- bottom side ----------------------------------------------------------
    cell_ics(b, 400, 12.9, 27.95)     # W ICs under the W low row (x 12.9..30.25, y 27.95..34.3; gate vias at y 34.62)
    cell_ics(b, 200, 36.0, 13.8)      # L ICs under the L high row (y 13.8..20.15, holes from 20.35)
    pack_row(b, ["U31", "U32"], 80.0, 9.65, 0, BOT, gap=0.8)   # R driver + INA180 under the R low (top) row, below the gate vias (y 9.18)
    b.place("U30", 88.65, 22.9, 0, BOT)                          # R AT32 under the R high row between the drain MLCCs
    from copper import reserved_rects
    reserved = reserved_rects(b, BLOCKS)
    regions = {
        "j1a": (17.0, 0.6, 13.8, 5.2),          # under J1, wall side of the pegs (VBAT_PACK pour weaves around)
        "j1b": (17.0, 11.0, 11.3, 4.9),         # under J1's pins row (x > 28.3 is the VBAT neck)
        "topleft": (7.2, 9.6, 9.6, 4.8),        # under SW1
        "left": (3.0, 14.5, 9.0, 12.3),         # left edge: H1, J2 are obstacles
        "wA": (12.6, 18.4, 17.7, 5.7),          # under the W high row (drain MLCCs fixed)
        "wB": (12.6, 34.9, 17.7, 2.4),          # under the W low row below the W ICs
        "wH": (12.6, 24.3, 17.7, 3.6),          # between the W motor holes
        "lH": (35.8, 20.3, 17.7, 3.9),          # between the L motor holes
        "rH": (79.6, 15.9, 17.7, 3.8),          # between the R motor holes
        "mid": (30.5, 13.5, 5.1, 23.8),         # strip between the W and L blocks (VBAT vias above y 13)
        "lcan": (36.3, 0.6, 12.0, 10.5),        # under the L can (VBAT vias at x 31..36)
        "wcan": (48.5, 0.6, 7.5, 12.7),         # under the W can
        "pstrip": (53.6, 13.5, 3.9, 16.2),      # strip under the L block / Pico gap (C223/C224 fixed)
        "l2": (35.8, 24.3, 17.7, 8.0),          # under the L low row
        "lfront": (35.8, 32.5, 15.7, 4.8),      # under R235 / the L TPs
        "usbl": (57.4, 0.5, 6.3, 4.4),          # under the Pico beside the USB pegs
        "usbr": (71.7, 0.5, 6.3, 4.4),
        "pico": (57.4, 5.7, 20.8, 24.0),        # under the Pico, above its debug holes (VBAT bus is on In2)
        "picoside": (57.4, 29.7, 9.8, 2.4),
        "pico2": (57.4, 32.2, 20.8, 5.1),       # below the debug holes
        "r1b": (79.6, 14.3, 9.0, 1.55),         # under the R low row below the driver / INA180
        "r1r": (88.8, 9.7, 8.5, 6.1),           # under the R low row right of the driver / INA180
        "rtop": (79.6, 0.6, 8.6, 8.6),          # under R335 / the R I+ strip, left of the chamfer
        "rtop2": (88.4, 5.5, 4.5, 3.7),
        "r2": (79.6, 19.8, 17.7, 4.2),          # under the R high row above the drain MLCCs
        "rcan": (79.6, 26.5, 13.4, 3.4),        # under the R can, above its VBAT via field (y 30..34)
        "rright": (98.6, 16.5, 5.7, 10.3),      # right notch (H2 is an obstacle)
        "neck": (33.2, 37.7, 27.3, 12.5),       # under the neck up to the Pico antenna keep-out (J3 pins, H3 are obstacles)
        "pneck": (75.0, 37.5, 4.2, 12.7),       # under the Pico's right pad column beside the antenna keep-out
    }
    pk = Packer(b, regions, gap=0.25, fixed=["U40", "U41", "U42", "U20", "U21", "U22", "U30", "U31", "U32", "C323", "C324", "C423", "C424", "C223", "C224", "R2", "NT1", "NT2"], extra=reserved)
    rest = []
    rest += pk.add(["D1", "C1", "C2", "C5", "Q1", "D2", "R1", "C3"], ["j1a", "j1b", "topleft", "left"])    # pack entry, RPP
    rest += pk.add(["U4", "R30", "R31", "C30", "C31"], ["j1b", "topleft", "left", "wcan", "lcan", "pico"])  # pack INA226 at R2
    rest += pk.add(["U7@90", "R60", "R61", "C60", "C61"], ["mid", "neck"])                                 # weapon INA226 at R435
    rest += pk.add(["U5", "R40", "R41", "C40", "C41"], ["lfront", "l2", "pstrip", "pico"])                 # drive-L INA226 at R235
    rest += pk.add(["U6", "R50", "R51", "C50", "C51"], ["rtop", "r1r", "rcan", "pico"])                    # drive-R INA226 at R335
    rest += pk.add(["Q46", "R440", "R441", "Q47", "Q48", "R442", "R443", "R444", "Q49", "Q50", "TH1"], ["wA", "wB", "mid", "neck"])  # weapon VCC switch / enable / reset hold, NTC at the W FETs
    L = [f"C{200 + n}" for n in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)] + [f"R{200 + n}" for n in (0, 1, 2, 3, 4, 32, 33, 34)] + ["D20", "D21", "D22", "C220", "C221", "C222"] + [f"R{220 + i}" for i in range(12)] + [f"R{205 + i}" for i in range(9)]
    R = [f"C{300 + n}" for n in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)] + [f"R{300 + n}" for n in (0, 1, 2, 3, 4, 32, 33, 34)] + ["D30", "D31", "D32", "C320", "C321", "C322"] + [f"R{320 + i}" for i in range(12)] + [f"R{305 + i}" for i in range(9)]
    W = [f"C{400 + n}" for n in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)] + [f"R{400 + n}" for n in (0, 1, 2, 3, 4, 32, 33, 34)] + ["D40", "D41", "D42", "C420", "C421", "C422"] + [f"R{420 + i}" for i in range(12)] + [f"R{405 + i}" for i in range(9)]
    rest += pk.add(W, ["wA", "wB", "wH", "mid", "topleft", "left", "neck", "lcan"])
    rest += pk.add(L, ["l2", "lH", "lcan", "lfront", "pstrip", "wcan", "mid", "neck", "pneck"])
    rest += pk.add(R, ["r2", "r1r", "r1b", "rH", "rcan", "rtop", "rtop2", "rright", "pico2", "pico"])
    rest += pk.add(["U8", "C70", "C71", "U9", "C72", "C73"], ["neck", "pico"])                              # IMU / shock sensor
    rest += pk.add(["U10", "C80", "R80", "R81", "R82"], ["pico", "neck"])                                   # flash
    misc = ["U1", "L1", "C10", "C11", "C12", "C13", "C14", "C15", "R10", "R11", "D3", "U2", "C16", "C17", "U3", "C18", "C19", "R12", "R13", "C20", "R14", "R15", "C21", "R16",
            "U11", "C81", "R83"]
    rest += pk.add(misc, ["pico", "pico2", "picoside", "usbl", "usbr", "wcan", "pstrip", "neck", "lcan", "left", "topleft", "rright", "rcan", "r1r", "r1b", "mid", "lH", "wH", "rH", "pneck"])
    for k, st in pk.state.items():
        print(f"  region {k:8} filled to y={st[1] + st[2]:.1f} of {regions[k][1] + regions[k][3]:.1f}")
    rest = sorted({r.split("@")[0] for r in rest if b.fps[r.split("@")[0]].GetPosition() == pcbnew.VECTOR2I(0, 0)})
    if rest:
        print("UNPLACED (bottom overflow):", rest)


# ---------------------------------------------------------------- checks
def check(b: Board, mech: dict) -> list[str]:
    poly = mech["outline"]
    problems = []
    boxes = {}
    for ref, fp in b.fps.items():
        cb = courtyard(fp)
        boxes[ref] = (cb, fp.IsFlipped())
        corners = ((cb[0], cb[1]), (cb[2], cb[1]), (cb[0], cb[3]), (cb[2], cb[3]))
        if ref == "A1":
            corners = ((cb[0], 0.3), (cb[2], 0.3), (cb[0], 50.7), (cb[2], 50.7))
        for x, y in corners:
            x = min(max(x, cb[0] + 0.05), cb[2] - 0.05)
            y = min(max(y, cb[1] + 0.05), cb[3] - 0.05)
            if not point_in_poly(x, y, poly):
                problems.append(f"{ref} corner ({x:.1f},{y:.1f}) outside the outline")
                break
    refs = list(boxes)
    for i in range(len(refs)):
        for j in range(i + 1, len(refs)):
            (a, fa), (c, fc) = boxes[refs[i]], boxes[refs[j]]
            if fa == fc and overlaps(a, c, 0.0):
                if refs[i].startswith("NT") or refs[j].startswith("NT"):
                    continue  # net-ties sit in the shunt pad gap by design
                if {refs[i], refs[j]} & {"J21", "J31", "J41"} and (refs[i][0] == "Q" or refs[j][0] == "Q"):
                    continue  # motor holes sit between the FET rows by design (no courtyard)
                problems.append(f"overlap {refs[i]} {refs[j]}")
    # through-hole pads and NPTH holes block both sides
    blockers = []
    for ref, fp in b.fps.items():
        for pad in fp.Pads():
            if pad.GetDrillSize().x > 0:
                bb = pad.GetBoundingBox()
                blockers.append((ref, (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))))
    for ref, (cb, _) in boxes.items():
        for oref, hb in blockers:
            if oref != ref and overlaps(cb, hb, 0.1) and not ref.startswith("NT") and not (ref[0] == "Q" and oref in ("J21", "J31", "J41")):
                problems.append(f"{ref} courtyard over a hole of {oref}")
                break
    for z in b.fps["A1"].Zones():
        if ("RF" in z.GetZoneName() or "Antenna" in z.GetZoneName()) and "disabled" not in z.GetZoneName():
            zb = z.GetBoundingBox()
            zr = (pcbnew.ToMM(zb.GetLeft()), pcbnew.ToMM(zb.GetTop()), pcbnew.ToMM(zb.GetRight()), pcbnew.ToMM(zb.GetBottom()))
            for ref, (cb, _) in boxes.items():
                if ref != "A1" and overlaps(cb, zr):
                    problems.append(f"{ref} inside Pico keep-out {z.GetZoneName()}")
    for ref in ("C225", "C325", "C425", "J1", "SW1", "J2"):   # > 8 mm tall: not under the drum (neck, y > 37.5)
        if ref in boxes and boxes[ref][0][3] > 37.5:
            problems.append(f"{ref} is tall and sits under the drum")
    return problems
