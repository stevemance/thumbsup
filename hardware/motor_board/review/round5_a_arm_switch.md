# Round 5 / A: dynamic ARM (rev E) and power entry (D4, UVLO, R15)

Scope: the rev E changes to the dynamic ARM (C15 470 nF, C16 2.2 µF, R41 47 k, U14 74LVC1G17 → W_ARM_S), D4 (12 V
gate–source zener on Q7/Q8), the R13/R14 100 k / 22 k UVLO, and the rest of the ARM path and power entry.  No design file
was edited.  All simulations were run on copies in `/tmp/r5a/` using KiCad's libngspice (`hardware/tools/spice/ngspice_shared.py`):

* `arm/arm.py` (ARM netlist), `s1_level.py` (armed level, arm time, edges), `s2_disarm.py` (disarm times, tolerance corners),
  `s3_pause.py` (float-from-high, pause tolerance), `s4_faults.py` / `s5_c16open.py` (single faults plus the boot self-test sequence);
* `d4/sim_d4.py` (soft-start and steady Vgs with a realistic zener knee), `sim_sag.py` / `sim_sag2.py` (pack sag with and without D4);
* `spice/sim_hotplug.py` (unchanged copy, re-run).

References: [DS] Diodes DS35124 Rev 8-2 (74LVC1G17), [BAT] Nexperia BAT54S (1 July 2022), [LM] TI SNOSDE5A (LM74502),
[Z] CJ MMSZ5221B–5259B (A, Jun 2011), [HYG] HYG015N04LS1C2, [D] DESIGN.md rev E, [N] design/motor_board.py.

## Models

* **BAT54:** `d(is=2e-7 n=1 rs=1.5 cjo=10p m=0.4 vj=0.35 eg=0.69 xti=2 bv=30)`.  Checked against [BAT] Fig. 1/2: IR at 0.5–3 V is
  0.17 µA at 25 °C and 21.4 µA at 85 °C (the Fig. 2 curves show ~0.25–0.4 µA and ~18–25 µA at low VR).  V_F(1 mA) is 0.225 V at 25 °C
  (≤ 0.32 V max per Table 7).  Only 25 °C / 25 V has a maximum (2 µA, versus ~1.5 µA typical from Fig. 2, a ratio of 1.3).  "Worst"
  runs therefore add 11 µA (1.5 × typ) or 21 µA (2 × typ) of extra reverse leakage across each diode at 85 °C.
* **ARM circuit:** a square-wave source through R_src (50 Ω, or 1 kΩ) drives W_ARM_CLK, with R18 100 k and 5 pF on that node.
  C15 couples it to ARM_AC.  D1 goes GND→ARM_AC and D2 goes ARM_AC→W_ARM.  W_ARM has C16, R41 and 10 pF.  Amplitude is 3.3 V
  (or 3.0 V).  After the stop, the source is held high, held low, or disconnected ("float").
* **U14 thresholds:** [DS] p.4/5 tabulates VCC = 3 V only (VT+ 1.50–2.00 V, VT− 0.80–1.30 V at −40…85 °C and 0.80–1.33 V at
  −40…125 °C) and 4.5 V.  Linear interpolation to VCC = 3.3 V gives VT+ ≤ 2.15 V and VT− 0.88–1.43 V (UNVERIFIED: an
  interpolation).  Crossing times are reported at 1.45 / 1.33 / 0.88 / 0.80 V.
* **MMSZ5242B:** [Z] specifies only VZ 11.4–12.6 V at IZT 20 mA, ZZT ≤ 30 Ω, ZZK ≤ 600 Ω at 0.25 mA, and IR ≤ 1 µA at 9.1 V.
  Two models were fitted.  "Worst low": 11.4 V at 20 mA with the 600 Ω knee (nbv 5.8, rs 22), which gives 10.09 V at 60 µA.
  "Typ knee": ~177 Ω at 0.25 mA, which gives 10.66 / 11.26 / 11.86 V at 60 µA for the min / nom / max part.
