"""Layout checks for the motor board: run after every routing session.  /usr/bin/python3 layout_check.py [--no-render]

Prints (and writes out/check/report.txt):
  1. KiCad DRC: errors by type (must be 0), schematic parity (must be 0), unconnected items by net class (progress)
  2. gate escapes: each weapon FET gate pin (and Q8's) has a same-net via with a stub from the pin
  3. via fields: vias of each power pour's net inside its outline, against a minimum
  4. copper pours: filled, and how many separate islands each fill has (> 1 = copper cut off from its connection)
  5. GND pads with no via, no GND pour and no tie yet (they need one while routing)
Renders each copper layer to out/check/*.png (top view; B.Cu mirrored so it reads as seen from below)."""
import collections
import json
import math
import subprocess
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent / "motor_board"
PCB = PROJ / "motor_board.kicad_pcb"
OUT = HERE / "out" / "check"
OUT.mkdir(parents=True, exist_ok=True)
lines = []


def say(s=""):
    print(s)
    lines.append(s)


# ---------------------------------------------------------------- 1. DRC
drc_json = OUT / "drc.json"
subprocess.run(["kicad-cli", "pcb", "drc", "--schematic-parity", "--format", "json", "-o", str(drc_json), str(PCB)],
               capture_output=True, text=True)
r = json.loads(drc_json.read_text())
viol = r["violations"]
errs = collections.Counter(v["type"] for v in viol if v["severity"] == "error")
warns = collections.Counter(v["type"] for v in viol if v["severity"] == "warning")
say("== 1. DRC")
say(f"  errors: {sum(errs.values())} {dict(errs) if errs else ''}")
for v in viol:
    if v["severity"] == "error":
        say("    " + v["type"] + " | " + " / ".join(i["description"][:70] for i in v["items"]))
say(f"  warnings: {dict(warns)}")
say(f"  schematic parity issues: {len(r.get('schematic_parity', []))}")

board = pcbnew.LoadBoard(str(PCB))
t = pcbnew.ToMM
bb = board.GetBoardEdgesBoundingBox()
OX, OY = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
fps = {f.GetReference(): f for f in board.GetFootprints()}
cls_of = {str(n).split("/")[-1]: str(ni.GetNetClassName()) for n, ni in board.GetNetsByName().items() if str(n)}
unc = collections.Counter()
for u in r.get("unconnected_items", []):
    d = u["items"][0]["description"]
    n = d[d.find("[") + 1:d.find("]")].split("/")[-1] if "[" in d else "?"
    unc[cls_of.get(n, "?")] += 1
say(f"  unconnected items: {len(r.get('unconnected_items', []))} by class {dict(unc)}")

