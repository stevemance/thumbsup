# Round 11 (b): mechanical audit of rev K

Auditor: adversarial netlist and documentation audit, 2026-09-24.  I did not edit any design file.  Everything that
regenerates output ran on copies:
* motor_board.py in `/tmp/r11/design`.
* calcs.py and both sims in `/tmp/r11/hw/motor_board`, with `hw/tools` symlinked so that the sims' `../../tools/spice`
  import resolves.

Out of scope: board area, chassis fit.  Firmware-contract wording appears only as NOTEs.

## Method and raw results

| Step | What was run or read | Result |
|---|---|---|
| Netlist | `python3 design/motor_board.py` (copy) | `236 refs (204 placed components), 160 nets, 67 BOM lines`, `checks: OK`.  netlist.csv, nets.md, bom.csv and mcu_pinmap.md regenerate **byte-identical** to the working tree |
| Calcs | `python3 design/calcs.py` (copy) | calcs.md is byte-identical |
| Sims | `sim_hotplug.py` 3.95 s, `sim_arm.py` 3.65 s (copy, hardware venv) | Both are identical to the committed `hotplug.out` and `arm.out` |
| Sim sensitivity | `sim_hotplug.py` copy with the rev K capacitor placement (N-04) | Every result moves by ≤ 2 %; the worst case is 2.66 V/µs |
| Datasheets | `pdftotext -layout` of all 34 PDFs; ST XML | Pin tables below.  The datasheets/README index matches the directory exactly (34 files) |
| Footprints | every standard footprint parsed from `/usr/share/kicad/footprints/*.pretty`; pad names compared with the netlist pin set of every ref | 33 standard footprints, all present, pads = pins.  4 thumbsup: footprints, all in §6.12 |
| JLC | `POST …/selectSmtComponentList/v2 {"keyword":"Cxxxx"}` for **all 67 BOM lines**, 2 s apart (method of review/r6_parts_lookup.md, round2_e_bom.md) | classes below |

### 1. Pins vs datasheets

| Part | Source | Result |
|---|---|---|
| U1 STM32G474RET6 | ST XML: the script checks name + AF; I dumped every ADC/COMP/OPAMP/DAC/UCPD signal separately; I/O types from the DS12288 pin table | OK.  PA0 ADC1_IN1/ADC2_IN1/COMP3_INP; PA1 ADC2_IN2/COMP1_INP; PB11 ADC1_IN14/COMP6_INP; PA2 ADC1_IN3 (COMP2_INM only); PA3 ADC1_IN4; PA4 ADC2_IN17 (DAC1_OUT1); PA5 ADC2_IN13; PA6 ADC2_IN3 (DAC2_OUT1); PB1 ADC3_IN1; PB12 ADC4_IN3; PB13 ADC3_IN5; PA8 ADC5_IN1 + OPAMP5_VOUT; PA9 ADC5_IN2; PC3 OPAMP5_VINP; PF0 ADC1_IN10; PF1 ADC2_IN10.  Each weapon CSA pin reaches exactly one COMPx_INP (PB1 is the other COMP1_INP option, selected by INPSEL).  UCPD1_CC1 = PB6, CC2 = PB4 (§8).  Timers, SPI3, USART1, SWD AFs: script OK.  I/O types: PA2 FT_a; PA4, PA5, PB11, PB0, PB10, PC5 TT_a; PD2, PC13 FT |
| U2 DRV8323RH (RGZ) | SLVSDJ3D Table 6-4 | 49/49 OK; pin 46 NC "can be left floating"; GAIN 32 open = 20 V/V |
| U3/U4 DRV8316CR (RGF) | SLVSH07 Table 6-1 | 41/41 OK; NC 1 and 24 "open".  VM 9/10/11 now on L_VM/R_VM; the datasheet's "CP: capacitor between CP and VM" is honoured (C303/C403 CP–L_VM/R_VM) |
| U5 AP2112K SOT-25 | DS39724 | 1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT: OK |
| U6 SN74LVC08A PW | SCAS283 | 14/14 OK; 4A/4B to GND, 4Y open |
| U7 INA239 | pin diagram | 1 CS, 2 MOSI, 3 ALERT, 4 MISO, 5 SCLK, 6 VS, 7 GND, 8 VBUS, 9 IN−, 10 IN+: OK |
| U8 BQ76907 | SLUSE96A Table 5-1 | 21/21 OK (4S: VC7–VC6, VC5–VC4, VC3–VC2, VC1–VC0; VC6=VC5, VC4=VC3, VC2=VC1) |
| U9/U10 SN74LVC3G17 DCU | SCES470 | 1A1 3Y2 2A3 GND4 2Y5 3A6 1Y7 VCC8: OK |
| U11/U12 TPS22945 DCK | SLVS832D | 1 VOUT, 2 GND, 3 OC, 4 ON ("do not leave floating": tied to VIN), 5 VIN: OK |
| U13 LM74502 DDF | SNOSDE5A Table 5-1 | 8/8 OK; OV to GND as directed; C14 100 nF VS–GND as directed |
| U14 74LVC1G17 SOT353 | DS35124 | 1 NC, 2 A, 3 GND, 4 Y, 5 VCC: OK |
| Q1–Q8 | HYG015N04LS1C2 on the KiCad PQFN-8-EP (pads 1–5) | 1–3 S, 4 G, 5 D: OK |
| D1, D2, D4, D5, D10, D3 (KiCad pad 1 = K) | datasheets | D1 K = VBAT; D2 K = BUCK_SW; D4 K = PSW_G, A = PSW_S; D5 K = CELL0, A = GND; D10 K = PSW_DV, A = PSW_RG (C13 can only absorb gate current); D3 K = GND.  All polarities correct |
| D7/D8 BAV99, D9 BAT54S | Nexperia Table 2 | 1 = A1, 2 = K2, 3 = K1/A2.  D7/D8 clamp GND→MTEMP→+3V3; D9 is the GND→ARM_AC clamp and the ARM_AC→W_ARM rectifier: OK |
| J1–J4, wire holes | DESIGN §3.5, §3.3, §3.1 | J1 20 pins = the §3.5 table.  J2/J3: 1 VS, 2 GND, 3–5 S1–S3, 6 TEMP, MP.  J4: 1 = B0 … 5 = B4.  J_BAT± and J_WA–J_WC are 1.5 mm²; J_LA–J_RC are 0.5 mm²: OK |

