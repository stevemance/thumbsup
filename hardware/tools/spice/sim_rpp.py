#!/usr/bin/env python
"""
Reverse-polarity-protection P-FET (AP40P05 class) orientation check.

Compares
  A) "as-designed" (tools/gen_skidl.py pack_input): battery+ -> FET SOURCE, load <- FET DRAIN
  B) "textbook":                                    battery+ -> FET DRAIN,  load <- FET SOURCE
with a DC sweep of the battery from -13 V to +13 V.

FET: generic level-1 PMOS, Vto = -1.5 V, KP = 6 A/V^2 (W/L = 1 -> Rds(on) ~ 20 mohm at
Vgs = -10 V), explicit body diode D from drain (anode) to source (cathode).
Gate network: Rpd 100k gate->GND, 12 V zener anode=gate / cathode=source.
Optionally Rgs 100k gate<->source (the schematic has it; --rgs 100k).
Load: 100 ohm output->GND.

Run:  ../.venv/bin/python sim_rpp.py [--rgs 100k]
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ngspice_shared import NgSpice  # noqa: E402

MODELS = """
* generic 40 V P-MOSFET, Vto=-1.5 V, Rds(on)~20 mohm at Vgs=-10 V (level 1, W/L=1)
.model PFET PMOS(level=1 vto=-1.5 kp=6 lambda=0 is=1e-32 cbd=0 cbs=0)
* explicit body diode (anode = drain, cathode = source)
.model DBODY D(is=1e-12 n=1 rs=0.01)
* 12 V zener (MMSZ5242B class), anode = gate, cathode = source
.model DZ D(is=1e-14 n=1 rs=1 bv=12 ibv=5e-3)
"""


def netlist(orientation, rgs):
    lines = ["rpp orientation %s" % orientation,
             "vbat bat 0 dc 0",
             "rpd g 0 100k",
             "rload out lds 100",
             "vsense lds 0 dc 0"]
    if orientation == "A":
        # battery on SOURCE, load on DRAIN.  M D G S B
        lines += ["m1 out g bat bat pfet",
                  "dbody out bat dbody",   # anode=drain(out) cathode=source(bat)
                  "dz g bat dz"]           # anode=gate  cathode=source(bat)
        src = "bat"
    else:
        # battery on DRAIN, load on SOURCE.
        lines += ["m1 bat g out out pfet",
                  "dbody bat out dbody",   # anode=drain(bat) cathode=source(out)
                  "dz g out dz"]           # anode=gate  cathode=source(out)
        src = "out"
    if rgs:
        lines.append("rgs g %s %s" % (src, rgs))
    lines.append(MODELS)
    lines.append(".end")
    return "\n".join(lines), src


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rgs", default=None, help="optional gate-source resistor, e.g. 100k")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    ng = NgSpice(verbose=args.verbose)
    results = {}
    for orient, label in (("A", "as-designed: bat+ -> SOURCE, load <- DRAIN"),
                          ("B", "textbook:    bat+ -> DRAIN,  load <- SOURCE")):
        nl, src = netlist(orient, args.rgs)
        ng.load_netlist(nl)
        ng.run("dc vbat -13 13 0.05")
        vb = ng.vector("v(bat)")
        vout = ng.vector("v(out)")
        vg = ng.vector("v(g)")
        vsrc = ng.vector("v(%s)" % src)
        iload = ng.vector("vsense#branch")
        vgs = vg - vsrc
        f = lambda arr, x: float(np.interp(x, vb, arr))
        r = {}
        for x in (-12.6, 9.0, 12.6):
            r[x] = dict(vout=f(vout, x), iload=f(iload, x), vgs=f(vgs, x))
        results[orient] = (label, r)

    print("=" * 78)
    print("RPP P-FET orientation sweep  (Rpd=100k, zener 12 V G-S, load 100 ohm, Rgs=%s)"
          % (args.rgs or "none"))
    print("=" * 78)
    print("%-45s %8s %10s %10s %8s" % ("orientation", "Vbat", "Vout[V]", "Iload[mA]", "Vgs[V]"))
    for orient, (label, r) in results.items():
        for x in (12.6, 9.0, -12.6):
            d = r[x]
            print("%-45s %+8.1f %10.3f %10.2f %+8.2f"
                  % (label if x == 12.6 else "", x, d["vout"], d["iload"] * 1e3, d["vgs"]))
        print()

    a, b = results["A"][1], results["B"][1]
    print("Conclusion:")
    for orient, r in (("A", a), ("B", b)):
        blocks = abs(r[-12.6]["vout"]) < 0.5 and abs(r[-12.6]["iload"]) < 1e-3
        print("  %s: at -12.6 V the load sees %.2f V / %.1f mA -> %s"
              % (orient, r[-12.6]["vout"], r[-12.6]["iload"] * 1e3,
                 "BLOCKS reverse polarity" if blocks else "DOES NOT block (body diode conducts)"))
    if abs(b[-12.6]["vout"]) < 0.5 <= abs(a[-12.6]["vout"]):
        print("  -> Orientation B (battery on DRAIN, load on SOURCE) is correct.")
        print("     Vgs (B) at +9.0 V = %+.2f V, at +12.6 V = %+.2f V"
              % (b[9.0]["vgs"], b[12.6]["vgs"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
