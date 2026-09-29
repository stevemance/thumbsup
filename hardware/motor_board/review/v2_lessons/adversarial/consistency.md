# v2 lessons memo: consistency red-team

Memo checked against DESIGN.md (§1, §3.3-3.5, §5, §6), PLACEMENT.md, FAB.md, round3_e_system, r2_drive,
round13_a and hardware/REVIEW.md. Keys: R = README, D = design.md, P = process.md, E = electrical.md,
C = critique.md.

## Critical

**K1. The pin-swap rule ignores the reset, boot and sampling constraints.**
The memo lists only the AF check, the encoder CH1/CH2 rule and "specific ADC/COMP pins" (R §3 Pins, C §3).
- R §1.2 and C §3 say TIM1's six outputs "sit together on pins 35-44" (PA8-PA10, PB13-PB15). D §11 lists
  "ADC5 PA8/PA9" as fixed (L_SOA_F/L_SOB_F, the only ADC5 inputs; mcu_pinmap rows 42/43). You cannot have both.
- DESIGN §3.5 says "the STM32 ROM bootloader toggles some weapon-control pins". The ROM UART is on PA9/PA10. Moving
  a W_INH line onto PA9/PA10 puts a line the bootloader drives onto a gate input.
- The JTAG pins have pulls at reset (PA15 and PB4 pull up, PA13 pull up, PA14 pull down). PB4/PB6 have UCPD
  dead-battery pull-downs (DESIGN §3.4, l.265). PB8 is BOOT0. PC13-PC15 are limited to 2 MHz / 30 pF (round13_a N-03).
  "Everything off in reset" (DESIGN §1 Safety) depends on which pin carries which enable.
- The firmware contract samples ADC1/ADC2 simultaneously with "3 ranks everywhere" (DESIGN §8 STM32 row). A CSA
  swap to another ADC changes the sampling architecture, not only the AF.

*Fix:* add a pin-legality checklist that `motor_board.py` or the AF checker enforces. It covers: reset pull state
and bootloader and JTAG activity for every weapon or drive enable, INH, INL and DRV_OFF pin; the dead-battery and
BOOT0 pins; the PC13-PC15 drive limits; and ADC grouping and simultaneity. Correct R §1.2: TIM1 on one edge
conflicts with ADC5 unless L_SOA/B move, and that is a firmware-contract change.

**K2. "J1 anywhere on the bottom" is treated as free, but J1 fixes where the compute board sits.**
The memo's only J1 rule is "beside the MCU, UART/SWD/NRST facing it" (R §3, C §4). What it drops:
- PLACEMENT §5.2 and FAB "Before ordering": the compute board mirrors J1 pin 1, keeps clear zones under every
  bottom wire joint (JBAT, JW, JL, JR) and J4's pins, and keeps the Pico W antenna and its USB port beyond this
  board's outline.
- The outline is now fixed (no notch). The antenna therefore has to overhang one end, and J1's position decides
  which end that can be.
- E3-09: the drive ICs' thermal copper must not face the Pico.
- E3-04 / DESIGN §6.2: J1's GND pins must sit outside the pack-return path. C §4 puts J1 at y 15-29, which touches
  the y < 18 power band.

C §4 flags it as an interface change, but README §5 does not list it.
*Fix:* make "compute-board interface" an input gate before floorplanning. It needs: Pico W antenna and USB end,
clear zones, J1 mirror coordinates, mated height, and a re-run of the L2 plane-drop solve for the chosen J1 spot.
Add it to README §5 as a user decision.

## Major

**M1. The gate corridor is both kept and blamed.**
- Kept: R §2/D §13 keep "the bridge … and the gate corridor" as one rigid macro, and D §15 lists the bottom gate
  corridor under "keep-outs that paid off".
- Blamed: R §1.5 and C §11.5 name "the bottom reserved as a gate corridor" as a root cause.
- Dropped: C §4 says "no reserved gate corridor: gates route on L1".
- Unresolved: E §5 flags the conflict with the L3 VBAT feed and leaves it open.

