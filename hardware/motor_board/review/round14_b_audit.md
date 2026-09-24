# Round 14 — B: consistency audit (rev L, after the round-13 text edits)

Scope: the whole package, with emphasis on DESIGN.md internal consistency after rounds 12/13.
Out of scope: board area/fit, prose style.  Settled items in review/CHANGES.md are not re-raised.

## Regeneration

Package copied to `/tmp/r14b/`; `design/motor_board.py` → `237 refs (205 placed components), 160
nets, 67 BOM lines` / **`checks: OK`**; `design/calcs.py` regenerated `calcs.md`.  `diff -rq`
against the tree: **no differences** (netlist.csv, nets.md, bom.csv, mcu_pinmap.md, calcs.md all
match the generators).

## Counts, refs, LCSC

- bom.csv: 67 lines, Qty sum 199; DNP C110–C112/C114–C116 (6) absent from the CSV and listed as
  DNP in BOM.md:5, DESIGN.md:37, :621.  README:7, BOM.md:4–5, DESIGN §1 agree.
- Every refdes named in DESIGN/BOM/README/calcs/spice/datasheets READMEs exists in netlist.csv.
- All 28 LCSC numbers in the BOM.md "Parts to watch" table match bom.csv.  "ICs U1–U14 (11
  lines)" is right.
- mcu_pinmap.md matches every pin/AF cited in DESIGN §3.3/§3.4/§8 (PC13 TIM1_BKIN, PB7
  TIM8_BKIN, PC15/PC14/PD2/PA12 GPIO, PB11 COMP6_INP, PA0/PA1/PA2, PC3 OPAMP5_VINP, SPI3 PC10–12,
  CS PC9/PB4/PA11).  TP10 = VBAT (netlist), so §9 step 0 is wired as described; L_VM/R_VM carry
  only R302/R402 as a DC path from VBAT (nets.md:63, :106, :123).
- Datasheet checks for the round-12/13 text: DRV8316C 3x PWM (SLVSH07 Table 8-4: INL = 1 → INH
  selects L or H; Hi-Z only with INL = 0) and 6x (Table 8-3); DRV8323 H-device tRETRY 4 ms (typ
  only); MT6701 power-up ABZ absolute-position train is a register option, default off, no ABZ for
  50 ms after power-up; MT6701 55 000 rpm.

## Findings

### B14-01 (MAJOR) — the per-drive hold-off cannot coast: TIM8/TIM20 MOE = 0 is a brake

DESIGN.md:599 (round-13 R13D-01 text): "**Per-drive hold-off:** stop one drive with its own timer
(TIM8 or TIM20 MOE = 0, outputs to the coast idle state), keeping the shared DRV_OFF for faults on
both drives".

There is no coast idle state.  INLA/B/C of U3/U4 are tied to +3V3 (DESIGN.md:213, nets), so in 3x
PWM mode each phase is L (INH = 0) or H (INH = 1) — SLVSH07 Table 8-4.  With MOE = 0 the timer
forces INH to OISx: all low sides on or all high sides on, both a short brake.  The package
already says so elsewhere: DESIGN.md:214 "a timer break forces the low sides on = brake";
DESIGN.md:587–588 "a halted core then leaves the drives braking".  Only DRV_OFF (shared) gives
Hi-Z.

Consequence: a per-drive latch at speed short-brakes that motor (calcs.md:137: ~50–80 A
uncontrolled into ~0.2–0.3 Ω) until the DRV8316's 16 A latched OCP Hi-Zs it — one wheel locks
briefly and the stop itself raises a new fault.  (For a DRV8316 that has reset into its default 6x
mode, idle INH = 1 does give Hi-Z per Table 8-3, but the same idle level on a configured 3x chip is
all-high-sides-on, so no single idle level coasts both cases.)

