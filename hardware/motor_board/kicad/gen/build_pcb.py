"""Create motor_board.kicad_pcb from the schematic (kicad-cli netlist): footprints linked to their symbols (so
"Update PCB from Schematic" matches them), nets on pads, a placeholder outline, 4 copper layers, and a rough
floorplan: key parts placed explicitly, every other part put at the nearest free spot to the pads it connects to.

Run with the system python3 (KiCad's pcbnew module)."""
import collections
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, "/home/smance/projects/thumbsup/hardware/motor_board/kicad/lib_build")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kicadlib as K  # noqa: E402
from blocks import BLOCKS, order_key  # noqa: E402

MB = Path("/home/smance/projects/thumbsup/hardware/motor_board")
PROJ = MB / "kicad" / "motor_board"
PCB = PROJ / "motor_board.kicad_pcb"
TMP = Path(__file__).resolve().parent / "out"
NET = TMP / "pcb.net"
BW, BH = 75.0, 60.0            # placeholder outline (DESIGN §6.13: ~3600-4400 mm2; settled at layout)
OX, OY = 100.0, 70.0            # board origin on the page
RAILS = {"GND", "+3V3", "+5V", "+3V3A", "VBAT"}

# ---------------------------------------------------------------- explicit placement (board mm, courtyard centre)
T, B = "top", "bottom"
EXPLICIT = {
    "MH1": (3.5, 3.5, 0, T), "MH2": (BW - 3.5, 3.5, 0, T), "MH3": (3.5, BH - 3.5, 0, T), "MH4": (BW - 3.5, BH - 3.5, 0, T),
    # power entry along the top edge: BAT holes -> Q7/Q8 -> RS4 -> C1 -> bridge
    "JBAT1": (4.5, 10.5, 0, T), "JBAT2": (4.5, 17.0, 0, T),
    "Q7": (11.5, 8.0, 180, T), "Q8": (19.2, 8.0, 0, T),      # common source: pins face each other
    "RS4": (27.5, 5.5, 0, T), "D1": (27.5, 11.5, 0, T),
    "C1": (39.0, 8.5, 0, T),
    # weapon bridge: one row per phase, drain tab left / source pins right (HS pins face the LS tab = phase node),
    # LS source -> shunt -> GND; the local 10 uF in the gap under each HS FET
    "Q1": (50.0, 9.5, 180, T), "Q2": (57.7, 9.5, 180, T), "RS1": (63.9, 9.5, 90, T), "JW1": (69.8, 10.5, 0, T),
    "Q3": (50.0, 18.1, 180, T), "Q4": (57.7, 18.1, 180, T), "RS2": (63.9, 18.1, 90, T), "JW2": (69.8, 18.5, 0, T),
    "Q5": (50.0, 26.7, 180, T), "Q6": (57.7, 26.7, 180, T), "RS3": (63.9, 26.7, 90, T), "JW3": (69.8, 26.7, 0, T),
    "C25": (50.0, 13.8, 0, T), "C26": (50.0, 22.4, 0, T), "C31": (50.0, 31.3, 0, T),
    "TH1": (57.7, 31.3, 0, T),
    "U2": (40.0, 25.0, 180, T),      # gate/sense pins (8-22) toward the bridge, logic pins toward the MCU
    "U7": (27.5, 17.5, 0, T),
    "U8": (16.0, 29.0, 0, T), "J4": (6.5, 29.0, "edge-left", T),
    "U1": (30.0, 44.0, 0, T),
    "J1": (52.0, 44.0, 0, B),
    "U3": (14.0, 49.0, 0, T), "JL1": (10.0, 57.0, 0, T), "JL2": (14.0, 57.0, 0, T), "JL3": (18.0, 57.0, 0, T),
    "U4": (62.0, 47.0, 0, T), "JR1": (56.0, 57.0, 0, T), "JR2": (60.0, 57.0, 0, T), "JR3": (64.0, 57.0, 0, T),
    "J2": (3.3, 44.0, "edge-left", T), "J3": (BW - 3.3, 40.0, "edge-right", T),
    "D3": (40.0, BH - 1.5, 0, T),
}
BOTTOM_BLOCKS = {"Sensor L (J2)", "Sensor R (J3)", "Weapon interlock (AND)", "Dynamic ARM"}
TOP_ALWAYS = re.compile(r"^(TP\d+|J\d+|JP\d+)$")     # test pads and connectors stay on top (JP: reachable)


