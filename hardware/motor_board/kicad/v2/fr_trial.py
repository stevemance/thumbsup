"""Freerouting trial on a COPY of the placed v2 board (never the project board).
    /usr/bin/python3 fr_trial.py prep     # copy + zones/rule areas -> out/fr/board.kicad_pcb, board.dsn (pour nets cut)
    /usr/bin/python3 fr_trial.py route N  # Freerouting N passes -> board.ses
    /usr/bin/python3 fr_trial.py import   # SES -> out/fr/routed.kicad_pcb, DRC summary
Setup (memo 3.1): In1 = GND plane (GND pads reach it with vias); In2 routable except the front power band and the
L3 islands under U3/U4; B.Cu routable except the front band and the thermal-via fields; the pour nets (VBAT, pack path,
weapon phase/shunt nodes, drive outputs and VM feeds) are removed from the DSN network: pours carry them, their pads
stay as obstacles."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FR = HERE / "out" / "fr"
FR.mkdir(parents=True, exist_ok=True)
SRC = HERE.parent / "motor_board" / "motor_board.kicad_pcb"
BIN = Path("/home/smance/projects/thumbsup/hardware/tools/freerouting/freerouting-2.4.1-linux-x64/bin/freerouting")
OX, OY = 100.0, 70.0
POUR = ["VBAT", "BAT_IN", "PSW_S", "VBAT_SW", "W_A", "W_B", "W_C", "W_SLA", "W_SLB", "W_SLC", "L_A", "L_B", "L_C",
        "R_A", "R_B", "R_C", "L_VM", "R_VM"]


def rect(x0, y0, x1, y1):
    import pcbnew
    ch = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        ch.Append(pcbnew.VECTOR2I_MM(OX + x, OY + y))
    ch.SetClosed(True)
    return ch


def prep():
    import pcbnew
    shutil.copy(SRC, FR / "board.kicad_pcb")
    for ext in (".kicad_pro", ".kicad_dru"):
        shutil.copy(SRC.with_suffix(ext), FR / ("board" + ext))
    if "--nogv" not in sys.argv:     # GND stitch vias at the SMD GND pads first (P3), so the router only sees signals
        subprocess.run(["/usr/bin/python3", str(HERE / "gndvias.py"), str(FR / "board.kicad_pcb")], check=True)
    b = pcbnew.LoadBoard(str(FR / "board.kicad_pcb"))
    gnd = b.FindNet("GND")
    z = pcbnew.ZONE(b)
    z.SetLayer(pcbnew.In1_Cu); z.SetNet(gnd); z.Outline().AddOutline(rect(0.3, 0.3, 84.7, 34.7))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    b.Add(z)

    def keepout(layers, box, name, vias=True):
        k = pcbnew.ZONE(b)
        k.SetIsRuleArea(True)
        k.SetDoNotAllowTracks(True); k.SetDoNotAllowVias(vias); k.SetDoNotAllowPads(False)
        k.SetDoNotAllowZoneFills(False); k.SetDoNotAllowFootprints(False)
        ls = pcbnew.LSET()
        for l in layers:
            ls.AddLayer(l)
        k.SetLayerSet(ls)
        k.Outline().AddOutline(rect(*box))
        k.SetZoneName(name)
        b.Add(k)

    keepout([pcbnew.In2_Cu, pcbnew.B_Cu], (0.0, 0.0, 85.0, 18.5), "front power band", vias=False)   # no tracks; GND stitching and a few signal vias may pass
    keepout([pcbnew.In1_Cu], (0.0, 0.0, 85.0, 35.0), "L2 GND: no tracks", vias=False)
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    for ref in ("U2", "U3", "U4"):
        ep = max(fps[ref].Pads(), key=lambda p: p.GetBoundingBox().GetWidth() * p.GetBoundingBox().GetHeight())
        bb = ep.GetBoundingBox()
        box = [pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())]
        box = [box[0] - OX, box[1] - OY, box[2] - OX, box[3] - OY]
        keepout([pcbnew.B_Cu], (box[0] - 0.5, box[1] - 0.5, box[2] + 0.5, box[3] + 0.5), f"{ref} thermal field")
        if ref != "U2":
            keepout([pcbnew.In2_Cu], (box[0] - 1.5, box[1] - 1.5, box[2] + 1.5, box[3] + 1.5), f"{ref} L3 island")
    pcbnew.SaveBoard(str(FR / "board.kicad_pcb"), b)
    b = pcbnew.LoadBoard(str(FR / "board.kicad_pcb"))
    if not pcbnew.ExportSpecctraDSN(b, str(FR / "board_full.dsn")):
        raise SystemExit("DSN export failed")
    # cut the pour nets from the network section
    t = (FR / "board_full.dsn").read_text()
    cut = 0
    for n in POUR:
        for full in {m for m in re.findall(r'\(net "?([^\s")]+)"?', t) if m.split("/")[-1] == n}:
            pat = re.compile(r'\n\s*\(net "?' + re.escape(full) + r'"?\s*\n\s*\(pins[^)]*\)\s*\)')
            t, k = pat.subn("", t)
            cut += k
    # L2 = GND plane: a "power" layer (vias pass, no tracks).  A wire_keepout over the whole layer made Freerouting
    # refuse every via (2026-09-29: 0 vias in 20 passes); declaring the layer a plane is the Specctra way.
    t = re.sub(r'\n\s*\(wire_keepout "" \(polygon L2\.GND[^)]*\)\)', "", t)
    t = t.replace("(layer L2.GND\n      (type signal)", "(layer L2.GND\n      (type power)")
    # Freerouting 2.4.1 never routes on a layer whose name says PWR/GND (0 L3 tracks in 20 passes with it named
    # L3.PWR_GND; an autoroute_settings scope in the DSN breaks its parser): rename it for the router, back on import
    t = t.replace("L3.PWR_GND", "L3.SIG")
    (FR / "board.dsn").write_text(t)
    print("DSN written, pour nets cut:", cut)


def route(passes):
    cmd = [str(BIN), "-de", str(FR / "board.dsn"), "-do", str(FR / "board.ses"), "-mp", str(passes), "-mt", "8",
           "--gui.enabled=false", "--router.fanout.enabled=false", f"--router.max_passes={passes}",
           "--router.optimizer.enabled=false"]
    print(" ".join(cmd), flush=True)
    with open(FR / "fr.log", "w") as f:
        subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, text=True, timeout=7200)
    print("\n".join((FR / "fr.log").read_text().splitlines()[-15:]))


def imp():
    import pcbnew
    b = pcbnew.LoadBoard(str(FR / "board.kicad_pcb"))
    ses = FR / "board.ses"
    ses.write_text(ses.read_text().replace("L3.SIG", "L3.PWR_GND"))
    if not pcbnew.ImportSpecctraSES(b, str(ses)):
        raise SystemExit("SES import failed")
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(str(FR / "routed.kicad_pcb"), b)
    r = subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "-o", str(FR / "drc.json"), str(FR / "routed.kicad_pcb")],
                       capture_output=True, text=True)
    d = json.load(open(FR / "drc.json"))
    import collections
    unc = collections.Counter()
    for u in d.get("unconnected_items", []):
        for it in u["items"]:
            m = re.search(r"\[(.*?)\]", it["description"])
            if m:
                unc[m.group(1).split("/")[-1]] += 1
                break
    print("violations:", collections.Counter(v["type"] for v in d["violations"]).most_common(8))
    print("unconnected:", len(d.get("unconnected_items", [])), "by net:", unc.most_common(40))


if __name__ == "__main__":
    {"prep": prep, "route": lambda: route(int(sys.argv[2]) if len(sys.argv) > 2 else 30), "import": imp}[sys.argv[1]]()
