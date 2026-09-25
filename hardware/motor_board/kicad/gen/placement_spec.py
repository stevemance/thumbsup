"""Two-sided placement of the motor board (v2).  Coordinates in mm, board top view: x to the robot's right,
y toward the REAR (y = 0 is the front edge, facing the drum).  EXPLICIT entries give the courtyard centre,
rotation (KiCad degrees, top-view) and side; ANCHORED entries are put at the nearest free spot to an anchor
(a pad or a point), trying the listed rotations and preferring the one whose pads land nearest their nets.

Floorplan (top side):
    front edge (drum):  [MH1][JBAT2][U13 strip ........][D1] [JW_C]      [JW_B] [MH2?]  [JW_A] [MH2]
                        [JBAT1][Q7 ][Q8 ][RS4 ]        [ weapon bridge: 3 U-cells, phase C, B, A ]
                        [ J4  ][R302][    C1   ]       [ shunts + local 10 uF under each cell    ]
                        [     ][    ][         ]       [ U2 + buck ]              [ drive R: U4 ]
    rear edge (motors): [MH3][JL1-3][   U3    ]       [ U5, TPs  ]              [JR1-3]  [MH4]
Bottom side: the MCU, header J1, sensor connectors J2/J3 and every cool low-profile part.
"""
BW, BH = 75.0, 35.0
CORNER_R = 1.5
EDGE = 0.4          # anchored parts: courtyard to board edge (JLC adds rails on a board this size)
GAP = 0.1           # anchored parts: extra gap between courtyards (courtyards already carry 0.25 mm)
EDGE_OK = {"J4", "J2", "J3"}
OVERLAP_OK = {("NT2", "RS2")}   # net tie GND pad on the shunt's GND pad corner (same net)   # edge connectors may touch the edge (mating face flush with the edge)
T, B = "T", "B"
# soldering clearance around hand-soldered through-holes, both sides (review: iron tip + fillet; a bridge at J4 shorts a cell)
THT_CLEAR = {"JBAT": 2.0, "JW": 2.0, "JL": 1.5, "JR": 1.5, "J4": 1.5}
# thermal-via fields: nothing on the other side within 1 mm of these exposed pads (DESIGN 6.5 "full via array")
EP_KEEPOUT = [("U2", "B", 1.0, "DRV8323 thermal pad"), ("U3", "B", 1.0, "DRV8316 thermal pad"), ("U4", "B", 1.0, "DRV8316 thermal pad")]
# bottom routing corridor: the weapon gate/sense runs leave the FETs through vias and cross to U2 here (DRV8323 p75)
KEEPOUT = [((34.5, 8.5, 70.5, 19.0), "B", "weapon gate/sense via corridor between the bridge and U2"),
           ((49.3, 18.0, 58.9, 27.3), "B", "U2 fan-out and via field (U2 outline + the phase-A via strip on its right)"),
           ((20.0, 32.6, 27.5, 35.0), "B", "U3 logic-pin via escape (INHx, DRV_OFF, nFAULT, +3V3 behind U3)")]

# ------------------------------------------------------------------ weapon bridge (top, front right)
# U-cell per phase, left to right C, B, A (the order U2's pins come out in, U2 rotated 180 deg):
#   LS rot 90  = drain tab to the FRONT (phase node), source pins to the rear, gate pin at the rear-right corner
#   HS rot 270 = source pins to the FRONT (phase node), drain tab to the rear (VBAT), gate pin at the front-left
#   the phase node (HS pins + LS tab) is one short copper strip at the front, the phase wire hole right in front
#   of it; the LS source feeds its shunt directly behind it; the local 10 uF stands behind the HS drain with its
#   GND pad next to the shunt's GND pad: VBAT -> HS -> phase -> LS -> shunt -> cap is one compact U on L1 with
#   the L2 GND plane directly under it (DESIGN 6.1).
CELL = {"C": 35.5, "B": 48.0, "A": 60.5}
FETS = {"C": ("Q5", "Q6", "RS3", "C31", "JW3", "NT3"), "B": ("Q3", "Q4", "RS2", "C26", "JW2", "NT2"),
        "A": ("Q1", "Q2", "RS1", "C25", "JW1", "NT1")}
