"""Board setup for the motor board (layout step 0): stack-up, the L2 GND plane, net classes + net patterns,
design-rule minimums and the pre-defined track/via sizes.  Idempotent; close KiCad first.
Run with /usr/bin/python3 (KiCad's pcbnew).   --check  only prints which nets each class pattern catches."""
import fnmatch
import json
import re
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent / "motor_board"
PCB, PRO = PROJ / "motor_board.kicad_pcb", PROJ / "motor_board.kicad_pro"

# ---------------------------------------------------------------- net classes (name, track, clearance, via pad, via drill, patterns)
CLASSES = [
    ("Power", 0.5, 0.15, 0.6, 0.3, ["VBAT", "BAT_IN", "*PSW_S", "VBAT_SW", "W_A", "W_B", "W_C", "*W_SL?"],
     "pack / weapon current: carried by the pours; tracks of these nets are short links to fine-pitch pins (widen where room)"),
    ("Drive", 0.5, 0.15, 0.6, 0.3, ["L_VM", "R_VM", "L_A", "L_B", "L_C", "R_A", "R_B", "R_C"],
     "DRV8316 supply and phases: 8 A peak, 1-2 A rms"),
    ("Gate", 0.25, 0.15, 0.6, 0.3, ["*W_GH?", "*W_GL?", "*PSW_G", "*PSW_RG"],
     "gate drive: 60/120 mA IDRIVE on the weapon (0.25 mm leaves U2's 0.5 mm-pitch pins), route with its source return"),
    ("Sense", 0.2, 0.15, 0.45, 0.25, ["*W_SN?", "*INA_INP", "*INA_INN"],
     "Kelvin sense pairs, route as tight pairs away from the phase nodes"),
    ("Rail", 0.4, 0.15, 0.6, 0.3, ["+5V", "+3V3", "+3V3A"], "logic rails (+5V up to 0.6 A)"),
]
DEFAULT = dict(track=0.15, clearance=0.15, via=0.45, drill=0.25)
TRACKS = [0.127, 0.15, 0.2, 0.3, 0.4, 0.5, 0.8, 1.0, 1.5]
VIAS = [(0.4, 0.2), (0.45, 0.25), (0.6, 0.3), (0.8, 0.4)]
RULES = dict(min_clearance=0.127, min_track_width=0.127, min_via_diameter=0.4, min_through_hole_diameter=0.2,
             min_via_annular_width=0.1, min_hole_clearance=0.25, min_hole_to_hole=0.25, min_copper_edge_clearance=0.3)

# ---------------------------------------------------------------- stack-up (JLC04161H-7628, 1 oz outer + 1 oz inner)
STACKUP = '''		(stackup
			(layer "F.SilkS" (type "Top Silk Screen"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "7628") (epsilon_r 4.4) (loss_tangent 0.02))
			(layer "In1.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 2" (type "core") (thickness 1.065) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
			(layer "In2.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "7628") (epsilon_r 4.4) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen"))
			(copper_finish "ENIG")
			(dielectric_constraints no)
		)
'''


def short(n):
    return n.split("/")[-1]


board = pcbnew.LoadBoard(str(PCB))
nets = sorted({str(n) for n in board.GetNetsByName().keys() if str(n)})
# KiCad matches the pattern against the full net name (local nets are "/sheet/NAME")
catch = {c[0]: sorted(n for n in nets if any(fnmatch.fnmatchcase(short(n), p) for p in c[5])) for c in CLASSES}
PATTERNS = {cls: got for cls, got in catch.items()}     # exact full net names (KiCad matches the full name)
seen = {}
for cls, got in catch.items():
    print(f"{cls:6s} ({len(got)}): {', '.join(short(n) for n in got)}")
    for n in got:
        seen.setdefault(n, []).append(cls)
dup = {n: c for n, c in seen.items() if len(c) > 1}
assert not dup, f"nets in two classes: {dup}"
if "--check" in sys.argv:
    sys.exit(0)

