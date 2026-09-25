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
    "C21": (60.45, 22.5, 90),    # charge-pump caps swapped so pins 5/4/3 (VCP, CPH, CPL) reach them as parallel
    "C20": (59.45, 25.28, 180),  #   top-layer lanes: C21 (VCP-VM) above next to C24, C20 (CPL | CPH) below
    "R20": (58.7, 26.6, None),   # FB divider 0.1 mm rearward: courtyard room for C20
    # test pads off U1's footprint: its body is the fan-out via field (the through vias need the top clear)
    "TP12": (17.15, 24.65, None),
    "TP5": (31.9, 11.35, None),
    "TP8": (17.6, 27.1, None),
    "TP4": (17.2, 29.25, None),
    "TP2": (15.0, 28.7, None),
    "TP3": (14.95, 25.5, None),
    "TP6": (16.5, 13.05, None),
    "TP1": (58.9, 18.8, None),
    "R21": (60.7, 26.6, None),
}
DROP_VIAS = [("GND", 55.4, 15.9), ("GND", 45.5, 16.7), ("GND", 46.7, 16.5),   # channels for GLB / SNC's lane
             ("VBAT", 68.15, 13.05), ("GND", 67.9, 15.9),                      # and for GHA/SHA through cell A
             ("GND", 33.905, 22.0), ("GND", 36.155, 22.0)]    # old TP12/TP5 GND vias, stranded in U1's fan-out field
# (a dropped via's stub tracks go with it)
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
pos = [(pcbnew.ToMM(v.GetPosition().x) - OX, pcbnew.ToMM(v.GetPosition().y) - OY) for v in drop]
for t in b.GetTracks():
    if t.GetClass() == "PCB_TRACK":
        for e in (t.GetStart(), t.GetEnd()):
            ex, ey = pcbnew.ToMM(e.x) - OX, pcbnew.ToMM(e.y) - OY
            if any(abs(ex - x) < 0.01 and abs(ey - y) < 0.01 for x, y in pos):
                drop.append(t)
                print("removing stub", t.GetNetname(), round(ex, 2), round(ey, 2))
                break
for v in drop:                  # remove after the walk (removing while iterating the board's list crashes pcbnew)
    b.Remove(v)
print("filling"); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); print("saving")
pcbnew.SaveBoard(str(BASE), b)