# ---------------------------------------------------------------- netlist
def load_netlist():
    r = subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o", str(NET), str(PROJ / "motor_board.kicad_sch")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    tree = K.parse(NET.read_text())
    comps = {}
    for c in K.children(K.child(tree, "components"), "comp"):
        ref = K.child(c, "ref")[1]
        props = {K.child(p, "name")[1]: (K.child(p, "value") or [None, ""])[1] for p in K.children(c, "property")}
        fields = {K.child(f, "name")[1]: (f[2] if len(f) > 2 else "") for f in K.children(K.child(c, "fields") or ["fields"], "field")}
        sp = K.child(c, "sheetpath")
        comps[ref] = dict(value=K.child(c, "value")[1], footprint=K.child(c, "footprint")[1], fields=fields,
                          dnp="dnp" in props, sheetname=props.get("Sheetname", ""), sheetfile=props.get("Sheetfile", ""),
                          path=K.child(sp, "tstamps")[1] + K.child(c, "tstamps")[1], desc=(K.child(c, "description") or ["", ""])[1],
                          pins={})
    nets = {}
    for n in K.children(K.child(tree, "nets"), "net"):
        name = K.child(n, "name")[1]
        nodes = [(K.child(nd, "ref")[1], K.child(nd, "pin")[1]) for nd in K.children(n, "node")]
        nets[name] = nodes
        for ref, pin in nodes:
            comps[ref]["pins"][pin] = name
    return comps, nets


def short(net):
    return net.split("/")[-1]


def load_fp(fpid):
    lib, name = fpid.split(":", 1)
    for d in (PROJ, Path("/usr/share/kicad/footprints")):
        p = d / f"{lib}.pretty"
        if (p / f"{name}.kicad_mod").exists():
            return pcbnew.FootprintLoad(str(p), name)
    raise FileNotFoundError(fpid)


# ---------------------------------------------------------------- board
comps, nets = load_netlist()
board = pcbnew.BOARD()
board.SetCopperLayerCount(4)
ds = board.GetDesignSettings()
ds.SetBoardThickness(pcbnew.FromMM(1.6))
board.SetLayerName(pcbnew.In1_Cu, "In1.Cu")
tb = board.GetTitleBlock()
tb.SetTitle("Motor Board"); tb.SetRevision("${REV}"); tb.SetCompany("Daedalus Innovation Labs LLC")
tb.SetComment(0, "Design: hardware/motor_board/DESIGN.md")
netinfo = {}
for name in nets:
    ni = pcbnew.NETINFO_ITEM(board, name)
    board.Add(ni)
    netinfo[name] = ni


def P(x, y):
    return pcbnew.VECTOR2I_MM(OX + x, OY + y)


def outline(r=2.0):
    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(P(*a)); s.SetEnd(P(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.1)); board.Add(s)

    def arc(cx, cy, a0):
        k = r * math.sqrt(0.5)
        pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in (a0, a0 + 45, a0 + 90)]
        a = pcbnew.PCB_SHAPE(board); a.SetShape(pcbnew.SHAPE_T_ARC); a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(pcbnew.FromMM(0.1))
        a.SetArcGeometry(P(*pts[0]), P(*pts[1]), P(*pts[2])); board.Add(a)
    seg((r, 0), (BW - r, 0)); seg((BW, r), (BW, BH - r)); seg((BW - r, BH), (r, BH)); seg((0, BH - r), (0, r))
    arc(BW - r, r, 270); arc(BW - r, BH - r, 0); arc(r, BH - r, 90); arc(r, r, 180)


outline()
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
        if f.GetName() not in ("Reference",):
            f.SetVisible(False)
    fp.Reference().SetTextSize(pcbnew.VECTOR2I_MM(0.8, 0.8)); fp.Reference().SetTextThickness(pcbnew.FromMM(0.12))
    if c["dnp"]:
        fp.SetDNP(True)
    for pad in fp.Pads():
        n = c["pins"].get(pad.GetNumber())
        if n:
            pad.SetNet(netinfo[n])
    board.Add(fp)
    fps[ref] = fp
missing_pads = [(r, p) for r, c in comps.items() for p in c["pins"] if p not in {q.GetNumber() for q in fps[r].Pads()}]
assert not missing_pads, missing_pads


# ---------------------------------------------------------------- geometry helpers (board-local mm)
def set_pose(fp, x, y, rot, side):
    want_back = side == B
    if fp.IsFlipped() != want_back:
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(P(x, y))


def court(fp):
    """courtyard bbox in board-local mm (falls back to the pads' bbox)."""
    fp.BuildCourtyardCaches()
    c = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
    if c.OutlineCount():
        bb = c.BBox()
        x0, y0, x1, y1 = bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()
    else:
        xs, ys = [], []
        for p in fp.Pads():
            b = p.GetBoundingBox(); xs += [b.GetLeft(), b.GetRight()]; ys += [b.GetTop(), b.GetBottom()]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        pad = pcbnew.FromMM(0.25)
        x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    t = pcbnew.ToMM
    return t(x0) - OX, t(y0) - OY, t(x1) - OX, t(y1) - OY


