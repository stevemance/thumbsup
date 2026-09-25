"""For each multi-pin part: pads grouped by side (rot 0, top view, y down) with their nets -> stdout."""
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
b = pcbnew.LoadBoard(str(HERE.parent / "motor_board" / "motor_board.kicad_pcb"))
t = pcbnew.ToMM
want = sys.argv[1:]
for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
    r = fp.GetReference()
    if want and r not in want:
        continue
    if fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(0)
    c = fp.GetPosition()
    pads = [(p.GetNumber(), t(p.GetPosition().x - c.x), t(p.GetPosition().y - c.y), p.GetNetname().split("/")[-1]) for p in fp.Pads()]
    if len(pads) < 3:
        continue
    xs = [p[1] for p in pads]; ys = [p[2] for p in pads]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sides = {"L": [], "R": [], "T": [], "B": [], "C": []}
    for n, x, y, net in pads:
        d = {"L": x - x0, "R": x1 - x, "T": y - y0, "B": y1 - y}
        s = min(d, key=d.get)
        if d[s] > 0.6 and (x1 - x0) > 1 and (y1 - y0) > 1:
            s = "C"
        sides[s].append((n, net, round(x, 2), round(y, 2)))
    print(f"== {r} ({fp.GetFPIDAsString().split(':')[1]}) pad extents x[{x0:.2f},{x1:.2f}] y[{y0:.2f},{y1:.2f}]")
    for s in "TLBRC":
        if sides[s]:
            key = (lambda p: p[3]) if s in "LR" else (lambda p: p[2])
            print(f"  {s}: " + ", ".join(f"{n}:{net}" for n, net, _, _ in sorted(sides[s], key=key)))
