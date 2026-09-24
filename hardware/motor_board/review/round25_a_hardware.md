# Round 25 — A: hardware review (rev L, after the round 24 text changes)

Scope: the round 24 §8.1/§9 changes (row 0 "every reading < 30 mA for ≥ 100 ms", paused
during a weapon braking command; instant weapon coast only with a zero/positive torque
command; still-rotor alignment after resume step 4; unlocked re-coast/recover sequence;
CTRL4 writes bracketed by unlock/lock; optional CLR_FLT after lowering the DRV_OFF pin), and
every hardware fact and SPI word they rely on.  Out of scope as before: area/fit, prose,
firmware preferences.

**Result: 0 BLOCKER, 0 MAJOR, 1 MINOR, 3 NOTE.**

## What was re-run

In a scratch copy (package minus `datasheets/` and `review/`):

- `design/motor_board.py`: 237 refs, 160 nets, `checks: OK`; `netlist.csv`, `nets.md`,
  `bom.csv` and `mcu_pinmap.md` regenerate byte-identical.
- `design/calcs.py`: `calcs.md` regenerates byte-identical.
- `spice/sim_hotplug.py`, `sim_arm.py`, `sim_weapon_spinup.py`: outputs identical to the
  captured `.out` files (spinup differs only by the code fences).  The bridge sim (~15 min)
  was not re-run; nothing in rounds 24/25 touches it.

## Verified (no finding)

**DRV8316C SPI words** (SLVSH07 §8.5.1.1 / Table 8-9: B15 W, B14–B9 address, B8 even parity
over the whole word, B7–B0 data).  Every DRV8316 word in DESIGN.md decoded and parity-checked:

| Word | Reg (addr) | Data meaning (SLVSH07 table) | Parity |
|---|---|---|---|
| 0x0603 / 0x0606 | CTRL1 (3h) | REG_LOCK 011b unlock / 110b lock (Table 8-18) | even |
| 0x087C / 0x097D | CTRL2 (4h) | bit 6 reserved = 1, SDO push-pull, SLEW 200 V/µs, 3x PWM; CLR_FLT W1C (Table 8-19) | even |
| 0x0A4E | CTRL3 (5h) | OVP_SEL 22 V, OVP_EN, SPI_FLT_REP = 1, OTW_REP = 0 (Table 8-20) | even |
| 0x0C90 / 0x0D10 | CTRL4 (6h) | DRV_OFF bit 7 = 1 / 0, OCP_DEG 0.6 µs, 16 A, latched (Table 8-21) | even |
| 0x0D94 / 0x0C14 | CTRL4 (6h) | same with OCP_LVL = 24 A | even |
| 0x0F00 | CTRL5 (7h) | CSA 0.15 V/A (Table 8-22) | even |
| 0x1019 | CTRL6 (8h) | BUCK_DIS, BUCK_CL, BUCK_PS_DIS (Table 8-23) | even |
| 0x1818 | CTRL10 (Ch) | DLYCMP_EN, DLY_TARGET 8h = 1.8 µs (Table 8-24) | even |

The two words DESIGN.md names as wrong (0x0C10, 0x0D90) are indeed odd parity.

**Lock bracketing (round 24).**  Table 8-18: REG_LOCK 110b "lock[s] the settings by ignoring
further register writes except to these bits"; 011b unlocks all registers.  So every CTRL4
write (Release 0x0D10, coast 0x0C90, the 24 A window 0x0D94/0x0C14 and its return) and every
CLR_FLT must sit between 0x0603 and 0x0606 — the per-drive coast, Release, fault recovery,
re-coast/recover (0x0603 → 0x0C90 → 0x097D → 0x0606) and 24 A window sequences all do.
CLR_FLT clears latched OCP (OCP_MODE = 0, §8.4.1.3 / fault table) and is self-clearing, so the
read-back expectation CTRL2 0x7C is right.  OCP trip points 10/16/22 A and 15/24/30 A
(electrical characteristics, IOCP) match the "10 A OCP minimum" and 24 A window text.

**DRV_OFF pin vs nFAULT.**  SLVSH07 §8.4.2 note: the DRVOFF pin "can trigger fault condition
resulting in nFAULT getting pulled low", and OCP is inactive while the pin is high — the
basis of the step-2 optional CLR_FLT and of "an nFAULT while the pin is high / during a
resume is expected".  Correct.

**INA239 facts row 0 / row 1 rely on** (SLYS027A):
- CURRENT_LSB = SHUNT_CAL / (4 × 819.2e6 × R) = 4096 / (4 × 819.2e6 × 1 mΩ) = 1.25 mA
  (Eq. 1, ×4 for ADCRANGE = 1), full scale ±40.96 A — so 30 mA = 30 µV = 24 LSB, 50 mA = 40 LSB.
- Shunt offset ±5 µV max (±5 mA) — small against the 30 mA threshold and the ~100 mA idle.
- ADC_CONFIG 0xB480 = MODE Bh (continuous shunt + bus), VBUSCT = VSHCT = 2h = 150 µs, VTCT 0,
  AVG 0 (Table 7-6): one shunt+bus pair every ~300 µs, so "3 consecutive conversions (~1 ms)"
  is 0.9 ms and "every reading for ≥ 100 ms" is ~330 readings.
