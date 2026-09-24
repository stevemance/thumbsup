# Trim C — §8 firmware-contract rows, boot order and §3.5 compute-board bullets

Scope: DESIGN.md §8 boot-order paragraph, every row of the §8 table (Heartbeat … USART1), and the
compute-board contract text in §3.5 item 4 that rounds 12–30 added.  §8.1 itself is out of scope
(see the knock-on notes in §3 below).  Nothing in DESIGN.md was edited.

Rule applied: **KEEP** every hardware fact, register word and pin/timer setting firmware must
respect and every realistic 1 lb-robot fault (hit, jam, cut cable, bounced switch, hung compute
board, MCU reset mid-match).  **SIMPLIFY** procedures to their intent.  **CUT** multi-condition
chains, optional probes, and tuning detail that belongs in the firmware design once code and bench
data exist.

Datasheet checks for the facts that are kept (all confirmed):

* DRV8316C (SLVSH07): frame W/A5..A0/P/D7..D0, P = even parity over the word; SPI mode 1 (capture
  on SCLK falling, shift on rising); SDO Hi-Z with nSCS high; t_READY 1 ms; registers reset on
  power-up and sleep; CTRL1 REG_LOCK 3h unlock / 6h lock; CTRL2 reset 0x60 (bit 6 reserved = 1,
  SDO_MODE push-pull), CLR_FLT self-clears; CTRL3 bit 3 OVP_SEL 22 V, bit 1 SPI_FLT_REP = 1
  disables SPI faults on nFAULT, bit 0 OTW_REP; CTRL4 bit 7 DRV_OFF "1h = Hi-Z FETs", OCP_LVL 0 =
  16 A, OCP_MODE 0 = latched; CTRL5 CSA_GAIN 0 = 0.15 V/A; CTRL6 BUCK_PS_DIS/BUCK_CL/BUCK_DIS;
  CTRL10 DLYCMP_EN + DLY_TARGET 8h = 1.8 µs; IC_STAT NPOR 0 = POR seen, cleared by CLR_FLT; OVP
  22 V setting 20 V min rising.  Every SPI word below re-computed: 0x0603, 0x0606, 0x1019, 0x0A4E,
  0x0C90, 0x0D10, 0x0F00, 0x1818, 0x087C, 0x097D (and §8.1's 0x0D94, 0x0C14) all have even parity.
* DRV8323 (SLVSDJ3): ENABLE low pulse 8–40 µs (t_RST) clears faults without sleep; t_WAKE ≤ 1 ms.
* INA239 (SLYS027A): DEVICE_ID = DIEID 239h (bits 15:4) + REV_ID 1h → reads 2391h.  ADC_CONFIG
  0xB480 = MODE Bh, VBUSCT 2h, VSHCT 2h, VTCT 0, AVG 0.  SHUNT_CAL 0x1000 (1 mΩ, 1.25 mA LSB,
  ×4 for ADCRANGE = 1), SOVL 0x76C0 = 38.0 mV / 1.25 µV, BOVL 0x17C0 = 19.0 V / 3.125 mV.
  ALATCH flags clear on reading DIAG_ALRT.
* MT6701: 55 000 rpm max; no ABZ output for the first ~50 ms after power-up by default; the
  power-up absolute AB pulse train is an opt-in register setting; Z_PULSE_WIDTH at 0x32[6:4].
* STM32 figures: 170 MHz / (2 × 3542) = 24.00 kHz, / (2 × 1771) = 48.00 kHz; 170 MHz / 2 Mbaud =
  BRR 85.

---

## 1. Verdict table

| Row / rule | Verdict | Reason |
|---|---|---|
| **Boot order** — sequence (IWDG, UCPD dead-battery, clocks, USART1/first heartbeat, DBGMCU freeze, GPIO/PC11/PC13–15 rule, SPI3, U3/U4/U7 config, W_EN, offsets, strap test, BOR option byte) | KEEP | Hardware facts and ordering constraints; reformatted as a numbered list so it can be read |
| Boot order — the full "drives resume" recipe inlined | SIMPLIFY | Duplicates §8.1; one line pointing to it |
| Boot order — weapon needs W_ARM_S high + fresh ARM edge since reset | KEEP | Realistic: W_ARM_S is hardware and survives an MCU watchdog reset, so without this the weapon would resume on its own mid-match; throttle-zero added so the gate is complete in one place |
| **Heartbeat** row | KEEP (wording) | Needed by the compute-board self-test and fault reporting; "fell" flag catches glitches shorter than a heartbeat |
| **Command link** — CRC, 100–250 ms timeout → coast, stay stopped | KEEP | Core failsafe |
| Command link — random session ID + modulo-2¹⁶ "must advance" sequence rule | SIMPLIFY | Intent is only "a re-sent stale frame is not fresh" (hung compute board with circular DMA); a counter that must change covers it |
| Command link — "Heartbeat frames to the compute board …" | CUT | Duplicate of the Heartbeat row and §3.5 |
| **Watchdog/faults** — IWDG ~20 ms with task check-in, HardFault handler, CLL + BKE on TIM20, no flash erase | KEEP | Hardware facts |
| Watchdog/faults — break-flag clearing order at boot | SIMPLIFY | Keep the one real constraint (U2 wake nFAULT and INA239 ALERT share W_nFAULT), drop the cross-procedure prose |
| **CPU budget** | KEEP | Settled pre-round 12 |
| **Drive VM** | KEEP | Hardware fact (R302/R402) |
| **Power budget** — 32 A shared, VBAT fold-back toward 12 V, ≤ ~10 A regen current limit, bus < 18.5 V, not a bus-voltage regulator | KEEP | All derived from hardware limits (SOVL, UVLO, TVS clamp vs 4.0 V sense pins); text already tight |
| **DRV8323RH** — no registers, ENABLE pulse, wake nFAULT, CSA offsets, CHxN statics, OISxN, AOE = 0 | KEEP | Hardware facts; ENABLE pulse now quoted as 8–40 µs (t_RST) |
| DRV8323RH — "re-read and clear DIAG_ALRT every ≤ 0.5 ms while W_nFAULT is low before timing U2's release" | SIMPLIFY | Keep the fact (wired-OR, ALERT latched until read) and the rule "read DIAG_ALRT before blaming U2"; cadence is firmware design |
| **W_ARM_S** row | SIMPLIFY (light) | Content is right; removed repetition (reported twice, "latches" said twice) |
| **DRV8316C** — SPI format, configuration sequence and every word, Release, fault recovery, expected read-back values, NPOR, 6x-mode-after-reset, OVP 20 V min, CSA sample timing, duty caps, ILIM unusable | KEEP | Register values/SPI words exact, verified above |
| DRV8316C — interleaved conditional clauses (IC_STAT FAULT "outside a drives-resume step", "for a single-chip rewrite after the per-drive coast…", rewrite-vs-Release explanation) | SIMPLIFY | Restructured into Configuration / Release / Coast / Recovery / Register check blocks; same words, fewer qualifiers |
| DRV8316C — per-drive coast word | KEEP (moved) | Register sequence belongs with the others; §8.1 can reference it |
| DRV8316C — drive current limit ~1–1.5 A | KEEP | Marked as a starting value |
| **STM32 timers/ADC** | KEEP (verbatim) | Settled pre-round 12; facts |
| **Timer inputs** — encoder config, ICxF, 32-bit extension, MT6701 power-up train off, sensor cannot be re-powered | KEEP | Hardware facts |
| Timer inputs — observer plausibility check → sensorless | KEEP | Realistic (encoder cable hit, magnet loose) |
| Timer inputs — two-step alignment, sign check, other-encoder-still check, offset not zeroing | KEEP / SIMPLIFY | Real need (incremental encoder, 180° dead zone, cable swap is a real assembly error); outcome list shortened, repeat count "a few" |
| Timer inputs — invalid angle with rotor turning → next Z + stored offset | KEEP | Needed after an MCU reset while the robot is moving |
| Timer inputs — optional torque-relax (~20 ms) spring-back probe for a lost encoder | CUT | Optional, speculative; the report + observer check is enough |
| Timer inputs — "compute board may command a sensorless restart", "after a left/right-crossed report only once the operator has cleared drive row 7…" | CUT | Policy detail duplicated in §8.1 |
| Timer inputs — first-Z check → "Z offset stale" | KEEP | Catches a re-glued magnet; cheap |
| Timer inputs — Z-count candidate reference / noise-pulse rule / "matches neither" rule / re-reference-on-second-mismatch (rounds 28–30) | SIMPLIFY | Intent: small error = drift (correct), larger = lost edges (re-reference), second one since reset = suspect → sensorless.  Candidate logic is firmware design |
| Timer inputs — slipped-magnet discussion, torque-sign test rationale, 40–50 ms residual, ~16° spread | SIMPLIFY | One clause: only the observer can see it; accepted |
| Timer inputs — speed cap ≤ ~50 k rpm, field weakening sensorless only | KEEP | MT6701 rating |
| **Weapon fast trip (required)** and **(wiring)** | KEEP (verbatim) | Settled rounds 9–11; hardware-derived |
| **INA239 timing** | KEEP | Hardware fact |
| **Weapon safety** | KEEP (wording) | Real combat faults (jammed drum, over-temperature, regen into full pack, no short-brake) |
| **Braking and reversal** | KEEP (light trim) | Facts |
| **INA239 (U7)** | KEEP | Register values exact; ID check reworded to DIEID so a later REV_ID does not fail it |
| **BQ76907**, **Motor NTC**, **USART1** | KEEP (verbatim) | Facts |
| **§3.5 item 4 lead text** — "A reported weapon latch makes the compute board stop the ARM toggle (disarm) first, then persist its copy" | SIMPLIFY | Keep "disarm on a reported latch"; persistence cut (below) |
| §3.5 — Boot self-test (a)–(d) | KEEP | Pre-round 12; catches real part faults; "weapon command at zero" folded in |
| §3.5 — Re-arm after a motor-MCU reset | SIMPLIFY | Keep: hold low ≥ 250 ms then toggle, only without a latch, throttle at zero, never auto-clear |
| §3.5 — Radio loss must also stop the drives | KEEP | Real |
| §3.5 — Hold-up ~470 µF, don't back-power via MB_RX | KEEP | Hardware |
| §3.5 — NRST reset on lost heartbeat, ≤ 2 per 10 s | SIMPLIFY | Keep the rule and the limit; drop the per-reset 50 ms expectation (stated once in the boot order) |
| §3.5 — Mirror the weapon latch and keep it across a motor-board power cycle | CUT (make optional) | Needs a compute-board flash write and a "persist after disarm" ordering rule; after a power cycle the weapon's first-start checks (§8.1 rows 4/5, U2 VDS OCP) re-detect a real short within one event that the hardware already survives.  Show the latch to the operator; persisting it is optional |

---

## 2. Replacement text (ready to paste)

### 2.1 §8 boot order

**Replaces** the paragraph in DESIGN.md §8 from `**Boot order:** start the **IWDG**` through
`is an option byte: program it once over SWD (level 4, ~2.8 V).` (inclusive).

```markdown
**Boot order** (each step before the next):

1. Start the **IWDG** (~20 ms; frozen on debug halt in debug builds via DBG_IWDG_STOP); refresh it
   explicitly through the rest of boot.
2. `HAL_PWREx_DisableUCPDDeadBattery()` before any GPIO init (PB4/PB6 dead-battery pull-downs).
3. Clocks: HSI16 → PLL 170 MHz.
4. USART1 and the first heartbeat (the compute board expects it within ~50 ms of reset, §3.5).
5. DBGMCU: freeze TIM1/TIM8/TIM20 on core halt (a halted core then leaves the drives braking and
   the weapon coasting).
6. GPIO (PC11 pull-down; never enable RTC_OUT/TAMP/LSE on PC13–15) → SPI3 → configure U3/U4
   (DRV8316C row: they end coasted) and U7 → W_EN high → CSA offsets → the §7.16 strap boot test
   (drum stopped).
7. Drives: DRV_OFF pin low only when the drives are commanded, always through §8.1 "drives resume".
8. Weapon: TIM1 CHxN only while W_ARM_S (PD2) is high **and** a fresh low→high ARM edge has been
   seen since this reset (the heartbeat carries "ARM edge required" until then) **and** the weapon
   command has been seen at zero.

BOR level is an option byte: program it once over SWD (level 4, ~2.8 V).
```

### 2.2 §8 table

**Replaces** the whole table under the boot order, from the header line `| Device | Setting |`
through the `| USART1 | … |` row (inclusive).  Rows marked *verbatim* in §1 are copied unchanged.

```markdown
| Device | Setting |
|---|---|
| Heartbeat (to the compute board, every ≤ 10 ms) | CRC + an incrementing counter; W_ARM_S level; a latched "W_ARM_S fell" flag with the time since that edge (ms, saturating; held until the compute board acknowledges it, so a glitch shorter than a heartbeat still shows); "ARM edge required"; latch/hold flags with reason; fault counters; DRV8316 register-check status |
| Command link / failsafe | Frames from the compute board carry a CRC and a sequence counter; a frame whose counter has not changed is not fresh (a hung compute board can keep re-sending its last frame from DMA).  No fresh valid frame for 100–250 ms → drives coast (DRV_OFF high), weapon coast (CHxN low); stay stopped until commanded again (weapon: throttle-zero interlock, §8.1) |
| Watchdog / faults | IWDG ~20 ms, refreshed from the main loop only when every task has checked in (control ISRs, command-timeout handler, fault supervisor).  HardFault/NMI handler: DRV_OFF high, TIM1 MOE = 0, then wait for the IWDG.  SYSCFG_CFGR2.CLL = 1 so a core lockup breaks the timers in hardware; CLL acts only on timers with BKE = 1, so set BKE on TIM20 too (no break pin: BKINE = 0).  No flash erase/program while running (a page erase outlasts the IWDG).  U2's ~1 ms wake nFAULT and the INA239 ALERT both pull W_nFAULT (the TIM1 break) low: at boot clear TIM1's break flag only after U2 is awake and DIAG_ALRT has been read; TIM8/TIM20 break flags are cleared inside "drives resume" (§8.1).  Boot-time events are not faults.  Fault handling: §8.1 |
| CPU budget | Two FOC loops at 48 kHz + one at 24 kHz + observers ≈ 60–80 % peak on the 170 MHz M4F: bare-metal ISRs in CCM SRAM, CORDIC for sin/cos, measure cycles at bring-up; fallback: keep 48 kHz PWM (the 2:1 timer lock and the sampling scheme depend on it) and run the drive current loops at 24 kHz (~5–6 updates per electrical cycle at top speed: acceptable only below top speed), or the weapon observer at 12 kHz |
| Drive VM | the DRV8316 VM sits I × 0.1 Ω below VBAT (R302/R402): use VBAT − I_bus × 0.1 Ω for voltage feed-forward (the DRV8316 cannot report its VM) |
| Power budget | One shared budget: weapon + drive current ≤ ~32 A (below the 38 A SOVL trip); **fold back drive and weapon current as VBAT sags toward ~12 V (required: the switch UVLO can open as high as 10.1 V and the logic cutoff at 9.2–10.3 V)**; combined regen limited by a **current** limit (≤ ~10 A: with the switch open during a brake the TVS then clamps ≤ ~28.7 V, keeping the 4.0 V-rated sense pins PA3–PA5 at ~3.7 V nominal, ≤ ~3.75 V worst case) sized so the bus stays below 18.5 V (not a bus-voltage regulator, which would hide an open switch) |
| DRV8323RH (U2) | No registers.  ENABLE (W_EN) high at boot and kept high; an 8–40 µs low pulse (t_RST) clears a latched fault without sleeping, a longer one is sleep.  Expect nFAULT low for ~1 ms (t_WAKE) after each wake.  Measure the CSA offsets (bridge idle, INLx = 0) after every wake.  FOC: hold TIM1 CHxN statically high (CCxNE = 0, OSSR = 1, polarity for high off-state); six-step: per-phase Hi-Z via CHxN.  Break (MOE = 0) with OISxN = 0 → INL low → coast.  **AOE = 0** (re-enabling is a firmware decision).  W_nFAULT is a wired-OR of U2's nFAULT and the INA239 ALERT (ALATCH = 1: held until DIAG_ALRT is read), so read and clear DIAG_ALRT before attributing a low W_nFAULT to U2 (§8.1) |
| W_ARM_S (PD2) | EXTI both edges, high priority (U14 gives clean edges).  A **falling** edge acts at once: full weapon stop (CHxN low, current controllers reset) and sets the heartbeat's "W_ARM_S fell" flag (the compute board, which knows when it stopped toggling, does the timing).  A rising edge counts only after W_ARM_S has stayed high ≥ 5 ms.  Re-arm needs a new ARM edge and the weapon command at zero (§8.1 throttle-zero interlock) |
| DRV8316C (U3, U4) | **SPI:** mode 1, ≤ 5.3 MHz, 16-bit frames with an even-parity bit (B8, computed by firmware, not copied from constants); one device selected at a time (never both CS low); one SPI3 owner task for U3/U4/U7.  SDO is Hi-Z while nCS is high (CTRL2 resets to push-pull, 0x60).  Registers reset on any sleep/UVLO: ignore reads before the configuration is written.  **Configuration** (after t_READY 1 ms; at boot with the DRV_OFF pin high; the same sequence is the "rewrite" after an NPOR or mismatch, for one chip with the pin left as it is): CTRL1 0x0603 (unlock) → **CTRL6 0x1019** (BUCK_DIS, BUCK_CL, BUCK_PS_DIS) → **CTRL3 0x0A4E** (OVP 22 V on, SPI faults off nFAULT, OTW *not* on nFAULT: poll it) → **CTRL4 0x0C90** (OCP 16 A latched, a short-circuit backstop; bit 7 DRV_OFF = 1: the chip stays coasted) → **CTRL5 0x0F00** (CSA 0.15 V/A) → **CTRL10 0x1818** (delay compensation on, DLY_TARGET 0x8 = 1.8 µs: covers the worst-case driver delay; TI's 1.2 µs cannot be held at the delay's upper spread) → CTRL2 0x087C (SLEW 200 V/µs, 3x PWM, push-pull SDO) → CTRL2 0x097D (CLR_FLT) → CTRL1 0x0606 (REG_LOCK).  CTRL4 and CTRL5 are written explicitly.  **Release** (only inside §8.1 "drives resume", with the timer already running FOC preset to the back-EMF): CTRL1 0x0603 → CTRL4 **0x0D10** → CTRL1 0x0606 (§8.1 may add CTRL2 0x097D before the lock).  **Per-drive coast:** CTRL1 0x0603 → CTRL4 **0x0C90** → CTRL1 0x0606 (0x0D90 and 0x0C10 have odd parity and are rejected).  **Fault recovery** (a locked chip ignores CLR_FLT): CTRL1 0x0603 → CTRL2 0x097D → CTRL1 0x0606.  **Register check at ~100 Hz:** expect CTRL1 0x06, CTRL2 **0x7C** (CLR_FLT self-clears), CTRL3 0x4E, CTRL4 0x10 released / 0x90 coasted, CTRL5 0x00, CTRL6 0x19, CTRL10 0x18, IC_STAT NPOR = 1; also read IC_STAT FAULT (0 on a released chip with the DRV_OFF pin low) and the OTW bit (derate on OTW; a still-low nFAULT gives no new EXTI edge).  A mismatch or NPOR = 0 means the chip reset (it comes up in 6x PWM mode) → rewrite (it ends coasted), report, §8.1 drive events.  OVP 22 V trips at 20 V minimum.  Sample the CSAs in the centre of the low-side-on interval, ≥ 1 µs after it opens + DLY_TARGET; duty ≤ ~81 % (L) / ~86 % (R, rank-2 pair, C = −(A+B)), flat-bottom SVPWM (CTRL3 PWM_100_DUTY_SEL left 0 is fine at that cap).  Current limiting in the FOC loop (ILIM modes unusable with VREF = AVDD); starting limit ~1–1.5 A for the Mk4.1 (traction) |
| STM32 timers/ADC | §3.4: TIM1 24 kHz (ARR 3542, PWM mode 1), TIM8/TIM20 48 kHz (ARR 1771, PWM mode 2) reset-slaved via ITR0 with URS = 1 (TIM8/TIM20 OISx = 1, OSSI = 1, §8.1); the timers never stop (ADC triggers ≤ 1 ms apart).  ADC clock asynchronous PLLP 42.5 MHz /1 for all ADCs; ADC1/ADC2 dual simultaneous; injected on TIM8_TRGO2 (OC6REF, 48 kHz), 3 ranks everywhere, 12.5 cycles, JQDIS = 1; regular (ADC1/ADC2) on TIM1_TRGO2 = OC6REF inside the non-overlap windows (relative to CCR6), 4 ranks with VREFINT (VREFEN) and R_MTEMP both at 247.5 cycles.  Circular DMA; never stop an ADC without disable/enable; set JQDIS before writing JSQR; discard the first samples after every start and debug halt (ES0430: > 1 ms without a trigger); reject rev Z silicon.  TIM1 MMS = update; TIM8/TIM20 combined reset + trigger mode, slaves enabled first.  Trigger details: TIM8 OC6 in PWM mode 2 (rising edge used as TRGO2 = OC6REF; PWM mode 1 would sample 1.5 µs before the valley); TIM1 OC6 for the regular trigger at CCR 568–2311 (PWM mode 2) or 1231–2974 (PWM mode 1); ADC1/ADC2 DUAL = 00001 (combined regular + injected simultaneous); the weapon uses the sample taken while TIM1 counts down near its peak (read TIM1 DIR).  OPAMP5: VM_SEL = follower, VP_SEL = VINP2 (PC3), OPAINTOEN = 1 **before** OPAEN (otherwise it drives PA8), high-speed mode; calibrate the L_SOC offset separately; **do not run HAL OPAMP self-calibration** (it clears OPAINTOEN and drives PA8 against U3's SOA for ~25 ms): use the factory trim.  VREFBUF off (VREF+ is tied to VDDA).  TIM1 BKIN (PC13) and TIM8 BKIN (PB7) active low; R_nFAULT (PC15) EXTI at top priority: record it; §8.1 drive events decide (the DRV8316 already Hi-Zs itself on its own faults).  DRV_OFF low only when the drives are commanded (§8 boot order) |
| Timer inputs | TIM3/TIM2 encoder mode on CH1/CH2 (MT6701 ABZ, 1024 PPR = 4096 counts/rev), Z via CH3 capture interrupt; input filter ICxF ≤ 0b0011; TIM3 extended to 32 bits in software.  Leave the MT6701 power-up absolute ABZ train **off** (the default).  The sensor is powered from +3V3 (TPS22945 ON = VIN): the MCU cannot re-power it.  **Start angle** (ABZ is incremental): whenever the angle is invalid (after a reset, or after ≥ ~20 ms without edges while the observer says the motor turns) and the rotor is still, align one drive at a time in **two steps** (~1 A at +90° electrical, then at 0°, ~100 ms each; a single vector has a dead zone at 180° error where gearbox friction holds the rotor).  Check that the encoder moved by the expected amount (~171 counts) **and sign** and that the other drive's encoder stayed still (catches swapped J2/J3 sensor cables or motor bundles).  Wrong sign on two clean alignments → wiring fault, latch that drive; the other encoder following → left/right crossed (§8.1 drive row 7); too little motion → retry at a higher current, then sensorless and report; a disturbed alignment (robot pushed) is repeated a few times, then sensorless and report.  Set an angle offset (never zero the count, so odometry stays continuous); the wheel moves ≤ ~0.4 mm through 28.5:1.  If the rotor is turning, take the angle from the next Z and the stored Z offset instead.  **Z reference:** Z's electrical offset is measured once at bring-up and stored (§9 step 5).  At the first Z after an alignment, > ~30° electrical from it → keep the alignment and report "Z offset stale" (re-run §9 step 5, e.g. after a magnet re-glue).  At every later Z compare the count (mod 4096; capture Z with the counter's direction bit, or set Z_PULSE_WIDTH = 1 LSB, so a reversal does not shift it): a few counts is drift (correct it); a larger error is lost or extra A/B edges → re-reference; a second one since reset marks the encoder suspect → sensorless and report.  **Encoder plausibility:** above a few thousand rpm compare the encoder angle with the sensorless observer; > ~30° electrical disagreement → that drive goes sensorless and reports.  This is also the only check for a slipped magnet (Z moves with it): an accepted residual.  **Lost encoder at standstill** cannot be told from a pushing stall (ABZ has no status; the pull-ups freeze the count): report "no encoder edges, torque commanded" with its duration in the heartbeat; once moving, the plausibility check catches it.  Return to encoder mode after edges resume and a Z matches the reference.  **Speed cap on the encoder:** ≤ ~50 k rpm motor (MT6701 rated 55 k rpm); field weakening only in sensorless mode |
| Weapon fast trip (required) | The DRV8323 CSA **inverts**: shoot-through and phase-to-phase / phase-to-VBAT shorts pull SOx *low*, so each comparator trips when SOx < ~0.45 V (VREF/2 − 30 A × 40 mV/A; default **30 A**: at the 20 A limit the PWM ripple is ±3–5.5 A and nuisance trips would keep restarting the weapon (§8.1 row 6), so lower it only after measuring).  Inverting inputs from the internal-only DACs (DAC3_CH1, DAC4_CH2; DAC1_CH1/DAC2_CH1 would drive PA4/PA6).  With TIM1 BKP = 0 (active-low nFAULT on PC13) no inversion anywhere: COMPx POL = 0, BKCMPxP = 0.  Outputs to TIM1's **main break (BRK, BKCMPxE)**, not BRK2 (BRK2 would leave the INL enables high through the output polarity in FOC).  TIM1 dead time 0 (the DRV8323 inserts its own; the INL enable only falls after the timer dead time).  OSSI = 1 (otherwise R47–R49 add ~1.5–2 µs), BKF = 0, blanking off by default (the CSA slew already acts as ~120 ns of blanking; a TIM1_OC5 window would be a blind spot).  Comparators enabled only while U2 is awake; comparator interrupts to tell a comparator trip from nFAULT |
| Weapon fast trip (wiring) | COMP3 (PA0, W_SOA), COMP1 (PA1, W_SOB), COMP6 (PB11, W_SOC); each CSA pin reaches only one comparator non-inverting input |
| INA239 timing | shunt and bus conversion ≤ 150 µs each so SOVL/BOVL act within ~0.3–0.45 ms (the alert follows the conversion that sees the limit) |
| Weapon safety | Coast if the bus exceeds 18.5 V (from the INA239 VBUS reading: the VBAT_SNS ADC can read low while a compute board holds its pin at reset), then restart as §8.1 row 1.  **Stall cut-out** (§8.1 row 10): at the current limit with no speed rise for > 0.5 s → coast ~1 s and retry; TH1 > ~100 °C → coast until < ~80 °C; report (a jammed drum otherwise dissipates continuously).  Weapon control at 24 kHz gives ~7–8 updates per electrical cycle at full speed (2822 = 14 poles, 7 pole pairs: confirm): use the sensorless observer with angle prediction there, six-step only at low speed.  **Never short-brake the drum** (all low sides on at 25 k rpm ≈ 14 V BEMF into tens of mΩ = hundreds of A) |
| Braking and reversal | Regen returns to the pack through the switch FETs (bidirectional when on); the bus rises by I × R_pack (~1.4 V at 20 A).  **Weapon:** reverse (e.g. an invertible drum) by a controlled FOC deceleration inside the combined ~10 A regen limit (Power budget row; ≈ 0.5 s from full speed), then spin up; or coast down.  **Drives:** normal FOC braking/reversal inside the same limit.  If the pack is disconnected mid-spin, the INA239 BOVL break + the 18.5 V coast stop the drum from pumping the bus; the DRV8316 OVP Hi-Zs the drives.  INA239 current is signed: negative = regen |
| INA239 (U7) | DEVICE_ID check: DIEID (bits 15:4) = 239h (reads 2391h; 229h = INA229 → 24-bit register handling).  SHUNT_CAL 0x1000 (1 mΩ, ADCRANGE = 1, ±40.96 mV); continuous shunt + bus: **ADC_CONFIG 0xB480** (MODE Bh, VBUSCT = VSHCT = 2h = 150 µs, no temperature, AVG = 1; the reset value runs ~1 ms conversions with temperature and would break the §8.1 timing); use CNVRF to tell which conversion follows an event.  **Write only SOVL = 0x76C0 (38 A) and BOVL = 0x17C0 (19.0 V)**; leave SUVL, BUVL, TEMP_LIMIT and PWR_LIMIT at their reset values (every limit drives ALERT, which is the weapon break).  DIAG_ALRT: ALATCH = 1, CNVR = 0, APOL = 0.  Low-pack warning and switch-open detection (§8.1 row 0) are firmware |
| BQ76907 (from the compute board) | after every POR: Vcell Mode = 4 (CONFIG_UPDATE); cell OV/UV thresholds on ALERT; allow SLEEP; balancing never enabled; I²C address 0x08 (7-bit), CRC off (BQ76907RGRR) |
| Motor NTC | R_ntc = R_measured − 2.2 kΩ (series protection resistor) |
| USART1 | 2 Mbaud; USART1 clocked from PCLK2 = 170 MHz (BRR = 85, exact; HSI16-derived via the PLL) |
```

### 2.3 §3.5 compute-board requirements, item 4

**(a) Replaces** the sentence inside item 4 (the W_ARM_CLK bullet body):
`A reported weapon latch makes the compute board stop the ARM toggle (disarm) first, then persist its copy.`
with:

```markdown
On a reported weapon latch the compute board stops the ARM toggle (disarms).
```

(The rest of the item 4 body — 500 Hz, gap limits, RAM ISR, 50 ms permission refresh, radio
≤ 0.5 s, heartbeat gating, no flash writes while armed, Low/Hi-Z when disarmed — is KEEP,
unchanged.)

**(b) Replaces** all six sub-bullets under item 4, from `   * **Boot self-test (timed, …` through
`     until the operator clears it (§8.1); run the boot self-test with the weapon command at zero.`
(inclusive), with:

```markdown
   * **Boot self-test (timed, run by the compute board, which knows when it stopped toggling; weapon
     command at zero):** (a) give one single edge and expect W_ARM_S to stay low (catches a C15/C16
     swap); (b) toggle for 100 ms and expect W_ARM_S high; (c) hold W_ARM_CLK high and expect the
     heartbeat's "W_ARM_S fell" flag within 20–250 ms (the fastest good board is ~30 ms, an open
     C16 ~0 ms); (d) toggle again, hold low, expect the same.  Uses the heartbeat fields defined in
     §8 (period ≤ 10 ms).  Catches a shorted C15, an open/high R41, an open C16 and a U14 stuck
     high.  On failure: refuse to arm and report it (the drive still works).
   * **Re-arm after a motor-MCU reset:** when the heartbeat reports "ARM edge required" and no
     weapon latch, hold W_ARM_CLK low for ≥ 250 ms, then toggle again; the weapon then waits for
     its command at zero.  A reported latch or hold is shown to the operator and needs an operator
     action to clear (§8.1); the compute board never sends "clear faults" on its own.  Keeping a
     latch across a power cycle is optional (the weapon's first-start checks re-detect a real
     short).
   * **Radio loss** (≤ 0.5 s) must also stop the drives: stop sending drive commands (the motor
     MCU's command timeout then coasts everything), not only the ARM toggle.
   * Hold-up: ~470 µF on the compute board's 5 V input rides through millisecond contact bounce
     at the switch/XT30 under load (otherwise both boards reset and Bluetooth takes seconds to
     reconnect).  Do not drive MB_RX while the motor board is unpowered (a USB-powered Pico would
     back-power the motor MCU through R17).
   * If the motor MCU's heartbeat stops for > 100 ms, stop toggling and pulse NRST (open drain),
     except during an SWD session or flash of the motor MCU; at most 2 such resets within 10 s,
     then stop resetting and report (a broken return line must not reset the motor MCU forever).
```

---

## 3. Knock-on notes for the other trims (not in this file's scope)

* §8.1 "Latch word" paragraph: its last sentence ("A power cycle therefore clears the board's
  latches, so **the compute board mirrors the weapon latch … then persists the copy**") conflicts
  with the §3.5 cut above; reduce to "A power cycle clears the board's latches (the compute board
  shows them to the operator, §3.5)".  §8.1 row 0's "the compute board does not persist it"
  clause becomes unnecessary.
* §8.1 "Per-drive coast" paragraph repeats the coast/Release words now listed in the DRV8316C
  row; it can reference that row and keep only the bench-verify note.
* References kept to §8.1 by name/number: "drives resume", "throttle-zero interlock", weapon rows
  0, 1, 6, 10, drive row 7.  If the §8.1 trim renumbers or renames them, update these rows.
* §9 step 5 still has to store the Z offset (and λ if §8.1 keeps the back-EMF preset); nothing in
  these rows needs the "optional torque-relax" or Z-candidate tests any more — drop them from §9
  if present.
* The Timer-inputs rewrite drops "not after a left/right-crossed report until drive row 7 is
  cleared" — that gating belongs in §8.1 row 7, which already says it.
