#!/usr/bin/env python3
"""Verify out/motor_board.kicad_sym + out/motor_board.pretty against the reviewed design.

Checks, for every BOM line that maps to a library symbol:
  1. fields: Footprint and LCSC match design/bom.csv;
  2. pins: the symbol's pin numbers equal the netlist's pin numbers for every designator using it,
     and the pin names agree (ICs; connectors and two-terminal parts compare numbers only);
  3. pads: the symbol's pin numbers equal the footprint's numbered pads (stock or custom);
  4. ERC preview: per netlist net, pin-type conflicts KiCad's ERC would flag
     (output/power-out collisions, power-in nets without a power-out driver → PWR_FLAG needed);
and, for the custom footprints, compares pads with JLC's EasyEDA footprint when one is given.

Exit status 1 on any error (warnings and notes do not fail).
"""
import collections
import csv
import sys
from pathlib import Path

import kicadlib as K
import parts as P

HERE = Path(__file__).parent
OUT = HERE / "out"
DESIGN = HERE.parent.parent / "design"
EASYEDA = Path("/home/smance/.claude/jobs/7be37e37/tmp/ee/ee.pretty")  # optional cross-check

errors, warnings, notes = [], [], []


def norm(name):
    return name.replace("~{", "").replace("}", "").replace(" ", "").upper()


def names_match(sym_name, net_name):
    a, b = norm(sym_name), norm(net_name)
    if not a:
        return None  # stock symbol with unnamed pins (e.g. 74xx gates): number check only
    return a == b or b.startswith(a + "-") or a.replace("/", "") == b.replace("/", "")


def centred(d, rot):
    """Pad centres rotated by rot degrees and centred on their bounding box."""
    import math
    r = math.radians(rot)
    pts = {n: (p["at"][0] * math.cos(r) - p["at"][1] * math.sin(r),
               p["at"][0] * math.sin(r) + p["at"][1] * math.cos(r)) for n, p in d.items()}
    xs = [v[0] for v in pts.values()]
    ys = [v[1] for v in pts.values()]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return {n: (x - cx, y - cy) for n, (x, y) in pts.items()}


