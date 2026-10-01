"""hZ: last opens on hNE.  R_S2: its L1 lane under MB_TX can't via anywhere east (R_S1's lane / via sit south of it),
so it drops at the pin (38.75, 33.4), runs L4 east through C64's old spot to a via north of the MB_RX lane, then L3 to
the east agent's corridor.  C64 (U1 VDD 4.7 uF bulk, position not critical) moves to the MCU's front-left corner beside C61.1 (+3V3);
its old feed (via (37.75, 34.4), the L3 lane to via (44.4, 33.2) and that via's L1 stub from pin 64) goes with it."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9


def move(ref, x, y, rot, side):
    EDITS.append(dict(op="move", ref=ref, x=x, y=y, rot=rot, side=side))


EDITS.append(dict(op="rip", box=(38.6, 33.3, 43.2, 34.5), nets=[v2_pre.n_("R_S2")], layers=[F1], reroute=False))
EDITS.append(dict(op="rip", box=(37.5, 32.15, 44.6, 34.65), nets=[v2_pre.n_("+3V3")], layers=[F1, L3, L4],
                  reroute=False))
move("C64", 32.0, 21.0, 90, "B")
tr("+3V3", L4, [(32.0, 21.775), (32.2, 21.6), (34.25, 21.6)], w=0.2)
tr("GND", L4, [(32.0, 20.225), (32.6, 19.6), (32.9, 19.6)], w=0.2)
via("GND", (32.9, 19.6))
EDITS.append(dict(op="rip_segs", tracks=[], vias=[(v2_pre.n_("+3V3"), (37.75, 34.4)), (v2_pre.n_("+3V3"), (44.4, 33.2))]))
tr("R_S2", F1, [(38.75, 31.93), (38.75, 33.4)])
via("R_S2", (38.75, 33.4))
tr("R_S2", L4, [(38.75, 33.4), (39.25, 33.9), (41.8, 33.9), (42.4, 33.3)])
via("R_S2", (42.4, 33.3))
tr("R_S2", L3, [(42.4, 33.3), (42.95, 33.85), (46.0, 33.85), (46.4, 33.45), (46.4, 33.37)])
