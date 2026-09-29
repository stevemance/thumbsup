# v2 lessons: electrical, power integrity, thermal, EMC and stack-up (4 layers, 85 x 35 mm)

Sources: DESIGN.md (§3, §4, §6), design/calcs.md, FAB.md, PLACEMENT.md, ROUTING_PLAN.md, review/round3_e_system.md
(E3-04, E3-09, E3-10), review/round2_a_weapon_power.md (R2A-04), review/r2_drive.md (D-08), and a read-only pcbnew
query of the current 6-layer board (`kicad/motor_board/motor_board.kicad_pcb` in worktree-routing, called "v1-6L"
below). Coordinates are in the PLACEMENT.md frame (origin at the front-left corner).

## A. Current levels (design numbers)

| Path | Continuous / typical | Peak / fault | Source |
|---|---|---|---|
| Pack: BAT_IN → Q7 → Q8 → RS4 → VBAT → C1, and the GND return to JBAT2 | ~3–4 A (drives 2 × 1.5 A + logic); ~9–10 A rms over a match (22 A at ~15 % duty) | 22 A for 0.5 s (27 A at a 25 A weapon limit); INA239 SOVL trip 38 A | calcs §7, §9, §11 |
| Weapon phases (Q1–Q6, RS1–RS3, JW1–3) | 20 A current limit | 30–60 A comparator fast trip; 62–93 A VDS-OCP backstop (4 µs deglitch) | DESIGN §3.2 |
| Weapon bus-cap ripple | ~8 A rms shared by C1 and C25/C26/C31 (bursts < 1 s) | — | calcs §7 |
| Drive VM per channel (R302/R402 → L_VM/R_VM) | 1–1.5 A rms (traction limit), ≤ 2 A rms continuous | 8 A (0.8 V across R302); DRV8316 OCP at 16–24 A | DESIGN §3.3, calcs §5 |
| Drive outputs (JL/JR) | as VM | as VM | — |
| Buck (U2 LMR16006, 0.7 MHz) | VIN ~0.18 A average; +5V ≤ 0.6 A (≤ 0.45 A to J1) | 0.71 A inductor peak; 1.2–1.7 A into a shorted output (D2 carries it) | calcs §3 |
| +3V3 (U5) | ~120 mA | sensor switches limit at 100–200 mA | calcs §4 |
| Dissipation | U3/U4 0.9–1.35 W typ (worst 1.96 W at 1.5 A); weapon FET 0.84 + 1.1 W per switching FET in bursts; shunts 0.8 W; Q7+Q8 2.0–2.5 W at 22 A; R302/R402 0.25 W avg, ≤ 1 W bursts; board ~4.4 W average | Q7 16–22 W for ~8 ms at every switch-on (54–57 mJ) | calcs §5, §6, §9, §11 |

## B. Recommended 4-layer stack-up (JLCPCB)

