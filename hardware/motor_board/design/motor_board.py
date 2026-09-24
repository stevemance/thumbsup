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
MCU_PINS exists on that pin.

Pin numbers come from the datasheets in ../datasheets/README.md (DRV8316C SLVSH07 pin table,
DRV8323 SLVSDJ3D R-variant pin table, STM32 open pin data, and each small part's datasheet).
MCU_PINS alternate functions are checked against ST's pin database automatically; every placed
part must also carry an LCSC number or the checks fail.
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
    "1u_50V_0603": "C15849", "2u2_50V_0805": "C377773", "4u7_16V_0603": "C19666", "10u_50V_1206": "C13585",
    "22u_25V_0805": "C45783",
    "R10k": "C25744", "R100k": "C25741", "R68k": "C36871", "R56k": "C25796", "R1k": "C11702",
    "LED": "C2286", "NTC10k": "C13564",
    # Extended parts (numbers from jlcpcb.com / lcsc.com part pages, 2026-09-23)
    "STM32G474RET6": "C521608", "DRV8316CRRGFR": "C5447274", "DRV8323RHRGZR": "C543035",
    "FET": "C2874970",             # HUAYI HYG015N04LS1C2, 40 V 1.4 mOhm typ @ 10 V PDFN5x6 (used on the v1 design)
    "SHUNT_2m": "C2844506",        # Milliohm HoLR2512-3W-2mR-1%
    "SMBJ20A": "C151922",          # BORN SMBJ20A (several makers; pick the one in stock)
    "C_BULK": "C278516",           # Panasonic EEHZK1V331P 330 uF 35 V hybrid polymer, 10x10.2
    "AP2112K-3.3": "C51118",
    "74LVC08": "C465737",          # TI SN74LVC08APWR TSSOP-14 (alt Nexperia 74LVC08APW C6053)
    "LVC3G17": "C68245",           # TI SN74LVC3G17DCUR VSSOP-8 2.3x2 (DCT alt C18213, same pinout)
    "L22u": "C167971",             # Changjiang FNR5040S220MT 22 uH 1.8 A 5x5
    "SS34": "C8678",               # SS34 40 V 3 A SMA (buck catch diode)
    "SM06B": "C3029345",           # SH1.0 6P horizontal SMD (JST SM06B-SRSS-TB clone; C160405 out of stock)
    "B2B_M": "C59981",             # BOOMELE 1.27-2*10P, 1.27 mm 2x10 SMD male (6,280 in stock 2026-09-23)
    "INA239": "C2876522",          # TI INA239AIDGSR VSSOP-10 (INA229AIDGSR C2846803 is a pin-compatible drop-in)
    "SHUNT_1m": "C46961745",       # JIERR RE2512F3R001 1 mOhm 3 W 2512 (verified for the v1 board)
    "R390k_0603": "C137735", "R51k": "C25794", "R10R": "C25077", "R100R": "C25076", "R22_1206": "C17958",
    "R47k": "C25792", "R75k": "C25798", "R18k": "C25762", "R4k7": "C25900",   # review/r6_parts_lookup.md
    "1n_50V_0402": "C1523",
    "TPS22945": "C47507",          # TI TPS22945DCKR 100 mA current-limited load switch, SC70-5
    "R330": "C25104", "22p_0402": "C1555",
    "R100R_0603": "C22775", "4u7_50V_1206": "C29823", "220n_25V_0603": "C21120",
    "22n_50V_0603": "C21122", "R6k8_0805": "C17772", "LM74502": "C3236215", "R0R1_2512": "C25466", "100n_100V_0805": "C28233", "R15k": "C25756", "1N4148W": "C81598", "R1M": "C26083", "ZENER12": "C21567", "470n_25V_0603": "C1623", "2u2_16V_0603": "C23630", "LVC1G17": "C212314", "B5819W": "C8598", "BAT54S": "C47546",   # Nexperia BAT54S,215 SOT-23
    "BAV99": "C2500", "R2k2_0603": "C4190", 
    "BQ76907": "C22458649",        # TI BQ76907RGRR 2-7S monitor (listed at JLC; BQ76905 not found at LCSC)
    "XH5": "C263757",              # JST S5B-XH-A(LF)(SN) side-entry THT; vertical B5B-XH-A = C157991
}

# ============================================================== power entry and battery monitoring
# BAT+ -> Q7 -> PSW_S -> Q8 -> VBAT_SW -> RS4 (pack shunt, INA239) -> VBAT.  BAT- = GND directly.
# U13 LM74502 drives the back-to-back high-side pair (common source PSW_S).  Q7 (drain at the pack): its body diode
# blocks the plug-in surge, and it is the FET that sits in its linear region while the 60 uA gate drive into C13
# (Cdvdt) ramps VBAT at ~2.2 V/ms (~0.8 A into ~380 uF; 54-57 mJ, 16 W peak).  Q8 (drain at the board) conducts in
# reverse when on; its body diode blocks a reversed pack.  Board GND is tied to pack- at all times (the BQ76907 cell inputs never see a floating ground).
# EN/UVLO (filtered by C18) turns the pair off below ~9.0 V; the bus reaches it within ~0.1-0.4 s of the switch opening, so any
# re-close after that is soft again (spice/sim_hotplug.py).
part("J_BAT+", "BAT+ wire", "Connector_Wire:SolderWire-1.5sqmm_1x01_D1.7mm_OD3.9mm", {"1": ("BAT+", "BAT_IN")}, desc="battery + (pigtail to an XT30 on the lead, through the external power switch)")
part("J_BAT-", "BAT- wire", "Connector_Wire:SolderWire-1.5sqmm_1x01_D1.7mm_OD3.9mm", {"1": ("BAT-", "GND")}, desc="battery - (board ground)")
part("Q7", "HYG015N04LS1C2", "Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic",
     {"1": ("S", "PSW_S"), "2": ("S", "PSW_S"), "3": ("S", "PSW_S"), "4": ("G", "PSW_G"), "5": ("D", "BAT_IN")}, LCSC["FET"],
     "inrush FET, high side (drain to the pack): body diode blocks the plug-in surge; linear during the soft-start ramp (16 W peak, 54-57 mJ); 1.4 mOhm typ when on")
part("Q8", "HYG015N04LS1C2", "Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic",
     {"1": ("S", "PSW_S"), "2": ("S", "PSW_S"), "3": ("S", "PSW_S"), "4": ("G", "PSW_G"), "5": ("D", "VBAT_SW")}, LCSC["FET"],
     "reverse-polarity FET, back-to-back with Q7 (drain to the board): its body diode blocks a reversed pack; conducts source-to-drain when on")
part("U13", "LM74502DDFR", "Package_TO_SOT_SMD:Texas_DDF0008A_SOT-8_1.6x2.9mm_P0.65mm",
     {"1": ("EN/UVLO", "PSW_EN"), "2": ("GND", "GND"), "3": ("NC", "NC"), "4": ("VCAP", "PSW_CAP"), "5": ("VS", "BAT_IN"),
      "6": ("GATE", "PSW_G"), "7": ("OV", "GND"), "8": ("SRC", "PSW_S")}, LCSC["LM74502"],
     "high-side switch controller (SNOSDE5A): charge pump, 60 uA gate source for inrush control, 2.4 A gate sink, -65 V reverse rating; OV unused")
