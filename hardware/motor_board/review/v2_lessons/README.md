# Motor board layout v2: lessons from attempt 1 and the rules for the restart

**Revision 2 (2026-09-29)**, after five adversarial reviews ([adversarial/](adversarial/)).  Their findings were checked
before being taken in.  Section 6 lists what changed from revision 1 and why.

Attempt 1 (branch `worktree-routing`, kept as the backup) reached 13 open connections on 6 layers, 85 x 35 mm, and
did not close.  v2 restarts from the same schematic (rev L1) on **4 layers**, 85 x 35 mm, under the ground rules the
user set on 2026-09-29:

- **Outline:** fixed at 85 x 35 mm.
- **J1** (20-pin 1.27 mm board-to-board header): anywhere on the **bottom**.
- **Hot parts:** on the top side.
- **Parts:** may be moved freely.  **Nothing is removed without asking.**
- **Cable exits (soft preferences):** left drive at the bottom-left (rear-left), right drive at the bottom-right
  (rear-right), weapon at the top-right (read as front-right; to confirm with the user).
- **MCU pins:** may be reassigned freely.  DESIGN.md, CHANGES.md and the pin map are updated with every move.
- **Copper weight:** our call, and weight matters.
- **Layers:** do not propose more.

Detail and evidence:

| File | Scope |
|---|---|
| [design.md](design.md) | Design lessons: clusters, pin assignment, what worked, 6 to 4 layers, checklist |
| [process.md](process.md) | Process and tooling lessons, what the user values |
| [electrical.md](electrical.md) | Currents, loops, Kelvin, thermal, EMC, v1 electrical defects |
| [critique.md](critique.md) | Independent post-mortem with measurements |
| [adversarial/](adversarial/) | factcheck, electrical, floorplan, process, consistency: the reviews of the above |

The files above are kept as written.  **Where they disagree with this page, this page wins.**  Among the known
superseded items: critique §4's floorplan (it does not fit, adversarial/floorplan.md), critique §8's L3 plan, the via
figures, and the TIM1-on-one-edge claim.

## 1. Why attempt 1 did not close

1. **Via sites and inner-layer channels around the MCU ran out; board area did not.**  Growing the board 10 mm
   closed 1 net.  The empty band the grow left was an inner-layer bus corridor, so blocks moved into it could not
   get vias.  The total via count was normal: 304 signal vias for 311 signal connections, 0.98 per connection.  The
   problem was *where* vias were needed.
2. **The MCU pin map was fixed before placement.**  Seven nets leave U1 on the side opposite their load, and the
   weapon-control nets leave from three sides.
3. **The MCU was on the bottom with an unrelated block on top of it.**  The left sensor front end sat over U1's
   fan-out, and both needed the same via sites.
4. **The MCU was off-centre relative to its loads, and U6 was on the wrong side.**  The MCU-to-U4/U10/J3 nets formed
   a bus wall around U2 (v1 had 12 nets plus +3V3 toward U4).  U6 at the far front-left stretched the W_INLx nets to
   38-70 mm.
5. **Inner layers were reserved for power by region.**  The overflow went onto the L5 "GND plane".
6. **Process: routing started with no routability check.**  It then used a sequential router, plus about 31 hours of
   incremental patching that spent the room later fixes needed.

## 2. What is kept from attempt 1

- **The weapon bridge cells:** Q1-Q6, RS1-RS3, C25/C26/C31, NT1-3, JW1-3, a ~4 nH commutation loop.  Kept as a
  block at the front-right.  Where the gate pairs run (L1 inside the cells, or a bottom corridor) is an **open
  decision** (section 5): the files disagree, and nobody has checked that L1 has room.
- **The pack entry block** (JBAT1/2, Q7/Q8, U13, RS4, D1), the connector pin orders, and the circuit, BOM and 3D
  models.
- **The discipline:** DRC 0 and parity 0 at every commit, the ops round log, isolated experiment directories, and
  the diagnostic tools.

## 3. Rules for v2

### 3.1 Stack-up and planes (electrical.md B, corrected by adversarial/electrical.md)

JLC's 4-layer builds with thin prepreg (1080 at 0.069 mm, 3313 at 0.092 mm) are symmetric with a **0.8-1.2 mm core
between L2 and L3**.  **L3 therefore couples to L4, not to L2.**  Everything below follows from that.

