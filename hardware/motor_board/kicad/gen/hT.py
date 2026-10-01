"""hT: divider taps on hWE: the weapon phase-voltage tops R22 / R24 / R26 (68 k, W_x -> W_Vx) and the VBAT divider top
R63 (68 k, VBAT -> VBAT_SNS).

The W_x phase copper and VBAT reach the MCU front pocket only along the lanes behind the shunt row: the SHx sense lanes to
U2 run east-west in a solid F / L4 bundle and the pocket was closed on L3 by R_S3 (y 17.42), the +5V stub, W_INLC_M's
diagonal and W_NTC's staircase.  Plan:
- R_S3's L3 lane moves to the front edge of the L3 signal area (y 16.39, behind the VBAT band, in front of the NTx / VBAT
  via row); the L3 corridor between that via row and the +5V stub (y 18.6) then carries VBAT (y 17.4, from the VBAT via
  (69.75, 16.85) of the east VBAT feed) and W_A (y 17.72; y 17.5 past W_SNA's via, from the big via (77.65, 17.95) of
  W_A's L4 lane).  W_B: a via on its F lane at U2.16 (64.75, 19.5) -> L3 y 18.95; W_C: its L4 lane's via at U2.19
  (63.25, 20.3) -> L3 y 19.25 (between the +5V stub and W_SOB / W_SOC).  All four are 0.15 mm (no current).
- The four 68 k tops stand in one row in front of W_SOB's F lane (R63, R22, R24, R26 at x 46.26 .. 49.11), pad 1 north
  on its tap via (via in pad), pad 2 onto the existing W_VA (F) / W_VB (F -> L3) / W_VC (F) / VBAT_SNS (L3 hub) copper.
  The 68 k sits at the MCU end, so the long runs are W_x / VBAT on L3 over the bundle's phase / gate / Kelvin lanes and
  beside the push-pull R_S3, +5V and BMS lanes; no W_x run is next to an analog net (W_SOB / W_SOC are on F above L2 there).
- W_NTC (L3) threads between the row's pad-1 and pad-2 vias (y 20.91) and climbs to its via (44.2, 20.25) west of it.
- W_INLC_M's L3 diagonal / F column through the pocket and W_nFAULT's L4 wiggle are ripped: W_INLC_M runs on L4 (x 45.4
  down, y 20.93 east, under W_NTC's lane: digital over analog, 4 mm, see report) and hops to F over W_NTC at (49.9, 21.75);
  W_nFAULT runs straight on L4 (y 19.75) to U2's side; TP9 stays (via in pad); R42 / C19 move beside U2.28's W_nFAULT copper.
"""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9
n_ = v2_pre.n_


def move(ref, x, y, rot, side="F"):
    EDITS.append(dict(op="move", ref=ref, x=x, y=y, rot=rot, side=side))


# ---------------------------------------------------------------- rips
# R_S3's L3 lane (y 17.42) and its east leg (redrawn below)
EDITS.append(dict(op="rip", box=(44.55, 17.35, 80.35, 17.65), nets=[n_("R_S3")], layers=[L3], reroute=False))
# W_INLC_M through the pocket: L3 diagonal, the F column and its top via
EDITS.append(dict(op="rip", box=(45.45, 18.15, 49.95, 20.9), nets=[n_("W_INLC_M")], layers=[L3], reroute=False))
EDITS.append(dict(op="rip_segs", tracks=[(n_("W_INLC_M"), F1, (49.9, 20.85), (49.9, 22.75))],
                  vias=[(n_("W_INLC_M"), (49.9, 20.85))]))
# W_nFAULT: the L4 wiggle (46.3, 19.15) -> (52.8, 20.2) and the F stub to TP9 (+ its via)
EDITS.append(dict(op="rip", box=(46.25, 19.1, 52.85, 20.75), nets=[n_("W_nFAULT")], layers=[L4], reroute=False))
EDITS.append(dict(op="rip", box=(48.85, 20.3, 51.05, 20.65), nets=[n_("W_nFAULT")], layers=[F1], reroute=False))
EDITS.append(dict(op="rip_segs", tracks=[], vias=[(n_("W_nFAULT"), (48.9, 20.35))]))
# R42's +3V3 feed (R42 moves)
EDITS.append(dict(op="rip", box=(44.0, 20.7, 46.4, 21.95), nets=["+3V3"], layers=[L4], reroute=False))
# W_NTC's L3 staircase and its lane west of x 48.35 (the lane is redrawn from x 65.9)
EDITS.append(dict(op="rip", box=(44.15, 20.2, 48.4, 21.35), nets=[n_("W_NTC")], layers=[L3], reroute=False))
# divider pad stubs at the old R22 / R24 / R26 spots, W_VB's L3 east end + via, R63's old (bottom) VBAT_SNS stub
EDITS.append(dict(op="rip", box=(45.4, 20.55, 47.1, 21.1), nets=[n_("W_VA")], layers=[F1], reroute=False))
EDITS.append(dict(op="rip", box=(46.45, 21.65, 47.0, 21.9), nets=[n_("W_VB")], layers=[F1], reroute=False))
EDITS.append(dict(op="rip_segs", tracks=[(n_("W_VB"), L3, (46.5, 21.7), (44.15, 21.7))], vias=[(n_("W_VB"), (46.5, 21.7))]))
EDITS.append(dict(op="rip", box=(48.05, 22.0, 49.25, 22.55), nets=[n_("W_VC")], layers=[F1], reroute=False))
EDITS.append(dict(op="rip", box=(42.4, 24.3, 42.8, 24.8), nets=[n_("VBAT_SNS")], layers=[L4], reroute=False))

