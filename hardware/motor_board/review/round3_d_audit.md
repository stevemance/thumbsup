# Round 3 — D: mechanical netlist / pin / footprint / BOM / docs audit (rev C)

Auditor: adversarial, read-only (no design file edited).  Date 2026-09-23.

## Method

* `design/motor_board.py` was run on a copy (`/tmp/mbaudit`), so the checked-in outputs were not rewritten.
  Result: `201 refs (180 placed components), 150 nets, 56 BOM lines` / `checks: OK`.  All four
  generated files (`netlist.csv`, `nets.md`, `bom.csv`, `mcu_pinmap.md`) are byte-identical to the checked-in ones.
* Datasheets were converted with `pdftotext -layout`.  The scanned drawings (BOOMELE, XUNPU) were
  rendered with `pdftoppm` and read by eye.
* Footprints: each non-`thumbsup:` footprint was opened in `/usr/share/kicad/footprints/*.pretty`.
  Its set of pad numbers was compared with the set of netlist pin numbers for that part.
* BOM, refdes ranges and 2-node nets were checked by script against the `PARTS` dict.

## 1. IC pin audit (netlist pin ↔ datasheet pin name/number)

| IC | Source | Result |
|---|---|---|
| U1 STM32G474RET6 LQFP-64 | `ref/STM32G474RxTx_pins.xml` | All 64 pins match by position and name.  All 40 required AFs exist (script check).  Power pins: 1 VBAT, 15/31/47/63 VSS, 16/32/48/64 VDD, 27 VSSA, 28 VREF+, 29 VDDA: correct.  The TT_a claims in DESIGN (PA4, PA5, PB11, PB0, PB10, PC5) match DS12288 Table 12 (TT_a). |
| U2 DRV8323RH RGZ-48 | SLVSDJ3D Table 6-4 (DRV8323RH column) | All 48 pins + PAD (49) match by number and name.  NC pin 46: "can be left floating" (OK).  Straps are correct per the EC table and Fig. 8-23/8-24: MODE 47 k→AGND = 3x PWM; IDRIVE 75 k→AGND = 60/120 mA; VDS 18 k→AGND = 0.13 V; GAIN Hi-Z = 20 V/V ("GAIN = Hi-Z 19.4 20 20.6"). |
| U3/U4 DRV8316CR RGF-40 | SLVSH07 Table 6-1 (CR column) | All 40 pins + PAD (41) match.  NC pins 1 and 24: "No connection, open" (OK).  SDO: CTRL2 SDO_MODE reset 1h = push-pull, so deleting R51 is valid.  nSCS has an internal RPU of 80–130 kΩ to AVDD, so no external pull-up is needed.  §8 frames 0x0603/0x1019/0x0B4F/0x1915/0x087C/0x097D/0x0606 all have the correct register offsets (3h/8h/5h/Ch/4h), bit fields and even parity. |
| U5 AP2112K SOT-25 | DS39724 pin table | 1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT: match. |
| U6 SN74LVC08A PW | SCAS283 Pin Functions | 1–14 match (8 = 3Y, 9 = 3A, 10 = 3B, 11 = 4Y). |
| U7 INA239 DGS | Table 5-1 | 1 CS, 2 MOSI, 3 ALERT, 4 MISO (push-pull, Hi-Z with CS high: tCS_MISO_HIZ), 5 SCLK, 6 VS, 7 GND, 8 VBUS, 9 IN−, 10 IN+: match. |
| U8 BQ76907 RGR | SLUSE96A Table 5-1 / 7-1 / 8-3 | All 20 pins + EP (21) match.  4S wiring per Table 7-1 (VC6=VC5, VC4=VC3, VC2=VC1).  SRP/SRN/TS → VSS and DSG/CHG open, per Table 8-3.  VC0 through R6 + C8 to VSS, per Table 8-3. |
| U9/U10 SN74LVC3G17 DCU | SCES470F Pin Functions | 1 1A, 2 3Y, 3 2A, 4 GND, 5 2Y, 6 3A, 7 1Y, 8 VCC: match. |
| U11/U12 TPS22945 DCK | SLVS832D Pin Functions | 1 VOUT, 2 GND, 3 OC (open-drain flag, NC is OK), 4 ON, 5 VIN: match. |
| Q1–Q8 HYG015N04LS1C2 | HUAYI pin figure "S S S G / D D D D" | Leads 1–3 = S, 4 = G, drain = pad 5.  In the KiCad `PQFN-8-EP_6x5mm_P1.27mm_Generic`, pad "5" is one custom pad that merges drain leads 5–8 and the tab: match. |
| D1–D8 | KiCad pad 1 = K | D1 K=VBAT; D2 K=BUCK_SW; D3 K=GND; D4 K=RPP_G (zener clamps the gate positive); D5 K=CELL0 (clamps VC0 negative); D6 K=VBAT, A=RPP_G (gate discharges into a collapsing VBAT).  All correct.  D7/D8 BAT54S: 1 A1=GND, 2 K2=+3V3, 3 K1/A2=MTEMP, a correct dual clamp (Nexperia series pinning; see M3 on the missing datasheet). |
| Connectors | netlist / DESIGN §3.5 / drawings | J1 20 pins = DESIGN §3.5 table.  BOOMELE land: 0.74 × 1.5 mm pads, 6.5 mm outer span, so pad centres are at ±2.5 mm and there are no pegs: this matches DESIGN.  J2/J3 1 VS, 2 GND, 3–5 S1–S3, 6 TEMP, MP; the XUNPU drawing has 6 × 1.0 mm-pitch pads + 2 tabs of 1.2 × 2.5 mm (matches BOM.md).  J4 1 = B0 … 5 = B4.  JP1/JP2: pad 2 is the common, 1–2 bridged = +3V3. |