- SOVL 0x76C0 = 30400 × 1.25 µV = 38.0 mV = 38 A; BOVL 0x17C0 = 6080 × 3.125 mV = 19.0 V.
- DIAG_ALRT ALATCH bit 15, CNVR bit 14, APOL bit 12, CNVRF bit 1 (cleared by the read with
  ALATCH = 1) — as used.

**Switch-open physics row 0 assumes (netlist).**  RS4 sits VBAT_SW → VBAT, after Q7/Q8.  When
the external switch in the BAT+ lead opens, Q7/Q8 stay on (U13 VS = BAT_IN is back-fed from
VBAT through the on FETs until EN/UVLO opens them near 9 V), so the shunt carries only what
hangs on BAT_IN/PSW nodes: U13 45 µA + R13/R14 (115 kΩ, ~0.15 mA) + C14 charge — ≈ 0.2 mA DC.
A 0.3 V p-p 48 kHz bus ripple into C14 (100 nF) is ~9 mA peak AC, which the 150 µs sinc
conversion averages to ~0.  So "switch open ⇒ |I| < 30 mA on every reading" holds, and a
closed switch reads ≥ ~100 mA idle (calcs §"Drain switched on and idle": 100–120 mA).

**Weapon brake/coast sequencing (round 24).**  With the switch open during a braking
command, row 0 is paused but the drum's regen has nowhere to go: the bus rises to BOVL 19 V
→ row 1 "looks open" (|I| ≈ 0.2 mA, VBUS > 18 V) → coast → braking command ends → row 0
confirms within 100 ms.  If the drives absorb more than the brake returns, the bus sags into
row 2 instead (the round-24 N2 path) — end result unchanged.  The instant-coast rule now
excludes braking commands, so the end of a closed-switch brake (current passing through zero)
cannot trigger it.  No hardware fact contradicted.

**Resume sequencing (round 24).**  Still-rotor alignment after step 4 is consistent with the
hardware: a coasted chip (CTRL4 bit 7 = 1, "Hi-Z FETs") cannot push alignment current, and
with TIM8 BKINE back to 1 an L_nFAULT (PB7 = TIM8_BKIN, `mcu_pinmap.md`) during alignment
breaks TIM8 as intended.  R_nFAULT (PC15) is EXTI only; TIM20 has BKINE = 0 permanently — as
stated.

## Findings

### R25A-01 (MINOR) — step (2)'s "send one CLR_FLT" does not say it is bracketed; a bare CTRL2 0x097D to a locked chip is ignored

§8.1 "drives resume" step (2): "if an nFAULT raised by the pin is still latched …, send one
CLR_FLT before the Release".  At that point the chip is locked (every sequence ends with
CTRL1 0x0606), and SLVSH07 Table 8-18 says a locked device ignores all writes except REG_LOCK —
the §8 DRV8316 row itself notes "a locked device ignores CLR_FLT".  Round 24 carefully added
"every CTRL4 write is bracketed by the unlock/lock", but this new CLR_FLT is the one DRV8316
write in §8.1 given without its word sequence.  Read literally (write 0x097D), it is silently
ignored; step (4) then sees nFAULT still low, spends its once-per-resume re-coast/recover on
this, and the BKINE = 0 window runs its full ~2 × 5 ms.  Not unsafe (the chip stays Hi-Z while
its fault is latched, and the unlocked recover does clear it), but it is the only place the
text would lead a hand-implementer to an ineffective SPI write.

Fix: "send the fault-recovery sequence (CTRL1 0x0603 → CTRL2 0x097D → CTRL1 0x0606) before the
Release" — or fold it into the Release: 0x0603 → 0x097D → 0x0D10 → 0x0606.  (Whether it is
needed at all stays the §9 step 2 bench decision.)

### N1 (NOTE) — "every reading" and INA239 noise: log the switch-open maximum in §9

SLYS027A Fig. 7-4 (AVG = 1) shows roughly ±15 µV peak with occasional larger spikes at 50 µs
conversions and a few µV at 1.052 ms; 150 µs lies between, so a switch-open reading is
~0 ± 10 mA against the 30 mA threshold (24 LSB).  A single spike ≥ 30 mA restarts the 100 ms
window (delay, not a miss), so the margin is adequate.  Suggest the §9 step 6 switch-open
tests also log the largest |I| reading while open with the drives PWMing, to confirm no
reading approaches 30 mA on the real layout.

### N2 (NOTE) — BKINE = 0 window with the step-4 repeat

"BKINE = 0 from here to the end of step 4, ≤ ~10 ms": with the one allowed repeat (two
≤ ~5 ms nFAULT waits plus SPI) it can reach ~10–11 ms.  Harmless (only the L_nFAULT hardware
break is off; the DRV8316 protects itself and CLL still acts), and "~" covers it; mentioned
only so the firmware timeout is not written as a hard 10 ms that aborts the retry.

### N3 (NOTE) — verification record

All DRV8316 SPI words, INA239 register values and the switch-open current path the round 24
text relies on check out against SLVSH07 / SLYS027A and the netlist (tables above).  The
netlist, calcs and three SPICE scripts reproduce their committed outputs exactly.
