#!/usr/bin/env python3
"""Build the motor-board project library from parts.py.

Writes out/motor_board.kicad_sym and out/motor_board.pretty/*.kicad_mod.  Nothing is installed into
the KiCad project; copy the two into kicad/motor_board/ once check_lib.py passes.

    python3 build_lib.py && python3 check_lib.py
"""
import copy
from pathlib import Path

import kicadlib as K
from kicadlib import Str
import parts as P

HERE = Path(__file__).parent
OUT = HERE / "out"
DESIGN = HERE.parent.parent / "design"
GRID = 2.54


# ------------------------------------------------------------------ symbol helpers
def prop(name, value, at=(0, 0, 0), hide=True):
    node = [
        "property", Str(name), Str(value),
        ["at", *(fmt(v) for v in at)],
        ["show_name", "no"], ["do_not_autoplace", "no"],
    ]
    if hide:
        node.append(["hide", "yes"])
    node.append(["effects", ["font", ["size", "1.27", "1.27"]]])
    return node


def fmt(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def set_props(sym, name, spec, lcsc):
    """Replace/insert the standard properties of a symbol node."""
    values = {
        "Reference": spec["ref"], "Value": name, "Footprint": spec["fp"],
        # no manufacturer URL recorded → the LCSC product page (carries the datasheet PDF)
        "Datasheet": spec.get("datasheet") or (f"https://www.lcsc.com/product-detail/{lcsc}.html" if lcsc else ""),
        "Description": spec["desc"], "LCSC": lcsc, "MPN": name, "ki_fp_filters": spec["fp"].split(":")[1],
    }
    existing = {p[1]: p for p in K.children(sym, "property")}
    for key, val in values.items():
        if key in existing:
            existing[key][2] = Str(val)
        else:
            idx = max(i for i, c in enumerate(sym) if isinstance(c, list) and c[0] == "property") + 1
            sym.insert(idx, prop(key, val))
    for key in ("ki_keywords",):
        if key in existing:
            sym.remove(existing[key])


def rename_units(sym, old, new):
    for c in sym:
        if isinstance(c, list) and c and c[0] == "symbol" and isinstance(c[1], str) and c[1].startswith(old + "_"):
            c[1] = Str(new + c[1][len(old):])


def stock_symbol(name, spec, lcsc, libcache):
    lib, sname = spec["src"]
    L = libcache.setdefault(lib, K.load_symbol_lib(K.STOCK_SYM / f"{lib}.kicad_sym"))
    syms = K.symbols(L)
    node = copy.deepcopy(syms[sname])
    ext = K.child(node, "extends")
    if ext:  # flatten a derived symbol: parent's body, child's properties
        parent = copy.deepcopy(syms[ext[1]])
        child_props = {p[1]: p for p in K.children(node, "property")}
        for p in K.children(parent, "property"):
            if p[1] in child_props:
                parent[parent.index(p)] = child_props[p[1]]
        rename_units(parent, ext[1], sname)
        node = parent
    node[1] = Str(name)
    rename_units(node, sname, name)
    for unit in K.children(node, "symbol"):
        for pin in K.children(unit, "pin"):
            num = K.child(pin, "number")[1]
            if num in spec.get("rename", {}):
                K.child(pin, "name")[1] = Str(spec["rename"][num])
    set_props(node, name, spec, lcsc)
    return node


def pin_node(p, x, y, angle, length=GRID):
    number, name, etype, _side = p
    return ["pin", etype, "line", ["at", fmt(x), fmt(y), str(angle)], ["length", fmt(length)],
            ["name", Str(name), ["effects", ["font", ["size", "1.27", "1.27"]]]],
            ["number", Str(number), ["effects", ["font", ["size", "1.27", "1.27"]]]]]


def new_symbol(name, spec, lcsc):
    pins = spec["pins"]
    side = {s: [p for p in pins if p[3] == s] for s in "LRTB"}
    ch = 0.8  # approx. text width per character at 1.27 mm font
    name_w = lambda ps: max((len(p[1]) for p in ps), default=0) * ch
    width = max(name_w(side["L"]) + name_w(side["R"]) + 4 * GRID, (len(side["B"]) + 1) * GRID, (len(side["T"]) + 1) * GRID)
    width = GRID * round(width / GRID + 0.5)
    rows = max(len(side["L"]), len(side["R"]))
    # room for the rotated names of bottom/top pins inside the body
    bot = GRID * round((name_w(side["B"]) + 1.5) / GRID + 0.5) if side["B"] else 0
    top = GRID * round((name_w(side["T"]) + 1.5) / GRID + 0.5) if side["T"] else 0
    height = GRID * (rows + 1) + bot + top
    x0, x1 = -width / 2, width / 2
    y1 = height / 2
    y0 = -height / 2
    top_row = y1 - GRID - top
    units_pins = []
    for i, p in enumerate(side["L"]):
        units_pins.append(pin_node(p, x0 - GRID, top_row - i * GRID, 0))
    for i, p in enumerate(side["R"]):
        units_pins.append(pin_node(p, x1 + GRID, top_row - i * GRID, 180))
    for side_key, y, ang in (("B", y0 - GRID, 90), ("T", y1 + GRID, 270)):
        ps = side[side_key]
        start = -GRID * (len(ps) - 1) / 2
        for i, p in enumerate(ps):
            units_pins.append(pin_node(p, start + i * GRID, y, ang))
    body = ["symbol", Str(f"{name}_0_1"),
            ["rectangle", ["start", fmt(x0), fmt(y1)], ["end", fmt(x1), fmt(y0)],
             ["stroke", ["width", "0.254"], ["type", "default"]], ["fill", ["type", "background"]]]]
    unit = ["symbol", Str(f"{name}_1_1"), *units_pins]
    node = ["symbol", Str(name),
            ["pin_names", ["offset", "1.016"]],
            ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"], ["in_pos_files", "yes"],
            ["duplicate_pin_numbers_are_jumpers", "no"],
            prop("Reference", spec["ref"], (x0, y1 + 1.27, 0), hide=False),
            prop("Value", name, (x0, y0 - 1.27 - (2 * GRID if side["B"] else 0) - 1.27, 0), hide=False),
            body, unit, ["embedded_fonts", "no"]]
    set_props(node, name, spec, lcsc)
    for p in K.children(node, "property"):  # left-justify the visible texts
        if p[1] in ("Reference", "Value"):
            K.child(p, "effects").append(["justify", "left"])
    return node


def build_symbols():
    lib = ["kicad_symbol_lib", ["version", "20251024"], ["generator", Str("motor_board_lib_build")],
           ["generator_version", Str("10.0")]]
    cache = {}
    names = sorted(list(P.NEW) + list(P.STOCK))
    for name in names:
        code = (P.NEW.get(name) or P.STOCK.get(name))["lcsc"]  # from parts.py, not the BOM (check_lib compares)
        if name in P.NEW:
            lib.append(new_symbol(name, P.NEW[name], code))
        else:
            lib.append(stock_symbol(name, P.STOCK[name], code, cache))
    OUT.mkdir(exist_ok=True)
    (OUT / "motor_board.kicad_sym").write_text(K.dump(lib) + "\n")
    return names


# ------------------------------------------------------------------ footprint helpers
def fp_text(kind, text, x, y, layer, hide=False):
    h = " (hide yes)" if hide else ""
    return (f'\t(property "{kind}" "{text}"\n\t\t(at {fmt(x)} {fmt(y)} 0)\n\t\t(layer "{layer}"){h}\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n')


def line(x1, y1, x2, y2, layer, w):
    return (f'\t(fp_line\n\t\t(start {fmt(x1)} {fmt(y1)})\n\t\t(end {fmt(x2)} {fmt(y2)})\n'
            f'\t\t(stroke\n\t\t\t(width {w})\n\t\t\t(type solid)\n\t\t)\n\t\t(layer "{layer}")\n\t)\n')


def rect(x0, y0, x1, y1, layer, w):
    return (line(x0, y0, x1, y0, layer, w) + line(x1, y0, x1, y1, layer, w) +
            line(x1, y1, x0, y1, layer, w) + line(x0, y1, x0, y0, layer, w))


def pad(num, x, y, w, h, shape="roundrect", layers='"F.Cu" "F.Paste" "F.Mask"', rr=0.25, extra=""):
    rrs = f"\n\t\t(roundrect_rratio {rr})" if shape == "roundrect" else ""
    return (f'\t(pad "{num}" smd {shape}\n\t\t(at {fmt(x)} {fmt(y)})\n\t\t(size {fmt(w)} {fmt(h)})\n'
            f'\t\t(layers {layers}){rrs}{extra}\n\t)\n')


def footprint(name, descr, body_lines, pads_txt, crt, ref_y, val_y, attr="smd"):
    x0, y0, x1, y1 = crt
    return (f'(footprint "{name}"\n\t(version 20250114)\n\t(generator "motor_board_lib_build")\n'
            f'\t(layer "F.Cu")\n\t(descr "{descr}")\n\t(attr {attr})\n'
            + fp_text("Reference", "REF**", 0, ref_y, "F.SilkS")
            + fp_text("Value", name, 0, val_y, "F.Fab")
            + '\t(fp_text user "${REFERENCE}"\n\t\t(at 0 0 0)\n\t\t(layer "F.Fab")\n\t\t(effects\n\t\t\t(font\n'
              '\t\t\t\t(size 0.5 0.5)\n\t\t\t\t(thickness 0.08)\n\t\t\t)\n\t\t)\n\t)\n'
            + body_lines + rect(x0, y0, x1, y1, "F.CrtYd", 0.05) + pads_txt + ")\n")


def fp_rgf0040e(name):
    pads = []
    pw, ph = 0.6, 0.25
    for i in range(12):  # 1-12 left, top to bottom
        pads.append(pad(1 + i, -2.4, -2.75 + 0.5 * i, pw, ph))
    for i in range(8):   # 13-20 bottom, left to right
        pads.append(pad(13 + i, -1.75 + 0.5 * i, 3.4, ph, pw))
    for i in range(12):  # 21-32 right, bottom to top
        pads.append(pad(21 + i, 2.4, 2.75 - 0.5 * i, pw, ph))
    for i in range(8):   # 33-40 top, right to left
        pads.append(pad(33 + i, 1.75 - 0.5 * i, -3.4, ph, pw))
    # EP 3.7 x 5.7, copper + mask only; paste as TI's 12 windows 1.05 x 1.15 (69 %)
    pads.append(pad(41, 0, 0, 3.7, 5.7, shape="rect", layers='"F.Cu" "F.Mask"'))
    for cx in (-1.25, 0, 1.25):
        for cy in (-2.025, -0.675, 0.675, 2.025):
            pads.append(pad("", cx, cy, 1.05, 1.15, rr=0.1, layers='"F.Paste"'))
    body = rect(-2.5, -3.5, 2.5, 3.5, "F.Fab", 0.1) + line(-2.5, -2.5, -1.5, -3.5, "F.Fab", 0.1)
    # silkscreen: corner ticks on the package outline (clear of the pads, which overhang it by
    # 0.2 mm, by >= 0.2 mm), pin-1 dot outside the pin-1 corner
    s = 0.12
    for sx in (-1, 1):
        for sy in (-1, 1):
            body += line(sx * 2.61, sy * 3.61, sx * 2.61, sy * 3.25, "F.SilkS", s)
            body += line(sx * 2.61, sy * 3.61, sx * 2.25, sy * 3.61, "F.SilkS", s)
    body += line(-2.85, -3.35, -2.85, -3.35, "F.SilkS", 0.3)  # pin-1 dot, inside the courtyard
    return footprint(name, "TI RGF0040E VQFN-40 5x7 mm, 0.5 mm pitch, EP 3.7x5.7 (SLVSH07 p.92-94)",
                     body, "".join(pads), (-2.95, -3.95, 2.95, 3.95), -4.7, 4.7)


def fp_two_pad(name, spec):
    (pw, ph), x, (bl, bw) = spec["pad"], spec["x"], spec["body"]
    pads = pad(1, -x, 0, pw, ph, rr=0.08) + pad(2, x, 0, pw, ph, rr=0.08)
    body = rect(-bl / 2, -bw / 2, bl / 2, bw / 2, "F.Fab", 0.1)
    body += line(-0.6, -ph / 2 - 0.2, 0.6, -ph / 2 - 0.2, "F.SilkS", 0.12)
    body += line(-0.6, ph / 2 + 0.2, 0.6, ph / 2 + 0.2, "F.SilkS", 0.12)
    cx, cy = x + pw / 2 + 0.25, ph / 2 + 0.25
    return footprint(name, spec["descr"],
                     body, pads, (-cx, -cy, cx, cy), -cy - 0.8, cy + 0.8)


def fp_header(name, spec):
    n, pitch, (pw, ph), x, (bw, bl) = spec["n"], spec["pitch"], spec["pad"], spec["x"], spec["body"]
    pads = []
    for i in range(n):
        y = -pitch * (n - 1) / 2 + i * pitch
        pads.append(pad(2 * i + 1, -x, y, pw, ph))
        pads.append(pad(2 * i + 2, x, y, pw, ph))
    body = rect(-bw / 2, -bl / 2, bw / 2, bl / 2, "F.Fab", 0.1)
    y1 = -pitch * (n - 1) / 2
    body += line(-x - pw / 2, y1 - ph / 2 - 0.3, -x + pw / 2, y1 - ph / 2 - 0.3, "F.SilkS", 0.12)  # pin-1 bar
    body += line(-0.6, -bl / 2 - 0.1, 0.6, -bl / 2 - 0.1, "F.SilkS", 0.12)
    body += line(-0.6, bl / 2 + 0.1, 0.6, bl / 2 + 0.1, "F.SilkS", 0.12)
    cx, cy = x + pw / 2 + 0.25, bl / 2 + 0.3
    return footprint(name, "BOOMELE 1.27-2*10P SMD male header 2x10, 1.27 mm, pads 2.5x0.74 (vendor P.C.B Layout)",
                     body, "".join(pads), (-cx, -cy, cx, cy), -cy - 0.8, cy + 0.8)


def fp_sh(name, spec):
    n, pitch, (sw, sh), sy = spec["n"], spec["pitch"], spec["sig"], spec["sig_y"]
    (mw, mh), mx, my, (bw, bd) = spec["mp"], spec["mp_x"], spec["mp_y"], spec["body"]
    pads = [pad(i + 1, -pitch * (n - 1) / 2 + i * pitch, sy, sw, sh) for i in range(n)]
    pads += [pad("MP", -mx, my, mw, mh), pad("MP", mx, my, mw, mh)]
    body = rect(-bw / 2, sy + sh / 2 - 0.4, bw / 2, sy + sh / 2 - 0.4 + bd, "F.Fab", 0.1)
    p1x = -pitch * (n - 1) / 2
    body += line(p1x - sw / 2 - 0.4, sy - sh / 2, p1x - sw / 2 - 0.4, sy + sh / 2, "F.SilkS", 0.12)  # pin-1 mark
    cx = max(mx + mw / 2, bw / 2) + 0.25
    y0, y1 = sy - sh / 2 - 0.25, max(my + mh / 2, sy + sh / 2 - 0.4 + bd) + 0.25
    return footprint(name, "XUNPU WAFER-SH1.0-6PWB SMD right angle, 1.0 mm (vendor P.C.B LAYOUT); JST SM06B-SRSS-TB compatible",
                     body, "".join(pads), (-cx, y0, cx, y1), y0 - 0.8, y1 + 0.8)


def build_footprints():
    d = OUT / "motor_board.pretty"
    d.mkdir(parents=True, exist_ok=True)
    for name, spec in P.FOOTPRINTS.items():
        k = spec["kind"]
        txt = {"qfn_rgf0040e": lambda: fp_rgf0040e(name), "two_pad": lambda: fp_two_pad(name, spec),
               "header_2xN": lambda: fp_header(name, spec), "sh_ra": lambda: fp_sh(name, spec)}[k]()
        (d / f"{name}.kicad_mod").write_text(txt)
    return list(P.FOOTPRINTS)


if __name__ == "__main__":
    s = build_symbols()
    f = build_footprints()
    print(f"{len(s)} symbols -> out/motor_board.kicad_sym; {len(f)} footprints -> out/motor_board.pretty/")
