"""Pour acceptance test: can each power net's planned pour actually connect its pads?
    /usr/bin/python3 pourtest.py <stage | board.kicad_pcb> [NET[:F,L3,B] ...] [--clr 0.2]
For each net (default: every pour net on its planned layers), on a scratch copy of the board: remove all zones, add one
full-board top-priority zone of that net on the given layers (solid pad connection, given clearance), fill, and group the
net's pads by copper connectivity (existing tracks / vias + the fill).  PASS = one group.  A single-net pour is the
optimistic case (the real pours share the area), so a FAIL here is a hard wall; a PASS still needs the real pour stage.
Adapted from the 2026-10-01 review's pour script (review power-1 / signal-3)."""
import sys
import tempfile
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
LM = {"F": pcbnew.F_Cu, "L3": pcbnew.In2_Cu, "B": pcbnew.B_Cu}
# planned pour layers (DESIGN 6.2): power stage on L1; VBAT on L1 + the L3 band
PLAN = {"VBAT": "F,L3", "BAT_IN": "F", "PSW_S": "F", "VBAT_SW": "F", "W_A": "F", "W_B": "F", "W_C": "F",
        "W_SLA": "F", "W_SLB": "F", "W_SLC": "F", "L_A": "F", "L_B": "F", "L_C": "F", "R_A": "F", "R_B": "F",
        "R_C": "F", "L_VM": "F", "R_VM": "F"}

args = sys.argv[1:]
clr = 0.2
if "--clr" in args:
    i = args.index("--clr"); clr = float(args[i + 1]); args = args[:i] + args[i + 2:]
src = args[0]
board = Path(src) if src.endswith(".kicad_pcb") else HERE.parents[1] / "gen" / "out" / "exp" / src / "proj" / "motor_board.kicad_pcb"
want = [(a.split(":")[0], a.split(":")[1] if ":" in a else PLAN.get(a.split(":")[0], "F")) for a in args[1:]] or list(PLAN.items())

base = pcbnew.LoadBoard(str(board))
full = {n.split("/")[-1]: n for n in (str(k) for k in base.GetNetsByName().keys()) if n}
fails = 0
for net, lays in want:
    b = pcbnew.LoadBoard(str(board))                       # fresh copy per net
    for z in list(b.Zones()):
        b.Remove(z)
    ni = b.FindNet(full[net])
    bb = b.GetBoardEdgesBoundingBox()
    for L in lays.split(","):
        z = pcbnew.ZONE(b)
        z.SetLayer(LM[L]); z.SetNet(ni); z.SetAssignedPriority(100)
        z.SetLocalClearance(pcbnew.FromMM(clr))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetMinThickness(pcbnew.FromMM(0.15))
        o = z.Outline(); o.NewOutline()
        for x, y in [(bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()), (bb.GetRight(), bb.GetBottom()),
                     (bb.GetLeft(), bb.GetBottom())]:
            o.Append(x, y)
        b.Add(z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.BuildConnectivity()
    c = b.GetConnectivity()
    pads = [p for p in b.GetPads() if p.GetNetname() == full[net]]
    seen, groups = set(), []
    for p in pads:
        k = (p.GetParentFootprint().GetReference(), p.GetNumber())
        if k in seen:
            continue
        g = {k}
        for it in c.GetConnectedItems(p):
            if it.GetClass() == "PAD":
                g.add((it.GetParentFootprint().GetReference(), it.GetNumber()))
        seen |= g; groups.append(sorted(g))
    ok = len(groups) == 1
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {net:8s} [{lays}] groups {len(groups)}" +
          ("" if ok else ":  " + " | ".join(" ".join(f"{r}.{n}" for r, n in g) for g in groups)))
print(f"{fails} net(s) failing")