def pad_xy(fp, num=None):
    pts = [(pcbnew.ToMM(p.GetPosition().x) - OX, pcbnew.ToMM(p.GetPosition().y) - OY) for p in fp.Pads() if num is None or p.GetNumber() == num]
    return pts


def centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


occ = {T: [], B: []}         # placed courtyard rects per side
placed = {}


def occupy(ref, side_list):
    r = court(fps[ref])
    for s in side_list:
        occ[s].append((r, ref))


def sides_of(fp):
    tht = any(p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) for p in fp.Pads())
    return [T, B] if tht else [B if fp.IsFlipped() else T]


def place_explicit(ref, x, y, rot, side):
    fp = fps[ref]
    if isinstance(rot, str):                 # edge connector: pads (back of the part) point inward
        inward = {"edge-left": (1, 0), "edge-right": (-1, 0), "edge-top": (0, 1), "edge-bottom": (0, -1)}[rot]
        best = None
        for r in (0, 90, 180, 270):
            set_pose(fp, x, y, r, side)
            cx0, cy0, cx1, cy1 = court(fp)
            px, py = centroid(pad_xy(fp))
            v = (px - (cx0 + cx1) / 2) * inward[0] + (py - (cy0 + cy1) / 2) * inward[1]
            if best is None or v > best[0]:
                best = (v, r)
        rot = best[1]
    set_pose(fp, x, y, rot, side)
    # move so the courtyard centre is at (x, y), then keep it on the board
    cx0, cy0, cx1, cy1 = court(fp)
    dx, dy = x - (cx0 + cx1) / 2, y - (cy0 + cy1) / 2
    dx += max(0, 0.2 - (cx0 + dx)) - max(0, (cx1 + dx) - (BW - 0.2))
    dy += max(0, 0.2 - (cy0 + dy)) - max(0, (cy1 + dy) - (BH - 0.2))
    pos = fp.GetPosition()
    fp.SetPosition(pcbnew.VECTOR2I(pos.x + pcbnew.FromMM(dx), pos.y + pcbnew.FromMM(dy)))
    placed[ref] = True
    occupy(ref, sides_of(fp))


for ref, (x, y, rot, side) in EXPLICIT.items():
    place_explicit(ref, x, y, rot, side)

# ---------------------------------------------------------------- automatic placement
GRID = 0.5
OFFS = sorted(((i * GRID, j * GRID) for i in range(-80, 81) for j in range(-80, 81)), key=lambda d: d[0] ** 2 + d[1] ** 2)
MARGIN = 0.15            # courtyard-to-courtyard gap (courtyards already carry their own clearance)
EDGE = 0.5


def overlaps(r, side):
    x0, y0, x1, y1 = r
    for (a0, b0, a1, b1), _ in occ[side]:
        if x0 < a1 + MARGIN and a0 < x1 + MARGIN and y0 < b1 + MARGIN and b0 < y1 + MARGIN:
            return True
    return False


block_of = {r: (s, t) for s, bl in BLOCKS.items() for t, refs in bl.items() for r in refs}
comp_desc = {r: c["desc"] for r, c in comps.items()}
from importlib import util as _u  # noqa: E402
_spec = _u.spec_from_file_location("mbd", MB / "design" / "motor_board.py"); _m = _u.module_from_spec(_spec); _spec.loader.exec_module(_m)
design_desc = {r: p.get("desc", "") for r, p in _m.PARTS.items()}


ANCHOR = {"U9": "J2", "U11": "J2", "D7": "J2", "U10": "J3", "U12": "J3", "D8": "J3"}


