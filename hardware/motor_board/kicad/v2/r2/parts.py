"""List parts (block, side, position, nets) from out/placement.csv + design/netlist.csv.
    python3 r2/parts.py [BLOCK ...] | [-r REF ...]"""
import collections
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
MB = V2.parents[1]
sys.path.insert(0, str(V2))
sys.path.insert(0, str(V2.parent / "gen"))
from blocknets import blk  # noqa: E402

pl = {r["ref"]: r for r in csv.DictReader(open(V2 / "out" / "placement.csv"))}
nets = collections.defaultdict(list)
for r in csv.DictReader(open(MB / "design" / "netlist.csv")):
    nets[r["ref"]].append(f"{r['pin']}:{r['net']}")
args = sys.argv[1:]
refs = set(args[1:]) if args[:1] == ["-r"] else None
want = set(args) if args and refs is None else None
for ref in sorted(pl, key=lambda r: (blk.get(r, "?"), r)):
    b = blk.get(ref, "?")
    if (want and b not in want) or (refs and ref not in refs):
        continue
    p = pl[ref]
    print(f"{b:6s} {ref:6s} {p['side'][0]} ({p['x']},{p['y']}) r{p['rot']} {p['value'][:12]:12s} " + " ".join(nets[ref]))
