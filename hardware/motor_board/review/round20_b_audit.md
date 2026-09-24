# Round 20 — B audit (consistency, rev L after round 19)

Scope: the whole package, with most weight on DESIGN.md §8 / §8.1 / §9 after the round-19 edits.
Board area and fit, and prose style, are out of scope.  Items settled in review/CHANGES.md rounds 1–19
are not raised again unless they are actually wrong.  Line numbers refer to the tree as audited;
the /tmp/r20b copy is identical.

## Reproduction

* Copied the package to /tmp/r20b.  `design/motor_board.py` prints `237 refs (205 placed components),
  160 nets, 67 BOM lines` / `checks: OK`.  `design/calcs.py` ran clean.
* `diff -rq /tmp/r20b <tree>` after both runs: no differences.  netlist.csv, nets.md, bom.csv,
  mcu_pinmap.md and calcs.md are all current.
* bom.csv: 67 lines, Qty sum 199.  205 placed − 6 DNP (C110–C112, C114–C116) = 199.  This matches
  BOM.md:4–5, README.md:7 and DESIGN.md:37.
* Every LCSC number in DESIGN.md and datasheets/README.md appears in bom.csv.  The LCSC numbers in
  BOM.md that are not in bom.csv are all named alternates: C1235414, C529413, C157991, C18213,
  C2150467, C2846803, C53055322 and C6053.
* DRV8316 SPI words were recomputed.  Format: B15 = W, B14:9 = address, B8 = parity, B7:0 = data,
  even parity over all 16 bits.
  * All pass: 0x0603, 0x0606, 0x087C, 0x097D, 0x0A4E, 0x0C90, 0x0D10, 0x0F00, 0x1019, 0x1818,
    0x1915.
  * The two words the text names as wrong really do have odd parity: 0x0D90 and 0x0C10
    (DESIGN.md:686–687).
  * Addresses: CTRL1 = 0x03, CTRL2 = 0x04, CTRL3 = 0x05, CTRL4 = 0x06, CTRL5 = 0x07, CTRL6 = 0x08,
    CTRL10 = 0x0C.
  * Expected read-backs match the data bytes, with CTRL4 0x10 released and 0x90 coasted.
* Checked against the pin map:
  * the PB7 = L_nFAULT / TIM8_BKIN, PC15 = R_nFAULT, PC14 = DRV_OFF and PC13 = TIM1_BKIN
    references in §3.3, §8 and §8.1;
  * TIM8 (PB6/PC7/PB9) and TIM20 (PB2/PC2/PC8) as INH.
* Checked against the source files:
  * arm.out (7–10 edges; 12 ms at 500 Hz; 52–164 ms disarm) against DESIGN.md §5, §3.2 and §9
    step 3;
  * spice/README.md file list against spice/.
* Every internal § reference in DESIGN.md resolves.  §8.4, §9.2 and §11.1 point into TI datasheets,
  and calcs §10/§11 point into calcs.md.

## Findings

