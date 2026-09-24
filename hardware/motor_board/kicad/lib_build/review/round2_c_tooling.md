# Round 2 (c): tooling audit of lib_build (check_lib.py / kicadlib.py / build_lib.py / test_check_lib.py)

Scope: can `check_lib.py` still report 0 errors when the library is wrong? I also verified `out/`
independently with my own parser, `pcbnew` and KiCad 10.0.6 `kicad-cli`.

The audit covers HEAD **a7eae22**. That commit landed during the audit and adds the RS4 custom footprint
`R_2512_JIERR_RE_small_electrode`. I re-ran every step below on a7eae22; the results for 779d144 were
the same, except that the JIERR footprint is new. Scratch work was done in the job tmp directory and has
been deleted.

Counts: **0 BLOCKER, 2 MAJOR, 4 MINOR, 7 NOTE**

The library at HEAD is correct as far as the tooling and my recomputation can tell (see the NOTES). Every
finding below is a gap that lets a *future* wrong library pass.

---

## Mutations I planted (scratch copy; `build_lib.py`, then `check_lib.py`)

| Mutation (realistic library error) | check_lib |
|---|---|
| RGF pads 1-12 without `F.Paste` (unsoldered pins) | **passes** |
| RGF pad 1 on `B.Cu B.Paste B.Mask` (pad on the wrong side) | **passes** |
| RGF pad 1 with `B.Cu F.Paste F.Mask` | **passes** |
| RGF EP paste window moved to x = 2.3 (on top of pads 21-24, a bridge) | **passes** |
| All 12 RGF EP paste windows deleted (EP not soldered) | **passes** |
| RGF signal pad 5 rotated 90° (0.25 x 0.6) | caught (gap 0.075 mm) |
| HoLR pad rotated (4.0 x 3.1 instead of 3.1 x 4.0) | **passes** |
| HoLR pads 1 mm further out each side (x = ±3.2) | **passes** |
| JIERR land replaced by the HoLR land (3.1 x 4.0 at ±2.2) | **passes** |
| BOOMELE odd/even columns swapped (mirrored board-to-board pinout) | **passes** |
| BOOMELE numbering reversed (pin 1 at the bottom) | **passes** |
| BOOMELE pitch 1.0 instead of 1.27 | **passes** |
| SH1.0 pads 1/2 swapped | caught (JLC comparison) |
| 74LVC08 pin 3 (1Y) moved from unit 1 into unit 2 | **passes** |
| DRV8316 VM pin 9 made hidden (a `power_in` pin) | **passes** |
| DRV8316 VM pin 9 listed twice at two positions | **passes** |
| DRV8316 SOA typed input; nFAULT typed output; DRV8323 GHA typed power_out | **pass** (no conflict on their nets) |
| WAFER connector symbol: numbers of Pin_1/Pin_2 swapped | **passes** |
| BOM map 1N4148W<->B5819W swapped **and** their LCSC codes swapped in parts.py | **passes** |
| MMSZ5242B built from `Device:D_Schottky` instead of `D_Zener` | **passes** |
| BAV99 footprint SOT-23 -> SOT-23-3 (BOM unchanged) | caught |
| INA239 MSOP-10 -> MSOP-10-1EP (BOM unchanged) | caught |
| Symbol LCSC field only changed in `out/` | caught |
| A vendored EasyEDA reference file deleted | caught |

`test_check_lib.py` passes: all 12 planted mutations are caught and the baseline exits 0 (run with
`TMPDIR` pointed at scratch). `check_lib.py` on HEAD reports 28 symbols, 0 errors, 0 warnings and 20 notes.

---

## MAJOR-1: a documented deviation exempts a footprint from every JLC comparison, so pinout errors pass

`check_lib.check_footprint_geometry` turns *any* difference into a note when the footprint is listed in
`parts.EASYEDA_DEVIATIONS`:

```python
dev = P.EASYEDA_DEVIATIONS.get(name)
if diffs and not dev: errors.append(...)
elif diffs: notes.append(...documented deviation...)
```

- Three of the five custom footprints are listed: `BOOMELE_1.27-2x10P_SMD`, `R_2512_HoLR_1-4mR` and
  (new in a7eae22) `R_2512_JIERR_RE_small_electrode`.
- For these three, the only geometric checks left are the copper gap (0.15 mm or more) and courtyard
  containment. The builder derives the courtyard from the same spec, so that check follows any spec
  error.
