"""v2 drive-IC fan-out (P3 pre-route): the U3 / U4 (DRV8316) nets that are not pours, on top of the bridge pre-route.
Experiment module for tail.py:

    cd kicad/gen && TAIL_EXP=v2_drive TAIL_BASE=<abs>/kicad/gen/out/exp/v2_bridge/proj/motor_board.kicad_pcb /usr/bin/python3 tail.py

Layers: F.Cu = L1, In1.Cu = L2 (GND plane, untouched), In2.Cu = L3, B.Cu = L4.  Board-local mm, y toward the rear.
Keep-outs honoured (memo 3.1): no L3/L4 tracks in the front band (y < 18.5); no L3 in the U3/U4 islands (exposed pad
+ 1.5 mm); no L4 in the thermal-via fields (exposed pad + 0.5 mm).  L3 lanes have L4 free above them and the L4 CSA
runs have L3 free below them (no stacked parallel signals), except short orthogonal crossings.

Channels: U3 -> MCU behind U4 (L4: L_SOA/B/C; L3: +3V3, L_INHA, L_INHB) and behind the JR pads (L3: L_nCS, L_INHC,
L_nFAULT; L4: SCK, MISO, MOSI, DRV_OFF).  U4's east pins run straight to the MCU's west pins on L1 (INHA, nFAULT,
DRV_OFF via TP8); INHB / INHC on L3 under the MCU to vias under the body.

Exceptions to record: vias inside the L3 islands (L_CP 8.55,21.24; L_CPL 9.8,21.24; R_CPH 19.44,23.6; +3V3 at
7.75/10.25/11.25/12.25, 27.4) - fr_trial's island rule areas ban vias and must be carved round these; POFV in U1.42
(L_SOB_F) and U1.45 (DRV_OFF, for R50).

NOT routed here (placement): U4's front pins (R_SOA/B/C, R_nCS, SPI at U4, R_SWBK, R_FBBK), U3's buck nets to R300
(L_SWBK, L_FBBK incl. C307), SPI at U7, R_AVDD between the pin-37/C406 group and pin 25 / C405 and R401.2.
"""
L, R = "/drive_left/", "/drive_right/"
NET = {n: L + n for n in ("L_CP", "L_CPH", "L_CPL", "L_AVDD", "L_FBBK", "L_SWBK")}
NET.update({n: R + n for n in ("R_CP", "R_CPH", "R_CPL", "R_AVDD", "R_FBBK", "R_SWBK")})
NET.update({f"{s}_SO{p}_F": f"/mcu/{s}_SO{p}_F" for s in "LR" for p in "ABC"})


def n_(net):
    return NET.get(net, net)


F1, L3, L4 = "F.Cu", "In2.Cu", "B.Cu"
PV = dict(d=0.4, drill=0.2)             # signal via
RV = dict(d=0.45, drill=0.25)           # rail via (+3V3, GND stitch)

# ---------------------------------------------------------------- keep-outs for router requests
EP_U3, EP_U4 = (6.65, 22.45, 12.35, 26.15), (20.65, 20.65, 24.35, 26.35)


def grow(b, d):
    return (b[0] - d, b[1] - d, b[2] + d, b[3] + d)


ISL_U3, ISL_U4 = grow(EP_U3, 1.5), grow(EP_U4, 1.5)
FLD_U3, FLD_U4 = grow(EP_U3, 0.5), grow(EP_U4, 0.5)
M = 0.1                                 # the router keeps the centreline out of a box: grow by ~w/2
BAND = [(0, 0, 14.0, 18.5), (27.0, 0, 85, 18.5), (14.0, 0, 27.0, 16.3)]   # L3 VBAT edge y 16.0 for x 14-27 (+0.3)
AVOID = [[ly, *grow(b, M)] for ly in (L3, L4) for b in BAND] + [
    [L3, *grow(ISL_U3, M)], [L3, *grow(ISL_U4, M)], [L4, *grow(FLD_U3, M)], [L4, *grow(FLD_U4, M)]]

EDITS = []


def tr(net, layer, pts, w=0.15):
    EDITS.append(dict(op="track", net=n_(net), layer=layer, pts=pts, w=w))


def via(net, c, v=PV):
    EDITS.append(dict(op="via", net=n_(net), c=c, **v))


def route(net, a, b, layers, **kw):
    kw.setdefault("avoid", [])
    kw["avoid"] = AVOID + kw["avoid"]
    kw.setdefault("via_cost", 3.0)
    EDITS.append(dict(op="route", net=n_(net), a=a, b=b, layers=layers, **kw))


