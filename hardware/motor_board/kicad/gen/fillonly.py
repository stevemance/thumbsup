"""GND SMD pads whose only tie to the planes is the outer GND fill (no track/via path of their own to a GND via).
/usr/bin/python3 fillonly.py [board] -> REF.PIN list (python literal)"""
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
b = pcbnew.LoadBoard(sys.argv[1] if len(sys.argv) > 1 else str(HERE.parent / "motor_board" / "motor_board.kicad_pcb"))
gnd = b.GetNetcodeFromNetname("GND")
tr = [x for x in b.GetTracks() if x.GetNetCode() == gnd]
vias = [x for x in tr if x.GetClass() == "PCB_VIA"]
segs = [x for x in tr if x.GetClass() == "PCB_TRACK"]
out = []
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetNetCode() != gnd or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        # flood over GND tracks from the pad on its layer; done when a via is reached
        lay = p.GetLayer() if p.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu) else (pcbnew.B_Cu if f.IsFlipped() else pcbnew.F_Cu)
        front = [s for s in segs if s.GetLayer() == lay and (p.HitTest(s.GetStart()) or p.HitTest(s.GetEnd()))]
        seen, ok = set(), any(p.HitTest(v.GetPosition()) for v in vias)
        while front and not ok:
            s = front.pop(); 
            if id(s) in seen:
                continue
            seen.add(id(s))
            for e in (s.GetStart(), s.GetEnd()):
                if any((v.GetPosition() - e).EuclideanNorm() < pcbnew.FromMM(0.05) for v in vias):
                    ok = True
                front += [t for t in segs if t.GetLayer() == lay and id(t) not in seen and (t.GetStart() == e or t.GetEnd() == e)]
        if not ok:
            out.append((f.GetReference(), p.GetNumber()))
print(len(out)); print(out)
