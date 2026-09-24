# Round 19 — B: consistency audit (rev L)

Scope: the whole package, focused on DESIGN.md §3.3, §8, §8.1 and §9 as edited in round 18.
Line numbers refer to the working tree as audited (DESIGN.md is 769 lines).

## Reproduction

* The package was copied to `/tmp/r19b/`.  `design/motor_board.py` printed "237 refs (205 placed
  components), 160 nets, 67 BOM lines / checks: OK".  `design/calcs.py` ran cleanly.
* The regenerated `netlist.csv`, `nets.md`, `bom.csv`, `mcu_pinmap.md`, `calcs.md` and `BOM.md` are
  **byte-identical** to the tree (`diff -rq` of the whole copy against the tree is empty).
* bom.csv has 67 lines and a total Qty of 199.  The 6 DNP parts (C110–C112, C114–C116) are in the
  netlist only.  BOM.md:4–6 and README.md:7 match.  Rev labels read "rounds 11–18" / "eighteen".
* **LCSC:** all 28 BOM.md table rows have the same LCSC number as bom.csv.  Every LCSC number in
  BOM.md that is not in bom.csv is a named alternate (C1235414, C529413, C157991, C18213, C2150467,
  C2846803, C53055322).  DESIGN.md, README.md and datasheets/README.md cite only bom.csv numbers.
* **Values:** a script matched every "Rxx/Cxx/… value" mention against bom.csv.  The only hits
  were false positives: the range "R22–R27 68k/10k", "R7–R10 0402", "Q7 16 …", "C310 4 × …" and
  "R117 0603".
* **MCU pins:** a script matched every "NET PXn" / "PXn NET" mention against mcu_pinmap.md.  The only
  hits were the `_F` suffix on the filtered CSA nets (e.g. L_SOA → L_SOA_F), which is not an error.
* **IC pinouts:** the U3/U4 pin numbers in §3.3 (VM 9–11, CP 8/CPH 7/CPL 6, AVDD 25, VREF 37,
  SW_BK 5/FB_BK 3/GND_BK 4, INH 27/29/31, INL 28/30/32, DRVOFF 21, nSLEEP 23, nFAULT 22,
  SOA/B/C 40/39/38) match netlist.csv.
* **Other READMEs:** datasheets/README.md indexes every PDF in the folder, and every PDF it names
  exists.  spice/README.md names only files that exist; `ngspice_shared.py` is in
  `hardware/tools/spice/`.

## DRV8316 SPI words (B15 W0, B14–9 address, B8 even parity)

| Word | Addr | Data | 1s | Parity |
|---|---|---|---|---|
| 0x0603 / 0x0606 | 03 CTRL1 | 03 / 06 | 4 / 4 | OK |
| 0x1019 | 08 CTRL6 | 19 | 4 | OK |
| 0x0A4E | 05 CTRL3 | 4E | 6 | OK |
| 0x0C90 / 0x0D10 | 06 CTRL4 | 90 / 10 | 4 / 4 | OK |
| 0x0F00 | 07 CTRL5 | 00 | 4 | OK |
| 0x1818 (0x1915 not used) | 0C CTRL10 | 18 (15) | 4 (6) | OK |
| 0x087C / 0x097D | 04 CTRL2 | 7C / 7D | 6 / 8 | OK |
| 0x0C10 / 0x0D90 | 06 | quoted as the wrong words | 3 / 5 | odd, as the text says |

* Every occurrence was counted: 0x0C90 ×4, 0x0D10 ×4, 0x0603 ×4, 0x0606 ×4, 0x097D ×2.  Each one
  is used for the same purpose everywhere: DESIGN.md:597, 612, 677, 684–688 and 758.
* The read-back expectations match these words: CTRL1 0x06, CTRL2 0x7C, CTRL3 0x4E, CTRL4 0x10/0x90,
  CTRL5 0x00, CTRL6 0x19, CTRL10 0x18 (:612).

## Row and step references

All of these resolve correctly:

* §8.1 row 0 (:620), row 6 (:615), row 10 (:618, :660, :767), row 5 (:753), row 1 (:761) and
  rows 1–12 (:651).
* Drive row 7 (:614).
* §9 step 5 (:614), step 6 (:459, :656), step 0 (:555) and step 2 (:564).
* "after 3" in weapon row 7 (:658) is row 3 (SOVL read first).