two("C14", "100nF 100V", C0805, "BAT_IN", "GND", LCSC["100n_100V_0805"], "U13 VS (>= 22 nF); 100 V: when the switch opens under load the pack-lead energy rings BAT_IN to 40-60 V (Q7 avalanches by design), and C14 is the only ceramic across the unswitched pack")
two("C12", "220nF 25V", C0603, "PSW_CAP", "BAT_IN", LCSC["220n_25V_0603"], "U13 VCAP to VS (>= 10 x Ciss of Q7+Q8 = 81 nF; SNOSDE5A 9.2.2.4)")
two("R1", "4.7k", R0402, "PSW_G", "PSW_RG", LCSC["R4k7"], "RG: isolates Cdvdt from the gate so turn-off (2.4 A sink) stays fast (SNOSDE5A 8.3.3.1)")
two("D10", "1N4148W", "Diode_SMD:D_SOD-123", "PSW_DV", "PSW_RG", LCSC["1N4148W"],
    "Cdvdt steering: C13 can only slow the gate's rise; with a reversed pack GND is the most positive node and C13 must not push the gate up", names=("K", "A"))
two("C13", "22nF 50V", C0603, "PSW_DV", "GND", LCSC["22n_50V_0603"], "Cdvdt: VBAT ramp ~2.2 V/ms with R32's bleed (1.3-3.0 V/ms over IGATE 40-77 uA), ~0.8 A into ~380 uF")
two("R32", "1M", R0402, "PSW_DV", "GND", LCSC["R1M"], "resets C13 between power-ups (tau 22 ms); draws ~20-28 uA of the 40-77 uA gate drive during the ramp")
two("R13", "100k", R0402, "BAT_IN", "PSW_EN", LCSC["R100k"], "EN/UVLO top (low impedance: the 0-5 uA EN sink adds only 0.3-0.5 V): off below ~9.0 V (7.7-10.1 incl. 1 % resistors), on above ~9.8 V (worst 10.8); limits an unloaded quick re-close step to ~9 V")
two("R14", "15k 1%", R0402, "PSW_EN", "GND", LCSC["R15k"], "EN/UVLO bottom")
two("C18", "100nF 16V", C0402, "PSW_EN", "GND", LCSC["100n_16V_0402"], "EN/UVLO filter (1.3 ms with R13||R14): the weapon's 24 kHz bus ripple must not trip the switch UVLO on a tired pack")
two("D4", "MMSZ5242B 12V", "Diode_SMD:D_SOD-123", "PSW_G", "PSW_S", LCSC["ZENER12"],
    "Q7/Q8 gate-source clamp: keeps Vgs < 15 V (U13 GATE-SRC abs max) and < 20 V (FET) through sag/recovery transients and at full charge-pump voltage (VCAP-VS up to 13.9 V)", names=("K", "A"))
two("R15", "6.8k 0805", "Resistor_SMD:R_0805_2012Metric", "VBAT", "GND", LCSC["R6k8_0805"],
    "bus bleeder (41 mW): after the switch opens, VBAT falls to the switch UVLO within ~0.1-0.4 s, so a later re-close starts soft")
two("RS4", "1mR 1% 2512", "motor_board:R_2512_JIERR_RE_small_electrode", "VBAT_SW", "VBAT", LCSC["SHUNT_1m"], "pack current shunt, after the switch FETs (INA239 inputs must stay >= -0.3 V; Kelvin to U7 through R2/R3)")
two("R2", "10R", R0402, "VBAT_SW", "INA_INP", LCSC["R10R"], "INA239 IN+ series (TI 8.1.4: dV/dt robustness on a short)")
two("R3", "10R", R0402, "VBAT", "INA_INN", LCSC["R10R"], "INA239 IN- series")
two("C2", "100nF 50V", C0603, "INA_INP", "INA_INN", LCSC["100n_50V_0603"], "INA239 differential input filter (80 kHz with 2 x 10 ohm)")
part("U7", "INA239AIDGSR", "Package_SO:MSOP-10_3x3mm_P0.5mm",
     {"1": ("CS", "INA_nCS"), "2": ("MOSI", "SPI_MOSI"), "3": ("ALERT", "W_nFAULT"), "4": ("MISO", "SPI_MISO"),
      "5": ("SCLK", "SPI_SCK"), "6": ("VS", "+3V3"), "7": ("GND", "GND"), "8": ("VBUS", "VBAT"),
      "9": ("IN-", "INA_INN"), "10": ("IN+", "INA_INP")}, LCSC["INA239"],
     "pack monitor: 16-bit V, I, P, die temp (INA229 = pin-compatible, 24-bit registers + energy/charge).  ALERT (open drain, "
     "SOVL and BOVL only) shares W_nFAULT -> TIM1 break: a pack over-current kills the weapon PWM in hardware")
two("C3", "100nF 16V", C0402, "+3V3", "GND", LCSC["100n_16V_0402"], "U7 VS")
two("R12", "100k", R0402, "INA_nCS", "+3V3", LCSC["R100k"], "U7 CS deselected while the MCU is in reset (the INA239 has no internal pull)")
two("D1", "SMBJ20A", "Diode_SMD:D_SMB", "VBAT", "GND", LCSC["SMBJ20A"], "TVS on VBAT, after the switch (a reversed pack must not forward-bias it): standoff 20 V, clamp ~32 V (<40 V DRV8316 abs max)", names=("K", "A"))
two("C1", "330uF 35V hybrid polymer", "Capacitor_SMD:CP_Elec_10x10.5", "VBAT", "GND", LCSC["C_BULK"],
    "bulk, next to the weapon bridge; also limits VM dV/dt at plug-in (DRV8316 4 V/us, spice/sim_hotplug.py)", names=("+", "-"))
# logic cutoff (2.3 V/cell, not pack protection): divider on the buck's nSHDN (U2 pin 48) stops the 5 V rail (MCU, compute board) below ~9.2 V
two("R4", "390k 1%", "Resistor_SMD:R_0603_1608Metric", "VBAT", "BUCK_EN", LCSC["R390k_0603"], "buck UVLO top: on at ~10.4 V, off at ~9.2 V (nominal, see calcs)")
two("R5", "51k 1%", R0402, "BUCK_EN", "GND", LCSC["R51k"], "buck UVLO bottom")
two("C10", "100nF 16V", C0402, "BUCK_EN", "GND", LCSC["100n_16V_0402"], "nSHDN filter (high-impedance divider next to the switching node; 4.5 ms)")
# ---- cell monitoring (balance lead): BQ76907, 4S wiring per the BQ76907 datasheet Table 7-1:
# cells VC7-VC6 (4), VC5-VC4 (3), VC3-VC2 (2), VC1-VC0 (1); shorted VC6=VC5, VC4=VC3, VC2=VC1.
# Host = the compute board over I2C on the header (all 52 motor-MCU I/O are in use).
part("J4", "JST XH 5-pin (balance)", "Connector_JST:JST_XH_S5B-XH-A_1x05_P2.50mm_Horizontal",
     {"1": ("B0", "BAL0"), "2": ("B1", "BAL1"), "3": ("B2", "BAL2"), "4": ("B3", "BAL3"), "5": ("B4", "BAL4")},
     LCSC["XH5"], "4S balance lead: pin 1 = pack negative (B0) ... pin 5 = pack positive (B4); check the pack's lead order")
