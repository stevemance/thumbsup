"""Copy a board with a GND zone on In1 (the L2 plane) filled, for the GND-connectivity count.
    /usr/bin/python3 r2/gndzone.py <in.kicad_pcb> <out.kicad_pcb>"""
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
bb = b.GetBoardEdgesBoundingBox()
gnd = b.FindNet("GND")
z = pcbnew.ZONE(b)
z.SetLayer(pcbnew.In1_Cu)
z.SetNet(gnd)
z.SetZoneName("L2 GND plane (check copy)")
z.SetLocalClearance(pcbnew.FromMM(0.2))
z.SetMinThickness(pcbnew.FromMM(0.2))
z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
ch = pcbnew.SHAPE_LINE_CHAIN()
m = pcbnew.FromMM(0.35)
for x, y in ((bb.GetLeft() + m, bb.GetTop() + m), (bb.GetRight() - m, bb.GetTop() + m),
             (bb.GetRight() - m, bb.GetBottom() - m), (bb.GetLeft() + m, bb.GetBottom() - m)):
    ch.Append(pcbnew.VECTOR2I(int(x), int(y)))
ch.SetClosed(True)
z.Outline().AddOutline(ch)
b.Add(z)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[2], b)
print("filled", sys.argv[2])
