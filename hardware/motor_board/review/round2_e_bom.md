# Round 2 / E: adversarial BOM review (motor board rev B)

Reviewer: adversarial BOM / JLC assembly pass.  Date checked: **2026-09-23**.  No design files were edited.

## Method

- Ran `python3 design/motor_board.py`, which printed `179 refs (158 placed components), 141 nets, 52 BOM lines` / `checks: OK`.  The Qty column of `design/bom.csv` adds up to 158.
- Looked up every one of the 52 C-numbers using the two r6 endpoints, one request at a time, 2 s apart, with retry and backoff:
  - **LCSC** `https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=Cxxxx` gave maker, MPN, package (`encapStandard`), parameters and LCSC stock.  This is the data behind `https://www.lcsc.com/product-detail/Cxxxx.html`.
  - **JLC** `POST https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList/v2` with `{"keyword":"Cxxxx"}` gave `componentLibraryType` (`base` = Basic, `expand` = Extended), `preferredComponentFlag`, `stockCount` and `canPresaleNumber`.  This is the data behind `https://jlcpcb.com/partdetail/Cxxxx`.
  - The raw dump is in `/tmp/r2e/bom.txt`.  The scripts are `/tmp/r2e/look.py` and `/tmp/r2e/srch.py`.
- Took each part's net from `design/netlist.csv`.  Checked capacitor and resistor requirements against the datasheets in `datasheets/` (pdftotext).  **(DS)** marks a datasheet quote.
- Took lifecycle status from the ti.com product pages (`https://www.ti.com/product/<part>`; each page shows its status badge) and from a web search.

Class key: **B** = Basic, **PE** = Preferred Extended (no loading fee), **E** = Extended (loading fee).  "Presale" is JLC `canPresaleNumber`.  Five boards need at most 5 × Qty per line (21 × 5 = 105 for the largest line).

Rail maxima used: VBAT is 16.8 V steady and ≤ 32.4 V at the SMBJ20A clamp (LCSC C151922: "Clamping Voltage = 32.4 V @ Ipp 18.6 A").  +5V is 5.05 V.  +3V3 is 3.3 V.  CELLn–CELL(n−1) is ≤ 4.2 V.

## 1. Line-by-line table (live 2026-09-23)

