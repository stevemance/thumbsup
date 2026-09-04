#!/usr/bin/env python
"""
FD6288-style bootstrap supply droop at 24 kHz / 95 % duty.

VCC = 9 V (sagged 3S), Rboot = 2.2 ohm, 1N5819 Schottky, Cboot = 100 nF (and 1 uF).
High-side gate = 4 nF (HYG015N04LS1C2 Ciss ~ 4050 pF) charged from VB via a 2 ohm
switch when HIN is high and discharged to VS when low.  VS is an ideal 0/9 V pulse in
phase with HIN.  Floating-supply quiescent current IQBS = 270 uA (FD6288Q max) from VB to VS.

Reports VBS at the start and end of the high-side on-time in the last simulated cycle
and compares with the FD6288Q VBS UVLO (VBSUV- 4.3 V typ / 4.7 V max, VBSUV+ 4.6 typ / 5.0 max).

Run:  ../.venv/bin/python sim_bootstrap.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ngspice_shared import NgSpice  # noqa: E402

VCC = 9.0
VBUS = 9.0
F = 24e3
DUTY = 0.95
T = 1 / F
TON = DUTY * T
IQBS = 270e-6
VBSUV_FALL_MAX = 4.7
VBSUV_FALL_TYP = 4.3
VBSUV_RISE_MAX = 5.0


def netlist(cboot, cgate=4e-9, rboot=2.2, td=1e-6):
    return """fd6288 bootstrap droop
vcc vcc 0 dc %(vcc)g
rboot vcc rb %(rboot)g
dboot rb vb d1n5819
cboot vb vs %(cboot)g
iq vb vs dc %(iq)g
* switch node: 0 V while low side on, VBUS while high side on
vvs vs 0 pulse(0 %(vbus)g %(td)g 50n 50n %(ton)g %(T)g)
* HIN control
vctl ctl 0 pulse(0 1 %(td)g 10n 10n %(ton)g %(T)g)
vctln ctln 0 pulse(1 0 %(td)g 10n 10n %(ton)g %(T)g)
* high-side gate capacitance, charged from VB when HIN high, discharged to VS when low
cg hg vs %(cg)g
sup vb hg ctl 0 swg
sdn hg vs ctln 0 swg
.model swg sw(vt=0.5 vh=0.1 ron=2 roff=1e9)
* 1N5819 Schottky (Vf ~0.3-0.4 V)
.model d1n5819 d(is=31.7u n=1.373 rs=0.051 cjo=110p m=0.35 vj=0.8 bv=40 ibv=1e-4)
.end""" % dict(vcc=VCC, rboot=rboot, cboot=cboot, iq=IQBS, vbus=VBUS, td=td,
               ton=TON, T=T, cg=cgate)


def run_case(ng, cboot, ncycles):
    ng.load_netlist(netlist(cboot))
    tstop = 1e-6 + ncycles * T
    ng.run("tran 10n %g 0 20n" % tstop)
    t = ng.vector("time")
    vbs = ng.vector("v(vb)") - ng.vector("v(vs)")
    vhg = ng.vector("v(hg)") - ng.vector("v(vs)")
    # last full cycle
    t0 = 1e-6 + (ncycles - 1) * T
    on = (t >= t0 + 0.2e-6) & (t <= t0 + TON - 0.2e-6)
    vbs_start = float(np.interp(t0 + 0.3e-6, t, vbs))
    vbs_end = float(np.interp(t0 + TON - 0.05e-6, t, vbs))
    vbs_min = float(vbs[on].min())
    vbs_pre = float(np.interp(t0 - 0.05e-6, t, vbs))       # just before HS turns on
    vgs_on = float(np.interp(t0 + TON - 0.05e-6, t, vhg))  # gate drive at end of on-time
    # also first cycle (worst case if the cap was never refreshed fully)
    return dict(vbs_pre=vbs_pre, vbs_start=vbs_start, vbs_end=vbs_end, vbs_min=vbs_min,
                vgs_end=vgs_on, droop=vbs_pre - vbs_end)


def main():
    ng = NgSpice()
    print("=" * 84)
    print("FD6288 bootstrap: VCC=%.1f V, Rboot=2.2 ohm, 1N5819, Cgate=4 nF, IQBS=%d uA, %g kHz, %.0f%% duty (t_on=%.1f us)"
          % (VCC, IQBS * 1e6, F / 1e3, DUTY * 100, TON * 1e6))
    print("=" * 84)
    print("%-10s %10s %10s %10s %10s %10s %10s | %s" % (
        "Cboot", "VBS pre[V]", "VBS t=0+", "VBS end", "droop[V]", "VBS min", "Vgs end", "margin to VBSUV- max 4.7 V / typ 4.3 V"))
    for cboot, ncyc in ((100e-9, 40), (1e-6, 200)):
        r = run_case(ng, cboot, ncyc)
        print("%-10s %10.3f %10.3f %10.3f %10.3f %10.3f %10.3f | %+.2f V / %+.2f V %s" % (
            "%g nF" % (cboot * 1e9), r["vbs_pre"], r["vbs_start"], r["vbs_end"], r["droop"],
            r["vbs_min"], r["vgs_end"],
            r["vbs_min"] - VBSUV_FALL_MAX, r["vbs_min"] - VBSUV_FALL_TYP,
            "OK" if r["vbs_min"] > VBSUV_FALL_MAX else "AT RISK"))
    print()
    print("Analytic check (100 nF): charge-share droop = VBS*Cg/(Cboot+Cg) = %.3f V; IQBS droop = %.3f V"
          % (8.6 * 4e-9 / 104e-9, IQBS * TON / 100e-9))
    print("VBS recharge window per cycle (low side on) = %.2f us; Rboot*Cboot = %.2f us (100 nF) / %.2f us (1 uF)"
          % ((T - TON) * 1e6, 2.2 * 100e-9 * 1e6, 2.2 * 1e-6 * 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