# ---------------------------------------------------------------- L2 GND plane (board outline, solid to vias, thermal spokes on THT)
pro_before = PRO.read_text()
have = [z for z in board.Zones() if z.GetLayer() == pcbnew.In1_Cu and z.GetNetname() == "GND"]
if not have:
    bb = board.GetBoardEdgesBoundingBox()
    z = pcbnew.ZONE(board)
    z.SetLayer(pcbnew.In1_Cu)
    z.SetNetCode(board.GetNetsByName()["GND"].GetNetCode())
    z.SetZoneName("L2 GND plane")
    z.SetAssignedPriority(0)
    z.SetLocalClearance(pcbnew.FromMM(0.2))
    z.SetMinThickness(pcbnew.FromMM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)      # GND through-holes (JBAT2) get spokes: solderable
    z.SetThermalReliefGap(pcbnew.FromMM(0.5))
    z.SetThermalReliefSpokeWidth(pcbnew.FromMM(1.0))            # 4 x 1 mm spokes (DESIGN 6.9)
    ol = z.Outline()
    ol.NewOutline()
    m = pcbnew.FromMM(0.3)                                       # outline pulled in by the copper-to-edge clearance
    for x, y in ((bb.GetLeft() + m, bb.GetTop() + m), (bb.GetRight() - m, bb.GetTop() + m),
                 (bb.GetRight() - m, bb.GetBottom() - m), (bb.GetLeft() + m, bb.GetBottom() - m)):
        ol.Append(x, y)
    board.Add(z)
    print("added the L2 GND plane")

t = pcbnew.ToMM
fps = {f.GetReference(): f for f in board.GetFootprints()}


def pad(ref, num):
    return [p for p in fps[ref].Pads() if p.GetNumber() == num][0]


def lset(*layers):
    ls = pcbnew.LSET()
    for l in layers:
        ls.addLayer(l)
    return ls


# ---------------------------------------------------------------- layer names (display only)
board.SetLayerName(pcbnew.In1_Cu, "L2.GND")
board.SetLayerName(pcbnew.In2_Cu, "L3.PWR+SIG")

# ---------------------------------------------------------------- rule areas: the placement review's keep-outs, so DRC guards them
existing = {z.GetZoneName() for z in board.Zones()}


def rule_area(name, layers, rect=None, poly=None, footprints=True, tracks=False, vias=False, copper=False, pads=False):
    if name in existing:                      # already there: refresh its rules
        z = [q for q in board.Zones() if q.GetZoneName() == name][0]
        z.SetDoNotAllowFootprints(footprints); z.SetDoNotAllowTracks(tracks); z.SetDoNotAllowVias(vias)
        z.SetDoNotAllowZoneFills(copper); z.SetDoNotAllowPads(pads)
        return
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetZoneName(name)
    z.SetLayerSet(lset(*layers))
    z.SetDoNotAllowFootprints(footprints); z.SetDoNotAllowTracks(tracks); z.SetDoNotAllowVias(vias)
    z.SetDoNotAllowZoneFills(copper); z.SetDoNotAllowPads(pads)
    ol = z.Outline(); ol.NewOutline()
    pts = poly or [(rect[0], rect[1]), (rect[2], rect[1]), (rect[2], rect[3]), (rect[0], rect[3])]
    for x, y in pts:
        ol.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    board.Add(z)


bb = board.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05       # board-local origin (front-left corner)
for ref in ("U2", "U3", "U4"):
    ep = max(fps[ref].Pads(), key=lambda p: t(p.GetBoundingBox().GetWidth()) * t(p.GetBoundingBox().GetHeight()))
    b = ep.GetBoundingBox()
    rule_area(f"keepout: {ref} thermal-via field (bottom, parts and tracks)", [pcbnew.B_Cu],
              (t(b.GetLeft()) - 1.0, t(b.GetTop()) - 1.0, t(b.GetRight()) + 1.0, t(b.GetBottom()) + 1.0), tracks=True)