EXPLICIT = {}
for ph, x0 in CELL.items():
    hs, ls, rs, cap, jw, nt = FETS[ph]
    EXPLICIT[ls] = (x0 + 3.0, 9.05, 90, T, f"phase {ph} low side: drain tab faces the phase strip at the front, source pins face its shunt {rs} directly behind; hot part, top")
    EXPLICIT[hs] = (x0 + 9.2, 9.25, 270, T, f"phase {ph} high side: source pins face the phase strip at the front, drain tab (VBAT) faces its 10 uF {cap} behind; hot part, top")
    EXPLICIT[jw] = (x0 + 6.1, 2.75, 0, T, f"phase {ph} motor wire: at the front edge (drum side), directly in front of the phase strip joining {hs} source and {ls} drain")
    EXPLICIT[rs] = (x0 + 3.2, 15.35, 0, T, f"phase {ph} shunt: directly behind {ls}'s source pins (pad 1), GND pad 2 toward the cell centre next to {cap}'s GND pad; 0.8 W peak, top")
    EXPLICIT[nt] = (x0 + 4.3, 18.3, 0, T, f"Kelvin tie SN{ph}: directly behind the inner edge of {rs}'s GND pad, so the sense return starts at the shunt, not in the cap's return copper (DESIGN 6.3)")
    if ph == "B":
        EXPLICIT[nt] = (x0 + 3.6, 13.85, 0, T, "Kelvin tie SNB: GND pad on the inner-front corner of RS2's GND pad, sense pad in the gap between the shunt pads, so both B Kelvin vias sit in the gap and the pair leaves on L3 in front of U2's fan-out (routing)")
    if ph == "A":
        EXPLICIT[nt] = (x0 + 3.6, 13.85, 0, T, "Kelvin tie SNA: GND pad on the inner-front corner of RS1's GND pad, sense pad in the pad gap (its via there), in front of the SL via so the pair from U2's right side arrives in order (routing)")
    if ph == "C":
        EXPLICIT[nt] = (x0 + 3.6, 16.85, 0, T, "Kelvin tie SNC: GND pad on the inner-rear corner of RS3's GND pad, sense pad in the gap between the shunt pads (its via there), rear of the SL via so phase C's bottom-layer bundle arrives in order (routing)")
    EXPLICIT[cap] = (x0 + 8.6, 15.5, 270, T, f"phase {ph} bridge 10 uF: VBAT pad on {hs}'s drain tab, GND pad beside {rs}'s GND pad: closes the commutation loop on L1 (DESIGN 6.1)")