def target(ref):
    c = comps[ref]
    if ref in ANCHOR:
        return centroid(pad_xy(fps[ANCHOR[ref]])), 5
    desc = design_desc.get(ref, "")
    mu = re.search(r"\b(U\d+)\b", desc)
    mp = re.search(r"\bpin (\d+)\b", desc)
    if ref.startswith("NT"):                                  # Kelvin tie at the shunt's ground pad
        rs = "RS" + ref[2:]
        return pad_xy(fps[rs], "2")[0], 3
    if mu and mu.group(1) in placed:
        u = mu.group(1)
        if mp and pad_xy(fps[u], mp.group(1)):
            return pad_xy(fps[u], mp.group(1))[0], 3
        mine = {short(n) for n in c["pins"].values()} - {"GND"}
        pts = [pt for p in fps[u].Pads() if short(p.GetNetname()) in mine for pt in [pad_xy(fps[u], p.GetNumber())[0]]]
        return (centroid(pts) if pts else centroid(pad_xy(fps[u]))), 3
    if mp and not mu:                                         # "buck VIN at pin 47": the block's IC
        sheet, title = block_of[ref]
        ics = [r for r in BLOCKS[sheet][title] if r.startswith("U") and r in placed]
        if ics and pad_xy(fps[ics[0]], mp.group(1)):
            return pad_xy(fps[ics[0]], mp.group(1))[0], 3
    pts = []
    for n in c["pins"].values():
        if short(n) in RAILS or short(n).startswith("unconnected"):
            continue
        for r2, pin in nets[n]:
            if r2 != ref and r2 in placed:
                pts += pad_xy(fps[r2], pin)
    if pts:
        return centroid(pts), len(pts)
    sheet, title = block_of[ref]
    anchors = [r for r in BLOCKS[sheet][title] if r in placed]
    if anchors:
        return centroid([centroid(pad_xy(fps[a])) for a in anchors]), 0
    return (BW / 2, BH / 2), 0


def side_for(ref):
    if TOP_ALWAYS.match(ref):
        return T
    return B if block_of[ref][1] in BOTTOM_BLOCKS else T


def auto_place(ref):
    fp = fps[ref]
    (tx, ty), _ = target(ref)
    side = side_for(ref)
    best = None
    for rot in (0, 90):
        set_pose(fp, 0, 0, rot, side)
        cx0, cy0, cx1, cy1 = court(fp)
        w, h = cx1 - cx0, cy1 - cy0
        ox, oy = (cx0 + cx1) / 2, (cy0 + cy1) / 2          # courtyard centre relative to the origin
        tried = 0
        for dx, dy in OFFS:
            x, y = tx + dx, ty + dy
            r = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
            if r[0] < EDGE or r[1] < EDGE or r[2] > BW - EDGE or r[3] > BH - EDGE:
                continue
            tried += 1
            if not any(overlaps(r, s) for s in ([T, B] if len(sides_of(fp)) == 2 else [side])):
                d = math.hypot(dx, dy) + (0.3 if rot else 0)
                if best is None or d < best[0]:
                    best = (d, rot, x - ox, y - oy)
                break
    if best is None:
        return False
    _, rot, x, y = best
    set_pose(fp, round(x / 0.05) * 0.05, round(y / 0.05) * 0.05, rot, side)
    placed[ref] = True
    occupy(ref, sides_of(fp))
    return True


failed = []
for sheet, bl in BLOCKS.items():
    for title, refs in bl.items():
        todo = [r for r in refs if r not in placed]
        # ICs / big parts first, then whatever is best connected to what is already placed
        todo.sort(key=order_key)
        while todo:
            big = [r for r in todo if r[0] in "UQLJ"]
            if big:
                ref = big[0]
            else:
                ref = max(todo, key=lambda r: (target(r)[1], -order_key(r)[2]))
            todo.remove(ref)
            if not auto_place(ref):
                failed.append(ref)

# ---------------------------------------------------------------- report + save
shutil.copy(PCB, TMP / "motor_board.kicad_pcb.bak") if PCB.exists() else None
pro_before = (PROJ / "motor_board.kicad_pro").read_text()
pcbnew.SaveBoard(str(PCB), board)
import json  # noqa: E402
pro = json.loads(pro_before)          # SaveBoard rewrites the project file: keep ours, with placeholder JLC rules
dflt = pro["net_settings"]["classes"][0]
assert dflt["name"] == "Default"
dflt.update(clearance=0.127, track_width=0.15, via_diameter=0.45, via_drill=0.25)
pro["board"]["design_settings"]["rules"].update(min_clearance=0.1, min_track_width=0.1, min_via_diameter=0.4,
                                                 min_through_hole_diameter=0.2, min_copper_edge_clearance=0.3)
(PROJ / "motor_board.kicad_pro").write_text(json.dumps(pro, indent=2) + "\n")
top = sum(1 for r in fps if not fps[r].IsFlipped()); bot = len(fps) - top
area = {s: sum((r[2] - r[0]) * (r[3] - r[1]) for r, ref in occ[s] if s == T or ref not in [x for _, x in occ[T]]) for s in (T, B)}
print(f"footprints {len(fps)} (top {top}, bottom {bot}), nets {len(nets)}, failed to place: {failed}")
print(f"courtyard area: top {area[T]:.0f} mm2, bottom {area[B]:.0f} mm2 of {BW * BH:.0f} mm2 board")
