"""hY: CELL1 / BMS_BAT / CELL0 at U8, on hZ.
- C4 (cell-1 input filter, CELL1-CELL0) sat east of the I2C L3 lanes under L1's pads, where no layer had room for its
  CELL1 pad; it moves under U8 between R8 and R9 (nearer VC1 / VC0).
- R11 (BAL4 -> BAT 100R) sat north of R10 with a BAL4 run from R10 up to it: that run walled C8 (VC0 filter) off from
  U8 and CELL0's way around it boxed R11's BMS_BAT pad in.  R11 moves beside R10 / J4.5 (BAL4 local), its BMS_BAT pad
  routes to the existing BMS_BAT run, and the BAL4 wall goes."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9
n_ = v2_pre.n_


def move(ref, x, y, rot, side):
    EDITS.append(dict(op="move", ref=ref, x=x, y=y, rot=rot, side=side))


# C4 -> under U8; its old CELL0 leaf goes
EDITS.append(dict(op="rip", box=(75.12, 21.4, 77.0, 24.9), nets=[n_("CELL0"), n_("CELL1")], layers=[L4], reroute=False))
move("C4", 73.3, 27.98, 270, "B")
route("CELL1", P("C4", 1), P("C5", 2), margin=4.0)
route("CELL0", P("C4", 2), ("via", 69.55, 25.7), margin=4.0)

# R11 -> beside R10 / J4.5; the BAL4 run R10.1 -> old R11.1, the old BMS_BAT stub, and CELL0's loop around R11 go
EDITS.append(dict(op="rip", box=(75.8, 20.9, 77.5, 27.9), nets=[n_("BAL4")], layers=[L4], reroute=False))
EDITS.append(dict(op="rip", box=(74.9, 18.5, 78.0, 25.0), nets=[n_("CELL0")], layers=[L4], reroute=False))
EDITS.append(dict(op="rip", box=(75.06, 19.6, 76.7, 20.8), nets=[n_("CELL0")], layers=[L3], reroute=False))
EDITS.append(dict(op="rip_segs", tracks=[], vias=[(n_("CELL0"), (75.0, 19.9))]))
move("R11", 76.2, 29.37, 0, "B")
route("BAL4", P("R11", 1), P("R10", 1), [L4], margin=3.0)
# BMS_BAT: R11.2 -> via beside J4.5 -> L3 lane y 32.28 behind J4 (between the pads and BMS_SCL) into the existing run
tr("BMS_BAT", L4, [(77.02, 29.37), (77.02, 30.67), (76.69, 31.0), (76.25, 31.0)])
via("BMS_BAT", (76.25, 31.0))
tr("BMS_BAT", L3, [(76.25, 31.0), (75.8, 31.45), (75.8, 32.1), (75.62, 32.28), (68.45, 32.28)])
# CELL0: C8.1 north on L4 (x 77.7, where the old loop ran) and west to a via onto CELL0's L3 run to U8.5
via("CELL0", (75.4, 20.83))
tr("CELL0", L3, [(75.05, 20.75), (75.4, 20.83)])
tr("CELL0", L4, [(75.4, 20.83), (75.72, 21.2), (77.4, 21.2), (77.7, 21.5), (77.7, 24.3), (77.85, 24.45), (77.85, 26.17)])
# +5V's L3 lane bends north round the CELL0 via into its via at C29
EDITS.append(dict(op="rip_segs", tracks=[(n_("+5V"), L3, (67.7, 20.4), (75.9, 20.4)), (n_("+5V"), L3, (75.9, 20.4), (76.05, 20.25)),
                                         (n_("+5V"), L3, (76.05, 20.25), (76.1, 20.25))], vias=[]))
tr("+5V", L3, [(67.7, 20.4), (74.8, 20.4), (75.2, 20.0), (75.85, 20.0), (76.1, 20.25)], w=0.2)
