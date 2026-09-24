# Round 2 review D: monitors, logic, connectors, and netlist integrity (motor board rev B)

Scope: U8 BQ76907 with the rev-B parts (D5, R11, C9, C11, C4–C8), the U8 footprint, J1, the power LED,
J4, and how U7's ALERT and W_nFAULT interact. Also a mechanical audit of `design/motor_board.py` and the
generated `design/nets.md` / `bom.csv` against DESIGN.md, BOM.md and the KiCad 10 libraries. No design file
was edited. `motor_board.py` was run on a copy in /tmp, and its outputs match the committed files byte for
byte ("179 refs (158 placed components), 141 nets, 52 BOM lines, checks: OK").

Sources (text via `pdftotext -layout`, figures rendered with `pdftoppm`):
- **BQ** = `datasheets/BQ76907.pdf` (SLUSE96A, rev. July 2026)
- **BAT54** = `datasheets/BAT54WS_Diodes.pdf` (DS30098 Rev 14-2)
- **INA239** = `datasheets/INA239.pdf` (SLYS027A); **INA229** = `datasheets/INA229.pdf`
- **DRV8323** = SLVSDJ3D; **DRV8316C** = SLVSH07; **TPS** = SLVS832D; **LVC08** = SCAS283; **3G17** = SCES470F; **AP2112K**; **ST** = DS12288 Rev 4
- KiCad library: `/usr/share/kicad/footprints` (every footprint below was checked with `test -f`)

## Findings

