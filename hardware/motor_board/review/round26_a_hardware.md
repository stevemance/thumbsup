# Round 26 — A: hardware review (rev L, after the round 25 text changes)

Scope: the round 25 §8/§8.1/§9 changes (CLR_FLT folded into the Release
0x0603 → 0x097D → 0x0D10 → 0x0606; BKINE = 0 window up to ~12 ms; row 0 every-reading run and
its pause keyed on a regenerating FOC torque command, ended by a protective coast; regen limit
as a current limit; the 18.5 V coast classified as row 1; instant coast only with a positive
torque command), and every hardware fact and SPI word they rely on.  Out of scope as before:
area/fit, prose, firmware preferences.

**Result: 0 BLOCKER, 0 MAJOR, 1 MINOR, 2 NOTE.**

## What was re-run

Scratch copy `/tmp/r26a` (package minus `datasheets/` and `review/`, deleted afterwards):

- `design/motor_board.py`: 237 refs, 160 nets, 67 BOM lines, `checks: OK`; `netlist.csv`,
  `nets.md`, `bom.csv`, `mcu_pinmap.md` regenerate byte-identical.  `calcs.py` → `calcs.md`
  byte-identical.
- `spice/sim_arm.py`, `spice/sim_hotplug.py`: identical to `arm.out` / `hotplug.out`.  The
  bridge and spin-up sims were not re-run (nothing since round 20 touches them).

## Verified (no finding)

**SPI words** (SLVSH07 §8.5.1.1: B15 W, B14–B9 address, B8 even parity over the word, B7–B0 data).

| Word | Reg | Data | Parity (ones) |
|---|---|---|---|
| 0x0603 / 0x0606 | CTRL1 (3h) | REG_LOCK unlock / lock (Table 8-18) | 4 / 4 |
| 0x097D | CTRL2 (4h) | 0x7D: bits 7–6 = 01b (reserved, reset 1h), SDO push-pull, SLEW 3h = 200 V/µs, PWM_MODE 2h = 3x, CLR_FLT (W1C, self-clearing) (Table 8-19, p.64) | 8 |
| 0x0D10 / 0x0C90 | CTRL4 (6h) | DRV_OFF 0 / 1, OCP_DEG 1h = 0.6 µs, OCP_LVL 16 A, OCP_MODE latched (Table 8-21, p.65) | 4 / 4 |
| 0x0D94 / 0x0C14 | CTRL4 (6h) | same with OCP_LVL 1h = 24 A (coast / release) | 6 / 4 |

The folded Release is bracketed by unlock/lock, so both CTRL2 and CTRL4 writes are accepted.
CTRL2 0x7D rewrites PWM_MODE with the value already set (3x) — no PWM-mode change while the FETs
operate; step (1) has already rewritten any silently reset chip while coasted.

**18.5 V coast → row 1 classification.**  INA239 VBUS (U7 pin 8) is on VBAT, after RS4
(netlist: `VBAT,U7,8,VBUS`; RS4 pin 1 VBAT_SW → IN+, pin 2 VBAT → IN−).  Switch open: the bus
decays at ~100 mA / ~374 µF ≈ 0.27 V/ms (calcs §7 row "Bus decay"; DESIGN says ~0.2 V/ms), so
from an 18.5 V reading the second post-coast bus conversion (≤ ~0.6–0.9 ms later) still reads
≥ ~18.25 V > 18 V with |I| ≈ 0.2 mA → "looks open" → row 0.  Switch closed: the bus dumps into
the pack (~30 µs) and |I| ≈ +idle ≈ 100 mA → over-voltage → restart below 18 V with the regen
limit halved.  Correct both ways; margin ~0.25 V, adequate given INA239 VBUS error (±0.1 %).

**Regen current limit.**  1.4 V at 20 A (R_pack ≈ 70 mΩ) plus Q7/Q8 + RS4 (~4 mΩ): 10 A weapon
regen into a 16.8 V pack → ~17.5 V; 20 A combined → ~18.3 V, which is what the §9 step 6
< 18.3 V check guards.  A switch opening mid-brake still pumps C1 at ~27 V/ms (10 A / 374 µF)
into D1 before BOVL acts — already covered (§7 "D1 is the real clamp", 0.3–0.8 ms).