- **Default JLC041611-1080** (1.6 mm, 1 oz on all layers).  The inner layers are 30 µm finished, which must be
  specified: JLC's default inner copper is 0.5 oz.  Not 1.2 mm: it saves ~2 g but deflects 2.4x more, against the
  MLCC flex-crack rule next to unfused pack copper.  No 2 oz, because of the weight and the loss of the 0.127 mm logic
  rules.
- **L1:** parts, power pours, pack path, gate/Kelvin/VDRAIN across the power band.
- **L2:** solid GND.  No trace, no jumper.
- **L3:**
  - The VBAT feed pour in the front power band, including an L3 copy of the pre-RS4 pack nets (BAT_IN / PSW_S /
    VBAT_SW) under Q7/Q8.
  - Elsewhere a GND pour, plus few budgeted slow lanes.  Each lane needs GND fill on L4 directly above it.
- **L4:** bottom parts, MCU fan-out, signals, GND fill stitched to L2.
  - **Under the L3 VBAT band, L4 is solid GND with no signals.**  It carries the pack ripple return (~0.35 nH vs ~6 nH
    via L2 alone).
  - **No L4 trace may cross an L3 VBAT/GND boundary.**  A custom DRC or check script enforces this.
  - **No pack-current copper on L4** (it faces the compute board).
- **Via fields must not slot the planes:**
  - Pitch ≥ 1.3 mm at 0.3 mm drill, or unused inner pads removed.
  - Staggered fan-out rows.
  - A plane-integrity check (minimum copper between antipads) is part of the routability gate.
- **Drive-motor VBAT feeds** (C1 to R302/R402 to U3/U4 VM): a planned corridor on L1/L3, poured, ≥ 1 mm.  In v1,
  R402 and U2's buck input hung off a 21 mm, 0.15 mm L4 track.
- **DRV8316 VM bulk caps within 2 mm of their VM pins (DESIGN value).**  This protects the 4 V/µs hot-plug limit.
  Re-run sim_hotplug if placement misses it.
- **Thermal for U3/U4:**
  - One plane makes the effective RθJA ~35-45 °C/W, not the JEDEC 25.7.
  - An L3 GND island of ≥ 10 x 10 mm under each, with no lanes.
  - The thermal copper must not face the compute board, which resolves the E3-09 / rule-15 conflict: no exposed
    bottom pad.
- **Sense loops** (CSA, Kelvin, NTC) stay out from under phase copper **on every layer**.  30 µm planes do not shield
  below ~10 MHz.
- **Order via-in-pad (POFV) and record its price**, or ban it for signals.
- **Before ordering, confirm on the JLC form:** the stack-up name, 1 oz inner copper, and the via-in-pad price.

### 3.2 Floorplan (to be derived fresh, with measurements)

Critique §4's floorplan **does not fit** (adversarial/floorplan.md): the sensor blocks, the buck and the MCU/test strip
are at 129-185 % of their boxes, and the U4 bus runs at 118 % of its channel.  v2 derives its own floorplan with an
**area budget per side and per block** first.  The principles hold:

- Power in the front band, logic in the rear.
- **MCU on top, centred on its loads**, next to U2.
- U6/U14 between the MCU and U2.
- Each sensor front end sits beside its connector, off every IC, as a monotonic chain.  J2/J3 go near their drive
  ICs and cable corners (DESIGN §6.9), not mid-edge.
- **J1 on the bottom where the UART/SWD/NRST/ARM pins face it.**  The ARM charge pump (U14/C15/D9) goes at J1
  pin 19 (design.md), with the safety pull-downs at the receiving end.
- The BMS block is self-contained.
- The drive ICs sit at the rear corners.
- **A reserved channel for the MCU-to-U4 bus** of 12-13 nets.
- Test pads in reachable strips, never in the MCU core.

adversarial/floorplan.md offers an alternative worth starting from: test pads and D1 in the empty front strip, J1
under it, the buck south of U2 as in v1, and the U4 channel at ~64 %.  Its J3-next-to-J2 idea puts the right motor's
cable across the robot and needs the user's OK.

**Placement rules:**

- Parts under an IC are only that IC's own passives, or a self-contained block.  No fan-out over another block's
  fan-out.
