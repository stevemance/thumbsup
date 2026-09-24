# Review round 3-B: sensor chain (rev C), DRV8316C block, rev C BOM delta

Scope: J2/J3 sensor chain (R54–R59, R110–R117, C110–C116, U9–U12, C45–C50, R52/R53, C72/C73, D7/D8), U3/U4
after the C307/C407 change and the DESIGN §8 DRV8316C register sequence, plus every part added or changed in
rev C (review/CHANGES.md, round 2 table).  No design file was edited.

Method:
- `design/motor_board.py` was run on a copy in /tmp (`201 refs (180 placed components), 150 nets, 56 BOM lines`,
  `checks: OK`).  The regenerated bom.csv, nets.md, netlist.csv and mcu_pinmap.md are byte-identical to the
  committed files.
- LCSC product-detail JSON and the JLC `selectSmtComponentList/v2` API were queried one request at a time with
  2 s gaps (script and raw output in /tmp/r3b/, 2026-09-23).
- Datasheets: **[C]** DRV8316C SLVSH07; **[TPS]** TPS22945 SLVS832D; **[LVC]** SN74LVC3G17 SCES470F; **[ST]**
  STM32G474 DS12288 Rev 4; **[HYG]** HYG015N04LS1C2 V1.0.  Two were downloaded from the LCSC `pdfUrl` for this
  review (not in `datasheets/`): **[NX]** Nexperia BAT54S product data sheet, 1 July 2022 (C47546), and **[CJ]**
  JSCJ B5817W–B5819W, rev D Mar 2015 (C8598).
- SPICE: `spice/sim_hotplug.py` was re-run unmodified from a wrapper (/tmp/r3b/leak.py) that adds a resistor
  across D6 to model reverse leakage.

## Findings

