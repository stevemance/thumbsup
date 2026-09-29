"""v2 placement spec (floorplan approved 2026-09-29: both drives at the rear-left, MCU rotated 180 in the rear centre,
U2 behind the middle bridge cell, J1 on the bottom at the rear-right).  Coordinates in mm, board top view, origin at
the front-left corner: x to the robot's right, y toward the REAR (y = 0 is the front edge, drum side).

EXPLICIT: courtyard centre, rotation (KiCad degrees), side, why.  Only the weapon bridge cells keep attempt 1's
geometry (lessons memo section 2); every other position is new.
ANCHORED: generated.  Each remaining part goes near its anchor: the IC pin its description names ("U3 VM pin 9"),
otherwise the pad of an already placed part on its most specific net, otherwise its block's IC.  Its side comes
from floorplan.side_of() (heights, hot parts, pack nets), its region from REGION below."""
import csv
import importlib.util
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MB = HERE.parents[1]
sys.path.insert(0, str(HERE))
import floorplan as FP  # noqa: E402
from blocknets import blk as BLOCK_OF  # noqa: E402

BW, BH = 85.0, 35.0
CORNER_R = 1.5
EDGE = 0.4          # anchored parts: courtyard to board edge
GAP = 0.1           # anchored parts: extra gap between courtyards
EDGE_OK = set()
OVERLAP_OK = {("NT1", "RS1"), ("NT2", "RS2"), ("NT3", "RS3")}   # net ties sit on their shunt's GND pad (same net)
T, B = "T", "B"
THT_CLEAR = {"JBAT": 2.0, "JW": 2.0, "JL": 1.5, "JR": 1.5, "J4": 1.5}
EP_KEEPOUT = [("U2", "B", 1.0, "DRV8323 thermal pad"), ("U3", "B", 1.0, "DRV8316 thermal pad"),
              ("U4", "B", 1.0, "DRV8316 thermal pad")]
KEEPOUT = [((0.0, 0.0, 85.0, 18.5), "B", "front power band: L4 is solid GND under the L3 VBAT band (memo 3.1)")]

# ------------------------------------------------------------------ weapon bridge (attempt 1 cells, +10 mm grow)
CELL = {"C": 45.5, "B": 58.0, "A": 70.5}
FETS = {"C": ("Q5", "Q6", "RS3", "C31", "JW3", "NT3"), "B": ("Q3", "Q4", "RS2", "C26", "JW2", "NT2"),
        "A": ("Q1", "Q2", "RS1", "C25", "JW1", "NT1")}
EXPLICIT = {}
for ph, x0 in CELL.items():
    hs, ls, rs, cap, jw, nt = FETS[ph]
    EXPLICIT[ls] = (x0 + 3.0, 9.05, 90, T, f"phase {ph} low side: drain tab to the phase strip at the front, source pins to its shunt {rs} behind")
    EXPLICIT[hs] = (x0 + 9.2, 9.25, 270, T, f"phase {ph} high side: source pins to the phase strip, drain tab (VBAT) to its 10 uF {cap} behind")
    EXPLICIT[jw] = (x0 + 6.1, 2.75, 0, T, f"phase {ph} motor wire: front edge (drum side), in front of the phase strip")
    EXPLICIT[rs] = (x0 + 3.2, 15.35, 0, T, f"phase {ph} shunt: behind {ls}'s source pins, GND pad toward {cap}")
    EXPLICIT[nt] = (x0 + 3.6, 13.85 if ph != "C" else 16.85, 0, T, f"Kelvin tie SN{ph}: at {rs}'s GND pad inner edge (DESIGN 6.3)")
    # 1210 (v2): 0.3 mm further from the shunt than attempt 1's 1206 (review/v2_parts/adversarial/bridge_caps_1210.md)
    EXPLICIT[cap] = (x0 + 8.9, 15.5, 270, T, f"phase {ph} bridge 10 uF 1210: VBAT pad on {hs}'s drain tab, GND pad beside {rs}'s GND pad (commutation loop, DESIGN 6.1)")

