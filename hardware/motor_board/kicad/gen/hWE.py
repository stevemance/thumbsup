"""hWE: east-area power-first rework (2026-10-01, on hR).
- buck re-placed tight at U2's rear-east corner (DESIGN 6.7, review power-4 / signal-6): C27 (VIN) at the corner beside
  pin 47, D2 anode next to C27's GND, L1 above D2's cathode, C28 beside the SW node, C29 on L1's output pad;
  VIN / SW / CB leave pins 47 / 45 / 44 south and run east under J4's body side by side (the go and return of the hot
  loop together); C20 (CP) at pins 3/4, C24 / C21 one column east on the VM trace
- VBAT for U2 (review signal-2): C26.1 (cell B drain cap) -> L1 gap east of C26 -> via -> L4 spine west of the BMS
  vias -> via on the VM trace at pins 6/7 (VDRAIN Kelvin to a high-side drain point) -> L3 -> the VIN / R4 via
"""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9
n_ = v2_pre.n_


def move(ref, x, y, rot, side="F"):
    EDITS.append(dict(op="move", ref=ref, x=x, y=y, rot=rot, side=side))


# ---------------------------------------------------------------- rips
EDITS.append(dict(op="rip", box=(64.0, 20.9, 80.0, 30.0), nets=[n_(x) for x in ("BUCK_SW", "BUCK_CB", "U2_CPH", "U2_CPL", "U2_VCP")],
                  layers=[F1], reroute=False))
EDITS.append(dict(op="rip", box=(65.0, 23.0, 74.0, 29.0), nets=[n_("VBAT")], layers=[F1], reroute=False))
EDITS.append(dict(op="rip", box=(75.5, 19.8, 80.0, 28.2), nets=[n_("+5V")], layers=[F1], reroute=False))
EDITS.append(dict(op="rip_segs", tracks=[("GND", F1, (78.64, 21.8), (78.75, 20.8)),
                                         (n_("BMS_BAT"), L3, (70.6, 23.55), (69.5, 23.55)),
                                         (n_("BMS_BAT"), L3, (69.5, 23.55), (68.45, 24.6)),
                                         (n_("BMS_BAT"), L3, (68.45, 24.6), (68.45, 32.28))], vias=[]))
# the BMS cell hops under the new buck / U2 caps: re-joined by the router on L3 / L4
EDITS.append(dict(op="rip", box=(69.0, 20.5, 75.3, 28.5), nets=[n_("CELL0")], layers=[L3], reroute=False))
EDITS.append(dict(op="rip", box=(69.0, 24.0, 73.5, 28.5), nets=[n_("CELL1")], layers=[L3], reroute=False))
EDITS.append(dict(op="rip", box=(69.5, 24.5, 70.0, 25.75), nets=[n_("CELL0")], layers=[L4], reroute=False))
EDITS.append(dict(op="rip", box=(72.7, 28.0, 73.25, 28.62), nets=[n_("CELL0")], layers=[L4], reroute=False))
EDITS.append(dict(op="rip", box=(72.6, 26.5, 73.28, 27.18), nets=[n_("CELL1")], layers=[L4], reroute=False))
EDITS.append(dict(op="rip_segs", tracks=[(n_("CELL1"), L4, (71.15, 25.75), (70.47, 25.75))],
                  vias=[(n_("CELL0"), (69.55, 25.7)), (n_("CELL1"), (71.15, 25.75)),
                        (n_("CELL1"), (72.65, 26.55)), (n_("CELL0"), (72.75, 28.1))]))

# ---------------------------------------------------------------- placement
move("C20", 69.205, 25.34, 0)        # CPH west at pin 4, CPL east (pin 3 runs under the west pad)
move("C27", 69.43, 27.15, 0)         # VIN west at the corner, GND east
move("C24", 72.26, 23.54, 180)       # VM bypass: GND west, VBAT east (VM trace below it)
move("C21", 72.26, 25.10, 0)         # VCP west, VBAT east (VM trace above it)
move("D2", 73.475, 27.03, 180)       # anode west (next to C27 GND), cathode east under L1.1
move("L1", 76.145, 23.53, 0)
move("C28", 77.305, 27.395, 180)     # SW west (beside D2.K), CB east

