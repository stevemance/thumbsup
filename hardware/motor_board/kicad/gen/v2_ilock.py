"""v2 region 1 pre-route (P3/P5): weapon interlock and U2 control between the MCU's east edge and U2, on top of
v2_bridge + v2_drive.  Experiment module for tail.py:

    cd kicad/gen && TAIL_EXP=v2_ilock TAIL_BASE=<abs>/kicad/gen/out/exp/v2_drive/proj/motor_board.kicad_pcb /usr/bin/python3 tail.py

Nets: U2's local parts (CPH/CPL/VCP, MODE/IDRIVE/VDS, DVDD, the buck CB/SW/EN/FB), the six gate inputs (W_INHx from the
MCU, W_INLx from the AND gate U6), the MCU-side INL requests W_INLx_M (pull-downs R47-R49) to U6, the arm chain
(W_ARM, W_ARM_S, W_ARM_CLK, ARM_AC), W_EN, W_nFAULT and the CSA outputs W_SOA/B/C.  Rules: v2_pre.py.

U2's rear pin row (37-42 at 0.5 mm pitch, C24's GND pad right behind pins 42-44): every gate input drops to a via
straight behind its pin - INHA/B/C (37/39/41) in a row at y 28.25, INLA/B (38/40) in a second row between them,
INLC (42) at (63.45, 28.18) beside C24.  INH leaves on L3 lanes west (y 28.25 / 27.8 / 27.35); INLA/INLB come on
L4 from U6's rear pins through the R9|R10 and R8|R9 gaps, INLC on L3 (y 26.9) from a via in U6's pin 8.

U6 (DQFN-14, bottom; its GND pad and the top-side U2 strap resistors R44-R46 / C9 / C22 leave no room for vias
around it): W_ARM_S joins pins 2/5 on L3 through vias in their pads (POFV) and pin 10 on L4 north to R19;
INLB_M arrives on L1 through a via in pin 4 (POFV); U14's W_ARM pin shares a via with TP6 right above it (POFV)."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, chain, tr, via, PV, POFV, RV  # noqa: F401

# keep out of the MCU body's rear strip (the rear-row pins 49-60 drop to vias there, regions 2/3)
v2_pre.EXTRA_AVOID += [["*", 33.3, 29.7, 42.95, 31.65], [F1, 42.1, 27.8, 42.95, 31.3, "tracks"]]
# region 2/3 escapes of the MCU's east pins 5-7: L_MTEMP via in R52.2 (inside the body), the L3 strip y 27.4-29.9 east
# of the MCU (their vias), L1 east of pins 5-7 (their stubs); the bottom under the east pins (region 2 dividers)
v2_pre.EXTRA_AVOID += [["*", 42.0, 27.1, 42.9, 27.9], [L3, 43.8, 27.4, 55.5, 29.9, "tracks"],
                       [L4, 38.0, 18.5, 47.8, 27.5, "tracks"],
                       ["*", 38.9, 18.9, 41.6, 19.85]]      # + the outer ends of pins 18-22 (region 2 divider vias)
v2_pre.EXTRA_AVOID += v2_pre.RESERVE_R2 + v2_pre.RESERVE_R3 + v2_pre.RESERVE_R3B
# R_MTEMP's exit from the MCU body's rear-east corner onto the rear L1 lane behind J4 (region 2)
v2_pre.EXTRA_AVOID += [[F1, 42.1, 30.45, 44.6, 31.15, "tracks"], [F1, 44.2, 30.45, 46.4, 32.75, "tracks"],
                       [F1, 45.5, 32.1, 61.0, 32.7, "tracks"]]

# ---------------------------------------------------------------- placement (kicad/v2/spec.py EXPLICIT, 2026-09-30)
# R40 (W_EN pull-down) off the bottom under U2's rear pins to the top at (52.0, 24.0); R45 / R46 (IDRIVE / VDS straps)
# swapped; the anchored parts around them pinned where they were (spec.py "pinned (pre-routed)").

# ---------------------------------------------------------------- U2 rear row fan-out (explicit)
FAN = {"W_INHA": (60.75, (60.75, 28.25)), "W_INLA": (61.25, (61.25, 28.85)),
       "W_INHB": (61.75, (61.75, 28.25)), "W_INLB": (62.25, (62.25, 28.75)),
       "W_INHC": (62.75, (62.75, 28.25)), "W_INLC": (63.25, (63.45, 28.18))}
for n, (x, v) in FAN.items():
    via(n, v)
    tr(n, F1, [(x, 27.6), (x, 27.875), v] if v[0] != x else [(x, 27.6), v])
# INH lanes west on L3: y 27.35 / 27.8 / 28.25 behind U2, stepping up at x 54-55.6 (under INLC's L3 corner, clear of
# the ARM_S via at U14) to y 26.45 / 26.75 / 27.05 between J4 and the MCU, so the strip y 27.4-29.9 east of the MCU
# stays free on L3 for the MCU's east-pin vias (NRST, R_MTEMP, the rear-row nets: regions 2/3)
tr("W_INHA", L3, [(60.75, 28.25), (54.7, 28.25), (53.5, 27.05), (37.0, 27.05)])      # on under the MCU body
tr("W_INHB", L3, [(61.75, 28.25), (61.75, 27.8), (55.15, 27.8), (54.1, 26.75), (46.25, 26.75), (46.25, 25.55)])
tr("W_INHC", L3, [(62.75, 28.25), (62.75, 27.35), (55.6, 27.35), (54.7, 26.45), (47.1, 26.45), (46.85, 26.2),
                  (46.85, 25.55)])
# MCU ends: vias between C43/C72 (bottom) and TP1 (top), L1 straight into pins 9 / 8
via("W_INHB", (46.25, 25.55)); via("W_INHC", (46.85, 25.55))
tr("W_INHB", F1, [(44.1, 26.0), (46.25, 26.0), (46.25, 25.55)])
tr("W_INHC", F1, [(44.1, 26.5), (46.85, 26.5), (46.85, 25.55)])

# ---------------------------------------------------------------- U6 fan-out (bottom = L4)
U6V = {"W_ARM_S5": (57.0, 25.6), "W_ARM_S2": (58.5, 25.85), "W_INLB_M": (57.5, 25.95), "W_INLC": (55.85, 24.2)}
via("W_ARM_S", U6V["W_ARM_S5"], POFV, "POFV U6.5")
via("W_ARM_S", U6V["W_ARM_S2"], POFV, "POFV U6.2")
via("W_INLB_M", U6V["W_INLB_M"], POFV, "POFV U6.4")
via("W_INLC", U6V["W_INLC"], POFV, "POFV U6.8")
# ARM_S: pins 5 / 2 joined on L3 under the rear row; pin 10 north on L4 (y 22.475 between the pad row and R47) to R19.1
# and a via at (55.3, 22.95) into the L3 net; L3 on to a via beside U14.4
tr("W_ARM_S", L3, [(57.0, 25.6), (57.0, 26.4), (58.5, 26.4), (58.5, 25.85)])
tr("W_ARM_S", L4, [(57.0, 23.26), (57.0, 22.475), (54.66, 22.475), (54.66, 22.9)])
via("W_ARM_S", (55.3, 22.95))
tr("W_ARM_S", L4, [(55.3, 22.475), (55.3, 22.95)])
tr("W_ARM_S", L3, [(55.3, 22.95), (57.0, 24.65), (57.0, 25.6)])
via("W_ARM_S", (55.2, 25.9))
tr("W_ARM_S", L3, [(55.3, 22.95), (54.75, 23.5), (54.75, 25.45), (55.2, 25.9)])
tr("W_ARM_S", L4, [(55.2, 25.9), (54.65, 25.9)])
# INLC: pin 8 via, L3 south then east along y 26.9 to its via beside C24
tr("W_INLC", L3, [(55.85, 24.2), (55.85, 26.9), (62.9, 26.9), (63.45, 27.45), (63.45, 28.18)])
# INLA: pin 3 south-east through the R9 | R10 gap (L4), a via below the gap, L3 east (y 28.9) to its via
tr("W_INLA", L4, [(58.0, 25.8), (58.0, 26.15), (58.53, 26.68), (58.53, 28.9)])
via("W_INLA", (58.53, 28.9))
tr("W_INLA", L3, [(58.53, 28.9), (61.2, 28.9), (61.25, 28.85)])
# INLB: pin 6 south-west through the R8 | R9 gap (L4), a via below it, L3 east along y 29.4 up to its via (the J4 ->
# R-row BAL hops cross both on L4)
tr("W_INLB", L4, [(56.5, 25.8), (56.5, 26.4), (56.05, 26.85), (56.05, 28.95), (55.75, 29.25), (55.75, 29.4)])
via("W_INLB", (55.75, 29.4))
tr("W_INLB", L3, [(55.75, 29.4), (61.65, 29.4), (62.25, 28.8), (62.25, 28.75)])
# INLA_M: pin 1 east, north past C40 (x 59.6), west along y 21.3 into R47.1 from the north
tr("W_INLA_M", L4, [(59.2, 24.7), (59.6, 24.7), (59.6, 21.3), (56.96, 21.3), (56.96, 21.8)])
# +3V3: pin 14 north to C40.1
tr("+3V3", L4, [(59.1, 24.2), (59.2, 24.1), (59.2, 22.1)], 0.2)
# INLC_M: pin 9 out of its south end, west along y 23.55 (between R19 and U14) into R49.1
tr("W_INLC_M", L4, [(56.5, 23.55), (56.2, 23.55), (52.95, 23.55), (52.6, 23.2)])
# GND: pins 12 / 13 / 7 to the thermal pad, stitching vias north of pin 13 and between U14 and U6
tr("GND", L4, [(58.0, 23.5), (58.0, 24.1)], 0.2)
tr("GND", L4, [(58.5, 23.5), (58.5, 23.55), (58.15, 23.9), (58.15, 24.1)], 0.2)
tr("GND", L4, [(56.2, 24.7), (56.9, 24.7)], 0.2)
tr("GND", L4, [(55.8, 24.7), (55.25, 24.4), (54.65, 24.4)], 0.2)
via("GND", (55.25, 24.4), RV)
# U14: W_ARM pin 2 straight up into TP6 (via in both pads), +3V3 pin 5 to C17.1
via("W_ARM", (54.0, 24.3), POFV, "POFV U14.2 / TP6")
tr("+3V3", L4, [(53.35, 25.9), (52.1, 25.9)], 0.2)

# ---------------------------------------------------------------- W_EN: TP7 -> R40.1 -> U2.33 on L1 (lane y 25.15)
tr("W_EN", F1, [(50.95, 22.25), (50.95, 22.9), (51.35, 23.3), (51.35, 24.2), (51.66, 24.51), (52.0, 24.51)])
tr("W_EN", F1, [(52.0, 24.51), (52.64, 25.15), (59.3, 25.15), (59.4, 25.25), (59.9, 25.25)])

# ---------------------------------------------------------------- U2 locals (L1)
route("U2_CPH", P("U2", 4), P("C20", 1), [F1], margin=1.5)
route("U2_CPL", P("U2", 3), P("C20", 2), [F1], margin=1.5)
route("U2_MODE", P("U2", 29), P("R44", 1), [F1], margin=1.5)
route("U2_IDRIVE", P("U2", 30), P("R45", 1), [F1], margin=1.5)
route("U2_VDS", P("U2", 31), P("R46", 1), [F1], margin=1.5)
route("U2_DVDD", P("U2", 36), P("C22", 1), [F1], margin=1.5)
tr("BUCK_CB", F1, [(64.25, 27.6), (64.25, 27.95), (64.45, 28.15), (64.45, 29.95), (64.1, 30.3)])
route("BUCK_SW", P("U2", 45), P("L1", 1), [F1], margin=2.0, w=0.2)
route("BUCK_SW", P("U2", 45), P("C28", 2), [F1], margin=2.0, w=0.2)
route("BUCK_SW", P("C28", 2), P("D2", 1), [F1], margin=2.0, w=0.2)
chain("BUCK_FB", [P("U2", 1), P("R20", 2), P("R21", 1)], [F1, L3, L4])
route("U2_VCP", P("U2", 5), P("C21", 1), [F1, L3, L4])
chain("BUCK_EN", [P("U2", 48), P("R4", 2), P("C10", 1)], [F1, L3, L4])
route("BUCK_EN", P("U2", 48), P("R5", 1), [F1, L3, L4])
route("ARM_AC", P("D9", 3), P("C15", 2), [L4], margin=1.5)


# ---------------------------------------------------------------- MCU legs (router)
# INLC_M: pin 21's inner end to a via under the MCU body (clear of C41 below), L3 east to R49
via("W_INLC_M", (40.0, 22.85))
tr("W_INLC_M", F1, [(39.75, 21.1), (39.75, 22.6), (40.0, 22.85)])
route("W_INLC_M", ("via", 40.0, 22.85), P("R49", 1), [L3, L4], margin=3.0)
chain("W_nFAULT", [P("U2", 28), P("TP9", 1), P("R42", 1), P("C19", 1)], margin=3.0)
route("W_nFAULT", P("R42", 1), P("U1", 20), margin=3.0)

# ---------------------------------------------------------------- CSA outputs (analog: L1 / L3)
route("W_SOA", P("U1", 12), P("U2", 25), margin=4.0)
route("W_SOB", P("U1", 17), P("U2", 24), margin=4.0)
route("W_SOC", P("U1", 13), P("U2", 23), margin=4.0)

route("W_INHA", ("pt", 37.0, 27.05, L3), P("U1", 44), [F1, L3], margin=2.0)
# W_EN / ARM_S leave pins 3 / 4 on L1 (L3 / L4 east of the MCU stay free for the region 2/3 analog runs)
route("W_EN", P("TP7", 1), P("U1", 3), [F1], margin=3.0)
# ARM_S: via at pin 4's tip, L3 east along y 28.4, a via below the R7 | R8 gap, L4 up the gap into U14.4
via("W_ARM_S", (44.7, 28.55)); via("W_ARM_S", (53.55, 28.4))
tr("W_ARM_S", F1, [(44.2, 28.5), (44.65, 28.5), (44.7, 28.55)])
tr("W_ARM_S", L3, [(44.7, 28.55), (44.85, 28.4), (53.55, 28.4)])
tr("W_ARM_S", L4, [(53.55, 28.4), (53.55, 27.3), (54.3, 26.55), (54.65, 26.3)])
route("W_INLA_M", P("R47", 1), P("U1", 37), margin=4.0)
# INLB_M: from pin 4's via on L1 down the C9 | C22 gap and west along y 28.85, the router takes it on to U1.46 on
# the MCU's west side; R48 (north of U6) joins the via in U6.4 through the router
tr("W_INLB_M", F1, [(57.5, 25.95), (57.15, 26.3), (57.15, 28.5), (56.8, 28.85), (46.0, 28.85)])
route("W_INLB_M", ("pt", 46.0, 28.85, F1), P("U1", 46), [F1, L3, L4], margin=4.0)
route("W_INLB_M", P("R48", 1), ("via", *U6V["W_INLB_M"]), margin=3.0)

route("W_ARM", P("TP6", 1), P("D9", 2), margin=3.0, avoid=[[L4, 44.0, 28.2, 60.4, 30.1, "tracks"]])
chain("W_ARM", [P("D9", 2), P("C16", 1), P("R41", 1)], margin=2.0)
chain("W_ARM_CLK", [P("J1", 19), P("R18", 1), P("C15", 1)], margin=2.0)
route("W_nFAULT", P("U1", 20), P("U7", 3), [F1, L3, L4], margin=3.0)
