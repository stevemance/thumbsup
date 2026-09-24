# Trim B — DESIGN.md §8.1 drive policy

Scope: the §8.1 "Drive events" intro and "drives resume" steps 1–4 (incl. the 24 A fallback),
"One event, one count", the drive-event table rows 1–7 (incl. 6/6a), "Per-drive coast" and
"SPI health".  The current text is ~1850 words.  The replacement below is ~1050 words (about 55 %), with the table kept.

Datasheet checks (SLVSH07 = DRV8316C, SBOSA20 = INA239, MT6701, STM32G474 DS):

- **SPI frame** (SLVSH07 §8.5.1.1, Table 8-9): B15 W0 (1 = read), B14–B9 address, B8 parity
  (the 16-bit word must have an even number of 1s), B7–B0 data.  SDO is 8 status bits + 8 data
  bits with **no parity**, and SDO is Hi-Z while nSCS is high (§8.5.1).
- **Words**, recomputed from address and data (the number of 1s is shown after each word):
  CTRL1 (3h) unlock 0x0603 (4) and lock 0x0606 (4); CTRL2 (4h) 0x087C (6) and with CLR_FLT
  0x097D (8); CTRL4 (6h) coast 0x0C90 (4), release 0x0D10 (4), coast at 24 A 0x0D94 (6),
  release at 24 A 0x0C14 (4).  0x0C10 has odd parity, so the chip would reject it.
- **CTRL4 bit 7 DRV_OFF**: "1h = Hi-Z FETs" (Table 8-21).  It is described only in the register
  map, so its behaviour must be checked on the bench.  CTRL4 0x10 means OCP_DEG 0.6 µs,
  OCP_LVL 16 A, OCP_MODE latched.  I_OCP is 10/16/22 A min/typ/max at 16 A and 15/24/30 A at
  24 A (§7.5).
- **Register lock** (Table 8-18): 110b makes the chip ignore every write except to CTRL1
  bits 2–0.  A locked chip therefore ignores CLR_FLT, so every CLR_FLT must be wrapped in an
  unlock/lock pair.
- **VM UVLO**: 4.1–4.3 V falling (§7.5).  A VM or AVDD UVLO gives no report on nFAULT and
  disables the logic (Table 8-8, §8.3.14.1–2).  The registers return to their reset values on
  power-up (§8.5.1): CTRL2 0x60 = 6x mode (Table 8-19) and CTRL4 0x10 = not Hi-Z.  NPOR latches
  low until CLR_FLT.
- **6x truth table** (Table 8-3): INL = 1 with INH = 0 turns the low side on; INL = 1 with
  INH = 1 is Hi-Z.  **3x truth table** (Table 8-4): INL = 1 with INH = 1 turns the high side on.
  INL is tied high on this board, so:
  - INH idling high (a timer at MOE = 0 with OISx = 1) brakes a 3x-mode chip on all three high
    sides, but leaves a 6x-mode chip Hi-Z;
  - INH floating reads low through the internal ~100 kΩ pull-down (§7.5, RPD), which turns a
    6x-mode chip's low sides on.
- **DRVOFF pin** (§8.4.2): with the pin high the FETs are off, SPI is active, OCP is inactive,
  and the pin "can trigger fault condition resulting in nFAULT getting pulled low".
- **PWM_MODE** (§8.3.2 note): TI says not to change PWM_MODE while the FETs operate.  INL is
  tied high, so the rewrite must Hi-Z the chip through CTRL4 before it writes CTRL2.  The §8
  sequence already does this: CTRL4 0x0C90 comes before CTRL2 0x087C.
- **Chip-side facts**: nSCS has an internal pull-up of 80–130 kΩ (§7.5).  CTRL2 bits 7–6
  reset to 01b, so bit 6 reads 1 on a live chip.  OCP, CP-UV, OVP and OTSD all Hi-Z the bridge
  and pull nFAULT low (Table 8-8).  OVP, CP-UV and OTSD recover automatically; OCP is latched
  with OCP_MODE = 00b.  t_READY is 1 ms.  The CSA idles at VREF/2 (§8.3.11), and VREF is AVDD on
  this board.
- **INA239**: DEVICE_ID reads 2391h (§7.6.1.17).  With ALATCH = 1, reading DIAG_ALRT clears the
  alert flags (Table 7-13).
