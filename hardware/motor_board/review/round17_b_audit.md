# Round 17 — B audit (consistency, rev L after round 16)

Auditor B.  I copied the package to `/tmp/r17b/`.  `design/motor_board.py` printed `237 refs (205 placed
components), 160 nets, 67 BOM lines` / `checks: OK`, and I reran `design/calcs.py`.  `diff -rq` of the
regenerated `netlist.csv`, `nets.md`, `bom.csv`, `mcu_pinmap.md` and `calcs.md` against the tree
shows no differences.

## Cross-file checks (clean)

* **BOM counts:** bom.csv has 67 lines and Σ Qty = 199.  The only netlist refs missing from the CSV are
  the 6 DNP parts (C110–C112, C114–C116) and the copper-only items (JP, J_*, NT, TP).  DESIGN §1,
  BOM.md and README all agree on 199 / 67 / 6 DNP.
* **BOM.md "Parts to watch":** all 28 LCSC numbers match bom.csv.
* **Designators:** every one named in DESIGN, README, BOM.md, calcs.md, spice/README and
  datasheets/README exists in the netlist.  (L2–L4 in DESIGN §6 are copper layers, and MH1–MH4 have
  no pins.)
* **MCU pins:** all 49 pins named in DESIGN match their nets and AFs in mcu_pinmap.md (e.g. PC13
  TIM1_BKIN, PB7 TIM8_BKIN, PC15 R_nFAULT, PB11 COMP6_INP, PC3 OPAMP5_VINP, PF0/PF1 ADC1/2_IN10).
* **DRV8316C pins against SLVSH07 Table 6-1:** INLA/B/C (28/30/32) are on +3V3, DRVOFF 21 and nFAULT 22
  are correct, and the 3x/6x truth tables (Tables 8-3/8-4) match the §8.1 "INH high → Hi-Z in 6x"
  claim.
* **SPI words:** I checked every DRV8316 word in DESIGN.md for even parity over all 16 bits (write
  frame = addr<<9 | P<<8 | data), and each one uses the correct register address (CTRL1 3h … CTRL10 Ch).
  All pass: 0x0603, 0x0606, 0x1019, 0x0A4E, 0x0C90, 0x0F00, 0x1818, 0x1915 (the rejected TI value),
  0x087C, 0x097D and 0x0D10.  The two odd-parity words in the text, 0x0D90 (line 684) and 0x0C10
  (line 685), are both cited as the *wrong* frames, which is correct.  CTRL1 unlock/lock = 011b/110b
  (Table 8-18).  CTRL2 bits 7–6 are reserved with reset value 01b, so the "bit 6 reads 1" test in
  drive row 3 holds.  0x1000 / 0x76C0 / 0x17C0 are INA239 values and carry no parity.
* **Row and step cross-references:** §8 fast-trip → row 6, stall cut-out → row 10, §9 step 6 → row 5,
  row 7 → §9 step 4, §7.16 → §9 step 2 and Z offset → §9 step 5 are all correct.  The one exception is
  in finding B17-02.

## Findings

### B17-01 — MAJOR — the restart resistance check (row 5) runs up to ~1 k rpm, where drum BEMF is larger than the I·R it measures

DESIGN.md:656: "every restart from standstill (**drum < ~1 k rpm**) first applies a short DC pulse
(~5 A, ~1 ms) to each phase pair; a V/I below ~half the value stored at bring-up → … latch the
weapon".  The weapon is a 2822 **1800 KV** class motor (DESIGN.md:31).

* **BEMF at the threshold:** at 1000 rpm the line-line BEMF is ≈ 1000/1800 ≈ 0.56 V.
* **Signal being measured:** a 2822 of this KV has a line-line R of roughly 0.05–0.1 Ω (not published),
  so 5 A gives only 0.25–0.5 V of I·R.
* **Time scale:** the electrical frequency is 7 pole pairs × 1000/60 ≈ 117 Hz, so BEMF swings through
  ~40° electrical during a 1 ms pulse.

The measured V/I can therefore be anywhere from roughly 0 to 2× the true resistance, depending on
rotor phase.  Even at ~300 rpm the error is ±0.03 Ω, which is 30–60 % of R.

**Effect:** a healthy motor fails the check and the weapon latches whenever a restart happens with the
drum turning slowly.  This contradicts row 10, which says a jammed drum "never latches — a drum jammed
by an opponent retries" (DESIGN.md:661).  Situations where it happens:

* a row 10 retry while an opponent is still pushing or releasing the drum;
* a re-arm during the long free coast-down (§9 step 6 measures it);
* a row 6 restart after the drum has slowed.

**Fix (text only):**

* Run the check only when the drum is actually stopped: measured line-line BEMF below ~10 % of
  I × R_stored, i.e. well under ~100 rpm.  If it is still turning, wait for it (a phase-to-phase short
  brakes a slow drum to a stop by itself) or skip the check and rely on rows 4/8.
* Alternatively, measure ±I pulses back-to-back and average them.  This only works where BEMF is
  quasi-constant over the pair, so again at very low speed.
* State in the row which speed estimate gates the check (W_Vx catch-spin amplitude).

### B17-02 — MINOR — §8 weapon-safety row still sends polled TH1 > ~100 °C to row 9

DESIGN.md:617: "TH1 > ~100 °C → coast until < ~80 °C (**row 9**)".  Round 16 (B16-07) moved polled
TH1 > ~100 °C to **row 10** (DESIGN.md:661, "or TH1 > ~100 °C (polled; no break involved)").  Row 9
(DESIGN.md:660) is the W_nFAULT-stuck-low row (U2 OTSD at TH1 > ~90 °C / GDF).  The reference is
stale: change it to "row 10".

### B17-03 — MINOR — INA239 row still describes the round-15 switch-open detection

DESIGN.md:619: "the switch-open detection (≈ 0 A **with the drum driven**; §8.1 row 0)".  Row 0 is now
a continuous monitor, "|I| < ~30 mA … VBUS > ~8 V for ≥ ~100 ms, **whether or not the drum is
driven**; suspended during commanded regen" (DESIGN.md:651).  Change it to "(|I| < ~30 mA for
≥ ~100 ms; §8.1 row 0)".

### B17-04 — MINOR — per-drive coast paragraph calls 0x0D10 "the boot value"

DESIGN.md:684–685: "leave with CTRL4 **0x0D10** (**the boot value**; 0x0C10 has odd parity…)".  After
round 16 the boot and rewrite sequence writes **0x0C90** (DESIGN.md:611: "CTRL4 0x0C90 … the chip stays
coasted").  0x0D10 is now the separate **Release** step (DESIGN.md:611: "CTRL1 0x0603 → CTRL4 0x0D10 →
CTRL1 0x0606").  A reader who reads "boot value" literally would write 0x0D10 at boot, which is exactly
what B16-03 removed.  Change it to "leave with the §8 Release sequence (CTRL4 0x0D10)".

### B17-05 — MINOR — the rewrite reuses a sequence whose precondition is "DRV_OFF high", but a per-drive rewrite runs with DRV_OFF low

* DESIGN.md:611: "After t_READY (1 ms), **with DRV_OFF high**: CTRL1 0x0603 → … The same sequence is
  the §8.1 'rewrite' after an NPOR or mismatch".
* Drive row 2 (DESIGN.md:677) performs that rewrite for a *single* chip while the other drive keeps
  running, so the shared DRV_OFF pin is low.

As written, a literal implementation raises the shared pin and coasts the healthy drive.  That is
benign but contradicts the per-drive design.  The ordering is otherwise safe: row 2 runs the per-drive
coast (CTRL4 0x0C90) before the rewrite.

**Fix:** "with DRV_OFF high at boot, or after the per-drive coast (§8.1) for a single-chip rewrite".

### B17-06 — MINOR — §3.5 forbids flash *programming* while armed; §8.1 has the compute board program its latch copy, excluding only erase

* DESIGN.md:345–346 (§3.5 item 4): "**No flash erase/program** on the compute board while armed (an
  RP2040 sector erase stalls XIP code for up to 400 ms)".
* DESIGN.md:644–645 (§8.1 latch word): "it persists the copy with a program-only write to a pre-erased
  flash slot — **never an erase while armed**".

A weapon latch normally arises while armed, so the reader cannot tell whether the copy may be written
at once or must wait for the disarm.  An RP2040 page program also takes the flash out of XIP, but only
for ≲ 1 ms, which is inside the W_ARM_CLK gap budget if the toggle ISR runs from RAM.

**Fix:** either §3.5 allows "one ≤ 256 B page program (ISR in RAM)" or §8.1 says "after the disarm that
the latch forces".