| # | Refs (net) | C-no | Comment | LCSC/JLC record: maker MPN, package, key params | Pkg vs footprint | V rating vs net max | Dielectric / tol | JLC stock / presale (LCSC) | Class | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | C1 (VBAT) | C278516 | 330 µF 35 V hybrid | PANASONIC EEHZK1V331P, SMD D10×L10.2, 330 µF ±20 %, 35 V, ESR 20 mΩ | CP_Elec_10x10.5 OK | 35 V vs 32.4 V clamp (0.93×); 16.8 V steady | polymer hybrid | 6,558 / 6,515 (6,548) | E | OK |
| 2 | C11 (BMS_REG 3.3 V), C22 (U2_DVDD 3.3 V), C46/C49 (L_VS/R_VS ≤ 5.05 V), C69 (+5V), C70 (+3V3) | C52923 | 1 µF 25 V | Samsung CL05A105KA5NQNC, 0402, 1 µF ±10 % 25 V X5R | 0402 OK | 25 V vs ≤ 5.05 V | X5R ±10 % | 6,723,903 / 5,239,721 | B | OK (bias: §2) |
| 3 | C2 (INA diff), C24/C300/C301/C400/C401 (VBAT), C28 (BUCK_CB–SW) | C14663 | 100 nF 50 V | YAGEO CC0603KRX7R9BB104, 0603, X7R ±10 % 50 V | 0603 OK | 50 V vs 32.4 V | X7R | 49,045,127 / 37,867,126 | B | OK |
| 4 | C20/C304/C404 (CPH–CPL, swings 0…VM) | C1622 | 47 nF 50 V | Samsung CL10B473KB8NNNC, 0603, X7R ±10 % 50 V | 0603 OK | 50 V vs 32.4 V; meets TI "≥ 2× VM" at 16.8 V | X7R | 780,005 / 658,486 | B | OK |
| 5 | C21 (VCP–VM ≈ 11 V), C303/C403 (CP–VM ≈ 5 V), C305/C405 (AVDD 3.3 V) | C15849 | 1 µF 50 V | Samsung CL10A105KB8NNNC, 0603, X5R ±10 % 50 V | 0603 OK | 50 V; TI asks 25 V for CVCP (DS DRV8323 pin table) | X5R | 6,329,220 / 4,204,096 (LCSC 1,750) | B | OK (C305 margin: N1) |
| 6 | C25/C26/C302/C308/C402/C408 (VBAT) | C13585 | 10 µF 50 V | Samsung CL31A106KBHNNNE, 1206, X5R ±10 % 50 V | 1206 OK | 50 V vs 32.4 V | X5R | 2,685,158 / 2,095,677 | B | OK |
| 7 | C29/C30 (+5V) | C45783 | 22 µF 25 V | Samsung CL21A226MAQNNNE, 0805, X5R ±20 % 25 V | 0805 OK | 25 V vs 5.05 V | X5R | 4,300,822 / 3,689,008 | B | OK |
| 8 | 21 × 100 nF (+3V3, +3V3A, NRST, BUCK_EN ≤ 3.75 V, VBAT_SNS ≤ 4.15 V, NTC/MTEMP, L/R_VSRC ≤ 5.05 V, AVDD) | C1525 | 100 nF 16 V | Samsung CL05B104KO5NNNC, 0402, X7R ±10 % 16 V | 0402 OK | 16 V vs ≤ 5.05 V | X7R | 25,338,097 / 20,171,064 | B | OK |
| 9 | C307/C407 (FB_BK, 3.3 V default) | C59461 | 22 µF 6.3 V | Samsung CL10A226MQ8NRNC, 0603, X5R ±20 % **6.3 V** | 0603 OK | 6.3 V vs 3.5 V max VBK; **DRV8316C DS asks ≥ 10 V** | X5R | 8,420,342 / 7,896,142 | B | **m1** |
| 10 | C4–C7 (cell diff ≤ 4.2 V), C8 (CELL0–GND ≈ 0 V) | C64705 | 220 nF 50 V | Samsung CL10B224KB8NNNC, 0603, X7R ±10 % 50 V | 0603 OK | 50 V vs ≤ 4.2 V (≤ 16.8 V if a tap floats) | X7R | 329,038 / 300,997 | E | OK electrically; **m3** (fee) |
| 11 | C41–C43 (W_Vx divider ≤ 4.2 V) | C1523 | 1 nF 50 V | FH 0402B102K500NT, 0402, X7R ±10 % 50 V | 0402 OK | OK | X7R | 3,818,324 / 3,343,120 | B | OK |
| 12 | C64 (+3V3), C66 (+3V3A / VREF+) | C19666 | 4.7 µF 16 V | Samsung CL10A475KO8NNNC, 0603, X5R ±10 % 16 V | 0603 OK | 16 V vs 3.3 V | X5R | 2,787,397 / 2,315,174 | B | OK |
| 13 | C80–C82, C90–C92 (SOx filter) | C1555 | 22 pF C0G | FH 0402CG220J500NT, 0402, C0G ±5 % 50 V | 0402 OK | OK | C0G | 1,742,063 / 1,520,613 | B | OK |
| 14 | C9 (BMS_BAT 16.8 V), C27 (VBAT buck VIN) | C377773 | 2.2 µF 50 V | Samsung CL21A225KBQNNNE, 0805, X5R ±10 % 50 V | 0805 OK | 50 V vs 32.4 V | X5R (not Y5V: the r5 B5 fix holds) | 705,612 / 577,734 | B | C9 **m2** |
| 15 | D1 (VBAT–GND) | C151922 | SMBJ20A | BORN SMBJ20A, SMB, uni, VRWM 20 V, VBR 24.5 V (field), Vc 32.4 V @ 18.6 A, 600 W | D_SMB OK | VRWM 20 V > 16.8 V | n/a | 81,315 / 81,235 | E | OK |
| 16 | D2 (BUCK_SW) | C8678 | SS34 | MDD SS34, SMA, 40 V 3 A, VF 0.55 V @ 3 A, IR 500 µA @ 40 V | D_SMA OK | 40 V vs 32.4 V (81 %) | n/a | 4,617,414 / 4,463,723 | B | OK |
| 17 | D3 | C2286 | LED red | KENTO KT-0603R, 0603, VF 1.8–2.4 V, 20 mA | OK | n/a | n/a | 4,086,596 / 3,651,724 | B | OK (≈ 3 mA) |
| 18 | D4 (RPP_G) | C21567 | MMSZ5242B | JSCJ MMSZ5242B, SOD-123, 11.4–12.6 V, 350 mW | OK | n/a | n/a | 3,849 / 3,718 | E | OK |
| 19 | D5 (CELL0 clamp) | C124205 | BAT54WS | DIODES BAT54WS-7-F, SOD-323, 30 V, 100 mA, IR 2 µA @ 25 V | OK | 30 V vs ≈ 0 V | n/a | 76,868 / 76,306 | E | OK |
| 20 | J1 | C59981 | 2×10 1.27 SMD | BOOMELE 1.27-2\*10P, SMD vertical, 2×10P, 3 A | custom fp | n/a | n/a | 7,393 / 6,842 | E | OK |
| 21 | J2, J3 | C3029345 | SH1.0 6P R/A | XUNPU WAFER-SH1.0-6PWB, SMD right angle, 50 V 1 A, aux solder pins | JST fp (tabs 0.2 mm off, see r6 A11) | 50 V vs 5 V | n/a | 30,558 / 29,538 | E | OK (pin-1 still UNVERIFIED, known) |
| 22 | J4 | C263757 | JST XH 5P | JST S5B-XH-A(LF)(SN), THT right angle | OK | 250 V | n/a | 21,888 / 21,723 | E | OK (THT) |
| 23 | L1 | C167971 | 22 µH 1.8 A | cjiang FNR5040S220MT, 5×5, 22 µH ±20 %, "Current Rating 1.6 A", Isat 1.8 A, DCR 168 mΩ (max) | L_Changjiang_FNR5040S OK | n/a | n/a | 24,474 / 24,032 | E | OK |
| 24 | Q1–Q7 | C2874970 | HYG015N04LS1C2 | HUAYI, PDFN5x6-8L, 40 V, Vgs ±20 V, RDS 2.4 mΩ @ 4.5 V (field), Qg 59 nC | PQFN-8-EP 6×5 OK | 40 V vs 32.4 V (81 %) | n/a | 17,261 / 17,134 | E | OK |
| 25 | R1, R40, R41, R47–R49 | C25741 | 100k | UNI-ROYAL 0402WGF1003TCE, 1 %, 62.5 mW, 50 V | OK | R1 sees ≤ 20.4 V | ±1 % | 9,087,563 / 7,920,554 | B | OK |
| 26 | R2, R3 | C25077 | 10R | UNI-ROYAL 0402WGF100JTCE, 62.5 mW (listing ±1 %, MPN "J") | OK | n/a | n/a | 2,042,809 / 1,607,059 | B | OK |
| 27 | R20 | C25796 | 56k 1 % | UNI-ROYAL 0402WGF5602TCE, 1 % | OK | n/a | ±1 % | 240,927 / 199,929 | PE | OK |
| 28 | 13 × 10k 1 % | C25744 | 10k 1 % | UNI-ROYAL 0402WGF1002TCE, 1 % | OK | n/a | ±1 % | 24,147,426 / 20,847,871 | B | OK |
| 29 | R22, R24, R26 (phase → divider), R63 (VBAT_SNS) | C36871 | 68k 1 % | UNI-ROYAL 0402WGF6802TCE, 1 %, 50 V | OK | 28.2 V max across | ±1 % | 260,866 / 216,042 | PE | OK |
| 30 | R300, R400 | C17958 | 22R 1206 | UNI-ROYAL 1206W4F220JT5E, 22 Ω 1 %, 250 mW, 200 V | 1206 OK | n/a | n/a | 909,259 / 844,029 | B | OK (§3) |
| 31 | R4 (VBAT → BUCK_EN) | C137735 | 390k 1 % | YAGEO RC0603FR-07390KL, 0603, 1 %, 100 mW, 75 V | 0603 OK | 28.7 V across at clamp | ±1 % | 15,940 / 9,179 (LCSC 2,500) | E | OK |
| 32 | R44 | C25792 | 47k 1 % | UNI-ROYAL 0402WGF4702TCE | OK | n/a | ±1 % | 5,820,842 / 5,477,565 | B | OK |
| 33 | R45 | C25798 | 75k 1 % | UNI-ROYAL 0402WGF7502TCE | OK | n/a | ±1 % | 57,276 / 19,176 (**LCSC 0**) | PE | OK (N6) |
| 34 | R46 | C25762 | 18k 1 % | UNI-ROYAL 0402WGF1802TCE | OK | n/a | ±1 % | 592,197 / 535,007 | PE | OK |
| 35 | R5 | C25794 | 51k 1 % | UNI-ROYAL 0402WGF5102TCE | OK | n/a | ±1 % | 2,015,091 / 1,894,731 | B | OK |
| 36 | R54–R59 | C25900 | 4.7k | UNI-ROYAL 0402WGF4701TCE, 1 % | OK | n/a | n/a | 16,282,289 / 15,074,886 | B | OK |
| 37 | R6–R11 | C25076 | 100R | UNI-ROYAL 0402WGF1000TCE, 1 % | OK | R11 sees ≤ 16.8 V at hot plug | n/a | 4,809,767 / 3,981,068 | B | OK (N4) |
| 38 | R60 | C17168 | 0R | UNI-ROYAL 0402WGF0000TCE | OK | n/a | n/a | 10,473,661 / 9,088,536 | B | OK |
| 39 | R62 | C11702 | 1k | UNI-ROYAL 0402WGF1001TCE | OK | n/a | n/a | 8,819,920 / 6,783,408 | B | OK |
| 40 | R70–R72, R80–R82 | C25104 | 330R | UNI-ROYAL 0402WGF3300TCE | OK | n/a | n/a | 1,346,306 / 1,160,805 | B | OK |
| 41 | RS1–RS3 | C2844506 | 2 mΩ 2512 | Milliohm HoLR2512-3W-2mR-1%, 2512, ±1 %, ±75 ppm (power field "-"; 3 W from the MPN) | custom land (r5 m8) | n/a | ±1 % | 3,115 / 3,102 | E | OK |
| 42 | RS4 | C46961745 | 1 mΩ 2512 | JIERR RE2512F3R001, 2512, 1 mΩ ±1 %, 3 W, ±50 ppm | R_2512 OK | n/a | ±1 % | 39,847 / 39,589 | E | OK |
| 43 | TH1 | C13564 | NCP18XH103F03RB | muRata, 0603, 10 kΩ ±1 %, B25/50 3380 K ±1 % | OK | n/a | ±1 % | 218,224 / 214,649 | E | OK |
| 44 | U1 | C521608 | STM32G474RET6 | ST, LQFP-64 10×10, 512 KB | OK | 3.3 V | n/a | **316 / 193 (LCSC 157)** | E | OK for 5; m5 |
| 45 | U11, U12 | C47507 | TPS22945DCKR | TI, SC-70-5, 1.62–5.5 V, 400 mΩ | OK | 5.5 V vs 5.05 V | n/a | 10,164 / 10,151 | E | OK |
| 46 | U2 | C543035 | DRV8323RHRGZR | TI, VQFN-48-EP 7×7, 6–60 V | OK | 60 V | n/a | **203 / 186** | E | OK; reserve (N5) |
| 47 | U3, U4 | C5447274 | DRV8316CRRGFR | TI, VQFN-40, SPI, 8 A peak, 95 mΩ | custom RGF fp | VM ≤ 35 V recommended vs 32.4 V | n/a | 2,928 / 2,886 | E | OK |
| 48 | U5 | C51118 | AP2112K-3.3TRG1 | DIODES, SOT-25, 3.3 V, 600 mA, VIN 6 V max | SOT-23-5 OK | 6 V vs 5.05 V | n/a | 46,370 / 44,633 | E | OK |
| 49 | U6 | C465737 | SN74LVC08APWR | TI, TSSOP-14, 1.65–3.6 V, OV-tolerant inputs | OK | 3.6 V vs 3.3 V | n/a | 35,282 / 35,226 | E | OK |
| 50 | U7 | C2876522 | INA239AIDGSR | TI, VSSOP-10, VCM −0.3…85 V, 2.7–5.5 V | MSOP-10 3×3 P0.5 OK | 85 V | n/a | **111 / 75** | E | OK; reserve (N5) |
| 51 | U8 | C22458649 | BQ76907RGRR | TI, VQFN-20-EP 3.5×3.5, 3–38.5 V | OK | 38.5 V vs 16.8 V | n/a | 2,394 / 2,391 | E | OK |
| 52 | U9, U10 | C68245 | SN74LVC3G17DCUR | TI, VSSOP-8 0.5 mm, 1.65–5.5 V, Schmitt | OK | OK | n/a | 3,335 / 3,241 | E | OK |