- **STM32G474**: TIM8_BKIN is on PB7 (AF, DS pin table).  TIM20_BKIN is only on PF7 and PF9,
  which LQFP-64 does not have, so R_nFAULT has no hardware break.  BKINE, OISx, OSSI and LOCK
  are RM0440 fields (the reference manual is not in datasheets/); they are carried over from
  round 22–23 reviewer checks.
- **MT6701**: ABZ output is incremental with no status line; rated to 55 k rpm.

## 1. Rule-by-rule disposition

| # | Current rule | Verdict | Reason |
|---|---|---|---|
| 1 | Event sources: R/L_nFAULT, ~100 Hz register check, NPOR/CP-UV; first match wins | KEEP | Defines the inputs |
| 2 | nFAULT while the pin is high, during a resume, or from a commanded coast is not an event (SLVSH07 §8.4.2) | KEEP | Datasheet fact.  Without it, every pin toggle would look like a fault |
| 3 | Drives resume is the one procedure for every pin-low and every un-coast; it never passes through a brake (12–31 A at speed against 10–22 A OCP) | KEEP | This is the core safety property.  The numbers are cut to one clause |
| 4 | Step 1: read NPOR and registers first; a silently reset chip gets the rewrite; make sure every chip being resumed is coasted; leave running drives alone | KEEP, SIMPLIFY | Silent VM-UVLO reset into 6x mode is a real bounce case.  The counting cross-reference moves to "one event, one count" |
| 5 | Step 2: lower the pin only if some drive is unlatched | KEEP | One clause |
| 6 | Step 2: fold CLR_FLT into the Release only if the §9 bench check shows a pin-raised nFAULT stays latched | SIMPLIFY | CLR_FLT is now always part of the Release (after the CTRL4 word).  It is harmless: a real fault re-latches within the 0.6 µs deglitch.  This removes a branch that depended on a bench result |
| 7 | Step 2: angle source, encoder valid → back-EMF preset V_q = ω·λ with latency compensation | KEEP, SIMPLIFY | Essential: no current step at release.  The derivation is cut |
| 8 | Step 2: encoder counting but angle invalid → take the angle from the next Z and the stored offset (not stale, not suspect, only once stored) | KEEP, SIMPLIFY | Realistic case (an MCU reset mid-match while moving).  Condensed to "a trusted stored Z offset" |
| 9 | Step 2: encoder still → preset 0, align after step 4 | KEEP | Needed: a coasted chip cannot push alignment current |
| 10 | Step 2: an OCP at a zero preset marks the encoder suspect; "encoder suspect or phase short" reporting after coast-down | SIMPLIFY | Merged into one rule: any resume that fails on an encoder-derived preset marks the encoder suspect.  This also covers R30D-02 (a slipped magnet gives a wrong Z preset) |
| 11 | Step 2: no usable encoder → coast for the measured coast-down time, then preset 0; OCP retried every ~0.5 s, never latched; restore BKINE/MOE between retries | KEEP, SIMPLIFY | A pushed robot can exceed the safe-resume speed, so a latch here would lose the match.  Each attempt costs at most one OCP trip.  A 2 Hz reported retry is bounded, not a restart storm |
| 12 | Step 2: TIM8_AF1 BKINE = 0 (BKE stays 1 for CLL; LOCK = 0), clear the break flag, set MOE | KEEP | Hardware fact: a coasted chip may hold L_nFAULT low, and the TIM8 break would then block MOE |
| 13 | Step 2: BKINE window "a few ms, ≤ ~12 ms with step 4's one repeat — not a hard 10 ms timeout" | CUT | Timing trivia.  It follows from the ~5 ms nFAULT wait |
| 14 | Step 2: 24 A OCP fallback for the resume window (0x0D94 / 0x0C14, ≤ 50 ms, register check expects 0x94/0x14) | CUT → one sentence | Speculative until the §9 top-speed resume test fails.  The two parity-checked words are kept in a parenthesis so nobody has to re-derive them |
| 15 | Step 3: Release words, including the optional CLR_FLT and the 24 A variant | SIMPLIFY | One fixed sequence: 0x0603 → 0x0D10 → 0x097D → 0x0606 |
| 16 | Step 4: wait ≤ ~5 ms for nFAULT high; then BKINE = 1 | KEEP | |
| 17 | Step 4: if nFAULT stays low, re-coast and recover in one unlocked sequence, repeat once from (2), otherwise classify through the table; a resume OCP always goes to the resume count | SIMPLIFY | Now: re-coast (one unlocked sequence), MOE = 0, BKINE = 1, and handle it as a failed resume (rule 10/11).  The one-time repeat and the reclassification are cut |
| 18 | Resume OCPs counted on their own; with a valid encoder > ~3/s latches the drive; never toward row 1 or the supply budget | SIMPLIFY | The first failure on an encoder preset demotes the drive to the no-encoder branch, so a wrong angle can no longer latch it (R30D-02).  Keep "never toward row 1 or the supply budget" |
| 19 | A latched drive stays coasted | KEEP | |
| 20 | One event, one count: a bus event matching weapon row 2 and drive row 1 is counted once; weapon row 1's defer-to-row-0 also governs the drives | KEEP, SIMPLIFY | Prevents double-counting into the supply budget.  Row 2's "while a supply restart is pending" rule moves here |
| 21 | Row 1 supply: both chips, a bus event within ~1 ms, or a DRV8316 OVP within ~1 ms of BOVL → pin high, resume after 20 ms steady | KEEP | Realistic (contact bounce).  Wording shortened |
| 22 | Row 2 single chip (OCP, mismatch, NPOR, CP-UV) → per-drive coast, recover, rewrite, resume; > ~3/s → latch that drive | KEEP | Essential: one chip's fault must not take out the other drive; the restart count is bounded |
| 23 | Row 2: latched drive keeps INH high, OISx = 1 with OSSI = 1 so a break or reset leaves it Hi-Z in 6x mode; boot releases only unlatched drives; rewrite only for an already latched chip | KEEP, SIMPLIFY | Hardware facts (6x/3x truth tables, INH pull-down).  One sentence |
| 24 | Row 2: "while a supply restart is pending, leave it to drives resume" | MOVE | To "one event, one count" |
| 25 | Row 3 unpowered: CTRL2 reads 0x00, nFAULT low and all CSAs < 0.3 V → latch that drive; the other drive continues | KEEP | Realistic (R302/R402 fused open).  Satisfies "a dead chip doesn't take out the healthy drive" |
| 26 | Row 4 powered but deaf: ≥ 3 consecutive bad reads while the other devices answer → pin high, latch both, weapon unaffected | KEEP | Hardware fact: the nSCS pull-up deselects a chip on an open CS, and the chip then follows its timer unverified.  The only way to Hi-Z it is the shared pin |
| 27 | Row 5 OTW/OTSD → derate or coast until cooled | KEEP | OTSD recovers automatically, so the chip must be coasted first (covered by the new general rule) |
| 28 | Row 6: ordered sub-rules (a)(b)(c) with numeric motion windows and ≤ ~5 repeats | SIMPLIFY | Kept as three one-line outcomes.  The fine-grained order stays, because (a) must be checked before (c) |
| 29 | Row 6a: wrong sign on two consecutive clean alignments → latch (wiring) | KEEP | Never run a drive backwards |
| 30 | Row 7: left/right crossed → latch both until operator clear and re-alignment | KEEP | Never run a drive backwards (crossed motor bundles) |
| 31 | Per-drive coast: CTRL4 0x0C90 wrapped in unlock/lock; exit only through resume with 0x0D10; register check expects 0x90 while coasted | KEEP | Verified words |
| 32 | Per-drive coast: no PWM_MODE change while the FETs operate | KEEP, SIMPLIFY | TI note.  Reworded as the reason the rewrite writes CTRL4 before CTRL2 |
| 33 | Per-drive coast: bench-verify Hi-Z at speed, nFAULT behaviour, re-drive after 0x0D10 | KEEP | The bit is documented only in the register map |
| 34 | Per-drive coast: never write CTRL2 bit 6 as 0 | KEEP | Row 3 depends on it |
| 35 | (new, implicit before) On any nFAULT or register event from a released chip, coast it over SPI first | ADD (makes explicit) | OVP, CP-UV and OTSD recover by themselves.  On the left drive the TIM8 break has already set INH high, so the recovered 3x-mode chip would brake at speed |
| 36 | SPI health: each DIAG_ALRT read feeds the classifier; the poll compares config bits only | KEEP | ALATCH read-clear fact |
| 37 | SPI health: INA239 DEVICE_ID plus config read-back every poll; rewrite on mismatch | KEEP | A reset INA239 silently loses SOVL/BOVL |
| 38 | SPI health: firmware computes DRV8316 parity | KEEP | |
| 39 | SPI health: two or more devices failing → SPI3 fault: pin high, weapon coast, retry ~100 ms as a hold | KEEP | |
| 40 | SPI health: INA239 alone failing on ≥ 3 polls (a one-rewrite fix is only reported) or the row 0 cross-check/plausibility → weapon off until operator clear, drives on VBAT_SNS, re-enters at once while still failing | KEEP, SIMPLIFY | Shortened.  The row 0 tests themselves are outside this scope |