| ID | Sev | Refdes / net | What is wrong | Evidence | Proposed fix |
|---|---|---|---|---|---|
| R3B-01 | MINOR | D7/D8 BAT54S on L_MTEMP/R_MTEMP | **The Schottky clamp's leakage biases the motor-NTC reading when the board is hot, and it biases toward "colder".** The node source resistance is 10k ‖ (2.2k + R_NTC): 2.2 kΩ at a 120 °C motor and 5.5 kΩ at 25 °C.  The sensitivity at 120 °C is only 2.83 mV/K.  The BAT54's typical I<sub>R</sub> at 85 °C is about 20–30 µA at 0.5–3 V, against about 0.3 µA at 25 °C.  The two diodes of the pair leak in opposite directions, so the typical net current is small.  With the upper diode more reverse-biased at a hot motor, it is +2.8 µA, which reads the motor **2.2 K colder** at a 120 °C motor with the board at 85 °C.  With no cancellation, one diode's leakage alone gives up to **18.7 K** at 120 °C and 12 K at 100 °C.  At a 60 °C board the figures are 0.4 K typical and ≤ 3.3 K bound.  All leakage values are typical-curve readings (no max is given above 25 °C), so the bound is UNVERIFIED.  The error is small in normal use, but it points the unsafe way, and the part also costs an Extended fee | [NX] Table 7 "IR VR = 25 V … max 2 µA (25 °C)"; Fig. 2 typical IR: 85 °C ≈ 20 µA at 1 V, 125 °C ≈ 200 µA; calculation in this review (B3380 10k NTC, 10k 1 % pull-up, 12-bit at 3.3 V) | Change D7/D8 to **Nexperia BAV99,215, C2500**: JLC **Basic**, 1.07 M in stock, SOT-23 with the **same pinout** as the BAT54S (1 = A1, 2 = K2, 3 = K1/A2).  It is a silicon pair with 0.5 µA max at 80 V, so its leakage is negligible at these temperatures.  The fault clamp rises to ≈ 3.3 + 0.75 V = 4.05 V at 6 mA, and PF0/PF1 are FT (abs max VDD + 4 = 7.3 V), so that is fine.  This also removes one Extended line |
| R3B-02 | MINOR | D6 B5819W (VBAT → RPP_G), C13; DESIGN §1/§4/§5 "5 A inrush", "0.06–0.08 V/µs" | **D6's reverse leakage adds to the gate charging current and cancels part of the inrush limiting.**  D6 sits reverse-biased by ≈ 16 V across the gate network during the plug-in ramp, in parallel with R1 (≈ 150 µA).  JSCJ specifies I<sub>R</sub> ≤ **1 mA** at 40 V, 25 °C, and a 1 A Schottky's leakage grows roughly 10× from 25 to 100 °C.  The hot-plug simulation was re-run with a leakage resistor across D6.  None: 5.1 A.  100 kΩ (0.16 mA): 9.4 A.  33 kΩ: 17 A.  16 kΩ (≈ 1 mA): **27 A nominal / 23 A stiff-pack cold-C1**.  The peak VM dV/dt the script reports did not change (0.064–0.079 V/µs); only the peak current, and with it the ramp, did.  The DRV8316's 4 V/µs limit is still met with ≥ 50× margin.  Q8's peak linear-mode power rises from ≈ 85 W to ≈ 450 W for ≈ 0.2 ms.  By eye that is between the 100 µs and 1 ms lines of the [HYG] Fig. 3 SOA (UNVERIFIED; Tc = 25 °C chart).  C13 (0402 50 V X7R) also sees up to 16.8 V at plug-in and loses some capacitance, which speeds the Miller ramp too (UNVERIFIED, no curve).  The documented "5 A" is the ideal-diode figure | [CJ] "IR VR=40V B5819W max 1 mA" (Ta = 25 °C); `spice/sim_hotplug.py` model `dsch d(is=1e-6 …)` has no reverse leakage; /tmp/r3b/leak.py output | Change D6 to **1N4148W, C81598** (JLC Basic, SOD-123, **same footprint**, 75 V, I<sub>R</sub> 1 µA at 75 V).  The gate discharge needs only µA, so VF does not matter.  D5 stays B5819W, because it runs at ≈ 0 V reverse bias.  Optionally add the leakage case to sim_hotplug.py |
| R3B-03 | MINOR | DESIGN §8 CTRL3 = 0x4F (OTW_REP = 1) with L_nFAULT → TIM8_BKIN and R_nFAULT → EXTI → DRV_OFF | **A thermal *warning* hard-stops the drives, so the MCU gets no chance to derate.**  With OTW_REP = 1, nFAULT goes low at T<sub>OTW</sub> (135 °C min) while the DRV8316C keeps driving.  On this board that low is a TIM8 hardware break on the left channel (the low sides come on, so the motor brakes).  On the right channel it raises DRV_OFF, and DRV_OFF is **shared**, so a warning on U4 turns off both drives.  Round 2 B-02 asked for OTW reporting so that the MCU could derate before OTSD (165 °C).  Over nFAULT, the warning instead costs about 30 °C of usable headroom and stops the robot | [C] Table 8-8 row OTW: "OTW_REP = 1b: nFAULT; Active / Active; recovery TJ < TOTW – TOTW_HYS"; §7.5 TOTW 135/145/155 °C; DESIGN §3.3 DRVOFF/nFAULT rows, §8 STM32 row | Write **CTRL3 = 0x4E (frame 0x0A4E)**: OVP 22 V, SPI_FLT_REP = 1, OTW_REP = 0.  Read STAT1.OTW / IC_STAT.OT in the existing ~100 Hz SPI supervision and derate from there.  Update DESIGN §8 and §4 ("OTW reporting on") |
| R3B-04 | MINOR | DESIGN §8 sequence ending in CTRL1 = 0x0606 (REG_LOCK); §3.3 "nSLEEP → +3V3 (fault clear via SPI CLR_FLT)" | Once REG_LOCK = 110b is set, the datasheet says writes are ignored "except to these bits and address 0x03h bits 2-0", which as written includes CTRL2.CLR_FLT.  OCP is kept **latched** (CTRL4 = 0x10), and nSLEEP is tied high.  After an OCP event, a plain CLR_FLT write would therefore be ignored, and the drive would stay Hi-Z until a power cycle.  §8 does not describe any runtime fault-clear sequence.  Whether the W1C CLR_FLT bit is exempt from the lock is not stated (UNVERIFIED) | [C] Table 8-18 REG_LOCK "6h = … lock the settings by ignoring further register writes except to these bits and address 0x03h bits 2-0"; Table 8-21 OCP_MODE 0h latched | Add to §8: **runtime fault clear = CTRL1 0x0603 → CTRL2 0x097D → CTRL1 0x0606**, then read IC_STAT back.  Check it at bring-up by forcing a fault |
| R3B-05 | MINOR | BOM.md "Extended-part lines … U1–U12 (**10 lines**)" | bom.csv has **9** U lines: U1, U2, U3/U4, U5, U6, U7, U8, U9/U10, U11/U12.  The live classes give **22 Extended**, 4 Preferred and 30 Basic lines.  The Extended list is otherwise correct: C4–C8 and D5/D6 are now Basic, and D7/D8 are Extended (see the table below) | bom.csv; JLC `componentLibraryType` for every rev-C C-number | "U1–U12 (9 lines)", and state the total: 22 Extended lines (it becomes 21 with R3B-01) |
| R3B-06 | MINOR | `datasheets/README.md` | The index is stale for rev C.  It lists "BAT54WS_Diodes.pdf — VC0 clamp **D5**", but D5 is now B5819W and BAT54WS is no longer on the board.  There is **no BAT54S or B5819W datasheet** in `datasheets/`, and the package claims "PDFs of every non-generic part".  The HYG015N04LS1C2 row says "Q1–Q6, … Q7" and omits Q8 | `ls datasheets/`; README rows 17, 24 | Add the Nexperia BAT54S (or BAV99, per R3B-01) and JSCJ B5819W PDFs (LCSC pdfUrl for C47546 / C8598), mark BAT54WS as unused, and add Q8 |

