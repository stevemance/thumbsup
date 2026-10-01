"""h3: hub placement + the weapon gate fan-out by hand, on top of h1.

U6 (the INL AND gate) moves from under U2's west strap resistors (no via room, inputs facing U2) to the bottom right
behind U2's rear gate pins, rot 270: its outputs 3 / 6 face pins 38 / 40 and output 8 sits under pin 42, each joined by
an L1 stub and a via in U6's pad (POFV).  The INH pins 37 / 39 / 41 drop through vias in their own pads (POFV) to L3.
R40 / R16 / R62 / C40 leave U6's new spot.  Everything else: h4 (router flow)."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, chain, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9


def move(ref, x, y, rot, side):
    EDITS.append(dict(op="move", ref=ref, x=x, y=y, rot=rot, side=side))


# the r2 router's copper for the nets this rework does not touch (h3_replay.json, kicad/v2/r2/replay.py from
# routed_r2), minus the nets listed in H3_DROP (conflicts with the new hub)
import json, os  # noqa: E401,E402
from pathlib import Path  # noqa: E402
_drop = set(os.environ.get("H3_DROP", "CELL0,R_MTEMP,BMS_SCL,VBAT_SNS_H").split(","))
EDITS += [e for e in json.load(open(Path(__file__).with_name("h3_replay.json")))
          if e["net"].split("/")[-1] not in _drop]

move("U6", 61.75, 30.25, 270, "B")
move("R62", 56.6, 26.45, 180, "B")     # LED resistor beside D3
move("C40", 60.0, 33.1, 90, "B")       # U6 decoupling south of pin 14

# ---------------------------------------------------------------- U2 west straps (adjacent pads, L1, first)
route("U2_DVDD", P("U2", 36), P("C22", 1), [F1], margin=1.0)
route("U2_MODE", P("U2", 29), P("R44", 1), [F1], margin=1.5)
route("U2_IDRIVE", P("U2", 30), P("R45", 1), [F1], margin=1.5)
route("U2_VDS", P("U2", 31), P("R46", 1), [F1], margin=1.5)

# ---------------------------------------------------------------- the L3 weapon bus MCU -> U2 / U6 (h1 vias)
# Under the MCU's east pins the lanes leave y 27.45-28.45 and the +3V3 pin-1 spot free for vias (R_MTEMP at R53.2);
# east of x 46 they step down, in order, to the U2 / U6 end (B 26.95, A 28.05, C 28.45, INLB_M 29.35, INLA_M 29.65).
tr("W_INHB", L3, [(45.8, 26.2), (46.9, 26.2), (47.65, 26.95), (59.0, 26.95)])
tr("W_INHA", L3, [(35.2, 28.3), (36.0, 27.5), (36.85, 26.65), (46.6, 26.65), (48.0, 28.05), (59.0, 28.05)])
tr("W_INHC", L3, [(39.9, 27.2), (40.1, 27.0), (46.4, 27.0), (47.95, 28.45), (59.0, 28.45)])
tr("W_INLB_M", L3, [(35.6, 29.0), (35.75, 28.85), (46.6, 28.85), (47.1, 29.35), (61.75, 29.35)])
tr("W_INLA_M", L3, [(38.5, 29.9), (39.25, 29.15), (46.4, 29.15), (46.9, 29.65), (59.0, 29.65), (59.4, 30.0)])
via("W_INLA_M", (59.4, 30.0))
tr("W_INLA_M", L4, [(59.4, 30.0), (60.31, 30.0)])
move("R47", 61.5, 33.1, 90, "B")      # W_INLA_M pull-down south of U6
move("C67", 45.9, 27.0, 0, "F")        # NRST cap on top at pin 7's tip (INHB's escape boxes pin 7 in from the north)
tr("ARM_AC", L4, [(48.3, 25.12), (48.3, 25.97)])
tr("LED_A", L4, [(55.18, 26.45), (55.9, 26.45)])

# ---------------------------------------------------------------- the east-pin L1 lanes (pin order = lane order)
# NRST (pin 7, via C67): lane y 27.75 to x 54.41, a via between the L3 lanes into J1.8, north to TP4 / R16 (top)
move("R16", 47.4, 27.3, 90, "F")       # NRST pull-up on the NRST lane
tr("NRST", F1, [(43.67, 27.0), (45.42, 27.0)])
tr("NRST", F1, [(45.42, 27.0), (45.42, 27.75), (54.41, 27.75), (54.41, 23.45)])
via("NRST", (54.41, 27.5))
tr("NRST", L4, [(54.41, 27.5), (54.41, 27.75)])
# W_ARM_S (pin 4): lane y 28.5 to x 55.0, north to a via beside U14 (U14.4 on L4); L4 east through the old U6 spot and
# down beside U6 to a jumper over its input row that joins pins 2 and 5 (pin 10 joins pin 5 on L3: below)
tr("W_ARM_S", F1, [(43.67, 28.5), (55.0, 28.5), (55.0, 25.8), (55.6, 25.4)])
via("W_ARM_S", (55.6, 25.4))
tr("W_ARM_S", L4, [(55.6, 25.4), (55.1, 24.9), (55.1, 24.54)])
tr("W_ARM_S", L4, [(55.6, 25.4), (59.3, 25.4), (59.3, 28.3), (62.25, 28.3), (62.25, 28.65)])
tr("W_ARM_S", L4, [(60.75, 28.3), (60.75, 28.65)])
# W_EN (pin 3): lane y 29.0 to x 56.6, north to U2.33 between R46 and C22; R40 / TP7 on top beside it
move("R40", 55.8, 27.6, 90, "F")
move("TP7", 57.6, 28.4, 0, "F")
tr("W_EN", F1, [(43.67, 29.0), (56.6, 29.0), (56.6, 25.6), (56.95, 25.25), (60.06, 25.25)])

# ---------------------------------------------------------------- U2 rear gate pins
# INL 38 / 40 / 42: L1 stubs south into vias in U6's output pads 3 / 6 / 8
tr("W_INLA", F1, [(61.25, 27.7), (61.25, 28.9)])
via("W_INLA", (61.25, 28.9), POFV, "POFV U6.3")
tr("W_INLB", F1, [(62.25, 27.7), (62.25, 27.9), (62.75, 28.4), (62.75, 29.25)])
via("W_INLB", (62.75, 29.25), POFV, "POFV U6.6")
tr("W_INLC", F1, [(63.25, 27.7), (63.25, 30.5), (63.35, 30.5)])
via("W_INLC", (63.35, 30.5), POFV, "POFV U6.8")
# INH 37 / 39 / 41: vias in the pads' rear halves to L3; lanes leave west (B from the north, A and C from the south)
via("W_INHA", (60.75, 27.5), POFV, "POFV U2.37")
via("W_INHB", (61.75, 27.5), POFV, "POFV U2.39")
via("W_INHC", (62.75, 27.5), POFV, "POFV U2.41")
tr("W_INHB", L3, [(61.75, 27.5), (61.75, 26.95), (59.0, 26.95)])
tr("W_INHA", L3, [(60.75, 27.5), (60.75, 28.05), (59.0, 28.05)])
tr("W_INHC", L3, [(62.75, 27.5), (62.75, 28.45), (59.0, 28.45)])
# U6 inputs on the pin row facing U2: INLB_M (4) and ARM_S (5) through vias in their pads; ARM_S pin 10 (rear row)
# joins pin 5 on L3 under the body
via("W_INLB_M", (61.75, 29.35), POFV, "POFV U6.4")
via("W_ARM_S", (62.25, 28.9), POFV, "POFV U6.5")
via("W_ARM_S", (62.25, 31.6), POFV, "POFV U6.10")
tr("W_ARM_S", L3, [(62.25, 28.9), (62.25, 31.6)])