# ================================================================ U3 front row (pins 3..12 face the power band)
# Pins (y 21.9): 12 GND 6.75 | 11-9 VM | 8 CP 8.75 | 7 CPH 9.25 | 6 CPL 9.75 | 5 SWBK 10.25 | 4 GND | 3 FBBK 11.25 | 2 GND
# The VM / CP caps form a wall (C301, C300, C303, C302) with three L1 gaps: B (x 9.0, between the C300/C303 pads),
# C (x 10.55, C300.2 | C302.1) and the strip under C302 to the east.  C304 (the flying cap) is rotated so CPH / CPL
# cross; the charge pump therefore takes two vias in front of the pins (inside the L3 island, 1.2 mm from the pad).
# CPH: L1 through gap B to C304.1.
tr("L_CPH", F1, [(9.25, 21.9), (9.25, 21.35), (9.12, 21.22), (9.12, 19.95), (9.0, 19.83), (9.0, 18.1), (9.3, 17.8),
                 (9.525, 16.9)])
# CP: via in front of pin 8, L4 to a via between C303.1 and C300.1, L1 into C303.1.
tr("L_CP", F1, [(8.75, 21.9), (8.75, 21.44), (8.55, 21.24)])
via("L_CP", (8.55, 21.24))
tr("L_CP", L4, [(8.55, 21.24), (8.225, 20.915), (8.225, 19.55)])
via("L_CP", (8.225, 19.55))
tr("L_CP", F1, [(8.225, 19.55), (8.225, 18.65)])
# CPL: via in front of pin 6, L4 round CP's hop to a via in gap A (C301 | C303.1), L1 up gap A into C304.2.
tr("L_CPL", F1, [(9.75, 21.9), (9.8, 21.24)])
via("L_CPL", (9.8, 21.24))
tr("L_CPL", L4, [(9.8, 21.24), (9.2, 20.64), (9.2, 19.1), (9.0, 18.9), (7.575, 18.9), (7.375, 18.7)])
via("L_CPL", (7.375, 18.7))
tr("L_CPL", F1, [(7.375, 18.7), (7.375, 17.5), (7.975, 16.9)])
# C300.2 (VM cap GND) is boxed in by CPH / gap C: its own stitch via in the channel under C303.2
via("GND", (9.775, 19.525), RV)
tr("GND", F1, [(9.775, 19.525), (9.775, 20.4)], 0.25)
# GND pins to the exposed pad (short L1 stubs; the pad's thermal vias take them to L2)
for x_, y_, x2, y2 in ((6.75, 21.9, 6.75, 22.7), (10.75, 21.9, 10.75, 22.7), (11.75, 21.9, 11.75, 22.7),
                       (9.25, 26.7, 9.25, 25.9), (6.1, 23.55, 6.9, 23.55), (6.1, 25.05, 6.9, 25.05)):
    tr("GND", F1, [(x_, y_), (x2, y2)], 0.2)

# ================================================================ channels to the MCU (lanes, west ends)
# Behind U4 (between its L3 island, y <= 27.85, and the JR pads, y >= 30.225): the three left CSA outputs on L4
# (over L3 GND), then +3V3, INHA, INHB on L3 (under L4 GND fill).  Behind the JR pads (y 32.6-34.6): nCS, INHC,
# nFAULT, DRV_OFF on L3 and SCK / MISO / MOSI on L4 (not stacked over the L3 lanes).
XU4, XJR = 17.9, 17.9
LU4 = {"L_SOA": 27.95, "L_SOB": 28.23, "L_SOC": 28.51, "+3V3": 28.9, "L_INHA": 29.45, "L_INHB": 29.73}
LJR3 = {"L_nCS": 32.65, "L_INHC": 32.93, "L_nFAULT": 33.21}
LJR4 = {"SPI_SCK": 34.03, "SPI_MISO": 34.31, "SPI_MOSI": 34.59}
XU4E, XJRE = 25.0, 27.0                  # east ends of the explicit lanes (the router takes over from there)
for n, y in LU4.items():
    tr(n, L4 if n.startswith("L_SO") else L3, [(XU4, y), (XU4E, y)], 0.2 if n == "+3V3" else 0.15)
for n, y in LJR3.items():
    tr(n, L3, [(XJR, y), (XJRE, y)])
for n, y in LJR4.items():
    tr(n, L4, [(XJR, y), (XJRE, y)])

# ================================================================ U3 east side (pins 33-40 face the U3 | U4 gap)
# A staggered via field just outside the L3 island (x >= 14.05): column A x 14.25, column B x 15.45, 1.25 mm pitch
# in each column.  CSA outputs leave on L4 (east, then south at x 16.74-17.3 into the behind-U4 lanes, L3 below them
# is GND), the SPI and nCS on L4 (south at x 15.62-16.46 to the behind-JR lanes), AVDD on L3 to C306.
U3E = [("L_SOA", "40", (14.25, 22.3)), ("L_SOB", "39", (15.45, 22.95)), ("L_SOC", "38", (14.25, 23.55)),
       ("L_nCS", "36", (14.25, 24.8)), ("SPI_SCK", "35", (15.45, 25.45)),
       ("SPI_MOSI", "34", (14.25, 26.05)), ("SPI_MISO", "33", (15.45, 26.65))]