EXPLICIT.update({
    "MH1": (3.0, 3.0, 0, T, "M2 hole, front-left corner"),
    "MH2": (82.0, 3.0, 0, T, "M2 hole, front-right corner"),
    "MH3": (3.0, 32.0, 0, T, "M2 hole, rear-left corner"),
    "MH4": (82.0, 32.0, 0, T, "M2 hole, rear-right corner"),
    # pack path along the front-left: JBAT1 -> Q7 -> Q8 -> RS4 -> C1 -> bridge
    "JBAT1": (8.75, 3.25, 0, T, "BAT+ wire: front-left, first in the pack path, beside Q7's drain tab"),
    "JBAT2": (3.25, 8.75, 0, T, "BAT- wire: left edge next to BAT+ (the pair leaves together)"),
    "Q7": (15.9, 3.7, 180, T, "inrush FET: drain tab toward JBAT1, source pins toward Q8 (common source PSW_S); hot, top"),
    "Q8": (23.8, 3.7, 0, T, "reverse FET: source pins toward Q7, drain tab (VBAT_SW) against RS4 pad 1; top"),
    "RS4": (32.8, 3.5, 0, T, "pack shunt: pad 1 on Q8's drain tab, pad 2 (VBAT) toward C1/D1 and the bridge"),
    "D1": (41.0, 3.3, 180, T, "bus TVS: front strip between RS4's VBAT pad and the bridge"),
    "C1": (37.8, 12.1, 180, T, "330 uF bulk: VBAT pad (right) toward the bridge and RS4, GND pad (left); 10.5 mm tall, top"),
    # drive left: U3 at the left edge, outputs west to JL, VM pins front to R302
    "U3": (9.5, 24.3, 270, T, "drive L DRV8316: outputs face the JL holes (west), VM pins face R302 (front), SPI/CSA pins face east (MCU); hot, top"),
    "R302": (9.5, 13.9, 180, T, "drive L VM feed 0.1R: in the front band so U3's front stays free for its VM/CP decoupling (within 2 mm, DESIGN 6.6); VM pad (left) toward U3's VM pins, VBAT pad (right) on the VBAT feed from C1 (L3/L1, not through the bridge copper)"),
    "JL1": (2.5, 20.4, 0, T, "drive L phase A wire: left edge, level with U3's phase A outputs"),
    "JL2": (2.5, 24.0, 0, T, "drive L phase B wire: left edge"),
    "JL3": (2.5, 27.6, 0, T, "drive L phase C wire: left edge"),
    "J2": (10.5, 32.3, 0, T, "drive L sensor connector (vertical SH): rear edge behind U3"),
    # drive right: U4 next to U3, outputs west to the JR column between the cells
    "U4": (22.5, 23.5, 0, T, "drive R DRV8316: control pins (INH, nFAULT, DRVOFF) face the MCU (east), outputs face the JR holes on the rear edge, VM pins face the gap to U3 where its VM caps sit, SPI/CSA pins face the front; hot, top"),
    "R402": (21.5, 13.9, 180, T, "drive R VM feed 0.1R: in the front band (U4's front free for its decoupling); VM pad (left) toward U4's VM pins, VBAT pad (right) on the VBAT feed from C1"),
    "JR1": (18.6, 31.3, 0, T, "drive R phase A wire: rear edge behind U4 (right motor cable crosses the robot, user OK 2026-09-29)"),
    "JR2": (22.5, 31.3, 0, T, "drive R phase B wire: rear edge"),
    "JR3": (26.4, 31.3, 0, T, "drive R phase C wire: rear edge"),
    "J3": (80.5, 23.5, 90, T, "drive R sensor connector (vertical SH): rear-right edge, off the drive cells (their fan-out is the congested part); nearer the right motor"),
    # MCU and weapon driver
    "U1": (43.5, 26.25, 180, T, "STM32G474: rear centre, rotated 180 (pins 33-48 face the drives, pins 1-16 face U2/J1; kicad/v2/pinsolve.py)"),
    "U2": (63.5, 23.0, 180, T, "DRV8323RH: behind the middle bridge cell, rotated 180: B/C gate pins face the bridge, A pins face cell A, CSA/straps face the MCU, buck pins at its rear-right corner; hot, top"),
    # header and balance lead
    "J1": (75.3, 23.0, 90, B, "header to the compute board (bottom, rear-right): beside U2's thermal-via field, under the buck; +5V close, MCU nets west"),
    "U5": (76.0, 33.0, 0, T, "3.3 V LDO: rear-right corner beside the buck output (+5V) and over J1"),
    "J4": (58.5, 31.6, 0, T, "balance lead (vertical XH): rear edge behind the MCU/U2 gap, so U2's rear-right corner stays free for the buck input loop (DESIGN 6.7); BMS parts under it on the bottom"),
})

