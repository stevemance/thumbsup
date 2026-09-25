"""Rebuild the six sub-sheets: parts grouped by circuit block and spread over the A3 sheet, a net label on
every pin (GND/+3V3/+5V power symbols, global labels for nets that leave the sheet, local labels otherwise),
no-connect flags on NC pins, pin numbers visible.  Keeps each sheet's header (uuid, paper, title block)."""
import collections
import copy
import csv
import importlib.util
import re
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, "/home/smance/projects/thumbsup/hardware/motor_board/kicad/lib_build")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kicadlib as K  # noqa: E402
from kicadlib import Str  # noqa: E402
from blocks import BLOCKS, order_key  # noqa: E402

MB = Path("/home/smance/projects/thumbsup/hardware/motor_board")
PROJ = MB / "kicad" / "motor_board"
BACKUP = Path(__file__).resolve().parent / "out" / "sch_backup"
ROOT_UUID = "171e0a5d-7eac-4b29-8fcf-e7df83310741"
SHEET_UUID = {"power": "686c9e87-0e2e-496f-ae2e-dae51f4b5078", "drive_left": "7b99b204-f915-4856-bbcf-a1062742dde6",
              "mcu": "930effe6-f1bc-4e4e-aebc-c98263d4a033", "sensors": "99bc43a5-30f9-4090-828f-f0aa103e36ff",
              "weapon": "b615a5c8-f1c9-4a04-91a7-9f53e1b27fc7", "drive_right": "c237dd26-979f-47a1-ac98-54e992f91368"}
POWER_NETS = {"GND": "GND", "+3V3": "+3V3", "+5V": "+5V"}
G = 2.54
PAGE = (420.0, 297.0)
AREA = (12.7, 12.7, 407.3, 284.3)          # inside the border
TITLE = (290.0, 250.0)                      # title block keep-out: x > 290 and y > 250

spec = importlib.util.spec_from_file_location("mbd", MB / "design" / "motor_board.py")
mbd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mbd)
PARTS = mbd.PARTS
netpins = collections.defaultdict(dict)
for r in csv.DictReader(open(MB / "design" / "netlist.csv")):
    netpins[r["ref"]][r["pin"]] = r["net"]

# ---------------------------------------------------------------- sheet membership must match SHEETS.md
md = (MB / "kicad" / "SHEETS.md").read_text()
for sec in re.split(r"\n## ", md)[1:]:
    name = sec.split("\n")[0].strip()
    want = set(re.search(r"\*\*Parts:\*\* (.*)", sec).group(1).split(", "))
    if name == "mcu":
        want |= {r for r in PARTS if r.startswith("MH")}
    have = {r for refs in BLOCKS[name].values() for r in refs}
    assert want == have, (name, sorted(want - have), sorted(have - want))
sheet_of = {r: s for s, bl in BLOCKS.items() for refs in bl.values() for r in refs}
assert set(sheet_of) == set(PARTS)
net_sheets = collections.defaultdict(set)
for ref, pins in netpins.items():
    for n in pins.values():
        net_sheets[n].add(sheet_of[ref])

# ---------------------------------------------------------------- symbols
mylib = K.load_symbol_lib(PROJ / "motor_board.kicad_sym")
mysyms = K.symbols(mylib)
by_lcsc = {K.sym_props(s).get("LCSC"): n for n, s in mysyms.items()}
stock_cache = {}


def stock(lib, name):
    L = stock_cache.setdefault(lib, K.load_symbol_lib(K.STOCK_SYM / f"{lib}.kicad_sym"))
    s = K.symbols(L)[name]
    assert not K.child(s, "extends"), f"{lib}:{name} is derived"
    return s


