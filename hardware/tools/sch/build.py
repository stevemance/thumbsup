#!/usr/bin/env python3
"""Build the ThumbsUp KiCad schematic from ``circuit.py`` and prove it.

Steps:
1. write the custom symbol library,
2. build the SKiDL circuit, run SKiDL ERC, write ``thumbsup.net`` (reference netlist),
3. draw every sheet with explicit placement (``layouts.py``),
4. run ``kicad-cli sch erc`` and ``kicad-cli sch export netlist`` on the result,
5. compare the KiCad netlist with the SKiDL netlist — same (ref, pin) partition or fail,
6. render PNG previews into ``kicad/preview`` for review.

Run from anywhere::

    hardware/tools/.venv/bin/python hardware/tools/sch/build.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parents[2]
OUT = ROOT / "hardware" / "kicad"
os.environ.setdefault("KICAD10_SYMBOL_DIR", "/usr/share/kicad/symbols")
os.environ.setdefault("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")

import kicad_sch_api as ksa  # noqa: E402

import circuit  # noqa: E402
import layouts  # noqa: E402
import symbols  # noqa: E402
from draw import Root, Sheet  # noqa: E402
from sexp import kicad_netlist_nets  # noqa: E402

SHEETS = [
    # key, file stem, title, drawer
    ("pack", "thumbsup_pack", "Pack input, TVS, shunt, reverse polarity", lambda d, s: layouts.draw_pack(d, s), "A4"),
    ("rails", "thumbsup_rails", "5 V buck, 3V3 LDOs, monitors", lambda d, s: layouts.draw_rails(d, s)),
    ("pico", "thumbsup_pico", "Pico W and control I/O", lambda d, s: layouts.draw_pico(d, s)),
    ("sense", "thumbsup_sense", "INA226 x4, IMU, high-g", lambda d, s: layouts.draw_sense(d, s)),
    ("io", "thumbsup_io", "Log flash and status LEDs", lambda d, s: layouts.draw_io(d, s)),
    ("esc_l", "thumbsup_esc_l", "ESC L control (AM32)", lambda d, s: layouts.draw_esc(d, s, "L", 200)),
    ("esc_l_bridge", "thumbsup_esc_l_bridge", "ESC L power stage", lambda d, s: layouts.draw_bridge(d, s, "L", 200)),
    ("esc_r", "thumbsup_esc_r", "ESC R control (AM32)", lambda d, s: layouts.draw_esc(d, s, "R", 300)),
    ("esc_r_bridge", "thumbsup_esc_r_bridge", "ESC R power stage", lambda d, s: layouts.draw_bridge(d, s, "R", 300)),
    ("esc_w", "thumbsup_esc_w", "ESC W control (AM32) + weapon enable", lambda d, s: (layouts.draw_esc(d, s, "W", 400), layouts.draw_weapon_enable(d, s))),
    ("esc_w_bridge", "thumbsup_esc_w_bridge", "ESC W power stage", lambda d, s: layouts.draw_bridge(d, s, "W", 400)),
]


def cross_sheet_nets(d) -> set:
    sheets = defaultdict(set)
    for p in d.parts:
        for pin in p.pins:
            if pin.is_connected() and pin.net is not None:
                sheets[pin.net.name].add(d.sheet_of[p.ref])
    return {n for n, ss in sheets.items() if len(ss) > 1}


def skidl_partition(d) -> dict[frozenset, str]:
    nets = defaultdict(set)
    for p in d.parts:
        for pin in p.pins:
            if pin.is_connected() and pin.net is not None and not pin.net.name.startswith("__NOCONNECT"):
                nets[pin.net.name].add((p.ref, str(pin.num)))
    return {frozenset(v): k for k, v in nets.items() if v}


def kicad_partition(net_text: str) -> dict[frozenset, str]:
    nets = kicad_netlist_nets(net_text)
    return {frozenset(v): k for k, v in nets.items() if v}


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    symbols.write_library(OUT)
    cache = ksa.get_symbol_cache()
    cache.add_library_path(OUT / "thumbsup.kicad_sym")

    d = circuit.build(OUT)
    circuit.check_and_netlist(d, OUT / "thumbsup.net")
    for junk in ("build.erc", "build_sklib.py", "circuit.erc"):  # SKiDL side files
        (Path.cwd() / junk).unlink(missing_ok=True)
    cross = cross_sheet_nets(d)
    drawn: set[str] = set()

    for i, row in enumerate(SHEETS):
        key, stem, title, drawer = row[:4]
        paper = row[4] if len(row) > 4 else "A3"
        s = Sheet(d, key, title, OUT / f"{stem}.kicad_sch", cross, paper=paper, sid=i + 1)
        drawer(d, s)
        # every part assigned to this sheet must have been placed
        missing = [p.ref for p in d.parts if d.sheet_of[p.ref] == key and p.ref not in s.comps]
        if missing:
            print(f"ERROR: sheet {key} did not place {missing}")
            return 1
        drawn.update(s.comps)
        s.finish()
    unplaced = [p.ref for p in d.parts if p.ref not in drawn]
    if unplaced:
        print(f"ERROR: never placed {unplaced}")
        return 1

    root = Root("ThumbsUp v1", OUT / "thumbsup.kicad_sch")
    root.text(20, 22, "ThumbsUp v1 — 1 lb antweight control / power / 3× AM32 ESC board", 3, True)
    root.text(20, 30, "Generated from hardware/tools/sch/circuit.py (SKiDL).  Do not edit the .kicad_sch files by hand; edit the Python and rebuild.", 1.5)
    root.text(20, 35, "Cross-sheet signals are global labels; rails are power symbols.  Sheet order follows the power flow.", 1.5)
    cols = 3
    for i, (key, stem, title, *_) in enumerate(SHEETS):
        x = 30.48 + (i % cols) * 91.44
        y = 50.8 + (i // cols) * 33.02
        root.sheet(title, f"{stem}.kicad_sch", x, y, 76.2, 20.32)
    root.finish()

    # ---- KiCad checks
    erc = run(["kicad-cli", "sch", "erc", "--format", "json", "--severity-all", "-o", str(OUT / "erc.json"), str(OUT / "thumbsup.kicad_sch")])
    if erc.returncode not in (0, 5):
        print(erc.stdout, erc.stderr)
    report = json.loads((OUT / "erc.json").read_text())
    counts = defaultdict(int)
    for sh in report["sheets"]:
        for v in sh["violations"]:
            if v.get("excluded"):
                continue
            counts[(v["severity"], v["type"])] += 1
    print("KiCad ERC:")
    for (sev, typ), n in sorted(counts.items()):
        print(f"  {sev:8} {typ:32} {n}")
    if "--verbose" in sys.argv:
        for sh in report["sheets"]:
            for v in sh["violations"]:
                if v["severity"] == "warning" and v["type"] != "four_way_junction":
                    print("   ", sh.get("path", ""), v["type"], [i.get("description", "")[:60] for i in v.get("items", [])])
    shown = 0
    for sh in report["sheets"]:
        for v in sh["violations"]:
            if v.get("excluded") or v["severity"] != "error" or shown >= 40:
                continue
            items = "; ".join(i.get("description", "")[:60] for i in v.get("items", []))
            print(f"    {sh.get('path', '')} {v['type']}: {v['description'][:70]} [{items}]")
            shown += 1
    net = run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(OUT / "thumbsup_kicad.net"), str(OUT / "thumbsup.kicad_sch")])
    if net.returncode != 0:
        print(net.stdout, net.stderr)
        return 1

    # ---- pad-function sanity: symbol pin numbers must match the vendor pinout the footprint uses.
    # (The equivalence check below compares (ref, pin) partitions, so it cannot see this class of error.)
    pad_errors = []
    for p in d.parts:
        if p.name == "HYG015N04LS1C2":
            nets = {str(pin.num): (pin.net.name if pin.is_connected() else None) for pin in p.pins}
            if not (nets["1"] == nets["2"] == nets["3"]) or nets["4"] in (nets["1"], nets["5"]) or nets["5"] == nets["1"]:
                pad_errors.append(f"{p.ref}: S={nets['1']},{nets['2']},{nets['3']} G={nets['4']} D={nets['5']}")
        if p.name in ("Q_PMOS_GSD", "AO3400A"):
            nets = {str(pin.num): (pin.net.name if pin.is_connected() else None) for pin in p.pins}
            if len({nets["1"], nets["2"], nets["3"]}) != 3:
                pad_errors.append(f"{p.ref}: G/S/D not on distinct nets {nets}")
    if pad_errors:
        print("PAD MAPPING ERRORS:", *pad_errors, sep="\n  ")
        return 1

    # ---- netlist equivalence
    want = skidl_partition(d)
    got = kicad_partition((OUT / "thumbsup_kicad.net").read_text())
    ok = True
    for grp, name in want.items():
        if grp not in got:
            ok = False
            # find where the pins ended up
            where = defaultdict(set)
            for g2, n2 in got.items():
                for pin in grp:
                    if pin in g2:
                        where[n2].add(pin)
            print(f"MISMATCH skidl net {name}: {sorted(grp)}\n   kicad has: {dict(where)}")
    extra = [name for grp, name in got.items() if grp not in want and len(grp) > 1]
    if extra:
        ok = False
        print("EXTRA kicad nets:", extra)
    print("netlist equivalence:", "OK" if ok else "FAILED", f"({len(want)} nets)")
    errors = sum(n for (sev, _), n in counts.items() if sev == "error")
    return 0 if ok and errors == 0 else 2


def render(dpi: int = 70):
    """PDF per sheet, rasterised with pdftoppm (KiCad's SVG text needs its own font)."""
    prev = OUT / "preview"
    prev.mkdir(exist_ok=True)
    for old in prev.glob("*.png"):
        old.unlink()
    for row in [("root", "thumbsup", "", None)] + SHEETS:
        stem = row[1]
        pdf = prev / f"{stem}.pdf"
        run(["kicad-cli", "sch", "export", "pdf", "--no-background-color", "-o", str(pdf), str(OUT / f"{stem}.kicad_sch")])
        run(["pdftoppm", "-r", str(dpi), "-png", "-singlefile", "-f", "1", "-l", "1", str(pdf), str(prev / stem)])
        pdf.unlink(missing_ok=True)


if __name__ == "__main__":
    rc = main()
    if "--render" in sys.argv:
        render()
    sys.exit(rc)
