"""Push the design's pin -> net map into a board's pads (after a pin swap), in place:
    /usr/bin/python3 setpadnets.py <board.kicad_pcb> [...] [--refs U1,J1]
Reads design/netlist.csv (written by design/motor_board.py); default refs: U1.  Only pads whose net differs change; a
pad's old copper stays (it now belongs to the old net, so DRC flags any track left on a moved pin).  Prints each change."""
import csv
import sys
from pathlib import Path

import pcbnew

MB = Path(__file__).resolve().parents[2]
refs = ["U1"]
args = sys.argv[1:]
if "--refs" in args:
    i = args.index("--refs")
    refs = args[i + 1].split(",")
    args = args[:i] + args[i + 2:]
PIN = {}
for row in csv.DictReader(open(MB / "design" / "netlist.csv")):
    if row["ref"] in refs:
        PIN[(row["ref"], row["pin"])] = row["net"]

for path in args:
    b = pcbnew.LoadBoard(path)
    nets = {n.GetNetname().split("/")[-1]: n for n in b.GetNetsByName().values() if n.GetNetname()}
    for ref in refs:
        fp = b.FindFootprintByReference(ref)
        for p in fp.Pads():
            want = PIN.get((ref, p.GetNumber()))
            if not want or want == "NC" or want not in nets:
                continue
            if p.GetNetname().split("/")[-1] != want:
                print(f"{Path(path).name}: {ref}.{p.GetNumber()} {p.GetNetname()} -> {nets[want].GetNetname()}")
                p.SetNet(nets[want])
    b.Save(path)
