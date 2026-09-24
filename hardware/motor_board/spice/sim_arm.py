#!/usr/bin/env python3
"""Dynamic ARM charge pump: arm level, arm time, disarm time, pause tolerance.

Circuit (design/motor_board.py): J1.19 W_ARM_CLK (R18 100k to GND) -> C15 470 nF -> D9 BAT54S
(pin 1 A1 = GND, pin 3 common = ARM_AC, pin 2 K2 = W_ARM) -> W_ARM with C16 2.2 uF and R41 47k ->
U14 74LVC1G17 Schmitt buffer (VT+ <= 2.0 V at 3.0 V VCC, ~2.15 V at 3.3 V; VT- 0.80-1.33 V).

The compute board drives W_ARM_CLK from a 3.3 V GPIO (50 ohm source).  D9 hot leakage is modelled
as a parallel resistance per diode (BAT54 IR ~25 uA at 3 V / 85 C -> ~130 kOhm).

Reports, per toggle rate and temperature: the armed W_ARM range, rising edges and time to cross
VT+ (2.15 V), time from the last edge until W_ARM < 1.33 V (earliest disarm) and < 0.8 V (latest
disarm) for the clock stuck low and stuck high, and the longest pause the armed level survives.

Run: ../../tools/.venv/bin/python sim_arm.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "spice"))
from ngspice_shared import NgSpice  # noqa: E402

VT_POS, VT_NEG_HI, VT_NEG_LO = 2.15, 1.33, 0.80
T_STOP = 0.4


def netlist(f, stuck, rleak):
    per = 1.0 / f
    return f"""arm
vclk clk0 0 pulse(0 3.3 0 1u 1u {per/2} {per})
vst st 0 {stuck}
bsel clk 0 v = time < {T_STOP} ? v(clk0) : v(st)
rsrc clk w 50
r18 w 0 100k
c15 w ac 470n
d9a 0 ac dbat
rla ac 0 {rleak}
d9b ac arm dbat
rlb arm ac {rleak}
.model dbat d(is=2e-7 n=1.0 rs=2 cjo=10p)
c16 arm 0 2.2u
r41 arm 0 47k
.options method=gear
.tran 5u {T_STOP + 0.5} 0 {max(per / 40, 5e-6)}
.end
"""


def cross_below(t, v, t0, level):
    m = t > t0
    idx = np.argmax(v[m] < level)
    return (t[m][idx] - t0) if (v[m] < level).any() else float("nan")


def _sim(job):
    f, stuck, rleak = job
    ng = NgSpice()
    ng.load_netlist(netlist(f, stuck, rleak))
    ng.run("run")
    return job, ng.vector("time"), ng.vector("v(arm)")


def main():
    import multiprocessing as mp
    jobs = [(f, stuck, rleak) for rleak in ("1e12", "130k") for f in (250, 500, 1000, 10000) for stuck in (0.0, 3.3)]
    with mp.get_context("spawn").Pool(min(len(jobs), mp.cpu_count())) as pool:
        res = {job: (t, v) for job, t, v in pool.map(_sim, jobs, chunksize=1)}
    print("Dynamic ARM (C15 470n, D9 BAT54S, C16 2.2u, R41 47k, U14 74LVC1G17)")
    print(f"{'case':30s} {'armed W_ARM':>13s} {'arm':>16s} {'disarm, stuck low':>20s} {'disarm, stuck high':>20s}")
    for rleak, tag in (("1e12", "25 C"), ("130k", "85 C")):
        for f in (250, 500, 1000, 10000):
            t, v = res[(f, 0.0, rleak)]
            on = v[(t > T_STOP - 0.1) & (t < T_STOP)]
            t_arm = t[np.argmax(v > VT_POS)] if (v > VT_POS).any() else float("nan")
            edges = int(np.ceil(t_arm * f)) if t_arm == t_arm else -1
            dl = [cross_below(t, v, T_STOP, lv) * 1000 for lv in (VT_NEG_HI, VT_NEG_LO)]
            th, vh = res[(f, 3.3, rleak)]
            dh = [cross_below(th, vh, T_STOP, lv) * 1000 for lv in (VT_NEG_HI, VT_NEG_LO)]
            arm = f"{t_arm*1000:5.1f} ms/{edges:2d} edges" if edges > 0 else "never"
            print(f"{tag} {f:6d} Hz {'':16s} {on.min():5.2f}-{on.max():4.2f} V {arm:>16s} "
                  f"{dl[0]:7.0f}-{dl[1]:4.0f} ms {'':6s}{dh[0]:7.0f}-{dh[1]:4.0f} ms")
    print(f"\nPause tolerance: a gap in the toggling is survived while W_ARM stays above VT- (max {VT_NEG_HI} V):"
          " equal to the 'disarm' columns' first number, measured from the last edge.")


if __name__ == "__main__":
    main()