Every C-number resolves in both the LCSC and JLC catalogues.  Every MPN matches its Comment.  Every LCSC package matches the KiCad footprint.  No part is Y5V or Z5U: the MLCC dielectrics are X5R, X7R and C0G.  No line has stock below 50, and no line's presale figure is negative.

## 2. Capacitor bias derating

The effective-C figures are **estimates**.  They come from typical Samsung and Murata X5R/X7R DC-bias curves for the same case size and voltage rating (±15 points).  Samsung's product pages returned a server error, so I have no part-specific curve.  Worst case = estimate × (1 − tolerance) × 0.85 for X5R/X7R temperature drift.

| Refs | Part | Bias | Estimated C_eff (25 °C) | Estimated worst case | Requirement (source) | Verdict |
|---|---|---|---|---|---|---|
| C9 | 2.2 µF 0805 50 V X5R | 16.8 V | ≈ 1.0–1.2 µF | **≈ 0.8–0.9 µF** | BQ76907 **Cf (BAT) 1–40 µF**, and CREGSRC ≥ 1 µF.  BAT and REGSRC share C9 (DS §6.3 rec. op. table, lines "Cf … 1 … 40 µF", "CREGSRC … 1 µF") | **m2** |
| C27 | 2.2 µF 0805 50 V X5R | 16.8 V | ≈ 1.1 µF | ≈ 0.85 µF | Buck VIN.  C25/C26 (2 × 10 µF) are on the same node | OK |
| C25/C26/C302/C308/C402/C408 | 10 µF 1206 50 V X5R | 16.8 V | ≈ 4–5 µF | ≈ 3.5 µF | DRV8316 ≥ 10 µF nominal rated ≥ 2× VM.  Two per IC | OK |
| C21 | 1 µF 0603 50 V X5R | ≈ 11 V (VCP–VM) | ≈ 0.6–0.7 µF | ≈ 0.5 µF | DRV8323 "X5R or X7R, 1 µF, 25 V" (DS pin table) | OK (nominal as specified) |
| C303/C403 | 1 µF 0603 50 V X5R | ≈ 5 V | ≈ 0.85 µF | ≈ 0.65 µF | DRV8316 CP 1 µF | OK |
| C305/C405 | 1 µF 0603 50 V X5R | 3.3 V | ≈ 0.9–0.95 µF | **≈ 0.69–0.73 µF** | DRV8316C: "effective capacitance between 0.7 µF and 1.3 µF at 3.3 V across operating temperature" (SLVSH07 CAVDD row) | N1 (at the lower edge) |
| C64, C66 | 4.7 µF 0603 16 V X5R | 3.3 V | ≈ 3.0–3.5 µF | ≈ 2.3–2.7 µF | STM32 VDD bulk 4.7 µF; VREF+ 1 µF + 100 nF | OK |
| C46, C49 | 1 µF 0402 25 V X5R | 3.3 V or 5.05 V (JP1/JP2) | ≈ 0.75 µF at 3.3 V, ≈ 0.5–0.6 µF at 5 V | ≈ 0.4 µF | TPS22945 COUT ≥ 0.1 µF; COUT(MAX) = ILIM(min) × tBLANK(min) / VOUT = 0.1 A × 5 ms / 5 V = 100 µF (DS §9.1.5, eq.) | OK (see N2 for CIN) |
| C11, C22, C69, C70 | 1 µF 0402 25 V X5R | 3.3–5.05 V | ≈ 0.55–0.8 µF | ≈ 0.45 µF | BQ76907 CEXT REGOUT 1 µF; DRV8323 CDVDD 1 µF 6.3 V (DVDD = 3.3 V, DS VDVDD); AP2112 ≥ 1 µF (with C64 in parallel) | OK |
| C29/C30 | 22 µF 0805 25 V X5R | 5.05 V | ≈ 11–13 µF each | ≈ 9 µF each | buck output | OK |
| C307/C407 | 22 µF 0603 6.3 V X5R | 3.3 V | ≈ 9–11 µF | ≈ 7 µF | buck unused (resistor mode); rating: see m1 | m1 |
| C4–C8 | 220 nF 0603 50 V X7R | ≤ 4.2 V | ≈ 215 nF | ≈ 165 nF | BQ76907 CC 0.1–10 µF; RC ≤ 200 µs (100 Ω × 220 nF = 22 µs) | OK |
| C20/C304/C404 | 47 nF 50 V X7R | 0…VM | ≈ 35–40 nF at 16.8 V | — | TI 47 nF rated ≥ 2× VM | OK |

