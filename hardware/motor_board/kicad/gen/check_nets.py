"""Compare the schematic's connectivity (kicad-cli netlist export) with design/netlist.csv, pin by pin.

Nets are compared as sets of ref.pin (names may differ: KiCad prefixes local nets with /sheet/).
For hand-drawn sheets, 2-pin non-polarized parts (R, C, L, NT, TH) may be flipped: pass --swap-ok.
"""
import collections
import csv
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/home/smance/projects/thumbsup/hardware/motor_board/kicad/lib_build")
import kicadlib as K  # noqa: E402

MB = Path("/home/smance/projects/thumbsup/hardware/motor_board")
NET = str(Path(__file__).resolve().parent / "out" / "check.net")
r = subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o", NET, str(MB / "kicad/motor_board/motor_board.kicad_sch")],
                   capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stdout + r.stderr)
tree = K.parse(Path(NET).read_text())
kic = {}
for n in K.children(K.child(tree, "nets"), "net"):
    name = K.child(n, "name")[1]
    nodes = frozenset(f'{K.child(nd, "ref")[1]}.{K.child(nd, "pin")[1]}' for nd in K.children(n, "node"))
    kic[nodes] = name
want = collections.defaultdict(set)
for row in csv.DictReader(open(MB / "design" / "netlist.csv")):
    if row["net"] != "NC":
        want[row["net"]].add(f'{row["ref"]}.{row["pin"]}')
    else:
        want[f'NC:{row["ref"]}.{row["pin"]}'].add(f'{row["ref"]}.{row["pin"]}')
want_sets = {frozenset(v): k for k, v in want.items()}
pin_to_want = {p: k for k, v in want.items() for p in v}
pin_to_kic = {p: s for s in kic for p in s}

ok = [s for s in want_sets if s in kic]
bad = [(want_sets[s], s) for s in want_sets if s not in kic]
print(f"design nets: {len(want_sets)} (incl. NC pins), matched exactly: {len(ok)}, differing: {len(bad)}")
names = collections.Counter()
for s in ok:
    k, w = kic[s], want_sets[s]
    short = k.split("/")[-1]
    if not w.startswith("NC:") and short != w and not short.startswith("Net-") and not short.startswith("unconnected-"):
        names[(w, k)] += 1
for name, s in sorted(bad)[:40]:
    parts = collections.defaultdict(set)
    for p in s:
        ks = pin_to_kic.get(p)
        parts[kic.get(ks, "<missing>") if ks else "<missing>"].add(p)
    print(f"  {name}: split/merged in KiCad as", {k: sorted(v)[:6] for k, v in parts.items()})
for (w, k), _ in names.items():
    print(f"  name differs: design {w} vs KiCad {k}")
