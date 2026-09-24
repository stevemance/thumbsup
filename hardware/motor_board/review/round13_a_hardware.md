# Round 13 / A: hardware (rev L): circuit correctness and the round-12 edits

Scope: power entry, the weapon DRV8323RH (straps, interlock, dynamic ARM), the DRV8316CR drives including the R302/R402
VM filter, current sense and the fast-trip thresholds, INA239, BQ76907, the sensor interfaces, logic levels, pin numbers
against the datasheet pads, absolute maximum ratings and part ratings.  I also checked that the round-12 edits are
technically correct.  Area and fit are out of scope.  This file is the only one I wrote in the package.

**Snapshot and reproducibility.**  I copied the package to `/tmp/r13a/`.  `design/motor_board.py` prints "237 refs (205 placed
components), 160 nets, 67 BOM lines, checks: OK".  The generated nets.md, netlist.csv, bom.csv and mcu_pinmap.md are
identical to the working tree.  `sim_hotplug.py` and `sim_arm.py` (hardware venv; they need `../../tools/spice`, so I ran
them from a copy placed next to a link to it) reproduce `hotplug.out` and `arm.out` byte-identically.  The working tree
picked up round-13 B text edits while I was reviewing.  I re-read the §8 fault-class row, the Timer-inputs row, §7.16, §7.21
and §9 step 0 afterwards, and the findings below apply to that current text.

References: [DRV23] DRV8323 SLVSDJ3D; [DRV16] DRV8316C SLVSH07; [INA] INA239; [MT] MT6701CT-STD; [STM] STM32G474 datasheet;
[D] DESIGN.md (rev L, current); [N] motor_board.py / nets.md.  Page numbers are PDF pages.

## Round-12 edits: verification