def choose(ref, p):
    if p["lcsc"] in by_lcsc and ref != "TH1":
        n = by_lcsc[p["lcsc"]]
        return "motor_board", n, mysyms[n]
    fp = p["footprint"]
    table = [("Resistor_SMD", ("Device", "Thermistor_NTC") if ref == "TH1" else ("Device", "R")),
             ("Capacitor_SMD", ("Device", "C")), ("Connector_Wire", ("Connector_Generic", "Conn_01x01")),
             ("TestPoint", ("Connector", "TestPoint")), ("NetTie", ("Device", "NetTie_2")),
             ("Jumper:SolderJumper-3_P1.3mm_Bridged12", ("Jumper", "SolderJumper_3_Bridged12")),
             ("MountingHole", ("Mechanical", "MountingHole"))]
    for prefix, (lib, name) in table:
        if fp.startswith(prefix):
            return lib, name, stock(lib, name)
    raise SystemExit(f"{ref}: no symbol rule for {fp}")


choice = {ref: choose(ref, PARTS[ref]) for ref in PARTS}
for ref, (lib, name, s) in choice.items():
    sp = {p["number"] for p in K.sym_pins(s)}
    assert sp == set(netpins.get(ref, {})), (ref, sorted(sp), sorted(netpins.get(ref, {})))


def units_of(s):
    return sorted({p["unit"] for p in K.sym_pins(s)} - {0}) or [1]


def unit_pins(s, unit):
    """[(number, x, y, outward_dir)] in schematic coords relative to the symbol origin (y down).
    outward_dir: 0 right, 90 up, 180 left, 270 down (the way a label should extend)."""
    out = []
    for sub in K.children(s, "symbol"):
        m = re.search(r"_(\d+)_(\d+)$", sub[1])
        if int(m.group(1)) not in (0, unit) or int(m.group(2)) not in (0, 1):
            continue
        for g in K.children(sub, "pin"):
            at = K.child(g, "at")
            x, y, a = float(at[1]), -float(at[2]), int(float(at[3])) % 360
            num = K.child(g, "number")[1]
            out.append((num, x, y, (a + 180) % 360))   # the pin points into the body; labels go the other way
    return out


def body_bbox(s, unit):
    xs, ys = [], []
    for sub in K.children(s, "symbol"):
        m = re.search(r"_(\d+)_(\d+)$", sub[1])
        if int(m.group(1)) not in (0, unit) or int(m.group(2)) not in (0, 1):
            continue
        for g in sub[2:]:
            if not isinstance(g, list):
                continue
            if g[0] == "rectangle":
                for k in ("start", "end"):
                    c = K.child(g, k)
                    xs.append(float(c[1])); ys.append(-float(c[2]))
            elif g[0] in ("polyline", "bezier"):
                for p in K.child(g, "pts")[1:]:
                    xs.append(float(p[1])); ys.append(-float(p[2]))
            elif g[0] == "circle":
                c = K.child(g, "center"); r = float(K.child(g, "radius")[1])
                xs += [float(c[1]) - r, float(c[1]) + r]; ys += [-float(c[2]) - r, -float(c[2]) + r]
            elif g[0] == "arc":
                for k in ("start", "mid", "end"):
                    c = K.child(g, k)
                    xs.append(float(c[1])); ys.append(-float(c[2]))
            elif g[0] == "pin":
                at = K.child(g, "at"); L = float(K.child(g, "length")[1])
                x, y, a = float(at[1]), -float(at[2]), int(float(at[3])) % 360
                dx, dy = {0: (L, 0), 90: (0, -L), 180: (-L, 0), 270: (0, L)}[a]
                xs += [x, x + dx]; ys += [y, y + dy]
    if not xs:
        return (-2.54, -2.54, 2.54, 2.54)
    return (min(xs), min(ys), max(xs), max(ys))


def label_kind(net):
    if net == "NC":
        return "nc"
    if net in POWER_NETS:
        return "power"
    return "global" if len(net_sheets[net]) > 1 else "local"


def label_len(net):
    k = label_kind(net)
    return {"nc": 1.5, "power": 4.0}.get(k, len(net) * 1.1 + (4.5 if k == "global" else 1.5))


def extents(s, unit, ref):
    """bbox of the unit including the labels that will hang off its pins, plus ref/value room."""
    x0, y0, x1, y1 = body_bbox(s, unit)
    for num, x, y, d in unit_pins(s, unit):
        L = label_len(netpins[ref][num])
        if d == 0: x1 = max(x1, x + L)
        elif d == 180: x0 = min(x0, x - L)
        elif d == 90: y0 = min(y0, y - L)
        else: y1 = max(y1, y + L)
    return x0 - 3.0, y0 - 3.5, x1 + 3.0, y1 + 3.5