for k in range(5):
    two(f"R{6 + k}", "100R 0603" if k == 0 else "100R", "Resistor_SMD:R_0603_1608Metric" if k == 0 else R0402, f"BAL{k}", f"CELL{k}", LCSC["R100R_0603"] if k == 0 else LCSC["R100R"], f"cell input {k} series R (input filter; balancing unused; TI limits 10-1000 ohm, RC <= 200 us)")
for k in range(1, 5):
    two(f"C{3 + k}", "220nF 25V", C0603, f"CELL{k}", f"CELL{k-1}", LCSC["220n_25V_0603"], f"cell {k} input filter (differential, <= 4.3 V; 22 us with 100 ohm)")
two("C8", "220nF 25V", C0603, "CELL0", "GND", LCSC["220n_25V_0603"], "VC0 filter to VSS")
two("D5", "B5819W", "Diode_SMD:D_SOD-123", "CELL0", "GND", LCSC["B5819W"],
    "VC0 clamp: the balance-lead B0 wire and the main BAT- path differ by the pack current x wiring R; keeps VC0 above its -0.3 V abs min", names=("K", "A"))
part("U8", "BQ76907RGRR", "Package_DFN_QFN:QFN-20-1EP_3.5x3.5mm_P0.5mm_EP2x2mm",
     {"1": ("VC4", "CELL2"), "2": ("VC3", "CELL2"), "3": ("VC2", "CELL1"), "4": ("VC1", "CELL1"), "5": ("VC0", "CELL0"),
      "6": ("SRP", "GND"), "7": ("SRN", "GND"), "8": ("TS", "GND"), "9": ("DSG", "NC"), "10": ("CHG", "NC"),
      "11": ("VSS", "GND"), "12": ("SCL", "BMS_SCL"), "13": ("SDA", "BMS_SDA"), "14": ("ALERT", "BMS_ALERT"),
      "15": ("REGOUT", "BMS_REG"), "16": ("REGSRC", "BMS_BAT"), "17": ("BAT", "BMS_BAT"),
      "18": ("VC7", "CELL4"), "19": ("VC6", "CELL3"), "20": ("VC5", "CELL3"), "21": ("PAD", "GND")},
     LCSC["BQ76907"], "per-cell voltages, die temp (balancing unused); protection FET drivers and coulomb counter unused (INA239 does current).  "
     "Firmware: write the 4S cell mode after every POR")
two("R11", "100R 0603", "Resistor_SMD:R_0603_1608Metric", "BAL4", "BMS_BAT", LCSC["R100R_0603"],
    "U8 BAT/REGSRC supply from the balance lead top (TI 8.2: >= 50 ohm filter); 0603 for the ~0.7 mJ plug-in pulse into C9")
two("C9", "4.7uF 50V X7R", C1206, "BMS_BAT", "GND", LCSC["4u7_50V_1206"], "U8 BAT decoupling: >= 1 uF effective at 16.8 V (TI min 1 uF); 50 V also fits 6S")
two("C11", "4.7uF 16V", C0603, "BMS_REG", "GND", LCSC["4u7_16V_0603"], "U8 REGOUT (enabled by OTP default, TI min 1 uF effective at 3.3 V)")

# power LED (SPARC: visible power indicator independent of firmware)
two("R62", "1k", R0402, "+5V", "LED_A", LCSC["R1k"], "power LED, ~3 mA")
part("D3", "LED red", "LED_SMD:LED_0603_1608Metric", {"1": ("K", "GND"), "2": ("A", "LED_A")}, LCSC["LED"],
     "power LED on +5V (KiCad pad 1 = K; the KENTO drawing numbers the other way: check the cathode mark in the JLC preview)")

# ============================================================== weapon: DRV8323RH (U2, hardware/pin-strapped variant) + 6 FETs
# No SPI: settings are strap resistors (SLVSDJ3D Figures 8-23/8-24, EC table), so ENABLE (sleep) can gate the driver
# without losing configuration.
W = "W_"
U2 = {
    "1": ("FB", "BUCK_FB"), "2": ("PGND", "GND"), "3": ("CPL", "U2_CPL"), "4": ("CPH", "U2_CPH"),
    "5": ("VCP", "U2_VCP"), "6": ("VM", "VBAT"), "7": ("VDRAIN", "VBAT"),
    "8": ("GHA", "W_GHA"), "9": ("SHA", "W_A"), "10": ("GLA", "W_GLA"), "11": ("SPA", "W_SLA"), "12": ("SNA", "W_SNA"),
    "13": ("SNB", "W_SNB"), "14": ("SPB", "W_SLB"), "15": ("GLB", "W_GLB"), "16": ("SHB", "W_B"), "17": ("GHB", "W_GHB"),
    "18": ("GHC", "W_GHC"), "19": ("SHC", "W_C"), "20": ("GLC", "W_GLC"), "21": ("SPC", "W_SLC"), "22": ("SNC", "W_SNC"),
    "23": ("SOC", "W_SOC"), "24": ("SOB", "W_SOB"), "25": ("SOA", "W_SOA"), "26": ("VREF", "+3V3"),
    "27": ("DGND", "GND"), "28": ("nFAULT", "W_nFAULT"), "29": ("MODE", "U2_MODE"), "30": ("IDRIVE", "U2_IDRIVE"),
    "31": ("VDS", "U2_VDS"), "32": ("GAIN", "NC"), "33": ("ENABLE", "W_EN"), "34": ("CAL", "GND"),
    "35": ("AGND", "GND"), "36": ("DVDD", "U2_DVDD"), "37": ("INHA", "W_INHA"), "38": ("INLA", "W_INLA"),
    "39": ("INHB", "W_INHB"), "40": ("INLB", "W_INLB"), "41": ("INHC", "W_INHC"), "42": ("INLC", "W_INLC"),
    "43": ("BGND", "GND"), "44": ("CB", "BUCK_CB"), "45": ("SW", "BUCK_SW"), "46": ("NC", "NC"),
    "47": ("VIN", "VBAT"), "48": ("nSHDN", "BUCK_EN"), "49": ("PAD", "GND"),
}
part("U2", "DRV8323RHRGZR", "Package_DFN_QFN:Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm", U2, LCSC["DRV8323RHRGZR"],
     "weapon gate driver + 3 CSA + 5 V/0.6 A buck; GAIN pin open (Hi-Z) = 20 V/V; CAL tied low (offset calibrated in firmware); "
     "nSHDN = UVLO divider (logic cutoff)")