# ---------------------------------------------------------------- R_S3 at the front edge of the L3 signal area
tr("R_S3", L3, [(44.6, 17.6), (45.81, 16.39), (80.3, 16.39), (80.3, 25.6)])

# ---------------------------------------------------------------- divider row (68 k tops, pad 1 north on the tap via)
VY = 20.4
XV, XA, XB, XC = 46.26, 47.21, 48.16, 49.11
for ref, x in (("R63", XV), ("R22", XA), ("R24", XB), ("R26", XC)):
    move(ref, x, VY + 0.51, -90)
via("VBAT", (XV, VY), POFV, "R63.1 (VBAT tap)")
via("W_A", (XA, VY), POFV, "R22.1 (W_A tap)")
via("W_B", (XB, VY), POFV, "R24.1 (W_B tap)")
via("W_C", (XC, VY), POFV, "R26.1 (W_C tap)")


def diag_x(x, y):
    """x where a 45-degree run from the via (x, VY) reaches lane height y"""
    return x + VY - y


# VBAT: the VBAT via of the east feed (69.75, 16.85) -> L3 y 17.4 -> R63.1
tr("VBAT", L3, [(69.75, 16.85), (69.2, 17.4), (diag_x(XV, 17.4), 17.4), (XV, VY)])
# W_A: big via of its L4 lane -> L3 y 17.5 (past W_SNA's via) / 17.72 -> R22.1
tr("W_A", L3, [(77.65, 17.95), (77.2, 17.5), (71.9, 17.5), (71.68, 17.72), (diag_x(XA, 17.72), 17.72), (XA, VY)])
# W_B: via on its F lane at U2.16 -> L3 y 18.95 -> R24.1
via("W_B", (64.75, 19.5), PV, "W_B tap off the U2.16 lane")
tr("W_B", L3, [(64.75, 19.5), (64.2, 18.95), (diag_x(XB, 18.95), 18.95), (XB, VY)])
# W_C: its L4 lane's via at U2.19 -> L3 y 19.25 -> R26.1
tr("W_C", L3, [(63.25, 20.3), (63.25, 19.6), (62.9, 19.25), (diag_x(XC, 19.25), 19.25), (XC, VY)])

# W_NTC between the row's pad-1 and pad-2 vias, up to its via west of the row
tr("W_NTC", L3, [(65.9, 21.3), (50.6, 21.3), (50.21, 20.91), (44.6, 20.91), (44.2, 20.51), (44.2, 20.25)])

# pad-2 legs
tr("W_VA", F1, [(45.35, 21.05), (45.7, 20.91), (46.75, 20.91), (46.95, 21.15), (XA, VY + 1.02)])
tr("W_VB", F1, [(XB, VY + 1.29), (47.9, 21.95), (45.5, 21.95), (45.25, 21.7)])
via("W_VB", (45.25, 21.7), PV, "W_VB F leg -> its L3 lane")
tr("W_VB", L3, [(45.25, 21.7), (44.15, 21.7)])
tr("W_VC", F1, [(XC, VY + 1.02), (XC, 22.2), (48.6, 22.65), (48.0, 22.65)])
via("VBAT_SNS", (XV, VY + 1.02), POFV, "R63.2 -> L3 VBAT_SNS")
tr("VBAT_SNS", L3, [(XV, VY + 1.02), (XV, 22.6), (46.45, 22.8)])

# ---------------------------------------------------------------- W_nFAULT: straight L4 lane, TP9 via in pad, R42 / C19 at U2
tr("W_nFAULT", L4, [(46.3, 19.15), (46.3, 19.75), (52.3, 19.75), (52.8, 20.2)])
via("W_nFAULT", (50.9, 20.3), POFV, "TP9 (in pad)")
tr("W_nFAULT", L4, [(50.9, 20.3), (50.9, 19.75)])
move("R42", 57.5, 21.4, 0, "B")
move("C19", 57.5, 22.35, 0, "B")
tr("W_nFAULT", L4, [(56.99, 21.4), (57.0, 23.4)])
tr("+3V3", L4, [(58.01, 21.4), (57.75, 20.75)])
EDITS.append(dict(op="drop", pad=("C19", "2"), net="GND"))

# ---------------------------------------------------------------- W_INLC_M re-joined on L4 (digital), F hop over W_NTC
# its F escape row (y 18.1) ends at the via (45.4, 18.1); L4 down between C44 and R42's old spot, east between the divider
# row's pad-1 vias and R63.2's via / D9, up at (49.9, 21.75) onto the old F column's lower half -> the via (49.9, 22.75)
tr("W_INLC_M", L4, [(45.4, 18.1), (45.4, 20.73), (45.6, 20.93), (49.6, 20.93), (49.9, 21.23), (49.9, 21.75)])
via("W_INLC_M", (49.9, 21.75), PV, "W_INLC_M L4 -> F over W_NTC")
tr("W_INLC_M", F1, [(49.9, 21.75), (49.9, 22.75)])