- Result: a mirrored or reversed pinout, or a wrong pitch, on **J1** (the inter-board connector) passes
  with 0 errors. So do a rotated or relocated shunt land, or the HoLR land used for the JIERR part (see the
  table).
- `parts.py` says "every deliberate deviation (check_lib fails on any other)". That is not true for the
  footprints that are listed.

Suggested fix:
- Keep the numbering and topology check even when a deviation is documented. After centring and the
  best rotation, each of our pads' nearest JLC pad must carry the same number. Mirroring or reversing J1
  then fails, because the columns sit at ±2.0 vs ±2.3 and swap sides.
- Compare the listed footprints with the values recorded in `parts.FOOTPRINTS` (pitch, x, pad size)
  instead of skipping them.
- Or record each deviation as the expected numbers plus a tolerance, not free text.

## MAJOR-2: pad layer and paste checks accept back-side pads, missing paste and moved or missing EP paste

The layer check is `any(l.endswith("Cu"))` and `any("Mask" in l)`:
- `B.Cu` and `B.Mask` satisfy it.
- `F.Paste` is never required.
- Unnumbered (paste-only) pads are checked only for courtyard containment.

So these mutations all pass, and each one breaks assembly:
- signal pads with no paste;
- a pad moved to the back side;
- the RGF EP paste windows deleted (the DRV8316 thermal pad is left unsoldered);
- a paste window moved onto signal pads (a solder bridge).

Suggested fix:
- For SMD footprints, require every numbered SMD pad to have `F.Cu` and `F.Mask`, and `F.Paste` unless
  the pad is an EP that has windows.
- Require every paste-only pad to lie inside a copper pad of one number (the EP), not to overlap any
  other number, and require the EP paste coverage to fall in a stated band (TI RGF: 12 x 1.05 x 1.15 =
  69 %).

## MINOR-1: symbol unit and body-style structure is not checked

`kicadlib.sym_pins` records `unit`, but `check_lib` never uses it:
- Moving 74LVC08 pin 3 (1Y) from gate 1 into gate 2 passes. The netlist is still right by number, but
  the gate-1 drawing loses its output and gate 2 gains a second one.
- A same-name duplicate pin at a second position (VM 9 twice) also passes.

Suggested fix:
- For stock copies, assert that each (unit, body style) keeps the same pin set as the stock source. Only
  names may change, through `rename`.
- For all symbols, assert that repeated numbers inside one unit and body style are stacked, meaning they
  sit at the same position.

## MINOR-2: hidden `power_in` pins are not flagged

KiCad's schematic editor connects a hidden power-input pin to a global net with the pin's name.
- Hiding DRV8316 VM (pin 9) passes check_lib. In a schematic, that pin would silently join a net called
  "VM" rather than the wired one.
- HEAD has **no** hidden `power_in` pins. The only hidden pins are STM32 VSS 31/47/63 (passive, stacked),
  HYG015 S 2/3 (passive, stacked), 74LVC1G17 pin 1 and AP2112K pin 4 (both `no_connect`).

Suggested fix: make any hidden `power_in` pin an ERROR.

## MINOR-3: symbol identity is never compared with the BOM line

Round 1's MINOR-2 is only half fixed.
- LCSC is now compared three ways (symbol, `parts.py`, BOM), but the symbol's Value/MPN is never compared
  with the BOM Comment, and neither is the stock source symbol.
- If the map swap is accompanied by the matching LCSC swap in `parts.py`, it passes: the symbol named
  and valued "B5819W" then carries the 1N4148W's C81598.
- A Zener built from `D_Schottky` also passes.

Suggested fix: emit an MPN column from `design/motor_board.py` into `bom.csv` and compare it with the
symbol's MPN. The Comment alone is not enough: "LED red", "330uF 35V hybrid polymer" and the three shunt
lines do not contain the MPN. Alternatively, keep a second MPN→LCSC table that does not go through
`BOM_TO_SYMBOL`.

## MINOR-4: seven vendored JLC references are unused, so stock footprints get no geometry cross-check

`ref/easyeda/` holds 12 files. `EASYEDA_REF` uses 5 of them, one per custom footprint. Nothing in the repo
reads the other 7 (the only mention is `review/round1_b_footprints.md`):
- `DFN-8…`
- `SC-70-5…`
- `SOT-23-8…`
- `TSSOP-14…`
- `VQFN-20…`
- `VQFN-48…`
- `VSSOP-10…`

