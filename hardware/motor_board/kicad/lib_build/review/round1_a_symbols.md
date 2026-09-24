# Round 1 review A: symbols (motor_board.kicad_sym, 28 symbols)

Reviewer: independent adversarial check against the manufacturer datasheets. I did not rely on the
comments in parts.py or on check_lib.py. All pin data was pulled straight from the generated
`out/motor_board.kicad_sym` with my own parser and compared by hand and by script with the datasheet
tables (pdftotext of the PDFs in `hardware/motor_board/datasheets/`).

## Result

**0 BLOCKER, 0 MAJOR, 1 MINOR, 8 NOTE.** Every pin number, pin name, exposed pad, unit mapping and
diode orientation I checked matches the datasheet. The library is fit for schematic capture.

## What was checked, and how

| Check | Method | Result |
|---|---|---|
| KiCad loads the file | `kicad-cli sym export svg` (KiCad 10.0.6) on all 28 symbols, 45 unit/body-style SVGs | rc=0, no warnings |
| Symbol pins vs footprint pads | For each symbol, the set of pin numbers compared with the set of named pads in its Footprint field (stock `/usr/share/kicad/footprints` or `out/motor_board.pretty`) | Exact match on all 28, and every Footprint `lib:name` exists |
| Symbol pins vs netlist | Every `design/netlist.csv` (ref, pin) looked up in the symbol assigned by `bom.csv` | No missing pins. Every symbol pin appears in the netlist, including in the `NC` pseudo-net. Name differences are cosmetic only (`~{CS}`/`CS`, `PB8`/`PB8-BOOT0`, `PG10`/`PG10-NRST`, `Pin_n`/signal names) |
| ERC typing | Each netlist net classified with the symbol pin types: several outputs on one net, output plus power_out, no_connect pins used on a real net, power_in with no power_out | No driver conflicts and no no_connect pin on a real net. The only flags are power_in nets fed from off-board or through a jumper or resistor (VBAT, BAT_IN, BMS_BAT, L_VM/R_VM, +5V, +3V3A, L_/R_VSRC, GND). They need a PWR_FLAG in the schematic, which is expected and not a library issue |
| Stacked/hidden pins | Positions of hidden pins | STM32 VSS 31/47/63 are stacked on visible VSS 15. HYG S 2/3 are stacked on S 1. The NC pins of AP2112K pin 4 and 74LVC1G17 pin 1 are hidden no_connect. All correct |
| LCSC numbers | lcsc.com product page for all 27 non-generic codes | All 27 match the MPN and package (details below) |
| Datasheet URLs | HTTP fetch | The TI, Diodes and Nexperia BAV99 URLs return the right PDF. For BAT54S and ST, see N6 |

### Per-symbol datasheet verification