**No pin-number, pin-name or NC mismatches.  No NC pin needs to be tied.**

## 2. Net audit

* Every net has at least 2 nodes.  No net consists of passives only.  Every signal net has a driver and a load.
* **69 two-node nets**, all intended point-to-point connections: BAL0–BAL3, BAT_NEG, BMS_ALERT/SCL/SDA/REG, BOOT0, BUCK_CB,
  LED_A, L_/R_ CP/CPH/CPL, L_/R_ INHA–C, L_/R_ S1–S3, L_/R_ SOA–C (CSA → 330 Ω), L_/R_ SWBK, L_/R_ TEMPJ,
  L_/R_ nCS, MB_TX/RX, U2_CPH/CPL/DVDD/IDRIVE/MODE/VCP/VDS, W_GHA–C, W_GLA–C, W_INHA–C, W_INLA–C, W_SNA–C, W_SOA–C.
* Decoupling is present for every IC power pin: U1 (C60–C63, C64, C65, C66/C71, C74); U2 (C24/C25/C26 VM, C27 VIN, C23 VREF,
  C22 DVDD, C21 VCP, C20, C28); U3/U4 (C300/301/302/308, C305, C306, C303, C304, C307); U5 (C69/C70); U6 C40; U7 C3;
  U8 (C9, C11); U9/U10 (C47/C50); U11/U12 (C45/C48 in, C46/C49 out).
* Pull rails are correct: R42 W_nFAULT → +3V3 (INA ALERT abs max VS + 0.3); R301/R401 → own AVDD; R50 DRV_OFF ↑;
  R40/R41/R47–R49 ↓; R12 INA_nCS ↑; R54–R59 → +3V3; R61 BOOT0 ↓.
* Abs-max: every VBAT pin is rated for it.  U2 VM/VDRAIN/VIN 65 V; U3/U4 VM 40 V (TVS 32.4 V); U7 VBUS/IN± 85 V; U8 BAT 40 V;
  Q gates are clamped by D4; nSHDN is HV-tolerant; the caps are rated 25–50 V where required.
  Every +5V pin is rated for it: U5 6.5 V; U11/U12 (via JP) 6 V; U9/U10 inputs 5.5 V.

## 3. Findings

