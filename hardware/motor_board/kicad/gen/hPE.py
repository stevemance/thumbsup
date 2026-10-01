"""hPE: power-entry rework (power-first, 2026-10-01), on hR.  Area: x 0-44, y 0-18 (JBAT1/2, Q7/Q8, U13, RS4, C1, U7 inputs)."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9
n_ = v2_pre.n_


def move(ref, x, y, rot, side="F"):
    EDITS.append(dict(op="move", ref=ref, x=x, y=y, rot=rot, side=side))


def rip(box, nets, layers=None):
    e = dict(op="rip", box=box, nets=[n_(n) if n != "GND" else n for n in nets], reroute=False)
    if layers:
        e["layers"] = layers
    EDITS.append(e)


# ---- rips ----
rip((6.0, 5.0, 53.0, 18.4), ["+5V"], [F1])                       # the JP1 +5V leg through the power band
rip((14.0, 0.0, 28.0, 10.0), ["PSW_G"])                           # gate: channel trace, R1 loop, U13 hop, D4 diag
rip((19.0, 9.5, 22.0, 11.0), ["PSW_CAP"])
rip((16.9, 9.9, 17.9, 10.3), ["PSW_EN"], [F1])                    # U13.1's stub (U13 turns)
rip((24.0, 5.5, 31.5, 14.5), ["INA_INP", "INA_INN"])

# ---- parts ----
move("U13", 18.85, 8.4, 0)
move("C12", 19.05, 10.95, 0)
move("C14", 22.15, 10.95, 0)
move("D4", 24.8, 8.0, 180)
move("R2", 29.8, 9.6, 180)
move("R3", 29.8, 11.15, 180)
move("C2", 28.0, 10.375, 270)
move("R15", 30.2, 16.5, 270)

# ---- PSW_G: Q7.4 -> west lane under Q7 (between tab and source pins) -> R1.1 and U13.6 (under U13's body);
#      Q7.4 -> front edge -> under Q8 (between source pins and tab) -> Q8.4; U13.6 -> D4.1 east, south of D4.2.
#      The Q7/Q8 source channel stays free for the pack current.
tr("PSW_G", F1, [(18.725, 1.795), (17.4, 1.795), (17.4, 6.35), (16.6, 6.35), (16.21, 6.74), (16.21, 7.3)], w=0.25)
tr("PSW_G", F1, [(20.15, 8.725), (19.15, 8.725), (18.85, 8.425), (18.85, 6.35), (17.4, 6.35)], w=0.25)
tr("PSW_G", F1, [(18.725, 1.795), (18.725, 0.75), (22.05, 0.75), (22.05, 5.605), (20.975, 5.605)], w=0.25)
tr("PSW_G", F1, [(20.15, 8.725), (21.6, 8.725), (22.2, 9.325), (26.45, 9.325), (26.45, 8.0)], w=0.25)
# ---- PSW_S: U13.8 (SRC) -> Q7.1, and -> D4.2
tr("PSW_S", F1, [(20.15, 7.425), (19.9, 7.3), (19.9, 6.3), (19.2, 5.6)], w=0.25)
tr("PSW_S", F1, [(20.15, 7.425), (22.75, 7.425), (23.0, 7.7)], w=0.25)
# ---- GND: U13.7 east via, U13.2 via in pad, C14.2 via
tr("GND", F1, [(20.15, 8.075), (21.1, 8.075)], w=0.25)
via("GND", (21.1, 8.075))
via("GND", (17.55, 8.075), POFV, "pofv")
tr("GND", F1, [(22.925, 10.95), (23.75, 10.95)], w=0.3)
via("GND", (23.75, 10.95))
# ---- PSW_EN: U13.1 west of the west pin column, down to the existing run between D10's pads
tr("PSW_EN", F1, [(17.55, 7.425), (16.8, 7.425), (16.8, 9.6), (16.3, 10.1)])
# ---- PSW_CAP: U13.4 -> C12.1
tr("PSW_CAP", F1, [(17.55, 9.375), (17.8, 9.6), (17.8, 9.8), (18.275, 10.275), (18.275, 10.95)], w=0.2)
# ---- BAT_IN: U13.5 (VS) -> C12.2 -> C14.1; fed from Q7's tab by an L3 hop (the only crossing, see the report)
tr("BAT_IN", F1, [(20.15, 9.375), (20.15, 10.2), (19.825, 10.525), (19.825, 10.95)], w=0.25)
tr("BAT_IN", F1, [(19.825, 10.95), (21.375, 10.95)], w=0.3)
via("BAT_IN", (20.6, 10.95))
via("BAT_IN", (16.75, 5.7), POFV, "pofv")
tr("BAT_IN", L3, [(16.75, 5.7), (20.6, 9.55), (20.6, 10.95)], w=0.3)

# ---- INA239 Kelvin taps from RS4's pad inner edges, as a pair down to R2 / R3 / C2, then to U7.10 / U7.9
tr("VBAT_SW", F1, [(30.6, 5.3), (30.6, 9.25), (30.4, 9.5)], w=0.2)
tr("VBAT", F1, [(35.05, 5.3), (34.65, 5.95), (31.15, 5.95), (31.15, 10.3), (30.45, 11.0)], w=0.2)
tr("INA_INP", F1, [(29.29, 9.6), (28.0, 9.6), (27.6, 9.6), (26.45, 10.75), (26.45, 12.35), (26.5, 12.6)], w=0.2)
tr("INA_INN", F1, [(29.29, 11.15), (28.0, 11.15), (27.55, 11.15), (27.0, 11.7), (27.0, 12.6)], w=0.2)
tr("VBAT", F1, [(30.31, 11.15), (30.31, 11.95), (27.75, 11.95), (27.5, 12.2), (27.5, 12.6)], w=0.2)   # U7.8 VBUS
tr("GND", F1, [(28.0, 13.9), (28.0, 14.65)], w=0.2)
via("GND", (28.0, 14.65))
# ---- R15 (bleeder) beside C3, VBAT via into the L3 band, GND via
tr("VBAT", F1, [(30.2, 15.675), (31.0, 15.675)], w=0.3)
via("VBAT", (31.0, 15.675), RV)
tr("GND", F1, [(30.2, 17.325), (30.95, 17.325)], w=0.3)
via("GND", (30.95, 17.325))
# ---- C1's VBAT pad into the L3 VBAT band
for x in (40.6, 42.0, 43.4):
    via("VBAT", (x, 12.1), POFV, "pofv")

# ---- +5V to JP1.3: the old leg through the power band is ripped above; no replacement path exists without re-routing
#      the drive / MCU corridor (see the hPE report), so JP1.3 is left open here.
