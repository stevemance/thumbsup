"""r2 stage: BMS (U8 bottom in front of J4) local nets on top of r2_u2east: BALx (J4 -> series R), CELLx (series R ->
U8 + ladder caps), BMS_REG, BMS_BAT (R11 -> U8; C9 on the top west of J4 joined later with the rear bus).
All of it is bottom-side copper (the parts are on the bottom): cell lines are short L4 hops (the analog-on-L3 rule is for
runs; these are bottom-pad hops), crossings with the other BMS lines allowed (the BMS nets are DC, RC-filtered)."""
import os

import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401
import r2_auto as A

v2_pre.VIA_PITCH = 0.9
v2_pre.STACK_PEN = 8.0
BASE = os.environ.get("R2_BASE", "r2_u2east")
# explicit core of the cell ladder (U8 rot 90 at (71.1, 22.5), C7 at the east pins, C5 / C6 between U8 and the R row)
tr("CELL4", L4, [(73.1, 22.5), (73.9, 22.4)])                                   # pin 18 -> C7.1
tr("CELL3", L4, [(73.1, 23.5), (73.9, 23.65)])                                  # pin 20 -> C7.2
tr("CELL3", L4, [(73.1, 23.0), (73.45, 23.3), (73.45, 23.5)])                   # pin 19 -> pin 20's lead
tr("CELL3", L4, [(74.3, 24.3), (74.3, 24.65), (74.95, 25.3)])                   # C7.2 -> C6.1
tr("CELL3", L4, [(75.175, 26.2), (75.22, 26.8)])                                # C6.1 -> R9.2
tr("CELL2", L4, [(71.6, 24.6), (71.75, 25.3)])                                  # pins 2 / 1 -> C5.1
tr("CELL2", L4, [(72.1, 24.6), (72.1, 25.3)])
tr("CELL2", L4, [(72.45, 25.75), (73.2, 25.75)])                                # C5.1 -> C6.2
tr("CELL2", L4, [(72.05, 26.2), (72.07, 26.8)])                                 # C5.1 -> R8.2
tr("CELL1", L4, [(70.6, 24.6), (70.5, 25.3)])                                   # pins 4 / 3 -> C5.2
tr("CELL1", L4, [(71.1, 24.6), (70.85, 25.3)])
tr("CELL1", L4, [(70.5, 26.2), (70.6, 26.8)])                                   # C5.2 -> R7.2
tr("CELL4", L4, [(76.4, 26.8), (76.4, 26.6), (75.875, 26.075), (75.875, 22.75), (75.5, 22.4), (74.7, 22.4)])   # R10.2 -> C7.1
tr("BMS_REG", L4, [(72.1, 20.4), (72.4, 19.9), (72.6, 19.75)])                  # pin 15 -> C11.1
NETS = ["BAL1", "BAL2", "BAL3", "BAL4", "CELL1", "CELL2", "CELL3", "CELL4", "BMS_REG", "CELL0", "BAL0", "BMS_BAT"]
A.route_opens(BASE, NETS, margin=4.0, no_shadow=True, layers=[L4, L3])
A.route_opens(BASE, NETS, margin=9.0, no_shadow=True, layers=[L4, L3], retry=True)
