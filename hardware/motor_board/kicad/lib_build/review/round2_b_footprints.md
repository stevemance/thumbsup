# Round 2 (B): footprint review, motor_board parts library

Scope: the 4 custom footprints in `out/motor_board.pretty/` (as generated at 779d144), every symbol's `Footprint`
field in `out/motor_board.kicad_sym`, and the KiCad 10 stock footprints those fields point to. I checked each one
against the vendor drawings in `hardware/motor_board/datasheets/`, rendered with `pdftoppm` and measured in pixels,
and used LCSC/EasyEDA only for identifying the purchased part. All 4 custom footprints load in KiCad 10 `pcbnew`
(`FootprintLoad`). Scratch files have been deleted.

**Counts: 0 BLOCKER, 0 MAJOR, 1 MINOR, 5 NOTE.**

Pad ↔ pin (script over all 28 symbols): every symbol's set of pin numbers is identical to its footprint's set of
pad numbers (EP 21/41/49, MP and HYG pad 5 included). Nothing is missing and nothing is extra.

---

## DRV8316C / TI RGF0040E: round-1 fix verified correct

Measured on SLVSH07 p.93 rendered at 400 dpi (12X scale → 189.7 px/mm, calibrated on EP (3.7) = 702 px):

| Item | TI (measured) | Library | OK |
|---|---|---|---|
| Left/right pad columns | centres at ±2.39 (the (4.8) extension lines fall at x = 1276/2183 px, which are exactly the pad-centre pixels 1276.5/2183.5), pad 0.60 long | x = ±2.4, 0.6 × 0.25 | ✓ |
| Top/bottom pad rows | pad −3.685…−3.08 / +3.08…+3.69 → centre ±3.385 (the (6.8) line runs through the row middle) | y = ±3.4, 0.25 × 0.6 | ✓ |
| Pad 1 / pad 12 | y centre −2.735 / (5.5) span | y = −2.75 / +2.75 | ✓ |
| Pad 13…20, 40…33 | x = −1.74 … +1.74 ((3.5) span) | ±1.75 step 0.5 | ✓ |
| EP 41 | 3.70 × 5.68 | 3.7 × 5.7 at 0,0 | ✓ (package EP 3.6-3.8 × 5.6-5.8, p.92) |
| Pad-to-EP gap | 45 px = 0.24 | 0.25 (pad inner edge 2.1 vs EP 1.85; 3.1 vs 2.85) | ✓ |
| Paste (p.94) | 12 × (1.05 × 1.15), columns 0/±1.25, rows ±0.675/±2.025, 69 % | same, all inside EP (max x 1.775, max y 2.6) | ✓ |
| Terminal coverage | body 5.0 × 7.0, terminal L 0.3-0.5 (p.92) → lead 2.0/2.2…2.5 and 3.0/3.2…3.5 from centre | pad 2.1…2.7 and 3.1…3.7 | ✓ |

Numbering: in the p.93 top view, pin 1 is top-left, 1-12 run down the left side, 13-20 run left→right along the bottom,
21-32 run up the right side and 33-40 run right→left along the top. The library matches this, and so does the p.92 bottom view
after mirroring (pin 1 bottom-left in bottom view). The Table 6-1 / pinout figure (DRV8316CR: pin 1 NC, 24 NC, 26 AGND) matches the symbol.

Clearances (rectangles, from the file): pad-pad 0.25 along a side, corner pads (1/40, 12/13, 20/21, 32/33) 0.225 in x and y,
pad-EP 0.25, no overlaps. The courtyard is ±2.95 × ±3.95, 0.25 beyond the pad extents ±2.7/±3.7 and outside the max body ±2.55/±3.55.
Silk corner marks (±2.61/±3.61, w 0.12) are ≥ 0.31 mm from any pad. The pin-1 dot at (−3.1, −3.3), Ø0.3, is next to pad 1 on the
correct corner, ≥ 0.43 mm from copper. The Fab chamfer is at the pin-1 corner. **Round-1 B1 and m1 are resolved.**

## MINOR

### m1. RE2512F3R001 (RS4, pack shunt): the stock `R_2512_6332Metric` land is smaller than JIERR's land for this part
- Which variant C46961745 is (round-1 N6): the **small-electrode** part. Evidence: (a) the part number has no `L` suffix, and the JIERR
  ordering code (datasheet p.1) uses `L` = 大电极/large electrode; (b) LCSC's product photos (front/back, 1 mm grid) show
  end terminations about 1 mm long on a 6.4 mm body, which is E = 1.0 ± 0.2, not 2.2 (p.3 dimension table). The one contrary sign is LCSC's
  attribute "TCR ±50 ppm/°C". JIERR's TCR table gives ±50 ppm for 1 mΩ only in the large-electrode build (small 1-1.5 mΩ = ±350 ppm).
  That attribute is therefore inconsistent with the datasheet and should not be relied on. The JLC/EasyEDA footprint for C46961745 is a generic
  `RES-SMD_L6.3-W3.2_R2512` (2.0 × 3.46 at ±2.667) and does not help decide.
