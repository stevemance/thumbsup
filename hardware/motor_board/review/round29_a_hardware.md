# Round 29 A — hardware review (rev L, after the round-28 text changes)

Scope: the round-28 text changes (Z-count check, bounce figures, idle current, LiHV, §9 step 6),
checked against the MT6701 and STM32G474 datasheets, the netlist and the sim outputs, plus a
re-check of the encoder signal path.

## What was checked

* **Regeneration.**  I copied the package to /tmp (no datasheets/review) and re-ran
  `design/motor_board.py` (237 refs, 160 nets, 67 BOM lines, "checks: OK") and `design/calcs.py`.
  The regenerated `netlist.csv`, `nets.md`, `bom.csv`, `BOM.md` and `calcs.md` are byte-identical
  to the tree.  `spice/*.out` are newer than their scripts.  Round 28 A already reproduced the
  bounce sims, so I did not run them again.
* **Encoder path (netlist).**  J2/J3 pin 5 → R112/R116 1 k → U9/U10 3A → 3Y → PB0 `TIM3_CH3` /
  PB10 `TIM2_CH3`.  A/B go to PC6/PB5 (`TIM3_CH1/2`) and PA15/PB3 (`TIM2_CH1/2`), matching
  `mcu_pinmap.md`.  The 4.7 k pull-ups against the MT6701 push-pull output draw 0.58 mA, inside
  its 2 mA VOL rating (MT6701 datasheet, digital I/O table, p.8).  The 1 nF filter caps are DNP.
* **MT6701 Z generation** (MT6701CT-STD v1.9):
  * §7.3 p.12: Z marks the 0° position.
  * p.14: the Z width can be 1, 2, 4, 8, 12 or 16 LSB, or 180°.  The chip puts out exactly one Z
    per turn ("芯片设计保证了每圈只出一个Z脉冲").
  * Fig. 11/12 p.15: 1024 PPR = 4096 steps, so 1 LSB is one quadrature count.
  * p.16 and p.30: `Z_PULSE_WIDTH[2:0]` is at 0x32[6:4] (EEPROM); 0x0 and 0x7 both give 1 LSB.
  * The same byte holds `HYST[2]` (bit 7) and `ZERO[11:8]`, so it must be written read-modify-write.
    That is an off-board programming detail.
  * **Verified:** "Z pulse width 1 LSB" in §9 step 5 is a real, programmable setting.
  * At the 50 k rpm encoder cap, 1 LSB is 1/(50000/60 × 4096) ≈ 293 ns.  The ICxF ≤ 0b0011
    filter (8 × 5.9 ns ≈ 47 ns) passes that.  The G474 needs only 2 Tck on TI1/TI2 (datasheet
    Table 84, p.171).
* **STM32 Z capture and the direction bit.**  CH3 input capture on TIM3/TIM2 works while
  CH1/CH2 run the encoder: the capture channels are independent.
  * The G474's hardware index input is on **ETR** only (Table 84, tW(INDEX) "on ETR input").
    TIM3_ETR is PD2 (used for W_ARM_S) and TIM2_ETR is PA0/PA5/PA15 (all used), so the CH3
    software capture is the right choice.
  * In encoder mode `TIMx_CR1.DIR` is read-only and shows the count direction (RM0440 TIMx_CR1;
    the reference manual is not in `datasheets/`).  The hardware does not latch it with CCR3, so
    the ISR reads it afterwards.
  * This is sound.  At speed the direction cannot reverse within ISR latency, and near standstill
    the latency is far shorter than one count period.
* **Round-28 numbers:**
  * 1024 PPR × 4 = 4096 counts per turn; 90° electrical = 4096/6/4 ≈ 171 counts; 30° ≈ 57 counts.
    All consistent.
  * Bounce: §1 (≤ 2.75 V/µs in 0–50 °C, 2.82 only at −40 °C), §3.3, §5, §7.2 (≤ 2.26 / ≤ 2.33 to
    ~1.3 ms, 2.66 / 2.82 at −40 °C, re-close from ~3.8–10 V) and calcs row 87 agree with each other,
    with `hotplug.out` (4.4–9.3 V before re-close; 2.212 / 2.258 / 2.662 V/µs) and with round 28 A's
    reproduced table.  The §1 figure of 2.75 V/µs is a loose but true upper bound for 0–50 °C
    (actual ≤ 2.33).
  * LiHV: 4 × 4.35 = 17.4 V, plus 10 A × 70 mΩ = 18.1 V, or ~18.6 V with a ~120 mΩ cold or old pack.
    At 20 A: 17.4 + 1.4 = 18.8 V.  Consistent with §8's "~1.4 V at 20 A".
  * §9 step 6 figures:
    * SMBJ20A (BORN table, p.3): VBR 22.2–24.5 V, VC 32.4 V at IPP 18.6 A.
    * At 10 A the clamp is 24.5 + 7.9 × 10/18.6 = 28.7 V.  Through the 68 k/10 k divider that is
      3.68 V nominal, 3.75 V worst (1 %).  Matches.
    * "4.0 V at ~12–14 A": the room-temperature linear model gives 14.5–16 A.  A TVS warmed by
      the clamp (VBR +~5 %) gives ~12 A.  The stated range is on the safe side.
    * "The drives' OVP usually cuts in first": correct.  DRV8316 OVP trips at 20–22 V, which is
      below D1's 22.2 V minimum VBR.

## Findings

### R29A-01 (MINOR): the new slipped-magnet check also trips on normal low-speed braking, reversals and being shoved

