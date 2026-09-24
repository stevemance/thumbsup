"""Parts in the motor-board project library (motor_board.kicad_sym / motor_board.pretty).

One "atomic" symbol per purchased part: pins, footprint, LCSC, MPN and datasheet are fixed, so the
schematic only needs the part placed.  Generic R/C (and the NTC) stay stock Device:R / Device:C /
Device:Thermistor_NTC with fields set per instance.

Sources for every pin table and land pattern are cited next to each entry; build_lib.py writes the
library, check_lib.py verifies it against design/netlist.csv, design/bom.csv and the footprints.

Pin tuple: (number, name, electrical type, side, hidden)
  type: KiCad pin types (input, output, bidirectional, tri_state, passive, power_in, power_out,
        open_collector, no_connect)
  side: L / R / T / B (symbol body side); pins are drawn in the order listed on each side.
"""

DS = "https://www.ti.com/lit/ds/symlink/"

# ---------------------------------------------------------------- new symbols (drawn by build_lib.py)
# Pin numbers and names: datasheet pin-function tables (cited), identical to design/nets.md.
# Types: from the datasheet TYPE column, mapped as I→input, O→output, OD→open_collector,
# I/O→bidirectional, PWR supply/ground→power_in, regulator outputs→power_out; charge-pump, bootstrap,
# switch-node and half-bridge output pins are passive (they only meet capacitors, inductors or
# motor windings, and several same-net pins of one part would otherwise trip ERC).
NEW = {
    # SLVSH07 (DRV8316C) Table 6-1, 40-pin VQFN RGF (DRV8316CR column)
    "DRV8316CRRGFR": dict(lcsc="C5447274", 
        ref="U", desc="Three-phase BLDC motor driver, 40 V 8 A peak, SPI, 3x/6x PWM, integrated CSA (DRV8316C)",
        datasheet=DS + "drv8316c.pdf", fp="motor_board:TI_RGF0040E_VQFN-40-1EP_5x7mm_P0.5mm_EP3.7x5.7mm",
        pins=[
            ("9", "VM", "power_in", "L"), ("10", "VM", "power_in", "L"), ("11", "VM", "power_in", "L"),
            ("8", "CP", "passive", "L"), ("7", "CPH", "passive", "L"), ("6", "CPL", "passive", "L"),
            ("5", "SW_BK", "passive", "L"), ("3", "FB_BK", "passive", "L"),
            ("27", "INHA", "input", "L"), ("28", "INLA", "input", "L"), ("29", "INHB", "input", "L"),
            ("30", "INLB", "input", "L"), ("31", "INHC", "input", "L"), ("32", "INLC", "input", "L"),
            ("21", "DRVOFF", "input", "L"), ("23", "nSLEEP", "input", "L"),
            ("36", "nSCS", "input", "L"), ("35", "SCLK", "input", "L"), ("34", "SDI", "input", "L"),
            ("13", "OUTA", "passive", "R"), ("14", "OUTA", "passive", "R"),
            ("16", "OUTB", "passive", "R"), ("17", "OUTB", "passive", "R"),
            ("19", "OUTC", "passive", "R"), ("20", "OUTC", "passive", "R"),
            ("40", "SOA", "output", "R"), ("39", "SOB", "output", "R"), ("38", "SOC", "output", "R"),
            ("33", "SDO", "tri_state", "R"), ("22", "nFAULT", "open_collector", "R"),
            ("25", "AVDD", "power_out", "R"), ("37", "VREF/ILIM", "power_in", "R"),
            ("1", "NC", "no_connect", "R"), ("24", "NC", "no_connect", "R"),
            ("2", "AGND", "power_in", "B"), ("26", "AGND", "power_in", "B"), ("4", "GND_BK", "power_in", "B"),
            ("12", "PGND", "power_in", "B"), ("15", "PGND", "power_in", "B"), ("18", "PGND", "power_in", "B"),
            ("41", "PAD", "power_in", "B"),
        ]),
    # SLVSDJ3D (DRV8323) Table 6-4, 48-pin VQFN RGZ (DRV8323RH column)
    "DRV8323RHRGZR": dict(lcsc="C543035", 
        ref="U", desc="Three-phase smart gate driver, 6-60 V, hardware interface, 3 CSAs, 600 mA buck (DRV8323RH)",
        datasheet=DS + "drv8323.pdf", fp="Package_DFN_QFN:Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm",
        pins=[
            ("6", "VM", "power_in", "L"), ("7", "VDRAIN", "input", "L"), ("5", "VCP", "passive", "L"),
            ("4", "CPH", "passive", "L"), ("3", "CPL", "passive", "L"),
            ("47", "VIN", "power_in", "L"), ("44", "CB", "passive", "L"), ("45", "SW", "passive", "L"),
            ("1", "FB", "input", "L"), ("48", "nSHDN", "input", "L"),
            ("37", "INHA", "input", "L"), ("38", "INLA", "input", "L"), ("39", "INHB", "input", "L"),
            ("40", "INLB", "input", "L"), ("41", "INHC", "input", "L"), ("42", "INLC", "input", "L"),
            ("33", "ENABLE", "input", "L"), ("29", "MODE", "input", "L"), ("30", "IDRIVE", "input", "L"),
            ("31", "VDS", "input", "L"), ("32", "GAIN", "input", "L"), ("34", "CAL", "input", "L"),
            ("8", "GHA", "output", "R"), ("9", "SHA", "bidirectional", "R"), ("10", "GLA", "output", "R"),
            ("11", "SPA", "input", "R"), ("12", "SNA", "input", "R"),
            ("17", "GHB", "output", "R"), ("16", "SHB", "bidirectional", "R"), ("15", "GLB", "output", "R"),
            ("14", "SPB", "input", "R"), ("13", "SNB", "input", "R"),
            ("18", "GHC", "output", "R"), ("19", "SHC", "bidirectional", "R"), ("20", "GLC", "output", "R"),
            ("21", "SPC", "input", "R"), ("22", "SNC", "input", "R"),
            ("25", "SOA", "output", "R"), ("24", "SOB", "output", "R"), ("23", "SOC", "output", "R"),
            ("28", "nFAULT", "open_collector", "R"), ("36", "DVDD", "power_out", "R"),
            ("26", "VREF", "power_in", "R"), ("46", "NC", "no_connect", "R"),
            ("2", "PGND", "power_in", "B"), ("27", "DGND", "power_in", "B"), ("35", "AGND", "power_in", "B"),
            ("43", "BGND", "power_in", "B"), ("49", "PAD", "power_in", "B"),
        ]),
    # SLUSE96A (BQ76907) Table 5-1, 20-pin VQFN RGR
    "BQ76907RGRR": dict(lcsc="C22458649", 
        ref="U", desc="2-7S battery monitor and protector, I2C (BQ76907, CRC off)",
        datasheet=DS + "bq76907.pdf", fp="Package_DFN_QFN:QFN-20-1EP_3.5x3.5mm_P0.5mm_EP2x2mm",
        pins=[
            ("17", "BAT", "power_in", "L"), ("16", "REGSRC", "power_in", "L"),
            ("18", "VC7", "input", "L"), ("19", "VC6", "input", "L"), ("20", "VC5", "input", "L"),
            ("1", "VC4", "input", "L"), ("2", "VC3", "input", "L"), ("3", "VC2", "input", "L"),
            ("4", "VC1", "input", "L"), ("5", "VC0", "input", "L"),
            ("6", "SRP", "input", "L"), ("7", "SRN", "input", "L"),
            ("15", "REGOUT", "power_out", "R"), ("12", "SCL", "bidirectional", "R"),
            ("13", "SDA", "bidirectional", "R"), ("14", "ALERT", "open_collector", "R"),
            ("9", "DSG", "output", "R"), ("10", "CHG", "output", "R"), ("8", "TS", "bidirectional", "R"),
            ("11", "VSS", "power_in", "B"), ("21", "PAD", "power_in", "B"),
        ]),
    # SNOSDE5A (LM74502) Table 5-1, 8-pin SOT-23 DDF
    "LM74502DDFR": dict(lcsc="C3236215", 
        ref="U", desc="Reverse-polarity / high-side switch controller, 3.2-65 V, 60 uA gate source (LM74502)",
        datasheet=DS + "lm74502.pdf", fp="Package_TO_SOT_SMD:Texas_DDF0008A_SOT-8_1.6x2.9mm_P0.65mm",
        pins=[
            ("5", "VS", "power_in", "L"), ("1", "EN/UVLO", "input", "L"), ("7", "OV", "input", "L"),
            ("3", "NC", "no_connect", "L"),
            ("6", "GATE", "output", "R"), ("8", "SRC", "input", "R"), ("4", "VCAP", "passive", "R"),
            ("2", "GND", "power_in", "B"),
        ]),
    # SLVS832D (TPS22945) Pin Functions, SC-70-5 DCK
    "TPS22945DCKR": dict(lcsc="C47507", 
        ref="U", desc="Current-limited load switch, 100-200 mA, auto-restart, open-drain OC flag (TPS22945)",
        datasheet=DS + "tps22945.pdf", fp="Package_TO_SOT_SMD:SOT-353_SC-70-5",
        pins=[
            ("5", "VIN", "power_in", "L"), ("4", "ON", "input", "L"),
            ("1", "VOUT", "power_out", "R"), ("3", "OC", "open_collector", "R"),
            ("2", "GND", "power_in", "B"),
        ]),
}

