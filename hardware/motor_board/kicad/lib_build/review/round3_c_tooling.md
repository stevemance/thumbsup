# Round 3 (c): tooling audit of lib_build (check_lib.py / test_check_lib.py / build_lib.py / kicadlib.py)

Scope: can `check_lib.py` still pass a wrong library, does it reject a correct one for the wrong reason,
and is the library at HEAD right when checked independently? Audited **HEAD c568dc2**.

The worktree had uncommitted edits from another session while I worked: the RGF pin-1 dot, the JIERR
Fab body and a comment move in `parts.py`. So I ran everything on a `git archive HEAD` export in the job
scratch directory, which I deleted afterwards.

Counts: **0 BLOCKER, 1 MAJOR, 1 MINOR, 8 NOTE**

The library at HEAD is correct: everything I recomputed agrees (see NOTES 1-3). The MAJOR is a checker
gap that would let a reversed sensor connector through.

---

## Runs at HEAD

- `test_check_lib.py`: all 23 mutations are caught, the baseline exits 0 and it prints `ALL CAUGHT`
  (run with `TMPDIR` pointed at scratch).
- `check_lib.py`: 28 symbols, 0 errors, 0 warnings, 28 notes.
- `build_lib.py` reproduces the committed `out/` byte for byte.

## Mutations I planted (HEAD export: edit, then rebuild or edit `out/`, then run `check_lib.py`)

