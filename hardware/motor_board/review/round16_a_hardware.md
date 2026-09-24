# Round 16 / A: hardware (rev L): the round-15 §8.1 rewrite against the datasheets and the netlist

Scope: every hardware or datasheet fact that the rewritten DESIGN §8.1 (fault policy), the reordered weapon rows 0–12,
the drive rows 1–6, the per-drive coast, the latch word and the §3.5/§9 text rely on.  I also re-checked the parts of the
circuit where I had a reason to doubt them.  Board area/fit, prose, and firmware choices that are one reasonable option
among several are out of scope.  This file is the only one I wrote in the package.

**Snapshot.**  I copied the package to `/tmp/r16a`.  `design/motor_board.py` prints "237 refs (205 placed components),
160 nets, 67 BOM lines, checks: OK".  The regenerated nets.md, netlist.csv, bom.csv and mcu_pinmap.md are byte-identical
to the working tree.  `sim_hotplug.py` and `sim_arm.py` (run in a copy with the `tools/spice` helper beside it)
reproduce `hotplug.out` and `arm.out` byte-identically.

References: [DRV16] DRV8316C SLVSH07; [DRV23] DRV8323 SLVSDJ3D; [INA] INA239 SLYS027A; [STM] STM32G474 DS12288;
[RM] RM0440 (not in datasheets/); [D] DESIGN.md rev L; [N] nets.md / motor_board.py.

## Verification of the facts §8.1 relies on