for name, (x0, y0, x1, y1) in (("keepout: weapon gate/sense via corridor (bottom, parts)", (34.5, 8.5, 70.5, 19.0)),
                               ("keepout: U2 fan-out (bottom, parts)", (49.3, 18.0, 58.9, 27.3)),
                               ("keepout: U3 logic-pin escape (bottom, parts)", (20.0, 32.6, 27.5, 35.0))):
    rule_area(name, [pcbnew.B_Cu], (OX + x0, OY + y0, OX + x1, OY + y1))
for ref, f in fps.items():
    clear = {"JBAT": 2.0, "JW": 2.0, "JL": 1.5, "JR": 1.5, "J4": 1.5}
    m = next((v for k, v in clear.items() if ref.startswith(k)), None)
    if m is None:
        continue
    for p in f.Pads():
        if p.GetAttribute() != pcbnew.PAD_ATTRIB_PTH:
            continue
        c, r = p.GetPosition(), t(p.GetBoundingBox().GetWidth()) / 2 + m
        poly = [(t(c.x) + r * __import__("math").cos(a / 16 * 6.283185), t(c.y) + r * __import__("math").sin(a / 16 * 6.283185)) for a in range(16)]
        rule_area(f"keepout: {ref}.{p.GetNumber()} solder zone (bottom, parts)", [pcbnew.B_Cu], poly=poly)
for ref in ("MH1", "MH2", "MH3", "MH4"):
    c = fps[ref].GetPosition()
    poly = [(t(c.x) + 2.6 * __import__("math").cos(a / 16 * 6.283185), t(c.y) + 2.6 * __import__("math").sin(a / 16 * 6.283185)) for a in range(16)]
    rule_area(f"keepout: {ref} washer (outer layers, everything)", [pcbnew.F_Cu, pcbnew.B_Cu], poly=poly,
              footprints=False, tracks=True, vias=True, copper=True, pads=False)

# ---------------------------------------------------------------- thermal vias in the exposed pads (GND), 1.1 mm pitch
gnd = board.GetNetsByName()["GND"]
have_via = {(v.GetPosition().x, v.GetPosition().y) for v in board.GetTracks() if v.GetClass() == "PCB_VIA"}
nvia = 0
for ref in ("U2", "U3", "U4"):
    ep = max(fps[ref].Pads(), key=lambda p: t(p.GetBoundingBox().GetWidth()) * t(p.GetBoundingBox().GetHeight()))
    b = ep.GetBoundingBox()
    x0, y0, x1, y1 = t(b.GetLeft()) + 0.55, t(b.GetTop()) + 0.55, t(b.GetRight()) - 0.55, t(b.GetBottom()) - 0.55
    nx, ny = int((x1 - x0) / 1.1) + 1, int((y1 - y0) / 1.1) + 1
    sx, sy = ((x1 - x0) / (nx - 1) if nx > 1 else 0), ((y1 - y0) / (ny - 1) if ny > 1 else 0)
    for i in range(nx):
        for j in range(ny):
            pos = pcbnew.VECTOR2I_MM(x0 + i * sx, y0 + j * sy)
            if (pos.x, pos.y) in have_via:
                continue
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pos); v.SetDrill(pcbnew.FromMM(0.3)); v.SetWidth(pcbnew.FromMM(0.6))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd)
            board.Add(v)
            nvia += 1
print("thermal vias added:", nvia)

# ---------------------------------------------------------------- silkscreen labels (DESIGN 6.9 markings + wire names)
have_txt = {(d.GetText(), d.GetLayer()) for d in board.GetDrawings() if d.GetClass() == "PCB_TEXT"}


def label(text, x, y, layer, size=0.8, rot=0):
    if (text, layer) in have_txt:
        return
    s_ = pcbnew.PCB_TEXT(board)
    s_.SetText(text); s_.SetLayer(layer); s_.SetPosition(pcbnew.VECTOR2I_MM(x, y))
    s_.SetTextSize(pcbnew.VECTOR2I_MM(size, size)); s_.SetTextThickness(pcbnew.FromMM(size * 0.15))
    s_.SetTextAngleDegrees(rot)
    if layer == pcbnew.B_SilkS:
        s_.SetMirrored(True)
    board.Add(s_)