for n, p, c in U3E:
    via(n, c)
for n, p, c in U3E:
    route(n, ("pad", "U3", p), ("via", *c), [F1], margin=1.2, tol=0.02)
tr("L_SOA", L4, [(14.25, 22.3), (17.3, 22.3), (17.3, 27.95), (XU4, 27.95)])
tr("L_SOB", L4, [(15.45, 22.95), (17.02, 22.95), (17.02, 28.23), (XU4, 28.23)])
tr("L_SOC", L4, [(14.25, 23.55), (16.74, 23.55), (16.74, 28.51), (XU4, 28.51)])
tr("L_nCS", L4, [(14.25, 24.8), (16.46, 24.8), (16.46, 32.11), (16.65, 32.3)])
via("L_nCS", (16.65, 32.3))
tr("L_nCS", L3, [(16.65, 32.3), (17.0, 32.65), (XJR, 32.65)])
tr("SPI_SCK", L4, [(15.45, 25.45), (16.18, 25.45), (16.18, 33.75), (16.46, 34.03), (XJR, 34.03)])
tr("SPI_MISO", L4, [(15.45, 26.65), (15.9, 26.65), (15.9, 34.03), (16.18, 34.31), (XJR, 34.31)])
tr("SPI_MOSI", L4, [(14.25, 26.05), (14.85, 26.65), (14.85, 27.2), (15.62, 27.2), (15.62, 34.31), (15.9, 34.59),
                    (XJR, 34.59)])
# AVDD: pin 37 drops at its own tip (L3-island edge), L4 west of the via field to a via in the C306 | C404 gap (L1
# stub into C306.1), then L3 west to pin 25's group (C305, R301.2)
via("L_AVDD", (13.55, 24.05)); via("L_AVDD", (14.1, 27.35))
tr("L_AVDD", F1, [(12.9, 24.05), (13.55, 24.05)])
tr("L_AVDD", L4, [(13.55, 24.05), (13.5, 24.1), (13.5, 26.75), (14.1, 27.35)])
tr("L_AVDD", F1, [(14.1, 27.35), (13.5, 27.8)])

# ================================================================ U3 rear row (pins 21-32 face the rear / J2)
# The left sensor block (R301, R55/R56, C111, R111, R112, C47) sits on L4 right behind the row, so the vias go where
# L4 is free: +3V3 pins 23/28/30/32 straight behind the pins (L3 island edge, 1.25 mm from the pad; +3V3 joins on L4
# to C47.1 and a trunk via), the INH pins to three sites between the sensor parts, nFAULT at R301.1, AVDD at R301.2.
# From there on L3: INHA / INHB north-east into the behind-U4 lanes, INHC / nFAULT / DRV_OFF south under J2 into the
# behind-JR lanes.
QV = {"DRV_OFF": (5.6, 27.9), "L_nFAULT": (6.45, 27.95), "L_AVDD": (9.26, 28.2), "L_INHA": (9.3, 31.7),
      "L_INHB": (10.9, 30.2), "L_INHC": (10.9, 31.55)}
for n, c in QV.items():
    via(n, c)
V33 = [(7.75, 27.4), (10.25, 27.4), (11.25, 27.4), (12.25, 27.4)]
for c in V33 + [(15.15, 28.95)]:
    via("+3V3", c, RV)
for n, p in (("DRV_OFF", "21"), ("L_nFAULT", "22"), ("L_INHA", "27"), ("L_INHB", "29"), ("L_INHC", "31")):
    route(n, ("pad", "U3", p), ("via", *QV[n]), [F1], margin=1.5, tol=0.02)
for p, c in zip(("23", "28", "30", "32"), V33):
    tr("+3V3", F1, [(float({"23": 7.75, "28": 10.25, "30": 11.25, "32": 12.25}[p]), 26.7), c], 0.2)