| # | Sev | Where | Finding | Evidence |
|---|---|---|---|---|
| M1 | MINOR | README.md:7 | "158 JLC-assembled parts (rev B, …)" is stale.  Rev C has 174 assembled + 6 DNP in 56 lines. | bom.csv Qty sum = 174, 56 lines; DESIGN.md:35 and BOM.md:4 say 174 + 6 DNP |
| M2 | MINOR | datasheets/README.md:17, :25 | HYG015N04LS1C2 is listed for "weapon FETs Q1–Q6, reverse-polarity FET Q7".  Q8 (inrush limiter) is missing.  MMSZ5242B is listed as "Q7 gate clamp D4"; it clamps the common Q7/Q8 gate. | motor_board.py:100 Q8 HYG015N04LS1C2; nets RPP_G: Q7.4, Q8.4, D4.1 |
| M3 | MINOR | datasheets/README.md:24 | Stale: "BAT54WS_Diodes.pdf \| VC0 clamp D5", but D5 is a B5819W (C8598).  There is no datasheet for B5819W (D5, D6) or BAT54S (D7, D8), although DESIGN.md:20 claims "PDFs of every non-generic part".  So the D7/D8 pin mapping (1 = A1, 2 = K2, 3 = common) has no document in the package. | bom.csv `B5819W,"D5,D6",…,C8598`, `BAT54S,"D7,D8",…,C47546`; `ls datasheets/` |
| M4 | MINOR | BOM.md:51–52; DESIGN.md §3.3; datasheets/README.md:30 | Custom footprint `thumbsup:SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB` (J2/J3):<br>• it is missing from BOM.md's "Draw the custom footprints" list;<br>• DESIGN.md never names it;<br>• datasheets/README says the JST SM06B is "the JST original the footprint is drawn to", which contradicts BOM.md:30 ("tab pads 1.2 × 2.5 mm per the XUNPU drawing").<br>The source drawing should be XUNPU_WAFER-SH1.0-6PWB.pdf (verified: 6 × 1.0 mm-pitch pads + 2 tabs 1.2 × 2.5). | motor_board.py:282; BOM.md:30, :51–52 |
| M5 | MINOR | BOM.md:34 | "U1–U12 (10 lines)": the U parts occupy **9** bom.csv lines (U1, U2, U3/U4, U5, U6, U7, U8, U9/U10, U11/U12).  The rest of the list gives the correct total of 23 Extended lines (round2_e §5). | bom.csv |
| M6 | MINOR | DESIGN.md:102; motor_board.py:93, :106, :123 | The hot-plug numbers disagree:<br>• C13 "sets ~0.05 V/µs" (DESIGN);<br>• "~0.04 V/us instead of 4-6 V/us" (motor_board.py:93);<br>• C13 desc "~0.04 V/us, 5-8 A inrush" (:106);<br>• the SPICE output and DESIGN §1/§4/§5 say **0.06–0.08 V/µs, 5.1–5.2 A**.<br>The C1 desc (:123) still says C1 "limits VM dV/dt at plug-in", which the Q8 limiter superseded (DESIGN.md:105). | spice/hotplug.out rows "WITH Q8 limiter" 0.06/0.07/0.08 V/us, 5.1/5.2/5.1 A |
| M7 | MINOR | motor_board.py:117 | U7 description: "ALERT (open drain, **only SOVL enabled**)".  Rev C programs SOVL **and** BOVL. | DESIGN.md:103, :416; CHANGES.md R2A-01 |
| M8 | MINOR | DESIGN.md:344 | Layout rule 1: "C25/C26 (10 µF) directly across **each** half-bridge".  There are three half-bridges and two 10 µF caps (C24 is the 100 nF at U2 pin 6).  Either a third bridge cap is intended and missing from the netlist, or the rule should say "shared by the three half-bridges". | nets VBAT: C25, C26 (C1206 10 µF) only; motor_board.py:188–189 |
| N1 | NOTE | RS4 | RS4 uses the generic `R_2512_6332Metric` land (1.225 × 3.35 mm pads, 4.7 mm gap).  The JIERR suggested land is 2.1 × 4.0 mm pads with a 4.1 mm gap (small electrode), or 3.1 × 4.0 mm with a 1.3 mm gap (large electrode).  Which electrode C46961745 has is not recorded.  It is solderable (and was used on v1), but RS1–RS3 got a custom land for the same reason. | RE2512F3R001 "Suggested PCB dimensions"; KiCad pad size |
| N2 | NOTE | J2/J3 footprint | The netlist has one pin "MP": when drawing, number **both** tabs "MP". | motor_board.py:284 |
| N3 | NOTE | thumbsup: library | None of the 7 motor-board `thumbsup:` footprints exist yet.  `hardware/kicad/thumbsup.pretty` holds only v1-board parts.  The sources are documented for RGF0040E (TI drawing), HoLR (Milliohm land) and BOOMELE (vendor land).  SolderPad 3×5 / 2×3 are defined only by their names. | `ls hardware/kicad/thumbsup.pretty` |
| N4 | NOTE | DESIGN §3.3 / §7 | A sensor S-line chafed onto a motor phase puts 16.8 V through 1 kΩ into U9/U10 inputs (abs max 6.5 V, no clamp to VCC), which destroys the buffer.  Round 2 accepted this ("kills a buffer, not the MCU"), but the current DESIGN.md lists only the VS and TEMP residuals. | SCES470F §6.1; round2_b B-05 |
| N5 | NOTE | motor_board.py:22–23 | The docstring says "Parts marked 'confirm' in the BOM need their pinout checked", but no part is marked "confirm". | BOM.md |
| N6 | NOTE | DESIGN.md:72 | "Each drive channel is one IC and ~12 passives": the netlist has 17 per channel (C300–C308, R300, R301, R70–R72, C80–C82). | netlist |
| N7 | NOTE | W_SOA–C | The DRV8323 CSA outputs go straight to PA0–PA2 with no RC filter (the drive CSAs get 330 Ω + 22 pF).  The CSA is specified for a 60 pF load, and the ADC sample cap is well inside that, so this is acceptable.  It is noted only because it is asymmetric with the drives. | SLVSDJ3D EC "60pF load" |