The high-side gate pins sit at the front of each cell (PLACEMENT §7), and on L1 the cell's VBAT pour and shunt row
lie between them and U2. The high-side gates cannot stay on L1 without cutting the commutation loop. The "reuse the
geometry (route_blocks 1-2, pregrow_cellc.json)" rule also carries 6-layer layer assignments (L4/L6 gates over L5).
*Fix:* one decision in README. Low sides go on L1 through the shunt gap. High sides get a narrow bottom corridor,
sized from the 6 pairs, with L3 GND under it, and the L3 VBAT width is re-budgeted around it (E §2's ≥ 5 mm). Reuse
the cell placement only, not its routed copper.

**M2. Bottom-side stacking contradicts DESIGN §6.13 and the thermal keep-outs.**
- DESIGN §6.13: "Loop-critical parts (bridge caps, CSA filters, DRV decoupling, gate network, buck loop) stay on the
  same side as their IC." C §4, however, puts the MCU decaps and ADC RC filters on the bottom under a top U1, and U3's
  4 × 10 µF under U3.
- U3's 10 µF would sit inside the "pad + 1 mm" thermal keep-out (PLACEMENT §4, E §15).
- R §3 wants fan-out via rows "outside U1's body", but bottom decaps "directly under their pins" need vias inside
  that ring.
- E §15 asks for an "exposed bottom GND pad" under U3/U4, which faces the compute board (E3-09).

*Fix:* the MCU decaps (C60-C66, C71) and the CSA filters go on the same side as U1. Only slow, DC parts may go
underneath. The DRV bulk goes beside the IC on top, or on the bottom outside pad + 1 mm. Drop the exposed bottom
pad, or show it does not face the Pico.

**M3. The DRV8316 bulk-cap distance has three values.**
DESIGN §6.6 says "4 × 10 µF within 2 mm". The memo says "within 3 mm" (R §3, E §8). PLACEMENT §5.3 accepted up to
19 mm, and the memo never revokes that. This limit protects the 4 V/µs VM abs max, so it is a hot-plug item.
*Fix:* state "DESIGN §6.6 (2 mm) is restored; PLACEMENT §5.3 relaxations are void in v2". Any exception needs a
sim_hotplug re-run, recorded in CHANGES.md.

**M4. DRV_OFF: the memo contradicts itself, and the safety angle is missing.**
- C §9 lists DRV_OFF as "can be long … harmless" and C §4 accepts a "~60 mm span". E §13 says ≤ ~50 mm. v1 had
  130 mm with 5 vias.
- The real limit is PC14's 30 pF (round13_a N-03: 50-80 mm ≈ 15-25 pF with TP8). The thin prepreg the memo
  recommends raises the pF per mm.
- R50 is a single 10 k pull-up, while each DRV8316 has an internal 100 k pull-down (round10_b). A broken branch
  leaves that chip enabled and outside the MCU's coast control.

*Fix:* replace the length rule with a capacitance budget (trace + vias + TP8 + 2 pins ≤ ~25 pF, computed for the
chosen stack). Put R50 at the branch point. Ask the user whether a second pull-up (an added part) at the far chip
is wanted.

**M5. The ARM charge pump has two locations, and the safety pulls are not placed.**
D §F7 puts "U14/C15/D9 at pin 19" of J1. R §3 ("U6/U14 between MCU and U2") and C §4 (U14, D9, C15 at x 50-56)
put it by U2. Placing it by U2 runs the ≥ 500 Hz W_ARM_CLK square wave across the logic core, against DESIGN §6.8
("W_ARM_CLK/C15/D9 away from MB_TX and switching nodes").
*Fix:* keep the charge pump at J1 pin 19 and run the DC level W_ARM_S to U6 and PD2. Add a rule that the safety
pull-downs sit at the receiving end, so a broken trace reads "off": R19 at U6/PD2, R40 at U2 ENABLE, R47-R49 at U6,
R18 at J1.

**M6. No per-side area budget, and the fallbacks break the user's constraints.**
- Moving U1, J3's channel and U7 to the top adds ~250 mm² to v1's 1731 mm² of top courtyard. That reaches ~66 % of
  2987 mm², about the 69 % PLACEMENT §1 called "full" at 75 mm.
- The bottom loses the area under the bridge, the thermal pads and U1's escape field.
- C §11.1 and §6 fall back to "add ~5 mm of length or move the BMS off the board". The outline is fixed, and
  moving the BMS removes parts.

*Fix:* before the floorplan, compute a courtyard budget per side under the v2 rules (hot on top, stacking rule,
keep-outs), with and without the shrinks. Delete the grow and remove fallbacks. If it does not fit, the only
levers are shrinks the user approves.

**M7. "Every GND pad gets its own via within 0.5 mm" is overfit to 6 layers.**
v1 needed ~63 late GND vias because its L4/L6 fills fragmented. On 4 layers a top GND pad beside an L1 GND pour
does not need its own via. A blanket rule adds ~100+ vias in the exact area whose via sites were the root cause
(R §1.1), and the "~1.1 vias per connection" budget does not count them.
*Fix:* reserve a GND via per decap and per IC GND pin. Other GND pads may share a pour or a via within ~1.5 mm.
Count GND vias in the via-site capacity per IC.

**M8. The layer jobs for the rails and L3 disagree.**
+5V goes "on L3 or a top pour" (D §E) or as an "L1/L4 trace" (E §D). The rear of L3 is "GND pour everywhere else"
(E §B), "signal channels plus +3V3/+5V" (C §8), "signals + rail trunks" (P §0) or GND with "a few slow lanes"
(R §3). These change the capacity model the routability gate needs.
*Fix:* one layer-job table in the README: each rail gets one layer and width, and the L3 GND-reference region
fixes the lane budget.

**M9. The test strip contradicts itself and silently drops pads.**
- C §10 puts VBAT, +5V, +3V3 and the debug pads in one rear strip "inline on each net's existing route (no stubs)".
  VBAT's route is in the front power band, so a rear VBAT pad needs a pack-derived stub across the logic region.
- The same list omits TP2-TP4 (SWDIO/SWCLK/NRST) and adds a Tag-Connect. That is a removal plus an added footprint.
*Fix:* keep TP1-TP12 (DESIGN §3.4). VBAT and 5V pads sit at the edge of their own blocks, and a VBAT pad goes behind
a net-tie or a 0.2 mm tap. Any TP removal or Tag-Connect goes to README §5.

**M10. Process bias: "build a PathFinder router" versus what the user asked for.**
P §14 quotes the user's "bias more towards … hand-routing … vs autorouting script dev". R §3 and P §5 still make a
global negotiated-congestion router, with a < 2 min pass and true pad shapes, a mandatory step. The tool does not
exist and the 2 min target is unproven.
*Fix:* the gate is metrics (crossings, cut-line demand, via sites). Routing is hand or interactive for the
channels, plus the existing A* for short hookups. A congestion router is optional, time-boxed (e.g. ≤ half a day)
and shown to the user before it is used.

**M11. The floorplan is anchored on v1.**
- C §4 copies v1's front-18 / rear-17 split, the 41 mm bridge band and the pack at the front-left, then only
  shuffles the logic.
- J3 sits at x 52-64, 15-20 mm from U4/JR, and J2 at x 26-37. DESIGN §6.9 says "J2/J3 at the board edge near the
  drive ICs". The encoder cables go to the drive motors, whose exits the user wants at the rear corners.

*Fix:* score ≥ 2 floorplan candidates (e.g. J2/J3 at the rear corners, or a bridge compacted toward the weapon
exit) with the same metrics before choosing.

**M12. Part shrinks lack the footprint-verification lesson.**
hardware/REVIEW.md F01/F04 (symbol pin ≠ pad function, which parity cannot see) and E3-15 (1:1 print of custom
footprints) apply to every package change in README §5: U6 WQFN, J4 PH/GH, vertical J2/J3, C1, D2/L1.
- C1 also needs its ripple (2.8 A) re-checked and sim_hotplug re-run.
- J2/J3 pin 1 is still unconfirmed against the mating cable (DESIGN §6.9).

*Fix:* each shrink carries a pad-function check, an LCSC stock and class check, and the sims it affects.

## Minor

- **m1. The bottom height limit.** README §5 says "≤ 1.1 mm parts", but PLACEMENT §5.1/§5.2 record that the user
  relaxed it (J3 3.35 mm, U1 1.6 mm on the bottom). State the real limit: mated height minus the compute board's
  top parts.
- **m2. A lesson the memo misses.** "MCU on top" is not new: DESIGN §6.13 already listed U1 on top, and PLACEMENT
  §5.1 deviated from it. The real lesson is that any deviation from DESIGN §6 needs routability evidence, not just
  space.
- **m3. Documentation debt.** DESIGN §6.1/§6.2 and FAB (layers 6, JLC061611-1080B, 0.09 mm rules, the via-in-pad
  list, "+3V3 fill") now describe the abandoned board. PLACEMENT.md is v1's. The memo has three floorplans (README
  §3, D §F, C §4). Name C §4 as the draft, list the docs to revert at setup, and check the DESIGN §6 rules into DRC
  (E §14).
