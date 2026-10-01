"""hL: left-motor sensor interface (cluster LEFT) by hand, on top of h3.

U9 (Schmitt buffer) moves to the MCU's rear-left corner (top, rot 270, x 28.5-31.0 between JR3 and the MCU): its
outputs leave through its own body on L1 straight into the MCU interior lanes (L_S3 y 30.38 -> front pin 30 via
x 38.95 / y 23.2, L_S2 y 30.66 -> pin 56, L_S1 y 30.94 -> pin 51).
The raw hall lines cross the JR field: L_H1 on L3 above JR (y 29.99, between L_INHB and the JR pads; L_INHA / L_INHB
move 0.025 north for it) from its J2 via, L_H2 on L1 above JR (y 29.40), L_H3 on L1 behind JR (y 32.72).  Filters:
R110 (H1) under U9 (the L3 lane ends in a POFV in R110.1), R111 (H2) / R112 (H3) on top in the lanes beside JR2; the
caps C110/C111/C112 and C47 under U9.  U9's inputs: pin 3 from the north on L1, pin 6 from the south on L1, pin 1 by
a via in the outer part of its pad (row end); the row-interior pads are 0.5 mm pitch, too tight for a via, so C111 /
C112 hang on POFVs beside / inside U9's body.  Pull-ups R55/R56 at J2 on the L4 +3V3 jog, R54 unchanged; R113 at J2.
L_MTEMP leaves R113.2 (J2) on L3 behind JR (y 33.8, between L4 DRV_OFF and SPI), weaves through the SPI via steps and
comes up in the MCU's rear-right corner (via 42.4, 31.0): L1 in the interior to pin 6 (POFV in R52.2, R52 rot 180),
L4 to the clamp D7.3.  DRV_OFF's L4 lane from U3 now runs on to R50.1 around the corner (x 33.83) instead of up to
its via at (29.3, 30.4) (U9's spot); R48 (W_INLB_M pull-down) leaves U9's spot for the bottom under the MCU."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV, n_  # noqa: F401

v2_pre.VIA_PITCH = 0.9


def move(ref, x, y, rot, side):
    EDITS.append(dict(op="move", ref=ref, x=x, y=y, rot=rot, side=side))


MINE = ["L_H1", "L_H2", "L_H3", "L_H1B", "L_H2B", "L_H3B", "L_S1", "L_S2", "L_S3", "L_TEMPJ", "L_MTEMP"]
EDITS.append(dict(op="rip", box=(0, 0, 85, 35), nets=[n_(n) for n in MINE]))
# DRV_OFF: the L4 lane's climb to the old via (29.3, 30.4) and the via's L1 leg to TP8
EDITS.append(dict(op="rip", box=(28.2, 29.5, 29.5, 33.0), nets=[n_("DRV_OFF")]))
# W_INLB_M: pin 46's west stub to R48's old spot
EDITS.append(dict(op="rip", box=(30.6, 28.9, 30.85, 29.1), nets=[n_("W_INLB_M")], layers=["F.Cu"]))
# +3V3: the dangling L4 stub toward C47's old spot
EDITS.append(dict(op="rip", box=(14.6, 29.1, 14.9, 29.4), nets=[n_("+3V3")], layers=["B.Cu"]))
# L_INHA / L_INHB: their L3 lanes under JR move 0.025 mm north (29.45 -> 29.425, 29.73 -> 29.705) so that L_H1's
# lane fits between L_INHB and the JR pads (Drive class 0.15)
EDITS.append(dict(op="rip", box=(9.5, 29.4, 27.8, 29.8), nets=[n_("L_INHA"), n_("L_INHB")], layers=["In2.Cu"]))

# ------------------------------------------------------------------ parts
move("U9", 29.75, 30.9, 270, "F")
move("TP8", 28.55, 27.4, 0, "F")
move("TP12", 26.5, 34.05, 0, "F")
move("TP5", 32.3, 34.05, 0, "F")
move("R48", 37.5, 28.55, 0, "B")
move("R52", 43.2, 27.5, 180, "B")
move("R110", 28.71, 30.1, 0, "B")
move("C110", 31.3, 30.15, 270, "B")
move("C111", 29.84, 28.45, 0, "B")
move("C112", 29.0, 31.25, 180, "B")
move("C47", 31.08, 32.1, 0, "B")
move("R111", 22.5, 29.1, 0, "F")
move("R112", 22.5, 33.9, 0, "F")
move("R55", 13.3, 29.2, 90, "B")
move("R56", 14.6, 29.3, 90, "B")
move("R113", 13.95, 34.2, 0, "B")

# ------------------------------------------------------------------ U9 outputs: through U9's body into the MCU
tr("L_S3", F1, [(30.0, 29.5), (30.0, 30.38), (38.95, 30.38), (38.95, 23.2), (35.25, 23.2), (35.25, 20.9)])
tr("L_S2", F1, [(29.0, 32.3), (29.0, 30.66), (37.75, 30.66), (37.75, 31.6)])
tr("L_S1", F1, [(30.0, 32.3), (30.0, 30.94), (35.25, 30.94), (35.25, 31.6)])

# ------------------------------------------------------------------ J2 end
# H1: pin 3 -> via (R54.1 beside it on L4) -> L3, out between L_INHB's and L_INHC's vias to the lane y 30.01
tr("L_H1", F1, [(10.0, 33.0), (10.0, 32.2), (10.15, 32.05)])
via("L_H1", (10.15, 32.05))
tr("L_H1", L4, [(10.01, 32.6), (10.15, 32.05)])
tr("L_INHA", L3, [(9.3, 29.7), (9.575, 29.425), (27.625, 29.425), (28.6, 28.45)])
tr("L_INHB", L3, [(10.9, 30.0), (11.195, 29.705), (27.755, 29.705), (28.88, 28.58)])
tr("L_H1", L3, [(10.15, 32.05), (10.15, 30.95), (11.1, 30.95), (11.5, 30.55), (12.06, 29.99), (27.9, 29.99),
                (28.2, 30.1)])
# H2: pin 4 -> via -> L4 past R55 (pull-up on the +3V3 jog) -> via -> L1 riser x 12.6 -> lane y 29.40
tr("L_H2", F1, [(11.0, 33.0), (11.35, 32.65), (11.35, 32.4)])
via("L_H2", (11.35, 32.4))
tr("L_H2", L4, [(11.35, 32.4), (11.8, 32.0), (12.6, 31.3), (13.3, 30.6), (13.3, 29.71)])
via("L_H2", (12.6, 31.3))
tr("L_H2", F1, [(12.6, 31.3), (12.6, 29.4), (22.0, 29.4), (22.0, 29.1)])
# H3: pin 5 -> via -> L4 north of the TEMPJ via (R56 pull-up branch) -> via -> L1 lane y 32.72
tr("L_H3", F1, [(12.0, 33.0), (12.25, 32.75), (12.25, 32.4)])
via("L_H3", (12.25, 32.4))
tr("L_H3", L4, [(12.25, 32.4), (12.65, 31.98), (13.85, 31.98), (14.3, 32.42)])
tr("L_H3", L4, [(14.0, 31.98), (14.6, 31.38), (14.6, 29.81)])
via("L_H3", (14.3, 32.42))
tr("L_H3", F1, [(14.3, 32.42), (14.6, 32.72), (21.99, 32.72), (21.99, 33.9)])
# TEMPJ: pin 6 -> via -> R113 (L4) -> POFV in R113.2 -> L3
tr("L_TEMPJ", F1, [(13.0, 33.0), (13.15, 32.85), (13.15, 32.4)])
via("L_TEMPJ", (13.15, 32.4))
tr("L_TEMPJ", L4, [(13.15, 32.4), (13.12, 34.2)])

# ------------------------------------------------------------------ the filtered side at U9
# H2B: R111.2 (top) -> lane y 29.40 -> north of U9 into pin 3's north end; via beside it to C111 (L4)
tr("L_H2B", F1, [(23.0, 29.1), (23.0, 29.4), (27.5, 29.4), (28.45, 28.45), (29.5, 28.45), (29.5, 29.2)])
via("L_H2B", (29.5, 28.45), POFV, "POFV C111.1 (north of U9.3)")
# H3B: R112.2 (top) -> lane y 32.72 -> under pin 5's south end into pin 6; via in U9's body to C112 (L4)
tr("L_H3B", F1, [(23.01, 33.9), (23.01, 32.72), (27.6, 32.72), (28.08, 33.2), (29.5, 33.2), (29.5, 32.3)])
tr("L_H3B", F1, [(29.5, 32.3), (29.5, 31.25)])
via("L_H3B", (29.5, 31.25), POFV, "POFV C112.1 (in U9 body)")
# H1B: R110.2 -> (L4) -> via east of pin 1 -> pin 1; C110
via("L_H1", (28.2, 30.1), POFV, "POFV R110.1 (end of the L3 lane)")
tr("L_H1B", L4, [(29.22, 30.1), (30.35, 30.1), (30.6, 29.85), (31.3, 29.67)])
via("L_H1B", (30.6, 29.85), POFV, "POFV U9.1 (east part of the pad)")
tr("L_H1B", F1, [(30.6, 29.85), (30.5, 29.75), (30.5, 29.5)])
# U9 supply / ground
via("GND", (28.9, 29.2), POFV, "POFV U9.4 (west part of the pad)")
tr("GND", F1, [(28.9, 29.2), (29.0, 29.3), (29.0, 29.5)])
via("+3V3", (30.6, 32.1), POFV, "POFV U9.8 (east part) + C47.1")
tr("+3V3", F1, [(30.6, 32.1), (30.5, 32.2), (30.5, 32.3)])
tr("+3V3", L4, [(30.6, 32.1), (30.6, 32.41), (30.94, 32.75), (32.4, 32.75), (32.4, 30.31), (32.32, 30.0)], w=0.2)
via("GND", (31.75, 31.45), PV, "C110.2 / C47.2")
tr("GND", L4, [(31.3, 30.63), (31.75, 31.45), (31.56, 32.1)])
via("GND", (30.25, 27.75), PV, "C111.2")
tr("GND", L4, [(30.25, 27.75), (30.32, 28.45)])
via("GND", (28.3, 31.85), PV, "C112.2")
tr("GND", L4, [(28.3, 31.85), (28.52, 31.25)])
# test pads TP12 / TP5 (GND) behind U9 / the MCU's rear-left: one GND via under the MCU corner, L1 links
via("GND", (33.1, 32.3), PV, "TP5 / TP12")
tr("GND", F1, [(32.3, 34.05), (32.3, 33.4), (33.1, 32.6), (33.1, 32.3)])
tr("GND", F1, [(26.5, 34.05), (26.8, 34.35), (32.0, 34.35), (32.3, 34.05)], w=0.2)

# ------------------------------------------------------------------ DRV_OFF: U3's L4 lane on to R50.1 around the corner
tr("DRV_OFF", L4, [(27.6, 33.62), (33.83, 33.62), (33.83, 29.3), (32.5, 29.3), (32.31, 29.11), (32.31, 28.5)])
# ------------------------------------------------------------------ R48 (W_INLB_M pull-down) under the MCU
via("W_INLB_M", (36.6, 28.85), POFV, "POFV R48.1 corner, to the L3 W_INLB_M lane")
tr("W_INLB_M", L4, [(36.6, 28.85), (36.99, 28.55)])
via("GND", (38.4, 28.0), PV, "R48.2")
tr("GND", L4, [(38.01, 28.55), (38.4, 28.0)])

# ------------------------------------------------------------------ L_MTEMP: R113.2 (J2) -> L3 behind JR -> rear-right corner
via("L_MTEMP", (14.77, 34.2), POFV, "POFV R113.2")
tr("L_MTEMP", L3, [(14.77, 34.2), (15.17, 33.8), (16.9, 33.8), (17.15, 34.05), (17.45, 34.05), (17.7, 33.8),
                    (33.85, 33.8), (34.13, 34.08), (34.7, 34.08), (35.1, 33.68), (36.6, 33.68), (36.8, 33.88),
                    (41.6, 33.88), (41.6, 31.8), (42.4, 31.0)])
via("L_MTEMP", (42.4, 31.0), PV, "rear-right corner")
tr("L_MTEMP", L4, [(42.4, 31.0), (40.01, 31.0)])
tr("L_MTEMP", F1, [(42.4, 31.0), (42.55, 30.85), (42.55, 27.7), (42.69, 27.5), (43.3, 27.5)])
via("L_MTEMP", (42.69, 27.5), POFV, "POFV R52.2 (at U1.6's inner end)")
tr("L_MTEMP", L4, [(42.69, 27.5), (41.7, 27.77)])
tr("+3V3", L4, [(43.71, 27.5), (43.71, 27.8), (42.94, 28.57), (42.94, 28.7)])
