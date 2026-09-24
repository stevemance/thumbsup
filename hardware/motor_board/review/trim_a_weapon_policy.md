# Trim A: §8.1 weapon fault policy (intro, weapon events, restart, supply budget, MCU resets, clearing)

Scope: DESIGN.md §8.1 lines 626–672 and 703–713 (rev L): "Where it runs", "Latch word", weapon
events rows 0–12, "Every weapon restart", "Supply budget", "MCU resets", "Clearing / throttle-zero".
Not in scope: drive events, per-drive coast, drives resume, SPI health, §8 table, §9.

Current length of the scope: ~2 100 words.  The replacement below is ~1 200 words (about 55 %), and most of it is the table.

How I judged each rule.  I kept a rule if a single realistic fault or a normal fight event
triggers it: drum impacts, contact bounce at the switch or XT30, a phase short or pinched lead,
regen into a full pack or an open bus, a jammed drum, over-temperature, the pack lead pulled or
switched off, or an MCU crash.  I also kept hardware facts that firmware must respect.  I
simplified rules whose intent is sound but whose text had grown into a procedure.  I cut rules
that only matter in multi-condition chains, and rules that exist mainly to guard against
earlier over-specified rules.

Hardware facts checked in `datasheets/` for this trim:
* DRV8323 hardware (H) variant: VDS OCP is fixed at 4 ms automatic retry (SLVSDJ3D §8.3.6.3: "OCP_MODE bit is configured for 4ms automatic retry"; t_RETRY 4 ms typ).
* DRV8323 VM UVLO, CPUV and OTSD release nFAULT on their own when the condition clears (§8.3.6.1, 8.3.6.2, 8.3.6.7).
* DRV8323 GDF stays latched until CLR_FLT or an ENABLE reset pulse (§8.3.6.5).  t_RST is 8–40 µs; a longer low is sleep (table line "ENABLE = low period to reset faults").
* INA239 with ALATCH = 1: ALERT stays asserted until DIAG_ALRT is read (§7.3 "A read of the DIAG_ALRT register will reset the status of the ALERT pin").  Conversion times: 150 µs = field 2h.
* STM32G474: 32 backup registers, retained in VBAT mode, erased by tamper detection (DS §3.26).  The RCC_CSR flag behaviour comes from RM0440, which is not in `datasheets/`; I kept the existing statement unchanged but shortened.

## 1. Rule-by-rule verdicts

