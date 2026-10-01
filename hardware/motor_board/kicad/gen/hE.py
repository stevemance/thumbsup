"""hE: the EAST cluster by hand, on top of hM (h3 -> hL -> hC -> hM) (BMS bus, R_S1/2/3, R_MTEMP, the +3V3 island).
Measured: h4E (h4 router flow on hE) + hNE (= hN, JP1 +5V leg) -> 3 signal/rail opens, DRC 0: R_S2 (MCU end),
BMS_BAT (R11.2), CELL1 (C4.1).  Notes below on the as-built routes (some details changed from the plan text):
R_S1 runs L1 to a via behind C64 (43.7, 34.5); R_S3 leaves pin 24 on L1 (y 17.65) to a via at (44.6, 17.6);
R_MTEMP's U1.5 POFV -> R53.2 -> L4 east of MB_RX's R17 leg -> via (45.95, 32.0); C73 sits at the R117 end;
D5 (CELL0 clamp) went to the bottom behind J4; C40 / R47 swapped.

Plan (L3 unless noted):
  - rear corridor behind J1 / U6 / J4 (lanes N->S behind J4: BMS_BAT 32.28, SCL 32.56, SDA 32.84, ALERT 33.12,
    R_MTEMP 33.40, R_S2 33.68, R_S1 33.96, +3V3 34.30); BMS_BAT peels north through J4's 2/3 gap to U8.16, the I2C
    lanes and R_S2/R_S1 climb an L3 column east of J4.5 (x 76.9-79.2), R_MTEMP drops to R117, +3V3 runs on along the
    rear edge and up the east edge to the JP2 island via.
  - BMS I2C: POFVs in J1.6 / J1.5 / J1.3; at the U8 end the column lanes turn west north of the +5V lane into three
    vias north-west of U8 (between TH1 and the gate diagonals) with L4 stubs onto pins 12/13/14.
  - R_S1/R_S2: vias on the MCU rear-pin verticals (the L1 lanes to x 46 go), U10 pins 7 / 5 from a via north of U10
    and one under its body; R_S3: POFV in U1.24, front L3 strip y 18.9 / 17.42 east, down to a via south of U10.
  - U10 rework: C114 (R_H1B filter) south beside R114, R_H3B on L4 under U10 to R116, U10.8 -> C50 -> island.
  - R_MTEMP: POFV in U1.5 -> R53.2 -> C73 (moved beside R53) -> via behind TP2 -> corridor -> R117.2; D8 behind J4
    (bottom) beside R117, its +3V3 from the corridor +3V3 lane (POFV), GND via."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9


def move(ref, x, y, rot, side):
    EDITS.append(dict(op="move", ref=ref, x=x, y=y, rot=rot, side=side))


def rip(tracks=(), vias=()):
    EDITS.append(dict(op="rip_segs", tracks=list(tracks), vias=list(vias)))


def n(s):
    return v2_pre.n_(s)


# ---------------------------------------------------------------- rips
rip(tracks=[(n("R_S1"), F1, (38.45, 34.56), (46.0, 34.56)), (n("R_S2"), F1, (38.95, 34.28), (46.0, 34.28))])
tr("R_S2", F1, [(38.95, 34.28), (43.0, 34.28)])     # R_S2's lane shortened (clear of R_S1's via behind C64)
_h3b = [(F1, (79.65, 19.4), (79.75, 19.3)), (F1, (79.65, 22.45), (79.65, 19.4)), (F1, (79.6, 22.5), (79.65, 22.45)),
        (L4, (79.5, 22.4), (79.6, 22.5)), (L4, (79.15, 22.3), (79.2, 22.35)), (L4, (79.1, 22.15), (79.15, 22.2)),
        (L4, (79.75, 19.3), (79.85, 19.4)), (L4, (79.15, 22.2), (79.15, 22.3)), (L4, (79.05, 21.5), (79.05, 22.05)),
        (L4, (79.2, 22.35), (79.3, 22.35)), (L4, (81.6, 20.5), (81.15, 20.95)), (L4, (81.15, 20.95), (81.15, 20.99)),
        (L4, (79.85, 19.4), (81.35, 19.4)), (L4, (81.4, 19.45), (81.5, 19.45)), (L4, (79.1, 22.1), (79.1, 22.15)),
        (L4, (79.3, 22.35), (79.35, 22.4)), (L4, (79.05, 22.05), (79.1, 22.1)), (L4, (81.55, 19.6), (81.6, 19.65)),
        (L4, (81.6, 19.65), (81.6, 20.5)), (L4, (81.35, 19.4), (81.4, 19.45)), (L4, (79.35, 22.4), (79.5, 22.4)),
        (L4, (81.5, 19.45), (81.55, 19.5)), (L4, (81.55, 19.5), (81.55, 19.6))]
_h1b = [(F1, (80.5, 23.8), (80.45, 23.85)), (F1, (80.45, 23.85), (80.45, 23.9)), (F1, (80.5, 22.6), (80.5, 23.8)),
        (L4, (80.5, 20.75), (80.5, 22.6)), (L4, (79.6, 20.6), (80.35, 20.6)), (L4, (80.35, 20.6), (80.5, 20.75)),
        (L4, (80.45, 23.9), (80.05, 24.3)), (L4, (79.03, 20.05), (79.1, 20.1)), (L4, (79.1, 20.1), (79.6, 20.6))]
_h2b = [(L4, (79.05, 24.3), (79.05, 26.1)), (L4, (79.05, 26.1), (78.9, 26.25)), (L4, (78.9, 26.25), (78.9, 28.7)),
        (L4, (78.9, 28.7), (78.6, 29.0)), (L4, (78.6, 29.0), (78.55, 29.07))]
rip(tracks=[(n("R_H3B"), ly, a, b) for ly, a, b in _h3b] + [(n("R_H1B"), ly, a, b) for ly, a, b in _h1b] +
    [(n("R_H2B"), ly, a, b) for ly, a, b in _h2b],
    vias=[(n("R_H3B"), (79.6, 22.5)), (n("R_H3B"), (79.75, 19.3)), (n("R_H1B"), (80.5, 22.6)),
          (n("R_H1B"), (80.45, 23.9))])
EDITS.append(dict(op="rip_ref", ref="D8"))

# ---------------------------------------------------------------- parts
move("C73", 79.7, 32.4, -90, "B")       # R_MTEMP filter cap at the sensor end beside R117 (pad 1 north)
move("D5", 69.5, 33.5, 0, "B")          # CELL0 Schottky clamp to the bottom behind J4 beside R6 (CELL0 west)
move("C114", 79.15, 26.6, 270, "B")     # R_H1B filter cap south of U10 between C8 and C48 (pad 1 north)
move("D8", 74.95, 33.45, 180, "B")      # R_MTEMP clamp behind J4, beside R117
# C40 / R47 swap places: R47 (W_INLA_M pull-down) west, reached from U6.1 on L4; C40 east, fed from U6.14 on L4
# (the h4 W_INLA_M jumper used a via that is now in the rear corridor)
move("R47", 60.0, 33.1, 270, "B")       # pad 1 north
move("C40", 61.5, 33.1, 270, "B")       # pad 1 (+3V3) north

# ---------------------------------------------------------------- lane grid behind J4
Y = dict(BMS_BAT=32.28, BMS_SCL=32.56, BMS_SDA=32.84, BMS_ALERT=33.12, R_MTEMP=33.40, R_S2=33.68, R_S1=33.96)
Y3 = 34.30                               # +3V3 (rail)

# ---------------------------------------------------------------- R_S1 / R_S2 (MCU rear pins -> U10)
# R_S2 is OPEN at the MCU end: its L1 lane (y 34.28, to x 46) sits between MB_TX (34.0) and R_S1 (34.56), and L3
# under the rear corner is cut by L_MTEMP (L3 y 33.88 + x 41.6 up to its via (42.4, 31.0)); the corridor lane below
# starts at (46.4, 33.37) as the reserved slot.
# R_S1 stays on its L1 lane past C64 (L3 under the MCU's rear corner stays free for C64's +3V3), via behind C64
tr("R_S1", F1, [(38.45, 34.56), (43.64, 34.56), (43.7, 34.5)])
via("R_S1", (43.7, 34.5))
tr("R_S2", L3, [(46.4, 33.37), (53.0, 33.37), (53.31, Y["R_S2"]),
                (77.7, Y["R_S2"]), (77.94, 33.92), (78.75, 33.92), (78.75, 23.7), (78.55, 23.5), (78.55, 23.3)])
via("R_S2", (78.55, 23.3))
tr("R_S2", L4, [(78.55, 22.0), (78.55, 23.3)])
tr("R_S1", L3, [(43.7, 34.5), (43.75, 34.55), (50.0, 34.55), (50.59, Y["R_S1"]), (77.4, Y["R_S1"]), (77.64, 34.2),
                (79.15, 34.2), (79.15, 19.8), (79.7, 19.25)])
via("R_S1", (79.7, 19.25))
tr("R_S1", L4, [(79.55, 21.0), (79.55, 20.6), (79.5, 20.55), (79.5, 19.45), (79.7, 19.25)])

# R_S3: pin 24 north on L1, east on L1 y 17.65 north of W_INLC_M's lane (y 18.1), via at x 44.6 (front band ends at
# 44.5 on L3), L3 front strip y 17.42 east, down beside U10 to a via south of it
tr("R_S3", F1, [(38.25, 19.8), (38.25, 17.95), (38.55, 17.65), (44.6, 17.65), (44.6, 17.6)])
via("R_S3", (44.6, 17.6))
tr("R_S3", L3, [(44.6, 17.6), (44.78, 17.42), (80.3, 17.42), (80.3, 25.6), (79.95, 25.95)])
via("R_S3", (79.95, 25.95))
tr("R_S3", L4, [(79.95, 25.95), (79.55, 25.55), (79.55, 24.8)])

# ---------------------------------------------------------------- U10 inputs / supply
tr("R_H3B", L4, [(79.05, 21.5), (79.05, 22.35), (79.3, 22.6), (80.45, 22.6), (80.55, 22.5), (80.55, 21.25),
                 (80.8, 21.0), (81.15, 20.99)])
tr("R_H1B", L4, [(79.35, 26.3), (79.5, 26.45), (80.45, 26.45), (80.45, 25.0), (80.65, 24.55)])
tr("GND", L4, [(79.35, 27.1), (80.1, 27.45)])                                  # C114.2 -> C48.2
tr("R_H2B", L4, [(79.05, 24.9), (78.55, 25.4), (78.55, 29.07)])               # U10.3 -> C115.1 west of C114
tr("+3V3", L4, [(80.05, 21.0), (80.05, 20.4), (80.07, 20.2)], w=0.2)
tr("+3V3", L4, [(80.07, 19.9), (80.3, 19.15), (84.1, 19.15), (84.3, 18.95)], w=0.2)

# ---------------------------------------------------------------- BMS I2C (J1 east end -> U8 north pins)
via("BMS_SCL", (55.675, 30.1), POFV, "POFV J1.6")
via("BMS_ALERT", (55.675, 32.95), POFV, "POFV J1.5")
via("BMS_SDA", (56.945, 32.1), POFV, "POFV J1.3")
tr("BMS_SCL", L3, [(55.675, 30.1), (55.925, 30.35), (58.45, 30.35), (58.45, Y["BMS_SCL"]), (76.92, Y["BMS_SCL"]),
                   (76.92, 19.15), (71.0, 19.15), (70.4, 19.75), (70.1, 20.05), (69.0, 20.05), (68.6, 19.85)])
tr("BMS_SDA", L3, [(56.945, 32.1), (57.685, Y["BMS_SDA"]), (77.2, Y["BMS_SDA"]), (77.2, 18.85), (69.9, 18.85),
                   (69.5, 19.25), (69.5, 19.6)])
tr("BMS_ALERT", L3, [(55.675, 32.95), (55.845, Y["BMS_ALERT"]), (77.48, Y["BMS_ALERT"]), (77.48, 18.5), (69.45, 18.5),
                     (69.3, 18.65)])
via("BMS_SCL", (68.6, 19.85))
via("BMS_SDA", (69.5, 19.6))
via("BMS_ALERT", (69.3, 18.65))
tr("BMS_SCL", L4, [(70.6, 20.6), (70.6, 20.15), (69.0, 20.15), (68.6, 19.85)])
tr("BMS_SDA", L4, [(71.1, 20.6), (71.1, 19.85), (70.85, 19.6), (69.5, 19.6)])
tr("BMS_ALERT", L4, [(71.6, 20.6), (71.6, 19.2), (71.15, 18.75), (69.4, 18.75), (69.3, 18.65)])

# ---------------------------------------------------------------- BMS_BAT (C9.1 -> U8.16 through J4's 2/3 gap)
tr("BMS_BAT", F1, [(58.6, 33.9), (59.1, 33.4), (59.1, 31.9)])
via("BMS_BAT", (59.1, 31.9))
tr("BMS_BAT", L3, [(59.1, 31.9), (61.4, 31.9), (61.4, Y["BMS_BAT"]), (68.45, Y["BMS_BAT"]), (68.45, 24.6),
                   (69.5, 23.55), (70.6, 23.55), (73.0, 21.15)])
via("BMS_BAT", (73.0, 21.15))
tr("BMS_BAT", L4, [(73.0, 21.15), (72.85, 21.5)])

# ---------------------------------------------------------------- R_MTEMP
via("R_MTEMP", (44.35, 28.0), POFV, "POFV U1.5")
# L4 east of MB_RX's R17 leg (x 45.5) and west of J1.20, via behind TP2
tr("R_MTEMP", L4, [(44.35, 28.0), (45.27, 28.0), (45.85, 28.58), (45.85, 31.9), (45.95, 32.0)])
via("R_MTEMP", (45.95, 32.0))
tr("R_MTEMP", L4, [(78.5, 32.45), (79.45, 31.95)])                              # R117.2 -> C73.1
tr("R_MTEMP", L3, [(45.95, 32.0), (46.85, 32.9), (53.8, 32.9), (54.3, Y["R_MTEMP"]), (77.9, Y["R_MTEMP"]), (77.9, 31.6)])
via("R_MTEMP", (77.9, 31.6))
tr("R_MTEMP", L4, [(77.9, 31.6), (78.1, 32.2)])
tr("R_MTEMP", L4, [(74.6, 33.45), (76.9, 33.45), (77.4, 32.95), (77.6, 32.75), (78.1, 32.75)])     # D8.3 -> R117.2

# ---------------------------------------------------------------- +3V3: C40.1 -> corridor -> east edge -> JP2 island
via("+3V3", (61.9, 34.43), RV)
tr("+3V3", L4, [(61.9, 34.43), (62.1, 34.23), (62.1, 32.9), (61.7, 32.6)], w=0.2)        # -> C40.1
tr("+3V3", L4, [(60.31, 30.6), (60.31, 31.95), (60.46, 32.1), (61.3, 32.1), (61.45, 32.4)], w=0.2)  # U6.14 -> C40.1
tr("W_INLA_M", L4, [(59.4, 30.0), (59.4, 30.3), (59.65, 30.55), (59.65, 32.3), (59.9, 32.55)])  # -> R47.1
tr("+5V", L4, [(50.25, 31.45), (50.45, 31.9)])                                           # J1.13
tr("+3V3", L3, [(61.9, 34.43), (62.03, Y3), (76.05, Y3), (76.3, 34.55), (83.3, 34.55), (84.3, 33.55), (84.3, 18.95)],
   w=0.2)                                # the rear-right corner is an R1.5 arc about (83.5, 33.5)
via("+3V3", (75.89, 34.4), POFV, "POFV D8.2")
# +5V: J1.13 / TP11 / C30 (the corridor takes the via spots the router used under J1's west half) -> U5.1 on top
via("+5V", (50.25, 31.45), RV)
tr("+5V", F1, [(49.65, 32.2), (49.65, 33.4)], w=0.2)
tr("+5V", F1, [(50.1, 31.85), (52.25, 31.85), (52.6, 32.2), (52.95, 32.3)], w=0.2)
via("GND", (80.3, 33.5))                                                         # C73.2
tr("GND", L4, [(79.7, 32.88), (80.3, 33.5)])
tr("CELL0", L4, [(66.6, 34.0), (67.3, 33.5), (67.85, 33.5)])                     # R6.2 -> D5.1
tr("GND", L4, [(71.15, 33.5), (71.75, 32.45), (75.4, 32.45)])                    # D5.2 -> D8.1
via("GND", (76.3, 31.6))
tr("GND", L4, [(76.3, 31.6), (76.0, 32.2)])