- **m4. Weight is unquantified.** A full 1 oz layer is ~0.94 g here, and the 1.2 mm laminate saves 2-3 g. Never
  trade GND integrity for copper weight. Check 1.2 mm against flex (E3-10) and stack availability.
- **m5. Unfused pack copper.** No spacing rule for exposed BAT_IN/PSW_S/VBAT against GND (debris). D4 puts PSW_S
  on the bottom face, and there is no TVS D1 loop rule. *Fix:* ≥ 0.3 mm on unfused pack nets where it fits, a tight
  D1 loop, and a list of pack-potential pads on the bottom.
- **m6. Mechanics and assembly are dropped.** Rails and mouse-bite tabs away from rear-edge pads (FAB), iron access
  to the bottom joints next to 5.5 mm J1, bottom-first reflow, J4 THT, C1 staking, D3 visible from outside, and the
  "B−/B4+" and "VS/T" silk (DESIGN §6.9).
- **m7. The cable-exit reading.** "Top-right" is read as front-right; confirm it with the user.
- **m8. The thresholds are uncalibrated.** "≤ 70 % cut-line capacity", "< 10 % sweep yield" and "1.1 vias per
  connection" are opinions. Compute the v1 board's cut-line demand at its known failures to calibrate them.
- **m9. Missing tooling lessons.** v1.2 had an automated `placement.check` for the Pico RF keep-out and chassis
  fit (REVIEW §7); v2 needs one for the compute-board clear zones and heights. Editing sheets in place drifts from
  `motor_board.py`, the declared netlist source: name one path for pin swaps (motor_board.py → nets → sch → pcb
  parity) and regenerate mcu_pinmap.md from it.