| Edit | Verdict | Check |
|---|---|---|
| R12A-01 → §9 step 0, R302/R402 forced-current check | **Correct** (one NOTE, N-01) | R302 is the only DC element between VBAT and L_VM [N].  The alternative path runs through U3: GND → low-side body diode → OUTx → high-side body diode → VM.  It needs VBAT − L_VM ≥ ~1.2 V plus a return through VBAT's loads, so at 0.1 V it carries nothing, with or without a motor fitted.  0.1 W in R302 is fine.  An open R302 gives the supply's CV limit, and either polarity is harmless |
| R12A-N01 (SDO) / N02 (VM feed-forward) | Correct | CTRL2 resets to 60h, SDO_MODE = 1 (push-pull), and SDO is Hi-Z with nSCS high ([DRV16] Table 8-19, §8.5).  The DRV8316 has no VM readback, so VBAT − I_bus·0.1 Ω is the only option |
| R12D-01 → §8 fault classes | **Partly wrong** (MINOR, R13A-01) | The class structure is sound.  The VDS OCP firmware latch works against the H-variant's hardware 4 ms auto-retry: nFAULT breaks TIM1, and with AOE = 0 MOE stays 0, so INLx stays low when U2 retries ([DRV23] §8.3.6.3.2 p.49).  The supply-class *detection* is the problem: it relies on "VBAT < ~9 V (VBAT_SNS / INA239 VBUS)", which cannot see the bounces the class was written for |
| R12D-02 → §8 start angle | **Incomplete** (MINOR, R13A-02) | Single-vector d-axis alignment has a 180° dead zone, and "Z is the reference" as worded cannot detect a wrong alignment |
| R12D-03 → §7.16 / boot 6x test | Correct (one NOTE, N-02) | 6x mode, INL = 0, INH = 1 → high side on ([DRV23] Table 8-2) → W_Vx = 16.8/7.8 = 2.15 V, against ~0 V for Hi-Z |
| R12D-04 → encoder speed cap 50 k rpm | Correct | At 50 k rpm and 1024 PPR, A/B run at 853 kHz: count edges every 293 ns, against the ICxF = 0b0011 filter's 8/170 MHz = 47 ns.  The 55,000 rpm rating is at [MT] p.8 |
| R12D-05 → §9 soak and regen tests | Correct | 18.3 V leaves 0.2 V under the 18.5 V coast |
| Heat budget +0.3 W (DRV8323) | Correct | I_VM 10.5–14 mA × 16.8 V = 0.18–0.24 W ([DRV23] p.17 l.1619).  Gate drive 3 × 59 nC × 24 kHz × 16.8 V ≈ 0.07 W.  Total 0.25–0.31 W |

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R13A-01 | MINOR | [D] §8 "Watchdog / faults" row, the **Supply class** sentence (and "a loaded contact bounce does all of these at once") | **The supply-class detection cannot see most of the events it exists for.**  The simulated loaded bounces pull the bus to 4.4–4.8 V for 0.3–0.8 ms, then re-close.<br><br>**(1) VBAT_SNS misses the short ones.**  VBAT_SNS is behind a 0.87 ms RC (68k‖10k × 100 nF).  My step model: the bus falls at 20 A / 380 µF to 4.6 V and is held for the bounce length.  Filtered minimum: **0.1 ms: 13.7 V; 0.3 ms: 12.0 V (10.7 V from a 12.5 V loaded bus); 0.8 ms: 8.8 V (8.0 V)**.  So only bounces of ~0.8 ms or longer read below 9 V.<br><br>**(2) INA239 VBUS catches it only if polled.**  It sees the dip only if firmware reads every conversion.  The shunt + bus cycle is ~300 µs, each result overwrites the last, and CNVR cannot be used because ALERT is the break line.  §4b plans reads at 100 Hz–1 kHz.<br><br>**(3) The DRV8316 flags do not fire.**  At 4.4–4.8 V the filtered VM stays above the DRV8316 UVLO (4.1–4.3 V falling), and VCP_UV is referenced to VM, so neither CP-UV nor NPOR is expected.<br><br>**(4) "U2 UVLO" is only inferable.**  It trips (5.4–5.8 V falling, 10 µs deglitch), but the H-variant reports it only as nFAULT low, with no register.<br><br>What firmware actually sees after a 0.3 ms bounce: W_nFAULT low for the bounce plus the ~1 ms wake, i.e. ~1.3–1.8 ms; a latched SOVL (~50 A recharge averaged over 150 µs); and a VBAT_SNS reading of ~12 V, "normal".  So "SOVL during a bus recharge" and "coincides with VBAT < 9 V" are both undecidable as written.  An implementer following the text finds a break that matches no class | [DRV23] p.17 l.1818–1822 (VUVLO 5.4–5.8 V, 10 µs), p.48 Table 8-7, §8.3.6.1; [DRV16] p.13 (VUVLO 4.1–4.3 V falling, VCPUV 2.2–2.6 V *above VM*); `hotplug.out` bounce rows (VM before 4.4–4.8 V, 109–210 A); [D] §3.4 (C68 0.87 ms), §4b (INA239 read rate), §8 INA239 row (CNVR = 0) | Classify on the signals the MCU does get:<br>• **W_nFAULT low time**: released in ≲ 3 ms means U2 UVLO / wake; ~4 ms (tRETRY) means VDS OCP; still low means GDF/OTSD/UVLO (sustained).  Read DIAG_ALRT first, so the INA latch does not stretch the line.<br>• **DIAG_ALRT SHNTOL with no comparator flag and no 4 ms nFAULT** → supply class.<br>• **VBAT dip**: a dip detector on VBAT_SNS (e.g. > ~1.5–2 V within 1 ms), or read INA239 VBUS every conversion (≥ 3.3 kHz) and keep a running minimum, instead of an absolute 9 V on a filtered signal.<br>Drop "DRV8316 CP-UV / NPOR" and "does all of these at once" from the bounce description; keep them as supply-class indicators for longer dips |
| R13A-02 | MINOR | [D] §8 "Timer inputs": **Start angle** and **Z is the reference** | **(a) Dead zone.**  A single d-axis vector has an unstable equilibrium at 180° error.  Torque = Kt·I·sin θ = 2.73 mN·m × sin θ at 1 A.  With ~0.3–0.5 mN·m of planetary friction reflected to the motor (unmeasured; typical for a 16 mm gearmotor), a rotor within ~±6–11° of 180° does not move.  Firmware then zeroes the count ~170–190° off, **roughly 3–6 % of starts**.  FOC with a ~180° error applies reversed torque, and the encoder tracks the wrong-way motion consistently.  The drive lurches backwards at the current limit until the observer comparison acts, "above a few thousand rpm".<br><br>**(b) The Z check is relative.**  "Store the count at the first Z; at each Z a mismatch … → correct" compares Z with Z.  It catches lost or extra counts, but never an alignment offset: the first Z simply records the wrong reference.<br><br>**(c) The power-up train is a standstill hazard.**  On a sensor re-power at standstill (a TPS22945 80 ms retry from a cable intermittent; the observer says "not turning", so no invalidation), the programmed absolute train is **added** to the valid running count, and nothing detects it until the next Z | [C §10] Kt 2.73 mN·m/A, 6 pole pairs, 28.5:1; [MT] §7.3 p.12–13 (50 ms silent, optional power-up absolute train, Fig. 8(2)); [N] U11/U12 ON = VIN | (1) **Two-step alignment**: inject at +90° electrical, then 0°, or sweep the vector through ≥ 1 electrical turn and back (SimpleFOC-style).  Check that the encoder moved in the expected direction by about the expected amount; otherwise retry or fall back to sensorless.  (2) **Calibrate Z's electrical offset once** (bring-up, stored in flash; the magnet-to-rotor relation is fixed).  At the first Z after any start, compare the aligned angle with the stored offset: > ~30° electrical means re-align or go sensorless.  Then Z becomes an absolute reference.  (3) Say that the power-up absolute train, if used, must be handled on a re-power, or recommend leaving it unprogrammed |

