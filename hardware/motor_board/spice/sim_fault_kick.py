#!/usr/bin/env python3
"""Weapon fault-clear kick at the DRV8316 VM pins (reconstruction of the round 9/10 reviewer sims).

Why: when the weapon bridge is turned off with a large current in a fault inductance, that current keeps flowing
through the opposite FETs' body diodes back into VBAT, and the bus that sagged during the fault rebounds.  The
DRV8316C (both drives) has a 4 V/us absolute-maximum VM ramp rate and a 40 V VM abs max (SLVSH07 7.1).  Rev K put
R302/R402 0.1 ohm + local MLCC in each DRV8316 VM feed to filter this; round 10's sims assumed a linear 16 uF per
drive.  v2 has 2 x 10 uF X7R 1210 per drive (~7.6 uF each at 16.8 V) and 3 x 10 uF X5R 1206 on VBAT at the bridge
(~2.3 uF each at 16.8 V).  MLCCs use the same C(V) law as sim_hotplug.py (Q = C0 V0 atan(V/V0)), but in a
charge-integrator form (capq below): sim_hotplug's capline() (charge as a function of V, differentiated by a reference
cap) does not converge at the ns time steps this event needs (timestep too small at t = 0), while integrating the
current into a charge node and setting V = V0 tan(Q / (C0 V0)) is robust.  Checked against the analytic charge
(1210 pair, 16.8 -> 5 V: dQ 207.02 uC sim vs 207.02 uC analytic).  The charge node is initialised from a DC op.

Model (after round9_d's appendix + round10_a's trip timing):
  pack 16.8 V + R (48 mOhm nominal / 20 mOhm stiff) + lead L (150 / 50 nH) + 8 mOhm; C14 100 nF; Q7/Q8 + RS4 on
  (~4 mOhm); SMBJ20A TVS at VBAT; C1 330 uF + ESR {20, 40, 100, 300 mOhm} + 3 nH.
  VBAT -> 5 nH || 2 ohm -> bridge node BR with C25/C26/C31 (3 x 10 uF 1206 X5R, C(V)) + 1 mOhm + 0.3 nH.
  BR -> 3 nH || 2 ohm commutation loop -> weapon FETs.  FET channels are ramped conductances (2.7 mOhm hot);
  all four FETs of the two involved legs have body diodes (bv 44 V = avalanche) and 2 nF Coss.
  Fault types:
    pp  phase-to-phase short A-B (HS_A + LS_B on, 2 mOhm shunt in LS_B source): after turn-off the fault current
        returns into BR through LS_A / HS_B body diodes (the worst kick);
    pg  phase-to-GND short at A (HS_A on): after turn-off the current freewheels in LS_A's body diode; the kick is
        the bus rebound from the pack-lead current alone;
    mot motor winding (40 uH line-line) at a 60 A trip: current returned to the bus over ~100 us.
  Trip: the channel starts to turn off t_off after fault onset and its conductance ramps to 0 over t_fall.
  Comparator trip (DESIGN 7.21 / round10_a R10A-01): current starts to fall 0.7-1.0 us after onset; VDS-only
  (comparator blind, e.g. phase-to-GND): 4 us deglitch.
  Each DRV8316 VM branch: from VBAT 10 nH || 2 ohm plane -> R302 0.1 ohm -> VM node with 2 x 10 uF 1210 X7R (C(V),
  5 mOhm, 0.5 nH) + 200 nF (10 mOhm, 0.3 nH); R302 (2512) has 1 nH ESL; both branches modelled, 0.5 A DC load each.
  One case per variant drops the R302 / 200 nF ESLs (para=False) to show how much the 5-50 ns figures depend on them.
  Validation: the 'round-10 assumption' variant (16 uF linear per drive, 12 uF linear bridge) with ideal parasitics
  gives 2.0 / 3.6 V/us rise / fall (50 ns) and 1.1 / 1.5 (200 ns) for the 100 nH, 1 us trip -- round10_a quotes
  2.2 / 3.6 and 1.0 / 1.5 for its model.
  Other loads: buck ~2.5 W as 113 ohm, dividers + bleeder.
Reported at U3's VM pin: peak dV/dt rising / falling as 50 ns and 200 ns moving averages (the bases round 9/10
used) and on a 5 ns grid (near-instantaneous), VM min/max, VBAT max, peak fault current.

Run: ../../tools/.venv/bin/python sim_fault_kick.py      (cases run in parallel, ~1 min)
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools", "spice"))
sys.path.insert(0, HERE)
from ngspice_shared import NgSpice  # noqa: E402
import math  # noqa: E402

CM_REAL = (3, 10e-6, 8.92)      # C25/C26/C31 10 uF 50 V X5R 1206, C(V)
CM_1210 = (3, 10e-6, 29.9)      # proposal: C25/C26/C31 as 1210 X7R
CM_OLD = (1, 12e-6, None)       # round 9/10 assumption: 12 uF linear
CVM_REAL = (2, 10e-6, 29.9)     # per drive: 2 x 10 uF 50 V X7R 1210 (v2)
CVM_OLD = (1, 16e-6, None)      # round 10 assumption: 16 uF linear
CVM_1206 = (4, 10e-6, 8.92)     # pre-v2: 4 x 10 uF X5R 1206, C(V)
T0 = 5e-6                       # fault onset


def capq(name, a, b, n, c0, v0, vinit):
    """n parallel MLCCs, C(V) = n c0 / (1 + (V/v0)^2) (v0=None: linear), as a charge integrator.
    Returns (netlist lines, .ic entry or '').  vinit: the DC voltage across the part at t = 0."""
    if v0 is None:
        return f"{name} {a} {b} {n * c0}", ""
    k = n * c0 * v0
    qi = k * math.atan(vinit / v0) / 1e-6            # charge as volts on a 1 uF reference cap
    return (f"v{name}s {a} {name}_i 0\n"
            f"e{name} {name}_i {b} vol = '{v0} * tan(v({name}_q) * 1e-6 / {k})'\n"
            f"f{name} 0 {name}_q v{name}s 1\n"
            f"c{name}r {name}_q 0 1u\n"
            f"r{name}r {name}_q 0 1e15\n"
            f"{name}x {a} {b} 1p"), f"v({name}_q)={qi}"


def netlist(fault="pp", lsh_nh=100.0, t_off=1.0e-6, t_fall=100e-9, esr=0.020, rbat=0.048, lead_nh=150.0,
            cm=CM_REAL, cvm=CVM_REAL, t_end=40e-6, tmax=2e-9, vinit=None, para=True):
    vinit = vinit or dict(br=16.7, vm=16.65, vmb=16.65)
    cml, icm = capq('cm', 'br', 'nm1', *cm, vinit['br'])
    cvl, icv = capq('cvm', 'vm', 'nv1', *cvm, vinit['vm'])
    cvbl, icvb = capq('cvmb', 'vmb', 'nvb1', *cvm, vinit['vmb'])
    ics = " ".join(x for x in (icm, icv, icvb) if x)
    t1, t2 = T0 + t_off, T0 + t_off + t_fall
    g = f"pwl(0 0 {T0} 0 {T0 + 10e-9} 1 {t1} 1 {t2} 0)"
    if fault == "pp":
        fault_net = f"lf a fx {lsh_nh}n\nrfx fx b 5m"
        on = "bhsa hs a i = v(hs, a) * v(ga) / 2.7m\nblsb b sb i = v(b, sb) * v(ga) / 2.7m"
    elif fault == "pg":
        fault_net = f"lf a fx {lsh_nh}n\nrfx fx 0 5m\nrbpull b 0 1k"
        on = "bhsa hs a i = v(hs, a) * v(ga) / 2.7m"
    else:   # motor winding, 40 uH line-line + 50 mOhm, switched on for t_off (150 us: ~55 A), then off
        fault_net = f"lf a fx {lsh_nh}n\nrfx fx b 50m"
        on = "bhsa hs a i = v(hs, a) * v(ga) / 2.7m\nblsb b sb i = v(b, sb) * v(ga) / 2.7m"
    return f"""fault kick
