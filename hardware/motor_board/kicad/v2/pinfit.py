"""How well the MCU pin map fits the floorplan: for each MCU signal net, the angle between the pin's outward
direction and the bearing to its destination, for each MCU rotation.  python3 pinfit.py [x y]
Destinations are block anchor points of the v2 floorplan (floorplan.py, variant A)."""
import csv
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MB = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "gen"))
from blocknets import blk  # noqa: E402

MCU = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) > 2 else (40.0, 26.75)
# anchor per block (top view, mm): where that block's end of an MCU net is expected to be
ANCHOR = {"U3": (8, 24), "U4": (23, 25), "SENL": (7, 31), "SENR": (22, 31), "DRVOFF": (15.5, 24), "CSAF": None,
          "U2": (56, 23), "AND": (54, 25), "J1": (73, 23), "ARM": (70, 25), "TP": (54, 31), "BMS": (70, 31),
          "INA": (36, 10), "WANA": None, "PDIV": (63, 10), "BRIDGE": (63, 12), "WNF": (52, 26), "LDO": None,
          "LED": None, "BUS": (34, 8), "MCU": None}
# nets whose far end is a filter/divider at the MCU: follow the net through to the real source
THROUGH = {"L_SOA_F": "U3", "L_SOB_F": "U3", "L_SOC_F": "U3", "R_SOA_F": "U4", "R_SOB_F": "U4", "R_SOC_F": "U4",
           "W_VA": "PDIV", "W_VB": "PDIV", "W_VC": "PDIV", "W_NTC": "BRIDGE", "VBAT_SNS": "J1",
           "L_MTEMP": "SENL", "R_MTEMP": "SENR"}
SKIP = {"GND", "+3V3", "+3V3A", "NC", "NRST_"}

rows = list(csv.DictReader(open(MB / "design" / "netlist.csv")))
mcu = {r["pin"]: r["net"] for r in rows if r["ref"] == "U1"}
others = {}
for r in rows:
    if r["ref"] != "U1":
        others.setdefault(r["net"], set()).add(blk.get(r["ref"], "?"))


def pin_xy(pin, rot):
    """LQFP-64 10x10, pad centres at +-5.75 (KiCad footprint, pin 1 top-left, CCW), then rotated by rot (deg, CCW
    in the board's y-down frame as KiCad shows it)."""
    n = int(pin) - 1
    side, k = divmod(n, 16)
    off = -3.75 + 0.5 * k
    x, y = [(-5.75, off), (off, 5.75), (5.75, -off), (-off, -5.75)][side]
    a = math.radians(rot)
    return (x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a))


def dest(net):
    b = THROUGH.get(net)
    if b:
        return ANCHOR[b]
    bs = [x for x in others.get(net, ()) if ANCHOR.get(x)]
    if not bs:
        return None
    pts = [ANCHOR[x] for x in bs]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


for rot in (0, 90, 180, 270):
    bad, tot, cost = [], 0, 0.0
    for pin, net in sorted(mcu.items(), key=lambda t: int(t[0])):
        if net in SKIP:
            continue
        d = dest(net)
        if d is None:
            continue
        px, py = pin_xy(pin, rot)
        out = math.atan2(py, px) if abs(abs(px) - abs(py)) > 0.01 else math.atan2(py, px)
        # outward normal of the pin's edge
        ox, oy = (math.copysign(1, px), 0) if abs(px) > abs(py) else (0, math.copysign(1, py))
        bx, by = d[0] - (MCU[0] + px), d[1] - (MCU[1] + py)
        ang = math.degrees(math.acos(max(-1, min(1, (ox * bx + oy * by) / math.hypot(bx, by)))))
        tot += 1
        cost += ang
        if ang > 100:
            bad.append(f"{pin}:{net}({ang:.0f})")
    print(f"rot {rot:3d}: mean {cost / tot:5.1f} deg over {tot} nets; facing away (>100 deg): {len(bad)}  " + " ".join(bad))
