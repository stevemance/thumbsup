"""hD: power LED D3 and its resistor R62 back on the top face (DESIGN 3.1: visible from outside; review netlist-1 /
mech-2), on hT: D3 at (49.0, 30.0) north of TP11, R62 at (47.8, 32.0) with its +5V pad on the rear +5V lane (L1 y 32.92);
the LED string stays on L1 (no via; a bottom R62 + LED_A via found no room past the L3 gate bus); cathode on L1 to C69.2."""
import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV  # noqa: F401

v2_pre.VIA_PITCH = 0.9
n_ = v2_pre.n_


def move(ref, x, y, rot, side):
    EDITS.append(dict(op="move", ref=ref, x=x, y=y, rot=rot, side=side))


EDITS.append(dict(op="rip", box=(0, 0, 85, 35), nets=[n_("LED_A")], reroute=False))
move("D3", 49.0, 30.0, 180, "F")
move("R62", 47.8, 32.0, 90, "F")
route("+5V", P("R62", 1), ("pt", 47.8, 32.92, F1), [F1], margin=1.5)
route("LED_A", P("R62", 2), P("D3", 2), [F1], margin=2.0)
# no via spot near D3 (L3 gate bus, L4 SWD / arm lanes): its cathode runs on L1 north of TP3 to C69.2 (GND, stitched later)
tr("GND", F1, [(49.79, 30.0), (54.3, 30.0), (54.3, 30.95)], w=0.2)
