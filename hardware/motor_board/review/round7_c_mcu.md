# Round 7 (C): MCU timer/ADC plan and firmware contract, rev G

Scope: DESIGN.md rev G §3.3, §3.4, §3.5, §8 and §9, checked against `round6_c_mcu.md` and `CHANGES.md` (round 6 → rev G).
No design file was edited.

Sources used this round:

* **SLVSH07** (`datasheets/DRV8316C.pdf`):
  * §7.5 tPD 650/1050 ns and tDEAD 500/750 ns at 200 V/µs, tSET ≤ 1 µs, tMIN_PULSE 600 ns;
  * §8.3.9.1 and Table 8-6 (delay compensation; TI recommends 0x5 at 200 V/µs and 0x8 at 125 V/µs);
  * §8.3.14.1 (NPOR latched low until CLR_FLT);
  * Table 8-13 (IC_STAT: NPOR 0 = POR detected, 1 = none);
  * Tables 8-18 to 8-24 (CTRL1 to CTRL10, reset values).  CTRL2 bit 0 CLR_FLT is **W1C**: "automatically resets after being written".
* **RM0440 Rev 7** (the WeActStudio mirror, the local copy fetched in round 5):
  * SYSCFG_CFGR2 CLL;
  * §28.3 break circuitry: Figure 316, "BKE … enables the complete break protection (including all sources …)", and "MOE cannot be set while the break input is active";
  * TIMx_AF1 reset value 0x0000 0001 (BKINE = 1);
  * the OPAMP5 pin table (PC3 = VINP2, VOUT → ADC5_IN3).
* **DS12288** (`datasheets/STM32G474RET6.pdf`): Table 66 tLATR, Table 67 RAIN max.
* `ref/STM32G474RxTx_pins.xml`: the AF of every pin listed in §3.4 and §8, rechecked.

Timing model (the same as rounds 5 and 6):

* 170 MHz timers.  TIM8 period 20.835 µs, TIM1 period 41.671 µs.
* 42.5 MHz asynchronous ADC clock.  tLATR is 1.5–2.5 cycles.  Each injected rank is 12.5 + 12.5 cycles.
* The drive low-side (LS) window is ±h about valley + T, with h = (1 − D) × 10.4175 µs.
* For i > 0, the LS channel conducts only in [−h + T + tDEAD, h + T − tDEAD], and the CSA needs a further tSET = 1 µs.

---

## 1. Re-check of the rev G changes

### 1a. DLY_TARGET 1.8 µs by default (CTRL10 0x1818): VERIFIED

**The frame.**
* 0x1818 decodes as W = 0, address 0x0C, B8 = 0, data 0x18: DLYCMP_EN = 1 and DLY_TARGET = 8h.
* Table 8-24 gives 8h = 1.8 µs.
* The word has four 1-bits, so the parity is even.

**Why 1.8 µs.**
* The worst-case tPD + tDEAD at 200 V/µs is 1.05 + 0.75 = 1.80 µs, so the target holds by specification with no spare.
* TI's Table 8-6 value for 200 V/µs is 0x5 (1.2 µs).  Picking 0x8 is a documented, deliberate deviation.

**Reserved bits.** Bits 7–5 of CTRL10 are R-0, so the register reads back 0x18.

### 1b. CCR6 ≈ 257–264: VERIFIED

The target is the centre of the valid window, valley + T + tSET/2 = 2.30 µs.

| CCR6 | t_inj (µs) | rank 1 | rank 2 | rank 3 | group centre | injected busy until |
|---|---|---|---|---|---|---|
| 257 | 1.512 | 1.547–1.865 | 2.135–2.453 | 2.724–3.041 | 2.294 | 3.335 |
| 258 | 1.518 | 1.553–1.871 | 2.141–2.459 | 2.729–3.047 | 2.300 | 3.341 |
| 264 | 1.553 | 1.588–1.906 | 2.176–2.494 | 2.765–3.082 | 2.335 | 3.376 |

* CCR6 = 258 is the exact centre.
* The range 257–264 is the round 6 range (155–162) plus 102 counts, i.e. +0.6 µs.

### 1c. Regular windows [3.34, 13.59] / [24.18, 34.43] µs: VERIFIED