## 3. Resistor dissipation

| Refs | Across (worst) | P steady / worst | Rating | Verdict |
|---|---|---|---|---|
| R300/R400 22 Ω 1206 | (VM − VBK) × IBK (DRV8316C SLVSH07 eq. 6: PRBK > (VM − VBK) × IBK) | 13.5 V × IBK: 5 mA → 68 mW, 10 mA → 135 mW, **18.5 mA → 250 mW**.  Worst at the clamp (29.1 V) × 5 mA = 146 mW | 250 mW | OK while IBK ≤ 18 mA.  The buck has no external load, and firmware disables it (BUCK_DIS / BUCK_CL / BUCK_PS_DIS, r2 D-17).  The TI example sizes 0.41 W for a 20 mA load.  NOTE only |
| R1 100k | VBAT − 12 V zener | 0.23 mW / 4.2 mW at 32.4 V | 62.5 mW | OK |
| R4 390k 0603 | 14.9 V / 28.7 V | 0.57 mW / 2.1 mW | 100 mW, 75 V | OK.  An 0402 (50 V) would also do, but no Basic/PE 390k 0402 exists (JLC search "390kΩ 0402": all `expand`, no preferred flag).  C23150, the 0603 PE part, is still over-committed at **−3,439**, so C137735 stays |
| R5 51k | ≤ 3.75 V | 0.28 mW | 62.5 mW | OK |
| R63 68k | 14.6 V / 28.2 V | 3.1 mW / 11.7 mW | 62.5 mW, 50 V | OK |
| R22/R24/R26 68k | phase at VM, 100 % duty | 3.1 mW / 11.7 mW | 62.5 mW | OK |
| R54–R59 4.7k | 3.3 V (Hall line held low) | 2.3 mW; a line shorted to VS = 5 V gives 0.6 mW | 62.5 mW | OK |
| R42/R43/R50/R52/R53/R301/R401 10k | 3.3 V | 1.1 mW | 62.5 mW | OK |
| R62 1k | ≈ 3 V | 9 mW | 62.5 mW | OK |
| R6–R10 100 Ω | µA (balancing never enabled, DESIGN §4a) | ≈ 0 | 62.5 mW | OK.  Balancing would put ≈ 20 mA → 40 mW in each.  DESIGN.md already forbids it |
| R11 100 Ω | balance-lead hot plug into C9 | 2.8 W peak, τ ≈ 220 µs, E = ½CV² ≈ 0.3 mJ | 62.5 mW (pulse rating not checked) | N4 |
| R2/R3 10 Ω, R70–R82 330 Ω, pull-downs | µA | ≈ 0 | — | OK |
| RS1–RS3 2 mΩ | 20 A weapon phase | 0.8 W | 3 W | OK |
| RS4 1 mΩ | 22 A pack | 0.48 W | 3 W | OK |
| TH1 | 10k/10k divider at 3.3 V | ≤ 0.27 mW (≈ 0.3 °C self-heating) | 100 mW | OK |