| Rule / row (current text) | Verdict | Reason |
|---|---|---|
| Where it runs: ISRs only record; SPI task classifies ~0.5 ms later after the first INA239 conversion that started after the event | **KEEP** (shortened) | Hardware timing fact: at the break, the bus evidence of a bounce does not exist yet.  Needed for row 2 to work at all |
| Where it runs: use the latched comparator EXTI flags (the live COMP output is not latched; TIM1 has one break flag) | **KEEP** (one clause) | G4 hardware fact; without it, rows 4/6 cannot tell a comparator trip from nFAULT |
| Where it runs: "time since the weapon's first applied vector" recorded | **KEEP** (folded into row 4) | Row 4 needs it |
| Where it runs: VBAT_SNS samples up to +0.5 ms | **SIMPLIFY** | Merged into the row 2 wording ("around the event") |
| (from §8 DRV8323 row) read/clear DIAG_ALRT first so the remaining W_nFAULT low time is U2's own | **KEEP** (one sentence in "where it runs") | INA239 ALERT is wired-OR onto W_nFAULT and latched (ALATCH = 1, verified).  Without this, the row 7/8/9 timing is meaningless |
| Latch word in TAMP backup registers, magic + CRC; survives NRST/IWDG/BOR/lockup; RTCAPBEN + DBP; never touch RTCSEL | **KEEP** | Needed so a crash cannot un-latch a shorted weapon.  Hardware facts |
| Latch word contents: itemised list (row 1 count, supply-budget history, crossed, INA239 hold, …) | **SIMPLIFY** | "Latches with reason, holds needing an operator clear, event counters, cumulative uptime".  The exact list is a firmware data-structure decision |
| Cumulative uptime ms rewritten every ~10 ms as the timebase | **KEEP** (short) | Rate limits (row 1, MCU resets) must span a reset, and no clock survives one |
| Invalid word: BORRSTF → fresh power-up, else "all latched"; PINRSTF/lockup detail | **SIMPLIFY** | Keep the rule and drop the flag commentary |
| Compute board mirrors the weapon latch across power cycles, disarms first, then persists | **KEEP** | Essential property: the weapon never re-arms without the operator after a power cycle.  (The "disarm then persist" ordering already lives in §3.5) |
| **Row 0** switch open: \|I\| < ~30 mA on every reading ≥ ~100 ms, VBUS > ~8 V | **KEEP** | Realistic: switch-off at match end with the drum spinning, or an XT30 pulled by an impact.  Physical basis: the ~100 mA idle draw always flows through RS4 when the switch is closed.  A bounce (≤ ~1.3 ms, §7.2) never reaches 100 ms |
| Row 0: hold until operator clear or fresh power-up; own flag, not persisted | **KEEP** | A drum-powered board must not let the robot drive after switch-off.  An end-of-match switch-off must not need a clear |
| Row 0: pause while a regenerating command is active; a protective coast ends the pause | **SIMPLIFY** | Replaced by "paused while firmware's own electrical-power estimate for any driven motor is negative; any protective coast ends the pause".  This covers commanded braking and a back-driven drive in one rule |
| Row 0: "after such a coast with \|I\| < ~50 mA the brake does not resume until pack current returns" | **CUT** (implied) | Row 1 now restarts only when pack current is back, otherwise row 0 holds.  Same outcome, no separate rule |
| Row 0: suspended while firmware's pack-current estimate (idle + actively driven channels) is within ~50 mA of zero | **CUT** | Guards a case that needs steady regen equal to the 100 mA idle draw ±30 mA for 330 consecutive readings with nothing commanded to regenerate.  The negative-power pause already covers the plausible versions.  It also required a bring-up idle-current estimate model |
| Row 0: instant weapon coast when the weapon is motoring, electrical power ≤ 0 and \|I\| < 50 mA on 3 conversions, plus its catch-spin-on-current-return clause | **CUT** | Added in rounds 21–25 to patch the estimate rules.  An open switch under weapon throttle has no energy source except the drum itself, so waiting ≤ 100 ms for row 0 costs nothing.  The drum cannot motor from its own back-EMF |
| Row 0: INA239 cross-check vs firmware estimate (~max(1 A, 30 %) for ~200 ms) | **CUT** | Speculative (R2/R3 cracked open).  It needs a calibrated whole-board current model.  An INA239 whose ID/config reads back correctly but whose shunt path is broken is a bench/firmware diagnostic, not a contract item |
| Row 0: plausibility (≈ 0 A with a steady bus while stopped/motoring ≥ 1 A → INA239 failure, e.g. C2 cracked short) | **CUT** | Single-part failure whose worst outcome is a fail-safe hold with a report.  Any board fault can cause that.  The detection logic grew three conditions to avoid its own false positives |
| Row 0: "a contact bounce never reaches the 100 ms persistence" | **KEEP** (one clause) | States the property: bounces never latch or hold |
| **Row 1** BOVL / 18.5 V coast → over-voltage: restart below 18 V with the regen limit halved; > ~3 in 10 s → latch | **KEEP** | Realistic: regen into a full or cold pack, or a lead pulled during a brake.  Bounded restarts; protects D1 |
| Row 1 "looks open" test (first two post-alert conversions, \|I\| < 50 mA and VBUS > 18 V; decay-rate and dump-time figures) | **SIMPLIFY** | Replaced by "restart only once pack current is back; otherwise row 0 holds within its 100 ms".  Same decision without a second classifier or its timing argument |
| Row 1: open bus under hard drive load may read as over-voltage | **CUT** | Covered: row 0 catches the open switch after any coast |
| **Row 2** bus event (INA239 VBUS < ~10 V or VBAT_SNS slope > ~5 V/ms) → supply, restart after 20 ms steady | **KEEP** | The most common real event: switch/XT30 bounce under load.  Never latches.  Thresholds are sim-based starting values |
| Row 2: parenthetical slope figures (bounce ≥ 7–10 V/ms, load step ≤ 2.5 V/ms, compute-board reset ~1 V/ms, light-load bounce may land in row 7) | **SIMPLIFY** | Keep the two figures that justify the threshold; the rest belongs in calcs/§9 |
| **Row 3** SOVL → overload fold-back, ramp back ~0.5 s, floor at traction limit, never latches | **KEEP** | Realistic: drum spin-up plus a drive push exceeds 38 A.  Includes a bounce re-close inrush (R16D-N1) |
| **Row 4** comparator re-trip ≤ ~200 µs after the first vector on two consecutive restarts → short → latch | **KEEP** | A real hard short (FET D–S, phase–VBAT, phase–phase while spinning) re-trips within one PWM period.  One fast re-trip alone can be a bad catch.  Essential "a real short latches" |
| **Row 5** standstill resistance check → latch | **SIMPLIFY** | Realistic fault (motor lead pinched phase-to-phase with the drum stopped: the current loop regulates it as load, R15A-04/R16D-02).  Keep the intent: brief DC pulse per phase pair, R < ~half the bring-up value → latch.  Cut the averaging windows, noise counts, rpm bounds, 2 s timeout and ΔV-from-duty details; they are firmware design, set in §9 step 6 |
| **Row 6** other comparator trip → catch-spin restart after 50–100 ms; > ~5/s → off ~1 s; never latches | **KEEP** | Drum impacts cause desync trips; this is the normal fight path |
| Row 6: ≤ ~34 A trip-chain arithmetic | **CUT** (lives in §7.21 / §8 fast-trip row) | Not policy |
| **Row 7** U2 short nFAULT without bus evidence → restart; > ~5 in 10 s → **latch** | **SIMPLIFY** (no latch) | U2 UVLO/CPUV self-release (verified).  Without bus evidence the most likely cause is a light-load bounce (the current text says so itself).  Latching on it breaks "bounces never latch".  Now counted in the supply budget, which bounds it.  The failing-CP-cap case this latch targeted is speculative, and the supply budget bounds it anyway |
| Row 7/8 t_split timing discrimination (UVLO/wake recovery < ~3 ms vs 4 ms VDS-OCP retry) | **KEEP** | Verified: H variant has fixed 4 ms automatic retry.  This is the only way to tell VDS OCP from UVLO on a register-less part |
| **Row 8** W_nFAULT released at t_RETRY → VDS OCP → latch | **KEEP** | Phase-to-ground short bypasses the shunts, so only VDS sees it (§7.21).  The 30 A comparators act in ≤ 1 µs, before the 4 µs VDS deglitch, so a VDS OCP means a real short.  Latch |
| **Row 9** nFAULT low > ~10 ms: TH1 > 90 °C → OTSD (cool-down) else GDF → latch + W_EN pulse | **KEEP** (shortened) | GDF is latched in the chip (verified) and means a damaged FET or gate path.  OTSD self-clears (verified) |
| Row 9 clause: INA239 marked failed with a stuck ALERT → report reason "INA239" | **CUT** | Chain of two conditions; the weapon is already off in that state |
| **Row 10** stall cut-out / TH1 > ~100 °C → coast and retry, never latches | **KEEP** | A drum jammed by an opponent is a normal fight event |
| **Row 11** §7.16 strap boot test failed → latch | **KEEP** | Hardware fact: a wrong or open strap puts U2 in the wrong mode |
| **Row 12** unknown → latch | **SIMPLIFY** | Latching on one unexplained break (EMI glitch on W_nFAULT, an unmodelled release time) latches a working weapon mid-fight.  Real shorts are already caught by rows 4/5/8/9.  New rule: one restart as row 6; a second unknown within ~10 s latches.  Still bounded and fail-safe |
| Every weapon restart: catch-spin, then three-phase FOC, never six-step | **KEEP** | Six-step floats a phase and hides a short from rows 4/5 (R15A-04) |
| Supply budget: > ~5 supply restarts in 1 s → everything off ~1 s | **KEEP** | Bounded restarts; lets a chattering contact settle |
| Supply budget: > ~20 in a minute → "supply unstable" hold until operator clear (persisted) | **CUT** → report only | A loose connector that keeps reconnecting should keep the robot fighting.  Restarts are benign and already bounded by the 1 s hold-off.  The hold protects no hardware (U13 soft-start energy per re-close is set by hardware, not by firmware restarts).  Report the count so the crew fixes the connector |
| Supply budget: U13's own UVLO restart counts too | **KEEP** (implicit) | It looks like a bounce and is counted as one |
| MCU resets: latch survives reset | **KEEP** | Essential |
| MCU resets: IWDG/HardFault within ~2 s of a weapon event → latch | **SIMPLIFY** | Replaced by "an event unclassified at reset counts as unknown (row 12)" plus the rate limit below.  One crash during a fight does not latch; a repeat does |
| MCU resets: > ~3 IWDG/lockup/HardFault resets in ~10 s → latch weapon | **KEEP** | Bounds auto-re-arm after crashes: the compute board re-arms automatically after a reset with no latch (§3.5) |
| MCU resets: BOR with a valid word → supply budget | **KEEP** | A brown-out is a bounce |
| Clearing: operator "clear faults" frame, never automatic; weapon also needs disarm, new ARM edge, throttle zero; W_EN pulse after GDF | **KEEP** | Essential: no re-arm without the operator.  W_EN pulse is a verified hardware requirement (GDF latched, t_RST 8–40 µs) |
| Throttle-zero interlock after arm/re-arm/reset/link recovery/clear | **KEEP** | Essential and simple |

