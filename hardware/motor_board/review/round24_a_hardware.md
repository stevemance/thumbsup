# Round 24 — A: hardware review (rev L, after round 23)

Scope: the round-23 text changes (§8 boot order, §8.1 "drives resume" steps 1–4 ordering, the
still-rotor / turning-rotor / dead-encoder branches, the 24 A resume window and its register-check
expectations, BKINE/LOCK, the weapon switch-open-under-throttle coast from the INA239 alone, the
weapon's exclusion from row-0 suspension, drive row 7 latching both drives, §9) and the circuit
facts and SPI words they rely on.

The package was copied to /tmp/r24a without datasheets/ and review/, then deleted afterwards.
* `motor_board.py` regenerates `nets.md`, `netlist.csv` and `bom.csv` byte-identical ("checks: OK",
  237 refs, 160 nets, 67 BOM lines).
* `calcs.py` regenerates `calcs.md` identically.
* `sim_arm.py` and `sim_hotplug.py` (with `PYTHONPATH=hardware/tools/spice`) reproduce `arm.out` and
  `hotplug.out` exactly.

References: [D] DESIGN.md line; [DRV] SLVSH07 (DRV8316C.pdf), printed page; [INA] SBOSA20
(INA239.pdf); [MT] MT6701CT-STD.pdf; [N] design/nets.md; [C] design/calcs.md.

**Counts: 0 BLOCKER, 0 MAJOR, 0 MINOR, 4 NOTE.**

The round-23 text is consistent with the hardware.  Every SPI word and every circuit fact it uses
checks out (see "Verified" below).  The notes are robustness and wording points only.

| ID | Class | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R24A-N1 | NOTE | [D] l.675 "release at CTRL4 OCP_LVL = 24 A … (coast 0x0D94 → release 0x0C14, then back to 0x0D10 within ~50 ms — parity checked …)" | **The "back to 0x0D10" write has no unlock bracket.**<br>• The Release and coast words each spell out CTRL1 0x0603 → CTRL4 → CTRL1 0x0606.<br>• By this point the chip is locked (REG_LOCK = 110b), and a locked chip ignores register writes.<br>• If the bare word is sent, CTRL4 stays 0x14.  After the window the register check expects 0x10, sees a mismatch and goes to drive row 2 (coast, rewrite, resume at 24 A again).  That repeats until the drive latches.<br>• This only affects the optional fallback, and firmware would find it on the bench. | [DRV] Table 8-18 p.62 (REG_LOCK 6h "ignoring further register writes except to these bits"); Table 8-21 p.65 | Write "then back to 0x0D10 (CTRL1 0x0603 → CTRL4 0x0D10 → CTRL1 0x0606) within ~50 ms". |
| R24A-N2 | NOTE | [D] l.675 "an OCP at a zero preset marks the encoder suspect … the OCP does not count toward a latch"; "retried every ~0.5 s without ever latching" | **A shorted drive output also produces "OCP at a zero preset".**<br>• Examples: a phase shorted to GND or to VBAT through a chafed lead or a solder bridge, with the robot standing still.<br>• At the zero vector (all phases at 50 %) the shorted phase's high or low FET conducts half of every period, so the chip OCPs at once.<br>• Under the new rule this is reported as "encoder suspect" and retried every ~0.5 s forever.  It is never latched or named as a short.<br>• **Safety:** harmless.  Each event is a ≤ ~1 µs OCP (0.6 µs deglitch, [DRV] p.13).  At 2 Hz that is gentler than TI's own 5 ms auto-retry, and R302/R402 see ~1 mJ per event.<br>• **The problem is diagnosis only:** the report names the wrong part.<br>• One observation separates the cases.  With a dead encoder and a turning rotor, the OCP stops once the rotor has coasted down.  With an output short, it repeats at a zero preset even after the §9 step 6 coast-down time. | [DRV] Table 8-8 p.48 (OCP latched → Hi-Z); p.13 IOCP 10/16/22 A, tOCP_DEG; [D] l.675 | Optional: report "OCP at zero preset after coast-down: possible output short" as well as "encoder suspect".  Or count those OCPs toward the drive's resume-OCP latch. |
| R24A-N3 | NOTE | [D] l.677 step (4) "if still low, re-coast … run the fault recovery … once and repeat from (2)"; l.612 boot sequence (CLR_FLT written with the DRV_OFF pin high); l.694 "Bench-verify … whether it pulls nFAULT low" | **Step 4's single repeat may be used up on every resume.**<br>• SLVSH07 says the DRVOFF pin "can trigger fault condition resulting in nFAULT getting pulled low".<br>• Table 8-8 does not list this fault, so it is unknown whether it is latched.<br>• If it is latched: the only CLR_FLT before the Release is sent while the pin is still high (boot, or before the pin is lowered).  Then every Release after a pin-high period finds nFAULT low, and step 4 always takes its one allowed repeat.  A resume at speed then loses ~5 ms plus a second preset computation.  A real second fault then goes straight to the table.<br>• This is already covered by the bench-verify item.  It is only a note on ordering. | [DRV] §8.4.2 p.53 note; Table 8-8 p.48; §8.4.1.3 (CLR_FLT clears once the condition has cleared) | Optional: in step (2), after lowering the pin and before the Release, send one fault recovery (CTRL1 0x0603 → CTRL2 0x097D → CTRL1 0x0606) while the chip is still coasted by the CTRL4 bit.  Or decide it from the §9 step 2 bench result. |
| R24A-N4 | NOTE | [D] l.9 "rev L rounds 11–22"; README.md l.7 "twenty-two adversarial review rounds" | **Stale round labels.**  Round 23 changed rev L text, so these should read "11–23" / "twenty-three".  This is bookkeeping only. | CHANGES.md "Round 23 → rev L" | Update both. |

## Verified (no finding)

**DRV8316C SPI words** [DRV §8.5.1.1 p.54: W B15, address B14:9, parity B8 = even number of 1s over
the whole word, data B7:0].  All recomputed with the correct address, fields and parity:

| Word | Register | Data |
|---|---|---|
| 0x0603 / 0x0606 | CTRL1 | unlock / lock |
| 0x087C / 0x097D | CTRL2 | 0x7C = SDO push-pull, 200 V/µs, 3x mode; CLR_FLT, P = 1 |
| 0x0A4E | CTRL3 | 0x4E = reserved bit 6, OVP 22 V on, SPI_FLT_REP off nFAULT, OTW_REP 0 |
| 0x0C90 / 0x0D10 | CTRL4 | coast / Release |
| 0x0D94 / 0x0C14 | CTRL4 | 24 A coast / 24 A Release |
| 0x0F00 | CTRL5 | 0.15 V/A, P = 1 |
| 0x1019 | CTRL6 | BUCK_DIS, BUCK_CL, BUCK_PS_DIS |
| 0x1818 | CTRL10 | DLY_TARGET setting |

CTRL4 field details [DRV Table 8-21 p.65]:
* Bit 7 DRV_OFF = Hi-Z; OCP_DEG 1 = 0.6 µs; OCP_LVL 0/1 = 16/24 A; OCP_MODE 0 = latched.
* The register check's expected values 0x10 / 0x90 / 0x94 / 0x14 match these fields.
* IOCP is 10/16/22 A at LVL 0 and 15/24/30 A at LVL 1 [DRV p.13].
* Only PWM_MODE carries a "do not change during operation" caution [DRV §8.3.2].  Changing OCP_LVL on the fly is not restricted.

**Drive branches in "drives resume" (2)–(3):**
* **Still rotor:** preset 0 → Release → align.  A coasted chip (CTRL4 bit 7 or the DRVOFF pin) cannot push current.  With INL = +3V3 in 3x mode, every INH state connects each phase to a rail, so any current probe is a brake [N INLx; DRV §8.3.2.2].
* **Encoders:** the MT6701 Z comes once per mechanical revolution at the EEPROM ZERO position, so the stored Z electrical offset is absolute [MT].
* **Cut encoder cable:** the R54–R59 pull-ups freeze the ABZ lines high through U9/U10, so the count stops and no Z edge arrives.  "Not counting" is therefore indistinguishable from a still rotor, as the text says.
* **MT6701 limits:** TDelay 5 µs typ; 55 k rpm max [MT].
* **Preset error at top speed:** 15° gives ≈ 10 A (λ = 0.263 mWb, 6 pole pairs, [C] §10), consistent with the text.

**BKINE / LOCK and the resume window:**
* L_nFAULT → PB7 (TIM8_BKIN) and R_nFAULT → PC15 (EXTI) [N].  TIM20 keeps BKINE = 0 and BKE = 1.
* Between no-encoder retries the chip is re-coasted (0x0C90), so MOE = 0 with OISx = 1 and OSSI = 1 idles INH high onto a Hi-Z chip.
* Using BKINE rather than BKE, and keeping LOCK = 0, was settled in R22A-03 / R23A-N1.  There was no new reason to doubt it.

**Weapon switch-open-under-throttle rule (INA239 alone):**
* With the switch open, RS4 carries only BAT_IN's load: U13 45 µA, R13+R14 115 kΩ ≈ 0.15 mA, C14 [N BAT_IN, VBAT_SW].  The FETs stay on because BAT_IN is back-fed from VBAT through Q8/Q7.  |I| < 50 mA is 40 LSB at 1.25 mA/LSB (SHUNT_CAL 0x1000, ADCRANGE 1).
* The INA239 shunt offset is ±5 µV max = ±5 mA [INA p.1, EC table], well inside the 50 mA threshold.
* ADC_CONFIG 0xB480 decodes to MODE Bh, VBUSCT = VSHCT = 150 µs, VTCT 0, AVG 1.  One shunt reading comes every ~0.3 ms, so "3 consecutive conversions ≈ 1 ms" is right.
* After the coast, the estimate is idle + driven drives ≥ ~0.1 A, so row 0 is not suspended and confirms within its 100 ms.
* **Weapon excluded from row-0 suspension:** a closed-switch regen that nets ≈ 0 pack current trips the ~1 ms coast first, and pack current then returns.  So a held weapon regen cannot build the 100 ms "switch open" mean.
* **Drive row 7 latching both drives:** consistent with §9 step 6 and the latch word.

**Circuit spot checks:**
* The DRV8316 pinout matches U3/U4 in the netlist [DRV Table 6-1 p.4–5].
* nSCS has an internal 80–130 kΩ pull-up [DRV p.10].  Row 4's "100 kΩ nCS pull-up" relies on it, and the netlist rightly has no external one.
* DRVOFF: R50 10 k pull-up to +3V3 against the two chips' internal 100 kΩ pull-downs gives ≥ 2.57 V worst case (70 kΩ min each), above VIH 1.5 V [DRV p.10].
* W_nFAULT is wire-ORed between U2 nFAULT, U7 ALERT, R42 and C19 [N].

No other hardware issues were found in the round-23 text or the circuit it depends on.