EXPLICIT.update({
    # mounting: corners where the floorplan allows (see PLACEMENT.md for the chassis mounting)
    "MH1": (3.0, 3.0, 0, T, "M2 stack/chassis hole, front-left corner"),
    "MH2": (BW - 2.8, 3.0, 0, T, "M2 stack/chassis hole, front-right corner (right of phase A's wire hole)"),
    "MH3": (3.0, 32.0, 0, T, "M2 stack/chassis hole, rear-left corner"),
    "MH4": (BW - 2.8, 32.0, 0, T, "M2 stack/chassis hole, rear-right corner (same x as MH2: the four holes form a rectangle)"),
    # battery entry (left end): pack path BAT+ -> Q7 -> Q8 -> RS4 -> VBAT runs left-to-right along the front
    "JBAT1": (3.2, 8.7, 0, T, "BAT+ wire: left edge (battery beside the board's left end), first in the pack path, next to Q7's drain"),
    "JBAT2": (9.2, 3.0, 0, T, "BAT- wire: 8.3 mm from BAT+ (the pair leaves together, twist it); GND joins the L2 plane at the hole"),
    "Q7": (10.0, 9.0, 180, T, "inrush FET: drain tab next to JBAT1, source pins toward Q8's (common source PSW_S; the two gate pins end up at opposite corners of the pair, so PSW_G reaches Q8's through a via); 1.1 mm pad gap to Q8 (JLC QFN-QFN 1.0 mm); 16 W peak at switch-on, top"),
    "Q8": (17.9, 9.0, 0, T, "reverse FET: source pins toward Q7's, drain tab (VBAT_SW) against RS4 pad 1; ~1 W at 22 A, top"),
    "RS4": (26.1, 9.0, 0, T, "pack shunt: pad 1 on Q8's drain tab, pad 2 (VBAT) toward C1/D1; INA239 Kelvin taps from the pad inner edges"),
    "D1": (27.0, 3.0, 180, T, "bus TVS: front strip, cathode (VBAT) straight in front of RS4's VBAT pad, anode to GND vias; across VBAT/GND before the bridge"),
    "C1": (24.3, 18.0, 180, T, "330 uF bulk: VBAT pad (right) 5.8 mm from RS4's VBAT pad and toward the bridge, GND pad (left) into the L2 plane: next to both the switch output and the bridge (DESIGN 6.6); 10.5 mm tall, top; stake by hand"),
    "J4": (6.5, 20.9, 270, T, "balance lead: left edge beside the battery wires, mating face at the edge; 6.1 mm tall so top (the board gap is ~5 mm)"),
    # drive left (rear-left, the left motor is behind this corner)
    "U3": (23.0, 30.0, 270, T, "drive L DRV8316: VM pins face C1/R302 (front), phase outputs face the JL wire holes (left), logic toward the rear/MCU vias; ~1-2 W, top"),
    "R302": (15.5, 18.5, 270, T, "drive L VM feed 0.1R: L_VM pad (rear) toward U3's VM pins, VBAT pad (front) fed on its own L3 branch from C1 (not through the bridge copper, DESIGN 6.6); up to 1 W, top, 7 mm from U3's thermal pad"),
    "JL1": (7.8, 32.4, 0, T, "drive L phase A wire: rear edge, left end (left motor behind)"),
    "JL2": (12.0, 32.4, 0, T, "drive L phase B wire: rear edge"),
    "JL3": (16.2, 32.4, 0, T, "drive L phase C wire: rear edge, next to U3's outputs"),
    # weapon driver: behind the bridge, gate/sense pins face the cells
    "U2": (53.50, 23.0, 180, T, "DRV8323RH: behind the bridge centre, rotated 180 so the phase B/C gate+sense pins are on its front edge (facing the middle of the bridge) and the phase A pins on its right side (toward cell A, front-right); straps/DVDD/VREF on its left, buck pins at its rear-right corner; hot (gate drive + 5 V buck), top"),
    # U2's 5 V buck as one compact block right behind its SW pin (DESIGN 6.7 / LMR16006 layout):
    # L1 SW pad under pin 45, D2's cathode beside it, both output caps bridging D2's anode and L1's +5V pad
    "L1": (48.4, 30.0, 180, T, "buck inductor: SW pad (right) 2 mm from C28/D2's SW end, +5V pad (left) over the output caps; 4 mm tall, warm, top"),
    "D2": (55.0, 30.8, 270, T, "buck catch diode: cathode (top) 1.9 mm below SW pin 45, anode (bottom) beside C27's GND pad, so the pulsed input loop C27 -> VIN -> SW -> D2 closes in ~4 x 4 mm; 0.18 W, top"),
    "C29": (50.5, 33.85, 0, T, "buck output cap: +5V pad toward L1's +5V pad, GND pad toward D2's anode"),
    "C30": (46.9, 33.85, 0, T, "second buck output cap: +5V pad under L1's +5V pad"),
    "C27": (58.0, 29.0, 270, T, "buck VIN cap: VIN pad (top) 2.4 mm from U2 pin 47, GND pad (bottom) beside D2's anode: the input loop is the one that must be small (LMR16006 p17)"),
    "C28": (52.1, 28.8, 270, T, "bootstrap cap: in the gap between L1 and D2, CB pad (top) 2.7 mm from pin 44, SW pad (bottom) on the SW copper"),
    # U3's AVDD cap and nFAULT pull-up behind its rear pins (out of the phase-output fan, DESIGN 3.3 AGND return)
    "C305": (21.65, 33.95, 180, T, "U3 AVDD cap: AVDD pad behind pin 25, GND pad behind pins 22-23 (AGND side), leaving the INH/DRV_OFF pins behind U3 free to escape (verification review)"),
    "R301": (19.1, 33.55, 0, T, "U3 nFAULT pull-up to AVDD: behind nFAULT pin 22, 1 mm from JL3's ring on the top (outside its bottom solder zone)"),
    # drive right (rear-right, the right motor is behind this corner)
    "U4": (66.5, 24.5, 90, T, "drive R DRV8316: rotated 90 so the phase outputs face the JR wire holes on the right edge and the VM pins face R402 behind it; CSA/logic pins via to the MCU below; ~1-2 W, top"),
    "R402": (64.07, 32.9, 0, T, "drive R VM feed 0.1R: rear edge behind U4: pad 2 (R_VM, right) below U4's VM pins with the VM/CP caps in the row between, pad 1 (VBAT, left) fed on its own L3 branch from C1 (not through the bridge copper, DESIGN 6.6); up to 1 W, top, clear of U4's thermal pad"),
    "JR1": (73.10, 25.8, 0, T, "drive R phase A wire: right edge, level with U4's phase-A output pins (no crossing)"),
    "JR2": (73.10, 22.0, 0, T, "drive R phase B wire: right edge beside U4's outputs"),
    "JR3": (73.10, 18.2, 0, T, "drive R phase C wire: right edge next to U4's outputs (phase order A, B, C from the rear, no crossing)"),
    "TH1": (58.73, 15.35, 90, T, "weapon FET NTC: in the gap behind phase B's high-side drain tab (the hottest copper), between C26 and RS1 (DESIGN 3.2)"),
    # bottom: header and sensor connectors
    "J1": (16.6, 19.2, 0, B, "header to the compute board (bottom): left of the MCU beside J4's pin column (outside its solder zone), clear of U2/U3's via fields and the gate corridor, behind the pack-return path (which runs from the bridge to JBAT2 along the front); frees the MCU's ring"),
    "J2": (33.3, 31.85, 0, T, "drive L sensor connector: TOP side at the rear edge (moved off the bottom, where it sat under U3's thermal-via field), mating face at the edge, the left motor behind; 3.35 mm tall"),
    "J3": (54.0, 31.9, 180, B, "drive R sensor connector (bottom): rear edge under the buck (D2/C27/C28), not under R402 (1 W) or U4's via field, mating face at the edge; 3.35 mm tall"),
})