| Claim | Verdict | Evidence |
|---|---|---|
| CTRL4 bit 7 = DRV_OFF, "1h = Hi-Z FETs"; CTRL4 reset 0x10 = OCP_DEG 0.6 µs, 5 ms retry, 16 A, latched | Correct | [DRV16] §8.6.2.4, Fig. 8-54 / Table 8-21 p.65 |
| SPI word = W(B15), A5..A0(B14–B9), P(B8), D7..D0; even parity over the 16-bit word | Correct | [DRV16] §8.5.1.1, Table 8-9 p.54–55.  Addresses: CTRL1 3h, CTRL2 4h, CTRL3 5h, CTRL4 6h, CTRL5 7h, CTRL6 8h, CTRL10 Ch (Table 8-16 p.60) |
| Parity of every DRV8316 frame in §8/§8.1 | **All correct except one** (R16A-01) | Script over every 16-bit hex word in DESIGN.md: 0x0603, 0x0606, 0x087C, 0x097D, 0x0A4E, 0x0D10, 0x0C90, 0x0F00, 0x1019, 0x1818, 0x1915 are even.  **0x0C10 is odd.**  (0x1000, 0x76C0 and 0x17C0 are INA239 values, where parity does not apply) |
| Expected read-backs 0x7C / 0x4E / 0x10 (0x90 coasted) / 0x00 / 0x19 / 0x18 | Correct | Field-by-field against Tables 8-19..8-24: CTRL2 0x7C = reserved 01, SDO push-pull, 200 V/µs, 3x, CLR_FLT 0; CTRL3 0x4E = reserved bit 6, OVP 22 V on, SPI_FLT_REP 1, OTW_REP 0; CTRL6 0x19 = BUCK_PS_DIS, BUCK_CL, BUCK_DIS; CTRL10 0x18 = DLYCMP_EN + 1.8 µs |
| A reset DRV8316 comes up in 6x mode; NPOR 0 = POR seen | Correct | CTRL2 reset 60h, PWM_MODE 0h = 6x (Table 8-19); IC_STAT NPOR (Table 8-13) |
| CSA idle = ~1.65 V on a powered chip | Correct | 0 A output = VREF/2 [DRV16] §8.3.x p.39, Fig. 8-29/8-30; VREF = own AVDD 3.1–3.465 V → 1.55–1.73 V |
| nFAULT pulled to the chip's own AVDD → low when that chip is unpowered | Correct | [N] R301/R401 to L_AVDD/R_AVDD; [DRV16] pin table p.5 (pull-up > 2.2 V at power-up) |
| nSCS has an internal 100 kΩ pull-up (an open nCS = deselected) | Correct | [DRV16] EC "LOGIC-LEVEL INPUTS (nSCS)", RPU 80/100/130 kΩ p.10 |
| An unpowered or deaf chip reads 0x0000 | Correct | SDO Hi-Z with nSCS high [DRV16] §8.5.1; PC11 pull-down [D] §3.4 |
| INA239 SOVL 0x76C0 = 38 A, BOVL 0x17C0 = 19.0 V, SHUNT_CAL 0x1000 | Correct | [INA] Table 7-14 (1.25 µV/LSB at ADCRANGE 1): 30400 × 1.25 µV = 38.0 mV; Table 7-16 (3.125 mV/LSB): 6080 → 19.0 V; SHUNT_CAL = 819.2e6 × 1.25 mA × 1 mΩ × 4 = 4096 |
| Other limits stay "never trip" at reset | Correct | SUVL 8000h (most negative), BUVL 0h, SOVL/BOVL 7FFFh reset; comparisons are "exceeds"/"falls below" [INA] Tables 7-13..7-17 |
| ALATCH = 1: ALERT held until DIAG_ALRT is read; CNVR = 0; APOL = 0 active-low open drain | Correct | [INA] §7.3.x p.16 and Table 7-13 p.23–25 |
| Registers update only at conversion end; first bus conversion started after the event ≤ ~0.45 ms at 150 µs | Correct | [INA] §7.3.4 p.13–14: enabled inputs convert sequentially; worst case = rest of the bus conversion + shunt + bus = 3 × 150 µs |
| No POR flag on the G474; BORRSTF set at power-on and BOR; PINRSTF with every reset; lockup → IWDG | Correct | [RM] RCC_CSR; [STM] §3.11.2 (BOR always on).  Settled in R15A N-01 |
| Backup registers survive system/BOR resets, lost only when the backup domain loses power (VBAT = +3V3) | Correct | [STM] §3.26 p.39: "not reset by a system or power reset"; tamper erases them (unused) |
| VBAT_SNS slope > ~5 V/ms separates a bounce from a load step or a compute-board reset | Feasible, load-dependent (N-02) | τ = 8.72 kΩ × 100 nF = 0.87 ms; PA3 = ADC1 regular rank 2 on TIM1_TRGO2 (24 kHz, runs through a break).  My estimate (constant bus current into 380 µF, 4-sample sliding average): 1.4 V load step → 1.4 V/ms; 20 A bounce ≥ 0.3 ms → 10.5 V/ms; 10 A → 5.2–12.7 V/ms; 5 A → 4.3–8.6 V/ms |

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R16A-01 | **MAJOR** | [D] §8.1 "Per-drive coast": "leave with CTRL4 **0x0C10**" | **The frame that ends a per-drive coast has the wrong parity.  With it, the per-drive coast in drive row 2 would never end.**<br><br>0x0C10 = address 6h, data 10h, P = 0.  That word has three 1 bits (0x0C: 2, 0x10: 1), so it is odd.  The even-parity frame is **0x0D10**, which is the value §8 already uses for the initial CTRL4 write.  Round 15's R15A-01 recommended 0x0D10.  The paragraph with the error also says "even parity makes it 0x0C90, not 0x0D90", so the leave frame contradicts the rule stated right beside it.<br><br>The datasheet does not say whether the device executes a frame with a parity error.  It defines the parity rule and a SPI_PARITY status bit.  If the frame is rejected, DRV_OFF stays 1 and the chip stays Hi-Z.  The ~100 Hz check then reads 0x90 when it expects 0x10, which is drive row 2 again: another coast and another failed leave.  After ~3 of these within a second, that drive latches.  The result is fail-safe (the wheel coasts), but every transient per-drive event (OCP, CP-UV, NPOR, a register mismatch) would cost that wheel for the rest of the match | [DRV16] §8.5.1.1 p.54 (parity rule), Table 8-9, Table 8-15 (SPI_PARITY); parity check of every hex word in DESIGN.md (table above) | Text only: "leave with CTRL4 **0x0D10**" (DRV_OFF = 0, OCP 16 A latched, even parity).  Better still, tell firmware to compute B8 from the other 15 bits rather than copy constants |

## Notes

