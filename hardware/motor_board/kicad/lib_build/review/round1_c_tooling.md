# Round 1 (c): tooling audit of lib_build (check_lib.py / kicadlib.py / build_lib.py)

Scope: can `check_lib.py` report 0 errors while the library is still wrong? Plus independent verification
of `out/` with my own parser and KiCad 10.0.6 (`kicad-cli`, `pcbnew` Python). The scratch scripts were
deleted after the run, as instructed. Each finding says how to reproduce it.

Counts: **1 BLOCKER, 1 MAJOR, 3 MINOR, 8 NOTE**

---

## BLOCKER-1: RGF0040E footprint pad centres are 0.3 mm too far inboard, so all 40 pins short to the EP

`parts.py` reads TI's example board layout (SLVSH07 p.93, drawing 4224999/B) as "outer spans 4.8 (x) and
6.8 (y), so pad centres x = ±2.1, y = ±3.1". On p.93 the extension lines of (4.8) and (6.8) run through
the **centres** of the pad columns and rows, so the centres should be at x = ±2.4 and y = ±3.4. That
matches JLC's EasyEDA `VQFN-40_L7.0-W5.0-P0.50-BL-EP5.7` (centres ±2.40 / ±3.40).

With the current values:
- Left and right pads span x = 1.8 to 2.4 and top and bottom pads span y = 2.8 to 3.4. The EP (pad 41,
  3.7 x 5.7) reaches x = ±1.85 and y = ±2.85, so **every perimeter pad overlaps the EP by 0.05 mm**.
- The corner pads also overlap each other: 1/40, 12/13, 20/21 and 32/33.
- Measured with `pcbnew.FootprintLoad` + `PAD.GetEffectiveShape().Collide()`: 44 overlapping copper pairs
  between pads with different numbers. The other three custom footprints have 0.
- The outer pad edge (2.4 / 3.4) also lies 0.1 mm *inside* the 5 x 7 body, so there is no toe fillet.

Fix: put the pad centres at x = ±2.4 (pins 1-12 and 21-32) and y = ±3.4 (pins 13-20 and 33-40). The pad
size of 0.6 x 0.25 is correct. After that, re-derive the courtyard (pads then reach ±2.7 / ±3.7, so a
0.25 mm clearance means ±2.95 / ±3.95) and the silk corner ticks (currently at ±2.61 / ±3.61, which would
then sit on the pads). The EP and the 12 paste windows are unaffected.

This also resolves check_lib's WARN "pad positions differ by up to 0.30 mm" for this footprint. That
warning was the only signal, and it does not fail the check (see MAJOR-1).

## MAJOR-1: check_lib has no geometric checks, and the one geometric cross-check never fails

- Pad-vs-pin checking compares **sets of numbers** only. Nothing checks for copper overlap, pads outside
  the courtyard, or pad layers. Mutations that still pass with 0 errors:
  - moving RGF pad 1 onto pad 12's position;
  - adding a second copper pad numbered "5";
  - taking F.Cu off the EP (mask only).
- The EasyEDA comparison is the only positional check. It:
  - reports differences as WARN, so the exit status stays 0 (BLOCKER-1 shipped this way);
  - reads from `/home/smance/.claude/jobs/7be37e37/tmp/ee/ee.pretty`, a job scratch directory, and
    `continue`s silently when the file is missing, so once that directory is cleaned the check disappears
    with no note.
- Suggested fix:
  - make overlap between pads with different numbers an ERROR (the `pcbnew` collide test above is about
    10 lines);
  - check that every numbered pad has a copper layer;
  - check that the courtyard contains every pad;
  - vendor the EasyEDA reference footprints into the repo, or print a note when they are absent.

## MINOR-1: pin names are not compared for diodes, the LED or the polarised cap

`compare_names` covers only Reference "U", the MOSFET, BAV99 and BAT54S. The netlist has K/A names for
D1-D5 and D10 and +/- for C1, so this check would cost nothing. Mutation results:
- swapping pin numbers 1<->2 (anode/cathode) in SMBJ20A, SS34 or KT-0603R: MISSED (0 errors);
- swapping 1<->2 in EEHZK1V331P (+/-): MISSED;
- the same swap on BAV99, the MOSFET, DRV8316 or the 74LVC08: CAUGHT.

The current library is correct. My own comparison found every name equal (K/A, +/-, A1/K2/K1A2, G/S/D, and
all IC names). Suggested fix: compare names whenever the symbol's pin names are non-empty and not `Pin_N`.

## MINOR-2: the BOM->symbol mapping and the LCSC field check are circular

`build_lib.lcsc_by_symbol()` and `check_lib` both go through the same `P.BOM_TO_SYMBOL`, and the check
compares LCSC against the value the build copied from that same row. A wrong mapping between two parts
that share a footprint is therefore invisible. Demonstration: swap `"1N4148W"` and `"B5819W"` in the map
(both D_SOD-123), rebuild into scratch and run check_lib. The result is exit 0 with 0 errors, yet the
symbol whose Value and MPN are "B5819W" carries C81598, which is the 1N4148W.

Related gaps:
- BOM rows whose Comment is not in the map are skipped silently.
- The fallback coverage warning only looks at refs starting with U/Q/D/J/L, so if the shunt (RS1-RS4)
  or C1 comments drift out of the map, nothing is reported.

