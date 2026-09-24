# Round 1 (B): footprint review, motor_board parts library

Scope: every symbol's `Footprint` in `out/motor_board.kicad_sym`, the 4 custom footprints in
`out/motor_board.pretty/`, and the KiCad 10 stock footprints they point to. I checked each one against
the manufacturer drawings in `hardware/motor_board/datasheets/`, rendering them at 300-400 dpi and measuring
where needed. I checked JLC's EasyEDA footprints (`ee.pretty`) as a second opinion but did not treat them as the reference.

**Counts: 1 BLOCKER, 0 MAJOR, 1 MINOR, 9 NOTE.**

Pad ↔ pin check (script): for all 28 symbols, every symbol pin number has a pad and every numbered pad
has a pin. There are no missing or extra pads (U41/MP/EP included).

---

## BLOCKER

### B1. TI_RGF0040E (DRV8316C): perimeter pads are 0.3 mm too far inboard. All 40 pads short to the thermal pad, and the corner pads short to each other

- Footprint: `motor_board:TI_RGF0040E_VQFN-40-1EP_5x7mm_P0.5mm_EP3.7x5.7mm`. Pads 1-12/21-32 are at
  x = ±2.1 and pads 13-20/33-40 at y = ±3.1 (size 0.6 × 0.25). EP 41 is 3.7 × 5.7 at 0,0.
- Source: SLVSH07 (DRV8316C.pdf) p.93, "EXAMPLE BOARD LAYOUT RGF0040E". The **(4.8)** and **(6.8)**
  dimensions run between the dash-dot **pad centrelines**, not between the pads' outer edges. On the 400 dpi render, the extension
  lines of (4.8) pass through the middle of pad 1 and pad 32. Measured on the 110 dpi render:
  EP (3.7) = 195 px → 52.7 px/mm; the left pad column spans 335-367 px (centre 351) and the right column 585-615 px
  (centre 600). 249 px / 52.7 = 4.72 ≈ 4.8 centre-to-centre, and pad length 32 px = 0.6. The package
  (p.92) is 5.0 × 7.0 with terminal length 0.3-0.5, so the terminals run from 2.0-2.2 out to 2.5 from centre. TI's pad
  (centre 2.4, 2.1…2.7) covers them. The library pad (1.8…2.4) stops 0.1 short of the body edge and runs under the EP.
- Consequence (computed from the generated file): **all 40 signal pads overlap EP 41 by 0.05 mm**
  (pad inner edge x = −1.80 vs EP edge −1.85; y = −2.80 vs −2.85). Pads 1/40, 12/13, 20/21 and 32/33 also overlap each other by
  0.075 × 0.075 mm. As built, every DRV8316C pin (VM, OUTx, SPI…) would be copper-merged with PGND. The board would not work.
- `parts.py` has the misreading: "outer spans 4.8 (x) and 6.8 (y) → pad centres x = ±2.1, y = ±3.1".
- JLC EasyEDA `VQFN-40_L7.0-W5.0-P0.50-BL-EP5.7` has the same pattern rotated 90° with pad centres at **±3.40 / ±2.40**,
  0.6 × 0.25, EP 3.7 × 5.7. JLC's is correct and agrees with TI.
- Fix: pad centres x = ±2.4 (pins 1-12, 21-32) and y = ±3.4 (pins 13-20, 33-40). EP, pitch, pad size and the 12
  paste windows (1.05 × 1.15 at x 0/±1.25, y ±0.675/±2.025, which match p.94) stay as they are. Pad-to-EP gap then = 0.25 mm,
  as in TI's drawing. See m1 for the courtyard/silk that follows. check_lib.py should gain a pad-overlap
  test, because it did not catch this.

## MINOR

