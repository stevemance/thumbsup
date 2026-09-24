# Review round 7 / D: system-level adversarial review (rev G)

Reviewer role: power electronics and combat robotics, fresh eyes on the whole package.  No design
file was edited.  Board area and chassis fit are out of scope.

Inputs: DESIGN.md rev G (read end to end), design/calcs.md, design/nets.md, spice/*.out plus
`sim_hotplug.py` / `sim_arm.py` (to check what the models include), review/CHANGES.md,
review/round6_d_system.md, design/bom.csv, and these datasheets: DRV8323 (SLVSDJ3D), LM74502,
74LVC1G17 (Diodes), MT6701 and HYG015N04LS1C2.  The G474 comparator pin map comes from
`ref/STM32G474RxTx_pins.xml`.

Evidence tags: **[D §x]** DESIGN.md, **[C §x]** calcs.md, **[N]** nets.md, **[S file]** spice
output or model, **[CH]** CHANGES.md, **[DS …]** datasheet, **[X]** ST pin XML.

---

## 1. Safety chain walk-through (rev G)

| Phase | What happens | Verdict |
|---|---|---|
| Power-on | Soft-start ~2.2 V/ms.  The MCU is held in reset until the buck starts.  CHxN is pulled low by R47–R49, so INL = 0 and the weapon is Hi-Z.  W_EN is pulled down.  DRV_OFF is pulled up, so the drives are Hi-Z.  If C16 still holds charge from a quick power cycle, W_ARM_S may start high, but the "fresh edge since reset" rule blocks the weapon [D §8] | OK |
| Arming | Arming needs software toggling, ≥ 7 edges, and a firmware-qualified rising edge.  A single edge does not arm (0.58 V step on C15/C16).  The boot self-test covers the static faults | OK (timing wording: R7D-05) |
| Fight with hits | Faults are bounded by VDS OCP, INA239 SOVL/BOVL and the fault counters.  Not covered: a jammed drum (R7D-04), a weapon phase short (R7D-11) and encoder corruption (R7D-09) | gaps below |
| Brown-out / supply bounce | The logic cutoff has a 4.5 ms filter (R4‖R5 × C10).  U13 EN/UVLO has **no** filter.  Firmware folds back at 12 V, above the worst-case switch-off of 10.0 V.  A ms-scale contact bounce during spin-up resets both boards (R7D-08).  The §4 threshold is stale (R7D-01) | minor |
| Signal loss | Radio loss drops the ARM permission within ≤ 0.5 s plus 50 ms plus ~30–200 ms.  **Drives** stop only if the compute board stops sending frames.  Nothing requires it to (R7D-02) | gap |
| Compute board hang | The permission deadline stops the ISR, so ARM decays.  Frames stop, or their sequence number stops advancing, so everything coasts | OK |
| Motor MCU hang | IWDG ~20 ms, CLL → break, HardFault safe state.  A frozen weapon vector for ≤ 20 ms is bounded by VDS OCP and the latched break (AOE = 0) | OK |
| Faults | DRV8323 nFAULT + INA239 ALERT → TIM1 BKIN.  L_nFAULT → TIM8 BKIN.  R_nFAULT → EXTI → DRV_OFF.  A strap fault on MODE turns the disarmed state into a brake (R7D-06) | note |
| Disarm | W_ARM_S falls, then U6 pulls INL low → Hi-Z, and firmware forces CHxN low, so a later hardware ARM rise cannot re-enable the bridge by itself | OK |
| Power-off | Without the drum spinning, the bus decays and logic is off in ~0.1 s.  With the drum spinning, the FETs stay on and the board stays alive for seconds (R7D-07) | note |

Single points of failure beyond §7.16/§7.20: MODE strap open (R7D-06).  The GAIN pin is Hi-Z by
design, so leakage shifts the CSA gain (R7D-06).  Everything else I tried (D9 either diode short,
C15 open, C16/R41 short, R18 open, U14 VCC open, R50/R40 open) fails safe.

## 2. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| **R7D-01** | MINOR | Doc contradiction (switch UVLO) | **§4 still gives the rev F switch UVLO.**  The row reads "switch FETs off below ~7.8 V (7.0–8.6)".  Rev G changed R14 18 k → 15 k: off ~9.0 V (7.7–10.0 V), which §3.1, calcs §9, §5 and §9 step 1 all use.  The change also moved the behaviour.  At the worst-case corners the switch now opens **above** the typical logic cutoff (10.0 V vs 9.2 V).  A deep sag therefore disconnects the pack and forces a full soft-start, not just a logic reset.  The 12 V firmware foldback is what keeps BAT_IN above that level, and the package never states it as a requirement | [D §4] l.376 vs [D §3.1] R13/R14 row, [C §9] "on 9.8 V / off 9.0 V typ … off 7.72–9.97 V", [CH] R6B-01 | Fix the §4 row.  In §8 "Power budget", state that the foldback floor (12 V at VBAT) must stay above the worst-case switch-off (10.0 V at BAT_IN) |
| **R7D-02** | MINOR | Safety: signal loss / bring-up | **Radio-loss failsafe covers the weapon only, and the "tested" claim has no test.**  §3.5 item 4 ties radio freshness to the W_ARM_CLK permission.  Nothing requires the compute board to stop sending **drive** commands on radio loss.  §8's failsafe fires only when frames stop or their sequence number stops advancing, so a healthy compute board keeps the last drive command indefinitely.  Common event rules (SPARC-derived) require *all* motion to stop on signal loss; this is checked at tech inspection by switching the transmitter off.  CHANGES says R6D-07 is "≤ 0.5 s requirement, tested", but §9 has no transmitter-off step.  It also has no test for §7.5 switch-open detection or for a hung compute-board main loop.  After power-up or radio re-acquisition, nothing requires the weapon command to be seen at zero before ARM is granted | [D §3.5] item 4; [D §8] command-link row; [D §9] steps 3–6 (no radio test); [CH] R6D-07 | §3.5 item 4: on radio loss (≤ 0.5 s) the compute board sends zero drive **and** weapon commands (or stops sending frames), and grants ARM again only after the weapon command has been seen at zero.  §9 step 3 or 6: transmitter off → drive and weapon stop within X s (measure it); stall the compute main loop via a debug command → ARM falls; open the switch with the drum spinning → firmware coasts |
| **R7D-03** | MINOR | Assumption: weapon control rate | **The weapon runs at 7–8 control updates per electrical cycle at top speed, and the package never says so.**  A 28 mm outrunner is typically 12N14P, i.e. 7 pole pairs (confirm for the Repeat 2822).  25.6 k rpm (loaded) to 30.2 k rpm (no load, 16.8 V) gives **3.0–3.5 kHz electrical**.  TIM1 and the weapon CSA samples run at 24 kHz, so that is **6.9–8.0 samples per cycle**, with ~1.5 periods of compute+PWM delay = **~65–80° electrical of lag** if uncompensated.  The design moved the drives to 48 kHz for this reason, and §8 calls 5–6 updates "acceptable only below top speed".  The six-step fallback is weaker still.  Phase voltages are sampled once per TIM1 period through an 8.7 µs RC (68k‖10k × 1 nF), so each 60° floating window (~56 µs at 3 kHz) gets **~1.3 samples**.  No hardware zero-crossing path exists: only W_VC/PB11 is a comparator + input (COMP6_INP); PA4/PA5 are only COMP1/2_INM, whose + inputs PA1/PB1 are taken | [D §3.4] TIM1 24 kHz, "weapon uses the samples at the TIM1 peak"; [D §3.2] R22–R27/C41–C43; [D §8] CPU-budget row; [S sim_weapon_spinup] 25 573 rpm; [X] PA4 COMP1_INM, PA5 COMP2_INM, PB11 COMP6_INP | State the weapon's pole pairs, electrical frequency and update ratio in §3.2/§4.  In §8 pick the top-speed strategy: sensorless FOC with 1.5-period angle compensation + PLL (a slowly varying drum makes this workable), or six-step with interpolated ADC zero-crossing.  Add a §9 step 6 check that the drum reaches its speed at the rated current without losing sync |
| **R7D-04** | MINOR | Assumption: weapon heat / hits | **A jammed or stalled drum breaks the "0.5 s bursts" assumption, and §8 has no stall rule or FET over-temperature action.**  calcs §11 treats the weapon bridge as "thermal-mass limited, not steady state".  A drum jammed against an opponent or a wall, held at the 20 A FOC limit, runs continuously.  One half-bridge carries ~20 A: 0.4–0.8 W conduction per FET + ~1.1 W switching, ≈ **2–2.5 W in one FET pair and ~3–4 W in the bridge**, + 0.4 W in its shunt.  A PDFN 5×6 on a small 4-layer board at ~40–60 °C/W is on the order of +100 °C within tens of seconds.  The 2822 winding sees 20² × ~0.05–0.1 Ω ≈ **20–40 W**.  At zero speed the sensorless observer has no BEMF, so restart attempts repeat.  TH1 exists but only feeds telemetry (10 Hz).  "Derate on OTW" exists only for the DRV8316 | [C §6, §11]; [S sim_weapon_spinup] R = 0.10 Ω; [D §3.2] TH1; [D §4b] temperatures at 10 Hz; [D §8] (no stall/TH1 rule) | §8 weapon row: current at the limit with speed below ~X rpm (or no observer lock) for > ~0.3–0.5 s → coast, report, and allow a limited number of restart attempts.  TH1: derate above ~90 °C, cut above ~110 °C (tune at bring-up).  Log both in the heartbeat |
| R7D-05 | NOTE | Doc consistency (ARM timing; R6D-08 fix incomplete) | §3.5 item 4 still says "no gap longer than ~20 ms **(≥ 50 ms disarms)**".  §3.2 now says a ~50 ms gap is *tolerated* with nominal parts (~30 ms worst), and arm.out gives 52–164 ms nominal with ~30–200 ms tolerance.  So "≥ 50 ms disarms" is wrong: only ≥ ~200 ms always disarms.  Self-test (c) passes at **20**–250 ms.  The earliest disarm time *is* the pause tolerance [S arm.out footer], so a board measuring 20–29 ms passes the test yet tolerates barely the 20 ms gap the contract allows.  §1/§9 use 30–200 | [D §3.2] l.180; [D §3.5] l.332, l.346; [D §9] step 3; [S arm.out] | Item 4: "gaps > ~30 ms may disarm, ≥ ~200 ms always disarms; keep gaps ≤ 20 ms".  Self-test pass window ≈ 30–250 ms |
| R7D-06 | NOTE | Single point of failure (DRV8323 straps) | **An open MODE strap turns "disarmed" into "brake".**  MODE Hi-Z (R44 missing, tombstoned or cracked) selects **1x PWM** [DS DRV8323 Fig. 8-23].  In 1x mode **INLC is nBRAKE**: low turns all low sides on [DS §8.3.1.1.3].  INLC = CH3N AND W_ARM_S, so the disarmed state short-brakes a coasting drum, the case §8 forbids ("hundreds of A").  With a ~10 µH winding and 14 V BEMF the current ramps to the 62–93 A VDS OCP in ~50 µs and then retries every 4 ms until the fault counter latches, so it is bounded but not benign.  §9 step 3 cannot see it: with the motor stopped, Hi-Z and brake both read 0 V through the dividers.  The GAIN pin is open by design (Hi-Z = 20 V/V needs > 500 kΩ).  Leakage below a few hundred kΩ shifts it to 10 V/V, halving the measured current and doubling the effective 20 A limit.  Only VDS OCP (62–93 A) catches that.  Neither case is in §7.16 | [N] U2.29 = U2_MODE/R44, U2.32 GAIN = NC; [D §3.2] straps; [D §7.16]; [DS DRV8323] SLVSDJ3D §8.3.1.1.3, Fig. 8-23 | Firmware: any weapon CSA current above a few A while disarmed → W_EN low (sleep) and report.  Cross-check INA239 pack current against Σ(duty × phase current) from the CSAs; a mismatch means a gain fault.  §9 step 2: measure the MODE/GAIN pin voltages against the Fig. 8-23 levels.  Add both to §7.16 |
| R7D-07 | NOTE | Power-off with a spinning drum | While the drum holds VBAT above ~9 V (≈ ≥ 18 k rpm), BAT_IN is back-fed through the **on** Q7/Q8, so U13 never sees UVLO and keeps them on for the whole coast (seconds).  "Wait ≥ 2 s" therefore does not guarantee a soft re-close.  A re-close from ~12 V is the simulated 1.35 V/µs / 83 A case, so it stays under 4 V/µs; this is a wording issue only.  §7.5's firmware reaction ("stops the drives") should also coast the weapon.  Otherwise an armed, speed-holding FOC drains the bus and the logic reboots repeatedly until the drum slows | [N] BAT_IN = Q7.D, U13.VS; [D §3.1] "Wait ≥ 2 s"; [D §7.5]; [S hotplug.out] "off 10 ms … 12.0 V 1.351 V/µs 82.73 A" | §3.1/§7.2: "with the drum spinning the FETs stay on until it slows; a re-close then is the fast case (≤ 1.4 V/µs)".  §7.5: detection → drives **and** weapon coast |
| R7D-08 | NOTE | Brown-out ride-through (hits) | A ms-scale contact bounce at the screw switch or XT30 during spin-up drains C1+MLCC (~380 µF) at 20 A / 380 µF ≈ **53 V/ms**.  The bus collapses in < 0.3 ms, U13 (unfiltered EN) opens the FETs, and both MCUs reset.  The motor side recovers in ~0.3 s (soft-start + re-arm handshake).  The Pico W must reconnect its Bluetooth controller: **seconds** of no control.  A 1.27 mm header fret on impact has the same effect | [D §3.1] U13/R13/R14 (no EN cap), R4/R5/C10 (4.5 ms filter); [D §3.5] item 2 | §3.5 item 2: bulk capacitance after the compute board's Schottky so the Pico rides through ~5 ms (0.2 A × 5 ms / ~2.2 V ≈ **470 µF**).  The radio link then survives and only the re-arm handshake is needed |
| R7D-09 | NOTE | Drive encoder faults | §8 has no encoder plausibility check.  ABZ is incremental.  At 1024 PPR ×4 and 6 pole pairs, one electrical cycle is 683 counts: ~170 counts of error (noise or missed edges after a hit) zeroes the torque and ~340 reverses it, so FOC runs away at the 1–1.5 A limit until the next Z.  Z resync is per mechanical revolution, and a noisy Z makes it worse.  An unplugged J2/J3 freezes A/B high (the 4.7 k pull-ups), so the motor locks instead of driving | [D §3.3] signals; [D §8] timer-inputs row | §8: compare encoder speed with the flux/BEMF estimate (or current response); on mismatch or no counts under current, switch to sensorless or stop that wheel and report.  Check that Z arrives every 4096 ± a few counts |
| R7D-10 | NOTE | Pits: USB-powered compute board, robot off | With the Pico on USB and the robot switch open, the Pico's UART TX idles high into MB_RX.  That current flows into the unpowered STM32's PC5 clamp and through R17 into the motor board's +3V3, part-powering the MCU rail (BOR holds it in reset, but it is an undefined state and an injection-current overstress).  Reading logs over USB in the pits is the usual workflow | [N] MB_RX = J1.6, R17 → +3V3, U1.23; [D §3.5] item 5 | Item 5: keep MB_RX, NRST, SWD and W_ARM_CLK Hi-Z/low unless the header +5V is present (sense it ahead of the Schottky) |
| R7D-11 | NOTE | Weapon phase short (hits) | The H-variant VDS OCP deglitch is fixed at 4 µs [DS]; the FET's IDM is 600 A [DS HYG015N04LS1C2].  Take a cut weapon lead shorting two phases near the motor: R ≈ 2 FETs hot (4.2 mΩ) + shunt 2 mΩ + ~10 cm of wire and contact (~4–5 mΩ) ≈ 11 mΩ, L ≈ 100 nH.  From 16.8 V the current reaches ~1.5 kA × (1 − e^(−4/9)) ≈ **~500 A** before the trip, at IDM, and again every 4 ms retry until the fault counter latches.  A cheap firmware-only improvement: W_SOA (PA0 = COMP3_INP) and W_SOB (PA1 = COMP1_INP) are already on comparator inputs.  COMP + DAC → TIM1 BRK2 cuts in ~100–200 ns whenever the low-side return is phase A or B.  A low-side-C path is not covered, so this is partial | [DS DRV8323] "tOCP_DEG fixed at 4 µs" (hardware variant); [DS HYG015N04LS1C2] IDM 600 A; [X] PA0/PA1 | Optional §8 item: COMP1/COMP3 fast trip at ~30 A → BRK2.  Otherwise record it as a residual in §7 |

## 3. Checked and found consistent (no finding)

* §5 against spice/*.out: hotplug (2.23 V/ms, 0.003–0.009 V/µs, 16.5/21.8 W, 53–54 mJ; reversed
  pack 13 A with D10 vs 102–146 A without; re-close 0.12–1.35 V/µs typical and 3.0–3.3 V/µs at
  minimum UVLO), arm (52–134 / 67–164 ms, 7–10 edges, 12 ms at 500 Hz), bridge and spin-up rows.
* §1 counts: 190 assembled parts, 65 BOM lines (bom.csv), plus 6 DNP.
* U14 thresholds in docs/sim (VT+ ≤ 2.0 V at 3.0 V, VT− 0.80–1.33 V) match the Diodes datasheet.
  The armed level at ≥ 500 Hz is 2.74–2.95 V: ≥ 0.6 V above VT+.
* LM74502 I(GATE) is 40 µA min, and R32 draws ≤ ~28 µA at the end of the ramp, so the gate always
  has net charge current.  Turn-on is slower at the minimum (~1–1.8 V/ms) but harmless.  C13 (50 V)
  sees ≤ ~44 V even at the TVS clamp.
* Re-close with C13 still charged (D10 blocks its discharge, R32 τ = 22 ms): only the FETs'
  Miller capacitance limits the edge, ~0.05–0.3 V/µs, which is under both the 4 V/µs limit and the
  simulated FET-on re-close cases.
* Every single fault in the ARM chain other than R7D-06 fails safe: either diode in D9 shorted,
  C15 open, C16/R41 shorted, R18 open, U14 VCC open, R50 open (drives brake, not drive), R40 open.
* Disarm then re-arm while the drum spins: firmware forces CHxN low on ARM loss, so a hardware ARM
  rise alone cannot apply the TIM1 zero vector (a brake) to the drum.
* MT6701 supply 3.0–5.5 V at the default 3.3 V jumper; EEPROM programming needs 4.5–5.5 V, as §9
  says.  55 k rpm rating vs a duty-capped ~47 k rpm.
* R6D-02…R6D-11 fixes are present in §3.5, §6.9/§6.13, §7.20 and §9, except the item-4 wording
  (R7D-05) and the missing radio test (R7D-02).

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R7D-01 | MINOR | §4 still says switch UVLO ~7.8 V (7.0–8.6); rev G is 9.0 V (7.7–10.0), which can now exceed the 9.2 V logic cutoff; state the 12 V foldback vs 10.0 V margin as a requirement |
| R7D-02 | MINOR | Radio loss only drops ARM; no requirement that drives stop; §9 has no transmitter-off, main-loop-hang or switch-open-with-drum test despite "tested" |
| R7D-03 | MINOR | Weapon at 24 kHz is ~7–8 updates per electrical cycle at 3.0–3.5 kHz (7 pole pairs, confirm); six-step gets ~1.3 ADC samples per sector and no comparator path; not stated or planned |
| R7D-04 | MINOR | A jammed drum at the 20 A limit is continuous (~2–2.5 W in one FET pair, 20–40 W in the motor); §8 has no stall cut-out and no TH1 action |
| R7D-05 | NOTE | §3.5 "(≥ 50 ms disarms)" contradicts §3.2 (~50 ms tolerated); self-test floor 20 ms should be ~30 ms |
| R7D-06 | NOTE | MODE strap open → 1x PWM, where INLC = nBRAKE, so disarm short-brakes the drum; open GAIN pin leakage halves the measured current; add firmware checks and §7.16 entries |
| R7D-07 | NOTE | A spinning drum keeps Q7/Q8 on after the switch opens, so "wait 2 s" does not give a soft re-close (still < 4 V/µs); §7.5 should coast the weapon too |
| R7D-08 | NOTE | A ms contact bounce under weapon load resets both boards; Pico Bluetooth reconnect = seconds; ~470 µF ride-through on the compute board |
| R7D-09 | NOTE | No encoder plausibility check or sensorless fallback in §8 (683 counts per electrical cycle; ~340 counts of error reverses torque) |
| R7D-10 | NOTE | USB-powered Pico with the robot off back-powers the motor MCU through MB_RX/R17; gate the header outputs on +5V present |
| R7D-11 | NOTE | Weapon phase short reaches ~500 A (≈ IDM) during the fixed 4 µs VDS deglitch; COMP1/COMP3 → BRK2 on W_SOA/W_SOB is a firmware-only partial fix |

**Verdict: 0 BLOCKER, 0 MAJOR, 4 MINOR, 7 NOTE. Not clean.**