# ------------------------------------------------------------------ regions for the anchored parts (per block, side)
REGION = {
    (T, "PSW"): (0.0, 0.0, 31.0, 13.6), (T, "BUS"): (24.0, 0.0, 44.6, 18.5), (T, "INA"): (22.0, 0.0, 44.6, 18.5),
    (T, "BRIDGE"): (44.5, 0.0, 85.0, 18.7), (T, "PDIV"): (44.5, 0.0, 85.0, 20.0),
    (T, "U3"): (0.0, 13.5, 15.0, 35.0), (T, "VML"): (0.0, 13.5, 15.0, 35.0), (T, "SENL"): (0.0, 13.5, 15.5, 35.0),
    (T, "U4"): (13.5, 13.5, 31.0, 35.0), (T, "VMR"): (13.5, 13.5, 31.0, 35.0), (T, "SENR"): (64.0, 18.5, 85.0, 35.0),
    (T, "DRVOFF"): (13.5, 13.5, 33.0, 35.0),
    (T, "MCU"): (31.0, 18.0, 52.0, 35.0), (T, "LDO"): (31.0, 18.0, 58.0, 35.0), (T, "CSAF"): (31.0, 18.0, 52.0, 35.0),
    (T, "WANA"): (31.0, 18.0, 58.0, 35.0), (T, "LED"): (31.0, 18.0, 85.0, 35.0),
    (T, "U2"): (49.0, 18.5, 70.0, 30.0), (T, "WNF"): (48.0, 18.5, 70.0, 35.0), (T, "AND"): (48.0, 18.5, 70.0, 35.0),
    (T, "BUCK"): (58.0, 18.5, 80.0, 35.0), (T, "BMS"): (44.0, 24.0, 68.0, 35.0), (T, "ARM"): (48.0, 18.5, 85.0, 35.0),
    (T, "J1"): (48.0, 18.5, 85.0, 35.0), (T, "TP"): (0.0, 18.5, 85.0, 35.0),
    (B, "SENL"): (0.0, 18.5, 15.5, 35.0), (B, "U3"): (0.0, 18.5, 15.5, 35.0),
    (B, "SENR"): (56.0, 18.5, 85.0, 35.0), (B, "U4"): (14.5, 18.5, 31.0, 35.0), (B, "DRVOFF"): (14.5, 18.5, 33.0, 35.0),
    (B, "MCU"): (31.0, 18.5, 50.0, 35.0), (B, "CSAF"): (31.0, 18.5, 50.0, 35.0), (B, "WANA"): (31.0, 18.5, 52.0, 35.0),
    (B, "LDO"): (31.0, 18.5, 52.0, 35.0), (B, "LED"): (31.0, 18.5, 85.0, 35.0), (B, "INA"): (31.0, 18.5, 50.0, 35.0),
    (B, "AND"): (48.0, 18.5, 70.0, 30.0), (B, "WNF"): (48.0, 18.5, 70.0, 35.0), (B, "PDIV"): (44.0, 18.5, 70.0, 30.0),
    (B, "J1"): (58.0, 18.5, 85.0, 35.0), (B, "ARM"): (56.0, 18.5, 85.0, 35.0), (B, "BMS"): (44.0, 24.0, 68.0, 35.0),
    (B, "TP"): (0.0, 18.5, 85.0, 35.0), (B, "ARM"): (0.0, 18.5, 85.0, 35.0), (B, "BRIDGE"): (44.0, 18.5, 85.0, 35.0),
}
# per-part overrides: (side, anchor) - where the automatic rule would pick badly
OVERRIDE = {
    "TH1": (T, ("Q3", "5")),        # FET NTC on phase B's high-side drain copper (moved off C26's side, 1210 fit)
    "C9": (T, ("J4", "5")), "D5": (T, ("J4", "1")),
    # buck loop (DESIGN 6.7): VIN cap at pin 47, output caps at L1's +5V pad
    "C27": (T, ("U2", "47")), "C29": (T, ("L1", "2")), "C30": (T, ("L1", "2")),
    # DRV8316 VM bulk at the VM pins (DESIGN 6.6: within 2 mm)
    "C302": (T, ("U3", "10")), "C308": (T, ("U3", "11")), "C402": (T, ("U4", "10")), "C408": (T, ("U4", "11")),
    "R15": (T, ("C1", "1")), "TP10": (T, ("C1", "1")),
    "D3": (B, ("J1", "1")), "R62": (B, ("J1", "1")),
    # test pads: a strip on the bottom between the drive cells (reachable, off every fan-out; memo 3.2)
    **{f"TP{i}": (B, (10.0, 19.6)) for i in (1, 2, 3, 4, 5)}, **{f"TP{i}": (B, (23.0, 19.6)) for i in (6, 7, 8, 9, 11, 12)},
}
FIRST = {"C302", "C308", "C402", "C408", "C27"}   # loop-critical: placed before the other anchored parts