### NOTES

| ID | Sev | Item | Note | Evidence |
|---|---|---|---|---|
| N3-1 | NOTE | R113/R117 2.2k **0402** in a phase-to-TEMP short | A drive phase shorted to the TEMP wire at 16.8 V and high duty puts (16.8 − 3.7)² / 2.2k ≈ **78 mW** into R113; at the 88 % duty cap that is ≈ 69 mW, and at the 22 V OVP level ≈ 150 mW.  The 0402 is rated 62.5 mW.  It is a sustained overload but survivable short-term.  If it fails, it fails open and reads as an open NTC (3.3 V), which is benign and detectable.  Optional: use a 2.2k 0603 | C25879 "62.5 mW"; the netlist comment says 6 mA |
| N3-2 | NOTE | C110–C116 value (100 pF, DNP) | The coupled glitch lands on the connector-side node, which recovers through 4.7k × (cable ≈ 50 pF) ≈ 0.24 µs.  A 1k × 100 pF = 100 ns filter behind it only partly attenuates such a pulse.  For Halls, 1 nF (τ = 1 µs, the round-2 suggestion) or the timer filter ICxF (≥ 1 µs for Halls, DESIGN §8) is what actually rejects it.  For MT6701 ABZ leave them off, as documented.  The cable capacitance is an estimate | round 2 B-04; DESIGN §3.3 |
| N3-3 | NOTE | VS hard short vs +3V3 (3.3 V jumper) | TI's own scope shot shows a hard short drawing **≈ 1.8 A peak** that decays to the limit within ≈ 2 µs, with C<sub>IN</sub> = 10 µF; that is ≈ 2 µC.  Here C45 is ≈ 3.5–4 µF effective at 3.3 V, backed by ≈ 10–14 µF on the +3V3 plane (C48, C64, C70, 20 × 100 nF, C66 via R60).  Expect a local dip of ≈ 0.2–0.5 V for about 1–2 µs (estimate).  That is far shorter than the DRV8316C nSLEEP t<sub>RST</sub> of 20 µs.  §8 says "BOR level raised" without a number: BOR level 4 (≈ 2.8 V) is the only setting a dip could reach, so **use BOR level ≤ 3**.  Keep the §9 scope test.  With the 5 V jumper, the dip falls on +5V (44 µF), and +3V3 sits behind the LDO | [TPS] Fig. 24 (400 mA/div, 10 µs/div), 7.6 "hard short 4 µs"; [C] 7.5 tRST |
| N3-4 | NOTE | R6 (0402, 100 Ω) in the balance-lead hot-plug path | With the main switch open, VBAT floats and Q7/Q8 are off, and their back-to-back body diodes block both ways.  C9's charging current at balance-lead plug-in therefore returns BAL4 → R11 → C9 → GND → D5/C8 → CELL0 → **R6** → BAL0.  R6 carries the same pulse as R11, which was upsized to 0603 for it: ≈ 0.7 W peak each, τ ≈ 0.6 ms.  R6's 0402 pulse rating was not checked (UNVERIFIED).  An 0603 for R6 matches the R11 reasoning | netlist BMS_BAT / CELL0; DESIGN §3.1 "U8's supply current returns … only through VC0" |
| N3-5 | NOTE | DNP handling | bom.csv correctly omits C110–C112 and C114–C116 (qty sum 174 = 180 placed − 6 DNP).  When the KiCad schematic is drawn, give them the DNP / "exclude from position files" attributes as well.  Otherwise JLC's CPL lists designators that are missing from the BOM, and the order gets queried | `design/motor_board.py` groups loop skips `p["dnp"]` |

