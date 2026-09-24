# Review round 6 / D: system-level adversarial review (rev F)

Reviewer role: power electronics and combat robotics, fresh eyes on the whole package.  No design
file was edited.

Inputs: DESIGN.md rev F (read end to end), design/calcs.md, design/nets.md, design/bom.csv,
BOM.md, spice/*.out, review/CHANGES.md, review/round5_d_system.md, `motor_board.py` (`PARTS`,
imported to count footprints), KiCad 8 stock footprint courtyards (`/usr/share/kicad/footprints`),
chassis meshes `models/Chassis - Main Chassis.3mf` (v1) and
`models/v1.1/Chassis - Main Chassis_inland_tough_pla.3mf` read with
`hardware/tools/mech/chassis.py` (`load`, `raster_floor`, 0.5 mm cells),
`hardware/mech/board_outline.json`, datasheets AP2112K, MT6701.

Evidence tags: **[D §x]** DESIGN.md, **[C §x]** calcs.md, **[N]** nets.md, **[B]** bom.csv /
`PARTS`, **[M]** chassis mesh, **[K]** KiCad courtyard, **[DS …]** datasheet.

---

## 1. Area budget with real courtyards

### 1.1 What the parts need

KiCad F.CrtYd bounding boxes of the footprints in `PARTS` [K].  Custom footprints are estimated
from their lands: J1 ≈ 7.5 × 13.2, RS1–RS3 ≈ 7.7 × 3.9, U3/U4 ≈ 6.1 × 8.1, J2/J3 ≈ 10 × 5.5,
TP 1.5 × 1.5.  MH = Ø2.2 hole plus the M2 nylon standoff/nut, ≈ 5.5 × 5.5 on **both** sides.

All courtyards: **≈ 2410 mm²** (+ 120 MH on the second side).  That agrees with round 5 (2430).

Parts that must stay on the top under DESIGN's own rules: §6.13 (loop-critical parts on their IC's
side, bottom ≤ 1.2 mm) and §6.1/§6.5–6.7:

| Top group | mm² |
|---|---|
| Q1–Q8 PDFN 5×6 (7.3 × 5.8) | 339 |
| RS1–RS4 | 120 |
| C1 (13.5 × 11.0) | 149 |
| **U1 LQFP-64 (13.4 × 13.4; 1.6 mm tall, so not bottom; §6.13 assigns it to neither side)** | 180 |
| U2 VQFN-48 + U3/U4 VQFN-40 | 170 |
| DRV8316 decoupling/CP/AVDD/CBK loop ×2 (3 × 1206, 5 × 0603, 0805, 2 × 0402 each) | 126 |
| DRV8323 CP/DVDD/VREF, straps R44–R46 (≤ 2 mm from pins), buck loop C27–C30, R20/R21, L1, D2 | 107 |
| C25/C26/C31, D1 | 65 |
| J2/J3 + J4 | 309 |
| 5 × SolderWire-1.5sqmm + 6 × 0.5sqmm | 200 |
| MH1–MH4 | 120 |
| CSA/ADC filters at U1 (R70–R82, C80–C92, C41–C43) | 25 |
| D3 | 4 |
| **Top total** | **≈ 1910** |
| Bottom (everything else incl. J1, TPs, MH) | ≈ 730 |

DESIGN §4 says top ≈ **1500** and bottom ≈ 900.  The totals agree; the split does not.  The ~410 mm²
difference is U1 (180) plus the DRV/buck loop passives (~230).  §6.13's own rules keep those on
the top.  The top side sets the board size.

Mating envelopes are missing from the budget.  A mated SH plug plus its cable bend needs ≈ 8 × 7 mm
in front of J2/J3.  The XH plug plus its wires needs ≈ 12.5 × 12 mm in front of J4.  The v1.1 bay
walls are 1 mm from the board edge, so these connectors must face inward, and that envelope has to
stay clear of parts on the top: **≈ +270 mm²**.  The compute board also needs relief in the motor
board for the Pico W antenna (§3.5 item 6) and probably for its USB plug (§5 R6D-11).  That is
≈ 200–400 mm² of outline that holds nothing.

### 1.2 What the chassis offers (measured)

Floor region at Z ≤ 2.6 mm, connected to the bay, necks excluded, eroded by the 1 mm wall
clearance [M]:

| Chassis | Main bay | Shape |
|---|---|---|
| v1 | **3495 mm²** (board_outline.json: 3447) | 106.5 wide × 19 mm full-width strip, 86.5 wide elsewhere, 37.5 deep |
| v1.1 | **3077 mm²** (−12 %; the "−17 %" in §6.13 counted the necks) | 109.5 wide for only **14.5 mm**, 89.5 wide elsewhere, ~34.5 deep; corner blocks with 14 mm lid bosses; the neck is cut by a full-height rib at y ≈ 145.5 and the switch mount (z ≈ 15) |

The free area stays 3077 mm² up to z = 13.5 mm, so nothing in the v1.1 bay intrudes at the height
of the stacked board.

### 1.3 Fit

| Case | Top need (courtyards + mating) | Board at 60 % / 50 % use | v1.1 (3077 − ~200 antenna ≈ 2880) |
|---|---|---|---|
| As specified (5×6 FETs, cell monitor fitted) | ≈ 2180 | 3630 / 4360 | **does not fit (26–51 % over)** |
| Fight-build DNP (−J4 block, −its mating) | ≈ 1830 | 3050 / 3660 | does not fit |
| DNP + 3.3×3.3 FETs (8 × ~17.6 vs 42.3 mm²) | ≈ 1630 | 2720 / 3260 | fits only at ≥ ~57 % top-side use |

**Answer:** the §6.13 budget is optimistic by ~27 % on the side that limits the board.  As
specified, the board does not plausibly fit the v1.1 bay.  It fits only with **both** §6.13
levers applied and a dense power side.  So the levers are prerequisites, not fallbacks.

## 2. Mass

FR-4 at 1.85 g/cm³ × 0.16 cm = **0.30 g/cm²**.  4 × 35 µm Cu at ~70 % mean fill is 0.09 g/cm², and
mask/silk ≈ 0.02 g/cm².  That gives **≈ 0.39–0.41 g/cm² = 3.9–4.1 g per 1000 mm²**.  §4 says
"0.9 g per 1000 mm²".  That is the laminate of a 0.5 mm board, and 3.3–4.5× too low for a 1.6 mm,
4-layer board.

| Item | g |
|---|---|
| PCB, 2900–3600 mm² (the §1.3 range that can fit) | 11.5–14.5 |
| Parts (§4's own 6–8; round 5 itemised 5.3) | 5.5–8 |
| Solder | ~0.8 |
| **Motor board** | **≈ 18–23** (§4: 12–15) |
| + off-board wiring/switch/nylon ~6.5 + compute board 8–12 | stack **≈ 32–42 g** vs the ≤ 40 g target |

"1.2 mm saves ~0.7 g" is really 0.4 mm × 1.85 g/cm³ × ~30 cm² ≈ **2.2 g**.

---

## 3. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| **R6D-01** | **MAJOR** | Area budget / fit (the R5D-01 fix is numerically wrong) | **The §4/§6.13 area budget puts ~410 mm² of top-only parts on the bottom, leaves out the connector mating envelopes, and so claims a fit that the numbers do not support.**  Top courtyards are ≈ 1910 mm², not 1500 mm².  The difference is U1 (LQFP-64, 1.6 mm tall, not assigned to either side in §6.13) and the DRV8316/DRV8323/buck loop passives that §6.13 itself keeps on their IC's side.  With the mating zones (≈ 270 mm²), the board needs **3600–4400 mm²** at the budget's own 50–60 % use.  The measured v1.1 main bay is **3077 mm²** (≈ 2880 after the antenna relief).  Only "fight-build DNP **and** 3.3 × 3.3 FETs" gets to 2700–3300 mm².  §1 "Build: fits the chassis bay" is stated as met | §1.1–1.3 above; [K] courtyards; [M] v1.1 raster; [D §1] Build row, [D §4] area row, [D §6.13], [D §6.9] "J2/J3 at the board edge" | Decide both levers **before** drawing, because they change the netlist, BOM, calcs and bridge sim (a 3.3 × 3.3 40 V FET has a different RDS, Qgd and SOA).  Or enlarge the v1.1 bay.  Correct §4/§6.13: top ≈ 1.9k mm², U1 on top, mating envelopes and antenna/USB relief listed, v1.1 bay = 3077 mm² (−12 %).  Change §1 to "fits only with …" |
| R6D-02 | MINOR | Mass (§4) | **The laminate figure is 3.3–4.5× too low**, so the board mass is understated by ~6–8 g.  0.9 g per 1000 mm² is what a 0.5 mm board weighs.  1.6 mm FR-4 alone is 3.0 g per 1000 mm²; with 4 × 1 oz and mask it is ≈ 3.9–4.1 g.  Motor board ≈ **18–23 g**, not 12–15.  The stack comes to ≈ 32–42 g vs the ≤ 40 g target.  "1.2 mm saves ~0.7 g" is ≈ 2.2 g | §2 above; [D §4] mass row; DESIGN_REQUIREMENTS C-2 | Fix the §4 row.  Consider 1.2 mm at order time (keep the §6.10 orientation rule) |
| R6D-03 | MINOR | Doc contradiction (two-sided) | **§3.5 still says "J1 is the only part on the bottom side … everything else is on top"**, and it still offers "hand-solder it / a through-hole 1.27 mm header is the cheaper alternative".  BOM.md J1 row: "JLC second side or hand-solder".  Rev F makes the bottom side carry ~100 parts [D §1, §6.13].  JLC second-side assembly is now mandatory, and the hand-solder/THT options no longer save anything.  A THT J1 would also put 20 pin stubs on the crowded top | [D §3.5] l.316–321; BOM.md l.35; [D §1] Build row; [D §6.13] | Rewrite §3.5's J1 paragraph and the BOM.md J1 row for the two-sided build.  Drop the hand-solder alternative |
| R6D-04 | MINOR | Stack clearance / bottom-side parts | **The 4.9–6.0 mm stack gap is budgeted twice.**  §3.5 item 7 gives the whole gap to compute-board parts.  §6.13 now puts ≤ 1.2 mm parts on the motor board's underside.  With the Pico's parts at ~3.6 mm (round 5 §1.1) and the 4.9 mm socket, the clearance is **4.9 − 3.6 − 1.2 = 0.1 mm**.  That is contact under impact.  Some parts §6.13 sends to the bottom also exceed 1.2 mm: **U5 AP2112K SOT-25 is 1.00–1.30 mm** [DS AP2112K, dim K]; **C9** (C29823, a Samsung CL31 "H" code 1206 4.7 µF 50 V) is **1.6 mm**; D4/D5 SOD-123 are ~1.35 mm.  U13 on the bottom also brings **BAT_IN**, unswitched and unfused pack +, onto the face that touches the compute board | [D §3.5] item 7; [D §6.13]; [N] U13 VS = BAT_IN, C14; [B] C9 C29823 | §3.5 item 7: gap ≥ compute parts + 1.2 mm + ≥ 1 mm clearance (i.e. the 6.0 mm or a taller socket), or a bottom keep-out over the Pico footprint.  §6.13: list max heights per part and put C9/D4/D5/U5 on top (≈ +45 mm²).  Keep BAT_IN/VBAT copper off the bottom inside the compute-board footprint |
| R6D-05 | MINOR | Bring-up (§9 step 3) | **The safety-path tests cannot be run as written on the two-sided board.**  §6.13 puts the TPs on the bottom, which faces the compute board 5–6 mm away.  Step 3 needs the compute board connected (W_ARM_CLK, and "W_ARM_S via the heartbeat") **and** a scope on TP6–TP9 at the same time.  With the stack assembled the TPs cannot be reached; unstacked, J1 has no mate.  Step 2's "SWD … TP pads" has the same problem | [D §6.13] "bottom = … TPs"; [D §9] steps 2–3; [N] TP6 = W_ARM | Put TP1–TP12 (or at least TP6–TP9 plus SWD) on the top.  Or specify a bring-up jumper: a 1.27 mm 2 × 10 IDC ribbon between J1 and the compute-board socket, and say so in §9 |
| R6D-06 | MINOR | Safety: compute-board hang | **The toggle contract does not catch the most common hang: the main loop stuck while interrupts still run.**  §3.5 item 4 has the ISR toggle "gated by a flag the main loop sets".  A flag that stays set keeps W_ARM_CLK toggling after the main loop dies (for example a BTstack/CYW43 deadlock on core 0).  §2's "a hung compute board disarms the weapon by itself" is then false, and only the motor MCU's command timeout remains.  That timeout is also defeatable: §8 counts any "valid frame" (CRC + sequence number) but never requires the sequence number to **advance**, so a DMA or ISR re-sending a stale frame keeps the weapon running | [D §2] ARM bullet; [D §3.5] item 4; [D §8] command-link row | §3.5: the ISR toggles only while `now < deadline`, and the main loop writes `deadline = now + ~20 ms` after it has done all its checks (a deadline, not a latched flag).  §8: a frame is valid only if its CRC is good **and** its sequence number advanced; a repeated number counts as no frame |
| R6D-07 | MINOR | Safety: radio-loss latency | **Signal-loss-to-stop latency is unbounded.**  §3.5 item 4 lets the "radio link fresh" timeout exceed the controller's report interval "because some controllers only send on change".  For such a controller the only link-loss signal is the Bluetooth supervision timeout.  For BR/EDR that defaults to 0x7D00 slots = **20 s** unless the host shortens it.  Out of range, the robot keeps its last drive and weapon command until then.  Event rules require a prompt failsafe | [D §3.5] item 4; Bluetooth Core spec HCI default Link_Supervision_Timeout 0x7D00 | Require a controller that streams reports (e.g. ≥ 50 Hz), or have the compute board write a link supervision timeout of ≤ ~250–500 ms.  State a maximum radio-loss-to-disarm time (e.g. ≤ 0.5 s) in §1/§3.5 and test it in §9 (switch the controller off) |
| R6D-08 | NOTE | Doc consistency (ARM gap) | §3.2 says "a gap in the toggling of up to ~50 ms is tolerated", and §3.5 item 4 says "(≥ 50 ms disarms)".  arm.out gives a 52 ms minimum nominal, and ~30–200 ms with tolerances (§3.2, §9).  With tolerances a gap of ~30 ms can disarm, and a 50 ms gap does not reliably disarm | [D §3.2, §3.5 item 4]; spice/arm.out | "Gaps > ~30 ms may disarm; ≥ ~200 ms always disarms; design for ≤ 20 ms" |
| R6D-09 | NOTE | Bring-up (§9 steps 5–6) | (a) There is no MT6701 step.  The firmware assumes ABZ mode, 1024 PPR (ABZ_RES = 0x3FF) and a known DIR [D §8 timer inputs, C §8], and the part is programmed off-board [D §3.3].  Verify/program it before step 5.  (b) Steps 5–6 do not name the supply.  Step 1 leaves the bench supply at 0.2 A, but step 6 goes to a 20 A weapon limit (22 A pack peak): that needs a LiPo (plus a fuse/smoke-stopper for the first run) | [D §9]; [DS MT6701] ABZ_MUX/ABZ_RES/DIR registers | Add "5a. program/verify each MT6701: ABZ, 1024 PPR, DIR", and "6: from a 4S pack through the XT30/switch" |
| R6D-10 | NOTE | Availability single point of failure | **The weapon stage's gate driver U2 makes the 5 V for the whole robot** (MCU, sensors, compute board, radio).  A weapon-stage failure that damages U2 (e.g. the §5 case of SHx < −7 V with a long loop, or a shoot-through) makes the robot immobile and unresponsive, not just weaponless.  This fails safe (everything coasts) but it decides matches, and §7 does not list it | [D §2] "The weapon driver also makes the 5 V rail"; [D §5] bridge row; [D §7] | Add a §7 residual (or accept the separate buck the §2 bullet rejected) |
| R6D-11 | NOTE | Compute-board mechanics | §3.5 item 6 asks for antenna relief, but the Pico W's micro-USB is at the other end of the module.  A micro-B overmold (~7 mm thick, centred ~2.5 mm above the carrier) is taller than the 4.9–6.0 mm gap.  A plug inserted under the motor board's edge collides with it.  That end needs relief too, or USB is unusable with the stack assembled | [D §3.5] items 6–7 | Add to item 7: USB plug access (relief or at the stack's edge); count it in the §6.13 outline losses |

## 4. Checked and found consistent (no finding)

* §5 vs spice/*.out: hotplug (0.003–0.009 V/µs, 16.4/21.5 W, re-close 0.12–2.2 V/µs, worst
  3.38 V/µs), ARM (52–134 / 67–164 ms, 7–10 edges, 12 ms at 500 Hz), spin-up and bridge rows all
  match their .out files.
* §1 counts: 188 assembled + 6 DNP, 62 BOM lines match `PARTS`/bom.csv.
* ARM pickup from switching nodes: a 5 pF stray from a 16.8 V edge moves 84 pC/edge.  At 48 k
  edges/s that is ≈ 4 µA against the R41 bleed of ≈ 43 µA at 2 V, so no edge coupling can arm it.
* Stack height in v1.1: the motor board top is ≈ 13–14 mm; with C1 on top the stack reaches ≈ 24–25 mm, under the
  32.6 mm walls.  Nothing in the bay above the floor up to z = 13.5 mm (the free area is unchanged).
* Idle draw for §9 step 1 "< 60 mA" at 12 V (2 × DRV8316 awake + unprogrammed MCU + dividers +
  R15 ≈ 45 mA): plausible.
* §6.2/§6.10 stack-up contradiction (R5D-03) fixed; §7.17/§7.18 match §8 and calcs §9.

## 5. Weapon safety chain: single points of failure (rev F)

| Single fault | Effect | Covered / documented |
|---|---|---|
| U14 Y stuck high | Hardware gate and firmware check both see ARM | §7.16 (documented); command timeout remains |
| Compute main loop hung, ISR alive | ARM keeps toggling | **Not covered as specified** (R6D-06); the motor MCU timeout covers it only if frames stop or their sequence numbers stop advancing |
| Radio lost with an on-change controller | Robot keeps its last command for up to the BT supervision timeout | **Not documented** (R6D-07) |
| BAT_IN on the bottom touching the compute board | Unfused pack short through a thin trace | **Not documented** (R6D-04) |
| U2 damaged by a weapon fault | Whole robot dead (fails safe) | **Not documented** (R6D-10) |
| C15/R41/C16/U14 static faults, U6 gate, Q7/Q8 short | — | §7.16 |

## 6. Summary

| ID | Sev | One line |
|---|---|---|
| R6D-01 | MAJOR | Area budget moves U1 and the loop passives (~410 mm²) to the bottom and omits connector mating: top ≈ 1910 mm² → 3600–4400 mm² board vs a measured 3077 mm² v1.1 bay; fits only with DNP + 3.3×3.3 FETs, so decide those before drawing |
| R6D-02 | MINOR | §4 laminate 0.9 g/1000 mm² is 3.3–4.5× low; board ≈ 18–23 g, stack ≈ 32–42 g vs 40 g; 1.2 mm saves ~2.2 g, not 0.7 |
| R6D-03 | MINOR | §3.5/BOM.md still say J1 is the only bottom part and offer hand-solder/THT J1, which contradicts the two-sided rev F |
| R6D-04 | MINOR | Stack gap budgeted twice (0.1 mm left with the 4.9 mm socket); U5 (1.3 mm), C9 (1.6 mm), D4/D5 (1.35 mm) exceed the 1.2 mm bottom limit; unfused BAT_IN on the bottom face |
| R6D-05 | MINOR | TPs on the bottom face the compute board: §9 step 3 (scope TP6–TP9 + heartbeat) is impossible without a ribbon jumper or top-side TPs |
| R6D-06 | MINOR | ISR "gated by a flag" keeps ARM alive when the compute main loop hangs; "valid frame" does not require an advancing sequence number |
| R6D-07 | MINOR | Radio-loss failsafe latency unbounded for on-change controllers (BR/EDR supervision timeout default 20 s); specify ≤ 0.5 s and test it |
| R6D-08 | NOTE | "Up to ~50 ms tolerated" / "≥ 50 ms disarms" vs ~30–200 ms with tolerances |
| R6D-09 | NOTE | §9 lacks MT6701 programming/verification and the supply for the 20 A weapon step |
| R6D-10 | NOTE | U2 failure kills the robot's 5 V (fails safe but decides matches); not in §7 |
| R6D-11 | NOTE | Pico W USB plug end needs relief like the antenna end |

**Verdict: 0 BLOCKER, 1 MAJOR, 6 MINOR, 4 NOTE. Not clean.**