two("R44", "47k 1%", R0402, "U2_MODE", "GND", LCSC["R47k"], "MODE = 47k to AGND: 3x PWM (INHx = PWM, INLx = phase enable, INLx 0 = Hi-Z)")
two("R45", "75k 1%", R0402, "U2_IDRIVE", "GND", LCSC["R75k"], "IDRIVE = 75k to AGND: 60 mA source / 120 mA sink (spice/sim_weapon_bridge.py)")
two("R46", "18k 1%", R0402, "U2_VDS", "GND", LCSC["R18k"], "VDS = 18k to AGND: VDS OCP 0.13 V (~60 A hot, shoot-through / hard-short backstop; 4 ms auto-retry)")
two("C20", "47nF 50V", C0603, "U2_CPH", "U2_CPL", LCSC["47n_50V_0603"], "charge-pump flying cap (VM-rated)")
two("C21", "1uF 50V", C0603, "U2_VCP", "VBAT", LCSC["1u_50V_0603"], "VCP to VM (sees ~11 V; 0603 50 V keeps ~0.8 uF effective)")
two("C22", "1uF 25V", C0402, "U2_DVDD", "GND", LCSC["1u_25V_0402"], "DVDD 3.3 V internal regulator")
two("C23", "100nF 16V", C0402, "+3V3", "GND", LCSC["100n_16V_0402"], "VREF (CSA supply/reference) at U2 pin 26")
two("C24", "100nF 50V", C0603, "VBAT", "GND", LCSC["100n_50V_0603"], "VM at U2 pin 6")
two("C25", "10uF 50V", C1206, "VBAT", "GND", LCSC["10u_50V_1206"], "weapon bridge local, high-side drains")
two("C26", "10uF 50V", C1206, "VBAT", "GND", LCSC["10u_50V_1206"], "weapon bridge local, high-side drains")
two("C31", "10uF 50V", C1206, "VBAT", "GND", LCSC["10u_50V_1206"], "weapon bridge local: one 10 uF per half-bridge (C25 A, C26 B, C31 C)")
# buck (LMR16006X core, 0.7 MHz): 5 V / 0.6 A for the compute board and the 3.3 V LDO
two("C27", "2.2uF 50V", C0805, "VBAT", "GND", LCSC["2u2_50V_0805"], "buck VIN at pin 47")
two("C28", "100nF 50V", C0603, "BUCK_CB", "BUCK_SW", LCSC["100n_50V_0603"], "buck bootstrap CB-SW")
two("L1", "FNR5040S220MT 22uH 1.8A", "Inductor_SMD:L_Changjiang_FNR5040S", "BUCK_SW", "+5V", LCSC["L22u"],
    "buck inductor: Isat 1.6 A min / 1.8 A typ vs buck current limit 1.2 A typ / 1.7 A max (soft ferrite roll-off only in a +5V short)")
two("D2", "SS34 40V 3A", "Diode_SMD:D_SMA", "BUCK_SW", "GND", LCSC["SS34"], "buck catch diode (carries ~ILIMIT continuously into a shorted +5V)", names=("K", "A"))
two("R20", "56k 1%", R0402, "+5V", "BUCK_FB", LCSC["R56k"], "FB top: Vout = 0.765 V x (1 + 56k/10k) = 5.05 V")
two("R21", "10k 1%", R0402, "BUCK_FB", "GND", LCSC["R10k"], "FB bottom")
two("C29", "22uF 25V", C0805, "+5V", "GND", LCSC["22u_25V_0805"], "buck output")
two("C30", "22uF 25V", C0805, "+5V", "GND", LCSC["22u_25V_0805"], "buck output")

# 3 half bridges: HYG015N04LS1C2 (40 V, 1.4 mOhm typ @ 10 V, PDFN 5x6).  A 3.3x3.3 40 V FET (<=5 mOhm) saves ~40 % bridge area
for ph, hi, lo, shunt, nt in (("A", "Q1", "Q2", "RS1", "NT1"), ("B", "Q3", "Q4", "RS2", "NT2"), ("C", "Q5", "Q6", "RS3", "NT3")):
    fet = lambda d, g, s: {"1": ("S", s), "2": ("S", s), "3": ("S", s), "4": ("G", g), "5": ("D", d)}   # HYG015N04LS1C2 on PQFN-8-EP 6x5: leads 1-3 S, 4 G, tab 5 D
    part(hi, "HYG015N04LS1C2", "Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic", fet("VBAT", f"W_GH{ph}", f"W_{ph}"), LCSC["FET"], f"weapon phase {ph} high side")
    part(lo, "HYG015N04LS1C2", "Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic", fet(f"W_{ph}", f"W_GL{ph}", f"W_SL{ph}"), LCSC["FET"], f"weapon phase {ph} low side")
    two(shunt, "2mR 1% 2512", "thumbsup:R_2512_HoLR_1-4mR", f"W_SL{ph}", "GND", LCSC["SHUNT_2m"], f"phase {ph} low-side shunt; custom land = Milliohm HoLR 1-4 mOhm pattern (2.0 mm terminals), Kelvin taps at the pad inner edges")
    two(nt, "NetTie", "NetTie:NetTie-2_SMD_Pad0.5mm", f"W_SN{ph}", "GND", desc=f"Kelvin tie SN{ph} to the shunt's ground pad", names=("1", "2"))
    part(f"J_W{ph}", f"Weapon {ph}", "Connector_Wire:SolderWire-1.5sqmm_1x01_D1.7mm_OD3.9mm", {"1": (ph, f"W_{ph}")}, desc=f"weapon motor phase {ph}")
    # phase voltage divider (catch-spinning-drum restart, six-step BEMF, sensorless observer check)
    k = 22 + 2 * (ord(ph) - 65)
    two(f"R{k}", "68k 1%", R0402, f"W_{ph}", f"W_V{ph}", LCSC["R68k"], f"phase {ph} divider top (25.2 V -> 3.23 V)")
    two(f"R{k+1}", "10k 1%", R0402, f"W_V{ph}", "GND", LCSC["R10k"], f"phase {ph} divider bottom")
    two(f"C{41 + ord(ph) - 65}", "1nF 50V", C0402, f"W_V{ph}", "GND", LCSC["1n_50V_0402"],
        f"phase {ph} divider filter at the MCU (8.8 us; ADC sample kickback, ring suppression, keeps a TVS-level spike below the 4 V abs max of PA4/PA5 (TT_a); PA2 is FT_a)")

# weapon interlock: each phase enable INLx = TIM1_CHxN AND W_ARM_S (dynamic ARM from the compute board, below).  In 3x PWM mode
# INLx = 0 puts the phase Hi-Z whatever INHx does, so without ARM the weapon coasts and cannot be driven, and the
# DRV8323 stays awake (ENABLE = W_EN from the MCU) so nFAULT/CSA keep working.  W_ARM_S also goes to the MCU (PD2, FT).
part("U6", "SN74LVC08APWR", "Package_SO:TSSOP-14_4.4x5mm_P0.65mm",
     {"1": ("1A", "W_INLA_M"), "2": ("1B", "W_ARM_S"), "3": ("1Y", "W_INLA"),
      "4": ("2A", "W_INLB_M"), "5": ("2B", "W_ARM_S"), "6": ("2Y", "W_INLB"), "7": ("GND", "GND"),
      "8": ("3Y", "W_INLC"), "9": ("3A", "W_INLC_M"), "10": ("3B", "W_ARM_S"),
      "11": ("4Y", "NC"), "12": ("4A", "GND"), "13": ("4B", "GND"), "14": ("VCC", "+3V3")},
     LCSC["74LVC08"], "hardware weapon interlock (SN74LVC08A pinout, SCAS283; 4th gate inputs grounded)")
