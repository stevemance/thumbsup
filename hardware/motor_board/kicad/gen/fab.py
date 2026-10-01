"""JLC fab package: gerbers + drill (kicad-cli), BOM + CPL with explicit, reviewed rotations.
    /usr/bin/python3 fab.py [board.kicad_pcb | stage] [out_dir]        (default: stage hS -> kicad/gen/out/fab/)

CPL convention = kicad-jlcpcb-tools (fabrication.py): position = centre of the pad bounding box, Y negated; rotation =
KiCad orientation, mirrored for the bottom side as (180 - rot) % 360, then + the JLC correction.  Unlike the plugin's
regex table (cpl_rotations_db), every orientation-sensitive part has an explicit correction here, each verified against
JLC's own footprint for that LCSC part (2026-10-01 footprint triple-check, tmp review fpcheck.json; repo copies of JLC
footprints in kicad/lib_build/ref/easyeda).  The plugin's defaults would have put C1 and U8 in reversed / wrong and U3,
U4, U7, U13, U11, U12, U14, J1 and Q1-Q8 90 deg off, and turned D7-D9 the wrong way.
Two-terminal unpolarised R / C / L / shunts: 0 (rotation is moot).  Any other part without an entry is an error."""
import collections
import csv
import subprocess
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
arg = sys.argv[1] if len(sys.argv) > 1 else "hS"
BOARD = Path(arg) if arg.endswith(".kicad_pcb") else HERE / "out" / "exp" / arg / "proj" / "motor_board.kicad_pcb"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "out" / "fab"

# reference -> JLC rotation correction (deg), with the evidence: JLC footprint name, pad-1 position vs ours
CORR = {
    "U1": 270,   # LQFP-64 C521608: JLC LQFP-64_L10.0-W10.0-P0.50-LS12.0-BL, pad 1 (-3.75,5.7) vs ours (-5.675,-3.75)
    "U2": 0,     # VQFN-48 C543035: JLC ...-TL pin 1 (-3.41,-2.75), same orientation as Texas_RGZ0048A
    "U3": 270,   # DRV8316 C5447274: JLC VQFN-40_L7.0-W5.0-...-BL pad 1 (-2.75,2.4) vs ours (-2.4,-2.75)
    "U4": 270,
    "U5": 270,   # AP2112K SOT-23-5 C51118: JLC SOT-25-5_..-BL pad 1 (-0.95,1.30) vs ours (-1.1375,-0.95)
    "U6": 0,     # SN74LVC08A WQFN-14 C31971766: JLC ...-TL pad 1 (-0.25,-1.40) = ours
    "U7": 270,   # INA239-Q1 VSSOP-10 C4367136: JLC VSSOP-10_..-BL pad 1 (-1.0,2.35) vs ours MSOP-10 (-2.1,-1.0)
    "U8": 0,     # BQ76907 QFN-20 C22458649: JLC VQFN-20_..-TL pad 1 (-1.75,-1.0) = ours (the plugin's QFN-20 rule is wrong)
    "U9": 180,   # SN74LVC3G17 VSSOP-8 C68245: JLC VSSOP-8_L2.1-W2.4-..-BR, fits at 180
    "U10": 180,
    "U11": 270,  # TPS22945 SC-70-5 C47507: JLC SC-70-5_..-BL pad 1 (-0.65,0.84) vs ours SOT-353 (-0.8375,-0.65)
    "U12": 270,
    "U13": 270,  # LM74502 C3236215: JLC SOT-23-8_..-BL pad 1 (-0.97,1.26) vs ours Texas_DDF0008A (-1.3,-0.975)
    "U14": 270,  # 74LVC1G17 SOT-353 C212314: JLC SOT-353_..-BL pad 1 (-0.65,1.01)
    **{f"Q{i}": 270 for i in range(1, 9)},  # HYG015N04LS1C2 C2874970: JLC DFN-8_L5.9-W5.2-..-BL is ours turned +90
    "D1": 0,     # SMBJ20A C151922: JLC SMB pad 1 = K at -x, = ours
    "D2": 0,     # PMEG4030ER C389355: JLC 1 = K at -x, = ours (Nexperia CFP3)
    "D3": 0,     # KT-0603R C2286: cathode at -x in JLC's and ours (vendor numbers it pin 2; check the preview)
    "D4": 0,     # MMSZ5242B SOD-123 C21567: JLC 1 = K at -x
    "D5": 0,     # B5819W SOD-123 C8598: JLC bar on pin 1 at -x
    "D7": 180,   # BAV99 C2500: JLC SOT-23-3_..-BR, fits at 180 (worst pin error 0.30 mm vs >2 mm at 0/90/270)
    "D8": 180,
    "D9": 180,   # BAT54S C47546: same
    "D10": 0,    # 1N4148WS SOD-323 C2128: JLC 1 = K at -x
    "C1": 0,     # EEHZK1V331P C278516: JLC CAP-SMD_BD10.0 pad 1 (+) at -x = ours (the plugin's CP_Elec_10x10 180 is wrong)
    "J1": 90,    # BOOMELE 2x10 C59981: JLC rows along X, ours along Y (part symmetric: +-90 both fine)
    "J2": 180,   # JST BM06B-SRSS-TB C160392: JLC footprint is ours rotated 180
    "J3": 180,
    "J4": 180,   # JST B5B-XH-A C157991: JLC pin 1 at +x; pad-bbox centre = body centre, so no offset needed here
}
TWO_TERMINAL = ("C", "R", "L", "RS", "TH")


