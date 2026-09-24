# Review round 19 / D: system-level review (rev L)

Reviewer role: adversarial system reviewer (power electronics and combat robotics).  I read DESIGN.md rev L end to end, plus
design/calcs.md, spice/*.out, review/CHANGES.md (rounds 1–18), round18_d_system.md and round18_a_hardware.md.  I also read the
INA239 datasheet (input bias) and the DRV8316C datasheet (DRVOFF), and the nets for the INA239 input network.  The package was
copied to `/tmp/r19d/` and nothing in it was edited apart from this file.  Hardware is unchanged since round 16, so no SPICE deck
was re-run; the outputs were re-read.  The focus was the round-18 §8.1 text:

* row 1, which now defers "looks open" to row 0;
* row 0 suspension and plausibility;
* the drive-table nFAULT exemption;
* the latch-word contents;
* the boot Release.

Evidence tags: **[D l.N]** = DESIGN.md line, **[S file]** = spice output, **[C §N]** = calcs.md, **[N]** = nets.md,
**[INA]** = INA239.pdf.

---

## 1. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| R19D-01 | MINOR | §8.1 drive row 7 (L/R crossover) | **Two different pit errors give the row 7 symptom, and row 7 treats both as swapped sensor cables.  For the other error, crossed motor-wire bundles, the row 7 response runs the robot with forward and reverse swapped.  The report also points the crew to a "fix" that turns off detection for good.**<br>• **The error.**  The three drive-L wires go into J_RA..J_RC and the three drive-R wires go into J_LA..J_LC.  The bundles look alike, so this is easy to do when re-soldering six drive wires, for example after swapping in a spare motor board.  The encoders stay on the correct connectors.<br>• **What alignment sees.**  Aligning drive L energises U3, which now turns the right motor.  The right encoder (J3 → TIM2) moves and TIM3 stays still.  This is exactly the row 7 evidence "the other encoder moved while the aligning drive's own encoder stayed still".  The sign test cannot tell the two errors apart: both motors and encoders are built and programmed alike, and the phase order within each bundle is intact.<br>• **Row 7 response.**  Both drives go to sensorless.  Channel L then drives the physical right motor in the left motor's "forward" sense.  The motors are mounted mirror-image, so that is backwards for the right wheel.  Wheel speeds become right = −v_L and left = −v_R.  **Translation is reversed**; the turn direction is kept.<br>• **The crew follows the report ("swapped J2/J3") and swaps the sensor cables.**  Each channel is now self-consistent: U3 turns the right motor and TIM3 reads the right encoder.  Alignment passes cleanly with the correct sign, encoder FOC runs with no report, and the robot **still drives backwards**.<br>• **No later check catches it.**  §9 has a by-eye direction check after weapon rewiring [D l.764], but none for the drives | [D l.682] row 7; [D l.614] alignment "other encoder must stay still"; [D l.759–764] §9 swap tests; [N] J2 → U9 → TIM3, J3 → U10 → TIM2.  Kinematics: v_right,phys = −v_L, v_left,phys = −v_R → forward command gives −v, yaw rate ∝ v_L − v_R unchanged | Row 7: report "left/right crossed: sensor cables **or** motor wire bundles", not only J2/J3.  §9 and the pit procedure: after any drive rewiring or board swap, command a short forward move and confirm the direction by eye.  The compute board can also check it with its IMU (a forward command must give +x acceleration).  Keep the sensorless response: it is correct for the sensor-cable case |
| R19D-02 | MINOR | §8.1 row 0 plausibility, INA239 current channel | **The round-18 plausibility gate handles one failure only: a pack-current channel that reads 0 with the drum stopped.  Two other realistic single faults still bypass the "INA239 alone failing" path, which is weapon off, drives continue [D l.692–693].**<br>• **(a) C2 cracks short while the drum spins.**  C2 is a 0603 MLCC across IN+/IN− in the pack-current region.  §6.10 names flex cracks as the impact failure mode.  The drum is at speed mid-match and the weapon is driven (it is not suspended).  \|I\| ≈ 0 for 100 ms, the drum is not stopped, so the gate does not apply → **switch-open hold**: weapon coast and DRV_OFF high.  An operator clear re-trips within 100 ms for as long as the drum coasts (10–40 s, §7.6).  Only then does the gate send it to the INA239 path.  The robot cannot drive for ≥ 10 s plus the operator's reaction, which is a count-out in most rule sets.  It is physically implausible as a switch-open: with the switch open, a **driven** (motoring) weapon has no source.  A coasting drum can hold the bus only at its rectified line-to-line peak, VBUS ≈ BEMF_ll,pk − ~1 V.  With the pack connected, VBUS sits above the drum's BEMF, because the weapon duty cap keeps BEMF ≤ ~0.9 × the spin-up bus (14.2 V at a 15.6 V bus [S spinup.out]).<br>• **(b) R2 or R3 (10 Ω Kelvin resistor) cracks open.**  The open input drifts at I_B / C2 ≤ 2.5 nA / 100 nF = 25 mV/s [INA], which is 25 A/s at 1 mΩ.  The reading saturates at ±41 A within ~1.6 s at the maximum bias current (longer at typical bias).<br>&nbsp;&nbsp;– **Positive saturation:** permanent SOVL → row 3 "fold back the shared budget … ramping back while the pack current stays below it".  It never ramps back, and the text gives no floor for the fold-back.  The budget is shared with the drives [D l.609], so it can starve them.  W_nFAULT is also held low, so the SPI owner re-reads DIAG_ALRT every ≤ 0.5 ms indefinitely.<br>&nbsp;&nbsp;– **Negative saturation:** SOVL can never trip and row 0 can never match.  Pack over-current protection and switch-open detection are both lost **silently**, and the SPI health check (ID + configuration read-back) passes | [D l.651] gate text ("drum stopped" only); [D l.477] §6.10; [D l.609, 654, 692–693]; [N] INA_INP/INA_INN: C2, R2, R3; [INA] I_B ≤ 2.5 nA; [S spinup.out] 25 573 rpm → 14.2 V | Make it a general two-sided plausibility check.  If the INA239 current disagrees with firmware's estimate (idle + Σ channel power / VBUS) by more than max(~1 A, ~30 %) for ≥ ~200 ms while the bus is steady, take the INA239-failure path.  Extend the row 0 gate from "drum stopped" to "no possible source": the weapon is stopped **or driven (positive power)**, or VBUS is ≥ ~1 V above the measured weapon line-to-line peak (W_Vx during coast).  Give row 3 a floor that never folds the drive share below its ~1.5 A-per-motor limit |
| R19D-N1 | NOTE | §8.1 row 0 suspension clause 2 | The text reads "pack-current estimate **from the actively driven channels only**".  R18D-02's fix was "idle + actively driven channels".  Read literally, the estimate is 0 whenever nothing is driven, so row 0 is suspended at exactly the idle moments when it should detect.  Detection is then delayed until something is driven: a drive command above ~50 mA equivalent lifts the suspension, and the hold follows 100 ms later.  Row 1's "looks open → row 0 decides" state also stays open-ended meanwhile, though coasted and at zero torque.  The end state is safe.  Say "idle (bring-up value) + actively driven channels" | [D l.651, 652] | — |
| R19D-N2 | NOTE | §8.1 row 1 "VBUS stays above ~18 V" / "(an open bus decays only ~0.2 V/ms)" | The 0.2 V/ms figure is the idle load only (0.1 A / 374 µF = 0.27 V/ms).  With the drives motoring, an open bus falls at P/(C·V): 10 / 30 / 43 W → 1.4 / 4.2 / 5.7 V/ms.  Take the case where weapon regen roughly balances drive consumption, e.g. the tail of a drum brake while driving hard.  The BOVL overshoot is then small, the break removes the source, and VBUS falls below 18 V within the ~0.6 ms two-conversion window.  An open switch or a bounce is then classified as over-voltage: a restart with the switch open, and after > 3 in 10 s a persisted weapon latch "over-voltage" instead of the non-persisted switch-open flag.  In the common cases the D1 overshoot (bus near ~22–24 V at the break) keeps VBUS above 18 V, so this is narrow and ends safe.  \|I\| < ~50 mA in both conversions already separates the cases (switch closed: ≥ idle ~60–100 mA, or ≫ with any load).  Drop the VBUS conjunct, or replace it with "VBUS not settled at a constant level" | [D l.652]; 374 µF [C §9]; drive 1.5 A at 46.5 k rpm ≈ 20 W mech per motor [C §10] | — |
| R19D-N3 | NOTE | Weapon row 1 vs drive row 1 on the same BOVL | When the switch opens during a brake, the bus overshoots past the DRV8316 OVP (20–22 V) before D1 clamps.  Drive row 1 (OVP within ~1 ms of a BOVL) then sets DRV_OFF high and restarts both drives after 20 ms of steady bus.  Weapon row 1 ("looks open") says drives to zero torque and row 0 decides.  With the drum holding the bus, the drives restart and run on drum energy until row 0 matures ~100 ms later.  That is bounded and harmless, but the precedence is unstated: say that a pending row 1 "looks open" holds the drive-row-1 restart until row 0 has decided | [D l.652, 676] | — |
| R19D-N4 | NOTE | Drive-table nFAULT exemption, exit side | The exemption covers nFAULT while the DRV_OFF pin is high, within ~1 ms of raising it, and during a commanded coast.  Nothing covers the exit.  An nFAULT that is still low after the pin is lowered and the Release written gives no new EXTI edge, and L_nFAULT would keep the TIM8 break asserted, so MOE cannot be set.  The ~100 Hz check reads CTRL registers, OTW and NPOR, but not the IC_STAT FAULT bit.  Say: "nFAULT still low ~1 ms after the Release (pin low) → drive event (row 2 via SPI status)", and add IC_STAT FAULT to the 100 Hz read.  A fault that arises while the FETs are off (pin high) cannot be an OCP, so nothing is masked today | [D l.672, 612]; [DRV8316C] DRVOFF pin: "all outputs Hi-Z" | — |

---

## 2. Scenario walk-through (current rev L text)

| Scenario | Path | Outcome |
|---|---|---|
| Drum impacts, single or flurries | Row 6 catch-spin after 50–100 ms; > 5/s → 1 s off; row 4 needs two consecutive fast re-trips | Safe, no latch |
| Bounce under heavy weapon load | U2 UVLO / bus event → row 2 → restart after 20 ms steady (supply budget) | Bounded |
| Bounce during weapon brake, drives idle | BOVL → row 1 looks open (\|I\| ≈ 0, VBUS > 18 V) → coast, zero torque → current returns → supply restart | Bounded, no hold (R18D-01 fixed) |
| Bounce during drive regen (being shoved) | Pump 1.3–2.7 V/ms → BOVL only for bounces ≳ 1–2 ms → looks open → supply restart | Sound |
| Bounce during brake-while-driving | Can fall to the over-voltage branch (N2) | Bounded; counted toward the 3/10 s latch |
| Pushing / being pushed | Drive regen suspends row 0; stall 5 s → no fault; OTW derates | Sound |
| Jammed drum | Row 10 retry; row 5 passes at each stopped restart | No latch |
| Wheel in the air | Duty cap 46.5 k rpm; encoder cap 50 k is enforced (an 18.3 V regen bus would allow 50.6 k uncapped) | Sound |
| Weapon phase–phase short, spinning / stopped | Row 4 (2nd fast re-trip) / row 5 | Latched |
| Weapon phase–GND / –VBAT short | Row 8 (VDS OCP) / rows 6→4 | Latched |
| Drive short, spinning or stopped | DRV8316 OCP 16 A → drive row 2 → > 3/s latch, coasted, INH high | Sound |
| DRV8316 unpowered / deaf / fails shorted | Row 3 / row 4 / R302 fuses → row 3 | Sound |
| SPI3 fault; INA239 ID lost | Hold with retry / weapon off, drives on VBAT_SNS | Sound |
| C2 short (drum stopped) | Gate → INA239 path | Sound |
| C2 short (drum spinning); R2/R3 open | Row 0 hold for the whole coast-down / SOVL fold-back loop or silent loss | **R19D-02** |
| Compute-board reboot | ARM falls in 52–164 ms [S arm.out]; command timeout; new session; self-test; edge + throttle zero | Sound |
| Radio drop | ≤ 0.5 s → ARM toggle and commands stop; throttle-zero interlock | Sound |
| Switch opened mid-match, weapon motoring | Row 2 supply restarts; row 0 (not suspended) holds after 100 ms | Safe, bounded |
| Switch opened while braking | Row 1 looks open → row 0 hold; one D1 overshoot ≈ 10 A × ~24 V × ≤ 0.3 ms ≈ 70 mJ | Safe |
| Switch opened, drum coasting, disarmed | Row 0 hold after 100 ms (with an idle-inclusive estimate, N1) | Safe |
| Switch opened, drum stopped | Bus reaches the 9.2 V buck cutoff in ~28 ms at idle (sooner under drive load), before row 0 matures | Safe |
| Regen into a full pack (switch closed) | 10 A × 74 mΩ → 17.5 V < 18.5 V coast; a real BOVL needs ≥ ~31 A or a high-R pack → row 1 restart, cap 3/10 s | Sound |
| Pit: drive phase swap / encoder A/B swap | Sign check → wiring-fault latch | Sound |
| Pit: J2/J3 sensor swap | Row 7 → both sensorless (correct) | Sound |
| Pit: L/R motor-wire bundles crossed | Row 7 → sensorless with translation reversed; following the report masks it | **R19D-01** |
| Pit: weapon wires swapped | By-eye direction check [D l.764] | Accepted (settled) |
| Power cycle with latches | Board latch lost; compute board mirrors the weapon latch until operator clear; drive latches re-detected at boot; switch-open hold not persisted | Sound |
| MCU reset / IWDG | Latch word honoured; boot coasts both chips (CTRL4 0x0C90), releases only unlatched drives, aligns one at a time; ARM edge + throttle zero | Sound |

## 3. Checked and found sound

* **Round-18 changes:**
  * Row 1 now uses the magnitude of the first two post-alert conversions, not the sign.
  * Bounces during regen go through row 0's 100 ms persistence.
  * The row 0 suspension restarts the mean (bounded by the drum's hold-up time).
  * Drive row 7 now needs the aligning drive's own encoder to stay still.
  * OSSI = 1 on TIM8/TIM20.
  * The boot releases the DRV_OFF pin and writes a per-chip Release, then sets MOE.
  * The latch word holds "supply unstable" and the drive row 7 flag.
* **Parity words.**  0x0C90 and 0x0D10 are the right coast/release words, and the rewrite ends coasted.
* **No operator-less re-arm into a latch.**
  * Automatic restarts happen only inside a continuous ARM.
  * An ARM fall, a reset, a link recovery or a clear needs a new edge and throttle zero.
  * Clearing needs the operator, and the compute board disarms before it persists a latch.
* **No masked short** in the weapon rows.  The drive-side exemption applies only while the FETs are off (N4).
* **§1 margins** (hardware unchanged):
  * DRV8316 VM: 0.80–2.26 V/µs loaded bounce, 2.66 V/µs at −40 °C ESR, ≤ 2.09 V/µs re-close, ≤ 0.005 V/µs closure, all against 4 V/µs [S hotplug.out].
  * Q7: 16.5 / 22.0 W, 53.8–56.9 mJ.
  * Reversed pack: 13.1 A with D10.
  * ARM: 2.50–2.95 V against VT+ ≤ 2.15 V, 7–10 edges, disarm 52–164 ms [S arm.out].
  * Spin-up: 22.1 A peak, 14.06 V minimum [S spinup.out].
  * Weapon bridge at 60 mA / 6 nH: VDS 29.4 V, SH −4.58 V [S bridge.out].
  * D1 clamp 32.4 V against 35 V (C1) and 40 V (DRV8316).
  * SOVL 38.0 A against the 32 A budget.
  * BOVL 19.0 V against the 20 V minimum DRV8316 OVP.

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R19D-01 | MINOR | Crossed L/R drive motor bundles give the same evidence as swapped J2/J3 cables.  Row 7's sensorless response then drives with translation reversed, and the "swap J2/J3" report leads the crew to a consistent-but-mirrored wiring that passes every check.  Fix: ambiguous report + a pit forward-direction check (optionally by IMU) |
| R19D-02 | MINOR | The INA239 plausibility gate covers only "reads 0, drum stopped".  C2 shorted with the drum spinning still holds the robot for the whole coast-down (≥ 10 s).  An open R2/R3 saturates the reading: a SOVL fold-back loop with no floor on the shared budget, or a silent loss of SOVL and switch-open detection.  Fix: two-sided measured-vs-estimated check → INA239-failure path; "no possible source" gate; fold-back floor |
| R19D-N1..N4 | NOTE | Idle term in the row 0 estimate; row 1 VBUS conjunct under drive load; weapon/drive row-1 precedence; nFAULT still low after Release + IC_STAT FAULT poll |

**Verdict: 0 BLOCKER, 0 MAJOR, 2 MINOR, 4 NOTE.**  Every walked scenario ends safe and bounded.  No masked short and no
operator-less re-arm was found.  The one reversed-drive path is a pit wiring error that row 7 misnames (R19D-01).  Both MINORs
are firmware-contract and procedure text; no hardware change is needed.
