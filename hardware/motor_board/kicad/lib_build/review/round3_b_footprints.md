# Round 3 (B): footprint review, motor_board parts library

Scope: the 5 custom footprints in `out/motor_board.pretty/` at c568dc2, every `Footprint` field in
`out/motor_board.kicad_sym` (28 parts), the KiCad 10 stock footprints those fields point to, and the RS4 change in
`design/motor_board.py`, `design/bom.csv`, `BOM.md` and `DESIGN.md`. I checked everything again against the vendor drawings
(pdftotext, plus pages rendered with pdftoppm) and LCSC/JLC. Tools: KiCad 10.0.6 `pcbnew` Python. Scratch files are deleted.

**Counts: 0 BLOCKER, 0 MAJOR, 0 MINOR, 5 NOTE.**

## Whole-library checks (scripted, pcbnew)

- **Pins and pads:** for all 28 symbols, the symbol's pin-number set equals its footprint's pad-number set. EP 21/41/49, the SH `MP` and HYG pad 5 are included.
- **Netlist:** every `design/netlist.csv` (ref, pin) for the 43 library-part refs exists as a pad, and no numbered pad is left unconnected.
  For every ref, `bom.csv`'s Footprint column matches the library footprint (RS4 = `R_2512_JIERR_RE_small_electrode`).
- **Overlaps:** no two differently numbered copper pads overlap. The only bbox hits are the un-numbered paste apertures inside the EPs.
- **Paste:** every numbered SMD pad has F.Paste, except the EP pads (21/41/49/HYG 5). Those use separate paste apertures.
- **Build output:** `build_lib.py`, re-run into scratch, regenerates `out/` byte-identically, so the committed files are the generated ones.
  `check_lib.py`: 0 errors, 0 warnings. The worktree was left clean.

## RS4: JIERR RE2512F3R001, `R_2512_JIERR_RE_small_electrode`: correct

- **Land:** JIERR datasheet p.5 "Suggested PCB dimensions" (rendered). The figure puts L between the pads' inner edges, b along the pad
  and a across it. For 2512 small electrode: a = 4.0, b = 2.1, L = 4.1 (large electrode: 4.0 / 3.1 / 1.3).
  Footprint: pads 2.1 × 4.0 at x = ±3.1, which gives inner edges ±2.05 (gap 4.1), outer edges ±4.15 and height 4.0. **This matches exactly.** Pad 1 is at −x and pad 2 at +x,
  with netlist RS4.1 = VBAT_SW and RS4.2 = VBAT (a resistor, so either way is fine).
- **Terminal coverage:** p.3: L 6.4 ± 0.2 and small-electrode E 1.0 ± 0.2, so the terminal runs 2.2…3.2 from centre (1.9…3.5 at the tolerance extremes).
  The whole terminal sits on the pad (2.05…4.15).
- **Courtyard:** ±4.4 × ±2.25, which is 0.25 beyond the copper. The silk bars sit at y ±2.2 over the pad gap, away from the copper. The layers are F.Cu/F.Paste/F.Mask.
- **C46961745 is the small-electrode part:**
  (a) LCSC, JLC and szlcsc.com (item 49133284) all list MPN **RE2512F3R001**, with no `L`. JIERR's ordering code (p.1) adds `L` = 大电极 (large electrode).
  szlcsc also lists a separate `RE2512F3R000L` among the related parts, so the L versions are catalogued as different items.
  (b) LCSC's product photos (1 mm grid, downloaded from alimg.szlcsc.com) show end terminations about 1/6 of the 6.4 mm body, i.e. about 1 mm.
  That is E = 1.0, not the large-electrode 2.2 (which would be about 1/3 of the body).
  The only contrary sign is LCSC/JLC's "TCR ±50 ppm/°C" attribute (see N1).
- **Design files:** `motor_board.py` line 125, `bom.csv` line 56, `BOM.md` line 37 and `DESIGN.md` line 487 all name the new footprint and the p.5 land.
  `DESIGN.md` line 452 ("U7 IN+/IN− from RS4's pad inner edges") agrees with JIERR's figure, which takes the sensing traces from the inner edges.

## DRV8316C RGF0040E: correct (independent re-derivation)

- **Pads:** SLVSH07 RGF0040E example board layout: 40X (0.6) × (0.25), (4.8)/(6.8) overall, (5.5) for pins 1-12 and (3.5) for pins 13-20, EP (3.7) × (5.7).
  Pad centres x ±2.4 give 2.1…2.7 per side. That leaves 0.25 to the EP edge at 1.85 and covers the terminal (body 4.9-5.1, L 0.3-0.5 → 2.0…2.55).
  The other convention (outer-extent 4.8, pads 1.8…2.4) would overlap the 3.7 EP, so the centre-span reading is the only consistent one.
  y ±3.4 likewise gives 3.1…3.7 against EP 2.85.
