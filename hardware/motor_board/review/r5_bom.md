# R5: BOM and manufacturability review (motor board rev A)

Reviewer: adversarial BOM / JLC assembly pass. Date checked: **2026-09-23**. No design files were changed.

**Method.** I looked up every C-number in `design/motor_board.py` `LCSC{}` / `design/bom.csv`, one at a time with a 1.5 s pause, in two places:
- **LCSC product-detail API** (`wmsc.lcsc.com/ftps/wm/product/detail?productCode=Cxxxx`). This is the data behind `https://www.lcsc.com/product-detail/Cxxxx.html`. It gave the MPN, maker, package, parameters and LCSC stock.
- **JLCPCB SMT-library API** (`jlcpcb.com/.../smtGood/selectSmtComponentList/v2`). This is the data behind `https://jlcpcb.com/partdetail/Cxxxx`. It gave the library class (`base` = Basic, `expand` = Extended, and the "preferred" flag), JLC stock, and `canPresaleNumber` (available stock minus stock already reserved by other orders; a negative value means the stock is already committed).

I checked ratings against the datasheets in `datasheets/` (pdftotext) where a claim depended on them. "Stock" below is **JLC stock / LCSC stock** on 2026-09-23. Source URLs follow the patterns above. Only the C-number changes, so the table does not repeat them.

Class key: **B** = Basic. **PE** = Preferred Extended (no loading fee in Economic PCBA). **E** = Extended ($3 loading fee per unique part).

## 1. Line-by-line verification

