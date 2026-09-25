"""Per-net routing report for the critical nets: track length per layer, vias, widths.
/usr/bin/python3 net_report.py [NET ...]   (default: the critical list below)"""
import collections
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
b = pcbnew.LoadBoard(str(HERE.parent / "motor_board" / "motor_board.kicad_pcb"))
t = pcbnew.ToMM
CRIT = ["W_GHA", "W_GHB", "W_GHC", "W_GLA", "W_GLB", "W_GLC", "W_A", "W_B", "W_C", "W_SLA", "W_SLB", "W_SLC",
        "W_SNA", "W_SNB", "W_SNC", "PSW_G", "PSW_S", "L_VM", "R_VM", "L_A", "L_B", "L_C", "R_A", "R_B", "R_C",
        "+5V", "+3V3", "BUCK_SW", "BUCK_FB", "INA_INP", "INA_INN", "DRV_OFF", "W_ARM_CLK", "MB_TX"]
want = sys.argv[1:] or CRIT
per = collections.defaultdict(lambda: dict(len=collections.Counter(), vias=0, widths=set()))
for tr in b.GetTracks():
    n = tr.GetNetname().split("/")[-1]
    if n not in want:
        continue
    if tr.GetClass() == "PCB_VIA":
        per[n]["vias"] += 1
    else:
        per[n]["len"][b.GetLayerName(tr.GetLayer())] += t(tr.GetLength())
        per[n]["widths"].add(round(t(tr.GetWidth()), 3))
for n in want:
    d = per.get(n)
    if not d:
        print(f"{n:10s} (no tracks or vias)")
        continue
    lens = ", ".join(f"{k} {v:.1f}" for k, v in sorted(d["len"].items()))
    print(f"{n:10s} total {sum(d['len'].values()):6.1f} mm  [{lens}]  vias {d['vias']}  widths {sorted(d['widths'])}")
