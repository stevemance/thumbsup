# Round 12 (b): mechanical audit of rev K (after the round-11 fixes)

Auditor: adversarial netlist and documentation audit, 2026-09-24.  I edited no design file.  The regeneration
ran on a copy in `/tmp/r12/motor_board`.  Out of scope: board area, chassis fit and prose style.

## Method and raw results

| Step | What I ran or read | Result |
|---|---|---|
| Netlist | `python3 design/motor_board.py` (copy) | Printed `237 refs (205 placed components), 160 nets, 67 BOM lines`, `checks: OK`.  netlist.csv, nets.md, bom.csv and mcu_pinmap.md regenerate **byte-identical** to the working tree |
| Delta since round 11 | diff against the round-11 snapshot (`/tmp/r11/design`) | Netlist: only **C19** 1 nF 50 V 0402 (C1523) was added, W_nFAULT–GND.  Text changed in the R302/R402 desc, the mcu_pinmap NRST/BOOT0 labels, and calcs.py §7/§9/§11 |
| BOM | bom.csv | 67 lines.  Qty sum = designator count = **199**.  The 6 DNP parts (C110–C112, C114–C116) are excluded, and 205 − 6 = 199.  67 unique LCSC numbers, each with one footprint.  DESIGN §1, BOM.md and README all say 199 / 67 / 6 DNP |
| Footprints | every standard footprint parsed from `/usr/share/kicad/footprints`; each footprint's pad names compared with the netlist pins of every ref that uses it | All 33 standard footprints exist and pads = pins.  The 4 `thumbsup:` footprints are all listed in DESIGN §6.12 |
| Package vs footprint | by hand | Every IC, diode, FET, L1, C1, J4 and R302/R402 matches its package (DCU = VSSOP-8 2.3×2, DDF = SOT-23-8, DGS = MSOP-10, RGR = QFN-20 3.5×3.5, SE = SOT-353, etc.) |
| MCU | ST XML dump (every ADC/COMP/OPAMP/DAC/TIMx/SPI3/USART1/UCPD signal per pin) vs MCU_PINS, DESIGN §3.2–§3.4, §8 and the ADC table | All correct.  Weapon CSAs: PA0 COMP3_INP + ADC1_IN1/ADC2_IN1, PA1 COMP1_INP, PB11 COMP6_INP + ADC1_IN14.  The other analog pins: PA2 ADC1_IN3, PA3 ADC1_IN4, PA4 ADC2_IN17, PA5 ADC2_IN13, PA6 ADC2_IN3, PB1 ADC3_IN1, PB12 ADC4_IN3, PB13 ADC3_IN5, PA8/PA9 ADC5_IN1/IN2, PC3 OPAMP5_VINP, PF0/PF1 ADC1_IN10/ADC2_IN10.  Timers and buses: PC13 TIM1_BKIN, PB7 TIM8_BKIN, PA7/PB14/PB15 TIM1_CH1N–3N, TIM8 on PB6/PC7/PB9, TIM20 on PB2/PC2/PC8, TIM3/TIM2 inputs, SPI3 on PC10–12, USART1 on PC4/PC5.  The analog-input count is 16, as DESIGN §1 says |
| IC pins | pdftotext of the datasheets | Re-verified against the datasheet pin tables and all correct: <br>• U2 DRV8323RH (SLVSDJ3D Table 6-4, 49/49) <br>• U3/U4 DRV8316CR (SLVSH07 Table 6-1, 41/41) <br>• U13 LM74502 (8/8) <br>• U7 INA239 (10/10) <br>• U8 BQ76907 (21/21) <br>The other small parts have not changed since round 11, which checked them |
| DRV8316 SPI words | address / data / even parity decoded for all nine frames in §8 | All correct: CTRL1 0x0603 and 0x0606; CTRL6 0x1019; CTRL3 0x0A4E; CTRL4 0x0D10; CTRL5 0x0F00; CTRL10 0x1818; CTRL2 0x087C and 0x097D |
| Derived numbers | RC constants and dividers recomputed | All correct: <br>• Time constants: C18 1.3 ms, C68 0.87 ms, C10 4.5 ms, C16 103 ms, R32 22 ms, C19 10 µs, R302 1.6 µs (corner 99 kHz), cell taps 22 µs, C2 80 kHz. <br>• Dividers: FB 5.05 V; VBAT_SNS 2.15 V at 16.8 V (÷7.8, 25.7 V max). <br>• INA239 registers: SOVL 0x76C0 = 38 A, BOVL 0x17C0 = 19.0 V, SHUNT_CAL 0x1000. <br>• Timers: ARR 3542/1771 → 24/48 kHz; BRR 85 → 2 Mbaud |
| Round-11 fixes | each CHANGES round-11 row checked against the files | Every row is present **except** the two below (F1, F2): the sim figures in DESIGN and the Q7 text in calcs |
| Sims | `spice/hotplug.out` and `arm.out` compared with every quoted figure | See F1.  arm.out matches DESIGN §1, §3.2, §3.5, §5 and §9 |
| JLC (live, 2026-09-24) | the JLC `selectSmtComponentList/v2` API, run for the most critical lines | All seven match their MPN and class: <br>• C521608 STM32G474RET6, 205 in stock <br>• C543035 DRV8323RHRGZR, 203 in stock <br>• C5447274 DRV8316CRRGFR, 2,923 in stock <br>• C2876522 INA239AIDGSR, 101 in stock <br>• C25466 UNI-ROYAL 25121WF100LT4E, Extended <br>• C1523 0402 1 nF 50 V X7R, Basic <br>• C167971 FNR5040S220MT: its maker is **cjiang** (see F4) <br>The other 60 lines are unchanged since round 11's full lookup |
| Datasheet index | files vs datasheets/README.md | 35 PDFs and 35 rows, matching one to one (UNIROYAL_2512_thick_film.pdf is new) |

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R12B-01 | MINOR | DESIGN.md:109 (§3.1 R15 row), DESIGN.md:426 (§5 hotplug row), DESIGN.md:504 (§7.2) | **The sim figures predate the rerun.**  sim_hotplug.py was rerun in round 11 with the real capacitor placement (R11B-N04), and hotplug.out now holds the new results.  The DESIGN text still quotes the old run: <br>• "2.06 V/µs worst" (§3.1). <br>• "1.8–2.06 V/µs" (§5). <br>• "0.8–2.25 V/µs … 2.65 V/µs" (§5, §7.2). <br>The committed output says **1.833–2.092**, **0.801–2.258** and **2.662**.  A reader who checks the quoted "worst" against hotplug.out finds it exceeded.  Every conclusion still holds: "≤ 2.1" / "≤ 2.75 V/µs" and the 4 V/µs limit.  The "≤ 2.1" (§7.2, §7.5) and "2.1" (R302 desc) wordings are fine | hotplug.out: the "off 400 ms … min UVLO" row gives 2.092; the "0.8 ms … 0 C C1 100 mOhm" row gives 2.258; the "-40 C limit" row gives 2.662 | §3.1 "2.09 V/µs worst"; §5 "1.8–2.09", "0.8–2.26", "2.66"; §7.2 "≤ 2.26 … 2.66" |
| R12B-02 | MINOR | design/calcs.py:153 → calcs.md:109; DESIGN.md:386 (§4), DESIGN.md:109 (§3.1) | **Q7 and bus figures disagree between calcs and DESIGN.**  CHANGES round 11 lists "Q7 22.0 W, 54–57 mJ" as done, and R11B-N01 asked for the calcs.py text too.  Three mismatches remain: <br>• calcs.md still says "Q7 16 W peak (**21.5 W** at the max gate current) / **54 mJ**".  DESIGN §4, which names calcs.md as its source, says 22.0 W; §5 says 54–57 mJ; hotplug.out gives 22.0 W and 53.8–56.9 mJ. <br>• The bus-decay τ also split in round 11: calcs.md:111 says "~374 µF, τ ~2.3 s", but DESIGN §3.1 still says "**τ ≈ 2.4 s**". <br>• "~380 µF" (calcs.md:109, DESIGN §3.1, the motor_board.py C13 desc) vs "~374 µF" (calcs.md:111) is only a rounding difference | calcs.md:109, :111; DESIGN.md:109, :386, :426; hotplug.out close rows | calcs.py:153 → "16.5 W peak (22.0 W …) / 54–57 mJ"; DESIGN §3.1 → "τ ≈ 2.3 s" |
| R12B-03 | MINOR | DESIGN.md:9; review/CHANGES.md "Round 11" heading; README.md:6 | **The netlist changed in round 11 without a revision label.**  C19 was added (198 → 199 parts, 236 → 237 refs), but the package is still called "rev K", the same name as the round-10 package that round 11 audited. <br>• DESIGN's revision line ends at "rev K round 10". <br>• CHANGES' Round 11 heading has no "→ rev" label. <br>• README says "after **ten** adversarial review rounds". <br>Someone who started drawing from the round-10 rev K has nothing that tells them to add C19 | diff of /tmp/r11/design/netlist.csv vs design/netlist.csv (only the two C19 rows) | Label it rev L (or "rev K.1"), add "rev L round 11" to DESIGN:9 and the CHANGES heading, and change README to "eleven" |
| R12B-N01 | NOTE | BOM.md:27; design/motor_board.py:76 (LCSC comment) | L1 is called "**Fenghua** FNR5040S220MT".  JLC lists C167971 as **cjiang (Changjiang Microelectronics Tech)** FNR5040S220MT, which matches the datasheet file name `FNR5040S_CJiang.pdf` and the KiCad footprint `L_Changjiang_FNR5040S`.  The LCSC number and MPN are correct; only the maker name is wrong | live JLC lookup (above) | "Changjiang (cjiang) FNR5040S220MT" |
| R12B-N02 | NOTE | design/motor_board.py:377 (DNP C110–C116 value "1nF") vs :264/:233 ("1nF 50V", same C1523) | The DNP filter caps use the value string "1nF", while C19 and C41–C43 use "1nF 50V" with the same LCSC number.  The BOM groups parts by value, so un-DNPing them (for Hall sensors) would give a 68th line that repeats C1523 | motor_board.py `two(f"C{sr + k}", "1nF", …)` | Use "1nF 50V" |
| R12B-N03 | NOTE | design/motor_board.py:296 (R302/R402 desc); DESIGN.md:207, :548 | "loaded contact bounce 3.75 → **2.2** V/µs".  The worst case at the 0 °C bound is now 2.258 V/µs, and §5 says 2.25.  Rounding it down to 2.2 is the one place where the figure reads as better than the output | hotplug.out | "→ ~2.3 V/µs" (or 2.26) |
| R12B-N04 | NOTE (firmware naming) | DESIGN.md:605 (§8 STM32 row) | "OPAMPINTEN = 1 **before** OPAMPEN".  In RM0440 the OPAMPx_CSR bit is **OPAINTOEN**, and the enable bit is OPAEN.  The intent is right; the names cannot be searched for as written | RM0440 OPAMPx_CSR | "OPAINTOEN = 1 before OPAEN" |