**NC pins (16):** all 16 are allowed to float:
* J1.7 and J1.18 (spare).
* U11.3 and U12.3 (OC open-drain flag).
* U13.3.
* U14.1.
* U2.32 (GAIN Hi-Z, the intended setting) and U2.46.
* U3.1/24 and U4.1/24.
* U5.4.
* U6.11 (output).
* U8.9 and U8.10 (TI: leave floating).

### 2. Nets

**Nets with one node:** none.  **Nets in total:** 160.

**Two-node nets (71), all intended.**  Round 10 said "73", but its own category list adds up to 71: that was a miscount, not a change.

| Group | Nets |
|---|---|
| Point-to-point control | W_INHA/B/C, W_INLA/B/C, L_/R_INHA/B/C, L_/R_nCS, L_/R_S1–S3, MB_TX |
| CSA, direct to the MCU | W_SOA/B/C |
| CSA, into its filter R | L_/R_SOA/B/C |
| Gates | W_GHA/B/C, W_GLA/B/C |
| Kelvin ties | W_SNA/B/C |
| Straps and charge pumps | U2_MODE/IDRIVE/VDS, U2_CPH/CPL/VCP/DVDD, BUCK_CB, L_/R_CP/CPH/CPL |
| Unused DRV8316 buck | L_/R_SWBK |
| Soft-start and regulator | PSW_CAP, PSW_RG, BMS_REG |
| Balance taps | BAL0–BAL3 |
| BMS I²C and alert (pull-ups on the compute board) | BMS_SCL/SDA/ALERT |
| Other | VBAT_SNS_H, BOOT0, ARM_AC, LED_A, L_/R_TEMPJ |

**Drivers and pull resistors.**  Every signal net has one driver and at least one load.  The open-drain nets have their pull-ups: W_nFAULT (R42 to +3V3), L_/R_nFAULT (R301/R401 to their own AVDD).  The remaining pulls go to the correct rails:

| Direction | Rail | Nets (resistor) |
|---|---|---|
| Pull-down | GND | W_EN (R40), W_INLx_M (R47–R49), W_ARM_CLK (R18), W_ARM_S (R19), BOOT0 (R61) |
| Pull-up | +3V3 | DRV_OFF (R50), INA_nCS (R12), NRST (R16), MB_RX (R17) |

**Decoupling:** every power pin is decoupled.

