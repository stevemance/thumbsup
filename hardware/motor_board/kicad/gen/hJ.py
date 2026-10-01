"""hJ: +5V to JP1.3 (LEFT sensor supply select, review power-3 follow-up), on hWE.
JP1 stays at the front-left (7.6, 9.55) but is turned 180 deg (rot 270): pad 1 (+3V3) to the front, pad 2 (L_VSRC) in
place, pad 3 (+5V) at the rear end.  +3V3 now leaves pad 1 east and runs down x 8.8 (between JP1 and C307) to its old
path at (9.0, 12.3); L_VSRC is untouched.  +5V leaves pad 3 south, runs west at y 11.65 (south of L_VSRC's y 11.1 leg,
north of R302) and down the west edge at x 1.75 beside L_VSRC (x 1.2), steps east north of JL1 (L1 y 18.8, between
C308 and JL1's pad) to an RV at (4.6, 19.6), then on L3 down the free strip x 4.6 (west of U3's L3 island, east of the
JL / MH3 holes), east under J2 / U11 (y 33.9 -> 34.42, south of DRV_OFF / L_nFAULT) and along the rear edge lane
(y 34.42, south of L_MTEMP) to x 41, then up to the +5V copper at TP11 / J1.13.  No +5V in the L1 front power area and
no L3 / L4 track in the front band.  L_MTEMP's via-in-pad in R113.2 (bottom) moves 0.25 mm north inside the pad to
open the rear lane."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9
n_ = v2_pre.n_


def move(ref, x, y, rot, side="F"):
    EDITS.append(dict(op="move", ref=ref, x=x, y=y, rot=rot, side=side))


# ---------------------------------------------------------------- rips
EDITS.append(dict(op="rip_segs", tracks=[("+3V3", F1, (7.6, 10.85), (7.65, 10.9)),
                                         ("+3V3", F1, (7.65, 10.9), (7.65, 10.95)),
                                         ("+3V3", F1, (7.65, 10.95), (9.0, 12.3)),
                                         (n_("L_MTEMP"), L3, (14.77, 34.2), (15.17, 33.8))],
                  vias=[(n_("L_MTEMP"), (14.77, 34.2))]))

# ---------------------------------------------------------------- JP1 turned: pad 1 front, pad 3 rear
move("JP1", 7.6, 9.55, 270)

# +3V3: pad 1 (7.6, 8.25) east, down x 8.8 to the old path
tr("+3V3", F1, [(7.6, 8.25), (8.8, 8.25), (8.8, 12.1), (9.0, 12.3)], w=0.2)

# L_MTEMP via-in-pad (R113.2, bottom) 0.25 north inside the pad
via("L_MTEMP", (14.77, 33.95), POFV, "L_MTEMP via-in-pad R113.2 moved 0.25 mm north (rear lane for +5V)")
tr("L_MTEMP", L3, [(14.77, 33.95), (14.92, 33.8), (15.17, 33.8)], w=0.15)

# +5V: pad 3 (7.6, 10.85) -> west edge -> RV -> L3 strip -> rear lane
tr("+5V", F1, [(7.6, 10.85), (7.6, 11.65), (1.75, 11.65), (1.75, 18.8), (4.6, 18.8), (4.6, 19.6)], w=0.2)
via("+5V", (4.6, 19.6), RV, "JP1.3 +5V: L1 west edge -> L3 strip")
tr("+5V", L3, [(4.6, 19.6), (4.6, 33.4), (5.1, 33.9), (6.7, 33.9), (7.22, 34.42), (34.6, 34.42)], w=0.2)
# threads south of the SPI_MISO via (35.3, 34.1), north of the SPI_MOSI via (36.2, 34.45) / south of L_MTEMP (w 0.15)
tr("+5V", L3, [(34.6, 34.42), (34.76, 34.58), (35.55, 34.58), (35.9, 34.0), (36.45, 34.0), (36.75, 34.3)], w=0.15)
tr("+5V", L3, [(36.75, 34.3), (41.0, 34.3)], w=0.2)
# up the L3 slot x 41.94 between L_MTEMP (x 41.6) and the R_S2 via (42.4, 33.3) (w 0.15), east under U1's rear-east
# corner (between the +3V3 via and the SWCLK via) to a via south of TP2, then L1 y 32.92 to TP11 / C30's +5V
tr("+5V", L3, [(41.0, 34.3), (41.94, 34.3), (41.94, 32.75), (42.1, 32.6), (42.6, 32.6)], w=0.15)
tr("+5V", L3, [(42.6, 32.6), (42.95, 32.95), (44.65, 32.95), (44.65, 33.15)], w=0.2)
via("+5V", (44.65, 33.15), PV, "rear +5V lane L3 -> L1 (TP11)")
tr("+5V", F1, [(44.65, 33.15), (44.65, 32.92), (49.65, 32.92)], w=0.2)