| Mutation | check_lib |
|---|---|
| SH1.0 (J2/J3) signal numbering reversed: pin 1 at +x, tabs unchanged | **passes** |
| SH1.0 whole footprint mirrored in x | **passes** |
| SH1.0 signal row moved 1.0 mm toward the tab pads | **passes** |
| SH1.0 all pads shifted 1 mm (origin off the body) | caught (courtyard) |
| RGF mirrored in x | caught (JLC compare, 4.8 mm) |
| RGF all pads shifted 0.5 mm | caught (courtyard) |
| RGF EP paste cut to 6 windows (34 %) | caught (coverage band) |
| HoLR land rotated onto the y axis | caught (courtyard / drawing) |
| RGF `(attr smd exclude_from_pos_files exclude_from_bom)` / `(attr smd dnp)` / `(attr through_hole)` | **passes** |
| DRV8316 symbol `(in_bom no)` / `(on_board no)` | **passes** |
| RGF footprint-level `solder_paste_margin -0.5`; pad-level paste margin -0.2; pad mask margin 0.3 | **passes** |
| RGF pin-1 silk dot / Fab chamfer at the opposite corner; BOOMELE pin-1 bar at the bottom | passes (NOTE 5) |
| DRV8316 VM pin 9 duplicated at a second, non-stacked position | passes (NOTE 6) |
| MMSZ5242B built from `D_Schottky`; DRV8323 GHA typed `input` | passes (NOTE 6) |
| INA239 line's symbol renamed `INA229AIDGSR` (LCSC still C2876522) | passes (NOTE 7) |
| LM74502 symbol renamed `LM74502HDDFR` | caught (MPN) |
| `STOCK_EASYEDA_REF` TSSOP-14 entry deleted | passes: the check is silently skipped (NOTE 8) |
| HoLR `FOOTPRINTS` and `DRAWING` both changed to gap 1.6 | passes (expected: both are transcriptions) |
| Deviation added for SH with no `DRAWING` entry | caught |
| HoLR pad 2 only 3.0 tall, top edges aligned | passes (only pad 1's height is measured; the builder makes both pads from one spec) |
| EP paste windows numbered `41`, the KiCad stock convention | rejected (NOTE 8) |

---

## MAJOR-1: the JLC comparison drops `MP` pads, so a reversed single-row connector passes

In `check_footprint_geometry`, the arrangement comparison uses
`common = [n for n in set(a) & set(b) if n != "MP"]`. It then centres and tries four rotations.

For `SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB`, that leaves pads 1-6, which form one straight row. A single row
rotated by 180° lands on itself with the numbering reversed. So each of these passes with 0 errors:

- **Pin order reversed** (pin 1 at the +x end). This is exactly the "confirm the pin-1 end" risk that
  BOM.md flags for J2/J3. It would swap VS (pin 1) with TEMP (pin 6) and GND (pin 2) with S3 (pin 5) on
  both sensor connectors.
- **Footprint mirrored in x.**
- **Signal row moved relative to the tab pads.** The tabs are never compared by position, only for
  containment in a courtyard that the builder derives from the same spec.

The SH footprint has no `EASYEDA_DEVIATIONS` entry, so `check_drawing` does not run for it either. The
other custom footprints are not affected:
- RGF: a mirror is not a rotation.
- BOOMELE: `check_drawing` enforces odd pins on the left and pin 1 at the top.
- Two-pad resistors: symmetric by nature.

HEAD is correct. Our SH footprint equals JLC's within 0.05 mm, and it also matches KiCad's own
`JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal`, an independent source: pin 1 at -x, signal row at -y,
tabs at +y.

Suggested fix:
- Include the `MP` pads in the centring and rotation.
- Match the `MP` pads as a set: each of ours must lie within tolerance of some JLC `MP` pad under the same
  transform.
- Add a test mutation that reverses the SH signal numbering.

## MINOR-1: attributes that remove a part or its paste from the fab outputs are not checked

A footprint `attr` of `exclude_from_pos_files`, `exclude_from_bom`, `dnp` or `through_hole` passes. So do
a symbol with `in_bom no` or `on_board no`, and a footprint- or pad-level `solder_paste_margin` or
`solder_mask_margin`.

Each of these silently changes the JLC BOM, CPL or paste layer:
- The part is not placed.
- The RGF pins get no paste.
- The mask web between 0.5 mm-pitch pins disappears.

The builder hard-codes the right values, so today this can only come from hand-editing `out/` or from a
stock source, which makes it MINOR. HEAD is clean:
- pcbnew reports every footprint as SMD with no exclude or DNP flags, except J4 (JST XH), which is THT
  by design.
- All 28 symbols have `in_bom yes` and `on_board yes`.
- No custom footprint sets any margin or clearance.

Suggested fix: require `attr smd` with no exclusion flags on custom footprints, `in_bom yes` and
`on_board yes` on every symbol, and no `solder_*_margin` unless it is listed.

---

## NOTES

1. **`parts.DRAWING` matches the vendor drawings.** I rendered each page and read the dimension
   arrows.
   - **HoLR2512 p.3, 1-4 mΩ row:** A 4.0, L 1.3, B 3.1. L is the gap between the pads' inner edges and B
     is the pad length, so this matches `pad=(3.1, 4.0), gap=1.3`.
   - **JIERR RE2512 p.5, small electrode:** a 4.0, b 2.1, L 4.1, so it matches `pad=(2.1, 4.0), gap=4.1`.
     The JIERR p.1 part-number key confirms that the "L" suffix means large electrode, so RE2512F3R001 is
     the small-electrode part.
   - **BOOMELE "P.C.B Layout":** pitch 1.27, pad 0.74 wide, 6.5 overall, 1.5 between rows. The 2.5 mm
     pad length is derived as (6.5 - 1.5) / 2, not printed.
   - The drawing does not number the pins. The odd-left, pin-1-top convention comes from KiCad's
     `PinHeader_2x10_P1.27mm_Vertical_SMD`, and our footprint matches it. JLC's reference agrees under a
     90° rotation, not a mirror.
2. **KiCad 10.0.6 loads everything.**
   - `kicad-cli sym export svg` plotted all 28 symbols (40 SVGs).
   - `kicad-cli fp export svg` plotted all 5 custom footprints.
   - `kicad-cli sym upgrade --force` changed no pin (number, name, type, unit, body style, hidden) and no
     property.
   - Every Footprint field loads through `pcbnew.FootprintLoad`. `motor_board` points to `out/`, and the
     10 stock nicknames are all in the KiCad template table that `~/.config/kicad/10.0/fp-lib-table`
     nests.
3. **Independent recompute** (own s-expression parser for symbols, pcbnew for footprints, BOM rows
   matched to symbols by LCSC and not through `BOM_TO_SYMBOL`).
   - All 28 BOM lines with a library part map to exactly one symbol, 43 designators in all, and no
     symbol is unused.
   - For every designator, the symbol pin numbers equal the netlist pin numbers and equal the numbered
     copper pads loaded by pcbnew. No footprint has an unnumbered copper pad.
   - Every pin name agrees with the netlist, except on connectors (Pin_N against signal names) and on
     plain resistors (unnamed pins against 1/2).
   - No repeated pin number sits at two positions.
   - Hidden pins are STM32 VSS 31/47/63 and HYG S 2/3 (passive, stacked) and the NC pins of the 74LVC1G17
     and AP2112K (`no_connect`). None is `power_in`.
4. **No false positives at HEAD.**
   - The new checks (layers, EP paste 69 %, drawing values, JLC arrangement, units, MPN) pass the correct
     library.
   - The closest margin is MSOP-10 against JLC's VSSOP-10: 0.25 mm against a 0.35 mm limit, a toe-length
     difference only.
5. **Pin-1 markers (silk dot, Fab chamfer, header bar) are not checked.** At HEAD all three are at the
   pin-1 corner. JLC places by copper and its own data, so this affects only hand assembly and
   inspection.
6. **Carried over from round 2 (no board effect).**
   - Pin electrical types are exercised only through ERC conflicts.
   - A stock copy's source symbol (Zener against Schottky) is not compared.
   - A non-stacked duplicate pin passes.
7. **MPN check.** It is a substring match against BOM.md rows that contain the LCSC code. Those rows also
   name the alternates, so a symbol named `INA229AIDGSR` passes on the INA239 line. `LM74502HDDFR` is
   caught only because BOM.md writes `LM74502H` without "DDFR". The LCSC code is compared three ways, and
   that decides what JLC fits, so only the MPN text could go wrong.
8. **Checker configuration and style assumptions.**
   - A footprint missing from `STOCK_EASYEDA_REF` is skipped silently. `DFN-8_L5.9…` in `ref/easyeda/` is
     still unused, and there is no PQFN rename.
   - EP detection is hard-coded to pad numbers 41, 49 and 21 with a width over 1.5 mm.
   - EP paste windows numbered with the EP number (KiCad's stock convention) are rejected as "lacks
     F.Cu" and "used 13 times".
   - `check_drawing` rejects a correct header footprint drawn rotated.
   - All of these are conservative or only a matter of configuration. None of them is wrong at HEAD.