# wire names on the bottom (the solder side), inside each hole's part-free solder zone
for ref, text, dx, dy in (("JBAT1", "BAT+", 3.3, 0), ("JBAT2", "BAT-", 0, 3.2), ("JW1", "WA", 0, 3.2), ("JW2", "WB", 0, 3.2),
                          ("JW3", "WC", 0, 3.2), ("JL1", "LA", 0, -2.4), ("JL2", "LB", 0, -2.4), ("JL3", "LC", 0, -2.4),
                          ("JR1", "RA", -2.5, 0), ("JR2", "RB", -2.5, 0), ("JR3", "RC", -2.5, 0)):
    c = fps[ref].GetPosition()
    label(text, t(c.x) + dx, t(c.y) + dy, pcbnew.B_SilkS)
# connector pin markings (DESIGN 6.9): J4 B- at pin 1, B4+ at pin 5; J2/J3 VS at pin 1, T at pin 6
for ref, num, text, dx, dy in (("J4", "1", "B-", 2.2, 0), ("J4", "5", "B4+", 2.4, 0)):
    c = pad(ref, num).GetPosition()
    label(text, t(c.x) + dx, t(c.y) + dy, pcbnew.F_SilkS)
for ref in ("J2", "J3"):
    lay = pcbnew.B_SilkS if fps[ref].IsFlipped() else pcbnew.F_SilkS
    for num, text in (("1", "VS"), ("6", "T")):
        c = pad(ref, num).GetPosition()
        label(f"{text} {ref}" if num == "1" else text, t(c.x), t(c.y) - 1.8, lay, size=0.8)
label("FRONT (drum)", OX + 47.6, OY + 1.2, pcbnew.B_SilkS, size=0.8)
label("MOTOR BOARD rev L", OX + 52.0, OY + 12.0, pcbnew.B_SilkS, size=1.0)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(PCB), board)

# ---------------------------------------------------------------- stack-up into (setup ...)
s = PCB.read_text()
s = re.sub(r"\n\t\t\(stackup.*?\n\t\t\)\n", "\n", s, flags=re.S)
s = s.replace("\n\t(setup\n", "\n\t(setup\n" + STACKUP, 1)
assert "(stackup" in s
PCB.write_text(s)

# ---------------------------------------------------------------- project: net classes, patterns, rules, sizes
p = json.loads(pro_before)          # SaveBoard rewrote the project file: start from the one we had
ns = p["net_settings"]
proto = dict(ns["classes"][0])
default = dict(proto, name="Default", track_width=DEFAULT["track"], clearance=DEFAULT["clearance"],
               via_diameter=DEFAULT["via"], via_drill=DEFAULT["drill"])
classes = [default]
COLOURS = {"Power": "rgba(220, 40, 40, 0.900)", "Drive": "rgba(240, 140, 0, 0.900)", "Gate": "rgba(170, 60, 220, 0.900)",
           "Sense": "rgba(0, 180, 90, 0.900)", "Rail": "rgba(40, 110, 240, 0.900)"}
for i, (name, w, clr, via, drill, pats, why) in enumerate(CLASSES):
    classes.append(dict(proto, name=name, track_width=w, clearance=clr, via_diameter=via, via_drill=drill, priority=i,
                        pcb_color=COLOURS[name]))
ns["classes"] = classes
ns["netclass_patterns"] = [{"netclass": cls, "pattern": n} for cls, got in PATTERNS.items() for n in got]
ds = p["board"]["design_settings"]
ds["rules"].update(RULES)
ds["track_widths"] = [0.0] + TRACKS
ds["via_dimensions"] = [{"diameter": 0.0, "drill": 0.0}] + [{"diameter": d, "drill": dr} for d, dr in VIAS]
PRO.write_text(json.dumps(p, indent=2) + "\n")
print("project: classes", [c["name"] for c in classes], "| patterns", len(ns["netclass_patterns"]))