tr("+3V3", L4, [(7.75, 27.4), (12.9, 27.4), (12.9, 28.68), (14.73, 28.68), (15.15, 28.95)], 0.2)
tr("+3V3", L4, [(14.73, 28.68), (14.73, 29.25)], 0.2)
tr("+3V3", L3, [(15.15, 28.95), (15.2, 28.9), (XU4, 28.9)], 0.2)
tr("L_nFAULT", L4, [(6.45, 27.95), (7.24, 28.2)])
# AVDD pin 25 straight into C305.1 (right behind the pin); its via at the pad's corner takes R301.2 on L4
tr("L_AVDD", F1, [(8.75, 26.7), (8.75, 27.9), (9.0, 28.15), (9.0, 28.88)])
tr("L_AVDD", F1, [(9.26, 28.2), (9.0, 28.3)])
tr("L_AVDD", L4, [(9.26, 28.2), (8.26, 28.2)])
tr("GND", F1, [(7.375, 28.88), (7.1, 29.3), (7.1, 30.5)], 0.25)          # C305.2 to J2's GND mounting pad
route("L_AVDD", ("via", 14.1, 27.35), ("via", 9.26, 28.2), [L3], margin=1.5, tol=0.02)
# L3 from the rear-row vias (explicit): south group straight down then east under J2 into the behind-JR lanes,
# north group up then east into the behind-U4 lanes (north of the INH vias, south of the +3V3 trunk via).
tr("DRV_OFF", L3, [QV["DRV_OFF"], (5.6, 33.2), (5.89, 33.49), (17.1, 33.49), (17.3, 33.62)])
# DRV_OFF must leave the behind-JR bundle northward first (to TP8), so it changes to L4 between the L3 lanes and the
# L4 SPI lanes, runs above them and turns north east of JR3 to a via under TP8.
via("DRV_OFF", (17.3, 33.62))
tr("DRV_OFF", L4, [(17.3, 33.62), (27.6, 33.62), (28.3, 32.92), (28.3, 31.4), (29.3, 30.4)])
via("DRV_OFF", (29.3, 30.4))
tr("DRV_OFF", F1, [(29.3, 30.4), (28.55, 29.65), (28.55, 28.0)])
tr("L_nFAULT", L3, [QV["L_nFAULT"], (6.45, 32.7), (6.96, 33.21), (XJR, 33.21)])
tr("L_INHC", L3, [QV["L_INHC"], (10.9, 32.65), (11.18, 32.93), (XJR, 32.93)])
tr("L_INHA", L3, [QV["L_INHA"], (9.3, 29.7), (9.55, 29.45), (XU4, 29.45)])
tr("L_INHB", L3, [QV["L_INHB"], (10.9, 30.0), (11.17, 29.73), (XU4, 29.73)])

# ================================================================ U4 west side (pins 2-12 face U3)
# Pins: 1 NC | 2 GND | 3 FBBK | 4 GND | 5 SWBK | 6 CPL | 7 CPH | 8 CP | 9-11 VM | 12 GND.  L1 exits: a 1-track strip
# between the pins and C402/C400 (x 19.49), W1 (y 22.46, C402.1 | C400.2) and W2 (y 24.05, C400.2 | C400.1).
# CP: W2 straight into C403.1.
tr("R_CP", F1, [(20.1, 24.25), (19.75, 24.25), (19.55, 24.05), (17.0, 24.05)])
# CPL: up the strip, W1, down the x 16.1 corridor (C403 | U3 via field) into C404.2.
tr("R_CPL", F1, [(20.1, 23.25), (19.8, 23.25), (19.49, 22.94), (19.49, 22.6), (19.35, 22.46), (16.3, 22.46),
                 (16.1, 22.66), (16.1, 27.1), (15.9, 27.3), (15.6, 27.3)])
# CPH: via at the strip (L3-island edge), L4 west of the thermal field to a via beside C404.1.
tr("R_CPH", F1, [(20.1, 23.75), (19.6, 23.75), (19.44, 23.6)])
via("R_CPH", (19.44, 23.6))
tr("R_CPH", L4, [(19.44, 23.6), (18.9, 24.14), (18.9, 26.7), (17.72, 27.5)])
via("R_CPH", (17.72, 27.5))
tr("R_CPH", F1, [(17.72, 27.5), (17.1, 27.5)])
# FBBK: up the strip past pins 2 / 1 into R400.2; SWBK: via in pad 5 (POFV), L4 west of the thermal field to a via
# below R400.1
tr("R_FBBK", F1, [(20.1, 21.75), (19.8, 21.75), (19.49, 21.44), (19.49, 19.3), (19.9, 18.9), (19.9, 18.2)])
via("R_SWBK", (19.93, 22.75))
tr("R_SWBK", F1, [(20.1, 22.75), (19.93, 22.75)])
tr("R_SWBK", L4, [(19.93, 22.75), (19.93, 19.7), (19.18, 18.95), (18.42, 18.95)])
via("R_SWBK", (18.42, 18.95))
tr("R_SWBK", F1, [(18.42, 18.95), (18.42, 18.0)])
# GND pins to the exposed pad
for x_, y_, x2, y2 in ((20.1, 21.25, 20.9, 21.25), (20.1, 22.25, 20.9, 22.25), (20.1, 26.25, 20.9, 26.25),
                       (21.75, 26.9, 21.75, 26.1), (23.25, 26.9, 23.25, 26.1), (24.9, 23.75, 24.1, 23.75)):
    tr("GND", F1, [(x_, y_), (x2, y2)], 0.2)

