"""hX: final clean-up on hP: J1 pad 16 (spare, NC) carries the schematic's auto net "unconnected-(J1-Pin_16-Pad16)" (the
parity check flagged the pad's empty net; pad 7 already has its own); the dangling INA_nCS via at (20.0, 26.75) (a
through via on a straight L4 run, joined on L4 only) goes."""
import pcbnew

import v2_pre
from v2_pre import EDITS

v2_pre.VIA_PITCH = 0.9
NC16 = "unconnected-(J1-Pin_16-Pad16)"


def j1_16(b, ctx):
    ni = b.FindNet(NC16)
    if ni is None:
        ni = pcbnew.NETINFO_ITEM(b, NC16)
        b.Add(ni)
    p = [q for q in ctx["fps"]["J1"].Pads() if q.GetNumber() == "16"][0]
    p.SetNet(ni)


EDITS.append(dict(op="rip_segs", tracks=[], vias=[(v2_pre.n_("INA_nCS"), (20.0, 26.75))]))
EDITS.append(dict(op="py", fn=j1_16))
