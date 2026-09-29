#!/usr/bin/env python3
"""Weapon half-bridge switching transient with a real supply network and DC-biased MLCCs.

Companion to sim_weapon_bridge.py (same FET model, loop split, shunt, damping and motor load; its netlist is reused
and the supply block and/or gate drive are replaced).  Two findings about the original script drive this one:

1. It ties the bridge rail to an ideal 16.8 V source with 470 uF + 20 uF linear across it, so the bus capacitance
   (C1, C25/C26/C31, their DC bias) cannot affect its results at all.
2. Its gate drive (11 V edge behind Rg = 11 V / IDRIVE, same strength both ways, fixed 100 ns dead time, no
   handshake) turns a FET off over ~0.3-1.2 us, far longer than the dead time, so every edge in bridge.out is a
   shoot-through: 150-850 A through both FETs for 0.2-1.2 us (column 'I FET pk', flag SHOOT-THROUGH).  The ideal
   rail hides it.  The DRV8323 prevents this with its VGS handshake (it only turns a gate on once the opposite
   gate has discharged; SLVSDJ3D smart gate drive) and sinks 2 x the source current (IDRIVEN = 2 x IDRIVEP, R45
   75 k -> 60 / 120 mA).  gate='idrive' models that: IDRIVEP source to ~11 V, IDRIVEN sink, 100 ns dead time plus
   the handshake at VGS 1.5 V.  With it the FET-path peak is |I_load| + body-diode recovery only (22-33 A).

Supply (esr not None):

  pack 16.8 V + 20 mOhm + 50 nH (stiff) + 8 mOhm lead; lead current initialised to I_load / 2 (the PWM average);
  C1 330 uF, ESR {20, 300} mOhm, 3 nH;  C1 -> 5 nH || 2 ohm -> bridge rail;
  the leg's own 10 uF (C25 for phase A) at the rail, 1 mOhm + 0.4 nH ESL (its ESL is in series with the loop, so the
  effective commutation loop is L_loop + 0.4 nH);  the other two legs' caps (C26/C31) behind 2 nH || 2 ohm of plane.
  MLCCs: 1206 X5R 10 uF C(V) (V0 = 8.92 V, ~2.2 uF at 16.8 V), or the 1210 X7R alternative (V0 = 29.9 V, ~7.6 uF),
  or the 20 uF linear the original script assumed (lumped at the rail, for comparison).
  The C(V) law is the charge-integrator capq() from sim_fault_kick.py.  All caps start at 16.8 V (uic).
Variants: the original gate model on the ideal rail (reproduces bridge.out exactly) and on the real supply; then the
IDRIVE + handshake gate on the ideal rail, and on the real supply with 1206 X5R C(V) (C1 20 / 300 mOhm), 20 uF
linear (the original value) and 1210 X7R C(V) for C25/C26/C31.  IDRIVE (source/sink): 60/120 mA (design, R45 75 k),
120/240 mA (R45 open, DESIGN 9 fault case), 260/520 mA.

Run: ../../tools/.venv/bin/python sim_weapon_bridge.py     (cases in parallel, ~1 min)
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools", "spice"))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import sim_weapon_bridge as wb  # noqa: E402
from ngspice_shared import NgSpice  # noqa: E402

VB = wb.VBAT


def capq_ic(name, a, b, n, c0, v0):
    """C(V) MLCC bank for a uic transient starting at VB across it (see sim_fault_kick.capq)."""
    if v0 is None:
        return f"{name} {a} {b} {n * c0} ic={VB}"
    k = n * c0 * v0
    qi = k * math.atan(VB / v0) / 1e-6
    return (f"v{name}s {a} {name}_i 0\n"
            f"e{name} {name}_i {b} vol = '{v0} * tan(v({name}_q) * 1e-6 / {k})'\n"
            f"f{name} 0 {name}_q v{name}s 1\n"
            f"c{name}r {name}_q 0 1u ic={qi}\n"
            f"r{name}r {name}_q 0 1e15\n"
            f"{name}x {a} {b} 1p ic={VB}")


def supply(i_load, esr, local, others):
    return f"""vpack vp 0 {VB + 0.028 * i_load / 2}
