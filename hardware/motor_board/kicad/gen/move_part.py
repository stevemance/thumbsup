"""Nudge placed parts on a board (keeps everything else): /usr/bin/python3 move_part.py <board> REF dx dy [REF dx dy ...]"""
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
fps = {f.GetReference(): f for f in b.GetFootprints()}
a = sys.argv[2:]
for i in range(0, len(a), 3):
    f = fps[a[i]]
    p = f.GetPosition()
    f.SetPosition(pcbnew.VECTOR2I(p.x + pcbnew.FromMM(float(a[i + 1])), p.y + pcbnew.FromMM(float(a[i + 2]))))
    print("moved", a[i], a[i + 1], a[i + 2])
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[1], b)
