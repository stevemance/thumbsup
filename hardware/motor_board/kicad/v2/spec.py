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
KEEPOUT = [((0.0, 0.0, 85.0, 18.5), "B", "front power band: L4 is solid GND under the L3 VBAT band (memo 3.1)"),
           # fan-out escapes (first Freerouting trial: anchored parts sealed these pin rows)
           ((67.7, 20.8, 69.4, 23.7), "T", "U2 phase-A gate/sense pins 8-12: escape east then north to cell A"),
           ((13.5, 22.0, 14.6, 26.6), "T", "U3 SPI/CSA/nCS pins 33-40: escape east"),
           ((6.4, 27.3, 12.6, 28.1), "T", "U3 control pins 21-32 (INH, nFAULT, DRVOFF): escape rear"),
           ((20.3, 18.8, 24.7, 19.5), "T", "U4 SPI/CSA/nCS pins 33-40: escape front"),
           ((25.5, 20.9, 26.4, 26.6), "T", "U4 control pins 21-32: escape east to the MCU"),
           ((58.2, 20.8, 59.32, 25.6), "T", "U2 CSA/nFAULT/ENABLE pins 24-33: escape west to the MCU"),
           ((4.0, 18.5, 33.0, 27.5), "B", "drive-to-MCU escape corridor on L4 (U3/U4 SPI, CSA, control): no bottom parts"),
           ((29.7, 18.0, 31.3, 34.6), "T", "MCU fan-out ring (west)"), ((44.7, 18.0, 46.3, 34.6), "T", "MCU fan-out ring (east)"),
           ((31.3, 18.0, 44.7, 19.55), "T", "MCU fan-out ring (front)"), ((31.3, 33.0, 44.7, 34.6), "T", "MCU fan-out ring (rear)")]

# ------------------------------------------------------------------ weapon bridge (attempt 1 cells, +10 mm grow)
CELL = {"C": 45.5, "B": 58.6, "A": 71.1}   # B, A +0.6 mm: opens the C|B door for phase B's gate pair (README_bridge.md)
FETS = {"C": ("Q5", "Q6", "RS3", "C31", "JW3", "NT3"), "B": ("Q3", "Q4", "RS2", "C26", "JW2", "NT2"),
        "A": ("Q1", "Q2", "RS1", "C25", "JW1", "NT1")}
EXPLICIT = {}
for ph, x0 in CELL.items():
    hs, ls, rs, cap, jw, nt = FETS[ph]
    EXPLICIT[ls] = (x0 + 3.0, 9.05, 90, T, f"phase {ph} low side: drain tab to the phase strip at the front, source pins to its shunt {rs} behind")
    EXPLICIT[hs] = (x0 + 9.2, 9.25, 270, T, f"phase {ph} high side: source pins to the phase strip, drain tab (VBAT) to its 10 uF {cap} behind")
    EXPLICIT[jw] = (x0 + 6.1, 2.75, 0, T, f"phase {ph} motor wire: front edge (drum side), in front of the phase strip")
    EXPLICIT[rs] = (x0 + 3.2, 15.35, 0, T, f"phase {ph} shunt: behind {ls}'s source pins, GND pad toward {cap}")
    EXPLICIT[nt] = (x0 + 3.9, 16.85, 0, T, f"Kelvin tie SN{ph}: at the rear of {rs}'s GND pad inner edge; its SN pad (right side of the pad gap) carries the SN via to L4, GL passes on the gap's left side (README_bridge.md)")
    # 1210 (v2): 0.3 mm further from the shunt than attempt 1's 1206 (review/v2_parts/adversarial/bridge_caps_1210.md)
    EXPLICIT[cap] = (x0 + 8.9, 15.5, 270, T, f"phase {ph} bridge 10 uF 1210: VBAT pad on {hs}'s drain tab, GND pad beside {rs}'s GND pad (commutation loop, DESIGN 6.1)")

