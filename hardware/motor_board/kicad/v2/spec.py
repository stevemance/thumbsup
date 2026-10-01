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
           ((67.7, 20.8, 69.4, 23.27), "T", "U2 phase-A gate/sense pins 8-12: escape east then north to cell A"),
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
            ((67.7, 20.9, 70.6, 23.27), "T", "bridge: phase-A bundle into U2 pins 8-12"),
            ((69.9, 19.4, 73.2, 22.2), "T", "bridge: phase-A bundle (diagonal)"),
            ((72.2, 17.85, 75.8, 20.2), "T", "bridge: phase-A bundle leaving RS1"),
            ((74.4, 17.85, 77.8, 19.0), "T", "bridge: phase-A gate pair from its lane vias"),
            ((77.8, 17.85, 79.3, 18.5), "T", "bridge: phase-A gate pair lane vias"),
            ((57.65, 5.5, 58.66, 13.0), "T", "bridge: phase-B gate pair in the C|B channel (FET row)"),
            ((56.04, 13.0, 57.76, 17.85), "T", "bridge: phase-B gate pair in the C|B channel (shunt row)"),
            ((45.8, 18.5, 67.0, 20.3), "B", "bridge: L4 Kelvin C/B and phase-C gate pair to U2's in-pad vias (over L3 GND)"),
            ((81.8, 20.4, 82.6, 26.6), "B", "r2: J3 pad via column (J3's pads are on the top)"),
            ((60.6, 27.7, 63.8, 30.0), "B", "r2: U2 gate-input (INL) via field behind pins 38/40/42"),
            ((59.3, 27.0, 60.4, 30.0), "B", "r2: INL lines from the via field north to U6")]

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
    # drive CSA filters under the MCU's west half: held where the first pass had them (kicad/gen/v2_drive.py lands on
    # their pads; the second pass released the other rear-stage pins and the anchored pass moved these too)
    "R71": (33.65, 28.3, 270, B, "drive L SOB filter resistor (pinned: v2_drive copper)"),
    "R72": (34.9, 24.55, 270, B, "drive L SOC filter resistor (pinned: v2_drive copper)"),
    "C81": (35.05, 26.25, 0, B, "drive L SOB filter cap (pinned: v2_drive copper)"),
    "C82": (36.05, 24.75, 90, B, "drive L SOC filter cap (pinned: v2_drive copper)"),
    "R80": (37.25, 19.1, 0, B, "drive R SOA filter resistor (pinned: v2_drive copper)"),
    "C90": (39.25, 19.35, 0, B, "drive R SOA filter cap (pinned: v2_drive copper)"),
    "C91": (35.3, 23.0, 0, B, "drive R SOB filter cap (pinned: v2_drive copper)"),
    "R70": (33.65, 24.3, 270, B, "drive L SOA filter resistor (pinned: v2_drive copper)"),
    "C80": (33.55, 26.25, 270, B, "drive L SOA filter cap (pinned: v2_drive copper)"),
    "R50": (31.8, 28.5, 180, B, "DRV_OFF pull-up under U1 pin 45 (pinned: v2_drive's in-pad via)"),
    "C62": (32.8, 30.0, 0, B, "MCU decoupling (pinned at its first-pass spot)"),
})