- **DRV8316CRRGFR**: SLVSH07 Table 6-1, DRV8316CR column. The symbol's pins 1-40 agree on number and name: NC 1,24; AGND 2,26; FB_BK 3; GND_BK 4; SW_BK 5; CPL 6; CPH 7; CP 8; VM 9-11; PGND 12,15,18; OUTA 13,14; OUTB 16,17; OUTC 19,20; DRVOFF 21; nFAULT 22; nSLEEP 23; AVDD 25; INHA..INLC 27-32; SDO 33; SDI 34; SCLK 35; nSCS 36; VREF/ILIM 37; SOC 38; SOB 39; SOA 40. The thermal pad is 41 and goes to GND, per the table ("Must be connected to analog ground"). This is the CR (SPI) variant, not CT.
- **DRV8323RHRGZR**: SLVSDJ3D Table 6-4, DRV8323RH column. All 48 pins plus PAD 49 match, including GAIN 32, IDRIVE 30, MODE 29, VDS 31, CAL 34, ENABLE 33, nSHDN 48, CB 44, SW 45, VIN 47, NC 46, and FB 1. Both SPx/SNx orderings are correct: B is 14/13, and A and C are 11/12 and 21/22.
- **BQ76907RGRR**: SLUSE96A Table 5-1, pins 1-20 exact. The package drawing (RGR0020A) shows "EXPOSED PAD 21", which is symbol pin 21 (PAD, power_in, on GND).
- **LM74502DDFR**: SNOSDE5A Table 5-1: 1 EN/UVLO, 2 GND, 3 N.C, 4 VCAP, 5 VS, 6 GATE, 7 OV, 8 SRC. Exact.
- **TPS22945DCKR**: SLVS832D Pin Functions (DCK): 1 VOUT, 2 GND, 3 OC (open drain), 4 ON, 5 VIN. Exact.
- **STM32G474RET6** (stock STM32G474RETx): DS12288 Table 12, LQFP64 column. All 64 pins match, including 5 PF0, 6 PF1, 7 PG10(-NRST), 15/31/47/63 VSS, 16/32/48/64 VDD, 27 VSSA, 28 VREF+, 29 VDDA, 60 PB7, 61 PB8(-BOOT0), 62 PB9.
- **INA239AIDGSR** (stock INA229): INA239 Table 5-1: 1 CS, 2 MOSI, 3 ALERT (OD), 4 MISO, 5 SCLK, 6 VS, 7 GND, 8 VBUS, 9 IN-, 10 IN+. Exact.
- **SN74LVC08APWR** (stock 74LS08, 4 gates + power unit, both body styles): SCAS283 Pin Functions, TSSOP column. Unit 1 is 1,2→3. Unit 2 is 4,5→6. Unit 3 is 9,10→8. Unit 4 is 12,13→11. Unit 5 is GND 7 and VCC 14. The renames are correct in both the normal and the De Morgan body styles.
- **SN74LVC3G17DCUR** (stock 74LVC3G17): SCES470F Pin Functions. Unit 1 is 1A 1→1Y 7. Unit 2 is 3A 6→3Y 2. Unit 3 is 2A 3→2Y 5. Unit 4 is GND 4 and VCC 8. Each input-output pair belongs to one gate (see N1 about the unit order).
- **74LVC1G17SE-7**: Diodes DS35124 Pin Assignments for SOT353 (the ordering table confirms that "SE" means SOT353): 1 NC, 2 A, 3 GND, 4 Y, 5 VCC. Exact.
- **AP2112K-3.3TRG1**: Diodes AP2112 Pin Descriptions, SOT25: 1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT. Exact.
- **HYG015N04LS1C2**: HUAYI datasheet p.1 "Pin Description", PDFN5*6-8L: pins 1-3 S, 4 G, 5-8 D (drain on the tab). In the symbol, 1/2/3 are S, 4 is G and 5 is D. The stock `PQFN-8-EP_6x5mm_P1.27mm_Generic` has pads 1-4 plus one custom pad "5" covering the leads and the tab (drain). Symbol and footprint agree with each other and with the part.
- **BAV99**: Nexperia BAV99 Table 2: 1 A1, 2 K2, 3 K1/A2. In the symbol graphics, pin 1 (x=-7.62) is at diode 1's anode. Diode 1's cathode bar is at the junction, where pin 3 is. Diode 2's cathode bar is at x=+3.81, next to pin 2. Correct.
- **BAT54S**: Nexperia BAT54S Table 2: 1 A1, 2 K2, 3 K1;A2. The graphics are arranged the same way as BAV99: pin 1 is the anode, pin 3 is the common node, pin 2 is the cathode. Correct.
- **Two-terminal diodes** (SMBJ20A, SS34, 1N4148W, MMSZ5242B, B5819W, KT-0603R): pin 1 = K sits at the bar end of the triangle and pin 2 = A. The stock D_SMB, D_SMA, D_SOD-123 and LED_0603 footprints follow the KiCad convention of pad 1 = cathode. The LCSC listing for C151922 confirms that SMBJ20A is unidirectional, so a polarized symbol is right.
- **EEHZK1V331P** (C_Polarized): pin 1 is the "+" end and CP_Elec_10x10.5 pad 1 is "+". Correct.
- **Passives and connectors** (R, L, Conn_*): the pin numbers are the footprint pad numbers. The WAFER-SH1.0 symbol's MP pin maps to the two "MP" tab pads. The mapping of connector pin numbers to vendor drawings is a footprint question and is left to the footprint review.

### LCSC numbers (lcsc.com product pages)

