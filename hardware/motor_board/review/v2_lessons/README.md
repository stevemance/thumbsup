# Motor board layout v2: lessons from attempt 1 and the rules for the restart

Attempt 1 (branch `worktree-routing`, kept as the backup) reached 13 open connections on 6 layers, 85 x 35 mm, with
688 vias, and did not close.  v2 restarts from the same schematic (rev L1) on **4 layers**, 85 x 35 mm, with the
ground rules the user set on 2026-09-29:

- The board outline is fixed.  **J1** (20-pin 1.27 mm board-to-board header) may go anywhere on the **bottom**.
- **Hot parts go on the top side.**
- Parts may be moved freely.  **Nothing is removed without asking the user.**
- Preferred cable exits (soft): the left drive motor at the bottom-left, the right drive motor at the bottom-right
  (rear corners), the weapon at the top-right (front-right).
- MCU pins may be reassigned freely.  Every move goes into DESIGN.md, CHANGES.md and the pin map straight away.
- Copper weight is our call.  Weight matters, so add copper only where the numbers need it.  Do not propose more
  layers.

The four detailed reviews in this folder carry the evidence.  This page collects the conclusions:

| File | Scope |
|---|---|
| [design.md](design.md) | Design-specific lessons: clusters, pin assignment, what worked, 6 to 4 layers, placement checklist |
| [process.md](process.md) | Process and tooling: router, tail loop, sweeps, gotchas, what the user values, proposed workflow |
| [electrical.md](electrical.md) | Currents, stack-up, loops, Kelvin, thermal, EMC, v1 electrical defects |
| [critique.md](critique.md) | Independent post-mortem with measurements, a proposed floorplan, part-size candidates, ranked root causes |

## 1. Why attempt 1 did not close (consensus of all four reviews)

1. **Via and inner-layer capacity around the MCU ran out; board area did not.**  The board was 20-30 % smaller than
   DESIGN §6.13's own estimate (courtyards 2537 mm² on 2987 mm² of outline).  Growing it 10 mm closed 1 net.  The
   empty band the grow left was an inner-layer bus corridor, so parts moved into it could not reach vias
   (48 open).
2. **The MCU pin map was fixed before placement.**  Seven nets leave U1 on the side opposite their load.  The 11
   weapon-control nets leave from three sides, although TIM1's six outputs sit together on pins 35-44.
3. **The MCU was on the bottom, with an unrelated block on top of it.**  The left sensor front end sat directly over
   U1's fan-out, and both needed the same via sites.  That cluster stayed stuck for 47 rounds.
4. **The MCU was off-centre relative to its loads, and U6 was on the wrong side.**  About 22 east-bound nets formed
   an 11-lane L3 bus wall around U2 and J3.  U6 turned 3 short links into six 58-70 mm nets.
5. **Inner layers were reserved for power by region.**  An L3 VBAT pour covered the whole front half, the bottom was
   reserved as a gate corridor, and the overflow went onto the L5 "GND plane" as 300 mm of signal.
6. **Process: routing started with no routability check on the placement.**  It then used a sequential greedy router
   plus four days of incremental patching, which spends the room later fixes need.

## 2. What is kept from attempt 1

- **The weapon bridge macro:** three U-cells (Q1-Q6, RS1-RS3, C25/C26/C31, NT1-3, JW1-3), a ~4 nH commutation
  loop, gate/Kelvin pairs.  Reuse it as a rigid block at the front-right.
- **The pack entry** (JBAT1/2, Q7/Q8, U13 soft-start, RS4, D1) as a block, and the connector pin orders.
- **The discipline:** DRC 0 and parity 0 at every commit, an ops-based round log, isolated experiment directories,
  and the diagnostic tools (density.py, viaspot, netcc, islands, cydump, blockmove, set3d).
- **The circuit, BOM and 3D models**, unchanged except where section 5 asks the user.

## 3. Rules for v2 (merged; the detail is in the files)

**Stack-up (electrical.md B):** 4 layers, 1 oz on every layer (the inner 1 oz must be ordered; JLC defaults to
0.5 oz, which puts 20-45 mV on the pack return).  Thin prepreg (~0.08-0.1 mm) on both outer pairs.  1.6 mm, or
1.2 mm to save ~2-3 g if the commutation-loop estimate holds.

- L1: parts and power pours.
- L2: solid GND, with no trace or jumper ever.
- L3: VBAT feed pour over the front power band only, GND pour elsewhere, and a few slow lanes where no L4 signal
  runs above.
- L4: bottom parts, MCU fan-out and signals, GND fill stitched to L2.

No 2 oz: the fine-pitch parts and the weight both argue against it.  The pack capacity comes from L1 and L3 pours
in parallel plus via fields.

**Floorplan (critique §4, design §F):**

- Power in the front ~18 mm: pack entry at the front-left, bulk cap at the bridge, the bridge at the front-right.
- Logic in the rear ~17 mm.
- **MCU on top**, in the middle of its loads, next to U2, with its pin sides facing their blocks.
- U6/U14 between the MCU and U2.  U2's logic edge stays open.
- Each sensor front end sits beside its connector, off every IC.  Its chain (connector, pull-up, 1 k, buffer, MCU)
  runs monotonic, with no crossings.
