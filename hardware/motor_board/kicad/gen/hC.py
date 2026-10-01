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
tr("W_nFAULT", F1, [(40.25, 20.57), (40.25, 19.15), (46.3, 19.15)])
via("W_nFAULT", (46.3, 19.15))
tr("W_nFAULT", L4, [(46.3, 19.15), (46.3, 19.79), (47.3, 20.02)])