A = []   # ANCHORED: (ref, side, anchor, rotations, why)


def add(refs, side, anchor, why, rots=(0, 90, 180, 270)):
    for r in refs.split():
        A.append((r, side, anchor, rots, why))


# ---------------------------------------------------------------- top: bridge extras
#add( ("RS1", "2"), "Kelvin tie SNA: at RS1's GND pad inner edge (DESIGN 6.3)")
#add( ("RS2", "2"), "Kelvin tie SNB: at RS2's GND pad inner edge")
#add( ("RS3", "2"), "Kelvin tie SNC: at RS3's GND pad inner edge")
# ---------------------------------------------------------------- top: power switch (hot/BAT_IN parts)
add("U13", T, ("Q7", "4"), "LM74502: front strip above the Q7/Q8 pair, ~2 mm from Q7's gate, GATE/SRC short (DESIGN 6.6); BAT_IN pin, so top")
add("C14", T, ("U13", "5"), "U13 VS cap across the unswitched pack (BAT_IN, so top): on U13's right because JBAT2's solder zone takes its left; 0805 parallel to the front edge")
add("R13", T, ("U13", "1"), "EN/UVLO top resistor from BAT_IN: top (BAT_IN never on the bottom face)")
add("C12", T, ("U13", "4"), "VCAP-VS cap: beside U13, off the FET copper (LM74502 p19: heat shifts its capacitance)")
add("C18", T, ("U13", "1"), "EN/UVLO filter at U13 pin 1 (DESIGN 6.6)")
# ---------------------------------------------------------------- top: drive L / R decoupling at the pins
for s, u in (("30", "U3"), ("40", "U4")):
    add(f"C{s}0 C{s}1", T, (u, "10"), f"{u} VM 100 nF at pins 9/11 (serve pin 10 too): within 2 mm, same side as the IC (DESIGN 6.5/6.6)")
    add(f"C{s}3", T, (u, "8"), f"{u} CP cap at pin 8: at the pin (DRV8316C layout)")
    add(f"C{s}4", T, (u, "7"), f"{u} CPH-CPL flying cap at pins 6/7")
    if u == "U4":
        add(f"C{s}5 R{s}1", T, (u, "25"), f"{u} AVDD cap / nFAULT pull-up to AVDD: at pin 25, short return to its AGND pin")
    add(f"C{s}6", T, (u, "37"), f"{u} VREF cap at pin 37")