## 4. Footprints

* All 27 non-custom footprints exist in `/usr/share/kicad/footprints`.  Each one's pad-number set equals the part's netlist pin set, EP and tab pads included:
  * U2 1–49; U3/U4 need 1–41 (custom); U8 1–21; the PQFN pad 5 covers the drain;
  * LQFP-64 64 pads; MSOP-10 10; TSSOP-14 14; VSSOP-8 8; SOT-23-5 / SOT-353 5; SOT-23 3; JST XH 5; JP 3; 2-pad parts 2.
* Custom (`thumbsup:`) footprints and where they are documented:
  * TI_RGF0040E (41 pads; EP 3.7 × 5.7 matches TI's 3.6–3.8 × 5.6–5.8): DESIGN §3.3, BOM.md.
  * R_2512_HoLR_1-4mR (2): DESIGN §3.2, BOM.md.
  * BOOMELE_1.27-2x10P_SMD (20): DESIGN §3.5, BOM.md.
  * SH1.0-6P_RA_XUNPU (6 + MP): see **M4**.
  * SolderPad_4x6/3x5/2x3 (1): "and the solder pads" in BOM.md.

## 5. bom.csv

* 56 lines, Qty sum **174**, no designator appears twice, and every Qty equals its designator count.
* The 6 DNP parts (C110–C112, C114–C116) are excluded, as are the pads, test points, net-ties and jumpers (27 refs).
* No LCSC number appears with two different comments, and no comment appears with two LCSC numbers.
* The counts in DESIGN.md:35 and BOM.md:4 (174 + 6 DNP, 56 lines) are correct.  README.md is wrong (M1).
* Every refdes and refdes range cited in DESIGN.md, BOM.md, README.md and datasheets/README.md exists in the netlist (script check).

## Verdict

**BLOCKER 0, MAJOR 0, MINOR 8, NOTE 7.**  The connectivity, pinouts, footprints and BOM are clean.  All the MINORs are documentation text.