two("C40", "100nF 16V", C0402, "+3V3", "GND", LCSC["100n_16V_0402"], "U6 decoupling")
two("R40", "100k", R0402, "W_EN", "GND", LCSC["R100k"], "U2 ENABLE low (sleep) while the MCU is in reset")
# dynamic ARM: the compute board must keep toggling W_ARM_CLK from its control loop (>= 500 Hz, 3.3 V square wave).
# C15/D9 rectify it into W_ARM (2.5-2.9 V at >= 500 Hz); stuck high, stuck low, a hung compute board or an unplugged header
# let R41 discharge C16 below the U14 Schmitt threshold in 30-200 ms, which floats the weapon (INLx = 0).  W_ARM_S
# (U14 output) feeds U6 and PD2.
two("R18", "100k", R0402, "W_ARM_CLK", "GND", LCSC["R100k"], "W_ARM_CLK defined low with the header unplugged")
two("C15", "470nF 25V", C0603, "W_ARM_CLK", "ARM_AC", LCSC["470n_25V_0603"], "ARM charge pump: coupling cap (a DC level passes nothing; < C16 so a clock stuck high cannot hold W_ARM up)")
part("D9", "BAT54S", "Package_TO_SOT_SMD:SOT-23",
     {"1": ("A1", "GND"), "2": ("K2", "W_ARM"), "3": ("K1A2", "ARM_AC")}, LCSC["BAT54S"],
     "ARM charge pump: clamp (ARM_AC >= -0.2 V) + rectifier into W_ARM (Nexperia BAT54S,215: 1 A1, 2 K2, 3 common)")
two("C16", "2.2uF 16V", C0603, "W_ARM", "GND", LCSC["2u2_16V_0603"], "ARM hold cap: ~8 edges to arm; tau 103 ms with R41")
two("R41", "47k 1%", R0402, "W_ARM", "GND", LCSC["R47k"],
    "ARM bleed: W_ARM below U14's VT- 30-200 ms after the toggling stops (stuck high or low, 25-85 C incl. D9 leakage, VT- 0.8-1.33 V); swamps input leakage")
part("U14", "74LVC1G17SE-7", "Package_TO_SOT_SMD:SOT-353_SC-70-5",
     {"1": ("NC", "NC"), "2": ("A", "W_ARM"), "3": ("GND", "GND"), "4": ("Y", "W_ARM_S"), "5": ("VCC", "+3V3")}, LCSC["LVC1G17"],
     "Schmitt buffer on the slow RC ARM level (Diodes DS35124: SOT-353 1 NC, 2 A, 3 GND, 4 Y, 5 VCC; VT+ <= 2.0 V, VT- >= 0.8 V at 3 V): clean edges into U6 and PD2")
two("C17", "100nF 16V", C0402, "+3V3", "GND", LCSC["100n_16V_0402"], "U14 decoupling")
two("R19", "10k 1%", R0402, "W_ARM_S", "GND", LCSC["R10k"], "W_ARM_S held low if U14's output opens or U14 is unpowered (U6 inputs and PD2 must not float; 10 k beats 3 x 5 uA worst-case input leakage)")
for k, ph in enumerate("ABC"):
    two(f"R{47 + k}", "100k", R0402, f"W_INL{ph}_M", "GND", LCSC["R100k"], f"TIM1_CH{k+1}N low while the MCU is in reset (U6 input must not float)")
two("R42", "10k 1%", R0402, "W_nFAULT", "+3V3", LCSC["R10k"], "nFAULT pull-up")
two("C19", "1nF 50V", C0402, "W_nFAULT", "GND", LCSC["1n_50V_0402"], "W_nFAULT glitch filter at PC13 (TIM1 BKF = 0 is required for the comparator trip, so the pin needs analog filtering; assertion is a strong open-drain pull-down, only the release slows to ~10 us)")
two("R43", "10k 1%", R0402, "+3V3", "W_NTC", LCSC["R10k"], "weapon FET NTC pull-up")
two("TH1", "NCP18XH103F03RB", "Resistor_SMD:R_0603_1608Metric", "W_NTC", "GND", LCSC["NTC10k"], "at the weapon FETs")
two("C44", "100nF 16V", C0402, "W_NTC", "GND", LCSC["100n_16V_0402"], "NTC node filter at the MCU")

# ============================================================== drive: 2 x DRV8316CR (U3 left, U4 right)
def drv8316(ref, s):
    pins = {
        "1": ("NC", "NC"), "2": ("AGND", "GND"), "3": ("FB_BK", f"{s}_FBBK"), "4": ("GND_BK", "GND"), "5": ("SW_BK", f"{s}_SWBK"),
        "6": ("CPL", f"{s}_CPL"), "7": ("CPH", f"{s}_CPH"), "8": ("CP", f"{s}_CP"), "9": ("VM", f"{s}_VM"), "10": ("VM", f"{s}_VM"),
        "11": ("VM", f"{s}_VM"), "12": ("PGND", "GND"), "13": ("OUTA", f"{s}_A"), "14": ("OUTA", f"{s}_A"), "15": ("PGND", "GND"),
        "16": ("OUTB", f"{s}_B"), "17": ("OUTB", f"{s}_B"), "18": ("PGND", "GND"), "19": ("OUTC", f"{s}_C"), "20": ("OUTC", f"{s}_C"),
        "21": ("DRVOFF", "DRV_OFF"), "22": ("nFAULT", f"{s}_nFAULT"), "23": ("nSLEEP", "+3V3"), "24": ("NC", "NC"),
        "25": ("AVDD", f"{s}_AVDD"), "26": ("AGND", "GND"), "27": ("INHA", f"{s}_INHA"), "28": ("INLA", "+3V3"),
        "29": ("INHB", f"{s}_INHB"), "30": ("INLB", "+3V3"), "31": ("INHC", f"{s}_INHC"), "32": ("INLC", "+3V3"),
        "33": ("SDO", "SPI_MISO"), "34": ("SDI", "SPI_MOSI"), "35": ("SCLK", "SPI_SCK"), "36": ("nSCS", f"{s}_nCS"),
        "37": ("VREF/ILIM", f"{s}_AVDD"), "38": ("SOC", f"{s}_SOC"), "39": ("SOB", f"{s}_SOB"), "40": ("SOA", f"{s}_SOA"),
        "41": ("PAD", "GND"),
    }
    side = "left" if s == "L" else "right"
    part(ref, "DRV8316CRRGFR", "thumbsup:TI_RGF0040E_VQFN-40-1EP_5x7mm_P0.5mm_EP3.7x5.7mm", pins, LCSC["DRV8316CRRGFR"],
         f"drive {side}: 3 half bridges 8 A pk, 3 CSA (no shunts), SPI; 3x PWM mode, INLx tied high, DRVOFF shared.  "
         f"Footprint: draw from TI RGF0040E land pattern (not in the KiCad library)")
    n = int(ref[1:]) * 100
    two(f"C{n}", "100nF 50V", C0603, f"{s}_VM", "GND", LCSC["100n_50V_0603"], f"{ref} VM pin 9")
    two(f"C{n+1}", "100nF 50V", C0603, f"{s}_VM", "GND", LCSC["100n_50V_0603"], f"{ref} VM pin 11")
    two(f"C{n+2}", "10uF 50V", C1206, f"{s}_VM", "GND", LCSC["10u_50V_1206"], f"{ref} VM bulk")
    two(f"C{n+8}", "10uF 50V", C1206, f"{s}_VM", "GND", LCSC["10u_50V_1206"], f"{ref} VM bulk (1206 50 V X5R keeps ~4 uF at 16.8 V each)")
    two(f"C{n+9}", "10uF 50V", C1206, f"{s}_VM", "GND", LCSC["10u_50V_1206"], f"{ref} VM bulk (with R{n+2}: ~16 uF effective behind 0.1 ohm)")
    two(f"C{n+10}", "10uF 50V", C1206, f"{s}_VM", "GND", LCSC["10u_50V_1206"], f"{ref} VM bulk")
    two(f"R{n+2}", "0.1R 1W 2512", "Resistor_SMD:R_2512_6332Metric", "VBAT", f"{s}_VM", LCSC["R0R1_2512"],
        f"{ref} VM feed: with C{n+2}/C{n+8}-C{n+10} a ~1.6 us RC that isolates the DRV8316 (4 V/us VM abs max) from bus events: "
        "loaded contact bounce 3.75 -> 2.26 V/us, worst re-close 3.44 -> 2.09 V/us, weapon fault-clear kick 9-11 -> ~1-2 V/us (review sims); "
        "0.11/0.24/0.52 W at 1/1.5/2 A rms incl. the drive's own PWM ripple (RC corner ~99 kHz), <= ~1 W in weapon bursts; 0.8 V drop at an 8 A peak")
    two(f"C{n+3}", "1uF 50V", C0603, f"{s}_CP", f"{s}_VM", LCSC["1u_50V_0603"], f"{ref} CP to VM")
    two(f"C{n+4}", "47nF 50V", C0603, f"{s}_CPH", f"{s}_CPL", LCSC["47n_50V_0603"], f"{ref} charge-pump flying cap (>=2x VM)")
    two(f"C{n+5}", "1uF 50V", C0603, f"{s}_AVDD", "GND", LCSC["1u_50V_0603"], f"{ref} AVDD (TI: 0.7-1.3 uF effective at 3.3 V)")
    two(f"C{n+6}", "100nF 16V", C0402, f"{s}_AVDD", "GND", LCSC["100n_16V_0402"], f"{ref} VREF pin 37 (tied to its own AVDD: ROC is 2.8 V..AVDD, and AVDD can be as low as 3.1 V)")
    # buck unused: SLVSH07 8.3.4.2 / 9.2.1.1.5 resistor mode, RBK 22 ohm + CBK 22 uF populated, then CTRL6 = 0x19 over SPI
    two(f"R{n}", "22R 1206", "Resistor_SMD:R_1206_3216Metric", f"{s}_SWBK", f"{s}_FBBK", LCSC["R22_1206"],
        f"{ref} buck unused: resistor mode (SLVSH07 9.2.1.1.5); 1206 for dissipation until firmware sets BUCK_DIS")
    two(f"C{n+7}", "22uF 25V", C0805, f"{s}_FBBK", "GND", LCSC["22u_25V_0805"], f"{ref} buck unused: CBK (SLVSH07: 22 uF, >= 10 V)")
    two(f"R{n+1}", "10k 1%", R0402, f"{s}_nFAULT", f"{s}_AVDD", LCSC["R10k"],
        f"{ref} nFAULT pull-up to its own AVDD (TI: pull up to AVDD; valid whenever the chip is powered)")
    for ph in "ABC":
        part(f"J_{s}{ph}", f"Drive {s} {ph}", "Connector_Wire:SolderWire-0.5sqmm_1x01_D0.9mm_OD2.1mm", {"1": (ph, f"{s}_{ph}")}, desc=f"drive {side} motor phase {ph}")


