# Motor board BOM notes (rev A, 2026-09-23)

The machine-readable BOM is [`design/bom.csv`](design/bom.csv) (JLCPCB columns: Comment,
Designator, Footprint, LCSC Part #), generated from `design/motor_board.py`.  113 placed parts,
41 lines.  Solder pads, test pads, net-ties and solder jumpers are copper only.

## Parts to watch

| Line | Part | LCSC | Note |
|---|---|---|---|
| U1 | STM32G474RET6 LQFP-64 | C521608 | Extended.  RBT6/RCT6 (less flash) are pin-identical if stock is short |
| U2 | DRV8323RSRGZR VQFN-48 7×7 | C545497 | Extended.  Must be the **R** (buck) **S** (SPI) variant: 48-pin, not the 40-pin DRV8323S |
| U3, U4 | DRV8316RRGFR VQFN-40 5×7 | C5218861 | Extended.  **R** = SPI variant (the T variant has no BUCK_DIS and different pins 24/33–36) |
| Q1–Q7 | HUAYI HYG015N04LS1C2 PDFN 5×6 | C2874970 | 40 V 1.4 mΩ.  Q1–Q6 weapon bridge, Q7 reverse-polarity FET.  Footprint: generic PQFN-8-EP 6×5, leads 1–3 S, 4 G, tab D (as used on the v1 board) |
| U7 | TI INA229AIDGSR VSSOP-10 | C2846803 | 986 in stock 2026-09-23.  Pack V/I/P/energy/charge on SPI |
| RS4 | JIERR RE2512F3R001 1 mΩ 3 W 2512 | C46961745 | Pack shunt |
| D4 | MMSZ5242B 12 V SOD-123 | C21567 | Q7 gate clamp |
| U8 | TI BQ76907RGRR VQFN-20 3.5×3.5 | C22458649 | Cell monitor/balancer (2–7S).  Listed in JLC's library; stock not visible when checked, so confirm before ordering.  The BQ76905 (2–5S) is the same idea but was not found at LCSC.  Footprint: KiCad VQFN-20 3.5×3.5 EP 2×2 — check the EP size against TI's RGR drawing |
| J4 | JST S5B-XH-A(LF)(SN) side-entry THT (balance lead) | C263757 | Vertical alternative B5B-XH-A(LF)(SN) = C157991 (69,790 in stock).  Through-hole: JLC's THT assembly or hand-solder |
| RS1–RS3 | Milliohm HoLR2512-3W-2mR-1% | C2844506 | Low-inductance wide-terminal 2 mΩ parts are better for the SPx transient if available (DESIGN §5) |
| C1 | Panasonic EEHZK1E471P 470 µF 25 V hybrid polymer 10×10.2 | C242138 | **Only ~5 in stock at LCSC when checked.**  Needs low ESR *and* high ripple current (~8 A rms bursts, shared with the MLCCs): a plain electrolytic such as ROQANG RVT1E471M1010 (C72518) is in stock but its ripple rating is far too low.  Alternatives: KNSCHA 118EC421 (C46528073, 14 mΩ / 4 A hybrid, was not in the JLC assembly library when last checked) or pre-order EEHZK1E471P from LCSC to your JLC parts stock.  Re-run `spice/sim_hotplug.py` with the chosen part's ESR |
| D1 | SMBJ20A | C151922 (BORN) | Several makers; any SMBJ20A (standoff 20 V, clamp ≤ 32.4 V) |
| L1 | Shun Xiang Nuo SMNR4020-22UH, 4×4×2 mm | C135264 | 22 µH, 0.35 Ω, 1.05 A: covers the 0.73 A peak at the full 0.6 A load (a hard 5 V short will saturate it; the buck's current limit and thermal shutdown handle that).  Sunlord SWPA4030S220MT is no longer listed at LCSC.  Draw the footprint from `datasheets/SMNR4020-22UH.pdf` |
| J1 | BOOMELE 1.27-2*10P, 1.27 mm 2×10 SMD male, 1.5 mm body / 3 mm pins | C59981 | 6,280 in stock.  The compute board needs the matching 2×10 SMD female; pick it with that board (stack height sets the board spacing) |
| J2, J3 | JST SM06B-SRSS-TB(LF)(SN) | C160405 | Mating cable: JST SHR-06V-S housing + crimped SSH leads, or pre-crimped JST-SH cables |
| U6 | 74LVC1G08SE-7 SOT-353 | C460522 | Pinout 1 A, 2 B, 3 GND, 4 Y, 5 VCC (standard SC-70-5) |
| TH1 | Murata NCP18XH103F03RB 0603 | C13564 | B 3380 K |

Datasheets for every non-generic part are in [`datasheets/`](datasheets/).

All resistors and ceramic capacitors are JLC **Basic** parts (numbers in `motor_board.py`'s
`LCSC` table), chosen so the assembly has as few Extended-part fees as possible: Extended parts
are U1–U8, Q1–Q7, RS1–RS4, C1, D1, D4, L1, J1–J4.

## Off-board parts (not in the JLC order)

| Item | Qty | Note |
|---|---|---|
| XT30 pigtail (16–18 AWG, ~100 mm) | 1 | Soldered to J_BAT+/J_BAT−; keep it short (hot-plug sim assumed ~150 nH) |
| Main power switch | 1 | FingerTech Mini Power Switch (40 A cont, 2.15 g) or Repeat Screw Switch (1.5 g), soldered into the + wire of the pigtail, mounted in the chassis wall |
| Motor leads | 9 | Weapon: 16–18 AWG to J_WA–J_WC; drive: motor leads to J_LA.. / J_RA.. |
| Sensor cables | 2 | JST-SH 6-pin to the Hall/encoder board on each drive motor |
| MT6701 sensor PCBs | 2 | Only if the drive motors have no Halls: MT6701 + 100 nF + JST-SH, magnet on the motor shaft/bell |

## Before ordering

1. Re-check stock and Basic/Extended class on jlcpcb.com for every line the day you order.
2. Confirm footprints for L1, J1 and C1 against the chosen parts' drawings.
3. Run `python3 design/motor_board.py` after any change: it must print `checks: OK`.
