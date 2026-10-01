"""courtyard sizes and pad boxes (relative to courtyard centre) of parts, from out/geom_place.json"""
import json, sys
from pathlib import Path
g = json.load(open(Path(__file__).resolve().parent.parent / "out" / "geom_place.json"))
for ref in sys.argv[1:]:
    p = [q for q in g["parts"] if q["ref"] == ref][0]
    x0, y0, x1, y1 = p["box"]; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    pads = [q for q in g["pads"] if q["ref"] == ref]
    print(f"{ref} {p['side']} court {x1-x0:.2f} x {y1-y0:.2f} at ({cx:.2f},{cy:.2f}): " + "  ".join(
        f"{q['num']}:{q['net'].split('/')[-1]}[{q['box'][0]-cx:+.2f},{q['box'][1]-cy:+.2f},{q['box'][2]-cx:+.2f},{q['box'][3]-cy:+.2f}]" for q in pads))
