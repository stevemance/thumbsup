#!/usr/bin/env python3
"""Battery hot-plug (power-switch closure) transient at the drive-driver VM pins.

Why: the DRV8316C (both drive channels) has a 40 V absolute maximum on VM and a 4 V/us
absolute-maximum VM ramp rate (SLVSH07 7.1).  Closing the power switch onto a board whose input
is a low-ESR capacitor bank is an undamped LC step; without a limiter the ramp is set by the bulk
capacitor's ESR x dI/dt, and a stiff pack, short leads or an aged/cold C1 push it past 4 V/us.

Rev K power entry (design/motor_board.py): BAT+ -> Q7 -> PSW_S -> Q8 -> VBAT_SW -> RS4 -> VBAT,
back-to-back high-side HYG015N04LS1C2 (Q7, drain at the pack, is the FET in its linear region during the
ramp; Q8 conducts backwards and blocks a reversed pack) driven by U13 LM74502 (SNOSDE5A): 60 uA gate source from a
charge pump at VS + ~12 V, 2.4 A gate sink when EN/UVLO falls, RG 4.7k -> D10 1N4148W (steering) -> Cdvdt 22 nF to GND
with R32 1M across it,
EN/UVLO divider 100k/15k + C18 100 nF from VS with the 3 uA EN sink (off < ~9.0 V typ; 'min UVLO' cases use EN falling 0.968 V so that, with the modelled 3 uA sink, the bus opens at
7.7 V = minimum threshold with 1 % resistors and no sink current: the worst case);
a hysteretic comparator (on above the rising threshold, off below the falling one) gates the 60 uA source and the 2 ohm sink, D4 12 V gate-source zener,
bus bleeder R15 6.8k.  GND is tied to pack-.

Load model (not a fixed resistor, per review R3A-02): the 5 V buck as a constant-power 2.5 W load
that runs above ~9.8 V (UVLO 10.4 on / 9.2 off, simplified), plus ~66 kOhm of DC dividers and R15.
Bus capacitance: C1 330 uF (ESR 20 mOhm new, 40 aged, 300 = its -40 C limit) + 3 x 10 uF 1206
(C25/C26/C31) derated to 4 uF on VBAT, and each DRV8316's VM pins behind 5 nH + R302/R402 0.1 ohm with 4 x 10 uF
(~16 uF) + 200 nF (both drive branches modelled; the measured one is U3's).

Reports, per case: peak VM dV/dt over the whole event (including any closure spike), the average
0-90 % ramp rate, peak pack current (the first A-level spike is C14 100 nF
ringing with the lead, upstream of the FETs), and Q7's peak power and energy.  Switch-reclose cases open
the switch at 60 ms and re-close it after a given off-time (the bus decays through the real load).
Also: a contact bounce (0.1, 0.3, 0.8 ms) under a 20 A weapon load, a reversed pack with and without D10 (U13's unpowered gate hold modelled as a resistor), and the
40/77 uA gate-current spread.  Cases run in parallel (~4 s).

Run: ../../tools/.venv/bin/python sim_hotplug.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "spice"))
from ngspice_shared import NgSpice  # noqa: E402

FET = (".model hyg vdmos(vto=1.9 kp=180 rd=0.5m rs=0.3m rg=1.95 cgs=3.9n cgdmax=1.6n cgdmin=0.033n "
       "a=0.25 cjo=5.4n m=0.5 vj=0.7 is=5e-12 n=1.05 rb=0.8m tt=4n bv=44 ibv=250u)")


def netlist(vpack=16.8, rbat=0.048, lead_nh=150.0, esr=0.020, off_ms=None, igate="60u", vth_f=1.14, vth_r=1.24,
            steer=True, rhold=None, tmax="20u", iload=0.0, c18="100n", rvm=0.1, cvm="16u"):
    t_on = 1e-3
    if off_ms is None:
        ctl = f"pwl(0 0 {t_on} 0 {t_on + 1e-6} 1)"
        t_end = t_on + 25e-3
    else:
        t2 = 60e-3 + off_ms * 1e-3
        ctl = f"pwl(0 0 {t_on} 0 {t_on + 1e-6} 1 60m 1 60.001m 0 {t2} 0 {t2 + 1e-6} 1)"
        t_end = t2 + 25e-3
    return f"""hotplug