## Rev C BOM delta (live 2026-09-23)

| Refs (net, max V) | C-no | LCSC/JLC record | Pkg vs footprint | Rating vs net | Derating (estimate) | JLC stock / presale | Class | Verdict |
|---|---|---|---|---|---|---|---|---|
| Q8 (D GND, S RPP_S; ≤ 16.8 V, 32.4 V TVS) | C2874970 | HUAYI HYG015N04LS1C2, PDFN5x6-8L, 40 V, ±20 V Vgs | PQFN-8-EP 6×5 ✔ (same as Q1–Q7) | 40 V ✔; Vgs ≤ 12 V (D4) ✔ | — | 17,261 / 17,134 | E (shares the Q line, no extra fee) | OK (see R3B-02 on the ramp current) |
| C12 (RPP_G–RPP_S, ≤ 12 V) | C21120 | Samsung CL10B224KA8NNNC, 0603, 220 nF X7R ±10 % 25 V | 0603 ✔ | 25 V vs 12 V ✔ | ≈ −5 % at the 3 V plateau, ≈ −30 % at 12 V (after turn-on, irrelevant) | 829,934 / 720,952 | B | OK |
| C13 (RPP_G–GND, ≤ 16.8 V at plug-in, ≤ 32 V TVS) | C15195 | Samsung CL05B103KB5NNNC, 0402, 10 nF X7R 50 V | 0402 ✔ | 50 V ✔ | some loss at 16.8 V (UNVERIFIED); speeds the ramp, R3B-02 | 4,439,357 / 3,692,232 | B | OK |
| D5 (CELL0, ≈ 0 V reverse), D6 (VBAT–RPP_G, ≤ 20 V reverse) | C8598 | JSCJ B5819W SL, SOD-123, 40 V 1 A, IR ≤ 1 mA @ 40 V | D_SOD-123 ✔ (pad 1 = K: D5 K = CELL0, D6 K = VBAT ✔) | 40 V ✔ | — | 466,565 / 390,400 | B | D5 OK; D6: R3B-02 |
| D7, D8 (MTEMP, 0…3.3 V) | C47546 | Nexperia BAT54S,215, SOT-23, 30 V 200 mA, IR 2 µA @ 25 V | SOT-23 ✔; pins 1 A1 = GND, 2 K2 = +3V3, 3 K1/A2 = MTEMP ✔ ([NX] Table 2) | 30 V ✔; 6–13 mA fault vs 200 mA ✔ | — | 136,407 / 135,159 | E | R3B-01 |
| R110–R112, R114–R116 (sensor lines) | C11702 | UNI-ROYAL 0402WGF1001TCE, 1 kΩ 1 % 62.5 mW | 0402 ✔ | ✔ (≤ 5 V across in a fault) | — | 8,820,648 / 6,784,156 | B | OK (shares the R62 line) |
| R113, R117 (TEMPJ–MTEMP) | C25879 | UNI-ROYAL 0402WGF2201TCE, 2.2 kΩ **1 %** 100 ppm 62.5 mW | 0402 ✔ | fault power: N3-1 | — | 1,207,361 / 910,512 | B | OK |
| C110–C112, C114–C116 (DNP) | C1546 | FH 0402CG101J500NT, 100 pF C0G 50 V | 0402 ✔ | ✔ | C0G | 3,561,174 / 3,145,521 | B | OK; absent from bom.csv ✔ |
| C9 (BMS_BAT 16.8 V) | C29823 | FH 1206B475K500NT, 4.7 µF X7R ±10 % 50 V | 1206 ✔ | 50 V ✔ | ≈ 2.1–2.8 µF at 16.8 V, worst ≈ 1.6 µF ≥ BQ76907 1 µF ✔ (UNVERIFIED curve) | 649,703 / 565,825 | B | OK |
| C11 (BMS_REG 3.3 V), C45/C48 (VSRC 3.3 or 5.05 V) | C19666 | Samsung CL10A475KO8NNNC, 4.7 µF X5R 16 V 0603 | 0603 ✔ | 16 V ✔ | ≈ 3.5 µF at 3.3 V, ≈ 2.6 µF at 5 V; > C46/C49 effective (≈ 0.75 / 0.5 µF) ✔ | 2,789,386 / 2,317,143 | B | OK |
| C4–C8 (cell diff ≤ 4.2 V; ≤ 16.8 V with a floating tap) | C21120 | as C12 | 0603 ✔ | 25 V ✔ | ≈ 200 nF | — | B | OK (round 2 m3 fix is correct) |
| R11 (BAL4–BMS_BAT) | C22775 | UNI-ROYAL 0603WAF1000T5E, 100 Ω 1 % 100 mW 75 V | 0603 ✔ | ✔ | pulse: see N3-4 for R6 | 12,552,418 / 11,147,222 | B | OK |
| C307/C407 (FB_BK ≤ 3.5 V) | C45783 | Samsung CL21A226MAQNNNE, 22 µF X5R ±20 % 25 V 0805 | C_0805 ✔ | 25 V ≥ TI "≥ 10 V" ✔ | ≈ 15–18 µF at 3.3 V | 4,302,639 / 3,690,821 | B | OK |
| R12 (INA_nCS pull-up) | C25741 | UNI-ROYAL 0402WGF1003TCE, 100 kΩ 1 % | 0402 ✔ | ✔ | — | 9,088,461 / 7,921,498 | B | OK |
| C74 (U1 VBAT pin 1, +3V3) | C1525 | Samsung CL05B104KO5NNNC, 100 nF X7R 16 V 0402 | 0402 ✔ | ✔ | — | 25,345,554 / 20,178,579 | B | OK |

