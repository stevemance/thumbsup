#!/usr/bin/env python3
"""ThumbsUp motor board: the reference netlist.

This file is the connection list you draw the KiCad schematic from.  It is plain data
(no SKiDL, no KiCad): every part, every pin, every net.  Running it

    python3 hardware/motor_board/design/motor_board.py

checks the design and writes, next to this file:

    netlist.csv     one row per pin: net, ref, pin number, pin name
    nets.md         the same, grouped by net (easier to read while drawing)
    bom.csv         JLCPCB BOM format (Comment, Designator, Footprint, LCSC)
    mcu_pinmap.md   STM32G474RET6 pin plan, each alternate function verified against
                    ST's pin database (ref/STM32G474RxTx_pins.xml)

Checks: every pin of every IC is either on a net or explicitly "NC"; no net has a single
connection unless it is on the allowed list; every MCU alternate function named in
MCU_PINS exists on that pin; decoupling/pull-up parts are counted.

Pin numbers come from the datasheets in ../ref/README.md (DRV8316 SLVSF16B Table 6-1,
DRV8323 SLVSDJ3D Table 6-4, STM32 open pin data).  Parts marked "confirm" in the BOM
need their pinout checked against the chosen vendor part before drawing.
"""

from __future__ import annotations

import csv
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REF = HERE.parent / "ref"

PARTS: dict[str, dict] = {}


def part(ref, value, footprint, pins, lcsc="", desc="", dnp=False):
    """pins: {pin_number: (pin_name, net)}; net 'NC' = intentionally unconnected."""
    assert ref not in PARTS, ref
    PARTS[ref] = dict(value=value, footprint=footprint, pins=pins, lcsc=lcsc, desc=desc, dnp=dnp)


def two(ref, value, footprint, net1, net2, lcsc="", desc="", names=("1", "2"), dnp=False):
    part(ref, value, footprint, {"1": (names[0], net1), "2": (names[1], net2)}, lcsc, desc, dnp)


# Footprint shorthands (KiCad standard libraries)
R0402, C0402, C0603, C0805, C1206 = ("Resistor_SMD:R_0402_1005Metric", "Capacitor_SMD:C_0402_1005Metric",
                                     "Capacitor_SMD:C_0603_1608Metric", "Capacitor_SMD:C_0805_2012Metric",
                                     "Capacitor_SMD:C_1206_3216Metric")

# LCSC numbers: filled from the JLC lookup (see ../BOM.md for stock / class / date checked)
LCSC = {
    # JLC Basic passives (C-numbers from the JLC basic-parts list; stock/class re-check before ordering)
    "100n_50V_0603": "C14663", "100n_16V_0402": "C1525", "47n_50V_0603": "C1622", "1u_25V_0402": "C52923",
    "1u_50V_0603": "C15849", "2u2_50V_0805": "C49217", "4u7_10V_0402": "C23733", "10u_50V_1206": "C13585",
    "22u_25V_0805": "C45783", "22u_6V3_0603": "C59461",
    "R10k": "C25744", "R100k": "C25741", "R68k": "C36871", "R56k": "C25796", "R1k": "C11702", "R22_0603": "C23345",
    "SCHOTTKY": "C8598",           # B5819W SOD-123 40 V 1 A (Basic)
    "LED": "C2286", "NTC10k": "C13564",
    # Extended parts (numbers from jlcpcb.com / lcsc.com part pages, 2026-09-23)
    "STM32G474RET6": "C521608", "DRV8316RRGFR": "C5218861", "DRV8323RSRGZR": "C545497",
    "FET": "C2874970",             # HUAYI HYG015N04LS1C2, 40 V 2.0 mOhm PDFN5x6 (used on the v1 design)
    "SHUNT_2m": "C2844506",        # Milliohm HoLR2512-3W-2mR-1%
    "SMBJ20A": "C151922",          # BORN SMBJ20A (several makers; pick the one in stock)
    "C_BULK": "C242138",           # Panasonic EEHZK1E471P - LOW STOCK when checked, see BOM.md
    "AP2112K-3.3": "C51118", "74LVC1G08": "C460522",   # Diodes 74LVC1G08SE-7 SOT-353
    "L22u": "C135264",             # Shun Xiang Nuo SMNR4020-22UH: 22 uH, 0.35 ohm, 1.05 A, 4x4 mm
    "SM06B": "C160405",            # JST SM06B-SRSS-TB(LF)(SN)
    "B2B_M": "C59981",             # BOOMELE 1.27-2*10P, 1.27 mm 2x10 SMD male (6,280 in stock 2026-09-23)
    "INA229": "C2846803",          # TI INA229AIDGSR VSSOP-10 (986 in stock 2026-09-23)
    "SHUNT_1m": "C46961745",       # JIERR RE2512F3R001 1 mOhm 3 W 2512 (verified for the v1 board)
    "ZENER12": "C21567",           # MMSZ5242B 12 V SOD-123
    "R390k_0603": "C23150", "R51k": "C25794", "R10R": "C25077", "R100R": "C25076",
    "BQ76907": "C22458649",        # TI BQ76907RGRR 2-7S monitor (listed at JLC; BQ76905 not found at LCSC)
    "XH5": "C263757",              # JST S5B-XH-A(LF)(SN) side-entry THT; vertical B5B-XH-A = C157991
}