One exception is B19-05: the row 0 → §9 step 4 reference.

---

## Findings

### B19-01 — MAJOR — nothing re-arms TIM8 MOE (or clears a DRV_OFF-pin nFAULT) when the DRV_OFF **pin** goes low again after a pin-only stop.  An nFAULT still low after the pin falls is not exempt.

**Evidence**

* SLVSH07 §8.4.2 (DRV8316C.pdf p.53): "Since DRVOFF pin independently disables MOSFET, it can
  trigger fault condition resulting in nFAULT getting pulled low."  The package accepts this at
  DESIGN.md:672 and :726.
* L_nFAULT is TIM8_BKIN, active low (:216, :613).  While it is low the TIM8 break clears MOE.  BIF
  cannot be cleared and MOE cannot be set until the input is inactive.  AOE is not specified for
  TIM8.
* The package re-arms MOE in only two places:
  * the boot order, tied to the Release write (:597);
  * the drive-table preamble: "After a **Release**, clear that timer's break flag and set MOE
    again" (:672).
* Several stops raise only the pin and later restart without any Release write:
  * command-link timeout, then "commanded again" (:605);
  * weapon row 2 supply, "restart everything" (:653);
  * drive row 1, "restart both after 20 ms steady" (:676);
  * row 0, after the operator clears it (:651);
  * the SPI3 fault retry (:691).
* The exemption at :672 covers "while the DRV_OFF pin is high or within ~1 ms after firmware
  **raised** it".  Everything after a raise is already covered by "while high", so the clause adds
  nothing.  It says nothing about the time **after the pin is lowered**.  SLVSH07 does not say
  whether a DRVOFF-induced nFAULT releases by itself or needs CLR_FLT.

**Consequences if §8/§8.1 are implemented as written**

* After the first link dropout, supply restart or switch-open clear, the right drive runs.  The
  left drive stays at the TIM8 break idle level.  With OISx = 1 in 3x mode that is a high-side
  **brake** (§3.3 :214, drive row 2 :677).  The robot drags one wheel for the rest of the match.
* Suppose the pin-induced fault is latched until CLR_FLT.  Then both nFAULTs are still low once
  the pin is low, so they are no longer exempt.  They classify as drive row 1 "both at once" →
  DRV_OFF high → restart, and each pass counts in the supply budget.  After ~20 passes in a minute
  the result is the "supply unstable" hold (:668–670).

**Fix**

* Define one "drives resume" step for every pin-low transition, not only for Release:
  1. Lower the pin.
  2. If nFAULT is still low after ~1 ms, run the §8 fault recovery (CTRL1 0x0603 → CTRL2 0x097D
     → CTRL1 0x0606).
  3. Wait for nFAULT high.
  4. Clear the TIM8 (and TIM20) BIF and set MOE.
* Extend the :672 exemption to "from raising the pin until that resume step completes".
* Verify on the bench in §9 step 2: toggle the pin with the chips released, then check nFAULT and
  whether the left drive switches after the pin falls.

### B19-02 — MINOR — the §8 Watchdog row's break-flag clear timing contradicts the round-18 boot order for TIM8/TIM20

* :606 says to "Clear the break flags at boot, **after** U2's ~1 ms wake fault has cleared, the
  DRV8316 fault clear and the INA239 alert read (so MOE can be set …)".  The DRV8316 fault clear
  (CTRL2 0x097D) is part of the configuration sequence.  At that point the chips are still coasted
  (CTRL4 0x0C90) and the pin is high (:612), so L_nFAULT may be low and the TIM8 break stays
  active.
* :597 (round 18) moves the TIM8/TIM20 clear to after the pin release and the per-chip Release.
* Taken literally, :606 attempts a TIM8 clear that cannot succeed, and :606 and :597 give two
  different times.