vpack vp0 0 {vpack}
vctl ctl 0 {ctl}
s1 vp0 vp ctl 0 swm
.model swm sw(vt=0.5 ron=1m roff=1e8)
rbat vp b1 {rbat}
llead b1 b2 {lead_nh}n
rlead b2 bat_in 0.008
c14 bat_in 0 100n
* U13 LM74502: charge pump VS+12 V, 60 uA gate source when EN/UVLO is above threshold, 2 ohm sink below
bcp cp 0 v = v(bat_in) + 12
* EN/UVLO comparator with hysteresis: sw turns on above vth_r and off below vth_f (vt +- vh); en_on = 1 V when on
ven1 one 0 1
sen one en_on en 0 swcmp
.model swcmp sw(vt={(vth_f + vth_r) / 2} vh={(vth_r - vth_f) / 2} ron=1 roff=1e9)
ren_on en_on 0 1meg
bg cp psw_g i = {igate} * v(en_on) * 0.5 * (1 + tanh((v(bat_in) - 3.9) * 5))
dgc psw_g cp dclamp
.model dclamp d(is=1e-12 n=1)
{'bsink psw_g psw_s i = (v(psw_g) - v(psw_s)) / 2 * (1 - v(en_on))' if rhold is None else 'rhold psw_g psw_s ' + str(rhold)}
ren1 bat_in en 100k
ren2 en 0 15k
c18 en 0 {c18}
ien en 0 3u
dz4 psw_s psw_g dzen
.model dzen d(bv=12 ibv=1m is=1e-12)
rgi psw_g psw_rg 4.7k
{'d10 psw_rg psw_dv dsig' if steer else 'rsteer psw_rg psw_dv 1m'}
.model dsig d(is=2.5n n=1.8 rs=0.6 cjo=2p)
cdvdt psw_dv 0 22n
r32 psw_dv 0 1meg
m7 bat_in psw_g psw_s psw_s hyg
m8 vbat_sw psw_g psw_s psw_s hyg
rs4 vbat_sw vbat 0.001
dtvs 0 vbat dtvs
.model dtvs d(bv=23.3 ibv=1m rs=0.49 cjo=1n)
cb vbat nb1 330u
rb nb1 nb2 {esr}
lb nb2 0 3n
cm vbat nm1 12u
rm nm1 nm2 0.001
lm nm2 0 0.5n
lt vbat vm 5n
rt vm vm2 {rvm}
cvm vm2 nv1 {cvm}
rv nv1 0 0.005
cvhf vm2 0 200n
* the other drive's VM filter branch (R402 + ~16 uF)
lt2 vbat vmb 5n
rt2 vmb vmb2 {rvm}
cvmb vmb2 nvb1 {cvm}
rvb nvb1 0 0.005
cvhfb vmb2 0 200n
* loads: buck as constant power above ~9.8 V, DC dividers ~66 k (R63/R64 78k + R4/R5 441k; the weapon phase dividers
* have no DC path from VBAT while the bridge is Hi-Z), bleeder R15 6.8 k
bbuck vbat 0 i = 2.5 / max(v(vbat), 1) * 0.5 * (1 + tanh((v(vbat) - 9.8) * 5))
rdiv vbat 0 66k
r15 vbat 0 6.8k
* optional motor load (weapon at its current limit): constant current while the bus is above 5 V
bmot vbat 0 i = {iload} * 0.5 * (1 + tanh((v(vbat) - 5) * 5))
{FET}
.options method=gear reltol=1e-3 itl4=100
.tran 100n {t_end} 0 {tmax}
.end
"""


def run(t_from=0.0, **kw):
    ng = NgSpice()
    ng.load_netlist(netlist(**kw))
    ng.run("run")
    t = ng.vector("time")
    v = ng.vector("v(vm2)")
    i = ng.vector("i(llead)")
    vds7 = ng.vector("v(bat_in)") - ng.vector("v(psw_s)")     # Q7 (drain at the pack) is the FET that limits
    m = t >= t_from
    tm, vmm, im = t[m], v[m], i[m]
    dvdt = np.diff(vmm) / np.diff(tm)
    v0, vf = vmm[0], vmm[-1]
    lo, hi = v0 + 0.1 * (vf - v0), v0 + 0.9 * (vf - v0)
    try:
        t10 = tm[np.argmax(vmm > lo)]
        t90 = tm[np.argmax(vmm > hi)]
        ramp = (hi - lo) / (t90 - t10) / 1e6 if t90 > t10 else float("nan")
    except ValueError:
        ramp = float("nan")
    i7 = (ng.vector("v(vbat_sw)") - ng.vector("v(vbat)")) / 0.001   # Q7 current = RS4 current
    p7 = np.abs(vds7[m] * i7[m])
    e7 = np.trapezoid(p7, tm)
    return dvdt.max() / 1e6, ramp, np.abs(im).max(), p7.max(), e7, v0, tm[-1]


def _case(job):
    kind, name, kw, t_from = job
    return kind, name, kw, run(t_from=t_from, **kw)


def main():
    import multiprocessing as mp
    import sys as _sys
    stiff = dict(rbat=0.020, lead_nh=50.0)
    jobs = [("close", n, kw, 0.0) for n, kw in (
        ("nominal pack/lead, new C1", dict()),
        ("stiff pack, 50 nH lead, C1 ESR 40 mOhm (aged)", dict(esr=0.040, **stiff)),
        ("stiff pack, 50 nH lead, C1 ESR 300 mOhm (-40 C)", dict(esr=0.300, **stiff)),
        ("300 nH lead (long pigtail)", dict(lead_nh=300.0)),
        ("12 V pack (tired 4S)", dict(vpack=12.0)),
        ("gate source at the 77 uA max, stiff pack", dict(igate="77u", **stiff)),
        ("gate source at the 40 uA min, nominal pack", dict(igate="40u")))]
    for rh in ("300", "3k", "100k"):
        for steer in (True, False):
            jobs.append(("rev", f"  gate hold {rh:>5s} ohm, {'with' if steer else 'WITHOUT'} D10", dict(vpack=-16.8, rhold=rh, steer=steer), 0.0))
    for off, esr, vf, tag in ((1, 0.04, 1.14, ''), (10, 0.04, 1.14, ''), (100, 0.04, 1.14, ''), (300, 0.04, 1.14, ''), (500, 0.04, 1.14, ''),
                              (700, 0.04, 1.14, ''), (100, 0.3, 0.968, 'min UVLO'), (300, 0.3, 0.968, 'min UVLO'), (350, 0.3, 0.968, 'min UVLO'), (400, 0.3, 0.968, 'min UVLO'), (450, 0.3, 0.968, 'min UVLO'), (500, 0.3, 0.968, 'min UVLO'),
                              (700, 0.3, 0.968, 'min UVLO'), (500, 0.06, 0.968, 'min UVLO'), (1000, 0.3, 0.968, 'min UVLO'), (1500, 0.3, 0.968, 'min UVLO')):
        kw = dict(off_ms=off, esr=esr, vth_f=vf, vth_r=vf + 0.1, **stiff)
        jobs.append(("reclose", f"  off {off:5d} ms, C1 ESR {esr*1000:3.0f} mOhm {tag:9s}", kw, 60e-3 + off * 1e-3))
    for off, esr, st, tag in ((0.3, 0.04, {}, "nominal"), (0.3, 0.04, stiff, "stiff"), (0.8, 0.04, stiff, "stiff"),
                              (0.1, 0.1, stiff, "stiff, 0 C"), (0.3, 0.1, stiff, "stiff, 0 C"), (0.8, 0.1, stiff, "stiff, 0 C"),
                              (0.3, 0.3, stiff, "-40 C limit")):
        kw = dict(off_ms=off, esr=esr, iload=20.0, **st)
        jobs.append(("bounce", f"  {off:4.1f} ms bounce, 20 A load, {tag:10s} C1 {esr*1000:3.0f} mOhm", kw, 60e-3 + off * 1e-3))
    if "--serial" in _sys.argv:
        results = [_case(j) for j in jobs]
    else:
        with mp.get_context("spawn").Pool(min(len(jobs), mp.cpu_count())) as pool:
            results = pool.map(_case, jobs, chunksize=1)
    print("4S pack switched onto the board through the LM74502 + Q7/Q8 high-side switch; DRV8316 VM limits 40 V and 4 V/us")
    print(f"{'case':56s} {'peak dV/dt':>11s} {'ramp':>11s} {'I peak':>7s} {'Q7 Ppk':>7s} {'Q7 E':>7s}")
    shown = set()
    for kind, name, kw, (pk, ramp, ipk, p7, e7, v0, tend) in results:
        flag = "EXCEEDS 4 V/us" if pk > 4 else ""
        if kind == "close":
            print(f"{name:56s} {pk:8.3f}V/us {ramp*1000:7.2f}V/ms {ipk:6.2f}A {p7:6.1f}W {e7*1000:5.1f}mJ  {flag}")
        elif kind == "rev":
            if kind not in shown:
                print("\nReversed pack (-16.8 V), U13 unpowered; its internal gate-source hold is unspecified, modelled as a resistor:")
            print(f"{name}: peak pack current {ipk:6.2f} A")
        elif kind == "bounce":
            if kind not in shown:
                print("\nContact bounce under a 20 A weapon load (C18 delays the UVLO, the FETs stay on while the bus falls);"
                      "\n  C1 ESR 40 mOhm = aged limit at 20 C, 100 mOhm = bound for aged at 0 C (interpolated between the ZK 20 C and -40 C limits);"
                      "\n  (all at the DRV8316 VM pins, behind R302/R402 0.1 ohm + ~16 uF):")
            print(f"{name} VM before {v0:5.1f} V {pk:8.3f}V/us {ipk:7.1f}A  {flag}")
        else:
            if kind not in shown:
                print("\nSwitch opened at 60 ms and re-closed (stiff pack, 50 nH lead); 'VM before' = bus at re-close:")
            print(f"{name} VM before {v0:5.1f} V {pk:8.3f}V/us {ramp*1000:7.2f}V/ms {ipk:6.2f}A {p7:6.1f}W {e7*1000:5.1f}mJ  {flag}")
        shown.add(kind)


if __name__ == "__main__":
    main()