| # | Class | Where | Finding | Fix |
|---|---|---|---|---|
| B20-01 | **MAJOR** | DESIGN.md:652 (row 0 plausibility clause) vs :519–522 (§7.5), :652 (row 0 "a coasting drum holds the bus up for seconds"), :694, :734 | **The round-19 plausibility clause turns "switch opened while driving with the drum spinning" into an INA239 failure, and the drives keep running.**<br>• The gate reads "≈ 0 A with a steady bus … while the drives/weapon draw ≥ ~1 A by firmware's estimate (a steady bus under load proves the pack path) … → the INA239-failure path, not this hold".<br>• A steady bus under a *drive* load does not prove the pack path.  The same sentence says "only a spinning drum can hold the bus up".  §7.5 says the coasting drum keeps the board powered through body-diode rectification down to ~19 k rpm.<br>• Scenario: the switch opens mid-match (knocked, or the UVLO opens) or is switched off while the operator is still driving.  The drum is coasting and the drives are motoring at ≥ ~1 A (R19D-N2 gives 10–43 W of drive power).<br>• Result: the drives are fed by the drum's kinetic energy.  At ~30 W out of ~64 J (§7.4) VBUS falls only ~2 % (~0.3 V) in 100 ms, so it reads "steady".  The bus sits at the drum's rectified BEMF, so the third clause does not fire, but the second one does.<br>• Row 0 therefore never declares switch-open.  The INA239-failure path runs instead: "weapon off, drives continue on VBAT_SNS" (:694).  The ~200 ms cross-check points the same way.<br>• The robot keeps driving under operator command for ~0.7–2 s, until the drum falls to ~19 k rpm and the logic browns out.  The event is reported as a failed INA239.<br>• This contradicts §7.5 ("Firmware detects it … and stops the drives") and the row 0 action.  §9 step 3 (:734) tests the switch-open case only with the drives idle, so the bench would not catch it.<br>• Cause: R19A N-01's premise ("a motoring load ≥ 1 A collapses the open bus") holds only when no coasting drum feeds the bus.  R19D-02 asked for "weapon stopped **or driven (positive power)**".  The text added drive load, which neither review proposed. | Restrict clause 2 to the **weapon** motoring (positive weapon power ≥ ~1 A).  Drive load alone counts only when the drum is stopped (clause 1) or the bus sits clearly above the drum's rectified BEMF (clause 3).  Apply the same exclusion to the ~200 ms cross-check (drum spinning and VBUS ≈ its rectified BEMF → not an INA239 failure).  Add to §9 step 3: "open the switch while driving with the drum spinning → switch-open hold, drives off". |
| B20-02 | MINOR | DESIGN.md:673 ("wait for nFAULT high (≤ ~5 ms, else drive row 2)") vs :673 "first match wins", :678–681 | **The drives-resume timeout jumps straight to drive row 2 and skips the first-match table.**<br>• Row 2's evidence is "one chip answering on SPI: OCP, mismatch, NPOR, CP-UV".  An nFAULT still low 5 ms after the pin goes low can have other causes.<br>• (a) A chip that went deaf (open or stuck nCS) while the pin was high can take neither the recovery nor CLR_FLT, so its nFAULT stays low.  Row 2 then does per-drive coast, rewrite and release, all ignored, and after > 3 cycles latches that one drive and "holds its INH high".  In 3x mode that brakes the deaf side while the other drive runs.  Row 4 exists to prevent exactly this ("it cannot be coasted alone: DRV_OFF high, latch both").  Row 4's 3-poll confirmation (~30 ms) can lose the race against 4 × (5 ms resume + rewrite).<br>• (b) A chip in OTSD during a supply-restart resume loops through row 2 and gets latched, and the latch persists across resets.  Row 5 says OTSD is "not a latch".<br>• (c) An unpowered chip (row 3) ends latched either way, but with the wrong reason. | "else classify it through the drive table (first match: row 2 if it answers with a fault, rows 3/4 if it does not answer, row 5 on OTSD)". |
| B20-03 | MINOR | DESIGN.md:597 (§8 boot order) vs :606 (watchdog row), :673 (drives resume "boot" listed); §9 step 2 :727 | **The boot order still bypasses the round-19 drives-resume procedure.**<br>• :597 reads "release the DRV_OFF pin and write the per-chip Release … then clear the TIM8/TIM20 break flags and set MOE".  It has no ~1 ms nFAULT check, no fault recovery and no wait for nFAULT high.<br>• The boot sequence is where a firmware writer reads the order, and following it literally reproduces B19-01 at boot: BKIN is level-sensitive, so BIF cannot be cleared and MOE cannot be set while L_nFAULT is low.  The left drive would then stay braked.<br>• This contradicts :606 ("TIM8/TIM20 only through the 'drives resume' step") and :673, which lists boot as a user of the procedure.<br>• Related: §9 step 2 expects nFAULT high "after the Release write with the DRV_OFF pin low".  The procedure checks it after the resume, which can include a fault recovery. | :597 → "… write the per-chip Release when the drives are commanded, then the §8.1 **drives resume** (it clears the TIM8/TIM20 break flags and sets MOE) → …".  §9 step 2: "nFAULT high after drives resume (note whether a fault recovery was needed)". |
| B20-04 | MINOR | DESIGN.md:9 ("rev L rounds 11–18"); README.md:7 ("after eighteen adversarial review rounds") | Round 19 was applied to rev L (CHANGES.md "Round 19 … → rev L (text only)"), but both labels still stop at 18.  The same stale label was raised and fixed as B16-08 and B18-06. | "rounds 11–19" / "nineteen" (or whatever round 20 makes it). |
| B20-05 | MINOR | DESIGN.md:652 (cross-check and plausibility → "the INA239-failure path"), :693–694 | **The INA239-failure path has no defined exit, and round 19 made it reachable from heuristics.**<br>• Before round 19 the path was entered only on SPI evidence: DEVICE_ID or configuration read-back failing.  Now a ~200 ms current-vs-estimate mismatch of > max(1 A, 30 %) and a 100 ms plausibility test also lead to it.<br>• :693–694 say only "weapon off, … drives continue on VBAT_SNS, report".  They do not say whether this is a hold (and until what: an operator clear? the mismatch ending?) or a retry.  It is also not in the latch word (:636–646).<br>• A false positive can come from a transient estimate error (catch-spin, regen transitions) or from B20-01.  It then either removes the weapon for the rest of the match or needs an MCU reset, and neither is specified.  The SPI3 fault next to it does specify its behaviour ("retry every ~100 ms (a hold, not a restart loop)"). | State it: for example, a hold that the operator clear releases once DEVICE_ID/configuration pass and the cross-check has agreed for ≥ ~1 s.  Say that it is not persisted, and whether it counts toward anything. |