Every rev-C C-number resolves at LCSC and JLC, every MPN matches its Comment, and every package matches its
footprint.  All stock is ≥ 136 k, so there is no line-quantity issue for 5 boards.

## VERIFIED OK

1. **BAT54S pinout** ([NX] Table 2): 1 = A1, 2 = K2, 3 = K1/A2.  The netlist has 1 = GND, 2 = +3V3, 3 = MTEMP, which clamps
   MTEMP to [−VF, 3.3 V + VF].  This matches KiCad `Package_TO_SOT_SMD:SOT-23` pad numbering.
2. **NTC resolution and 2.2k error** (10k B3380, 10k 1 % pull-up, 12-bit at 3.3 V):

   | Motor °C | R_NTC | V_node | mV/K (2.2k) | LSB/K | mV/K (no 2.2k) | 2.2k ±1 % error |
   |---|---|---|---|---|---|---|
   | −20 | 75.0 k | 2.92 V | 17.2 | 21 | 18.1 | 0.01 K |
   | 25 | 10.0 k | 1.81 V | 25.5 | 32 | 31.4 | 0.06 K |
   | 80 | 1.71 k | 0.93 V | 7.9 | 9.8 | 11.2 | 0.47 K |
   | 100 | 1.02 k | 0.81 V | 4.7 | 5.8 | 6.8 | 0.88 K |
   | 120 | 646 Ω | 0.73 V | 2.8 | 3.5 | 4.1 | 1.55 K |

   At the hot end the 2.2k costs about 30 % of the sensitivity, which still leaves ≥ 3.5 LSB/K.  The tolerance error after
   the firmware subtracts 2.2 kΩ is ≤ 1.6 K.  The source impedance (≤ 8.9 kΩ) behind 100 nF is fine for the slow ADC
   channels.  An open NTC reads 3.3 V and a shorted one reads 0.60 V (the 2.2k keeps a short from reading 0 V), and
   both are distinguishable from the valid range.  Clamp leakage: R3B-01.
3. **Phase-to-TEMP fault**: (16.8 − 3.6)/2.2k = 6 mA (13 mA at the TVS clamp) into the upper BAT54S diode, far below
   200 mA, and 12 mA of back-feed into +3V3 against a ~120 mA load.  PF0/PF1 see ≤ 3.7 V (FT, abs max 7.3 V; no
   positive injection on FT pins, [ST] Table 14/15).
4. **1k series + buffer input, edge rate**: C<sub>I</sub> = 4 pF typ ([LVC] 6.5) plus about 2 pF of pad and trace gives
   τ ≈ 6 ns, a 10–90 % rise of about 13 ns and ≈ 4 ns extra delay.  The MT6701 worst-case edge spacing is 267 ns at
   55 krpm × 1024 PPR × 4, so the effect is negligible.  With the 100 pF fitted, τ is 100 ns, which is too slow for
   fast ABZ, as DESIGN says.
