"""pad centres/boxes from a stage's geom_r2.json:  python3 r2/padxy.py EXP REF [REF...]"""
import json, sys
from pathlib import Path
g = json.load(open(Path(__file__).resolve().parents[2] / "gen" / "out" / "exp" / sys.argv[1] / "geom_r2.json"))
for ref in sys.argv[2:]:
    for p in sorted([p for p in g["pads"] if p["ref"] == ref], key=lambda p: (len(p["num"]), p["num"])):
        b = p["box"]
        print(f"{ref}.{p['num']:3s} {p['net'].split('/')[-1]:10s} c({p['c'][0]:.3f},{p['c'][1]:.3f}) box[{b[0]:.3f},{b[1]:.3f},{b[2]:.3f},{b[3]:.3f}] {''.join(l[0] for l in p['layers'])}")