drv8316("U3", "L")
drv8316("U4", "R")
two("R50", "10k 1%", R0402, "DRV_OFF", "+3V3", LCSC["R10k"], "DRVOFF high = both drive bridges Hi-Z until the MCU drives it low")

# drive sensor connectors: Hall (UVW) or MT6701 (ABZ or UVW), motor NTC.
# VS: JP selects 3.3 V (default) or 5 V, then a 100 mA current-limited switch so a crushed cable cannot pull down
# the logic rails.  S1-S3: 4.7k pull-ups (open-drain Halls) into a 3.3 V Schmitt buffer whose inputs tolerate 5.5 V,
# so 5 V push-pull sensors are safe and the MCU's TT_a pins (PB0, PB10) never see more than 3.3 V.
for s, jref, jp, rt, ub, us, rp, cn, sr, dt in (("L", "J2", "JP1", "R52", "U9", "U11", 54, 45, 110, 7),
                                               ("R", "J3", "JP2", "R53", "U10", "U12", 57, 48, 114, 8)):
    part(jref, "SH1.0 6P SMD R/A", "thumbsup:SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB",
         {"1": ("VS", f"{s}_VS"), "2": ("GND", "GND"), "3": ("S1", f"{s}_H1"), "4": ("S2", f"{s}_H2"),
          "5": ("S3", f"{s}_H3"), "6": ("TEMP", f"{s}_TEMPJ"), "MP": ("MP", "GND")},
         LCSC["SM06B"], f"drive {s} sensor: 1 VS, 2 GND, 3 H1/A/U, 4 H2/B/V, 5 H3/Z/W, 6 motor NTC (JST SH compatible)")
    part(jp, "SolderJumper_3", "Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm",
         {"1": ("A", "+3V3"), "2": ("C", f"{s}_VSRC"), "3": ("B", "+5V")},
         desc=f"sensor {s} supply: 1-2 = 3.3 V (default, bridged), 2-3 = 5 V (5 V Hall ICs)")
    part(us, "TPS22945DCKR", "Package_TO_SOT_SMD:SOT-353_SC-70-5",
         {"1": ("VOUT", f"{s}_VS"), "2": ("GND", "GND"), "3": ("OC", "NC"), "4": ("ON", f"{s}_VSRC"), "5": ("VIN", f"{s}_VSRC")},
         LCSC["TPS22945"], f"sensor {s} supply switch: 100-200 mA limit, 5-20 ms blanking, 80 ms auto-restart (SLVS832D); ON tied to VIN; OC flag unused")
    two(f"C{cn}", "4.7uF 16V", C0603, f"{s}_VSRC", "GND", LCSC["4u7_16V_0603"], f"{us} VIN (>= the output cap, TI; holds +3V3 during the switch's response to a hard short)")
    two(f"C{cn + 1}", "1uF 25V", C0402, f"{s}_VS", "GND", LCSC["1u_25V_0402"], f"{us} VOUT / sensor supply at {jref}")
    part(ub, "SN74LVC3G17DCUR", "Package_SO:VSSOP-8_2.3x2mm_P0.5mm",
         {"1": ("1A", f"{s}_H1B"), "7": ("1Y", f"{s}_S1"), "3": ("2A", f"{s}_H2B"), "5": ("2Y", f"{s}_S2"),
          "6": ("3A", f"{s}_H3B"), "2": ("3Y", f"{s}_S3"), "4": ("GND", "GND"), "8": ("VCC", "+3V3")},
         LCSC["LVC3G17"], f"sensor {s} Schmitt buffer (SCES470F pinout: 1A1 3Y2 2A3 GND4 2Y5 3A6 1Y7 VCC8); inputs 5.5 V tolerant")
    two(f"C{cn + 2}", "100nF 16V", C0402, "+3V3", "GND", LCSC["100n_16V_0402"], f"{ub} VCC")
    for k in range(3):
        two(f"R{rp + k}", "4.7k", R0402, f"{s}_H{k + 1}", "+3V3", LCSC["R4k7"], f"sensor {s} line {k + 1} pull-up (open-drain Halls; noise margin)")
        two(f"R{sr + k}", "1k", R0402, f"{s}_H{k + 1}", f"{s}_H{k + 1}B", LCSC["R1k"], f"sensor {s} line {k + 1} series R (with the optional C: phase-coupled glitch filter)")
        two(f"C{sr + k}", "1nF 50V", C0402, f"{s}_H{k + 1}B", "GND", LCSC["1n_50V_0402"],
            f"sensor {s} line {k + 1} filter, DNP by default (fit for Hall sensors: 1 us; never with MT6701 ABZ)", dnp=True)
    two(rt, "10k 1%", R0402, "+3V3", f"{s}_MTEMP", LCSC["R10k"], f"motor {s} NTC pull-up")
    two(f"R{sr + 3}", "2.2k 0603", "Resistor_SMD:R_0603_1608Metric", f"{s}_TEMPJ", f"{s}_MTEMP", LCSC["R2k2_0603"], f"motor {s} NTC series R: limits a phase-to-TEMP cable short to ~6 mA into D{dt} (known offset, subtract in firmware)")
    part(f"D{dt}", "BAV99", "Package_TO_SOT_SMD:SOT-23",
         {"1": ("A1", "GND"), "2": ("K2", "+3V3"), "3": ("K1A2", f"{s}_MTEMP")}, LCSC["BAV99"],
         f"motor {s} NTC clamp to GND / +3V3 (BAV99,215: 1 = anode D1, 2 = cathode D2, 3 = common; nA leakage, unlike a Schottky)")