The two conditions are:
* the regular trigger comes after the injected group ends: t_r + 1.5 cycles ≥ 3.376;
* the regular group ends before the next injected trigger: t_r + 2.5 cycles + 371 cycles ≤ 20.835 + 1.512 + 1.5 cycles.

Result:
* the windows are **[3.34, 13.59] and [24.18, 34.43] µs**, valid over the whole CCR6 range 257–264;
* "each window moves by CCR6/170 MHz" is correct.

The regular group is 371 cycles = 8.73 µs:
* ranks 1–3 at 24.5 cycles, rank 4 at 247.5 cycles;
* the VREFINT rank is 5.82 µs, which meets the ≥ 4 µs requirement.

### 1d. The weapon uses ranks 1–2 only: VERIFIED

The weapon's valid limit is peak + h_w + 0.15 µs (DRV8323 tPD).

| Ranks used | Weapon duty cap |
|---|---|
| Ranks 1–2 (end at ≤ peak + 2.494 µs) | **88.7–88.9 %** |
| Ranks 1–3 (end at 3.08 µs) | 85.9–86.1 % |

* Ranks 1–2 give all three phases: A+B in rank 1, then C+A in rank 2.
* §3.4's "weapon ~86–88 %" is therefore correct and conservative.

### 1e. Drive R: rank-2 pair with C = −(A+B), ~86 %: VERIFIED

* The rank-2 pair is A on ADC4 and B on ADC3, sampled simultaneously.
* The cap is **86.1–86.5 %** at maximum tDEAD and 88.5–88.9 % at typical tDEAD, over CCR6 = 257–264.

### 1f. Drive L ~81 %: VERIFIED

The cap is **80.5–80.8 %** at maximum tDEAD and 82.9–83.2 % at typical tDEAD.

### 1g. Heartbeat fields and period ≤ 10 ms: VERIFIED in §8 and §3.5, but the fix was only partly carried through

* §8 defines the heartbeat fields:
  * the W_ARM_S level;
  * a latched "fell" flag plus the time since that edge in ms;
  * "ARM edge required";
  * faults and counters;
  * the register-check status.
* §3.5 item 4 refers to those fields and to the ≤ 10 ms period.

However, the §8 W_ARM_S row still contains the round 6 text: see R7C-04.

### 1h. The sequence number must advance: present, but underspecified (R7C-05)

### 1i. CTRL3 read-back and the mismatch action: present

* CTRL3 is now read back.
* The mismatch action is DRV_OFF high, rewrite the sequence, report.
* The expected read-back values are not stated, and one of them differs from the frame that was written: see R7C-01.

### 1j. No OPAMP self-calibration: VERIFIED

* §8 forbids the HAL self-calibration and uses the factory trim.
* OPAMPINTEN is set before OPAMPEN.
* The mapping is confirmed by the RM0440 OPAMP5 table: VINP2 = PC3, VOUT = PA8, internal output to ADC5_IN3.

### 1k. CLL: present, but incomplete for TIM20 (R7C-02)

### 1l. No flash erase while running: VERIFIED

* A page erase takes 22.02 / 24.47 ms (typ / max).
* The IWDG times out in 18.8–21.7 ms, so the rule is needed.

### 1m. Break flags cleared at boot: present, but without the ordering condition (R7C-03)

### 1n. USART1 clock text: VERIFIED

* PCLK2 = 170 MHz with OVER16 gives BRR = 85, exactly 2.000 Mbaud.
* USART1SEL = 00 (PCLK2) is the reset default.
* The combined error with an RP2040 is at most the HSI16 spread of 1.85 %: the RP2040's 125 MHz / (16 × 2 Mbaud) = 3.90625 is exact with FBRD = 58.

### 1o. §9 CCR6 trim step: present (step 5); the method is not given (N-4)

---

## 2. Findings