| # | Refs | C-number | Claimed | Verified (MPN, value, rating, package) | Stock JLC / LCSC (presale) | Class | Status |
|---|---|---|---|---|---|---|---|
| 1 | C1 | C242138 | 470 µF 25 V polymer, 10×10.5 | Panasonic EEHZK1E471P: hybrid polymer, 470 µF ±20 %, 25 V, 10×10.2 mm (G case). The datasheet gives 20 mΩ and 2.8 A rms at 100 kHz. LCSC's "420 mA@100 Hz" is a generic field. | 936 / 936 (883) | E | **ISSUE** (M1): 25 V rating vs the 32 V TVS clamp. BOM.md's "~5 in stock" is stale. |
| 2 | C2,C4–C8,C24,C28,C300,C301,C400,C401 (12) | C14663 | 100 nF 50 V 0603 | YAGEO CC0603KRX7R9BB104: 100 nF ±10 %, 50 V, X7R, 0603 | 49.0 M / 7.7 M | B | OK |
| 3 | C20,C304,C404 | C1622 | 47 nF 50 V 0603 | Samsung CL10B473KB8NNNC: 47 nF ±10 %, 50 V, X7R, 0603 | 780 k / 320 k | B | OK. Sees VM, 32 V worst case, which is 64 % of rating. |
| 4 | C21,C22,C305,C405,C66,C69,C70 (7) | C52923 | 1 µF 25 V 0402 | Samsung CL05A105KA5NQNC: 1 µF ±10 %, 25 V, **X5R**, 0402 | 6.7 M / 1.3 M | B | OK on 3.3–5 V rails. **ISSUE on C21** (m4): VCP–VM is about 11 V, so heavy DC-bias loss. |
| 5 | C25,C26,C302,C402 | C13585 | 10 µF 50 V 1206 | Samsung CL31A106KBHNNNE: 10 µF ±10 %, 50 V, X5R, 1206, T = 1.6 mm | 2.69 M / 484 k | B | OK. About 5 µF effective at 16.8 V (§3). The SPICE model already assumes 5 µF. |
| 6 | C27 | **C49217** | 2.2 µF 50 V 0805 | **FH 0805F225M500NT: 2.2 µF ±20 %, 50 V, Y5V** | **1 / 0 (−23)** | PE | **ISSUE** (B5): Y5V dielectric and out of stock |
| 7 | C29,C30 | C45783 | 22 µF 25 V 0805 | Samsung CL21A226MAQNNNE: 22 µF ±20 %, 25 V, X5R, 0805 | 4.30 M / 2.03 M | B | OK. About 11–13 µF each at 5 V. |
| 8 | C3,C23,C40,C60–C63,C65,C67,C68,C306,C406 (12) | C1525 | 100 nF 16 V 0402 | Samsung CL05B104KO5NNNC: 100 nF ±10 %, 16 V, X7R, 0402 | 25.4 M / 6.4 M | B | OK. Every node is ≤ 3.3 V. C68 on VBAT_SNS reaches ≤ 4.1 V at a 32 V clamp. |
| 9 | C307,C407 | C59461 | 22 µF 6.3 V 0603 | Samsung CL10A226MQ8NRNC: 22 µF ±20 %, 6.3 V, X5R, 0603 | 8.4 M / 6.5 M | B | OK as TI specifies (a "6.3 V, 22 µF" CBK). Only if BUCK_SEL stays at 3.3 V (m6). |
| 10 | C64 | C23733 | 4.7 µF 10 V 0402 | Samsung CL05A475MP5NRNC: 4.7 µF ±20 %, 10 V, X5R, 0402 | 2.69 M / 1.13 M | B | MINOR (m7): about 2.2 µF effective at 3.3 V |
| 11 | C9,C303,C403 | C15849 | 1 µF 50 V 0603 | Samsung CL10A105KB8NNNC: 1 µF ±10 %, 50 V, X5R, 0603 | 6.34 M / 1.7 k | B | OK. C9 is at 16.8 V (about 0.5 µF effective); C303/C403 are at CP–VM, about 5 V. |
| 12 | D1 | C151922 | SMBJ20A | BORN SMBJ20A: **unidirectional**, VRWM 20 V, VBR 24.5 V (LCSC field; standard spec is 22.2–24.5 V), **Vc 32.4 V @ 18.6 A**, 600 W 10/1000 µs, SMB | 81.3 k / 81.2 k | E | OK |
| 13 | D2 | C8598 | B5819W 40 V 1 A SOD-123 | JSCJ (Changjiang) **B5819W SL**: 40 V, 1 A, VF 0.6 V @ 1 A, IFSM 9 A, SOD-123 | 467 k / 205 k | **B** | OK. 40 V covers the 32 V clamp. |
| 14 | D3 | C2286 | LED red 0603 | KENTO KT-0603R: red, 0603, VF 1.8–2.4 V, 20 mA max | 4.09 M / 2.54 M | B | OK. About 3 mA through 1 k from 5 V. |
| 15 | D4 | C21567 | MMSZ5242B 12 V SOD-123 | JSCJ MMSZ5242B: Vz 12 V (11.4–12.6 V), 350 mW, SOD-123 | 3,849 / 3,840 | E | OK |
| 16 | J1 | C59981 | 2×10 1.27 mm SMD male | BOOMELE 1.27-2\*10P ("Vertical SMD Pin"): 2×10, 1.27 × 1.27 mm, square gold pin, 3 mm mating pin, 1.5 mm insulator, 3 A. Datasheet land: two pad rows, 6.5 mm outer span. | 7,393 / 6,280 | E | OK. Footprint note m9. |
| 17 | J2,J3 | **C160405** | JST SM06B-SRSS-TB | JST SM06B-SRSS-TB(LF)(SN): SH 1.0 mm, 6P, SMD right angle | **3 / 0 (−464)** | E | **ISSUE** (B4): cannot build 2 |
| 18 | J4 | C263757 | JST S5B-XH-A (side entry) | JST S5B-XH-A(LF)(SN): XH 2.5 mm, 5P, **THT right angle** | 21.9 k / 21.6 k | E | OK for stock. THT needs Standard PCBA (N3). |
| 19 | L1 | C135264 | 22 µH ≥ 1.2 A | SXN SMNR4020-22UH: 22 µH ±20 %, **Isat = Irated = 1.05 A**, DCR 0.35 Ω typ (datasheet) / 455 mΩ (LCSC field, likely max), 4×4 mm | 43.4 k / 43.4 k | E | **ISSUE** (M3): Isat is below the buck current limit. The comment "≥1.2A" is not met. |
| 20 | Q1–Q7 | C2874970 | HYG015N04LS1C2 40 V | HUAYI HYG015N04LS1C2: 40 V, Vgs ±20 V, RDS(on) **1.4 typ / 1.7 max @ 10 V**, 2.0 typ / 2.4 max @ 4.5 V, Qg 59 nC, PDFN5×6-8L | 17.3 k / 17.3 k | E | OK. The LCSC-dict comment "2.0 mOhm" is the 4.5 V typical figure (n1). |
| 21 | R1,R40,R41 | C25741 | 100 k 0402 | UNI-ROYAL 0402WGF1003TCE: 100 k 1 %, 62.5 mW, 50 V | 9.09 M / 4.85 M | B | OK. R1 is 4 mW at a 32 V clamp. |
| 22 | R2,R3,R11 | C25077 | 10 Ω 0402 | UNI-ROYAL 0402WGF100JTCE: 10 Ω. The MPN suffix says 5 % (J); the listing says 1 %. 62.5 mW. | 2.05 M / 391 k | B | OK. The tolerance doesn't matter here. |
| 23 | R20 | C25796 | 56 k 1 % 0402 | UNI-ROYAL 0402WGF5602TCE: 56 k 1 % | 241 k / 163 k | **PE** | OK. BOM.md wrongly says "Basic" (m2). |
| 24 | R21,R23,R25,R27,R42,R43,R50–R53,R61,R64,R301,R401 (14) | C25744 | 10 k 1 % 0402 | UNI-ROYAL 0402WGF1002TCE: 10 k 1 % | 24.2 M / 12.4 M | B | OK |
| 25 | R22,R24,R26,R63 | C36871 | 68 k 1 % 0402 | UNI-ROYAL 0402WGF6802TCE: 68 k 1 % | 261 k / 179 k | **PE** | OK. m2 applies. |
| 26 | R300,R400 | C23345 | 22 Ω 0603 | UNI-ROYAL 0603WAF220JT5E: 22 Ω, **100 mW**, 75 V | 9.63 M / 7.49 M | B | **ISSUE** (M2): power margin |
| 27 | R4 | **C23150** | 390 k 1 % 0603 | UNI-ROYAL 0603WAF3903T5E: 390 k 1 %, 100 mW | 32.6 k / **0** (**−3,419**) | PE | **ISSUE** (m1): stock is over-committed |
| 28 | R5 | C25794 | 51 k 1 % 0402 | UNI-ROYAL 0402WGF5102TCE: 51 k 1 % | 2.01 M / 1.58 M | B | OK |
| 29 | R6–R10 | C25076 | 100 Ω 0402 | UNI-ROYAL 0402WGF1000TCE: 100 Ω 1 % | 4.81 M / 1.71 M | B | OK |
| 30 | R60 | C17168 | 0 Ω 0402 | UNI-ROYAL 0402WGF0000TCE: 0 Ω | 10.5 M / 5.44 M | B | OK |
| 31 | R62 | C11702 | 1 k 0402 | UNI-ROYAL 0402WGF1001TCE: 1 k 1 % | 8.82 M / 1.50 M | B | OK |
| 32 | RS1–RS3 | C2844506 | 2 mΩ 1 % 2512 | Milliohm HoLR2512-3W-2mR-1%: **2 mΩ ±1 %, 2512 (6.4×3.2 mm), 3 W** (part-number code; derates above 70 °C), TCR ±75 ppm/°C (LCSC field; the datasheet allows ±50 or ±75). For 1–4 mΩ the **terminals are 2.0 mm long** and the datasheet gives its own land pattern. | 3,115 / 3,115 | E | OK (size confirmed 2512). Land-pattern note m8. 0.8 W at 20 A. |
| 33 | RS4 | C46961745 | 1 mΩ 1 % 2512 3 W | JIERR RE2512F3R001: 1 mΩ ±1 %, 3 W, 2512, alloy, ±50 ppm/°C | 39.9 k / 39.9 k | E | OK. 0.48 W at 22 A. |
| 34 | TH1 | C13564 | NCP18XH103F03RB | Murata NCP18XH103F03RB: 10 kΩ ±1 %, B25/50 = 3380 K ±1 %, 0603 | 218 k / 215 k | E | OK |
| 35 | U1 | C521608 | STM32G474RET6 | ST STM32G474RET6, LQFP-64 10×10, 512 KB | **321** / 157 (198) | E | OK for 1–5 boards. Check again on order day. |
| 36 | U2 | **C545497** | DRV8323RSRGZR | TI DRV8323RSRGZR, VQFN-48 7×7 | **0 / 0 (−77)** | E | **ISSUE** (B1) |
| 37 | U3,U4 | **C5218861** | DRV8316RRGFR | TI DRV8316RRGFR, VQFN-40 5×7 | **13 / 0 (−36)** | E | **ISSUE** (B2) |
| 38 | U5 | C51118 | AP2112K-3.3TRG1 | Diodes AP2112K-3.3TRG1: 3.3 V, 600 mA, VIN max 6 V, SOT-23-5 | 46.4 k / 46.4 k | E | OK. The input is +5 V at 5.05 V. |
| 39 | U6 | C460522 | 74LVC1G08SE-7 | Diodes 74LVC1G08SE-7, SOT-353, 1.65–5.5 V | 9,123 / 9,120 | E | OK |
| 40 | U7 | **C2846803** | INA229AIDGSR | TI INA229AIDGSR, VSSOP-10, VCM 85 V | **2 / 0 (−56)** | E | **ISSUE** (B3). BOM.md's "986 in stock" is wrong today. |
| 41 | U8 | C22458649 | BQ76907RGRR | TI BQ76907RGRR, VQFN-20 3.5×3.5, 3–38.5 V | 2,394 / 2,394 | E | OK. BOM.md's "stock not visible" is stale. |

