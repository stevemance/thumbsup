# Motor board BOM notes (rev L, 2026-09-24)

The machine-readable BOM is [`design/bom.csv`](design/bom.csv) (JLCPCB columns: Comment,
Designator, Footprint, LCSC Part #), generated from `design/motor_board.py`: **194 assembled
parts, 67 lines**, plus 6 DNP footprints (C110–C112, C114–C116, left out of the CSV; mark them
DNP / exclude-from-position in KiCad).  Wire holes (plated through-holes), test pads, net-ties, solder jumpers and
mounting holes are copper only.  Stock figures are from the JLC/LCSC lookups of 2026-09-23/24
([`review/r6_parts_lookup.md`](review/r6_parts_lookup.md), [`review/round2_e_bom.md`](review/round2_e_bom.md),
[`review/round3_b_drive_sensors_bom.md`](review/round3_b_drive_sensors_bom.md)); re-check on order day.

## Parts to watch

| Line | Part | LCSC | Note |
|---|---|---|---|
| U1 | STM32G474RET6 LQFP-64 | C521608 | Extended, **122 at JLC on 2026-10-01: reserve it**.  RBT6/RCT6 (less flash, C1235414 / C529413) are pin-identical.  LCSC is not ST-authorised: check marking/ID/revision at bring-up |
| U2 | DRV8323RHRGZR VQFN-48 7×7 | C543035 | Extended, **~203 in stock: reserve it**; alt listing C2150467.  Must be **R** (buck) **H** (hardware/strap) 48-pin |
| U3, U4 | DRV8316CRRGFR VQFN-40 5×7 | C5447274 | Extended, ~2,900.  **C** variant (datasheet SLVSH07), SPI; the "R" in the MPN is tape & reel.  Custom footprint (RGF0040E) |
| U7 | INA239AIDGSR VSSOP-10 | C2876522 | Extended, **0 in stock at JLC (2026-10-01): owner decision pending**.  INA229AIDGSR (C2846803, pin/footprint compatible; firmware must handle its 24-bit registers) is also at 0; INA239AQDGSRQ1 (C4367136, VSSOP-10, same DGS package) had 7 |
| U8 | BQ76907RGRR VQFN-20 3.5×3.5 | C22458649 | Extended, ~2,400.  CRC-off variant (not BQ7690701) |
| U13 | LM74502DDFR SOT-23-8 (DDF) | C3236215 | Extended, ~8,300.  Must be the plain LM74502 (60 µA gate drive), **not LM74502H** (11 mA: no soft-start).  KiCad `Texas_DDF0008A_SOT-8_1.6x2.9mm_P0.65mm` |
| U6 | SN74LVC08ABQAR WQFN-14 (BQA) 2.5×3 | C31971766 | Extended, ~3,000 (thin: reserve).  Same die and pin numbers as the TSSOP (SCAS283); thermal pad 15 to GND.  KiCad `DHWQFN-14-1EP_2.5x3mm_P0.5mm_EP1x1.5mm` (= TI BQA0014A land and JLC's footprint).  Its ARM inputs come from the U14 Schmitt buffer.  v2 swap (was SN74LVC08APWR C465737) |
| U14 | Diodes 74LVC1G17SE-7 SOT-353 | C212314 | Extended, ~5,400.  Schmitt buffer on W_ARM (1 NC, 2 A, 3 GND, 4 Y, 5 VCC) |
| U9, U10 | SN74LVC3G17DCUR VSSOP-8 | C68245 | Extended, 3,335.  DCT package C18213 (7,218) has the same pinout on `SSOP-8_2.95x2.8mm_P0.65mm` |
| U11, U12 | TPS22945DCKR SC-70-5 | C47507 | Extended, 10k.  100–200 mA limit, auto-restart (TPS22944 has no auto-restart and little stock) |
| Q1–Q8 | HUAYI HYG015N04LS1C2 PDFN 5×6 | C2874970 | 40 V 1.4 typ / 1.7 max mΩ @ 10 V.  Q1–Q6 weapon bridge; Q7/Q8 power switch (Q7 takes the 54–57 mJ soft-start pulse).  Generic PQFN-8-EP 6×5, leads 1–3 S, 4 G, tab D |
| C1 | Panasonic EEHZK1V331P 330 µF 35 V hybrid polymer 10×10.2 | C278516 | ~6,500.  ESR 20 mΩ, 2.8 A rms ripple.  Stake with adhesive (the vibration-proof EEHZK1V331V has only ~26 at JLC) |
| L1 | ZE ZEMS404030-220M 22 µH 4.1×4.1×3.0 molded | C49009291 | Extended, ~2,300.  Isat 3.1 A min / 3.5 typ (−30 % L), DCR 0.22 Ω max.  KiCad `L_Changjiang_FTC404030S` (= ZE land: 1.4 × 4.1 pads, 1.3 gap).  JLC has no footprint data for it: expect a query; alternate MetalLions MTQH404030S220MBT C51883186 (same land, in JLC's library).  v2 swap (was FNR5040S220MT C167971) |
| D2 | Nexperia PMEG4030ER CFP3 / SOD-123W | C389355 | Extended, ~12k.  40 V 3 A, VF 0.44 V max @ 1 A, Tj 150 °C; pad 1 = cathode.  Alternate MDD DSK34 C41029 (needs MDD's 3.2 mm-pitch land, not `D_SOD-123F`).  v2 swap (was SS34 C8678) |
| D4 | MMSZ5242B 12 V SOD-123 | C21567 | Extended.  Q7/Q8 gate-source clamp |
| C14 | Samsung CL10B104KC8NNNC 100 nF 100 V X7R 0603 | C15725 | Extended.  U13 VS: BAT_IN rings to 40–60 V when the switch opens under load (needs ≥ 22 nF).  v2 swap (was 0805 C28233) |
| R302, R402 | 0.1 Ω 1 % 1 W 2512 (UNI-ROYAL 25121WF100LT4E) | C25466 | Extended, 76k.  DRV8316 VM feed filter |
| D5 | B5819W SOD-123 | C8598 | Basic.  VC0 clamp (low VF at mA currents) |
| D10 | 1N4148WS SOD-323 | C2128 | Basic.  Cdvdt steering diode (reversed-pack protection of the soft-start); µA currents, ≤ ~30 V reverse.  v2 swap (was 1N4148W SOD-123 C81598) |
| R15 | UNI-ROYAL 0603WAF6801T5E 6.8 k 1 % 0603 | C23212 | Basic.  Bus bleeder, 41 mW (154 mW briefly at the TVS clamp).  v2 swap (was 0805 C17772) |
| R300, R400 | ROHM ESR03EZPJ220 22 Ω 0603 anti-surge 250 mW | C2074038 | Extended, ~4,700.  DRV8316 buck resistor mode (68–100 mW until firmware sets BUCK_DIS; ~1.1 mJ start-up pulse).  A plain 0603 is not enough.  v2 swap (was 1206 C17958) |
| C25, C26, C31, C302, C308, C402, C408 | Murata GRM32ER71H106KA12L 10 µF 50 V X7R 1210 | C77102 | Extended, ~68k.  C25/C26/C31: weapon bridge local caps, one per half-bridge (v2 swap from 1206 X5R C13585 at the user's OK, 2026-09-29: cuts the VDS-trip-only fault kick at the DRV8316 VM pins from 7.7 to 4.3 V/µs and the bus peak from ~30 to ~22 V).  DRV8316 VM bulk, 2 per drive: ~7.6 µF each at 16.8 V (Murata curve, −24 %) = ~15 µF per drive.  Alternate Samsung CL32A106KBJNNNE C380537.  v2: replaces 4 × 1206 per drive (C309/C310/C409/C410 removed with the user's OK, 2026-09-29), which kept only ~2.3 µF each.  Flex-crack rules apply (DESIGN §6.10) |
| D7, D8 | Nexperia BAV99,215 SOT-23 | C2500 | Basic.  Motor-NTC clamps (nA leakage; 1 = A1, 2 = K2, 3 = common) |
| D9 | Nexperia BAT54S,215 SOT-23 | C47546 | Extended, ~286k.  Dynamic-ARM charge pump (Schottky needed for the ~2.9 V output) |
| RS1–RS3 | Milliohm HoLR2512-3W-2mR-1% | C2844506 | Custom land for 1–4 mΩ parts (2.0 mm terminals) |
| RS4 | JIERR RE2512F3R001 1 mΩ 3 W | C46961745 | Pack shunt, small-electrode version (no "L" suffix).  Custom land per JIERR p.5 (2.1 × 4.0 pads, 4.1 gap): `R_2512_JIERR_RE_small_electrode` |
| J1 | BOOMELE 1.27-2*10P SMD male | C59981 | Custom footprint to the vendor land; **bottom side** (JLC second side or hand-solder).  Compute board: mirrored female socket |
| J2, J3 | JST BM06B-SRSS-TB (genuine) SH 1.0 6-pin **vertical** SMD | C160392 | Extended, ~40k.  KiCad `JST_SH_BM06B-SRSS-TB_1x06-1MP_P1.00mm_Vertical` (= JST layout, pin 1 at x = −2.5).  **JLC's footprint is ours rotated 180°: fix the rotation in the CPL** (FAB.md).  Strain-relieve the cable: the joints take the pull.  v2 swap (was XUNPU R/A clone C3029345) |
| J4 | JST B5B-XH-A(LF)(SN) **vertical** THT (plain -A, no peg) | C157991 | Extended, ~72k.  Through-hole: JLC Standard PCBA or hand-solder.  9.8 mm tall mated (check the lid).  **JLC's footprint is rotated 180° with its origin at the body centre: fix rotation and offset in the CPL** (FAB.md); a reversed J4 puts B− on pin 5.  v2 swap (was side-entry S5B-XH-A C263757) |
| D3 | KENTO KT-0603R | C2286 | Vendor pin numbering is the reverse of KiCad's: check the cathode mark in the JLC preview |
| R45 | 75 k 0402 1 % | C25798 | Preferred; 0 at LCSC but ~57k at JLC (fine for JLC assembly) |

**Classes** (JLC fee per Extended line): the ICs U1–U14 (11 lines), Q1–Q8, C1, D1, D4, D9, L1,
RS1–RS3, RS4, R302/R402, TH1, R4 (390 k, no fee-free option in stock), J1, J2/J3, J4 are Extended.
Preferred (no fee): R20 56 k, R22/R24/R26/R63 68 k, R45 75 k, R46 18 k.  Everything else is Basic.

## Off-board parts (not in the JLC order)

| Item | Qty | Note |
|---|---|---|
| XT30 pigtail (16–18 AWG, ~100 mm) | 1 | Pushed through and soldered in the JBAT1/JBAT2 plated holes, strain-relieved |
| Main power switch | 1 | FingerTech Mini Power Switch (40 A cont, 2.15 g) or Repeat Screw Switch (1.5 g), in the + wire of the pigtail, mounted in the chassis wall |
| Motor leads | 9 | Weapon: 16–18 AWG to JW1–JW3; drive: motor leads to JL1.. / JR1.. |
| Drive motors | 2 | Repeat Mini Mk4.1 (1106, 3500 KV, 28.5:1) — plan of record, currently sold out |
| MT6701 sensor PCBs + magnets | 2 | MT6701 + 100 nF + JST-SH, diametric magnet on the motor end |
| Sensor cables | 2 | JST-SH 6-pin (SHR-06V-S + SSH crimps, or pre-crimped) |
| Nylon M2 standoffs + screws | 4 | Clamp the two-board stack through MH1–MH4 |

## Before ordering

1. Re-check stock and class on jlcpcb.com for every line the day you order; reserve U1, U2 and U7 (all under ~210 in stock).
2. Draw the custom footprints listed in DESIGN §6.12.
3. Run `python3 design/motor_board.py` after any change: it must print `checks: OK` (it also
   fails on any placed part without an LCSC number, and on one LCSC number used with two
   footprints).