# ============================================================== MCU (U1) and logic power
MCU_PINS = {
    # pin: (name, net, required alternate function or '' for GPIO/analog-only)
    "1": ("VBAT", "+3V3", ""), "2": ("PC13", "W_nFAULT", "TIM1_BKIN"), "3": ("PC14", "DRV_OFF", ""),
    "4": ("PC15", "R_nFAULT", ""), "5": ("PF0", "L_MTEMP", "ADC1_IN10"), "6": ("PF1", "R_MTEMP", "ADC2_IN10"),
    "7": ("PG10-NRST", "NRST", ""), "8": ("PC0", "W_INHA", "TIM1_CH1"), "9": ("PC1", "W_INHB", "TIM1_CH2"),
    "10": ("PC2", "R_INHB", "TIM20_CH2"), "11": ("PC3", "L_SOC_F", "OPAMP5_VINP"), "12": ("PA0", "W_SOA", "ADC1_IN1"),
    "13": ("PA1", "W_SOB", "ADC2_IN2"), "14": ("PA2", "W_VC", "ADC1_IN3"), "15": ("VSS", "GND", ""),
    "16": ("VDD", "+3V3", ""), "17": ("PA3", "VBAT_SNS", "ADC1_IN4"), "18": ("PA4", "W_VA", "ADC2_IN17"),
    "19": ("PA5", "W_VB", "ADC2_IN13"), "20": ("PA6", "W_NTC", "ADC2_IN3"), "21": ("PA7", "W_INLA_M", "TIM1_CH1N"),
    "22": ("PC4", "MB_TX", "USART1_TX"), "23": ("PC5", "MB_RX", "USART1_RX"), "24": ("PB0", "L_S3", "TIM3_CH3"),
    "25": ("PB1", "R_SOC_F", "ADC3_IN1"), "26": ("PB2", "R_INHA", "TIM20_CH1"), "27": ("VSSA", "GND", ""),
    "28": ("VREF+", "+3V3A", ""), "29": ("VDDA", "+3V3A", ""), "30": ("PB10", "R_S3", "TIM2_CH3"),
    "31": ("VSS", "GND", ""), "32": ("VDD", "+3V3", ""), "33": ("PB11", "W_SOC", "COMP6_INP"),
    "34": ("PB12", "R_SOA_F", "ADC4_IN3"), "35": ("PB13", "R_SOB_F", "ADC3_IN5"), "36": ("PB14", "W_INLB_M", "TIM1_CH2N"),
    "37": ("PB15", "W_INLC_M", "TIM1_CH3N"), "38": ("PC6", "L_S1", "TIM3_CH1"), "39": ("PC7", "L_INHB", "TIM8_CH2"),
    "40": ("PC8", "R_INHC", "TIM20_CH3"), "41": ("PC9", "L_nCS", ""), "42": ("PA8", "L_SOA_F", "ADC5_IN1"),
    "43": ("PA9", "L_SOB_F", "ADC5_IN2"), "44": ("PA10", "W_INHC", "TIM1_CH3"), "45": ("PA11", "INA_nCS", ""),
    "46": ("PA12", "W_EN", ""), "47": ("VSS", "GND", ""), "48": ("VDD", "+3V3", ""),
    "49": ("PA13", "SWDIO", "SYS_JTMS-SWDIO"), "50": ("PA14", "SWCLK", "SYS_JTCK-SWCLK"), "51": ("PA15", "R_S1", "TIM2_CH1"),
    "52": ("PC10", "SPI_SCK", "SPI3_SCK"), "53": ("PC11", "SPI_MISO", "SPI3_MISO"), "54": ("PC12", "SPI_MOSI", "SPI3_MOSI"),
    "55": ("PD2", "W_ARM_S", ""), "56": ("PB3", "R_S2", "TIM2_CH2"), "57": ("PB4", "R_nCS", ""),
    "58": ("PB5", "L_S2", "TIM3_CH2"), "59": ("PB6", "L_INHA", "TIM8_CH1"), "60": ("PB7", "L_nFAULT", "TIM8_BKIN"),
    "61": ("PB8-BOOT0", "BOOT0", ""), "62": ("PB9", "L_INHC", "TIM8_CH3"), "63": ("VSS", "GND", ""), "64": ("VDD", "+3V3", ""),
}
part("U1", "STM32G474RET6", "Package_QFP:LQFP-64_10x10mm_P0.5mm", {p: (n, net) for p, (n, net, _) in MCU_PINS.items()},
     LCSC["STM32G474RET6"], "170 MHz M4F; TIM1 weapon, TIM8 drive L, TIM20 drive R, TIM3/TIM2 drive sensors, SPI3 to U3/U4/U7, USART1 to compute")
for i, pin in enumerate(("16", "32", "48", "64")):
    two(f"C6{i}", "100nF 16V", C0402, "+3V3", "GND", LCSC["100n_16V_0402"], f"U1 VDD pin {pin}")