## 4. BOM.md statements compared with live data

| Statement in BOM.md | Live data | Verdict |
|---|---|---|
| U1 "Extended, ~321 in stock" | JLC 316, **presale 193**, LCSC 157 | stale (m5) |
| U2 "203 in stock" | 203 / presale 186 | correct |
| U3/U4 "2,928", datasheet SLVSH07 | 2,928 / 2,886; `datasheets/DRV8316C.pdf` header reads "SLVSH07 – DECEMBER 2022" | correct |
| U7 "111 in stock"; INA229AIDGSR C2846803 drop-in "when stocked" | 111 / **75**; C2846803 is JLC 2, **presale −56**, LCSC 0 | correct (INA229 still unobtainable) |
| U8 "2,394" | 2,394 / 2,391 | correct |
| U6 "35k"; Nexperia C6053 alternate | 35,282; C6053 74LVC08APW,118 TSSOP-14, 17,460 / 17,435 | correct |
| U9/U10 "3,335"; C18213 "7,218" | 3,335; C18213 SN74LVC3G17DCTR 7,218 / 7,106 | correct |
| U11/U12 "10k" | 10,164 | correct |
| C1 "6,558", ESR 20 mΩ | 6,558; LCSC ESR 20 mΩ | correct |
| L1 "24k", DCR 0.13 Ω | 24,474; LCSC DCR 168 mΩ (max field); r6 datasheet 0.129 typ / 0.168 max | correct (typical) |
| J2/J3 "30k"; LXWCONN C53055322 | 30,558; C53055322 28,835 / 28,794 | correct |
| J4 vertical B5B-XH-A = C157991 | JST B5B-XH-A(LF)(SN), 63,403 / 56,542 | correct |
| D2 "Basic" | `base` | correct |
| Extended list "U1–U12, Q1–Q7, C1, C4–C8, D1, D4, D5, L1, RS1–RS4, TH1, R4, J1–J4" | Exactly 23 `expand` / non-preferred lines, matching the list | correct |
| "C4–C8 (220 nF 50 V 0603 has no Basic part)" | true for 50 V.  **C21120** CL10B224KA8NNNC 220 nF **25 V** X7R 0603 is `base`, 829,934 / 720,952 | misleading (m3) |
| Preferred list "R20 56k, **R22–R27/R63** 68k, R45 75k, R46 18k" | The 68k parts are R22, R24, R26, R63.  **R23, R25, R27 are 10k Basic** | wrong (m4) |
| "Everything else is Basic" | the remaining 25 lines are all `base` | correct |
| Header "rev B, **2026-09-24**" and "lookup on 2026-09-23" | today is 2026-09-23, so the header is dated tomorrow | m5 |
| DESIGN.md l.173 "C307 22 µF **6.3 V** … (TI §9.2.1.1.5)" | That wording is from SLVSF16B (DRV8316).  The fitted part is DRV8316**C** (SLVSH07), which says "X5R or X7R, 22-µF, **≥ 10-V**" (CBK row) and "a **10-V rated**, 22-µF capacitor for CBK" (§9, unused-buck paragraph) | m1 |

