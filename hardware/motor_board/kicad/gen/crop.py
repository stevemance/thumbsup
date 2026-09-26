"""Render a region of the board (board-local mm) to PNG for review.
/usr/bin/python3 crop.py x0 y0 x1 y1 out.png [layers]   default layers: F.Cu,B.Cu,In2.Cu,Edge.Cuts
Colours: KiCad's (F.Cu red, B.Cu blue, In2 yellow-ish); the board is seen from the top."""
import subprocess
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
import os
PCB = Path(os.environ["CROP_PCB"]) if os.environ.get("CROP_PCB") else HERE.parent / "motor_board" / "motor_board.kicad_pcb"
x0, y0, x1, y1 = map(float, sys.argv[1:5])
out = Path(sys.argv[5]).resolve()
layers = sys.argv[6] if len(sys.argv) > 6 else "F.Cu,B.Cu,In2.Cu,F.SilkS,Edge.Cuts"
b = pcbnew.LoadBoard(str(PCB))
bb = b.GetBoardEdgesBoundingBox()
t = pcbnew.ToMM
W, H = t(bb.GetWidth()), t(bb.GetHeight())
svg = out.with_suffix(".svg")
subprocess.run(["kicad-cli", "pcb", "export", "svg", "--layers", layers, "--mode-single", "--fit-page-to-board",
                "--exclude-drawing-sheet", "-o", str(svg), str(PCB)], capture_output=True)
scale = 60      # px per mm
code = f"""
import cairosvg, io
from PIL import Image
png = cairosvg.svg2png(url={str(svg)!r}, output_width={int(W * scale)}, background_color='white')
im = Image.open(io.BytesIO(png))
fx, fy = im.width / {W}, im.height / {H}
im.crop((int(({x0} + 0.05) * fx), int(({y0} + 0.05) * fy), int(({x1} + 0.05) * fx), int(({y1} + 0.05) * fy))).save({str(out)!r})
"""
subprocess.run(["uv", "run", "--no-project", "--with", "cairosvg", "--with", "pillow", "python", "-c", code], check=True, capture_output=True)
print(out)