Every C-number resolves in both the JLC SMT library and LCSC; none is LCSC-only. The listed MPNs and packages match `motor_board.py` on every line except these: C27 is Y5V (not stated in the design, and not acceptable); the L1 current rating is below the design's own "≥1.2 A"; and the Q-FET RDS comment is off.

## 2. Capacitor voltage stress and DC bias

The DC-bias figures are **typical Samsung X5R class curves for that case size and rating**. Samsung's product page and spec sheet for these parts publish only a generic example curve. I did not get a part-specific numeric curve, so the effective-C column is an estimate (±15 points). It is not a verified value.

| Refs | Part | Across | V steady (worst) | Rating / ratio | Effective C at bias (est.) | Verdict |
|---|---|---|---|---|---|---|
| C1 | EEHZK1E471P 25 V hybrid | VBAT–GND | 16.8 V (TVS clamp up to 32.4 V at Ipp; ≥ 22.2 V as soon as D1 conducts) | 25 V: 1.49× steady, **0.77× at clamp** | n/a (polymer, no bias loss) | **M1** |
| C24,C300,C301,C400,C401 | 100 n 50 V X7R 0603 | VBAT | 16.8 (32) | 3.0× (1.56×) | about 70 nF | OK |
| C25,C26,C302,C402 | 10 µ 50 V X5R 1206 | VBAT | 16.8 (32) | 3.0× (1.56×) | about 4–5.5 µF | OK. sim_hotplug already uses 5 µF. |
| C27 | 2.2 µ 50 V **Y5V** 0805 | VBAT (buck VIN) | 16.8 (32) | 3.0× | **about 0.3–0.6 µF**, and Y5V also loses up to −82 % over temperature | **B5** |
| C20,C304,C404 | 47 n 50 V X7R | CPH–CPL (swings 0…VM) | 16.8 (32) | 3.0× (1.56×), which meets TI's "≥ 2× VM" | about 35 nF | OK |
| C21 | 1 µ 25 V **0402 X5R** | U2 VCP–VM | about 10.5–11 V (DRV8323 VCP = VM + 10.5 V) | 2.3× | **about 0.3–0.4 µF** (0402 25 V X5R at 44 % of rating) | **m4**: TI specifies "1 µF, 25 V" |
| C303,C403 | 1 µ 50 V X5R 0603 | DRV8316 CP–VM | 4.7 V typ, 5.25 V max | 9.5× | about 0.85 µF | OK |
| C28 | 100 n 50 V | BUCK_CB–SW | about 5 V | 10× | about 95 nF | OK |
| C29,C30 | 22 µ 25 V X5R 0805 | +5 V | 5.05 V | 5× | about 11–13 µF each | OK |
| C307,C407 | 22 µ 6.3 V X5R 0603 | FB_BK (VBK) | 3.3 V (BUCK_SEL default 00b) | 1.9× | about 8–10 µF | OK at 3.3 V. At 5.0/5.7 V it is only 1.1× (m6). |
| C64 | 4.7 µ 10 V X5R 0402 | +3V3 | 3.3 V | 3.0× | about 2–2.5 µF | m7 |
| C22,C305,C405,C66,C69,C70 | 1 µ 25 V X5R 0402 | 3.3–5 V rails | ≤ 5.05 V | ≥ 5× | about 0.6–0.8 µF | OK |
| C9 | 1 µ 50 V X5R 0603 | BMS_BAT | 16.8 V | 3.0× | about 0.45–0.55 µF | OK (TI app circuit uses 1 µF; fine for supply filtering) |
| C2–C8 | 100 n 50 V X7R | INA diff / cell diff / CELL0–GND | ≤ 4.3 V | > 10× | about 95 nF | OK |
| C3,C23,C40,C60–C63,C65,C67,C68,C306,C406 | 100 n 16 V X7R 0402 | 3.3 V nodes; VBAT_SNS ≤ 2.15 V (4.1 V at a clamp) | ≤ 3.3 V | ≥ 3.9× | about 85 nF | OK |