* **Fix:** in :606 limit the list to TIM1 ("TIM1: after U2's wake fault and the INA239 alert read;
  TIM8/TIM20: after the Release, see boot order").

### B19-03 — MINOR — the latch-word contents list is missing the state that round 18 put into it

* :636 lists the latch word as "Weapon, left and right latches, reason, a reset counter and a
  cumulative uptime".  Other lines say more state is stored there or survives resets:
  * **"supply unstable"** hold, "stored in the latch word" (:670);
  * **drive row 7** sensorless-until-realigned, "stored in the latch word" (:682);
  * **weapon row 1** over-voltage count, "> ~3 within 10 s … bounds the energy into D1 across MCU
    resets too" (:652).  That needs the count and its timestamps to survive a reset.
  * **brown-out resets** "count toward the supply budget" (:697–698).  That needs the supply-budget
    counts (per second and per minute) with timestamps in the backup registers.
* **Fix:** add these to the :636 list: the supply-unstable flag, the drive-row-7 flag, the
  over-voltage restart history and the supply-budget history.  Also check that they fit the
  TAMP_BKPxR count with the magic value and the CRC.

### B19-04 — MINOR — one bus event can be classified twice (weapon row 2 and drive row 1), and the two tables disagree while row 0 is deciding

* A contact bounce that pulls both DRV8316 nFAULTs low (CP-UV/UV) **before** the SPI owner raises
  the pin is not exempt, because the pin is still low.  It matches drive row 1 ("Both DRV8316s at
  once, a bus event within ~1 ms", :676).  The same bounce matches weapon row 2 (:653).
* Both rows restart "(supply budget)".  Nothing says that one bus event counts once.  About 3
  real bounces in a second then reach the "> ~5 within a second → everything held off ~1 s" limit
  (:668) instead of ~5.
* Weapon row 1 "looks open" sets the drives to **zero torque, row 0 decides** over 100 ms (:652).
  Round 18 added "DRV8316 OVP within ~1 ms of an INA239 BOVL" to drive row 1, whose action is
  "DRV_OFF high, **restart both after 20 ms steady**" (:676).
  * The OVP trips at 20 V minimum and BOVL at 19 V, so this is the §9 step 6 "open the switch
    while braking" case (:761).
  * Neither table says which action wins across the two tables.
  * Drive row 1 also counts the event in the supply budget.
* **Fix:**
  * Say that the classifier merges weapon and drive evidence within ~1 ms into **one** event,
    counted once.
  * Say that a pending weapon row 1 "row 0 decides" overrides drive row 1's restart (the drives
    stay at zero torque until row 0 resolves).

### B19-05 — MINOR — row 0 sends the idle-current measurement to §9 step 4, but step 4 does not contain it

* Row 0 (:651) says: "the idle current is measured at bring-up (§9 step 4)".
* Step 4 (:740–745) covers the charge pumps, the fast trip and t_split, with no idle current.
* The item is written inside **step 2** (:727: "in step 4 at 16.8 V, the minimum idle current
  (row 0 threshold)").  A technician working through step 4 will not see it.  This value also sets
  the margin of the row 1 "|I| < ~50 mA" test (:652).
* **Fix:** move the sentence into step 4.

### B19-06 — MINOR — §9 step 6 stores the "drum fitted" resistance before the drum is fitted

* :752–753 reads: "motor without drum, 5 A limit; … raise the limit in steps to 20 A; **with the
  drum fitted**, store the three phase-pair ΔV/ΔI values … **Then the drum**; measure the free
  coast-down time".
* Row 5 (:656) requires the reference to be "stored at bring-up with the drum fitted".  The step
  text puts that measurement before the sentence that fits the drum.
* **Fix:** move the ΔV/ΔI sentence after "Then the drum".

## Notes

* **N1:** CHANGES.md:357 still records B18-02 as "uses the last INA239 reading before the event".
  Round 18's R18A-01 (CHANGES.md:363) replaced that with post-alert |I| and VBUS, and DESIGN.md:652
  says "the current sign is not usable".  Mark B18-02 as superseded by R18A-01 so the summary does
  not contradict the design.
* **N2:** :613 says "DRV_OFF low only when drives **armed**", while :597 says "when the drives are
  **commanded**".  The drives have no arm state.  Use one term.
* **N3:** drive row 1 "restart both" (:676) should read "restart the unlatched drives".  A
  row 2/3-latched chip must stay coasted, as :677 says.  Likewise, the boot order (:597) should keep
  the pin high while row 4 has latched both drives (a deaf chip can be stopped only by the pin).
* **N4:** row 0 plausibility (:651): "C1 alone would fall ~27 V in 100 ms".  With C1 = 330 µF
  (bom.csv) at ~0.1 A this is ~30 V.  The conclusion is unaffected.

## Counts

BLOCKER 0 · MAJOR 1 · MINOR 5 · NOTE 4
