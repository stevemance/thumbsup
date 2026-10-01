"""Pad offsets of a footprint from its courtyard centre for a given rotation / side (board top view, y to the rear).
    /usr/bin/python3 r2/fp.py REF ROT SIDE [REF ROT SIDE ...]"""
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
b = pcbnew.LoadBoard(str(HERE.parents[1] / "motor_board" / "motor_board.kicad_pcb"))
t = pcbnew.ToMM
fps = {f.GetReference(): f for f in b.GetFootprints()}
a = sys.argv[1:]
for i in range(0, len(a), 3):
    ref, rot, side = a[i], float(a[i + 1]), a[i + 2]
    f = fps[ref]
    if f.IsFlipped() != (side == "B"):
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetOrientationDegrees(rot)
    cy = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
    r = cy.BBox()
    cx, cyy = (t(r.GetLeft()) + t(r.GetRight())) / 2, (t(r.GetTop()) + t(r.GetBottom())) / 2
    print(f"{ref} rot {rot:g} {side}: court {t(r.GetWidth()):.2f} x {t(r.GetHeight()):.2f}")
    for p in sorted(f.Pads(), key=lambda p: (len(p.GetNumber()), p.GetNumber())):
        q = p.GetPosition()
        bb = p.GetBoundingBox()
        print(f"   {p.GetNumber():>3} {p.GetNetname().split('/')[-1]:12s} ({t(q.x) - cx:+.2f}, {t(q.y) - cyy:+.2f})  "
              f"size {t(bb.GetWidth()):.2f} x {t(bb.GetHeight()):.2f}")
