# Adversarial review: v2 part swaps (function and fitness)

Reviewed: `review/v2_parts/proposal.md` (recommended set, items 1-4, 6, 7, 8a, 9).
Sources: `design/motor_board.py` (MB), `DESIGN.md`, `design/calcs.md`, `kicad/lib_build/parts.py`,
the proposer's datasheets in `/home/smance/.claude/jobs/35ed3eaa/tmp/v2parts/`, and the repo datasheets in
`/home/smance/projects/thumbsup/hardware/motor_board/datasheets/`, which I extracted to `/tmp/advp/`
(DRV8323 SLVSDJ3, LMR16006 SNVSA24, DRV8316C SLVSH07, JST XH, JST SH, 1N4148W). I also fetched ROHM's ESR datasheet.
All 11 C-numbers were re-queried at JLC and are the claimed MPNs.
No repo files were edited.

## Summary

| # | Swap | Verdict |
|---|---|---|
| 1 | U6 → SN74LVC08ABQAR WQFN-14 | **ACCEPT WITH CONDITION** (add pad 15 = GND to the symbol and the pin map; keep it on the top side or accept that a leadless part can't be inspected) |
| 2 | D2 → PMEG4030ER CFP3 | **ACCEPT WITH CONDITION**: the proposal's thermal argument is wrong (see below). The short-circuit survival claim needs cathode copper or has to be dropped. |
| 3 | L1 → ZEMS404030-220M | **ACCEPT** (Isat and the land pattern verified; the proposal's pad-width worry is unfounded) |
| 4 | J4 → B5B-XH-A vertical | **ACCEPT** (height is a layout item) |
| 6 | J2/J3 → BM06B-SRSS-TB vertical | **ACCEPT WITH CONDITION** (no electrical mirroring; mechanical strain relief; doc updates) |
| 7 | R300/R400 → ESR03EZPJ220 0603 | **ACCEPT** (equal rating and derating, anti-surge series; the pulse energy is ~1 mJ) |
| 8a | 4 × 1206 → 2 × 1210 per drive | **ACCEPT WITH CONDITION: needs user approval** (it removes C309/C310/C409/C410 and breaks the DESIGN §6.6 contract; the 1210 DC-bias figure is unverified) |
| 9 | R15 / C14 / D10 one size down | **ACCEPT** all three |

## 1. U6 SN74LVC08APWR → SN74LVC08ABQAR (C31971766)

* **Pin numbers identical: verified.** SCAS283W Table 4-1 (`sn74lvc08a.txt:152-186`) has a single pin-number column for
  "SOIC, SSOP, SOP, CDIP, TSSOP, VQFN, WQFN": 1A=1, 1B=2, 1Y=3, 2A=4, 2B=5, 2Y=6, GND=7, 3Y=8, 3A=9, 3B=10, 4Y=11, 4A=12,
  4B=13, VCC=14.  This matches the MB U6 pin map exactly (MB:236-241).
* **Thermal pad: verified.** "The thermal pad can be connected to GND or left floating. Do not connect to any other signal
  or supply" (footnote: BQA only, `:175-186`).  The package drawing says it "must be soldered to the PCB for optimal
  thermal and mechanical performance" (`:1446`, `:1514`), so the pad must exist and carry paste.  Tie it to GND.
* **Footprint: verified.** In KiCad `DHVQFN-14-1EP_2.5x3mm_P0.5mm_EP1x1.5mm`, pads 1 and 14 sit on the top short side (1 at −0.25),
  2-6 run down the left, 7 and 8 sit on the bottom, 9-13 run up the right, and pad 15 is 1.0 × 1.5.  TI's BQA0014A example land (`:1453-1500`) has the
  same arrangement and the same 1.0 × 1.5 exposed pad.  KiCad's pads are 0.825 mm long against TI's 0.6 mm.  That is an IPC toe extension and is fine.
* **Logic unchanged.** It is the same die and datasheet.  Note: U6 does **not** implement DRV_OFF.  DRV_OFF is PC14 straight to U3/U4
  pin 21, with R50 pulling it up (MB:317).  U6 is the weapon interlock INLx = TIM1_CHxN AND W_ARM_S (MB:233-241).  The swap changes neither
  function.  The inputs keep R19 and R47-R49 as defined levels.
* **Conditions.**
  1. Add pin "15": ("EP", "GND") to the MB pin map.  The U6 symbol also needs a 15th pin, or the build's
     SKiDL↔KiCad netlist check / "pad not in schematic" DRC will flag an unconnected EP.
  2. It is leadless with 0.5 mm pitch, so AOI can't see the joints.  That is acceptable at JLC.
  3. Stock is 2,984.  Buy the board's worth now, or keep the TSSOP as a documented alternative.

## 2. D2 SS34 (SMA) → PMEG4030ER (CFP3 / SOD-123W, C389355)

* **Voltage.** VR is 40 V, the same as SS34, and it is specified at Tj = 25 °C (`pmeg4030er.txt:72`).  TI asks for 1.25 × VIN max
  (`LMR16006.txt:781`).  At the 32.4 V TVS clamp that is 40.5 V, marginally above 40 V.  The original has **the same** margin, so this is not a regression.
  SW ringing above the clamp adds to both parts equally.
* **Current.** IF(AV) 3 A, IFSM 50 A (the SS34 has 80 A; no surge case applies here).  The buck peak current limit is **1.2 A typ / 1.7 A max**
  (DRV8323 SLVSDJ3 electrical table, `/tmp/advp/DRV8323.txt:1906-1909`).  That is the variant actually fitted: the LMR16006X core
  inside U2.  VF is 0.44 V max at 1 A and 0.54 V max at 3 A, lower than the SS34.
* **Leakage and runaway.** IR is 25 µA typ / 100 µA max at 40 V, 25 °C (`:233-234`).  The SS34 is 0.5 mA max at 25 °C and 5 mA
  at 125 °C (`C8678.txt:75-77`).  The DSK34 is 0.5 mA / 10 mA at 100 °C (`C41029.txt:66-68`).  At 16.8 V, D ≈ 0.3 and
  mA-level leakage, the reverse loss is ≤ ~tens of mW.  It is not a runaway risk at these power levels, and leakage is irrelevant against the
  ≥ ~100 mA permanent 5 V load (calcs §4).  The PMEG leaks less than the part it replaces.
* **Capacitance and recovery.** Cd is 95 pF at 10 V (`:236`) against SS34 180 pF at 4 V (`C8678.txt:78`).  Lower is better for SW ringing.
  A Schottky has no reverse recovery.
* **FINDING (verified): the thermal argument is wrong.**
  * The proposal credits Rth(j-a) 130 K/W and tells you to "give the **anode** a GND pour".
  * The datasheet's 130 K/W condition is a **1 cm² cathode pad** (`pmeg4030er.txt:105-117`, note [3]).  The heat path is the
    **cathode tab**: Rth(j-sp) 18 K/W is "soldering point of cathode tab" (note [5]).
  * The cathode is BUCK_SW (MB:212), and DESIGN §6.7 requires "SW node tiny" (DESIGN.md:470).  So the realistic figure is the
    **220 K/W standard-footprint value**.
  * Into a shorted +5V at ~1.2-1.7 A (0.5-0.8 W), that gives Tj ≈ 50 + 0.6 × 220 ≈ 180 °C, which is > 150 °C.
  * The DESIGN/calcs claim "SS34 3 A: survives a shorted +5V" (DESIGN.md:192, calcs §3) would therefore not hold for this part as drawn.
  * Caveats:
    * The 4-layer board with inner planes will do better than the datasheet's single-sided FR4.
    * The SS34's 70 °C/W also assumes 5 × 5 mm pads (`C8678.txt:84-85`) and has only a 125 °C Tj, so the original's short-survival claim
      was probably optimistic too.  Treat this as a pre-existing weakness that the swap does not fix, not a new one the swap causes.
    * Whether U2's thermal shutdown ever ends a +5V short is not established.  The buck's own loss is small, so D2 may carry
      ILIMIT indefinitely.
* **Verdict: ACCEPT WITH CONDITION.** Functionally it is equal or better (VF, leakage, Cd, Tj max).  Conditions:
  1. Either give the cathode tab as much copper as the SW-node rule allows and accept a bounded short survival, or reword the DESIGN
     "survives a shorted +5V" claim.
  2. Fix the proposal's "anode GND pour" note.
  3. DSK34 fallback: same electrical class, but with SS34-level leakage and an unstated RθJA mounting condition.  Acceptable as the fallback.

## 3. L1 FNR5040S220MT → ZE ZEMS404030-220M (C49009291)

* **Isat vs the real current limit.**
  * ILIMIT is 1.7 A max for the DRV8323's LMR16006X core (`DRV8323.txt:1906-1909`).
  * TI: "22 µH with a 1.6 A current rating… current limit without saturating the inductor" (`LMR16006.txt:709-711`).
  * ZE: Isat 3.5 typ / 3.1 "Max" at −30 % L (`C49009291.txt:145-164`).  The column the proposal reads as the guaranteed minimum is
    labelled "Max" in the datasheet, so it is ambiguous, but either value is ≥ 1.8 × 1.7 A.  PASS.
* **DCR.** 190 typ / 220 max mΩ against 170.  Normal-load loss rises by +11 mW, which is negligible.  In a +5V short: 1.7² × 0.22 = 0.64 W.
  Irms is 2.3-2.6 A for ΔT 40 K, so the rise is ≈ 22 K.  PASS.
* **SRF.** It is **not given** in the ZE datasheet, and the proposal doesn't list it either.  For a 22 µH metal-alloy 4030 it is very likely ≫ 0.7 MHz.
  This is speculation, low risk.
* **Footprint: the proposal's worry is unfounded (verified from the drawing, rendered page 3).**  A = outer span 4.10,
  **B = the gap between pads 1.30**, C = pad length 4.10.  So each pad is (4.10 − 1.30)/2 = 1.40 × 4.10 mm with a 1.30 gap.  KiCad
  `L_Changjiang_FTC404030S` has pads 1.4 × 4.1 at ±1.35 (gap 1.3, span 4.1): an exact match.  The body terminals (E 1.35, G 1.4) sit
  on the lands.
* **Temperature.** −55…+125 °C including self-heating.  It is AEC-Q200-tested.
* **Verdict: ACCEPT.** Update the calcs §3 / DESIGN §3.2 inductor row: Isat, DCR, and the "soft ferrite roll-off" wording.

## 4. J4 S5B-XH-A → B5B-XH-A(LF)(SN) (C157991)

* **What J4 is: verified.** The 4S balance lead.  Pin 1 = B0 (pack −) … pin 5 = B4 (MB:147-149), and it feeds U8 through R6-R10.
* **Pinout and mating.** It is the same XH series and the same XHP-5 housing.  JST's circuit numbering is defined on the header, so plug circuit 1 goes to header
  circuit 1 for top entry and side entry alike (`JST_XH.txt:49-107`, "No. 1 circuit" on both drawings).  The netlist is unchanged.  KiCad
  `JST_XH_B5B-XH-A_1x05_P2.50mm_Vertical` pads 1-5 are in line.
* **Current.** 3 A per pin (AWG 22) (`JST_XH.txt:7`).  That is the same as today and orders of magnitude above the balance-tap currents.
* **Height.** The header is 7 mm and the mated height is 9.8 mm (`JST_XH.txt:60-75`), plus the wire bend.  That is a layout/lid item, not a blocker.
* **Check.** Make sure the footprint has no boss hole and that the plain -A (not -AM) part is ordered.  JST's top-entry drawing shows a boss for some
  variants (`JST_XH.txt:51-80`).  I did not resolve which variants from the extracted text.
* **Verdict: ACCEPT.** Keep the DESIGN §6.9 silkscreen "B−"/"B4+".

## 6. J2/J3 XUNPU R/A → JST BM06B-SRSS-TB vertical (C160392)

* **What they carry.** VS (switched 3.3/5 V through U11/U12), GND, H1/A/U, H2/B/V, H3/Z/W, and the motor NTC.  MP = GND (MB:320-326).  That covers the MT6701 ABZ
  encoder or Halls.
* **Mirroring: none electrically.**
  * JST numbers circuits on the header, and BM and SM appear in one table with the same "No. 1 circuit" marking
    (`/tmp/advp/SH.txt:61-102, 217-242`).  A 1:1 SH cable lands pin 1 on pin 1 whichever header type is used.
  * In both KiCad footprints, pad 1 is at x = −2.5 in top view (SM06B: pads at y = −2 with tabs at +1.875; BM06B: pads at y = +1.325 with tabs at −1.2).
    So the fan-out order is the same, only the signal row and the tabs swap sides.
  * The genuine JST part also removes the open item in DESIGN §6.9: the "clone's drawing does not number its pins" (DESIGN.md:482-483).
* **Rating.** 1 A / 50 V (`SH.txt:7-8`), unchanged.
* **Conditions.**
  1. A vertical SMD SH header takes cable pull as peel on its solder joints.  In a combat robot, tie the cable down near
     the header (this is mechanical and speculative in degree).
  2. Update DESIGN §6.9/§6.12 and `parts.py`: the custom XUNPU footprint and the EASYEDA_REF entry go.
* **Verdict: ACCEPT WITH CONDITION.**

## 7. R300/R400 22 Ω 1206 (C17958) → ROHM ESR03EZPJ220 0603 (C2074038)

* **Role: verified.** RBK for the unused DRV8316 buck in resistor mode (MB:299-300; SLVSH07 9.2.1.1.5, `/tmp/advp/DRV8316C.txt:4395-4404`).
  Firmware writes CTRL6 = 0x19 (BUCK_DIS) first thing (DESIGN.md:666).
* **Continuous.** P ≈ (VM − VBK) × IBK ≈ 13.5 V × 5-7.4 mA = 68-100 mW, and only if firmware never configures the chip (r5 M2, `review/r5_bom.md:87`).
  ESR03 is rated 0.25 W at 70 °C, derated to 0 at 155 °C (ROHM ESR datasheet, fetched).  At a 100 °C board next to the DRV8316 (calcs §5: +35 to +50 °C at 1.5 A plus
  50 °C ambient), that leaves ≈ 0.16 W, which is > 0.1 W.  The original C17958 (UNI-ROYAL 1206W4F220JT5E) has the same 0.25 W rating and derating, so it is equal.
* **Pulse.**
  * Before CTRL6 is written, BUCK_CL = 0, so the limit is 360-900 mA (`DRV8316C.txt:801`).
  * The start-up event is CBK 22 µF charging to 3.3 V through 22 Ω.  The energy in R is C·(VM·Vf − Vf²/2) = 22 µF × (16.8 × 3.3 − 5.4) ≈ **1.1 mJ**,
    with a peak of ≤ 16.8²/22 = 12.8 W over ~0.5 ms.
  * ROHM's anti-surge ESR series is pulse-rated, and the original 1206W4 is a plain thick-film part.
  * The ESR03 limiting-pulse curve is **not** in the short-form datasheet I fetched, so the margin number is unverified.  The 1 mJ energy is
    tiny against an 0603's thermal mass.
* **Verdict: ACCEPT.** Keep the r5 M2 firmware requirement (BUCK_CL/BUCK_DIS written first).

## 8a. VM filter: 4 × CL31A106KBHNNNE 1206 → 2 × CL32A106KBJNNNE 1210 per drive (drop C309/C310/C409/C410)

* **Needs user approval.** It removes four parts.  The user's rule is "no removals without asking" (memory: hardware-layout-v2).
  It also contradicts the DESIGN contract: §6.6 "each DRV8316 gets its 2 × 100 nF + **4 × 10 µF** within 2 mm" (DESIGN.md:469),
  §3.3 (DESIGN.md:209), and the MB descriptions of C308/C309 (MB:290-293).
* **TI requirement.**
  * TI asks for ≥ 10 µF CVM2 rated at least 2 × the normal operating voltage (`DRV8316C.txt:1490-1494`; pin table `:439-443`).
  * 2 × 1210 50 V meets both, even at a pessimistic 5 µF each.
  * TI also asks for "two 0.1 µF (for each pin)".  The design uses 2 × 100 nF for pins 9/10/11 (DESIGN §6.5).  That is pre-existing and not part of this swap.
* **DC-bias claims.**
  * The 1206 at 16.8 V is **verified** at −78 % from the proposer's saved Samsung data (`sam31.html`: −77.98 % at 16.77 V).  So the design's
    "~4 µF each / ~16 µF per drive" (DESIGN.md:209, MB:291) is overstated by ~2×.  That is a real, pre-existing contract error.
  * The 1210 at −30 % (7 µF) is **not verifiable**: no saved data, and the Samsung site refused my re-fetch.  I am sceptical that
    the 1210 retains ~70 % at 34 % of rated voltage when the 1206 retains 22 % (speculative).  At a −50 % curve the branch is 10 µF, still better than
    today's real ~8.8 µF, but the sim benefit (0 °C bounce 3.39 → 2.51 V/µs) would shrink.
* **Other checks.**
  * The sim models the branch as one lumped `cvm` (`sim_hotplug_c1.py:47-108`).  Two parts instead of four roughly doubles the
    branch ESR/ESL, which the sim does not see.  The 100 nF parts carry the HF duty, so this is a minor effect.
  * X5R is rated to 85 °C.  The board near the DRV8316 can exceed that (calcs §5), and that is equally true of today's X5R 1206.
  * A 1210 is more flex-crack-prone.  Add 1210 to the §6.10 orientation / ≥ 3 mm rule.
* **Verdict: ACCEPT WITH CONDITION.**
  1. Get explicit user approval for removing C309/C310/C409/C410.
  2. Verify the CL32A106KBJNNNE curve from a second source.
  3. Update DESIGN §3.3/§6.6, calcs §7, sim `cvm`, and DESIGN.md:36's "~16 µF" environment row.
  4. Also correct the existing ~16 µF claim whatever is decided.
  * Non-removal alternative: 4 × 1210 per drive.

## 9. One size down

| Ref | Role (verified) | Check | Verdict |
|---|---|---|---|
| R15 6.8 k 0805 → 0603WAF6801T5E (C23212, 0.1 W) | VBAT bleeder (MB:123-124; DESIGN.md:109) | 16.8²/6.8 k = 41 mW (41 %); at the 20 V OVP level 59 mW; the 154 mW at the 32.4 V clamp is transient only.  75 V element rating ≫ 32.4 V | ACCEPT |
| C14 100 nF 100 V 0805 → CL10B104KC8NNNC (C15725, verified MPN, 100 V X7R 0603) | U13 VS decoupling and the only ceramic across the unswitched pack; BAT_IN rings to 40-60 V (MB:111) | 100 V rating kept; needs ≥ 22 nF.  An X7R 0603 keeps well over 22 nF at 60 V (the DC-bias figure is not verified, but X7R 100 V has a large margin) | ACCEPT (keep the §6.10 orientation rule) |
| D10 1N4148W SOD-123 → 1N4148WS SOD-323 (C2128, CJ) | Cdvdt steering; blocks C13 pushing the gate up with a reversed pack (MB:114-115; DESIGN.md:107) | Only µA gate currents flow forward; reverse ≤ ~pack + Vgs ≈ 30 V.  The original is VR 75 V / VRM 100 V, 150 mA (`1N4148W.txt:24-26`).  The WS is the same die class (datasheet not read: speculative on exact figures) | ACCEPT |

## Items not verified

* ESR03 pulse curve.
* CL32A106KBJNNNE DC bias.
* ZEMS404030 SRF.
* The 1N4148WS datasheet.
* Whether the XH footprint needs a boss.
* The real Rth of D2 on this 4-layer board.
