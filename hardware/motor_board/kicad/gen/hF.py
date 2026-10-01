"""hF: small fixes from the 2026-10-01 adversarial review, on hY (silk follows in hS).
- dead copper: R_VSRC / R_TEMPJ stubs + one-layer vias by JP2 / J3, the L_AVDD / L_nFAULT L4 stubs, the GND L4 stub at U8
- C9 (BMS_BAT 4.7 uF 1206) turned parallel to the rear edge (DESIGN 6.10 flex rule), pads 0.9 mm in from it
- C73 (R_MTEMP filter) out of MH4's 2.65 mm standoff / washer circle on the bottom, beside R117"""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9
n_ = v2_pre.n_


def move(ref, x, y, rot, side):
    EDITS.append(dict(op="move", ref=ref, x=x, y=y, rot=rot, side=side))


EDITS.append(dict(op="rip_segs", tracks=[
    (n_("R_VSRC"), F1, (82.85, 16.0), (82.4, 16.45)), (n_("R_VSRC"), F1, (82.4, 16.45), (82.4, 18.65)),
    (n_("R_TEMPJ"), F1, (82.9, 21.0), (82.3, 21.0)),
    (n_("L_AVDD"), L4, (9.26, 28.2), (8.26, 28.2)), (n_("L_nFAULT"), L4, (6.45, 27.95), (7.24, 28.2)),
    ("GND", L4, (68.6, 24.0), (68.97, 24.0)), ("GND", L4, (68.6, 25.09), (68.6, 24.0)),
    # C9's old BMS_BAT stub, C73's old links
    (n_("BMS_BAT"), F1, (58.6, 33.9), (59.1, 33.4)),
    (n_("R_MTEMP"), L4, (78.5, 32.45), (79.45, 31.95)), ("GND", L4, (79.7, 32.88), (80.3, 33.5)),
], vias=[(n_("R_VSRC"), (82.4, 18.65)), (n_("R_TEMPJ"), (82.3, 21.0))]))

# C9: rot 0 at the rear edge between U5 and J4; BMS_BAT pad west joins the existing run at (59.1, 33.4)
move("C9", 59.2, 33.2, 0, "T")
tr("BMS_BAT", F1, [(59.1, 33.4), (58.2, 33.4)])

# C73: (78.0, 31.0) r180 on the bottom: R_MTEMP pad east down to R117.2, GND pad west to a via north of it
move("C73", 78.0, 31.0, 180, "B")
tr("R_MTEMP", L4, [(78.48, 31.0), (78.48, 31.75), (78.3, 32.1)])
tr("GND", L4, [(77.52, 31.0), (77.7, 30.6), (78.0, 30.3)], w=0.2)
via("GND", (78.0, 30.3))