# ---------------------------------------------------------------- copies of stock symbols
# (stock lib, stock symbol, pin renames {number: new name}) — the stock pin numbers/types are kept
# and every one is checked against the datasheet and the netlist like the new ones.
STOCK = {
    "STM32G474RET6": dict(lcsc="C521608", src=("MCU_ST_STM32G4", "STM32G474RETx"), ref="U",
        desc="STM32G474RET6 Arm Cortex-M4F 170 MHz, 512 KB flash, LQFP-64",
        datasheet="https://www.st.com/resource/en/datasheet/stm32g474re.pdf",
        fp="Package_QFP:LQFP-64_10x10mm_P0.5mm"),
    "INA239AIDGSR": dict(lcsc="C2876522", src=("Sensor_Energy", "INA229"), ref="U",
        desc="85 V, 16-bit SPI current/voltage/power monitor (INA239; pin-compatible with INA229)",
        datasheet=DS + "ina239.pdf", fp="Package_SO:MSOP-10_3x3mm_P0.5mm"),
    # SN74LVC08A PW pinout: 1A 1, 1B 2, 1Y 3, 2A 4, 2B 5, 2Y 6, GND 7, 3Y 8, 3A 9, 3B 10, 4Y 11,
    # 4A 12, 4B 13, VCC 14
    "SN74LVC08APWR": dict(lcsc="C465737", src=("74xx", "74LS08"), ref="U",
        rename={"1": "1A", "2": "1B", "3": "1Y", "4": "2A", "5": "2B", "6": "2Y", "8": "3Y", "9": "3A",
                "10": "3B", "11": "4Y", "12": "4A", "13": "4B"},
        desc="Quad 2-input AND gate, 1.65-3.6 V, TSSOP-14 (SN74LVC08A)",
        datasheet=DS + "sn74lvc08a.pdf", fp="Package_SO:TSSOP-14_4.4x5mm_P0.65mm"),
    # Diodes 74LVC1G17 SOT353 (SE) pinout: 1 NC, 2 A, 3 GND, 4 Y, 5 VCC
    "74LVC1G17SE-7": dict(lcsc="C212314", src=("74xGxx", "74LVC1G17"), ref="U", rename={"2": "A", "4": "Y"},
        desc="Single Schmitt-trigger buffer, SOT-353 (Diodes 74LVC1G17SE)",
        datasheet="https://www.diodes.com/assets/Datasheets/74LVC1G17.pdf",
        fp="Package_TO_SOT_SMD:SOT-353_SC-70-5"),
    # SN74LVC3G17 (SCES470F) DCU pinout: 1A 1, 3Y 2, 2A 3, GND 4, 2Y 5, 3A 6, 1Y 7, VCC 8
    "SN74LVC3G17DCUR": dict(lcsc="C68245", src=("74xGxx", "74LVC3G17"), ref="U",
        rename={"1": "1A", "2": "3Y", "3": "2A", "5": "2Y", "6": "3A", "7": "1Y"},
        desc="Triple Schmitt-trigger buffer, VSSOP-8 DCU (SN74LVC3G17)",
        datasheet=DS + "sn74lvc3g17.pdf", fp="Package_SO:VSSOP-8_2.3x2mm_P0.5mm"),
    "AP2112K-3.3TRG1": dict(lcsc="C51118", src=("Regulator_Linear", "AP2112K-3.3"), ref="U",
        desc="600 mA 3.3 V LDO, SOT-23-5 (Diodes AP2112K-3.3)",
        datasheet="https://www.diodes.com/assets/Datasheets/AP2112.pdf", fp="Package_TO_SOT_SMD:SOT-23-5"),
    "HYG015N04LS1C2": dict(lcsc="C2874970", src=("Transistor_FET", "Q_NMOS_SSSGD_AvalancheRated"), ref="Q",
        desc="N-MOSFET 40 V, 1.4 mOhm typ @ 10 V, PDFN 5x6 (HUAYI HYG015N04LS1C2)",
        datasheet="", fp="Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic"),
    "BAV99": dict(lcsc="C2500", src=("Diode", "BAV99"), ref="D", rename={"1": "A1", "2": "K2", "3": "K1A2"},
        desc="Dual switching diode in series, 100 V 215 mA, SOT-23 (Nexperia BAV99)",
        datasheet="https://assets.nexperia.com/documents/data-sheet/BAV99_SER.pdf", fp="Package_TO_SOT_SMD:SOT-23"),
    "BAT54S": dict(lcsc="C47546", src=("Diode", "BAT54S"), ref="D", rename={"1": "A1", "2": "K2", "3": "K1A2"},
        desc="Dual Schottky diode in series, 30 V 200 mA, SOT-23 (Nexperia BAT54S)",
        datasheet="https://assets.nexperia.com/documents/data-sheet/BAT54S.pdf", fp="Package_TO_SOT_SMD:SOT-23"),
    "SMBJ20A": dict(lcsc="C151922", src=("Device", "D_Zener"), ref="D",
        desc="Unidirectional TVS 20 V standoff, 600 W, SMB (BORN SMBJ20A)", datasheet="", fp="Diode_SMD:D_SMB"),
    "SS34": dict(lcsc="C8678", src=("Diode", "SS34"), ref="D", desc="Schottky 40 V 3 A, SMA", datasheet="", fp="Diode_SMD:D_SMA"),
    "1N4148W": dict(lcsc="C81598", src=("Diode", "1N4148W"), ref="D", desc="Switching diode 75 V 150 mA, SOD-123",
        datasheet="", fp="Diode_SMD:D_SOD-123"),
    "MMSZ5242B": dict(lcsc="C21567", src=("Device", "D_Zener"), ref="D", desc="Zener 12 V 350 mW, SOD-123 (JSCJ MMSZ5242B)",
        datasheet="", fp="Diode_SMD:D_SOD-123"),
    "B5819W": dict(lcsc="C8598", src=("Device", "D_Schottky"), ref="D", desc="Schottky 40 V 1 A, SOD-123",
        datasheet="", fp="Diode_SMD:D_SOD-123"),
    "KT-0603R": dict(lcsc="C2286", src=("Device", "LED"), ref="D", desc="LED red 0603 (KENTO KT-0603R)",
        datasheet="", fp="LED_SMD:LED_0603_1608Metric"),
    "FNR5040S220MT": dict(lcsc="C167971", src=("Device", "L"), ref="L", desc="22 uH 1.6 A shielded inductor 5x5x4 (Changjiang FNR5040S220MT)",
        datasheet="", fp="Inductor_SMD:L_Changjiang_FNR5040S"),
    "EEHZK1V331P": dict(lcsc="C278516", src=("Device", "C_Polarized"), ref="C", rename={"1": "+", "2": "-"}, desc="330 uF 35 V hybrid polymer 10x10.2 (Panasonic EEH-ZK1V331P)",
        datasheet="", fp="Capacitor_SMD:CP_Elec_10x10.5"),
    "HoLR2512-3W-2mR": dict(lcsc="C2844506", src=("Device", "R"), ref="R", desc="2 mOhm 1% 3 W 2512 alloy shunt (Milliohm HoLR2512)",
        datasheet="", fp="motor_board:R_2512_HoLR_1-4mR"),
    "RE2512F3R001": dict(lcsc="C46961745", src=("Device", "R"), ref="R", desc="1 mOhm 1% 3 W 2512 shunt (JIERR RE2512F3R001)",
        datasheet="", fp="motor_board:R_2512_JIERR_RE_small_electrode"),
    "25121WF100LT4E": dict(lcsc="C25466", src=("Device", "R"), ref="R", desc="0.1 Ohm 1% 1 W 2512 (UNI-ROYAL 25121WF100LT4E)",
        datasheet="", fp="Resistor_SMD:R_2512_6332Metric"),
    "BOOMELE_1.27-2x10P": dict(lcsc="C59981", src=("Connector_Generic", "Conn_02x10_Odd_Even"), ref="J",
        desc="2x10 1.27 mm SMD male header, 5.5 mm lead span (BOOMELE 1.27-2*10P)",
        datasheet="", fp="motor_board:BOOMELE_1.27-2x10P_SMD"),
    "WAFER-SH1.0-6PWB": dict(lcsc="C3029345", src=("Connector_Generic_MountingPin", "Conn_01x06_MountingPin"), ref="J",
        desc="SH 1.0 mm 6-pin SMD right-angle (XUNPU WAFER-SH1.0-6PWB, JST SM06B-SRSS-TB compatible)",
        datasheet="", fp="motor_board:SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB"),
    "S5B-XH-A": dict(lcsc="C263757", src=("Connector_Generic", "Conn_01x05"), ref="J",
        desc="JST XH 5-pin side-entry THT (balance lead)", datasheet="",
        fp="Connector_JST:JST_XH_S5B-XH-A_1x05_P2.50mm_Horizontal"),
}

