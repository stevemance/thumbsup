# ThumbsUp v1 parts (rev v1.2, 2026-09-04)

Every LCSC number below was read from its lcsc.com / jlcpcb.com product page on
2026-09-03; "Basic" / "Extended" is JLCPCB's class on that page.  The BOM field `LCSC`
on every symbol in `kicad/` carries the same number (source: `tools/sch/circuit.py`).
Design rationale and review history: [REVIEW.md](REVIEW.md); layout constraints:
[LAYOUT.md](LAYOUT.md).

**Before ordering:** confirm JLC stock the same day for the low-stock lines marked ⚠;
FD6288Q (C328453) is out of stock, so the driver is ordered as **HX6288 C54423134**
(pin-identical per its datasheet, EP = COM). Confirm XT30 polarity against a physical
connector (the Amass drawing has no "+" mark; the KiCad footprint puts "+" on pad 2).

Assembly: JLC Standard PCBA, both sides (FETs, shunts, cans, TPs, LEDs on top; ICs and
passives on the bottom). Hand-soldered after SMT: Pico W (castellated), J1 XT30, J2/J3
headers, the nine motor leads. Hybrid polymer cans are SMT. SWD is a 1×5 pad row
(`thumbsup:SWD_1x05_P1.27mm_Pads`) for pogo pins or wires.

## ICs and semiconductors

| Qty | Ref | Part | LCSC | Class | Notes |
|---|---|---|---|---|---|
| 1 | A1 | Raspberry Pi Pico W | — | — | `Module:RaspberryPi_Pico_W_SMD_HandSolder`; custom symbol `thumbsup:PicoW` (grounds typed power-in) |
| 3 | U20 U30 U40 | Artery AT32F421K8U7, QFN-32 5×5 | C2965611 | Ext | AM32 `AT32DEV_F421`; EP = VSS (only ground) |
| 3 | U21 U31 U41 | ZHHXDZ **HX6288**, QFN-24 4×4 (FD6288Q C328453 alternate) | C54423134 | Ext | pin-identical to FD6288Q; EP (pin 25) = COM; 2 085 in stock |
| 3 | U22 U32 U42 | TI INA180A1IDBVR, SOT-23-5 | C122228 | Ext | 20 V/V, ±150 µV; 15 100 in stock |
| 18 | Q20–25 Q30–35 Q40–45 | Huayi HYG015N04LS1C2, PDFN 5×6 | C2874970 | Ext | 40 V, 2.0 mΩ @ 4.5 V; **leads 1–3 = S, 4 = G, tab = D** (custom symbol) |
| 4 | U4–U7 | TI INA226AIDGSR, VSSOP-10 | C49851 | Ext | 0x40 / 0x41 / 0x44 / 0x45 |
| 1 | U1 | Diodes AP63205WU-7, TSOT-23-6 | C2071056 | Ext | 5 V / 2 A buck, FB→VOUT, EN 100k/27k (on 5.4 V / off 4.6 V) |
| 2 | U2 U3 | Diodes AP2112K-3.3TRG1, SOT-23-5 | C51118 | Ext | +3V3_A (sensors) / +3V3_MCU (AT32 ×3, flash) |
| 1 | U10 | Winbond W25Q128JVSIQ, SOIC-8 208 mil | C97521 | **Basic** | 16 MB match log |
| 1 | U8 | ST LSM6DS3TR-C, LGA-14 | C967633 | Ext | 0x6A (SA0 = GND, CS = VDDIO, SDx/SCx = GND) |
| 1 | U9 | ADI ADXL375BCCZ, LGA-14 | C579466 | Ext ⚠ | 0x53; 179 in stock, $22 |
| 1 | U11 | 74AHCT1G125GW, SOT-353 | C52953352 | Ext ⚠ | SK6812 level shift; 470 in stock |
| 2 | Q1 Q46 | AllPower AP40P05 P-MOSFET, SOT-23 | C2886385 | Ext | G=1 S=2 D=3 (DS V1.1), Vgs ±20 V, 65–120 mΩ, 5 A: logic RPP / weapon VCC switch |
| 4 | Q47–Q50 | AOS AO3400A, SOT-23 | C20917 | **Basic** | weapon enable AND, reset hold ×2 |
| 1 | D1 | Yangjie SMBJ15A, SMB | C699013 | Ext | TVS 15 V standoff; **3S only** |
| 1 | D2 | MMSZ5242B 12 V, SOD-123 | C21567 | Ext | RPP gate clamp |
| 10 | D3 D20–22 D30–32 D40–42 | 1N5819WS, SOD-323 | C191023 | **Basic** | VSYS isolation + 9 bootstrap |
| 1 | D4 | KENTO KT-0603R red LED | C2286 | **Basic** | pack-present LED (from +VDRV) |
| 2 | D5 D6 | OPSCO SK6812MINI-C | C7423117 | Ext | custom footprint `thumbsup:LED_SK6812MINI-C` from the DS land pattern |
| 1 | L1 | cjiang FHD4020S-4R7MT 4.7 µH | C602031 | Ext | Isat 4.9 A, 4×4×2 mm (footprint `L_Changjiang_FNR4020S`, check pads) |
| 1 | TH1 | Murata NCP18XH103F03RB 10 k NTC 0603 | C13564 | Ext | B = 3380 K, at the weapon FETs |
| 1 | SW1 | XKB TS-1187A-B-A-B tactile 5.1×5.1 | C318884 | **Basic** | footprint `SW_Push_1P1T_XKB_TS-1187A` |
| 1 | J1 | Amass XT30PW-M30.G.Y | C431092 | Ext | pack input through a back-wall slot; it is also the SPARC disconnect (J4 dropped in v1.2); "+" = pad 2 |
| 4 | R2 R235 R335 R435 | JIERR RE2512F3R001 1 mΩ 3 W 2512 | C46961745 | Ext | footprint `thumbsup:R_2512_Shunt_Kelvin`; Kelvin via NT net-ties |
| 8 | NT1 NT2 NT20 NT21 NT30 NT31 NT40 NT41 | `thumbsup:NetTie-2_Kelvin_0.4mm` | — | — | copper-only pads in the shunt pad gap; no BOM line |
| 2 | C225 C325 | Panasonic **EEHZK1E471P** 470 µF 25 V hybrid polymer, SMD 10×10.2 | C242138 | Ext | 20 mΩ; footprint `CP_Elec_10x10.5` |
| 1 | C425 | KNSCHA 118EC421 470 µF 25 V hybrid polymer, SMD 10×12.5 | C46528073 | Ext | 14 mΩ / 4 A ripple for the weapon; footprint `CP_Elec_10x12.5`; C4 (entry) and C426 dropped in v1.2 — all three cans sit on the one VBAT pour |