Fix (text): state that a per-drive stop is a brake (choose OISx = 0 and accept it, relying on the
DRV8316 OCP at speed; or ramp that drive's current to zero first), or use DRV_OFF (both drives)
whenever a coast is required and restart the healthy drive afterwards.

### B14-02 (MAJOR) — lost-encoder probe gives a false sensor fault whenever a wheel is stalled under torque

DESIGN.md:607: "**Lost encoder at low speed:** no encoder edge for ~150–200 ms while torque is
commanded → step the commanded angle by a few electrical degrees; still no counts → that drive
switches to sensorless and reports a sensor fault".  §9 step 6 (DESIGN.md:666) tests only the true
positive.

With a healthy encoder, "torque commanded, no edges for 150–200 ms" is the normal state of a
wheel pushing an opponent or a wall, or of a small torque below the gearbox breakaway.  Shifting
the current vector by δ = a few electrical degrees changes the torque by cos δ (−0.1…−0.4 % for
3–5°), so a stalled rotor does not move; one count is ~0.5° electrical at the motor (4096
counts/rev, ~6 pole pairs), and drivetrain compliance for a 0.4 % torque change is far below that.
So the probe cannot distinguish "sensor lost" from "rotor held", and every pushing stall longer
than ~0.2 s flips that drive into sensorless mode — which has no usable torque at standstill —
exactly in a pushing match.  No return to encoder mode is specified either.

The probe only works when it can actually move the rotor: e.g. drop the torque command to zero /
inject a d-axis-only pulse or a large (≥ ~45–90°) angle step briefly and look for the rotor
springing back through compliance/backlash, or require the probe to be run only when the commanded
torque is below a known friction level; and specify how the drive returns to encoder mode (e.g.
encoder counts agree with the observer again at speed, as in the plausibility check).

### B14-03 (MINOR) — single-chip DRV8316 events still take DRV_OFF high (both drives), contradicting the per-drive hold-off and the §9 step 6 test

- DESIGN.md:605 (DRV8316 row): "on a mismatch or NPOR = 0 …: DRV_OFF high, rewrite the sequence,
  report."
- DESIGN.md:606 (timers row): "R_nFAULT (PC15) EXTI at top priority → DRV_OFF high."
- versus DESIGN.md:599: single-chip CP-UV/NPOR/register mismatch "counts toward that drive's
  latch"; "per-drive hold-off … keeping the shared DRV_OFF for faults on both drives"; and
  DESIGN.md:667: "hold R_nCS high (a dead U4) → only the right drive latches, the left keeps
  running."

With R_nCS held high the U4 read-back is 0x0000 → per :605 DRV_OFF goes high and the left drive
stops on every recovery attempt until the latch, so the step-6 expectation is not what :605/:606
specify.  Fail-safe in direction, but the firmware contract now says both things.  Fix: in :605 and
:606 stop only the affected drive (subject to B14-01), or say explicitly that DRV_OFF goes high
first and the healthy drive is restarted.

### B14-04 (MINOR) — INA239 SOVL classified two ways in the same row

DESIGN.md:599, supply class (not counted): "an INA239 SOVL alert (DIAG_ALRT) with no comparator
flag (bus recharge after a bounce, **or over budget**)".  Same row, other events: "SOVL with no bus
dip and no comparator flag (overload) → fold back, **> ~3 within a second latches the weapon**".
An over-budget SOVL is therefore both uncounted supply class and a counted overload.  The
round-13 N-note (CHANGES.md:276 "classes for … overload SOVL") intended the second; the supply-class
clause should read "SOVL with no comparator flag **and a VBAT dip** (bus recharge after a bounce)"
and drop "or over budget".

### B14-05 (MINOR) — §3.5 compute-board re-arm rule ignores the reset-persistent weapon latch

DESIGN.md:355–356 (compute-board requirements): "when the heartbeat reports 'ARM edge required',
hold W_ARM_CLK low for ≥ 250 ms, then toggle again" — an unconditional automatic re-arm.
DESIGN.md:599: "a weapon latched before a reset stays latched and is reported, and the compute
board must not auto-re-arm it"; clearing needs a "clear faults" frame plus disarm and a new ARM
edge.  Hardware is safe (an ARM edge alone does not clear the latch), but §3.5 is the list the
compute-board designer works from and has neither the exception nor the "clear faults" frame.  Add
"unless the heartbeat reports a latched weapon fault (then only on an explicit operator clear)".

### B14-06 (MINOR) — revision labels not updated for round 13

- DESIGN.md:9: "rev L rounds 11–12"; CHANGES.md:264 "Round 13 … → rev L (text only)".
- README.md:7: "after twelve adversarial review rounds"; there are thirteen (CHANGES.md
  rounds 1–13).
Same class of item as R12B-03.

## Notes

- N1. DESIGN.md:666 "sensor fault within ~0.2 s" vs :607 150–200 ms of no edges **plus** the probe
  step: the report comes slightly after 0.2 s.  Say ~0.2–0.3 s (moot if B14-02 changes the probe).
- N2. DESIGN.md:599 VDS-OCP vs UVLO discrimination (< ~3 ms vs ~4 ms nFAULT low) relies on the
  H-device tRETRY, which SLVSDJ3D gives as 4 ms **typ only** (DRV8323.pdf, tRETRY table).  Measure
  it on the bench (§9 step 4) before fixing the 3 ms boundary.  With the "VDS OCP stays short class
  even if a supply indicator coincides" precedence, any supply event holding nFAULT ≥ ~3 ms latches
  the weapon; fine for the 0.1–1.2 ms bounces analysed, worth stating.
- N3. The §7.16 boot INH one-shot test (DESIGN.md:552–553) is not placed in the §8 boot order
  (DESIGN.md:589–592); it needs W_EN high and must run before the first ARM qualification.  One
  clause in the boot order would do.
- N4. DESIGN.md:599 "latches … lost only at power-off": the backup domain is on +3V3 (VBAT pin 1),
  so a sag deep enough to collapse +3V3 (not just reset the MCU) also clears the latches.  Accurate
  enough, but "power-off or a +3V3 collapse" is the honest wording.

## Checked and consistent (no finding)

§7.21:576 and §8 fast-trip row :608 both defer to the §8 fault classes (R13B-01 holds); §7.16
boot test (≥ 30 µs one-shot, τ 8.7 µs = 68k‖10k × 1 nF, only when W_Vx ≈ 0, fail → latched);
§8 start angle (two-step alignment, offset not count zeroing, ≤ 0.4 mm wheel travel checks out:
180° el / 6 pp / 28.5 × 135.7 mm), Z offset stored at §9 step 5 and checked at the first Z, MT6701
power-up ABZ train off in both §8 and §9 step 5; speed cap ≤ ~50 k rpm vs 55 k rpm and the ~47 k rpm
duty-capped top speed (§3.3, calcs §10); §9 step 0 (TP10 = VBAT, R302 the only DC path, measure on
R302's pads), referenced correctly from §7.16:548; §6.6 DRV_OFF note (PC13–15 2 MHz / 30 pF limit;
PC14 the only output of the three); §6.6 → §9 step 6 VM scope check; §9 step 3 armed soak and TP
assignments; hotplug.out figures quoted in §3.1/§3.3/§5/§7.2 (2.09, 0.8–2.26, 2.66 V/µs; 22.0 W;
54–57 mJ); arm.out figures; calcs §11 heat budget 4.4 W = §4; spice/README and datasheets/README
match the files present.

**Counts: 0 BLOCKER, 2 MAJOR, 4 MINOR, 4 NOTE.**