### Knock-on edits outside this scope (for whoever owns them)

1. **§9 step 4:** "the idle-draw term of the §8.1 row 0 estimate … row 0's 50 mA estimate band" is stale; there is no estimate any more.  Keep the idle-current measurement only as a check that the idle draw is well above the 30 mA row 0 threshold (expect ~95–113 mA).
2. **§9 step 6 classifier list:** "brake the drum to a stop and reverse it … no switch-open or INA239-failure report" still holds for switch-open.  Remove "INA239-failure" if SPI health drops the cross-check and plausibility tests.  Add an expectation: a light-load bounce (row 7) is a supply-class restart and never latches.
3. **SPI health (other agent):** "or the persistent cross-check or plausibility test" refers to rules cut here.  INA239 failure then means ID/config read-back only.
4. **Drive events (other agent):** the "supply unstable" hold no longer exists.  Drive supply events (drive row 1) share this supply budget, one count per event.  Drive row 1's "deferred to row 0 when weapon row 1 did so" now reads "weapon row 1 restarts only once pack current is back".
5. **§8 "Weapon safety" row:** "classify and restart as §8.1 row 1" is unchanged and still correct.
6. **§7.21, §3.2:** "two consecutive comparator re-trips… or a failed restart resistance check… latch" is unchanged and still correct.
7. Row numbers 0–12 are unchanged, so existing cross-references remain valid.

