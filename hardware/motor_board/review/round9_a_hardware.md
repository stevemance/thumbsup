# Round 9 / A: hardware (rev I), schematic-capture readiness

Scope: rev I's hardware changes (C14 → 100 nF 100 V 0805; R33 100 k in the header VBAT_SNS branch), rev I's
operating-envelope / loaded-bounce documentation (the "60 mΩ aged, ~0 °C" C1 ESR), then one more independent pass over every
circuit block.  No design file was edited.

**Snapshot.**  I copied the package to `/tmp/r9a/motor_board` at the start of the review.  While I worked, the live package was
edited (00:24: DESIGN §3.4/§3.5 item 3 R33 wording, §6.10 C14 crack rule, J1.11 pin name `VBAT_SNS_H`, "53 → 54 mJ", sim
docstring / spice README bounce wording).  I re-copied the live package to `/tmp/r9a/live` and re-checked it: `motor_board.py` gives
"230 refs (198 placed components), 158 nets, 66 BOM lines, checks: OK" with nets.md / netlist.csv / bom.csv / mcu_pinmap.md
byte-identical to the live files, and `sim_hotplug.py` reproduces `hotplug.out` byte-identically.  Findings below are against the live
(00:24) state; two items I would otherwise have raised (R33 not in the compute-board requirements, C14 not in the flex-crack rule) are
already fixed there and are listed as verified.

Probes (in `/tmp/r9a/probe/`, hardware venv, importing `spice/sim_hotplug.py` unchanged):
* `bounce_esr.py`: loaded bounce (20 A, stiff pack 20 mΩ / 50 nH, C18 100 nF), off 0.1/0.3/0.8 ms, C1 ESR 60/78/100/120 mΩ,
  typical and minimum UVLO; plus 30 A load and 77 µA gate-current variants.
* `c13bias.py`: soft-start closure with C13 = 22/15/13 nF (DC-bias derating) × gate current 60/77 µA × nominal/stiff pack.