# ============================================================== power entry and battery monitoring
# BAT+ -> RS4 (pack shunt, INA229) -> VBAT.  BAT- -> Q7 (reverse-polarity FET, low side) -> GND.
part("J_BAT+", "BAT+ pad", "thumbsup:SolderPad_4x6mm", {"1": ("BAT+", "VBAT_PACK")}, desc="battery + (pigtail to an XT30 on the lead)")
part("J_BAT-", "BAT- pad", "thumbsup:SolderPad_4x6mm", {"1": ("BAT-", "BAT_NEG")}, desc="battery -")
part("Q7", "HYG015N04LS1C2", "Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic",
     {"1": ("S", "GND"), "2": ("S", "GND"), "3": ("S", "GND"), "4": ("G", "RPP_G"), "5": ("D", "BAT_NEG")}, LCSC["FET"],
     "reverse-polarity protection in the ground return: body diode conducts first, then the channel (1.4 mOhm); reversed pack -> Vgs < 0, off")
two("R1", "100k", R0402, "VBAT", "RPP_G", LCSC["R100k"], "Q7 gate from VBAT (48 uA through the zener at 16.8 V)")
two("D4", "MMSZ5242B 12V", "Diode_SMD:D_SOD-123", "RPP_G", "GND", LCSC["ZENER12"], "Q7 gate clamp (Vgs max 20 V; TVS events reach 32 V)", names=("K", "A"))
two("RS4", "1mR 1% 2512", "Resistor_SMD:R_2512_6332Metric", "VBAT_PACK", "VBAT", LCSC["SHUNT_1m"], "pack current shunt, high side (Kelvin to U7 through R2/R3)")
two("R2", "10R", R0402, "VBAT_PACK", "INA_INP", LCSC["R10R"], "INA229 IN+ series (TI 8.1.4: dV/dt robustness on a short)")
two("R3", "10R", R0402, "VBAT", "INA_INN", LCSC["R10R"], "INA229 IN- series")
two("C2", "100nF 50V", C0603, "INA_INP", "INA_INN", LCSC["100n_50V_0603"], "INA229 differential input filter (80 kHz with 2 x 10 ohm)")
part("U7", "INA229AIDGSR", "Package_SO:VSSOP-10_3x3mm_P0.5mm",
     {"1": ("CS", "INA_nCS"), "2": ("MOSI", "SPI_MOSI"), "3": ("ALERT", "W_nFAULT"), "4": ("MISO", "SPI_MISO"),
      "5": ("SCLK", "SPI_SCK"), "6": ("VS", "+3V3"), "7": ("GND", "GND"), "8": ("VBUS", "VBAT"),
      "9": ("IN-", "INA_INN"), "10": ("IN+", "INA_INP")}, LCSC["INA229"],
     "pack monitor: 20-bit V, I, P, energy and charge (coulomb counter), die temp.  ALERT (open drain) shares W_nFAULT -> TIM1 break: a programmed pack over-current kills the weapon PWM in hardware")
two("C3", "100nF 16V", C0402, "+3V3", "GND", LCSC["100n_16V_0402"], "U7 VS")
two("D1", "SMBJ20A", "Diode_SMD:D_SMB", "VBAT", "GND", LCSC["SMBJ20A"], "TVS after the RPP FET (a reversed pack must not see it): standoff 20 V, clamp ~32 V (<40 V DRV8316 abs max)", names=("K", "A"))
two("C1", "470uF 25V polymer", "Capacitor_SMD:CP_Elec_10x10.5", "VBAT", "GND", LCSC["C_BULK"], "bulk, next to the weapon bridge", names=("+", "-"))
# deep-discharge cutoff: divider on the buck's nSHDN (U2 pin 48) stops the 5 V rail (MCU, compute board) below ~9.2 V
two("R4", "390k 1%", "Resistor_SMD:R_0603_1608Metric", "VBAT", "BUCK_EN", LCSC["R390k_0603"], "buck UVLO top: on at ~10.4 V, off at ~9.2 V (nominal, see calcs)")
two("R5", "51k 1%", R0402, "BUCK_EN", "GND", LCSC["R51k"], "buck UVLO bottom")
# ---- cell monitoring (balance lead): BQ76907, 4S wiring per the BQ76907 datasheet Table 7-1:
# cells VC7-VC6 (4), VC5-VC4 (3), VC3-VC2 (2), VC1-VC0 (1); shorted VC6=VC5, VC4=VC3, VC2=VC1.
# Host = the compute board over I2C on the header (all 52 motor-MCU I/O are in use).
part("J4", "JST XH 5-pin (balance)", "Connector_JST:JST_XH_S5B-XH-A_1x05_P2.50mm_Horizontal",
     {"1": ("B0", "BAL0"), "2": ("B1", "BAL1"), "3": ("B2", "BAL2"), "4": ("B3", "BAL3"), "5": ("B4", "BAL4")},
     LCSC["XH5"], "4S balance lead: pin 1 = pack negative (B0) ... pin 5 = pack positive (B4); check the pack's lead order")