* **LM74502 (sag sims):** the charge pump sources 300 µA into C12 below V_off (11.0 / 12.4 / 13.9 V) and sinks 5 µA above it.  The
  60 µA gate source is fed from VCAP and gated by EN and VCAP UVLO; it cannot exceed VCAP.  A 2 Ω GATE–SRC sink is active when EN is
  low.  An optional GATE→VCAP diode is included in some runs (UNVERIFIED whether the IC has one).  The rest of the netlist is as in
  `sim_hotplug.py`.

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| **R5A-01** | **MAJOR** | [D §3.5 item 4] boot self-test; [D §7.16]; [D §8] W_ARM_S row | **The boot self-test does not detect an open (or high-value) R41, although §3.5 and §7.16 say it does.  With R41 open, the ARM is no longer dynamic: once armed it never disarms at room temperature.**  The test holds W_ARM_CLK high for 300 ms and then low for 300 ms, starting from a discharged C16.  That is a single rising edge, which lifts W_ARM only to C15/(C15+C16) × swing ≈ 0.56 V, below U14's VT+ min of 1.5 V.  So W_ARM_S reads low in both phases whether R41 is fitted or not, and the test passes.  In service, only D2's reverse leakage (~0.2 µA at 25 °C, i.e. ~0.1 V/s on 2.2 µF) discharges C16.  A hung compute board, a stuck-high or stuck-low pin, or an unplugged header then leaves the weapon hardware-armed indefinitely.  Only the motor MCU's firmware timeout and IWDG remain.  When hot the fault is masked (the 85 °C diode leakage alone disarms in 120–150 ms), so it may pass a warm bring-up test too.  The same blind spot covers a wrong R41 value (e.g. 470 k, a ~1–1.5 s hold).  **C16 open** is caught only by luck: W_ARM then follows the clock, so the self-test's rising edge gives a 10–19 ms W_ARM_S pulse, which a polled heartbeat bit can miss.  In service, INLx is then chopped at the toggle rate. | `s4_faults.py`, self-test sequence (1–301 ms high, 301–601 ms low), then 500 Hz toggling, then stuck high, then toggling, then stuck low.  **R41 open, 25 °C:** self-test high-phase max W_ARM 0.58 V, end of the low phase 0.55 V (both below VT+), so the test PASSES.  Toggling gives 3.17 V.  **Stuck high: no disarm within 300 ms; stuck low: no disarm within 300 ms.**  R41 open, 85 °C: disarm 150 / 122 ms (leakage only).  Healthy board: self-test max 0.56 V; disarm 158 / 128 ms (25 °C).  `s5_c16open.py`, C16 open: W_ARM > 1.33 V for 19.2 ms (25 °C) or 10.2 ms (85 °C) after the self-test edge, then 0 V.  C15 short IS caught (high phase 3.14 V). | Make the self-test **dynamic and timed**.  (1) Toggle at 500 Hz for ≥ 50 ms: expect W_ARM_S high (tests C15 open, D9, C16 short and U14 stuck low).  (2) Hold high: the motor MCU timestamps the PD2 falling edge (EXTI) and reports the elapsed time.  Expect ~25–250 ms: faster means C16 open or low, slower or never means R41 open or high, and never also covers a C15 short.  (3) Re-toggle, then hold low: same window.  Report "edges seen / time to disarm" in the heartbeat instead of a sampled level.  Update §3.5 item 4, §7.16 (R41 open is not caught today), the §8 W_ARM_S row and §9 step 3.  The weapon cannot run during the test (CHxN is not commanded), and the §8 fresh-edge rule then needs the normal re-arm. |
| R5A-02 | MINOR | [D §1 Safety row, §3.2 Dynamic ARM, §9 step 3]; [N] R41/C16 comments | **The documented "disarms in 100–160 ms" is the time to 0.8 V at 25 °C only.**  U14 releases anywhere in VT− 0.80–1.33 V (0.88–1.43 V interpolated to 3.3 V), and the hot BAT54S leakage adds to R41.  The real window is roughly **30–200 ms**.  The §9 step 3 pass limit ("drops W_ARM_S within 100–160 ms, repeat with the board warm") will **fail a good board** when warm (48–100 ms at 85 °C with typical leakage), and at room temperature with a high-VT− U14 (76–95 ms stuck low / high to 1.33 V).  Likewise "rises above 2.0 V within ~10 ms" measures 10.02–10.17 ms, a coin-flip pass.  Safety is not affected: the shortest disarm still tolerates the 20 ms gap, and the longest (~190 ms) is below the 250 ms re-arm hold and the 300 ms self-test. | `s2_disarm.py`, stop after 200 ms at 500 Hz / 50 Ω, time to 1.45 / 1.33 / 0.88 / 0.80 V.  **25 °C:** high 84 / 95 / 147 / 158 ms, low 67 / 76 / 118 / 128 ms (float = low).  **85 °C typ leakage:** high 61 / 67 / 94 / 100 ms, low 48 / 53 / 76 / 80 ms.  **85 °C + 11 µA:** 41–83 ms.  **85 °C + 21 µA:** 35–71 ms.  1 kΩ source at 85 °C + 21 µA: 30–65 ms.  **Tolerance corners** (C16 ±20 %, C15 ±10 %, R41 ±1 %): 25 °C up to **190 ms** (stuck high, to 0.8 V); 85 °C + 21 µA down to **27 ms** (stuck low, to 1.45 V).  Adding U14's ±5 µA II ([DS] p.4) as a source current pushes the long end to ~210–225 ms (hand calculation). | Replace "100–160 ms" with "~30–200 ms (≈ 50–160 ms nominal, faster when hot)" in §1, §3.2, [N] R41 and the netlist header comment.  §9 step 3: pass window 25–250 ms for both stuck levels and float, cold and warm; arm within ≤ 15 ms at 500 Hz. |
| R5A-03 | MINOR | [N] net W_ARM_S (U14.4 → U6.2/5/10, PD2); [D §8] | **W_ARM_S has no defined level if U14's output stops driving** (pin 4 lifted or cracked joint, VCC or GND pin open).  The three LVC08 B-inputs and PD2 then float, and a floating CMOS AND input can sit high, which enables INLx statically.  This is a single assembly fault that can arm the hardware interlock.  The self-test would catch it only if the floating net happens to read high during the test. | [N] line 251–253: nothing else drives W_ARM_S and it has no pull-down (nets.md: `W_ARM_S: U1.55(PD2), U14.4(Y), U6.10, U6.2, U6.5`).  [DS] p.1: IOFF "disables the output" when unpowered, i.e. Hi-Z.  [LVC08]: inputs must not float. | Zero-BOM fix: configure **PD2 with its internal pull-down** (~40 kΩ; U14 drives 24 mA, so no conflict) in the §8 GPIO step.  Or add a 100 k pull-down on W_ARM_S.  (During MCU reset U14 still drives the net, and CHxN is held low by R47–R49.) |
| R5A-04 | NOTE | [D §3.2] "U14 VT+ ≤ 2.0 V", "2.74–2.83 V", "~8 edges" | **The numbers are right in substance but quoted at the wrong conditions.**  VT+ ≤ 2.0 V is the VCC = 3.0 V column; at 3.3 V it is ~2.15 V (interpolated).  2.74–2.83 V holds only for a stiff 3.3 V source.  "~8 edges": 4 rising edges already reach VT+ min (1.5 V), 6 reach 2.0 V and 7 reach 2.15 V.  "One stray edge cannot arm" is true (0.56 V).  All margins hold: the lowest armed level at ≥ 500 Hz is 2.51 V (3.0 V drive); at 250 Hz, 3.0 V drive, 85 °C + 21 µA it is 2.22 V (still > 2.15 V). | `s1_level.py` (min over the last 20 ms): 500 Hz / 50 Ω 2.78 V (25 °C), 2.85–2.91 V (85 °C); 1 kΩ source 2.60–2.71 V; 3.0 V amplitude 2.51–2.64 V; 10–90 % duty changes it by ≤ 0.05 V at 500 Hz–1 kHz; 10 kHz 2.65–3.15 V; 250 Hz 2.22–2.61 V.  Ripple ≤ 157 mV (250 Hz) and ≤ 84 mV (500 Hz). | Quote VT+ ≈ 2.15 V at 3.3 V, the armed level 2.5–2.9 V, and "≥ 4 edges".  No circuit change. |
| R5A-05 | NOTE | [D §3.1] D4 row; [N] D4 | **Vgs ≥ 10 V with D4 is typical, not guaranteed.**  The zener carries the 40–77 µA gate current, where [Z] specifies nothing but IR ≤ 1 µA at 9.1 V.  A minimum part (11.4 V at 20 mA) with the maximum knee impedance (ZZK 600 Ω) sits at 10.1 V at 25 °C, and ~9.7 V at −20 °C with a ~+0.08 %/K tempco (UNVERIFIED for this vendor).  Irrelevant for losses: [HYG] RDS(on) is 1.4 mΩ typ at 10 V and 2.0 at 4.5 V.  D4 is otherwise sound (details under VERIFIED OK).  Side effect worth one line: after a deep sag D4 has discharged C13, so on recovery Vgs dips while C13 recharges at 2.7 V/ms.  The FETs stay enhanced. | `sim_d4.py` final Vgs: no D4 11.1 / 12.5 / 14.0 V (V_off 11.0 / 12.4 / 13.9); with D4 10.09 (worst low), 11.07–11.26 (nominal), 11.09–11.86 V (max part).  `sim_sag2.py`, 16.8 V → 9.3 / 8.5 / 8.0 V sag, recovery in 20–100 µs with 20 A still flowing: Vgs min 4.7–6.9 V with D4 (11.8–12.9 V without), Q7 peak 14–19 W for µs (11–14 W without). | Text: "Vgs 10–12 V (zener-limited)".  No change needed. |
| R5A-06 | NOTE | [D §3.1] R13/R14 and R15 rows, [D §3.1 external switch] "wait ≥ 1 s", calcs row "below the UVLO in ~1 s" | **The UVLO low end is undocumented and makes "~1 s" typical rather than worst case.**  The off threshold is 1.027 V (min) × 5.545 + I_EN·100 k; the sink has no minimum, so the floor is **5.7–6.0 V**, against the quoted 6.6 V typ / 7.35 V worst-high.  Worst decay from buck-off (up to 10.3 V) to 5.7 V, with τ = 366 µF × 5.44 kΩ ≈ 2.0 s (2.4 s with C1 +20 %), is ~1.2–1.5 s.  Consequence: the documented re-close residual (2.4–3.3 V/µs) exists for up to ~1.5 s, not 1 s.  Also, with 1 % resistors the high-end off threshold is 7.46 V, touching the buck's 7.4 V minimum off (harmless: order does not matter). | [LM] 6.5: V(EN_UVLOF) 1.027 / 1.14 / 1.235 V; I(EN/UVLO) 3 typ / 5 max µA (no min).  Re-run `sim_hotplug.py`: VM is 5.8 V at 1000 ms (typical thresholds), still above a 5.7 V minimum-threshold part. | Say "off 5.7–7.35 V (6.6 typ)" and "wait ≥ 2 s" (still no burden with a screw switch). |
| R5A-07 | NOTE | [D §7.16] | U6 single faults (an AND output, or a B-input, stuck high) enable one weapon phase without ARM.  They are not covered by any self-test.  One enabled phase cannot produce torque (the other two are Hi-Z).  At most, a low-side-on phase lets a coasting drum brake through the other phases' low-side body diodes, and only while firmware drives that CHxN.  Acceptable, but list it in §7.16 for completeness. | 3x PWM: INLx = 0 ⇒ Hi-Z ([D §2]).  U6 inputs/outputs per [N] lines 232–236. | Documentation only. |