| ID | Sev | Note |
|---|---|---|
| N-01 | NOTE | **Drive rows 3/4 do not cover every combination, and "answering" is not defined.**  Row 3 needs nFAULT low **and** CSAs ~0 V.  Row 4 needs nFAULT high **or** CSAs ~1.65 V.  An unpowered chip's SOx pins are only clamped by its ESD structures (the unpowered state is not specified), so they may float at a middle value, while nFAULT low alone can also be a powered chip in a latched fault.  Suggest: row 3 only when nFAULT is low **and** all three SOx are < ~0.3 V; **every other not-answering case → row 4** (the safe superset: DRV_OFF high, both drives latched).  A hardware test for "answering": CTRL2 bit 6 is reserved and always 1 (reset 60h, [DRV16] Table 8-19), so a CTRL2 read of 0x00 means the chip did not answer, whatever the other registers show |
| N-02 | NOTE | **The row 2 slope figure depends on bus current.**  "A contact bounce reaches ≥ ~7–10 V/ms" holds at ≳ 5–10 A of bus current.  With the drum cruising at ~2–3 A, a bounce long enough to push U2 into UVLO (bus ≈ 5.6 V) reaches only ~4.5–6 V/ms at the filter output.  If that bounce ends within ~0.45 ms of the UVLO, the INA239 VBUS reading misses it too, so it lands in row 7 (weapon restart, counted; latch after ~5 in 10 s).  That outcome is acceptable (restart, not a false latch on one event).  Only the parenthetical overstates the separation.  §9 step 6's timed interruptions should include one at light drum load |
| N-03 | NOTE | **INA239 alert latency.**  With continuous shunt + bus at 150 µs each, a limit is compared once per 300 µs cycle.  An over-limit that starts just after a conversion began can take up to ~0.45 ms (§7.21's "0.3–0.8 ms" for BOVL is consistent; §8's "within ~0.3 ms" is optimistic).  No design consequence: the weapon's fast protection is the comparator.  Also, §3.1's "die temperature" is read only if temperature conversions are enabled.  That lengthens the cycle and moves the row 2 "≤ ~0.45 ms" timing, so keep MODE = shunt + bus |
| N-04 | NOTE | **The INA239 configuration is not in the ~100 Hz read-back.**  DEVICE_ID survives an INA239 reset, but SHUNT_CAL, ADC_CONFIG (conversion times revert to 1052 µs), SOVL/BOVL and ALATCH do not.  A reset INA239 would silently remove the pack over-current and bus over-voltage breaks.  Reading back SOVL/BOVL/ADC_CONFIG/DIAG_ALRT.ALATCH with the DEVICE_ID poll costs four frames |
| N-05 | NOTE | **Deaf-from-boot DRV8316 keeps its buck on.**  Row 4 can now last a whole match on a chip that was never configured.  It then runs in its reset state: buck enabled at 3.3 V into R300/R400 (22 Ω 1206, 250 mW) with BUCK_CL = 0.  r5 M2 estimated P ≈ 13.5 V × I_BK ≈ 70–100 mW for a few mA of AVDD/internal load.  That is inside the rating, and the DRV_OFF pin keeps the FETs off, so no change is needed; I record it only because round 5 assumed a short window |
| N-06 | NOTE | **Backup-domain wording.**  (a) Setting DBP also needs the PWR clock (RCC_APB1ENR1.PWREN), as well as RTCAPBEN for the TAMP registers.  (b) Changing RTCSEL does not itself reset the backup domain.  Once RTCSEL is set it cannot be changed without BDRST, and **BDRST** is the thing never to use.  (c) A very short supply interruption can leave the backup domain valid, so "a power cycle clears the board's latches" is not guaranteed.  That errs on the safe side |
| N-07 | NOTE | **§3.5 "heartbeat within ~50 ms of release".**  The hardware part of boot fits: NRST rises with R16/C67 τ = 1 ms, tRSTTEMPO ≤ 0.4 ms, DRV8316 t_READY 1 ms, U2 wake ≤ 1 ms.  The firmware must still send its first heartbeat before offsets, the strap boot test and the ADC warm-up, or the compute board will report a live motor MCU as dead |

## Independent re-checks (no finding)

* Weapon row order: a VDS OCP cannot coincide with a comparator trip on a shunt-path short.  The comparator chain
  Hi-Zs the bridge in 0.7–1.0 µs, inside the DRV8323's 4 µs VDS deglitch ([DRV23]; [D] §7.21).  So rows 4–6 ahead of
  row 8 do not hide a VDS-OCP latch.
* The EXTI lines needed (PC13, PB7, PC15, PD2, and COMP1/3/6 = EXTI 21/29/32) do not clash with any other EXTI
  source on the same line number in the pin plan.  PB7/PC13 keep their Schmitt input (IDR/EXTI) in AF mode.
* An unpowered U3 holds L_nFAULT (TIM8_BKIN) low, which holds the TIM8 break.  The injected ADC trigger is
  TIM8_TRGO2 = OC6REF, which keeps running with MOE = 0, so the right drive's sampling is unaffected.
* W_nFAULT: R42 10 k / C19 1 nF → ~10 µs release; INA239 ALERT and U2 nFAULT sink 0.33 mA; timings in rows 7–9 are
  ms-scale, unaffected.
* VBAT_SNS divider numbers in §3.5 (25.7 V full scale, 109 kΩ source, one-third reading with a 50 k pull-down,
  ±0.85 V per µA of leakage) recomputed: correct.
* DRV8316 CTRL3 SPI_FLT_REP = 1 keeps a parity or frame error off nFAULT, so a bad frame (R16A-01) would show only in
  STAT2, not as an nFAULT event.

**Verdict: 0 BLOCKER, 1 MAJOR, 0 MINOR, 7 NOTE.**  No hardware change is needed.  The one real error is the parity of the
per-drive coast exit frame (0x0C10 → 0x0D10).