# BOM comment (design/bom.csv "Comment") → library symbol, for check_lib.py
BOM_TO_SYMBOL = {
    "STM32G474RET6": "STM32G474RET6", "DRV8323RHRGZR": "DRV8323RHRGZR", "DRV8316CRRGFR": "DRV8316CRRGFR",
    "INA239AIDGSR": "INA239AIDGSR", "BQ76907RGRR": "BQ76907RGRR", "LM74502DDFR": "LM74502DDFR",
    "TPS22945DCKR": "TPS22945DCKR", "SN74LVC08APWR": "SN74LVC08APWR", "74LVC1G17SE-7": "74LVC1G17SE-7",
    "SN74LVC3G17DCUR": "SN74LVC3G17DCUR", "AP2112K-3.3TRG1": "AP2112K-3.3TRG1",
    "HYG015N04LS1C2": "HYG015N04LS1C2", "BAV99": "BAV99", "BAT54S": "BAT54S", "SMBJ20A": "SMBJ20A",
    "SS34 40V 3A": "SS34", "1N4148W": "1N4148W", "MMSZ5242B 12V": "MMSZ5242B", "B5819W": "B5819W",
    "LED red": "KT-0603R", "FNR5040S220MT 22uH 1.8A": "FNR5040S220MT",
    "330uF 35V hybrid polymer": "EEHZK1V331P", "2mR 1% 2512": "HoLR2512-3W-2mR",
    "1mR 1% 2512": "RE2512F3R001", "0.1R 1W 2512": "25121WF100LT4E",
    "B2B 2x10 1.27mm male": "BOOMELE_1.27-2x10P", "SH1.0 6P SMD R/A": "WAFER-SH1.0-6PWB",
    "JST XH 5-pin (balance)": "S5B-XH-A",
}