A stock footprint is checked only by name equality with `bom.csv`, and both names are hand-chosen.

I ran the comparison myself: pad centres after centring and best rotation, no mirroring.

| Stock footprint | JLC ref | max centre diff | Numbering |
|---|---|---|---|
| SOT-353_SC-70-5 | SC-70-5_L2.1… | 0.002 mm | same |
| Texas_DDF0008A_SOT-8 | SOT-23-8_L2.9… | 0.040 mm | same |
| TSSOP-14_4.4x5mm_P0.65mm | TSSOP-14_L5.0… | 0.062 mm | same |
| QFN-20-1EP_3.5x3.5mm_EP2x2mm | VQFN-20_…EP2.1 | 0.062 mm | same |
| Texas_RGZ0048A_VQFN-48 | VQFN-48_…EP5.1 | 0.027 mm | same |
| MSOP-10_3x3mm_P0.5mm | VSSOP-10_L3.0… | 0.25 mm (toe only: KiCad ±2.1 x 1.5 long, JLC ±2.35 x 1.3) | same |
| PQFN-8-EP_6x5mm_Generic | DFN-8_L5.9… | not comparable | JLC numbers 1-8 + EP 9; KiCad merges drain into pad 5 (the symbol matches KiCad's) |

So the stock choices agree with JLC today. Suggested fix: add these pairs to the geometry comparison,
with a PAD_RENAME entry for the PQFN.

---

## NOTES

1. **KiCad loads everything (HEAD).**
   - `kicad-cli sym export svg` plotted all 28 symbols (40 unit and body-style SVGs, no errors).
   - `kicad-cli fp export svg` plotted all 5 custom footprints, including the new JIERR one.
   - `kicad-cli sym upgrade --force` changed no pin (number, name, type, unit, hidden) and no property of
     any of the 28 symbols. I checked this at 779d144; a7eae22 changes only the RE2512F3R001 Footprint
     field.
2. **Every Footprint field resolves.** I resolved each through KiCad 10's own
   `~/.config/kicad/10.0/fp-lib-table` (which nests the template table), plus `motor_board` pointing at
   `out/motor_board.pretty`. `pcbnew.FootprintLoad` loaded all 28.
3. **Independent recompute (own s-expression parser; symbols matched to BOM rows by LCSC, not through
   `BOM_TO_SYMBOL`).**
   - All 28 BOM lines and all 43 designators map to exactly one symbol.
   - Symbol pin numbers equal netlist pin numbers for every designator.
   - Names agree for every non-connector pin (K/A, +/-, A1/K2/K1A2, G/S/D, all IC names). Connector
     symbols use Pin_N = N, and SH1.0 `MP` = MountPin.
   - Pin numbers equal the footprint's numbered copper pads for every symbol. No footprint has an
     unnumbered copper pad.
   - Each `ki_fp_filters` equals its footprint.
   - Checked by eye against the BOM comments, every symbol's MPN is the right part for its line.
4. **Full KiCad default ERC matrix, run over every netlist net** (non-library parts treated as passive):
   no conflicts.
   - check_lib's own rules still lack output×open_collector, output×open_emitter and
     tri_state×power_out. No net at HEAD can trigger them; for example, each nFAULT net has one driver,
     a pull-up and an MCU pin.
   - Pin electrical types are not compared with any reference. They are exercised only through
     conflicts, so a wrong type on a net without a conflict passes (see the table).
5. **Reproducibility.**
   - Re-running `build_lib.py` at HEAD reproduces `out/` byte for byte.
   - Re-running `design/motor_board.py` reproduces `netlist.csv` and `bom.csv` byte for byte ("checks: OK").
   - check_lib does not itself detect a stale `out/`. The three-way LCSC and footprint-name comparisons
     cover most of what staleness could hide.
6. **Connector symbols.** Pin names are not compared for J parts (by design), and nothing ties Pin_N to
   number N, so a renumbered generic connector symbol passes (see the table). It holds for all four
   today.
7. **Housekeeping.** `test_check_lib.py` copies `design/` and `lib_build/` into the system temp directory
   (`tempfile.mkdtemp`) for each of its 13 runs. Set `TMPDIR` when disk is tight. The netlist names come
   from `design/motor_board.py`, which is typed by hand from the same datasheets as `parts.py`. The two
   are independent transcriptions, not independent sources, so a shared misreading of a datasheet would
   pass.
