"""List the anchored parts farthest from their anchor (out/placement_v2.csv)."""
import csv
import sys
from pathlib import Path

rows = list(csv.DictReader(open(Path(__file__).resolve().parent / "out" / "placement_v2.csv")))
n = int(sys.argv[1]) if len(sys.argv) > 1 else 25
for r in sorted([r for r in rows if r["anchor_mm"]], key=lambda r: -float(r["anchor_mm"]))[:n]:
    print(f"{r['ref']:6s} {r['side']:6s} {float(r['anchor_mm']):6.2f} mm  {r['rule']}")