## 3. Resistor power

| Ref | Case | Worst-case dissipation | Rating | Verdict |
|---|---|---|---|---|
| R300/R400 (22 Ω, DRV8316 buck RBK, resistor mode) | TI SLVSF16B §9.2.1.1.5 eq. 18: P_RBK ≈ (VM − VBK) × IBK. VBK = 3.3 V (default), VM = 16.8 V, so P = 13.5 V × IBK. With BUCK_PS_DIS = 0 (the default) AVDD is fed from VBK, so IBK = the AVDD load + VREF (50 µA) + internal quiescent. IAVDD is allowed up to 30 mA. The datasheet does not state the part's own draw; the IVM difference between buck on and buck off suggests a few mA. Result: 5 mA → 68 mW, 7.4 mA → 100 mW, 30 mA → 0.41 W. Until firmware sets BUCK_CL = 1, the default BUCK_CL = 0 (600 mA limit) gives on-pulses of (16.8 − 3.3)/22 = 0.61 A. That is 8.3 W peak into an 0603. TI's worked example sizes RBK at 0.43 W. | 0603 = 100 mW | **M2** |
| R1 (100 k, Q7 gate) | (16.8 − ~11)² / 100 k = 0.3 mW; at a 32 V clamp, (32 − 12)² / 100 k = 4 mW | 62.5 mW | OK |
| R4/R5 divider (390 k / 51 k) | 16.8² / 441 k = 0.64 mW | 100 / 62.5 mW | OK |
| R63/R64, R22–R27 (68 k / 10 k) | 16.8² / 78 k = 3.6 mW; 25.2 V phase → 8.1 mW | 62.5 mW | OK |
| R2/R3/R11 (10 Ω) | µA-level currents (INA229 bias, BQ76907 about 150 µA) | 62.5 mW | OK. R2/R3 see the input-filter charge current on a pack-short dV/dt; that is short and TI recommends it. |
| R6–R10 (100 Ω) | balancing unused; nA–µA | 62.5 mW | OK. If balancing is ever enabled (50 mA): 0.25 W, which is not OK in 0402. |
| R62 (1 k LED) | (5 − 2) V × 3 mA = 9 mW | 62.5 mW | OK |
| RS1–RS3 (2 mΩ) | 20 A → 0.8 W; 40 A OCP-level transient → 3.2 W for µs–ms | 3 W @ 70 °C | OK |
| RS4 (1 mΩ) | 22 A → 0.48 W; 27 A → 0.73 W | 3 W | OK |

