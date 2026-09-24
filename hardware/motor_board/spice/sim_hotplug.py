#!/usr/bin/env python3
"""Battery hot-plug transient at the drive-driver VM pins.

Why: the DRV8316 (both drive channels) has a 40 V absolute-maximum on VM and a 4 V/us
maximum VM ramp rate (SLVSF16B 7.1).  Plugging a 4S pack (16.8 V full) into a board
whose input is a low-ESR capacitor bank through the battery lead is an undamped LC
step: the classic result is up to 2x overshoot (33.6 V) and ramps of tens of V/us.

Model (all values per-case below):
  pack 16.8 V, 4 x 12 mOhm internal R -> Q7 body diode in the return, RS4 1 mOhm -> lead (2 x 120 mm of 20 AWG, ~150 nH, 8 mOhm)
  -> board VBAT: TVS SMBJ20A (BV ~22.2-24.5 V, Rdyn ~0.5 ohm from the 32.4 V @ 18.5 A clamp),
  bulk C1 470 uF polymer (ESR 20 mOhm, ESL 3 nH), 4 x 10 uF MLCC at the bridges (derated
  to 5 uF at 16 V, ESR 5 mOhm), each DRV8316 VM pin behind 5 nH of board trace with its
  own 10 uF + 2 x 100 nF.
  The contact closure is a 16.8 V step with 5 ns rise (real XT30 closures bounce; the
  first closure is the worst case).

Reports the peak VM at the DRV8316 and the maximum dV/dt, with and without the polymer
bulk capacitor, and with the TVS removed.

Run: python3 sim_hotplug.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "spice"))
from ngspice_shared import NgSpice  # noqa: E402

VPACK = 16.8


def netlist(bulk=True, tvs=True, lead_nh=150.0, rbat=0.048):
    return f"""hotplug
vpack vp bneg pwl(0 0 1u 0 1.005u {VPACK})
* Q7 reverse-polarity FET: its body diode carries the plug-in surge (the gate takes ~0.4 ms to charge)
drpp 0 bneg dbody
.model dbody d(is=1e-9 n=1.3 rs=2m)
rbat vp b1 {rbat}
llead b1 b2 {lead_nh}n
rlead b2 bp 0.008
* pack shunt RS4
rs4 bp vbat 0.001
* TVS SMBJ20A
{"dtvs 0 vbat dtvs" if tvs else "* no TVS"}
.model dtvs d(bv=23.3 ibv=1m rs=0.49 cjo=1n)
* bulk polymer
{"cb vbat nb1 470u" if bulk else "* no bulk"}
{"rb nb1 nb2 0.020" if bulk else ""}
{"lb nb2 0 3n" if bulk else ""}
* bridge MLCCs (4 x 10 uF derated to 5 uF)
cm vbat nm1 20u
rm nm1 nm2 0.00125
lm nm2 0 0.5n
* trace to the DRV8316 VM pins and its local decoupling
lt vbat vm 5n
rt vm vm2 0.005
cvm vm2 nv1 10u
rv nv1 0 0.005
cvhf vm2 0 200n
.tran 2n 600u 0 20n
.end
"""


def run(**kw):
    ng = NgSpice()
    ng.load_netlist(netlist(**kw))
    ng.run("run")
    t = ng.vector("time")
    v = ng.vector("v(vm2)")
    dvdt = np.diff(v) / np.diff(t)
    return v.max(), dvdt.max() / 1e6, v[-1]


def main():
    print(f"4S pack {VPACK} V step into the board through ~150 nH of battery lead")
    print(f"{'case':44s} {'VM peak':>8s} {'max dV/dt':>11s} {'final':>7s}")
    cases = [
        ("470 uF polymer + MLCC + TVS (as designed)", dict()),
        ("no polymer bulk (MLCC only) + TVS", dict(bulk=False)),
        ("no polymer bulk, no TVS", dict(bulk=False, tvs=False)),
        ("as designed, 300 nH lead (long pigtail)", dict(lead_nh=300.0)),
        ("as designed, stiff pack (4 x 5 mOhm)", dict(rbat=0.020)),
        ("no polymer bulk, stiff pack (4 x 5 mOhm)", dict(bulk=False, rbat=0.020)),
    ]
    for name, kw in cases:
        vpk, dvdt, vf = run(**kw)
        flag = []
        if vpk > 40:
            flag.append("EXCEEDS 40 V abs max")
        elif vpk > 35:
            flag.append("above 35 V operating")
        if dvdt > 4:
            flag.append("EXCEEDS 4 V/us ramp")
        print(f"{name:44s} {vpk:7.1f}V {dvdt:9.2f}V/us {vf:6.1f}V  {'; '.join(flag)}")


if __name__ == "__main__":
    main()