# ---------------------------------------------------------------- custom footprints (motor_board.pretty)
# Geometry in mm, KiCad convention (y down), top view.  Every value cites its drawing.
FOOTPRINTS = {
    # TI RGF0040E (SLVSH07 p.92 outline, p.93 example board layout): pins 1-12 left (top→bottom),
    # 13-20 bottom (left→right), 21-32 right (bottom→top), 33-40 top (right→left); pads 0.6 x 0.25;
    # (4.8) and (6.8) are pad-CENTRE spans (the extension lines are the pads' centrelines) → pad
    # centres x = ±2.4, y = ±3.4 (same as JLC's EasyEDA footprint); EP 3.7 x 5.7, paste 12 x 1.05 x 1.15.
    "TI_RGF0040E_VQFN-40-1EP_5x7mm_P0.5mm_EP3.7x5.7mm": dict(kind="qfn_rgf0040e"),
    # Milliohm HoLR2512 1-4 mOhm recommended land (datasheet p.3): A = 4.0 (pad height),
    # L = 1.3 (gap), B = 3.1 (pad length) → pads 3.1 x 4.0 at x = ±2.2.  Body 6.4 x 3.2.
    "R_2512_HoLR_1-4mR": dict(kind="two_pad", pad=(3.1, 4.0), x=2.2, body=(6.4, 3.2),
        descr="Milliohm HoLR2512 1-4 mOhm, recommended land 3.1x4.0 mm, gap 1.3 mm (HoLR2512 datasheet p.3)"),
    # BOOMELE 1.27-2*10P drawing "P.C.B Layout": pads 0.74 x 2.5 (6.5 outer, 1.5 row gap),
    # pitch 1.27, 2 x 10 → pad centres x = ±2.0, y = ±5.715 (KiCad PinHeader_2x10_P1.27mm SMD
    # orientation: odd pins in the x < 0 column, pin 1 at the top).  Body 12.7 x 3.4.
    "BOOMELE_1.27-2x10P_SMD": dict(kind="header_2xN", n=10, pitch=1.27, pad=(2.5, 0.74), x=2.0, body=(3.4, 12.7)),
    # XUNPU WAFER-SH1.0-6PWB drawing "P.C.B LAYOUT" (measured at 300 dpi): signal pads 0.5 x 1.7 at
    # pitch 1.0 (x = -2.5 … 2.5), y = -1.7; tab pads 1.2 x 2.5, inner edge 0.5 outside pad 6's
    # centre → x = ±3.6, y = +1.7 (overall 5.5); identical to JLC's EasyEDA footprint.
    # JIERR RE2512 small-electrode (no "L" suffix; LCSC C46961745 is this version, 1.0 mm terminals)
    # suggested PCB dimensions (datasheet p.5): a = 4.0 (pad height), b = 2.1 (pad length),
    # L = 4.1 (gap) → pads 2.1 x 4.0 at x = ±3.1.  Body 6.35 x 3.2.
    "R_2512_JIERR_RE_small_electrode": dict(kind="two_pad", pad=(2.1, 4.0), x=3.1, body=(6.35, 3.2),
        descr="JIERR RE2512 small-electrode 2512 shunt, suggested land 2.1x4.0 mm, gap 4.1 mm (datasheet p.5)"),
    "SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB": dict(kind="sh_ra", n=6, pitch=1.0, sig=(0.5, 1.7), sig_y=-1.7,
                                               mp=(1.2, 2.5), mp_x=3.6, mp_y=1.7, body=(8.35, 4.3)),
}

