"""r2 stage 1: U2's east side and the 5 V buck (DESIGN 6.7), on top of r2_drive.  Explicit copper (kicad/v2 spec.py r2
block has the placement):

  - U2 east pins 7..1 leave east as a staircase: VBAT 6/7 straight into C24.1; VCP (5) under C24 into C21.1; CPH (4)
    past C24 and down into C20.1; CPL (3) down into C20.2; GND (2) into the exposed pad; FB (1) through a via in the
    pad's outer end (POFV) to the FB divider R21/R20 on the bottom (R20's +5V by an L3 hop from C29).
  - Rear pins 44/45/47 go south under J4's front edge and east: VIN (y 28.3) into C27.1 (VBAT via for R4 on the
    bottom), SW (y 29.0) up into L1's SW pad (D2's cathode and C28's SW pad right above it), CB (y 29.55) on past L1
    and north through L1's and D2's pad gaps to C28's CB pad.  EN (48) through a via in the pad's outer end (POFV) to
    R4/R5/C10 on the bottom.
  - Output: C29.1 to L1.2 through D2's pad gap; C29.2 / D2.2 GND joined; C21.2 VBAT joined to C27.1 VBAT.
Layers F.Cu = L1, In2.Cu = L3, B.Cu = L4."""
import os

import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9

# ---------------------------------------------------------------- U2 east pins
tr("VBAT", F1, [(67.2, 23.75), (67.98, 23.75)], 0.2)
tr("VBAT", F1, [(67.2, 24.25), (67.98, 24.25)], 0.2)
tr("U2_VCP", F1, [(67.2, 24.75), (67.4, 24.85), (71.555, 24.85), (71.555, 24.45)])
tr("U2_CPH", F1, [(67.2, 25.25), (70.0, 25.25), (70.0, 26.45)])
tr("U2_CPL", F1, [(67.2, 25.75), (68.1, 25.75), (68.43, 26.08), (68.43, 26.45)])
tr("GND", F1, [(66.7, 26.25), (65.8, 26.25)], 0.2)
tr("GND", F1, [(63.75, 27.2), (63.75, 26.35)], 0.2)
# FB: via in pin 1's outer end, FB divider on the bottom west of U8
via("BUCK_FB", (67.2, 26.75), POFV, "POFV U2.1")
tr("BUCK_FB", L4, [(67.2, 26.75), (67.45, 26.3)])
tr("BUCK_FB", L4, [(67.28, 26.11), (66.85, 25.85), (66.85, 24.3), (67.28, 24.06)])
tr("GND", L4, [(67.92, 25.09), (68.6, 25.09), (68.6, 24.0), (68.97, 24.0)], 0.2)        # R21.2 -> U8 pin 6 (GND)
tr("+5V", L4, [(67.6, 22.77), (67.7, 22.4), (67.7, 20.4)], 0.2)                      # R20.1 north to a via
via("+5V", (67.7, 20.4), RV)
route("+5V", ("via", 67.7, 20.4), P("C29", 1), [L3, F1], margin=2.0, w=0.2, layer_cost={F1: 3.0})
# ---------------------------------------------------------------- rear pins 44-48
via("BUCK_EN", (66.25, 27.65), POFV, "POFV U2.48")
tr("BUCK_EN", L4, [(66.25, 27.65), (67.075, 27.85)])
tr("BUCK_EN", L4, [(66.25, 27.65), (65.53, 27.75)])
tr("BUCK_EN", L4, [(66.25, 27.65), (66.25, 28.0)])
tr("VBAT", F1, [(65.75, 27.7), (65.75, 28.3), (71.65, 28.3), (71.65, 27.75)], 0.3)
via("VBAT", (69.9, 28.3), RV)
tr("VBAT", L4, [(69.9, 28.3), (69.45, 28.0)], 0.2)
tr("VBAT", F1, [(73.1, 24.5), (73.1, 25.0), (71.9, 26.2), (71.65, 26.45)], 0.3)
tr("BUCK_SW", F1, [(64.75, 27.7), (64.75, 29.0), (75.9, 29.0), (75.9, 27.8)], 0.4)
tr("BUCK_SW", F1, [(75.85, 22.9), (75.9, 23.85)], 0.6)
tr("BUCK_SW", F1, [(74.4, 22.5), (75.3, 22.5)], 0.3)
tr("BUCK_CB", F1, [(64.25, 27.7), (64.25, 29.55), (76.85, 29.55), (76.85, 21.3), (74.4, 21.3)], 0.2)
# ---------------------------------------------------------------- output
tr("+5V", F1, [(77.2, 20.8), (77.6, 21.2), (77.6, 23.4), (78.0, 23.8)], 0.4)
tr("GND", F1, [(78.645, 21.8), (78.75, 20.8)], 0.6)
