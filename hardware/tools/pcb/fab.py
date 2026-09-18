#!/usr/bin/env python3
"""JLCPCB fabrication outputs from kicad/thumbsup.kicad_pcb + the schematic:

    hardware/fab/thumbsup_gerbers.zip     Gerbers (4 Cu, mask, paste, silk, edge) + Excellon drills
    hardware/fab/thumbsup_bom.csv         JLC BOM: Comment, Designator, Footprint, LCSC Part #
    hardware/fab/thumbsup_cpl.csv         JLC CPL: Designator, Mid X, Mid Y, Layer, Rotation

    /usr/bin/python3 hardware/tools/pcb/fab.py [outdir]

Only parts with an LCSC field and not DNP go on the BOM/CPL (the Pico W, XT30, headers,
test points, net-ties, motor holes and fiducials are hand-soldered or bare copper)."""

from __future__ import annotations

import csv
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from board import KICAD, ROOT  # noqa: E402

PCB = KICAD / "thumbsup.kicad_pcb"
LAYERS = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"


def gerbers(out: Path):
    g = out / "gerbers"
    if g.exists():
        shutil.rmtree(g)
    g.mkdir(parents=True)
    subprocess.run(["kicad-cli", "pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask",
                    "--no-x2", "--use-drill-file-origin", "-o", str(g) + "/", str(PCB)], check=True, capture_output=True)
    subprocess.run(["kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
                    "--drill-origin", "plot", "--generate-map", "--map-format", "gerberx2", "-o", str(g) + "/", str(PCB)],
                   check=True, capture_output=True)
    z = out / "thumbsup_gerbers.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(g.iterdir()):
            zf.write(f, f.name)
    return z


def bom_cpl(out: Path):
    board = pcbnew.LoadBoard(str(PCB))
    bom_rows, cpl_rows = [], []
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for fp in board.Footprints():
        ref = fp.GetReference()
        lcsc = fp.GetFieldText("LCSC") if fp.HasField("LCSC") else ""
        if not lcsc or fp.IsDNP():
            continue
        fpid = fp.GetFPIDAsString().split(":")[-1]
        grouped.setdefault((fp.GetValue(), fpid, lcsc), []).append(ref)
        pos = fp.GetPosition()
        cpl_rows.append([ref, f"{pcbnew.ToMM(pos.x):.3f}", f"{-pcbnew.ToMM(pos.y):.3f}",
                         "Bottom" if fp.IsFlipped() else "Top", f"{fp.GetOrientationDegrees():.1f}"])
    for (value, fpid, lcsc), refs in sorted(grouped.items(), key=lambda kv: kv[1][0]):
        bom_rows.append([value, ",".join(sorted(refs)), fpid, lcsc])
    with (out / "thumbsup_bom.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        w.writerows(bom_rows)
    with (out / "thumbsup_cpl.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        w.writerows(sorted(cpl_rows))
    return len(bom_rows), len(cpl_rows)


def main(argv):
    out = Path(argv[0]) if argv else ROOT / "hardware" / "fab"
    out.mkdir(parents=True, exist_ok=True)
    z = gerbers(out)
    n_bom, n_cpl = bom_cpl(out)
    print(f"{z} ({z.stat().st_size // 1024} kB), BOM lines {n_bom}, CPL parts {n_cpl}")


if __name__ == "__main__":
    main(sys.argv[1:])
