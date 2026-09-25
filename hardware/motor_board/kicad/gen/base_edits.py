"""Routing-driven edits to the pre-routing base (base/motor_board_base.kicad_pcb), idempotent.
/usr/bin/python3 base_edits.py           (close KiCad first)

Why each one exists is in route_blocks.py (block 1 notes).  Positions are board-local mm; parts keep their rotation
except where one is given.  placement_spec.py / bridge_pours.py carry the same values for a from-scratch rebuild."""
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
BASE = HERE / "base" / "motor_board_base.kicad_pcb"
OX, OY = 100.0, 70.0
MOVE = {                # ref: (x, y, rot or None) of the footprint origin
    "NT2": (51.6, 13.85, 0),     # flat on RS2's GND pad inner-front corner, sense pad in the pad gap
    "NT3": (39.1, 16.85, 0),     # flat on RS3's GND pad inner-rear corner, sense pad in the pad gap
    "NT1": (64.1, 13.85, 0),     # flat on RS1's GND pad inner-front corner, sense pad in the pad gap
    "R24": (48.5, 4.5, None),    # between JW3's and JW2's solder zones, clear of the gate bundles
    "R62": (61.3, 21.3, None),   # out of phase A's escape diagonals right of U2
}
DROP_VIAS = [("GND", 55.4, 15.9), ("GND", 45.5, 16.7), ("GND", 46.7, 16.5),   # channels for GLB / SNC's lane
             ("VBAT", 68.15, 13.05), ("GND", 67.9, 15.9)]                      # and for GHA/SHA through cell A
L3_FEED = [(21.0, 1.5), (34.6, 1.5), (34.6, 6.0), (72.8, 6.0), (72.8, 18.2), (34.6, 18.2), (34.6, 20.8), (21.0, 20.8)]

b = pcbnew.LoadBoard(str(BASE))
mm = pcbnew.FromMM
for f in b.GetFootprints():
    if f.GetReference() in MOVE:
        x, y, rot = MOVE[f.GetReference()]
        if rot is not None:
            f.SetOrientationDegrees(rot)
        f.SetPosition(pcbnew.VECTOR2I(mm(x + OX), mm(y + OY)))
        print("placed", f.GetReference(), x, y, f.GetOrientationDegrees())
for z in b.Zones():
    if z.GetZoneName() == "L3 VBAT feed":
        o = z.Outline()                     # same 8 corners as bridge_pours.py drew: move them in place
        assert o.TotalVertices() == len(L3_FEED)
        for i, (x, y) in enumerate(L3_FEED):
            o.SetVertex(i, pcbnew.VECTOR2I(mm(x + OX), mm(y + OY)))
        print("L3 VBAT feed outline: front edge y 6.0 (front strip for the divided phase / NTC lines), rear edge y 18.2")
drop = []
for v in b.GetTracks():
    if v.GetClass() != "PCB_VIA":
        continue
    x, y = pcbnew.ToMM(v.GetPosition().x) - OX, pcbnew.ToMM(v.GetPosition().y) - OY
    for net, dx, dy in DROP_VIAS:
        if v.GetNetname() == net and abs(x - dx) < 0.01 and abs(y - dy) < 0.01:
            drop.append(v)
            print("removing via", net, dx, dy)
for v in drop:                  # remove after the walk (removing while iterating the board's list crashes pcbnew)
    b.Remove(v)
print("filling"); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); print("saving")
pcbnew.SaveBoard(str(BASE), b)
