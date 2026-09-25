"""For the given nets: every pad (ref.num, layer, xy) and every via already on the net (from the last build),
so a bus can be planned from its real end points.   python3 net_ends.py NET [NET ...]"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
g = json.load(open(HERE / "out" / "route" / "geom.json"))
routes = json.load(open(HERE / "out" / "route" / "routes.json"))
for net in sys.argv[1:]:
    pads = [f"{p['ref']}.{p['num']}{p['layers'][0][0]}({p['c'][0]:.2f},{p['c'][1]:.2f})" for p in g["pads"] if p["net"] == net]
    vias = [f"({v['c'][0]:.2f},{v['c'][1]:.2f})" for r in routes if r.get("ok") for v in r["vias"] if v["net"] == net]
    vias += [f"({v['c'][0]:.2f},{v['c'][1]:.2f})*" for v in g["vias"] if v["net"] == net]
    print(f"{net:16s} pads {' '.join(pads)}\n{'':16s} vias {' '.join(vias)}")
