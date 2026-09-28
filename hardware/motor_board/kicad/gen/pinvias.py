"""Per-pin via reach for an IC: python3 pinvias.py geom.json REF [r] [pins...]   -> nearest legal via spot per pad
(uses viaspot.py's rules; for choosing MCU pin swaps)."""
import subprocess
import sys
from pathlib import Path

g, ref = sys.argv[1], sys.argv[2]
r = sys.argv[3] if len(sys.argv) > 3 else "1.5"
pins = sys.argv[4:]
for p in pins:
    out = subprocess.run(["python3", str(Path(__file__).with_name("viaspot.py")), g, ref, p, r], capture_output=True, text=True).stdout
    lines = out.strip().splitlines()
    print(lines[0].split(" pad ")[0], "|", lines[1].strip() if len(lines) > 1 else "")
