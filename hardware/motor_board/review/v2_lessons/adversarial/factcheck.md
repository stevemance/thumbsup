# Fact-check of the v2 lessons memo (README + design / process / electrical / critique)

Ground truth: `kicad/motor_board/motor_board.kicad_pcb` at 10a9f15 (identical copper to 79dc2e9), queried read-only
with pcbnew; `kicad-cli pcb drc`; `design/netlist.csv`, `mcu_pinmap.md`, `bom.csv`, `ref/STM32G474RxTx_pins.xml`,
DESIGN / PLACEMENT / FAB / ROUTING_PLAN / calcs, and `git log`. Coordinates are in the PLACEMENT frame (origin at the front-left).

## 1. WRONG claims and contradictions, ranked by impact on the restart

**W1. The via budget compares two different ratios, and v1 already meets the v2 target.** (README §3 "Vias",
critique §8, process §10)
"688 vias (2.2 per signal connection)" is 688 / 311: every via on the board, including 269 GND, 58 VBAT and
46 +3V3, divided by the signal connections only. Signal vias per signal connection were:
- 304 / 311 = **0.98** using the memo's own figures;
- 291 / 267 = 1.09 by my count (signal nets only, power and phase nets excluded).

So "budget ≈ 1.1 per connection (v1: 2.2)" is a target v1 already met. The critique's "roughly 120-150 signal
vias against 304" works out to about 0.45 per connection, which contradicts its own "~1.1" (1.1 × 311 ≈ 340).
Fix before using this as a gate: define the metric (signal vias ÷ signal connections), set the target from the
120-150 figure (about 0.4-0.5), and budget the GND and rail drops separately.

**W2. Moving TIM1 to "one edge, pins 35-44" is presented as free. It is not.** (README §1.2, critique §3 and §11.2)
The AF data is right: TIM1_CH1-3 = PA8/PA9/PA10 (42-44) and CH1N-3N = PB13/PB14/PB15 (35-37). The memo leaves out
three conflicts:
- **ADC5_IN1/IN2 exist only on PA8/PA9** (checked in the XML). They carry L_SOA_F/L_SOB_F today, and with OPAMP5
  (PC3) they make up the left drive's dedicated ADC5 group. Moving TIM1 there moves the left CSA to another ADC.
  ADC1-4 are already assigned to the weapon and the right drive, so the per-motor sampling scheme has to be
  redesigned.
- **PB13 carries R_SOB_F (ADC3_IN5).**
- **PC8 is the only TIM20_CH3 pin** (R_INHC). The critique's "TIM8_CH1-3 on PC6/PC7/PC8 on the same edge" collides
  with it.

design.md §11 lists "ADC5 PA8/PA9" as a fixed pin, while README and critique put TIM1 there. That is a direct
contradiction. The critique does mention "PA8/PA9 … would have to move", but not what it costs.

**W3. The right-drive VM feed defect is misdescribed, and it is worse than stated.** (electrical C8, C14, E;
design §14)
- A connectivity test on VBAT copper, with the L4 tracks removed, splits the net. **R402.1, U2.47 (buck VIN), C27
  and R4 are joined to VBAT only through the 21 mm, 0.15 mm L4 track** (via (67.95, 23.15) → (73.05, 22.55) →
  (73.05, 30.2) → via (66.55, 32.4)).
- electrical calls that track "the R4/R402-area sense branch" and says R402 is "fed through 0.3 mm tracks". In fact
  the right drive's 1-1.5 A rms (8 A peak) and the buck input both run through about 140 squares of 0.15 mm
  inner copper.
- design §14 says "R402's feed (~36 mm) wraps U1: 25.8 mm on B, 12.5 on L5, 7 on L3". Those three numbers are
  **R_VM**, the filtered side from R402.2 to C410 (B 26.0 / L5 12.6 / L3 7.1). That path stays at x > 57 and does
  not wrap U1.
- The R302 part is confirmed: about 15 mm of 0.3 mm B.Cu from the RS4 area to a via at R302.

