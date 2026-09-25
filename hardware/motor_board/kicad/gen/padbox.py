"""Pad boxes (board-local mm) of the given refs, with net: for designing pours.  /usr/bin/python3 padbox.py Q3 Q4 ..."""
import sys
from pathlib import Path

import pcbnew

b = pcbnew.LoadBoard(str(Path(__file__).resolve().parent.parent / "motor_board" / "motor_board.kicad_pcb"))
t = pcbnew.ToMM
bb = b.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
for f in b.GetFootprints():
    if f.GetReference() not in sys.argv[1:]:
        continue
    print(f.GetReference(), "bottom" if f.IsFlipped() else "top", f"rot {f.GetOrientationDegrees():.0f}")
    for p in f.Pads():
        r = p.GetBoundingBox()
        print(f"   {p.GetNumber() or '-':3s} {p.GetNetname().split('/')[-1]:8s} x {t(r.GetLeft()) - OX:6.2f}..{t(r.GetRight()) - OX:6.2f}  y {t(r.GetTop()) - OY:6.2f}..{t(r.GetBottom()) - OY:6.2f}")