# ---------------------------------------------------------------- top: weapon driver decoupling + straps + buck
add("C24", T, ("U2", "6"), "U2 VM 100 nF: as close to pin 6 as possible (DRV8323 'must')")
EXPLICIT["C21"] = (60.45, 22.5, 90, T, "VCP-VM cap at pin 5: beside C24, its VM pad next to C24's, VCP pad reached by a lane under C24 (routing)")
EXPLICIT["C20"] = (59.45, 25.28, 180, T, "charge-pump flying cap at pins 3/4: CPL pad left, CPH pad right, so pins 5/4/3 fan out to C21/C20 as parallel lanes without crossing (routing)")
add("C22", T, ("U2", "36"), "DVDD cap at pin 36, short path to AGND")
add("C23", T, ("U2", "26"), "VREF cap at pin 26")
add("R44", T, ("U2", "29"), "MODE strap within 2 mm of pin 29, returned to AGND (DESIGN 6.4)")
add("R45", T, ("U2", "30"), "IDRIVE strap within 2 mm of pin 30")
add("R46", T, ("U2", "31"), "VDS strap next to pin 31 (2.5 mm: three 0402s cannot all sit within 2 mm of pins 29-31), AGND return")
add("R20 R21", T, ("U2", "1"), "FB divider at pin 1, away from L1 (DESIGN 6.7)")
add("R4 R5 C10", T, ("U2", "48"), "buck nSHDN/UVLO divider + filter at pin 48, away from the SW node")
add("U5", T, ("C29", "1"), "3.3 V LDO: fed from the buck's +5V; 0.2 W (+38 C), top")
add("C69", T, ("U5", "1"), "U5 input cap")
add("C70", T, ("U5", "5"), "U5 output cap")
# ---------------------------------------------------------------- top: user-facing
add("D3", T, (40.5, 33.8), "power LED: top, rear edge, visible from above/behind (DESIGN 3.1: visible from outside)")
add("TP10", T, ("C1", "1"), "VBAT test pad: at C1's VBAT")
add("TP11", T, ("C29", "1"), "+5V test pad: at the buck output")
EXPLICIT["TP1"] = (58.9, 18.8, 0, T, "+3V3 test pad: top, in a free spot right of U2's front, off U1's footprint (routing)")
EXPLICIT["TP5"] = (31.9, 11.35, 0, T, "GND test pad: top, front-left, off U1's footprint (routing)")
EXPLICIT["TP12"] = (26.45, 25.75, 0, T, "GND test pad: top, right of U3's front, off U1's footprint (routing)")
EXPLICIT["TP2"] = (15.0, 28.7, 0, T, "SWDIO pad: top, beside J1 (the SWD header), off U1's footprint (routing)")
EXPLICIT["TP3"] = (14.95, 25.5, 0, T, "SWCLK pad: top, beside J1 (routing)")
EXPLICIT["TP4"] = (17.2, 29.25, 0, T, "NRST pad: top, beside J1 (routing)")
EXPLICIT["TP6"] = (16.5, 13.05, 0, T, "W_ARM test pad: top, front-left beside the ARM circuit, off U1's footprint (routing)")
add("TP7", T, ("U2", "33"), "W_EN test pad: at U2 ENABLE")
add("TP9", T, (44.5, 21.0), "W_nFAULT test pad: left of U2, clear of the gate/sense strip in front of it")
EXPLICIT["TP8"] = (21.35, 4.95, 0, T, "DRV_OFF test pad: top, front-left in free space on the net (a probe point works anywhere on it) (routing)")