The current mapping is right. I re-derived all 28 symbol<->BOM pairs by LCSC code instead of by the map;
each symbol's Value/MPN matches its BOM comment, and exactly one symbol exists per mapped row. Suggested
fix:
- assert that each symbol's MPN or Value appears in its row's Comment (or keep a separate MPN column);
- report every unmapped BOM row that is not a generic R or C.

## MINOR-3: duplicate numbers and pin types are not checked

- Both pin numbers and pad numbers are compared as sets, so a pin listed twice in one unit and body
  style, or an extra copper pad reusing a signal number, passes (see MAJOR-1).
- Pin electrical types are never compared with anything. The "ERC preview" handles only output-output
  (error) and power_out-power_out (warning). It omits these conflicts that KiCad's default matrix treats
  as errors:
  - output-power_out;
  - output-open_collector;
  - tri_state-power_out;
  - a no_connect pin on a real net.
- Mutations that pass: DRV8323 GHA retyped as power_out, and DRV8316 nFAULT retyped as output.

Against the current library, my own full-matrix recomputation over every netlist net (non-library parts
treated as passive) finds **no conflicts**:
- no no_connect-typed pin sits on a real net;
- 8 of the 16 NC-bucket pins are typed no_connect, and the rest are unused MCU/IC pins with other types
  that need a no-connect flag, as expected;
- no net lacks a driver for an input pin.

Suggested fix: use the full KiCad default matrix in the ERC preview.

---

## NOTES (verified, no action needed unless stated)

1. **KiCad loads everything.**
   - `kicad-cli sym export svg` plotted all 28 symbols (40 unit/body-style SVGs, no errors).
   - `kicad-cli fp export svg` plotted all 4 custom footprints.
2. **The syntax round-trips.**
   - `kicad-cli sym upgrade --force` into scratch, then a semantic diff (properties order-insensitive,
     numbers normalised) showed **zero** semantic changes, only the generator string.
   - `kicad-cli fp upgrade --force` added only uuids, empty Datasheet/Description properties,
     `(embedded_fonts no)` and `(duplicate_pad_numbers_are_jumpers no)`.
   - Pads, layers, paste-only pads (12 x `""` F.Paste), MP pads and the courtyard were unchanged.
   - The footprints are written as `(version 20250114)`, the KiCad 9 format. That is harmless, but
     KiCad 10 will re-save them.
3. **Every Footprint field resolves.** I resolved each through KiCad 10's default table
   (`~/.config/kicad/10.0/fp-lib-table` nests `/usr/share/kicad/template/fp-lib-table`), plus
   `motor_board` mapped to `out/motor_board.pretty`, and loaded each with `pcbnew.FootprintLoad`. All 28
   load; numbered pads equal symbol pins for all 28; each `ki_fp_filters` matches its own footprint.
4. **Independent pin/pad/netlist recompute (my own parser, symbols matched to BOM rows by LCSC):** every
   covered designator's pin set equals the netlist, and every symbol's pin set equals its footprint's
   numbered pads. None of the used footprints has an unnumbered copper pad; the PQFN-8 and RGF `""` pads
   are paste-only.
5. **Flattening of stock and derived symbols is lossless.** All 23 copies match the stock originals in
   `/usr/share/kicad/symbols` exactly for:
   - pin number, name, type, position/orientation and hidden flag (the declared renames aside);
   - unit and body-style sets (e.g. 74LS08: 1_1..4_2 plus 5_0/5_1; 74LVC3G17: 1_1..4_1);
   - per-unit graphics and top-level flags.

   The derived symbols are STM32G474RETx (parent STM32G474R_B-C-E_Tx), AP2112K-3.3 (AP2204K-1.5),
   SS34 (SB120) and 1N4148W (1N4001); none lost pins or units. `ki_keywords` is dropped deliberately.
   For several passives the stock Datasheet is replaced by "".
6. **Hidden pins are benign.**
   - STM32 VSS 31/47/63 (passive) are stacked on the visible VSS 15.
   - HYG015N04LS1C2 S pins 2/3 are stacked on pin 1.
   - 74LVC1G17 pin 1 and AP2112K pin 4 are hidden no_connect pins, and both sit in the netlist's NC
     bucket.
   - The duplicate numbers in SN74LVC08APWR are De Morgan body-style twins, not errors.
7. **The new-symbol geometry is sound.** All pins of the 5 new symbols are on the 1.27 mm grid, none are
   stacked, and every pin's inner end touches the body rectangle.
8. **Other parser observations.**
   - `kicadlib.sym_pins` silently ignores pins in nested symbols not named `*_N_M`. In practice that
     empties the pin set and is caught by the netlist comparison (mutation: CAUGHT).
   - `names_match` accepts `NAME-suffix`; the only users are STM32 `PG10-NRST` and `PB8-BOOT0`, and a
     wrong prefix is caught.
   - The HoLR2512 and BOOMELE custom footprints match their vendor drawings (HoLR p.3: A 4.0 / L 1.3 /
     B 3.1; BOOMELE P.C.B Layout: 6.5 outer, 1.5 gap, 0.74 x 2.5). Their EasyEDA WARNs are EasyEDA's own
     deviations. SH1.0 matches EasyEDA.
   - Cosmetic: FNR5040S220MT description says 1.6 A while the BOM comment says 1.8A. Value is the MPN
     even on Device:R-based shunts.