## 4. Issues

| ID | Sev | Issue | Evidence | Fix (replacement C-numbers checked 2026-09-23) |
|---|---|---|---|---|
| B1 | **BLOCKER** | U2 DRV8323RSRGZR is not buildable at JLC: 0 in stock and −77 presale, 0 at LCSC. | JLC API C545497: stock 0, canPresale −77. LCSC stock 0. The only in-stock 48-pin R-variant is **DRV8323RHRGZR C543035** (203 in stock). That is the hardware (H) variant: pins 29–32 are MODE/IDRIVE/VDS/GAIN, not SPI. It is **not** a drop-in and the design loses SPI configuration and fault readout. | Buy the RS variant elsewhere and consign it to JLC ("parts from my inventory" / Global Sourcing). A web-search snippet says the TI store has about 41 k DRV8323RSRGZR in stock and DigiKey has it on back-order (UNVERIFIED today). Don't redesign to RHRGZR unless consigned stock is impossible. Check again on order day. |
| B2 | **BLOCKER** | U3/U4 DRV8316RRGFR: 13 in stock at JLC but presale −36 (over-committed); 0 at LCSC. Needs 2 per board. | JLC API C5218861 | **DRV8316CRRGFR, C5447274** (2,928 in stock, presale 2,886, VQFN-40 5×7). TI SLVSH07 Table 6-1: the CR pinout matches the DRV8316R pinout used here. Pin 24 is NC, pins 33–36 are SDO/SDI/SCLK/nSCS, and 37 is VREF/ILIM. §8.3.3 says the variants are "largely pin-to-pin compatible". BUCK_DIS/BUCK_PS_DIS still exist. TI's product page recommends the "C" for new designs because of its improved CSA. Firmware must use the DRV8316C register map, which adds the ILIM / cycle-by-cycle modes and has some different defaults. Review the register-level differences before switching. |
| B3 | **BLOCKER** | U7 INA229AIDGSR: 2 in stock (presale −56) at JLC, 0 at LCSC. BOM.md's "986 in stock" is wrong. | JLC API C2846803 | (a) Consign from TI or a distributor, or use Global Sourcing. (b) Or use **INA239AIDGSR C2876522** (111 in stock, presale 75). It is the same VSSOP-10 pinout and the same SPI interface, but 16-bit, with **no ENERGY/CHARGE accumulators**, so firmware must integrate current for coulomb counting. INA228 (C5214669, I²C, 2 available) and INA237 (C2864837, I²C) would need interface changes. |
| B4 | **BLOCKER** | J2/J3 SM06B-SRSS-TB: 3 in stock (presale −464) at JLC, 0 at LCSC. Needs 2 per board. | JLC API C160405 | SH-1.0 6P right-angle SMD clones: **XUNPU WAFER-SH1.0-6PWB C3029345** (30.6 k) or **LXWCONN SH1.0mm-6P-WT C53055322** (28.8 k). Check the clone drawing (mounting-tab pads, pin-1 side) against the JST SM06B-SRSS-TB footprint before swapping. |
| B5 | **BLOCKER** | C27 (buck VIN at U2 pin 47): **Y5V** and out of stock (JLC 1 / presale −23, LCSC 0). At 16.8 V a 50 V Y5V 0805 keeps only about 15–30 % of 2.2 µF, and Y5V loses a further −82 % at the temperature extreme. This is the buck's hot-loop cap. | LCSC C49217 params: "Temperature Coefficient = Y5V", stock 0 | **Samsung CL21A225KBQNNNE, C377773**: 2.2 µF 50 V **X5R** 0805, **Basic**, 705 k in stock. It also removes one Preferred-Extended line. |
| M1 | MAJOR | C1 is rated 25 V, but the rail is clamped by an SMBJ20A (VBR 22.2–24.5 V, Vc 32.4 V at Ipp). Any event that makes D1 conduct (regen, weapon braking, lead inductance) takes C1 to or past 25 V. The datasheet in `datasheets/` states no surge rating. Panasonic hybrids are typically 1.15 × VR = 28.75 V (UNVERIFIED). The steady-state ratio is 1.49×. Stock is not the problem: 936 today, not ~5. | LCSC/JLC C242138. ZK datasheet row: 470 µF / 25 V, 10×10.2, 2.8 A, 20 mΩ. | **Panasonic EEHZK1V331P, C278516**: 330 µF **35 V** hybrid, the same 10×10.2 G case (same footprint), 20 mΩ, 2.8 A rms / 100 kHz (datasheet), 6,558 in stock. Re-run `spice/sim_hotplug.py` with 330 µF, because the DRV8316 4 V/µs ramp margin depends on C1. For ≥ 3 A ripple from one part: **JIERR MA35V330M10x10, C46550470** (polymer, 330 µF 35 V, 25 mΩ, 3.5 A @ 100 kHz, 35 k in stock, 10×10 mm; check the footprint). Two EEHZK1V331P in parallel give 660 µF / 5.6 A. 25 V in-stock options that pass ≥ 3 A: **MA25V470M8x10 C46550466** (470 µF, 25 mΩ, 4.1 A, 130 k in stock, 8×10 mm) and **KNSCHA 118EC421 C46528073** (470 µF, 14 mΩ, 4 A, 1,926 in stock, 10×12.8 mm); both keep the 25 V weakness. |
| M2 | MAJOR | R300/R400 (22 Ω 0603, 100 mW) in DRV8316 buck resistor mode: P ≈ 13.5 V × IBK is ≥ 100 mW once IBK ≥ 7.4 mA, and IBK is not bounded by the datasheet (IAVDD is allowed up to 30 mA). Until SPI sets BUCK_CL = 1, every on-pulse is 0.6 A (8 W peak) in an 0603. TI sizes RBK for 0.43 W. | SLVSF16B §8.3.4.2, §9.2.1.1.5 eq. 18–20, Table 8-5 (resistor mode requires BUCK_CL = 1b). Default BUCK_CL = 0 → 360–900 mA limit. | Change to 1206: **UNI-ROYAL 1206W4F220JT5E, C17958** (22 Ω, 250 mW, **Basic**, 909 k in stock). A 2010 0.5 W part matches TI's example exactly. Firmware: write BUCK_CL = 1 (and BUCK_PS_DIS = 1 before BUCK_DIS = 1) as the first SPI access. |
| M3 | MAJOR | L1 SMNR4020-22UH: Isat 1.05 A, below the DRV8323 buck peak current limit (ILIMIT 1.2 A typ, up to 1.7 A; SLVSDJ3 §7.5). At start-up into the compute board's input capacitance, or on a 5 V short, the switch runs to current limit and the inductor saturates. Current then overshoots past ILIMIT during the limit's response time. The design comment asks for "≥1.2A" and the part does not meet it. DCR is 0.35 Ω typ, not better. | LCSC/JLC C135264 ("Isat 1.05 A"); datasheet row SMNR4020-22UH: 0.350 Ω, 1.05 A | Same 4×4 footprint family: **Changjiang FHD4020S-220MT, C843299** (Isat 1.5 A, DCR 415 mΩ, 6.1 k in stock). This is the smallest change and still sits between typ and max ILIMIT. Better: **Changjiang FNR5040S220MT, C167971** (5×5, Isat 1.8 A, DCR 168 mΩ, 24.5 k in stock). Needs the L_Changjiang_FNR5040S footprint. |
| m1 | MINOR | R4 390 k 0603 (C23150): LCSC 0, JLC 32.6 k but presale −3,419 (over-committed) | JLC/LCSC API | **YAGEO RC0603FR-07390KL, C137735** (15.9 k) or **Panasonic ERJ3EKF3903V, C403198** (19.0 k), both 1 % 0603 |
| m2 | MINOR | BOM.md says "All resistors and ceramic capacitors are JLC Basic". False: 56 k (C25796), 68 k (C36871), 390 k (C23150) and 2.2 µF (C49217) are **Preferred Extended**. They carry no fee in Economic PCBA but do not count as Basic. BOM.md also carries stale stock claims: C1 "~5" (now 936), INA229 "986" (now 2), BQ76907 "not visible" (now 2,394). | JLC API `componentLibraryType = expand, preferredComponentFlag = true` | Fix the text. No part change is needed for 56 k / 68 k. |
| m3 | MINOR | The LCSC-dict comment on `FET` says "40 V 2.0 mOhm". The datasheet gives 1.4 mΩ typ / 1.7 mΩ max at Vgs = 10 V and 2.0 / 2.4 mΩ at 4.5 V. LCSC lists 2.4 mΩ @ 4.5 V. | HYG015N04LS1C2.pdf elec. char. table | Correct the comment. The netlist description already says 1.4 mΩ. |
| m4 | MINOR | C21 (VCP–VM on the DRV8323): a 25 V 0402 X5R at about 11 V is roughly 0.3–0.4 µF effective vs TI's "1 µF, 25 V". | SLVSDJ3 pin table: "X5R or X7R, 1 µF, 25 V ceramic capacitor between VCP and VM" | Use **C15849** (1 µF 50 V X5R 0603, already a BOM line, Basic): about 0.6 µF at 11 V. A 1 µF 25 V/50 V X7R 0805 would do better. |
| m6 | MINOR | C307/C407 are 22 µF 6.3 V 0603, adequate only while BUCK_SEL = 00b (3.3 V). If firmware ever selects 5.0/5.7 V, the cap runs at 90 % of rating with about 20 % of its capacitance left. | TI §9.2.1.1.5 | Keep BUCK_SEL at 3.3 V (document it as a firmware constraint), or use 22 µF 10 V 0805 |
| m7 | MINOR | C64 (MCU bulk) 4.7 µF 10 V 0402 gives about 2–2.5 µF at 3.3 V | typical 0402 10 V X5R bias | **Samsung CL10A475KO8NNNC, C19666** (4.7 µF 16 V X5R 0603, Basic, 2.79 M in stock) |
| m8 | MINOR | RS1–RS3: 1–4 mΩ HoLR2512 parts have **2.0 mm terminals** (5–500 mΩ parts have 0.9 mm). The datasheet gives a dedicated land for 1–4 mΩ, and the "sensing trace" connects at the inner pad edge. KiCad R_2512_6332Metric has pads 1.35 × 3.35 at ±2.9 mm, with the inner edge at ±2.225 mm. The part's terminals start at ±1.2 mm, so the Kelvin points in DESIGN §5 do not sit at the resistive element's edge, which adds pad-copper error to a 2 mΩ reading. | HoLR2512 datasheet p.2 dimension table (C = 2.0 mm for 1–4 mR) and recommended-pad table | Draw a custom footprint to the Milliohm 1–4 mΩ land pattern, with the sense taps at the inner pad edges |
| m9 | MINOR | J1 BOOMELE land (datasheet: 6.5 mm outer row span, 1.27 pitch) vs KiCad PinHeader_2x10_P1.27mm_Vertical_SMD (outer span 6.3 mm, pads 2.4 × 0.74). This is close but not the vendor land. | BOOMELE_1.27-2x10P.pdf drawing | Use the vendor land, and confirm the mating female part and stack height with the compute board |
| N1 | NOTE | Stock under 500 on the order date: STM32G474RET6 (JLC 321, presale 198). Also under 50 (or over-committed): B1–B5 and m1. | JLC API | Reserve or pre-order the STM32 into JLC parts inventory when ordering |
| N2 | NOTE | Extended-part fees: **18 Extended lines** (C242138, C151922, C21567, C59981, C160405, C263757, C135264, C2874970, C2844506, C46961745, C13564, C521608, C545497, C5218861, C51118, C460522, C2846803, C22458649). At $3 per unique Extended part that is about **$54 per order**. There are 4 more Preferred-Extended lines (3 after the B5 fix). 19 lines are Basic. | JLC API class per line | The fixes above add no new Extended lines except where a part is swapped one-for-one (C278516, C5447274, C3029345, C843299/C167971). C377773, C17958 and C19666 are Basic. |
| N3 | NOTE | J4 S5B-XH-A is **through-hole** (JLC "【插件】"). It needs JLC Standard PCBA THT assembly or hand soldering; Economic PCBA does not do THT. | JLC API C263757 | Either accept Standard PCBA, or hand-solder J4. Vertical B5B-XH-A C157991 (63.4 k in stock) is also THT. |
| N4 | NOTE | SMBJ20A: its minimum VBR of 22.2 V leaves only 5.4 V above a full 4S pack. That is fine (leakage ≤ 1 µA at 20 V). The clamp at Ipp (32.4 V) is below the DRV8316 40 V abs max, and all ceramic caps are ≥ 50 V except C1 (M1) and the low-voltage-node parts. | LCSC C151922 params | none |

