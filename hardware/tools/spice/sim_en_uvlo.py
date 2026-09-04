#!/usr/bin/env python
"""
AP63205 EN-pin programmable UVLO (R5 VIN->EN, R6 EN->GND).

EN pin model (datasheet 'Enable and Adjustable UVLO'):
  * 1.5 uA pull-up current into EN, always present
  * additional 4 uA hysteresis pull-up into EN only while the regulator is ON
  * EN rising threshold 1.18 V, falling threshold 1.10 V

Method:
  1. two linear DC sweeps of VIN (1.5 uA and 5.5 uA into EN) -> V_IN(on)/V_IN(off)
  2. a transient VIN triangle ramp with a hysteretic voltage-controlled switch
     (SW model vt=1.14 vh=0.04 -> on above 1.18 V, off below 1.10 V) that adds the
     4 uA source, as an independent confirmation of the on/off points.

Cases: (a) R5=470k / R6=100k (current design), (b) E96 pair for V_on~6.8 V, V_off~6.0 V
from datasheet Eq.1/Eq.2.

Run:  ../.venv/bin/python sim_en_uvlo.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ngspice_shared import NgSpice  # noqa: E402

VEN_H, VEN_L = 1.18, 1.10
I1, I2 = 1.5e-6, 4.0e-6

E96 = [1.00, 1.02, 1.05, 1.07, 1.10, 1.13, 1.15, 1.18, 1.21, 1.24, 1.27, 1.30, 1.33, 1.37, 1.40, 1.43,
       1.47, 1.50, 1.54, 1.58, 1.62, 1.65, 1.69, 1.74, 1.78, 1.82, 1.87, 1.91, 1.96, 2.00, 2.05, 2.10,
       2.15, 2.21, 2.26, 2.32, 2.37, 2.43, 2.49, 2.55, 2.61, 2.67, 2.74, 2.80, 2.87, 2.94, 3.01, 3.09,
       3.16, 3.24, 3.32, 3.40, 3.48, 3.57, 3.65, 3.74, 3.83, 3.92, 4.02, 4.12, 4.22, 4.32, 4.42, 4.53,
       4.64, 4.75, 4.87, 4.99, 5.11, 5.23, 5.36, 5.49, 5.62, 5.76, 5.90, 6.04, 6.19, 6.34, 6.49, 6.65,
       6.81, 6.98, 7.15, 7.32, 7.50, 7.68, 7.87, 8.06, 8.25, 8.45, 8.66, 8.87, 9.09, 9.31, 9.53, 9.76]


def nearest_e96(r):
    dec = 10 ** np.floor(np.log10(r))
    cands = [m * dec for m in E96] + [E96[0] * dec * 10]
    return min(cands, key=lambda c: abs(np.log(c / r)))


def datasheet_rs(von, voff):
    r5 = (0.932 * von - voff) / 4.1e-6
    r6 = 1.1 * r5 / (voff - 1.1 + 5.5e-6 * r5)
    return r5, r6


def analytic(r5, r6):
    von = VEN_H + r5 * (VEN_H / r6 - I1)
    voff = VEN_L + r5 * (VEN_L / r6 - I1 - I2)
    return von, voff


def dc_thresholds(ng, r5, r6):
    out = []
    for ipu, vth in ((I1, VEN_H), (I1 + I2, VEN_L)):
        ng.load_netlist("""ap63205 en divider
vin vin 0 dc 0
r5 vin en %g
r6 en 0 %g
i1 0 en dc %g
.end""" % (r5, r6, ipu))
        ng.run("dc vin 0 20 0.01")
        vin = ng.vector("v(vin)")
        ven = ng.vector("v(en)")
        out.append(float(np.interp(vth, ven, vin)))  # v(en) is monotonic in vin
    return out


def tran_thresholds(ng, r5, r6):
    ng.load_netlist("""ap63205 en divider with hysteretic on-state current
vin vin 0 pwl(0 0 20m 20 40m 0)
r5 vin en %g
r6 en 0 %g
i1 0 en dc %g
* 4 uA hysteresis current, switched in only while regulator is ON
vaux aux 0 dc 1000
raux aux enx 250meg
s1 enx en en 0 swhys
.model swhys sw(vt=%g vh=%g ron=1 roff=1e15)
.end""" % (r5, r6, I1, (VEN_H + VEN_L) / 2, (VEN_H - VEN_L) / 2))
    ng.run("tran 2u 40m")
    t = ng.vector("time")
    vin = ng.vector("v(vin)")
    on = ng.vector("v(enx)") < 10.0     # switch closed -> enx ~ en
    idx_on = np.argmax(on)              # first ON sample
    idx_off = idx_on + np.argmax(~on[idx_on:])
    return float(vin[idx_on]), float(vin[idx_off]), bool(on.any()), bool((~on[idx_on:]).any())


def main():
    ng = NgSpice()
    cases = [("(a) Grok design", 470e3, 100e3), ("(b) v1.0 as drawn", 100e3, 20e3), ("(c) v1.1 as built", 100e3, 27e3)]
    r5c, r6c = datasheet_rs(6.8, 6.0)
    r5e, r6e = nearest_e96(r5c), nearest_e96(r6c)
    cases.append(("(b) E96 for 6.8/6.0 V", r5e, r6e))

    print("=" * 84)
    print("AP63205 EN UVLO  (I_pu=1.5uA always, +4uA when ON; VEN_H=1.18 V, VEN_L=1.10 V)")
    print("=" * 84)
    print("Datasheet Eq.1/Eq.2 for VON=6.8 V, VOFF=6.0 V: R5=%.1fk  R6=%.2fk  -> E96: R5=%.1fk R6=%.2fk"
          % (r5c / 1e3, r6c / 1e3, r5e / 1e3, r6e / 1e3))
    print()
    print("%-24s %8s %8s | %9s %9s | %9s %9s | %9s %9s | %s" % (
        "case", "R5[k]", "R6[k]", "on(calc)", "off(calc)", "on(DC)", "off(DC)", "on(tran)", "off(tran)", "naive 1.18*(R5+R6)/R6"))
    for name, r5, r6 in cases:
        von_a, voff_a = analytic(r5, r6)
        von_dc, voff_dc = dc_thresholds(ng, r5, r6)
        von_t, voff_t, ok_on, ok_off = tran_thresholds(ng, r5, r6)
        print("%-24s %8.1f %8.2f | %9.3f %9.3f | %9.3f %9.3f | %9.3f %9.3f | %.3f V" % (
            name, r5 / 1e3, r6 / 1e3, von_a, voff_a, von_dc, voff_dc,
            von_t if ok_on else float("nan"), voff_t if ok_off else float("nan"),
            VEN_H * (r5 + r6) / r6))
    print()
    print("Notes: 'naive' ignores the EN pull-up currents (the '~6.7 V floor' figure in PARTS.md).")
    print("       tran values are quantised by the 2 us step on a 1 V/ms ramp (+/-2 mV).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