The rule is at DESIGN.md l.615: "below observer speed, encoder speed moving against the commanded
torque for ~30 ms also marks the encoder suspect".

Read as written, *speed opposite in sign to the torque command*, this is also true in normal
operation:

* **Braking or reversing below observer speed.**  During every deceleration the speed is positive
  and the torque negative.
  * Observer speed is ~3–5 k rpm motor = 0.24–0.40 m/s at the wheel (43.2 mm wheel, 28.5:1).
  * At the traction limit (2 motors × ~1 A × 2.73 mN·m/A × 28.5 × ~0.8 / 21.6 mm ≈ 5.8 N on
    0.454 kg ≈ 12.7 m/s²), the last stretch to zero takes 19–32 ms.
  * Any gentler speed-loop deceleration takes longer than 30 ms.  So an ordinary stop or direction
    change from walking pace marks the encoder suspect.
* **Being out-pushed.**  The robot commands forward torque while an opponent pushes it backwards.
  That is common in 1 lb matches, and the speed stays against the torque for as long as the push
  lasts.
* **Consequence.**  The drive is sent to sensorless exactly where sensorless cannot work (below
  observer speed).  §8 does not say whether the "edges resume and a Z matches" return applies to
  an encoder marked suspect.  If it does not, the drive stays weak for the rest of the match.  §9
  step 6 has no test that would expose this: the wall stall has zero speed, and the shove test
  is only during alignment.

Round 28 D's suggested check (round28_d l.74) also had a "commanded |Iq| ≥ ~0.5 A" condition.
That condition was dropped, and it would not have excluded braking anyway.

**Fix (text, l.615).**  Key the check on what a reversed torque constant actually does: the
**speed magnitude grows** in the direction opposite to the command.
* Suggested rule: |Iq| ≥ ~0.5 A and the encoder speed moving *away from zero* against the command
  for ~30 ms.
* This excludes braking and reversal.  It still catches a slip: a reversed offset gives
  α ≈ 2.7 mN·m / ~1.4×10⁻⁷ kg·m² ≈ 2×10⁴ rad/s² at 1 A, so ~5 k rpm within 30 ms.
* For shoves, either:
  * compare the acceleration with the model (a slip gives the full motor-plus-reflected-mass
    acceleration, about the size of the command; a push through 28.5:1 gives far less for the
    same |Iq|), or
  * answer a trip with a sign-checked re-alignment (the row 6/6a path, which also repeats when
    shoved) instead of going straight to sensorless.
* Add a §9 step 6 case: brake and reverse from ~0.3 m/s, and push the robot backwards against a
  forward command.  Expected result: no "encoder suspect".

### Notes

* **N1: re-referencing on the first Z mismatch trusts Z over A/B.**
  * A noise glitch on the Z line (harness noise is one of the causes the text itself lists)
    produces a spurious "mismatch".  The first-mismatch re-reference then moves the angle by an
    arbitrary amount.
  * The next true Z (≤ 1 motor turn ≈ 4.8 mm at the wheel) mismatches again and marks the encoder
    suspect, so this is bounded.  At a standstill with no torque command, though, the wrong angle
    can wait until the next move.
  * Cheap guard: in the capture ISR read the A/B pin levels (GPIO IDR).  The MT6701 Z sits at a
    fixed A/B state (Fig. 9/11), so reject a Z whose A/B state does not match the one recorded in
    §9 step 5.  This works at the low speeds where the wrong angle matters.
* **N2: "so a reversal does not move it" is off by one for the 1 LSB option.**
  * A rising-edge capture of a 1 LSB Z lands one count apart in the two directions.
  * That is inside "a few counts is drift", so it is harmless.  Firmware should not "correct" a
    ±1 difference that comes only from direction; either use the DIR bit or allow ±1.
* **N3: row 0's "the board alone draws ~100 mA" and the §7.17 / calcs "~95–113 mA" sit above a
  datasheet bottom-up estimate.**
  * DRV8323 IVM 10.5–14 mA (SLVSDJ3D EC table); 2 × DRV8316C IVMS 4–10 mA with BUCK_DIS
    (SLVSH07 EC table).
  * 3.3 V side through the 85 % buck ≈ 23–31 mA: G474 ~30–42 mA at 170 MHz (DS12288 Table 21, p.90) plus
    peripherals; 2 × MT6701 at 10–14 mA (p.7).
  * Dividers and R15 ≈ 3.5 mA.
  * Total ≈ 45–70 mA plus whatever the compute board draws.
  * §9 step 4 already measures the minimum and narrows the band ("≤ half the measured idle").
    Row 0's 30 mA threshold still holds at ~50 mA.  Nothing to change beyond perhaps noting that
    the figure includes a compute-board load (round 27 B-02 made the same observation).
* **N4 (§7.18).**  "~18.1–18.6 V … and trips the 18.5 V coast": only the upper end of that range
  trips the coast.  The point that LiHV is unsupported stands, because §9 step 6 requires < 18.3 V.

## Verdict

**0 BLOCKER, 0 MAJOR, 1 MINOR (R29A-01), 4 NOTE.**

The round-28 Z-count text is right about the hardware:
* The MT6701 1 LSB Z width is real and programmable (0x32[6:4]).
* A slip keeps Z and A/B consistent (§7.3 p.12).
* A CH3 capture with a DIR-bit read is the right method, since the G474 index input is ETR-only
  and both ETR pins are used.

The bounce, LiHV, idle and §9 step 6 figures are consistent and check out numerically.  The
netlist and calcs regenerate identically.  The one issue is the new torque-sign slip check, which
as worded also fires on normal braking and on being pushed.
