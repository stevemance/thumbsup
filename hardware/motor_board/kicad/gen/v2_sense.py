"""v2 region 2 pre-route (P3/P5): both motor-sensor front ends and the MCU's analog dividers, on top of v2_ilock.
Experiment module for tail.py:

    cd kicad/gen && TAIL_EXP=v2_sense TAIL_BASE=<abs>/kicad/gen/out/exp/v2_ilock/proj/motor_board.kicad_pcb /usr/bin/python3 tail.py

Left sensor (J2 / U9 / U11, R110-113, C110-112, R54-56, C45/C46) and right sensor (J3 / U10 / U12, R114-117,
C114-116, R57-59, C48/C49), their MCU lines (L_S1..3, R_S1..3, L/R_MTEMP via R52/R53, D7/D8, C72/C73), the phase
dividers W_VA/VB/VC, W_NTC and VBAT_SNS.  Rules: v2_pre.py.

The divider parts sit on the bottom right under the MCU pins they serve: vias in the MCU pads that land in the
resistor pad below (POFV: U1.22 = R23.1, U1.11 = R27.1, U1.14 = R63.2), W_VB through a via in C42.1 (POFV) in front of
pin 19, W_NTC through a via in front of pin 18."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, chain, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.STACK_PEN = 8.0
v2_pre.EXTRA_AVOID += v2_pre.RESERVE_R3 + v2_pre.RESERVE_R3B

# ---------------------------------------------------------------- dividers at the MCU (explicit)
via("W_VA", (39.25, 20.6), POFV, "POFV U1.22 / R23.1")
via("W_VC", (43.71, 25.0), POFV, "POFV U1.11 / R27.1")
via("VBAT_SNS", (43.71, 23.5), POFV, "POFV U1.14 / R63.2")
via("W_VB", (40.75, 19.5), POFV, "POFV C42.1")
tr("W_VB", F1, [(40.75, 20.0), (40.75, 19.5)])
via("W_NTC", (41.25, 19.95))
tr("W_NTC", F1, [(41.25, 20.2), (41.25, 19.95)])
tr("W_VA", L4, [(39.25, 20.6), (39.25, 21.85)])
route("W_VB", ("via", 40.75, 19.5), P("R25", 1), [L4], margin=1.0, stub=True)
tr("W_NTC", L4, [(41.25, 19.95), (41.75, 19.95), (41.75, 21.85), (41.3, 21.85)])
tr("W_NTC", L4, [(41.75, 19.95), (42.6, 19.95), (43.1, 20.45)])
tr("W_VC", L4, [(43.71, 25.0), (44.6, 25.0)])
route("VBAT_SNS", ("via", 43.71, 23.5), P("R64", 1), [L4], margin=1.0, stub=True)
route("VBAT_SNS", ("via", 43.71, 23.5), P("C68", 1), [L4, L3], margin=1.5, stub=True)
for n, a, b in (("W_VA", P("U1", 22), P("R22", 2)), ("W_VB", P("U1", 19), P("R24", 2)), ("W_VC", P("U1", 11), P("R26", 2))):
    route(n, a, b, margin=3.0)

via("R_S1", (35.25, 31.06), POFV, "POFV at the ends of U1.51 / U10.7 (stacked pads)")
route("R_S2", P("U10", 5), P("U1", 56), margin=2.0)
route("R_S3", P("U10", 2), P("U1", 30), margin=2.5)
route("R_H2B", P("R115", 2), P("U10", 3), margin=5.0)
# L_S2: via in U9.5 (its top row sits under J2's mounting pad, but pin 5 is clear of it), L1 north-east to y 29.6
via("L_S2", (13.22, 30.6), POFV, "POFV U9.5")
tr("L_S2", F1, [(13.22, 30.6), (13.3, 30.52), (13.3, 29.6), (13.5, 29.4), (15.8, 29.4)])
route("L_S2", ("pt", 15.8, 29.4, F1), P("U1", 57), margin=5.0)
# L_H3 to R112.1 (boxed in on L4 by the drive's +3V3 trunk and C47): L1 up the x 12.8 corridor west of L_S2 and C306,
# a via north of R112 and an L4 hop down into R112.1
tr("L_H3", F1, [(12.0, 33.2), (12.0, 32.9), (12.8, 32.1), (12.8, 27.2), (13.05, 26.95)])
via("L_H3", (13.05, 26.95))
tr("L_H3", L4, [(13.05, 26.95), (13.4, 27.3), (13.4, 27.9)])
# L_TEMPJ: L1 behind the JR pads (y 33.0) to a via beside R113.1
tr("L_TEMPJ", F1, [(13.0, 33.3), (13.3, 33.0), (28.9, 33.0), (29.3, 33.4), (29.3, 33.62)])
via("L_TEMPJ", (29.3, 33.62))
tr("L_TEMPJ", L4, [(29.3, 33.62), (29.6, 33.4)])
# ---------------------------------------------------------------- left sensor locals
chain("L_H1", [P("J2", 3), P("R110", 1), P("R54", 1)], margin=2.0)
chain("L_H2", [P("J2", 4), P("R111", 1), P("R55", 1)], margin=2.0)
route("L_H3", P("J2", 5), P("R56", 1), margin=2.0)
chain("L_H1B", [P("R110", 2), P("C110", 1), P("U9", 1)], margin=2.0)
chain("L_H2B", [P("R111", 2), P("C111", 1), P("U9", 3)], margin=2.0)
chain("L_H3B", [P("R112", 2), P("U9", 6)], margin=2.0)
route("L_H3B", P("R112", 2), P("C112", 1), margin=3.0)
chain("L_VS", [P("J2", 1), P("U11", 1), P("C46", 1)], margin=2.0)
chain("L_VSRC", [P("U11", 4), P("U11", 5), P("C45", 1)], margin=2.0)
# ---------------------------------------------------------------- right sensor locals
tr("R_VSRC", L4, [(76.96, 27.1), (76.96, 28.4)])
chain("R_VSRC", [P("U12", 4), P("C48", 1)], margin=2.0)
route("R_VSRC", P("JP2", 2), P("U12", 5), margin=2.0)
# R_TEMPJ: L1 down the strip between J3's pads and its mounting pad / J3.MP, past MH4, via beside R117.1
tr("R_TEMPJ", F1, [(81.3, 21.0), (80.6, 21.7), (80.6, 31.9), (79.6, 32.9), (79.4, 32.9)])
via("R_TEMPJ", (79.4, 32.9))
tr("R_TEMPJ", L4, [(79.4, 32.9), (78.7, 32.9)])
chain("R_VS", [P("J3", 1), P("U12", 1), P("C49", 1)], margin=2.0)
chain("R_H1", [P("J3", 3), P("R57", 1), P("R114", 1)], margin=2.0)
route("R_H2", P("J3", 4), P("R58", 1), margin=2.0)
tr("R_H2", L4, [(74.8, 27.24), (75.1, 27.54), (75.1, 28.9), (75.3, 29.1)])      # R58.1 -> R115.1 east of R58
chain("R_H3", [P("J3", 5), P("R59", 1), P("R116", 1)], margin=2.0)
# ---------------------------------------------------------------- U10 (under the MCU) to the MCU

# ---------------------------------------------------------------- MTEMP
# L_MTEMP: via in R52.2 right inside pin 6 (POFV), D7.3 beside it on L4; R_MTEMP: via at pin 5's tip (between C7, C5
# and the pins), L3 east in the strip y 27.4-29.9 that region 1 left free
via("L_MTEMP", (42.45, 27.5), POFV, "POFV R52.2")
tr("L_MTEMP", F1, [(43.2, 27.5), (42.45, 27.5)])
tr("L_MTEMP", L4, [(42.45, 27.5), (41.5, 27.5)])
# R_MTEMP: pin 5's inner end straight down inside the MCU body (L1), west to D8.3 (via in its pad under the body) and
# east out of the body's rear-east corner, round J4 onto the L1 lane y 32.4 behind it (rear highway) to R53 / C73 / R117
via("R_MTEMP", (40.7, 30.8), POFV, "POFV D8.3")
tr("R_MTEMP", F1, [(43.1, 28.0), (42.6, 28.0), (42.6, 30.8), (40.7, 30.8)])
tr("R_MTEMP", F1, [(42.6, 30.8), (44.3, 30.8), (45.9, 32.4), (60.6, 32.4)])
# at J4's east end a via to C73.1 / R53.2 (L4 hop round R53.1), then on along the rear edge on L1 (y 34.15, under D2)
# and L3 under R41 / U5 to a via beside R117.2
via("R_MTEMP", (61.25, 32.4))
tr("R_MTEMP", F1, [(60.6, 32.4), (61.25, 32.4)])
tr("R_MTEMP", L4, [(61.25, 32.4), (61.85, 31.8), (62.3, 31.6)])
tr("R_MTEMP", L4, [(62.3, 31.5), (61.85, 31.05), (61.85, 29.65), (62.2, 29.65)])
tr("R_MTEMP", F1, [(61.25, 32.4), (61.25, 33.9), (61.5, 34.15), (71.35, 34.15), (71.5, 34.3)])
via("R_MTEMP", (71.5, 34.3)); via("R_MTEMP", (76.1, 34.3))
tr("R_MTEMP", L3, [(71.5, 34.3), (76.1, 34.3)])
tr("R_MTEMP", L4, [(76.1, 34.3), (76.6, 33.8), (76.6, 33.4)])
route("L_MTEMP", ("via", 42.45, 27.5), P("C72", 1), margin=2.0)
route("L_MTEMP", ("via", 42.45, 27.5), P("R113", 2), margin=4.0)
# ---------------------------------------------------------------- long runs
route("R_H1B", P("U10", 1), P("C114", 1), margin=2.0)
route("R_H2B", P("U10", 3), P("C115", 1), margin=2.0)
tr("R_H3B", L4, [(35.75, 32.2), (35.77, 33.1)])
route("R_H1B", P("R114", 2), P("U10", 1), margin=5.0)
route("R_H3B", P("R116", 2), P("U10", 6), margin=5.0)
route("VBAT_SNS", P("R64", 1), P("R33", 1), margin=5.0)
route("L_S3", P("U1", 24), P("U9", 2), margin=5.0)
# L_S1: U9.7 south under U9's body, via east of it, L1 behind the JR pads (y 32.72), up past JR3 to y 31.7 (south of
# L_S2's lane) to a via at the MCU's rear-west corner; the router takes it on to U1.58
tr("L_S1", L4, [(14.25, 31.2), (14.25, 32.15), (15.0, 32.15), (15.15, 32.3)])
via("L_S1", (15.15, 32.3))
tr("L_S1", F1, [(15.15, 32.3), (15.57, 32.72), (27.9, 32.72), (28.92, 31.7), (31.8, 31.7), (31.9, 31.6)])
route("L_S1", ("pt", 31.9, 31.6, F1), P("U1", 58), margin=3.0)
route("L_VSRC", P("C45", 1), P("JP1", 2), margin=3.0)
