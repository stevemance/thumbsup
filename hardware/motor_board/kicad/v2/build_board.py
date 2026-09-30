"""v2: a brand-new 4-layer board straight from the schematic (nothing inherited from the v1 board file).

/usr/bin/python3 build_board.py      (writes ../motor_board/motor_board.kicad_pcb, project rules, custom DRC rules)

- netlist from kicad-cli; footprints from the project library / KiCad's stock libraries, linked to their symbols
- 4 copper layers, JLC041611-1080 stack-up (review/v2_lessons/README.md 3.1)
- outline 85 x 35 mm, 1.5 mm corner radius; MH1-MH4 at the corners
- every other part staged below the outline (y > 40 mm), top-side parts first, sorted by size
- design rules = JLCPCB 4-layer capabilities (jlcpcb.com/capabilities/pcb-capabilities, read 2026-09-29) with margin;
  the per-rule source is in RULES below and in motor_board.kicad_dru"""
import json
import math
import subprocess
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
MB = HERE.parents[1]                                  # hardware/motor_board
PROJ = MB / "kicad" / "motor_board"
PCB = PROJ / "motor_board.kicad_pcb"
sys.path.insert(0, str(MB / "kicad" / "lib_build"))
import kicadlib as K  # noqa: E402

BW, BH, R_CORNER = 85.0, 35.0, 1.5
OX, OY = 100.0, 70.0
MH = {"MH1": (3.0, 3.0), "MH2": (BW - 3.0, 3.0), "MH3": (3.0, BH - 3.0), "MH4": (BW - 3.0, BH - 3.0)}

STACKUP4 = '''		(stackup
			(layer "F.SilkS" (type "Top Silk Screen"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "prepreg") (thickness 0.069) (material "1080") (epsilon_r 3.91) (loss_tangent 0.02))
			(layer "In1.Cu" (type "copper") (thickness 0.03))
			(layer "dielectric 2" (type "core") (thickness 1.23) (material "FR4 core") (epsilon_r 4.6) (loss_tangent 0.02))
			(layer "In2.Cu" (type "copper") (thickness 0.03))
			(layer "dielectric 3" (type "prepreg") (thickness 0.069) (material "1080") (epsilon_r 3.91) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen"))
			(copper_finish "ENIG")
			(dielectric_constraints no)
		)
'''

# JLC 4-layer capability (value) -> our rule (value): margin on everything that is cheap to keep
RULES = dict(
    min_clearance=0.10,             # JLC min spacing 0.09 (outer and inner, 1 oz)
    min_track_width=0.10,           # JLC min track 0.09
    min_via_diameter=0.40,          # JLC min via 0.25 / 0.15 drill; 0.4/0.2 stays in the no-surcharge range
    min_through_hole_diameter=0.20,  # JLC min 0.15
    min_via_annular_width=0.10,     # 0.4 pad on 0.2 drill
    min_hole_to_hole=0.25,          # JLC via hole-to-hole 0.2 (pad holes 0.45: in the custom rules)
    min_hole_clearance=0.20,        # JLC via hole to track / inner copper 0.2
    min_copper_edge_clearance=0.30,  # JLC 0.2 from routed edges (+ the ±0.2 edge tolerance)
    min_silk_clearance=0.15,        # JLC pad-to-silk 0.15
    solder_mask_to_copper_clearance=0.0,
    min_resolved_spokes=2,
)
# net classes: width / clearance / via (pad, drill)
CLASSES = {
    "Default": (0.15, 0.127, 0.40, 0.20),
    "Power": (0.50, 0.15, 0.60, 0.30),
    "Gate": (0.25, 0.15, 0.50, 0.25),
    "Sense": (0.20, 0.15, 0.45, 0.25),
    "Rail": (0.20, 0.15, 0.45, 0.25),    # +3V3/+5V branches (<= 0.45 A) fit 0.5 mm-pitch pins; trunks drawn wider by hand
}
DRU = """(version 1)
# JLCPCB 4-layer capabilities (jlcpcb.com/capabilities/pcb-capabilities, 2026-09-29), with margin.
(rule "JLC PTH pad hole to track 0.28 (0.35 recommended)"
  (constraint hole_clearance (min 0.30mm))
  (condition "A.Type == 'Pad' && A.isPlated() && A.Pad_Type == 'Through-hole'"))
(rule "JLC pad hole to pad hole 0.45"
  (constraint hole_to_hole (min 0.45mm))
  (condition "A.Type == 'Pad' && B.Type == 'Pad'"))
(rule "JLC inner-layer PTH pad hole to copper 0.3"
  (layer inner)
  (constraint hole_clearance (min 0.30mm))
  (condition "A.Type == 'Pad' && A.Pad_Type == 'Through-hole'"))
(rule "JLC NPTH min 0.5"
  (constraint hole_size (min 0.50mm))
  (condition "A.Type == 'Pad' && A.Pad_Type == 'NPTH, mechanical'"))
(rule "JLC SMD pad to pad 0.15 (different nets)"
  (constraint clearance (min 0.15mm))
  (condition "A.Type == 'Pad' && B.Type == 'Pad' && A.Net != B.Net"))
(rule "JLC silkscreen line >= 0.15, text >= 1.0"
  (layer "F.SilkS") (constraint text_thickness (min 0.15mm)) (constraint text_height (min 1.0mm)))
(rule "JLC silkscreen line >= 0.15, text >= 1.0 (bottom)"
  (layer "B.SilkS") (constraint text_thickness (min 0.15mm)) (constraint text_height (min 1.0mm)))
(rule "v2: L2 is a solid GND plane, no tracks or vias of other nets' tracks on it"
  (layer "In1.Cu")
  (constraint disallow track))
"""