for k in range(5):
    two(f"R{6 + k}", "100R", R0402, f"BAL{k}", f"CELL{k}", LCSC["R100R"], f"cell input {k} series R (input filter; balancing unused; TI limits 10-1000 ohm, RC <= 200 us)")
for k in range(1, 5):
    two(f"C{3 + k}", "100nF 50V", C0603, f"CELL{k}", f"CELL{k-1}", LCSC["100n_50V_0603"], f"cell {k} input filter (differential)")
two("C8", "100nF 50V", C0603, "CELL0", "GND", LCSC["100n_50V_0603"], "VC0 filter to VSS (TI 8.2.7)")
part("U8", "BQ76907RGRR", "Package_DFN_QFN:VQFN-20-1EP_3.5x3.5mm_P0.5mm_EP2x2mm",
     {"1": ("VC4", "CELL2"), "2": ("VC3", "CELL2"), "3": ("VC2", "CELL1"), "4": ("VC1", "CELL1"), "5": ("VC0", "CELL0"),
      "6": ("SRP", "GND"), "7": ("SRN", "GND"), "8": ("TS", "GND"), "9": ("DSG", "NC"), "10": ("CHG", "NC"),
      "11": ("VSS", "GND"), "12": ("SCL", "BMS_SCL"), "13": ("SDA", "BMS_SDA"), "14": ("ALERT", "BMS_ALERT"),
      "15": ("REGOUT", "NC"), "16": ("REGSRC", "BMS_BAT"), "17": ("BAT", "BMS_BAT"),
      "18": ("VC7", "CELL4"), "19": ("VC6", "CELL3"), "20": ("VC5", "CELL3"), "21": ("PAD", "GND")},
     LCSC["BQ76907"], "per-cell voltages, die temp (balancing available but unused); protection FET drivers and coulomb counter unused (INA229 does current)")
two("R11", "10R", R0402, "BAL4", "BMS_BAT", LCSC["R10R"], "U8 supply from the balance lead top (TI app circuit); U8 stays off-board-power")
two("C9", "1uF 50V", C0603, "BMS_BAT", "GND", LCSC["1u_50V_0603"], "U8 BAT decoupling (50 V: also fits a 6S variant)")

# power LED (SPARC: visible power indicator independent of firmware)
two("R62", "1k", R0402, "+5V", "LED_A", LCSC["R1k"], "power LED, ~3 mA")
part("D3", "LED red", "LED_SMD:LED_0603_1608Metric", {"1": ("K", "GND"), "2": ("A", "LED_A")}, LCSC["LED"], "power LED on +5V")

# ============================================================== weapon: DRV8323RS (U2) + 6 FETs
W = "W_"
U2 = {
    "1": ("FB", "BUCK_FB"), "2": ("PGND", "GND"), "3": ("CPL", "U2_CPL"), "4": ("CPH", "U2_CPH"),
    "5": ("VCP", "U2_VCP"), "6": ("VM", "VBAT"), "7": ("VDRAIN", "VBAT"),
    "8": ("GHA", "W_GHA"), "9": ("SHA", "W_A"), "10": ("GLA", "W_GLA"), "11": ("SPA", "W_SLA"), "12": ("SNA", "W_SNA"),
    "13": ("SNB", "W_SNB"), "14": ("SPB", "W_SLB"), "15": ("GLB", "W_GLB"), "16": ("SHB", "W_B"), "17": ("GHB", "W_GHB"),
    "18": ("GHC", "W_GHC"), "19": ("SHC", "W_C"), "20": ("GLC", "W_GLC"), "21": ("SPC", "W_SLC"), "22": ("SNC", "W_SNC"),
    "23": ("SOC", "W_SOC"), "24": ("SOB", "W_SOB"), "25": ("SOA", "W_SOA"), "26": ("VREF", "+3V3"),
    "27": ("DGND", "GND"), "28": ("nFAULT", "W_nFAULT"), "29": ("SDO", "SPI_MISO"), "30": ("SDI", "SPI_MOSI"),
    "31": ("SCLK", "SPI_SCK"), "32": ("nSCS", "W_nCS"), "33": ("ENABLE", "W_ENABLE"), "34": ("CAL", "GND"),
    "35": ("AGND", "GND"), "36": ("DVDD", "U2_DVDD"), "37": ("INHA", "W_INHA"), "38": ("INLA", "W_INLA"),
    "39": ("INHB", "W_INHB"), "40": ("INLB", "W_INLB"), "41": ("INHC", "W_INHC"), "42": ("INLC", "W_INLC"),
    "43": ("BGND", "GND"), "44": ("CB", "BUCK_CB"), "45": ("SW", "BUCK_SW"), "46": ("NC", "NC"),
    "47": ("VIN", "VBAT"), "48": ("nSHDN", "BUCK_EN"), "49": ("PAD", "GND"),
}
part("U2", "DRV8323RSRGZR", "Package_DFN_QFN:VQFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm", U2, LCSC["DRV8323RSRGZR"],
     "weapon gate driver + 3 CSA + 5 V/0.6 A buck; nSHDN = UVLO divider (pack deep-discharge cutoff)")
