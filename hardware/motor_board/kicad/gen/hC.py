"""hC: centre cluster by hand, on top of h3 (coordinator).  W_nFAULT from MCU pin 20 along L1 in front of the MCU's front
row (south of the W_SOB lane) to a via beside its relocated pull-up R42 / filter C19; the TP9 / U2.28 / U7 legs are left
to the router flow."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, chain, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9


def move(ref, x, y, rot, side):
    EDITS.append(dict(op="move", ref=ref, x=x, y=y, rot=rot, side=side))


move("R42", 46.3, 20.3, 270, "B")
move("C19", 47.3, 20.5, 270, "B")
# pin 20 north to a via above the C71 / C90 pads; the net runs on L3 (y 19.5) from the west leg to R42's via, leaving
# L1 in front of pin 21 free for W_INLC_M
tr("W_nFAULT", F1, [(40.25, 20.57), (40.25, 18.6)])
via("W_nFAULT", (40.25, 18.6))
tr("W_nFAULT", L3, [(40.25, 18.6), (40.25, 19.5)])
via("W_nFAULT", (46.3, 19.15))
tr("W_nFAULT", L4, [(46.3, 19.15), (46.3, 19.79), (47.3, 20.02)])
# W_nFAULT west leg: U7.3 (INA239 ALERT) north through the gap between C407's pads to a via, L3 east (between R_nCS
# and R_INHC) to a via in front of the MCU's pin 29 / 30, then the L1 lane in front of the front row
tr("W_nFAULT", F1, [(27.5, 18.2), (27.5, 19.5), (27.35, 19.7), (27.35, 20.3)])
via("W_nFAULT", (27.35, 20.3))
tr("W_nFAULT", L3, [(27.35, 20.3), (35.5, 20.3), (35.9, 19.9), (36.3, 19.5), (46.0, 19.5), (46.3, 19.2), (46.3, 19.15)])
# W_INLC_M (pin 21): L1 north past W_nFAULT's via, east along y 18.1 to a via clear of the front band (x > 44.5), then
# the router to R49 / U6.9
tr("W_INLC_M", F1, [(39.75, 20.57), (39.75, 18.4), (40.05, 18.1), (45.4, 18.1)])
via("W_INLC_M", (45.4, 18.1))
route("W_INLC_M", ("via", 45.4, 18.1), P("R49", 1), [F1, L3, L4], margin=8.0)