- Loop-critical parts stay on their IC's side (DESIGN §6.13).
- Bottom parts respect the stack-gap height agreed with the user.  The ≤ 1.1 mm figure is outdated: v1's bottom
  already has 1.6-3.35 mm parts.
- Two-pin parts are placed by both ends.

### 3.3 MCU pins (co-assigned with the floorplan)

Score pin edge against destination bearing, then check every candidate against all of these:

- **AF legality** (ref/STM32G474RxTx_pins.xml).
- **Peripheral pins that exist on one pin only:**
  - ADC5 is only on PA8/PA9 (the left CSA today).
  - TIM20 CH1/CH2/CH3 are PB2 / PC2 / PC8, on three different edges.
  - The encoder must use CH1/CH2 of one timer.
  - Each CSA needs its ADC/COMP.
  - Simultaneous ADC1/ADC2 sampling pairs.
- **Reset and boot states:**
  - The ROM UART bootloader on PA9/PA10.
  - PA13/PA14/PA15/PB4 have reset pull-ups/pull-downs.
  - PB4/PB6 have dead-battery pull-downs.
  - PB8 is BOOT0.
  - PC13-PC15 are weak drivers (30 pF).
  - No weapon-control pin may glitch through boot.
- **DRV_OFF:** a single pull-up must not leave a driver enabled if a branch breaks.  Check PC14's load.

Useful options:

- USART1 on PB6/PB7 (the J1-facing edge in v1).
- Grouping TIM1 on pins 35-44 is **not free**: it takes PA8/PA9 from ADC5 and PB13 from R_SOB_F.

Expect a handful of unavoidable wrap-arounds.  Present the pin map to the user before placement is finalised
(firmware contract).

### 3.4 Vias

- **Signal vias ≤ ~1 per connection** (v1 was already at 0.98; the target is placement that lets the vias land
  outside the congested areas).
- Count stitching vias (one per signal via changing reference) in the budget.
- GND pads: a via each where the pad is not on a solid L1 GND pour.  This is not a blanket rule, because it spends
  scarce sites.

### 3.5 Rails

- **+5V** (buck at U2) and **+3V3** (U5) are planned trunks.
- **R20's +5V sense closes at C29/C30 at placement time.**  Open in v1, it would run the buck open-loop.
- Custom DRC minimum widths per power net class.

## 4. Workflow for v2 (revised per adversarial/process.md)

- **P0.  Freeze the inputs with the user:**
  - Part-size decisions.
  - Gate-corridor choice.
  - Stack-gap height.
  - J3 location option.
  - Confirmation of the weapon exit.
  - Fab and assembly facts: the JLC form, via-in-pad, two-sided assembly, panel rails and fiducials.
- **P1.  Floorplan + MCU pin assignment** with a per-side area budget.  **User checkpoint.**
- **P2.  Routability gate:** a **coarse global router on 0.5-1 mm tiles** (numpy, seconds per run).  It models:
  - per-tile track capacity per layer, with L2 at 0 and L3 lanes consuming L4 above;
  - per-tile via capacity;
  - the plane-integrity check.

  It is validated by reproducing v1's failure around the MCU.  The gate is no tile over capacity.
- **P3.  By hand:** MCU and QFN escape patterns, power pours, gate/Kelvin pairs, the buck loop, decoupling.
- **P4.  Detailed routing, time-boxed.**
  - Either the existing router confined to the global router's corridors, or Freerouting after a verified KiCad rule
    round-trip on this clean placement.  (It never had a fair trial in v1.)
  - DRC after every run; zone refill and island check.
  - If it stalls above ~10 opens, go back to P1/P2.
- **P5.  Finish ≤ ~10 opens by hand** (KiCad interactive or scripted ops).  Freeze-and-edit for polish only.
- **P6.  Close-out:** plane integrity, via-in-pad list, JLC DFM, assembly (two-sided, THT J4), silkscreen, D3
  visibility.
- **Time boxes:**
  - The global router: 1 day.
  - If a phase runs past 2x its estimate, or flat for 3 iterations, report with measurements and one
    recommendation.
- **No mandatory custom detailed router.**  The user's preference is professional hand-style routing.

## 5. Decisions for the user (before P1)