def snap(v):
    return round(v / G) * G


def fmt(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def uid():
    return Str(str(uuid.uuid4()))


def effects(size=1.27, justify=None, hide=False, bold=False):
    font = ["font", ["size", fmt(size), fmt(size)]]
    if bold:
        font += [["thickness", fmt(size * 0.2)], ["bold", "yes"]]
    e = ["effects", font]
    if justify:
        e.append(["justify"] + justify.split())
    if hide:
        e.append(["hide", "yes"])
    return e


# ---------------------------------------------------------------- writers
def lib_symbol_copy(lib, name, s):
    node = copy.deepcopy(s)
    node[1] = Str(f"{lib}:{name}")
    node[:] = [c for c in node if not (isinstance(c, list) and c and c[0] == "pin_numbers")]
    return node


def instance(ref, lib, name, s, unit, x, y, sheet, props=None):
    if props is None:
        p = PARTS[ref]
        values = dict(K.sym_props(s))
        values["Reference"] = ref
        values["Value"] = name if lib == "motor_board" else p["value"]
        values["Footprint"] = p["footprint"]
        if p["lcsc"]:
            values["LCSC"] = p["lcsc"]
        dnp = bool(p.get("dnp"))
        in_bom = "no" if re.match(r"^(JBAT\d|J[WLR]\d|JP\d|MH\d|NT\d|TP\d+)$", ref) else "yes"   # copper-only parts
    else:
        values, dnp, in_bom = props, False, "no"
    node = ["symbol", ["lib_id", Str(f"{lib}:{name}")], ["at", fmt(x), fmt(y), "0"], ["unit", str(unit)],
            ["exclude_from_sim", "no"], ["in_bom", in_bom], ["on_board", "yes" if props is None else "yes"],
            ["dnp", "yes" if dnp else "no"], ["fields_autoplaced", "no"], ["uuid", uid()]]
    libprops = {q[1]: q for q in K.children(s, "property")}
    for key, val in values.items():
        if key.startswith("ki_"):
            continue
        src = libprops.get(key)
        at = K.child(src, "at") if src else ["at", "0", "0", "0"]
        hide = bool(src and K.child(src, "hide")) if key in libprops else True
        if key in ("Reference", "Value") and props is None:
            hide = False
        eff = copy.deepcopy(K.child(src, "effects")) if src else ["effects", ["font", ["size", "1.27", "1.27"]]]
        eff[:] = [c for c in eff if not (isinstance(c, list) and c and c[0] == "hide")]
        prop = ["property", Str(key), Str(str(val)), ["at", fmt(x + float(at[1])), fmt(y - float(at[2])), at[3] if len(at) > 3 else "0"]]
        if hide:
            prop.append(["hide", "yes"])
        prop.append(eff)
        node.append(prop)
    for pin in sorted({q["number"] for q in K.sym_pins(s) if q["unit"] in (0, unit)}, key=lambda n: (len(n), n)):
        node.append(["pin", Str(pin), ["uuid", uid()]])
    node.append(["instances", ["project", Str("motor_board"),
                               ["path", Str(f"/{ROOT_UUID}/{SHEET_UUID[sheet]}"), ["reference", Str(values["Reference"])], ["unit", str(unit)]]]])
    return node


LJUST = {0: "left bottom", 90: "left bottom", 180: "right bottom", 270: "right bottom"}
GJUST = {0: "left", 90: "left", 180: "right", 270: "right"}
# power symbol rotation so the symbol body points along the outward direction
PWR_ROT = {"GND": {270: 0, 0: 90, 90: 180, 180: 270}, "up": {90: 0, 180: 90, 270: 180, 0: 270}}
pwr_counter = [0]
power_syms = {n: stock("power", n) for n in POWER_NETS.values()}


def net_marker(net, x, y, d, sheet, have):
    k = label_kind(net)
    if k == "nc":
        return [["no_connect", ["at", fmt(x), fmt(y)], ["uuid", uid()]]]
    if k == "local":
        return [["label", Str(net), ["at", fmt(x), fmt(y), str(d)], ["fields_autoplaced", "yes"],
                 effects(justify=LJUST[d]), ["uuid", uid()]]]
    if k == "global":
        return [["global_label", Str(net), ["shape", "passive"], ["at", fmt(x), fmt(y), str(d)], ["fields_autoplaced", "yes"],
                 effects(justify=GJUST[d]), ["uuid", uid()],
                 ["property", Str("Intersheetrefs"), Str("${INTERSHEET_REFS}"), ["at", fmt(x), fmt(y), "0"], effects(hide=True)]]]
    name = POWER_NETS[net]
    s = power_syms[name]
    have.add(("power", name))
    pwr_counter[0] += 1
    rot = PWR_ROT["GND" if name == "GND" else "up"][d]
    props = {"Reference": f"#PWR{pwr_counter[0]:04d}", "Value": name, "Footprint": "", "Datasheet": "", "Description": ""}
    node = instance(None, "power", name, s, 1, x, y, sheet, props=props)
    K.child(node, "at")[3] = str(rot)
    # place ref (hidden) and value beside the symbol, readable
    for q in K.children(node, "property"):
        if q[1] == "Value":
            off = {0: (0, 5.08), 90: (5.08, 0), 180: (0, -5.08), 270: (-5.08, 0)}[rot] if name == "GND" else \
                  {0: (0, -3.81), 90: (-3.81, 0), 180: (0, 3.81), 270: (3.81, 0)}[rot]
            q[3] = ["at", fmt(x + off[0]), fmt(y + off[1]), "0"]
            eff = K.child(q, "effects")
            eff[:] = [c for c in eff if not (isinstance(c, list) and c[0] == "justify")]
            if rot in (90, 270):
                eff.append(["justify", "left" if (name == "GND") == (rot == 90) else "right"])
    return [node]


# ---------------------------------------------------------------- layout
def pack_block(items, target_w):
    """items: [(key, w, h)] -> {key: (x, y)} top-left positions, total (w, h). Shelf packing."""
    pos, x, y, shelf, W = {}, 0.0, 0.0, 0.0, 0.0
    for key, w, h in items:
        if x > 0 and x + w > target_w:
            x, y, shelf = 0.0, y + shelf, 0.0
        pos[key] = (x, y)
        x += w
        shelf = max(shelf, h)
        W = max(W, x)
    return pos, W, y + shelf


def layout_sheet(sheet):
    """-> [(ref, unit, ox, oy)], [(title, x, y)]"""
    blocks = []
    for title, refs in BLOCKS[sheet].items():
        items = []
        for ref in sorted(refs, key=order_key):
            lib, name, s = choice[ref]
            for u in units_of(s):
                ex = extents(s, u, ref)
                items.append(((ref, u, ex), ex[2] - ex[0], ex[3] - ex[1]))
        area = sum(w * h for _, w, h in items)
        big = max(w for _, w, _ in items)
        target = max(big, (area ** 0.5) * 1.35)
        pos, W, H = pack_block(items, target)
        blocks.append((title, pos, W, H + 8.0))           # heading room
    # arrange blocks: shelves across the page, then spread rows/columns to fill it
    x0, y0, x1, y1 = AREA
    avail_w = x1 - x0
    rows, row, rw = [], [], 0.0
    for b in sorted(blocks, key=lambda b: -b[3]):
        if row and rw + b[2] > avail_w * 0.92:
            rows.append(row); row, rw = [], 0.0
        row.append(b); rw += b[2]
    rows.append(row)
    heights = [max(b[3] for b in r) for r in rows]
    free_h = (y1 - y0) - sum(heights) - (35.0 if True else 0)   # keep the title block strip free
    if free_h < 0:
        raise SystemExit(f"{sheet}: blocks do not fit vertically ({-free_h:.0f} mm over)")
    gap_h = free_h / (len(rows) + 1)
    placed, titles = [], []
    y = y0 + gap_h
    for r, h in zip(rows, heights):
        free_w = avail_w - sum(b[2] for b in r)
        if free_w < 0:
            raise SystemExit(f"{sheet}: row too wide")
        gap_w = free_w / (len(r) + 1)
        x = x0 + gap_w
        for title, pos, W, H in r:
            titles.append((title, snap(x), snap(y) + 1.27))
            for (ref, u, ex), (px, py) in pos.items():
                ox = snap(x + px - ex[0])
                oy = snap(y + 8.0 + py - ex[1])
                placed.append((ref, u, ox, oy))
            x += W + gap_w
        y += h + gap_h
    return placed, titles


# ---------------------------------------------------------------- write
BACKUP.mkdir(exist_ok=True)
DROP = {"symbol", "wire", "junction", "label", "global_label", "hierarchical_label", "no_connect", "text", "bus", "bus_entry", "polyline"}
report = {}
FLAGS = {"power": ["GND", "BAT_IN", "VBAT", "BMS_BAT"], "weapon": ["+5V"], "drive_left": ["L_VM"], "drive_right": ["R_VM"],
         "mcu": ["+3V3A"], "sensors": ["L_VSRC", "R_VSRC"]}
flg_counter = [0]
for sheet in BLOCKS:
    f = PROJ / f"{sheet}.kicad_sch"
    if not (BACKUP / f.name).exists():
        shutil.copy(f, BACKUP / f.name)
    sch = K.parse(f.read_text())
    sch[:] = [c for c in sch if not (isinstance(c, list) and c and c[0] in DROP)]
    K.child(sch, "paper")[1] = Str("A3")
    libsyms = K.child(sch, "lib_symbols")
    libsyms[:] = ["lib_symbols"]
    have = set()
    placed, titles = layout_sheet(sheet)
    body = []
    for ref, u, ox, oy in placed:
        lib, name, s = choice[ref]
        if (lib, name) not in have:
            libsyms.append(lib_symbol_copy(lib, name, s)); have.add((lib, name))
        body.append(instance(ref, lib, name, s, u, ox, oy, sheet))
        for num, px, py, d in unit_pins(s, u):
            body += net_marker(netpins[ref][num], ox + px, oy + py, d, sheet, have)
    # PWR_FLAGs: nets fed through passives / from off-board (ERC power_pin_not_driven otherwise)
    flags = FLAGS.get(sheet, [])
    if flags:
        libsyms.append(lib_symbol_copy("power", "PWR_FLAG", stock("power", "PWR_FLAG")))
        body.append(["text", Str("ERC power flags"), ["exclude_from_sim", "no"], ["at", "20.32", "254", "0"],
                     effects(size=1.5, justify="left bottom"), ["uuid", uid()]])
    for i, net in enumerate(flags):
        x, y = 25.4 + i * 30.48, 264.16
        flg_counter[0] += 1
        props = {"Reference": f"#FLG{flg_counter[0]:03d}", "Value": "PWR_FLAG", "Footprint": "", "Datasheet": "", "Description": ""}
        body.append(instance(None, "power", "PWR_FLAG", stock("power", "PWR_FLAG"), 1, x, y, sheet, props=props))
        body += net_marker(net, x, y, 270, sheet, have)
    for n in POWER_NETS.values():
        if ("power", n) in have:
            libsyms.append(lib_symbol_copy("power", n, power_syms[n]))
    for title, x, y in titles:
        body.append(["text", Str(title), ["exclude_from_sim", "no"], ["at", fmt(x), fmt(y), "0"],
                     effects(size=2.0, justify="left bottom", bold=True), ["uuid", uid()]])
    # insert before sheet_instances / embedded_fonts if present, else at the end
    tail = [c for c in sch if isinstance(c, list) and c and c[0] in ("sheet_instances", "embedded_fonts")]
    sch[:] = [c for c in sch if c not in tail] + body + tail
    f.write_text(K.dump(sch) + "\n")
    maxy = max(oy for _, _, _, oy in placed)
    report[sheet] = (len({p[0] for p in placed}), len(placed), round(maxy))
print(report, "power symbols:", pwr_counter[0])