# ---------------------------------------------------------------- U2 east copper
tr("VBAT", F1, [(67.2, 23.75), (67.6, 24.3)], w=0.2)
tr("VBAT", F1, [(67.2, 24.25), (67.6, 24.3)], w=0.2)
tr("VBAT", F1, [(67.6, 24.3), (73.035, 24.3)], w=0.2)          # VM / VDRAIN trace between C24 and C21
tr("VBAT", F1, [(73.035, 23.54), (73.035, 25.1)], w=0.6)
via("VBAT", (68.45, 24.17), RV, "VBAT feed onto the VM trace")
tr("U2_VCP", F1, [(67.2, 24.75), (67.45, 24.65), (71.3, 24.65)], w=0.15)
tr("U2_CPH", F1, [(67.2, 25.25), (68.43, 25.25)], w=0.2)
tr("U2_CPL", F1, [(67.2, 25.75), (67.38, 25.75), (67.68, 26.05), (69.98, 26.05), (69.98, 25.34)], w=0.15)

# ---------------------------------------------------------------- buck
tr("VBAT", F1, [(65.75, 27.6), (65.75, 28.3)], w=0.3)
tr("VBAT", F1, [(65.75, 28.3), (69.9, 28.3)], w=0.5)
tr("VBAT", F1, [(68.48, 27.6), (68.48, 28.1)], w=0.6)
tr("BUCK_SW", F1, [(64.75, 27.6), (64.75, 28.7), (65.05, 29.0)], w=0.25)
tr("BUCK_SW", F1, [(65.05, 29.0), (74.875, 29.0)], w=0.6)
tr("BUCK_SW", F1, [(74.875, 29.0), (74.875, 27.03)], w=0.6)
tr("BUCK_SW", F1, [(74.875, 27.03), (74.875, 25.2)], w=1.0)
tr("BUCK_SW", F1, [(74.875, 27.2), (76.53, 27.2)], w=0.6)
tr("BUCK_CB", F1, [(64.25, 27.6), (64.25, 29.65), (78.08, 29.65), (78.08, 27.395)], w=0.25)
tr("GND", F1, [(70.38, 27.15), (72.075, 27.03)], w=0.8)
via("GND", (71.35, 26.8), PV, "hot-loop GND (C27.2 / D2.A) to L2")
via("GND", (78.2, 19.15), PV, "C29 GND to L2")
tr("GND", F1, [(78.2, 19.15), (78.5, 19.5)], w=0.4)
tr("+5V", F1, [(77.1, 20.5), (77.1, 21.8)], w=0.6)
tr("+5V", F1, [(75.9, 19.95), (76.6, 20.1)], w=0.3)
tr("+5V", F1, [(77.9, 25.3), (78.4, 26.3), (79.5, 26.3), (79.85, 26.65), (79.85, 28.05), (79.95, 28.15), (81.4, 28.15)], w=0.2)

# ---------------------------------------------------------------- VBAT feed
tr("VBAT", F1, [(68.6, 14.0), (69.75, 14.0), (69.75, 16.85)], w=0.6)
via("VBAT", (69.75, 16.85), RV, "VBAT feed: L1 gap east of C26 -> L4")
tr("VBAT", L4, [(69.75, 16.85), (67.275, 16.85), (67.275, 19.7), (66.98, 20.0), (66.98, 23.55)], w=0.2)
tr("VBAT", L4, [(66.98, 23.55), (68.2, 23.55)], w=0.15)
tr("VBAT", L4, [(68.2, 23.55), (68.45, 23.8), (68.45, 24.17)], w=0.2)
tr("VBAT", L3, [(68.45, 24.17), (67.85, 24.77), (67.85, 28.0), (68.15, 28.3), (69.9, 28.3)], w=0.3)