C5447274 DRV8316CRRGFR VQFN40 · C543035 DRV8323RHRGZR VQFN-48 · C22458649 BQ76907RGRR VQFN-20 ·
C3236215 LM74502DDFR SOT-23-8 · C47507 TPS22945DCKR SC-70-5 · C521608 STM32G474RET6 LQFP-64 ·
C2876522 INA239AIDGSR VSSOP-10 · C465737 SN74LVC08APWR TSSOP-14 · C212314 74LVC1G17SE-7 SOT-353 ·
C68245 SN74LVC3G17DCUR VSSOP-8 · C51118 AP2112K-3.3TRG1 SOT-25 · C2874970 HYG015N04LS1C2 PDFN5x6 ·
C2500 Nexperia BAV99,215 · C47546 Nexperia BAT54S,215 · C151922 BORN SMBJ20A (uni) · C8678 MDD SS34 SMA ·
C81598 1N4148W SOD-123 · C21567 JSCJ MMSZ5242B · C8598 JSCJ B5819W SL · C2286 KENTO KT-0603R ·
C167971 FNR5040S220MT · C278516 EEHZK1V331P · C2844506 HoLR2512-3W-2mR-1% · C46961745 RE2512F3R001 ·
C25466 25121WF100LT4E · C59981 BOOMELE 1.27-2*10P · C3029345 XUNPU WAFER-SH1.0-6PWB · C263757 JST S5B-XH-A.
All match.

## Findings

### MINOR

- **M1: MMSZ5242B Description says "500 mW", but the fitted part is rated 350 mW.** The datasheet in the repo (`MMSZ5242B.pdf`, Maximum Ratings) gives "Power Dissipation Pd 350 mW", and the LCSC listing for C21567 (JSCJ) also says 350 mW. Only the text is wrong. Pins and footprint are fine. Fix `desc` in parts.py.

### NOTE

- **N1:** In SN74LVC3G17DCUR, unit B is gate 3 (6→2) and unit C is gate 2 (3→5), because that is the stock unit order. The pin names are correct, so the netlist comes out right, but "U9B" will not mean gate 2. Place units by pin name, not by unit letter.
- **N2:** The STM32 pin 7 is named `PG10` and pin 61 `PB8`. The datasheet names are `PG10-NRST` and `PB8-BOOT0`. The numbers are correct. This only matters when reading the schematic.
- **N3:** DRV8316C SDO (pin 33) is typed `tri_state`. SLVSH07 says the pin "requires an external pullup", which points to open drain. ERC behaviour is the same either way, because U3 and U4 share MISO and neither type conflicts.
- **N4:** The symbol for SMBJ20A is `D_Zener`. The pins and polarity are right. It is drawn with a zener graphic rather than a TVS graphic.
- **N5:** The Datasheet field is empty for 15 symbols: HYG015N04LS1C2, SMBJ20A, SS34, 1N4148W, MMSZ5242B, B5819W, KT-0603R, FNR5040S220MT, EEHZK1V331P, HoLR2512-3W-2mR, RE2512F3R001, 25121WF100LT4E and the three connectors. The PDFs are in the repo. This is not an error, but item 5 of the brief asks for these fields.
- **N6:** `https://assets.nexperia.com/documents/data-sheet/BAT54_SER.pdf` returned a bot-challenge HTML page to a scripted fetch, while `BAT54S.pdf` on the same host returned a PDF. I could not confirm that the `_SER` URL still resolves. The local BAT54S datasheet is a single-part document (2022), so consider `.../BAT54S.pdf`. The ST URL could not be fetched by script, which is normal for st.com.
- **N7:** The MPN field differs from the LCSC or manufacturer order code in two places: HoLR2512-3W-2mR vs "HoLR2512-3W-2mR-1%" (C2844506), and B5819W vs "B5819W SL" (C8598). The LCSC codes are correct, so JLC assembly is unaffected.
- **N8:** This is a footprint observation, outside the scope of this symbol review. The BQ76907 RGR0020A drawing gives the exposed pad as 2.05 mm. The stock `QFN-20-1EP_3.5x3.5mm_P0.5mm_EP2x2mm` pad 21 is 2.0 x 2.0. That is within normal land-pattern practice, but I am recording it for the footprint reviewer.

## Not checked here

- Connector pin numbering against the vendor drawings (BOOMELE, XUNPU SH, JST XH) and the geometry of the four custom footprints. That belongs to the footprint review.
- The physical LED cathode mark on the KT-0603R. The symbol and footprint agree with each other (pad 1 = K). Placement rotation belongs to the CPL/assembly check.