## 2. Proposed replacement text

The block below replaces everything from `**Drive events** (R_nFAULT/L_nFAULT, …` through the end of
the `**SPI health:**` paragraph, i.e. the current lines ~674–701.  Row numbers 1–7 and 6a are
unchanged, so the cross-references from §8's timer-inputs row still resolve.

```markdown
**Drive events** (R_nFAULT/L_nFAULT, the ~100 Hz register check incl. NPOR; first match wins).
An nFAULT while the DRV_OFF pin is high, inside a "drives resume", or on a firmware-coasted chip
is expected, not an event (the DRVOFF pin may pull nFAULT low, SLVSH07 §8.4.2).  **On any event
from a released chip, first coast it over SPI:** OVP, CP-UV and OTSD self-clear, and a chip that
recovers with INH idling high (MOE = 0, e.g. the TIM8 break on L_nFAULT) brakes on all three high
sides.

| # | Evidence | Action |
|---|---|---|
| 1 | Both DRV8316s at once; or a bus event (weapon row 2), or a DRV8316 OVP with an INA239 BOVL, within ~1 ms | **Supply** → DRV_OFF pin high; "drives resume" after VBUS is steady ≥ 20 ms (supply budget) |
| 2 | One chip answering: OCP, CP-UV, register mismatch, NPOR = 0 | Per-drive coast → fault recovery → rewrite (ends coasted) → "drives resume"; > ~3 in 1 s → **latch that drive** |
| 3 | One chip not answering (CTRL2 reads 0x00; bit 6 reads 1 on a live chip) with its nFAULT low **and** all its CSAs < ~0.3 V (powered, they idle at AVDD/2) | **Unpowered** (R302/R402 open) → latch that drive, ignore its nFAULT; the other drive continues |
| 4 | One chip silent or garbled otherwise, on ≥ 3 consecutive polls while the other devices answer (DRV8316 read-back has no parity) | **Powered but deaf** (open/stuck nCS; its pull-up deselects it and it follows its timer unverified; only the shared pin can Hi-Z it) → DRV_OFF pin high, **latch both drives**, report; weapon continues |
| 5 | OTW (polled) / OTSD | Derate on OTW; coast until cooled on OTSD; not a latch |
| 6 | Alignment not clean: (a) own encoder still while the other follows both steps on two consecutive alignments → row 7; (b) too little own motion → retry at higher current, then sensorless; (c) any other disturbance → repeat ≤ ~5 times, then sensorless | Report; not counted |
| 6a | Alignment sign wrong on two consecutive clean alignments | **Latch that drive** (phase or encoder wiring swapped) |
| 7 | Row 6 (a): left/right crossed (sensor cables or motor bundles) | **Latch both drives** until an operator clear and a clean re-alignment (latch word) |

A **latched drive** stays coasted across MCU resets (boot releases only unlatched drives); the
register check rewrites it on a mismatch.  Its timer sits at MOE = 0 with OISx = 1 **and
OSSI = 1**, so INH idles high: a chip that resets into 6x mode is then Hi-Z (INL = INH = 1),
whereas floating INH pins read low through the pull-downs and turn a 6x chip's low sides on.

**One event, one count:** a bus event matching weapon row 2 and drive row 1 counts once; a
row 2 event while a supply restart is pending is left to that restart; when weapon row 1 defers to
row 0, so do the drives.

**Per-drive coast** (the only per-chip Hi-Z; INL is tied high and the DRVOFF pin is shared):
CTRL1 0x0603 → CTRL4 **0x0C90** (bit 7 DRV_OFF, "Hi-Z FETs", Table 8-21) → CTRL1 0x0606.  The
register check expects CTRL4 0x90 coasted, 0x10 released.  Leave it only through "drives resume".
The rewrite writes CTRL4 before CTRL2 because TI forbids a PWM_MODE change while the FETs operate.
Never write CTRL2 bit 6 as 0.  Bench-verify (§9 step 2) Hi-Z at speed, the nFAULT behaviour, and
normal drive after the Release.

**Drives resume** — used every time the DRV_OFF pin goes low and to un-coast a chip.  A chip
leaves Hi-Z only when its timer already drives the motor's back-EMF voltage; never through
MOE = 0, which in 3x mode is a high-side brake (12–31 A at top speed vs the 10–22 A OCP).
1. Read IC_STAT and registers of each unlatched chip to be resumed; rewrite a silently reset one
   (a VM UVLO at 4.1–4.3 V gives no nFAULT and comes back in 6x mode); make sure each is coasted.
   Running drives are left alone.
2. Lower the pin.  Preset: encoder angle valid → V_q = ω·λ, V_d = 0 (λ from §9 step 5, PWM and
   MT6701 latency compensated); encoder counting but angle unknown → next Z with the stored Z
   offset, if stored and trusted; encoder not counting → 0 (align after step 4); no usable
   encoder → stay coasted for the measured coast-down time (§9 step 6), then 0.  Set TIM8_AF1
   BKINE = 0 (a coasted chip may hold L_nFAULT low; BKE stays 1 for the CLL break; BDTR LOCK = 0),
   clear the break flag, set MOE, run FOC with the preset at zero current demand.
3. Release: CTRL1 0x0603 → CTRL4 **0x0D10** → CTRL2 0x097D (CLR_FLT) → CTRL1 0x0606.
4. nFAULT high within ~5 ms → BKINE = 1 (TIM20 has no break pin).  Otherwise re-coast
   (0x0603 → 0x0C90 → 0x097D → 0x0606), MOE = 0, BKINE = 1: a **failed resume**.  With an
   encoder-derived preset (a cut ABZ cable reads as standstill), mark the encoder suspect and retry
   through the no-encoder branch; no-encoder retries repeat every ~0.5 s, reported, never latched
   (each costs one self-limited OCP trip).  Failed resumes never count toward rows 1–2 or the
   supply budget.  If §9's top-speed resume test trips OCP, fix it then (resume speed cap, or
   OCP_LVL 24 A: coast 0x0D94 / release 0x0C14).

**SPI health:** every DIAG_ALRT read feeds the weapon classifier (it clears SOVL/BOVL with
ALATCH = 1); the poll compares only configuration bits.  Each poll reads the INA239 DEVICE_ID
(2391h) and reads back CONFIG, ADC_CONFIG, SHUNT_CAL, SOVL, BOVL and DIAG_ALRT settings (a reset
INA239 silently loses SOVL/BOVL: rewrite).  Firmware computes each DRV8316 parity bit (even
parity over the 16-bit word).  Two or three devices failing in one poll → **SPI3 fault**: DRV_OFF
pin high, weapon coast, report, retry every ~100 ms.  The INA239 alone failing (≥ 3 consecutive
polls — a mismatch one rewrite fixes is only reported — or the row 0 cross-check/plausibility) →
weapon off until an operator clear (latch word; a still-failing INA239 re-enters at once); the
drives continue on VBAT_SNS.
```

## 3. Knock-on edits outside this scope (for whoever applies it)

- **§8 DRV8316C row, "Release"**: change it to `CTRL1 0x0603 → CTRL4 0x0D10 → CTRL2 0x097D →
  CTRL1 0x0606` so it matches step 3.  Drop "one repeat" and the "fold one CLR_FLT" wording
  wherever it appears (§8 boot-order sentence).
- **§8 timer-inputs row**: "§8.1 drive rows 6/6a" still resolves.  Its "§8.1 drives resume" Z
  reference still matches step 2.
- **§9 step 2**: the "record whether nFAULT stays low after lowering the pin" check becomes
  informational only (CLR_FLT is now always in the Release).
- **§9 step 6**: "OCP inside a resume window > ~3/s → latch" expectations, if any, change to
  "encoder marked suspect, no-encoder retries, reported".