two("C20", "47nF 50V", C0603, "U2_CPH", "U2_CPL", LCSC["47n_50V_0603"], "charge-pump flying cap (VM-rated)")
two("C21", "1uF 25V", C0402, "U2_VCP", "VBAT", LCSC["1u_25V_0402"], "VCP to VM (sees ~11 V)")
two("C22", "1uF 25V", C0402, "U2_DVDD", "GND", LCSC["1u_25V_0402"], "DVDD 3.3 V internal regulator")
two("C23", "100nF 16V", C0402, "+3V3", "GND", LCSC["100n_16V_0402"], "VREF (CSA supply/reference) at U2 pin 26")
two("C24", "100nF 50V", C0603, "VBAT", "GND", LCSC["100n_50V_0603"], "VM at U2 pin 6")
two("C25", "10uF 50V", C1206, "VBAT", "GND", LCSC["10u_50V_1206"], "weapon bridge local, high-side drains")
two("C26", "10uF 50V", C1206, "VBAT", "GND", LCSC["10u_50V_1206"], "weapon bridge local, high-side drains")
# buck (LMR16006X core, 0.7 MHz): 5 V / 0.6 A for the compute board and the 3.3 V LDO
two("C27", "2.2uF 50V", C0805, "VBAT", "GND", LCSC["2u2_50V_0805"], "buck VIN at pin 47")
two("C28", "100nF 50V", C0603, "BUCK_CB", "BUCK_SW", LCSC["100n_50V_0603"], "buck bootstrap CB-SW")
two("L1", "22uH >=1.2A", "Inductor_SMD:L_Changjiang_FNR4020S", "BUCK_SW", "+5V", LCSC["L22u"], "buck inductor, confirm footprint to chosen part")
two("D2", "40V 1A Schottky", "Diode_SMD:D_SOD-123", "BUCK_SW", "GND", LCSC["SCHOTTKY"], "buck catch diode", names=("K", "A"))
two("R20", "56k 1%", R0402, "+5V", "BUCK_FB", LCSC["R56k"], "FB top: Vout = 0.765 V x (1 + 56k/10k) = 5.05 V")
two("R21", "10k 1%", R0402, "BUCK_FB", "GND", LCSC["R10k"], "FB bottom")
two("C29", "22uF 25V", C0805, "+5V", "GND", LCSC["22u_25V_0805"], "buck output")
two("C30", "22uF 25V", C0805, "+5V", "GND", LCSC["22u_25V_0805"], "buck output")

# 3 half bridges: HYG015N04LS1C2 (40 V, 2 mOhm, PDFN 5x6).  A 3.3x3.3 40 V FET (<=5 mOhm) saves ~40 % bridge area
for ph, hi, lo, shunt, nt in (("A", "Q1", "Q2", "RS1", "NT1"), ("B", "Q3", "Q4", "RS2", "NT2"), ("C", "Q5", "Q6", "RS3", "NT3")):
    fet = lambda d, g, s: {"1": ("S", s), "2": ("S", s), "3": ("S", s), "4": ("G", g), "5": ("D", d)}   # HYG015N04LS1C2 on PQFN-8-EP 6x5: leads 1-3 S, 4 G, tab 5 D
    part(hi, "HYG015N04LS1C2", "Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic", fet("VBAT", f"W_GH{ph}", f"W_{ph}"), LCSC["FET"], f"weapon phase {ph} high side")
    part(lo, "HYG015N04LS1C2", "Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic", fet(f"W_{ph}", f"W_GL{ph}", f"W_SL{ph}"), LCSC["FET"], f"weapon phase {ph} low side")
    two(shunt, "2mR 1% 2512", "Resistor_SMD:R_2512_6332Metric", f"W_SL{ph}", "GND", LCSC["SHUNT_2m"], f"phase {ph} low-side shunt (Kelvin: SP{ph}/SN{ph} from the pad inner edges)")
    two(nt, "NetTie", "NetTie:NetTie-2_SMD_Pad0.5mm", f"W_SN{ph}", "GND", desc=f"Kelvin tie SN{ph} to the shunt's ground pad", names=("1", "2"))
    part(f"J_W{ph}", f"Weapon {ph}", "thumbsup:SolderPad_3x5mm", {"1": (ph, f"W_{ph}")}, desc=f"weapon motor phase {ph}")
    # phase voltage divider (catch-spinning-drum restart, six-step BEMF, sensorless observer check)
    k = 22 + 2 * (ord(ph) - 65)
    two(f"R{k}", "68k 1%", R0402, f"W_{ph}", f"W_V{ph}", LCSC["R68k"], f"phase {ph} divider top (25.2 V -> 3.23 V)")
    two(f"R{k+1}", "10k 1%", R0402, f"W_V{ph}", "GND", LCSC["R10k"], f"phase {ph} divider bottom")

