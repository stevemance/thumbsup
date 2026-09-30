# Weapon gate/Kelvin corridor (v2, 4 layers): decision

Frame: board top view, mm, x to the right, y toward the rear, y = 0 at the front edge. Pads are taken from
`kicad/v2/out/geom_place.json`. Nothing in the repo was changed.

Evidence scripts (not in the repo):
- `gate_corridor_check.py` (shapely): copper gaps for every via and trace proposed below.
- `gate_corridor_loop.py`: loop areas and stack-up inductances.

## 0. Recommendation

**Keep all three U-cells exactly as placed.** The commutation loop is untouched.

**Route each high-side gate pair (GHx + SHx) through a short, bounded L4 "pair lane" under the power band.** Use
2 vias per net at each end, with the pair's vias adjacent:
- **Phase C and phase A:** a y-lane from the cell's interior "mouth" (the 1.5 mm gap between the LS tab and the HS
  tab) straight back under the gap between the shunt and the cap, surfacing behind them.
- **Phase B:** an x-lane under its own LS FET (Q4) to the C|B inter-cell channel, surfacing at the front of that
  channel. The rest of its run is on L1.

**Everything else stays on L1 in the band:**
- All three low-side gates (GLx) run on L1 with **no via**. Each goes from pin 4 to the strip behind the pin row,
  through the shunt pad gap, then to U2.
- The six Kelvin lines (SLx = SPx, SNx) leave on L1 through the shunt pad gap. They drop to L4 at the rear of that
  gap, over L3 GND, to cross the gates and reach U2.

**Enabling changes, all small:**
- Cells B and A move **+0.6 mm in x**. This opens the C|B door for the B pair. JW1 stays where it is.
- The **L3 VBAT/GND boundary moves to y = 16.0 under the cells** (x ≥ 44.5).
- **U2 moves +1.0 mm to the rear**. This is the most J4 allows.
- **Via-in-pad (POFV)** goes on U2 pins 13, 14, 21, 22 (Kelvin B/C) and 23, 24 (SOC/SOB).
- A handful of anchored parts move out of the fan-out strip.

**Rejected:**
- **FET re-orientation.** It is loop-neutral, but U2's pin order then forces gate-to-gate crossings in cells C and A.
  See §3.1.
- **A long L4 or L3 corridor** under the cells. See §3.2.

## 1. The problem, precisely

In every cell the commutation loop is a closed ring of copper **on L1**:

HS tab (VBAT) → cap VBAT pad → cap GND pad → [0.6 mm L1 link] → shunt GND pad → shunt → SL pad → LS source pins →
LS die → LS tab (phase) → phase strip in front of the HS gate pin → HS source pins → HS die.

**The HS gate pin 4 sits inside the ring.** For example, Q5 pin 4 is at (52.44-53.15, 5.85-7.0). This follows from
the package chirality:
- An HYG015N04LS1C2 at rot 270 (pins forward) always has pin 4 at its **left** end.
- At rot 90 (pins back) it always has pin 4 at its **right** end.
- With the LS on the left and the HS on the right, both gates therefore face the cell interior.

**Every L1 exit from the interior is below the gate-pair minimum.** The pair needs 2 × 0.25 + 0.15 + 2 × 0.15 =
**0.95 mm**.

| Exit (cell C) | Copper gap |
|---|---|
| Interior channel, Q6 tab to Q5 tab | 1.5 mm (fits a pair, but it is a dead end) |
| Rear of the channel, Q5 tab corner (52.35, 12.65) to RS3 GND pad corner (52.45, 13.35) | **0.70 mm** |
| RS3 GND pad to C31 GND pad (the L1 ring link) | **0.60 mm** |
| Strip between the pin row / HS tab and the shunt row (y 12.45/12.65 to 13.35) | **0.7-0.9 mm** (one trace) |
| RS3 pad gap (under the body) | 1.3 mm, already used by GL + SL (+ SN) |