| ID | Sev | Where | Issue | Evidence | Fix |
|---|---|---|---|---|---|
| **R7C-01** | **MINOR** | §8 DRV8316C row: "Read back CTRL2/CTRL3/CTRL4/CTRL5/CTRL6/CTRL10 … on a mismatch or NPOR: DRV_OFF high, rewrite"; §9 step 2 "check BUCK_UV/NPOR clear after CLR_FLT" | **The expected read-back values are not given, and the obvious choice is wrong for CTRL2.**<br><br>**CTRL2.** The last CTRL2 frame written is 0x097D.  CLR_FLT is W1C and "automatically resets after being written", so CTRL2 reads back **0x7C**, not 0x7D.<br>A firmware author who compares against the last value written sees a mismatch on every poll.  The result is DRV_OFF high, a rewrite, and a report every ~10 ms.  **Both drives are dead**, because DRV_OFF is shared.<br><br>**NPOR polarity.** NPOR reads **0 when a POR was detected** and 1 when none was (Table 8-13).  "NPOR clear" in §9 reads naturally as NPOR = 0, which is the fault state. | SLVSH07 Table 8-19 (CLR_FLT W1C), Table 8-13 (NPOR 0h = POR detected), §8.3.14.1 | List the expected read-back values in §8:<br>• CTRL1 0x06 (locked);<br>• CTRL2 **0x7C**;<br>• CTRL3 0x4E;<br>• CTRL4 0x10;<br>• CTRL5 0x00;<br>• CTRL6 0x19;<br>• CTRL10 0x18;<br>• IC_STAT NPOR = **1** after CLR_FLT.<br><br>In §9 write "NPOR = 1, BUCK_UV = 0". |
| **R7C-02** | **MINOR** | §8 Watchdog row: "SYSCFG_CFGR2.CLL = 1 so a core lockup triggers the timer breaks in hardware" | **CLL only acts on a timer whose break function is enabled, and nothing tells the author to enable TIM20's.**<br>• Per RM0440, BKE "enables the complete break protection (including all sources …)", and Figure 316 gates tim_sys_brk behind BKE.<br>• TIM1 and TIM8 need BKE = 1 anyway, for their BKIN pins.<br>• **TIM20 has no break pin** (§3.3), so a natural init leaves BKE = 0.<br><br>**Consequence.** On a lockup, drive R keeps switching at its last duty until the IWDG fires (≤ 21.7 ms).  DRV_OFF stays low, because the handler never ran.<br><br>**A second trap.** TIM20_AF1.BKINE resets to **1**, and no GPIO carries TIM20_BKIN.  The level that an unmapped BKIN presents to an active-low break is **UNVERIFIED**, so BKE = 1 alone might hold TIM20 in permanent break. | RM0440 §28.3 (BKE description; Fig. 316; tim_sys_brk0 = LOCKUP, CLL); TIMx_AF1 reset 0x0000 0001; pin XML (no TIM20_BKIN on any used pin) | Add to §8:<br>• "TIM20: BDTR.BKE = 1 with TIM20_AF1.BKINE = 0 (system break only), so CLL covers drive R";<br>• TIM1/TIM8 BKE = 1, BKP = 0 (active low);<br>• check it at bring-up: force a lockup (e.g. a fault inside the HardFault handler, debug build) and scope INH and W_INL. |
| **R7C-03** | **MINOR** | §8 Watchdog row "Clear the break flags at boot"; §8 DRV8323RH row "Expect nFAULT low for ~1 ms after each wake" | **The round 6 fix dropped the ordering condition.**<br><br>**The rule.** Break inputs act on level, and "MOE cannot be set while the break input is active".<br><br>**The sources still active during boot:**<br>• W_nFAULT: low for ~1 ms after W_EN goes high;<br>• L_nFAULT (TIM8 BKIN): low until U3's CLR_FLT, per §9 step 2;<br>• INA239 ALERT: latched (ALATCH = 1) until DIAG_ALRT is read.<br><br>**What goes wrong.** A firmware that clears BIF/SBIF as its first boot step then:<br>• sees BIF set again;<br>• fails to set MOE, silently if AOE = 0;<br>• or counts boot-time breaks toward the "> 3 per second → latch off" rule. | RM0440 §28.3 break note ("MOE cannot be set while the break input is active"); round 6 R6C-N6(c); DESIGN §8 boot order | Reword it as a boot step:<br>1. after W_EN high + ≥ 1 ms, U3/U4 CLR_FLT and one INA239 DIAG_ALRT read, check that PC13 and PB7 are high;<br>2. then clear TIMx_SR.BIF/SBIF on TIM1/TIM8/TIM20;<br>3. then allow MOE.<br><br>Do not count breaks before this point as faults. |
| **R7C-04** | **MINOR** | §8 W_ARM_S row: "Time the falling edge after the toggling stops and report it (for the compute board's timed self-test)" | **Stale round 6 text.**<br>• The MCU never sees W_ARM_CLK, so it cannot time anything "after the toggling stops" (R6C-03).  The Heartbeat row and §3.5 now say the compute board does the timing.<br>• The latched "fell" flag has no clear rule.  Self-test step (d) comes after (c) has already latched the flag, so the compute board must be able to tell a new edge from the old one.<br>• The width and saturation of the "time since that edge" field are not defined. | nets.md (W_ARM_CLK only on C15/R18/J1.19); DESIGN §3.5 item 4 (c)/(d); §8 Heartbeat row | Replace the sentence with: "Time-stamp each PD2 falling edge.  The heartbeat carries the age of the most recent one (u16 ms, saturating) and an edge counter.  The latch clears on the next qualified rising edge."<br><br>The compute board computes t_fall = t_rx − age. |
| **R7C-05** | **MINOR** | §8 Command link row: "sequence number that must **advance** (a repeated frame does not count)" | **The rule has no definition for counter wrap or for a compute-board restart.** Two readings, both plausible, both fail:<br>• **Wrap.** "Advance" read as `seq > last` fails at the wrap.  A u8 at 1 kHz wraps every 256 ms, which gives a spurious failsafe (drives coast) every wrap.<br>• **Compute-board reboot.** The sequence restarts at 0, so the motor MCU rejects every frame until the counter passes the old value.  With a u16 that is up to 65 s; with a u32, forever. | DESIGN §8; §3.5 item 4 | Define the rule:<br>• u16 serial-number arithmetic: accept if (seq − last) mod 2¹⁶ ∈ [1, 32767];<br>• once the command timeout has fired, accept any sequence number as the new base, but move nothing until a second, advancing frame has arrived. |
| **R7C-06** | **MINOR** | §3.4 and §8 STM32 row: "injected on TIM8_TRGO2 (OC6REF)", "regular on TIM1_TRGO2 = OC6REF", "ADC1/ADC2 dual simultaneous" | **The trigger configuration that makes all the numbers true is not written down.** It exists only in round 4/5 reviews.<br><br>**(a) TIM8 OC6 mode.** OC6M must be **PWM mode 2** with MMS2 = OC6REF and JEXTEN = rising, so the edge falls at valley + CCR6.<br>• PWM mode 1 is the CubeMX default.  With it and a rising edge, the trigger lands at valley **− 1.51 µs**.<br>• That sample is outside the valid window at the cap: it needs ≥ −h + 3.55 µs.<br>• It also collides with the regular windows.<br><br>**(b) TIM1 OC6.** The regular trigger uses TIM1's own CCR6, which shares the name "CCR6" with TIM8's.<br>• Window 1 needs OC6 PWM2 with TIM1_CCR6 = **568–2311**.<br>• Window 2 needs OC6 PWM1 with TIM1_CCR6 = **1231–2974**.<br>• EXTEN must be rising.<br><br>**(c) Dual mode.** Both groups must be simultaneous, which is **DUAL = 00001** (combined regular simultaneous + injected simultaneous).  00101 or 00110 leaves one group independent.<br><br>**(d) Weapon sample selection.** The injected ISR runs at 48 kHz, and the weapon must use only the trigger at the TIM1 peak.  That is the one where TIM1_CR1.DIR = 1 (down-counting) in the JEOS ISR. | Computed above (§1b, §1c); RM0440 ADC_CCR DUAL; round5_c l.113/153 | Add to §8 STM32 row:<br>• TIM8: OC6M = PWM2, MMS2 = OC6REF, CCR6 ≈ 258;<br>• ADC: JEXTSEL = TIM8_TRGO2, JEXTEN = rising;<br>• TIM1: OC6M = PWM2 (or PWM1) with TIM1_CCR6 in 568–2311 (or 1231–2974), MMS2 = OC6REF, EXTSEL = TIM1_TRGO2, EXTEN = rising;<br>• DUAL = 00001;<br>• weapon samples are taken when TIM1 DIR = 1.<br><br>Name the two registers TIM8_CCR6 and TIM1_CCR6 everywhere. |
| R7C-N1 | NOTE | §3.4 "CCR6 set so the sample lands ~1 µs after the drive low-side window opens + DLY_TARGET" | **The wording describes a duty-dependent placement, but CCR6 is fixed.**<br>• The window opens at valley − h + T, which depends on duty.<br>• The chosen CCR6 instead centres the group on valley + T + tSET/2 = 2.3 µs, independent of duty.<br>• Rank 1 actually starts at valley + 1.55 µs, before valley + T.<br><br>The number is right; the sentence is not. | §1b | Say "CCR6 centres the injected group on valley + DLY_TARGET + tSET/2 (2.3 µs)". |
| R7C-N2 | NOTE | §3.5 item 4 ("the motor MCU's heartbeat is seen"); §8 Heartbeat row | **The compute board gates ARM on the heartbeat, but the heartbeat has no freshness field.**<br>• There is no CRC and no advancing counter, unlike the command frames.<br>• A UART TX in circular DMA keeps resending a stale buffer while the CPU is stuck.  The IWDG bounds this at ~20 ms, but only if that task is part of the check-in set. | §8 Watchdog row | Give the heartbeat a CRC and an advancing counter.  The compute board treats a non-advancing heartbeat as absent. |
| R7C-N3 | NOTE | §8 CTRL10 0x1818 with flat-bottom SVPWM | **Short pulses meet a long delay.**<br>• The middle and lower phases get HS pulses shorter than DLY_TARGET: tMIN_PULSE is 0.6 µs, against 1.8 µs.<br>• SLVSH07 does not say how delay compensation treats a pulse whose second edge arrives before the first delayed edge has been output (**UNVERIFIED**).<br>• The same question existed at 1.2 µs. | SLVSH07 §8.3.9.1, §7.5 tMIN_PULSE | Bring-up: with DLYCMP on, sweep one phase from 0 % to 10 % duty and scope OUTx.  Check the output pulse width against INHx, and that the OUT edge sits at INH + 1.8 µs for both current directions. |
| R7C-N4 | NOTE | §9 step 5 "Trim CCR6 on a scope so the drive CSA sample sits in the low-side window" | **The sampling instant cannot be seen on a scope.** OC6 has no pin, and all 64 pins are used (R6C-N6(d)). | mcu_pinmap.md | Give the method:<br>1. scope INHx → OUTx to confirm the 1.8 µs delay;<br>2. with a DC phase current at a fixed high duty, sweep CCR6 ±60 counts and log the reading;<br>3. set CCR6 in the middle of the flat plateau. |
| R7C-N5 | NOTE | §3.5 item 4 "no gap longer than ~20 ms (≥ 50 ms disarms)" vs §1/§9 "disarms ~30–200 ms" | **The parenthetical overstates the safe gap.**<br>• At the tolerance corner, a 30–50 ms gap can already disarm.<br>• The ~20 ms requirement itself is fine. | DESIGN §1, §9 step 3; `arm.out` | Write "(gaps of ~30 ms or more may disarm)". |
| R7C-N6 | NOTE | §8 DRV8316C row (100 Hz read-back) and INA239 (up to 1 kHz) | **Two shared resources are not called out.**<br>• **SPI3** is shared by U3, U4 and U7, and they are polled from different tasks.  The contract does not say that one owner serialises the bus.  A read-back preempted by an INA239 read corrupts both.<br>• **DRV_OFF** is shared, so a register mismatch on one DRV8316 stops **both** drives for the rewrite (~40 µs of frames plus the resume).  That is acceptable, but the contract should say so. | §3.4 SPI3; §8 | State: one SPI3 owner (a queue or a DMA sequencer), and "a mismatch on either DRV8316 coasts both drives". |

