# Round 2 review A: symbols (motor_board.kicad_sym, 28 symbols)

Reviewer: independent adversarial check at commit 779d144. The pin data comes from my own
s-expression parser run on `out/motor_board.kicad_sym`. I did not use check_lib.py or the parts.py
comments. Each symbol was compared with the manufacturer datasheet in `hardware/motor_board/datasheets/`
(pdftotext -layout) and with `design/netlist.csv` and `design/bom.csv`. I re-verified the round 1
review rather than trusting it.

## Result

**0 BLOCKER, 0 MAJOR, 0 MINOR, 6 NOTE.** I found no wrong pin number, pin name, exposed pad,
polarity, MOSFET S/G/D or gate-unit mapping. The round 1 MINOR (MMSZ5242B at 500 mW) is fixed. The
Description now says 350 mW, which matches the JSCJ datasheet (Pd 350 mW) and the LCSC page for C21567.

## Checks performed

| Check | Method | Result |
|---|---|---|
| KiCad loads the library | `kicad-cli sym export svg` (KiCad 10) | All 28 symbols and 41 unit/body-style plots export without errors |
| Symbol pins vs footprint pads | Set of pin numbers compared with the set of pad names in the `Footprint` .kicad_mod (stock library or `out/motor_board.pretty`) | Exact match on all 28. Every Footprint exists |
| BOM consistency | For every BOM line mapped to a library symbol, compared LCSC code and footprint name | All match |
| Netlist | Every (ref, pin) in netlist.csv looked up in the symbol for its BOM line. Checked that every symbol pin is used, that pin names agree, and that no net has two output/power_out drivers | No missing or unused pins. Name differences are cosmetic only: `~{CS}`/`CS`, `~{ALERT}`/`ALERT`, `PB8`/`PB8-BOOT0`, `PG10`/`PG10-NRST`, `MountPin`/`MP`, unnamed R pins. No driver conflicts. The no_connect pins (U2-46, U3/U4-1,24, U5-4, U13-3, U14-1) appear only on the `NC` pseudo-net |
| Datasheet URLs | `curl -L` with a browser UA | All 8 TI, 2 Diodes and 2 Nexperia URLs (including the new `BAT54S.pdf`) return `application/pdf` for the right part. For the ST URL, see N5. The LCSC product-page links use the same code as the LCSC field |
| LCSC ↔ MPN | Fetched lcsc.com pages this round: C167971, C21567, C8598, C2874970, C151922, C2286, C46961745, C68245, C3236215, C212314, C47507, C278516, C8678, C81598, C25466, C2844506 | Every page shows the stated MPN and package. C151922 is listed as unidirectional, SMB, VRWM 20 V |

### Pin tables (datasheet → symbol)

- **DRV8316CRRGFR**: SLVSH07 Table 6-1, DRV8316CR column. Matches pins 1 through 40: NC 1,24 · AGND 2,26 · FB_BK 3 · GND_BK 4 ·
  SW_BK 5 · CPL 6 · CPH 7 · CP 8 · VM 9-11 · PGND 12,15,18 · OUTA 13,14 · OUTB 16,17 · OUTC 19,20 ·
  DRVOFF 21 · nFAULT 22 · nSLEEP 23 · AVDD 25 · INHA/INLA/INHB/INLB/INHC/INLC 27-32 · SDO 33 · SDI 34 ·
  SCLK 35 · nSCS 36 · VREF/ILIM 37 · SOC 38 · SOB 39 · SOA 40. The thermal pad is pin 41 and goes to GND. The
  CT-only pins (GAIN 36, MODE 33, SLEW 34, OCP/SR 35, VSEL_BK 24) are correctly absent.
- **DRV8323RHRGZR**: SLVSDJ3D Table 6-4, DRV8323RH column. All 48 pins match, and the thermal pad is pin 49. This includes the RH-only
  pins MODE 29, IDRIVE 30, VDS 31, GAIN 32, the non-monotonic B phase (GHB 17, SHB 16, GLB 15,
  SPB 14, SNB 13), and SOA 25, SOB 24, SOC 23.
- **BQ76907RGRR**: SLUSE96A Table 5-1. Pins 1-20 match exactly (VC4..VC0 1-5, SRP 6, SRN 7, TS 8, DSG 9, CHG 10, VSS
  11, SCL 12, SDA 13, ALERT 14, REGOUT 15, REGSRC 16, BAT 17, VC7..VC5 18-20). The exposed pad is pin 21.