## 5. Summary of replacements

| Line | From | To | Class | Stock 2026-09-23 |
|---|---|---|---|---|
| U2 | C545497 (0) | consign DRV8323RSRGZR (TI store / Global Sourcing) | E | JLC 0 |
| U3, U4 | C5218861 (13, −36) | **C5447274** DRV8316CRRGFR (firmware register review) | E | 2,928 |
| U7 | C2846803 (2, −56) | consign INA229, or **C2876522** INA239AIDGSR (no energy/charge regs) | E | 111 |
| J2, J3 | C160405 (3, −464) | **C3029345** XUNPU WAFER-SH1.0-6PWB (check footprint) | E | 30,563 |
| C27 | C49217 (Y5V, 1) | **C377773** CL21A225KBQNNNE X5R | **B** | 705,372 |
| C1 | C242138 (25 V) | **C278516** EEHZK1V331P 35 V, same footprint (re-run the hot-plug sim) | E | 6,558 |
| R300, R400 | C23345 0603 | **C17958** 22 Ω 1206 250 mW | **B** | 909,259 |
| L1 | C135264 (Isat 1.05 A) | **C843299** FHD4020S-220MT (1.5 A, 4×4) or **C167971** FNR5040S220MT (1.8 A, 5×5) | E | 6,106 / 24,474 |
| R4 | C23150 (over-committed) | **C137735** RC0603FR-07390KL | E | 15,940 |
| C21 | C52923 | **C15849** (existing line) | B | 6.3 M |
| C64 | C23733 | **C19666** 4.7 µF 16 V 0603 | B | 2.79 M |