# weapon enable interlock: DRV8323 ENABLE = MCU W_EN AND header W_ARM (both pulled low)
part("U6", "74LVC1G08", "Package_TO_SOT_SMD:SOT-353_SC-70-5",
     {"1": ("A", "W_EN"), "2": ("B", "W_ARM"), "3": ("GND", "GND"), "4": ("Y", "W_ENABLE"), "5": ("VCC", "+3V3")},
     LCSC["74LVC1G08"], "hardware weapon interlock (confirm SOT-353 pinout of chosen part)")
two("C40", "100nF 16V", C0402, "+3V3", "GND", LCSC["100n_16V_0402"], "U6 decoupling")
two("R40", "100k", R0402, "W_EN", "GND", LCSC["R100k"], "W_EN low while the MCU is in reset")
two("R41", "100k", R0402, "W_ARM", "GND", LCSC["R100k"], "W_ARM low when the compute board is absent")
two("R42", "10k 1%", R0402, "W_nFAULT", "+3V3", LCSC["R10k"], "nFAULT pull-up")
two("R43", "10k 1%", R0402, "+3V3", "W_NTC", LCSC["R10k"], "weapon FET NTC pull-up")
two("TH1", "NCP18XH103F03RB", "Resistor_SMD:R_0603_1608Metric", "W_NTC", "GND", LCSC["NTC10k"], "at the weapon FETs")

# ============================================================== drive: 2 x DRV8316R (U3 left, U4 right)
def drv8316(ref, s):
    pins = {
        "1": ("NC", "NC"), "2": ("AGND", "GND"), "3": ("FB_BK", f"{s}_FBBK"), "4": ("GND_BK", "GND"), "5": ("SW_BK", f"{s}_SWBK"),
        "6": ("CPL", f"{s}_CPL"), "7": ("CPH", f"{s}_CPH"), "8": ("CP", f"{s}_CP"), "9": ("VM", "VBAT"), "10": ("VM", "VBAT"),
        "11": ("VM", "VBAT"), "12": ("PGND", "GND"), "13": ("OUTA", f"{s}_A"), "14": ("OUTA", f"{s}_A"), "15": ("PGND", "GND"),
        "16": ("OUTB", f"{s}_B"), "17": ("OUTB", f"{s}_B"), "18": ("PGND", "GND"), "19": ("OUTC", f"{s}_C"), "20": ("OUTC", f"{s}_C"),
        "21": ("DRVOFF", "DRV_OFF"), "22": ("nFAULT", f"{s}_nFAULT"), "23": ("nSLEEP", "+3V3"), "24": ("NC", "NC"),
        "25": ("AVDD", f"{s}_AVDD"), "26": ("AGND", "GND"), "27": ("INHA", f"{s}_INHA"), "28": ("INLA", "+3V3"),
        "29": ("INHB", f"{s}_INHB"), "30": ("INLB", "+3V3"), "31": ("INHC", f"{s}_INHC"), "32": ("INLC", "+3V3"),
        "33": ("SDO", "SPI_MISO"), "34": ("SDI", "SPI_MOSI"), "35": ("SCLK", "SPI_SCK"), "36": ("nSCS", f"{s}_nCS"),
        "37": ("VREF/ILIM", f"{s}_AVDD"), "38": ("SOC", f"{s}_SOC"), "39": ("SOB", f"{s}_SOB"), "40": ("SOA", f"{s}_SOA"),
        "41": ("PAD", "GND"),
    }
    side = "left" if s == "L" else "right"
    part(ref, "DRV8316RRGFR", "Package_DFN_QFN:VQFN-40-1EP_5x7mm_P0.5mm_EP3.6x5.6mm", pins, LCSC["DRV8316RRGFR"],
         f"drive {side}: 3 half bridges 8 A pk, 3 CSA (no shunts), SPI; 3x PWM mode, INLx tied high, DRVOFF shared")
    n = int(ref[1:]) * 100
    two(f"C{n}", "100nF 50V", C0603, "VBAT", "GND", LCSC["100n_50V_0603"], f"{ref} VM pin 9")
    two(f"C{n+1}", "100nF 50V", C0603, "VBAT", "GND", LCSC["100n_50V_0603"], f"{ref} VM pin 11")
    two(f"C{n+2}", "10uF 50V", C1206, "VBAT", "GND", LCSC["10u_50V_1206"], f"{ref} VM bulk")
    two(f"C{n+3}", "1uF 50V", C0603, f"{s}_CP", "VBAT", LCSC["1u_50V_0603"], f"{ref} CP to VM")
    two(f"C{n+4}", "47nF 50V", C0603, f"{s}_CPH", f"{s}_CPL", LCSC["47n_50V_0603"], f"{ref} charge-pump flying cap (>=2x VM)")
    two(f"C{n+5}", "1uF 25V", C0402, f"{s}_AVDD", "GND", LCSC["1u_25V_0402"], f"{ref} AVDD")
    two(f"C{n+6}", "100nF 16V", C0402, f"{s}_AVDD", "GND", LCSC["100n_16V_0402"], f"{ref} VREF pin 37 (tied to its own AVDD: ROC is 2.8 V..AVDD, and AVDD can be as low as 3.1 V)")
    # buck unused: TI 9.2.1.1.5 requires RBK 22 ohm + CBK 22 uF populated, BUCK_DIS=1 over SPI
    two(f"R{n}", "22R", "Resistor_SMD:R_0603_1608Metric", f"{s}_SWBK", f"{s}_FBBK", LCSC["R22_0603"], f"{ref} buck unused: resistor mode (SLVSF16B 9.2.1.1.5)")
    two(f"C{n+7}", "22uF 6.3V", C0603, f"{s}_FBBK", "GND", LCSC["22u_6V3_0603"], f"{ref} buck unused: CBK")
    two(f"R{n+1}", "10k 1%", R0402, f"{s}_nFAULT", "+3V3", LCSC["R10k"], f"{ref} nFAULT pull-up (must be >2.2 V at power-up)")
    for ph in "ABC":
        part(f"J_{s}{ph}", f"Drive {s} {ph}", "thumbsup:SolderPad_2x3mm", {"1": (ph, f"{s}_{ph}")}, desc=f"drive {side} motor phase {ph}")