# ================================================================ U4 east side (pins 21-32 face the MCU)
# Pins: 32 +3V3 | 31 INHC | 30 +3V3 | 29 INHB | 28 +3V3 | 27 INHA | 26 GND | 25 AVDD | 24 NC | 23 +3V3 | 22 nFAULT |
# 21 DRV_OFF.  INHC / INHB (to the MCU's front and east edges) drop to L3 just outside the L3 island; the three
# +3V3 pins between them join on an L1 bar behind those vias and go down at a via above C405 (L4 to R12.2 and a via
# under U1 to pin 32, and to pin 23's via, where U3's +3V3 trunk lands); INHA passes between C405's pads; AVDD ends
# in C405.1; nFAULT / DRV_OFF run straight to the MCU's west pins (DRV_OFF via TP8).
via("R_INHC", (26.2, 21.25)); via("R_INHB", (26.2, 22.25))
tr("R_INHC", F1, [(24.9, 21.25), (26.2, 21.25)]); tr("R_INHB", F1, [(24.9, 22.25), (26.2, 22.25)])
for y_ in (20.75, 21.75, 22.75):
    tr("+3V3", F1, [(24.9, y_), (26.65, y_)], 0.2)
tr("+3V3", F1, [(26.65, 20.75), (26.65, 22.75)], 0.2)
VB, VA = (26.95, 21.75), (26.1, 25.25)
tr("+3V3", F1, [(26.65, 20.75), (34.25, 20.75)], 0.2)                        # bar -> U1 pin 32 (west side)
via("+3V3", VB, RV)
via("+3V3", VA, RV)
tr("+3V3", F1, [(24.9, 25.25), VA], 0.2)
tr("+3V3", L4, [VB, (26.95, 24.9), (26.6, 25.25), VA], 0.2)
tr("+3V3", L3, [(XU4E, 28.9), (26.1, 28.9), VA], 0.2)                       # U3's +3V3 trunk joins here
via("+3V3", (34.45, 22.2), RV)                                              # under U1, to pin 32's inner end
tr("+3V3", F1, [(34.45, 22.2), (34.25, 22.0), (34.25, 21.3)], 0.2)
tr("R_INHA", F1, [(24.9, 23.25), (25.35, 23.25), (25.6, 23.5), (28.2, 23.5), (28.53, 23.83), (28.53, 26.25),
                  (29.9, 26.25), (30.15, 26.0), (32.325, 26.0)])
tr("R_AVDD", F1, [(24.9, 24.25), (27.4, 24.25)])
tr("R_AVDD", F1, [(22.25, 20.1), (22.25, 18.1)])        # pin 37 straight into C406.1
tr("R_AVDD", F1, [(27.4, 24.5), (27.96, 25.06), (27.96, 25.7)])             # C405.1 -> R401.2
tr("R_nFAULT", F1, [(24.9, 25.75), (26.94, 25.75)])                          # pin 22 -> R401.1
# DRV_OFF pull-up R50 sits under U1.45: via in the pin's pad (POFV)
via("DRV_OFF", (32.95, 28.5))
tr("DRV_OFF", L4, [(32.95, 28.5), (32.31, 28.5)])
# R81 (SOB filter, top, west of pin 34): R_SOB arrives through a via east of R81.1, R_SOB_F runs to pin 34 on L1

tr("R_SOB_F", F1, [(28.75, 22.51), (30.6, 22.51), (31.1, 23.0), (32.325, 23.0)])
# nCS arrives through a via in the west ring
via("R_nCS", (30.8, 21.95))
tr("R_nCS", F1, [(30.8, 21.95), (31.35, 22.5), (32.325, 22.5)])