## Answers to the brief

1. **ARM network.**  Armed level: see R5A-04, ≥ 2.51 V at ≥ 500 Hz in every case against VT+ ≤ 2.15 V.  Arm time: 10.0–10.2 ms to
   2.0 V at 500 Hz / 50 Ω (6 rising edges), 14–16 ms with a 1 kΩ or 3.0 V source, 20–32 ms at 250 Hz, ≤ 1.8 ms at 10 kHz.  Disarm:
   see R5A-02 (27–190 ms over corners).  Stuck high, stuck low and float all disarm, and float behaves exactly like stuck low (also
   when the pin floats from high: 67–128 ms at 25 °C, 35–57 ms at 85 °C + 21 µA).  Pause tolerance (`s3_pause.py`, min W_ARM during
   a gap parked low / high, 500 Hz): 20 ms → 2.29 / 2.40 V (25 °C), 2.00 / 2.19 V (85 °C + 21 µA), and 1.79 / 2.06 V at the
   C16 −20 % corner.  All are above 1.45 V, so **"< ~20 ms tolerated" holds**; the worst-case limit is ≈ 27 ms, and ≥ 50 ms at 25 °C.
   At 250 Hz a 20 ms gap leaves 1.75 V (85 °C + 21 µA).  "Arms in ~10 ms" holds (borderline for the §9 pass limit, R5A-02).
   "Disarms in 100–160 ms" does not (R5A-02).
