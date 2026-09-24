#!/usr/bin/env python3
"""Weapon half-bridge switching transient: HYG015N04LS1C2 pair on the DRV8323RS.

Checks against the datasheet limits that layout can break:
  * FET VDS peak vs 40 V (HYG015N04LS1C2 BVDSS).
  * DRV8323 SHx: -5 V continuous / -7 V for 200 ns below PGND (SLVSDJ3D 7.1).
  * DRV8323 SPx/SNx: -3..+3 V for 200 ns (shunt ESL x di/dt shows up here).

Model:
  VBAT 16.8 V with bulk + 20 uF of MLCC at the bridge; commutation-loop inductance split
  into drain (Ld), phase (Lp) and source (Ls) segments, each damped by a parallel 2 ohm
  (standing in for PCB / skin-effect losses at the ringing frequency); 2 mOhm 2512 shunt
  with 1 nH ESL.
  FETs: VDMOS approximation of HYG015N04LS1C2 calibrated to its datasheet capacitances and
  gate charge (see FET below).  Not a vendor model: body-diode recovery is the weakest part,
  so treat absolute overshoot as +-30 % and use the table for trends (loop L, IDRIVE).
  Gate drive: DRV8323 IDRIVE approximated as an 11 V edge behind Rg = 11 V / IDRIVE.
  3x PWM mode: the driver inserts ~100 ns dead time.
  Load: 20 uH motor phase carrying +-20 A (the weapon current limit).

Run: python3 sim_weapon_bridge.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "spice"))
from ngspice_shared import NgSpice  # noqa: E402

VBAT = 16.8
# HYG015N04LS1C2 datasheet (hardware/datasheets/pdf): RDS 1.4 mOhm @10 V, Vth 1.9 V, RG 1.95 ohm,
# Ciss 4050 pF, Coss 890 pF, Crss 33 pF (VDS 25 V), Qg 59 nC, Qgs 15 nC, Qgd 8.5 nC, trr 40 ns, Qrr 43 nC.
# cgdmax/cgdmin/a give ~8.5 nC of Miller charge over 0-17 V and 33 pF at 25 V; cjo+m give 890 pF at 25 V.
FET = (".model hyg vdmos(vto=1.9 kp=180 rd=0.5m rs=0.3m rg=1.95 cgs=3.9n cgdmax=1.6n cgdmin=0.033n "
       "a=0.25 cjo=5.4n m=0.5 vj=0.7 is=5e-12 n=1.05 rb=0.8m tt=4n bv=44 ibv=250u)")


def netlist(i_load, l_loop_nh, idrive=0.4, rdamp=2.0, snub=False):
    lq = l_loop_nh / 3.0
    rg = 11.0 / idrive
    # HS on 0..4 us, dead 100 ns, LS on 4.1..8 us, dead 100 ns, HS on again from 8.1 us
    return f"""weapon half bridge
vbat vb 0 {VBAT}
cbulk vb nb 470u
rbulk nb 0 0.02
cm vb nm 20u
rm nm nm2 1m
lm nm2 0 0.5n
ld vb d0 {lq}n
rdl vb d0 {rdamp}
rld d0 d_hs 0.3m
mhs d_hs g_hs s_hs s_hs hyg
lp s_hs ph {lq}n
rdp s_hs ph {rdamp}
mls ph g_ls s_ls s_ls hyg
ls s_ls s0 {lq}n
rds s_ls s0 {rdamp}
rls0 s0 sp 0.3m
rsh sp sh1 0.002
lsh sh1 0 1n
rdsh sh1 0 {rdamp}
{FET}
{"rsn1 d_hs sn1 1.0" if snub else ""}
{"csn1 sn1 s_hs 4.7n" if snub else ""}
{"rsn2 ph sn2 1.0" if snub else ""}
{"csn2 sn2 s_ls 4.7n" if snub else ""}
vghs gh_on s_hs pwl(0 11 4u 11 4.001u 0 8.1u 0 8.101u 11 12u 11)
vgls gl_on 0 pwl(0 0 4.1u 0 4.101u 11 8u 11 8.001u 0 12u 0)
rhs gh_on g_hs {rg}
rls gl_on g_ls {rg}
lmot ph mot 20u ic={i_load}
vmid mot 0 {VBAT / 2}
.tran 0.2n 12u 0 0.5n uic
.end
"""


def run(i_load, l_loop_nh, idrive=0.4, snub=False):
    ng = NgSpice()
    ng.load_netlist(netlist(i_load, l_loop_nh, idrive, snub=snub))
    ng.run("run")
    t = ng.vector("time")
    ph, dhs, shs = ng.vector("v(ph)"), ng.vector("v(d_hs)"), ng.vector("v(s_hs)")
    sp, sls = ng.vector("v(sp)"), ng.vector("v(s_ls)")
    il = ng.vector("i(ld)")
    m = t > 3.5e-6                                   # measure the 4 us and 8 us edges only
    settled = abs(ph[(t > 2e-6) & (t < 3.8e-6)] - VBAT).max() < 1.0 and abs(ph[(t > 7e-6) & (t < 7.9e-6)]).max() < 1.0
    didt = np.abs(np.diff(il) / np.diff(t))[m[1:]].max() / 1e9
    return dict(vds_hs=(dhs - shs)[m].max(), vds_ls=(ph - sls)[m].max(), sh_min=ph[m].min(),
                sp_min=sp[m].min(), sp_max=sp[m].max(), didt=didt, settled=settled)


def main():
    print("Weapon half bridge, 16.8 V, +-20 A, 100 ns dead time.  (An RC snubber across each FET made no difference; run(snub=True) to see.)")
    print(f"{'snub':>4s} {'IDRIVE':>6s} {'I load':>7s} {'L loop':>7s} {'VDS HS':>8s} {'VDS LS':>8s} {'SH min':>8s} {'SP min':>8s} {'SP max':>8s}")
    for snub in (False,):
        for idrive in (0.4, 0.15, 0.06):
            for l_loop in (3.0, 6.0, 12.0):
                for i_load in (20.0, -20.0):
                    r = run(i_load, l_loop, idrive, snub)
                    flags = []
                    if not r["settled"]:
                        flags.append("(did not settle: ignore)")
                    if max(r["vds_hs"], r["vds_ls"]) > 40:
                        flags.append("VDS>40V")
                    if r["sh_min"] < -7:
                        flags.append("SH<-7V")
                    if r["sp_min"] < -3 or r["sp_max"] > 3:
                        flags.append("SP out of +-3V")
                    print(f"{'yes' if snub else 'no':>4s} {idrive*1000:4.0f}mA {i_load:6.0f}A {l_loop:5.0f}nH {r['vds_hs']:7.1f}V {r['vds_ls']:7.1f}V "
                          f"{r['sh_min']:7.2f}V {r['sp_min']:7.2f}V {r['sp_max']:7.2f}V  {' '.join(flags)}")

if __name__ == "__main__":
    main()