### m1. RGF0040E courtyard and silk must move with the B1 fix
The courtyard is ±2.75 × ±3.75. After the fix the pads reach ±2.7 / ±3.7, leaving 0.05 mm margin (KiCad default is
0.25). Regenerate the courtyard at about ±2.95 × ±3.95. The pin-1 silk tick at x = −2.9 (y −2.75…−3.3) would be 0.2 mm from the relocated pad 1 (edge −2.7). Move it outward along with the other silk corner marks (±2.61 × ±3.61, which would fall inside the new pad extents).

---

## Custom footprints: verified (no error)

| Footprint | Drawing | Library | JLC EasyEDA | Verdict |
|---|---|---|---|---|
| R_2512_HoLR_1-4mR | HoLR2512 datasheet p.3 "Recommended Solder Pad", 1~4 mΩ row: A 4.0, L (gap) 1.3, B 3.1 | 3.1 × 4.0 at ±2.2 (gap 1.3, outer 7.5) | RES-SMD_L6.4-W3.2-A: 3.0 × 3.4 at ±2.55 (gap 2.1) | Library matches the vendor. EasyEDA is a generic 2512 land, and its gap 2.1 does not follow the 1-4 mΩ recommendation for the 2.0 mm terminals (p.2 C = 2.0 ± 0.2). **Library is right.** |
| BOOMELE_1.27-2x10P_SMD | Vendor "P.C.B Layout": 0.74 wide, 1.27 pitch, 6.5 ± 0.1 outer, 1.5 row gap → pads 2.5 long | 0.74 × 2.5 at x ±2.0, y ±0.635…±5.715; odd column x<0, pad 2 opposite pad 1 | HDR-SMD_20P…LS5.5: 0.8 × 2.5 at ±1.68 (outer 5.86, gap 0.86), same odd/even pairing (rotated 90°) | Library follows the labelled dimensions. Note: the drawing is not to scale (measured outer ≈ 6.0 mm at 71.9 px/mm), but the labels govern. Both lands cover the 5.5 mm foot span. **Library is right per vendor.** |
| SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB | XUNPU drawing "P.C.B LAYOUT" at 400 dpi, 104.2 px/mm: signal 0.5 × 1.70, pitch 1.0 (5.00 pin 1-6 centres); tabs 1.20 × 2.50, inner edge 0.50 beyond pad-6 centre → x ±3.6; overall 5.50 → signal centre −1.7, tab centre +1.7 (measured separation 3.39) | identical | CONN-SMD_6P…: identical (tabs numbered 7/8 instead of MP) | Correct. The pin-1 end is not marked on the XUNPU drawing. The JST SH layout (SM06B_JST_SH.pdf p.1, "viewed from the connector mounting surface", side entry) puts No.1 circuit at the left with the signal row on the far side from the tabs, which matches pad 1 at x = −2.5, y = −1.7 (and KiCad's JST_SH_SM06B). See N3. |
| TI_RGF0040E | see B1 | **wrong** | right | B1 |

Pin-1 check for RGF0040E (apart from B1): pin 1 top-left, 1-12 down the long left side, 13-20 along the bottom L→R, 21-32 up,
33-40 along the top R→L (40 at top-left). This matches the p.93 top view. EP 3.7 × 5.7 matches p.93 and the package EP (3.6-3.8 × 5.6-5.8).
Paste coverage 12 × 1.05 × 1.15 / (3.7 × 5.7) = 69 %, which matches p.94.

## Stock footprints: verified against the purchased part

| Part | Stock footprint | Evidence | Result |
|---|---|---|---|
| BQ76907RGRR | QFN-20-1EP_3.5x3.5mm_P0.5mm_EP2x2mm | BQ76907 p.62-64 RGR0020A: body 3.5, EP 2.05 ± 0.1, land 0.6 × 0.24 at (3.3) centres, EP land 2.05, 4 × 0.92 paste (81 %) | KiCad pads 0.875 × 0.25, 1.25…2.125 from centre, which covers the TI land (1.35…1.95) and the terminal (L 0.3-0.5). Numbering/pin 1 match. EP 2.0 vs 2.05 and paste 66 % vs 81 %: N1 |
| DRV8323RHRGZR | Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm | DRV8323 p.93-95 RGZ0048A: EP 5.15, land 0.6 × 0.24 at (6.8) centres; paste 67 % | KiCad 0.875 × 0.25 at ±3.4375 (3.0…3.875) covers TI 3.1…3.7. EP 5.15. Paste 16 × 1.04² = 65 %. OK |
| INA239AIDGSR (DGS) | MSOP-10_3x3mm_P0.5mm | INA239 p.41-42 DGS0010A: span 4.75-5.05, land 1.45 × 0.3 at (4.4) centres | KiCad 1.5 × 0.35 at ±2.1 (1.35…2.85) vs TI 1.475…2.925, which covers the foot (0.4-0.7). OK (0.15 mm pad gap: N2) |
| SN74LVC3G17DCUR | VSSOP-8_2.3x2mm_P0.5mm (tag Texas_DCU0008A) | TI DCU0008A (from the current TI SN74LVC3G14 datasheet, same package): span 3.0-3.2, land 0.85 × 0.3 at (3.1) centres | KiCad 1.25 × 0.35 at ±1.4 (0.775…2.025) covers TI 1.125…1.975. Pin order 1-4 left, 5-8 right. OK |
| LM74502DDFR | Texas_DDF0008A_SOT-8_1.6x2.9mm_P0.65mm | LM74502 p.28 DDF0008A: 8 × 1.05 × 0.45 at (2.6), pitch 0.65 | Exact match (±1.3, 1.05 × 0.45). OK |
| TPS22945DCKR, 74LVC1G17SE-7 | SOT-353_SC-70-5 | SC-70-5 / SOT353. TPS22945 pin table: 1 VOUT, 2 GND, 3 OC, 4 ON, 5 VIN | Standard pin-1 corner, pads 1.025 × 0.35 at ±0.8375 cover the leads. OK |
| HYG015N04LS1C2 | PQFN-8-EP_6x5mm_P1.27mm_Generic | Datasheet p.1: pin 1 corner, S S S G on one side, D D D D + tab on the other. p.7: 5.2 × 6.15, EP 4.25 × 3.82, H 0.5, K 1.26, L 0.58, b 0.4, e 1.27 | Pads 1-4 (1.15 × 0.7 at x −2.725, 1.27 pitch) are the S,S,S,G row. Pad 5 (custom) is the tab plus the merged drain-lead strip (x −1.1…3.5, width 4.2/4.7). Package EP spans −1.235…+2.575 and the drain tips reach 3.075, so the pad covers them. Pads 1-3 = S, 4 = G, 5 = D, which matches the symbol. OK (N4) |
| EEHZK1V331P (size G) | CP_Elec_10x10.5 | Panasonic p.2 size G: φ10, L 10.2, A/B 10.3, H 12.0 max, P 4.6, W 0.9 | Leads run 2.3…6.0 from centre. KiCad pads 4.4 × 2.5 at ±4.2 (2.0…6.4) cover them. Pad 1 = "+" = C_Polarized pin 1. OK |
| FNR5040S220MT | L_Changjiang_FNR5040S | Changjiang p.2 FNR5040S recommended land: a 2.3, b 1.4, c 4.2 | KiCad 1.4 × 4.2 at ±1.85 (gap 2.3). Exact. OK |
| SS34 (MDD) | D_SMA | SS34_MDD p.3: SMA/DO-214AC, suggested pad 1.52 × 1.68, C 3.93, E 5.45 | KiCad 2.5 × 1.8 at ±2.0 is a superset. Pad 1 = K = cathode band. OK |
| SMBJ20A (BORN) | D_SMB | SMB package | KiCad D_SMB pad 1 = K (band). Unidirectional TVS, symbol pin 1 K. OK |
| 1N4148W, B5819W, MMSZ5242B | D_SOD-123 | All three datasheets are SOD-123 (not SOD-323) | Pad 1 = K = band. Symbol pin 1 = K for all three. OK |
| KT-0603R | LED_0603_1608Metric | KT-0603R p.2: 1.6 × 0.8; pad 0.70 × 0.70-ish, gap 0.70; vendor terminal **① = "+" (anode)**, **② = cathode** (green corner mark and the diode symbol) | KiCad pad 1 = K, symbol pin 1 = K, so the net-to-terminal mapping is right. The vendor number reversal only affects JLC's placement rotation (N5). OK |
| 25121WF100LT4E | R_2512_6332Metric | UNI-ROYAL datasheet dimension table, 2512: L 6.35, W 3.20, top terminal 0.60 ± 0.25, bottom 0.50 ± 0.20 | Standard. OK |
| RE2512F3R001 | R_2512_6332Metric | JIERR p.3: suffix "L" = large electrode (E 2.2). **No suffix = small electrode E 1.0 ± 0.2**; 3 W, R001 is in the small-electrode range | Terminal runs 2.2…3.2 from centre and the pad runs 2.35…3.575, so the pad covers 0.85 of the 1.0 terminal. OK for the part as ordered (N6) |
| S5B-XH-A | JST_XH_S5B-XH-A_1x05_P2.50mm_Horizontal | Named exactly for the part | Pads 1-5, 2.5 pitch, pad 1 rectangular. OK |
| STM32G474RET6, SN74LVC08APWR, AP2112K-3.3, BAV99, BAT54S | LQFP-64 / TSSOP-14 / SOT-23-5 / SOT-23 | Standard packages; symbol pins (AP2112K 1 VIN 2 GND 3 EN 4 NC 5 VOUT; BAV99/BAT54S 1 A1, 2 K2, 3 K1A2) match the vendor pinouts | OK |

## NOTES

- **N1** BQ76907: the KiCad EP is 2.0 × 2.0, and TI's land and package-nominal EP are 2.05. Paste is 4 × 0.81² (66 %) vs TI 81 %.
  Solderable as is. If you want more thermal-pad solder, change the paste to TI's 4 × 0.92.
- **N2** MSOP-10 / VSSOP-8 stock pads are 0.35 wide at 0.5 pitch, leaving 0.15 mm copper gaps. That is at JLC's standard mask-web limit,
  so the mask will likely be ganged over the row. This is normal for these stock footprints.
- **N3** XUNPU SH connector: the drawing has no pin-1 mark. The library assumes JST SM06B numbering (JST p.1). BOM.md already
  says to confirm against a mating SHR-06V-S cable.
- **N4** HYG015 PQFN: the library footprint is rotated 90° relative to JLC's `DFN-8_L5.9-W5.2…` (pins on the long edges, top/bottom).
  Expect a CPL rotation correction.
- **N5** KT-0603R: the vendor calls the anode pin 1, and KiCad calls the cathode pad 1. JLC's own footprint may therefore be 180° off from the
  library's. Check the cathode mark in the JLC placement preview (BOM.md already says this).
- **N6** RE2512F3R001: correct only for the small-electrode (no "L" suffix) variant. If LCSC C46961745 is actually the large-electrode
  (E 2.2 mm) build, the 6332 land covers only 0.85 mm of each 2.2 mm terminal. In that case use the HoLR-style 1.3 mm-gap land. Check the LCSC
  photo/drawing before ordering.
- **N7** BOOMELE: the part is symmetric and has no pin-1 feature. The pad numbering only has meaning together with the mirrored female socket on
  the compute board (BOM.md). Make sure that board's footprint uses the mirror of this numbering.
- **N8** DRV8316C RGF: JLC's EasyEDA footprint is rotated 90° from the library's (pin 1 bottom-left, long axis horizontal). Expect a CPL
  rotation correction.
- **N9** RGF0040E EP has copper + mask only, with separate paste windows as intended. The stock QFN footprints use the same scheme. No issue.
