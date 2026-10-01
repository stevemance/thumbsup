"""hDA: drive-area power-first rework (2026-10-01 rework brief), on hR.

Phase outputs R_A/R_B/R_C (U4 pins 13-20 -> JR1-3): the F corridor south of U4 is cleared:
- INA_nCS leaves its F run under U4's output pins: from its via (20.0, 26.75) it stays on L4 (y 27.5, between the EP
  keep-out and L_SOA) to a new via (25.85, 27.5) east of R_C's path, then F to its old via (27.75, 27.75).
- R111 (L_H2 series 1 k) moves out of the corridor to x 16.07 between J2 and JR1 (rot -90, pads >= 1 mm from JR1's
  pad: critic-2); L_H2 reaches it on F (y 29.4), L_H2B drops to L4 next to it and runs y 29.2 under the JR row
  (between the L3 +3V3 and L_INHA lanes, no stacking) to C111.1 (POFV to U9.3, unchanged).
- explicit R_A/R_B/R_C tracks (0.8 mm) from the pin pairs into the wire-hole pads."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9
n_ = v2_pre.n_


def move(ref, x, y, rot, side, rip=False):
    if rip:                              # only for parts whose stubs no rip_segs below already lists (double remove crashes)
        EDITS.append(dict(op="rip_ref", ref=ref))
    EDITS.append(dict(op="move", ref=ref, x=x, y=y, rot=rot, side=side))


# ------------------------------------------------------------------ phase corridor south of U4
EDITS.append(dict(op="rip_segs", tracks=[
    (n_("INA_nCS"), F1, (27.75, 27.75), (27.45, 27.45)), (n_("INA_nCS"), F1, (27.45, 27.45), (20.50, 27.45)),
    (n_("INA_nCS"), F1, (20.50, 27.45), (20.35, 27.30)), (n_("INA_nCS"), F1, (20.35, 27.30), (20.35, 27.10)),
    (n_("INA_nCS"), F1, (20.35, 27.10), (20.00, 26.75)),
    (n_("L_H2"), F1, (12.60, 29.40), (22.00, 29.40)), (n_("L_H2"), F1, (22.00, 29.40), (22.00, 29.10)),
    (n_("L_H2B"), F1, (23.00, 29.10), (23.00, 29.40)), (n_("L_H2B"), F1, (23.00, 29.40), (27.50, 29.40)),
    (n_("L_H2B"), F1, (27.50, 29.40), (28.45, 28.45)), (n_("L_H2B"), F1, (28.45, 28.45), (29.50, 28.45)),
]))
tr("INA_nCS", L4, [(20.0, 26.75), (20.0, 27.5), (25.6, 27.5)])
via("INA_nCS", (25.6, 27.5), PV, "INA_nCS L4 -> F east of R_C (west of the L3 +3V3 riser x 26.1)")
tr("INA_nCS", F1, [(25.6, 27.5), (27.45, 27.5), (27.75, 27.75)])

move("R111", 16.07, 29.6, -90, "F")
tr("L_H2", F1, [(12.6, 29.4), (15.8, 29.4), (16.07, 29.13)])
tr("L_H2B", F1, [(16.07, 30.11), (16.5, 30.45), (16.95, 30.45)])
via("L_H2B", (16.95, 30.45), PV, "R111.2 -> L4 lane under the JR row (south of the L3 lanes y 28.9-30.0)")
tr("L_H2B", L4, [(16.95, 30.45), (18.2, 29.2), (27.6, 29.2), (28.35, 28.45), (29.36, 28.45)])

# phase tracks: pin pairs joined at the toes, 0.8 mm into the wire-hole pads
for net, (pa, pb), path in (("R_A", (20.75, 21.25), [(21.0, 27.45), (19.6, 28.85), (18.9, 30.45)]),
                            ("R_B", (22.25, 22.75), [(22.5, 27.45), (22.5, 30.45)]),
                            ("R_C", (23.75, 24.25), [(24.0, 27.45), (25.1, 28.7), (25.95, 30.45)])):
    tr(net, F1, [(pa, 26.9), (pa, 27.45), (pb, 27.45), (pb, 26.9)], w=0.25)
    tr(net, F1, path, w=0.8)

# ------------------------------------------------------------------ U3's unused buck: R300 next to U3 (was beside U4, its
# SW/FB runs walled R_VM and L_VM).  R300 on the bottom under U3's north edge (PLACEMENT 5.1: the unused-buck R/C of
# U3/U4 go on the bottom), SW from pin 5's existing via, FB by a POFV on the existing L_FBBK riser x 13.95; C307 stays.
EDITS.append(dict(op="rip_segs", tracks=[
    (n_("L_FBBK"), F1, (13.95, 15.95), (22.95, 15.95)), (n_("L_FBBK"), F1, (22.95, 15.95), (23.18, 16.18)),
    (n_("L_FBBK"), F1, (23.18, 16.18), (23.18, 16.75)),
    (n_("L_SWBK"), L4, (10.85, 18.70), (14.20, 18.70)), (n_("L_SWBK"), L4, (14.20, 18.70), (15.50, 17.40)),
    (n_("L_SWBK"), L4, (15.50, 17.40), (15.50, 16.50)),
    (n_("L_SWBK"), F1, (15.50, 16.50), (15.65, 16.35)), (n_("L_SWBK"), F1, (15.65, 16.35), (21.00, 16.35)),
    (n_("L_SWBK"), F1, (21.00, 16.35), (21.40, 16.75)), (n_("L_SWBK"), F1, (21.40, 16.75), (21.53, 16.75)),
], vias=[(n_("L_SWBK"), (15.5, 16.5))]))
move("R300", 13.05, 19.0, 0, "B")
tr("L_SWBK", L4, [(10.85, 18.7), (12.0, 18.7)])
via("L_FBBK", (13.95, 19.0), POFV, "POFV R300.2 (B) on the L_FBBK riser")

# ------------------------------------------------------------------ R_VM (U4): north island R402.2 + C408 + C402 on F,
# joined to the pin island (U4.9-11, C400, C401, C403) by an L3 strip (1.0 mm, x 17.95-18.95, outside EP + 1.5)
# with 3 POFVs in C402.1 and 3 vias at the pins (C400.1, C401.1 POFVs + one in the F landing).
for c in ((18.575, 20.75), (18.575, 21.65)):
    via("R_VM", c, POFV, "POFV C402.1 -> L3 R_VM strip")
via("R_VM", (17.6, 21.2), POFV, "under C402's body (west of INA_nCS's L4 bend) -> L3 R_VM strip")
via("R_VM", (18.6, 24.775), POFV, "POFV C400.1 -> L3 R_VM strip")
via("R_VM", (18.6, 26.475), POFV, "POFV C401.1 -> L3 R_VM strip")
via("R_VM", (17.75, 25.65), PV, "R_VM landing -> L3 strip")
tr("R_VM", L3, [(18.45, 20.75), (18.45, 26.475)], w=1.0)
tr("R_VM", L3, [(18.575, 20.75), (18.45, 20.75)], w=0.4)
tr("R_VM", L3, [(17.6, 21.2), (18.2, 21.2)], w=0.4)
via("R_VM", (17.45, 20.25), POFV, "under C402's body -> L3 R_VM strip (4th at the north end)")
tr("R_VM", L3, [(17.45, 20.25), (17.95, 20.25), (18.2, 20.5)], w=0.4)
tr("R_VM", L3, [(18.6, 24.775), (18.45, 24.775)], w=0.4)
tr("R_VM", L3, [(18.6, 26.475), (18.45, 26.475)], w=0.4)
tr("R_VM", L3, [(17.75, 25.65), (18.2, 25.65)], w=0.4)
# R_CPH's L4 leg moves off the POFVs (x 18.9 -> 19.35)
EDITS.append(dict(op="rip_segs", tracks=[
    (n_("R_CPH"), L4, (19.44, 23.60), (18.90, 24.14)), (n_("R_CPH"), L4, (18.90, 24.14), (18.90, 26.70)),
    (n_("R_CPH"), L4, (18.90, 26.70), (17.72, 27.50))]))
tr("R_CPH", L4, [(19.44, 23.6), (19.35, 23.69), (19.35, 26.85), (18.7, 27.5), (17.72, 27.5)])

# ------------------------------------------------------------------ L_VM (U3): R302.2 -> C308 (moved 0.4 toward U3) -> the
# column west of C301 -> C301/C300 and the pins on F; C302 (north-east, 2.6 mm) and C303.2 join by an L3 strip
# (y 19.9-20.8, under the EP + 1.5 edge) with 3 POFVs in C302.1 and POFVs in C301.1, C300.1, C303.2.
move("C308", 3.75, 16.3, 90, "F")
EDITS.append(dict(op="drop", pad=("C308", "2"), net="GND"))
for c in ((11.0, 20.6), (12.45, 20.05), (13.4, 20.3)):           # clear of +3V3's L4 diagonal under C302.1
    via("L_VM", c, POFV, "POFV C302.1 -> L3 L_VM strip")
via("L_VM", (6.5, 20.43), POFV, "POFV C301.1 -> L3 L_VM strip")
via("L_VM", (7.75, 20.45), POFV, "POFV C300.1 (west edge, clear of L_CP's L4 leg) -> L3 L_VM strip")
via("L_VM", (9.45, 18.4), POFV, "POFV C303.2 -> L3 L_VM strip")
tr("L_VM", L3, [(6.5, 20.35), (13.4, 20.35)], w=0.9)
tr("L_VM", L3, [(9.45, 18.4), (8.95, 18.9), (8.95, 20.0)], w=0.3)
# L_VSRC (JP1.2 -> U11) leaves the column: F west of JBAT2 / C308 along the left edge, L4 from y 18.6
EDITS.append(dict(op="rip", box=(5.0, 9.0, 8.0, 22.3), nets=[n_("L_VSRC")], layers=[F1]))
EDITS.append(dict(op="rip_segs", tracks=[], vias=[(n_("L_VSRC"), (5.65, 22.05))]))
tr("L_VSRC", F1, [(7.6, 9.55), (6.6, 9.55), (6.1, 10.05), (6.1, 10.8), (5.8, 11.1), (1.6, 11.1), (1.2, 11.5),
                   (1.2, 18.6)])
via("L_VSRC", (1.2, 18.6), PV, "L_VSRC F -> L4 north of JL1")
tr("L_VSRC", L4, [(1.2, 18.6), (1.35, 18.75), (5.35, 18.75), (5.65, 19.05), (5.65, 22.05)])
# VBAT side of R302: POFVs into the L3 VBAT band (y < 16) - the L3 VBAT pour itself is the power agents' work
for c in ((12.46, 12.9), (12.46, 13.9), (12.46, 14.9)):
    via("VBAT", c, POFV, "POFV R302.1 -> L3 VBAT band")