| Layer | Copper | Job |
|---|---|---|
| L1 top | 1 oz | all power parts; the pack path, the bridge VBAT / phase / shunt-GND pours; gate + Kelvin pairs where possible; local hookups |
| prepreg | **thin, ~0.08–0.10 mm** (JLC's 1080 or 3313 build; **not** the 7628 0.21 mm default) | |
| L2 | **1 oz** | **solid GND, never cut, no traces, no jumpers** |
| core | ~1.2 mm | |
| L3 | **1 oz** | **regional**: VBAT feed pour in the front power band; **GND pour everywhere else** (under U1, under U3/U4/U2's thermal pads, under the L4 gate/Kelvin, CSA and SPI runs); few slow lanes, only where no L4 signal runs above |
| prepreg | thin, ~0.08–0.10 mm | |
| L4 bottom | 1 oz | bottom parts, MCU fan-out, signals, GND fill stitched to L2/L3; **no pack-current copper** (DESIGN §6.10) |

Why:
- **Thin L1–L2** keeps the weapon commutation loop down. PLACEMENT §3 estimated ~4 nH at 0.21 mm, with ~70 % of it in the parts. The SPICE limit is ≤ 6 nH, target 3 nH, and at 12 nH SHx reaches −7.3 V against the −7 V abs max (DESIGN §5). The 6-layer order used a 0.069 mm L1–L2 for this reason (FAB.md).
- **Thin L3–L4** because L4 signals (MCU fan-out, gate/Kelvin pairs, CSA lines) take L3 as their reference. L3 therefore has to be GND wherever those signals run.
- **1 oz inner copper has to be ordered explicitly.** JLC's default inner copper is 0.5 oz. At 0.5 oz the pack return drops 20–45 mV across 1–2 squares, which is a 0.5 A weapon CSA error or 0.13 A of drive error (E3-04). 1 oz is 0.49 mΩ/sq and 0.5 oz is 0.98 mΩ/sq.
- **1 oz outer, not 2 oz.** U1 (LQFP-64, 0.2 mm pad gaps), U2 (0.5 mm-pitch QFN-48) and U3/U4 (VQFN-40) need fine etch. 2 oz outer copper raises JLC's minimum trace and space (confirm the value on the order form) and adds mass. Instead, the pack current gets its capacity from L1 and L3 pours in parallel plus via fields (rule 2).
- The stack-up **names change** at JLC (FAB.md). Confirm on the order form: 1.6 mm (or 1.2 mm, which saves ~2–3 g per DESIGN §4), 1 oz / 1 oz, and the thin prepreg on both outer pairs. Set the same stack in KiCad; set_stackup.py / base_edits.STACKUP6 need a STACKUP4.
- **Via-in-pad** (filled and capped) was free on the 6-layer JLC order (FAB.md). On 4 layers it may cost extra. The thermal-pad vias need it. If it is not ordered, use 0.2–0.25 mm drills tented on the bottom and a windowed paste on the pad (≤ 60 %) to limit solder wicking.
- **Alternative (not preferred):** L3 as all-GND with VBAT on L1 only. L1 in the bridge band is already full of FETs, shunts and caps, so a wide enough VBAT feed does not fit. Masked VBAT copper on L4 facing the compute board would break DESIGN §6.10.

## C. Requirements and lessons

**1. L2 is the one ground reference and is never cut.** *Evidence:* DESIGN §6.2 ("one solid, unsplit GND plane… no separate analog/power grounds"); ROUTING_PLAN kept L2 unbroken and put its slots in L5 instead. *v2 rule:* L2 has no tracks. Check it after pour for **antipad chains**: the VBAT via fields at the bridge cells, RS4 and C1 can merge their clearances into slots under the commutation loops. Keep a ≥ 0.3 mm copper web between the antipads in every via field.

**2. Pack path sizing.** *Evidence:* v1-6L carries the pack path on L1 (BAT_IN 35 mm², VBAT_SW 36 mm², VBAT 194 mm²) and on an L3 VBAT feed of 673 mm² (x 21–83, y 1.5–18). The L1-to-L3 via counts were **C1 2**, RS4 10, C25 5, C26 6 and C31 11 vias of 0.3 mm. *v2 rule:* design the path for ~10 A rms with 27 A bursts. The combined L1 + L3 width along the path is ≥ 5 mm per layer, which is ~1.5 mΩ over 30 mm with both layers in parallel: ~33 mV at 22 A. Count ~1 A per 0.3 mm via, so use ≥ 20 vias between the L1 pack pour and the L3 feed at RS4/C1, and **≥ 10–12 at each cell** (at the high-side drain tab and the cell cap). Wire holes JBAT1/JBAT2/JW1–3 get ≥ 4 × 1 mm thermal spokes on every connected layer (DESIGN §6.9).

**3. The pack return stays out of the logic.** *Evidence:* E3-04 predicted 20–45 mV of offset. The placement review's 2-D solve of L2 gave 1–4 mV at the MCU, the CSA filters and J1, because the power stage runs along the front and the logic sits at the rear (PLACEMENT §8). *v2 rule:* keep the same front/rear split, in the order the current flows: JBAT → Q7/Q8 → RS4 → C1 → bridge along the front edge; U1, U2's logic side, U5 and J1 at the rear. Re-run the plane-drop solve on the v2 L2 (there is no L5 any more to share the return). Tie J1's GND pins to the plane at the logic end only. MH1–MH4 stay NPTH, because metal standoffs would make a second ground path.

**4. Weapon commutation loop ≤ 6 nH (target 3 nH).** *Evidence:* DESIGN §6.1 and §5, sim_weapon_bridge. *v2 rule:* keep the PLACEMENT §3 U-cell: HS drain tab → C25/C26/C31 → shunt GND pad → LS source, all on L1 directly over L2. The cap's GND pad sits ≤ 0.75 mm from the shunt's GND pad. Both pads get vias to L2 (RS2 had 8 in-pad vias; give RS1–RS3 ≥ 6–8 each). There is no VBAT or signal copper on L2, and none between L1 and L2.

**5. Gate drive loops.** *Evidence:* the gate runs are 10–28 mm pin to pin (PLACEMENT §5.3). v1-6L put GHx/GLx on L6 at 0.25 mm over the L5 GND. IDRIVE is 60/120 mA with no gate resistors. *v2 rule:* route each gate with its return as a tight pair on the same layer: GHx with SHx, GLx with SLx. Put the via at the gate pin and change layer at most once, with the pair's vias adjacent. Low sides go on L1 through the gap between the shunt pads. On L4 the pairs need **GND on L3 underneath**. **Conflict to resolve at placement:** in v1-6L the L3 VBAT feed (y 1.5–18) sat right under the gate/Kelvin corridor (x 34.5–70.5, y 8.5–19). Either carve an L3 GND strip under the corridor while keeping the feed width elsewhere, or keep the pairs on L1.

**6. Shunt Kelvin and VDS sensing.** *Evidence:* DESIGN §3.2 and §6.3; NT1–NT3. SPx peaks at +3.2 V for a few ns from the shunt ESL (limit ±3 V, 200 ns). *v2 rule:* take SPx/SNx as an adjacent pair from the inner edges of the shunt pads (NTx on the GND pad), with no copper shared with the current path. Run them over solid GND, away from the phase strips, all the way to U2. Take U7 IN+/IN− from RS4's inner pad edges the same way; at 1 mΩ, every 1 µΩ of shared copper is a 0.1 % error. Take **VDRAIN** from the high-side drain copper at the cells, not from the C1 end: 1 mΩ of feed at 20 A is 20 mV against the 130 mV VDS trip (15 %). Route SHx from the FET source pins.

**7. DRV8323 straps and quiet island.** *Evidence:* R2A-04 (seven-level pins have ±0.27 V of margin). *v2 rule:* put R44–R46 within ~2 mm of pins 29–31 and return them to AGND pin 35 and the DVDD-cap return (the island at the thermal pad), never to the bridge ground. The GAIN pin 32 pad has no trace. C24 (VM 100 nF) goes at pin 6.

**8. DRV8316C hot loop and VM feed.** *Evidence:* DESIGN §3.3 and §6.5–6.6; PLACEMENT §5.3 (the 10 µF bulk sat up to 9.5 mm from U3 and **5–20 mm** from U4). C410 was 20 mm away and joined by a **0.15 mm run on L3/L5** (ROUTING_PLAN rounds 27–33; the sim sits near the 4 V/µs limit). **The v1-6L query shows R302's and R402's VBAT pads fed through 0.3 mm tracks.** R402.1 lies in no VBAT zone and has no VBAT via within 4 mm; R302.1 is reached by 0.3 mm tracks, partly on B.Cu. That breaks "own L3 branch from C1" and puts pack-derived current on the bottom face. *v2 rule:* feed each drive from C1 on its **own branch**, not through the bridge copper: ≥ 1.0 mm wide (or a pour) on L1/L3 with ≥ 3–4 vias per layer change, sized for 2 A rms and 8 A peak. Put all four 10 µF + two 100 nF within ~3 mm of the VM pins, on the filtered side of R302/R402. Return the 100 nF directly to the PGND pins on L1. If any bulk cap has to move, re-run sim_hotplug.

**9. DRV8316C AGND/PGND partition.** *Evidence:* D-08, TI SLVSH07 §11.1, DESIGN §3.3. *v2 rule:* build an AGND island (pins 2/26/41, the thermal pad, and the AVDD/VREF/C307 returns) joined to power GND at the pad. The SOx lines leave from the AGND side. R301's nFAULT pull-up goes to the IC's own AVDD.

**10. Buck hot loop and the FB sense (the R20 issue).** *Evidence:* in v1-6L, **R20.1 (+5V, the top of the FB divider) is still unconnected**: the nearest +5V was 12 mm away across the L3 east bus (ROUTING_PLAN "Left (24)", "What the last 17 need"). An open R20 leaves FB pulled to GND through R21, which drives the buck output open-loop toward VIN, the same failure class as v1 REVIEW #1. *v2 rule:* keep the pulsed input loop C27 → VIN (pin 47) → SW (45) → D2 → GND ≤ ~4 × 4 mm on L1 over L2 (PLACEMENT §3). The SW copper stays L1-only and tiny, with L3/L4 under it GND or empty. Put R20/R21 at FB pin 1, away from L1. **Plan the +5V sense trace from the C29/C30 + pad to R20 at placement time**, as a 0.2 mm trace away from SW and L1, and make it a DRC-checked connection (not "route later"). R4/R5/C10 go on the quiet side.

**11. Analog sensing isolation.** *Evidence:* DESIGN §6.8. v1-6L ran W_VA/W_VB/W_NTC, SPI_SCK (14 mm) and L_SOC through L5 slots. *v2 rule:* the CSA outputs (W_SOx, L/R_SOx), the phase dividers, the NTCs (TH1, motor NTCs), VBAT_SNS and the INA/BQ taps run over unbroken GND (L2 or L3-GND), ≥ 1 mm from the phase, SW and gate nets. Their filters sit at the MCU pins (330 Ω / 22 pF, 1 nF, C68). The phase-divider 68 k resistor sits at the phase node, so only the divided node travels. The weapon INH lines (PC0/PC1) leave through vias ≥ 1.5 mm from PA0/PA1/PB11/PC3/PA2 and run on the other outer layer, with L2/L3 GND between them. Put a **GND stitch via within ~1 mm of every signal via** that changes between L1 and L4, because the reference moves from L2 to L3.

**12. Cell monitor and pack monitor grounds.** *Evidence:* DESIGN §3.1 (VC0 = pack−; a board I·R adds cell-1 error) and §6.9. *v2 rule:* tie U8's VSS and D5 to GND next to JBAT2, outside the weapon return path. Keep the cell taps thin, paired, and away from the bridge. Give U7's GND and C2 a short return to the quiet plane.

**13. MCU decoupling and VDDA.** *Evidence:* DESIGN §3.4. In v1-6L, GND pads of C64, C90, C73, C111, C45 and C50 were left with no legal via (ROUTING_PLAN), and some decaps depended on fenced fill islands. *v2 rule:* place C60–C64 ≤ 2 mm from their VDD pins, **each GND pad with its own via to L2 within 0.5 mm, placed before the signal fan-out**. VDDA pin 29 (C65) and VREF+ pin 28 (C71 + C66 4.7 µF) are fed from +3V3 through R60 (0 Ω / ferrite) and return to the plane next to the pins. The layer under U1 is solid GND: that is L2 if U1 is on top, **L3 if U1 is on the bottom**. U2's VREF (the CSA reference) comes off the same +3V3 branch as VDDA. Keep DRV_OFF (PC14, ≤ 30 pF) ≤ ~50 mm.

**14. Net-class widths are not enforced.** *Evidence:* v1-6L classes are Power 0.5, Drive 0.5 and Rail 0.4 mm, yet VBAT has 0.15 mm runs on L4 (the R4/R402-area sense branch), R_VM has 0.15 mm (C410), L_VM has 0.25 mm segments, and R302/R402 are fed at 0.3 mm (rule 8). *v2 rule:* add custom DRC minimum-width rules for VBAT, BAT_IN, VBAT_SW, PSW_S, W_A/B/C, L/R_VM and L/R_A/B/C (≥ 0.8–1.0 mm). Put the sense branches of power nets (U2 VDRAIN, U7 VBUS and Kelvin, R4 nSHDN top, R22/R24/R26 phase-divider tops, U13 VS/EN) behind **net-ties**, so that thin traces cannot silently carry load current.

**15. Thermal.** *Evidence:* calcs §5 and §11; E3-09. RθJA 25.7 °C/W is the JEDEC 2s2p figure (76 × 114 mm); this 85 × 35 mm board, crowded and with half the inner copper of v1-6L, will do worse. v1-6L has U2 16, U3 15 and U4 15 in-pad vias. The 6-layer decision allowed logic lanes on L3 between the U3/U4 thermal vias because two full GND planes (L2, L5) took the heat. *v2 rule:*
- **U3/U4:** ≥ 15 vias (0.3 mm, 1.0–1.2 mm pitch) into L2 **and an L3 GND island of ≥ ~10 × 10 mm with no lanes through it**, plus an exposed bottom GND pad (parts keep-out = pad + 1 mm, as in PLACEMENT §4). U2 gets ≥ 16 vias.
- **R302/R402** (≤ 1 W bursts) sit on their own copper ≥ 5 mm from the U3/U4 thermal copper. Keep U11/U12 away from U3/U4.
- **Weapon FETs:** the high-side drain tabs sit on the VBAT pour, whose via stitching to L3 doubles as heat spreading. The low-side tabs are the phase node, so keep that copper moderate (rule 16); the 0.5 s bursts are limited by thermal mass. TH1 stays in the phase-B high-side drain copper.
- **Q7/Q8:** the 16–22 W switch-on pulse lasts ~8 ms and is set by die SOA. The 22 A burst (2–2.5 W for 0.5 s) wants a generous BAT_IN/PSW_S/VBAT_SW tab copper area on L1.
- The drive ICs' thermal copper must not face the Pico (E3-09).

**16. EMC.** *v2 rule:*
- The phase strips (W_A/B/C, L/R_A/B/C) and BUCK_SW are L1-only and as small as the current allows. Remove the unused inner annular rings on the phase wire holes, so switching nodes do not couple into L2/L3.
- Stitch GND vias every ~5 mm along the board edge in the logic region, and around the L3 GND/VBAT boundaries. Pull the L3 VBAT back ≥ 0.5 mm from the board edge.
- Twist the pack and motor leads and strain-relieve them (DESIGN §6.9).
- The Pico W antenna stays outside the board outline (PLACEMENT §5.2).
- MLCCs across VBAT and the 2512 parts are placed parallel to the nearest edge, ≥ 3 mm from the holes (E3-10). A flex crack there is a short on an unfused LiPo.

## D. 6-layer conveniences that need a 4-layer replacement

| 6-layer convenience (v1-6L) | Why it existed | 4-layer replacement |
|---|---|---|
| **L5 GND jumpers**: R_TEMPJ, W_INLA_M, W_VA, W_VB, SWDIO, SPI_SCK (14 mm), NRST, L_SOC, +3V3 ties, R_VM/C410 (12.6 mm at 0.15 mm) | routing past a full U1 field without touching L2 | **None allowed in L2.** Short (≤ 5 mm) jumpers only inside L3 GND regions, perpendicular, with stitch vias at both ends and **no L4 signal crossing above the slot**. The real fix is placement and pin order (hub nets short, the sensor front end off U1's via field). |
| **L5 +5V trunk to J1** (0.35 mm, 36.7 mm) | no other path | +5V as a ≥ 0.4–0.5 mm trace on L1/L4 (0.45 A, ~35 mΩ over 36 mm), planned at placement |
| **L4 +3V3 fill** (1828 mm²; L4 signals kept splitting it) | cheap distribution | **no 3V3 pour on a reference layer.** Run +3V3 as 0.3–0.4 mm trunks from U5 (120 mA) to each cluster, with local decaps |
| **L3 VBAT feed** (673 mm²; SW corner trimmed) | pack current off L1 | stays on L3, but only in the front power band. It has to leave a GND strip under the L4 gate/Kelvin corridor (rule 5) and it feeds R302/R402 as real branches (rule 8) |
| **L3 + L4 as two signal layers** (the 11-lane L3 east bus, L4 lanes and the W_* bundle) | routing capacity | lost. L3 is mostly a GND reference now, so bus lanes on L3 slot the reference for L4. Signal capacity is L1 + L4 plus a few L3 lanes, which placement has to plan for |
| **Two GND planes for thermal and returns** (L2 + L5; L3 lanes allowed between the U3/U4 thermal vias) | spreading | L3 GND island under U2/U3/U4 (rule 15); 1 oz inner copper |
| **Free via-in-pad** (thermal pads, RS2, 7 boxed-in passive pads) | JLC 6-layer | check the JLC 4-layer price; otherwise tented small-drill thermal vias. Do not depend on via-in-pad for escape routing |
| **0.069 mm L1–L2** | commutation loop | thin (1080/3313) prepreg on the 4-layer build (section B) |

## E. Open items to carry into v2

- The R20 +5V sense and the R302/R402 VBAT feeds are real electrical defects in v1-6L (rules 8 and 10). Treat them as placement requirements, not routing leftovers.
- Re-run sim_hotplug if any DRV8316 bulk cap ends up > 3 mm from its VM pins, and re-estimate the commutation loop at the chosen prepreg.
- Confirm on the JLC order form: the stack-up name, 1 oz inner copper, the 2 oz outer minimum space (if 2 oz is considered at all), and the via-in-pad price on 4 layers.