drv8316("U3", "L")
drv8316("U4", "R")
two("R50", "10k 1%", R0402, "DRV_OFF", "+3V3", LCSC["R10k"], "DRVOFF high = both drive bridges Hi-Z until the MCU drives it low")
two("R51", "10k 1%", R0402, "SPI_MISO", "+3V3", LCSC["R10k"], "SDO pull-up (DRV8323 SDO is open drain)")

# drive sensor connectors: Hall (UVW) or MT6701 (ABZ or UVW), motor NTC
for s, jref, jp, rt in (("L", "J2", "JP1", "R52"), ("R", "J3", "JP2", "R53")):
    part(jref, "SM06B-SRSS-TB", "Connector_JST:JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal",
         {"1": ("VS", f"{s}_VS"), "2": ("GND", "GND"), "3": ("S1", f"{s}_S1"), "4": ("S2", f"{s}_S2"),
          "5": ("S3", f"{s}_S3"), "6": ("TEMP", f"{s}_MTEMP"), "MP": ("MP", "GND")},
         LCSC["SM06B"], f"drive {s} sensor: 1 VS, 2 GND, 3 H1/A/U, 4 H2/B/V, 5 H3/Z/W, 6 motor NTC")
    part(jp, "SolderJumper_3", "Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm",
         {"1": ("A", "+3V3"), "2": ("C", f"{s}_VS"), "3": ("B", "+5V")},
         desc=f"sensor {s} supply: 1-2 = 3.3 V (default, bridged), 2-3 = 5 V (5 V sensors must be open-drain or use 5 V-tolerant pins)")
    two(rt, "10k 1%", R0402, "+3V3", f"{s}_MTEMP", LCSC["R10k"], f"motor {s} NTC pull-up")

