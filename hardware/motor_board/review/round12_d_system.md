# Review round 12 / D: system-level review (rev K)

Reviewer role: adversarial system reviewer (power electronics and combat robotics).  I read the
whole package fresh: DESIGN.md rev K end to end, design/calcs.md, design/motor_board.py,
spice/*.out, and the datasheets listed below.  I used review/CHANGES.md and round11_d_system.md to
avoid re-raising settled items.  Out of scope: board area and fit, and prose style.

No design file was edited.  One side effect to record: I ran `python3 design/motor_board.py` to
re-run its checks.  It passed and rewrote the generated files (netlist.csv, nets.md, bom.csv,
mcu_pinmap.md) from the unchanged rev K source.  The generator is deterministic and has no
timestamps, so the contents match the last regeneration from that source.

Evidence tags: **[D l.N]** = DESIGN.md line, **[P l.N]** = design/motor_board.py line,
**[C §N]** = calcs.md, **[S file]** = spice output.  Datasheet pages are the printed page numbers.

---

## 1. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| R12D-01 | **MINOR** | Fault handling and latching vs normal combat transients | **The latch policy treats every weapon comparator trip as a short, and it does not say which events count or what clears a latch.**  So ordinary fight events can switch a channel off for the rest of the match.<br><br>**(a) Comparator trips are not all ~500 A events.**  §8 latches the weapon on its first comparator trip because "each is a ~500 A-class event that kicks both DRV8316 VMs" [D l.598].  That holds for a hard short (100s of A/µs).  It does not hold for a **slow over-current**, such as a sensorless observer losing lock when the drum hits something.  That is the classic sensorless-weapon failure on impact.  In that case di/dt ≈ (VBUS + BEMF_LL) / 2L_ph ≈ 14–31 V / 8–15 µH ≈ **1–4 A/µs** (L_ph 4–7.5 µH, the range used in R11D-01).  Going from the 20 A limit to the 30 A threshold takes ≥ 2.5 µs.  The 0.7–1.0 µs trip chain [D l.573] adds ≤ 4 A, so the bridge turns off at **≤ ~34 A**.  That is 1/15 of the short-circuit current, so the kick at the DRV8316 VM is negligible.  One desync still ends the weapon for the fight.<br><br>**(b) A loaded contact bounce trips two fault sources, and neither has a stated policy.**  The bus falls to 4.4–4.8 V [S hotplug.out, bounce cases].  That is below U2's VM UVLO of 5.4–5.8 V (SLVSDJ3D p.18), so W_nFAULT asserts and TIM1 breaks.  On re-close, recharging ~380 µF by 12 V is ~4.6 mC.  Averaged over one ≤ 150 µs INA239 conversion that is ≥ 30 A, plus the 20 A load ≈ **50 A > SOVL 38 A**, so ALERT latches (ALATCH = 1) [D l.612].  The same bounce drops both DRV8316 VMs.  A CP-UV nFAULT is reported, and a VM UVLO below 4.1–4.3 V resets the chip silently: NPOR, no nFAULT report (SLVSH07 p.13, Table 8-8 p.48).  Both would count toward "> ~3 DRV8316 recoveries within a second → latch" [D l.598].  A chattering XT30 or screw switch in one hit easily gives 3 bounces.<br><br>**(c) Clear conditions are undefined.**  "Latch that drive off until re-commanded" is ambiguous, because drive commands arrive continuously.  For the weapon latch no clear condition is given at all | [D l.575, l.598, l.602, l.607, l.612]; [S hotplug.out] bounce "VM before 4.4–4.8 V", I peak 109–216 A; SLVSDJ3D p.18 VUVLO; SLVSH07 p.13 VUVLO 4.1–4.3 V falling, Table 8-8 (UVLO: no report, registers reset) | Rewrite the fault row of §8 in terms of **event classes**:<br>• **Short class, latch at once:** a VDS OCP (nFAULT releasing after ~4 ms with VBAT normal), or a second comparator trip within ~1 s.  Only the VDS-only phase-to-ground case exceeds the VM limit (§7.21).  A comparator-covered short repeated once is ~1–2 V/µs at the filtered VM (round 10), which is inside the 4 V/µs abs max.<br>• **Recoverable class, auto-restart:** a single comparator trip with no VDS OCP → restart through catch-spin after ~50–100 ms, counted and reported.  Also any break coinciding with VBAT below ~9 V, U2 UVLO, SOVL, or DRV8316 CP-UV/NPOR → restart when VBAT has recovered.  These do not count toward the latches.<br>• **Clear:** a latched channel clears only on an explicit compute-board command (e.g. disarm → new ARM edge → restart for the weapon; a "drive enable" frame for the drives).  Report it in the heartbeat.<br>Optionally: on R_nFAULT, stop only TIM20 (software break, MOE = 0) instead of setting the shared DRV_OFF, so a fault on one drive does not coast the other |
| R12D-02 | **MINOR** | Firmware contract gap: drive encoder absolute angle | **The contract never says how the drive FOC gets its electrical angle at power-up or after a reset.**  In ABZ mode the MT6701 gives only incremental counts [D l.239, l.606].  It outputs nothing for the first 50 ms after power-up (MT6701 §7.3 p.12).  It can optionally emit a pulse train encoding its absolute position within those 50 ms.  That option is register-programmed (Fig. 8(2) p.13) and is not in the §9 step 5 programming list [D l.651].<br>Three hardware facts turn this into failure cases:<br>(1) The sensor powers up **with** +3V3, because TPS22945 ON is tied to VIN [P l.330].  So the power-up train is only captured if TIM3/TIM2 are counting within a few ms of +3V3.  The §8 boot order configures them late [D l.585–589].<br>(2) An **MCU-only reset** (IWDG, NRST pulse from the compute board) clears the timer count, but the sensor stays powered and sends no new train.  The absolute angle is then lost, and the MCU cannot re-power the sensor.<br>(3) A **sensor supply retry** (TPS22945 80 ms auto-retry after a VS short, or a cable intermittent) re-powers the sensor mid-run.  Pulses are lost while it is off, and with the power-up option enabled a fresh absolute-position train is **added** to the running count.<br>In every case FOC runs with an arbitrary angle offset.  Past 90° the torque reverses.  The §8 plausibility check only acts "above a few thousand rpm", so at low speed the wheel can be driven the wrong way until the motor gets there | MT6701CT-STD §7.3 (p.12–13); [P l.329–331] ON = VSRC; [D l.239–241, l.585–591, l.606, l.651]; TPS22945 auto-retry 80 ms [D l.230] | Add to §8 "Timer inputs": (i) the **angle source at start**: either program the MT6701 power-up absolute train (add it to §9 step 5) with TIM3/TIM2 in encoder mode first thing after clocks, or run sensorless/I-f until the first Z.  Alignment by d-axis injection is also acceptable: through 28.5:1 the wheel moves ≤ 1/(2·6·28.5) rev ≈ 0.4 mm.  (ii) **Z is the reference:** at every Z capture compare the count modulo 1024×4 with the stored Z count and correct it (or fall back to sensorless) on a mismatch > a few counts.  (iii) After any MCU reset, and after ≥ ~20 ms without encoder edges while the observer says the motor turns (sensor re-power), mark the angle invalid until Z is seen again.  (iv) §9 step 5: power-cycle with the rotor at a marked position and check the start angle; hold VS shorted for 100 ms while spinning and check the recovery |
| R12D-03 | NOTE | ARM interlock single fault: MODE strap **shorted** | §7.16 covers an *open* R44 (1x mode).  A **shorted** R44, or pin 29 bridged to the AGND/EP copper, gives **6x PWM**.  In that mode INLx = 0 with INHx = 1 turns the **high side on** (SLVSDJ3D Table 8-2, p.32).  So without ARM, TIM1's INH outputs can still switch the high-side FETs.  No low side can turn on, so there is no torque from the pack.  But on a coasting drum, two high sides on at once short two phases through the VBAT rail: the same partial brake as the U6-stuck-high case.  The boot "INH pulse draws no current" test [D l.551] does not detect 6x mode, because a lone high side also draws no current.  §9 step 2 (MODE ≈ 1.2 V) does catch it at bring-up | SLVSDJ3D Table 8-2 p.32; [P l.196]; [D l.550–556, l.632] | Add "R44 shorted → 6x" to §7.16.  Make the boot test also read the phase divider (W_Vx) during the INH pulse with INL = 0.  In 3x mode the phase is Hi-Z (≈ 0 V); in 6x mode it is at VBAT/7.8 |
| R12D-04 | NOTE | Encoder over-speed with field weakening | §3.3 and calcs §10 put the duty-capped top speed at **46.5 k rpm**, inside the MT6701's **55,000 rpm** rating, and add that "field weakening can add some" [D l.198–200].  Only +18 % of field weakening, e.g. with a wheel in the air, exceeds the rating.  The no-load figure behind "4.7 m/s" is ~59 k rpm.  The ABZ output is then out of spec (A/B at ~940 kHz at 55 k rpm), and the plausibility check hands over to sensorless.  That is recoverable, but it is not stated | MT6701 §6 table p.8 (RS max 55,000 rpm); [C §10]; [D l.198–200] | §8: cap the drive speed at ~50 k rpm while running on the encoder.  Field weakening only in sensorless mode, or not at all |
| R12D-05 | NOTE | Bring-up checks missing for two firmware-contract assumptions | (a) **Regen on a full pack.**  The 18.5 V coast margin depends on the pack IR, which is not measured anywhere.  From 16.8 V at 10 A regen: +0.5–0.75 V with a fresh pack plus lead (50–75 mΩ), +1.0–1.5 V aged or cold (100–150 mΩ), which gives **17.8–18.3 V**.  Only 0.2 V is then left before the coast turns a controlled drum reversal into a free coast.  §8 already asks for bus-limited regen [D l.601, l.611], but §9 never exercises it.  (b) **ARM nuisance disarms.**  The compute board's toggle ISR must survive Bluetooth activity with gaps under ~20 ms [D l.337–338].  §9 checks the timing only on the bench, not under a real radio load | [D l.601, l.611, l.337–346, l.637–645] | §9 step 6: on a freshly charged pack, brake the drum at the chosen regen limit and log INA239 VBUS (the peak must stay < 18.3 V).  §9 step 3: a 10-minute armed soak with the transmitter active and the drum idle; expect **zero** "W_ARM_S fell" events |

---

## 2. Checked and found sound (no finding)

**Power-up / power-down sequencing.**

* Power-up order: soft-start 2.2 V/ms → buck on at 10.4 V → +3V3 → DRV8316s wake (DRVOFF held high by R50) → MCU.  The DRV8316 nFAULT pull-ups go to its own AVDD, so test-mode entry is avoided.
* Power-down: at idle the board draws ~0.12 A from ~380 µF, so the bus falls to the 9.2 V logic cutoff in ~25 ms.  Everything sleeps with +3V3.
* The logic comes back on at up to 11.5 V (calcs §9 worst case).  A resting 4S pack recovers above that, so there is no restart deadlock.

**Hot-plug and bounce.**

* The re-close and loaded-bounce numbers in [S hotplug.out] reproduce §5 and §7.2.
* Nothing in rev K changes the settled residuals.

**Buck start into the compute board's 470 µF hold-up.**

* The LMR16006 core has a cycle-by-cycle current limit, soft-start and OVTP, and **no hiccup** (SLVSDJ3D §8.3.5.5–8.3.5.6, p.47–48).
* It charges ~514 µF at ~1 A in ~3 ms and cannot lock up.
* The extra load on Q7 during its linear ramp is ≤ ~0.6 A → ≤ ~6 mJ added.  Trivial.

**nSHDN thresholds.**  I re-derived them with the pin's 1 µA / 4.2 µA pull-up currents: 10.42 V on, 9.17 V off.  They match §3.1.

**Reversed pack.**

* LM74502 limits: EN/UVLO min = V(VS), SRC ≤ V(VS) + 0.3 V (SNOSDE5A p.4).
* PSW_S sits one leakage-level body-diode drop above BAT_IN, because only µA flow through Q7's body diode (Q8 blocks).  This is TI's own back-to-back topology.

**Regen with the pack disconnected.**

* 10 A into ~380 µF is 26 V/ms, so the bus reaches the TVS clamp before BOVL acts.  At 10 A the SMBJ20A clamps at ≈ 28 V.
* 28 V puts PA4/PA5 at 3.6 V, under the TT 4.0 V abs max.  Even the full 32.4 V clamp gives 4.15 V, and only for the 0.3–0.8 ms before BOVL.
* §7.21 already records D1 as the real clamp.

**Short-braking the drives on CLL, debug halt or a TIM8 break.**

* At top speed, BEMF 13.3 V into ~0.5 Ω (R + ωL at 4.65 kHz electrical) is ~27 A, which is above the DRV8316 OCP of 16 A.  The channel latches Hi-Z; that is a safe outcome.
* At lower speeds it brakes, and the tyres slip at ~1 N·m at the wheel.

**6x default after a DRV8316 reset.**  INH = INL = 1 → Hi-Z (SLVSH07 Table 8-3).  R11's "brakes only on the PWM off-times" is confirmed.

**Sensor cable faults.**

* A phase on S1–S3 injects ≤ 13.5 mA through the 1 k resistor plus 2.9 mA through the 4.7 k pull-up into +3V3.  The 120 mA rail load absorbs it.
* A pin-1/pin-6 swapped cable harms nothing, because VS is current-limited and TEMP sits behind 2.2 k.

**Header faults.**

* Unplugged: R18 pulls ARM low and R17/R16 idle the other lines, so the board is safe.
* The toggling UART pins (5/6) are 13–14 positions from pin 19, so a one-pitch mis-mate cannot clock W_ARM_CLK.

**Thermal.**

* **Board.** ~20 g laminate + ~8 g parts ≈ 25 J/K.  4 W for 3 min is an adiabatic +29 K; with convection (τ ≈ 5 min) it is ≈ +22 K.
* **DRV8316.** Worst loss at 1.5 A is 1.96 W × ΨJB 7.2 °C/W ≈ +14 K over the local board.  At 50 °C ambient that gives a junction ≈ 50 + 29 + 14 + local spreading ≈ 100–110 °C, against OTW 135 °C min (SLVSH07 p.13–14).
* **R302/R402.** At a ~85 °C board the 2512 derates (1 W at 70 °C → 0 W at 155 °C) to 0.82 W, against 0.24 W at 1.5 A and 0.52 W at 2 A.
* **AP2112K.** 0.2 W × 184 °C/W = +37 K → ~115 °C, inside its 150 °C Tj.
* The heat budget [C §11] leaves out two items:
  * the DRV8323's awake current, 10.5–14 mA × 16.8 V ≈ 0.2 W (SLVSDJ3D p.17), plus its gate drive;
  * the DRV8316s' 0.27 W quiescent outside the 60 % drive duty.

  That is ~0.4–0.6 W, so the true average is ~4.5–4.7 W instead of ~4.1 W.  No conclusion changes.

**§1 requirements.**

* VM ≤ 2.75 V/µs vs 4 (31 % margin).
* Soft-start ≤ 0.01 V/µs.
* Weapon VDS ≤ 29 V vs 40 V, SHx ≥ −4.6 V vs −7 V at ≤ 6 nH.
* Disarm 52–164 ms simulated.
* 16 analog inputs.
* 5 V: 0.57 A of the 0.6 A rating (thin, but the limit is 1.2 A typical).
* BOM: 67 lines and 199 designators, matching §1.

---

## 3. Summary

| ID | Sev | One line |
|---|---|---|
| R12D-01 | MINOR | The first-trip weapon latch treats slow ~30–34 A over-currents (desync on impact) as ~500 A shorts.  Bounce-induced UVLO/SOVL/CP-UV/NPOR events have no stated policy and count toward the drive latch.  Clear conditions are undefined.  Classify the events; latch only the short class |
| R12D-02 | MINOR | No defined drive-encoder angle source at power-up, after an MCU-only reset or after a sensor re-power (MT6701 ABZ is incremental; its power-up absolute train is optional and unprogrammed; TPS22945 ON = VIN).  Define the start method and Z re-sync, and add bring-up checks |
| R12D-03 | NOTE | A shorted MODE strap (6x) lets INH turn the high sides on without ARM (partial brake on a coasting drum); the boot test misses it.  Read W_Vx in the test and add it to §7.16 |
| R12D-04 | NOTE | Field weakening can take the drive past the MT6701's 55 k rpm (duty-capped 46.5 k).  Cap the speed on the encoder |
| R12D-05 | NOTE | Bring-up: add a full-pack regen test (bus peak vs the 18.5 V coast) and an armed soak with the radio active (zero nuisance disarms) |

**Verdict: 0 BLOCKER, 0 MAJOR, 2 MINOR, 3 NOTE.**  Both MINORs are firmware-contract and bring-up
text only; no hardware change is needed.  The hardware is ready for schematic capture.