def load_netlist():
    net = HERE / "out" / "v2.net"
    net.parent.mkdir(exist_ok=True)
    r = subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o", str(net), str(PROJ / "motor_board.kicad_sch")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    tree = K.parse(net.read_text())
    comps = {}
    for c in K.children(K.child(tree, "components"), "comp"):
        ref = K.child(c, "ref")[1]
        props = {K.child(p, "name")[1]: (K.child(p, "value") or [None, ""])[1] for p in K.children(c, "property")}
        fields = {K.child(f, "name")[1]: (f[2] if len(f) > 2 else "") for f in K.children(K.child(c, "fields") or ["fields"], "field")}
        sp = K.child(c, "sheetpath")
        comps[ref] = dict(value=K.child(c, "value")[1], footprint=K.child(c, "footprint")[1], fields=fields,
                          dnp="dnp" in props, sheetname=props.get("Sheetname", ""), sheetfile=props.get("Sheetfile", ""),
                          path=K.child(sp, "tstamps")[1] + K.child(c, "tstamps")[1], pins={})
    nets = {}
    for n in K.children(K.child(tree, "nets"), "net"):
        name = K.child(n, "name")[1]
        nodes = [(K.child(nd, "ref")[1], K.child(nd, "pin")[1]) for nd in K.children(n, "node")]
        nets[name] = nodes
        for ref, pin in nodes:
            comps[ref]["pins"][pin] = name
    return comps, nets


def load_fp(fpid):
    lib, name = fpid.split(":", 1)
    for d in (PROJ, Path("/usr/share/kicad/footprints")):
        p = d / f"{lib}.pretty"
        if (p / f"{name}.kicad_mod").exists():
            return pcbnew.FootprintLoad(str(p), name)
    raise FileNotFoundError(fpid)


def P(x, y):
    return pcbnew.VECTOR2I_MM(OX + x, OY + y)


comps, nets = load_netlist()
board = pcbnew.BOARD()
board.SetCopperLayerCount(4)
for lid, name in ((pcbnew.F_Cu, "L1.TOP"), (pcbnew.In1_Cu, "L2.GND"), (pcbnew.In2_Cu, "L3.PWR_GND"), (pcbnew.B_Cu, "L4.BOT")):
    board.SetLayerName(lid, name)
board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(1.6))
tb = board.GetTitleBlock()
tb.SetTitle("Motor Board"); tb.SetRevision("${REV}"); tb.SetCompany("Daedalus Innovation Labs LLC")
tb.SetComment(0, "Design: hardware/motor_board/DESIGN.md; layout v2 (4 layers)")
netinfo = {}
for name in nets:
    ni = pcbnew.NETINFO_ITEM(board, name)
    board.Add(ni)
    netinfo[name] = ni