- J1 on the bottom, beside the MCU, with the UART/SWD/NRST pins facing it.
- The BMS block (J4, U8) is self-contained at the left.
- The drive-motor blocks sit at the rear corners: U3 at the left, U4 at the right.
- The test pads go in one rear strip, never in the MCU core.

**Stacking:** put only an IC's own passives under it, or a self-contained block.  Never put one block's fan-out
over another block's.

**Pins:** place the blocks first.  Then assign MCU pins with a score (pin edge against the direction of the
destination), AF-checked against `ref/STM32G474RxTx_pins.xml`.  Constraints: the encoder uses CH1/CH2 of one
timer, and the CSA inputs need specific ADC/COMP pins.  Record every change in the docs.

**Vias:** budget about 1.1 vias per signal connection, i.e. ≤ 1 per connection end (v1: 2.2).  Every GND pad gets
its own via within 0.5 mm.  Fan-out via rows sit outside U1's body.  Thermal arrays are placed at placement time.
Check the via-in-pad price on 4 layers before designing around it.

**Rails:** +5V (sourced at U2's buck) and +3V3 (U5) are planned trunks.  **R20's feedback-top sense closes at
C29/C30 at placement time.**  The R302/R402 VBAT feeds are ≥ 1 mm or poured.  The DRV8316 VM caps sit within 3 mm.
Custom DRC rules enforce the minimum widths per net class.

**Routability gate before any routing:**

- Ratsnest length and crossings.
- Demand against capacity on each cut line, at ≤ ~70 % of capacity.
- Via sites per IC.
- Zero parts stacked on escape fields.

**Routing:**

1. Critical short copper by hand: pours, gate/Kelvin, the buck loop, decoupling and GND drops.
2. One **global negotiated-congestion route** of all signals.  Nets route, overlaps are priced, and the whole set
   is re-routed until it is legal.  Report the open count, the overuse map and the via count.
3. If overuse persists, fix the placement or the pins, never patch.
4. The freeze-and-edit loop is for polish only, after 0 open.

## 4. My own lessons (the session lead)

1. **Test the premise before proposing a structural move.**  I proposed moving U2 into the gap on the claim that
   the gate loops would get shorter.  One look at the coordinates showed U2 was already central, and I had to
   correct myself.  Each proposal now comes with the numbers that justify it.
2. **Measure free space per layer and by via sites, never by the outer layers.**  The combined density map made
   the band look empty.  It was the busiest corridor on L3/L4.  The v2 congestion check counts via-site
   availability.
3. **Geometric transforms move the congestion with them.**  The grow, the U1 block move and the cell C move all
   preserved the bad topology.  Only separating stacked blocks, or changing the topology (pins, block order),
   changes routability.
4. **Planes are not overflow space.**  Letting "slow logic" onto L5 as a pressure valve cut up the plane round after
   round.  In v2, L2 carries nothing and L3's lanes are budgeted in the floorplan.
5. **Put design-level questions to the user early.**  The pin swaps, the test pads, the supply jumpers, part sizes
   and J1's position all turned out to be negotiable.  They came up after days of routing, when they should have
   been answered before placement.  v2 brings them to the floorplan review.
6. **Sweeps are not a strategy.**  Generated experiment batches (genl5/genmove/genfence/gentp/genreg) yielded
   ~2-5 %.  They are useful as a final polish, never as the main method.
7. **Tool hygiene:**
   - A lone new via is re-netted by SaveBoard, so give it an anchor stub.
   - `b.Zones()` becomes stale after zone moves.
   - gen_sch re-rolls uuids, so edit sheets in place.
   - The worktree guard blocks computed shell text, so write scripts to files.
   - zsh does not word-split and no-match globs abort.
   - Run long jobs in the background and wait with an until-loop.
   - Memory is limited, so run with J ≤ 2.
   - Leave the frozen board alone while the user has KiCad open.
8. **Subagents and worktrees:** don't switch the session's worktree while agents write files; they follow the
   session.  Give agents absolute paths in the worktree they will stay in.
9. **Keep the project board in sync** with the working state whenever the user may open it, and say which file
   they are looking at.

## 5. Decisions to bring to the user at the floorplan review (none taken yet)

- **Part-size changes** (same circuit and values, different package or part; critique §6, ~300 mm² total):
  - J4 balance connector: XH side-entry to PH/GH or vertical.
  - C1: 10 x 10.5 to 8 x 10, or 2 x 6.3 x 7.7 (ripple rating to check).
  - U6: TSSOP-14 to WQFN-14.
  - J2/J3: right-angle to vertical SH.
  - R300/R400: 1206 to 0603.
  - The eight 10 µF 1206 50 V caps to 0805 35 V.
  - D2/L1: smaller packages if the current allows.

  These are changes to parts, not removals, but they change the BOM, so they are the user's call.
- **A Tag-Connect footprint (or a 5-pad row) for SWD** at the MCU edge.  It would be an added footprint.
- **Where the BMS goes (J4 + U8) and which edge J4 sits on**, given the cable-exit preferences.
- **The mated stack height** (J1 plus the compute board's socket, 4.9-6.0 mm with the current plan).  It sets the
  bottom-side height limit (≤ 1.1 mm parts).