| Part | Decoupling |
|---|---|
| U1 | VDD C60–C63 + C64; VDDA C65; VREF+ C71 + C66; VBAT C74 |
| U2 | VM C24; VIN C27; VREF C23; DVDD C22; VCP C21; C20; CB C28.  Bridge: C25/C26/C31 + C1 |
| U3/U4 (rev K) | Now all on L_VM/R_VM behind R302/R402, which I checked in nets.md: <br>• VM: C300/C301 (100 nF at pins 9/11) + C302/C308/C309/C310 (4 × 10 µF). <br>• CP: C303 to L_VM. <br>• CPH/CPL: C304. <br>• AVDD: C305. <br>• VREF: C306. <br>• CBK: C307. <br>Nothing that belongs to a DRV8316 is left on VBAT, and no VBAT-only part moved |
| U5 | C69, C70 |
| U6 | C40 |
| U7 | C3 |
| U8 | C9, C11 |
| U9 | C47 |
| U10 | C50 |
| U11 | C45, C46 |
| U12 | C48, C49 |
| U13 | C14 |
| U14 | C17 |

**Absolute maximum ratings:**

**Reversed pack:**
* VS is −16.8 V, against a −65 V rating.
* EN is −2.2 V, which is ≥ V(VS).  OV is 0 V, which is ≤ 65 + V(VS).
* Q8's body diode blocks.
* D10 is reverse-biased (PSW_DV ≈ 0 V, PSW_RG ≈ −16 V), so C13 cannot lift the gate.
* L_VM and R_VM are unreachable, because they sit behind Q8.

**Switch open (balance lead only):**
* U8 returns through D5.
* U7 sits after the switch.

**Rev K:**
* L_VM sits at most I × 0.1 Ω from VBAT (0.8 V at 8 A).
* The CP cap stays referenced to the pins' own VM.

**MCU pins:**
* The TT_a inputs PB0/PB10 come from 3.3 V buffers.
* PC5 is pulled to 3.3 V.
* The dividers give 2.15 V at 16.8 V.

### 4. Footprints

**Standard footprints:** all 33 exist.  In each one the pad names equal the netlist pin set of every ref that uses it.
* PQFN-8-EP: pads 1–5.
* RGZ0048A: 1–49.
* QFN-20: 1–21.
* DDF0008A: 1–8.
* The new R302/R402 use `R_2512_6332Metric`, pads 1–2, the same footprint as RS4.

**thumbsup: footprints:** there are four, and all are in DESIGN §6.12.

| Footprint | Parts | Pins |
|---|---|---|
| BOOMELE_1.27-2x10P_SMD | J1 | 20 |
| R_2512_HoLR_1-4mR | RS1–RS3 | 2 |
| SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB | J2/J3 | 1–6 + MP |
| TI_RGF0040E_VQFN-40-1EP… | U3/U4 | 1–41 |

### 5. BOM

**bom.csv:**
* 67 lines.  Qty sum = designator count = 198.
* The DNP parts (C110–C112, C114–C116) are excluded.
* There are 67 unique LCSC numbers, each with one footprint.
* This matches DESIGN §1, BOM.md and README: 198 parts, 67 lines, 6 DNP.

**Every C-number matches its line's value, voltage, dielectric and size** (MPN decode):
* C21122 = 22 nF 50 V.
* C28233 = 100 nF 100 V.
* C13585 = 10 µF 50 V 1206.
* The other lines check out the same way.

**JLC classes today:** these match the BOM.md list and counts exactly.
* **Extended (25 lines):**
  * The 11 IC lines.
  * Q1–Q8, C1, D1, D4, D9, L1.
  * RS1–RS3, RS4, **R302/R402**, TH1, R4.
  * J1, J2/J3, J4.
* **Preferred (4 lines):** R20, R22/R24/R26/R63, R45, R46.
* **Basic:** all the rest.  This includes C14, C13, D2, D3, D5, D7/D8 and D10.

**C25466:**

| Field | Value |
|---|---|
| Part | UNI-ROYAL **25121WF100LT4E** |
| Rating | 100 mΩ ±1 % 1 W 200 V thick film, 2512 |
| TCR | ±800 ppm/°C |
| Class | `componentLibraryType = expand` (**Extended**), not preferred |
| Stock | 76,031 (presale 68,984) |

This matches the netlist (R302/R402, 0.1R 1W 2512, `R_2512_6332Metric`), BOM.md ("UNI-ROYAL 25121WF100LT4E … Extended, 76k") and the CHANGES rev K line.

**Stock:** U1 is at 205 (BOM.md says ~200), U2 at 203 and U7 at 101.

### 3. Documents vs netlist, BOM, calcs and sims

I read these documents in full against netlist.csv, nets.md, bom.csv, calcs.md, hotplug.out and arm.out:
* DESIGN.md, BOM.md, README.md.
* datasheets/README.md, spice/README.md.
* calcs.md, mcu_pinmap.md.
* CHANGES (rev K section), round8_c18_sweep.md.

