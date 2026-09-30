"""Print a placed part's pads: number, net, centre (board mm) and which side of the part they face.
    python3 pins.py U3 [U4 ...]      (reads out/geom_place.json)"""
import json
import sys
from pathlib import Path

g = json.load(open(Path(__file__).resolve().parent / "out" / "geom_place.json"))
for ref in sys.argv[1:]:
    ps = [p for p in g["pads"] if p["ref"] == ref]
    part = [p for p in g["parts"] if p["ref"] == ref][0]
    x0, y0, x1, y1 = part["box"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    print(f"{ref} ({part['side']}) courtyard x {x0:.2f}-{x1:.2f} y {y0:.2f}-{y1:.2f}")
    rows = {}
    for p in sorted(ps, key=lambda p: (len(p["num"]), p["num"])):
        dx, dy = p["c"][0] - cx, p["c"][1] - cy
        face = ("E" if dx > 0 else "W") if abs(dx) > abs(dy) else ("S(rear)" if dy > 0 else "N(front)")
        if abs(dx) < 1.0 and abs(dy) < 1.0:
            face = "centre"
        rows.setdefault(face, []).append(f"{p['num']}:{p['net'].split('/')[-1]}@({p['c'][0]:.2f},{p['c'][1]:.2f})")
    for face, r in rows.items():
        print(f"  {face:8s} " + "  ".join(r))