- **Numbering and paste:** numbering is 1-12 down the left, 13-20 left→right along the bottom, 21-32 up the right and 33-40 right→left along the top. This matches the land-pattern labels.
  Paste is 12 × 1.05 × 1.15 at columns 0/±1.25 and rows ±0.675/±2.025, 69 %. This matches the stencil page.
- **Pin-1 dot:** it now sits at (−2.85, −3.35), in the pin-1 corner between pad 1 and pad 40. It is 0.33 mm from pad 1's copper and 0.8 mm from pad 40's (see N2).

## Other custom footprints: re-checked, correct

- **HoLR2512 1-4 mΩ:** datasheet A 4.0 / L 1.3 / B 3.1 gives pads 3.1 × 4.0 at ±2.2 (0.65…3.75). The 1-4 mΩ terminal is C = 2.0 ± 0.2 on L = 6.4, so 1.2…3.2, all on the pad.
- **BOOMELE 1.27-2×10P:** "P.C.B Layout" 0.74 wide, 6.5 ± 0.1 overall, 1.5 row gap gives pads 2.5 × 0.74 at x ±2.0, pitch 1.27, y ±5.715. Lead span 5.5 → tips ±2.75 are inside the pad (0.75…3.25).
  Odd pins are at −x with pin 1 top, and the silk pin-1 bar is beside pad 1. The body is 3.4 × 12.7.
- **XUNPU WAFER-SH1.0-6PWB:** the drawing gives signal 0.50 × 1.70 at 1.00 pitch (5.00 span), tabs 1.20 × 2.50 with the inner edge 0.50 beyond the end pin, and 5.50 overall.
  The footprint has the same values. Its body is B = 8.35 × 4.30. The pin-1 silk bar is at −x next to pad 1.

## Stock footprints: re-checked

- **FNR5040S:** p.2 recommended land a 2.3 / b 1.4 / c 4.2 gives pads 1.4 × 4.2 at ±1.85. `L_Changjiang_FNR5040S` has the same values.
- **CP_Elec_10x10.5 vs EEH-ZK size G:** Panasonic gives D 10.0, L 10.2, A 10.3, I 3.5, W 0.9, P 4.6. The footprint pads (2.0…6.4, 2.5 wide) cover the terminals, and pad 1 is "+".
- **Packages:** 1N4148W, MMSZ5242B and B5819W are SOD-123 on their datasheets, SS34 is SMA (DO-214AC) and SMBJ20A is SMB. These match `D_SOD-123`, `D_SMA` and `D_SMB`.
  Pad 1 = K = symbol pin 1 on all six, and the netlist cathodes go to the expected nets (D1 VBAT, D2 BUCK_SW, D4 PSW_G, D5 CELL0, D10 PSW_DV).
- **Not repeated:** round 2's checks of the ICs, SOT-23 dual diodes, HYG PQFN, JST XH and 2512 still hold. The generated/stock files are unchanged since then,
  and I spot-checked VSSOP-8 (DCU: pads 0.775…2.025, 0.35 at 0.5 pitch).

## NOTES

- **N1.** LCSC/JLC list "TCR ±50 ppm/°C" for C46961745. JIERR p.2 gives ±50 ppm at 1 mΩ only for the large electrode (small, 1-1.5 mΩ: ±350 ppm).
  The MPN and the photos both say small electrode, so the attribute is the inconsistent item. Even in the worst case the land is not board-killing:
  a large-electrode part (terminals 1.0…3.2) on this land would still have about 1.15 mm of each terminal on copper.
  Confirm on the first reel or JLC's part photo if in doubt.
- **N2.** RGF0040E: the commit says the pin-1 dot is now "inside the courtyard". Its centre is inside, but the 0.3 mm dot spans x −3.0…−2.7, so it is still 0.05 mm past
  the courtyard edge (−2.95). It also nearly touches the silk corner mark: 0.03 mm to the edge of the x = −2.61 line. This is cosmetic.
- **N3.** `R_2512_JIERR_RE_small_electrode` Fab body is 6.35 × 3.2, while the datasheet says L = 6.4. Fab only.
- **N4.** In `parts.py` FOOTPRINTS, the XUNPU comment block is now separated from its `SH1.0-6P…` entry by the new JIERR comment and entry.
  The comment is misplaced, but the data is correct.
- **N5.** `DESIGN.md` line 484 still calls the library `thumbsup.pretty`. The actual library is `motor_board.pretty`.