two("C64", "4.7uF 16V", C0603, "+3V3", "GND", LCSC["4u7_16V_0603"], "U1 VDD bulk")
two("C65", "100nF 16V", C0402, "+3V3A", "GND", LCSC["100n_16V_0402"], "U1 VDDA pin 29")
two("C66", "4.7uF 16V", C0603, "+3V3A", "GND", LCSC["4u7_16V_0603"], "U1 VREF+ pin 28 bulk (ES0430 multi-ADC noise; moteus practice)")
two("C71", "100nF 16V", C0402, "+3V3A", "GND", LCSC["100n_16V_0402"], "U1 VREF+ pin 28")
two("R60", "0R", R0402, "+3V3", "+3V3A", "C17168", "VDDA feed (0 ohm; fit a 600 ohm@100MHz ferrite if ADC noise is a problem)")
two("C67", "100nF 16V", C0402, "NRST", "GND", LCSC["100n_16V_0402"], "NRST (internal pull-up)")
two("R61", "10k 1%", R0402, "BOOT0", "GND", LCSC["R10k"], "boot from flash")
two("R63", "68k 1%", R0402, "VBAT", "VBAT_SNS", LCSC["R68k"], "pack divider top (25.2 V -> 3.23 V)")
two("R64", "10k 1%", R0402, "VBAT_SNS", "GND", LCSC["R10k"], "pack divider bottom")
two("R33", "100k", R0402, "VBAT_SNS", "VBAT_SNS_H", LCSC["R100k"], "header branch of the pack divider: a compute-board pin's reset pull-down (RP2040 ~50 k) shifts the MCU reading < 6 % instead of 10-15 %; the compute board reads it through this 100 k (add ~10 nF at its ADC pin)")
two("C68", "100nF 16V", C0402, "VBAT_SNS", "GND", LCSC["100n_16V_0402"], "pack divider filter (0.87 ms; the fast bus OV trip is the INA239 BOVL alert)")
two("C74", "100nF 16V", C0402, "+3V3", "GND", LCSC["100n_16V_0402"], "U1 VBAT pin 1")
two("C72", "100nF 16V", C0402, "L_MTEMP", "GND", LCSC["100n_16V_0402"], "motor L NTC filter at PF0")
two("C73", "100nF 16V", C0402, "R_MTEMP", "GND", LCSC["100n_16V_0402"], "motor R NTC filter at PF1")
# drive CSA outputs: TI SLVSH07 9.2.1.1.6 RC (330 ohm + 22 pF) at each ADC / OPAMP pin
for s in "LR":
    for ph in "ABC":
        two(f"R{'7' if s == 'L' else '8'}{ord(ph) - 65}", "330R", R0402, f"{s}_SO{ph}", f"{s}_SO{ph}_F", LCSC["R330"], f"drive {s} CSA {ph} filter R")
        two(f"C{'8' if s == 'L' else '9'}{ord(ph) - 65}", "22pF C0G", C0402, f"{s}_SO{ph}_F", "GND", LCSC["22p_0402"], f"drive {s} CSA {ph} filter C (at the MCU pin)")

part("U5", "AP2112K-3.3TRG1", "Package_TO_SOT_SMD:SOT-23-5",
     {"1": ("VIN", "+5V"), "2": ("GND", "GND"), "3": ("EN", "+5V"), "4": ("NC", "NC"), "5": ("VOUT", "+3V3")},
     LCSC["AP2112K-3.3"], "3.3 V / 600 mA LDO for MCU, driver logic, CSA references, sensors")
two("C69", "1uF 25V", C0402, "+5V", "GND", LCSC["1u_25V_0402"], "U5 in")
two("C70", "1uF 25V", C0402, "+3V3", "GND", LCSC["1u_25V_0402"], "U5 out")

# ============================================================== board-to-board header (to the compute board)
part("J1", "B2B 2x10 1.27mm male", "thumbsup:BOOMELE_1.27-2x10P_SMD",
     {"1": ("+5V", "+5V"), "2": ("+5V", "+5V"), "3": ("GND", "GND"), "4": ("GND", "GND"),
      "5": ("MB_TX", "MB_TX"), "6": ("MB_RX", "MB_RX"), "7": ("SPARE1", "NC"), "8": ("NRST", "NRST"),
      "9": ("SWDIO", "SWDIO"), "10": ("SWCLK", "SWCLK"), "11": ("VBAT_SNS_H", "VBAT_SNS_H"), "12": ("GND", "GND"),
      "13": ("+5V", "+5V"), "14": ("GND", "GND"), "15": ("BMS_SDA", "BMS_SDA"), "16": ("BMS_SCL", "BMS_SCL"),
      "17": ("BMS_ALERT", "BMS_ALERT"), "18": ("SPARE2", "NC"), "19": ("W_ARM_CLK", "W_ARM_CLK"), "20": ("GND", "GND")},
     LCSC["B2B_M"], "to the compute board: 5 V out (<=0.45 A, 3 pins), UART, weapon ARM (toggled, pin 19 next to GND), reset + SWD for programming, pack voltage, cell monitor I2C + alert (pull-ups on the compute board); 7 and 18 spare.  Footprint: vendor land (20 x 1.5x0.74 mm pads at x = +-2.5 mm, odd pins left); the compute-board socket footprint is the mirror image")
two("R16", "10k 1%", R0402, "NRST", "+3V3", LCSC["R10k"], "NRST pull-up: an RP2040 pin in reset (~50k pull-down) must not hold NRST mid-level")
two("R17", "10k 1%", R0402, "MB_RX", "+3V3", LCSC["R10k"], "MB_RX pull-up (compute board absent or in reset)")
for i, (n, net) in enumerate((("3V3", "+3V3"), ("SWDIO", "SWDIO"), ("SWCLK", "SWCLK"), ("NRST", "NRST"), ("GND", "GND"),
                              ("W_ARM", "W_ARM"), ("W_EN", "W_EN"), ("DRV_OFF", "DRV_OFF"), ("W_nFAULT", "W_nFAULT"),
                              ("VBAT", "VBAT"), ("5V", "+5V"), ("GND", "GND")), 1):
    part(f"TP{i}", n, "TestPoint:TestPoint_Pad_D1.0mm", {"1": (n, net)}, desc="SWD / bring-up / safety-path test pad")
for i in range(1, 5):
    part(f"MH{i}", "M2 mounting hole", "MountingHole:MountingHole_2.2mm_M2", {},
         desc="NPTH M2 hole for the board-stack standoffs (nylon: no second ground path); the header must carry no mechanical load")

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
    for ref, p in PARTS.items():
        placed = not p["footprint"].startswith(("Connector_Wire", "TestPoint", "NetTie", "Jumper", "MountingHole"))
        if placed and not p["dnp"] and not p["lcsc"].startswith("C"):
            problems.append(f"{ref} {p['value']}: no LCSC part number ({p['lcsc'] or 'empty'})")
    fp_of = defaultdict(set)
    for ref, p in PARTS.items():
        if p["lcsc"]:
            fp_of[p["lcsc"]].add(p["footprint"])
    for lc, fps in fp_of.items():
        if len(fps) > 1:
            problems.append(f"LCSC {lc} is used with different footprints: {sorted(fps)}")
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
        dnp = sorted(r for r, q in PARTS.items() if q["dnp"])
        if dnp:
            f.write("DNP (footprint only, not assembled): " + ", ".join(dnp) + "\n\n")
        for net in sorted(nets, key=lambda n: (n == "NC", n)):
            f.write(f"- **{net}**: " + ", ".join(f"{r}.{n}({nm})" for r, n, nm in sorted(nets[net])) + "\n")
    groups = defaultdict(list)
    for ref, p in PARTS.items():
        if p["dnp"] or p["footprint"].startswith(("Connector_Wire", "TestPoint", "NetTie", "Jumper", "MountingHole")):
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
            f.write(f"| {pin} | {name} | {net} | {af or ('power' if net in ('GND', '+3V3', '+3V3A') else {'NRST': 'reset', 'BOOT0': 'boot mode'}.get(net, 'GPIO / analog'))} |\n")
    n_parts = sum(1 for p in PARTS.values() if not p["footprint"].startswith(("Connector_Wire", "TestPoint", "NetTie", "Jumper", "MountingHole")))
    print(f"{len(PARTS)} refs ({n_parts} placed components), {len([n for n in nets if n != 'NC'])} nets, {len(groups)} BOM lines")
    for p in problems:
        print("PROBLEM:", p)
    print("checks:", "OK" if not problems else f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