## Passives (0402 1 % / 0402 X7R unless noted; all Basic unless marked)

| Qty | Value | LCSC | Where |
|---|---|---|---|
| 32 | 10 Ω | C25077 | INA226 filters ×8, FET gate R ×18, R?4 not used — see 1 k |
| 9 | 2.2 Ω 0603 | C22939 | bootstrap R?32–34 |
| 3 | 100 Ω | C25076 | DShot series R24–R26 |
| 1 | 330 Ω | C25104 | SK6812 series |
| 4 | 1 kΩ | C11702 | power LED (from +VDRV, ~10 mA), ISENSE RC ×3 |
| 2 | 2.2 kΩ | C25879 | I2C pull-ups |
| 10 | 3.3 kΩ | C25890 | BEMF bottom ×9, NTC divider R23 |
| 1 | 4.7 kΩ 0603 | C23162 | R440 weapon VCC gate pull-up (stiff) |
| 52 | 10 kΩ | C25744 | pull-ups/downs, BEMF top, VN star, Rgs, dividers, R201/301/401 **DNP** |
| 1 | 22 kΩ | C25768 | pack divider low |
| 1 | 27 kΩ | C25771 (Ext) | buck EN divider low |
| 1 | 47 kΩ | C25792 | reset-hold divider |
| 9 | 100 kΩ | C25741 | RPP gate, EN divider, pack divider, AT32 V-div ×3, weapon enable ×3 |
| 38 | 100 nF 16 V 0402 | C1525 | logic decoupling, RC filters, RUN (logic rails only) |
| 15 | 100 nF 50 V 0603 X7R | C14663 | +VDRV / bootstrap ×9 / driver VCC |
| 3 | 10 nF 0402 | C15195 | ISENSE RC |
| 4 | 1 µF 25 V 0402 | C52923 | ADXL VS, AT32 VDDA ×3 |
| 2 | 1 µF 50 V 0603 (X5R) | C15849 | LDO inputs C16/C18 |
| 3 | 4.7 µF 16 V 0603 | C19666 | AT32 VDD bulk |
| 5 | 10 µF 25 V 0805 (X5R) | C15850 | LDO outputs ×2, driver VCC ×3 |
| 2 | 22 µF 25 V 0805 | C45783 | buck out |
| 11 | 10 µF 50 V 1206 (X5R, 85 °C) | C13585 | pack entry ×2, +VDRV, buck in ×2, FET drains ×6 (bottom side under the high-FET tabs, via into the VBAT pour); X7R alt C89632 (Ext) |
| 1 | 1×2 header | — | J2 ARM link |
| 1 | 2×6 header | — | J3 expansion |
| 3 | 1×5 header (or pogo pads) | — | SWD |
| 3 | motor lead holes | — | `thumbsup:MotorHoles_1x03_P5.90mm`: 3 × 2.0 mm plated holes between the FET rows |
| 12 | test point 1.5 mm | — | TP1–TP6 rails, TP10 DSHOT_L, TP200–203 L cell (ISENSE, VSENSE, TLM, I_L+), TP40 WEAPON_EN |
| 3 + 3 | M2.5 holes, fiducials | — | H1–H3 (`MountingHole_2.7mm_M2.5`), FID1–FID3 |

## Scaling that the stock AM32 hex expects

* `TARGET_VOLTAGE_DIVIDER 110` → 100 kΩ / 10 kΩ on PA6 (12.6 V → 1.15 V).
* `MILLIVOLT_PER_AMP 20`, `CURRENT_OFFSET 0` → 1 mΩ × INA180A1 (20 V/V) = 20 mV/A on PA3 (bus-side average current; regen reads 0).
* BEMF 10 k / 3.3 k, virtual neutral 3 × 10 k into PA1 (comparator INP).

## Dropped since v1.0

Through-hole electrolytics (C43839 / C503217: wrong footprint class, ~0.6 A ripple), 10 Ω
bootstrap resistors (2 V of drive lost at 48 kHz), 2.54 mm pin headers as motor pads, Omron
B3U footprint for the XKB switch, `Q_NMOS_GSD` for the PDFN FETs, the `C1361247?` INA180
placeholder, R440 100 k (weapon FET never turned off).