def edge(shape, *pts):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(shape); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.1))
    if shape == pcbnew.SHAPE_T_SEGMENT:
        s.SetStart(P(*pts[0])); s.SetEnd(P(*pts[1]))
    else:
        s.SetArcGeometry(P(*pts[0]), P(*pts[1]), P(*pts[2]))
    board.Add(s)


r = R_CORNER
for a, b in (((r, 0), (BW - r, 0)), ((BW, r), (BW, BH - r)), ((BW - r, BH), (r, BH)), ((0, BH - r), (0, r))):
    edge(pcbnew.SHAPE_T_SEGMENT, a, b)
for cx, cy, a0 in ((BW - r, r, 270), (BW - r, BH - r, 0), (r, BH - r, 90), (r, r, 180)):
    edge(pcbnew.SHAPE_T_ARC, *[(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in (a0, a0 + 45, a0 + 90)])

fps = {}
for ref, c in sorted(comps.items()):
    fp = load_fp(c["footprint"])
    fp.SetFPID(pcbnew.LIB_ID(*c["footprint"].split(":", 1)))
    fp.SetReference(ref)
    fp.SetValue(c["value"])
    fp.SetPath(pcbnew.KIID_PATH(c["path"]))
    fp.SetSheetname(c["sheetname"]); fp.SetSheetfile(c["sheetfile"])
    for k, v in c["fields"].items():
        if k not in ("Footprint", "Value", "Reference"):
            fp.SetField(k, v)
    for f in fp.GetFields():
        if f.GetName() != "Reference":
            f.SetVisible(False)
    fp.Reference().SetTextSize(pcbnew.VECTOR2I_MM(1.0, 1.0)); fp.Reference().SetTextThickness(pcbnew.FromMM(0.15))
    if c["dnp"]:
        fp.SetDNP(True)
    for pad in fp.Pads():
        n = c["pins"].get(pad.GetNumber())
        if n:
            pad.SetNet(netinfo[n])
    board.Add(fp)
    fps[ref] = fp
missing = [(r_, p) for r_, c in comps.items() for p in c["pins"] if p not in {q.GetNumber() for q in fps[r_].Pads()}]
assert not missing, missing

# MH at the corners, everything else staged below the board
for ref, (x, y) in MH.items():
    fps[ref].SetPosition(P(x, y))
    fps[ref].Reference().SetVisible(False)          # no silk at the board edge
stage = sorted((f for r_, f in fps.items() if r_ not in MH), key=lambda f: -f.GetBoundingBox(False, False).GetArea())
x, y, rowh = 0.0, BH + 5.0, 0.0
for f in stage:
    bb = f.GetBoundingBox(False, False)
    w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
    if x + w > 120:
        x, y, rowh = 0.0, y + rowh + 1.0, 0.0
    off = f.GetPosition() - bb.GetCenter()
    f.SetPosition(P(x + w / 2, y + h / 2) + off)
    x += w + 1.0
    rowh = max(rowh, h)

pro_path = PROJ / "motor_board.kicad_pro"
pro_before = pro_path.read_text()
pcbnew.SaveBoard(str(PCB), board)
txt = PCB.read_text()                    # a new BOARD has no stack-up block: insert ours at the top of (setup
assert "(stackup" not in txt
k = txt.index("\t(setup\n") + len("\t(setup\n")
PCB.write_text(txt[:k] + STACKUP4 + txt[k:])

pro = json.loads(pro_before)             # SaveBoard rewrites the project file: keep ours, set the JLC rules
pro["board"]["design_settings"]["rules"].update(RULES)
classes = {c["name"]: c for c in pro["net_settings"]["classes"]}
for name, (w, clr, vd, vdr) in CLASSES.items():
    if name in classes:
        classes[name].update(track_width=w, clearance=clr, via_diameter=vd, via_drill=vdr)
pro_path.write_text(json.dumps(pro, indent=2) + "\n")
(PROJ / "motor_board.kicad_dru").write_text(DRU)
subprocess.run(["/usr/bin/python3", str(MB / "kicad" / "gen" / "set3d.py"), str(PCB)], check=True, capture_output=True)
top = sum(1 for f in fps.values() if not f.IsFlipped())
print(f"v2 board: {len(fps)} footprints ({top} top as loaded), {len(nets)} nets, staged below the outline; "
      f"classes {sorted(classes)}")