---

## 3. Consistency sweep

**Pins.** Rechecked against the ST pin XML; all agree with §3.3, §3.4 and §8.

| Function | Pin |
|---|---|
| TIM1_BKIN | PC13 |
| TIM8_BKIN | PB7 |
| R_nFAULT | PC15 |
| DRV_OFF | PC14 |
| W_ARM_S | PD2 |
| USART1_TX / RX | PC4 / PC5 |
| TIM20_CH1/2/3 | PB2 / PC2 / PC8 |
| TIM8_CH1/2/3 | PB6 / PC7 / PB9 |
| OPAMP5_VINP | PC3 |

ADC channels:

| Pin | Channel |
|---|---|
| PA0 | ADC12_IN1 |
| PA1 | ADC12_IN2 |
| PA2 | ADC1_IN3 only (ADC2 never uses it) |
| PB11 | ADC12_IN14 |
| PA3 | ADC1_IN4 |
| PF0 | ADC1_IN10 |
| PF1 | ADC2_IN10 |
| PA4 | ADC2_IN17 |
| PA5 | ADC2_IN13 |
| PA6 | ADC2_IN3 |
| PB12 | ADC4_IN3 |
| PB13 | ADC3_IN5 |
| PB1 | ADC3_IN1 |
| PA8 | ADC5_IN1 |
| PA9 | ADC5_IN2 |