## Notes

| ID | Sev | Finding | Evidence / action |
|---|---|---|---|
| N-01 | NOTE | **§9 step 0: say where to measure the 0.10 V.**  A 2-wire reading at the supply terminals, or through the forcing probes, adds each probe's pad contact resistance.  At 10–50 mΩ per contact on a 1 mm pad, that is 20–100 mΩ in series with the 100 mΩ part.  A good R302 then reads 0.12–0.2 V, and a builder can reject a good board | Force through TP10 and the cap pad; read the voltage with a separate DMM **on R302's own two pads**.  Expect 0.099–0.101 V (1 % part) plus meter error; a short reads ≲ 5 mV |
| N-02 | NOTE | **The boot 6x-mode test assumes the drum is at rest.**  After an IWDG or NRST reset mid-match the drum may coast.  W_Vx then carries BEMF (up to ~VBAT/7.8) before and during the INH pulse, and the test reads as 6x mode, i.e. "refuse to arm".  The pulse itself is harmless in 3x mode (INL = 0 → Hi-Z) | Run the test only when all three W_Vx read ≈ 0 V before the pulse.  Otherwise defer it, and report "test deferred", not "failed" |
| N-03 | NOTE | **PC14 (DRV_OFF) is a backup-domain pin**: 2 MHz, ≤ 30 pF, not a current source ([STM] pin-table note 2).  The load is two DRVOFF inputs (~100 k internal pull-downs, 2 × 33 µA at 3.3 V), R50 (sunk when low, 0.33 mA < 3 mA) and TP8 with ~50–80 mm of trace, ≈ 15–25 pF.  That is inside the limits, but only if DRV_OFF is routed short between U1 and the two drive ICs | [STM] pin-definition table, footnote 2 ("PC13, PC14 and PC15 are supplied through the power switch … 3 mA … 2 MHz with a maximum load of 30 pF").  Action: layout note, "DRV_OFF trace short, no extra load; PC13–PC15 are 30 pF pins" |

## Independent re-verification (no finding)

* **Pinouts**: all 48 + EP pads of the DRV8323R RGZ match [DRV23] Table 6-4, with the RH column (MODE 29 and GAIN 32 as
  4-level pins; IDRIVE 30 and VDS 31 as 7-level pins; NC 46).  DRV8316CR pins 1–40 match [DRV16] Table 6-1 (NC 1/24; AGND
  2/26; PGND 12/15/18; nSCS 36; VREF/ILIM 37; SOA 40, SOB 39, SOC 38).  SN74LVC08A, SN74LVC3G17 DCU, 74LVC1G17 SOT-353,
  BAT54S, BAV99 and AP2112K SOT-23-5 are as netlisted; round 12 already checked the INA239, BQ76907, LM74502 and TPS22945.
* **Fast-trip polarity**: with BKP = 0 and BKCMPxP = 0, each comparator input is active low.  COMPx (POL = 0) goes low when
  SOx < DAC, which is the inverted CSA's over-current direction, so the §8 "no inversion anywhere" statement is right.  The
  VDS OCP turn-off uses the DRV8323's reduced gate current ([DRV23] §8.3.6.3.2).  That only slows the phase-to-ground
  residual in §7.21 (a lower kick rate), so nothing changes.
* **Supply behaviour during a bounce**: U2 trips its UVLO and re-wakes (nFAULT low for ~1 ms after).  The DRV8316s ride
  through 4.4–4.8 V (UVLO 4.1–4.3 V), and the buck and logic ride through on C29/C30 plus the compute board's 470 µF, because
  C10 holds nSHDN for 4.5 ms.  This is consistent with round 12 except for the detection gap in R13A-01.
* **Sims**: `hotplug.out` (worst 2.09 V/µs re-close, 0.8–2.26 V/µs bounce, 2.66 V/µs at −40 °C) and `arm.out` (52–164 ms
  disarm, 7–10 edges) reproduce exactly and match §1, §3.2, §5 and §7.2.

**Verdict: 0 BLOCKER, 0 MAJOR, 2 MINOR, 3 NOTE.**  The netlist, pin numbers, ratings and the R302/R402 bring-up physics are
correct, and no hardware change is needed.  Both MINORs are round-12 firmware-contract edits that are not yet technically
right:
* The supply-class fault detection keys on a filtered VBAT that misses sub-ms bounces.  Classify by nFAULT low time and
  DIAG_ALRT instead.
* The single-vector d-axis alignment has a 180° dead zone that the relative Z check cannot catch.  Use two-step alignment
  and a stored Z electrical offset.
