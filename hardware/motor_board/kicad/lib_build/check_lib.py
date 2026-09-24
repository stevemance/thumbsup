#!/usr/bin/env python3
"""Verify out/motor_board.kicad_sym + out/motor_board.pretty against the reviewed design.

Errors (exit 1):
  coverage  every design/bom.csv line is either a library symbol or a generic R/C/NTC (by footprint);
            every library symbol is used by some BOM line;
  fields    symbol Footprint == BOM footprint; symbol LCSC == parts.py's expected code == BOM LCSC
            (two independent sources, so a BOM_TO_SYMBOL mix-up is caught);
  pins      per designator: symbol pin numbers == netlist pin numbers, names agree (all parts
            except connectors and plain R/L, whose netlist names are signal names or 1/2);
            a pin number used twice must carry one name (KiCad stacking);
  pads      symbol pin numbers == the footprint's numbered pads; every numbered pad has copper and
            mask; only "MP" may repeat;
  geometry  (custom footprints) copper pads of different numbers >= 0.15 mm apart; courtyard
            encloses every pad; pads agree with JLC's EasyEDA footprint (ref/easyeda/) within
            0.05 mm unless a deviation is documented in parts.EASYEDA_DEVIATIONS;
  ERC       per netlist net: output-output, output-power_out, power_out-power_out between different
            parts, a no_connect pin on a real net.
Notes: nets needing a PWR_FLAG, minimum copper gaps, documented JLC deviations.
"""
import collections
import csv
import math
import sys
from pathlib import Path

import kicadlib as K
import parts as P

HERE = Path(__file__).parent
OUT = HERE / "out"
DESIGN = HERE.parent.parent / "design"
EASYEDA = HERE / "ref" / "easyeda"
GENERIC_FP = ("R_0402", "R_0603", "R_0805", "R_1206", "C_0402", "C_0603", "C_0805", "C_1206")
NUMBER_ONLY_PREFIX = ("J",)   # connectors: netlist pin names are signal names
PLAIN_2T = ("R", "L")         # netlist names 1/2

errors, warnings, notes = [], [], []


def norm(name):
    return name.replace("~{", "").replace("}", "").replace(" ", "").upper()


def names_match(sym_name, net_name):
    a, b = norm(sym_name), norm(net_name)
    if not a:
        return None
    return a == b or b.startswith(a + "-")


def pad_box(p):
    (x, y, *rot), (w, h) = p["at"], p["size"]
    if rot and int(round(float(rot[0]))) % 180 == 90:
        w, h = h, w
    return x - w / 2, y - h / 2, x + w / 2, y + h / 2


def centred(pts, rot):
    r = math.radians(rot)
    q = {n: (x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r)) for n, (x, y) in pts.items()}
    xs = [v[0] for v in q.values()]
    ys = [v[1] for v in q.values()]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return {n: (x - cx, y - cy) for n, (x, y) in q.items()}


def courtyard(fp):
    xs, ys = [], []
    for ln in K.children(fp, "fp_line") + K.children(fp, "fp_rect"):
        if K.child(ln, "layer") and K.child(ln, "layer")[1] == "F.CrtYd":
            for key in ("start", "end"):
                c = K.child(ln, key)
                xs.append(float(c[1]))
                ys.append(float(c[2]))
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def check_drawing(name, pads):
    """Measure a deviated footprint against the manufacturer-drawing values in parts.DRAWING."""
    d = P.DRAWING.get(name)
    if not d:
        errors.append(f"{name}: documented deviation but no parts.DRAWING entry to measure against")
        return
    def close(a, b, tol=0.02):
        return abs(a - b) <= tol
    if "gap" in d:  # two-pad land along x
        p1, p2 = pads["1"], pads["2"]
        b1, b2 = pad_box(p1), pad_box(p2)
        w, h = b1[2] - b1[0], b1[3] - b1[1]
        gap = b2[0] - b1[2]
        if not (close(w, d["pad"][0]) and close(h, d["pad"][1]) and close(gap, d["gap"])
                and close(b1[1], b2[1]) and pad_box(p2)[2] - pad_box(p2)[0] == w):
            errors.append(f"{name}: land {w:.2f} x {h:.2f}, gap {gap:.2f} vs drawing {d['pad']}, gap {d['gap']}")
    else:  # 2 x n header, odd pins in one column, pin 1 first row
        n = d["n"]
        for i in range(n):
            o, e = pads[str(2 * i + 1)], pads[str(2 * i + 2)]
            bo, be = pad_box(o), pad_box(e)
            if not close(o["at"][1], e["at"][1]) or not bo[0] < be[0]:
                errors.append(f"{name}: pins {2*i+1}/{2*i+2} are not a row pair (odd left, even right)")
                return
            if i and not close(o["at"][1] - pads[str(2 * i - 1)]["at"][1], d["pitch"]):
                errors.append(f"{name}: pitch between pins {2*i-1} and {2*i+1} is not {d['pitch']}")
                return
        b1, b2 = pad_box(pads["1"]), pad_box(pads["2"])
        if not (close(b1[2] - b1[0], d["pad"][0]) and close(b1[3] - b1[1], d["pad"][1]) and close(b2[0] - b1[2], d["row_gap"])):
            errors.append(f"{name}: pad {b1[2]-b1[0]:.2f} x {b1[3]-b1[1]:.2f}, row gap {b2[0]-b1[2]:.2f} vs drawing")


