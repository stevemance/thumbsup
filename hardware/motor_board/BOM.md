# Motor board BOM notes (rev L, 2026-09-24)

The machine-readable BOM is [`design/bom.csv`](design/bom.csv) (JLCPCB columns: Comment,
Designator, Footprint, LCSC Part #), generated from `design/motor_board.py`: **199 assembled
parts, 67 lines**, plus 6 DNP footprints (C110–C112, C114–C116, left out of the CSV; mark them
DNP / exclude-from-position in KiCad).  Wire holes (plated through-holes), test pads, net-ties, solder jumpers and
mounting holes are copper only.  Stock figures are from the JLC/LCSC lookups of 2026-09-23/24
([`review/r6_parts_lookup.md`](review/r6_parts_lookup.md), [`review/round2_e_bom.md`](review/round2_e_bom.md),
[`review/round3_b_drive_sensors_bom.md`](review/round3_b_drive_sensors_bom.md)); re-check on order day.

## Parts to watch

| Line | Part | LCSC | Note |
|---|---|---|---|
| U1 | STM32G474RET6 LQFP-64 | C521608 | Extended, **~200 at JLC: reserve it**.  RBT6/RCT6 (less flash, C1235414 / C529413) are pin-identical.  LCSC is not ST-authorised: check marking/ID/revision at bring-up |
| U2 | DRV8323RHRGZR VQFN-48 7×7 | C543035 | Extended, **~203 in stock: reserve it**; alt listing C2150467.  Must be **R** (buck) **H** (hardware/strap) 48-pin |
| U3, U4 | DRV8316CRRGFR VQFN-40 5×7 | C5447274 | Extended, ~2,900.  **C** variant (datasheet SLVSH07), SPI; the "R" in the MPN is tape & reel.  Custom footprint (RGF0040E) |
| U7 | INA239AIDGSR VSSOP-10 | C2876522 | Extended, **~101 in stock**.  INA229AIDGSR (C2846803) is pin/footprint compatible; firmware must handle its 24-bit registers |
| U8 | BQ76907RGRR VQFN-20 3.5×3.5 | C22458649 | Extended, ~2,400.  CRC-off variant (not BQ7690701) |
| U13 | LM74502DDFR SOT-23-8 (DDF) | C3236215 | Extended, ~8,300.  Must be the plain LM74502 (60 µA gate drive), **not LM74502H** (11 mA: no soft-start).  KiCad `Texas_DDF0008A_SOT-8_1.6x2.9mm_P0.65mm` |
| U6 | SN74LVC08APWR TSSOP-14 | C465737 | Extended, 35k.  Nexperia 74LVC08APW C6053 same pinout.  Its ARM inputs come from the U14 Schmitt buffer |
| U14 | Diodes 74LVC1G17SE-7 SOT-353 | C212314 | Extended, ~5,400.  Schmitt buffer on W_ARM (1 NC, 2 A, 3 GND, 4 Y, 5 VCC) |
| U9, U10 | SN74LVC3G17DCUR VSSOP-8 | C68245 | Extended, 3,335.  DCT package C18213 (7,218) has the same pinout on `SSOP-8_2.95x2.8mm_P0.65mm` |
| U11, U12 | TPS22945DCKR SC-70-5 | C47507 | Extended, 10k.  100–200 mA limit, auto-restart (TPS22944 has no auto-restart and little stock) |
| Q1–Q8 | HUAYI HYG015N04LS1C2 PDFN 5×6 | C2874970 | 40 V 1.4 typ / 1.7 max mΩ @ 10 V.  Q1–Q6 weapon bridge; Q7/Q8 power switch (Q7 takes the 54–57 mJ soft-start pulse).  Generic PQFN-8-EP 6×5, leads 1–3 S, 4 G, tab D |
| C1 | Panasonic EEHZK1V331P 330 µF 35 V hybrid polymer 10×10.2 | C278516 | ~6,500.  ESR 20 mΩ, 2.8 A rms ripple.  Stake with adhesive (the vibration-proof EEHZK1V331V has only ~26 at JLC) |
| L1 | Changjiang (cjiang) FNR5040S220MT 22 µH 5×5 | C167971 | 24k.  DCR 0.17 Ω max, Isat 1.6 A guaranteed / 1.8 typ (TI recommends 1.6 A).  FNR5045S220MT (Changjiang, 2.0 A, same land) if more margin is wanted.  KiCad `L_Changjiang_FNR5040S` |
| D2 | SS34 SMA | C8678 | Basic.  40 V 3 A buck catch diode |
| D4 | MMSZ5242B 12 V SOD-123 | C21567 | Extended.  Q7/Q8 gate-source clamp |
| C14 | 100 nF 100 V X7R 0805 | C28233 | Basic.  U13 VS: BAT_IN rings to 40–60 V when the switch opens under load |
| R302, R402 | 0.1 Ω 1 % 1 W 2512 (UNI-ROYAL 25121WF100LT4E) | C25466 | Extended, 76k.  DRV8316 VM feed filter |
| D5 | B5819W SOD-123 | C8598 | Basic.  VC0 clamp (low VF at mA currents) |
| D10 | 1N4148W SOD-123 | C81598 | Basic.  Cdvdt steering diode (reversed-pack protection of the soft-start) |
| D7, D8 | Nexperia BAV99,215 SOT-23 | C2500 | Basic.  Motor-NTC clamps (nA leakage; 1 = A1, 2 = K2, 3 = common) |
| D9 | Nexperia BAT54S,215 SOT-23 | C47546 | Extended, ~286k.  Dynamic-ARM charge pump (Schottky needed for the ~2.9 V output) |
| RS1–RS3 | Milliohm HoLR2512-3W-2mR-1% | C2844506 | Custom land for 1–4 mΩ parts (2.0 mm terminals) |
| RS4 | JIERR RE2512F3R001 1 mΩ 3 W | C46961745 | Pack shunt, small-electrode version (no "L" suffix).  Custom land per JIERR p.5 (2.1 × 4.0 pads, 4.1 gap): `R_2512_JIERR_RE_small_electrode` |
| J1 | BOOMELE 1.27-2*10P SMD male | C59981 | Custom footprint to the vendor land; **bottom side** (JLC second side or hand-solder).  Compute board: mirrored female socket |
| J2, J3 | XUNPU WAFER-SH1.0-6PWB (JST SM06B-SRSS-TB compatible) | C3029345 | 30k.  Alternate LXWCONN SH1.0mm-6P-WT C53055322.  Custom footprint (tab pads 1.2 × 2.5 mm per the XUNPU drawing).  **Confirm the pin-1 end** against a mating SHR-06V-S cable |
| J4 | JST S5B-XH-A side-entry THT | C263757 | Through-hole: JLC Standard PCBA or hand-solder.  Vertical B5B-XH-A = C157991 |
| D3 | KENTO KT-0603R | C2286 | Vendor pin numbering is the reverse of KiCad's: check the cathode mark in the JLC preview |
| R45 | 75 k 0402 1 % | C25798 | Preferred; 0 at LCSC but ~57k at JLC (fine for JLC assembly) |

**Classes** (JLC fee per Extended line): the ICs U1–U14 (11 lines), Q1–Q8, C1, D1, D4, D9, L1,
RS1–RS3, RS4, R302/R402, TH1, R4 (390 k, no fee-free option in stock), J1, J2/J3, J4 are Extended.
Preferred (no fee): R20 56 k, R22/R24/R26/R63 68 k, R45 75 k, R46 18 k.  Everything else is Basic.

## Off-board parts (not in the JLC order)

| Item | Qty | Note |
|---|---|---|
| XT30 pigtail (16–18 AWG, ~100 mm) | 1 | Pushed through and soldered in the JBAT1/J_BAT− plated holes, strain-relieved |
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