vias = [v for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
tracks = [x for x in board.GetTracks() if x.GetClass() == "PCB_TRACK"]


def L(p):
    return t(p.x) - OX, t(p.y) - OY


def pad_of(ref, num):
    return [p for p in fps[ref].Pads() if p.GetNumber() == num][0]


def in_box(pt, p, m=0.0):
    b = p.GetBoundingBox()
    x, y = pt
    return t(b.GetLeft()) - OX - m <= x <= t(b.GetRight()) - OX + m and t(b.GetTop()) - OY - m <= y <= t(b.GetBottom()) - OY + m


# ---------------------------------------------------------------- 2. gate escapes
say("== 2. gate escape vias (via + stub at each gate pin)")
for ref in ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q8"):
    g = pad_of(ref, "4")
    n = g.GetNetname()
    near = [v for v in vias if v.GetNetname() == n and math.dist(L(v.GetPosition()), L(g.GetPosition())) < 2.6]
    stub = any(x.GetNetname() == n and (in_box(L(x.GetStart()), g) or in_box(L(x.GetEnd()), g)) for x in tracks)
    say(f"  {ref} gate ({n.split('/')[-1]}): {'OK' if near and stub else 'MISSING'}"
        + (f" via at ({L(near[0].GetPosition())[0]:.2f}, {L(near[0].GetPosition())[1]:.2f})" if near else ""))

# ---------------------------------------------------------------- 3. via fields
say("== 3. via fields in the power pours")
MIN = {"HS drain VBAT": 8, "shunt/cap GND": 10, "pack: VBAT (": 15, "pack: GND at C1": 4, "pack: GND at D1": 2, "pack: GND at C14": 2}


def poly(z):
    ol = z.Outline()
    return [(t(ol.CVertex(i).x) - OX, t(ol.CVertex(i).y) - OY) for i in range(ol.FullPointCount())]


def inside(pg, x, y):
    c = False
    for i in range(len(pg)):
        (x1, y1), (x2, y2) = pg[i], pg[(i + 1) % len(pg)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


for z in sorted(board.Zones(), key=lambda z: z.GetZoneName()):
    name = z.GetZoneName()
    key = max((k for k in MIN if k in name), key=len, default=None)   # most specific name wins
    if not key or z.GetIsRuleArea():
        continue
    pg = poly(z)
    n = sum(1 for v in vias if v.GetNetname() == z.GetNetname() and inside(pg, *L(v.GetPosition())))
    if name.startswith("cell B: shunt"):          # cell B's return also uses the via-in-pad in RS2's GND pad
        n += sum(1 for v in vias if v.GetNetname() == z.GetNetname() and in_box(L(v.GetPosition()), pad_of("RS2", "2")))
    say(f"  {name}: {n} vias (min {MIN[key]}) {'OK' if n >= MIN[key] else 'LOW'}")

# ---------------------------------------------------------------- 4. pours
say("== 4. copper pours (filled area, islands)")
for z in sorted(board.Zones(), key=lambda z: z.GetZoneName()):
    if z.GetIsRuleArea():
        continue
    for layer in z.GetLayerSet().Seq():
        fp = z.GetFilledPolysList(layer)
        islands = fp.OutlineCount()
        area = fp.Area() / 1e12 if islands else 0.0
        flag = "" if islands == 1 else ("  <-- NOT FILLED" if islands == 0 else f"  <-- {islands} islands")
        say(f"  {z.GetZoneName()} [{board.GetLayerName(layer)}]: {area:.0f} mm2{flag}")

# ---------------------------------------------------------------- 5. GND pads still to connect
say("== 5. GND pads with no via / pour / tie yet (give them one while routing)")
gnd_polys = [(poly(z), z.GetLayer()) for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "GND"
             and z.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu)]
todo = []
for f in board.GetFootprints():
    for p in f.Pads():
        if p.GetNetname() != "GND" or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        c = L(p.GetPosition())
        lay = pcbnew.B_Cu if f.IsFlipped() else pcbnew.F_Cu
        if any(la == lay and inside(pg, *c) for pg, la in gnd_polys):
            continue
        if any(v.GetNetname() == "GND" and in_box(L(v.GetPosition()), p, 0.8) for v in vias):
            continue
        if any(x.GetNetname() == "GND" and (in_box(L(x.GetStart()), p) or in_box(L(x.GetEnd()), p)) for x in tracks):
            continue
        todo.append(f"{f.GetReference()}.{p.GetNumber()}")
say(f"  {len(todo)}: {' '.join(sorted(todo))}")
(OUT / "report.txt").write_text("\n".join(lines) + "\n")

# ---------------------------------------------------------------- renders
if "--no-render" not in sys.argv:
    sets = {"L1_top": "F.Cu,F.SilkS,Edge.Cuts", "L2_gnd": "In1.Cu,Edge.Cuts", "L3_pwr": "In2.Cu,Edge.Cuts",
            "L4_sig": "In3.Cu,Edge.Cuts", "L5_gnd": "In4.Cu,Edge.Cuts",
            "L6_bottom": "B.Cu,B.SilkS,Edge.Cuts"}
    for name, layers in sets.items():
        args = ["kicad-cli", "pcb", "export", "svg", "--layers", layers, "--mode-single", "--fit-page-to-board",
                "--exclude-drawing-sheet", "-o", str(OUT / f"{name}.svg"), str(PCB)]
        if name == "L6_bottom":
            args.insert(-2, "--mirror")
        subprocess.run(args, capture_output=True)
    code = ("import cairosvg,sys\nfor s in sys.argv[1:]:\n cairosvg.svg2png(url=s, write_to=s[:-4]+'.png', output_width=2400, "
            "background_color='white')")
    subprocess.run(["uvx", "--with", "cairosvg", "python", "-c", code] + [str(OUT / f"{n}.svg") for n in sets], capture_output=True)
    say(f"renders: {OUT}/L1_top.png, L2_gnd.png, L3_pwr.png, L4_sig.png, L5_gnd.png, L6_bottom.png (bottom mirrored: as seen from below)")
