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
    "TP12": (26.45, 25.75, None),
    "TP5": (31.9, 11.35, None),
    "TP8": (21.35, 4.95, None),
    "TP4": (35.55, 20.25, None),
    "TP2": (33.4, 20.25, None),
    "TP3": (14.95, 25.5, None),
    "TP6": (16.5, 13.05, None),
    "TP1": (58.9, 18.8, None),
    "R21": (60.7, 26.6, None),
}
# 2-pad parts placed by where their pads go: ref -> (pad1 xy, pad2 xy)
# U3 charge pump / VM caps re-placed to the pin order (VM 11-9, CP 8, CPH 7, CPL 6): C303 (CP|VM) and C301 (VM|GND)
# in the row nearest the pins, C304 (CPH|CPL) and C300 (VM|GND) one row out; U4's are the mirror image
# (x -> 89.5 - x, y -> 54.5 - y: U4's rear pin row mirrors U3's front row).
U3CAPS = {"C303": ((21.9, 26.05), (20.35, 26.05)), "C301": ((18.8, 26.05), (17.25, 26.05)),
          "C304": ((23.05, 24.55), (24.6, 24.55)), "C300": ((21.0, 24.55), (19.45, 24.55))}
U4OF = {"C303": "C403", "C301": "C401", "C304": "C404", "C300": "C400"}
PADPOS = dict(U3CAPS)
for r3, (p1, p2) in U3CAPS.items():
    PADPOS[U4OF[r3]] = ((round(89.5 - p1[0], 3), round(54.5 - p1[1], 3)), (round(89.5 - p2[0], 3), round(54.5 - p2[1], 3)))
# C23 (U2 VREF cap) 0.35 mm rearward: opens U2 pin 25 (W_SOA)'s only exit, between it and the SHC stair via
PADPOS["C23"] = ((48.78, 21.1), (47.82, 21.1))
# except C400: its mirror spot touches MH4's courtyard, so it goes on the bottom right under U4's VM caps, standing
# (VM pad nearest the pins, GND pad clear of MH4's washer keep-out), reached by one via from C403's VM pad
FLIP = {"C400"}
PADPOS["C400"] = ((68.9, 29.9), (68.9, 31.45))
DROP_VIAS = [("GND", 55.4, 15.9), ("GND", 45.5, 16.7), ("GND", 46.7, 16.5),   # channels for GLB / SNC's lane
             ("VBAT", 68.15, 13.05), ("GND", 67.9, 15.9),                      # and for GHA/SHA through cell A
             ("GND", 33.905, 22.0), ("GND", 36.155, 22.0)]    # old TP12/TP5 GND vias, stranded in U1's fan-out field
DROP_VIAS += [("GND", 46.7, 17.9), ("GND", 46.03, 19.195), ("GND", 37.225, 19.03)]  # + a cap GND via over U1 pin 12 (W_SOA exit)   # room for SNC's stair via and W_SOB's via (U2 front-left)
DROP_VIAS += [("GND", 18.555, 29.25), ("GND", 18.555, 30.75), ("GND", 70.945, 23.75), ("GND", 70.945, 25.25)]  # U3/U4 GND pins 15/18: tied to the EP instead (the motor-output lanes run there)
# (a dropped via's stub tracks go with it)
L3_FEED = [(21.0, 1.5), (34.6, 1.5), (34.6, 6.0), (72.8, 6.0), (72.8, 18.2), (34.6, 18.2), (34.6, 20.8), (21.0, 20.8)]

b = pcbnew.LoadBoard(str(BASE))
mm = pcbnew.FromMM
FLIP_MOVE = set()
for f in b.GetFootprints():
    if f.GetReference() in FLIP_MOVE and not f.IsFlipped():
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    if f.GetReference() in MOVE:
        x, y, rot = MOVE[f.GetReference()]
        if rot is not None:
            f.SetOrientationDegrees(rot)
        f.SetPosition(pcbnew.VECTOR2I(mm(x + OX), mm(y + OY)))
        print("placed", f.GetReference(), x, y, f.GetOrientationDegrees())
import math
old_pads = []                   # where re-placed parts' pads were: their old GND via stubs get removed below
for f in b.GetFootprints():
    if f.GetReference() in PADPOS:
        old_pads += [(pcbnew.ToMM(p.GetPosition().x) - OX, pcbnew.ToMM(p.GetPosition().y) - OY, p.GetNetname())
                     for p in f.Pads()]
for f in b.GetFootprints():
    if f.GetReference() in PADPOS:
        if f.GetReference() in FLIP and not f.IsFlipped():
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        (x1, y1), (x2, y2) = PADPOS[f.GetReference()]
        f.SetOrientationDegrees(0)
        pd = {p.GetNumber(): p.GetPosition() for p in f.Pads()}
        v0 = (pd["2"].x - pd["1"].x, pd["2"].y - pd["1"].y)             # pad1 -> pad2 at 0 degrees (board axes)
        a0 = math.degrees(math.atan2(-v0[1], v0[0]))
        a1 = math.degrees(math.atan2(-(y2 - y1), x2 - x1))
        f.SetOrientationDegrees((a1 - a0) % 360)
        pd = {p.GetNumber(): p.GetPosition() for p in f.Pads()}
        mid = ((pd["1"].x + pd["2"].x) / 2, (pd["1"].y + pd["2"].y) / 2)
        pos = f.GetPosition()
        f.SetPosition(pcbnew.VECTOR2I(int(pos.x + mm((x1 + x2) / 2 + OX) - mid[0]), int(pos.y + mm((y1 + y2) / 2 + OY) - mid[1])))
        pd = {p.GetNumber(): p.GetPosition() for p in f.Pads()}
        print("placed", f.GetReference(), "pads", [(round(pcbnew.ToMM(p.x) - OX, 2), round(pcbnew.ToMM(p.y) - OY, 2)) for p in (pd["1"], pd["2"])])
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
new_pads = [xy for pp in PADPOS.values() for xy in pp]
stale = [(x, y) for x, y, n in old_pads if n == "GND" and min(math.hypot(x - a, y - c) for a, c in new_pads) > 0.05]
vias_at = {}
for v in b.GetTracks():
    if v.GetClass() == "PCB_VIA":
        vias_at[(round(pcbnew.ToMM(v.GetPosition().x) - OX, 2), round(pcbnew.ToMM(v.GetPosition().y) - OY, 2))] = v
for t in b.GetTracks():         # a re-placed part's old GND stub (pad -> via) and its via
    if t.GetClass() == "PCB_TRACK" and t.GetNetname() == "GND":
        ends = [(pcbnew.ToMM(e.x) - OX, pcbnew.ToMM(e.y) - OY) for e in (t.GetStart(), t.GetEnd())]
        for k, (ex, ey) in enumerate(ends):
            if any(math.hypot(ex - x, ey - y) < 0.05 for x, y in stale):
                drop.append(t)
                o = ends[1 - k]
                v = vias_at.get((round(o[0], 2), round(o[1], 2)))
                if v is not None and v not in drop:
                    drop.append(v)
                print("removing stale GND stub/via of a re-placed part at", round(ex, 2), round(ey, 2))
                break
pos = [(pcbnew.ToMM(v.GetPosition().x) - OX, pcbnew.ToMM(v.GetPosition().y) - OY) for v in drop
       if v.GetClass() == "PCB_VIA" and v in drop[:len(drop)] and any(
           abs(pcbnew.ToMM(v.GetPosition().x) - OX - dx) < 0.01 and abs(pcbnew.ToMM(v.GetPosition().y) - OY - dy) < 0.01
           for _, dx, dy in DROP_VIAS)]
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