# ================================================================ MCU ends of the lanes
# CSA outputs on L4, north-east over L3 GND to the bottom filter resistors under U1's west pins.  SOB (the middle
# lane) goes straight east above R401 to R71; SOC crosses it with a short L3 hop and reaches R72 along y 23.25.
tr("L_SOA", L4, [(XU4E, 27.95), (26.0, 27.95), (29.8, 24.15), (33.2, 24.15), (33.45, 23.9)])
tr("L_SOB", L4, [(XU4E, 28.23), (26.6, 28.23), (27.9, 26.93), (30.0, 26.93), (30.86, 27.79), (33.65, 27.79)])
tr("L_SOC", L4, [(XU4E, 28.51), (27.3, 28.51), (27.3, 28.6)])
via("L_SOC", (27.3, 28.6))
tr("L_SOC", L3, [(27.3, 28.6), (27.3, 26.0), (29.9, 23.4), (29.9, 23.25)])
via("L_SOC", (29.9, 23.25))
tr("L_SOC", L4, [(29.9, 23.25), (34.28, 23.25), (34.28, 24.04), (34.9, 24.04)])
# INHA / INHB: L3 north-east to vias in the MCU's west fan-out ring, short L1 stubs into pins 38 / 39
via("L_INHA", (30.2, 24.6)); via("L_INHB", (30.95, 25.5))
tr("L_INHA", F1, [(30.2, 24.6), (30.6, 25.0), (32.325, 25.0)]); tr("L_INHB", F1, [(30.95, 25.5), (32.325, 25.5)])
E = dict(margin=3.0)
tr("L_INHA", L3, [(XU4E, 29.45), (27.6, 29.45), (28.6, 28.45), (28.6, 26.2), (30.2, 24.6)])
tr("L_INHB", L3, [(XU4E, 29.73), (27.73, 29.73), (28.88, 28.58), (28.88, 26.6), (29.78, 25.7), (30.75, 25.7), (30.95, 25.5)])
# rear pins: SPI up from L4 through three staggered vias below pins 52-54; nFAULT / nCS / INHC through vias under the
# MCU body at the inner ends of pins 55 / 61 / 62 (L3 under the rear pin row)
SV = {"SPI_SCK": (34.4, 33.65), "SPI_MISO": (35.3, 34.1), "SPI_MOSI": (36.2, 34.45)}
for n, c in SV.items():
    via(n, c)
tr("SPI_SCK", F1, [SV["SPI_SCK"], (35.2, 33.65), (35.75, 33.1), (35.75, 32.4)])
tr("SPI_MISO", F1, [SV["SPI_MISO"], (35.8, 34.1), (36.25, 33.65), (36.25, 32.4)])
tr("SPI_MOSI", F1, [SV["SPI_MOSI"], (36.4, 34.45), (36.75, 34.1), (36.75, 32.4)])
tr("SPI_SCK", L4, [(XJRE, 34.03), (34.02, 34.03), SV["SPI_SCK"]])
tr("SPI_MISO", L4, [(XJRE, 34.31), (34.9, 34.31), SV["SPI_MISO"]])
tr("SPI_MOSI", L4, [(XJRE, 34.59), (35.8, 34.59), (35.94, 34.45), SV["SPI_MOSI"]])
# nCS (north lane) turns under the rear pin row to a via under the MCU body at pin 61's inner end; INHC and nFAULT
# stay south and come up in the rear fan-out ring below pins 62 and 55.
via("L_nCS", (40.0, 30.1)); via("L_INHC", (40.5, 33.3)); via("L_nFAULT", (37.45, 33.4))
tr("L_nCS", L3, [(XJRE, 32.65), (31.5, 32.65), (33.5, 30.65), (39.45, 30.65), (40.0, 30.1)])
tr("L_nCS", F1, [(40.0, 30.1), (40.25, 30.35), (40.25, 31.4)])
tr("L_INHC", L3, [(XJRE, 32.93), (40.1, 32.93), (40.5, 33.3)])
tr("L_INHC", F1, [(40.5, 33.3), (40.75, 33.05), (40.75, 32.4)])
tr("L_nFAULT", L3, [(XJRE, 33.21), (37.26, 33.21), (37.45, 33.4)])
tr("L_nFAULT", F1, [(37.45, 33.4), (37.25, 33.2), (37.25, 32.4)])
tr("R_nFAULT", F1, [(26.94, 25.7), (26.94, 26.55), (32.1, 26.55), (32.325, 26.5)])
tr("DRV_OFF", F1, [(24.9, 26.25), (25.5, 26.85), (27.5, 26.85), (28.2, 27.55), (28.55, 28.0)])
route("DRV_OFF", ("pad", "TP8", "1"), ("pad", "U1", "45"), [F1], **E)
route("+3V3", ("via", 34.45, 22.2), ("pad", "R12", "2"), [L4], margin=1.0)
# INHC / INHB: L3 under the MCU's west half to vias under the body at the inner ends of pins 26 (front) and 10 (east)
via("R_INHC", (38.0, 22.75)); via("R_INHB", (42.4, 25.9))
tr("R_INHC", F1, [(38.0, 22.75), (37.25, 22.0), (37.25, 21.3)])
tr("R_INHB", F1, [(42.4, 25.9), (42.8, 25.5), (43.1, 25.5)])
tr("R_INHC", L3, [(26.2, 21.25), (26.55, 20.9), (37.4, 20.9), (38.0, 21.5), (38.0, 22.75)])
tr("R_INHB", L3, [(26.2, 22.25), (26.6, 22.65), (36.8, 22.65), (37.45, 23.3), (40.4, 23.3), (42.4, 25.3), (42.4, 25.9)])
# CSA filter outputs (bottom R/C under the MCU's west half) to the ADC pins; L1 only under the MCU body (outside it the
# fan-out ring belongs to the other pins)
AVF = [[F1, 20.0, 15.0, 31.45, 35.0], [F1, 31.3, 15.0, 44.7, 19.7], [F1, 44.55, 15.0, 50.0, 35.0], [F1, 31.3, 32.8, 44.7, 35.0]]
# L_SOB_F: pin 42 is boxed in by pin 43's escape and the ring: via in the pad (POFV), L4 between C80 and R71 to a
# via by C81.1, L1 round C114 to a via by R71.2
via("L_SOB_F", (32.9, 27.0)); via("L_SOB_F", (34.55, 26.8)); via("L_SOB_F", (34.2, 28.35))
tr("L_SOB_F", L4, [(32.9, 27.0), (33.16, 27.26), (34.1, 27.26), (34.55, 26.8), (34.57, 26.25)])
tr("L_SOB_F", F1, [(34.55, 26.8), (34.55, 27.9), (34.2, 28.25), (34.2, 28.35)])
tr("L_SOB_F", L4, [(34.2, 28.35), (33.65, 28.81)])
# R_SOC_F: R82 (top, west of pin 35) round its east side into pin 35; on under the body to a via by C92.1
tr("R_SOC_F", F1, [(29.15, 24.86), (29.47, 24.86), (29.75, 24.58), (29.75, 24.0), (30.25, 23.5), (32.325, 23.5)])
via("R_SOC_F", (37.25, 25.35))
tr("R_SOC_F", F1, [(32.325, 23.5), (36.3, 23.5), (37.25, 24.45), (37.25, 25.35)])
tr("R_SOC_F", L4, [(37.25, 25.35), (37.25, 24.3), (37.7, 23.85), (38.3, 23.77)])
for n, a, b in (("L_SOA_F", ("pad", "R70", "2"), ("pad", "U1", "36")), ("L_SOA_F", ("pad", "C80", "1"), ("pad", "R70", "2")),
                ("L_SOC_F", ("pad", "R72", "2"), ("pad", "U1", "43")), ("L_SOC_F", ("pad", "C82", "1"), ("pad", "R72", "2")),
                ("R_SOA_F", ("pad", "R80", "2"), ("pad", "U1", "25")), ("R_SOA_F", ("pad", "C90", "1"), ("pad", "R80", "2")),
                ("R_SOB_F", ("pad", "C91", "1"), ("pad", "U1", "34"))):
    route(n, a, b, [L4, F1], margin=4.0, avoid=AVF)

