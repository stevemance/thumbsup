# Adversarial review: C25/C26/C31 1206 X5R (C13585) -> 1210 X7R GRM32ER71H106KA12L (C77102)

Verdict: **ACCEPT WITH CONDITION.** Conditions are listed at the end.

I tried to break the change on ten points. None of them holds up as a reason to reject. Two layout items remain: phase B's cell needs ~0.6 mm more width, and the flex-crack rules apply to the 1210.

## Evidence used
* Murata datasheet GRM32ER71H106KA12 (typical charts, rendered from https://datasheet.octopart.com/GRM32ER71H106KA12L-Murata-datasheet-62317418.pdf):
  * body 3.2 x 2.5 x 2.5 mm, 110 mg, X7R, -55 to 125 C;
  * DC bias about -22 to -25 % at 16.8 V.
* For an ESL and ripple comparison I used Murata's 1206 50 V 10 uF X5R, GRM31CR61H106KA12 (https://datasheet.octopart.com/GRM31CR61H106KA12L-Murata-datasheet-17853164.pdf). Its body is 3.2 x 1.6 x 1.6, rated -55 to 85 C, and its DC bias is about -80 % at 17 V. It stands in for Samsung CL31A106KBHNNNE, which has the same case and dielectric class.
* LCSC C77102: 42,520 in stock (2026-09-29), $0.21-0.33. JLC lists it as Extended.
* Frozen v1 board (`kicad/gen/frozen/board.kicad_pcb`), measured with pcbnew: courtyard gaps around C25/C26/C31.
* KiCad stock footprints:
  * C_1206: pads 1.15 x 1.8 at +-1.475, courtyard +-2.3 x +-1.15.
  * C_1210: pads 1.15 x 2.7 at +-1.475, courtyard +-2.3 x +-1.6.
* `spice/bridge.out` and `spice/fault_kick.out`.

## Point by point

| # | Attack | Finding | Result |
|---|---|---|---|
| 1 | ESL: 1210 worse than 1206 | Both have the same 3.2 mm current path, and the 1210 is wider (2.5 vs 1.6), which lowers ESL.<br>From Murata's \|Z\| curves (inductive branch, ~0.5 ohm at 100 MHz, ~5 ohm at 1 GHz), both are about 0.8-0.9 nH on the fixture.<br>Self-resonance: ~1.3 MHz for the 1210 (at 0 V; the capacitance is higher) against ~2 MHz for the 1206.<br>The 1210 is taller (2.5 vs 1.6 mm), which adds a little internal loop height. That is second-order, and the wider pad (2.7 vs 1.8 mm) offsets it. | No regression |
| 1b | Effect on SHx / VDS | bridge.out at 60 mA IDRIVE:<br>&bull; 6 nH loop: VDS 26.0 V (1210) vs 26.1 V (1206), SHx -4.34 V in both.<br>&bull; 12 nH loop: VDS 30.6 / 30.7 V.<br>&bull; Rail 16.4-17.2 V vs 16.1-17.6 V.<br>The sims give both packages the same 0.3-0.4 nH ESL. Murata's data suggests ~0.8 nH per part, but that applies equally to both, so the comparison stands. It moves the absolute loop by about 0.5 nH, which is worth ~0.3-0.5 V of VDS at the 3-6 nH slope in bridge.out. The margin to 40 V stays about 13 V. | No regression, small improvement |
| 2 | Ripple current and self-heating | At 24 kHz each 1210 is ~0.87 ohm at 7.6 uF; the three together are ~0.29 ohm. C1 is ~0.03 ohm, so C1 takes most of the ~8 A fundamental and each MLCC sees roughly 0.3 A of fundamental plus the edge content, on the order of 1 A rms.<br>Murata's temperature-rise curve (100 kHz):<br>&bull; 1210: ~20 C rise at ~5 A rms, ~9 C at 3 A.<br>&bull; 1206: ~20 C at ~3 A, ~10 C at 2 A.<br>The 1210 carries about 1.6x the current for the same rise. | Improvement |
| 2b | Temperature rating | The old part is X5R, rated to 85 C, and its VBAT pad sits on a weapon FET's drain tab (the hottest copper on the board, where TH1 is placed). X7R is rated to 125 C and loses about 15 % at 125 C. | Real improvement the proposal did not mention |
| 3 | Resonance with C1 (lower ESR means less damping) | The MLCC ESR falls from ~5 mOhm (1206) to ~3 mOhm (1210). What matters is Z0 = sqrt(L/C) against C1's ESR.<br>With ~8 nH (C1 3 nH + 5 nH plane):<br>&bull; 3 x 1206 (~7 uF): Z0 ~34 mOhm, 670 kHz, Q ~1.6.<br>&bull; 3 x 1210 (~23 uF): Z0 ~19 mOhm, 370 kHz, Q ~0.9.<br>The larger capacitance lowers Z0 towards C1's 20 mOhm ESR, so the tank is better damped. The simulated rail ripple agrees: 1.1 V against 1.5 V at 20 mOhm. At C1 300 mOhm (-40 C) it is overdamped in both cases. | Improvement |
| 4 | Fault-kick side effects | fault_kick.out, the 1210 option compared with the 1206 baseline:<br>&bull; 200 ns column: 0.57-0.63 V/us against 1.54-1.89.<br>&bull; -40 C: 0.59 against 2.01.<br>&bull; VDS-only phase-to-phase residual: 4.29 against 7.71 V/us.<br>&bull; VBAT peak: 17.5 V against 19.8 V.<br>One figure is marginally worse: the 50 ns fall in the nominal/stiff 1.0 us cases goes from 2.71-2.88 to 2.93 V/us, still well under 4. The 5 ns fall is 5.27 against 4.80, but that column is ESL-dominated and is not a design limit (DESIGN uses 50 and 200 ns). | Net improvement; the 50 ns fall is +0.2 V/us, not a concern |
| 5 | Flex crack (unfused pack) | The 1210 has the same length as the 1206 but is 0.9 mm wider and 0.9 mm thicker. A stiffer body passes more strain to the terminations, so it is somewhat more crack-prone for the same board bend. The bus is switched but has no current limit once Q7/Q8 are on.<br>DESIGN §6.10 already lists 1210 (orientation, >= 3 mm from holes). In v1, C26 and C31 were standing across the board as documented exceptions (PLACEMENT.md, "Flex rule exceptions"); the argument there still holds (the board is held at its corners, strain runs mostly along x, 12-28 mm from the holes).<br>Mitigation: no soft-termination 10 uF / 50 V 1210 checked at JLC; the Murata GRJ/GCJ series would be the option if wanted. | Accept under §6.10 (keep the existing exception reasoning or orient them along x) |
| 6 | JLC availability | C77102 is Extended with 42.5k at LCSC (~68k reported earlier at JLC). It is already loaded for C302/C308/C402/C408, so the 3 extra units per board add **no new extended-part fee**. C13585 leaves the BOM entirely (it was a Basic part, so no fee is saved; the BOM loses one line). Cost is about +$0.35/board.<br>Alternate: Samsung CL32A106KBJNNNE (C380537, X5R, ~-30 %). It keeps the 85 C limit, so prefer the Murata part. | OK |
| 7 | Footprint | KiCad C_1210_3225Metric: pads 1.15 x 2.7, gap 1.8, span 4.1 mm. Murata's typical 3.2 x 2.5 reflow land is narrower, about 1.9-2.5 mm wide, against KiCad's 2.7. KiCad's pad is wider than the body, which gives slightly larger side fillets. This is harmless and matches the IPC nominal land. It is the same footprint already accepted for C302/C308 (jlc_footprints.md). | OK |
| 8 | Height and mass | 2.5 mm on the top side is fine: C1 is 10.5 mm. The part weighs 110 mg against about 30 mg for a 1206, roughly 3.5x the shock load on its joints. That is still tiny, and the part is not staked. | OK |
| 9 | Cell geometry (v1 cells, frozen board) | The length along the loop is unchanged: pad pitch 2.95, courtyard +-2.3 on both, so the VBAT pad still lands on the drain tab and the gap to Q1/Q3/Q5 (0.21 mm) is unaffected. The courtyard widens +-0.45 mm across the loop.<br>&bull; **C25:** RS1 is 0.16 mm to the left, JR3 0.96 mm to the right. It fits by shifting +0.29 mm, away from RS1, leaving 0 / 0.22 mm.<br>&bull; **C31:** RS3 is 0.16 mm to the left and nothing is within 1.5 mm on the right. It fits with a +0.29 mm shift.<br>&bull; **C26: does not fit as is.** RS2 is 0.16 mm to the left and TH1 0.16 mm to the right, so it is 0.58 mm short. Move TH1 (0402 NTC; there is room behind or beside the Q3 tab) or widen cell B by ~0.6 mm.<br>Shifting the cap 0.29 mm away from the shunt's GND pad adds very little loop area, and the 2.7 mm-wide pads more than offset it (wider current sheet). v2 is re-placing anyway, so this is a placement input, not a blocker. | Condition (cell B) |
| 10 | Docs consistency | `design/motor_board.py:209-211` already has C1210/C77102. DESIGN.md §3.2 (line 149, "10 uF 1206 ... X5R ~2.3 uF") and the §5 sim text still describe the 1206. The BOM line for C25/C26/C31 needs the new part. The CHANGES.md entry also needs updating. | Condition |

## Conditions
1. **Layout, phase B:** in the v1-style cells, C26 needs ~0.6 mm more width than the old 1206. Move TH1 or widen cell B. C25 and C31 fit with a ~0.3 mm shift away from their shunt; keep the VBAT pad on the drain tab.
2. **Flex rules:** apply DESIGN §6.10 to C25/C26/C31 as 1210s: orient parallel to the nearest edge/standoff line, >= 3 mm from holes, or keep and restate the documented across-board exception with its strain argument.
3. **Docs:** update DESIGN §3.2 (and the §5 sim rows) to "10 uF 50 V X7R 1210, ~7.6 uF at 16.8 V". Update the BOM row and CHANGES.md, and state the X7R 125 C benefit next to the FET drain tab.
4. **Optional sim note:** `sim_weapon_bridge.py` and `sim_fault_kick.py` give the MLCCs 0.3-0.4 nH ESL. Murata's curves show about 0.8 nH for both packages. This is a pre-existing optimism that does not change the comparison, and it costs about 0.5 V of VDS margin out of ~13 V.

## Not a reason to reject
* ESL: equal or better.
* Ripple: about 1.6x the headroom.
* Damping against C1: better.
* JLC: no new fee.
* Height: fine.