# JLC's EasyEDA footprint for each custom footprint (copied to ref/easyeda/ from easyeda2kicad), the pad
# renumbering needed to compare them, and every deliberate deviation (check_lib fails on any other).
EASYEDA_REF = {
    "TI_RGF0040E_VQFN-40-1EP_5x7mm_P0.5mm_EP3.7x5.7mm": "VQFN-40_L7.0-W5.0-P0.50-BL-EP5.7",
    "R_2512_HoLR_1-4mR": "RES-SMD_L6.4-W3.2-A",
    "BOOMELE_1.27-2x10P_SMD": "HDR-SMD_20P-P1.27-V-M-R2-C10-S1.27-LS5.5-1",
    "SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB": "CONN-SMD_6P-P1.00_XUNPU_WAFER-SH1.0-6PWB",
    "R_2512_JIERR_RE_small_electrode": "RES-SMD_L6.3-W3.2_R2512",
}
EASYEDA_PAD_RENAME = {"SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB": {"7": "MP", "8": "MP"}}
EASYEDA_DEVIATIONS = {
    "R_2512_HoLR_1-4mR": "HoLR datasheet land for 1-4 mOhm (3.1 x 4.0, gap 1.3); JLC's is a generic 2512 land",
    "R_2512_JIERR_RE_small_electrode": "JIERR p.5 small-electrode land (2.1 x 4.0, gap 4.1); JLC's pads are 2.0 x 3.46, gap 3.34",
    "BOOMELE_1.27-2x10P_SMD": "BOOMELE drawing land (0.74 x 2.5, 6.5 outer, 1.5 gap); JLC's pads are 0.8 wide, 0.86 gap",
}