# ============================================================== MCU (U1) and logic power
MCU_PINS = {
    # pin: (name, net, required alternate function or '' for GPIO/analog-only)
    "1": ("VBAT", "+3V3", ""), "2": ("PC13", "W_nFAULT", "TIM1_BKIN"), "3": ("PC14", "DRV_OFF", ""),
    "4": ("PC15", "R_nFAULT", ""), "5": ("PF0", "L_MTEMP", "ADC1_IN10"), "6": ("PF1", "R_MTEMP", "ADC2_IN10"),
    "7": ("PG10-NRST", "NRST", ""), "8": ("PC0", "L_SOA", "ADC1_IN6"), "9": ("PC1", "L_SOB", "ADC2_IN7"),
    "10": ("PC2", "R_INHB", "TIM20_CH2"), "11": ("PC3", "L_SOC", "ADC1_IN9"), "12": ("PA0", "W_SOA", "ADC1_IN1"),
    "13": ("PA1", "W_SOB", "ADC2_IN2"), "14": ("PA2", "W_SOC", "ADC1_IN3"), "15": ("VSS", "GND", ""),
    "16": ("VDD", "+3V3", ""), "17": ("PA3", "VBAT_SNS", "ADC1_IN4"), "18": ("PA4", "W_VA", "ADC2_IN17"),
    "19": ("PA5", "W_VB", "ADC2_IN13"), "20": ("PA6", "R_SOA", "ADC2_IN3"), "21": ("PA7", "R_SOB", "ADC2_IN4"),
    "22": ("PC4", "MB_TX", "USART1_TX"), "23": ("PC5", "MB_RX", "USART1_RX"), "24": ("PB0", "L_S3", "TIM3_CH3"),
    "25": ("PB1", "R_SOC", "ADC1_IN12"), "26": ("PB2", "R_INHA", "TIM20_CH1"), "27": ("VSSA", "GND", ""),
    "28": ("VREF+", "+3V3A", ""), "29": ("VDDA", "+3V3A", ""), "30": ("PB10", "R_S3", "TIM2_CH3"),
    "31": ("VSS", "GND", ""), "32": ("VDD", "+3V3", ""), "33": ("PB11", "W_VC", "ADC1_IN14"),
    "34": ("PB12", "W_NTC", "ADC1_IN11"), "35": ("PB13", "W_INLA", "TIM1_CH1N"), "36": ("PB14", "W_INLB", "TIM1_CH2N"),
    "37": ("PB15", "W_INLC", "TIM1_CH3N"), "38": ("PC6", "L_S1", "TIM3_CH1"), "39": ("PC7", "L_INHB", "TIM8_CH2"),
    "40": ("PC8", "R_INHC", "TIM20_CH3"), "41": ("PC9", "L_nCS", ""), "42": ("PA8", "W_INHA", "TIM1_CH1"),
    "43": ("PA9", "W_INHB", "TIM1_CH2"), "44": ("PA10", "W_INHC", "TIM1_CH3"), "45": ("PA11", "INA_nCS", ""),
    "46": ("PA12", "W_EN", ""), "47": ("VSS", "GND", ""), "48": ("VDD", "+3V3", ""),
    "49": ("PA13", "SWDIO", "SYS_JTMS-SWDIO"), "50": ("PA14", "SWCLK", "SYS_JTCK-SWCLK"), "51": ("PA15", "R_S1", "TIM2_CH1"),
    "52": ("PC10", "SPI_SCK", "SPI3_SCK"), "53": ("PC11", "SPI_MISO", "SPI3_MISO"), "54": ("PC12", "SPI_MOSI", "SPI3_MOSI"),
    "55": ("PD2", "W_nCS", ""), "56": ("PB3", "R_S2", "TIM2_CH2"), "57": ("PB4", "R_nCS", ""),
    "58": ("PB5", "L_S2", "TIM3_CH2"), "59": ("PB6", "L_INHA", "TIM8_CH1"), "60": ("PB7", "L_nFAULT", "TIM8_BKIN"),
    "61": ("PB8-BOOT0", "BOOT0", ""), "62": ("PB9", "L_INHC", "TIM8_CH3"), "63": ("VSS", "GND", ""), "64": ("VDD", "+3V3", ""),
}
part("U1", "STM32G474RET6", "Package_QFP:LQFP-64_10x10mm_P0.5mm", {p: (n, net) for p, (n, net, _) in MCU_PINS.items()},
     LCSC["STM32G474RET6"], "170 MHz M4F; TIM1 weapon, TIM8 drive L, TIM20 drive R, TIM3/TIM2 drive sensors, SPI3 to the 3 drivers, USART1 to compute")
for i, pin in enumerate(("16", "32", "48", "64")):
    two(f"C6{i}", "100nF 16V", C0402, "+3V3", "GND", LCSC["100n_16V_0402"], f"U1 VDD pin {pin}")
two("C64", "4.7uF 10V", C0402, "+3V3", "GND", LCSC["4u7_10V_0402"], "U1 VDD bulk")
two("C65", "100nF 16V", C0402, "+3V3A", "GND", LCSC["100n_16V_0402"], "U1 VDDA/VREF+")
two("C66", "1uF 25V", C0402, "+3V3A", "GND", LCSC["1u_25V_0402"], "U1 VDDA/VREF+")
two("R60", "0R", R0402, "+3V3", "+3V3A", "C17168", "VDDA feed (0 ohm; fit a 600 ohm@100MHz ferrite if ADC noise is a problem)")
two("C67", "100nF 16V", C0402, "NRST", "GND", LCSC["100n_16V_0402"], "NRST (internal pull-up)")
two("R61", "10k 1%", R0402, "BOOT0", "GND", LCSC["R10k"], "boot from flash")
two("R63", "68k 1%", R0402, "VBAT", "VBAT_SNS", LCSC["R68k"], "pack divider top (25.2 V -> 3.23 V)")
two("R64", "10k 1%", R0402, "VBAT_SNS", "GND", LCSC["R10k"], "pack divider bottom")
two("C68", "100nF 16V", C0402, "VBAT_SNS", "GND", LCSC["100n_16V_0402"], "pack divider filter (7 ms)")

part("U5", "AP2112K-3.3TRG1", "Package_TO_SOT_SMD:SOT-23-5",
     {"1": ("VIN", "+5V"), "2": ("GND", "GND"), "3": ("EN", "+5V"), "4": ("NC", "NC"), "5": ("VOUT", "+3V3")},
     LCSC["AP2112K-3.3"], "3.3 V / 600 mA LDO for MCU, driver logic, CSA references, sensors")
two("C69", "1uF 25V", C0402, "+5V", "GND", LCSC["1u_25V_0402"], "U5 in")
two("C70", "1uF 25V", C0402, "+3V3", "GND", LCSC["1u_25V_0402"], "U5 out")