def check_units(name, sym):
    exp = P.UNITS.get(name)
    by_unit = collections.defaultdict(set)
    for p in K.sym_pins(sym):
        by_unit[p["unit"]].add(p["number"])
    got = {frozenset(v) for u, v in by_unit.items() if u}
    if exp is None:
        if len([u for u in by_unit if u]) > 1:
            errors.append(f"{name}: {len(by_unit)} units but no expected grouping in parts.UNITS")
        return
    if got != {frozenset(e) for e in exp}:
        errors.append(f"{name}: unit pin groups {sorted(map(sorted, got))} != datasheet {sorted(map(sorted, exp))}")


def check_hidden(name, sym):
    # KiCad joins every hidden power_in pin to a global net named after the pin, whatever other pins
    # exist (a hidden VM on U3 and U4 would short L_VM to R_VM), so none are allowed
    for p in K.sym_pins(sym):
        if p["hidden"] and p["type"] == "power_in":
            errors.append(f"{name}: hidden power_in pin {p['number']} '{p['name']}' (KiCad makes it a global net)")


def check_stock_arrangement(fp_full):
    ref = P.STOCK_EASYEDA_REF.get(fp_full)
    if not ref:
        return
    lib, fname = fp_full.split(":")
    a = {p["number"]: p for p in K.fp_pads(K.load_footprint(K.stock_footprint_path(lib, fname))) if p["number"]}
    b = {}
    for p in K.fp_pads(K.load_footprint(EASYEDA / f"{ref}.kicad_mod")):
        b.setdefault(p["number"], p)
    common = [n for n in set(a) & set(b)]
    if set(a) != set(b):
        errors.append(f"{fname}: pad numbers differ from JLC {ref}")
        return
    ca = centred({n: a[n]["at"][:2] for n in common}, 0)
    best = min((max(max(abs(ca[n][0] - cb[n][0]), abs(ca[n][1] - cb[n][1])) for n in common), rot)
               for rot in (0, 90, 180, 270) for cb in [centred({n: b[n]["at"][:2] for n in common}, rot)])
    (errors if best[0] > 0.35 else notes).append(
        f"{fname} vs JLC {ref}: pad arrangement within {best[0]:.2f} mm (rotation {best[1]})")