EXPLICIT["JW1"] = (76.6, 2.75, 0, T, "phase A motor wire: stays at x 76.6 when cell A moves +0.6 (clear of MH2's washer zone); still bridges Q2's tab and Q1's source pins")
# weapon gate/Kelvin corridors (README_bridge.md): anchored parts stay out of the L1 gate/Kelvin paths and of the L4
# Kelvin / phase-C gate-pair run to U2's in-pad vias
KEEPOUT += [((46.9, 17.85, 59.3, 19.3), "T", "bridge: GLC and the phase-B gate pair, west of U2"),
            ((59.3, 17.85, 67.7, 19.83), "T", "bridge: U2 front fan-out strip (GLC, GHB, SHB, GLB)"),
            ((67.7, 20.9, 70.6, 23.55), "T", "bridge: phase-A bundle into U2 pins 8-12"),
            ((69.9, 19.4, 73.2, 22.2), "T", "bridge: phase-A bundle (diagonal)"),
            ((72.2, 17.85, 75.8, 20.2), "T", "bridge: phase-A bundle leaving RS1"),
            ((74.4, 17.85, 77.8, 19.0), "T", "bridge: phase-A gate pair from its lane vias"),
            ((77.8, 17.85, 79.3, 18.5), "T", "bridge: phase-A gate pair lane vias"),
            ((57.65, 5.5, 58.66, 13.0), "T", "bridge: phase-B gate pair in the C|B channel (FET row)"),
            ((56.04, 13.0, 57.76, 17.85), "T", "bridge: phase-B gate pair in the C|B channel (shunt row)"),
            ((45.8, 18.5, 67.0, 20.3), "B", "bridge: L4 Kelvin C/B and phase-C gate pair to U2's in-pad vias (over L3 GND)")]

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
    "U1": (38.0, 26.25, 180, T, "STM32G474: rear centre, rotated 180 (pins 33-48 face the drives, pins 1-16 face U2/J1; kicad/v2/pinsolve.py)"),
    "U2": (63.5, 24.0, 180, T, "DRV8323RH: behind the middle bridge cell, rotated 180: B/C gate pins face the bridge, A pins face cell A, CSA/straps face the MCU, buck pins at its rear-right corner; hot, top"),
    # header and balance lead
    # rear band, second pass (2026-09-30): J1 behind the MCU's UART/SWD/NRST pins, J4 + BMS as one block in the
    # rear-right corner, the buck on U2's east side (the first pass had J4 in the rear centre and J1 40 mm away)
    "J1": (52.5, 30.95, 90, B, "header to the compute board (bottom, rear centre): right behind the MCU's UART (pins 59/60), SWD (49/50) and NRST (7) pins; +5V from the buck beside it; MCU nets west"),
    "J4": (69.7, 31.6, 0, T, "balance lead (vertical XH): rear-right corner with the BMS (U8 and its filters on the bottom under it); off the MCU-J1 path loop (DESIGN 6.7); BMS parts under it on the bottom"),
    # drive fan-out fixes (P3 pre-route, kicad/gen/v2_drive.py, 2026-09-30)
    "R400": (19.25, 17.895, 0, T, "drive R buck resistor: at U4's front-left corner (U3's R300 had this spot), fed from U4's west pins 3/5; keeps U4's SPI/CSA front edge free"),
    "R300": (22.355, 16.75, 0, T, "drive L buck resistor: in the power band in front of U4 (R400's old spot; U3's own front has no room between R302 and the VM/CP caps); reached on L1 along the band corridor (FBBK) and by an L4 hop (SWBK)"),
    "R401": (27.45, 25.7, 0, T, "drive R nFAULT pull-up (to AVDD): top, between C405 and TP8, at U4 pins 22/25 (was on the bottom behind the drive-to-MCU bundle)"),
    "R81": (28.75, 22.0, 270, T, "drive R SOB filter resistor: top, west of U1 pin 34 between C405 and the MCU ring (was at U1's rear-west corner, 12 mm from its cap C91)"),
    "C305": (8.15, 28.88, 180, T, "drive L AVDD cap: right behind U3 pin 25 (AVDD pad under the pin), between the rear-escape keep-out and J2"),
    # held where the anchored pass put them (R81's move would otherwise pull R82 into its old corner)
    "R82": (29.15, 24.35, 270, T, "drive R SOC filter resistor: top, west of U1 pin 35 below R81 (under U1 it was unreachable from U4 past the bottom decoupling)"),
    "C92": (38.3, 24.25, 270, B, "drive R SOC filter cap under U1 (pinned: pre-routed)"),
    "R60": (39.5, 24.75, 90, B, "+3V3A filter (pinned where the anchored pass placed it)"),
    # region pre-routes (kicad/gen/v2_ilock.py, 2026-09-30)
    "R45": (56.3, 22.75, 90, T, "U2 IDRIVE strap: R46's old spot (pin 30 IDRIVE sits above pin 31 VDS, so the two straps' stubs crossed)"),
    "R46": (57.05, 24.5, 180, T, "U2 VDS strap: R45's old spot, straight west of pin 31"),
})