The Freerouting trial reported only 5 bridge opens because `fr_trial.py` cuts the pour nets (W_x, W_SLx, GND, VBAT)
from the DSN. The ring was not modelled: its GLC route runs 17 mm along y = 12.95 through where the shunt-row copper
goes. With the pours in place, every interior exit is closed.

L3 and L4 are not free in the band (the memo 3.1 rules), and L2 has no traces. So the HS pair must leave the ring
either through a via or through a re-oriented FET.

## 2. TI guidance (what it allows)

- **SLVSDJ3D §11.1 (DRV832x data sheet).**
  - "Minimize the loop length for the high-side and low-side gate drivers. The high-side loop is from the GHx pin … to
    the high-side power MOSFET gate, then follows the high-side MOSFET source back to the SHx pin. The low-side loop is
    from the GLx pin … then follows the low-side MOSFET source back to the **PGND** pin."
  - "Layer changes and vias should be avoided."
  - "Extra care should be taken in the low side path as excessive inductance can cause the VGLS regulator to
    overshoot."
  - The LS gate returns through **PGND (the plane)**, not through SLx. So GL needs a solid GND plane under it (L1 over
    L2), not a paired trace.
- **SLVA951 (DRV832x layout guide).**
  - §4: "a good practice is to avoid vias wherever possible"; "each via is capable of at most 200 mA". Our peak is
    120 mA sink.
  - §6.2 and §6.4: "TI recommends that a gate signal stays in the same layer **when possible** to avoid vias".
  - §6.3: SHx goes "to the connection between the high-side MOSFET source and low-side MOSFET drain".
  - §6.5: SPx/SHx are routed "as a differential".
  - §7.4: SPx/SNx are routed "as independent traces directly to the terminals of the sense resistor".
  - §7: minimise GND-CBYPASS-VM-QHS-OUT-QLS-RSENSE-GND.
- **SLVA959B §4.** Route the high-side gate and the switch-node trace "as close as possible to minimize inductance,
  loop area, and … dv/dt" noise. TI suggests starting at 20 mil. That figure is for its 1-2 A IDRIVE range; at 60/120
  mA, SLVA951's 15 mil/A makes 0.25 mm ample.
- **SLPA010 (NexFET ringing).**
  - Its "optimized" layout puts the driver IC on the bottom under the FETs, so TI itself accepts gate vias to shorten
    the loop.
  - It also shows that the SH pick-up point sets the common-source inductance. A pick-up at the HS source / LS drain
    junction is the low-inductance choice.

**Reading:** vias on gate lines are discouraged, not forbidden. The plan keeps GL (the sensitive loop) via-free and
gives each HS pair exactly one down/up pair of adjacent vias.

## 3. Options

### 3.1 FET re-orientation inside the cell (option 1)

**The only orientation that puts the HS gate outside the ring is the mirrored cell ("M"):**
- HS on the left (rot 270): its gate is at the left-front, facing out.
- LS on the right (rot 90): its gate is at the right-rear, facing out.
- The shunt sits behind the LS with its SL pad under the LS sources and its GND pad toward the cap.
- The cap sits behind the HS.

Rot 0 and rot 180 variants re-trap the gate: the phase copper has to wrap pin 4 to reach pins 1-3.

**The loop is not the problem.** Through the pad centres:
- As placed: **59.1 mm², perimeter 33.6 mm**.
- Mirrored: **55.1 mm², 32.6 mm**.

With L2 0.069 mm below L1, the board part of the loop is ≈ Σ μ0·h·l/w, and one square of L1 over L2 is 0.087-0.126
nH (h = 0.069-0.1 mm). Both cells land at the same ~0.4 nH of board inductance. The parts (FETs, 1210 ESL, 2512)
dominate the ~3-4 nH.

Costs of the mirrored cell:
- The cap's VBAT pad overlaps the HS tab by only **~1.1 mm** (2.7 mm today), because the shunt's GND pad occupies the
  space behind the HS.
- The cap sticks 1.6 mm out of the cell.

**Why it is rejected: U2's pin order.** Going round U2 from the front-left, the pins are:

`SNC SLC GLC SHC GHC | GHB SHB GLB SLB SNB | (east edge, front to rear) SNA SLA GLA SHA GHA`

For planar routing, cells C and A need **GL to the left of the HS pair**, and B needs the pair to the left of GL.
- A mirrored cell puts the pair on the left and GL on the right. That produces **gate-over-gate crossings in cells C
  and A** (gate vias again, now far from the FETs).
- A mirrored B has sources SN, SL, GL against pins GL, SL, SN: three inversions and 4 Kelvin vias in a 1.8 mm strip.

The as-placed cell ("N") already has the right gate order for C and A. It only lacks a way out.

**"Open the ring" variant (no rotation).** Move the cap-GND to shunt-GND link to L2 vias and send the pair out between
the shunt and the cap. This is blocked by the **0.70 mm pinch** between the HS-tab corner and the shunt-pad corner.
Clearing it means moving the shunt/cap row ≥ 0.5 mm to the rear. That eats the U2 fan-out strip, which is already
short (§5). Rejected.

### 3.2 L4 corridor under the cells (option 2, as a bounded exception)

**What the L4 GND under the L3 VBAT band does.** L3 is 0.069 mm from L4 and 1.23 mm from L2, so the L3 feed's image
return runs in L4.

A lane of width w cut into L4 across that current forces the return up to L2 over the lane:
ΔL ≈ μ0 · d(L2-L3) · w / l.

| Lane | Extra inductance |
|---|---|
| 1.2 mm × 11 mm y-lane | **+0.17 nH** |
| 1.2 mm × 6 mm | +0.31 nH |
| Stitching-via rows | about +0.05 nH |

The C1-to-cell-A feed is ~0.3 nH with L4 solid. Two y-lanes (C, A) bring it to **≈ 0.8 nH**.

`sim_weapon_bridge.py` models C1 → rail as **5 nH ‖ 2 Ω** and the other legs' caps behind **2 nH ‖ 2 Ω**. Even with
the lanes, the real feed stays several times below what the SPICE results already cover. An **x-lane** (parallel to
the feed current) costs essentially nothing.

**L3 instead of L4 is out.** An L3 lane would slot the VBAT feed itself, which carries 22-27 A of DC. At x ≈ 51.6 the
L3 cross-section would drop from ~14 mm to ~3 mm, because JW3's antipad takes the front.

**Coupling and reference:**
- The pair lane over L3 VBAT is a microstrip at h = 0.069 mm: Z0 ≈ 35 Ω, L′ ≈ 0.21 nH/mm per trace, pair loop
  ≈ **0.40 nH/mm**. That is the same as on L1 over L2.
- The pair is balanced (SH is the return), so it does not need its plane to be GND.
- GH to VBAT is 0.125 pF/mm (parallel plate), ~2 pF with fringe for a 12 mm lane. It adds in parallel with Cgd:
  ≈ +6 % of the model's Cgd_min of 33 pF at high VDS, and negligible at the plateau.
- Toward the compute board (5 mm away) the lane couples ~0.01 pF.

