"""Block-to-block signal-net counts from design/netlist.csv (rails excluded), and the MCU's nets per block.
python3 blocknets.py"""
import collections
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MB = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "gen"))
from blocks import BLOCKS  # noqa: E402

RAILS = {"GND", "+3V3", "+3V3A", "+5V", "VBAT", "NC"}
SHORT = {"Power switch (LM74502 + back-to-back FETs)": "PSW", "Bus: shunt, TVS, bulk, bleeder": "BUS",
         "Pack monitor (INA239)": "INA", "Cell monitor (BQ76907)": "BMS", "Weapon nFAULT": "WNF",
         "Gate driver (DRV8323RH)": "U2", "5 V buck (in U2)": "BUCK", "Weapon bridge": "BRIDGE",
         "Phase dividers (top)": "PDIV", "Weapon interlock (AND)": "AND", "Dynamic ARM": "ARM",
         "Drive L (DRV8316C)": "U3", "Drive R (DRV8316C)": "U4", "DRV_OFF pull-up (shared)": "DRVOFF",
         "MCU (STM32G474)": "MCU", "3.3 V LDO": "LDO", "Header to compute board": "J1", "Test pads": "TP",
         "Weapon analog (phase, NTC, pack)": "WANA", "Drive CSA filters": "CSAF", "Power LED, mounting holes": "LED",
         "Sensor L (J2)": "SENL", "Sensor R (J3)": "SENR"}
blk = {}
for s, bl in BLOCKS.items():
    for bn, refs in bl.items():
        name = SHORT.get(bn, bn)
        if bn == "VM filter":
            name = "VML" if s == "drive_left" else "VMR"
        if bn == "Motor wires":
            name = "JL" if s == "drive_left" else "JR"
        for r in refs:
            blk[r] = name
nets = collections.defaultdict(set)
pins = collections.defaultdict(list)
for r in csv.DictReader(open(MB / "design" / "netlist.csv")):
    if r["net"] in RAILS or r["net"].startswith("unconnected"):
        continue
    nets[r["net"]].add(blk[r["ref"]])
    pins[r["net"]].append(f'{r["ref"]}.{r["pin"]}')
pair = collections.Counter()
pair_nets = collections.defaultdict(list)
for n, bs in (nets.items() if __name__ == "__main__" else ()):
    bs = sorted(bs)
    for i in range(len(bs)):
        for j in range(i + 1, len(bs)):
            pair[(bs[i], bs[j])] += 1
            pair_nets[(bs[i], bs[j])].append(n)
for (a, b), k in (pair.most_common() if __name__ == "__main__" else ()):
    print(f"{a:7s} {b:7s} {k:3d}  " + " ".join(sorted(pair_nets[(a, b)])))