These items are settled and I did not re-raise them:
* R11B-N11: the script cannot detect an omitted pin.  I re-checked by hand and every pad set matches.
* The DRV8316 SDO needs a pull-up only until it is configured (§8).
* L1 Isat (round 2).

**Checked and correct:**

**Rev K content:**
* L_VM and R_VM each carry R302/R402.2, C300/C301/C302/C308/C309/C310 and C303.2, plus U3/U4 pins 9–11.
* VBAT has nothing left over from the DRV8316s.

**C19:**
* Netlist, BOM line, DESIGN §3.2 and the CHANGES R11D row agree.
* Round 11 said to set the filter by BKF = 0.  The C19 design gives the same result.

**Round-11 changes that landed:**
* R302/R402 loss is 0.11/0.24/0.52 W everywhere (motor_board.py, DESIGN §3.3, calcs §7).
* The heat budget includes R302/R402: 0.29 W average, ~4.1 W total, and DESIGN §4 says the same.
* The slew limit reads "≤ 2.75 V/µs", scoped to switch/bounce events (DESIGN §1, calcs §7).
* The fault-clear kick reads "~1–2 V/µs (review sims)" in all three places.
* §7.21 names the UniOhm datasheet and marks the pulse rating UNVERIFIED.
* §8 has the drive VM feed-forward row.
* mcu_pinmap labels NRST and BOOT0.
* The spice README and sim docstring describe the real capacitor placement.
* The passive count is "~20" (11 C + 3 R + 6 filter).

**Lists and counts:**
* TP1–TP12 match DESIGN §3.4 and §9.
* The J1 table matches the netlist.
* The DNP list is the same in DESIGN §3.3 and §9 and in BOM.md.
* The §7.15 fight-build list is complete.
* BOM.md class counts are right: 11 IC lines, 25 Extended, 4 Preferred.

**Verdict: 0 BLOCKER, 0 MAJOR, 3 MINOR, 4 NOTE.**  All 7 findings are documentation or labelling, not
wiring.  I found no connection, pin, footprint, AF or LCSC error.