# ================================================================ U3 buck (R300 now in the power band in front of U4)
# FBBK: L1 along the east strip under C302, up the U3 | U4 channel to the band corridor (y 15.95, between R302/R402
# and C302/C408/R400/R300): west through R302's pad gap to C307, east over R300.1 into R300.2.
tr("L_FBBK", F1, [(11.25, 21.9), (11.25, 21.27), (13.95, 21.27), (13.95, 15.95), (10.9, 15.95), (10.55, 15.6),
                  (10.55, 11.3)])
tr("L_FBBK", F1, [(13.95, 15.95), (22.95, 15.95), (23.18, 16.18), (23.18, 16.75)])
# SWBK: L1 up gap C (C300.2 | C302.1) to a via in the gap's upper end, L4 into the band corridor (x >= 14) to a via at
# R300.1's west end
tr("L_SWBK", F1, [(10.25, 21.9), (10.25, 21.4), (10.55, 21.1), (10.55, 19.25), (10.6, 18.95)])
via("L_SWBK", (10.6, 18.95)); via("L_SWBK", (15.5, 16.5))
tr("L_SWBK", L4, [(10.6, 18.95), (10.85, 18.7), (14.2, 18.7), (15.5, 17.4), (15.5, 16.5)])
tr("L_SWBK", F1, [(15.5, 16.5), (15.65, 16.35), (21.0, 16.35), (21.4, 16.75), (21.53, 16.75)])

# ================================================================ U4 front (pins 33-40 face the power band)
# SPI: SCK and MOSI on L1 north past C406 / R300 and east under U7's body into pins 5 / 2 from their inner ends; MISO
# (between them at U7) drops at pin 33 to L3 and comes up under U7 pin 4 (the strip south of U7 keeps room for
# INA_nCS / W_nFAULT).  The link to U3's SPI vias is three L3 lanes through the band corridor (L3 VBAT edge at y 16.0
# for x 14-27), crossing once to swap the order U4 and U3 present.
tr("SPI_SCK", F1, [(23.25, 20.1), (23.25, 19.45), (23.95, 18.75), (23.95, 16.1), (24.23, 15.82), (25.2, 15.82),
                   (25.37, 15.65), (28.5, 15.65), (28.5, 17.45)])