def check_footprint_geometry(path):
    fp = K.load_footprint(path)
    allpads = K.fp_pads(fp)
    pads = [p for p in allpads if p["number"]]
    name = path.stem
    ep_numbers = {p["number"] for p in pads if p["number"] in ("41", "49", "21") and p["size"][0] > 1.5}
    for p in pads:
        L = set(p["layers"])
        if any(l.startswith("B.") for l in L):
            errors.append(f"{name}: pad {p['number']} is on the back side ({sorted(L)})")
        # every SMD pad needs copper, mask and paste; an exposed pad's paste is the paste-only windows
        need = {"F.Cu", "F.Mask"} if p["number"] in ep_numbers else {"F.Cu", "F.Mask", "F.Paste"}
        if not need <= L:
            errors.append(f"{name}: pad {p['number']} lacks {sorted(need - L)} ({sorted(L)})")
    paste_only = [p for p in allpads if not p["number"]]
    for num in ep_numbers:
        ep = next(p for p in pads if p["number"] == num)
        eb = pad_box(ep)
        area = 0.0
        for q in paste_only:
            b = pad_box(q)
            if not (eb[0] - 1e-6 <= b[0] and eb[1] - 1e-6 <= b[1] and b[2] <= eb[2] + 1e-6 and b[3] <= eb[3] + 1e-6):
                errors.append(f"{name}: paste window at {q['at'][:2]} is not inside exposed pad {num}")
            area += (b[2] - b[0]) * (b[3] - b[1])
        cov = area / ((eb[2] - eb[0]) * (eb[3] - eb[1]))
        if not 0.5 <= cov <= 0.85:
            errors.append(f"{name}: exposed pad {num} paste coverage {cov:.0%} (expected 50-85 %)")
        else:
            notes.append(f"{name}: exposed pad {num} paste coverage {cov:.0%}")
    for q in paste_only:
        if not ep_numbers:
            errors.append(f"{name}: paste-only window at {q['at'][:2]} but no exposed pad")
    for num, n in collections.Counter(p["number"] for p in pads).items():
        if n > 1 and num != "MP":
            errors.append(f"{name}: pad number {num} used {n} times")
    boxes = [(p["number"], pad_box(p)) for p in pads]
    worst = None
    for i, (na, a) in enumerate(boxes):
        for nb, b in boxes[i + 1:]:
            if na == nb:
                continue
            gap = max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])
            if worst is None or gap < worst[0]:
                worst = (gap, na, nb)
    if worst and worst[0] < 0.15:
        errors.append(f"{name}: pads {worst[1]} and {worst[2]} are {worst[0]:.3f} mm apart"
                      f" ({'overlap' if worst[0] < 0 else 'too close'})")
    elif worst:
        notes.append(f"{name}: minimum copper gap {worst[0]:.3f} mm (pads {worst[1]}/{worst[2]})")
    crt = courtyard(fp)
    if not crt:
        errors.append(f"{name}: no F.CrtYd outline")
    else:
        for p in allpads:
            b = pad_box(p)
            if b[0] < crt[0] - 1e-6 or b[1] < crt[1] - 1e-6 or b[2] > crt[2] + 1e-6 or b[3] > crt[3] + 1e-6:
                errors.append(f"{name}: pad {p['number'] or '(paste)'} outside the courtyard")
                break
    ref = P.EASYEDA_REF.get(name)
    if not ref:
        errors.append(f"{name}: no EasyEDA reference listed in parts.EASYEDA_REF")
        return
    ep = EASYEDA / f"{ref}.kicad_mod"
    if not ep.exists():
        errors.append(f"{name}: EasyEDA reference {ep} missing")
        return
    a = {p["number"]: p for p in pads}
    b = {}
    for p in K.fp_pads(K.load_footprint(ep)):
        num = P.EASYEDA_PAD_RENAME.get(name, {}).get(p["number"], p["number"])
        b.setdefault(num, p)
    diffs = []
    if set(a) != set(b):
        diffs.append(f"pad numbers differ: ours only {sorted(set(a) - set(b))}, JLC only {sorted(set(b) - set(a))}")
    common = [n for n in set(a) & set(b) if n != "MP"]
    ca = centred({n: a[n]["at"][:2] for n in common}, 0)
    best = min((max(max(abs(ca[n][0] - cb[n][0]), abs(ca[n][1] - cb[n][1])) for n in common), rot)
               for rot in (0, 90, 180, 270) for cb in [centred({n: b[n]["at"][:2] for n in common}, rot)])
    if best[0] > 0.05:
        diffs.append(f"pad positions differ by up to {best[0]:.2f} mm (best rotation {best[1]})")
    for num in sorted(set(a) & set(b), key=lambda n: (len(n), n)):
        if max(abs(x - y) for x, y in zip(sorted(a[num]["size"]), sorted(b[num]["size"]))) > 0.05:
            diffs.append(f"pad {num} size {a[num]['size']} vs JLC {b[num]['size']}")
            break
    dev = P.EASYEDA_DEVIATIONS.get(name)
    if dev:
        # a deviation may change pad size and span, not the arrangement: same numbering, no mirror,
        # no rotation of individual pads, positions within 0.5 mm of JLC's after the best rotation
        if best[0] > 0.5:
            errors.append(f"{name}: pad arrangement differs from JLC by {best[0]:.2f} mm (mirrored/renumbered/wrong pitch?)")
        check_drawing(name, a)
    if diffs and not dev:
        errors.append(f"{name} vs JLC {ref}: " + "; ".join(diffs))
    elif diffs:
        notes.append(f"{name} vs JLC {ref}: documented deviation ({dev}): " + "; ".join(diffs))
    elif dev:
        warnings.append(f"{name}: deviation documented but the footprint now matches JLC")
    else:
        notes.append(f"{name} vs JLC {ref}: all pads agree within 0.05 mm")