- **LM74502DDFR**: SNOSDE5A Table 5-1: 1 EN/UVLO, 2 GND, 3 N.C, 4 VCAP, 5 VS, 6 GATE, 7 OV, 8 SRC. Exact match.
- **TPS22945DCKR**: SLVS832D DCK: 1 VOUT, 2 GND, 3 OC (open drain), 4 ON, 5 VIN. Exact match.
- **INA239AIDGSR** (stock INA229): INA239 Table 5-1: 1 CS, 2 MOSI, 3 ALERT (OD), 4 MISO, 5 SCLK, 6 VS,
  7 GND, 8 VBUS, 9 IN−, 10 IN+. Exact match.
- **STM32G474RET6**: DS12288 Figure 7 (LQFP64 pinout). All 64 pins match. VSS 31/47/63 are hidden and stacked
  on the visible VSS 15. VDD is on 16/32/48/64, VSSA 27, VREF+ 28, VDDA 29.
- **SN74LVC08APWR**: SCAS283 Pin Functions, TSSOP column: 1A1 1B2 1Y3 2A4 2B5 2Y6 GND7 3Y8 3A9 3B10
  4Y11 4A12 4B13 VCC14. Units are 1 = (1,2→3), 2 = (4,5→6), 3 = (9,10→8), 4 = (12,13→11), 5 = GND/VCC.
  The normal and De Morgan body styles are identical.
- **SN74LVC3G17DCUR**: SCES470F: 1A1 3Y2 2A3 GND4 2Y5 3A6 1Y7 VCC8. Each unit pairs the correct A with the correct Y
  (1→7, 6→2, 3→5). The power unit is 4/8.
- **74LVC1G17SE-7**: Diodes DS35124 SOT25/SOT353 pin assignment (the ordering table says SE = SOT353): 1 NC, 2 A, 3 GND,
  4 Y, 5 VCC. Exact match.
- **AP2112K-3.3TRG1**: Diodes DS39724 SOT25: 1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT. Exact match.

### Polarity / arrangement (checked in the symbol graphics, not just pin names)

- **BAV99 / BAT54S**: Nexperia Table 2 gives 1 = A1, 2 = K2, 3 = K1/A2. In both symbols, diode 1's triangle
  points from pin 1 (x = −7.62) toward the junction, and its cathode bar is at the pin 3 node. Diode 2 starts
  at the junction and its bar sits next to pin 2 (x = +7.62). Correct.
- **SMBJ20A, SS34, 1N4148W, MMSZ5242B, B5819W, KT-0603R**: the triangle points to the bar at pin 1 (K),
  and pin 2 is A. The D_SMB, D_SMA, D_SOD-123 and LED_0603 footprints use pad 1 = cathode. Correct.
- **HYG015N04LS1C2**: the HUAYI p.1 pin diagram gives 1-3 S, 4 G, 5-8/tab D. The symbol has S on 1 (with 2 and 3 hidden
  and stacked), G on 4 and D on 5. The PQFN-8-EP_6x5mm_P1.27mm_Generic footprint has pads 1-5, where pad 5 is the
  drain leads plus the tab. The channel arrow points inward (N-channel), and the body diode points from source to drain. Correct.
- **EEHZK1V331P**: pin 1 is named "+" and sits at the "+" mark. Pin 2 is "−". CP_Elec_10x10.5 pad 1 is "+". Correct.

## Findings

### NOTE

- **N1**: SN74LVC3G17DCUR unit B is gate 3 (3A 6 → 3Y 2) and unit C is gate 2 (2A 3 → 2Y 5). This is the stock
  unit order. The pins are correct, so the netlist is correct, but place units by pin name and not by unit letter.
  (Carried over from round 1.)
- **N2**: The MPN field is the base part number, not the LCSC order code, in two places: HoLR2512-3W-2mR (LCSC gives
  "HoLR2512-3W-2mR-1%") and B5819W (LCSC gives "B5819W SL"). The LCSC codes are correct, so JLC assembly is
  unaffected.
- **N3**: FNR5040S220MT: the Description says 1.6 A, while the BOM comment says "1.8A". LCSC C167971 lists rated current
  1.6 A and saturation current 1.8 A, so both numbers are correct but they refer to different ratings.
- **N4**: SMBJ20A uses the D_Zener graphic, not a TVS graphic. Pins and polarity are correct. The DRV8316C SDO pin is
  typed `tri_state`, which gives the same ERC result as open-drain on the shared MISO net.
- **N5**: The ST datasheet URL (`st.com/resource/en/datasheet/stm32g474re.pdf`) could not be fetched by script.
  st.com blocks non-browser clients, so this is expected. The URL follows ST's standard pattern for this part.
- **N6**: The ERC setup belongs to the schematic, not the library. Several power_in nets are fed from off-board or through a
  resistor or jumper, for example BAT/REGSRC, VM, and the buck outputs. They need PWR_FLAG in the schematic.

## Not checked here

- Custom footprint geometry and connector pad numbering against vendor drawings (footprint review).
- Physical cathode or pin-1 marks against JLC CPL rotation (assembly check).