# ---------------------------------------------------------------- bottom: MCU and its parts
add("U1", B, (35.5, 26.0), "STM32G474 (bottom): cool (~0.26 W); central rear, between the drive ICs and the weapon driver, away from the pack current (DESIGN 6.2); vias to U2/U3/U4 logic")
for c, pin in (("C60", "16"), ("C61", "32"), ("C62", "48"), ("C63", "64")):
    add(c, B, ("U1", pin), f"VDD decoupling at U1 pin {pin} (ST: as close as possible, may be on the underside)")
add("C64", B, ("U1", "32"), "VDD bulk near the VDD pins")
add("C65 R60", B, ("U1", "29"), "VDDA cap / VDDA feed at pin 29")
add("C66 C71", B, ("U1", "28"), "VREF+ caps at pin 28")
add("C74", B, ("U1", "1"), "VBAT-pin cap at pin 1")
add("C67", B, ("U1", "7"), "NRST cap at pin 7")
add("R61", B, ("U1", "60"), "BOOT0 pull-down at pin 60")
add("R70 C80", B, ("U1", "42"), "drive L CSA A filter: the cap at the MCU pin, the resistor along the line (DESIGN 6.8)")
add("R71 C81", B, ("U1", "43"), "drive L CSA B filter: the cap at the MCU pin, the resistor along the line")
add("R72 C82", B, ("U1", "11"), "drive L CSA C filter: the cap at the MCU pin, the resistor along the line")
add("R80 C90", B, ("U1", "34"), "drive R CSA A filter: the cap at the MCU pin, the resistor along the line")
add("R81 C91", B, ("U1", "35"), "drive R CSA B filter: the cap at the MCU pin, the resistor along the line")
add("R82 C92", B, ("U1", "25"), "drive R CSA C filter: the cap at the MCU pin, the resistor along the line")
add("R23 C41", B, ("U1", "18"), "phase A divider bottom + filter: the cap at the MCU pin, the resistor along the line")
add("R25 C42", B, ("U1", "19"), "phase B divider bottom + filter: the cap at the MCU pin, the resistor along the line")
add("R27 C43", B, ("U1", "14"), "phase C divider bottom + filter near the MCU pin (5.5 mm, see 5.3)")
add("R43 C44", B, ("U1", "20"), "weapon NTC pull-up + filter near the MCU pin (5.4 mm, see 5.3)")
add("R63 R64 C68", B, ("U1", "17"), "pack voltage divider + filter toward the MCU pin (DC node; 9.6 mm, see 5.3)")
add("R33", B, ("J1", "11"), "header branch of the pack divider: near J1")
add("R16", B, ("J1", "8"), "NRST pull-up near J1/U1")
add("R17", B, ("J1", "6"), "MB_RX pull-up near J1")
add("R40", B, ("U1", "46"), "W_EN pull-down near the MCU pin")
add("R42 C19", B, ("U1", "2"), "W_nFAULT pull-up + glitch filter at PC13 (DESIGN: filter at the pin)")
add("R50", B, ("U1", "3"), "DRV_OFF pull-up: near PC14, trace short (DESIGN 6.6)")
EXPLICIT["R62"] = (61.3, 21.3, 270, B, "power LED resistor: bottom, anywhere on the +5V-LED line (3 mA); right of C20, out of phase A's gate escape from U2's right side (routing)")
# ---------------------------------------------------------------- bottom: phase dividers (top resistor at the phase)
add("R22", B, ("JW1", "1"), "phase A divider top: beside JW1, just outside its solder zone, so the phase voltage stays local and only the divided node runs to the MCU")
EXPLICIT["R24"] = (48.5, 4.5, 0, B, "phase B divider top: in the gap between JW3's and JW2's solder zones, in front of phase C's gate columns, so the divided node leaves on the L3 front strip without crossing a gate/sense bundle (routing); phase via to cell B's copper beside it")
add("R26", B, ("JW3", "1"), "phase C divider top: just behind JW3's solder zone")
# ---------------------------------------------------------------- bottom: weapon interlock and ARM
add("U6", B, (32.0, 9.5), "interlock AND gates (bottom): the free block right of RS4, beside the pack path, out of the gate-via corridor; CHxN in from the MCU, INLx out to U2; LVC logic does not mind the few mV of pack-return offset")
add("C40", B, ("U6", "14"), "U6 decoupling at VCC")
add("R47 R48 R49", B, ("U6", "1"), "CHxN pull-downs at U6's inputs")
add("U14", B, ("U6", "2"), "ARM Schmitt buffer: next to U6 (W_ARM_S feeds all three gates) and on the way to J1 pin 19 (W_ARM_CLK)")
add("C17", B, ("U14", "5"), "U14 decoupling")
add("R19", B, ("U14", "4"), "W_ARM_S pull-down at U14's output")
add("D9 C16 R41", B, ("U14", "2"), "ARM rectifier/hold/bleed near U14's input (a slow RC node)")
add("C15 R18", B, ("J1", "19"), "ARM coupling cap / W_ARM_CLK pull-down at J1 pin 19 (keep away from MB_TX)")
# ---------------------------------------------------------------- bottom: drive L/R parts that need not be on top
for s, u, r in (("30", "U3", "R302"), ("40", "U4", "R402")):
    add(f"C{s}2 C{s}8 C{s}9 C{s[0]}10", B, (u, "10"), f"{u} VM 10 uF bulk (bottom, toward the VM pins on the filtered side of {r}; distance: 5.3); the 100 nF stay on top at the pins")
    add(f"R{s}0 C{s}7", B, (u, "5"), f"{u} buck resistor-mode parts (bottom, beside its thermal-via field at the SW_BK/FB_BK pins, placed before the bulk caps so the SW_BK node stays short while the buck runs at boot): ~0.05 W only until firmware sets BUCK_DIS")