def main():
    b = pcbnew.LoadBoard(str(BOARD))
    OUT.mkdir(parents=True, exist_ok=True)
    g = OUT / "gerbers"
    g.mkdir(exist_ok=True)
    pcb = str(BOARD)
    subprocess.run(["kicad-cli", "pcb", "export", "gerbers", "--subtract-soldermask",      # absolute coords, like the drill + CPL
                    "-l", "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts",
                    "-o", str(g), pcb], check=True, capture_output=True)
    subprocess.run(["kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
                    "--generate-map", "--map-format", "gerberx2", "-o", str(g) + "/", pcb], check=True,
                   capture_output=True)
    bom = collections.OrderedDict()
    rows, missing = [], []
    for f in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
        ref = f.GetReference()
        lcsc = f.GetFieldText("LCSC") if f.HasField("LCSC") else ""
        if f.IsDNP() or f.IsExcludedFromBOM() or not lcsc:
            continue
        key = (f.GetValue(), str(f.GetFPID().GetLibItemName()), lcsc)
        bom.setdefault(key, []).append(ref)
        if f.IsExcludedFromPosFiles():
            continue
        prefix = ref.rstrip("0123456789")
        if ref in CORR:
            corr = CORR[ref]
        elif prefix in TWO_TERMINAL:
            corr = 0
        else:
            missing.append(ref); continue
        rot = f.GetOrientationDegrees()
        bottom = f.IsFlipped()
        if bottom:
            rot = (180 - rot) % 360
        rot = (rot + corr) % 360
        pads = list(f.Pads())
        bb = pads[0].GetBoundingBox()
        for p in pads:
            bb.Merge(p.GetBoundingBox())
        c = bb.GetCenter()
        rows.append([ref, f.GetValue(), str(f.GetFPID().GetLibItemName()), f"{pcbnew.ToMM(c.x):.4f}",
                     f"{-pcbnew.ToMM(c.y):.4f}", f"{rot:g}", "bottom" if bottom else "top"])
    if missing:
        raise SystemExit(f"no CPL rotation entry for orientation-sensitive parts: {missing}")
    with open(OUT / "CPL.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Designator", "Val", "Package", "Mid X", "Mid Y", "Rotation", "Layer"])
        w.writerows(rows)
    with open(OUT / "BOM.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC", "Quantity"])
        for (val, fp, lcsc), refs in bom.items():
            w.writerow([val, ",".join(refs), fp, lcsc, len(refs)])
    print(f"{BOARD}\n-> {OUT}: gerbers + drill, BOM {len(bom)} lines / {sum(len(r) for r in bom.values())} parts, "
          f"CPL {len(rows)} placements ({sum(r[6] == 'bottom' for r in rows)} bottom)")


main()
