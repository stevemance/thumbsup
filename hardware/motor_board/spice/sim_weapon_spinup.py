#!/usr/bin/env python3
"""Weapon spin-up: battery, bulk capacitor, current-limited FOC drive, 2822 motor, drum.

Electro-mechanical model in SPICE (the mechanical side as its electrical analogue:
drum inertia = capacitor, speed = node voltage in rad/s):

  pack   4S, open-circuit 15.6 V (3.9 V/cell under load), internal 4 x 15 mOhm + 10 mOhm lead
  board  470 uF polymer bulk; logic + drives draw a constant 2.5 A (both drives at ~1 A, logic)
  motor  Repeat 2822 Mk3 1800 KV: Kt = 60/(2*pi*1800) = 5.31 mNm/A, R = 0.10 ohm
         (estimate; the vendor lists none), J rotor 3e-6 kg m2
  drum   J 1.8e-5 kg m2 (40 mm PLA drum, ~66 g, from the chassis 3MF)
  drive  FOC in DC-equivalent form: phase current = min(ILIM, (0.95 Vbus - Ke w)/R), so it is
         current-limited at low speed and voltage-limited at high speed; bus current from
         power balance at 97 % inverter efficiency.  Windage/iron loss: 2e-9 * w^2 N m.

Reports time to 90 % speed, peak battery current, minimum bus voltage (brown-out margin for
the 5 V buck, which needs about 6 V in), and the kinetic energy stored, for 15 / 20 / 25 A.

Run: python3 sim_weapon_spinup.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "spice"))
from ngspice_shared import NgSpice  # noqa: E402

KV = 1800.0
KT = 60.0 / (2 * np.pi * KV)
R_MOTOR = 0.10
J = 1.8e-5 + 3e-6
VOC = 15.6
R_PACK = 4 * 0.015 + 0.010


def netlist(ilim):
    return f"""weapon spin-up
vpack p 0 {VOC}
rpack p vbus {R_PACK}
cbulk vbus nb 470u ic={VOC - 2.5 * R_PACK}
rbulk nb 0 0.02
iaux vbus 0 2.5
* motor phase current (DC equivalent), current- or voltage-limited
bi i 0 v = max(0, min({ilim}, (0.95*v(vbus) - {KT}*v(w)) / {R_MOTOR}))
* bus current from power balance
bbus vbus 0 i = ({KT}*v(w)*v(i) + v(i)*v(i)*{R_MOTOR}) / (0.97*max(v(vbus), 1))
* mechanics: J dw/dt = Kt*i - 2e-9*w^2   (capacitor J, node voltage = w in rad/s)
bt 0 w i = {KT}*v(i) - 2e-9*v(w)*v(w)
cj w 0 {J} ic=0
.tran 1m 2.5 0 1m uic
.end
"""


def run(ilim):
    ng = NgSpice()
    ng.load_netlist(netlist(ilim))
    ng.run("run")
    t = ng.vector("time")
    w = ng.vector("v(w)")
    vbus = ng.vector("v(vbus)")
    ib = (VOC - vbus) / R_PACK
    k = t > 2e-3                          # skip the first 2 ms (initial-condition settling)
    ib, vbus = ib[k], vbus[k]
    wf = w[-1]
    t90 = t[np.argmax(w >= 0.9 * wf)]
    return dict(rpm=wf * 60 / (2 * np.pi), t90=t90, ipk=ib.max(), vmin=vbus.min(), e=0.5 * 1.8e-5 * wf ** 2)


def main():
    print(f"4S pack ({VOC} V under load, {R_PACK*1000:.0f} mOhm), 2822 {KV:.0f} KV, drum J 1.8e-5 kg m2")
    print(f"{'I limit':>8s} {'final rpm':>10s} {'t90':>7s} {'drum energy':>12s} {'pack I peak':>12s} {'min VBUS':>9s}")
    for ilim in (15.0, 20.0, 25.0):
        r = run(ilim)
        tip = r["rpm"] / 60 * np.pi * 0.040
        print(f"{ilim:7.0f}A {r['rpm']:9.0f} {r['t90']:6.2f}s {r['e']:9.1f} J {r['ipk']:10.1f} A {r['vmin']:8.2f} V   tip {tip:4.1f} m/s")


if __name__ == "__main__":
    main()