5. **1k series with a 5 V push-pull sensor and the 4.7k to +3V3**: the pull-up sits on the connector side, so the 1k
   carries only the buffer's input leakage (≤ ±5 µA, ≤ 5 mV).  The inputs tolerate 5.5 V at any VCC ([LVC] ROC).  The
   back-current into +3V3 is still (5.16 − 3.3)/4.7k = 0.4 mA per line.  Nothing adverse.
6. **TPS22945 with 4.7 µF on VIN, 5 V jumper**: VIN = +5V (4.93–5.16 V ≤ 5.5 V ROC).  C<sub>IN</sub> is ≈ 2.6 µF
   effective against C<sub>OUT</sub> ≈ 0.5 µF, which meets TI's "C<sub>IN</sub> > C<sub>OUT</sub>" ([TPS] §9.1.5).
   The extra capacitance on the +5V buck output (44 µF) and on the AP2112K output is harmless.  C<sub>OUT</sub>(max) =
   0.1 A × 5 ms / 5.5 V = 91 µF, far above the ~1.5 µF present.
7. **DRV8316C block after C307/C407**: CBK is 22 µF 25 V X5R 0805, which satisfies [C] Table 8-1 "X5R or X7R, 22-µF,
   ≥ 10-V" and §9.2.1.1.5 ("22-Ω for RBK and a 10-V rated, 22-µF capacitor").  The KiCad footprint is `C_0805` ✔.
   Nothing else in the U3/U4 block changed in rev C.  The pinout and the other passives were verified in round 2.
8. **DESIGN §8 register table vs [C] §8.6**: the addresses are CTRL1 3h, CTRL2 4h, CTRL3 5h, CTRL4 6h, CTRL5 7h,
   CTRL6 8h, CTRL10 Ch, IC_STAT 0h, STAT1 1h and STAT2 2h ✔.  Field values: CTRL2 0x7C = reserved 01b + SDO_MODE 1 +
   SLEW 11b (200 V/µs) + PWM_MODE 10b (3x) ✔; CTRL3 0x4F = reserved 1 + OVP_SEL 1 (22 V) + OVP_EN + SPI_FLT_REP +
   OTW_REP ✔ (but see R3B-03); CTRL4 reset 0x10 = OCP_DEG 0.6 µs, 16 A, latched ✔; CTRL5 reset 0x00 = 0.15 V/A ✔;
   CTRL6 0x19 = BUCK_PS_DIS + BUCK_CL 150 mA + BUCK_SEL 3.3 V + BUCK_DIS ✔; CTRL10 0x15 = DLYCMP_EN + DLY_TARGET 1.2 µs ✔;
   REG_LOCK 011b / 110b ✔.
9. **SPI frames and parity** (B15 W0, B14–B9 address, B8 parity making the word's 1-count even, [C] §8.5.1.1),
   recomputed: 0x0603, 0x1019, 0x0B4F, 0x0D10, 0x1915, 0x087C, 0x097D, 0x0606, and the reads 0x8100 / 0x8200 / 0x8400 /
   0x8800 / 0x9000 / 0x9900 all match DESIGN and round 2.  The fix frame for R3B-03 is CTRL3 0x4E → **0x0A4E**.
10. **D5/D6 orientation**: SOD-123 pad 1 = K.  D5 has K = CELL0 and A = GND (clamps VC0 ≥ −VF).  D6 has K = VBAT and
    A = RPP_G (discharges the gate into a collapsing VBAT).  D5's leakage at ≈ 0 V reverse bias is negligible for the cell-1 reading.
11. **DNP handling in bom.csv**: C110–C112 and C114–C116 are absent, the Qty column sums to 174, and there are 56 lines.
    The totals in the BOM.md header and the DESIGN §1 table (174 + 6 DNP, 56 lines) match.
12. **BOM.md class statements for the rev-C parts**: C4–C8 now Basic ✔, D5/D6 Basic ✔, D7/D8 Extended 136k ✔, Q8 on the
    Q line ✔, and the Preferred list (R20; R22/R24/R26/R63; R45; R46) is correct.  The only error is the U-line count
    (R3B-05).
13. **Generated files are current**: regenerating from motor_board.py reproduces the committed outputs byte for byte.

**Verdict: 0 BLOCKER, 0 MAJOR, 6 MINOR (R3B-01…06), 5 NOTE.**