def main():
    syms = K.symbols(K.load_symbol_lib(OUT / "motor_board.kicad_sym"))
    specs = {**P.NEW, **P.STOCK}
    netlist = collections.defaultdict(dict)
    nets = collections.defaultdict(list)
    for r in csv.DictReader(open(DESIGN / "netlist.csv")):
        netlist[r["ref"]][r["pin"]] = r["pin_name"]
        nets[r["net"]].append((r["ref"], r["pin"]))
    used = set()
    ref_types = {}
    checked_stock = set()
    bom_md = (DESIGN.parent / "BOM.md").read_text().splitlines()
    for row in csv.DictReader(open(DESIGN / "bom.csv")):
        name = P.BOM_TO_SYMBOL.get(row["Comment"])
        refs = row["Designator"].split(",")
        if not name:
            if not row["Footprint"].startswith(GENERIC_FP):
                errors.append(f"BOM line '{row['Comment']}' ({row['Designator']}) has no library symbol and is not a generic R/C")
            continue
        used.add(name)
        s = syms.get(name)
        if s is None:
            errors.append(f"{name}: missing from the library")
            continue
        props = K.sym_props(s)
        spec = specs[name]
        check_units(name, s)
        check_hidden(name, s)
        if props["Footprint"] in P.STOCK_EASYEDA_REF and name not in checked_stock:
            checked_stock.add(name)
            check_stock_arrangement(props["Footprint"])
        # MPN: the symbol name must appear in the BOM comment or in BOM.md's row for that LCSC
        alnum = lambda t: "".join(ch for ch in t.upper().replace("*", "X") if ch.isalnum())
        texts = [row["Comment"]] + [l for l in bom_md if row["LCSC Part #"] in l]
        if not any(alnum(name) in alnum(t) for t in texts):
            errors.append(f"{name}: part number not found in the BOM comment or BOM.md row for {row['LCSC Part #']}")
        fp_lib, fp_name = props["Footprint"].split(":")
        if fp_name != row["Footprint"]:
            errors.append(f"{name}: Footprint {fp_name} != BOM {row['Footprint']}")
        if not (props.get("LCSC") == spec["lcsc"] == row["LCSC Part #"]):
            errors.append(f"{name}: LCSC symbol {props.get('LCSC')} / parts.py {spec['lcsc']} / BOM {row['LCSC Part #']} disagree")
        pins = K.sym_pins(s)
        by_num = collections.defaultdict(set)
        for p in pins:
            by_num[p["number"]].add(p["name"])
        for num, nm in by_num.items():
            if len(nm) > 1:
                errors.append(f"{name}: pin number {num} used with different names {sorted(nm)}")
        sym_nums = set(by_num)
        types = {p["number"]: p["type"] for p in pins}
        compare_names = not refs[0].startswith(NUMBER_ONLY_PREFIX) and refs[0][0] not in PLAIN_2T
        for ref in refs:
            ref_types[ref] = types
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
                            errors.append(f"{name}/{ref}: pin {num} is '{sname}' in the symbol, '{nname}' in the netlist")
                        elif m is None:
                            errors.append(f"{name}/{ref}: pin {num} unnamed in the symbol (netlist '{nname}')")
        fpath = (OUT / "motor_board.pretty" / f"{fp_name}.kicad_mod") if fp_lib == "motor_board" \
            else K.stock_footprint_path(fp_lib, fp_name)
        if not fpath.exists():
            errors.append(f"{name}: footprint file {fpath} missing")
            continue
        pad_nums = {p["number"] for p in K.fp_pads(K.load_footprint(fpath)) if p["number"]}
        if pad_nums != sym_nums:
            errors.append(f"{name}: footprint {fp_name} pads without pin {sorted(pad_nums - sym_nums)}, "
                          f"pins without pad {sorted(sym_nums - pad_nums)}")
    for name in syms:
        if name not in used:
            errors.append(f"{name}: in the library but used by no BOM line")
    for path in sorted((OUT / "motor_board.pretty").glob("*.kicad_mod")):
        check_footprint_geometry(path)
    for net, members in sorted(nets.items()):
        if net == "NC":  # the netlist's bucket for unconnected pins (no-connect flags in the schematic)
            continue
        by = collections.defaultdict(set)
        for ref, pin in members:
            if ref in ref_types:
                by[ref_types[ref].get(pin)].add(ref)
        if len(by["output"]) > 1:
            errors.append(f"ERC {net}: outputs from {sorted(by['output'])}")
        if by["output"] and by["power_out"]:
            errors.append(f"ERC {net}: output {sorted(by['output'])} vs power_out {sorted(by['power_out'])}")
        if len(by["power_out"]) > 1:
            errors.append(f"ERC {net}: power_out from {sorted(by['power_out'])}")
        if by["no_connect"]:
            errors.append(f"ERC {net}: no_connect pin of {sorted(by['no_connect'])} on a real net")
        if by["power_in"] and not by["power_out"]:
            notes.append(f"ERC {net}: power_in without a power_out driver → PWR_FLAG in the schematic")
    for kind, items in (("ERROR", errors), ("WARN", warnings), ("note", notes)):
        for i in items:
            print(f"{kind}: {i}")
    print(f"\n{len(syms)} symbols, {len(errors)} errors, {len(warnings)} warnings, {len(notes)} notes")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
