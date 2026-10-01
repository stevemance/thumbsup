"""hM: coordinator leftovers on hC: R42's +3V3 leg, MB_RX to R17, the JP1 +5V leg."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9

# R42.2 (pull-up) by hand on L4 between the W_VA via and C60.2 into C60.1
tr("+3V3", L4, [(46.3, 20.81), (45.8, 21.3), (44.25, 21.3), (44.1, 21.45), (44.1, 21.9), (43.72, 22.28), (43.72, 22.5)])
route("MB_RX", P("R17", 1), ("pt", 46.0, 32.95, L4), margin=6.0)