# Gate grouping per unit for multi-unit symbols (datasheet pinouts), checked by check_lib.
UNITS = {
    # SN74LVC08A PW: gate 1 = 1A,1B,1Y (1,2,3); gate 2 = 4,5,6; gate 3 = 3A,3B,3Y (9,10,8);
    # gate 4 = 4A,4B,4Y (12,13,11); power GND 7, VCC 14
    "SN74LVC08APWR": [{"1", "2", "3"}, {"4", "5", "6"}, {"8", "9", "10"}, {"11", "12", "13"}, {"7", "14"}],
    # SN74LVC3G17 DCU: 1A/1Y (1,7), 2A/2Y (3,5), 3A/3Y (6,2); power GND 4, VCC 8
    "SN74LVC3G17DCUR": [{"1", "7"}, {"3", "5"}, {"2", "6"}, {"4", "8"}],
}

# JLC's EasyEDA footprints for the stock footprints (pad-arrangement cross-check only: a mirrored,
# re-numbered or wrong-pitch footprint fails; toe/heel length differences within 0.35 mm are normal).
STOCK_EASYEDA_REF = {
    "Package_TO_SOT_SMD:SOT-353_SC-70-5": "SC-70-5_L2.1-W1.3-P0.65-LS2.1-BL",
    "Package_TO_SOT_SMD:Texas_DDF0008A_SOT-8_1.6x2.9mm_P0.65mm": "SOT-23-8_L2.9-W1.6-P0.65-LS2.8-BL",
    "Package_SO:TSSOP-14_4.4x5mm_P0.65mm": "TSSOP-14_L5.0-W4.4-P0.65-LS6.4-BL",
    "Package_DFN_QFN:QFN-20-1EP_3.5x3.5mm_P0.5mm_EP2x2mm": "VQFN-20_L3.5-W3.5-P0.50-TL-EP2.1",
    "Package_DFN_QFN:Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm": "VQFN-48_L7.0-W7.0-P0.50-TL-EP5.1",
    "Package_SO:MSOP-10_3x3mm_P0.5mm": "VSSOP-10_L3.0-W3.0-P0.50-LS4.9-BL",
}

# Deviated custom footprints: the manufacturer-drawing values, transcribed again here (independently
# of FOOTPRINTS above) for check_lib to measure the built footprint against.
DRAWING = {
    # HoLR2512 datasheet p.3, 1-4 mOhm: B = 3.1 (pad length), A = 4.0 (pad height), L = 1.3 (gap)
    "R_2512_HoLR_1-4mR": dict(pad=(3.1, 4.0), gap=1.3),
    # JIERR RE2512 datasheet p.5, small electrode: b = 2.1, a = 4.0, L = 4.1
    "R_2512_JIERR_RE_small_electrode": dict(pad=(2.1, 4.0), gap=4.1),
    # BOOMELE 1.27-2*10P "P.C.B Layout": pad 0.74 wide x 2.5 long, pitch 1.27, 1.5 between rows,
    # 6.5 overall; 2 x 10
    "BOOMELE_1.27-2x10P_SMD": dict(pad=(2.5, 0.74), pitch=1.27, row_gap=1.5, n=10),
}