1. **Part sizes (same circuit, different package or part).**  The floorplan review says U6, D2/L1 and J4 are
   effectively needed:
   - U6: TSSOP-14 to WQFN-14.
   - D2/L1: SMA/5040 to SOD-123F/4030, if the current allows.
   - J4: XH side-entry to PH/GH or vertical.
   - C1: 10 x 10.5 to smaller, after the ripple and hot-plug sims.
   - J2/J3: right-angle to vertical SH.
   - R300/R400: 1206 to 0603.
   - 8 x 10 µF 1206 50 V to 0805 35 V.

   Each change gets a pin-to-pad check.
2. **Gate corridor:** gate/Kelvin pairs on L1 inside the bridge cells, or a bottom corridor under the cells.
3. **Stack-gap height** (the mated J1 + socket, 4.9-6.0 mm today) and the height limit for bottom parts.
4. **J3 location:** near U4 at the rear-right (short motor cable), or next to J2 (shorter logic, with the cable
   across the robot).
5. **Weapon exit** "top-right" means front-right (drum side).
6. **Test pads:** stay as TP1-TP12.  Nothing is replaced by a Tag-Connect unless the user asks.
7. **Compute-board implications of where J1 goes:**
   - The compute board mirrors J1.
   - The Pico W antenna and USB overhang this board's outline, since there is no notch.
   - Keep-outs under the bottom wire joints.

## 6. Revision 1 to revision 2: what changed and why

| Revision 1 said | Revision 2 | Source |
|---|---|---|
| Vias 2.2 per signal connection, target 1.1 | 0.98 per connection in v1; it was the location, not the count | factcheck (my ratio mixed GND/VBAT vias into it) |
| TIM1 on pins 35-44, free | Costs ADC5 (PA8/PA9 only) and R_SOB_F; TIM20 is single-pin per channel | factcheck, floorplan, consistency |
| L3 plans reasoned as if coupled to L2 | L3 couples to L4 (thick core), hence the L4-under-band GND, boundary and slot rules | adversarial/electrical |
| 1.2 mm optional | 1.6 mm default | adversarial/electrical |
| Critique §4 floorplan as the plan | Does not fit; derive fresh with an area budget and a reserved U4 channel | adversarial/floorplan |
| A custom negotiated detailed router | A coarse global router as the gate; detail by hand, confined routing or Freerouting; ≤ 10 opens by hand | adversarial/process |
| Pin rules: AF + encoder + CSA | Plus reset/boot states, single-pin peripherals, ADC sampling pairs, DRV_OFF | consistency |
| GND via per pad, always | Only where not on a solid L1 GND pour | consistency |
| Bottom parts ≤ 1.1 mm | Height per the agreed stack gap | factcheck, consistency |
| Tag-Connect instead of TP2-TP4 | TPs stay; no removals without asking | consistency |
| DRV8316 caps ≤ 3 mm | ≤ 2 mm (DESIGN) | consistency |
| ARM circuit by U2 | At J1 pin 19 | consistency, floorplan |
| "4 days of patching" | ~31 h per git | factcheck |
| W_INLx 58-70 mm | 38-70 mm measured | factcheck |

## 7. My own lessons (the session lead)

1. **Test the premise before proposing a structural move.**  The U2-into-the-gap proposal was wrong on its own
   premise.  So was my "2.2 vias per connection", which divided all vias by signal connections.  Each proposal now
   comes with checked numbers.
2. **Judge free space per layer and by via sites, never by the outer layers.**
3. **Geometric transforms move congestion with them.**  Only separating stacked blocks or changing the topology
   helps.
4. **Planes are not overflow space.**
5. **Put design-level questions to the user early:** pins, parts, test pads, jumpers, J1.
6. **Sweeps are polish, not a strategy.**
7. **Tool hygiene:**
   - A lone new via is re-netted by SaveBoard, so give it an anchor stub.
   - `b.Zones()` is stale after zone moves.
   - gen_sch re-rolls uuids.
   - The worktree guard: put scripts in files.
   - zsh does not word-split, and no-match globs abort.
   - Run long jobs in the background with until-loops, J ≤ 2 on memory.
8. **Subagents follow the session's worktree.**  Don't switch worktrees while they run.  Give them absolute paths
   in the worktree they will stay in.
9. **Keep the project board in sync** when the user may open it, and never write the board while KiCad has it open.
10. **Adversarial review of my own synthesis paid off**: it caught four errors that would have steered the restart
    wrong.