## 2. Proposed replacement text

Paste in place of DESIGN.md lines 626–672 (heading through "Supply budget").  Paste the second
block in place of lines 703–713 ("MCU resets" through the throttle-zero interlock).  The drive
events, per-drive coast, drives resume and SPI health text in between belongs to the other trim.

```markdown
### 8.1 Fault policy (thresholds are starting values, tuned in §9)

**Where it runs.**  Interrupts only record: the TIM1 break, the comparator EXTIs (use their
latched flags to tell which source tripped; TIM1 has one break flag for all sources) and the
nFAULT EXTIs store flags, the W_nFAULT level and a timestamp, plus the time since the weapon's
first applied vector after its last restart.  They never block and never touch SPI.  The **SPI
owner task** classifies ~0.5 ms later, after the first INA239 conversion that started after the
event, because the bus evidence of a contact bounce does not exist yet at the moment of the
break.  It reads and clears DIAG_ALRT first (the INA239 ALERT is wired onto W_nFAULT and latched,
ALATCH = 1), so any remaining W_nFAULT low time is U2's own.

**Latch word.**  The weapon, left and right latches (with reason), the holds that need an operator
clear, event counters and a cumulative uptime (ms, updated every ~10 ms: the timebase for rate
limits that span a reset) live in the backup registers (TAMP_BKPxR, magic value + CRC).  VBAT is
on +3V3, so they survive NRST/IWDG/BOR/lockup resets and are lost only when +3V3 collapses.
RTCAPBEN + DBP to write; never change RTCSEL (it resets the backup domain).  A valid word is
always honoured.  An invalid word means a fresh power-up if RCC_CSR BORRSTF is set, otherwise
"all latched".  A power cycle therefore clears the board's latches, so **the compute board
mirrors the weapon latch from the heartbeat and refuses to arm until the operator clears it**
(§3.5).

**Weapon events** (evaluate in order, first match wins; every row is counted and reported):

| # | Evidence | Class → action |
|---|---|---|
| 0 | **Continuous monitor, not tied to a break:** INA239 \|I\| < ~30 mA on every reading for ≥ ~100 ms with VBUS > ~8 V.  With the switch closed the board's own ~100 mA idle draw always flows through RS4; a contact bounce (≤ a few ms) never lasts 100 ms.  Paused (and the 100 ms restarted) while firmware's own electrical-power estimate for any driven motor is negative (braking, or a drive back-driven by a shove); any protective coast ends the pause | **Switch open** (switched off, or the pack lead pulled) → weapon coast, drives off (DRV_OFF high); hold until the operator clears it or a fresh power-up, whatever VBUS does (a coasting drum keeps the bus and the logic up for seconds).  Its own flag, not a weapon latch, and not persisted: an end-of-match switch-off must not need a clear |
| 1 | DIAG_ALRT BOVL (19 V), or the 18.5 V firmware coast (§8 weapon safety) | **Over-voltage** (regen into a full pack, or the pack lost during a brake) → weapon coast, drives to zero torque (this ends any row 0 pause).  Restart only once pack current is back and VBUS < 18 V, with the regen limit halved; if the current does not come back, row 0 holds.  More than ~3 within 10 s → latch the weapon (bounds the energy into D1) |
| 2 | **Bus event:** the post-event INA239 VBUS < ~10 V, or VBAT_SNS falling faster than ~5 V/ms around the event (a loaded contact bounce ≥ ~7 V/ms; a 0→20 A load step ≤ ~2.5 V/ms) | **Supply** (switch/connector bounce) → DRV_OFF high too; restart everything once VBUS has been steady ≥ 20 ms (supply budget below); never latches |
| 3 | DIAG_ALRT SOVL (38 A) | **Overload** → fold back the shared power budget (never below the drives' traction limit) and restart, ramping back over ~0.5 s; never latches |
| 4 | Comparator trip ≤ ~200 µs after the first applied vector of a restart, on **two consecutive** restarts | **Short** (a hard short re-trips within one PWM period; one fast re-trip can be a badly synchronised catch) → latch the weapon |
| 5 | Phase-pair resistance check failed.  Before spinning up a stopped drum (first start after arming, and every restart from standstill), apply a brief DC current pulse to each phase pair; R below ~half the value stored at bring-up with the drum fitted (§9 step 6) | **Short at standstill** (e.g. a pinched motor lead: with the drum stopped the current loop regulates a phase-to-phase short as load and the comparators never trip) → latch the weapon |
| 6 | Any other comparator trip | **Trip** (impact desync, over-current) → catch-spin restart after ~50–100 ms; more than ~5 within 1 s → weapon off ~1 s, then restart; never latches |
| 7 | W_nFAULT releases in < t_split (~3 ms; set in §9 step 4 between U2's UVLO/wake recovery and its fixed 4 ms VDS-OCP retry) | **U2 undervoltage** (usually a bounce too light to show on the bus) → weapon restart, counted in the supply budget; never latches |
| 8 | W_nFAULT releases at t_RETRY (~4 ms) | **VDS OCP** (phase-to-ground or shoot-through; a phase-to-ground short bypasses the shunts, so only VDS sees it) → latch the weapon |
| 9 | W_nFAULT low > ~10 ms | TH1 > ~90 °C → **U2 over-temperature**: as row 10.  Otherwise **gate-drive fault** (latched inside U2) → latch the weapon; clearing it also needs a W_EN reset pulse (8–40 µs) |
| 10 | Stall (at the current limit with no speed rise for > 0.5 s) or TH1 > ~100 °C (polled) | Coast ~1 s (or until TH1 < ~80 °C), then restart; never latches (a drum jammed by an opponent retries) |
| 11 | §7.16 strap boot test failed | Latch the weapon |
| 12 | Anything else | **Unknown** → one restart as row 6; a second unknown within ~10 s → latch the weapon |

**Every weapon restart** begins with a catch-spin (pick up the coasting drum's speed and angle) and then runs three-phase FOC, never six-step: six-step leaves a phase floating and hides a phase short from rows 4 and 5.

**Supply budget:** supply-class events (weapon rows 2 and 7, drive supply events, brown-out
resets; one count per event) are counted and reported.  More than ~5 within 1 s → everything off
~1 s, then retry.  A chattering connector never latches; the counts tell the crew to fix it.
```