# ---------------------------------------------------------------- bottom: power-switch gate network, pack monitor
add("D4", B, ("Q7", "4"), "Q7/Q8 gate-source clamp (bottom, under the gates; not BAT_IN)")
add("R1 D10 C13 R32", B, ("U13", "6"), "Cdvdt network on PSW_G (bottom, near U13's GATE pin; not BAT_IN)")
add("R14", B, ("U13", "1"), "EN/UVLO bottom resistor (bottom, under pin 1)")
add("R15", B, ("C1", "1"), "bus bleeder (bottom, under C1): 41 mW")
add("U7", B, ("RS4", "1"), "INA239 (bottom): under RS4, Kelvin taps from the pad inner edges through vias")
add("R2 R3 C2", B, ("U7", "10"), "INA239 input filter at IN+/IN-")
add("C3 R12", B, ("U7", "6"), "INA239 VS cap / CS pull-up")
# ---------------------------------------------------------------- bottom: cell monitor at J4
add("U8", B, (4.0, 20.5), "BQ76907 (bottom, cool, 1 mm): under J4's body, left of its pin column, so every cell tap is a short run from J4 on the same side")
add("R6 R7 R8 R9 R10 R11", B, ("U8", "3"), "cell-input series R: at U8 (DESIGN 6.9), on U8's side of J4's solder zone")
add("C4 C5 C6 C7 C8", B, ("U8", "3"), "cell-input filter caps, placed first round U8")
add("C9", B, ("U8", "17"), "BAT decoupling at U8 pin 17")
add("C11", B, ("U8", "15"), "REGOUT cap at pin 15 (BQ76907: must be at REGOUT)")
add("D5", B, ("U8", "5"), "VC0 clamp at U8")
# ---------------------------------------------------------------- bottom: sensor channels at J2 / J3
SW_AT = {"L": (38.5, 29.0), "R": (50.0, 29.5)}
SIDE = {"L": T, "R": B}
for s, j, u, v, jp, d, n0 in (("L", "J2", "U9", "U11", "JP1", "D7", 0), ("R", "J3", "U10", "U12", "JP2", "D8", 1)):
    add(v, SIDE[s], SW_AT[s], f"sensor {s} supply switch: near {j}, 16-19 mm from the drive IC (85 C part, DESIGN 6.5)")
    add(jp, SIDE[s], (v, "5"), f"sensor {s} supply select jumper at the switch input ({'top' if SIDE[s] == T else 'bottom, reachable with the stack apart'})")
    add(u, SIDE[s], (j, "4"), f"sensor {s} Schmitt buffer: toward {j} (distance in the table; see 5.3)")
    add(d, B, ("U1", "5" if s == "L" else "6"), f"motor {s} NTC clamp: at the MCU's ADC pin (P{'F0' if s == 'L' else 'F1'}), on the protected side of the 2.2k series R")