**Checked and correct:**

* **Refdes, values and pins:**
  * §3.1–§3.5 tables and bullets.  This includes the rev K VM row, C303 "CP–L_VM", C305–C307, R300/R301.
  * The J1 table and TP1–TP12.
  * §6.5/§6.6: 2 × 100 nF + 4 × 10 µF on the filtered side.
  * §6.12, §7.15, §9.
* **Rev K sim figures:**

  | Figure | Documents | hotplug.out |
  |---|---|---|
  | Quick re-close | 2.06 | 2.059 |
  | Loaded bounce | 2.25 / 2.2 | 2.246 |
  | −40 °C bounce | 2.65 | 2.652 |
  | Typical re-close | 0.06–0.7 | 0.062–0.694 |
  | Minimum-UVLO re-close | 1.8–2.06 | 1.801–2.059 |
  | Bounce with C1 at its aged 0 °C bound | 0.8–2.25 | 0.833–2.246 |

  The loaded bounce is quoted as 2.25 in §5, §7.2 and CHANGES, and as 2.2 in §3.3.  All these figures are in V/µs.
* **Rev K sizing:** RC 1.6 µs, 0.1–0.4 W, 0.8 V at 8 A, ~16 µF (4 × ~4 µF).
* **ARM numbers:** unchanged, and they match arm.out.  Armed level 2.50–2.95 V, 7–10 edges, 12 ms at 500 Hz, disarm 52–134 / 67–164 ms.
* **calcs.md against DESIGN §4:** every row matches apart from N-01.
* **CHANGES rev K:** every item is present in the documents.  This covers the R10B-01/02 labels, PC3 wording, bounce cases 0.1/0.3/0.8 ms, the sim docstring "Rev K", the §7.21 provenance, the 44 µs cell-to-cell figure, the §8 fast-trip rows and the §9 step 4 trip test.

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R11B-01 | MINOR | DESIGN.md:74 (§2 design choices) | The drive channel is said to be "one IC and **~17 passives**".  That count was exact for rev J: 9 caps C300–C308, R300/R301, and the 6-part CSA filter.  Rev K adds R302, C309 and C310, so each channel now has **20**: C300–C310 (11), R300–R302 (3), R70–R72 + C80–C82 (6).  A drawer who counts passives per channel against this would stop 3 short | netlist.csv (U3 channel: C300–C310, R300–R302, R70–R72, C80–C82); CHANGES rev K row | "~20 passives" |
| R11B-N01 | NOTE | DESIGN §4 "Power switch closure", §5 hotplug row; calcs.py:153 → calcs.md §9; DESIGN §3.1 Q7 row | The Q7 figures are stale since the rev K sim: <br>• The doc says "Q7 16 W peak (**21.5 W** at the max gate current)".  hotplug.out gives 16.5 W nominal and **21.9 W** at 77 µA. <br>• §5 gives "**53–56 mJ**".  The closure cases give 53.7–56.9 mJ, which is "54–57" | hotplug.out close rows | 16.5 W / 21.9 W / 54–57 mJ (calcs.py text too) |
| R11B-N02 | NOTE | DESIGN §5 hotplug row | "peak VM dV/dt **0.003–0.009** V/µs in every case".  The 0.009 is the pre-filter (rev J) figure.  hotplug.out now gives **0.002–0.005** V/µs (0.002 in the 40 µA case) | hotplug.out close rows | "0.002–0.005 V/µs" |
| R11B-N03 | NOTE | DESIGN §3.1 R1/D10 row, §5 | "100–146 A without D10".  hotplug.out gives **101.87 / 147.08 A** (3 k / 100 k hold) | hotplug.out reversed-pack rows | "~100–150 A" or "102–147 A" |
| R11B-N04 | NOTE | spice/sim_hotplug.py docstring (lines 21–22) and model (`cm vbat nm1 28u`, a single `rt/cvm` branch); spice/README model notes | **The sim's bus capacitance is still rev J's.**  It puts "7 x 10 uF 1206 MLCC derated to 4 uF" (28 µF) directly on VBAT.  In rev K only C25/C26/C31 (3 × 10 µF, ~12 µF) sit on VBAT; C302/C308/C402/C408 moved behind R302/R402.  Only one DRV8316 filter branch is modelled; the other 0.1 Ω + 16 µF is missing.  spice/README's model notes say "trace to VM" and do not mention the VM filter.  <br>**Impact, measured.**  I reran a copy with 12 µF on VBAT plus both filter branches.  Worst re-close 2.059 → **2.092** V/µs; bounce at the 0 °C bound 2.246 → **2.258**; −40 °C 2.652 → **2.662**; ramps and energies within 0.1.  Every conclusion (≤ 2.7 V/µs, "≤ 2.1", "≤ 2.25" to 2 sig. fig.) still holds.  calcs §9 "~386 µF" is similarly a pre-rev-K total: rev K is ~375 µF, and τ comes out at 2.3 s rather than 2.4 s | sim_hotplug.py:21–22, :92–103; nets.md VBAT/L_VM/R_VM; `/tmp/r11/hotplug_fix.out` | Model 12 µF on VBAT + two R/C branches; update the docstring and spice/README; rerun |
| R11B-N05 | NOTE | DESIGN §1 Environment; calcs §7 VM-filter row | "keep **every simulated bus event** ≤ 2.7 V/µs" / "every bus event <= 2.7 V/us at the VM pins".  §7.21 itself records a simulated phase-to-ground short (VDS trip only) at **~7–8 V/µs** at the filtered VM, from the round-10 sims.  The ≤ 2.7 claim holds for the sim_hotplug events only | DESIGN §7.21; round10_a R10A-01 | "every hot-plug, re-close and bounce case in sim_hotplug.py" |
| R11B-N06 | NOTE | DESIGN §3.3 VM row; motor_board.py R302 desc; calcs §7 | These give the fault-clear kick as "9–11 → **~1 V/µs** (sim)".  §7.21 gives "~1–2 V/µs (round 10 sims)".  round10_a: ~1 V/µs is a 200 ns average; at 50 ns it is ≤ 2.2 V/µs rising.  "(sim)" also reads as if it were in spice/, which it is not | round10_a_hardware.md R10A-01 fix column | Use "~1–2 V/µs (round-10 reviewer sims)" everywhere |
| R11B-N07 | NOTE | DESIGN §7.21 "R302/R402 take ~100 A for ~1 µs (~1 mJ, well inside a 2512's short-time overload)"; datasheets/ | Round 10 (round10_a N-06(a)) marked the 2512 thick-film single-pulse rating **UNVERIFIED**.  The doc now asserts it without a source.  No UniOhm datasheet is in datasheets/: the README excludes only "JLC **Basic** generics", and C25466 is Extended (1 W, ±800 ppm/°C) | JLC record above; datasheets/README.md last line | Add the UniOhm 2512 datasheet / pulse-load curve, or soften to "expected" |
| R11B-N08 | NOTE | calcs §11 heat budget; DESIGN §4 "Board heat" | The heat budget omits the new R302/R402 loss: 0.1–0.4 W each at 1–2 A drive bus current, ~0.2 W at the 1.5 A budget point.  The total changes by < 0.3 W average | calcs §7 VM-filter row | Add a line, or note it inside the drive row |
| R11B-N09 | NOTE (firmware) | DESIGN §8 | round10_a N-06(b) found that the drive VM now sits I_bus × 0.1 Ω below VBAT (0.8 V at 8 A, 1.6 V at the 16 A OCP).  The firmware contract does not say that drive voltage feed-forward / SVPWM normalisation should use VBAT − I·R, or tolerate ≤ 5 % | round10_a_hardware.md N-06 | One clause in the DRV8316 or STM32 row |
| R11B-N10 | NOTE | design/mcu_pinmap.md pins 7, 61 | NRST (PG10-NRST) and BOOT0 (PB8-BOOT0) are labelled "GPIO / analog".  The generator labels every AF-less, non-power pin this way | motor_board.py:500 | Label reset/boot pins, or add an explicit function string in MCU_PINS |
| R11B-N11 | NOTE (tooling) | motor_board.py docstring | "Checks: every pin of every IC is either on a net or explicitly NC".  The script never compares a part's pin list with its package, so an omitted pin would pass.  I checked completeness by hand against every KiCad pad set: all match.  (R10B-N07, one AF per pin checked, also still applies) | motor_board.py:451–506 | Compare pins with the footprint pad set (or a pin count per part) |

No BLOCKER or MAJOR finding.  I checked every connection, polarity, NC pin, footprint pad set, AF/ADC/COMP claim,
BOM total, JLC class and the C25466 record against its source, and each matches.  The rev K VM-filter change is
wired correctly: R302/R402 from VBAT; every VM pin, VM cap and the CP cap on L_VM/R_VM; nothing left on VBAT.

**Verdict: 0 BLOCKER, 0 MAJOR, 1 MINOR, 11 NOTE.**
