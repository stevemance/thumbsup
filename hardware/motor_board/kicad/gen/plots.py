"""One plot.py image per layer: python3 plots.py geom.json drc.json x0 y0 x1 y1 outprefix "F,B,L3,L4" [nets]"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
geom, drc, x0, y0, x1, y1, pre, layers = sys.argv[1:9]
nets = sys.argv[9] if len(sys.argv) > 9 else None
for l in layers.split(","):
    cmd = ["uv", "run", "--no-project", "--with", "matplotlib", "python", str(HERE / "plot.py"), geom, drc, x0, y0, x1, y1,
           f"{pre}_{l}.png", l] + ([nets] if nets else [])
    subprocess.run(cmd, check=True)
    print(f"{pre}_{l}.png")