# ------------------------------------------------------------------ rear band, second pass (2026-09-30, r2)
# U2's east side and the 5 V buck (DESIGN 6.7).  J3 moves 1.75 mm east (courtyard to x 84.9, pads 0.5 mm from the
# edge) so the buck fits between U2 and J3: U2's charge-pump / VM caps in two rows at pins 3-7 (C24 at the VM pins
# 6/7, VCP / CPH / CPL leave the pins as a staircase of L1 tracks), the input cap C27 behind C21 (VBAT pads joined),
# L1 against J3 with D2 (cathode over L1's SW pad) and the output cap C29 (GND pad over D2's anode) above it, the
# bootstrap cap C28 beside the SW node.  FB divider and EN parts on the bottom (not loop parts, away from SW).
EXPLICIT.update({
    "J3": (82.25, 23.5, 90, T, "drive R sensor connector (vertical SH): rear-right edge, 1.75 mm further east than the first pass so the buck fits between U2 and J3 (contacts 0.5 mm from the edge)"),
    "C24": (69.205, 24.05, 0, T, "U2 VM bypass: VBAT pad on pins 6/7, GND pad east (row 1 of U2's east caps)"),
    "C20": (69.205, 26.85, 180, T, "U2 flying cap: CPL pad at pin 3, CPH pad east (pin 4's track turns down behind the VCP track) (row 2)"),
    "C21": (72.33, 24.05, 0, T, "U2 VCP cap: VCP pad at the end of pin 5's track under C24, VBAT pad joined to C27's"),
    "C27": (72.6, 27.13, 0, T, "buck input cap (VIN pin 47 under J4's front edge): VBAT pad under C21's, GND pad toward L1"),
    "L1": (77.245, 25.835, 0, T, "buck inductor: against J3, SW pad west (D2's cathode right above it), +5V pad east"),
    "D2": (77.245, 22.345, 0, T, "buck catch diode: cathode on L1's SW pad, anode under C29's GND pad"),
    "C29": (77.845, 20.125, 0, T, "buck output cap: GND pad over D2's anode, +5V pad to L1 through D2's pad gap (L1/D2/C29 loop, DESIGN 6.7)"),
    "C28": (73.975, 21.725, 270, T, "buck bootstrap cap: CB pad (north) at the end of the CB track (under L1 / D2 through their pad gaps), SW pad (south) next to D2 cathode"),
    # FB divider under pin 1 (via in pin 1's pad), EN divider in the bottom strip between U2's thermal field and J4's
    # solder zone (pin 48 drops at a via behind the pin, under J4's front edge)
    "R21": (67.6, 25.6, 90, B, "buck FB divider low side: bottom west of U8, FB pad (south) next to the via in U2 pin 1"),
    "R20": (67.6, 23.55, 270, B, "buck FB divider high side: bottom north of R21 (FB pad south, +5V pad north; +5V by a short L3 hop from C29)"),
    "R5": (64.75, 27.75, 180, B, "buck EN pull-down: bottom strip behind U2, EN pad east at the via in pin 48"),
    "R4": (68.3, 27.95, 180, B, "buck EN divider high side: bottom strip behind U2, EN pad west at pin 48's via, VBAT pad east at a via on the VIN track"),
    "C10": (66.25, 28.6, 270, B, "buck EN cap: under pin 48's via"),
    # BMS (bottom, in front of J4): U8 with its cell pins facing J4 (CELL0-2 south, CELL3/4 + BAT east), I2C / REG
    # north; the series resistors in a row right in front of J4's solder zone, one per BAL pin
    "U8": (71.1, 22.5, 90, B, "cell monitor: bottom in front of J4 (cell pins south / east toward J4's BAL pins, I2C north to the vias west of TH1)"),
    "R7": (70.6, 27.575, 90, B, "BAL1 series R: CELL1 pad under C5 CELL1 pad"),
    "R8": (72.07, 27.575, 90, B, "BAL2 series R: CELL2 pad under C5's CELL2 pad"),
    "R9": (75.22, 27.575, 90, B, "BAL3 series R: CELL3 pad under C6's CELL3 pad"),
    "R10": (76.4, 27.575, 90, B, "BAL4 series R: CELL4 lead north along the east side to C7"),
    "R11": (75.85, 20.25, 90, B, "BAT filter R: north-east of U8 (BAT pad north toward U8 pins 16/17, BAL4 lead along the east side)"),
    "D5": (60.5, 32.6, 90, T, "CELL0 clamp: top west of J4, over R6 (CELL0 via between them)"),
    "C9": (57.9, 32.65, 90, T, "BMS BAT cap (1206, top): west of D5, BMS_BAT via to U8 on the bottom"),
    # right sensor: the VS jumper on the top in the front-right corner beside J3 (+5V from C29 next to it)
    "JP2": (83.4, 16.0, 90, T, "right sensor VS jumper: top, front-right corner beside J3 (C29's +5V, R_VSRC via to U12 under J3)"),
    # FET NTC on the L1 GND copper behind C26's GND pad (phase B's cap/shunt return)
    # BMS_BAT / CELL0 parts that must be on the top: west of J4, behind the gate-input bundle that leaves U2's rear row
    # westward (y 28.3-30.3); R6 behind J4 pin 1 (bottom, rear strip), its CELL0 lead north through J4's pin 1|2 gap
    "R6": (65.5, 34.2, 0, B, "BAL0 series R (0603, reverse-plug current, DESIGN 7.1): bottom behind J4 pin 1, CELL0 lead north through the pin 1|2 gap"),
    # LDO and the +5V bulk cap on the top above J1 (J1 is on the bottom; its +5V pins below), SWD / NRST test pads in a
    # row along the rear edge above J1's west end
    "U5": (54.6, 33.25, 0, T, "3.3 V LDO: top above J1's east half (+5V from J1 pins 1/2/13 and the buck trunk)"),
    "C69": (53.5, 30.95, 0, T, "LDO input cap: next to U5's +5V pins"),
    "C70": (55.75, 30.95, 0, T, "LDO output cap: next to U5's +3V3 pin"),
    "C30": (50.6, 33.95, 0, T, "+5V bulk at J1 (second buck output cap; the loop cap is C29 at L1)"),
    "TP12": (30.2, 31.55, 0, T, "GND test pad: top at the MCU's rear-west corner (no room east of the MCU)"),
    "TP5": (30.2, 33.7, 0, T, "GND test pad: top at the MCU's rear-west corner"),
    "TP11": (49.65, 31.85, 0, T, "+5V test pad: above J1, between the gate-input bundle and C30"),
    "TP2": (47.4, 33.95, 0, T, "SWDIO test pad: rear edge above J1's west end"),
    # drive / sense parts the drive pre-route lands next to
    "C64": (42.2, 33.75, 180, B, "MCU 4.7 uF (pinned: v2_drive's L_nCS via)"),
    # left sensor buffer off J2's pads / mounting tabs (its pins need via sites), between the drive's rear vias
    "U9": (12.3, 31.0, 90, B, "left sensor buffer: under J2's middle, clear of J2's mounting pads and the drive's rear-row vias"),
    "D8": (37.0, 31.0, 0, B, "right MTEMP clamp: under the MCU next to D7 (the left one), at the ADC end of R_MTEMP like D7 (no room under J3)"),
    "D7": (40.95, 31.0, 180, B, "left MTEMP clamp: under the MCU's rear-east corner beside D8"),
    "R117": (78.3, 33.3, 90, B, "right TEMPJ series R: rear strip between J4's solder zone and MH4"),
    "R113": (30.75, 33.1, 0, B, "left TEMPJ series R (first-pass spot; under the MCU it blocks v2_drive's L_SOC_F)"),
    "C7": (74.3, 23.1, 270, B, "CELL3/CELL4 cap: right at U8 pins 18 (CELL4, north pad) and 19/20 (CELL3, south pad)"),
    "C6": (74.4, 25.75, 180, B, "CELL2/CELL3 cap: between U8 and the R row, CELL3 pad under C7's"),
    "C5": (71.25, 25.75, 180, B, "CELL1/CELL2 cap: under U8 pins 1-4 (CELL1 pad west, CELL2 pad east)"),
    "C11": (73.4, 19.3, 0, B, "BMS REG cap: north of U8 at pin 15 (REG pad west), clear of the I2C pins"),
    "C4": (76.6, 23.45, 90, B, "CELL0/CELL1 cap: east of C6/C7 (no room at U8 pins 4/5 between the FB divider and C5)"),
    "R57": (83.75, 24.06, 0, B, "R_H1 pull-up: bottom under J3, R_H1 pad west at J3 pin 3's via, +3V3 pad east on the edge bar"),
    "R58": (83.75, 23.03, 0, B, "R_H2 pull-up: under J3 beside R57"),
    "R59": (83.75, 22.0, 0, B, "R_H3 pull-up: under J3 beside R58"),
    "R116": (81.15, 21.5, 90, B, "R_H3 series R: west of J3 pin 5's via"),
    "R115": (81.15, 23.5, 90, B, "R_H2 series R: west of J3 pin 4's via"),
    "R114": (81.15, 25.5, 90, B, "R_H1 series R: west of J3 pin 3's via"),
    "U10": (79.3, 22.9, 90, B, "right sensor buffer: bottom west of the series resistors (H1B / H2B / S3 on the south row, H3B / S1 / S2 north)"),
    "C49": (84.35, 25.55, 90, B, "R_VS cap: under J3 pin 1/2 east of the via column"),
    "U12": (82.8, 28.0, 270, B, "right VS switch: under J3 rear end (R_VS north toward J3 pin 1 via, R_VSRC south)"),
    "C48": (80.45, 28.4, 90, B, "R_VSRC cap: beside U12"),
    "U6": (57.5, 25.2, 180, B, "weapon AND gate: bottom west of U2 (INL outputs east toward the vias behind U2 pins 38/40/42)"),
    "R40": (59.75, 30.9, 90, B, "W_EN pull-down: bottom east of J1 (off the gate-input vias behind U2)"),
    "TP7": (55.3, 20.7, 0, T, "W_EN test pad: north of U2 straps (off the gate-input bus behind the MCU)"),
    "TH1": (69.3, 18.62, 0, T, "FET NTC: top behind C26's GND pad (phase B's commutation-cap / shunt GND copper; L2 GND below); W_NTC pad west"),
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
    (T, "J1"): (48.0, 18.5, 85.0, 35.0), (T, "TP"): (48.7, 19.8, 56.6, 26.3),
    (B, "SENL"): (0.0, 18.5, 15.5, 35.0), (B, "U3"): (0.0, 18.5, 15.5, 35.0),
    (B, "SENR"): (77.55, 18.5, 85.0, 35.0), (B, "U4"): (14.5, 18.5, 31.0, 35.0), (B, "DRVOFF"): (14.5, 18.5, 33.0, 35.0),
    (B, "MCU"): (31.0, 18.5, 50.0, 35.0), (B, "CSAF"): (31.0, 18.5, 50.0, 35.0), (B, "WANA"): (31.0, 18.5, 52.0, 35.0),
    (B, "LDO"): (31.0, 18.5, 52.0, 35.0), (B, "LED"): (31.0, 18.5, 85.0, 35.0), (B, "INA"): (31.0, 18.5, 50.0, 35.0),
    (B, "AND"): (46.0, 20.3, 59.9, 27.4), (B, "WNF"): (44.0, 20.3, 59.9, 27.4), (B, "PDIV"): (44.0, 18.5, 70.0, 30.0),
    (B, "J1"): (44.0, 20.3, 62.3, 35.0), (B, "BMS"): (66.9, 18.5, 77.5, 28.6),
    (B, "TP"): (0.0, 18.5, 85.0, 35.0), (B, "ARM"): (44.0, 20.3, 62.3, 35.0), (B, "BRIDGE"): (44.0, 18.5, 85.0, 35.0),
}
# per-part overrides: (side, anchor) - where the automatic rule would pick badly
OVERRIDE = {
    "C30": (T, ("J1", "2")), "U10": (B, ("J3", "4")), "U12": (B, ("J3", "1")), "D8": (B, ("J3", "6")),         # keep the right-sensor jumper at the rear-right (the bridge keep-outs pushed it to the front band)
    "TH1": (T, ("Q3", "5")),        # FET NTC on phase B's high-side drain copper (moved off C26's side, 1210 fit)
    "C9": (T, ("J4", "5")), "D5": (T, ("J4", "1")),
    # buck loop (DESIGN 6.7): VIN cap at pin 47, output caps at L1's +5V pad
    "C27": (T, ("U2", "47")), "C29": (T, ("L1", "2")),
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

# ------------------------------------------------------------------ r2: the pre-routed bridge + drive copper on L4 (and
# every via) blocks bottom parts (the anchored pass knows nothing of copper; out/r2v_drive.json is a dump of
# kicad/gen/out/exp/r2_drive made by r2/view.py)
import json as _json  # noqa: E402
import math as _math  # noqa: E402
_dump = HERE / "out" / "r2v_drive.json"
if _dump.exists():
    _D = _json.load(open(_dump))
    for _v in _D["vias"]:
        _r = _v["d"] / 2 + 0.15
        KEEPOUT.append(((_v["c"][0] - _r, _v["c"][1] - _r, _v["c"][0] + _r, _v["c"][1] + _r), "B", "pre-routed via"))
    for _t in _D["tracks"]:
        if _t["layer"] != "B" or max(_t["a"][1], _t["b"][1]) < 18.0:
            continue
        _h = _t["w"] / 2 + 0.15
        (_x0, _y0), (_x1, _y1) = _t["a"], _t["b"]
        if abs(_x0 - _x1) < 1e-6 or abs(_y0 - _y1) < 1e-6:
            KEEPOUT.append(((min(_x0, _x1) - _h, min(_y0, _y1) - _h, max(_x0, _x1) + _h, max(_y0, _y1) + _h), "B", "pre-routed L4 track"))
        else:
            _n = max(1, int(_math.hypot(_x1 - _x0, _y1 - _y0) / 0.4))
            for _k in range(_n + 1):
                _x, _y = _x0 + (_x1 - _x0) * _k / _n, _y0 + (_y1 - _y0) * _k / _n
                KEEPOUT.append(((_x - _h, _y - _h, _x + _h, _y + _h), "B", "pre-routed L4 track"))
