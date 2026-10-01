"""hN: after the router flow on hM: the long JP1 +5V leg (routed last so it cannot take the MCU-front corridors)."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9

route("+5V", P("JP1", 3), ("pt", 51.1, 31.7, F1), margin=30.0)