rbat vp b1 0.020
llead b1 b2 50n ic={i_load / 2}
rlead b2 c1 0.008
cc1 c1 c1a 330u ic={VB}
rc1 c1a c1b {esr}
lc1 c1b 0 3n
lpl c1 vb 5n
rpl c1 vb 2
{capq_ic('cloc', 'vb', 'nl1', *local)}
rloc nl1 nl2 1m
lloc nl2 0 0.4n
{'' if others is None else "lo vb vo 2n" + chr(10) + "ro vb vo 2" + chr(10) + capq_ic('coth', 'vo', 'no1', *others) + chr(10) + "roth no1 no2 1m" + chr(10) + "loth no2 0 0.3n"}
"""


GATE_IDRIVE = """* DRV8323 current-mode gate drive: IDRIVEP source (to ~11 V) / IDRIVEN sink, 3x PWM with 100 ns dead time AND the
* VGS handshake: a gate is only driven on once the opposite gate pin has fallen below ~1.5 V.  Off = sink (holds low).
vcmdh cmdh 0 pwl(0 1 4u 1 4.001u 0 8.1u 0 8.101u 1 12u 1)
vcmdl cmdl 0 pwl(0 0 4.1u 0 4.101u 1 8u 1 8.001u 0 12u 0)
bonh onh 0 v = v(cmdh) * 0.5 * (1 + tanh((1.5 - v(g_ls, s_ls)) / 0.1))
bonl onl 0 v = v(cmdl) * 0.5 * (1 + tanh((1.5 - v(g_hs, s_hs)) / 0.1))
bgh s_hs g_hs i = v(onh) * {isrc} * tanh(max(11 - v(g_hs, s_hs), 0) / 0.3) - (1 - v(onh)) * {isnk} * tanh(v(g_hs, s_hs) / 0.3)
bgl s_ls g_ls i = v(onl) * {isrc} * tanh(max(11 - v(g_ls, s_ls), 0) / 0.3) - (1 - v(onl)) * {isnk} * tanh(v(g_ls, s_ls) / 0.3)
rgh g_hs s_hs 100k
rgl g_ls s_ls 100k
"""


def netlist(i_load, l_loop_nh, idrive, esr, local, others, gate="idrive"):
    """idrive: source current (A); gate='idrive' -> sink = 2 x source + handshake, gate='rc' -> the original 11 V / Rg edge.
    esr=None -> the original ideal 16.8 V rail (bulk caps irrelevant)."""
    base = wb.netlist(i_load, l_loop_nh, idrive)
    out = []
    for ln in base.splitlines():
        w = ln.split(" ")[0]
        if esr is not None and w in ("vbat", "cbulk", "rbulk", "cm", "rm", "lm"):
            continue
        if gate == "idrive" and w in ("vghs", "vgls", "rhs", "rls"):
            continue
        out.append(ln)
        if ln.strip() == "weapon half bridge":
            if esr is not None:
                out.append(supply(i_load, esr, local, others))
            if gate == "idrive":
                out.append(GATE_IDRIVE.format(isrc=idrive, isnk=2 * idrive))
    return "\n".join(out).replace(".tran 0.2n 12u 0 0.5n uic", ".options method=gear\n.tran 0.2n 12u 0 0.5n uic")


def run(i_load, l_loop_nh, idrive, esr, local, others, gate="idrive"):
    ng = NgSpice()
    ng.load_netlist(netlist(i_load, l_loop_nh, idrive, esr, local, others, gate))
    ng.run("run")
    t = ng.vector("time")
    ph, dhs, shs = ng.vector("v(ph)"), ng.vector("v(d_hs)"), ng.vector("v(s_hs)")
    sp, sls, vb = ng.vector("v(sp)"), ng.vector("v(s_ls)"), ng.vector("v(vb)")
    m = t > 3.5e-6
    vb_before = vb[(t > 3.0e-6) & (t < 3.9e-6)].mean()
    settled = abs(ph[(t > 2e-6) & (t < 3.8e-6)] - vb_before).max() < 1.0 and abs(ph[(t > 7e-6) & (t < 7.9e-6)]).max() < 1.0
    ihs = ng.vector("i(ld)")
    ils = ng.vector("i(ls)")
    xt = max(ihs[m].max(), ils[m].max(), -ihs[m].min(), -ils[m].min())     # peak FET-path current (|I_load| = no shoot-through)
    return dict(vds_hs=(dhs - shs)[m].max(), vds_ls=(ph - sls)[m].max(), sh_min=ph[m].min(), sp_min=sp[m].min(),
                sp_max=sp[m].max(), vb_min=vb[m].min(), vb_max=vb[m].max(), ipk=xt, settled=settled)


X5R = (1, 10e-6, 8.92)
X5R2 = (2, 10e-6, 8.92)
X7R = (1, 10e-6, 29.9)
X7R2 = (2, 10e-6, 29.9)
VARIANTS = (("original gate model (RC, fixed 100 ns dead time), ideal rail = bridge.out", "rc", None, None, None),
            ("original gate model, real supply, C25 + C26/C31 1206 X5R C(V), C1 20 mOhm", "rc", 0.020, X5R, X5R2),
            ("IDRIVE current-mode + handshake, ideal rail", "idrive", None, None, None),
            ("real supply, C25 + C26/C31 1206 X5R C(V), C1 20 mOhm", 0.020, X5R, X5R2),
            ("real supply, C25 + C26/C31 1206 X5R C(V), C1 300 mOhm", 0.300, X5R, X5R2),
            ("real supply, 20 uF linear lumped at the leg (old value)", 0.020, (1, 20e-6, None), None),
            ("real supply, C25 + C26/C31 1210 X7R C(V), C1 20 mOhm", 0.020, X7R, X7R2))
VARIANTS = VARIANTS[:3] + tuple((("IDRIVE current-mode + handshake, " + v[0], "idrive") + v[1:]) for v in VARIANTS[3:])


def _case(job):
    vname, gate, i_load, l_loop, idrive, esr, local, others = job
    try:
        return job, run(i_load, l_loop, idrive, esr, local, others, gate)
    except Exception as e:  # noqa: BLE001
        return job, dict(err=str(e))


def main():
    import multiprocessing as mp
    jobs = [(vn, g, il, ll, idr, esr, loc, oth) for vn, g, esr, loc, oth in VARIANTS
            for idr in ((0.4, 0.15, 0.06) if g == "rc" else (0.06, 0.12, 0.26)) for ll in (3.0, 6.0, 12.0) for il in (20.0, -20.0)]
    with mp.get_context("spawn").Pool(mp.cpu_count()) as pool:
        res = pool.map(_case, jobs, chunksize=1)
    print("Weapon half bridge, 16.8 V, +-20 A, 100 ns dead time; real pack + C1 + DC-biased MLCCs (compare bridge.out, ideal 16.8 V rail).")
    print("Limits: VDS 40 V, SHx -7 V (200 ns), SPx +-3 V (200 ns).  'rail' = bridge-rail min/max after 3.5 us.")
    cur = None
    for (vn, g, il, ll, idr, esr, loc, oth), r in res:
        if vn != cur:
            print(f"\n== {vn}")
            print(f"{'IDRIVE':>6s} {'I load':>7s} {'L loop':>7s} {'VDS HS':>8s} {'VDS LS':>8s} {'SH min':>8s} {'SP min':>8s} {'SP max':>8s} {'rail':>12s} {'I FET pk':>8s}")
            cur = vn
        if "err" in r:
            print(f"{idr*1000:4.0f}mA {il:6.0f}A {ll:5.0f}nH ERROR {r['err'][:90]}")
            continue
        flags = []
        if r["ipk"] > 2.5 * abs(il):
            flags.append("SHOOT-THROUGH")
        if not r["settled"]:
            flags.append("(did not settle: ignore)")
        if max(r["vds_hs"], r["vds_ls"]) > 40:
            flags.append("VDS>40V")
        if r["sh_min"] < -7:
            flags.append("SH<-7V")
        if r["sp_min"] < -3 or r["sp_max"] > 3:
            flags.append("SP out of +-3V")
        print(f"{idr*1000:4.0f}mA {il:6.0f}A {ll:5.0f}nH {r['vds_hs']:7.1f}V {r['vds_ls']:7.1f}V {r['sh_min']:7.2f}V {r['sp_min']:7.2f}V "
              f"{r['sp_max']:7.2f}V {r['vb_min']:5.1f}-{r['vb_max']:4.1f}V {r['ipk']:7.0f}A  {' '.join(flags)}")


if __name__ == "__main__":
    main()