hr = {"L": ("R54 R55 R56", "R110 R111 R112", "C110 C111 C112", "R52 R113 C72", "C45 C46", "C47"),
      "R": ("R57 R58 R59", "R114 R115 R116", "C114 C115 C116", "R53 R117 C73", "C48 C49", "C50")}
for s, (pu, ser, flt, ntc, sw, dec) in hr.items():
    j, u, v = ("J2", "U9", "U11") if s == "L" else ("J3", "U10", "U12")
    for rr, jp_ in zip(ser.split(), ("3", "4", "5")):
        add(rr, SIDE[s], (j, jp_), f"sensor {s} line series R at {j} pin {jp_} (keeps the three channels in order)")
    add(flt, SIDE[s], (u, "3"), f"sensor {s} line filter caps (DNP) at {u}'s inputs")
    add(pu, SIDE[s], (j, "4"), f"sensor {s} pull-ups at {j}")
    add(ntc, SIDE[s], (j, "6"), f"motor {s} NTC pull-up / series R / filter near {j} pin 6")
    add(sw, SIDE[s], (v, "5"), f"{v} input/output caps at the switch")
    add(dec, SIDE[s], (u, "8"), f"{u} decoupling")
# placement order on the bottom: the MCU and its decoupling first, then the parts that must sit at a given
# connector or IC (drive bulk caps, sensor channels), then the rest in the order above
FIRST = ("U1 C60 C61 C62 C63 C64 C65 R60 C66 C71 C74 C67 "           # MCU + decoupling first (it needs a ring)
         "R300 C307 C302 C308 C309 C310 "                       # drive L bulk (rear left)
         "D4 R1 D10 C13 R32 R14 "                                    # power-switch gate network (front left)
         "U7 C3 C2 R2 R3 R12 "                                       # pack monitor under RS4
         "U8 C11 C9 D5 C4 C5 C6 C7 C8 R6 R7 R8 R9 R10 R11 "          # cell monitor under J4
         "R400 C407 C402 C408 C409 C410 "                            # drive R bulk (rear right)
         "U12 C48 C49 JP2 U10 C50 R114 R115 R116 C114 C115 C116 R57 R58 R59 R53 R117 C73 "
         "C80 C81 C82 C90 C91 C92 C41 C42 C43 C19 C44 C68 D7 D8 R43 R63 R64 "
         "U6 C40 U14 C17").split()
CRIT = ("C24 C21 C20 C22 C23 R44 R45 R46 C28 R20 R21 C300 C301 C303 C304 C305 C306 R301 C400 C401 C403 C404 C405 C406 R401 "
        "U13 C14 C12 C18 R13 U5 C69 C70").split()
top = [e for e in A if e[1] == T]
top.sort(key=lambda e: CRIT.index(e[0]) if e[0] in CRIT else len(CRIT))
bot = [e for e in A if e[1] == B]
bot.sort(key=lambda e: FIRST.index(e[0]) if e[0] in FIRST else len(FIRST))
ANCHORED = top + bot