## 5. Extended-fee count and stock risk

- **23 Extended lines** carry a loading fee: C1, C4–C8, D1, D4, D5, J1, J2/J3, J4, L1, Q1–Q7, R4, RS1–RS3, RS4, TH1, U1, U2, U3/U4, U5, U6, U7, U8, U9/U10, U11/U12.  At JLC's $3 per unique Extended part that is about **$69 per order**.  **4 Preferred** lines (R20, R22/24/26/63, R45, R46) and **25 Basic** lines carry no fee.  J4 is through-hole, so assembly also needs THT/Standard handling (r5 N3).
- Fee reductions available now:
  - C4–C8: swap to C21120 (Basic) and save $3 (m3).
  - R4: no Basic or Preferred option exists today (C23150 PE, presale −3,439).
- **No line has stock below 50, and no presale figure is negative.** The thinnest lines:
  - U7 INA239AIDGSR: presale 75.  JLC has no alternate (search "INA239" returns only C2876522).
  - U2 DRV8323RHRGZR: presale 186.  Backup: **C2150467 DRV8323RHRGZT**, the same die on a small reel, 97 in stock.
  - U1 STM32G474RET6: presale 193.  Backups: **C1235414 STM32G474RBT3** (128 KB, −40…125 °C, 2,297 / 1,956) or **C529413 STM32G474RBT6** (211 / 154), if 128 KB of flash is enough.
  - D4 MMSZ5242B: 3,718.  RS1–RS3: 3,102.  U9/U10: 3,241.  All are comfortable for 5 boards.