tr("SPI_MOSI", F1, [(23.75, 20.1), (23.75, 19.4), (24.45, 18.7), (24.45, 16.55), (24.8, 16.2), (26.9, 16.2),
                    (27.0, 16.3), (27.0, 17.45)])
tr("SPI_MISO", F1, [(24.25, 20.1), (24.25, 19.5), (24.65, 19.1), (25.4, 18.4)])
via("SPI_SCK", (23.95, 17.35)); via("SPI_MOSI", (24.45, 17.85)); via("SPI_MISO", (25.4, 18.4)); via("SPI_MISO", (28.0, 18.62))
tr("SPI_MISO", L3, [(25.4, 18.4), (25.62, 18.62), (28.0, 18.62)])
tr("SPI_MISO", F1, [(28.0, 18.62), (28.0, 17.45)])
tr("SPI_SCK", L3, [(23.95, 17.35), (16.14, 17.35), (15.86, 17.63), (15.86, 25.45), (15.45, 25.45)])
tr("SPI_MOSI", L3, [(24.45, 17.85), (16.14, 17.85), (16.14, 26.05), (14.25, 26.05)])
tr("SPI_MISO", L3, [(25.4, 18.4), (25.35, 18.35), (16.42, 18.35), (16.42, 26.65), (15.45, 26.65)])
# CSA outputs, nCS, the buck output to C407 and AVDD to C405 (router, in this order, round the explicit copper)
# nCS: via at the pin, L3 east under C407 (between MISO's L3 and INHC's), L4 down across the +3V3 bar / INHC lane
via("R_nCS", (22.75, 18.76)); via("R_nCS", (30.3, 19.6))
tr("R_nCS", F1, [(22.75, 20.1), (22.75, 18.76)])
tr("R_nCS", L3, [(22.75, 18.76), (24.9, 18.76), (25.2, 19.06), (26.1, 19.06), (26.3, 19.26), (29.96, 19.26),
                 (30.3, 19.6)])
tr("R_nCS", L4, [(30.3, 19.6), (30.8, 20.1), (30.8, 21.95)])
via("R_SOC", (29.2, 23.15))
tr("R_SOC", F1, [(29.2, 23.15), (29.15, 23.84)])
# CSA outputs: SOA through the band corridor on L4 (y 16.75) and east along y 18.9 to R80; SOB / SOC and the VREF tie
# (pin 37, via in pad) in the window between the band and U4's thermal field (y 19.23 / 19.51 / 19.95), SOB and SOC
# down to their top-side filters west of U1, the VREF tie down the U4 | E-via gap to pin 25's AVDD track.
V40, V39, V38, V37 = (20.75, 16.9), (21.2, 19.05), (21.8, 18.76), (22.25, 19.95)
for n, v in (("R_SOA", V40), ("R_SOB", V39), ("R_SOC", V38), ("R_AVDD", V37)):
    via(n, v)
tr("R_SOA", F1, [(20.75, 20.1), V40])
tr("R_SOB", F1, [(21.25, 20.1), (21.25, 19.1), V39])
tr("R_SOC", F1, [(21.75, 20.1), (21.75, 19.3), V38])
tr("R_SOA", L4, [V40, (20.9, 16.75), (26.3, 16.75), (26.8, 17.25), (26.8, 18.9), (27.06, 19.16), (28.6, 19.16),
                 (28.86, 18.9), (36.74, 18.9), (36.74, 19.1)])
tr("R_SOB", L4, [V39, (21.64, 19.49), (22.7, 19.49), (22.93, 19.72), (27.8, 19.72), (28.0, 19.92), (28.0, 21.49)])
tr("R_SOC", L4, [V38, (22.22, 19.18), (22.95, 19.18), (23.21, 19.44), (28.95, 19.44), (29.2, 19.69), (29.2, 23.15)])
tr("R_AVDD", L4, [V37, (22.3, 20.0), (25.1, 20.0), (25.35, 20.25), (25.35, 24.0), (25.6, 24.25)])
via("R_AVDD", (25.6, 24.25))
via("R_SOB", (28.0, 21.49))
tr("R_SOB", F1, [(28.0, 21.49), (28.75, 21.49)])
# buck output to C407: via at R400.2, L3 along y 16.5 (north of the SPI lanes), via west of U7 pin 1, L1 into C407.1
via("R_FBBK", (20.1, 16.85)); via("R_FBBK", (25.9, 18.15))
tr("R_FBBK", F1, [(20.1, 16.85), (20.08, 17.6)])
tr("R_FBBK", L3, [(20.1, 16.85), (20.5, 16.45), (25.6, 16.45), (25.9, 16.75), (25.9, 18.15)])
tr("R_FBBK", F1, [(25.9, 18.15), (26.1, 18.4), (26.3, 19.4)])