vpack vp 0 16.8
rbat vp b1 {rbat}
llead b1 b2 {lead_nh}n
rlead b2 bat_in 0.008
c14 bat_in 0 100n
rsw bat_in vbat 0.004
dtvs 0 vbat dtvs
.model dtvs d(bv=23.3 ibv=1m rs=0.49 cjo=1n)
cb vbat nb1 330u
rb nb1 nb2 {esr}
lb nb2 0 3n
* VBAT -> bridge node BR, with the bridge MLCCs C25/C26/C31
lbr vbat br 5n
rbr vbat br 2
{cml}
rm nm1 nm2 0.001
lm nm2 0 0.3n
* commutation loop to the weapon FETs
lcl br hs 3n
rcl br hs 2
vga ga 0 {g}
{on}
{fault_net}
* body diodes (bv 44 V models avalanche) and Coss of the four FETs in legs A and B
.model dbody d(is=5e-12 n=1.05 rs=0.8m tt=4n bv=44 ibv=250u)
dhsa a hs dbody
dlsa sa a dbody
dhsb b hs dbody
dlsb sb b dbody
chsa hs a 2n
clsa a sa 2n
chsb hs b 2n
clsb b sb 2n
rsha sa 0 2m
rshb sb 0 2m
* loads on VBAT: buck ~2.5 W, dividers, bleeder R15
rbuck vbat 0 113
rdiv vbat 0 66k
r15 vbat 0 6.8k
* DRV8316 U3 VM branch (measured) and U4
lt1 vbat t1 10n
rt1d vbat t1 2
rt1 t1 r1l {0.1}
{'lr' if para else 'rr'}1 r1l vm {'1n' if para else '1u'}
{cvl}
rv nv1 nv2 0.005
lv nv2 0 0.5n
cvhf vm h1a 200n
rh1 h1a h1b 10m
{'lh' if para else 'rlh'}1 h1b 0 {'0.3n' if para else '1u'}
ild1 vm 0 0.5
lt2 vbat t2 10n
rt2d vbat t2 2
rt2 t2 r2l {0.1}
{'lr' if para else 'rr'}2 r2l vmb {'1n' if para else '1u'}
{cvbl}
rvb nvb1 nvb2 0.005
lvb nvb2 0 0.5n
cvhfb vmb h2a 200n
rh2 h2a h2b 10m
{'lh' if para else 'rlh'}2 h2b 0 {'0.3n' if para else '1u'}
ild2 vmb 0 0.5
.options method=gear reltol=1e-4 itl4=200
{'.ic ' + ics if ics else ''}
.tran 1n {t_end} 0 {tmax}
.end
"""


def moving_rate(t, v, win):
    tg = np.arange(t[0], t[-1], 1e-9)
    vg = np.interp(tg, t, v)
    k = max(1, int(round(win / 1e-9)))
    d = (vg[k:] - vg[:-k]) / (k * 1e-9) / 1e6
    return d.max(), -d.min()


def dc_op(**kw):
    """DC operating point (caps open) to initialise the C(V) charge nodes."""
    kw = dict(kw, cm=CM_OLD, cvm=CVM_OLD)
    ng = NgSpice()
    ng.load_netlist(netlist(**kw))
    ng.run("op")
    return {n: float(ng.vector(f"v({n})")[0]) for n in ("br", "vm", "vmb")}


def run(**kw):
    vi = dc_op(**kw)
    ng = NgSpice()
    ng.load_netlist(netlist(vinit=vi, **kw))
    ng.run("run")
    t = ng.vector("time")
    vm = ng.vector("v(vm)")
    vb = ng.vector("v(vbat)")
    il = np.abs(ng.vector("i(lf)"))
    m = t > T0 - 0.5e-6
    t, vm, vb, il = t[m], vm[m], vb[m], il[m]
    r5 = moving_rate(t, vm, 5e-9)
    r50 = moving_rate(t, vm, 50e-9)
    r200 = moving_rate(t, vm, 200e-9)
    return dict(ipk=il.max(), vm_min=vm.min(), vm_max=vm.max(), vb_min=vb.min(), vb_max=vb.max(),
                r5=r5, r50=r50, r200=r200, vm0=vm[0])


def _case(job):
    name, kw = job
    try:
        return name, kw, run(**kw)
    except Exception as e:     # noqa: BLE001
        return name, kw, dict(err=str(e))


NOM = dict(rbat=0.048, lead_nh=150.0)
STIFF = dict(rbat=0.020, lead_nh=50.0)
VARIANTS = (("v2 real: VM 2x1210 C(V), bridge 3x1206 C(V)", dict(cm=CM_REAL, cvm=CVM_REAL)),
            ("v2 real, MLCC C0 x 0.81 (-10 % tol, cold, aging)", dict(cm=(3, 8.1e-6, 8.92), cvm=(2, 8.1e-6, 29.9))),
            ("round-10 assumption: VM 16u, bridge 12u linear", dict(cm=CM_OLD, cvm=CVM_OLD)),
            ("pre-v2 real: VM 4x1206 C(V), bridge 3x1206 C(V)", dict(cm=CM_REAL, cvm=CVM_1206)),
            ("option: bridge C25/C26/C31 as 1210 X7R", dict(cm=CM_1210, cvm=CVM_REAL)))


def jobs():
    out = []
    for vname, vkw in VARIANTS:
        cases = []
        for lsh in (100.0, 300.0, 1000.0):
            for toff in (0.7e-6, 1.0e-6):
                for esr, pk, ptag in ((0.020, NOM, "nom"), (0.040, STIFF, "stiff"), (0.100, STIFF, "stiff")):
                    cases.append((f"pp {lsh:4.0f}nH trip {toff*1e6:.1f}us/100ns C1 {esr*1e3:3.0f}m {ptag:5s}",
                                  dict(fault="pp", lsh_nh=lsh, t_off=toff, esr=esr, **pk)))
        cases.append(("pp  100nH trip 1.0us/ 50ns C1  40m stiff", dict(fault="pp", lsh_nh=100.0, t_off=1.0e-6, t_fall=50e-9, esr=0.040, **STIFF)))
        cases.append(("pp  100nH trip 1.0us/100ns C1 300m stiff (-40C)", dict(fault="pp", lsh_nh=100.0, t_off=1.0e-6, esr=0.300, **STIFF)))
        cases.append(("pp  100nH trip 1.0us/100ns C1  40m stiff, no R302/C ESL", dict(fault="pp", lsh_nh=100.0, t_off=1.0e-6, esr=0.040, para=False, **STIFF)))
        cases.append(("pp  100nH VDS-only 4us     C1  40m stiff (residual)", dict(fault="pp", lsh_nh=100.0, t_off=4e-6, esr=0.040, **STIFF)))
        cases.append(("pp  300nH VDS-only 4us     C1  40m stiff (residual)", dict(fault="pp", lsh_nh=300.0, t_off=4e-6, esr=0.040, **STIFF)))
        cases.append(("pg  100nH VDS-only 4us     C1  40m stiff (residual)", dict(fault="pg", lsh_nh=100.0, t_off=4e-6, esr=0.040, **STIFF)))
        cases.append(("pg  100nH VDS-only 4us     C1 100m stiff (residual)", dict(fault="pg", lsh_nh=100.0, t_off=4e-6, esr=0.100, **STIFF)))
        # motor winding: 40 uH, current reaches ~60 A at ~150 us; trip there, watch the return
        cases.append(("mot 40uH trip at ~60A      C1  40m stiff", dict(fault="mot", lsh_nh=40000.0, t_off=150e-6, esr=0.040, t_end=400e-6, tmax=10e-9, **STIFF)))
        for n, kw in cases:
            kw.update(vkw)
            out.append((f"{vname}|{n}", kw))
    return out


def main():
    import multiprocessing as mp
    js = jobs()
    if "--serial" in sys.argv:
        res = [_case(j) for j in js]
    else:
        with mp.get_context("spawn").Pool(mp.cpu_count()) as pool:
            res = pool.map(_case, js, chunksize=1)
    print("Weapon fault-clear kick at the DRV8316 U3 VM pins (behind 10 nH + R302 0.1 ohm + local caps).  Limits 4 V/us ramp, 40 V.")
    print("dV/dt columns: rise / fall, as 5 ns (near-instant), 50 ns and 200 ns moving averages.  Trip time = from fault onset")
    print("to the start of the 100 ns conductance ramp (comparator: 0.7-1.0 us per round10_a; VDS-only: 4 us).")
    cur = None
    for name, kw, r in res:
        vname, cname = name.split("|")
        if vname != cur:
            print(f"\n== {vname}")
            print(f"{'case':52s} {'Ipk':>6s} {'VM min-max':>12s} {'VBAT max':>8s} {'5ns r/f':>11s} {'50ns r/f':>11s} {'200ns r/f':>11s}")
            cur = vname
        if "err" in r:
            print(f"{cname:52s} ERROR {r['err'][:80]}")
            continue
        flag = "  >4 V/us (50ns)" if max(r["r50"]) > 4 else ""
        if r["vm_max"] > 40:
            flag += "  VM>40V"
        print(f"{cname:52s} {r['ipk']:5.0f}A {r['vm_min']:5.1f}-{r['vm_max']:4.1f}V {r['vb_max']:7.1f}V "
              f"{r['r5'][0]:5.2f}/{r['r5'][1]:5.2f} {r['r50'][0]:5.2f}/{r['r50'][1]:5.2f} {r['r200'][0]:5.2f}/{r['r200'][1]:5.2f}{flag}")


if __name__ == "__main__":
    main()
