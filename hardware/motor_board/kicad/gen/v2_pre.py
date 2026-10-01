"""Shared helpers for the v2 region pre-routes (P3/P5) on top of v2_bridge + v2_drive:
v2_ilock (weapon interlock / U2 control), v2_sense (motor-sensor front ends, dividers), v2_rear (J1, SWD, BMS, rails).

Layers: F.Cu = L1, In1.Cu = L2 (GND plane, never routed), In2.Cu = L3, B.Cu = L4.  Board-local mm, y toward the rear.
Rules applied to every router request (memo 3.1 / README_bridge.md):
  - front power band: no L3/L4 tracks at y < 18.5, except y < 16.3 for x 14-27 and x >= 44.5 (L3 VBAT edge y 16.0);
  - no L3 in the U3/U4 islands (exposed pad + 1.5 mm), no L4 in the U2/U3/U4 thermal-via fields (exposed pad + 0.5 mm);
  - analog nets (CSA, MTEMP/TEMPJ, dividers W_Vx / VBAT_SNS(_H), NTC, CELLx / BALx) use L1 and L3 only, and no other
    net's L3/L4 track may overlap an analog L3/L4 track (router "analog_nets": the layer above stays GND fill).
Digital L3 lanes may be crossed by L4 tracks; stacked parallel runs are checked afterwards (out/pr/rules.py)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
F1, L3, L4 = "F.Cu", "In2.Cu", "B.Cu"
PV = dict(d=0.4, drill=0.2)             # signal via
RV = dict(d=0.45, drill=0.25)           # rail via
POFV = dict(d=0.4, drill=0.2)           # via in pad (filled + capped)

_g = json.load(open(HERE / "out" / "pr" / "drive_geom.json"))
FULL = {n.split("/")[-1]: n for n in _g["nets"]}
FULL.update({n: n for n in _g["nets"]})


def n_(net):
    return FULL[net]


ANALOG_SHORT = [n for n in FULL if "/" not in n and (
    n.split("_")[-1] in ("SOA", "SOB", "SOC") or n.endswith(("_SOA_F", "_SOB_F", "_SOC_F")) or
    n in ("L_MTEMP", "R_MTEMP", "L_TEMPJ", "R_TEMPJ", "W_VA", "W_VB", "W_VC", "VBAT_SNS", "VBAT_SNS_H", "W_NTC") or
    n in ("CELL0", "CELL1", "CELL2", "CELL3", "CELL4", "BAL0", "BAL1", "BAL2", "BAL3", "BAL4"))]
ANALOG = sorted({FULL[n] for n in ANALOG_SHORT})


def grow(b, d):
    return (b[0] - d, b[1] - d, b[2] + d, b[3] + d)


EP = {"U3": (6.65, 22.45, 12.35, 26.15), "U4": (20.65, 20.65, 24.35, 26.35), "U2": (60.915, 21.545, 65.955, 26.455)}
M = 0.1
BAND = [(0, 0, 14.0, 18.5), (14.0, 0, 27.0, 16.3), (27.0, 0, 44.5, 18.5), (44.5, 0, 85, 16.3)]
AVOID = [[ly, *grow(b, M), "tracks"] for ly in (L3, L4) for b in BAND]
AVOID += [[L3, *grow(grow(EP[u], 1.5), M), "tracks"] for u in ("U3", "U4")]
AVOID += [[L4, *grow(grow(EP[u], 0.5), M), "tracks"] for u in ("U2", "U3", "U4")]

# via spots / stubs region 2 places explicitly next to the MCU (earlier regions keep out of them)
R2_SPOTS = [(39.25, 20.6), (40.75, 19.5), (41.25, 19.95), (43.71, 25.0), (43.71, 23.5), (42.45, 27.5)]
RESERVE_R2 = [["*", x - 0.45, y - 0.45, x + 0.45, y + 0.45] for x, y in R2_SPOTS] + [
    [L4, 41.55, 19.7, 43.3, 20.5, "tracks"], [L4, 41.55, 19.7, 41.95, 22.0, "tracks"]]   # W_NTC stubs on L4

# region 3's INA_nCS path (U7.1 -> C407 gap via -> L3 y 20.25 -> via at C61 -> R12.1; L1 y 19.45 to U1.23)
RESERVE_R3 = [["*", 26.95, 19.85, 27.75, 20.65], ["*", 33.0, 19.9, 33.8, 20.7], [L3, 27.1, 20.05, 33.6, 20.45, "tracks"],
              [F1, 26.3, 18.2, 27.6, 20.5, "tracks"], [F1, 33.2, 19.2, 38.9, 19.72, "tracks"],
              [L4, 33.3, 20.2, 33.9, 21.5, "tracks"]]

# region 3's BMS hops at U8 / J1 (BMS_BAT R11.2 -> U8.16, the I2C pair into J1, VBAT_SNS_H west of R58)
RESERVE_R3B = [[L4, 70.25, 31.0, 71.05, 32.1], [L4, 71.25, 21.9, 72.6, 29.5], [L4, 73.65, 26.1, 74.3, 29.3]]

EDITS = []
EXTRA_AVOID = []
VIA_PITCH = 0.0                         # r2: min centre distance of a new non-GND via to every non-GND via (router)
STACK_PEN = 0.0                         # router cost factor for L3/L4 runs stacked over another net (module may raise it)                        # per-module reserved boxes, added to every router request
NEW_VIAS = []                           # (net, c, kind) for the log


def tr(net, layer, pts, w=0.15):
    EDITS.append(dict(op="track", net=n_(net), layer=layer, pts=pts, w=w))


def via(net, c, v=PV, kind="via"):
    EDITS.append(dict(op="via", net=n_(net), c=c, **v))
    NEW_VIAS.append((net, c, kind))


def is_analog(net):
    return n_(net) in ANALOG


def route(net, a, b, layers=None, stub=False, **kw):
    """stub=True: a short local hop to a bottom-side pad (analog nets may use L4 for it)"""
    if layers is None:
        layers = [F1, L3, L4]
    if is_analog(net) and L4 in layers and not stub:
        # analog: L4 only for the last hop onto a bottom-side pad (8x cost); runs go on L1 / L3
        kw.setdefault("layer_cost", {})
        kw["layer_cost"].setdefault(L4, 8.0)
    kw["avoid"] = AVOID + EXTRA_AVOID + kw.get("avoid", [])
    kw.setdefault("via_cost", 3.0)
    kw.setdefault("margin", 3.0)
    kw["analog_nets"] = ANALOG
    kw.setdefault("stack_pen", STACK_PEN)
    if VIA_PITCH:
        kw.setdefault("via_pitch", VIA_PITCH)
    EDITS.append(dict(op="route", net=n_(net), a=a, b=b, layers=layers, **kw))


def P(ref, num):
    return ("pad", ref, str(num))


def chain(net, pads, layers=None, **kw):
    for a, b in zip(pads, pads[1:]):
        route(net, a, b, layers, **kw)
