#!/usr/bin/env python3
"""Build kicad/thumbsup.kicad_pcb from the schematic netlist + mechanical outline +
the placement/copper described in placement.py.  Runs with the system python3
(KiCad 10's pcbnew module).

    /usr/bin/python3 hardware/tools/pcb/build_pcb.py [--render] [--no-route]

Stages: populate footprints/nets -> outline & holes -> net classes -> placement
-> hand copper (zones, Kelvin, gate loops) -> Freerouting for the rest -> DRC.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from board import KICAD, ROOT, Board, mm, pt  # noqa: E402

MECH = ROOT / "hardware" / "mech" / "board_outline.json"
PCB = KICAD / "thumbsup.kicad_pcb"
PRO = KICAD / "thumbsup.kicad_pro"

# LAYOUT.md §2 — net classes: (name, clearance, track width, via size, via drill, patterns)
NET_CLASSES = [
    # power nets are carried by pours; the class track width only serves the sense / driver /
    # bootstrap pins on the bottom (a 3 mm width would make Freerouting skip these nets)
    ("POWER_30A", 0.1, 0.3, 0.5, 0.3, ["VBAT_PACK", "VBAT_LINK", "VBAT", "MOTOR_W_*", "*I_W+"]),
    ("POWER_20A", 0.1, 0.3, 0.5, 0.3, ["MOTOR_L_*", "MOTOR_R_*", "*I_L+", "*I_R+"]),
    ("GATE", 0.1, 0.25, 0.4, 0.2, ["?_HO?", "?_LO?", "?_G?H", "?_G?L", "?_VB?", "?_BT?"]),
    ("VDRV", 0.1, 0.6, 0.6, 0.3, ["+VDRV", "W_VCC", "+5V", "+5V_PICO", "U1_SW"]),
    ("3V3", 0.1, 0.25, 0.4, 0.2, ["+3V3_A", "+3V3_MCU", "+3V3_PICO"]),
    ("SENSE", 0.1, 0.1, 0.4, 0.2, ["?_ISENSE", "?_CSA_OUT", "I_?_S+", "I_?_S-", "PACK_S+", "PACK_S-", "U?_IN+", "U?_IN-", "?_VSENSE", "?_BEMF_?", "?_VN", "PACK_V_ADC", "3V3_MON", "NTC_ADC"]),
]


def write_net_classes():
    pro = json.loads(PRO.read_text())
    ns = pro.setdefault("net_settings", {})
    classes = [{
        "name": "Default", "clearance": 0.1, "track_width": 0.1, "via_diameter": 0.4, "via_drill": 0.2,
        "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "microvia_diameter": 0.3, "microvia_drill": 0.1,
        "bus_width": 12, "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "wire_width": 6,
    }]
    patterns = []
    for name, clr, w, via, drill, pats in NET_CLASSES:
        classes.append({
            "name": name, "clearance": clr, "track_width": w, "via_diameter": via, "via_drill": drill,
            "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": w, "microvia_diameter": 0.3, "microvia_drill": 0.1,
            "bus_width": 12, "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "wire_width": 6,
        })
        for p in pats:
            patterns.append({"netclass": name, "pattern": p})
    ns["classes"] = classes
    ns["netclass_patterns"] = patterns
    ns["meta"] = {"version": 4}
    PRO.write_text(json.dumps(pro, indent=2))


def stackup(b: Board):
    """4 layers, 1.6 mm, 2 oz outer / 1 oz inner (JLC)."""
    ds = b.b.GetDesignSettings()
    b.b.SetCopperLayerCount(4)
    ds.SetBoardThickness(mm(1.6))
    # layer names for the JLC stack: L1 power, L2 GND, L3 signal/rails, L4 power mirror
    b.b.SetLayerName(pcbnew.In1_Cu, "GND")
    b.b.SetLayerName(pcbnew.In2_Cu, "SIG")


def outline_and_holes(b: Board, mech: dict):
    b.outline(mech["outline"])
    for i, (x, y) in enumerate(mech["holes_m25"], 1):
        ref = f"H{i}"
        if ref in b.fps:
            b.place(ref, x, y)
    # fiducials: three corners of the wide section
    fid = [(11.0, 36.1), (47.3, 49.0), (99.7, 25.7)]
    for i, (x, y) in enumerate(fid, 1):
        if f"FID{i}" in b.fps:
            b.place(f"FID{i}", x, y)
    b.text("ThumbsUp v1.2", 21.5, 36.2, size=1.0)


def main(argv):
    mech = json.loads(MECH.read_text())
    b = Board()
    comps, nets = b.populate(KICAD / "thumbsup_kicad.net")
    b.design_rules()
    stackup(b)
    outline_and_holes(b, mech)
    import placement  # noqa: E402

    placement.place_all(b, mech)
    problems = placement.check(b, mech)
    for p in problems:
        print("PLACEMENT:", p)
    print(f"placement check: {len(problems)} problems")
    import copper  # noqa: E402

    copper.copper(b, mech, placement.BLOCKS, placement.SHUNTS)
    b.fill_zones()
    print("GND vias for top pads (n, in-pad):", copper.gnd_pad_vias(b.b, mech["outline"]))
    print("GND island stitch vias (added, missed):", copper.stitch_gnd_islands(b.b, mech["outline"]))
    for z in b.b.Zones():
        if not z.GetIsRuleArea():
            for l in z.GetLayerSet().Seq():
                n = z.GetFilledPolysList(l).OutlineCount()
                if n > 1:
                    print(f"  zone '{z.GetZoneName()}' on {b.b.GetLayerName(l)}: {n} islands")
    b.save(PCB)
    write_net_classes()
    print(f"wrote {PCB}: {len(b.fps)} footprints, {len(b.nets)} nets")
    if "--no-route" not in argv:
        import route  # noqa: E402

        route.autoroute(PCB)
    drc = subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-error", "-o", str(KICAD / "drc.json"), str(PCB)], capture_output=True, text=True)
    rep = json.loads((KICAD / "drc.json").read_text())
    from collections import Counter

    c = Counter((v["severity"], v["type"]) for v in rep.get("violations", []))
    print("DRC:", dict(c) if c else "clean", "| unconnected:", len(rep.get("unconnected_items", [])))
    if "--render" in argv:
        render()
    return 0


def render():
    prev = KICAD / "preview"
    prev.mkdir(exist_ok=True)
    subprocess.run(["kicad-cli", "pcb", "export", "svg", "--layers", "F.Cu,B.Cu,F.SilkS,Edge.Cuts,F.Mask", "--page-size-mode", "2", "--exclude-drawing-sheet", "-o", str(prev / "pcb_top.svg"), str(PCB)], capture_output=True)
    subprocess.run(["kicad-cli", "pcb", "export", "svg", "--layers", "In1.Cu,In2.Cu,B.Cu,Edge.Cuts", "--page-size-mode", "2", "--exclude-drawing-sheet", "-o", str(prev / "pcb_inner.svg"), str(PCB)], capture_output=True)
    subprocess.run(["kicad-cli", "pcb", "render", "--side", "top", "--zoom", "1", "-o", str(prev / "pcb_3d_top.png"), str(PCB)], capture_output=True)
    subprocess.run(["kicad-cli", "pcb", "render", "--side", "bottom", "-o", str(prev / "pcb_3d_bottom.png"), str(PCB)], capture_output=True)
    for svg in ("pcb_top.svg", "pcb_inner.svg"):
        subprocess.run(["convert", "-density", "150", str(prev / svg), "-background", "white", "-flatten", str(prev / svg.replace(".svg", ".png"))], capture_output=True)
        (prev / svg).unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
