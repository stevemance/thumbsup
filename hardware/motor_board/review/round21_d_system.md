# Review round 21 / D: system-level review (rev L)

Reviewer role: adversarial system reviewer (power electronics and combat robotics).  I read DESIGN.md rev L end to end,
design/calcs.md, spice/*.out, review/CHANGES.md (rounds 1–20) and round20_d_system.md (plus the round-20 A/B findings on
the INA239 path).  The package minus datasheets/ was copied to `/tmp/r21d/` (/tmp had < 50 MB free, not enough for the PDFs).
There, `design/motor_board.py` prints "237 refs (205 placed components), 160 nets, 67 BOM lines / checks: OK" and
`design/calcs.py` runs cleanly.  Round 20 changed text only, so no SPICE deck was re-run; the outputs were re-read.
Nothing in the package was edited apart from this file.

Evidence tags: **[D l.N]** = DESIGN.md line, **[S file]** = spice output, **[C §N]** = calcs.md.

---

## 1. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| R21D-01 | MAJOR | §8.1 drive row 6 (round-20 text) vs row 7 and §8 "too little motion" | **The new row 6 window makes row 7 unreachable, and it turns any alignment with too little motion into an endless, uncounted repeat.  A sensor cable pulled out in a hit (a case the design tests itself) therefore costs that drive for the rest of the match: it never falls back to sensorless.**<br>• **Row 6 swallows "too little motion".**  Row 6 matches when "the aligning drive moved outside **0.5–2×** the expected ~171 counts" [D l.682].  "Did not move" (0 counts) is outside that window.  Row 6 is first match, and its action is "Repeat the alignment; not counted", with no bound.<br>• **§8 says something else.**  §8 timer inputs says "too little motion → retry at a higher current, then run sensorless and report" [D l.614].  The two texts contradict each other, and a firmware author following the §8.1 table (first match) never reaches the fallback.<br>• **Row 7 is dead.**  Row 7 is "the other encoder moved while the aligning drive's own encoder stayed still" [D l.684].  An encoder that stayed still has moved 0 counts, so row 6 clause 1 matches first.  The other encoder moving also meets row 6 clause 2 ("either encoder was not still around a step").  Take crossed J2/J3 sensor cables (the case row 7 exists for, R16D-04/R17D-04/R19D-01).  Aligning drive L moves motor L, which TIM2 sees; TIM3 sees the still motor R.  The result is row 6, repeated forever, and never the "left/right crossed" report.  The §9 test expecting that report [D l.766–767] would fail.<br>• **Realistic single fault: a cut or unplugged encoder cable.**<br>&nbsp;&nbsp;– Unplugged while moving: the observer check switches the drive to sensorless, and the angle is marked invalid (≥ 20 ms without edges while the observer says it turns, a "sensor re-power") [D l.614].<br>&nbsp;&nbsp;– At the next standstill, or at drive enable after any MCU reset, the drive aligns.  The frozen count (the pull-ups hold the lines) gives 0 counts, so row 6 repeats.<br>&nbsp;&nbsp;– Each attempt is ~2 × 100 ms of ~1 A held at a fixed vector: that wheel is locked or dragged instead of driven.  Nothing bounds the loop.<br>&nbsp;&nbsp;– Before round 20 this case ended in sensorless running with a report.  Now the robot is effectively on one wheel.  The same happens to a wheel that 1 A cannot turn (wedged under an opponent: ~3.6 N at the tyre [C §10]) after a reset.<br>• Round 20's own proposal (R20D-03) bounded the disturbance retries ("after ~3 disturbed attempts, sensorless and report"); the adopted text dropped the bound | [D l.614, 682–684, 761, 766–767]; 90° el / 6 pole pairs = 15° mech = 4096 × 15/360 = **171 counts**; window 85–341 counts; a dead encoder gives 0; [C §10] 1 A × 2.73 mN·m × 28.5 × 0.8 / 21.6 mm ≈ 2.9–3.6 N | Split row 6.  (a) **Too little motion** (own encoder < ~0.5× expected, other encoder still): the §8 path, i.e. a higher current, then sensorless and report ("no encoder motion").  (b) **Crossed** (own encoder still, other encoder ≈ 0.5–2× expected): row 7, placed **above** the disturbance row.  (c) **Disturbed** (anything else outside the clean pattern): repeat, at most ~3 in a row, then sensorless and report; never latch.  Make §8 timer inputs say the same.  §9: unplug a sensor at standstill, then MCU-reset → that drive runs sensorless with a report (not an alignment loop) |
| R21D-02 | MINOR | §8.1 row 0 suspension clause vs a weapon held at throttle when the switch opens | **Round 20 took drive load out of the plausibility clause (R20D-02), but row 0 is still suspended "while any actively driven motor's electrical power is negative".  The switch opening while the operator holds weapon throttle creates exactly that, so the robot stays under control on drum energy after the switch opened.**<br>• **The case.**  Drum at speed under held throttle, BEMF ≈ 14.2 V l-l pk from a ~15.6 V spin-up bus [S spinup.out].  The switch opens (knocked open, or the crew switches off before the operator disarms).<br>• **The bus falls to the BEMF.**  C1 supplies drag, drives and logic: 30–50 W on 374 µF at 15 V ≈ 5–9 V/ms.  So the bus reaches the drum's BEMF within ~0.2–0.3 ms.<br>• **The weapon regenerates under FOC.**  From there the saturated weapon FOC can only draw current from the drum: the active bridge rectifies synchronously, and weapon electrical power (applied V × measured I) is **negative**.  Row 0 is suspended for as long as this lasts [D l.652].<br>• **No other path catches it.**  The cross-check is disabled because the drum is neither stopped nor motoring.  The plausibility clause does not apply for the same reason, and the bus is not above the BEMF.  No break occurs: no ALERT, no U2 UVLO at ~13 V, no BOVL, so rows 1–2 never run.<br>• **The result is R20D-02 again, through a different clause.**  Drives and weapon stay commandable until the drum falls to the logic cutoff: ~31 J, **~1–3 s at 10–30 W**.  That contradicts §7.5 ("Firmware … coasts the weapon and stops the drives") and the §9 step 3 test [D l.522, 736].  Only if the weapon command sits at the current limit does the row 10 stall cut-out end it after 0.5 s.<br>• **Why the clause exists.**  It protects against a closed-switch regen that makes the net pack current ≈ 0.  That case is already covered by the second suspension ("estimate within ~50 mA of zero") | [D l.522, 652, 662, 736]; [S spinup.out] 64.5 J, 14.2 V BEMF at 25.6 k rpm; energy above ~18.4 k rpm (≈ 10.2 V) ≈ 64.5 × (1 − (18.4/25.6)²) ≈ 31 J; C1 + locals ≈ 374 µF [C §9] | Suspend row 0 only while the **net** estimate (idle + actively driven channels, regen signed) lies within the cross-check tolerance of zero (~max(1 A, 30 %)), not on any negative channel power.  A clearly negative (or positive) estimate with a measured \|I\| < ~30 mA and a spinning, non-motoring drum → row 0.  §9 step 3: open the switch with the drum held at speed by the throttle → switch-open hold within ~0.1 s |
| R21D-03 | MINOR | §8.1 SPI health, INA239-failure entry (round-20 exit rule) | **One corrupted INA239 read now removes the weapon until the operator clears it.**<br>• **No confirmation on entry.**  The path is entered on "ID/read-back" failing, which is read every poll, with no confirmation count [D l.692–694].  Round 20 made the exit "stays off until the operator clears it (stored in the latch word)".<br>• **It is inconsistent with the rest of the SPI text.**<br>&nbsp;&nbsp;– A DRV8316 needs **≥ 3 consecutive** bad reads before it is declared deaf, because the read-back has no parity [D l.680]; the INA239 read has no CRC either.<br>&nbsp;&nbsp;– Two devices failing in one poll is only a ~100 ms retry hold [D l.692–693].  So a bit error that hits only the INA239 is punished harder than one that hits all three devices.<br>&nbsp;&nbsp;– A genuine INA239 reset is handled by "rewrite on a mismatch" in the same paragraph, yet it also counts as "failing".<br>• **The cost is a match.**  ~18 000 ID/config reads per 3-min match at 100 Hz, next to a 20 A, 24 kHz bridge, with MISO floating between transfers.  One glitch disarms the weapon until the operator does clear + disarm + new ARM edge + throttle zero.  In practice that is the rest of the match.  It is persisted, so a reset does not recover it either | [D l.680, 692–694]; B20-05 asked for a hold released "once DEVICE_ID/configuration pass" | Confirm the ID/read-back criterion like drive row 4: ≥ 3 consecutive failing polls in which the DRV8316s answer.  A config mismatch that one rewrite fixes and that then verifies is a counted report, not a failure.  Keep the operator-clear hold for confirmed failures and for the cross-check and plausibility entries, which already have 100–200 ms persistence |
| R21D-04 | MINOR | §8.1 drive table vs "drives resume" after a supply event (one-chip silent reset) | **A bus dip that resets only one DRV8316 is found by the 100 Hz poll while the supply restart is still waiting.  It is then classified as drive row 2: counted per drive and restarted at once, which contradicts "counted once with the supply event".**<br>• **The dip can reset one chip only.**  The DRV8316 UVLO is 4.1–4.3 V.  The loaded-bounce simulations leave VM at **4.4–4.8 V** [S hotplug.out], and the 1–3 ms interruptions in the §9 test go lower.  The two VM nodes also differ by I × 0.1 Ω of drive load.<br>• **The order of events.**  Weapon row 2 or drive row 1 raises DRV_OFF and waits ≥ 20 ms for a steady bus [D l.656, 677].  The poll (≤ 10 ms) finds one chip with NPOR = 0 or a mismatch.  That is not "both at once", and it is not "within ~1 ms" of the bus event, so drive row 2 matches.  The nFAULT exemption for a high DRV_OFF pin covers only nFAULT, not register or NPOR findings [D l.673].<br>• **What row 2 then does** [D l.678]:<br>&nbsp;&nbsp;– it counts one toward that drive's > 3/s latch;<br>&nbsp;&nbsp;– its "restart" runs drives resume, which **lowers the shared pin** before the 20 ms steady-bus wait has ended.<br>• **The nuisance.**  A chattering XT30/switch after a hit (4–5 ms-scale dips in a second, still under the > 5/s supply hold) that each reset the same chip latches that drive until an operator clear | [D l.656, 673, 677–678]; [S hotplug.out] 0.3–0.8 ms bounces, VM 4.4–4.8 V | While a supply restart (or any DRV_OFF-pin hold) is pending, leave NPOR and mismatch findings to the drives-resume check that follows.  Drives resume already rewrites and releases, counted once with the supply event.  Row 2 applies only with the pin low and no supply event within the preceding ~50 ms |
| R21D-N1 | NOTE | Row 3 (SOVL) before the U2 timing rows | A VDS OCP (row 8) that coincides with an SOVL would be classified as overload (restart, never latch).  The numbers make this unlikely.  A phase-to-GND short takes ~0.6 mC from C1 (~320 A peak × 4 µs / 2), and its recharge through RS4 adds only ~4 A to a 150 µs shunt conversion.  SOVL would therefore need ≥ ~34 A of load before the event, above the 32 A budget.  And a masked event re-trips as row 8 on the next restart once the fold-back lowers the load.  Optionally, apply row 3 only if W_nFAULT releases within ~0.5 ms after DIAG_ALRT is cleared | [D l.609, 655, 660] | — |
| R21D-N2 | NOTE | Drive row 2 action for a latched chip | A latched (coasted) chip that resets reads as a mismatch (CTRL4 0x10 vs the expected 0x90) and matches row 2.  Row 2 says "…rewrite, release, restart".  For a latched chip it should be the rewrite only (it ends coasted).  The Release rule [D l.612] and "a latched drive stays coasted" [D l.673] imply this, but row 2 does not say it | [D l.612, 673, 678] | — |

---

## 2. Scenario walk-through (rev L text as of round 20)

| Scenario | Path | Outcome |
|---|---|---|
| Drum impacts, single or flurries | Row 6 catch-spin; > 5/s → 1 s off; row 4 needs two consecutive fast re-trips | Safe, bounded, no latch |
| Locked or jammed drum | Row 6 and row 10 retries; row 5 passes at each stopped restart | No latch |
| Weapon phase–phase short, spinning / stopped | Row 4 / row 5 | Latched |
| Weapon phase–GND short | Row 8 VDS OCP (SOVL masking implausible, N1) | Latched |
| Bounce under weapon load, drum at speed | Row 2 supply; restart after 20 ms steady | Bounded |
| Bounce resets both DRV8316s | Row 1; drives resume reads NPOR, rewrites and releases, one count (R20D-01 closed) | Sound |
| Bounce resets one DRV8316 | The poll finds it before resume → drive row 2 count plus an early pin-low | **R21D-04** (nuisance latch on chatter) |
| Switch opened, drum coasting, operator driving | Plausibility is now weapon-only; row 0 holds after 100 ms (R20D-02 closed) | Sound |
| Switch opened, weapon throttle held | Weapon power negative → row 0 suspended; cross-check and plausibility idle | **R21D-02**: runs 1–3 s on drum energy |
| Switch opened while braking / motoring | Row 1 → row 0; motoring collapses the bus → supply → row 0 | Safe |
| C2 short / R2–R3 open | Plausibility / cross-check → INA239 path, operator-clear hold | Safe (weapon off, drives on) |
| One corrupted INA239 read | INA239 path at once, operator-clear hold | **R21D-03** |
| MCU reset mid-match, shoved during alignment | Row 6 repeat (R20D-03 closed for this case) | Sound while the shove lasts |
| Encoder cable pulled in a hit, then standstill or reset | Row 6 matches "0 counts" → endless repeat, no sensorless fallback | **R21D-01** |
| Pit: J2/J3 sensor cables or motor bundles crossed | Row 6 shadows row 7 → endless repeat, no "crossed" report | **R21D-01** (safe: no drive, but no diagnosis) |
| Pit: swapped drive phase or encoder pair | Clean wrong sign twice → row 6a latch | Sound, no reversed drive |
| Drive short (one chip) | OCP → row 2 → > 3/s latch, coasted, INH high | Sound |
| DRV8316 unpowered / deaf | Row 3 / row 4 (≥ 3 reads) | Sound |
| Compute-board reboot, radio drop, heartbeat loss | ARM falls (52–164 ms [S arm.out]); command timeout; ≤ 2 NRST pulses per 10 s; new edge + throttle zero | No operator-less re-arm |
| Power cycle with latches | Board latches lost; compute board mirrors the weapon latch; switch-open hold not persisted | Sound |

## 3. Checked and found sound

* **The round-20 fixes, re-walked:**
  * **Drives resume.**  NPOR and registers are read before any CLR_FLT; reset chips get the rewrite and the Release inside the supply event.  The boot order is Release → resume, and a resume timeout goes through the table.
  * **The weapon-only plausibility clause.**  A motoring weapon with the switch open pulls C1 down at ≥ ~2.7 V/ms even at 1 A × 13 V, so "steady" cannot hold.
  * **The cross-check** is limited to a stopped or motoring drum.
  * **The INA239-failure exit** now exists (but see R21D-03 on its entry).
  * **Alignment.**  A clean wrong sign twice is needed to latch, and a push repeats the alignment.
* **No masked short.**
  * Phase shorts latch by row 4, 5 or 8.
  * The resume brake window and the nFAULT exemptions apply only while the drive FETs are off or being released.
* **No operator-less re-arm.**
  * Automatic restarts happen only within a continuous ARM.
  * An ARM fall, a reset, a link recovery or a clear needs a new edge and throttle zero.
  * Latches, "supply unstable", the INA239 hold and row 7 are cleared only by an operator frame or a power cycle.
* **No reversed drive.**  Swapped phase or encoder pairs latch (row 6a).  Crossed bundles are covered by the §9 forward-move check.
  * R21D-01 blocks the "crossed" *report* but does not drive anything backwards: the aligning drive never completes.
* **§1 margins** (the hardware has not changed since round 16):
  * DRV8316 VM dV/dt: 0.80–2.26 V/µs for a loaded bounce, 2.66 V/µs at the −40 °C ESR and ≤ 2.09 V/µs for a re-close, all against 4 V/µs [S hotplug.out].
  * Q7: 16.5 / 22.0 W peak, 54–57 mJ.
  * ARM: 2.50–2.95 V against VT+ ≤ 2.15 V; 7–10 edges to arm; disarm in 52–164 ms [S arm.out].
  * Spin-up: 22 A peak, 14.1 V minimum.
  * D1: 32.4 V clamp against 35 V (C1) and 40 V (DRV8316).
  * INA239 limits: BOVL 19 V against the 20 V minimum DRV8316 OVP; SOVL 38 A against the 32 A budget.
  * MT6701: 47 k rpm with the duty cap and a 50 k rpm encoder cap, against its 55 k rpm rating.
  * The DRV8316 minimum VM of 4.4 V against its 4.1–4.3 V UVLO is handled by resume (R21D-04 is the one-chip remainder).
* **Scripts.**  Netlist checks and calcs run clean.

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R21D-01 | MAJOR | Row 6's "outside 0.5–2×" includes zero motion.  It makes row 7 (left/right crossed) unreachable and replaces §8's "too little motion → higher current → sensorless" with an endless, uncounted repeat.  A pulled encoder cable, or a reset while wedged, costs the drive for the match.  Fix: split too-little / crossed / disturbed, crossed above disturbed, bound the retries |
| R21D-02 | MINOR | Row 0 is still suspended by any driven motor's negative power.  With the switch opened while weapon throttle is held, the saturated weapon FOC regenerates from the drum, so the robot stays live ~1–3 s (R20D-02's outcome through another clause).  Fix: suspend only when the net estimate is near zero |
| R21D-03 | MINOR | The INA239-failure path is entered on a single bad ID or read-back and now needs an operator clear.  One SPI glitch loses the weapon for the match; the DRV8316s need ≥ 3 reads for the same thing.  Fix: 3-read confirmation; a mismatch fixed by a rewrite is a report |
| R21D-04 | MINOR | A one-chip silent reset found by the poll during the supply-restart wait goes to drive row 2 (per-drive count, early pin-low) instead of resume.  Chatter can latch a drive.  Fix: defer NPOR and mismatch findings to resume while a supply hold is pending |
| R21D-N1..N2 | NOTE | SOVL masking a VDS OCP is numerically implausible; the row 2 action for a latched chip should say "rewrite only" |

**Verdict: 0 BLOCKER, 1 MAJOR, 3 MINOR, 2 NOTE.**  All findings are firmware-contract text; no hardware change is needed.