The v2 rule is still right. The defect list should say "R402 + buck VIN on a 0.15 mm L4 trace".

**W4. The files disagree on the weapon gate corridor.** (design §13/§15 vs critique §4 vs electrical C5)
- design: "the bridge, U2 … and **the gate corridor** form one rigid macro … never cut through it". The bottom
  gate corridor is listed under "keep-outs that paid off".
- critique §4: "Under the bridge … **No reserved 'gate corridor': gates route on L1**".
- electrical C5: low sides on L1 between the shunt pads, or on L4 over an L3 GND strip.
- README §2 reuses the macro "as a rigid block".

Nobody has checked that L1 has room for GHx/SHx pairs inside the v1 U-cells. Decide this before reusing the
macro. Separately, electrical C5 gives the corridor as "x 34.5-70.5, y 8.5-19". The board's B.Cu keep-out is at
x 44.45-80.55, y 8.55-19.05, so electrical uses the coordinates from before the cell-C move.

**W5. The bottom height limit is stale.** (README §5)
"sets the bottom-side height limit (≤ 1.1 mm parts)" is the old assumption in DESIGN 6.13. PLACEMENT 5.1 says the
user relaxed it. v1's bottom already carries U1 at 1.6 mm, 1206 caps at 1.8 mm and J3 at 3.35 mm. The critique's
floorplan also puts 1206 bulk caps under U3. Let the mated J1 height set the limit, not 1.1 mm.

**W6. The W_INLx lengths disagree, and neither version is right.**
- README §1.4 and critique §2/§11: "U6 turned 3 short links into **six 58-70 mm** nets".
- design §5: "27-45 mm each". That is ROUTING_PLAN's pre-6-layer figure.
- Measured: W_INLA 38.4, W_INLA_M 37.7, W_INLB 64.8, W_INLB_M 69.7, W_INLC 57.6, W_INLC_M 58.2 mm. The range is
  **38-70**, and two of the six nets are about 38.

**W7. Test pads.** (critique §2, design §8)
- "8 of the 12 … are **2 mm** top pads": TP2 and TP7 are **1.0 mm** pads. The critique's own recommendation
  ("1.0 mm pads are enough") is already v1.