# ---------------------------------------------------------------- BMS_BAT around the feed
tr("BMS_BAT", L3, [(70.6, 23.55), (70.2, 23.15), (67.0, 23.15), (66.7, 23.45), (66.7, 29.2), (67.3, 29.8), (68.45, 29.8), (68.45, 32.28)])

# ---------------------------------------------------------------- BMS cell hops re-done (vias clear of the new top copper)
# CELL1: C5.2 -> via beside C21 / D2.A -> L3 -> via in C4.1 (POFV, under D2's body)
tr("CELL1", L4, [(70.475, 25.75), (70.9, 26.0), (71.2, 26.0)])
via("CELL1", (71.2, 26.0), PV, "CELL1 hop west")
tr("CELL1", L3, [(71.2, 26.0), (72.9, 26.0), (73.3, 26.4), (73.3, 26.95)])
via("CELL1", (73.3, 26.95), POFV, "CELL1 hop east, in C4.1's pad")
# CELL0: west branch (L4, U8.5 / R6 / D5) -> via under C27's body -> L3 -> via by C4.2 -> L3 north -> C8's via
tr("CELL0", L4, [(68.75, 26.75), (69.43, 26.95)])
via("CELL0", (69.43, 26.95), PV, "CELL0 hop west, under C27's body")
tr("CELL0", L3, [(69.43, 26.95), (69.93, 27.45), (73.4, 27.45), (73.95, 28.0)])
via("CELL0", (73.95, 28.0), PV, "CELL0 at C4.2")
tr("CELL0", L4, [(73.95, 28.0), (73.3, 28.755)])
tr("CELL0", L3, [(73.95, 28.0), (73.95, 23.5), (74.45, 23.0), (76.3, 23.0)])


# ---------------------------------------------------------------- C117 (BMS_BAT bypass) at U8.16/17 (review netlist-3 / power-6)
# the pocket east of U8's BAT pins: C11 up 0.05, C7 down 0.05, CELL0's C8 hop via and the +5V via (C29) moved out of it
EDITS.append(dict(op="rip", box=(73.1, 17.5, 76.0, 21.0), nets=[n_("BMS_BAT")], layers=[L4], reroute=False))
EDITS.append(dict(op="rip_segs", tracks=[
    (n_("CELL0"), L4, (75.4, 20.83), (75.72, 21.2)), (n_("CELL0"), L4, (75.72, 21.2), (77.4, 21.2)),
    (n_("CELL0"), L4, (77.4, 21.2), (77.7, 21.5)), (n_("CELL0"), L4, (77.7, 21.5), (77.7, 24.3)),
    (n_("+5V"), L3, (76.1, 20.25), (75.85, 20.0))],
    vias=[(n_("CELL0"), (75.4, 20.83)), (n_("+5V"), (76.1, 20.25))]))
move("C11", 73.4, 19.25, 0, "B")
move("C7", 74.3, 23.15, -90, "B")
move("C117", 75.075, 20.83, 0, "B")
tr("BMS_BAT", L4, [(73.0, 21.15), (73.6, 20.83), (74.3, 20.83)])
via("GND", (76.0, 21.75), PV, "C117 GND")
tr("GND", L4, [(75.85, 21.2), (76.0, 21.75)], w=0.25)
via("CELL0", (76.3, 23.0), PV, "CELL0 hop to C8 (between L1's pads)")
tr("CELL0", L4, [(76.3, 23.0), (77.4, 23.0), (77.7, 23.3), (77.7, 24.3)])
via("+5V", (75.9, 19.95), RV, "C29 +5V to the L3 lane")
tr("+5V", L3, [(75.9, 19.95), (75.85, 20.0)], w=0.2)