2. **Single faults** (`s4_faults.py`, 25 and 85 °C).  None of these arms the weapon: C15 open, D1 short, D1 open (W_ARM 0.01 V
   while toggling), D2 short (−0.10…0.48 V), D2 open, C16 short, R41 short and R18 short (all never arm, fail safe), and R18 open (no
   effect with the pin driven).  Faults that remove the dynamic behaviour or arm statically:
   * **C15 short** (static arm with the pin high): caught by the self-test high phase (3.14 V).
   * **R41 open** (never disarms at room temperature): **not caught** (R5A-01).
   * **C16 open** (W_ARM_S = the clock): caught only if the 10–19 ms pulse is latched (R5A-01).
   * **U14 output stuck high, or a pin 4–5 bridge:** caught (W_ARM_S high in both phases).
   * **U14 output open or unpowered:** W_ARM_S floats (R5A-03).
   * **U6:** one phase only, no torque (R5A-07).
3. **U14 pinout:** [DS] p.1/2, SOT353: 1 NC, 2 A, 3 GND, 4 Y, 5 VCC, which matches [N] line 252 and ordering code 74LVC1G17SE-7
   (SE = SOT353, p.10).  Input 5.5 V tolerant; IOFF.  **Power-up:** C16 is discharged (R41), so the input is at 0 V.  From
   VCC = 1.65 V the output is specified low (VT+ ≥ 0.70 V at 1.65 V); below that it cannot exceed VCC, and U6, on the same rail,
   cannot pass a high either.  CHxN are held low by R47–R49 while the MCU is in reset.  After a short +3V3 dip with C16 still charged,
   U14 comes up high, but U6 stays gated by CHxN = 0 and the §8 fresh-edge rule.  OK.