- JIERR p.5 "Suggested PCB dimensions", 2512 small electrode: a = 4.0 (pad height), b = 2.1 (pad length), L = 4.1 (gap) → pads
  2.05…4.15 from centre, 4.0 tall.
- Library (stock): 1.225 × 3.35 at ±2.9625 → 2.35…3.575, 3.35 tall. The nominal terminal is 2.2…3.2, so the pad starts 0.15 mm
  outboard of the terminal's inner edge (0.35 mm at E max 1.2) and is 0.65 mm narrower than the vendor land.
- Consequence: the joint is solderable, but there is less solder/copper than the vendor specifies on the one 3 W, 1 mΩ part that carries
  the full pack current. It is not board-killing. Fix: a custom 2-pad land per JIERR (2.1 × 4.0 at ±3.1), built the same way as `R_2512_HoLR_1-4mR`.
  Do **not** reuse the HoLR 1.3 mm-gap land: that land is for a 2.0 mm-terminal part.

## NOTES

- **N1** XUNPU SH connector, Fab outline only: the drawing's body (P.C.B LAYOUT, 400 dpi, 104 px/mm) runs from 1.49 mm below the
  signal-pad top edge to 0.24 mm above the tab bottom edge. The library's Fab body runs from 1.30 mm below to 0.10 mm beyond, so it is shifted about 0.2-0.35 mm
  toward the tabs. Copper is exact: signal 0.5 × 1.7 at 1.0 pitch, tabs 1.2 × 2.5 with the inner edge 0.50 beyond pad 6's centre (x ±3.6), pad-row to tab-row
  centres 3.39 (lib 3.4), overall 5.48 (lib 5.5). Courtyard and silk are unaffected.
- **N2** RGF0040E: the pin-1 silk dot (x −3.25…−2.95) sits just outside the courtyard (x −2.95). This is cosmetic and KiCad does not flag it.
- **N3** HYG015N04LS1C2 on `PQFN-8-EP_6x5mm_P1.27mm_Generic`, re-derived from p.7: H 0.5 + E2 3.82 + K 1.26 + L 0.58 = 6.14 ≈ E1
  6.15, so the source leads are at 2.495…3.075 and the EP at −1.235…+2.585 from centre (source side negative). Pads 1-4 span 2.15…3.3, and pad 5 spans −1.1…3.5 with core
  width 4.2 (D2 4.25) and 4.7 over the drain bumps (D1 5.2 → bump tips at ±2.1). The pad-1-4 to pad-5 gap is 1.05. Pads 1-3 S, 4 G, 5 D match the symbol. OK.
- **N4** Carried over, still true: SH connector pin 1 is not marked on the XUNPU drawing (JST SM06B numbering assumed; KiCad's JST footprint
  agrees: pad 1 at x −2.5 on the signal row); BOOMELE has no pin-1 feature, so the mating socket must mirror the numbering; RGF0040E and HYG PQFN
  are rotated 90° relative to JLC's footprints, so expect CPL rotation corrections; KT-0603R vendor pin ① is the anode (net mapping is right, check the
  JLC placement preview).
- **N5** Other stock footprints were re-checked for pad geometry and pin-1/polarity against the purchased part: BQ76907 RGR0020A (land 0.6 × 0.24 at
  (3.3), EP 2.05; KiCad 0.875 × 0.25 at ±1.6875, EP 2.0), DRV8323 RGZ0048A (KiCad ±3.4375, EP 5.15), INA239 DGS (pinout 1 CS … 10 IN+ matches the
  symbol), SN74LVC3G17 DCU, LM74502 DDF, SOT-353 ×2, SOT-23(-5), TSSOP-14, D_SMA/SMB/SOD-123 (pad 1 = K = symbol pin 1 for all six diodes/LED),
  CP_Elec_10x10.5 (pad 1 = "+"), FNR5040S, HoLR custom (p.3: A 4.0, L 1.3 gap, B 3.1 = library), BOOMELE custom (0.74 × 2.5, 6.5 outer, 1.5 gap,
  body 12.7 × 3.4 for 10 per row = library), JST XH S5B-XH-A. No discrepancies beyond round 1's N1/N2 (BQ76907 EP/paste slightly
  under TI's; 0.15 mm mask webs on MSOP/VSSOP).