## Notes

* **N1 — row 7 label drift.**  Round 19 widened drive row 7 to "left/right crossed: sensor cables **or motor bundles**" (:683).  Three places still use only the old sensor-cable wording:
  * the latch word calls it "sensor-cable-swap (drive row 7)" (:637);
  * the timer-inputs row says "(never after a sensor-cable swap, §8.1 drive row 7)" and "which catches swapped J2/J3 sensor cables" (:614).

  The row reference keeps the meaning unambiguous; suggested wording: "left/right-crossed hold".
* **N2 — watchdog row "after the Release".**  :606 says "TIM8/TIM20 only through the 'drives resume' step (§8.1), after the Release".  Drives resume also runs with no Release at all: link recovery and a supply restart of chips that were never CTRL4-coasted (:673).  Suggested: "only through the drives-resume step".
* **N3 — §9 step 4 wording.**  :741 says "measure the minimum idle current (the §8.1 row 0 threshold)".  The row 0 threshold is a fixed ~30 mA.  The bring-up value is the estimate's idle term and a margin check (row 0 :652 describes it that way).  Suggested: "(the idle term of the §8.1 row 0 estimate; confirm it is well above ~30 mA)".
* **N4 — §9 step 6 does not test the Release exit.**  §8.1 :689 asks to bench-verify that "the chip drives normally again after 0x0D10".  Step 6 (:759) tests the CTRL4 0x0C90 coast but not the exit.  Add "then 0x0D10 + drives resume: it drives normally".
* **N5 — resume after a supply event does not look at NPOR first.**  A chip whose VM dipped below its UVLO (the MCU riding through on hold-up) comes back in reset defaults.  "Drives resume" lowers the pin before the 100 Hz check sees NPOR = 0.  That is ≤ ~10 ms in the reset configuration.  With INL = +3V3 the 6x mode gives low-side / Hi-Z only (no shoot-through), and a fault recovery rewrites CTRL2.  It is bounded and settled in substance (R15A-01).  Reading IC_STAT before lowering the pin after a supply-class event would close it.

## Checked and consistent (round-19 edits)

* The §8 DRV8316 row, the §8.1 per-drive coast and the register check agree on CTRL4 0x0C90 / 0x0D10 and the read-backs 0x90 / 0x10.  The Release is the last step, for unlatched drives only.  The rewrite is the same sequence and ends coasted.
* The §8 timers row (TIM8/TIM20 OISx = 1, OSSI = 1) agrees with §3.3 :214 and drive row 2 :678.
* The INA239 row (AVG = 1, CNVRF, ALATCH = 1, CNVR = 0, SOVL 0x76C0, BOVL 0x17C0) agrees with row 1 :653 and SPI health :691.
* Watchdog row: TIM1 break clear at boot after U2 wake and the INA239 alert read.  BKE on TIM20 with BKINE = 0 matches §3.3 ("no TIM20 break pin on LQFP-64").
* Latch word :636–646 against its users:
  * the row 1 over-voltage count (:653);
  * "supply unstable" (:670–671);
  * the drive row 7 hold (:683);
  * the switch-open hold, deliberately not persisted (:652);
  * the MCU-reset rules (:696–700).
* Weapon rows:
  * row 0 suspension ("idle plus actively driven channels only") agrees with R19D-N1;
  * row 1 "looks open" and drive row 1 deferral (:653, :677) agree with "one event, one count" (:673);
  * the row 3 fold-back floor agrees with the power-budget row;
  * row 5's ~1 ms averaging and threshold from §9 step 6 match step 6 :754 (drum fitted before the reference, per B19-05/06).
* Drive rows:
  * drive row 1 → "drives resume" after 20 ms steady;
  * the drive row 7 report text matches §9 step 6 :764–766 (swap tests plus the forward-move check).
* §9 step 6 has the link timeout/recover test (R19A-01) at :758.  The row references in §8 (rows 6 and 10, drive row 7) resolve.
