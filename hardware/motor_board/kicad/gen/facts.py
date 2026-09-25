"""Numbers quoted in PLACEMENT.md, measured from the board (run with /usr/bin/python3)."""
import math
from pathlib import Path

import pcbnew

b = pcbnew.LoadBoard(str(Path(__file__).resolve().parent.parent / "motor_board" / "motor_board.kicad_pcb"))
t = pcbnew.ToMM
bb = b.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
fps = {f.GetReference(): f for f in b.GetFootprints()}


def pos(r):
    p = fps[r].GetPosition()
    return round(t(p.x) - OX, 2), round(t(p.y) - OY, 2)


def pad(r, n):
    for p in fps[r].Pads():
        if p.GetNumber() == n:
            return t(p.GetPosition().x) - OX, t(p.GetPosition().y) - OY


def d(a, c):
    return math.hypot(a[0] - c[0], a[1] - c[1])


print("MH:", {r: pos(r) for r in ("MH1", "MH2", "MH3", "MH4")})
print("J1 pin 1:", tuple(round(v, 2) for v in pad("J1", "1")), "pin 2:", tuple(round(v, 2) for v in pad("J1", "2")),
      "pin 19:", tuple(round(v, 2) for v in pad("J1", "19")), "side bottom" if fps["J1"].IsFlipped() else "top")
print("JBAT1-JBAT2 centres:", round(d(pos("JBAT1"), pos("JBAT2")), 2))
print("C1 VBAT - RS4 VBAT:", round(d(pad("C1", "1"), pad("RS4", "2")), 2), " C1 VBAT - R402 VBAT:", round(d(pad("C1", "1"), pad("R402", "1")), 2),
      " C1 VBAT - R302 VBAT:", round(d(pad("C1", "1"), pad("R302", "1")), 2))
print("R302 L_VM - U3.10:", round(d(pad("R302", "2"), pad("U3", "10")), 2), " R402 R_VM - U4.10:", round(d(pad("R402", "2"), pad("U4", "10")), 2))
dro = [p for r in fps for p in fps[r].Pads() if p.GetNetname().split("/")[-1] == "DRV_OFF"]
xy = [(t(p.GetPosition().x) - OX, t(p.GetPosition().y) - OY) for p in dro]
print("DRV_OFF span (max pad distance):", round(max(d(a, c) for a in xy for c in xy), 1), "mm over", len(xy), "pads")
for u, v in (("U11", "U3"), ("U12", "U4")):
    print(f"{u}-{v} centres: {d(pos(u), pos(v)):.1f} mm; {u} side {'bottom' if fps[u].IsFlipped() else 'top'}")
for j, parts in (("J2", ("U9", "U11", "D7", "R113")), ("J3", ("U10", "U12", "D8", "R117"))):
    print(j, {p: round(d(pos(p), pos(j)), 1) for p in parts})
edges = {}
for r, f in fps.items():
    for side in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        pass
print("heights: see PLACEMENT 5")