### B17-07 — MINOR — the §8 boot order has no USART1 / first heartbeat, but §3.5 requires one before device configuration

* DESIGN.md:367 (§3.5): "the motor MCU sends its first heartbeat **right after clocks and USART1,
  before the device configuration**".  The compute board allows ~50 ms after NRST release before it
  counts a failed reset.
* The §8 boot order (DESIGN.md:592–596) never mentions USART1 or the heartbeat:
  "IWDG → UCPD → clocks → DBGMCU → GPIO → SPI3 → configure U3/U4 … → W_EN → offsets → strap boot test
  → …".

This is a contract between the two boards and is currently stated on one side only.  Insert
"→ USART1 + first heartbeat" after "clocks" in the §8 boot order.

### B17-08 — MINOR — §9 step 2 expects nFAULT high after a sequence that now leaves the chips coasted

* DESIGN.md:724–725 (§9 step 2): "Write the DRV8316 sequence to U3, then U4; read back status (check
  BUCK_UV/NPOR clear after CLR_FLT **and that L_nFAULT/R_nFAULT are high**)".
* Since round 16 the sequence ends with CTRL4 bit 7 = 1 (DESIGN.md:611), and at step 2 the DRV_OFF pin
  is also still high.
* SLVSH07 §8.4.2 (p.53): "Since DRVOFF pin independently disables MOSFET, it can trigger fault
  condition resulting in nFAULT getting pulled low".  §8.1 itself says whether the bit does the same
  is unknown and must be bench-verified (DESIGN.md:686–687).

The step 2 pass criterion can therefore fail on a good board.  Reword it: "nFAULT high after the §8
Release with DRV_OFF low, or record its state while coasted (§8.1)".

### B17-09 — MINOR — a latched *left* drive may not keep "INH high" on its idle outputs: the TIM8 break (L_nFAULT) forces them low

* Drive row 2 (DESIGN.md:677): a latched drive "stays coasted … hold its INH outputs high, so a chip
  that resets into 6x mode is still Hi-Z".
* L_nFAULT is TIM8_BKIN (DESIGN.md:216, PB7), and "a timer break forces the low sides on" (DESIGN.md:214:
  OISx = 0 → INH low).
* If the coasted chip pulls nFAULT low (B17-08; unverified), the TIM8 break holds MOE = 0 and INH sits
  at the idle level, low.
* If that chip then resets (NPOR → 6x mode, CTRL4 bit cleared), INH = 0 / INL = 1 gives "L" (SLVSH07
  Table 8-3): the low sides turn on, and the latched left drive brakes instead of floating.

This does not affect the right drive (TIM20 has no break input), and the failure is braking, not
driving.

**Fix:** state how the high INH is held on a latched drive regardless of MOE: TIM8 OIS1–3 = 1 for that
drive, or the pins switched to GPIO output high.

## Notes

* **N1 — which vector starts the row-4 window?**  Row 4 measures "≤ ~200 µs after the first applied
  vector of a restart" (DESIGN.md:655), and row 5 prepends ~3 ms of DC pulses to every restart from
  standstill.  It should say whether the DC pulse or the first FOC vector starts that window.  If it
  is the DC pulse, row 4 can never fire from standstill (row 5 covers that).  If it is the FOC vector,
  a locked rotor with the raised §9 step 4 limit could latch through row 4, while §9 step 6 expects
  "row 6 cool-down, no latch" (DESIGN.md:763–764).
* **N2 — the SPI-health poll reads DIAG_ALRT every ~10 ms** (DESIGN.md:689).  With ALATCH = 1 a read
  clears the latched SOVL/BOVL flags and releases ALERT.  The same owner task classifies, so any flag
  a poll sees must go to the classifier rather than being dropped.  Worth one clause.
* **N3 — row 0 excludes only *commanded* regen** (DESIGN.md:651).  A robot pushed backwards while its
  drives hold zero speed regenerates without a regen command.  If the net pack current sits inside
  ±30 mA for ≥ 100 ms, the result is a switch-open hold until the operator clears it.  This is
  unlikely because the idle draw is ~100 mA; consider "no regen, commanded or measured (I < 0), within
  the window".
* **N4 — status:** round-16 items B16-01…08 and R16A/R16D are applied as CHANGES.md describes, apart
  from the stale remnants listed above.

## Counts

BLOCKER 0 · MAJOR 1 · MINOR 8 · NOTE 4