**Timers.** The same values appear in §3.4, §8 and calcs §8:
* TIM1: ARR 3542, PWM mode 1, 23 997.7 Hz;
* TIM8 and TIM20: ARR 1771, PWM mode 2, 47 995.5 Hz;
* URS = 1, ITR0, MMS = update.

**DRV8316 frames.** All ten were re-decoded:
* 0x0603, 0x1019, 0x0A4E, 0x0D10, 0x0F00, 0x1818, 0x087C, 0x097D, 0x0606;
* 0x1915 appears in the text only as the rejected alternative;
* the addresses are 03/08/05/06/07/0C/04/04/03 and every parity is even.

**Duty caps.** They agree everywhere:
* §3.4 and §8 give 81 / 86 / 86–88 %;
* §3.3 and §4 give 3.7 / 3.1 m/s;
* calcs §10 gives 46.5 k rpm and 10.3 updates per electrical cycle.

The ~50 k rpm sensorless hand-over in §8 is above the capped ~47 k rpm top speed.  That is harmless: it is only reached with field weakening.

**Thresholds.** The ordering is unchanged and consistent:

| Item | Value |
|---|---|
| Firmware weapon coast | 18.5 V |
| INA239 BOVL | 19.0 V |
| DRV8316 OVP | 20–22 V |
| Shared current budget | 32 A |
| SOVL | 38 A |