# ------------------------------------------------------------------ regions for the anchored parts (per block, side)
REGION = {
    (T, "PSW"): (0.0, 0.0, 31.0, 13.6), (T, "BUS"): (24.0, 0.0, 44.6, 18.5), (T, "INA"): (22.0, 0.0, 44.6, 18.5),
    (T, "BRIDGE"): (44.5, 0.0, 85.0, 18.7), (T, "PDIV"): (44.5, 0.0, 85.0, 22.5),   # to y 22.5: the strip behind the cells is the gate corridor now
    (T, "U3"): (0.0, 13.5, 15.0, 35.0), (T, "VML"): (0.0, 13.5, 15.0, 35.0), (T, "SENL"): (0.0, 13.5, 15.5, 35.0),
    (T, "U4"): (13.5, 13.5, 31.0, 35.0), (T, "VMR"): (13.5, 13.5, 31.0, 35.0), (T, "SENR"): (64.0, 18.5, 85.0, 35.0),
    (T, "DRVOFF"): (13.5, 13.5, 33.0, 35.0),
    (T, "MCU"): (31.0, 18.0, 52.0, 35.0), (T, "LDO"): (44.0, 26.0, 62.0, 35.0), (T, "CSAF"): (31.0, 18.0, 52.0, 35.0),
    (T, "WANA"): (31.0, 18.0, 58.0, 35.0), (T, "LED"): (31.0, 18.0, 85.0, 35.0),
    (T, "U2"): (49.0, 18.5, 70.0, 30.0), (T, "WNF"): (48.0, 18.5, 70.0, 35.0), (T, "AND"): (48.0, 18.5, 70.0, 35.0),
    (T, "BUCK"): (64.0, 19.4, 79.5, 28.2), (T, "BMS"): (60.0, 26.0, 80.0, 35.0), (T, "ARM"): (48.0, 18.5, 85.0, 35.0),
    (T, "J1"): (48.0, 18.5, 85.0, 35.0), (T, "TP"): (0.0, 0.0, 85.0, 35.0),
    (B, "SENL"): (0.0, 18.5, 15.5, 35.0), (B, "U3"): (0.0, 18.5, 15.5, 35.0),
    (B, "SENR"): (64.0, 18.5, 85.0, 28.2), (B, "U4"): (14.5, 18.5, 31.0, 35.0), (B, "DRVOFF"): (14.5, 18.5, 33.0, 35.0),
    (B, "MCU"): (31.0, 18.5, 50.0, 35.0), (B, "CSAF"): (31.0, 18.5, 50.0, 35.0), (B, "WANA"): (31.0, 18.5, 52.0, 35.0),
    (B, "LDO"): (31.0, 18.5, 52.0, 35.0), (B, "LED"): (31.0, 18.5, 85.0, 35.0), (B, "INA"): (31.0, 18.5, 50.0, 35.0),
    (B, "AND"): (48.0, 18.5, 70.0, 30.0), (B, "WNF"): (48.0, 18.5, 70.0, 35.0), (B, "PDIV"): (44.0, 18.5, 70.0, 30.0),
    (B, "J1"): (44.0, 26.5, 62.0, 35.0), (B, "ARM"): (44.0, 18.5, 62.0, 35.0), (B, "BMS"): (60.0, 28.2, 80.0, 35.0),
    (B, "TP"): (0.0, 18.5, 85.0, 35.0), (B, "ARM"): (0.0, 18.5, 85.0, 35.0), (B, "BRIDGE"): (44.0, 18.5, 85.0, 35.0),
}
# per-part overrides: (side, anchor) - where the automatic rule would pick badly
OVERRIDE = {
    "JP2": (T, (71.5, 33.3)),         # keep the right-sensor jumper at the rear-right (the bridge keep-outs pushed it to the front band)
    "TH1": (T, ("Q3", "5")),        # FET NTC on phase B's high-side drain copper (moved off C26's side, 1210 fit)
    "C9": (T, ("J4", "5")), "D5": (T, ("J4", "1")),
    # buck loop (DESIGN 6.7): VIN cap at pin 47, output caps at L1's +5V pad
    "C27": (T, ("U2", "47")), "C29": (T, ("L1", "2")), "C30": (T, ("L1", "2")),
    # DRV8316 VM bulk at the VM pins (DESIGN 6.6: within 2 mm)
    "C302": (T, ("U3", "10")), "C308": (T, ("U3", "11")), "C402": (T, ("U4", "10")), "C408": (T, ("U4", "11")),
    "R15": (T, ("C1", "1")), "TP10": (T, ("C1", "1")),
    "D3": (B, ("J1", "1")), "R62": (B, ("J1", "1")),
    # test pads: a strip on the bottom between the drive cells (reachable, off every fan-out; memo 3.2)
    # test pads on the TOP (flat pads; the top stays reachable with the stack assembled), near their nets; the first
    # trial had them on the bottom right in the drive-to-MCU escape corridor
    **{f"TP{i}": (T, None) for i in (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12)},
}
# every DRV8316 / DRV8323 decoupling part on the pin it serves (auto-anchoring put some on the wrong side)
for _u, _n in (("U3", 300), ("U4", 400)):
    OVERRIDE.update({f"C{_n}": (T, (_u, "9")), f"C{_n + 1}": (T, (_u, "11")), f"C{_n + 3}": (T, (_u, "8")),
                     f"C{_n + 4}": (T, (_u, "7")), f"C{_n + 5}": (T, (_u, "25")), f"C{_n + 6}": (T, (_u, "37")),
                     f"R{_n}": (T, (_u, "5")), f"C{_n + 7}": (T, (_u, "3")), f"R{_n + 1}": (B, (_u, "22"))})
OVERRIDE.update({"C20": (T, ("U2", "4")), "C21": (T, ("U2", "5")), "C22": (T, ("U2", "36")), "C23": (T, ("U2", "26")),
                 "C24": (T, ("U2", "6")), "R44": (T, ("U2", "29")), "R45": (T, ("U2", "30")), "R46": (T, ("U2", "31")),
                 "C28": (T, ("U2", "44")), "C10": (T, ("U2", "48")), "R20": (T, ("U2", "1")), "R21": (T, ("U2", "1"))})
FIRST = {"C302", "C308", "C402", "C408", "C27", "C300", "C301", "C303", "C304", "C400", "C401", "C403", "C404",
         "C20", "C21", "C24", "C22", "C23", "C28", "L1", "D2", "C29", "C30"}   # loop-critical: placed before the other anchored parts

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
        if ref.startswith("TP") and ref in OVERRIDE and anchor is None:
            anchor = net_anchor(ref, placed) or ("U1", "1")
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
