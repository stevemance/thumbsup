"""h1: hand-planned long nets on r2_senr (+ sensor timer swap, h0).  See kicad/v2/r2/h1_plan.md."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9

# ======================================================================= A. MCU west weapon pins -> L3 under the MCU
# PB15 / PA10 / PA12 (TIM1 CH3N / CH3 / CH2N) are on the west edge; the bottom under the west pins carries the drive's
# L_SOA / L_SOB lanes, so these go inward on L1 between the drive's west-pin escapes and drop to L3 inside the body.
# (the bottom under the MCU is a parts farm: via spots from a clearance scan, r2/probe.py scan)
# The five weapon lines leave the MCU on L3 in the order U2 / U6 need them (north -> south: INHB, INHA, INHC, INLB_M,
# INLA_M): INHA and INLB_M drop right inside the west pins, INLA_M crosses over them on L1 to a via further south, and
# INHC (an east pin) comes in from the east side to a via between them (lanes: h3).
via("W_INHA", (35.2, 28.3))
route("W_INHA", P("U1", 44), ("via", 35.2, 28.3), [F1], margin=2.5, via_cost=99)
tr("W_INLB_M", F1, [(32.33, 29.0), (35.6, 29.0)])
via("W_INLB_M", (35.6, 29.0))
via("W_INLA_M", (38.5, 29.9))
route("W_INLA_M", P("U1", 37), ("via", 38.5, 29.9), [F1], margin=3.5, via_cost=99)
via("W_INHC", (39.9, 27.2))
tr("W_INHC", F1, [(43.67, 26.5), (42.6, 26.5), (39.9, 27.2)])
# W_INLB_M's pull-down R48 on top beside pin 46 (west stub), out of U6's crowded input channel
EDITS.append(dict(op="move", ref="R48", x=30.4, y=29.6, rot=270, side="F"))
tr("W_INLB_M", F1, [(32.33, 29.0), (30.72, 29.0)])
via("W_INHB", (45.8, 26.2))
tr("W_INHB", F1, [(43.67, 26.0), (45.4, 26.0), (45.6, 26.2), (45.8, 26.2)])

# ======================================================================= B. MCU rear row
# SWD (PA13/PA14, fixed): via in the pad (POFV, staggered) -> two L4 lanes under the rear pins, east to J1 / TPs
via("SWDIO", (34.25, 31.5), POFV, "POFV U1.49")
via("SWCLK", (34.75, 32.4), POFV, "POFV U1.50")
tr("SWDIO", L4, [(34.25, 31.5), (34.25, 32.85), (43.5, 32.85)])
tr("SWCLK", L4, [(34.75, 32.4), (34.92, 32.57), (43.5, 32.57)])
# east-going rear pins 57-60 drop off their tips onto four L1 lanes behind the row (below L_INHC's via)
for net, x, y in (("MB_RX", 39.75, 33.72), ("MB_TX", 39.25, 34.0), ("R_S2", 38.75, 34.28), ("R_S1", 38.25, 34.56)):
    tr(net, F1, [(x, 31.93), (x, y - 0.2), (x + 0.2, y), (46.0, y)])