| ID | Sev | Ref / net | Issue | Evidence | Proposed fix |
|---|---|---|---|---|---|
| D2-01 | **MAJOR** | U7 ALERT → W_nFAULT → TIM1_BKIN; DESIGN §8 INA239 row, §3.1 RS4/U7 row | **The firmware contract cannot be carried out as written, and following it kills the weapon during spin-up.** DESIGN §8 says "**only SOVL** (≈ 35 A) enabled on ALERT … BUVL low-pack warning read by polling". The INA239 has no per-limit enable or mask bits. Every limit register is compared on every conversion, and any excursion asserts ALERT. So a BUVL written as a "low-pack warning" (≈ 3.5 V/cell = 14 V) pulls W_nFAULT low whenever the bus sags below it. DESIGN §4 and calcs.md give a 13.7–14.1 V minimum bus during a 25 A weapon spin-up. TIM1's break therefore trips and the weapon coasts every time it spins up on a partly used pack, which is the moment it matters in a fight. The same applies to any non-default BOVL, SUVL, TEMP_LIMIT or PWR_LIMIT. Because the DRV8323**H** has no SPI and no fault register, the MCU also cannot tell an INA trip from a driver fault afterwards unless ALATCH = 1 (round-1 R4-13 asked for this; see D2-05). | INA239 §7.3 (line 777 ff.): "The diagnostics listed in Table 7-1 are constantly monitored and can be reported through the ALERT pin whenever the monitored output value crosses its associated out-of-range threshold." DIAG_ALRT (Table 7-13) has only ALATCH, CNVR, SLOWALERT, APOL control bits and flag bits: **no mask/enable per limit**. Reset values that do not trip: SOVL 7FFFh, SUVL 8000h, BOVL 7FFFh, BUVL 0h, TEMP_LIMIT 7FF0h, PWR_LIMIT FFFFh. DESIGN §4: "Pack current peak / bus sag: 22 A / 14.1 V"; calcs.md line 112: "13.7 V minimum bus during a 25 A spin-up". | Rewrite the DESIGN §8 INA239 row: "Only SOVL is written (≈ 35 A). **BUVL, BOVL, SUVL, TEMP_LIMIT and PWR_LIMIT stay at their reset values**: on this part every limit drives ALERT = W_nFAULT = TIM1 break. Low-pack warning = firmware compares VBUS readings. DIAG_ALRT: ALATCH = 1, CNVR = 0, APOL = 0, SLOWALERT = 0. After any TIM1 break, read DIAG_ALRT.SHNTOL to tell a pack over-current from a DRV8323 fault." Also fix the §3.1 wording "only SOVL enabled". |
| D2-02 | MINOR | D5 / CELL0 (U8 VC0) | **D5 does not keep VC0 ≥ VSS − 0.3 V in every case DESIGN §3.1 lists.** (a) *Parked, DC* (switch open, balance lead in): ~146 µA flows through D5. From BAT54 Fig. 1 (typical), VF at 0.1–0.15 mA is ≈ 0.21 V at 25 °C, ≈ 0.28 V at 0 °C and ≈ 0.35 V at −40 °C. The guaranteed max is 240 mV at 0.1 mA, 25 °C, about 40 mV above typical. So the margin is fine at room temperature, but VC0 reaches about −0.3 V in an unheated garage or pit near 0 °C, and goes past it below that. (b) *Balance-lead hot plug with the main unplugged*: C9 charges through R11 + R6 = 200 Ω. The peak is ≈ 80 mA, where BAT54 VF is ≈ 0.5 V typ (1.0 V max at 100 mA). VC0 ≈ −0.5 V for roughly 1–2 ms (τ ≈ 200 Ω × C9 effective). (c) *Every power-switch closure* with the balance lead in: the C1 inrush goes through Q7's body diode plus the negative-lead L·di/dt (DESIGN §3.1), which lifts GND a volt or more above BAL0 for µs. D5 then carries (ΔV − VF)/R6 ≈ 5–15 mA, so VC0 ≈ −0.3…−0.4 V. All three cases are current-limited by R6/R11, and the internal VSS–VC0 diode takes little current while D5 clamps. This is a datasheet violation, not a likely failure. **Leakage**: D5 sits at ≈ 0 V bias in normal operation (GND − BAL0 = +I·R on discharge, slightly negative on regen), so reverse leakage is irrelevant (< 0.1 µA at 25 °C per Fig. 2). Forward conduction at the ≈ 0.11 V offset at 22 A is a few µA at 25 °C and ≈ 20 µA at 75 °C, which is at most ~2 mV of cell-1 error through R6. This is acceptable. | BQ 6.1: "VC0 … VSS–0.3 … VSS+6 V" (no current rating; the < 100 h transient note applies only to VIN(short) rows, not VC0). BQ §8.2 bullet: "recommended minimum voltage on the VC0 to VC4 pins extends down to –0.2V". BAT54 electrical table: VFM 240 mV max @ 0.1 mA, 320 @ 1 mA, 400 @ 10 mA, 500 @ 30 mA, 1000 @ 100 mA; Fig. 1 temperature curves. BQ 6.5 INORMAL 146 µA typ. DESIGN §3.1: "D5 also carries the C9 charge at balance-lead hot plug and the ground offset under high pack current". Magnitudes in (b) and (c) are estimates (UNVERIFIED by simulation). | Cheapest fix: a procedure. Plug the balance lead only with the main XT30 connected, so Q7's body diode shares the C9 charge, and say so in DESIGN §3.1/§7.1 (§7.1 already says "plug the balance lead last"). Correct the §3.1 claim to "clamps VC0 near −0.2…−0.35 V; brief excursions to about −0.5 V at hot plug". A better part: a lower-VF Schottky (VF ≤ 0.3 V at 100 mA, e.g. a 0.5–1 A SOD-323/SOD-123 part). Its higher leakage does not matter here (reverse bias ≈ 0), but check its forward current at 0.1 V (< 20 µA keeps the cell-1 error < 2 mV) (UNVERIFIED part choice). Add the balance network to `spice/sim_hotplug.py` to confirm (c). |
| D2-03 | MINOR | U8 REGOUT, C11 | **C11 is probably below CEXT min once DC bias is applied.** C52923 = Samsung CL05A105KA5NQNC, 1 µF 25 V **X5R 0402** (r5_bom.md line 20). At 3.3 V, 0402 X5R 1 µF parts typically keep only about 60–70 % (UNVERIFIED for this P/N: no curve in `datasheets/`). TI requires ≥ 1 µF on REGOUT, and the OTP enables REGOUT at 3.3 V on every POR, before any host exists. | BQ 6.7: "CEXT External capacitor REGOUT to VSS … 1 µF (min)". BQ §4 table: REGOUT STATUS "Enabled, 3.3V". | C11 → 4.7 µF 16 V 0603 (C19666, already on the BOM, Basic) or 2.2 µF 0603. No maximum CEXT is specified. |
| D2-04 | MINOR | INA_nCS (U7.1, PA11); SPI_SCK/SPI_MOSI at U7 | **U7's CS, SCLK and SDI float while the MCU is in reset and during every boot.** STM32 GPIOs are Hi-Z/analog after reset, and J1 pin 8 lets the compute board hold NRST. The DRV8316Cs have internal pull-ups on nSCS and pull-downs on SCLK/SDI, but the INA239 has neither. A floating CS with a floating SCLK can clock random bits into U7. The worst case is a write to DIAG_ALRT (APOL/CNVR) or a negative SOVL, which asserts ALERT = W_nFAULT continuously until firmware re-inits U7. CHANGES deleted R51 (the old MISO pull-up), so INA_nCS has only 2 connections. | nets.md: **INA_nCS**: U1.45, U7.1 only. DRV8316C EC table: nSCS "RPU Input pullup resistance 80–130 kΩ"; other logic inputs "RPD 70–130 kΩ". INA239 pin table and EC: no internal pull on CS/SCLK/SDI (no mention in SLYS027A; UNVERIFIED as "none"). ST: reset state of I/Os = analog. | Add a 100 kΩ pull-up INA_nCS → +3V3 (C25741, existing line). Firmware: write CONFIG.RST = 1 to U7 first thing at init, before configuring SOVL. |
| D2-05 | MINOR | DESIGN §8 (INA239 row), J4 silkscreen | **Two round-1 items that CHANGES.md lists as "Documentation … in DESIGN.md §3, §7, §8" are not in DESIGN.md.** R4-13 (ALATCH = 1, CNVR = 0, APOL = 0) is absent from the §8 INA239 row. R4-15 (silkscreen "B−" at J4 pin 1 and "B4+" at pin 5) appears nowhere in DESIGN §6. | `grep -i "ALATCH\|CNVR\|APOL\|silk" DESIGN.md BOM.md` → no match. CHANGES.md row: "W-04, W-07, …, R4-09/11–17 \| Documentation / firmware notes in DESIGN.md §3, §7, §8". | Add both. The ALATCH text is part of D2-01's fix. Put J4 polarity silk in DESIGN §6 item 7. |
| D2-06 | MINOR | BOM.md "Extended-part lines" paragraph | **BOM.md lists "R22–R27/R63 68k" as Preferred. R23, R25 and R27 are 10 kΩ** (divider bottoms, on the Basic "10k 1%" line). Only R22, R24, R26 and R63 are 68 k. | bom.csv: `68k 1%,"R22,R24,R26,R63"`; `10k 1%,"R21,R23,R25,R27,…"`. motor_board.py line 197–198. | Change to "R22/R24/R26/R63 68k". |
| D2-07 | NOTE | U8 footprint `Package_DFN_QFN:QFN-20-1EP_3.5x3.5mm_P0.5mm_EP2x2mm` | **Compatible with TI RGR0020A, but not TI's land.** KiCad: pads 0.875 × 0.25 at ±1.6875 mm (1.25–2.125 mm from centre), EP 2.00 × 2.00 (pad "21", mask only), paste 4 × 0.81 mm (≈ 66 %). TI: pads (0.6) × (0.24) at (3.3) row span (1.35–1.95 mm), EP (2.05), paste 4 × (0.92) (81 %). Pin order matches: 1–5 left top→bottom, 6–10 bottom, 11–15 right bottom→top, 16–20 top, EP = 21. The KiCad pads reach 0.1 mm further under the body (EP-to-pad gap 0.25 mm vs TI 0.325 mm). Package EP is 2.05 ± 0.1, so it can be up to 0.15 mm bigger than the KiCad EP pad. It will solder. The descr cites TI mpqf239, a generic 3.5 × 3.5 QFN, not RGR. | KiCad pad dump (this review). BQ pp. "PACKAGE OUTLINE / EXAMPLE BOARD LAYOUT / EXAMPLE STENCIL DESIGN" RGR0020A 4219031/B. | Optional: a local copy with EP 2.05 mm and 4 × 0.92 mm paste; otherwise keep it. |
| D2-08 | NOTE | C9 (U8 BAT/REGSRC) | C377773 = CL21A225KBQNNNE 2.2 µF 50 V **X5R** 0805. At 16.8 V a 50 V X5R 0805 typically keeps about 40–50 % (UNVERIFIED for this P/N), i.e. ≈ 1 µF, right at TI's Cf min 1 µF and CREGSRC min 1 µF. U8 has no short-circuit hold-up duty here, so the risk is low. | BQ 6.3: "Cf … 1 … 40 µF"; "CREGSRC … 1 µF". r6_parts_lookup.md line 13. | Optional: 4.7 µF 50 V 0805/1206 X5R, or accept. |
| D2-09 | NOTE | DESIGN §3.1 / §1: "INA229AIDGSR is pin- and register-compatible … fit it instead" | It is pin-compatible but not register-compatible. VSHUNT, VBUS and CURRENT are **24-bit** on the INA229 (16-bit on the INA239), and the INA229 adds ENERGY/CHARGE (40-bit). SPI frames and scaling differ, so a drop-in swap needs a firmware change. The alert logic is the same (ENERGYOF/CHARGEOF do not drive ALERT). | INA239 register map lines 1010–1016 vs INA229 lines 1060–1068; INA229 lines 874–883. | Reword: "pin-compatible; firmware must read the wider result registers (check DEVICE_ID)". |
| D2-10 | NOTE | DESIGN §7.1 | "Q7 is off, U8's µA return through D1" is outdated now that D5 is fitted. With a reversed main (VBAT = pack−) and the balance lead in, U8's current returns GND → D5 → R6 → BAL0: D5 (≈ 0.2 V) conducts before D1's forward drop (≈ 0.5–0.6 V at 150 µA). GND sits ≈ 0.2 V above VBAT, inside the DRV VM −0.3 V abs min. | Netlist: D1 K = VBAT, A = GND; D5 K = CELL0, A = GND; R6 BAL0–CELL0. | Reword to "U8's µA return through D5 (VC0 ≈ −0.2 V)". |
| D2-11 | NOTE | D3 / R62 power LED; DESIGN §3.1 "The power LED shows the switch state" | The LED is on +5V, so it shows "buck running", not "pack connected". With the switch closed but the pack below the UVLO (~9.2 V off, spread 7.4–10.3 V) or the buck faulted, VBAT and C1 are live and the LED is off. The drivers cannot run then (MCU unpowered, U3/U4 nSLEEP = +3V3 = 0, R40 holds ENABLE low), so this is not a motion hazard. It does mislead anyone using the LED as "safe to touch/unplug". | nets.md **+5V**: R62.1; **LED_A**: D3.2, R62.2. DESIGN §3.1 R4/R5 row. | Reword to "shows the logic rails are up; a dark LED does not prove the pack is disconnected". Or feed the LED from VBAT through ~4.7 kΩ (≈ 3 mA at 16.8 V, 50 mW) if a true "pack live" indicator is wanted. |
| D2-12 | NOTE | BMS_SDA / BMS_SCL / BMS_ALERT | The only pull-ups are on the compute board. During motor-board-only bring-up (DESIGN §9 steps 1–2) with a pack's balance lead in, U8's SCL/SDA float. TI says unused SCL/SDA must go to VSS. Harmless for a bench session. | BQ Table 8-3: "SCL, SDA: If not used, these pins must be connected to pin 11 (VSS)". nets.md: BMS_SCL = J1.16, U8.12 only. | Optional DNP 10 kΩ pads to +3V3 on BMS_SDA/SCL for standalone bring-up, or say in §9 "balance lead only with the compute board fitted". |
| D2-13 | NOTE | TPS22945 U11/U12: C45/C48 (VIN 100 nF), C46/C49 (VOUT 1 µF) | TI asks for CIN ≈ 1 µF and COUT ≈ 0.1 µF, and "CIN greater than COUT is highly recommended" (body-diode back-feed). The locally placed caps are the other way round. In practice VSRC is the +3V3/+5V plane through JP1/JP2, which carries several µF, and COUT = 1 µF is far below COUT(MAX) = ILIM·tBLANK/VIN (≈ 100 mA × ms / 5 V = tens of µF). So it works. | TPS §9.1.4 "A 1-µF ceramic capacitor, CIN …"; §9.1.5 "A 0.1-µF capacitor, COUT … a CIN greater than COUT is highly recommended"; §9.2.2.2 Eq. 2. | Optional: C45/C48 → 1 µF 25 V 0402 (C52923, existing line). |
| D2-14 | NOTE | U3/U4 VM pins 9/10/11 | DRV8316C pin table: "bypass to PGND with two 0.1-µF capacitors (for each pin) plus one bulk". The netlist has 100 nF at pins 9 and 11 only (pin 10 sits between them). Ambiguous wording, and adjacent pins share copper. Listed for completeness; the drive reviewer owns it. | DRV8316C Table 6-1 VM row; motor_board.py lines 240–243. | Place C300/C301 hugging pins 9–11. |
| D2-15 | NOTE | U1 pin 1 VBAT | Tied to +3V3 with no dedicated capacitor. ST's G4 hardware guide recommends 100 nF at VBAT when it is tied to VDD (AN4938, not in `datasheets/`: UNVERIFIED). Pin 1 sits next to pin 64 VDD (C63). | ST Fig. 16 power scheme (DS12288 p.82); netlist U1.1 on +3V3. | Place C63 between pins 64 and 1, or add a 100 nF. |
| D2-16 | NOTE | Main negative lead opening while running (combat damage) | If the BAT− wire or XT30 negative opens with the balance lead in, the only return path is GND → D5 (and U8's VSS–VC0 diode) → R6 → B0 wire. GND rises toward VBAT and R6 (0402) fuses. After that, VC1–VC4 sit up to ~16 V below VSS through 100 Ω each, so U8 is likely destroyed. This is not new (the U8 internal diode made the same path before D5) and the robot is dead anyway. UNVERIFIED. | Topology: Q7 body diode points GND → BAT_NEG, so it cannot return current from BAT_NEG; D5/R6 path per nets.md. | Accept; note it in §7. |
| D2-17 | NOTE | Stale text in the netlist source and calcs | `motor_board.py` line 21 "DRV8316 SLVSF16B Table 6-1" (the fitted DRV8316C is SLVSH07); line 89 "RS4 (pack shunt, INA229)"; line 221 "2 x DRV8316R"; lines 250 and 329 cite SLVSF16B sections; calcs.md lines 7–10 "SLVSF16B 7.5"; calcs.md line 49 puts "BQ76907 (from BAT)" in the 3V3 budget (U8 is fed from the balance lead). No connectivity impact. | grep output in this review. | Update the references. |

## VERIFIED OK

**U8 BQ76907 and the rev-B parts**
- Pin numbers vs BQ Table 5-1: 1 VC4, 2 VC3, 3 VC2, 4 VC1, 5 VC0, 6 SRP, 7 SRN, 8 TS, 9 DSG, 10 CHG, 11 VSS, 12 SCL, 13 SDA, 14 ALERT, 15 REGOUT, 16 REGSRC, 17 BAT, 18 VC7, 19 VC6, 20 VC5. The netlist matches exactly. EP pad 21 → GND. The KiCad QFN-20 EP is also pad "21".
- 4S mapping matches BQ Table 7-1 row 4 (VC7–VC6, VC5–VC4, VC3–VC2, VC1–VC0; shorts VC6 = VC5, VC4 = VC3, VC2 = VC1). C4–C7 sit across cells 1–4, and C8 goes CELL0 → GND.
- Unused pins per BQ Table 8-3: SRP/SRN/TS → VSS; DSG/CHG floating ("must be left floating"); REGSRC = BAT; ALERT used.
- R6–R10 = 100 Ω (10–1000 Ω); C4–C8 220 nF 50 V X7R 0603 (C64705, CL10B224KB8NNNC; ≥ 0.1 µF, and bias is ≤ 4.2 V, so no meaningful derating); RC = 22 µs ≤ 200 µs.
- R11 = 100 Ω, inside Rf 50–1000 Ω; the drop at 146 µA is 15 mV. C9 2.2 µF nominal (DC bias: D2-08). REGSRC tied to BAT is allowed (BQ §9). R10 and R11 are separate resistors from BAL4, as TI shows.
- D5 orientation: K = CELL0, A = GND (motor_board.py line 126). KiCad `D_SOD-323` pad 1 at x = −1.05 with the silk bar at x = −1.61, so pad 1 = K. Correct. Current ratings: IF 200 mA continuous and IFSM 600 mA cover the ≈ 80 mA hot-plug peak. Leakage is irrelevant at ≈ 0 V bias (see D2-02).
- BAT54WS C124205 = Diodes BAT54WS-7-F (r6_parts_lookup.md line 74), matching the datasheet in `datasheets/`.

**U7 ALERT / W_nFAULT**: both outputs are open-drain (INA239 pin 3; DRV8323 Table 6-4 nFAULT "OD"). R42 10 k → +3V3 = U7 VS, so ALERT stays inside VS + 0.3 V. The sink current is 0.33 mA. ALERT is inactive at reset (reset thresholds cannot trip; CNVR = 0). Discharge current makes IN+ (VBAT_PACK) > IN− (VBAT), which is a positive shunt voltage, so SOVL is the correct limit.

**J1 (BOOMELE 2×10 1.27)**: the pin list matches DESIGN §3.5 exactly (1/2/13 +5V; 3/4/12/14/20 GND; 5 MB_TX, 6 MB_RX, 7 W_ARM, 8 NRST, 9 SWDIO, 10 SWCLK, 11 VBAT_SNS, 15 SDA, 16 SCL, 17 ALERT, 18/19 NC). The custom footprint is listed as to-be-drawn in BOM.md "Before ordering" and DESIGN §3.5. W_ARM has R41 100 k to GND and goes to PD2 (FT) and U6 1B/2B/3B.

**J4**: pins 1–5 = BAL0…BAL4. `JST_XH_S5B-XH-A_1x05_P2.50mm_Horizontal` exists with pads 1–5.

**Power LED**: D3 pin 1 = K = GND and pin 2 = A = LED_A, with KiCad LED_0603 pad 1 = K. (5.05 − ~2 V) / 1 kΩ ≈ 3 mA.

**Pin completeness**: U1 64, U2 49, U3/U4 41, U5 5, U6 14, U7 10, U8 21, U9/U10 8, U11/U12 5, Q1–Q7 5, J1 20, J2/J3 7, J4 5. All pins are present. No dict literal has a duplicate pin key (checked with `ast`). 179 refdes, all unique.

**NC pins, each allowed by its datasheet**:
- DRV8323RH pin 46: "NC … can be left floating or connected to system ground".
- DRV8323RH pin 32 GAIN open = Hi-Z (> 500 kΩ) = 20 V/V (EC table "GAIN = Hi-Z 19.4 20 20.6").
- DRV8316CR pins 1 and 24: "NC … No connection, open". (On the CT variant pin 24 is VSEL_BK, so the fitted part must be the CR; the BOM says DRV8316CRRGFR.)
- BQ76907 DSG/CHG: Table 8-3.
- TPS22945 pin 3 OC: open-drain flag output. ON is active-high (Device Comparison table) and tied to VIN.
- 74LVC08 4Y (pin 11) is an output, and its inputs 4A/4B go to GND per SCAS283 "unused inputs … held at VCC or GND".
- AP2112K SOT-25 pin 4: "NC".
- J1 18/19: spare.

**Pinouts**:
- SN74LVC08A PW (1A1 1B2 1Y3 2A4 2B5 2Y6 GND7 3Y8 3A9 3B10 4Y11 4A12 4B13 VCC14).
- SN74LVC3G17 DCU (1A1 3Y2 2A3 GND4 2Y5 3A6 1Y7 VCC8).
- TPS22945 DCK (VOUT1 GND2 OC3 ON4 VIN5).
- DRV8323RH RGZ Table 6-4, all 48 pins plus PAD.
- DRV8316CR Table 6-1, all 40 pins plus PAD ("must be connected to analog ground").
- All of these match the netlist.

**Two-connection nets (68)**: each was reviewed and is intended:
- balance taps BAL0–3; BAT_NEG
- the BMS I²C and ALERT lines (pull-ups on the compute board)
- BMS_REG; BOOT0; BUCK_CB; LED_A
- the charge-pump nets (U2/L/R CPH, CPL, CP, VCP); U2_DVDD
- the strap nets U2_MODE, U2_IDRIVE, U2_VDS
- the gate nets W_GHx and W_GLx; INHx for all three motors; W_INLx (U6 → U2)
- W_SNx via net-ties; W_SOx (→ ADC)
- L/R_SOx (→ 330 Ω); L/R_SWBK
- the chip selects L_nCS and R_nCS (internal pull-up); INA_nCS (see D2-04)
- MB_TX/RX; L/R_S1–S3 (buffer → timer)

No floating inputs beyond D2-04 and D2-12. DRV8323/DRV8316 INHx/INLx and SCLK/SDI have internal pull-downs. DRV8316 nSCS has an internal pull-up.

**Decoupling on the right net**:
- U1: VDD × 4 C60–C63 plus C64 4.7 µF; VDDA/VREF+ (+3V3A) C65, C71 and C66 4.7 µF.
- U2: VM C24 plus C25/C26 ≥ 10 µF (DRV8323 "0.1 µF … and ≥ 10 µF"); VIN C27; DVDD C22 1 µF; VREF C23 0.1 µF; VCP C21 to VM; CB C28 0.1 µF CB–SW; CPH–CPL C20 47 nF 50 V.
- U3/U4: VM 2 × 100 nF plus 2 × 10 µF; CP 1 µF to VM; CPH–CPL 47 nF; AVDD 1 µF; VREF 100 nF.
- U5: in C69, out C70. U6: C40. U7: C3. U8: C9 and C11. U9/U10: C47/C50. U11/U12: C45/C48 (VIN) and C46/C49 (VOUT).

**Pull-ups and pull-downs go to the right rails**:
- R42 → +3V3 (same rail as U7 VS).
- R301/R401 → own AVDD (DRV8316C: "pulled to > 2.2 V on power up").
- R50 DRV_OFF → +3V3. The PC14 sink of 0.33 mA is within its 3 mA limit.
- R54–R59 → +3V3. R43/R52/R53 NTC pull-ups → +3V3 (ratiometric with +3V3A).
- R40/R41/R47–R49/R61 → GND.

**No +5V or VBAT on a 3.3 V-only pin**:
- +5V reaches only U5, J1, the LED, the R20 FB divider, and JP pin 3 → TPS22945 VIN (≤ 5.5 V) → J2/J3 pin 1.
- 5 V sensor outputs land on U9/U10 inputs (5.5 V-tolerant per 3G17) and on the 4.7 k pull-ups to +3V3 (≈ 0.36 mA back-feed per line).
- The motor NTC lines go to PF0/PF1, which are FT_fa/FT_a (ST Table 12; abs max VDD + 4 V), so a VS–TEMP short at 5 V is survivable.
- VBAT reaches the MCU only through the 68k/10k dividers (3.23 V at 25.2 V).

**Footprints**: all 29 non-custom footprint names exist in KiCad 10:
- `CP_Elec_10x10.5`
- `C_0402/0603/0805/1206`, `R_0402/0603/1206/2512_6332Metric`
- `JST_SH_SM06B-SRSS-TB_1x06-1MP…` (pads 1–6 plus "MP"), `JST_XH_S5B-XH-A…Horizontal`
- `D_SMA`, `D_SMB`, `D_SOD-123`, `D_SOD-323`, `L_Changjiang_FNR5040S`
- `SolderJumper-3_P1.3mm_Bridged12…` (pads 1/2/3), `LED_0603_1608Metric`, `NetTie-2_SMD_Pad0.5mm`
- `PQFN-8-EP_6x5mm…Generic` (pads 1–5), `QFN-20-1EP_3.5x3.5mm…EP2x2mm` (EP 21)
- `Texas_RGZ0048A_VQFN-48…` (EP 49), `LQFP-64_10x10mm`, `MSOP-10_3x3mm`, `TSSOP-14_4.4x5mm`, `VSSOP-8_2.3x2mm`
- `SOT-23-5`, `SOT-353_SC-70-5`, `TestPoint_Pad_D1.0mm`

All four thumbsup: footprints (TI_RGF0040E, R_2512_HoLR_1-4mR, BOOMELE_1.27-2x10P_SMD, SolderPad_*) are listed as to-be-drawn in BOM.md "Before ordering" item 2. The solder pads are listed generically.

**Polarised parts**: KiCad pad 1 = cathode on SMA/SMB/SOD-123/SOD-323/LED, and the netlist has pin 1 = K for D1 (VBAT), D2 (BUCK_SW), D3 (GND), D4 (RPP_G) and D5 (CELL0). C1 pin 1 "+" = VBAT, and CP_Elec pad 1 = +.

**Designators vs docs**: every refdes named in DESIGN.md, BOM.md and README.md exists in the netlist (regex cross-check, ranges expanded). All values quoted in DESIGN §3.1–3.5 match the netlist: R1, D4, RS4, R2/R3, C2, D1, C1, R4/R5/C10, D3/R62, R6–R11, C4–C9, C11, D5, C20–C30, R20/R21, L1, D2, R22–R27, C41–C44, R40–R49, TH1, C300–C308, R300/R301, R70–R72/C80–C82, R80–R82/C90–C92, JP1/JP2, U9–U12, C45–C50, R52–R59, C60–C73, R60/R61/R63/R64. The one exception is D2-06. BOM.md totals "158 placed parts, 52 lines" match the script output.

**bom.csv**: the value text is consistent within every line. Every placed part has an LCSC number (the script check passes; SolderPads, TestPoints, NetTies and Jumpers are correctly excluded).

## Verdict

BLOCKER 0 · MAJOR 1 (D2-01) · MINOR 5 (D2-02 … D2-06) · NOTE 11