# ------------------------------------------------------------------ anchored parts, generated
spec = importlib.util.spec_from_file_location("mbd", MB / "design" / "motor_board.py")
mbd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mbd)
PARTS = mbd.PARTS
RAILS = {"GND", "+3V3", "+3V3A", "+5V", "VBAT", "NC"}
net_pins = defaultdict(list)
for ref, p in PARTS.items():
    for num, (_, net) in p["pins"].items():
        net_pins[net].append((ref, num))


def desc_anchor(ref):
    m = re.search(r"\b(U\d+)\b[^;.]*?\bpins? (\d+)", PARTS[ref]["desc"])
    if m and m.group(1) in PARTS and m.group(2) in PARTS[m.group(1)]["pins"]:
        return (m.group(1), m.group(2))
    return None


def ref_anchor(ref, placed):
    """description names an IC but no pin ("U9 VCC"): that IC's pad on a net this part shares (not GND if possible)"""
    m = re.search(r"\b(U\d+)\b", PARTS[ref]["desc"])
    if not m or m.group(1) not in placed:
        return None
    ic = m.group(1)
    mine = {net for _, net in PARTS[ref]["pins"].values()}
    pads = [(num, net) for num, (_, net) in PARTS[ic]["pins"].items() if net in mine]
    pads.sort(key=lambda nn: nn[1] == "GND")
    return (ic, pads[0][0]) if pads else None


def net_anchor(ref, placed):
    best = None
    for num, (_, net) in PARTS[ref]["pins"].items():
        if net in RAILS or net.startswith("unconnected"):
            continue
        others = [(r, n) for r, n in net_pins[net] if r != ref and r in placed]
        if not others:
            continue
        others.sort(key=lambda rn: (0 if rn[0][0] in "UQJ" else 1, rn[0]))
        k = len(net_pins[net])
        if best is None or k < best[0]:
            best = (k, others[0])
    return best[1] if best else None


def block_ic(ref):
    b = BLOCK_OF.get(ref)
    ics = [r for r in PARTS if BLOCK_OF.get(r) == b and r[0] == "U"]
    return ics[0] if ics else None


ANCHORED = []
placed = set(EXPLICIT)
todo = [r for r in PARTS if r not in EXPLICIT and PARTS[r]["footprint"]]
for _ in range(6):
    left = []
    for ref in todo:
        side, anchor = OVERRIDE.get(ref, (None, None))
        side = side or FP.side_of(ref)
        anchor = anchor or desc_anchor(ref) or ref_anchor(ref, placed) or net_anchor(ref, placed)
        if anchor is None:
            left.append(ref)
            continue
        if isinstance(anchor, tuple) and isinstance(anchor[0], str) and anchor[0] not in placed:
            left.append(ref)
            continue
        region = REGION.get((side, BLOCK_OF.get(ref)))
        ANCHORED.append((ref, side, anchor, (0, 90, 180, 270), f"near {anchor}", region))
        placed.add(ref)
    todo = left
for ref in todo:            # no placed neighbour on a specific net: its block's IC
    side = FP.side_of(ref)
    ic = block_ic(ref) or "U1"
    ANCHORED.append((ref, side, ic, (0, 90, 180, 270), f"near {ic} (block)", REGION.get((side, BLOCK_OF.get(ref)))))
# decoupling first (IC pins), then the rest, so the loop-critical parts get the closest spots
ANCHORED.sort(key=lambda a: 0 if a[0] in FIRST else 1 if (isinstance(a[2], tuple) and a[2][0] in EXPLICIT and desc_anchor(a[0])) else 2)

if __name__ == "__main__":
    for a in ANCHORED:
        print(a[0], a[1], a[2], a[5])
    print(len(EXPLICIT), "explicit,", len(ANCHORED), "anchored")