**Width and stitching:**
- The pair is 0.25/0.15/0.25 plus 0.25 pour clearance, so the **slot is ≈ 1.2 mm wide**.
- L4 GND cannot be stitched beside the lane along the FET row: the L1 above is the phase tab or the VBAT tab.
- Stitching comes from:
  - the front neck (y 5.1-6.1, between JW's antipad and the lane);
  - the shunt and cap GND in-pad vias, which run along the rear half of the lane;
  - the region behind the band.
- That is enough for ≤ 13 mm lanes.

**What a long corridor (v1 style, L4 all the way to U2) would add:**
- It crosses the L3 VBAT/GND boundary.
- It pushes the U2 fan-out onto L4 (the U2 EP keep-out starts 0.3 mm behind the pad row).
- It still leaves U2's pin-order crossings.

Only a **short** lane per HS pair is justified.

### 3.3 Hybrid (option 3, recommended)

- GL and Kelvin stay on L1 through the shunt gap. That is the existing rule 5, and it fits: 1.3 mm gap, GL 0.25 plus
  SL/SN 0.2 plus 4 × 0.15 = 1.25 mm.
- Only the HS pair takes a lane. Each lane is placed so the pair **surfaces on the side U2's pin order needs**:

| Cell | Needed pair position | Lane |
|---|---|---|
| C | right of C's LS nets | y-lane, surfaces behind the RS3/C31 gap |
| B | left of B's LS nets | x-lane, surfaces in the C\|B channel |
| A | right of A's LS nets | y-lane, surfaces behind the RS1/C25 gap |

**Result: no gate-over-gate crossing anywhere.** The remaining inversions are Kelvin-only (C: SN; B: SL vs GL;
A: SN). They are handled by the Kelvin L4 hop at the shunt.

## 4. Recommended geometry

Cells B and A are shifted +0.6 mm, and U2 +1.0 mm to the rear. Vias are 0.3 mm drill / 0.6 mm pad. Gate class is
0.25/0.15; Kelvin is 0.2/0.15. All gaps below were checked against the placed pads with `gate_corridor_check.py`. The
tightest clearance is 0.166 mm (GHB at the C|B door, against the Q5 tab). Every other item is ≥ 0.25 mm.

**Per-cell lanes:**

| | C (as placed) | B (+0.6) | A (+0.6) |
|---|---|---|---|
| Mouth vias (L1 → L4) | SH (51.60, 6.45) in the phase pour at the channel mouth; GH (51.60, 7.55), with a 1 mm L1 stub from Q5 pin 4 | SH (64.70, 6.45); GH (64.70, 7.55), stub from Q3 pin 4 | SH (77.20, 6.45); GH (77.20, 7.55), stub from Q1 pin 4 |
| Via-pair spacing (L2/L3 antipad web at 0.7 mm antipads) | 1.10 mm (web 0.40) | 1.10 mm | 1.10 mm |
| L4 lane | x 50.9-51.7, y 6.2 → 12.8; jog to x 52.3-53.1 (under the RS3\|C31 gap: RS3 GND vias at x ≤ 51.9, C31 vias at x ≥ 53.5); y → 18.3 | y 6.25-7.75, x 64.7 → 58.05, under Q4's front half (no Q4 vias; the phase tab is L1 only) | as C, +25.6: x 76.5-77.3, then x 77.95-78.75 |
| Surfacing vias (L4 → L1) | SH (52.40, 17.95), GH (53.30, 18.55) | SH (58.05, 6.45), GH (58.05, 7.55), in the C\|B channel (2.2 mm wide) | SH (78.00, 17.95), GH (78.90, 18.55); 0.25 mm to J3's front MP pad |
| L1 onward | east to U2 SHC 63.25 / GHC 63.75 (y 20.16 after the move) | GH at x 58.05, SH at 58.65 down the channel; the door at y 12.0-13.6 goes to x 56.75 / 57.25 (door 1.22 mm; 0.166/0.29 clearance); rear to 18.3; east to GHB 64.25 / SHB 64.75 | diagonal west-rear, behind GL_A, to SHA (66.94, 22.75) / GHA (23.25) |
| Lane length | ~12.5 mm (slot ~1.2 × 12.5) | ~6.7 mm (x-slot, parallel to the feed) | ~12.5 mm |

**The 15 nets.** Lengths are pin to pin and approximate.

| Net | Layers | Vias | Route | Length |
|---|---|---|---|---|
| W_GHC | L1 → L4 → L1 | 2 | Q5.4 → mouth via → C lane → up behind RS3/C31 → U2.18 | ~25 mm |
| W_C (SHC) | L1 → L4 → L1 | 2 | Pick-up in the mouth pour, at the LS-drain/HS-source junction (SLVA951 §6.3) → paired with GHC → U2.19 | ~25 mm |
| W_GLC | L1 | 0 | Q6.4 → strip y≈12.9 → RS3 gap → rear → U2.20 | ~22 mm |
| W_SLC | L1 → L4 | 1 + POFV | SL pad inner-rear corner → via in the RS3 gap rear → L4 → U2.21 | ~15 mm |
| W_SNC | L1 → L4 | 1 + POFV | NT3 → via → L4, passing under GLC/SLC so it ends leftmost → U2.22 | ~15 mm |
| W_GHB | L1 → L4 → L1 | 2 | Q3.4 → B mouth → x-lane under Q4 → C\|B channel → U2.17 | ~27 mm |
| W_B (SHB) | L1 → L4 → L1 | 2 | Mouth pour → paired → U2.16 | ~27 mm |
| W_GLB | L1 | 0 | Q4.4 → RS2 gap → U2.15 (front-most trace of the bundle) | ~12 mm |
| W_SLB | L1 → L4 | 1 + POFV | Via in the RS2 gap rear, under GLB → U2.14 | ~6 mm |
| W_SNB | L1 → L4 | 1 + POFV | NT2 (move it to the gap rear, like NT3) → via → U2.13 | ~6 mm |
| W_GHA | L1 → L4 → L1 | 2 | Q1.4 → A mouth → A lane → up behind RS1/C25 → U2.8 | ~26 mm |
| W_A (SHA) | L1 → L4 → L1 | 2 | Mouth pour → paired → U2.9 | ~26 mm |
| W_GLA | L1 | 0 | Q2.4 → RS1 gap → diagonal → U2.10 | ~16 mm |
| W_SLA | L1 → L4 → L1 | 2 | RS1 gap → L4 → up at U2's front-right corner (x ≈ 68, y ≈ 21.5) → U2.11 | ~11 mm |
| W_SNA | L1 → L4 → L1 | 2 | As SLA, ending front-most → U2.12 | ~11 mm |

Gate-loop estimates:
- **HS:** ~25-27 mm × 0.40 nH/mm plus 2 via-pair transitions of ~1 nH each (L2-L3 cavity, 1.23 mm, 1.1 mm spacing)
  = **≈ 12-13 nH**.
  - With the model's Cgs of 3.9 nF and internal Rg of 1.95 Ω: Z0 ≈ 1.75 Ω, ζ ≈ 0.56, f0 ≈ 23 MHz. Damped.
  - With current-mode IDRIVE (60/120 mA) this loop does not set the edge rate.
- **LS:** 12-22 mm over L2, with no via, ≈ 3-5 nH. This is the loop TI singles out.
- For comparison, v1's pin-to-pin gate runs were 10-28 mm.

### 4.1 Enabling changes

1. **Cells B and A +0.6 mm in x.**
   - This takes the C|B door from 0.81 mm to 1.22 mm pad-to-pad.
   - Q1's courtyard ends at 83.25, which is fine against the 84.6 limit.
   - JW1 stays at x 76.6. A shift would overlap MH2's washer zone, and JW1 still bridges Q2's tab and Q1's pins
     through the strip in front of Q1.4, as in cell C today.
2. **L3 VBAT/GND boundary at y = 16.0 for x ≥ 44.5.**
   - The cap VBAT vias sit at y ≤ 14.6. The feed band keeps y ~1.5-16.
   - L4 must be solid under L3 VBAT (now y < 16.3). Behind that, L4 over L3 GND takes the Kelvin hops, so B's Kelvin
     vias can sit **inside** the RS2 gap and not in U2's fan-out strip.
   - The shunt and cap GND pads also gain L3 GND under them.
   - **Exception:** the C and A lanes cross this boundary as a balanced pair, 1-2 mm from the cell's 10 µF VBAT-GND
     cap. That cap is the stitching capacitor adversarial/electrical asked for. Record both lane exceptions in DESIGN
     §6.2 and the custom DRC as named rule areas.
3. **U2 +1.0 mm to the rear**, to (63.5, 24.0).
   - The front strip is 1.775 mm today, from the band copper at y 17.35 to the pin-20 pad at 19.125.
   - At x ≈ 61.6 the gate bundle has **6 L1 traces** (GLC, SHC, GHC, GHB, SHB, GLB), which need 2.55 mm. After the
     move there is 2.78 mm.
   - U2's courtyard rear lands at 28.17 against J4's 28.18.
   - The buck column follows: D2 ends at 34.59 against the 34.6 limit. **Re-run place.py and check the buck input loop
     (DESIGN 6.7).**
4. **POFV at U2 pins 13, 14, 21, 22 (Kelvin) and 23, 24 (SOx).**
   - Without it, the C/B Kelvin and SOx need up-vias in front of the 0.5 mm pad row. That means 8-10 L1 traces at
     x ≈ 61.6, which needs ~4 mm of strip and U2 ~2.4 mm further back. J4 blocks that.
   - Memo 3.1 already says to order POFV. Confirm with JLC that a 0.15-0.2 mm via fits in the RGZ pad.
5. **Move out of the fan-out paths:**
   - C23 and TP6, from the strip in front of U2's front-left.
   - R22, R24, R26, from behind RS3. C's Kelvin/GL exit there.
   - TP3 and TP4, from A's diagonal.
   - R21, R4, R20, C20, rearward along U2's east edge. The FB divider stays at pin 1.
6. **Optional:** move NT1 and NT2 to the rear of their GND pads, like NT3, so that SN starts behind the gap.

## 5. Risks and checks

- **Inductance:**
  - The commutation loop is unchanged.
  - Feed +0.2-0.5 nH, inside the SPICE's 2-5 nH assumptions.
  - HS gate loops ~12 nH, damped.
  - If P3 finds the HS gate ringing too high, the lever is IDRIVE, which is already at 60/120 mA. Gate resistors are
    not the lever.
- **Rule exceptions to record:**
  - Two L4 y-lane slots of ~1.2 × 12.5 mm and one x-lane of 1.2 × 6.7 mm under the L3 VBAT band.
  - Two lanes crossing the new y = 16 VBAT/GND boundary as pairs.
  - SH is a phase-node trace on L4 for ~12 mm. It is a signal trace; rule 16's "phase strips L1-only" is about the
    current-carrying strips.
- **Plane integrity:**
  - 12 gate vias through L2 and L3, all in pairs with a web of ≥ 0.38 mm.
  - The mouth vias sit in the ring interior, where no L1 conductor lies above L2.
  - Run the plane-integrity check.
- **Tightest clearance:** GHB at the C|B door, 0.166 mm to the Q5 tab. Hold it with a fixed 45° segment, or shift
  B/A by 0.7 mm instead of 0.6.
- **Fan-out:** the U2 front strip is the real bottleneck for **any** option. §4.1 items 3 and 4 are prerequisites,
  not polish.
- **Not verified:**
  - Pours are not modelled in the check.
  - The lane-slot inductance is a first-order estimate, not a field solve.
  - J3's clearance to the A pair (0.25 mm) is copper-only.

## 6. Sources

- TI SLVSDJ3D, DRV832x data sheet §11.1 Layout Guidelines: https://www.ti.com/lit/ds/symlink/drv8323.pdf
- TI SLVA951, Layout Guide for the DRV832x Family (§4, §6.2-6.5, §7): https://www.ti.com/lit/pdf/slva951
- TI SLVA959B, Best Practices for Board Layout of Motor Drivers (§4, §6.2-6.3): https://www.ti.com/lit/an/slva959b/slva959b.pdf
- TI SLPA010, Ringing Reduction Techniques for NexFET (optimized layout, CSI pick-up): https://www.ti.com/lit/an/slpa010/slpa010.pdf
- Repo:
  - kicad/v2/spec.py (CELL, FETS, KEEPOUT)
  - kicad/v2/out/geom_place.json
  - kicad/v2/out/fr/routed.kicad_pcb (trial routes)
  - DESIGN.md §3.2, §5, §6.1-6.2
  - review/v2_lessons/README.md §3.1, §5
  - review/v2_lessons/electrical.md C4-C6
  - review/v2_lessons/adversarial/electrical.md
  - spice/sim_weapon_bridge.py and spice/sim_hotplug.py (FET cgs 3.9 nF, rg 1.95 Ω)