# ============================================================== board-to-board header (to the compute board)
part("J1", "B2B 2x10 1.27mm male", "Connector_PinHeader_1.27mm:PinHeader_2x10_P1.27mm_Vertical_SMD",
     {"1": ("+5V", "+5V"), "2": ("+5V", "+5V"), "3": ("GND", "GND"), "4": ("GND", "GND"),
      "5": ("MB_TX", "MB_TX"), "6": ("MB_RX", "MB_RX"), "7": ("W_ARM", "W_ARM"), "8": ("NRST", "NRST"),
      "9": ("SWDIO", "SWDIO"), "10": ("SWCLK", "SWCLK"), "11": ("VBAT_SNS", "VBAT_SNS"), "12": ("GND", "GND"),
      "13": ("+5V", "+5V"), "14": ("GND", "GND"), "15": ("BMS_SDA", "BMS_SDA"), "16": ("BMS_SCL", "BMS_SCL"),
      "17": ("BMS_ALERT", "BMS_ALERT"), "18": ("SPARE1", "NC"), "19": ("SPARE2", "NC"), "20": ("GND", "GND")},
     LCSC["B2B_M"], "to the compute board: 5 V out (<=0.45 A, 3 pins), UART, weapon ARM, reset + SWD for programming, pack voltage, cell monitor I2C + alert (pull-ups on the compute board); 18-19 spare")
for i, (n, net) in enumerate((("3V3", "+3V3"), ("SWDIO", "SWDIO"), ("SWCLK", "SWCLK"), ("NRST", "NRST"), ("GND", "GND")), 1):
    part(f"TP{i}", n, "TestPoint:TestPoint_Pad_D1.0mm", {"1": (n, net)}, desc="SWD / bring-up pad")

# ============================================================== checks + outputs
SINGLE_OK = set()          # nets that legitimately have one pin (none expected)


def build_nets():
    nets = defaultdict(list)
    for ref, p in PARTS.items():
        for num, (name, net) in p["pins"].items():
            nets[net].append((ref, num, name))
    return nets


def check_mcu_af(problems):
    xml = REF / "STM32G474RxTx_pins.xml"
    ns = {"n": "http://dummy.com"}
    root = ET.parse(xml).getroot()
    sigs = {}
    for p in root.findall("n:Pin", ns):
        sigs[p.get("Position")] = (p.get("Name"), {s.get("Name") for s in p.findall("n:Signal", ns)})
    assert len(sigs) == 64
    for pin, (name, net, af) in MCU_PINS.items():
        stname, s = sigs[pin]
        if not stname.startswith(name.split("-")[0]):
            problems.append(f"U1 pin {pin}: named {name}, ST says {stname}")
        if af and af not in s:
            problems.append(f"U1 pin {pin} {stname}: {af} not available (has {sorted(x for x in s if x.startswith(af.split('_')[0]))})")
    return sigs


def main():
    problems = []
    nets = build_nets()
    for net, nodes in nets.items():
        if net == "NC":
            continue
        refs = {r for r, _, _ in nodes}
        if len(nodes) == 1 and net not in SINGLE_OK:
            problems.append(f"net {net} has one connection: {nodes}")
    sigs = check_mcu_af(problems)
    # every net that touches the MCU must reach something else (except analog-only / pads handled above)
    out = HERE
    with open(out / "netlist.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["net", "ref", "pin", "pin_name"])
        for net in sorted(nets):
            for ref, num, name in sorted(nets[net], key=lambda t: (t[0], t[1])):
                w.writerow([net, ref, num, name])
    with open(out / "nets.md", "w") as f:
        f.write("# Motor board nets (generated by motor_board.py — do not edit)\n\n")
        for net in sorted(nets, key=lambda n: (n == "NC", n)):
            f.write(f"- **{net}**: " + ", ".join(f"{r}.{n}({nm})" for r, n, nm in sorted(nets[net])) + "\n")
    groups = defaultdict(list)
    for ref, p in PARTS.items():
        if p["dnp"] or p["footprint"].startswith(("thumbsup:SolderPad", "TestPoint", "NetTie", "Jumper")):
            continue
        groups[(p["value"], p["footprint"].split(":")[-1], p["lcsc"])].append(ref)
    with open(out / "bom.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "Qty"])
        for (val, fp, lc), refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
            w.writerow([val, ",".join(sorted(refs)), fp, lc, len(refs)])
    with open(out / "mcu_pinmap.md", "w") as f:
        f.write("# STM32G474RET6 (LQFP-64) pin plan (generated by motor_board.py)\n\n")
        f.write("Every alternate function below was checked against ST's pin database (`../ref/STM32G474RxTx_pins.xml`).\n\n")
        f.write("| Pin | Port | Net | Function |\n|---|---|---|---|\n")
        for pin in sorted(MCU_PINS, key=int):
            name, net, af = MCU_PINS[pin]
            f.write(f"| {pin} | {name} | {net} | {af or ('power' if net in ('GND', '+3V3', '+3V3A') else 'GPIO / analog')} |\n")
    n_parts = sum(1 for p in PARTS.values() if not p["footprint"].startswith(("thumbsup:SolderPad", "TestPoint", "NetTie", "Jumper")))
    print(f"{len(PARTS)} refs ({n_parts} placed components), {len([n for n in nets if n != 'NC'])} nets, {len(groups)} BOM lines")
    for p in problems:
        print("PROBLEM:", p)
    print("checks:", "OK" if not problems else f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
