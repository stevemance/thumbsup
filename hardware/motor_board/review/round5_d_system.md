# Review round 5 / D: system-level adversarial review (rev E)

Reviewer role: power electronics and combat robotics, fresh eyes on the whole package.  No design
file was edited.

Inputs: DESIGN.md rev E (read end to end), design/calcs.md, design/nets.md, design/bom.csv,
BOM.md, spice/*.out, review/CHANGES.md, review/round4_d_system.md; datasheets LM74502, DRV8323,
BQ76907, 74LVC1G17 (Diodes); chassis geometry from `models/Chassis - Main Chassis.3mf` (v1) and
`models/v1.1/Chassis - Main Chassis_inland_tough_pla.3mf`, read with
`hardware/tools/mech/chassis.py` (`load`, `raster_floor`), plus `hardware/mech/board_outline.json`
and `hardware/LAYOUT.md` §1.

Evidence tags: **[D §x]** DESIGN.md, **[C §x]** calcs.md, **[N]** nets.md, **[B]** bom.csv,
**[DS …]** datasheet, **[M]** chassis mesh / board_outline.json.

---

## 1. Board area, chassis fit, mass

### 1.1 Chassis envelope (what the repo says)

* The only measured PCB bay is in the v1 chassis [M]: 104.5 × 37.5 mm with 16.5 mm corner
  chamfers and 9.5 × 10.5 mm front notches = **3447 mm²**, plus a 46.5 × 13.5 mm neck (628 mm²)
  under the drum where parts must be ≤ 8 mm tall.  Walls: 1 mm clearance; the side walls at the
  bay ends are the wheel pods.
* The v1.1 main chassis (models/v1.1, untracked) is 123.8 × 94.7 × 32.6 mm (v1: 121 × 98.8 ×
  33.6).  Its largest flat floor region at Z ≤ 2.6 mm is **3796 mm²**, against 4600 mm² for v1 on
  the same raster (1 mm cells).  So the newer chassis has **~17 % less** board floor, not more.
* The motor board sits above the compute board.  Its underside is ≈ 2 (floor) + 3 (standoff) +
  1.6 + 4.9–6.0 (mated J1) = 11.5–12.6 mm above the plate, so it **cannot use the ≤ 8 mm neck**.
  Height is fine: the top of C1 is at ≈ 24–25 mm, against 32.6–33.6 mm walls, as long as the lid
  has no features hanging into the bay.

### 1.2 Minimum area from the part list and the layout rules

Top-side courtyards (KiCad IPC-nominal courtyard sizes; J1 is on the bottom):

| Group | mm² |
|---|---|
| 8 × PDFN 5×6 (Q1–Q8) | 312 |
| 96 × 0402, 37 × 0603, 6 × 0805, 10 × 1206 | 474 |
| 4 × 2512 shunts | 119 |
| C1 10×10.5 can | 130 |
| U1 LQFP-64, U2 VQFN-48, U3/U4 VQFN-40 | 304 |
| L1, D1 SMB, D2 SMA, SOD-123/SOT-23/SC-70/VSSOP/TSSOP/MSOP/QFN-20 small parts | 250 |
| J2/J3 SH R/A, J4 XH side entry | 282 |
| Wire pads with solder clearance (2 × 4×6, 3 × 3×5, 6 × 2×3) | 335 |
| MH1–MH4 keep-outs, TP1–TP12, JP1/JP2 | 204 |
| **Total** | **≈ 2430** |

A single-sided power board carrying 22–27 A pours, with a ≤ 6 nH commutation loop per
half-bridge, ≥ 3 mm hole clearance for 1206/2512 parts [D §6.10], edge connectors and a
return-path floorplan [D §6.2], reaches 50–60 % courtyard utilisation in practice.  That puts
the board at **≈ 4000–4900 mm²** (70 %, extremely dense: 3470 mm²).  The pours alone are wide: a
22 A burst for 0.5 s in 1 oz copper heats adiabatically at ρJ²/c_v, which is ≈ 20 K/s at 10 mm
width and ≈ 80 K/s at 5 mm.  So the pack path needs 5–10 mm of copper on L1 plus L3.

### 1.3 Mass

| Item | g |
|---|---|
| PCB, 4-layer 1.6 mm FR-4 (0.30 g/cm² laminate + ~70 % copper on 4 × 1 oz + mask ≈ 0.39 g/cm²), 34–45 cm² | 13–18 |
| Components (C1 ~1.3, 8 FETs ~0.8, U1 0.35, J4 ~0.6, J1 ~0.4, L1 0.3, shunts 0.25, 1206s 0.25, ~140 small passives 0.4, rest ~0.6) | ~5.3 |
| Solder | ~0.8 |
| **Motor board** | **≈ 19–24** |
| Off-board: 2 × 100 mm 16 AWG pigtail (~3.2), XT30 half (~0.8), switch (1.5–2.2), nylon hardware (~0.8) | ~6.5 |
| Compute board (Pico W 3 g + 1.6 mm carrier + socket) | ~8–12 |
| **Electronics stack** | **≈ 34–43** |

The PCB laminate is **~65–70 % of the motor board's mass**.  C1, the FETs and the wiring are not
the dominant items, so the round-4 note D4-10 was wrong on this point.

---

## 2. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| **R5D-01** | **MAJOR** | Board area vs chassis | **The board as specified (all parts on the top side) does not fit the only chassis bay in the repo, and the package defines no outline or area budget.**  The top-side courtyards alone are ≈ 2430 mm² (§1.2).  At a realistic 50–60 % utilisation the board needs **4000–4900 mm²**.  The v1 bay offers **3447 mm²**, and the v1.1 chassis ~17 % less.  The neck is unusable because the motor board sits ≥ 11.5 mm up in the stack.  Three documented requirements reduce the usable area further: (a) §3.5 item 6 keeps the Pico W antenna out from under the motor board.  Both boards share one bay, so the motor board must be cut back over the antenna end, costing ~15 × 25 ≈ 375 mm².  (b) J2/J3 (SH R/A) "at the board edge" [D §6.9] face wheel-pod walls only 1 mm away.  A mated SH plug plus its cable bend needs ~6–8 mm beyond the connector face, so each connector either sits back from the edge or faces inward.  (c) The same applies to J4, whose XH side-entry plug plus wires need ~12–15 mm.  For comparison, the v1 board in this bay could not be routed automatically at ~310 parts two-sided on 4400 mm² (LAYOUT.md §5). | [M] board_outline.json (outline, "neck … ≤ 8 mm"); v1.1 flat-floor 3796 vs 4600 mm²; [B] 187 parts by footprint; [D §1] "everything on the top side except J1 … and J4"; [D §3.5] item 6, [D §6.2, §6.9, §6.10] | Before drawing: fix the outline from the chassis the robot will actually use, and write an area budget in §6.  Levers, in order of cost: (1) **put the ≤ 1 mm-tall passives and SOT/SC-70 logic on the bottom side**.  JLC two-sided assembly is already paid for because of J1, and this moves ~400 mm² off the top.  Keep bottom parts outside J1's footprint and ≤ 1 mm tall: the gap to the compute board is 4.9–6.0 mm minus Pico parts up to ~3.6 mm.  (2) Make the "fight build" DNP set [D §7.15] the default (U8/J4 block: −230 mm²).  (3) Use a 3.3 × 3.3 weapon FET [D §7.3] (≈ −140 mm²).  (4) Otherwise enlarge the bay in the chassis.  Re-run `chassis.py outline` against the chosen chassis |
| R5D-02 | MINOR | Mass | **The package has no mass budget.**  Estimated motor board ≈ 19–24 g, electronics stack ≈ 34–43 g (§1.3).  The only written budget is C-2 "electronics ≤ 40 g (stretch 35 g)" (DESIGN_REQUIREMENTS.md, v1).  The laminate dominates.  D4-10's "mass is dominated by C1, the FETs and the wiring" is wrong | §1.3 arithmetic; [B] | Add a mass line to §4 (weigh at bring-up; v1 bring-up item 9 already asks for it).  Cheap levers: 1.2 mm 4-layer (−25 % laminate, ≈ −3.5 g) on the motor board and 1.0 mm on the compute board.  Thinner boards flex more, so keep the MLCC/2512 orientation rule in §6.10 |
| R5D-03 | MINOR | Doc contradiction, layout | **§6.2 routes the pack current on "wide top/bottom pours", but §6.10 forbids pack-current copper on the bottom layer ("keep the high-current pours on top/inner layers").**  The D4-08 fix added §6.10 and left §6.2 unchanged.  With L2 reserved as a solid GND plane under the bridge (§6.1), the pack current can use only L1 and L3.  That is also what sets the pour widths in R5D-01 | [D §6.1, §6.2, §6.10] | §6.2: "top and L3 pours; bottom only outside the compute-board footprint and under mask".  State the stack-up explicitly: L1 power, L2 GND, L3 power/signal, L4 signal/GND |
| R5D-04 | MINOR | Assembly, combat robustness | **The battery and weapon leads (16–18 AWG) solder onto SMD pads** (SolderPad_4x6mm, 3x5mm, 2x3mm).  In a 1-lb robot the leads take tug and vibration, and SMD pads peel: copper-to-FR-4 peel strength is ~1 N/mm, so a 3 mm-wide pad lets go at a few N of lever load at the joint.  Getting enough heat into a pad tied to four 1 oz planes with a 16 AWG wire also makes cold joints likely.  The v1 design used 2 mm plated through-holes for the same reason (MOT-9, `MotorHoles_1x03_P5.90mm`) | [N] J_BAT±, J_WA–WC, J_LA–RC footprints; [D §6.12]; DESIGN_REQUIREMENTS MOT-9 | Plated through-holes (or slots) for J_BAT± and J_WA–WC (≥ 1.8 mm drill for 16 AWG), with the wire's insulation pressed against the board.  Keep SMD pads only for the 20 AWG drive leads, if at all.  Add strain relief of every lead to the chassis to §6.9 |
| R5D-05 | MINOR | Compute-board contract | **§3.5 item 2 names a part that does not do the job.**  "Isolated from USB VBUS (… e.g. the Pico's VSYS Schottky)": the Pico's on-board Schottky runs VBUS → VSYS.  It stops VSYS from back-feeding the PC.  It does **not** stop USB from feeding VSYS, and so the motor board's +5V.  A builder who wires +5V straight to VSYS gets USB → +5V → L1 → the buck high-side body diode → VBAT ≈ 4.4 V: every DRV and divider is back-powered from USB, and the power LED lights with the switch open.  This is exactly the failure item 2 warns about | [D §3.5] item 2; Pico datasheet "Powering Pico" (external supply into VSYS through its own Schottky/P-FET); [N] +5V → L1 → BUCK_SW | Reword: "a Schottky or ideal diode **from the motor board's +5V into VSYS** (anode on the J1 side), as in the Pico datasheet's external-supply circuit; the Pico's own VBUS diode is not enough" |
| R5D-06 | MINOR | Dynamic-ARM evidence | **The ARM timing numbers cannot be reproduced from the package, and they were computed against the wrong thresholds.**  (a) The simulation behind "100–160 ms, 25–85 °C" exists only as `/tmp/r4a/spice/sim_arm_fix.py`.  It is not in `spice/` and not in §5, and `/tmp` does not survive a reboot.  (b) That script times the disarm to **0.8 V** (the old 74LVC08 VIL) and the arm to **2.31 V** (PD2's VIH).  U14 now sets both: 74LVC1G17 VT− is **0.80–1.30 V** and VT+ is 1.50–2.00 V at 3 V.  With τ = R41·C16 = 103 ms from ~2.8 V, a high-VT− part disarms in ≈ 103·ln(2.8/1.3) ≈ **80 ms** at 25 °C, and sooner hot.  That is the safe direction, and the "< 20 ms gap does not disarm" claim still holds (2.0 V after 20 ms at 85 °C > 1.43 V).  But the §9 step 3 pass window "100–160 ms" can reject a good board | `find / -name 'sim_arm*'` → /tmp/r4a only; sim_arm_fix.py l.9/15 thresholds 2.31/0.8; [DS 74LVC1G17] VT+ 1.50–2.00, VT− 0.80–1.30 @ 3 V; [D §3.2, §5, §9.3] | Copy the ARM simulation into `spice/`, re-run it with U14's VT+/VT− bands (including a 3.3 V scaling), add a §5 row, and change the §9 pass criterion to "≤ 160 ms, and not before ~20 ms" |
| R5D-07 | MINOR | Pack protection claim | **"Deep-discharge cutoff" is claimed as a requirement met [D §1], but the 9.2 V buck cutoff is 2.3 V/cell**, below the ~3.0 V/cell floor for LiPo.  It keeps the logic alive during sags; it does not protect the pack.  An idle, switched-on robot draws ~1.6–1.9 W: logic ~1.2 W through the buck, the two awake DRV8316s and the DRV8323 ~0.3–0.5 W, bleeder and dividers 0.06 W.  That is ≈ 100–120 mA at 16 V, which takes a 450–650 mAh pack at storage charge to 3.0 V/cell in **~2–3 h**, then on down to 2.3 V/cell and the ~3 mA tail to 1.65 V/cell [C §9].  A robot left on in the pits ruins the pack.  §7 does not list this | [D §1] "deep-discharge cutoff"; [D §3.1] R4/R5; [C §9] buck UVLO rows and "drain with the buck off"; [C §4, §5] quiescent figures | Rename it "logic brown-out cutoff (not pack protection)".  Add a §7 residual and a compute-board requirement: a low-cell alarm (BQ76907 or VBAT_SNS < 3.5 V/cell at rest) that is loud (LED/beep through the drives) after N minutes disarmed.  A higher UVLO is not an option: the 1.05–1.38 V nSHDN spread already spans 7.4–10.3 V |
| R5D-08 | NOTE | Doc consistency | §3.3 says "48 kHz PWM/FOC (10 updates per electrical cycle at speed)".  §4 and calcs §10 say 8.2 at 16.8 V no-load and 9.8 at 14 V | [D §3.3] vs [D §4], [C §10] | "8–10 updates per electrical cycle" |
| R5D-09 | NOTE | Firmware contract, bring-up | **Debugging conflicts with the safety timers.**  (a) DBGMCU freezes TIM1/8/20 on halt but not the IWDG.  Once started (first thing at boot, ~20 ms), the IWDG resets a core halted at a breakpoint after 20 ms.  (b) §3.5 item 4 has the compute board pulse NRST after 100 ms without a heartbeat.  A halted core, and SWD flashing by the compute board itself (item 5), both stop the heartbeat | [D §8] boot order, watchdog row; [D §3.5] items 4–5 | §8: set DBG_IWDG_STOP in debug builds.  §3.5: the compute board suspends the NRST rule (and keeps W_ARM_CLK low) while it or an external probe owns SWD |
| R5D-10 | NOTE | Firmware contract, DRV8316 | CTRL4 (OCP 16 A, latched) and CTRL5 (CSA 0.15 V/A) are "reset value kept": never written and not in the 100 Hz read-back (CTRL2/6/10 only).  R_nCS (PB4) is also held low by the UCPD dead-battery Rd whenever the STM32 is in reset (for example while the compute board holds NRST), so U4 is selected with SCLK/SDI floating.  The DRV8316's internal pull-downs make a spurious write unlikely, but a wrong CSA gain would scale the drive current by up to 8× (0.15 → 1.2 V/A) without any other symptom | [D §8] DRV8316 row; [N] R_nCS = U1.57 PB4; [D §8] boot order (dead-battery note) | Write CTRL4/CTRL5 explicitly and add them to the read-back.  Optional: 100 k pull-ups on L_nCS/R_nCS (like R12 on INA_nCS) |
| R5D-11 | NOTE | Assembly checklist | §9 has no post-assembly step, although D4-09 recommended one.  A builder working from the checklist skips: staking C1 (and L1, J2/J3), the J1 pin-1/mirror check against the socket, setting the fight-build DNP set, and inspecting bottom-side vias/mask in the stack gap.  They appear only as scattered sentences in §3.5, §6.10 and BOM.md | [D §9]; [D §3.5] item 1, [D §6.10], [D §7.15]; round4_d D4-09 | Add "0. After assembly" to §9 |
| R5D-12 | NOTE | Weapon safety chain | **W_ARM_S is one node shared by the hardware gate (U6) and the firmware ARM check (PD2).**  If U14's output fails high after arming (a fault, or a bridge between SC-70 pins 4 Y and 5 VCC, which are adjacent), both layers see "armed", and only the command-link timeout is left.  At boot the case is fail-safe: the "fresh low→high edge" rule never fires.  Separately, §3.5 item 4 does not say what the compute board does when its boot self-test fails | [N] W_ARM_S → U6.2/5/10 and U1.55; [DS 74LVC1G17] pinout; [D §3.5] item 4, [D §8] boot order | Feed PD2 from W_ARM (before U14; FT Schmitt input, leakage ≤ 0.15 µA against R41 47 k) so that firmware and U6 read the ARM level independently.  Or state: "self-test failure → never toggle, report a fault" |
| R5D-13 | NOTE | Bring-up step 1 | "12 V current-limited to 0.2 A" is 5× below the soft-start's own demand of ~1 A (380 µF × 2.7 V/ms).  Whether the first closure hiccups depends on the supply: with an output capacitance below roughly 500 µF, BAT_IN collapses under the 6.6–7.35 V switch UVLO and U13 hiccups until C1 has charged in steps.  That is harmless, but it will look like a fault to the person doing bring-up | [D §9.1]; [C §9] soft-start 1.0 A, UVLO; LM74502 tUVLO_OFF 2 µs | Say so, or use a 1.2 A limit for the first closure and then drop to 0.2 A |
| R5D-14 | NOTE | Pack chemistry | The 18.5 V firmware coast and the 19.0 V BOVL assume 4.20 V/cell.  LiHV (4.35 V/cell = 17.4 V, common in insect classes) plus the documented ~1.4 V regen rise gives 18.8 V: nuisance weapon breaks during braking | [D §8] weapon-safety and braking rows; [D §3.1] U7 | §1: "LiPo 4.20 V/cell only", or make the thresholds a pack-type setting |
| R5D-15 | NOTE | Compute-board contract | Two ways a correct-looking compute board breaks the "≥ 500 Hz, no gap > 20 ms" rule: (a) Bluepad32 controllers differ in report rate, and some send reports only when an input changes.  A "fresh packet" freshness test can then disarm a driver who holds the sticks still, and the toggle cannot come from a per-packet loop at 500 Hz.  (b) RP2040 XIP flash sector erase is 45 ms typical and up to 400 ms max, which stalls code that runs from flash.  400 ms exceeds the ~70–160 ms disarm, so match logging to the Pico's flash disarms the weapon | [D §3.5] item 4; W25Q-class sector-erase spec | §3.5: toggle from a ≥ 1 kHz loop that checks **link** freshness (connection plus last-report age suited to the chosen controller), running from RAM; no flash erase while armed |

---

## 3. Power-on / power-off sequences (rev E, checked)

| Phase | Weapon | Drives | Logic / compute | Verdict |
|---|---|---|---|---|
| Switch closes | U13 ramps VBAT at 2.7 V/ms.  W_EN low (R40) → U2 asleep.  INL = 0 (R47–R49, W_ARM = 0) → Hi-Z | nSLEEP and DRVOFF follow +3V3 together; DRVOFF high → Hi-Z; internal buck charges C307 through R300 until firmware disables it | Buck on at ~10.4 V (~3.9 ms into the ramp), 5 V then 3.3 V; RP2040 GPIOs pulled down, so W_ARM_CLK is low | OK |
| STM32 boot | IWDG, dead-battery off, W_EN high, CSA offsets; TIM1 CHxN only after a fresh ARM edge | DRV_OFF low only when commanded | Heartbeat → compute board self-test (300 ms high / 300 ms low) → toggle | OK (see R5D-12 for the failure action) |
| Sag / brownout | STM32 BOR 2.8 V → reset → W_EN low → coast; the compute board usually survives (VSYS down to ~1.8 V) → "ARM edge required" handshake | DRV_OFF high on reset | — | OK |
| Switch opens, drum stopped | Bus to 9.2 V in ~14 ms (37.5 mJ / 2.65 W), MCU stays live meanwhile | As +3V3 collapses, DRVOFF and nSLEEP fall together: at worst a brief low-side brake (benign) | Both boards off | OK |
| Switch opens, drum spinning | Board runs on rectified BEMF down to ~19 k rpm (~10 s at a ~2.5 W load); BAT+ pad and pigtail stay live through Q7/Q8 | Firmware stops them on ≈ 0 A detection | Compute board stays alive | Accepted §7.5 |

## 4. Weapon safety chain: remaining single points of failure

| Single fault | Effect | Covered by |
|---|---|---|
| C15 short / R41 open | ARM becomes static / slow | Boot self-test [§3.5] (listed §7.16) |
| U14 Y stuck high, or Y–VCC bridge (adjacent pins) | Hardware gate **and** firmware check both see ARM | At boot: fresh-edge rule (fail-safe).  After arming: command timeout only (**R5D-12**) |
| U6 output stuck high | Hardware gate lost | Firmware CHxN low on ARM low (independent) |
| R44 (MODE) open → 1x PWM mode | INLC becomes nBRAKE: ARM low = all low sides on, chopped by VDS OCP (62–93 A, 4 µs every 4 ms) | Fail-safe in effect: the motor cannot be driven while disarmed, and the brake is weak.  Caught at bring-up |
| R44 short → 6x mode | With INL = 0, only the high sides can switch: no torque | Fail-safe |
| Q7 / Q8 short | Soft-start / reverse protection lost | Listed §7.16 |

No new MAJOR in the safety chain.

---

## 5. Summary

| ID | Sev | One line |
|---|---|---|
| R5D-01 | MAJOR | No outline or area budget; top-side courtyards ≈ 2430 mm² → ≈ 4000–4900 mm² board vs a 3447 mm² v1 bay (v1.1 ~17 % smaller), minus the Pico antenna keep-out and connector mating clearance; neck unusable in the stack.  Put passives on the bottom, make the DNP set the default, fix the outline first |
| R5D-02 | MINOR | No mass budget: motor board ≈ 19–24 g, stack ≈ 34–43 g vs the 40 g target; laminate is ~2/3 of the mass (D4-10 wrong); consider 1.2/1.0 mm boards |
| R5D-03 | MINOR | §6.2 "top/bottom pours" contradicts §6.10 "no pack current on the bottom"; state the stack-up |
| R5D-04 | MINOR | 16–18 AWG battery/weapon leads on SMD pads peel in a combat robot; use plated through-holes as v1 did |
| R5D-05 | MINOR | §3.5 item 2's "Pico VSYS Schottky" does not block USB from back-feeding +5V/VBAT; require a diode from +5V into VSYS |
| R5D-06 | MINOR | ARM sim lives only in /tmp and uses 0.8 V/2.31 V, not U14's VT− 0.8–1.3 V; the disarm can be ~80 ms and §9's 100–160 ms window can fail a good board |
| R5D-07 | MINOR | "Deep-discharge cutoff" is 2.3 V/cell; the idle board (~110 mA) flattens a pack in 2–3 h; rename it, add a residual and a low-cell alarm |
| R5D-08 | NOTE | "10 updates per electrical cycle" vs 8.2/9.8 |
| R5D-09 | NOTE | IWDG not frozen in debug; the NRST-on-heartbeat-loss rule fights SWD sessions and flashing |
| R5D-10 | NOTE | DRV8316 CTRL4/5 never written or read back; PB4's dead-battery Rd selects U4 during reset |
| R5D-11 | NOTE | §9 lacks a post-assembly step (staking, J1 mirror check, DNP set) |
| R5D-12 | NOTE | W_ARM_S is shared by the U6 gate and the firmware check; take PD2 from W_ARM; define the self-test failure action |
| R5D-13 | NOTE | Bring-up at a 0.2 A limit vs the 1 A soft-start: UVLO hiccup on low-capacitance supplies |
| R5D-14 | NOTE | LiHV packs trip the 18.5 V coast / 19 V BOVL during regen; state 4.20 V/cell |
| R5D-15 | NOTE | Controller report behaviour and RP2040 flash-erase stalls (up to 400 ms) break the ARM toggle contract |

**Verdict: 0 BLOCKER, 1 MAJOR, 6 MINOR, 8 NOTE. Not clean.**
