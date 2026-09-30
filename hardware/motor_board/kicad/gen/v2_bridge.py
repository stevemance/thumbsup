"""v2 weapon bridge: the 15 U2-bridge nets (gate pairs, low-side gates, shunt Kelvin), hand-drawn per
review/v2_layout/gate_corridor.md (option 3) on the v2 placement (kicad/v2/spec.py: cells B/A +0.6 mm, U2 at y 24.0,
net ties at the rear of the shunt pad gaps).  Experiment module for tail.py:

    cd kicad/gen && TAIL_EXP=v2_bridge TAIL_BASE=<abs>/kicad/motor_board/motor_board.kicad_pcb /usr/bin/python3 tail.py

Layers: F.Cu = L1, In1.Cu = L2 (GND plane, untouched), In2.Cu = L3, B.Cu = L4.  Board-local mm.
Rule areas and exceptions: kicad/v2/README_bridge.md.  No router requests: every segment is explicit.

  - HS gate pairs (GHx + SHx): L4 "lanes" under the band.  C and A: y-lanes from the cell's interior mouth; B: x-lane
    under Q4 to the C|B channel, then L1.  C's pair stays on L4 into U2 pins 18/19 (in-pad vias); A's pair and B's
    pair finish on L1.
  - GLx: L1 only, pin 4 -> strip behind the pin row -> left side of the shunt pad gap -> U2.
  - SLx/SNx: L1 taps (SL pad, net tie), then L4 over L3 GND (y > 16.3) into in-pad vias at U2 (C, B); A stays on L1
    except an SN hop under SL/GL.
"""
GATE, SENSE = 0.25, 0.2
GV = dict(d=0.6, drill=0.3)            # gate-pair vias
KV = dict(d=0.45, drill=0.2)           # Kelvin vias (and in the net-tie pads: POFV)
PV = dict(d=0.4, drill=0.2)            # via-in-pad (POFV) at U2 and RS2.1
W = "/weapon/"

EDITS = []


def tr(net, layer, pts, w):
    EDITS.append(dict(op="track", net=W + net, layer=layer, pts=pts, w=w))


def via(net, c, v):
    EDITS.append(dict(op="via", net=W + net, c=c, **v))


# U2 pad row (U2 at 63.5, 24.0, rot 180): front pads y 20.125-21.0 (centre 20.562), east pads x 66.5-67.375.
# In-pad vias are staggered along the 0.875 mm pad: "outer" y 20.30, "inner" y 20.80 (>= 0.15 mm to the neighbour
# pads, 0.425 mm to the thermal pad, 0.31 mm between neighbouring in-pad vias).
OUT, INN, PADC = 20.30, 20.80, 20.562

# ------------------------------------------------------------------ phase C (x0 45.5: Q6 LS, Q5 HS, RS3, NT3)
tr("W_GLC", "F.Cu", [(50.405, 11.875), (50.405, 12.9), (48.9, 12.9), (48.325, 13.475), (48.325, 19.0),
                     (62.75, 19.0), (62.75, PADC)], GATE)
# SL: stub off the SL pad's rear edge, via behind the pad, L4 to U2.21 (in-pad, inner)
tr("W_SLC", "F.Cu", [(47.5, 17.0), (47.5, 18.3)], SENSE)
via("W_SLC", (47.5, 18.3), KV)
tr("W_SLC", "B.Cu", [(47.5, 18.3), (48.2, 19.0), (62.25, 19.0), (62.25, INN)], SENSE)
via("W_SLC", (62.25, INN), PV)
# SN: via in NT3's SN pad, L4 round the SL via (it lands left of SL at U2), U2.22 (in-pad, outer)
via("W_SNC", (48.9, 16.85), KV)
tr("W_SNC", "B.Cu", [(48.9, 16.85), (46.9, 17.7), (46.9, 19.4), (61.75, 19.4), (61.75, OUT)], SENSE)
via("W_SNC", (61.75, OUT), PV)
# GH/SH pair: mouth vias between Q6's and Q5's tabs, L4 lane under the RS3|C31 gap, on to U2.18/19 (in-pad)
tr("W_GHC", "F.Cu", [(52.795, 6.425), (52.795, 6.9), (52.15, 7.55), (51.6, 7.55)], GATE)
via("W_GHC", (51.6, 7.55), GV)
tr("W_GHC", "B.Cu", [(51.6, 7.55), (51.6, 12.7), (52.8, 13.9), (52.8, 18.1), (63.75, 18.1), (63.75, INN)], GATE)
via("W_GHC", (63.75, INN), PV)
via("W_C", (51.6, 6.45), GV)           # SH pick-up in the mouth; L1 stub to Q5's source pin 3 (in front of pin 4)
tr("W_C", "F.Cu", [(51.6, 6.45), (51.6, 5.45), (53.9, 5.45), (54.065, 6.2)], GATE)
tr("W_C", "B.Cu", [(51.6, 6.45), (51.0, 7.05), (51.0, 12.9), (52.35, 14.25), (52.35, 18.55), (63.25, 18.55), (63.25, OUT)], GATE)
via("W_C", (63.25, OUT), PV)

