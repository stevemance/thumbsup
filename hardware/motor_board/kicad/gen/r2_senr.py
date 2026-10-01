"""r2 stage: right sensor front end under J3 (bottom), on top of r2_bms.  J3 (top, SMD) pins 6..1 drop to a via column
at x 82.3 (1.0 mm pitch, between J3's contact pads and its mounting tab); pull-ups R57-R59 east of the column on an
edge +3V3 bar fed from JP2.1 (top, front-right corner) through a via; series R114-R116 and U10 west of it; U12 / C48 /
C49 at the rear end; R_VSRC from JP2.2 through a via at the corner.  Local nets by the router."""
import os

import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401
import r2_auto as A

v2_pre.VIA_PITCH = 0.9
v2_pre.STACK_PEN = 8.0
BASE = os.environ.get("R2_BASE", "r2_bms")
COL = 82.3
for net, y in (("R_TEMPJ", 21.0), ("R_H3", 22.0), ("R_H2", 23.0), ("R_H1", 24.0), ("R_VS", 26.0)):
    via(net, (COL, y))
    tr(net, F1, [(82.9, y), (COL, y)])
via("GND", (COL, 25.0), RV)
tr("GND", F1, [(82.9, 25.0), (COL, 25.0)], 0.25)
# pull-ups: R_Hx pad west straight east of each via, +3V3 bar along the east edge from a via fed by JP2.1
for net, y in (("R_H3", 22.0), ("R_H2", 23.03), ("R_H1", 24.06)):
    tr(net, L4, [(COL, round(y) if net != "R_H1" else 24.0), (83.24, y)])
via("+3V3", (84.3, 18.95), RV)
tr("+3V3", F1, [(83.4, 17.75), (84.3, 18.5), (84.3, 18.95)], 0.25)
tr("+3V3", L4, [(84.3, 18.95), (84.55, 19.2), (84.55, 24.06), (84.26, 24.06)], 0.2)
tr("+3V3", L4, [(84.55, 23.03), (84.26, 23.03)], 0.2)
tr("+3V3", L4, [(84.55, 22.0), (84.26, 22.0)], 0.2)
# R_VSRC from JP2.2 (top) down the west side of JP2.1 to a via at the corner
via("R_VSRC", (82.4, 18.65))
tr("R_VSRC", F1, [(82.85, 16.0), (82.4, 16.45), (82.4, 18.65)], 0.2)
A.route_opens(BASE, ["R_H1", "R_H2", "R_H3", "R_H1B", "R_H2B", "R_H3B", "R_VS", "R_VSRC", "R_TEMPJ"], margin=3.0)
A.route_opens(BASE, ["R_H1", "R_H2", "R_H3", "R_H1B", "R_H2B", "R_H3B", "R_VS", "R_VSRC", "R_TEMPJ"], margin=6.0, retry=True)