**ARM timing.** It is consistent across §3.5 and §9: self-test window 20–250 ms, disarm 30–200 ms, heartbeat ≤ 10 ms, NRST pulse after 100 ms, permission refreshed every 50 ms.  The one exception is R7C-N5.

**ADC source impedance.**
* The 12.5-cycle rank at 42.5 MHz is 294 ns.
* DS12288 Table 67 allows 680 Ω (fast channels) at 208 ns, so 330 Ω behind 22 pF is fine.
* The OPAMP5 rank is ≥ 200 ns.

---

## VERIFIED OK

* **CTRL10 0x1818:** DLYCMP_EN = 1, 1.8 µs, even parity.  1.8 µs = the worst-case tPD + tDEAD at 200 V/µs.
* **CCR6 ≈ 257–264:** centres the injected group at 2.29–2.34 µs.  The ideal is 2.30 µs, at CCR6 = 258.
* **Regular windows [3.34, 13.59] / [24.18, 34.43] µs:** exact for the whole CCR6 range, with an 8.73 µs group.  They move with CCR6/170 MHz.
* **Weapon, ranks 1–2:** cap 88.7 %, against 85.9 % with rank 3.  A+B and C+A give all three phases.
* **Drive R, rank-2 pair with C = −(A+B):** 86.1–86.5 % worst case.
* **Drive L:** 80.5–80.8 % worst case.
* **Heartbeat fields and ≤ 10 ms period** are defined in §8 and used by §3.5.
* **CTRL3** is in the read-back list, and the mismatch action is defined.
* **OPAMP5:** no HAL self-calibration; factory trim; OPAMPINTEN before OPAMPEN; VINP2 = PC3.
* **CLL** exists and routes the LOCKUP to TIM1/8/15/16/17/20 break.  It is set at boot; see R7C-02 for TIM20.
* **No flash erase while running:** tERASE of 22–24.5 ms is longer than the 18.8–21.7 ms IWDG.
* **USART1:** PCLK2 170 MHz, BRR = 85, exactly 2 Mbaud; HSI16 through the PLL.
* **Clock plan:** HSI16 /4 × 85 = 340 MHz VCO → R/2 = 170 MHz, P/8 = 42.5 MHz.
* **Pins, timer values, INA239 values and thresholds** are consistent across §3.3, §3.4, §3.5, §4, §8, calcs and the pin XML.

---

**Verdict: 0 BLOCKER, 0 MAJOR, 6 MINOR (R7C-01…06), 6 NOTE.**  All of them are firmware or documentation fixes; no
hardware change is needed.