# ------------------------------------------------------------------ phase B (x0 58.6: Q4 LS, Q3 HS, RS2, NT2)
tr("W_GLB", "F.Cu", [(63.505, 11.875), (63.505, 12.9), (62.0, 12.9), (61.425, 13.475), (61.425, 17.65),
                     (65.25, 17.65), (65.25, PADC)], GATE)
via("W_SLB", (60.85, 16.95), PV)       # in RS2's SL pad, inner-rear corner (POFV)
tr("W_SLB", "B.Cu", [(60.85, 16.95), (61.45, 17.55), (65.75, 17.55), (65.75, INN)], SENSE)
via("W_SLB", (65.75, INN), PV)
via("W_SNB", (62.0, 16.85), KV)        # in NT2's SN pad (POFV)
tr("W_SNB", "B.Cu", [(62.0, 16.85), (66.25, 16.85), (66.25, OUT)], SENSE)
via("W_SNB", (66.25, OUT), PV)
# GH/SH pair: mouth vias, L4 x-lane under Q4's front half, up in the C|B channel, L1 through the door to U2.17/16
tr("W_GHB", "F.Cu", [(65.895, 6.425), (65.895, 6.9), (65.25, 7.55), (64.7, 7.55)], GATE)
via("W_GHB", (64.7, 7.55), GV)
tr("W_GHB", "B.Cu", [(64.7, 7.55), (64.3, 7.3), (58.45, 7.3), (58.05, 7.55)], GATE)
via("W_GHB", (58.05, 7.55), GV)
tr("W_GHB", "F.Cu", [(58.05, 7.55), (58.05, 12.0), (56.75, 13.4), (56.75, 18.55), (64.25, 18.55), (64.25, PADC)], GATE)
via("W_B", (64.7, 6.45), GV)
tr("W_B", "F.Cu", [(64.7, 6.45), (64.7, 5.45), (67.0, 5.45), (67.165, 6.2)], GATE)
tr("W_B", "B.Cu", [(64.7, 6.45), (64.3, 6.85), (58.45, 6.85), (58.05, 6.45)], GATE)
via("W_B", (58.05, 6.45), GV)
tr("W_B", "F.Cu", [(58.05, 6.45), (58.65, 7.0), (58.65, 12.1), (57.25, 13.6), (57.25, 18.1), (64.75, 18.1), (64.75, PADC)], GATE)

# ------------------------------------------------------------------ phase A (x0 71.1: Q2 LS, Q1 HS, RS1, NT1)
# the five nets fan into U2's east pads 12..8 (y 21.25..23.25) as parallel 45-degree lines
tr("W_GLA", "F.Cu", [(76.005, 11.875), (76.005, 12.9), (74.5, 12.9), (73.925, 13.475), (73.925, 18.225),
                     (69.9, 22.25), (66.938, 22.25)], GATE)
tr("W_SLA", "F.Cu", [(73.3, 17.0), (73.3, 18.2), (69.75, 21.75), (66.938, 21.75)], SENSE)
via("W_SNA", (74.5, 16.85), KV)        # in NT1's SN pad (POFV); L4 hop under SL/GL to the left of SL
tr("W_SNA", "B.Cu", [(74.5, 16.85), (73.65, 17.7), (72.7, 17.7), (72.4, 18.0)], SENSE)
via("W_SNA", (72.4, 18.0), KV)
tr("W_SNA", "F.Cu", [(72.4, 18.0), (69.15, 21.25), (66.938, 21.25)], SENSE)
# GH/SH pair: mouth vias, L4 y-lane under the RS1|C25 gap, up behind RS1/C25, L1 diagonal to U2.8/9
tr("W_GHA", "F.Cu", [(78.395, 6.425), (78.395, 6.9), (77.75, 7.55), (77.2, 7.55)], GATE)
via("W_GHA", (77.2, 7.55), GV)
tr("W_GHA", "B.Cu", [(77.2, 7.55), (77.2, 12.7), (78.4, 13.9), (78.4, 18.1), (78.85, 18.55)], GATE)
via("W_GHA", (78.85, 18.55), GV)
tr("W_GHA", "F.Cu", [(78.85, 18.55), (74.85, 18.55), (70.15, 23.25), (66.938, 23.25)], GATE)
via("W_A", (77.2, 6.45), GV)
tr("W_A", "F.Cu", [(77.2, 6.45), (77.2, 5.45), (79.5, 5.45), (79.665, 6.2)], GATE)
tr("W_A", "B.Cu", [(77.2, 6.45), (76.6, 7.05), (76.6, 12.9), (77.95, 14.25), (77.95, 17.65), (77.65, 17.95)], GATE)
via("W_A", (77.65, 17.95), GV)
tr("W_A", "F.Cu", [(77.65, 17.95), (74.8, 17.95), (70.0, 22.75), (66.938, 22.75)], GATE)

# ------------------------------------------------------------------ U2 SOC/SOB: in-pad vias only (their L4 exit west is
# the MCU-side routing's job; they must leave behind the phase-C L4 bundle, i.e. at y > 19.6)
EDITS.append(dict(op="vip", pad=("U2", "23"), off=(0.0, INN - PADC), **PV))
EDITS.append(dict(op="vip", pad=("U2", "24"), off=(0.0, OUT - PADC), **PV))