4. **D4:** see VERIFIED OK and R5A-05.  D4 does not stop the charge pump reaching full enhancement: the zener takes ≤ 77 µA from
   VCAP against a 162 µA minimum pump current.  Vgs is 10.1–11.9 V (≥ 10 V typical, not strictly guaranteed).  The soft-start is
   unchanged.  In the sag case, Vgs peaks at 12.0 V with D4 versus 16.1–19.1 V without (17.4 V for the 10 V sag).
5. **UVLO:** on 7.18 V / off 6.62 V typ; worst high 7.82 / 7.35 V (7.94 / 7.46 V with 1 % resistors); off floor 5.7–6.0 V (R5A-06).
   It stays below the buck cutoff (9.2 V typ, 7.4 V min).  The R15 bleeder takes the bus below the switch UVLO in ~0.7–1 s
   typical and ~1.5 s worst.
6. **`spice/sim_hotplug.py` re-run: output byte-identical to `spice/hotplug.out`** (`diff` clean, 62 s).
7. Other: R5A-03, R5A-06, R5A-07.  Nothing else is wrong in the power entry.

## VERIFIED OK

* `sim_hotplug.py` reproduces `hotplug.out` exactly.  `design/motor_board.py` (copy) regenerates `nets.md`, `netlist.csv` and `bom.csv`
  identically ("checks: OK", 225 refs, 156 nets, 64 lines).
* BAT54S pinout ([BAT] Table 2: 1 A1, 2 K2, 3 K1/A2) vs [N] D9: D1 clamps GND→ARM_AC, D2 rectifies into W_ARM.
* U14 pinout, VCC = +3V3 with C17 100 nF, 5.5 V-tolerant input, IOFF; power-up output low.
* LM74502 pinout ([LM] Fig. 5-1 / Table 5-1) vs [N] U13.  D4 cathode at PSW_G (SOD-123 pad 1 = K), as [LM] §9 suggests
  ("a zener diode can be used between GATE to SRC pin to clamp VGS").
* ARM armed level ≥ VT+ in every case simulated: 250 Hz–10 kHz, 10–90 % duty, 50 Ω–1 kΩ source, 3.0–3.3 V drive, 25/85 °C,
  up to 2 × typical leakage.
* One edge gives 0.56 V (cannot arm); 4–7 rising edges are needed.
* Stuck high no longer holds W_ARM up (C15 < C16).  Stuck low, stuck high, float and float-from-high all disarm.
* Pause tolerance ≥ 20 ms at every corner.
* The re-arm hold (≥ 250 ms) and self-test phases (300 ms) are longer than the longest disarm (~190–225 ms).
* C15 short and U14 stuck high are caught by the self-test.  Every diode, C15-open, C16-short, R41-short and R18 fault fails safe.
* D4: the soft-start ramp is unchanged at 2.67 V/ms with any zener model (Vgs during the ramp is ~2 V, where IR ≤ 1 µA).  Steady Vgs
  is 10.1–11.9 V, below the 15 V GATE–SRC abs max, and the zener current is ≤ 77 µA.
* D4 sag clamp: Vgs ≤ 12.0 V (without D4, 16.1–19.1 V, or 13.4–15.0 V if the IC has a GATE→VCAP diode).  The recovery dip leaves the
  FETs enhanced.  In the UVLO-trip case D4 also clamps negative Vgs to −0.8 V (the model without D4 shows −6 V).
* UVLO typ / worst-high figures in calcs.md are reproduced.  UVLO stays below the buck cutoff; the bleeder behaves as documented
  (typical).

**Verdict: 0 BLOCKER, 1 MAJOR, 2 MINOR (4 NOTE).**