- C25798 (R45 75k) shows LCSC stock 0 but JLC 57,276 / 19,176.  JLC assembly draws from JLC stock, so this is fine (N6).

## 6. Lifecycle and quality

- TI product pages (fetched 2026-09-23) show **ACTIVE** for TPS22945, DRV8323, INA239, BQ76907, DRV8316C, SN74LVC3G17 and SN74LVC08A.  None shows an NRND or "Not recommended for new designs" string.
- Panasonic EEHZK1V331P: Active per the distributor listings ([Future](https://www.futureelectronics.com/p/passives--capacitors--aluminum-organic-polymer/eehzk1v331p-panasonic-5188177), [Octopart](https://octopart.com/eehzk1v331p-panasonic-76964091), [Panasonic product page](https://industrial.panasonic.com/ww/products/capacitors/polymer-capacitors/hybrid-aluminum/zk-high-temp-reflow/EEHZK1V331P)).
- STM32: clones and counterfeits of STM32F4-class parts are documented ([Hackaday](https://hackaday.com/2020/10/22/stm32-clones-the-good-the-bad-and-the-ugly/), [ST community](https://community.st.com/t5/stm32-mcus-products/another-encounter-with-possibly-fake-chips/td-p/650133), [EEVblog LCSC thread](https://www.eevblog.com/forum/manufacture/unsettling-message-from-lcsc-about-stm32-purchase-counterfeit/)).  I found no report specific to the G474 at LCSC.  ST guarantees authenticity only through its authorized distributors.  NOTE (N7).
- I found no known quality issues for the remaining parts.  HUAYI, BORN, JSCJ, MDD, KENTO, XUNPU, BOOMELE, JIERR and Milliohm are domestic Chinese makers with no datasheet-independent verification here (NOTE).

## Findings

| ID | Severity | Item | Evidence | Fix |
|---|---|---|---|---|
| m1 | MINOR | C307/C407 CBK is 22 µF **6.3 V** (C59461).  The fitted DRV8316**C** datasheet asks for **≥ 10 V**.  DESIGN.md quotes the non-C datasheet (SLVSF16B) | SLVSH07 CBK row "X5R or X7R, 22-µF, ≥ 10-V"; §9 "a 10-V rated, 22-µF capacitor for CBK"; LCSC C59461 "Voltage Rating = 6.3V" | Use **C45783** 22 µF 25 V 0805 (Basic, already a BOM line, no fee; footprint → 0805), or **C86295** CL10A226MP8NUNE 22 µF 10 V 0603 (Extended, 900,201 / 687,776, +$3).  Update DESIGN.md l.173 |
| m2 | MINOR | C9 (BAT/REGSRC of BQ76907) 2.2 µF 0805 50 V X5R at 16.8 V: about 1.0–1.2 µF effective, worst case about 0.85 µF, which is below the **Cf ≥ 1 µF** minimum | BQ76907 DS rec. op.: "Cf External supply filter capacitance (BAT pin) 1 … 40 µF"; "CREGSRC 1 µF"; net BMS_BAT = C9, U8.16 REGSRC, U8.17 BAT | **C29823** FH 1206B475K500NT 4.7 µF 50 V X7R 1206 (**Basic**, 649,675 / 565,797), about 3 µF at 16.8 V.  Or C13585 10 µF 1206 (Basic, already a BOM line).  Hot-plug energy in R11/D5 rises in proportion (N4) |
| m3 | MINOR | C4–C8 use a 50 V Extended part where a 25 V Basic part suffices (≤ 4.2 V per cap, ≤ 16.8 V even with a floating tap).  This costs one Extended fee | C64705 `expand`; **C21120** CL10B224KA8NNNC 220 nF 25 V X7R 0603 `base` 829,934 / 720,952 | Swap to C21120 and correct the BOM.md note |
| m4 | MINOR | BOM.md Preferred list says "R22–R27/R63 68k".  R23/R25/R27 are 10k Basic | bom.csv 68k line = R22, R24, R26, R63 | Write "R22/R24/R26/R63 68k" |
| m5 | MINOR | BOM.md is stale or inconsistent: U1 "~321 in stock" is now JLC 316, presale 193, LCSC 157.  The header date (2026-09-24) is after the lookup date (2026-09-23) | JLC C521608 `stockCount 316, canPresaleNumber 193`; LCSC `stockNumber 157` | Refresh the figures and fix the date |
| N1 | NOTE | C305/C405 AVDD worst case ≈ 0.69–0.73 µF, at the lower edge of TI's 0.7–1.3 µF effective window.  A different 1 µF 0603 dielectric does not fix this | SLVSH07 CAVDD row | Leave the part as it is, and check AVDD ripple and regulation at bring-up |
| N2 | NOTE | TPS22945 local CIN (C45/C48, 100 nF) is smaller than COUT (C46/C49, 1 µF).  TI: "a CIN greater than COUT is highly recommended … 1-µF CIN usually sufficient" | TPS22945 DS §9.1.4–9.1.5 | Harmless here: VIN is the +3V3/+5V rail with ≥ 4.7 µF of bulk behind JP1/JP2.  Optionally make C45/C48 1 µF (C52923, same Basic line) |
| N3 | NOTE | R300/R400 250 mW covers IBK ≤ 18 mA at 16.8 V (≈ 10 mA at the 32 V clamp).  Relies on firmware writing CTRL6 early | SLVSH07 eq. 6 | None beyond the r2 D-17 firmware item |
| N4 | NOTE | R11 100 Ω 0402 takes a 2.8 W / ≈ 220 µs pulse at balance-lead hot plug (≈ 0.3 mJ; ≈ 0.6 mJ with the m2 fix).  The 0402 pulse curve was not checked | V²/R, τ = RC | Acceptable for an occasional event.  0603 if in doubt |
| N5 | NOTE | Thin stock: U7 presale 75, U2 186, U1 193 | §5 | Reserve on order day.  Backups: C2150467, C1235414 / C529413 |
| N6 | NOTE | C25798 shows LCSC stock 0 (JLC 57,276 / 19,176) | LCSC `stockNumber 0` | None for JLC assembly |
| N7 | NOTE | STM32 counterfeit risk exists in the grey market.  LCSC is not an ST-franchised source | web sources in §6 | Accept for prototypes.  Check the part marking and DBGMCU_IDCODE at bring-up |

No part is obsolete or NRND.  There is no wrong MPN, no wrong package, no Y5V/Z5U dielectric and no over-voltage rating.  No line is short for 5 boards.

**Verdict: BLOCKER 0, MAJOR 0, MINOR 5, NOTE 7.**