- Of the eight, TP5 sits at (31.95, 11.4) in the front power region, not the logic core. TP7 is at x 46.1.
- design says "TP2-TP6 and TP12 were placed 'above the MCU'". Only TP2 and TP4 (y 20.3, U1's front row) are over
  U1. TP3 (15.0, 25.6) and TP6 (16.6, 13.1) are 13-20 mm west of it, and TP12 (26.5, 25.8) is outside U1's
  x-range of 29.5-41.6.

**W8. Several process durations do not match the git history.**
- README says "four days of incremental patching". The freeze-and-edit tail ran from 5bbda02 (09-27 11:43) to
  3d6b776 (09-28 19:02), about 31 h. Routing as a whole ran from 09-25 10:33 to 09-28 19:02, about 3.4 days.
- process "09-28 overnight … rounds 26-47": the commits run 09-28 06:57-19:02 (daytime). Rounds 26-27 were
  09-27 22:15-23:25.
- "Roughly 30 h of routing effort" is not supported: about 80 h passed between the setup and the last round.

**W9. Smaller errors.**
- critique §6: "the design uses about 57 pins". 51 of the 52 I/O pins are used (only PC6 is NC), and 63 of 64
  pins are connected.
- critique §1: the "largest footprints" list stops at U6 (40.3 mm²) but skips U3/U4 (46.5) and Q1-Q8 (42.2 each).
  U6 is about 12th, not in the top eight.
- critique §1: "signals 304 over 105 nets". 688 − 269 − 58 − 46 = 315 vias over 108 nets. The 11-via gap is not
  explained.
- critique §6: C1's 2.8 A rms ripple rating is cited to "calcs 85". It is in DESIGN (C1 row) and BOM.md. calcs
  line 85 is the ~8 A rms ripple that C1 shares with the MLCCs, which matters for the C1-shrink proposal.
- electrical C8: "the sim sits near the 4 V/µs limit" follows ROUTING_PLAN. calcs §7 gives ≤ 2.75 V/µs (2.82 V/µs
  cold), which is about 70 % of the limit.
- design §7 has "R62 was 35 mm from D3" and design §9 has "R62 22 mm from D3 at 75 mm". The two disagree inside
  one file. Commit 0d0b06b says 35 mm.
- critique §4: "JR1-3 (83, 20-30)" and "U4 about (79, 25) as in v1". v1 has JR1-3 at y 18.25-25.85 and U4 at
  (76.55, 24.55).
- critique §2: the L3 VBAT pour spans "x 21-85, y 4-20". The pour bbox is x 21.05-82.85, y 1.55-18.25, which
  electrical has right.
- README §1.1: "20-30 % smaller" than the DESIGN 6.13 estimate. 2987 against 3600-4400 mm² is 17-32 %.
  Courtyards were within the estimate (top 1731 against about 1900; bottom 806 against 700-900). The shortfall was
  outline, not parts.
- design §11 says rev L2 was "never applied". It was applied in the rejected "front end into the band" trial
  (48 open, ROUTING_PLAN), just not kept.

## 2. UNSUPPORTED (no evidence in the repo; treat as unverified)

- JLC facts: that the default inner copper is 0.5 oz (FAB.md says so, but nobody checked it against JLC), that
  1080/3313 thin-prepreg 4-layer builds come with 1 oz inner copper, the 4-layer via-in-pad price, and 2 oz
  minimum spacing. Check all of them on the order form, as electrical E already says.
- Transcript-only figures: the Freerouting results (458 items; 241 unrouted / 479 violations; 5,090 locked items),
  56 + 10 guard refusals, "the assistant asked for 8 layers repeatedly", "user choice" for 4 → 6 layers, "9 of the
  last 17 opens trace to placement", 132-experiment batch, 2-5 % sweep yield.
- "~250 mm² freed" by moving U8/J4 off the board. DESIGN 6.13 names the lever but gives no area.
- The critique's expected v2 lengths (U1-U2 12-18 mm, W_INLx 15-20 mm total, halls 8-12 mm) are estimates, not
  measurements.
- "Gates on L1" in the U-cells (see W4) has not been checked for fit.

## 3. CONFIRMED (spot list)

- **Board and copper:** 85.1 x 35.1 mm, 6 Cu; courtyards 1731 + 806 = 2537 mm2 (85 %); 688 vias (GND 269,
  VBAT 58, +3V3 46; sizes 193/254/241); track F 989, B 1283, L3 954, L4 809, L5 300 mm.
- **Nets:** every longest-net and per-layer per-net length in critique section 1 and design sections 5, 6 and 16
  (SPI_MOSI at 80 mm is missing from the "longest" list); east bus 11 lanes plus R_S1; L3 VBAT 673 mm2; L4 +3V3
  1828 mm2; L1 pours; in-pad vias U2/U3/U4 16/15/15 and RS2 8; net-class widths and the thin VBAT/R_VM/L_VM runs.
- **DRC:** 13 unconnected, exactly design.md's list, and the other DRC items are warnings. R20.1 is about 12 mm
  from +5V.
- **Positions:** U1, U6 (under RS4's VBAT pad), U9, J1, J2, J3 (order reversed), C1, RS4, JP2, C410.
- **MCU:** the edge facing of every pin group; the 7 opposite-side nets; weapon nets on 3 sides; the TIM1 AF pins;
  TIM20 PB2/PC2/PC8; COMP3/1/6; encoder timers; SPI3; SWD; rev L2 is AF-legal. USART1 also exists on PB6/PB7 at
  the west (J1) edge, which the memo does not mention.
- **Other:** the LVC3G17 pinout; U2, U3 and J1 pin numbers; the BOM part claims; the stack-up and calcs figures;
  0.49 mOhm/sq; every commit-cited open count and the plateau and tail timings.