**Pause ended by a protective coast; brake held until pack current returns.**  Consistent with
the hardware: after any weapon coast with the switch open |I| through RS4 is only the BAT_IN-side
load (~0.2 mA, round 25 N-path), so "|I| < 50 mA" holds and the brake stays off; with the switch
closed |I| ≈ +idle > 50 mA and the brake resumes (or, if the drives happen to cancel it, it
waits harmlessly).

**Instant coast only with a positive command.**  Switch open under throttle: bus falls below
the drum BEMF, body diodes feed the bus (power ≤ 0), |I| ≈ 0.2 mA < 50 mA on 3 shunt
conversions (~0.9 ms at 0xB480).  No hardware fact contradicted.

**BKINE window ≤ ~12 ms.**  Two ≤ ~5 ms nFAULT waits + a few 16-bit SPI frames (~3 µs each at
5.3 MHz).  TIM8_AF1.BKINE (reset 1) only gates the PB7 L_nFAULT pin; BKE = 1 keeps CLL.

## Findings

### R26A-01 (MINOR) — CLR_FLT is folded in **before** 0x0D10; if the nFAULT is held by the CTRL4 DRV_OFF bit (not the pin) it is ineffective, and the §9 step 2 check cannot tell the two apart

- SLVSH07 §8.4.1.3 (p.53): CLR_FLT returns the device to operation only "when the fault
  condition clears".  §8.4.2 (p.53): the DRVOFF *pin* "can trigger fault condition resulting in
  nFAULT getting pulled low".  Table 8-8 (p.48) has no row for either the pin or the CTRL4
  DRV_OFF bit, so neither recovery type (latched / automatic) is documented.  DESIGN already
  expects the bit may pull nFAULT low ("an nFAULT raised by a commanded coast is expected").
- At step (2) the chip is still coasted by CTRL4 bit 7 = 1 when the pin goes low.  The §9 step 2
  observation "does nFAULT stay low after the pin is lowered with the chip coasted" then has
  three causes: (B1) a latched fault from the pin — CLR_FLT anywhere works; (B2) a level fault
  held by the bit — 0x0D10 alone clears it; (B3) a latched fault whose condition is the bit —
  CLR_FLT only works **after** 0x0D10.
- With the written order (0x097D before 0x0D10) B3 fails on every resume: step (4) sees nFAULT
  low, its recover (0x0C90 → 0x097D, again with the bit set) and the repeat fail the same way,
  and the chip is classified — only via IC_STAT FAULT counting as a register mismatch (drive
  row 2; the drive table has no catch-all row) → per-drive coast → resume → > 3/s → latch.  Both
  drives would latch at the first boot "drives resume".  Not unsafe and not silent (§9 step 2
  expects nFAULT high after a resume, so the bench would show it), but the text sends the
  implementer to an order that can be the wrong one.

Fix (either): (a) order the Release 0x0603 → 0x0D10 → 0x097D → 0x0606 — it clears B1 and B3,
is harmless in B2, and the worst case is one ~1 µs extra OCP pulse if a real OCP lands in the
~3 µs between the two frames (the chip re-trips and latches; step 4 sees it); or (b) make the
§9 step 2 check discriminate: lower the pin with the chip coasted; if nFAULT is low, send the
bracketed fault recovery — if it rises, B1 (keep the written order); if not, Release 0x0D10 — if
it rises, B2 (no CLR_FLT needed); if not, CLR_FLT after 0x0D10 (B3, use order (a)).

### N1 (NOTE) — row 1 decay figure

Row 1 says "an open bus decays only ~0.2 V/ms"; calcs gives ~374 µF and ~100 mA of board load
≈ 0.27 V/ms (plus DRV8316/DRV8323 quiescent).  The 18 V threshold still holds for the new
18.5 V-coast classification (≥ ~18.25 V at the second conversion, ≤ ~0.9 ms after the coast);
the margin is ~0.25 V rather than the ~0.3 V the 0.2 V/ms figure implies.  If the drives are left switching at zero
torque during row 1 their losses add to this; "~0.3 V/ms" would be the safer statement.

### N2 (NOTE) — verification record

All DRV8316 words the round 25 text uses (0x0603, 0x097D, 0x0D10, 0x0606, 0x0C90, 0x0D94,
0x0C14) decode to the intended registers and fields and have even parity; the INA239 current path
and VBUS node, and the switch-open / regen physics rows 0/1 rely on, check out against
SLVSH07 / SLYS027A, the netlist and calcs.  Netlist, calcs and two SPICE scripts reproduce their
committed outputs exactly.
