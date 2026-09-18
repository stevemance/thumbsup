"""ThumbsUp v1 connectivity — the single source of truth for the netlist.

Everything electrical is defined here with SKiDL.  ``draw.py``/``layouts.py``
only add geometry; ``build.py`` proves the drawn schematic has the same
connectivity as this file.

Design references (see hardware/REVIEW.md for the reasoning behind each choice):

* AM32 target ``AT32DEV_F421`` (HARDWARE_GROUP_AT_B + AT_045):
  PB4 input (TMR3 CH1), PA10/PB1 A-hi/lo, PA9/PB0 B, PA8/PA7 C,
  comparator INM PA0/PA4/PA5 = phase A/B/C BEMF, INP PA1 = virtual neutral,
  PA3 current ADC, PA6 voltage ADC.  Stock hex defaults:
  TARGET_VOLTAGE_DIVIDER 110 (100k/10k), MILLIVOLT_PER_AMP 20, CURRENT_OFFSET 0
  — the hardware below is scaled to those defaults so the stock hex is correct.
* FD6288Q: VCC 5–20 V, logic inputs limited to VCC+0.3 V (abs max), internal
  200 kΩ input pull-downs, 200 ns internal dead time.
* AP63205: fixed 5 V — FB pin must be tied to VOUT (DS Fig. 21).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

os.environ.setdefault("KICAD10_SYMBOL_DIR", "/usr/share/kicad/symbols")
os.environ.setdefault("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")

import builtins  # noqa: E402

from skidl import ERC, KICAD10, POWER, Net, Part, generate_netlist, lib_search_paths, set_default_tool  # noqa: E402


NC = builtins.NC  # SKiDL injects the no-connect net into builtins

# ---------------------------------------------------------------- footprints
FP = {
    "R0402": "Resistor_SMD:R_0402_1005Metric",
    "R0603": "Resistor_SMD:R_0603_1608Metric",
    "R2512": "Resistor_SMD:R_2512_6332Metric",
    "C0402": "Capacitor_SMD:C_0402_1005Metric",
    "C0603": "Capacitor_SMD:C_0603_1608Metric",
    "C0805": "Capacitor_SMD:C_0805_2012Metric",
    "C1206": "Capacitor_SMD:C_1206_3216Metric",
    "CP10": "Capacitor_SMD:CP_Elec_10x10.5",
    "SOT23": "Package_TO_SOT_SMD:SOT-23",
    "SOT23-5": "Package_TO_SOT_SMD:SOT-23-5",
    "TSOT23-6": "Package_TO_SOT_SMD:TSOT-23-6",
    "SOT353": "Package_TO_SOT_SMD:SOT-353_SC-70-5",
    "SOD323": "Diode_SMD:D_SOD-323",
    "SOD123": "Diode_SMD:D_SOD-123",
    "SMB": "Diode_SMD:D_SMB",
    "LED0603": "LED_SMD:LED_0603_1608Metric",
    "PDFN56": "Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic",
    "VSSOP10": "Package_SO:MSOP-10_3x3mm_P0.5mm",
    "SOIC8": "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm",
    "LGA14_LSM": "Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y",
    "LGA14_ADXL": "Package_LGA:LGA-14_3x5mm_P0.8mm_LayoutBorder1x6y",
    "L4020": "Inductor_SMD:L_Changjiang_FNR4020S",
    "PICO": "Module:RaspberryPi_Pico_W_SMD_HandSolder",
    "XT30": "Connector_AMASS:AMASS_XT30PW-M_1x02_P2.50mm_Horizontal",
    "H1x02": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
    "H1x03": "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
    "H1x05": "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
    "H2x06": "Connector_PinHeader_2.54mm:PinHeader_2x06_P2.54mm_Vertical",
    "SW": "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A",
    "TP": "TestPoint:TestPoint_Pad_D1.5mm",
    "NT": "thumbsup:NetTie-2_Kelvin_0.4mm",
    "SHUNT": "thumbsup:R_2512_Shunt_Kelvin",
    "MOTOR": "thumbsup:MotorHoles_1x03_P5.90mm",
    "SWD": "thumbsup:SWD_1x05_P1.27mm_Pads",
    "HOLE": "MountingHole:MountingHole_2.7mm_M2.5",
    "FID": "Fiducial:Fiducial_1mm_Mask2mm",
}

# LCSC numbers verified on lcsc.com / jlcpcb.com on 2026-09-03 (see PARTS.md).
LCSC = {
    "R10": "C25077", "R330": "C25104", "R1k": "C11702", "R2k": "C4109", "R3k3": "C25890",
    "R4k7": "C25900", "R10k": "C25744", "R20k": "C25765", "R22k": "C25768", "R47k": "C25792",
    "R100k": "C25741", "R2k2": "C25879", "R27k": "C25771", "R100": "C25076", "R4k7_0603": "C23162",
    "R2R2_0603": "C22939",
    "C100n": "C1525", "C100n_50V": "C14663", "C10n": "C15195", "C1u": "C52923",
    "C1u_0603": "C15849", "C4u7_0603": "C19666", "C10u_0805": "C15850", "C22u_0805": "C45783",
    "C10u_1206_50V": "C13585",
    "CP470": "C242138",  # Panasonic EEHZK1E471P hybrid polymer 470u 25V, 20 mOhm, SMD 10x10.2
}


@dataclass
class Design:
    parts: list = field(default_factory=list)
    sheet_of: dict = field(default_factory=dict)  # ref -> sheet key
    nets: dict = field(default_factory=dict)  # name -> Net
    notes: dict = field(default_factory=dict)  # ref -> short note (drawn on sheet)

    def add(self, sheet: str, part: Part, note: str | None = None) -> Part:
        self.parts.append(part)
        self.sheet_of[part.ref] = sheet
        if note:
            self.notes[part.ref] = note
        return part

    def by_ref(self, ref: str) -> Part:
        for p in self.parts:
            if p.ref == ref:
                return p
        raise KeyError(ref)


def _part(d: Design, sheet: str, ref: str, lib: str, name: str, value: str, fp: str, lcsc: str = "", note: str | None = None, **fields) -> Part:
    p = Part(lib, name, value=value, footprint=fp, ref=ref, tag=ref)
    if lcsc:
        p.fields["LCSC"] = lcsc
    for k, v in fields.items():
        p.fields[k] = v
    return d.add(sheet, p, note)


def R(d, sheet, ref, value, key=None, fp="R0402", note=None):
    return _part(d, sheet, ref, "Device", "R", value, FP[fp], LCSC.get(key, ""), note)


def C(d, sheet, ref, value, key=None, fp="C0402", note=None):
    return _part(d, sheet, ref, "Device", "C", value, FP[fp], LCSC.get(key, ""), note)


def nc_rest(part: Part) -> None:
    for pin in part.pins:
        if not pin.is_connected():
            pin += NC


# ---------------------------------------------------------------- the circuit
def build(out_dir) -> Design:
    set_default_tool(KICAD10)
    if str(out_dir) not in lib_search_paths[KICAD10]:
        lib_search_paths[KICAD10].insert(0, str(out_dir))
    d = Design()

    def net(name: str, power: bool = False) -> Net:
        n = Net(name)
        if power:
            n.drive = POWER
        d.nets[name] = n
        return n

    gnd = net("GND", True)
    vbat_pack = net("VBAT_PACK", True)   # XT30 + side, before the pack shunt
    vbat = net("VBAT", True)             # after pack shunt: motor bridges + logic RPP
    vdrv = net("+VDRV", True)            # after reverse-polarity P-FET: buck in, FD6288 VCC
    v5 = net("+5V", True)                # buck output: LDOs, LEDs, expansion
    v5_pico = net("+5V_PICO", True)      # +5V through Schottky -> Pico VSYS (USB back-feed block)
    v3a = net("+3V3_A", True)            # analog/sensor rail
    v3m = net("+3V3_MCU", True)          # 3x AT32 + flash
    w_vcc = net("W_VCC", True)           # weapon FD6288 VCC (switched)

    sda, scl = net("I2C1_SDA"), net("I2C1_SCL")
    dshot = {k: net(f"DSHOT_{k}") for k in "LRW"}
    arm_n, weapon_en = net("ARM_N"), net("WEAPON_EN")
    pack_v, mon_3v3, ntc_adc = net("PACK_V_ADC"), net("3V3_MON"), net("NTC_ADC")
    sk_in = net("SK6812_IN")
    spi_cs, spi_miso, spi_mosi, spi_sck = net("FLASH_CS"), net("SPI0_MISO"), net("SPI0_MOSI"), net("SPI0_SCK")
    lsm_int, adxl_int = net("LSM_INT1"), net("ADXL_INT1")
    run, uart_tx, uart_rx, gp10, gp11 = net("RUN"), net("UART0_TX"), net("UART0_RX"), net("GP10"), net("GP11")
    i_sense = {k: net(f"I_{k}+") for k in "LRW"}   # cell shunt hot side (Kelvin)
    motor = {k: {ph: net(f"MOTOR_{k}_{ph}") for ph in "ABC"} for k in "LRW"}

    # ------------------------------------------------------------ pack input
    S = "pack"
    j1 = _part(d, S, "J1", "Connector", "Conn_01x02_Pin", "XT30PW-M", FP["XT30"], "C431092", "pack; KiCad footprint: pad 2 = +, pad 1 = -")
    tvs = _part(d, S, "D1", "Device", "D_Zener", "SMBJ15A", FP["SMB"], "C699013", "TVS 15 V standoff / 24 V clamp")
    rsh = _part(d, S, "R2", "Device", "R", "1mΩ 3W", FP["SHUNT"], "C46961745", "pack shunt, Kelvin to U4")
    nt_pp = _part(d, S, "NT1", "Device", "NetTie_2", "Kelvin", FP["NT"], note="in the R2 pad gap")
    nt_pm = _part(d, S, "NT2", "Device", "NetTie_2", "Kelvin", FP["NT"], note="in the R2 pad gap")
    holes = [_part(d, S, f"H{i}", "Mechanical", "MountingHole", "M2.5", FP["HOLE"]) for i in range(1, 4)]
    fids = [_part(d, S, f"FID{i}", "Mechanical", "Fiducial", "Fiducial", FP["FID"]) for i in range(1, 4)]
    for h in holes + fids:
        h.fields["JLC"] = "no BOM"
    q1 = _part(d, S, "Q1", "Transistor_FET", "Q_PMOS_GSD", "AP40P05", FP["SOT23"], "C2886385", "logic reverse-polarity: D=pack, S=load")
    dz = _part(d, S, "D2", "Device", "D_Zener", "MMSZ5242B 12V", FP["SOD123"], "C21567", "Vgs clamp")
    rgs = R(d, S, "R1", "100k", "R100k")
    c_in1 = C(d, S, "C1", "10u 50V", "C10u_1206_50V", "C1206")
    c_in2 = C(d, S, "C2", "10u 50V", "C10u_1206_50V", "C1206")
    c_in3 = C(d, S, "C3", "100n 50V", "C100n_50V", "C0603")
    c_drv = C(d, S, "C5", "10u 50V", "C10u_1206_50V", "C1206")

    # J1: '+' is pad 2 on the KiCad AMASS footprint.  The power link J4 sits between the
    # entry filter and the shunt so that pulling it de-energises everything downstream.
    # J1 is the SPARC disconnect (PWR-2): it mates through a slot in the back wall and is the
    # only plug on the pack.  No second link fits the bay.
    # No entry electrolytic: the bay has no room for a fourth can; the three cell cans sit on
    # the same VBAT pour within 30 mm and the entry has 2x 10 uF MLCC + 100 nF next to the TVS.
    vbat_pack += j1[2], tvs["K"], c_in1[1], c_in2[1], c_in3[1], rsh[1], nt_pp[1]
    pack_sp = net("PACK_S+")
    pack_sm = net("PACK_S-")
    pack_sp += nt_pp[2]
    pack_sm += nt_pm[2]
    gnd += j1[1], tvs["A"], c_in1[2], c_in2[2], c_in3[2], rgs[2], c_drv[2]
    vbat += rsh[2], nt_pm[1], q1["D"]
    vdrv += q1["S"], dz["K"], c_drv[1]
    q1_g = net("Q1_G")
    q1_g += q1["G"], dz["A"], rgs[1]

    # ------------------------------------------------------------ rails
    S = "rails"
    buck = _part(d, S, "U1", "Regulator_Switching", "AP63205WU", "AP63205WU-7", FP["TSOT23-6"], "C2071056", "5 V / 2 A buck, FB tied to VOUT (fixed part)")
    c_bin1 = C(d, S, "C10", "10u 50V", "C10u_1206_50V", "C1206")
    c_bin2 = C(d, S, "C11", "10u 50V", "C10u_1206_50V", "C1206")
    c_bin3 = C(d, S, "C12", "100n 50V", "C100n_50V", "C0603")
    r_en_hi = R(d, S, "R10", "100k", "R100k", note="EN UVLO: on 5.4 V / off 4.6 V")
    r_en_lo = R(d, S, "R11", "27k", "R27k")
    c_bst = C(d, S, "C13", "100n 50V", "C100n_50V", "C0603")
    l1 = _part(d, S, "L1", "Device", "L", "4.7uH 4.9A", FP["L4020"], "C602031", "FHD4020S-4R7MT")
    c_out1 = C(d, S, "C14", "22u 25V", "C22u_0805", "C0805")
    c_out2 = C(d, S, "C15", "22u 25V", "C22u_0805", "C0805")
    d_vsys = _part(d, S, "D3", "Device", "D_Schottky", "1N5819WS", FP["SOD323"], "C191023", "blocks USB back-feed into +5V")
    ldo_a = _part(d, S, "U2", "Regulator_Linear", "AP2112K-3.3", "AP2112K-3.3TRG1", FP["SOT23-5"], "C51118", "sensor rail")
    c_la_in = C(d, S, "C16", "1u 50V", "C1u_0603", "C0603")
    c_la_out = C(d, S, "C17", "10u 25V", "C10u_0805", "C0805")
    ldo_m = _part(d, S, "U3", "Regulator_Linear", "AP2112K-3.3", "AP2112K-3.3TRG1", FP["SOT23-5"], "C51118", "3x AT32 + flash rail")
    c_lm_in = C(d, S, "C18", "1u 50V", "C1u_0603", "C0603")
    c_lm_out = C(d, S, "C19", "10u 25V", "C10u_0805", "C0805")
    r_pv_hi = R(d, S, "R12", "100k", "R100k", note="12.6 V -> 2.27 V")
    r_pv_lo = R(d, S, "R13", "22k", "R22k")
    c_pv = C(d, S, "C20", "100n", "C100n")
    r_3m_hi = R(d, S, "R14", "10k", "R10k")
    r_3m_lo = R(d, S, "R15", "10k", "R10k")
    c_3m = C(d, S, "C21", "100n", "C100n")
    r_led = R(d, S, "R16", "1k", "R1k", note="~10 mA from +VDRV")
    d_pwr = _part(d, S, "D4", "Device", "LED", "RED PWR", FP["LED0603"], "C2286", "pack-present LED, no firmware")

    vdrv += buck["IN"], c_bin1[1], c_bin2[1], c_bin3[1], r_en_hi[1]
    gnd += buck["GND"], c_bin1[2], c_bin2[2], c_bin3[2], r_en_lo[2], c_out1[2], c_out2[2]
    u1_en = net("U1_EN")
    u1_en += buck["EN"], r_en_hi[2], r_en_lo[1]
    u1_sw = net("U1_SW")
    u1_sw += buck["SW"], l1[1], c_bst[2]
    u1_bst = net("U1_BST")
    u1_bst += buck["BST"], c_bst[1]
    v5 += l1[2], buck["FB"], c_out1[1], c_out2[1], d_vsys["A"], ldo_a["VIN"], ldo_a["EN"], c_la_in[1], ldo_m["VIN"], ldo_m["EN"], c_lm_in[1]
    vdrv += r_led[1]
    v5_pico += d_vsys["K"]
    gnd += ldo_a["GND"], c_la_in[2], c_la_out[2], ldo_m["GND"], c_lm_in[2], c_lm_out[2]
    v3a += ldo_a["VOUT"], c_la_out[1], r_3m_hi[1]
    v3m += ldo_m["VOUT"], c_lm_out[1]
    ldo_a["NC"] += NC
    ldo_m["NC"] += NC
    vbat += r_pv_hi[1]
    pack_v += r_pv_hi[2], r_pv_lo[1], c_pv[1]
    gnd += r_pv_lo[2], c_pv[2], r_3m_lo[2], c_3m[2]
    mon_3v3 += r_3m_hi[2], r_3m_lo[1], c_3m[1]
    for i, (name, n) in enumerate((("+VDRV", vdrv), ("+5V", v5), ("+3V3_A", v3a), ("+3V3_MCU", v3m), ("GND", gnd), ("GND", gnd))):
        tpx = _part(d, S, f"TP{i + 1}", "Connector", "TestPoint", name, FP["TP"])
        n += tpx[1]
    led_k = net("PWR_LED_K")
    led_k += r_led[2], d_pwr["A"]
    gnd += d_pwr["K"]

    # ------------------------------------------------------------ pico + I/O
    S = "pico"
    pico = _part(d, S, "A1", "thumbsup", "PicoW", "Pico W", FP["PICO"], note="castellated, hand-solder")
    r_sda = R(d, S, "R20", "2.2k", "R2k2")
    r_scl = R(d, S, "R21", "2.2k", "R2k2")
    r_arm = R(d, S, "R22", "10k", "R10k", note="ARM_N pull-up from the Pico's own 3V3")
    c_run = C(d, S, "C25", "100n", "C100n")
    r_ds = {k: R(d, S, f"R{24 + i}", "100", "R100", note="DShot series, contention limit") for i, k in enumerate("LRW")}
    c_arm = C(d, S, "C23", "100n", "C100n")
    j_arm = _part(d, S, "J2", "Connector", "Conn_01x02_Pin", "ARM link", FP["H1x02"], note="physical arm plug/switch to GND")
    sw_rst = _part(d, S, "SW1", "Switch", "SW_Push", "RESET", FP["SW"], "C318884")
    j_exp = _part(d, S, "J3", "Connector_Generic", "Conn_02x06_Odd_Even", "EXPANSION", FP["H2x06"], note="autonomy card")
    th = _part(d, S, "TH1", "Device", "Thermistor_NTC", "10k NTC", FP["R0603"], "C13564", "place at weapon FETs, B=3380")
    r_ntc = R(d, S, "R23", "3.3k", "R3k3", note="centres the divider at ~57 C: 14 mV/K at 100 C")
    c_ntc = C(d, S, "C24", "100n", "C100n")

    v5_pico += pico["VSYS"]
    v3_pico = net("+3V3_PICO", True)
    v3_pico += pico["3V3"], r_arm[1]
    for n in (3, 8, 13, 18, 23, 28, 38):
        gnd += pico[n]
    gnd += pico["AGND"], c_run[2]
    for k, gp in (("L", "GPIO0"), ("R", "GPIO1"), ("W", "GPIO4")):
        pico_ds = net(f"DSHOT_{k}_PICO")
        pico_ds += pico[gp], r_ds[k][1]
        dshot[k] += r_ds[k][2]
    lsm_int += pico["GPIO2"]
    adxl_int += pico["GPIO3"]
    sda += pico["GPIO6"], r_sda[2]
    scl += pico["GPIO7"], r_scl[2]
    arm_n += pico["GPIO8"], r_arm[2], c_arm[1], j_arm[1]
    weapon_en += pico["GPIO9"]
    gp10 += pico["GPIO10"]
    gp11 += pico["GPIO11"]
    uart_tx += pico["GPIO12"]
    uart_rx += pico["GPIO13"]
    spi_miso += pico["GPIO16"]
    spi_cs += pico["GPIO17"]
    spi_sck += pico["GPIO18"]
    spi_mosi += pico["GPIO19"]
    sk_in += pico["GPIO22"]
    pack_v += pico["GPIO26_ADC0"]
    mon_3v3 += pico["GPIO27_ADC1"]
    ntc_adc += pico["GPIO28_ADC2"], th[2], r_ntc[1], c_ntc[1]
    run += pico["RUN"], sw_rst[1], j_exp[11], c_run[1]
    v3a += r_sda[1], r_scl[1], th[1], j_exp[3]
    gnd += c_arm[2], j_arm[2], sw_rst[2], r_ntc[2], c_ntc[2], j_exp[2], j_exp[4], j_exp[12]
    tp10 = _part(d, S, "TP10", "Connector", "TestPoint", "DSHOT_L", FP["TP"], note="I2C/ARM/DSHOT_R/W are on J3, J2 and the AT32 pads")
    dshot["L"] += tp10[1]
    v5 += j_exp[1]
    sda += j_exp[5]
    scl += j_exp[6]
    uart_tx += j_exp[7]
    uart_rx += j_exp[8]
    gp10 += j_exp[9]
    gp11 += j_exp[10]
    nc_rest(pico)

    # ------------------------------------------------------------ sensors
    S = "sense"

    def ina(ref, n, addr, a1, a0, vin_p, vin_m, note):
        nonlocal sda, scl, v3a, gnd, vbat
        u = _part(d, S, ref, "Sensor_Energy", "INA226", f"INA226 {addr}", FP["VSSOP10"], "C49851", note)
        c = C(d, S, f"C{n}0", "100n", "C100n")
        rp = R(d, S, f"R{n}0", "10", "R10")
        rm = R(d, S, f"R{n}1", "10", "R10")
        cf = C(d, S, f"C{n}1", "100n", "C100n", note="diff filter")
        a1 += u["A1"]
        a0 += u["A0"]
        sda += u["SDA"]
        scl += u["SCL"]
        v3a += u["VS"], c[1]
        gnd += u["GND"], c[2]
        vbat += u["Vbus"]
        vin_p += rp[1]
        vin_m += rm[1]
        fp_ = net(f"{ref}_IN+")
        fm_ = net(f"{ref}_IN-")
        fp_ += rp[2], u["Vin+"], cf[1]
        fm_ += rm[2], u["Vin-"], cf[2]
        u[3] += NC
        return u

    i_sp = {k: net(f"I_{k}_S+") for k in "LRW"}   # Kelvin taps on the cell shunts (net-tied to I_x+ / GND)
    i_sm = {k: net(f"I_{k}_S-") for k in "LRW"}
    ina("U4", 3, "0x40 pack", gnd, gnd, pack_sp, pack_sm, "pack current, high side")
    ina("U5", 4, "0x41 L", gnd, v3a, i_sp["L"], i_sm["L"], "drive L, low side")
    ina("U6", 5, "0x44 R", v3a, gnd, i_sp["R"], i_sm["R"], "drive R, low side")
    ina("U7", 6, "0x45 W", v3a, v3a, i_sp["W"], i_sm["W"], "weapon, low side")

    lsm = _part(d, S, "U8", "Sensor_Motion", "LSM6DS3", "LSM6DS3TR-C", FP["LGA14_LSM"], "C967633", "0x6A: SA0=GND, CS=VDDIO")
    c_l1 = C(d, S, "C70", "100n", "C100n")
    c_l2 = C(d, S, "C71", "100n", "C100n")
    v3a += lsm["VDD"], lsm["VDDIO"], lsm["CS"], c_l1[1], c_l2[1]
    gnd += lsm["SDO/SA0"], lsm["SDX"], lsm["SCX"], lsm[6], lsm[7], c_l1[2], c_l2[2]
    scl += lsm["SCL"]
    sda += lsm["SDA"]
    lsm_int += lsm["INT1"]
    nc_rest(lsm)

    adxl = _part(d, S, "U9", "Sensor_Motion", "ADXL343", "ADXL375BCCZ", FP["LGA14_ADXL"], "C579466", "0x53: SDO=GND, CS=VDDIO (pin-compatible symbol)")
    c_a1 = C(d, S, "C72", "1u", "C1u")
    c_a2 = C(d, S, "C73", "100n", "C100n")
    v3a += adxl["Vdd_I/O"], adxl["Vs"], adxl["~{CS}"], c_a1[1], c_a2[1]
    gnd += adxl[2], adxl[4], adxl[5], adxl["SDO/ADDR"], c_a1[2], c_a2[2]
    sda += adxl["SDA/SDI/SDIO"]
    scl += adxl["SCL/SCLK"]
    adxl_int += adxl["INT1"]
    nc_rest(adxl)

    # ------------------------------------------------------------ flash + LEDs
    S = "io"
    flash = _part(d, S, "U10", "Memory_Flash", "W25Q128JVS", "W25Q128JVSIQ", FP["SOIC8"], "C97521", "16 MB match log")
    c_fl = C(d, S, "C80", "100n", "C100n")
    r_cs = R(d, S, "R80", "10k", "R10k", note="CS idle high during Pico boot")
    r_wp = R(d, S, "R81", "10k", "R10k")
    r_hold = R(d, S, "R82", "10k", "R10k")
    spi_cs += flash[1], r_cs[2]
    spi_miso += flash[2]
    spi_mosi += flash[5]
    spi_sck += flash[6]
    fl_wp, fl_hold = net("FLASH_WP"), net("FLASH_HOLD")
    fl_wp += flash[3], r_wp[2]
    fl_hold += flash[7], r_hold[2]
    v3m += flash[8], c_fl[1], r_cs[1], r_wp[1], r_hold[1]
    gnd += flash[4], c_fl[2]

    buf = _part(d, S, "U11", "74xGxx", "74AHCT1G125", "74AHCT1G125GW", FP["SOT353"], "C52953352", "3V3 -> 5 V for SK6812 (VIH = 0.7 VDD)")
    c_buf = C(d, S, "C81", "100n", "C100n")
    r_sk = R(d, S, "R83", "330", "R330")
    led1 = _part(d, S, "D5", "thumbsup", "SK6812MINI-C", "SK6812MINI-C", "LED_SMD:LED_SK6812MINI_PLCC4_3.5x3.5mm_P1.75mm", "C7423117", "status")
    led2 = _part(d, S, "D6", "thumbsup", "SK6812MINI-C", "SK6812MINI-C", "LED_SMD:LED_SK6812MINI_PLCC4_3.5x3.5mm_P1.75mm", "C7423117", "weapon")
    c_led1 = C(d, S, "C82", "100n", "C100n")
    c_led2 = C(d, S, "C83", "100n", "C100n")
    sk_in += buf[2]
    gnd += buf[1], buf["GND"], c_buf[2], led1["GND"], led2["GND"], c_led1[2], c_led2[2]
    v5 += buf["VCC"], c_buf[1], led1["VDD"], led2["VDD"], c_led1[1], c_led2[1]
    sk_5v = net("SK6812_5V")
    sk_5v += buf[4], r_sk[1]
    sk_d1, sk_d2 = net("SK6812_D1"), net("SK6812_D2")
    sk_d1 += r_sk[2], led1["DIN"]
    sk_d2 += led1["DOUT"], led2["DIN"]
    led2["DOUT"] += NC

    # ------------------------------------------------------------ ESC cells
    for k, base in (("L", 200), ("R", 300), ("W", 400)):
        esc_cell(d, k, base, gnd, vbat, vdrv if k != "W" else w_vcc, v3m, dshot[k], i_sense[k], i_sp[k], i_sm[k], motor[k], net)

    # weapon enable: VCC P-FET switched by (WEAPON_EN AND ARM); MCU held in reset when off
    S = "esc_w"
    qp = _part(d, S, "Q46", "Transistor_FET", "Q_PMOS_GSD", "AP40P05", FP["SOT23"], "C2886385", "weapon VCC switch")
    qn = _part(d, S, "Q47", "Transistor_FET", "AO3400A", "AO3400A", FP["SOT23"], "C20917", "on = WEAPON_EN & ARM")
    qi = _part(d, S, "Q48", "Transistor_FET", "AO3400A", "AO3400A", FP["SOT23"], "C20917", "ARM_N high (disarmed) kills gate")
    qr = _part(d, S, "Q49", "Transistor_FET", "AO3400A", "AO3400A", FP["SOT23"], "C20917", "holds AT32 in reset while VCC off")
    qr2 = _part(d, S, "Q50", "Transistor_FET", "AO3400A", "AO3400A", FP["SOT23"], "C20917", "link removed -> reset, independent of Q46/Q47")
    r_pu = R(d, S, "R440", "4.7k", "R4k7_0603", "R0603", note="stiff: Q49 divider must not lift Q46's gate")
    tp_wen = _part(d, S, "TP40", "Connector", "TestPoint", "WEAPON_EN", FP["TP"], note="bench: 3.3 V here enables the cell")
    r_ens = R(d, S, "R441", "10k", "R10k")
    r_enpd = R(d, S, "R442", "100k", "R100k", note="off if Pico floats")
    r_rh = R(d, S, "R443", "100k", "R100k")
    r_rl = R(d, S, "R444", "47k", "R47k")
    vgate = net("W_VGATE")
    qn_g = net("W_QN_G")
    qr_g = net("W_QR_G")
    nrst_w = d.nets["W_NRST"]
    vdrv += qp["S"], r_pu[1]
    w_vcc += qp["D"]
    vgate += qp["G"], r_pu[2], qn["D"], r_rh[1]
    gnd += qn["S"], qi["S"], qr["S"], qr2["S"], r_enpd[2], r_rl[2]
    qn_g += qn["G"], r_ens[2], r_enpd[1], qi["D"]
    weapon_en += r_ens[1], tp_wen[1]
    arm_n += qi["G"], qr2["G"]
    qr_g += qr["G"], r_rh[2], r_rl[1]
    nrst_w += qr["D"], qr2["D"]

    return d


def esc_cell(d, k, base, gnd, vbat, vcc, v3m, dshot, i_p, i_sp, i_sm, motor, net):
    """One AM32 cell.  Sheet ``esc_<k>`` = MCU/driver/sense, ``esc_<k>_bridge`` = power stage."""
    S = f"esc_{k.lower()}"
    B = f"{S}_bridge"
    mcu = _part(d, S, f"U{base // 10}", "thumbsup", "AT32F421K8U7", "AT32F421K8U7", "Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.3x3.3mm", "C2965611", "AM32 AT32DEV_F421, bootloader F421_PB4")
    drv = _part(d, S, f"U{base // 10 + 1}", "thumbsup", "FD6288Q", "HX6288 / FD6288Q", "Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm", "C54423134", "HX6288 (pin-identical, in stock); FD6288Q C328453 alternate")
    csa = _part(d, S, f"U{base // 10 + 2}", "Amplifier_Current", "INA180A1", "INA180A1", FP["SOT23-5"], "C122228", "20 V/V x 1 mOhm = 20 mV/A (AM32 default)")
    tp = {n: _part(d, S, f"TP{base // 10}{i}", "Connector", "TestPoint", n, FP["TP"]) for i, n in enumerate(("ISENSE", "VSENSE", "TLM"))} if k == "L" else {}

    c_vdd_b = C(d, S, f"C{base}", "4.7u", "C4u7_0603", "C0603")
    c_vdd1 = C(d, S, f"C{base + 1}", "100n", "C100n")
    c_vdd2 = C(d, S, f"C{base + 2}", "100n", "C100n")
    c_vdda1 = C(d, S, f"C{base + 3}", "1u", "C1u")
    c_vdda2 = C(d, S, f"C{base + 4}", "100n", "C100n")
    c_nrst = C(d, S, f"C{base + 5}", "100n", "C100n")
    r_boot0 = R(d, S, f"R{base}", "10k", "R10k", note="BOOT0 low: run from flash")
    j_swd = _part(d, S, f"J{base // 10}", "Connector", "Conn_01x05_Pin", "SWD", FP["SWD"], note="1.27 mm pads: 3V3 SWDIO SWCLK NRST GND")
    r_pd = R(d, S, f"R{base + 1}", "10k DNP", "R10k", note="DNP: AT32 pull-up idles high for AM32 serial; fit only if the Pico never uses 1-wire")
    r_pd.fields["DNP"] = "yes"
    r_vhi = R(d, S, f"R{base + 2}", "100k", "R100k", note="AM32 divider 110 (11:1)")
    r_vlo = R(d, S, f"R{base + 3}", "10k", "R10k")
    c_v = C(d, S, f"C{base + 6}", "100n", "C100n")
    r_irc = R(d, S, f"R{base + 4}", "1k", "R1k")
    c_irc = C(d, S, f"C{base + 7}", "10n", "C10n")
    c_csa = C(d, S, f"C{base + 8}", "100n", "C100n")
    c_vcc1 = C(d, S, f"C{base + 9}", "10u 25V", "C10u_0805", "C0805")
    c_vcc2 = C(d, S, f"C{base + 10}", "100n 50V", "C100n_50V", "C0603")
    bemf_top = [R(d, S, f"R{base + 5 + i}", "10k", "R10k") for i in range(3)]
    bemf_bot = [R(d, S, f"R{base + 8 + i}", "3.3k", "R3k3") for i in range(3)]
    r_vn = [R(d, S, f"R{base + 11 + i}", "10k", "R10k") for i in range(3)]

    v3m += mcu["VDD"], mcu["VDD2"], mcu["VDDA"], c_vdd_b[1], c_vdd1[1], c_vdd2[1], c_vdda1[1], c_vdda2[1], j_swd[1], csa["V+"], c_csa[1]
    gnd += mcu["EP_VSS"], c_vdd_b[2], c_vdd1[2], c_vdd2[2], c_vdda1[2], c_vdda2[2], c_nrst[2], r_boot0[2], j_swd[5], r_pd[2], r_vlo[2], c_v[2], c_irc[2], csa["GND"], c_csa[2], drv["COM"], drv["EP"], c_vcc1[2], c_vcc2[2]
    nrst = net(f"{k}_NRST")
    nrst += mcu["NRST"], c_nrst[1], j_swd[4]
    boot0 = net(f"{k}_BOOT0")
    boot0 += mcu["BOOT0"], r_boot0[1]
    swdio, swclk = net(f"{k}_SWDIO"), net(f"{k}_SWCLK")
    swdio += mcu["PA13_SWDIO"], j_swd[2]
    swclk += mcu["PA14_SWCLK"], j_swd[3]
    dshot += mcu["PB4_DSHOT"], r_pd[1]
    vbat += r_vhi[1]
    vsense = net(f"{k}_VSENSE")
    vsense += r_vhi[2], r_vlo[1], c_v[1], mcu["PA6_V"]
    if tp:
        vsense += tp["VSENSE"][1]
    csa_out = net(f"{k}_CSA_OUT")
    csa_out += csa[1], r_irc[1]
    isense = net(f"{k}_ISENSE")
    isense += r_irc[2], c_irc[1], mcu["PA3_I"]
    if tp:
        isense += tp["ISENSE"][1]
    i_sp += csa["+"]
    i_sm += csa["-"]
    if tp:
        tlm = net(f"{k}_TLM")
        tlm += mcu["PB6_TLM_TX"], tp["TLM"][1]
    else:
        mcu["PB6_TLM_TX"] += NC
    vcc += drv["VCC"], c_vcc1[1], c_vcc2[1]
    for hin, lin, mh, ml in (("HIN1", "LIN1", "PA10_AH", "PB1_AL"), ("HIN2", "LIN2", "PA9_BH", "PB0_BL"), ("HIN3", "LIN3", "PA8_CH", "PA7_CL")):
        n = net(f"{k}_{hin}")
        n += mcu[mh], drv[hin]
        n = net(f"{k}_{lin}")
        n += mcu[ml], drv[lin]
    vn = net(f"{k}_VN")
    vn += mcu["PA1_VN"]
    for i, (ph, mpin) in enumerate((("A", "PA0_BEMFA"), ("B", "PA4_BEMFB"), ("C", "PA5_BEMFC"))):
        tap = net(f"{k}_BEMF_{ph}")
        motor[ph] += bemf_top[i][1]
        tap += bemf_top[i][2], bemf_bot[i][1], r_vn[i][1], mcu[mpin]
        gnd += bemf_bot[i][2]
        vn += r_vn[i][2]
    nc_rest(mcu)
    nc_rest(drv)

    # ---- power stage sheet
    q = {}
    for i, ph in enumerate("ABC"):
        qh = _part(d, B, f"Q{base // 10 + i * 2}", "thumbsup", "HYG015N04LS1C2", "HYG015N04LS1C2", FP["PDFN56"], "C2874970")
        ql = _part(d, B, f"Q{base // 10 + i * 2 + 1}", "thumbsup", "HYG015N04LS1C2", "HYG015N04LS1C2", FP["PDFN56"], "C2874970")
        rgh = R(d, B, f"R{base + 20 + i * 2}", "10", "R10")
        rgl = R(d, B, f"R{base + 21 + i * 2}", "10", "R10")
        rgsh = R(d, B, f"R{base + 26 + i * 2}", "10k", "R10k")
        rgsl = R(d, B, f"R{base + 27 + i * 2}", "10k", "R10k")
        dbt = _part(d, B, f"D{base // 10 + i}", "Device", "D_Schottky", "1N5819WS", FP["SOD323"], "C191023")
        rbt = R(d, B, f"R{base + 32 + i}", "2.2", "R2R2_0603", "R0603", note="bootstrap")
        cbt = C(d, B, f"C{base + 20 + i}", "100n 50V", "C100n_50V", "C0603")
        n = i + 1
        ho = net(f"{k}_HO{n}")
        lo = net(f"{k}_LO{n}")
        vb = net(f"{k}_VB{n}")
        gh, gl = net(f"{k}_G{ph}H"), net(f"{k}_G{ph}L")
        vbat += qh["D"]
        motor[ph] += ql["D"], rgsh[2], cbt[2]
        for n in (1, 2, 3):
            motor[ph] += qh[n]
            i_p += ql[n]
        ho += rgh[1]
        gh += rgh[2], qh["G"], rgsh[1]
        lo += rgl[1]
        gl += rgl[2], ql["G"], rgsl[1]
        i_p += rgsl[2]  # true gate-source, at the FET
        bt = net(f"{k}_BT{n}")
        vcc += rbt[1]
        bt += rbt[2], dbt["A"]
        vb += dbt["K"], cbt[1]
        q[ph] = (qh, ql)
    # driver-side connections to the same nets (on the ctrl sheet)
    drv = d.by_ref(f"U{base // 10 + 1}")
    for n in (1, 2, 3):
        d.nets[f"{k}_HO{n}"] += drv[f"HO{n}"]
        d.nets[f"{k}_LO{n}"] += drv[f"LO{n}"]
        d.nets[f"{k}_VB{n}"] += drv[f"VB{n}"]
        motor["ABC"[n - 1]] += drv[f"VS{n}"]

    c_d1 = C(d, B, f"C{base + 23}", "10u 50V", "C10u_1206_50V", "C1206")
    c_d2 = C(d, B, f"C{base + 24}", "10u 50V", "C10u_1206_50V", "C1206")
    if k == "W":
        bulks = [_part(d, B, f"C{base + 25}", "Device", "C_Polarized", "470u 25V polymer 4A", "Capacitor_SMD:CP_Elec_10x12.5", "C46528073", "KNSCHA 118EC421 14 mOhm / 4 A; alt EEHZK1E471P C242138")]
    else:
        bulks = [_part(d, B, f"C{base + 25}", "Device", "C_Polarized", "470u 25V hybrid", FP["CP10"], LCSC["CP470"], "EEHZK1E471P 20 mOhm, glue")]
    rsh = _part(d, B, f"R{base + 35}", "Device", "R", "1mΩ 3W", FP["SHUNT"], "C46961745", "Kelvin: INA180 + INA226 on the net-ties")
    nt_p = _part(d, B, f"NT{base // 10}", "Device", "NetTie_2", "Kelvin", FP["NT"], note="in the shunt pad gap")
    nt_m = _part(d, B, f"NT{base // 10 + 1}", "Device", "NetTie_2", "Kelvin", FP["NT"], note="in the shunt pad gap")
    j_m = _part(d, B, f"J{base // 10 + 1}", "Connector", "Conn_01x03_Pin", f"MOTOR {k}", FP["MOTOR"], note="3x 2 mm plated holes in the phase pours, 30 A")
    tp_i = _part(d, B, f"TP{base // 10}3", "Connector", "TestPoint", f"I_{k}+", FP["TP"]) if k == "L" else None
    vbat += c_d1[1], c_d2[1]
    gnd += c_d1[2], c_d2[2], rsh[2], nt_m[1]
    for cb in bulks:
        vbat += cb[1]
        gnd += cb[2]
    i_p += rsh[1], nt_p[1]
    if tp_i is not None:
        i_p += tp_i[1]
    i_sp += nt_p[2]
    i_sm += nt_m[2]
    motor["A"] += j_m[1]
    motor["B"] += j_m[2]
    motor["C"] += j_m[3]


def check_and_netlist(d: Design, netlist_path) -> None:
    ERC()
    generate_netlist(file_=str(netlist_path))
