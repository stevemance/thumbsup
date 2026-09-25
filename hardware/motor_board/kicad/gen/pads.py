import sys
from pathlib import Path
import pcbnew
b = pcbnew.LoadBoard(str(Path(__file__).resolve().parent.parent / "motor_board" / "motor_board.kicad_pcb"))
t = pcbnew.ToMM
for fp in b.GetFootprints():
    r = fp.GetReference()
    if r not in sys.argv[1:]:
        continue
    if fp.IsFlipped(): fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(0); c = fp.GetPosition(); fp.BuildCourtyardCaches(); bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
    print(f"{r} crt x[{t(bb.GetLeft()-c.x):.2f},{t(bb.GetRight()-c.x):.2f}] y[{t(bb.GetTop()-c.y):.2f},{t(bb.GetBottom()-c.y):.2f}]")
    for p in fp.Pads():
        s = p.GetSize()
        print(f"   {p.GetNumber() or '-':>3} {p.GetNetname().split('/')[-1]:10s} at ({t(p.GetPosition().x-c.x):6.2f},{t(p.GetPosition().y-c.y):6.2f}) size {t(s.x):.2f}x{t(s.y):.2f}")