```markdown
**MCU resets** (counted in the latch word): latches set before the reset stay set.  An event
still unclassified when the reset hit counts as unknown (row 12).  More than ~3 IWDG, lockup or
HardFault resets within ~10 s latch the weapon (the drives may still run).  A brown-out reset
counts in the supply budget.

**Clearing** needs an operator action forwarded by the compute board: a "clear faults" frame
carrying the operator input, never sent automatically.  For the weapon, clearing also needs a
disarm, a new ARM edge and the weapon throttle at zero, and after a gate-drive fault a W_EN
reset pulse.  **Throttle-zero interlock:** after any arm, re-arm, reset, link recovery or latch
clear, the weapon command must be seen at zero before the weapon may spin up.
```

### Safety properties preserved

* **The weapon never re-arms without the operator.**  Every latch persists across MCU resets in the latch word and across power cycles in the compute board's copy.  A latch is cleared only by an operator frame plus a disarm, a new ARM edge and throttle zero.  The throttle-zero interlock covers every restart path.
* **A real short latches:**
  * a hard short while spinning is caught by row 4;
  * a phase-to-phase short at standstill by row 5;
  * a phase-to-ground short by row 8;
  * a gate-path failure by row 9;
  * repeated unexplained breaks or crashes by row 12 and the MCU-reset rule.
* **Bounces and normal fight events never latch:**
  * bounces fall under rows 2 and 7 (row 7 no longer latches) and row 3 for re-close inrush;
  * impacts under row 6;
  * jams and heat under row 10;
  * regen under row 1, which latches only after > 3 in 10 s;
  * the switch-open hold needs ≥ 100 ms without pack current, which a bounce never reaches.
* **Restarts are bounded:**
  * row 6: 5/s, then a 1 s hold-off;
  * supply budget: 5/s, then a 1 s hold-off;
  * row 1: 3 in 10 s, then latch;
  * row 12: 2 in 10 s, then latch;
  * MCU crashes: 3 in 10 s, then latch;
  * stall and thermal: a 1 s coast, or until cool.