References: [ZK] Panasonic ZK series sheet (datasheets/EEHZK_Panasonic_C278516.pdf, 31-May-19), [LM] SNOSDE5A, [DRV23] SLVSDJ3D,
[DRV16] SLVSH07, [INA] INA239, [BQ] BQ76907, [AP] AP2112K DS39724, [LVC] Diodes DS35124, [HYG] HYG015N04LS1C2 V1.0,
[D] DESIGN.md rev I (live), [N] design/motor_board.py / nets.md, [S] spice/hotplug.out, arm.out.

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R9A-01 | MINOR | [D §1 Environment, §5 hotplug row, §7.2]; `sim_hotplug.py` bounce cases "60 mOhm ~ 0 C"; review/round8_c18_sweep.md row "60 mΩ (aged, ~0 °C)" | **The 60 mΩ "aged, ~0 °C" C1 ESR has no basis in the datasheet, and the conservative reading of it moves the envelope's worst loaded bounce from 3.37 to ~3.5–3.8 V/µs.**  [ZK] gives three ESR limits for EEHZK1V331P (size G): **20 mΩ** initial at 100 kHz / +20 °C (characteristics list, note *2); **≤ 200 % of the initial limit = 40 mΩ** after endurance (4000 h / 125 °C); and **0.3 Ω after endurance at −40 °C** ("ESR after Endurance (Ω / 100 kHz)(−40 ℃) … G 0.3").  There is no 0 °C figure and no ESR–temperature curve.  The design pairs the aged 20 °C limit (40 mΩ) and the aged −40 °C limit (300 mΩ) as limits, so the 0 °C point must be interpolated between them: log-linear in T gives 40 × 7.5^(20/60) = **78 mΩ**; Arrhenius-like (ln ESR linear in 1/T, the usual electrolyte behaviour) gives 40 × 7.5^0.46 = **~100 mΩ**.  60 mΩ (×1.5 over 20 °C, against ×7.5 over 60 °C) sits below both and is only reachable with a strong knee near −40 °C.  That is plausible for a typical part but not derivable as a limit.  **Conclusion survives**: at 78–100 mΩ the loaded bounce stays under the DRV8316's 4 V/µs, with 6–11 % margin instead of 16 %.  If the ESR at 0 °C is 120 mΩ, the margin is 3 %. | [ZK] p.1 Endurance / "ESR after Endurance" table; p.2 characteristics list (ESR*2 = 20 mΩ, 100 kHz / +20 °C).  `bounce_esr.py` (stiff pack, 20 A, C18 100 n; typical and minimum UVLO identical): 60 mΩ 2.14 / 3.37 / 3.37 V/µs (0.1/0.3/0.8 ms, = hotplug.out); **78 mΩ 2.36 / 3.54 / 3.56**; **100 mΩ 2.58 / 3.76 / 3.75** (= sweep table's 100 mΩ row); 120 mΩ 2.76 / 3.88 / 3.88.  30 A load: 3.40 (78) / 3.59 (100); 77 µA gate: 3.53 (78).  VM before re-close 4.4–9.7 V | Replace the "0 °C" cases in `sim_hotplug.py` with 100 mΩ (datasheet-interpolated aged limit at 0 °C) and quote the envelope's worst loaded bounce as **≤ 3.76 V/µs** in §1/§5/§7.2 and the sweep note, with the basis ("interpolated between [ZK]'s aged 20 °C and −40 °C limits").  If you keep 60 mΩ, label it as a typical-curve estimate, not a limit.  No hardware change |

## Notes

| ID | Sev | Finding | Evidence / action |
|---|---|---|---|
| N-01 | NOTE | **R33: effect on the two readings (asked for in scope).**  *PA3 (motor MCU):* with the header open, or with a high-impedance compute ADC, there is no change.  An ADC-pin leakage of I adds I × 8.72 kΩ: 1 µA gives +8.7 mV (0.4 %).  A compute-board pull-down of 50–80 k in reset gives **−5.5 to −4.6 %** (the "< 6 %" claim holds; −14.8 % without R33).  A compute pin mis-driven to 3.3 V or 0 V gives +4.3 % / −8.0 % at 16.8 V.  An unpowered compute board (ESD clamp ~0.3 V) gives ~−8 %.  All are bounded, and the 18.5 V coast uses the INA239 VBUS reading, so none is a protection issue.  *Compute board:* it now sees a **108.7 kΩ source** (100 k + 68 k ∥ 10 k).  With the pad pulls off, a high-impedance input and ~10 nF at the pin (as now required in §3.5 item 3), the DC reading is exact apart from its own leakage.  At 1 µA (the typical RP2040 max pad leakage; **UNVERIFIED**, the RP2040 datasheet is not in the package), the error is ±0.11 V at the pin = **±0.85 V at the pack**.  If the pad pull-down is left on, the reading is **÷3**.  The RP2040 ADC's switched-capacitor input is specified as a minimum input impedance (UNVERIFIED value).  Free-running near 500 ksps with only 10 nF, it can load a 109 k source noticeably, so sample slowly or average. | Motor board correct as drawn.  Suggest adding one line to §3.5 item 3: "source impedance ≈ 109 kΩ: pads' digital input and pulls disabled; accuracy is set by the pin leakage (≈ ±0.9 V pack at 1 µA): use it for a coarse check and take precise pack voltage from the INA239 value in the heartbeat" |
| N-02 | NOTE (UNVERIFIED derating) | **C13 DC bias is not in the soft-start spread.**  C13 (22 nF 50 V X7R **0402**, C1532) sits at the gate voltage, and by the end of the ramp that is ~VBAT + 5–12 V ≈ 20–29 V.  A 50 V 0402 X7R loses a sizeable share of its capacitance there, so the late ramp is faster than the 22 nF sim.  Bounded with a flat 15 nF / 13 nF: the ramp becomes 3.2 / 3.7 V/ms at 60 µA and **4.3 / 4.9 V/ms at 77 µA**.  **Q7's peak power becomes 24–27 W / 31–36 W** (against the documented 16 W / 21.5 W), while the energy stays **52 mJ** and the VM dV/dt stays ≤ 0.009 V/µs.  The energy is unchanged and the pulse gets shorter (~4 ms), so this stays well inside a 150 A PDFN 5×6 FET's capability (Rjc 2 °C/W).  Not a defect, but §3.1/§4/§5 quote "21.5 W at the max gate current" as the upper bound | `c13bias.py`.  Optional: C13 as 22 nF 50 V 0603 X7R (less derating), or quote "≤ ~35 W peak incl. C13 DC bias" |
| N-03 | NOTE (UNVERIFIED, firmware) | **BQ76907 TS tied to VSS** is TI's unused-pin termination ([BQ] Table 8-3: "TS: if not used, … connected to pin 11 (VSS)").  In thermistor mode the pin then reads 0 Ω (= very hot).  If the OTP defaults enable the TS-based OT/UT protections, the compute board will see BMS_ALERT and fault flags until it disables them or sets TS to ADCIN mode.  The defaults are in the TRM, not in the package | §8 BQ76907 row: "disable TS temperature protections (TS is tied to VSS)".  No hardware change |
| N-04 | NOTE | **Concurrent rev I doc edits verified**: §3.4 now says the header gets VBAT_SNS only through R33.  §3.5 item 3 asks for ~10 nF at the compute ADC pin with the pulls disabled.  §6.10 adds C14 (the one ceramic across the unswitched pack) to the flex-crack orientation rule.  J1.11 is named VBAT_SNS_H.  Q7 energy reads 54 mJ (hotplug.out 53.5–55.8 mJ).  §7.2's bounce range reads "0.1–1.2 ms (simulated range)". | `diff` of the start snapshot against the live files; live outputs regenerate byte-identically |

## Re-verification by block (independent pass)

* **Rev I C14:** C28233 = Samsung CL21B104KCFNNNE, 100 nF ±10 % **100 V X7R 0805**, JLC Basic, stock 1.69 M (JLC API,
  2026-09-24).  VS decoupling ≥ 22 nF ([LM] 6.3), which leaves ~85 nF at 16.8 V bias.  At plug-in, C14 rings with the lead (Z0 = √(50 nH / 100 nF) = 0.71 Ω, lightly
  damped) to ≤ ~2 × 16.8 = 34 V.  That is below Q7's 40 V BVDSS and U13's 60 V recommended maximum.  When the switch opens under load (UVLO trip at a bus of ≤ 10.1 V),
  BAT_IN ≈ VBAT + 0.8 + BV(Q7, ~44–48 V) ≈ 53–59 V.  That is within U13's VS and EN/UVLO 65 V absolute maximum ([LM] 6.1), and EN sees ≤ 7.8 V behind the divider.  The avalanche energy is
  ~0.1–0.2 mJ per event against EAS 370 mJ, and [HYG] note * says "repetitive rating; pulse width limited by max junction temperature".
* **Rev I R33:** see N-01.  The 0402 100 k (C25741) sees ≤ 2.2 V.  Injection into an unpowered compute board is ≤ ~20 µA.
* **Power entry / switch:** the U13 DDF pinout, OV → GND (never trips), C12 220 nF ≥ 0.1 µF VCAP–VS (≤ 13.9 V on a 25 V part), D4
  12 V against the 15 V GATE–SRC absolute maximum, and the D10 / C13 / R32 polarity all match [N].  UVLO recomputed from [LM] 6.5: off
  1.14 × 115/15 + 3 µA × 100 k = 9.04 V (7.7–10.1 V), on 9.81 V (≤ 10.8 V).  Buck nSHDN (R4/R5 with the [DRV23] 1.25 V threshold and
  −1/−4.2 µA pin current): on 10.4 V, off 9.2 V.  Soft-start and reversed-pack results reproduce (`hotplug.out` byte-identical).
  RS4/U7: SOVL 0x76C0 × 1.25 µV = 38.0 mV = 38 A, BOVL 0x17C0 × 3.125 mV = 19.0 V, and SHUNT_CAL 0x1000 → 1.25 mA/LSB, all correct.
  ALERT is open-drain, and IN+/IN−/VBUS sit behind Q8.  D1 SMBJ20A and C1 35 V are unchanged and OK.
* **U2 straps, buck, CSA, charge pump:** the [DRV23] H/W rows give IDRIVE 75 k→AGND = 60 mA source / 120 mA sink, VDS 18 k→AGND = 0.13 V
  (Hi-Z = 0.6 V), GAIN Hi-Z = 19.4–20.6 V/V, and MODE 47 k = 3x PWM (§8.3.1.1.2, "INLx = 0 → Hi-Z").  nSHDN abs max is −0.3 V to V(VIN), and the divider gives 1.9 V.
  CVIN is spec'd as 1–10 µF VM-rated (C27 2.2 µF 50 V), CBOOT 0.1 µF (C28), FB 0.765 × 6.6 = 5.05 V.  VCP 1 µF / CPH–CPL 47 nF are 50 V parts.
  VREF = +3V3, ratiometric with the ADC.
* **Interlock and ARM:** U6/U14 pinouts and pull-downs are as in [N].  [LVC] VT+ max interpolates to 2.15 V at 3.3 V (2.00 at 3.0 V, 2.74 at 4.5 V),
  against 2.50 V armed minimum ([S] arm.out, 85 °C, 250 Hz).  VT− max is 1.33 V.  Disarm times are 52–164 ms.  `arm.out` reproduces byte-identically.  The
  ≥ 0 °C envelope does not change the ARM results (the BAT54S leakage at 0 °C is below the 25 °C case).
* **Bridge:** HYG pads S 1–3 / G 4 / tab D; high-side drains on VBAT, VDRAIN Kelvin; SPx on the FET-source side, SNx via NT1–NT3.
  VGS ±20 V against a gate drive of ≤ 12.5 V.
* **U3/U4:** [DRV16] 7.1 VM abs max 40 V and ramp 4 V/µs; ground-pin difference ±0.3 V (the partition must hold it); CVM1/CVM2, CCP 1 µF,
  CFLY 47 nF, CAVDD 0.7–1.3 µF effective (C305 + C306 ≈ 1.0 µF at 3.3 V), CBK 22 µF ≥ 10 V with RBK 22 Ω 1206 (~0.13 W in resistor
  mode until BUCK_DIS); AVDD load ≤ 30 mA (R301 0.33 mA + VREF); VREF/ILIM 2.8 V–AVDD; nFAULT/SDO open-drain ≤ 5.5 V; push-pull SDO
  2.2–5.5 V.
* **Sensors:** the TPS22945 ON = VIN (active high), SN74LVC3G17 and BAV99 pinouts, the 2.2 k series NTC resistor and the DNP 1 nF filters are as in [N].  At 5 V (JP 2–3) the 4.7 k
  pull-ups back-feed +3V3 with at most 2.2 mA, which the ≥ 100 mA +3V3 load absorbs.
* **BQ76907:** 4S wiring per Table 7-1.  The unused pins follow Table 8-3 (N-03 on TS).  [BQ] 6.1 limits hold: VC(n) ≥ VC(n−1) − 0.3, VC0 ≥ VSS − 0.3
  (−0.11 V at 22 A), and ALERT/SCL/SDA ≤ VSS + 6 V; ALERT is open-drain (§7.4.8).  The C9/R11 hot-plug pulse and D5 are unchanged.
* **U5:** AP2112K-3.3, VIN/EN on +5V, 1 µF in/out ([AP]: "stable with 1.0 µF").  Its fold-back current limit is 50 mA at VOUT = 0 V ([AP] ISHORT).  The
  +3V3 loads are capacitive, resistive or current-limited (TPS22945 100–200 mA), and nothing pre-biases the output as a load at start-up (only the
  sources R17/MB_RX and the 5 V pull-up back-feed), so start-up is not blocked.  It dissipates ~0.2 W.
* **MCU support:** VDD 4 × 100 nF + 4.7 µF; VDDA/VREF+ on +3V3A (0 Ω); VBAT to +3V3; NRST 10 k + 100 nF (2.75 V against a 50 k
  RP2040 pull-down); BOOT0 10 k; PC14 sinks only 0.33 mA and sources ~66 µA into the two DRVOFF pull-downs (backup-domain pin
  limits).  PA3 sampled with C68 at the pin (charge-sharing error 5 pF / 100 nF).
* **Header:** the J1 pin map matches §3.5 (pin 11 = VBAT_SNS_H), with 3 × +5 V and 5 × GND.  W_ARM_CLK has R18 and sits next to GND pin 20.  MB_RX has R17 (2.75 V
  against a 50 k pull-down).  SWD is direct.
* **Loaded-bounce envelope (rev I §1/§7.2):** see R9A-01.  The sim's load stays constant down to 5 V.  A spinning drum's BEMF would hold the bus
  higher through the body diodes, so the collapse to ~4.5 V and the step that follows are the conservative (low-speed, current-limited) case.

## VERIFIED OK

* C14 100 nF 100 V X7R 0805 (C28233, Basic): value, rating, VS min capacitance, plug-in ring ≤ ~34 V, loaded-opening ring ≤ ~59 V < 65 V
  U13 abs max; now covered by the §6.10 crack rule.
* R33 100 k: PA3 shift ≤ 5.5 % with a 50–80 k compute pull-down, ≤ 8 % in every other compute-pin state; 18.5 V coast from the INA239;
  compute-side requirements now in §3.5 item 3 (N-01 adds the accuracy caveat).
* C1 ESR limits read from [ZK]: 20 mΩ new / 40 mΩ aged at 20 °C, 300 mΩ aged at −40 °C (the design's −40 °C corner is correct);
  2.8 A rms rating at 100 kHz / 125 °C.
* Power entry: U13 pinout, abs max (VS, EN, SRC, GATE–SRC, VCAP–VS), UVLO and buck-cutoff arithmetic, soft-start/reverse/re-close sims.
* INA239 limits and codes, pinout, ALERT open-drain wired-OR with U2 nFAULT.
* U2: 49-pin map, straps against the H/W EC rows, buck components against the external-component table, charge pump, VREF.
* U6/U14/D9/C15/C16/R41/R19 ARM network; U14 thresholds at 3.3 V; arm.out.
* Weapon bridge pinout, gate-drive margins, shunt Kelvin arrangement.
* U3/U4 external components against [DRV16] Table 8-1 and the §7.1/7.3 limits; AVDD loading; SDO/nFAULT levels; buck resistor mode.
* Sensor supply switches, Schmitt buffers, NTC clamp and series R; 5 V option back-feed.
* BQ76907 wiring, unused-pin terminations, I/O and cell-input abs max.
* AP2112K start-up (fold-back) and dissipation; MCU supply, reset, boot, backup-domain pin use.
* J1 pin functions and pull states; netlist / BOM / pinmap / hotplug.out / arm.out / calcs.md all regenerate byte-identically (live
  00:24 state).

**Verdict: 0 BLOCKER, 0 MAJOR, 1 MINOR, 4 NOTE.  Not clean (R9A-01: the 0 °C C1 ESR in the envelope claim is not
datasheet-supported; the datasheet-interpolated value still keeps the loaded bounce under 4 V/µs, ≤ 3.76 V/µs; documentation/sim-case fix
only).**