def main():
    lib = K.load_symbol_lib(OUT / "motor_board.kicad_sym")
    syms = K.symbols(lib)
    netlist = collections.defaultdict(dict)
    nets = collections.defaultdict(list)
    for r in csv.DictReader(open(DESIGN / "netlist.csv")):
        netlist[r["ref"]][r["pin"]] = r["pin_name"]
        nets[r["net"]].append((r["ref"], r["pin"]))
    ref_symbol = {}
    for row in csv.DictReader(open(DESIGN / "bom.csv")):
        name = P.BOM_TO_SYMBOL.get(row["Comment"])
        if not name:
            continue
        s = syms.get(name)
        if s is None:
            errors.append(f"{name}: missing from the library")
            continue
        props = K.sym_props(s)
        # 1. fields
        fp_lib, fp_name = props["Footprint"].split(":")
        if fp_name != row["Footprint"]:
            errors.append(f"{name}: Footprint {fp_name} != BOM {row['Footprint']}")
        if props.get("LCSC") != row["LCSC Part #"]:
            errors.append(f"{name}: LCSC {props.get('LCSC')} != BOM {row['LCSC Part #']}")
        pins = K.sym_pins(s)
        sym_nums = {p["number"] for p in pins}
        by_num = collections.defaultdict(set)
        for p in pins:
            by_num[p["number"]].add(p["name"])
        # 2. pins vs netlist
        compare_names = s is not None and props["Reference"] == "U" or name in ("HYG015N04LS1C2", "BAV99", "BAT54S")
        for ref in row["Designator"].split(","):
            ref_symbol[ref] = (name, {p["number"]: p["type"] for p in pins})
            npins = netlist.get(ref)
            if not npins:
                errors.append(f"{name}/{ref}: not in the netlist")
                continue
            if set(npins) != sym_nums:
                errors.append(f"{name}/{ref}: pins differ — symbol only {sorted(sym_nums - set(npins))}, "
                              f"netlist only {sorted(set(npins) - sym_nums)}")
            if compare_names:
                for num, nname in npins.items():
                    for sname in by_num.get(num, ()):
                        m = names_match(sname, nname)
                        if m is False:
                            errors.append(f"{name}/{ref}: pin {num} named '{sname}' in the symbol, '{nname}' in the netlist")
                        elif m is None:
                            notes.append(f"{name}/{ref}: pin {num} unnamed in the symbol (netlist '{nname}')")
        # 3. pads vs pins
        fpath = (OUT / "motor_board.pretty" / f"{fp_name}.kicad_mod") if fp_lib == "motor_board" \
            else K.stock_footprint_path(fp_lib, fp_name)
        if not fpath.exists():
            errors.append(f"{name}: footprint file {fpath} missing")
            continue
        pad_nums = {p["number"] for p in K.fp_pads(K.load_footprint(fpath)) if p["number"]}
        if pad_nums != sym_nums:
            errors.append(f"{name}: footprint {fp_name} pads {sorted(pad_nums - sym_nums)} have no pin, "
                          f"pins {sorted(sym_nums - pad_nums)} have no pad")
    # every non-passive netlist part is covered
    for ref in netlist:
        if ref not in ref_symbol and ref[0] in "UQDJL" and not ref.startswith(("J_", "JP")):
            warnings.append(f"{ref}: not covered by the library (check it is a stock/generic part)")
    # 4. ERC preview on the netlist's nets
    for net, members in sorted(nets.items()):
        if net == "NC":  # the netlist's bucket for unconnected pins (no-connect flags in the schematic)
            continue
        types = collections.Counter()
        for ref, pin in members:
            if ref in ref_symbol:
                types[ref_symbol[ref][1].get(pin, "?")] += 1
        drivers = types["power_out"]
        outs = types["output"]
        if drivers > 1 and not (net.startswith(("GND",)) or net == "NC"):
            same = {ref for ref, pin in members if ref_symbol.get(ref, (0, {}))[1].get(pin) == "power_out"}
            if len(same) > 1:
                warnings.append(f"ERC: net {net} has {drivers} power_out pins ({', '.join(sorted(same))})")
        if outs > 1:
            src = sorted({ref for ref, pin in members if ref_symbol.get(ref, (0, {}))[1].get(pin) == "output"})
            if len(src) > 1:
                errors.append(f"ERC: net {net} has output pins from {', '.join(src)} (output-output conflict)")
        if types["power_in"] and not drivers and net != "NC":
            notes.append(f"ERC: net {net} has power_in pins but no power_out → needs a PWR_FLAG (or a power symbol)")
    # 5. copper geometry of the custom footprints: no two copper pads of different numbers may
    #    overlap or come closer than 0.15 mm (JLC's minimum copper gap class is 0.1 mm)
    for fp_file in sorted((OUT / "motor_board.pretty").glob("*.kicad_mod")):
        cu = [p for p in K.fp_pads(K.load_footprint(fp_file)) if p["number"] and any("Cu" in l for l in p["layers"])]
        boxes = []
        for p in cu:
            (x, y, *rot), (w, h) = p["at"], p["size"]
            if rot and int(float(rot[0])) % 180 == 90:
                w, h = h, w
            boxes.append((p["number"], x - w / 2, y - h / 2, x + w / 2, y + h / 2))
        worst = None
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                if a[0] == b[0]:
                    continue
                gx = max(b[1] - a[3], a[1] - b[3])
                gy = max(b[2] - a[4], a[2] - b[4])
                gap = max(gx, gy)  # < 0 → overlap
                if worst is None or gap < worst[0]:
                    worst = (gap, a[0], b[0])
        if worst and worst[0] < 0.15:
            errors.append(f"{fp_file.stem}: pads {worst[1]} and {worst[2]} are {worst[0]:.3f} mm apart "
                          f"({'overlap' if worst[0] < 0 else 'too close'})")
        elif worst:
            notes.append(f"{fp_file.stem}: minimum copper gap {worst[0]:.3f} mm (pads {worst[1]}/{worst[2]})")
    # 6. custom footprints vs EasyEDA
    pairs = {"SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB": "CONN-SMD_6P-P1.00_XUNPU_WAFER-SH1.0-6PWB",
             "R_2512_HoLR_1-4mR": "RES-SMD_L6.4-W3.2-A",
             "BOOMELE_1.27-2x10P_SMD": "HDR-SMD_20P-P1.27-V-M-R2-C10-S1.27-LS5.5-1",
             "TI_RGF0040E_VQFN-40-1EP_5x7mm_P0.5mm_EP3.7x5.7mm": "VQFN-40_L7.0-W5.0-P0.50-BL-EP5.7"}
    for ours, theirs in pairs.items():
        ep = EASYEDA / f"{theirs}.kicad_mod"
        if not ep.exists():
            continue
        a = {p["number"]: p for p in K.fp_pads(K.load_footprint(OUT / "motor_board.pretty" / f"{ours}.kicad_mod")) if p["number"]}
        b = {}
        for p in K.fp_pads(K.load_footprint(ep)):
            num = {"7": "MP", "8": "MP"}.get(p["number"], p["number"]) if "SH1.0" in ours else p["number"]
            b.setdefault(num, p)
        diffs = []
        # best of four rotations (EasyEDA often draws parts turned), centred on the pad bounding box
        common = [n for n in set(a) & set(b) if n != "MP"]
        ca = centred({n: a[n] for n in common}, 0)
        best = min((max(max(abs(ca[n][0] - cb[n][0]), abs(ca[n][1] - cb[n][1])) for n in common), rot)
                   for rot in (0, 90, 180, 270) for cb in [centred({n: b[n] for n in common}, rot)])
        if best[0] > 0.05:
            diffs.append(f"pad positions differ by up to {best[0]:.2f} mm (best rotation {best[1]} deg)")
        for num in sorted(set(a) & set(b), key=lambda n: (len(n), n)):
            sa = sorted(a[num]["size"]); sb = sorted(b[num]["size"])
            if max(abs(x - y) for x, y in zip(sa, sb)) > 0.05:
                diffs.append(f"pad {num} size {a[num]['size']} vs {b[num]['size']}")
        pitch = lambda d, n1, n2: round(((d[n1]["at"][0] - d[n2]["at"][0]) ** 2 + (d[n1]["at"][1] - d[n2]["at"][1]) ** 2) ** 0.5, 3)
        if "1" in a and "2" in a and "1" in b and "2" in b and pitch(a, "1", "2") != pitch(b, "1", "2"):
            diffs.append(f"pad 1-2 distance {pitch(a, '1', '2')} vs {pitch(b, '1', '2')}")
        (notes if not diffs else warnings).append(
            f"{ours} vs EasyEDA {theirs}: " + ("all pad positions and sizes agree (within 0.05 mm)" if not diffs else "; ".join(diffs[:6])))
    for kind, items in (("ERROR", errors), ("WARN", warnings), ("note", notes)):
        for i in items:
            print(f"{kind}: {i}")
    print(f"\n{len(syms)} symbols, {len(errors)} errors, {len(warnings)} warnings, {len(notes)} notes")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
